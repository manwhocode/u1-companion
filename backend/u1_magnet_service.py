"""Mailbox/preflight for the printer-resident layer pause module."""
import json
from pathlib import Path
import time
import uuid
from u1_magnet_pause import parse_layers, analyse, save, MAGNET_COMMANDS, COMMAND_VERSION


class MagnetService:
    def __init__(self, api, folder):
        self.api, self.folder = api, Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)

    def state(self):
        s = self.api('/printer/objects/query?u1_magnet_pause&print_stats')['status']
        return {**s.get('u1_magnet_pause', {'available': False, 'message': 'Модуль пауз не установлен.'}),
                'printState': s.get('print_stats', {}).get('state'),
                'currentLayer': s.get('print_stats', {}).get('info', {}).get('current_layer') or 0}

    def require_commands(self, state):
        if not state.get('available') or state.get('commandVersion', 0) < COMMAND_VERSION:
            raise ValueError('Модуль пауз требует обновления команд. Обновление разрешено только после окончания печати.')

    def prepare(self, store, payload):
        if store.dryer.state().get('state') in ('heating', 'running', 'paused', 'interrupted'):
            raise ValueError('Сначала отмените сушку.')
        state = self.state()
        self.require_commands(state)
        if store.timed_pause.active or store.scheduler.active or store.calibration_jobs.active:
            raise ValueError('Сначала отключите таймер продолжения/расписание или дождитесь калибровки.')
        layers = parse_layers(payload.get('layers'))
        mode = 'current' if state['printState'] in ('printing', 'paused') else 'next'
        if payload.get('mode') != mode or (mode == 'current' and payload.get('job') != state.get('runtimeJob')):
            raise ValueError('Печать изменилась. Откройте настройку пауз заново.')
        filename = state.get('currentFilename') if mode == 'current' else payload.get('filename')
        if not isinstance(filename, str) or not filename or len(filename) > 512:
            raise ValueError('Выберите G-code на принтере.')
        roots = self.api('/server/files/roots')
        if isinstance(roots, dict): roots = roots['roots']
        root = next(Path(v['path']).resolve() for v in roots if v['name'] == 'gcodes')
        path = (root / filename).resolve(strict=True)
        if root not in path.parents or not path.is_file(): raise ValueError('Неверный путь G-code.')
        if mode == 'current' and any(n <= state['currentLayer'] for n in layers):
            raise ValueError('Укажите только ещё не начатые слои.')
        result = analyse(path, layers)
        token = str(uuid.uuid4())
        plan = {'version': 1, 'token': token, 'createdAt': time.time(), 'mode': mode,
                'filename': str(path.relative_to(root)), 'layers': layers,
                'job': state.get('runtimeJob') if mode == 'current' else None, **result}
        save(self.folder / (token + '-prepared.json'), plan)
        for old in self.folder.glob('*-prepared.json'):
            if time.time() - old.stat().st_mtime > 1800: old.unlink()
        return {k: plan[k] for k in ('token', 'filename', 'layers', 'total', 'mode')}

    def arm(self, payload):
        token = payload.get('token', '')
        if payload.get('confirmed') is not True or str(uuid.UUID(token)) != token:
            raise ValueError('Подтвердите план пауз.')
        self.require_commands(self.state())
        path = self.folder / (token + '-prepared.json')
        plan = json.loads(path.read_text())
        if not 0 <= time.time() - plan['createdAt'] < 180: raise ValueError('Проверка плана устарела.')
        # Consume on the worker side before dispatch; no retry after lost response.
        reservation = self.folder / (token + '-sent.json')
        with reservation.open('x') as output:
            json.dump({'time': time.time()}, output); output.flush()
            import os
            os.fsync(output.fileno())
        self.api('/printer/gcode/script', {'script': MAGNET_COMMANDS['arm'] + ' TOKEN=' + token}, timeout=15)
        result = self.state()
        if result.get('token') != token or result.get('state') not in ('armed', 'active', 'pausing', 'waiting_insertion'):
            raise ValueError('План пауз не подтверждён принтером. Обновите состояние; автоматического повтора нет.')
        return result

    def action(self, store, ident, payload):
        if not isinstance(ident, str) or str(uuid.UUID(ident)) != ident:
            raise ValueError('Некорректный идентификатор действия.')
        action = payload.get('action')
        if action not in ('pause', 'clear') or payload.get('confirmed') is not True:
            raise ValueError('Подтвердите действие.')
        state = self.state()
        self.require_commands(state)
        if action == 'pause' and (state.get('printState') not in ('printing', 'paused') or state.get('runtimeJob') != payload.get('job')):
            raise ValueError('Экземпляр печати изменился.')
        if action == 'pause' and store.timed_pause.active:
            store.timed_pause.update(state='cancelled', message='Автопродолжение отключено для установки магнитов.')
        if action == 'clear' and state.get('token') != payload.get('token'):
            raise ValueError('План изменился. Обновите окно.')
        path = self.folder / (ident + '-action-sent.json')
        with path.open('x') as output:
            json.dump({'action': action}, output); output.flush()
            import os
            os.fsync(output.fileno())
        script = MAGNET_COMMANDS['pause'] + ' CONFIRM=1' if action == 'pause' else MAGNET_COMMANDS['clear']
        self.api('/printer/gcode/script', {'script': script}, timeout=120)
        result = self.state()
        if action == 'pause':
            if result.get('runtimeJob') != payload.get('job') or result.get('printState') != 'paused':
                raise ValueError('Штатная пауза не подтверждена. Проверьте принтер; автоматического повтора нет.')
            if result.get('parked') is not True or result.get('parkingState') != 'parked':
                raise ValueError('Позиция стола после парковки не подтверждена. Продолжение заблокировано.')
        elif result.get('state') != 'cancelled':
            raise ValueError('Отмена плана не подтверждена. Обновите состояние; автоматического повтора нет.')
        return result
