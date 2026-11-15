"""U1 magnet insertion: exact layer boundaries, stock pause/resume, bed parking."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import uuid

STATES = {'armed', 'active', 'pausing', 'waiting_insertion'}
FOLDER = '/userdata/u1-addons/filament-ui-data/magnet-pauses'
COMMAND_VERSION = 2
MAGNET_COMMANDS = {name: 'COMPANION_MAGNET_' + name.upper() for name in ('arm', 'clear', 'pause')}


def parse_layers(text):
    if not isinstance(text, str) or len(text) > 4096:
        raise ValueError('Введите номера слоёв через запятую или пробел.')
    tokens = [v for v in re.split(r'[,\s]+', text.strip()) if v]
    if not tokens or any(not re.fullmatch(r'[0-9]+', v) for v in tokens):
        raise ValueError('Нужны целые положительные номера слоёв, например 12, 24 36.')
    values = sorted(set(map(int, tokens)))
    if len(values) > 100 or values[0] < 1 or values[-1] > 100000:
        raise ValueError('Допустимо до 100 слоёв с номерами от 1 до 100000.')
    return values


def signature(path):
    s = Path(path).stat()
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]


def analyse(path, layers):
    """Scan the original bytes, not transformed profile commands or UI counters."""
    path = Path(path)
    before = signature(path)
    if before[2] > 256 * 1024 * 1024:
        raise ValueError('Для пауз пока поддерживаются файлы до 256 МБ.')
    found, total, count, offset, boundary = {}, None, 0, 0, False
    absolute, e = True, 0.0
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for raw in stream:
            h.update(raw)
            text = raw.decode('utf-8').strip()
            if text.upper() == ';LAYER_CHANGE': boundary = True
            line = text.split(';', 1)[0].strip().upper()
            if line == 'M82': absolute = True
            if line == 'M83': absolute = False
            if re.match(r'^G(?:0|1|92)(?:\s|$)', line):
                value = re.search(r'(?:^|\s)E([-+]?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|$)', line)
                if value:
                    new_e = float(value[1])
                    if not line.startswith('G92') and boundary and (new_e - e if absolute else new_e) > 0:
                        raise ValueError('Маркер слоя стоит после подачи пластика. Такой файл пока не поддерживается.')
                    e = new_e if absolute or line.startswith('G92') else e + new_e
            if re.match(r'^SET_PRINT_STATS_INFO(?:\s|$)', line):
                t = re.search(r'\bTOTAL_LAYER=(\d+)(?=\s|$)', line)
                n = re.search(r'\bCURRENT_LAYER=(\d+)(?=\s|$)', line)
                if t:
                    value = int(t[1])
                    if total is not None and total != value: raise ValueError('Число слоёв в файле меняется.')
                    total = value
                if n and int(n[1]) > 0:
                    layer = int(n[1])
                    if layer != count + 1 or not boundary:
                        raise ValueError('Нужны последовательные маркеры слоёв Snapmaker Orca.')
                    count = layer; boundary = False
                    if layer in layers: found[str(layer)] = offset
            offset += len(raw)
    if signature(path) != before: raise ValueError('Файл изменился при проверке. Повторите.')
    if not total or count != total or any(str(n) not in found for n in layers):
        raise ValueError('Нет выбранного слоя или достоверных маркеров. Нужен G-code Snapmaker Orca.')
    return {'signature': before, 'sha256': h.hexdigest(), 'total': total, 'markers': found}


def parking_delta(gcode_z, physical_z, maximum, limit=270.5):
    values = (gcode_z, physical_z, maximum, limit)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError('Неизвестная позиция Z.')
    target = 200.0 if gcode_z < 195 else gcode_z + (5 if gcode_z < 265 else 2)
    return max(0.0, min(target - gcode_z, limit - gcode_z, maximum - 2 - physical_z))


def save(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
    temp = path.with_suffix('.next')
    with temp.open('wb') as f:
        os.chmod(temp, 0o600); f.write(raw); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


class U1MagnetPause:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.folder = Path(config.get('data_path', FOLDER))
        self.root = Path(config.get('gcode_root', '/userdata/gcodes')).resolve()
        self.file = self.folder / 'state.json'
        self.plan = {'state': 'idle', 'layers': [], 'done': [], 'message': ''}
        self.park = None; self.cycle = 0; self.job = str(uuid.uuid4()); self.available = False
        if self.file.exists():
            try:
                old = json.loads(self.file.read_text())
                if old.get('state') in STATES:
                    self.plan = {**old, 'state': 'needs_review', 'message': 'Klipper перезапускался. План отключён, настройте оставшиеся слои заново.'}
            except Exception: self.plan['message'] = 'Старый план повреждён; автоматические паузы отключены.'
        for name, handler in [(MAGNET_COMMANDS['arm'], self.arm), (MAGNET_COMMANDS['clear'], self.clear), (MAGNET_COMMANDS['pause'], self.manual)]:
            self.gcode.register_command(name, handler)
        self.printer.register_event_handler('klippy:ready', self.ready)
        self.printer.register_event_handler('print_stats:new_task_start', self.new_job)
        for name in ('print_stats:complete', 'print_stats:cancelled'):
            self.printer.register_event_handler(name, self.ended)

    def status(self, name): return self.printer.lookup_object(name).get_status(self.printer.get_reactor().monotonic())

    def persist(self): save(self.file, self.plan)

    def ready(self, *args):
        self.sd = self.printer.lookup_object('virtual_sdcard')
        self.pause = self.printer.lookup_object('pause_resume')
        self.move = self.printer.lookup_object('gcode_move')
        self.head = self.printer.lookup_object('toolhead')
        installed = []
        try:
            for name, method in [('SET_PRINT_STATS_INFO', self.layer), ('PAUSE', self.observed_pause), ('RESUME', self.resume), ('RESUME_BASE', self.resume_base)]:
                old = self.gcode.register_command(name, None)
                if old is None: raise ValueError('Не найдена штатная команда ' + name)
                installed.append((name, old)); setattr(self, 'original_' + name, old)
                self.gcode.register_command(name, method)
            self.available = True
        except Exception as error:
            for name, old in reversed(installed):
                self.gcode.register_command(name, None); self.gcode.register_command(name, old)
            self.plan['state'] = 'unsupported'; self.plan['message'] = str(error)
        try: self.persist()
        except OSError as error:
            self.available = False; self.plan.update(state='blocked', message='Журнал пауз недоступен: ' + str(error))

    def new_job(self, *args):
        self.job = str(uuid.uuid4()); self.park = None
        if self.plan['state'] in STATES:
            if self.plan['state'] == 'armed' and self.matches():
                self.plan.update(state='active', job=self.job)
            else:
                self.plan.update(state='cancelled', message='Запущен другой экземпляр печати; прежний план отключён.')
            try: self.persist()
            except OSError: self.plan['message'] = 'Не удалось записать смену задания; перед паузой будет повторная проверка журнала.'

    def ended(self, *args):
        self.park = None
        self.plan['requiresManualResume'] = False
        if self.plan['state'] in STATES:
            self.plan.update(state='finished', message='Задание завершено или отменено; план отключён.')
        try: self.persist()
        except OSError: pass

    def matches(self):
        try:
            path = Path(self.sd.file_path()).resolve()
            return path == self.root / self.plan['filename'] and signature(path) == self.plan['signature']
        except (OSError, TypeError, KeyError): return False

    def guard(self, paused=False):
        if not self.available: raise ValueError('Модуль пауз не готов.')
        stats = self.status('print_stats'); machine = self.status('machine_state_manager')
        # U1 notes paused only after the virtual-SD command returns. During
        # an in-file PAUSE, PAUSE_BASE has already saved PAUSE_STATE and set
        # is_paused, but print_stats legitimately still says printing.
        sd_pause_pending = (paused and stats['state'] == 'printing'
                            and self.pause.is_paused and self.sd.is_cmd_from_sd()
                            and getattr(self.sd, 'must_pause_work', False)
                            and bool(self.sd.file_path()))
        if stats['state'] not in (('paused',) if paused else ('printing', 'paused')) and not sd_pause_pending:
            raise ValueError('Нет активной печати.')
        if str(machine['main_state']) not in ('PRINTING', '1') or str(machine['action_code']) not in ('IDLE', '0'):
            raise ValueError('Дождитесь завершения штатной операции U1.')
        if stats.get('exception') or self.status('exception_manager').get('exceptions', [True]):
            raise ValueError('Сначала устраните ошибку принтера.')
        if self.status('purifier').get('power_detected') is not True:
            raise ValueError('Не подтверждено подключение верхнего кожуха.')
        if not set('xyz').issubset(self.status('toolhead').get('homed_axes', '')):
            raise ValueError('Неизвестны координаты XYZ. Опускание запрещено.')
        if paused and not self.pause.is_paused: raise ValueError('Штатная пауза не подтверждена.')

    def arm(self, gcmd):
        try:
            if not self.available: raise ValueError('Модуль не готов.')
            token = gcmd.get('TOKEN')
            if not re.fullmatch(r'[0-9a-f-]{36}', token) or str(uuid.UUID(token)) != token: raise ValueError('Неверный план.')
            source = self.folder / (token + '-prepared.json')
            if source.is_symlink() or source.stat().st_size > 65536: raise ValueError('Неверный файл плана.')
            plan = json.loads(source.read_text())
            if plan.get('version') != 1 or not 0 <= time.time() - plan['createdAt'] < 180: raise ValueError('Проверка плана устарела.')
            path = (self.root / plan['filename']).resolve()
            if self.root not in path.parents or signature(path) != plan['signature']: raise ValueError('G-code изменился.')
            layers = parse_layers(','.join(map(str, plan['layers'])))
            if layers != plan['layers'] or any(str(n) not in plan['markers'] or n > plan['total'] for n in layers): raise ValueError('Некорректные слои.')
            stock = self.printer.lookup_object('gcode_macro SET_PRINT_STATS_INFO').variables
            if any(stock.get(name, {}).get('enable') for name in ('pause_next_layer', 'pause_at_layer')):
                raise ValueError('Сначала отключите другую штатную паузу по слою.')
            state = self.status('print_stats')
            if plan['mode'] == 'current':
                if plan.get('job') != self.job or state['state'] not in ('printing', 'paused') or not self.sd.file_path() or Path(self.sd.file_path()).resolve() != path:
                    raise ValueError('Экземпляр печати изменился.')
                current = state.get('info', {}).get('current_layer') or 0
                if any(n <= current for n in layers): raise ValueError('Выберите только ещё не начатые слои.')
                phase = 'active'
            elif plan['mode'] == 'next' and state['state'] in ('standby', 'complete', 'cancelled'):
                phase = 'armed'
            else: raise ValueError('Состояние печати изменилось.')
            updated = {**plan, 'state': phase, 'job': self.job if phase == 'active' else None, 'done': [], 'message': 'План пауз сохранён на принтере.'}
            save(self.file, updated); self.plan = updated
            try: source.unlink()
            except OSError: pass
        except Exception as error: raise gcmd.error(str(error))

    def clear(self, gcmd):
        self.plan.update(state='cancelled', message='План отключён. Текущая пауза не снимается.'); self.persist()

    def observed_pause(self, gcmd):
        was = self.pause.is_paused
        try: return self.original_PAUSE(gcmd)
        finally:
            if not was and self.pause.is_paused: self.cycle += 1; self.park = None

    def lower(self):
        self.guard(paused=True)
        key = (self.job, self.cycle)
        if self.park and self.park['key'] == key:
            if self.park['state'] != 'parked': raise ValueError('Позиция стола после парковки не подтверждена. Продолжение заблокировано.')
            return
        saved = self.move.saved_states.get('PAUSE_STATE')
        if not isinstance(saved, dict): raise ValueError('Не найдена штатная точка возврата PAUSE_STATE.')
        before = copy.deepcopy(saved)
        self.head.wait_moves()
        hs, gs = self.status('toolhead'), self.status('gcode_move')
        delta = parking_delta(gs['gcode_position'][2], hs['position'][2], hs['axis_maximum'][2])
        self.park = {'key': key, 'pauseState': before, 'state': 'moving',
                     'source': self.sd.file_path(), 'position': self.sd.get_file_position()}
        # No firmware restart, homing, M84, PRINT_END or edits to PAUSE_STATE.
        if delta >= 0.1:
            self.gcode.run_script_from_command('SAVE_GCODE_STATE NAME=U1_MAGNET_MODAL\nG91\nG1 Z%.6f F600\nM400\nRESTORE_GCODE_STATE NAME=U1_MAGNET_MODAL MOVE=0' % delta)
        if self.move.saved_states.get('PAUSE_STATE') != before:
            self.park['state'] = 'blocked'; raise ValueError('Штатная точка возврата изменилась. Продолжение заблокировано.')
        self.park['state'] = 'parked'

    def manual(self, gcmd):
        try:
            if gcmd.get_int('CONFIRM', 0) != 1: raise ValueError('Подтвердите паузу и опускание стола.')
            self.guard()
            self.plan['requiresManualResume'] = True; self.persist()
            if not self.pause.is_paused: self.gcode.run_script_from_command('PAUSE')
            self.lower()
            self.plan['message'] = 'Стол опущен. Вставьте магниты и продолжите печать вручную.'
            if self.plan['state'] == 'active': self.plan['state'] = 'waiting_insertion'
            self.persist()
        except Exception as error: raise gcmd.error(str(error))

    def layer(self, gcmd):
        result = self.original_SET_PRINT_STATS_INFO(gcmd)
        if not self.sd.is_cmd_from_sd() or self.plan['state'] not in ('armed', 'active'): return result
        if self.plan['state'] == 'armed':
            if not self.matches():
                self.plan.update(state='cancelled', message='Другой файл: план не применяется.'); self.persist(); return result
            self.plan.update(state='active', job=self.job)
        if self.plan.get('job') != self.job: return result
        layer = gcmd.get_int('CURRENT_LAYER', 0)
        if layer not in self.plan['layers'] or layer in self.plan['done']: return result
        try:
            if not self.matches() or self.sd.file_position != self.plan['markers'].get(str(layer)):
                raise ValueError('Файл или граница слоя изменились.')
            self.guard()
            self.plan['done'].append(layer)
            self.plan.update(state='pausing', requiresManualResume=True, message='Пауза перед слоем %d: установка магнитов.' % layer); self.persist()
            if not self.pause.is_paused: self.gcode.run_script_from_command('PAUSE')
            self.lower()
            self.plan.update(state='waiting_insertion', message='Вставьте магниты, уберите инструменты и подтвердите обычное продолжение.'); self.persist()
        except Exception as error:
            self.plan.update(state='blocked', message=str(error))
            # Stop file dispatch even if the richer stock pause reports an error.
            self.sd.do_pause()
            try: self.persist()
            except Exception: pass
            # An exception escaping a virtual-SD command cancels the U1 job.
            # Keep dispatch stopped, report the fault, and never retry motion.
            self.gcode.respond_info('Пауза для магнитов заблокирована: ' + str(error))
        return result

    def resume_guard(self):
        if not self.park or self.park['key'][0] != self.job: return
        if self.park['state'] != 'parked' or not set('xyz').issubset(self.status('toolhead').get('homed_axes', '')):
            raise ValueError('Позиция стола после парковки не подтверждена. Продолжение заблокировано.')
        saved = self.move.saved_states.get('PAUSE_STATE', {})
        if (self.sd.file_path() != self.park['source'] or self.sd.file_position != self.park['position']
                or saved.get('last_position', [])[:3] != self.park['pauseState'].get('last_position', [])[:3]):
            raise ValueError('Файл или штатная точка возврата изменились. Продолжение заблокировано.')

    def resume(self, gcmd):
        try: self.resume_guard()
        except Exception as error: raise gcmd.error(str(error))
        return self.original_RESUME(gcmd)

    def resume_base(self, gcmd):
        try: self.resume_guard()
        except Exception as error: raise gcmd.error(str(error))
        result = self.original_RESUME_BASE(gcmd)
        if not self.pause.is_paused:
            self.park = None
            self.plan['requiresManualResume'] = False
            if self.plan['state'] == 'waiting_insertion':
                self.plan.update(state='active', message='Печать продолжена.'); self.persist()
            else: self.persist()
        return result

    def get_status(self, eventtime=None):
        return {**copy.deepcopy(self.plan), 'version': 1, 'available': self.available,
                'commandVersion': COMMAND_VERSION, 'layerPauseVersion': 2, 'runtimeJob': self.job,
                'parked': bool(self.park and self.park['state'] == 'parked'),
                'parkingState': self.park['state'] if self.park else None,
                'currentFilename': self.status('print_stats').get('filename', '')}


def load_config(config): return U1MagnetPause(config)
