"""U1 native calibration jobs. Browser-independent; never resume after service restart."""
import copy
import datetime
import json
from pathlib import Path
import re
import threading
import time
import uuid
from u1_feeder_settings import atomic

ACTIVE = {'starting', 'loading', 'calibrating', 'saving', 'finishing'}
QUERY = '/printer/objects/query?webhooks&print_stats&idle_timeout&machine_state_manager&exception_manager&print_task_config&purifier&extruder&extruder1&extruder2&extruder3&filament_feed%20left&filament_feed%20right&filament_motion_sensor%20e0_filament&filament_motion_sensor%20e1_filament&filament_motion_sensor%20e2_filament&filament_motion_sensor%20e3_filament'


def loaded(status, slot):
    sensor = status.get('filament_motion_sensor e%d_filament' % slot, {})
    return sensor.get('enabled') is True and sensor.get('filament_detected') is True


def reason(status, slot):
    types = status.get('print_task_config', {}).get('filament_type', [])
    material = types[slot].strip().upper() if len(types) > slot else ''
    if material == 'TPU' and loaded(status, slot):
        return ''
    feeder = status.get('filament_feed left' if slot < 2 else 'filament_feed right', {}).get('extruder%d' % slot, {})
    if not feeder.get('module_exist') or feeder.get('filament_detected') is not True:
        return 'Нет филамента в головке или податчике' if material == 'TPU' else 'Нет филамента в податчике'
    if not material or material == 'NONE':
        return 'Укажите материал филамента'
    if not loaded(status, slot):
        if feeder.get('disable_auto') is not False:
            return 'Требуется ручная загрузка в головку'
        if feeder.get('channel_error') != 'ok' or feeder.get('channel_error_state') != 'none':
            return 'Сначала устраните ошибку податчика'
        if feeder.get('channel_state') not in ('preload_finish', 'load_finish'):
            return 'Податчик ещё не готов к загрузке'
    return ''


def require_idle(status, cover=False):
    machine = status.get('machine_state_manager', {})
    if (status.get('webhooks', {}).get('state') != 'ready' or status.get('print_stats', {}).get('state') not in ('standby', 'complete', 'cancelled') or
            status.get('idle_timeout', {}).get('state') not in ('Idle', 'Ready') or machine.get('main_state') not in (0, 'IDLE') or
            machine.get('action_code') not in (0, 'IDLE') or status.get('exception_manager', {}).get('exceptions', [True])):
        raise ValueError('Калибровка доступна только на свободном принтере без активных ошибок.')
    if cover and status.get('purifier', {}).get('power_detected') is not True:
        raise ValueError('Пропал сигнал подключения верхнего кожуха. Очередь остановлена; проверьте кожух и его подключение.')


def signature(status, slot):
    task = status['print_task_config']
    return [task['filament_type'][slot], task['filament_color_rgba'][slot]]


def measured(logs, marker, slot):
    name = 'extruder' if slot == 0 else 'extruder%d' % slot
    fresh = [row for row in logs if row['time'] > marker]
    start = next((i for i, row in enumerate(fresh) if row['type'] == 'response' and row['message'].strip() == '// start flow calibration for ' + name), None)
    if start is None:
        raise ValueError('Начало калибровки выбранной головки не подтверждено журналом.')
    rows = fresh[start + 1:]
    if any(re.search(r'abort calibration|flow k is out of range|^!!|start flow calibration for ', row['message'], re.I) for row in rows):
        raise ValueError('Калибровка прервана или использован заводской K. Измеренный результат не подтверждён.')
    values = [re.fullmatch(r'// Got pressure advance: ([0-9.eE+-]+)\s*', row['message']) for row in rows if row['type'] == 'response']
    values = [float(value.group(1)) for value in values if value]
    if len(values) != 1 or not 0 <= values[0] <= 1:
        raise ValueError('Измеренный K не подтверждён журналом.')
    return values[0]


