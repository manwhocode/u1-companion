"""Allowlisted tools. Model calls can only read or propose; confirm is a UI-only route."""
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import threading
from pathlib import Path
from .storage import atomic, read, audit, ident, redact
from .control_plans import EXTRA, prepare as prepare_extra, cover_script

QUERY = '/printer/objects/query?webhooks&print_stats&pause_resume&toolhead&heater_bed&extruder&extruder1&extruder2&extruder3&purifier&exception_manager&print_task_config'
READS = {'get_printable_files', 'get_control_state', 'get_printer_status', 'get_print_progress', 'get_temperatures', 'get_filament_status',
         'get_active_print', 'get_error_history', 'get_moonraker_status',
         'get_available_macros', 'get_current_configuration', 'get_klipper_logs'}
CONTROL = {'pause_print': 'pause', 'resume_print': 'resume', 'cancel_print': 'cancel', 'start_print': 'start', **{name: name for name in EXTRA}}


class Moonraker:
    def api(self, path, payload=None, timeout=8):
        # Only internal application code supplies routes. No model-provided URLs.
        req = urllib.request.Request('http://127.0.0.1:7125' + path,
                                     data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as stream:
            return json.load(stream)['result']

    def item(self, key, default=None):
        try:
            return self.api('/server/database/item?' + urllib.parse.urlencode({'namespace': 'fluidd', 'key': key}))['value']
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return default
            raise

    def relay(self, operation, payload, request_id=None, timeout=30):
        request_id = request_id or str(uuid.uuid4())
        self.api('/server/database/item', {'namespace': 'u1_addon_requests', 'key': request_id,
                                         'value': {'operation': operation, 'payload': payload}})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = self.api('/server/database/item?' + urllib.parse.urlencode({'namespace': 'u1_addon_results', 'key': request_id}))['value']
                if not result.get('ok'):
                    raise ValueError(result.get('error') or 'Команда не выполнена.')
                return result.get('value')
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
            time.sleep(.3)
        raise TimeoutError('Нет подтверждённого результата. Проверьте принтер; повтор команды запрещён.')


def schemas(access='read'):
    rows = [{'type': 'function', 'name': name, 'description': 'Read current U1 data: ' + name,
             'strict': True, 'parameters': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}}
            for name in sorted(READS)]
    if access == 'control':
        for name in CONTROL:
            props = EXTRA[name] if name in EXTRA else {'filename': {'type': 'string', 'description': 'Exact existing printer G-code filename'}} if name == 'start_print' else EXTRA.get(name, {})
            rows.append({'type': 'function', 'name': name,
                         'description': 'Propose ' + name + '. Does NOT execute. Requires a separate user click in the app.',
                         'strict': True, 'parameters': {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}})
    return rows


