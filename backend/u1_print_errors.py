"""Read-only U1 error collection; durable inbox and idempotent history."""
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time
import uuid
import urllib.error
from u1_feeder_settings import atomic

STATUS = '/printer/objects/query?print_stats&print_task_config&exception_manager&webhooks'
FAILED = {'error', 'klippy_shutdown', 'klippy_disconnect', 'server_exit', 'interrupted'}


def clean(value, limit=1000):
    return str(value or '').replace('\x00', '')[:limit]


def valid_time(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def minimal_job(job):
    return {key: job[key] for key in ('job_id', 'filename', 'status', 'start_time', 'end_time') if key in job}


def in_job(job, timestamp):
    return (bool(re.fullmatch(r'[0-9a-fA-F]{1,16}', str(job.get('job_id', '')))) and
            valid_time(job.get('start_time')) and timestamp >= job['start_time'] and
            (job.get('status') == 'in_progress' or job.get('end_time') is None or timestamp <= job['end_time']))


def normalize(error):
    if isinstance(error, str):
        try:
            error = json.loads(error.lstrip('! /'))
        except ValueError:
            error = {'message': error}
    if not isinstance(error, dict):
        return None
    code = error.get('coded')
    if not isinstance(code, str) or not re.fullmatch(r'\d{4}-\d{4}-\d{4}-\d{4}', code):
        if all(type(error.get(key)) is int and 0 <= error[key] <= 9999 for key in ('id', 'index', 'code')):
            level = error.get('level', 3)
            level = level if type(level) is int and 0 <= level <= 9 else 3
            code = '%04d-%04d-%04d-%04d' % (level, error['id'], error['index'], error['code'])
        else:
            code = 'PRINT_MESSAGE'
    message = clean(error.get('message') or error.get('msg'))
    if not message and code == 'PRINT_MESSAGE':
        return None
    level = int(code[:4]) if code != 'PRINT_MESSAGE' else 3
    return {'code': code, 'message': message or 'Сообщение U1 без описания.', 'severity': min(level, 9)}


def fingerprint(error):
    code = error['code']
    return code[5:] if code != 'PRINT_MESSAGE' else 'message:' + hashlib.sha256(error['message'].encode()).hexdigest()[:16]


def capture(data, task):
    inventory, library = data.get('inventory', {}), data.get('library', {})
    colors = {color['id']: color for color in library.get('entries', []) + library.get('trash', [])}
    spools = {spool['id']: spool for spool in inventory.get('spools', [])}
    heads = inventory.get('heads', [None] * 4)
    used = task.get('extruders_used', [])
    restricted = len(used) == 4 and any(used)
    result = []
    for head, ident in enumerate(heads[:4]):
        if restricted and not used[head]:
            continue
        spool = spools.get(ident)
        if not spool:
            continue
        types, rgba = task.get('filament_type', []), task.get('filament_color_rgba', [])
        if len(types) == 4 and len(rgba) == 4 and (spool['material'] != types[head] or spool['hex'].lstrip('#').upper() != rgba[head][:6].upper()):
            continue
        row = {'head': head, 'spoolId': spool['id'], 'name': spool['name'], 'material': spool['material'], 'hex': spool['hex']}
        for key in ('colorId', 'manufacturer'):
            if spool.get(key):
                row[key] = spool[key]
        color = colors.get(spool.get('colorId'))
        if color:
            row['colorName'] = color['name']
        result.append(row)
    return result


class Inbox:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'print-error-inbox.json'
        self.lock = threading.RLock()
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {'events': [], 'dropped': 0, 'since': time.time()}
        if not isinstance(self.data.get('events'), list):
            raise ValueError('Повреждён входящий журнал ошибок.')

    def save(self):
        atomic(self.path, json.dumps(self.data, ensure_ascii=False, allow_nan=False).encode())

    def append(self, event):
        with self.lock:
            event = {**event, 'inboxId': str(uuid.uuid4())}
            if len(self.data['events']) >= 1000 or len(json.dumps(event, ensure_ascii=False)) > 16384:
                self.data['dropped'] += 1
            else:
                self.data['events'].append(event)
            self.save()

    def peek(self):
        with self.lock:
            return copy.deepcopy(self.data['events'][:100])

    def ack(self, identifiers):
        if not identifiers:
            return
        with self.lock:
            self.data['events'] = [event for event in self.data['events'] if event['inboxId'] not in identifiers]
            self.save()


class ErrorStream:
    def __init__(self, folder):
        self.inbox = Inbox(folder)
        self.mirror = Path(folder) / 'current.json'
        self.connected = False
        self.message = ''
        self.status = {}
        self.job = {}
        self.following = False
        self.context = []
        self.job_seen = 0
        self.filename_seen = 0

    def health(self):
        return {'connected': self.connected, 'message': clean(self.message),
                'dropped': self.inbox.data['dropped'], 'since': self.inbox.data['since']}

    def snapshot(self):
        try:
            with self.mirror.open(encoding='utf-8') as source:
                return capture(json.load(source)['data'], self.status.get('print_task_config', {}))
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def set_job(self, job, announce=False):
        if job.get('status') == 'in_progress':
            if self.job.get('job_id') != job.get('job_id'):
                self.context = self.snapshot()
            self.job, self.following = minimal_job(job), True
            self.job_seen = time.monotonic()
            if announce:
                self.inbox.append({'kind': 'start', 'job': self.job, 'spools': self.context, 'received': time.time()})
        elif self.following and self.job.get('job_id') == job.get('job_id'):
            self.job = minimal_job(job)
            self.inbox.append({'kind': 'finish', 'job': self.job, 'spools': self.context, 'received': time.time()})

    def native(self, error, cached=False):
        if not isinstance(error, dict):
            return
        parsed = normalize(error)
        if not parsed:
            return
        timestamp = error.get('timestamp', time.time())
        if not valid_time(timestamp):
            return
        stats = self.status.get('print_stats', {})
        job = self.job if self.following and in_job(self.job, timestamp) else {}
        if job and stats.get('filename') and stats['filename'] != job['filename'] and self.filename_seen > self.job_seen:
            job = {}
        if not job and stats.get('state') not in ('printing', 'paused', 'error'):
            return
        if not job and not stats.get('filename'):
            return
        context = self.context if job and job.get('status') != 'in_progress' else self.snapshot()
        if cached and time.time() - timestamp > 10:
            context = []  # Original bindings are unknown for an older cached event.
        self.inbox.append({'kind': 'error', 'job': job, 'filename': job.get('filename') or stats.get('filename', ''),
                           'time': timestamp, 'error': parsed, 'spools': context, 'received': time.time()})

    def on_message(self, value):
        if value.get('id') == 1 and 'result' in value:
            self.status = value['result'].get('status', {})
            self.filename_seen = time.monotonic()
        elif value.get('id') == 2 and 'result' in value:
            jobs = value['result'].get('jobs', [])
            if jobs:
                self.set_job(jobs[0], True)
        elif value.get('id') == 3 and 'result' in value:
            for error in value['result'].get('exceptions', []):
                self.native(error, True)
        method, params = value.get('method', ''), value.get('params', [])
        if method == 'notify_status_update' and params:
            for key, update in params[0].items():
                if key == 'print_stats' and 'filename' in update and update['filename'] != self.status.get(key, {}).get('filename'):
                    self.filename_seen = time.monotonic()
                self.status.setdefault(key, {}).update(update)
        elif method == 'notify_history_changed' and params:
            self.set_job(params[0].get('job', {}), True)
        elif method == 'notify_exception_notification' and params:
            self.native(params[0])
        elif method == 'notify_exception_status' and params:
            for error in params[0].get('exceptions', []):
                self.native(error, True)

    async def listen(self):
        from tornado.websocket import websocket_connect
        while True:
            socket = None
            try:
                self.status, self.job, self.following, self.context = {}, {}, False, []
                socket = await websocket_connect('ws://127.0.0.1:7125/websocket', connect_timeout=8,
                                                 ping_interval=20, ping_timeout=30, max_message_size=1024 * 1024)
                self.connected, self.message = True, ''
                queries = [('printer.objects.subscribe', {'objects': {
                    'print_stats': ['filename', 'state', 'exception', 'message'],
                    'print_task_config': ['filament_type', 'filament_color_rgba', 'extruders_used']}}),
                    ('server.history.list', {'limit': 1}), ('server.exception.query', {})]
                # Replies and notifications are processed in socket order. Query the
                # initial exception cache only after job/status replies were received.
                for ident, (method, params) in enumerate(queries, 1):
                    await socket.write_message(json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params, 'id': ident}))
                    while True:
                        message = await asyncio.wait_for(socket.read_message(), 15)
                        if message is None:
                            raise ConnectionError('Соединение журнала закрыто.')
                        value = json.loads(message)
                        self.on_message(value)
                        if value.get('id') == ident:
                            if 'error' in value:
                                raise RuntimeError(value['error'].get('message', 'Ошибка подписки'))
                            break
                while True:
                    message = await socket.read_message()
                    if message is None:
                        raise ConnectionError('Соединение журнала закрыто.')
                    self.on_message(json.loads(message))
            except Exception as error:
                self.connected, self.message = False, clean(error)
            finally:
                if socket is not None:
                    socket.close()
            await asyncio.sleep(5)

    def start(self):
        def run():
            try:
                asyncio.run(self.listen())
            except Exception as error:
                self.connected, self.message = False, clean(error)
        threading.Thread(target=run, daemon=True, name='u1-print-errors').start()


