"""Durable observation checkpoints. Never replay archived motion or fabricate MCU state."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


QUERY = '/printer/objects/query?webhooks&print_stats&virtual_sdcard&toolhead&gcode_move&print_task_config&machine_state_manager&exception_manager&purifier&heater_bed&extruder&extruder1&extruder2&extruder3'


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    temporary = path.with_suffix('.next')
    with temporary.open('wb') as stream:
        os.chmod(temporary, 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


class Recovery:
    def __init__(self, api, folder, native='/home/lava/printer_data/klippy', clock=time.time):
        self.api, self.folder, self.native, self.clock = api, Path(folder), Path(native), clock
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.folder / 'checkpoints.json'
        self.points = []
        if self.path.exists():
            # Corruption fails closed rather than silently overwriting history.
            data = json.loads(self.path.read_text())
            if data.get('version') != 1 or not isinstance(data.get('points'), list):
                raise ValueError('Повреждён журнал контрольных точек.')
            self.points = data['points'][:30]
        self.last = 0
        self.previous = None
        self.plans = {}

    def status(self):
        return self.api(QUERY)['status']

    def capture(self, force=False):
        s = self.status()
        stats, sd = s.get('print_stats', {}), s.get('virtual_sdcard', {})
        phase = stats.get('state')
        if phase not in ('printing', 'paused'):
            if self.points and self.points[0].get('state') in ('printing', 'paused') and phase in ('cancelled', 'complete', 'error') and self.points[0].get('endedAs') != phase:
                self.points[0]['endedAs'] = phase
                atomic(self.path, {'version': 1, 'points': self.points})
            return
        if not stats.get('filename') or not isinstance(sd.get('file_position'), int):
            return
        key = (stats['filename'], sd['file_position'], phase)
        now = self.clock()
        if key == self.previous and not force: return
        if now - self.last < 15 and not force and phase == 'printing': return
        files = {}
        total = 0
        # Native files are observed twice. A changing set is not archived as coherent.
        paths = sorted(self.native.glob('pl_print*.json'))
        for path in paths:
            if path.is_symlink() or path.stat().st_size > 512 * 1024: return
            raw = path.read_bytes()
            total += len(raw)
            if total > 4 * 1024 * 1024: return
            files[path.name] = raw.decode('utf-8')
        if paths != sorted(self.native.glob('pl_print*.json')): return
        if any((self.native / name).read_text() != raw for name, raw in files.items()): return
        point = {'id': str(uuid.uuid4()), 'time': now, 'filename': stats['filename'],
                 'state': phase, 'filePosition': sd['file_position'],
                 'layer': stats.get('info', {}).get('current_layer'),
                 'position': s.get('gcode_move', {}).get('gcode_position'),
                 'task': s.get('print_task_config', {}),
                 'nativeFiles': {name: hashlib.sha256(raw.encode()).hexdigest() for name, raw in files.items()},
                 'kind': 'observation', 'resumable': False}
        # Archive survives native CANCEL_PRINT cleanup; it is never copied back to Klipper.
        atomic(self.folder / (point['id'] + '.json'), {'point': point, 'nativeFiles': files})
        self.points.insert(0, point)
        removed, self.points = self.points[30:], self.points[:30]
        atomic(self.path, {'version': 1, 'points': self.points})
        for old in removed:
            ident = old.get('id', '')
            if str(uuid.UUID(ident)) == ident:
                (self.folder / (ident + '.json')).unlink(missing_ok=True)
        self.last, self.previous = now, key

    def state(self):
        s = self.status()
        return {'points': self.points, 'nativeAvailable': s.get('virtual_sdcard', {}).get('pl_env_valid') is True,
                'status': s, 'afterCancelSupported': False,
                'attempt': json.loads((self.folder / 'attempt.json').read_text()) if (self.folder / 'attempt.json').exists() else None}

    def native_point(self, store):
        store.require_idle(calibration=True)
        if store.scheduler.active or store.timed_pause.active:
            raise ValueError('Сначала отмените отложенный запуск и таймер паузы.')
        drying = store.folder / 'drying' / 'state.json'
        if drying.exists() and json.loads(drying.read_text()).get('state') in ('heating', 'running', 'paused'):
            raise ValueError('Сначала отмените сушку.')
        s = self.status()
        if s.get('webhooks', {}).get('state') != 'ready' or s.get('virtual_sdcard', {}).get('pl_env_valid') is not True:
            raise ValueError('U1 не подтверждает штатную точку восстановления.')
        if s.get('virtual_sdcard', {}).get('is_active') is not False or s.get('print_stats', {}).get('state') not in ('standby', 'complete', 'cancelled'):
            raise ValueError('Принтер занят. Для паузы используйте обычное продолжение.')
        machine = s.get('machine_state_manager', {})
        if type(machine.get('main_state')) is bool or machine.get('main_state') not in (0, 'IDLE') or type(machine.get('action_code')) is bool or machine.get('action_code') not in (0, 'IDLE'):
            raise ValueError('U1 не находится в свободном состоянии.')
        errors = s.get('exception_manager', {}).get('exceptions')
        if not isinstance(errors, list) or errors or s.get('purifier', {}).get('power_detected') is not True:
            raise ValueError('Проверьте ошибки и подключение верхнего кожуха.')
        for name in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3'):
            if s.get(name, {}).get('target') != 0:
                raise ValueError('Перед подготовкой восстановления выключите текущий нагрев.')
        raw = {}
        for path in sorted(self.native.glob('pl_print*.json')):
            if path.is_symlink() or path.stat().st_size > 512 * 1024:
                raise ValueError('Неверный файл штатной точки.')
            raw[path.name] = path.read_bytes()
        if sum(map(len, raw.values())) > 4 * 1024 * 1024:
            raise ValueError('Штатная точка слишком велика.')
        env = json.loads(raw['pl_print_file_env.json'])
        if type(env.get('env_flag')) is not int or env['env_flag'] <= 0:
            raise ValueError('Не подтверждён идентификатор штатного задания восстановления.')
        source = Path(env['file_path'])
        roots = self.api('/server/files/roots')
        if isinstance(roots, dict): roots = roots.get('roots', [])
        root = next(Path(item['path']).resolve() for item in roots if item['name'] == 'gcodes')
        source = source.resolve(strict=True)
        if root not in source.parents or not source.is_file():
            raise ValueError('Исходный G-code не найден в каталоге печати.')
        h = hashlib.sha256()
        with source.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
        fingerprint = hashlib.sha256(json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}, sort_keys=True).encode() + h.digest()).hexdigest()
        identity = hashlib.sha256((str(source) + ':' + str(env['env_flag'])).encode()).hexdigest()
        return {'filename': str(source.relative_to(root)), 'fingerprint': fingerprint, 'identity': identity}

    def prepare(self, store):
        point = self.native_point(store)
        if (self.folder / ('attempt-' + point['identity'] + '.json')).exists():
            raise ValueError('Запрос для этой точки уже отправлялся. Проверьте результат на экране U1; автоматический повтор запрещён.')
        self.plans = {key: plan for key, plan in self.plans.items() if self.clock() - plan['time'] < 120}
        token = str(uuid.uuid4())
        self.plans[token] = {**point, 'time': self.clock()}
        return {'token': token, 'filename': point['filename']}

    def resume(self, store, payload):
        if payload.get('confirmed') is not True:
            raise ValueError('Подтвердите сохранность модели и зоны движения.')
        plan = self.plans.pop(payload.get('token', ''), None)
        if not plan or not 0 <= self.clock() - plan['time'] < 120:
            raise ValueError('Предварительная проверка устарела.')
        if (self.folder / ('attempt-' + plan['identity'] + '.json')).exists():
            raise ValueError('Повтор восстановления заблокирован.')
        current = self.native_point(store)
        if current != {key: plan[key] for key in ('filename', 'fingerprint', 'identity')}:
            raise ValueError('Штатная точка или исходный файл изменились. Повторите проверку.')
        attempt = {'time': self.clock(), 'filename': plan['filename'], 'state': 'sent'}
        atomic(self.folder / ('attempt-' + plan['identity'] + '.json'), attempt)
        atomic(self.folder / 'attempt.json', attempt)
        # Only the stock validated MCU/host point. Never restore archive files or positions.
        self.api('/printer/gcode/script', {'script': 'SDCARD_PRINT_PL_RESTORE'}, timeout=1800)
        return {'requested': True, 'filename': plan['filename']}