class Gateway:
    def __init__(self, settings, root, moon=None, clock=time.time):
        self.settings, self.root, self.moon, self.clock = settings, Path(root), moon or Moonraker(), clock
        self.lock = threading.Lock()

    def enabled(self):
        value = self.settings.get()
        if not value['enabled'] or not value['consent']:
            raise ValueError('AI отключён или передача данных не разрешена.')
        return value

    def call(self, name, args, owner, chat):
        config = self.enabled()
        if not isinstance(args, dict):
            raise ValueError('Некорректные аргументы инструмента.')
        if name in READS:
            if args:
                raise ValueError('Этот инструмент не принимает параметры.')
            value = self.get(name)
            audit(self.root, {'kind': 'read', 'tool': name, 'chat': chat})
            return json.loads(redact(value))
        if name not in CONTROL or config['access'] != 'control':
            raise ValueError('Инструмент запрещён текущими разрешениями.')
        if name in EXTRA:
            plan = prepare_extra(self.moon, name, args)
            action_id = str(uuid.uuid4())
            row = {'id':action_id, 'tool':name, 'action':name, 'owner':owner, 'chat':chat,
                   'time':self.clock(), 'expires':self.clock()+120, 'revision':config['revision'],
                   'state':'pending', **plan}
            atomic(self.root / 'actions' / (action_id+'.json'), row)
            audit(self.root, {'kind':'proposed','id':action_id,'tool':name,'chat':chat})
            return {'status':'requires_confirmation','actionId':action_id,'summary':row['summary'],
                    'filename':row['filename'],'expires':row['expires'],'executed':False}
        if set(args) != ({'filename'} if name == 'start_print' else set()):
            raise ValueError('Неизвестные аргументы управления.')
        state = self.moon.relay('print_player_state', {})
        action = CONTROL[name]
        allowed = state.get({'pause': 'canPause', 'resume': 'canResume', 'cancel': 'canCancel', 'start': 'canStart'}[action])
        if allowed is not True:
            raise ValueError(state.get('reason') or 'Действие недоступно в текущем состоянии U1.')
        payload = {'action': action, 'currentJob': state.get('currentJob'), 'confirmed': True}
        plan = None
        if action == 'start':
            filename = args.get('filename')
            if (not isinstance(filename, str) or len(filename) > 512 or not filename.lower().endswith('.gcode')
                    or filename.startswith(('/', '\\')) or '..' in filename.replace('\\', '/').split('/') or '\n' in filename or '\r' in filename):
                raise ValueError('Нужен существующий G-code в каталоге принтера.')
            plan = self.moon.relay('print_player_prepare', {'filename': filename, 'mapping': [0, 1, 2, 3], 'bedLevel': True, 'flowCalibration': False})
        action_id = str(uuid.uuid4())
        actions = sorted((self.root / 'actions').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in actions[249:]:
            old.unlink()  # Unknown/deleted IDs always reject; no request is reconstructed.
        row = {'id': action_id, 'tool': name, 'action': action, 'owner': owner, 'chat': chat,
               'time': self.clock(), 'expires': self.clock() + 120, 'revision': config['revision'],
               'state': 'pending', 'payload': payload, 'plan': plan,
               'summary': {'pause': 'Поставить печать на паузу', 'resume': 'Продолжить печать',
                           'cancel': 'Отменить печать', 'start': 'Запустить печать'}[action],
               'filename': plan.get('filename') if plan else state.get('filename')}
        atomic(self.root / 'actions' / (action_id + '.json'), row)
        audit(self.root, {'kind': 'proposed', 'id': action_id, 'tool': name, 'chat': chat})
        return {'status': 'requires_confirmation', 'actionId': action_id, 'summary': row['summary'],
                'filename': row['filename'], 'expires': row['expires'], 'executed': False}

    def get(self, name):
        if name == 'get_printable_files':
            rows = self.moon.api('/server/files/list?root=gcodes')
            files = sorted([{'path': r['path'], 'modified': r.get('modified', 0)} for r in rows
                            if isinstance(r.get('path'), str) and r['path'].lower().endswith('.gcode')],
                           key=lambda r: r['modified'], reverse=True)
            jobs = self.moon.api('/server/history/list?limit=20').get('jobs', [])
            return {'files': files[:300], 'truncated': len(files) > 300,
                    'recentPrints': [{k: r.get(k) for k in ('filename', 'status', 'start_time', 'end_time')} for r in jobs]}
        if name == 'get_control_state':
            return {key: self.moon.relay(key, {}) for key in ('print_player_state', 'timed_pause_state', 'magnet_state', 'schedule_state')}
        if name == 'get_klipper_logs':
            # Fixed operational log, bounded tail. No model-provided paths.
            path = Path('/oem/klippylogs/klippy.log')
            if not path.is_file():
                return {'available': False}
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 12000))
                text = stream.read(12000).decode('utf-8', errors='replace')
            return {'available': True, 'tail': text, 'untrustedLogData': True}
        if name == 'get_moonraker_status':
            s = self.moon.api('/server/info')
            return {k: s.get(k) for k in ('klippy_connected', 'klippy_state', 'moonraker_version', 'failed_components', 'warnings')}
        if name == 'get_error_history':
            value = self.moon.item('u1_spool_usage_v1', {})
            return {'errors': value.get('errors', [])[:30]}
        if name == 'get_available_macros':
            rows = self.moon.api('/printer/gcode/help')
            return {'macros': list(rows)[:200], 'executionEnabled': False}
        if name == 'get_current_configuration':
            rows = self.moon.api('/printer/objects/query?configfile')['status']['configfile'].get('settings', {})
            return {key: {k: row.get(k) for k in ('min_temp', 'max_temp', 'min_extrude_temp', 'nozzle_diameter') if k in row}
                    for key, row in rows.items() if key in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3')}
        s = self.moon.api(QUERY)['status']
        if name == 'get_printer_status':
            return {k: s.get(k) for k in ('webhooks', 'print_stats', 'pause_resume', 'exception_manager', 'purifier')}
        if name in ('get_print_progress', 'get_active_print'):
            return s.get('print_stats', {})
        if name == 'get_temperatures':
            return {key: {k: s.get(key, {}).get(k) for k in ('temperature', 'target', 'power')}
                    for key in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3')}
        if name == 'get_filament_status':
            inventory = self.moon.item('u1_spool_inventory_v1', {})
            library = self.moon.item('u1_filament_library_v1', {})
            colors = {row['id']: row for row in library.get('entries', [])}
            used = self.moon.item('u1_spool_usage_v1', {}).get('totals', {})
            ids = inventory.get('heads', [])
            rows = []
            for head, spool_id in enumerate(ids):
                spool = next((row for row in inventory.get('spools', []) if row.get('id') == spool_id), None)
                if spool:
                    row = {k: spool.get(k) for k in ('id', 'name', 'manufacturer', 'material', 'hex', 'calibration', 'nozzleTemperature', 'bedTemperature')}
                    color = colors.get(spool.get('colorId'), {})
                    row['baseFilament'] = {k: color.get(k) for k in ('id', 'name', 'manufacturer', 'material', 'hex')}
                    row['effectiveTemperatures'] = {k: spool.get(k, color.get(k)) for k in ('nozzleTemperature', 'bedTemperature')}
                    row['effectiveCalibration'] = (spool if inventory.get('individualCalibration') else color).get('calibration', {})
                    row.update(head=head + 1, remainingGrams=max(0, spool.get('grams', 0) - max(0, used.get(spool_id, 0) - spool.get('accountedGrams', 0))))
                    rows.append(row)
            catalog = [{k: row.get(k) for k in ('id', 'name', 'manufacturer', 'material', 'hex', 'calibration', 'nozzleTemperature', 'bedTemperature')}
                       for row in library.get('entries', [])[:100]]
            drying = read(Path('/userdata/u1-addons/filament-ui-data/drying/profiles.json'), {})
            return {'totalUsedGrams': sum(v for v in used.values() if type(v) in (int, float) and 0 <= v < 1e12), 'task': s.get('print_task_config'), 'spools': rows, 'colors': catalog, 'dryingProfiles': drying,
                    'catalogTruncated': len(library.get('entries', [])) > 100}
        raise ValueError('Неизвестный инструмент чтения.')

    def confirm(self, action_id, owner, confirmed):
        ident(action_id)
        if confirmed is not True:
            raise ValueError('Нужно отдельное подтверждение действия.')
        config = self.enabled()
        p = self.root / 'actions' / (action_id + '.json')
        with self.lock:
            row = read(p)
            if (not row or row.get('owner') != owner or row.get('state') != 'pending'
                    or config['access'] != 'control' or row['revision'] != config['revision']
                    or not 0 <= self.clock() - row['time'] < 120):
                raise ValueError('Действие устарело, уже отправлено или изменились разрешения.')
            # Reserve durably before any write to the printer. No automatic retries.
            row.update(state='sent', sentAt=self.clock())
            atomic(p, row)
        audit(self.root, {'kind': 'confirmed', 'id': action_id, 'tool': row['tool']})
        try:
            if row['action'] in EXTRA:
                if row['operation'] == 'cover_fan':
                    p = self.moon.api('/printer/objects/query?purifier')['status']['purifier']
                    result = self.moon.api('/printer/gcode/script', {'script':cover_script(p, **row['payload'])}, timeout=60)
                else:
                    result = self.moon.relay(row['operation'], row['payload'], request_id=action_id, timeout=180)
            elif row['action'] == 'start':
                result = self.moon.relay('print_player_start', {'token': row['plan']['token'], 'confirmed': True}, request_id=action_id, timeout=180)
            else:
                result = self.moon.relay('print_player_action', row['payload'], request_id=action_id, timeout=180)
            row.update(state='completed', result=result)
        except Exception:
            row.update(state='needs_review', message='Нет подтверждённого выполнения. Проверьте U1; повтор этой команды запрещён.')
            atomic(p, row)
            audit(self.root, {'kind': 'needs_review', 'id': action_id})
            raise ValueError(row['message']) from None
        atomic(p, row)
        audit(self.root, {'kind': 'completed', 'id': action_id, 'tool': row['tool']})
        return result

    def reject(self, action_id, owner):
        p = self.root / 'actions' / (ident(action_id) + '.json')
        with self.lock:
            row = read(p)
            if not row or row.get('owner') != owner or row.get('state') != 'pending':
                raise ValueError('Действие уже обработано или принадлежит другой сессии.')
            row['state'] = 'rejected'
            atomic(p, row)
        audit(self.root, {'kind': 'rejected', 'id': row['id']})
        return {'rejected': True}