class ErrorMonitor:
    def __init__(self, api, get_item):
        self.api, self.get_item = api, get_item

    def watch(self, usage):
        return usage.setdefault('_errorWatch', {'job': None, 'spools': [], 'active': {}})

    def rows(self, task):
        inventory = self.get_item('u1_spool_inventory_v1', {'spools': [], 'heads': [None] * 4})
        library = self.get_item('u1_filament_library_v1', {'entries': [], 'trash': []})
        return capture({'inventory': inventory, 'library': library}, task)

    def begin(self, usage, job, spools):
        watch = self.watch(usage)
        if watch['job'] and watch['job']['job_id'] != job['job_id']:
            self.check_finished(usage, time.time())
        if not watch['job'] or watch['job']['job_id'] != job['job_id']:
            watch.update(job=minimal_job(job), spools=spools, active={})
        elif not watch['spools'] and spools:
            watch['spools'] = spools

    def add(self, usage, job, error, timestamp, spools, source='u1'):
        if not normalize(error):
            return None
        errors = usage.setdefault('errors', [])
        job_id = job['job_id'].upper()
        key = hashlib.sha256(json.dumps([job_id, fingerprint(error), timestamp, source], separators=(',', ':')).encode()).hexdigest()
        existing = next((row for row in errors if row['id'] == key), None)
        if existing:
            return existing
        if source == 'u1':
            # Replace a provisional poll/result entry when the exact U1 event
            # arrives later. Preserve one event, not one entry per data source.
            existing = next((row for row in reversed(errors) if row['jobId'] == job_id and
                             (row['source'] == 'history' or (row['source'] == 'observed' and fingerprint(row) == fingerprint(error) and
                              ('closedAt' not in row or abs(row['time'] - timestamp) <= 10)))), None)
        row = {'id': key, 'jobId': job_id, 'filename': clean(job['filename'], 1024), 'time': timestamp,
               **error, 'source': source, 'spools': copy.deepcopy(spools), 'jobStatus': job.get('status', 'in_progress')}
        if existing:
            previous_id = existing['id']
            closed = existing.get('closedAt')
            previous_status = existing.get('jobStatus')
            existing.update(row)
            if previous_status and previous_status != 'in_progress' and row['jobStatus'] == 'in_progress':
                existing['jobStatus'] = previous_status
            if closed is not None:
                existing['closedAt'] = closed
            for signature, ident in self.watch(usage)['active'].items():
                if ident == previous_id:
                    self.watch(usage)['active'][signature] = key
            return existing
        if len(errors) >= 10000 or len(json.dumps(errors, ensure_ascii=False).encode()) + len(json.dumps(row, ensure_ascii=False).encode()) > 4 * 1024 * 1024:
            raise ValueError('Журнал ошибок заполнен. Нужен экспорт и обслуживание журнала; новые сообщения остаются во входящей очереди.')
        errors.append(row)
        return row

    def finish(self, usage, job, spools, now):
        related = [row for row in usage.get('errors', []) if row['jobId'] == job['job_id'].upper()]
        if not related and job.get('status') in FAILED:
            self.add(usage, job, {'code': 'JOB_' + job['status'].upper(), 'message': 'История U1 отметила статус задания: ' + job['status'] + '. Подробное сообщение не было получено; причина по этому статусу не определяется.', 'severity': 2 if job['status'] == 'server_exit' else 3},
                     job.get('end_time') or now, spools, 'history')
        for row in usage.get('errors', []):
            if row['jobId'] == job['job_id'].upper():
                row['jobStatus'] = job['status']
                row.setdefault('closedAt', job.get('end_time') or now)
        watch = self.watch(usage)
        if watch['job'] and watch['job']['job_id'] == job['job_id']:
            watch.update(job=None, spools=[], active={})

    def consume(self, usage, events, now=None):
        now = time.time() if now is None else now
        ack = []
        for event in events:
            kind, job = event['kind'], event.get('job', {})
            if kind == 'error' and not job.get('job_id'):
                jobs = self.api('/server/history/list?limit=10')['jobs']
                candidates = [item for item in jobs if item['filename'] == event.get('filename') and in_job(item, event['time'])]
                if not candidates:
                    # Allow the history-start notification to arrive before retrying.
                    if now - event.get('received', now) < 60:
                        continue
                    ack.append(event['inboxId'])
                    usage.setdefault('errorService', {})['unbound'] = usage.get('errorService', {}).get('unbound', 0) + 1
                    continue
                job = max(candidates, key=lambda item: item['start_time'])
            if not re.fullmatch(r'[0-9a-fA-F]{1,16}', str(job.get('job_id', ''))):
                ack.append(event['inboxId'])
                continue
            if kind == 'start' and job.get('status') == 'in_progress':
                self.begin(usage, job, event.get('spools', []))
            elif kind == 'finish':
                self.finish(usage, job, event.get('spools', []), now)
            elif kind == 'error' and in_job(job, event['time']):
                row = self.add(usage, job, event['error'], event['time'], event.get('spools', []))
                watch = self.watch(usage)
                if row and watch['job'] and watch['job']['job_id'] == job['job_id']:
                    watch['active'][fingerprint(row)] = row['id']
            ack.append(event['inboxId'])
        return ack

    def poll(self, usage, now=None):
        now = time.time() if now is None else now
        watch = self.watch(usage)
        try:
            status = self.api(STATUS)['status']
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            if hasattr(error, 'close'):
                error.close()
            if watch['job']:
                self.check_finished(usage, now)
            return
        stats, task = status.get('print_stats', {}), status.get('print_task_config', {})
        if not watch['job'] and stats.get('state') in ('printing', 'paused'):
            jobs = self.api('/server/history/list?limit=1')['jobs']
            if jobs and jobs[0].get('status') == 'in_progress' and jobs[0].get('filename') == stats.get('filename'):
                self.begin(usage, jobs[0], self.rows(task))
        job = watch['job']
        if not job:
            return
        if stats.get('filename') == job['filename']:
            candidates = list(status.get('exception_manager', {}).get('exceptions', []))
            if stats.get('exception'):
                candidates.append(stats['exception'])
            elif stats.get('message') and stats.get('state') in ('paused', 'error'):
                candidates.append(stats['message'])
            current = {}
            for raw in candidates:
                error = normalize(raw)
                if error:
                    current[fingerprint(error)] = error
            for signature, error in current.items():
                row = next((row for row in usage.get('errors', []) if row['id'] == watch['active'].get(signature)), None)
                if row is None:
                    row = next((row for row in reversed(usage.get('errors', [])) if row['jobId'] == job['job_id'].upper() and
                                fingerprint(row) == signature and 'closedAt' not in row), None)
                if row is None:
                    context = self.rows(task) if stats.get('state') in ('printing', 'paused') else watch['spools']
                    row = self.add(usage, job, error, now, context, 'observed')
                watch['active'][signature] = row['id']
            for signature in list(watch['active']):
                if signature not in current:
                    row = next((row for row in usage.get('errors', []) if row['id'] == watch['active'][signature]), None)
                    if row:
                        row.setdefault('closedAt', now)
                    del watch['active'][signature]
        self.check_finished(usage, now)

    def check_finished(self, usage, now):
        watch = self.watch(usage)
        job = watch['job']
        try:
            final = self.api('/server/history/job?uid=' + job['job_id'])['job']
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            final = {**job, 'status': 'history_missing', 'end_time': now}
        if final['status'] != 'in_progress':
            self.finish(usage, final, watch['spools'], now)
