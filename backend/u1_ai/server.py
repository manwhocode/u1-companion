"""Loopback-only HTTP sidecar; nginx supplies an unspoofable local-origin header."""
import base64
import io
import zipfile
import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit
from .storage import ROOT, Settings, ident, read, atomic, audit
from .gateway import Gateway
from .agent import Agent
from .accounts import Accounts
from .codex_account import instance

PREFIX = '/u1-ai/api/'


class Application:
    def __init__(self, root=ROOT, moon=None, client_factory=None):
        self.root = Path(root)
        self.settings = Settings(root)
        self.accounts = Accounts(root)
        self.gateway = Gateway(self.settings, root, moon)
        self.agent = Agent(self.settings, self.gateway, root, **({'client_factory': client_factory} if client_factory else {}))
        self.lock = threading.RLock()
        self.rates = {}

    def authenticate(self, headers):
        token = headers.get('X-U1-AI-Session', '')
        if not re.fullmatch(r'[0-9a-f]{64}', token):
            raise PermissionError('Откройте AI Assistant через U1 Companion.')
        owner = hashlib.sha256(token.encode()).hexdigest()
        session = read(self.root / 'sessions' / (owner + '.json'))
        origin = headers.get('X-U1-Origin', '')
        if (not session or session.get('expires', 0) <= time.time()
                or not hmac.compare_digest(session.get('origin', ''), origin)):
            raise PermissionError('Сессия AI истекла. Откройте раздел заново.')
        actual_origin = headers.get('Origin')
        if actual_origin and not hmac.compare_digest(actual_origin, origin):
            raise PermissionError('Запрос с другого сайта отклонён.')
        referer = headers.get('Referer')
        if referer:
            p = urlsplit(referer)
            if p.scheme + '://' + p.netloc != origin:
                raise PermissionError('Запрос с другого сайта отклонён.')
        now = time.monotonic()
        with self.lock:
            if len(self.rates) > 200:
                self.rates = {k: v for k, v in self.rates.items() if v[-1] > now - 60}
            recent = [x for x in self.rates.get(owner, []) if x > now - 60]
            if len(recent) >= 180:
                raise ValueError('Слишком много запросов к AI.')
            self.rates[owner] = recent + [now]
        return owner, origin.startswith('https://')

    def route(self, method, path, data, owner, secure):
        if not path.startswith(PREFIX) or '?' in path or '#' in path:
            raise ValueError('Неизвестный маршрут AI.')
        route = path[len(PREFIX):]
        if method == 'GET' and route == 'state':
            try:
                printer = self.gateway.get('get_printer_status')
            except Exception:
                printer = {'webhooks': {'state': 'unknown', 'state_message': 'Нет актуального ответа Moonraker.'}}
            actions = []
            paths = sorted((self.root / 'actions').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
            for p in paths:
                row = read(p)
                actions.append({k: row.get(k) for k in ('id', 'state', 'summary', 'filename', 'expires')})
                actions[-1]['sameSession'] = row.get('owner') == owner
            try:
                codex_status = instance(self.root).status()
            except Exception as e:
                codex_status = {'connected': False, 'unavailable': True, 'login': {'error': 'Статус Codex пока недоступен. Повторите обновление.'}}
                audit(self.root, {'kind': 'codex_status_unavailable', 'errorType': type(e).__name__, 'rpc': getattr(instance(self.root), 'last_error', None), 'diagnostics': getattr(instance(self.root), 'diagnostics', [])})
            return {'settings': self.settings.public(), 'accounts': self.accounts.public(), 'codex': codex_status, 'busy': self.agent.busy, 'chats': self.agent.chats(),
                    'usage': read(self.root / 'usage.json', {}), 'audit': read(self.root / 'audit.json', [])[-50:], 'printer': printer, 'actions': actions}
        if method == 'GET' and route.startswith('jobs/'):
            row = read(self.root / 'jobs' / (ident(route[5:]) + '.json'))
            if not row or row.get('owner') != owner:
                raise PermissionError('Задача не найдена в этой сессии.')
            return {k: v for k, v in row.items() if k != 'owner'}
        if method == 'GET' and route.startswith('chats/'):
            return self.agent.history(ident(route[6:]))
        if method == 'POST' and route == 'chats/delete':
            return self.agent.delete_chat(data.get('id'), data.get('confirmed'))
        if route in ('remote/state', 'remote/code', 'remote/command'):
            from u1_remote import request as remote_request
            session = read(self.root / 'sessions' / (owner + '.json'), {})
            from u1_ai_session import local_hosts
            local = urlsplit(session.get('origin', '')).hostname in local_hosts()
            if route == 'remote/code' and method == 'GET':
                if not local: raise PermissionError('forbidden')
                return remote_request('code')
            if route == 'remote/state' and method == 'GET':
                return remote_request('state')
            if route == 'remote/command' and method == 'POST':
                if data.get('action') == 'rotate' and not local: raise PermissionError('forbidden')
                return remote_request('command', data)
        if method == 'POST' and route == 'codex/login':
            if not secure: raise PermissionError('Для входа откройте доверенный HTTPS.')
            return self.agent.submit('codex_login', data, owner)
        if method == 'POST' and route == 'account/pair':
            if not secure: raise PermissionError('Для входа откройте доверенный HTTPS.')
            session = read(self.root / 'sessions' / (owner + '.json'))
            token = self.accounts.pair(owner, data.get('profile'))
            script = Path(__file__).with_name('login-helper.ps1').read_text(encoding='utf-8-sig').replace('__ORIGIN__', session['origin']).replace('__PAIR__', token)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                z.writestr('Login.ps1', b'\xef\xbb\xbf' + script.encode('utf-8'))
                z.writestr('Start.cmd', '@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Login.ps1"\r\n')
            return {'zip': base64.b64encode(buf.getvalue()).decode(), 'expiresIn': 600}
        if method == 'POST' and route == 'account/select':
            return self.accounts.select(data.get('profile'))
        if method == 'POST' and route == 'settings':
            with self.lock:
                result = self.settings.change(data, secure)
            audit(self.root, {'kind': 'settings', 'enabled': result['enabled'], 'access': result['access']})
            return result
        if method == 'POST' and route == 'chat':
            self.gateway.enabled()
            return self.agent.submit('chat', data, owner)
        if method == 'POST' and route == 'models':
            return self.agent.submit('models', data, owner)
        if method == 'POST' and route == 'actions/confirm':
            return self.agent.submit('confirm', data, owner)
        if method == 'POST' and route == 'actions/reject':
            return self.gateway.reject(data.get('id'), owner)
        raise ValueError('Неизвестный метод AI.')


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'U1CompanionAI/1'
        def log_message(self, *args):
            pass  # Never log keys, chat bodies, session capabilities or request headers.

        def send_json(self, status, value):
            raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def dispatch(self, method):
            self.connection.settimeout(10)
            try:
                if method == 'GET' and self.path == '/health':
                    self.send_json(200, {'service': 'u1-companion-ai', 'version': 1})
                    return
                if method == 'POST' and self.path == '/u1-alexa/skill':
                    length=int(self.headers.get('Content-Length','-1'))
                    if not 0<length<=65536 or self.headers.get_content_type()!='application/json':raise PermissionError('Invalid voice request')
                    from u1_voice_control import Voice
                    from .gateway import Moonraker
                    value=Voice(Moonraker()).receive(self.rfile.read(length),self.headers.get('X-U1-Voice-Signature',''))
                    self.send_json(200,value)
                    return
                helper = method == 'POST' and self.path in (PREFIX+'helper/start', PREFIX+'helper/finish')
                if helper:
                    if not self.headers.get('X-U1-Origin', '').startswith('https://'): raise PermissionError('Нужен доверенный HTTPS.')
                    owner, secure = '', True
                else:
                    owner, secure = app.authenticate(self.headers)
                body = {}
                if method == 'POST':
                    length = int(self.headers.get('Content-Length', '-1'))
                    if not 0 <= length <= 128000 or self.headers.get_content_type() != 'application/json':
                        raise ValueError('Ожидается ограниченный JSON-запрос.')
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError('Ожидается JSON-объект.')
                if helper:
                    if self.path.endswith('/start'): result = app.accounts.start(body.get('pair'), body.get('port'))
                    else: result = app.accounts.finish(body.get('pair'), body.get('callback', ''))
                else:
                    result = app.route(method, self.path, body, owner, secure)
                self.send_json(200, {'ok': True, 'value': result})
            except PermissionError as error:
                self.send_json(403, {'ok': False, 'error': str(error)})
            except (ValueError, TypeError, KeyError) as error:
                # Settings changes never include payload values in their errors.
                message = str(error)
                key = app.settings.get().get('apiKey')
                self.send_json(400, {'ok': False, 'error': message.replace(key, '[REDACTED]') if key else message})
            except Exception:
                self.send_json(503, {'ok': False, 'error': 'Сервис AI временно недоступен. Команды не повторяются автоматически.'})

        def do_GET(self):
            self.dispatch('GET')

        def do_POST(self):
            self.dispatch('POST')
    return Handler


def main():
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 4547), handler(Application()))
    server.daemon_threads = True
    server.serve_forever()


if __name__ == '__main__':
    main()