class CalibrationJobs:
    def __init__(self, api, folder, execute=None):
        self.api, self.execute = api, execute
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = self.folder / 'state.json'
        self.instance = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.thread = None
        self.pending = None
        self.plans = {}
        self.job = json.loads(self.file.read_text()) if self.file.exists() else {'state': 'idle', 'results': [], 'message': ''}
        if self.job['state'] in ACTIVE:
            self.update(state='interrupted', message='Сервис или принтер перезапускался. Очередь не возобновлена. Проверьте экран принтера и нагрев перед новым запуском.')

    @property
    def active(self):
        with self.lock:
            return self.job['state'] in ACTIVE

    def update(self, **values):
        with self.lock:
            self.job.update(values)
            self.job['updatedAt'] = time.time()
            atomic(self.file, json.dumps(self.job, ensure_ascii=False, allow_nan=False).encode())

    def state(self):
        with self.lock:
            return copy.deepcopy(self.job)

    def status(self):
        return self.api(QUERY)['status']

    def logs(self):
        return self.api('/server/gcode_store?count=1000')['gcode_store']

    def prepare(self, payload):
        if self.active or self.execute is None:
            raise ValueError('Калибровка уже выполняется или сервис запуска не готов.')
        heads = payload.get('heads')
        if not isinstance(heads, list) or not 1 <= len(heads) <= 4 or any(type(head) is not int or head not in range(4) for head in heads) or len(set(heads)) != len(heads):
            raise ValueError('Выберите головки от 1 до 4 без повторений.')
        if type(payload.get('saveResults')) is not bool:
            raise ValueError('Неверный режим сохранения результатов.')
        status = self.status()
        require_idle(status)
        for head in heads:
            if reason(status, head):
                raise ValueError('Головка %d: %s' % (head + 1, reason(status, head)))
        token = str(uuid.uuid4())
        plan = {'heads': sorted(heads), 'saveResults': payload['saveResults'], 'created': time.monotonic(),
                'signatures': {str(head): signature(status, head) for head in heads},
                'cover': status.get('purifier', {}).get('power_detected') is True}
        self.plans = {token: plan}
        return {'token': token}

    def start(self, payload):
        token = payload.get('token')
        with self.lock:
            if token and self.job.get('token') == token:
                return self.state()
            plan = self.plans.get(token) if isinstance(token, str) else None
            if not plan or time.monotonic() - plan['created'] > 30:
                raise ValueError('Подтверждение запуска устарело. Подтвердите запуск заново.')
            if self.active:
                raise ValueError('Калибровка уже выполняется.')
            status = self.status()
            require_idle(status, plan['cover'])
            for head in plan['heads']:
                if reason(status, head) or signature(status, head) != plan['signatures'][str(head)]:
                    raise ValueError('Состояние выбранных головок изменилось. Повторите выбор.')
            self.job = {'id': str(uuid.uuid4()), 'token': token, 'state': 'starting', 'heads': plan['heads'], 'activeSlot': None,
                        'results': [], 'stopRequested': False, 'message': '', 'createdAt': time.time()}
            self.update()
            self.thread = threading.Thread(target=self.run, args=(copy.deepcopy(plan),), daemon=True, name='u1-native-calibration')
            self.thread.start()
            return self.state()

    def stop(self):
        if self.active:
            self.update(stopRequested=True, message='Текущая штатная операция завершится; следующие операции запускаться не будут.')
        return self.state()

    def settled(self, cover=False):
        status = self.status()
        for _ in range(40):
            if status.get('idle_timeout', {}).get('state') != 'Printing' or status.get('machine_state_manager', {}).get('main_state') not in (0, 'IDLE'):
                break
            time.sleep(0.5)
            status = self.status()
        require_idle(status, cover)
        return status

    def capture(self, slot, sig):
        raw = self.api('/server/database/item?namespace=fluidd')['value']
        inventory, library = raw['u1_spool_inventory_v1'], raw['u1_filament_library_v1']
        spool = next((spool for spool in inventory['spools'] if spool['id'] == inventory['heads'][slot]), None)
        return {'inventory': inventory, 'library': library, 'spool': spool, 'signature': sig}

    def save_result(self, slot, value, capture, status):
        row = {'slot': slot, 'value': value, 'saved': 'Штатный K применён и сохранён принтером.', 'warning': ''}
        if capture is not None:
            spool = capture['spool']
            if spool is None:
                row['warning'] = 'Нет привязанной катушки: K остался в штатных настройках принтера.'
            else:
                try:
                    if signature(status, slot) != capture['signature'] or [spool['material'], spool['hex'].lstrip('#').upper() + 'FF'] != capture['signature']:
                        raise ValueError('Материал/цвет не совпал с привязанной катушкой.')
                    individual = capture['inventory'].get('individualCalibration') is True
                    record = spool if individual else next((color for color in capture['library']['entries'] if color['id'] == spool['colorId']), None)
                    if record is None:
                        raise ValueError('Основа катушки отсутствует в библиотеке.')
                    calibration = {**record.get('calibration', {}), 'pressureAdvance': value,
                                   'date': datetime.datetime.now().strftime('%Y-%m-%d'), 'method': 'Штатная калибровка U1 (K)'}
                    event = threading.Event()
                    task = {'event': event, 'payload': {'kind': 'spool', 'id': spool['id'], 'individual': individual, 'value': calibration,
                            'libraryRevision': capture['library']['revision'], 'inventoryRevision': capture['inventory']['revision']}}
                    with self.lock:
                        self.pending = task
                    self.update(state='saving')
                    if not event.wait(45):
                        with self.lock:
                            if self.pending is task:
                                self.pending = None
                        raise ValueError('Сервис хранения не подтвердил запись K. Повторный запуск теста не требуется.')
                    if task.get('error'):
                        raise ValueError(task['error'])
                    row['saved'] = 'K сохранён для катушки «%s».' % spool['name'] if individual else 'K сохранён в общей карточке «%s».' % record['name']
                except Exception as error:
                    row['warning'] = str(error) + ' Очередь остановлена.'
                    self.update(stopRequested=True)
        with self.lock:
            self.update(results=self.job['results'] + [row])

    def drain(self, store):
        # Called only by the existing data worker's main thread.
        with self.lock:
            task, self.pending = self.pending, None
        if task:
            try:
                store.handle(str(uuid.uuid4()), {'operation': 'calibration', 'payload': task['payload']})
            except Exception as error:
                task['error'] = str(error)
            finally:
                task['event'].set()

    def run(self, plan):
        touched_slot = None
        final_state, final_message = 'failed', 'Очередь не завершена.'
        try:
            for slot in plan['heads']:
                if self.state()['stopRequested']:
                    break
                status = self.status()
                require_idle(status, plan['cover'])
                if reason(status, slot) or signature(status, slot) != plan['signatures'][str(slot)]:
                    raise ValueError('Головка %d: наличие, материал или цвет изменились.' % (slot + 1))
                capture = self.capture(slot, signature(status, slot)) if plan['saveResults'] else None
                self.update(activeSlot=slot, state='starting')
                status = self.status()
                require_idle(status, plan['cover'])
                if reason(status, slot) or signature(status, slot) != plan['signatures'][str(slot)]:
                    raise ValueError('Состояние головки изменилось перед запуском.')
                if self.state()['stopRequested']:
                    break
                if not loaded(status, slot):
                    sensor = status.get('filament_motion_sensor e%d_filament' % slot, {})
                    if sensor.get('enabled') is not True:
                        raise ValueError('Невозможно подтвердить загрузку: датчик головки выключен или недоступен.')
                    self.update(state='loading')
                    touched_slot = slot
                    self.execute('AUTO_FEEDING EXTRUDER=%d LOAD=1\nM400' % slot)
                    status = self.settled(plan['cover'])
                    if not loaded(status, slot):
                        raise ValueError('Штатная загрузка не подтверждена датчиком. Калибровка не запущена.')
                marker = max([0] + [row['time'] for row in self.logs()])
                status = self.status()
                require_idle(status, plan['cover'])
                if not loaded(status, slot) or signature(status, slot) != plan['signatures'][str(slot)]:
                    raise ValueError('Загрузка или материал изменились. Калибровка не запущена.')
                if self.state()['stopRequested']:
                    break
                self.update(state='calibrating')
                touched_slot = slot
                self.execute('T%d A0\nFLOW_CALIBRATE\nM400' % slot)
                value = measured(self.logs(), marker, slot)
                after = self.settled(plan['cover'])
                actual = after.get('extruder' if slot == 0 else 'extruder%d' % slot, {}).get('pressure_advance')
                if type(actual) not in (int, float) or abs(actual - value) > 0.000001:
                    raise ValueError('K в принтере не совпал с измеренным. Очередь остановлена.')
                self.save_result(slot, value, capture, after)
            final_state = 'stopped' if self.state()['stopRequested'] else 'completed'
            final_message = 'Очередь остановлена.' if self.state()['stopRequested'] else 'Калибровка выбранных головок завершена.'
        except Exception as error:
            final_message = str(error) + ' Следующие головки не запускаются. Проверьте экран принтера перед повторным запуском.'
        finally:
            self.update(state='finishing')
            # Only the head touched by this job; never reset another print's heaters.
            if touched_slot is not None:
                try:
                    status = self.status()
                    require_idle(status)
                    name = 'extruder' if touched_slot == 0 else 'extruder%d' % touched_slot
                    if status.get(name, {}).get('target', 0) != 0:
                        self.execute('M104 S0 T%d A0' % touched_slot)
                except Exception:
                    final_message += ' Автоматическое выключение нагрева не подтверждено; проверьте температуру на принтере.'
            self.update(state=final_state, message=final_message, activeSlot=None)
