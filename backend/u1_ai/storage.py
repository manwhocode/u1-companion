import json
import os
from pathlib import Path
import re
import time
import uuid
import threading

ROOT = Path('/userdata/u1-addons/ai-private')
AUDIT_LOCK = threading.Lock()
ID = re.compile(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z')


def ident(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('Некорректный идентификатор.')
    return value


def read(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    if path.is_symlink() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Некорректное хранилище AI.')
    return json.loads(path.read_text(encoding='utf-8'))


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Символическая ссылка в хранилище AI.')
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Превышен размер записи AI.')
    temp = path.with_name(path.name + '.' + str(uuid.uuid4()) + '.next')
    with temp.open('xb') as stream:
        os.chmod(temp, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


DEFAULT = {'version': 1, 'revision': '', 'enabled': False, 'consent': False,
           'requireConfirmation': True, 'provider': 'api', 'model': '', 'access': 'read', 'instructions': '', 'keepHistory': True,
           'contextChars': 24000, 'maxOutputTokens': 2000, 'apiKey': ''}


class Settings:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.path = self.root / 'settings.json'

    def get(self):
        return {**DEFAULT, **read(self.path, {})}

    def public(self):
        value = self.get()
        key = value['apiKey']
        public = {k: (v.replace(key, '[REDACTED]') if key and isinstance(v, str) else v)
                  for k, v in value.items() if k != 'apiKey'}
        return {**public, 'hasKey': bool(key)}

    def change(self, payload, secure=False):
        if not isinstance(payload, dict) or set(payload) - set(DEFAULT) - {'clearKey'}:
            raise ValueError('Неизвестные настройки AI.')
        old = self.get()
        if payload.get('revision') != old['revision']:
            raise ValueError('Настройки изменились. Обновите окно.')
        if ('apiKey' in payload or payload.get('clearKey')) and not secure:
            raise ValueError('Для сохранения ключа откройте доверенный HTTPS.')
        value = {**old, **{k: v for k, v in payload.items() if k not in ('version', 'revision', 'clearKey')}}
        if payload.get('clearKey') is True:
            value['apiKey'] = ''
            value['enabled'] = False
        if value['provider'] not in ('api', 'chatgpt', 'codex'): raise ValueError('Выберите способ подключения.')
        if value['access'] not in ('read', 'control'):
            raise ValueError('В первом этапе доступны чтение и подтверждаемое управление.')
        for k in ('enabled', 'consent', 'keepHistory', 'requireConfirmation'):
            if type(value[k]) is not bool:
                raise ValueError('Некорректный переключатель AI.')
        if not isinstance(value['apiKey'], str) or len(value['apiKey']) > 512 or any(c.isspace() for c in value['apiKey']):
            raise ValueError('Некорректный API-ключ.')
        if not isinstance(value['model'], str) or (value['model'] and not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', value['model'])):
            raise ValueError('Некорректное имя модели.')
        if not isinstance(value['instructions'], str) or len(value['instructions']) > 6000:
            raise ValueError('Слишком длинные инструкции.')
        for key in (old['apiKey'], value['apiKey']):
            if key and (key in value['instructions'] or key in value['model']):
                raise ValueError('API-ключ вводится только в отдельное поле ключа.')
        if type(value['contextChars']) is not int or not 4000 <= value['contextChars'] <= 100000:
            raise ValueError('Контекст: от 4000 до 100000 символов.')
        if type(value['maxOutputTokens']) is not int or not 256 <= value['maxOutputTokens'] <= 8000:
            raise ValueError('Ответ: от 256 до 8000 токенов.')
        from .accounts import Accounts
        if value['provider'] == 'codex':
            from .codex_account import instance
            connected = instance(self.root).status()['connected']
        else:
            connected = bool(value['apiKey']) if value['provider'] == 'api' else Accounts(self.root).connected()
        if value['enabled'] and (not value['consent'] or not connected or not value['model']):
            raise ValueError('Нужны подключение, модель и согласие на отправку данных в OpenAI.')
        # No key-bearing historical copies: existing full filament backups exclude this directory.
        value['revision'] = str(uuid.uuid4())
        atomic(self.path, value)
        return self.public()


def redact(value):
    text = json.dumps(value, ensure_ascii=False, default=str)
    text = re.sub(r'(?i)(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]+)', '[REDACTED]', text)
    text = re.sub(r'(?i)((?:api[_-]?key|password|cookie|authorization|token)["\s:=]+)[^\s,"}]+', r'\1[REDACTED]', text)
    return text


def audit(root, value):
    with AUDIT_LOCK:
        path = Path(root) / 'audit.json'
        rows = read(path, [])
        rows.append(json.loads(redact({'time': time.time(), **value})))
        atomic(path, rows[-500:])
