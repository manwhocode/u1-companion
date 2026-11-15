"""Versioned U1 user-data snapshots and serialized requests via Moonraker."""
import copy
import datetime
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import time
import uuid
import urllib.error
import urllib.parse

FORMAT = 'u1-filament-data'
SELECTION_FORMAT = 'u1-filament-selection'
SCOPES = {'full', 'colors', 'spools', 'cores'}
VERSION = 1
SPOOL_TEMPERATURE_OVERRIDES = True
PRINT_ERROR_LOG = True
CUMULATIVE_FILAMENT_STATS = True
MAINTENANCE_COUNTERS = True
from u1_maintenance import KEY as MAINTENANCE, Maintenance, validate as validate_maintenance, merge as merge_maintenance, totals as maintenance_totals
LIMIT = 8 * 1024 * 1024
CONTROL = 'u1_data_storage_v1'
REQUESTS = 'u1_addon_requests'
RESULTS = 'u1_addon_results'
KEYS = {'library': 'u1_filament_library_v1', 'inventory': 'u1_spool_inventory_v1', 'usage': 'u1_spool_usage_v1'}
MATERIALS = {'PLA', 'PETG', 'ABS', 'ASA', 'TPU', 'PVA', 'PA', 'PC'}
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, field, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError('Некорректное поле «' + field + '».')
    return value


def number(value, field, maximum=1e9):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError('Некорректное число «' + field + '».')


def fields(value, allowed, field):
    if not isinstance(value, dict) or set(value) - set(allowed.split()):
        raise ValueError('Неизвестные поля или формат «' + field + '».')


def rows(value, field, maximum=20000):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError('Некорректный список «' + field + '».')
    return value


def preset(value, spool=False):
    allowed = 'id name manufacturer material hex secondaryHex fullSpectrum calibration nozzleTemperature bedTemperature'
    if spool:
        allowed += ' colorId coreId coreName grams tare accountedGrams pricePerGram'
    fields(value, allowed, 'карточка')
    text(value.get('id'), 'ID', 120)
    text(value.get('name'), 'название', 100)
    if value.get('material') not in MATERIALS or not re.fullmatch(r'#[0-9a-fA-F]{6}', value.get('hex', '')):
        raise ValueError('Неверный материал или HEX.')
    value['hex'] = value['hex'].upper()
    if 'manufacturer' in value and (not isinstance(value['manufacturer'], str) or len(value['manufacturer']) > 80):
        raise ValueError('Некорректный производитель.')
    if 'secondaryHex' in value and not re.fullmatch(r'#[0-9a-fA-F]{6}', value['secondaryHex']):
        raise ValueError('Некорректный второй HEX.')
    if 'secondaryHex' in value:
        value['secondaryHex'] = value['secondaryHex'].upper()
    if 'fullSpectrum' in value and type(value['fullSpectrum']) is not bool:
        raise ValueError('Некорректный признак Full Spectrum.')
    if 'calibration' in value:
        calibration(value['calibration'])
    for field, minimum, maximum in (('nozzleTemperature', 150, 300), ('bedTemperature', 20, 100)):
        if field in value:
            number(value[field], field, maximum)
            if value[field] < minimum:
                raise ValueError('Температура вне допустимого диапазона: ' + field)
    if spool:
        for field in ('colorId', 'coreId', 'coreName'):
            text(value.get(field), field, 120)
        for field in ('grams', 'tare'):
            number(value.get(field), field)
        for field in ('accountedGrams', 'pricePerGram'):
            if field in value and value[field] is not None:
                number(value[field], field)


def calibration(value):
    fields(value, 'pressureAdvance flowRatio date method notes', 'калибровка')
    if not any(field in value for field in ('pressureAdvance', 'flowRatio')):
        raise ValueError('Укажите K или Flow Ratio.')
    if 'pressureAdvance' in value:
        number(value['pressureAdvance'], 'Pressure Advance', 1)
    if 'flowRatio' in value:
        number(value['flowRatio'], 'Flow Ratio', 3)
        if value['flowRatio'] == 0:
            raise ValueError('Flow Ratio должен быть больше 0.')
    date = text(value.get('date'), 'дата калибровки', 10)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        raise ValueError('Дата калибровки: ГГГГ-ММ-ДД.')
    datetime.date.fromisoformat(date)
    text(value.get('method'), 'метод калибровки', 100)
    if 'notes' in value and (not isinstance(value['notes'], str) or len(value['notes']) > 1000):
        raise ValueError('Примечание к калибровке: не больше 1000 символов.')


def unique(items, field):
    ids = [item['id'] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Повторяющиеся ID в «' + field + '».')


def validate_data(source):
    data = copy.deepcopy(source)
    fields(data, 'library inventory usage reviews maintenance', 'данные')
    if set(data) - {'maintenance'} != set(KEYS) | {'reviews'}:
        raise ValueError('В файле отсутствуют обязательные разделы.')
    library = data['library']
    fields(library, 'revision entries trash', 'библиотека')
    library.setdefault('trash', [])
    if not isinstance(library.get('revision'), str):
        raise ValueError('Некорректная версия библиотеки.')
    colors = rows(library.get('entries'), 'цвета') + rows(library['trash'], 'корзина цветов')
    for color in colors:
        preset(color)
    unique(colors, 'цвета и корзина')
    inventory = data['inventory']
    fields(inventory, 'revision spools cores heads trash individualCalibration', 'катушки')
    if 'individualCalibration' in inventory and type(inventory['individualCalibration']) is not bool:
        raise ValueError('Некорректный режим калибровки.')
    inventory.setdefault('trash', [])
    if not isinstance(inventory.get('revision'), str):
        raise ValueError('Некорректная версия катушек.')
    spools = rows(inventory.get('spools'), 'катушки') + rows(inventory['trash'], 'корзина катушек')
    for spool in spools:
        preset(spool, True)
    unique(spools, 'катушки и корзина')
    cores = rows(inventory.get('cores'), 'пустые катушки')
    for core in cores:
        fields(core, 'id name kind grams', 'пустая катушка')
        for field in ('id', 'name', 'kind'):
            text(core.get(field), field, 120)
        number(core.get('grams'), 'вес тары')
    unique(cores, 'пустые катушки')
    heads = rows(inventory.get('heads'), 'головки', 4)
    active = {spool['id'] for spool in inventory['spools']}
    if len(heads) != 4 or any(head is not None and head not in active for head in heads):
        raise ValueError('Повреждены привязки головок.')
    assigned = [head for head in heads if head is not None]
    if len(assigned) != len(set(assigned)):
        raise ValueError('Одна катушка назначена нескольким головкам.')
    usage = data['usage']
    fields(usage, 'totals records errors archivedRecords archivedErrors', 'расход')
    for key in ('archivedRecords', 'archivedErrors'):
        if key in usage:
            items = rows(usage[key], key, 100000)
            if any(not isinstance(item, str) or not 1 <= len(item) <= 120 for item in items) or len(set(items)) != len(items):
                raise ValueError('Некорректный архив списка журнала.')
    if not isinstance(usage.get('totals'), dict) or len(usage['totals']) > 40000:
        raise ValueError('Некорректные итоги расхода.')
    for ident, amount in usage['totals'].items():
        text(ident, 'ID расхода', 120)
        number(amount, 'расход')
    records = rows(usage.get('records'), 'история', 50000)
    for record in records:
        fields(record, 'id filename status time rows state method', 'задание')
        for field in ('id', 'filename', 'status'):
            text(record.get(field), field, 1024 if field == 'filename' else 120)
        number(record.get('time'), 'время', 1e12)
        if record.get('state') not in ('applied', 'review') or record.get('method') not in ('measured', 'estimate', 'manual'):
            raise ValueError('Неизвестный статус расхода.')
        for row in rows(record.get('rows'), 'расход по головкам', 4):
            fields(row, 'head required mm spoolId name pricePerGram grams colorId colorName', 'строка расхода')
            text(row.get('spoolId'), 'ID катушки', 120)
            if type(row.get('head')) is not int or row['head'] not in range(4):
                raise ValueError('Некорректная головка в расходе.')
            for field in ('required', 'mm', 'grams', 'pricePerGram'):
                if field in row:
                    number(row[field], field)
            if 'grams' not in row:
                raise ValueError('Не указан расход.')
            if 'name' in row:
                text(row['name'], 'название катушки', 100)
            for field, maximum in (('colorId', 120), ('colorName', 100)):
                if field in row:
                    text(row[field], field, maximum)
            if 'colorName' in row and 'colorId' not in row:
                raise ValueError('Не указан ID цвета в расходе.')
        if len({row['spoolId'] for row in record['rows']}) != len(record['rows']):
            raise ValueError('Повторяющаяся катушка в одном задании.')
    unique(records, 'задания')
    errors = rows(usage.get('errors', []), 'ошибки печати', 10000)
    for event in errors:
        fields(event, 'id jobId filename time code message severity source spools jobStatus closedAt', 'ошибка печати')
        for field, maximum in (('id', 64), ('jobId', 16), ('filename', 1024), ('code', 80), ('message', 1000), ('jobStatus', 120)):
            text(event.get(field), field, maximum)
        if not re.fullmatch(r'[0-9a-f]{64}', event['id']) or not re.fullmatch(r'[0-9A-Fa-f]{1,16}', event['jobId']):
            raise ValueError('Некорректный идентификатор ошибки печати.')
        if event.get('source') not in ('u1', 'observed', 'history') or type(event.get('severity')) is not int or not 0 <= event['severity'] <= 9:
            raise ValueError('Некорректный источник или уровень ошибки.')
        number(event.get('time'), 'время ошибки', 1e12)
        if 'closedAt' in event:
            number(event['closedAt'], 'время снятия сообщения', 1e12)
        links = rows(event.get('spools'), 'катушки задания', 4)
        for link in links:
            fields(link, 'head spoolId name colorId colorName material hex manufacturer', 'связь ошибки с катушкой')
            if type(link.get('head')) is not int or link['head'] not in range(4):
                raise ValueError('Некорректная головка в ошибке печати.')
            for field, maximum in (('spoolId', 120), ('name', 100), ('colorId', 120), ('colorName', 100), ('manufacturer', 80), ('material', 20), ('hex', 7)):
                if field in link:
                    text(link[field], field, maximum)
            if not link.get('spoolId') or not link.get('name'):
                raise ValueError('Не определена катушка в сохранённой связи ошибки.')
            if 'hex' in link and not re.fullmatch(r'#[0-9a-fA-F]{6}', link['hex']):
                raise ValueError('Некорректный HEX в истории ошибок.')
        if len({link['head'] for link in links}) != len(links):
            raise ValueError('Повтор головки в ошибке печати.')
    unique(errors, 'ошибки печати')
    if 'maintenance' in data:
        validate_maintenance(data['maintenance'])
    reviews = data['reviews']
    if not isinstance(reviews, dict) or len(reviews) > 50000:
        raise ValueError('Некорректные подтверждения расхода.')
    for ident, decision in reviews.items():
        text(ident, 'ID подтверждения', 120)
        if not re.fullmatch(r'[0-9A-Fa-f]{1,16}', ident):
            raise ValueError('Некорректный ID подтверждения.')
        fields(decision, 'time grams', 'подтверждение')
        number(decision.get('time'), 'время подтверждения', 1e12)
        for amount in rows(decision.get('grams'), 'подтверждённые граммы', 4):
            number(amount, 'подтверждённые граммы', 100000)
    return data


def selected_data(source, scope):
    if scope not in SCOPES:raise ValueError('Выберите состав данных.')
    data=validate_data(source)
    if scope=='full':return data
    result=state_from_raw({})
    if scope=='colors':result['library']=data['library']
    if scope=='cores':result['inventory']['cores']=data['inventory']['cores']
    if scope=='spools':
        for section in ('spools','trash'):
            result['inventory'][section]=data['inventory'][section]
            for row in result['inventory'][section]:
                spent=max(0,data['usage']['totals'].get(row['id'],0)-row.get('accountedGrams',0))
                row['grams']=round(max(0,row['grams']-spent),6);row['accountedGrams']=0
        spools=result['inventory']['spools']+result['inventory']['trash']
        color_ids={s['colorId'] for s in spools};core_ids={s['coreId'] for s in spools}
        for section in ('entries','trash'):result['library'][section]=[c for c in data['library'][section] if c['id'] in color_ids]
        result['inventory']['cores']=[c for c in data['inventory']['cores'] if c['id'] in core_ids]
    return validate_data(result)


def document(data, scope='full'):
    return {'format': FORMAT if scope=='full' else SELECTION_FORMAT, 'version': VERSION,
            **({'scope':scope} if scope!='full' else {}),
            'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'data': selected_data(data,scope)}


def parse_document(value):
    fields(value, 'format version createdAt data scope', 'файл')
    if value.get('format') not in (FORMAT,SELECTION_FORMAT) or type(value.get('version')) is not int or value['version'] != VERSION:
        raise ValueError('Неподдерживаемая версия файла. Нужен экспорт U1 версии 1.')
    text(value.get('createdAt'), 'дата экспорта', 100)
    try:
        datetime.datetime.fromisoformat(value['createdAt'])
    except ValueError as error:
        raise ValueError('Некорректная дата экспорта.') from error
    if value['format']==SELECTION_FORMAT and value.get('scope') not in SCOPES-{'full'}:raise ValueError('Не указан раздел частичного экспорта.')
    if value['format']==FORMAT and 'scope' in value:raise ValueError('Неверный формат полного экспорта.')
    return validate_data(value.get('data'))


def partial_target(current, imported, scope, mode):
    incoming=selected_data(imported,scope);result=copy.deepcopy(current);conflicts=0
    if scope=='colors':
        if mode=='replace':
            result['library']=incoming['library']
            present={c['id'] for c in result['library']['entries']+result['library']['trash']}
            linked={s['colorId'] for s in current['inventory']['spools']+current['inventory']['trash']}
            for section in ('entries','trash'):
                result['library'][section]+=[copy.deepcopy(c) for c in current['library'][section] if c['id'] in linked-present]
        else:
            known={c['id']:c for c in result['library']['entries']+result['library']['trash']}
            for section in ('entries','trash'):
                for c in incoming['library'][section]:
                    if c['id'] in known:conflicts+=known[c['id']]!=c
                    else:result['library'][section].append(c);known[c['id']]=c
    elif scope=='cores':
        if mode=='replace':
            result['inventory']['cores']=incoming['inventory']['cores']
            present={c['id'] for c in incoming['inventory']['cores']}
            linked={s['coreId'] for s in current['inventory']['spools']+current['inventory']['trash']}
            result['inventory']['cores'] += [copy.deepcopy(c) for c in current['inventory']['cores'] if c['id'] in linked-present]
        else:
            known={c['id']:c for c in result['inventory']['cores']}
            for c in incoming['inventory']['cores']:
                if c['id'] in known:conflicts+=known[c['id']]!=c
                else:result['inventory']['cores'].append(c);known[c['id']]=c
    elif scope=='spools':
        previous=selected_data(current,'spools')
        known={s['id']:s for s in previous['inventory']['spools']+previous['inventory']['trash']}
        if mode=='replace':result['inventory']['spools']=[];result['inventory']['trash']=[]
        colors={c['id']:c for c in incoming['library']['entries']+incoming['library']['trash']}
        cores={c['id']:c for c in incoming['inventory']['cores']}
        def dependency(item, destination, existing):
            original=item['id']
            if original in existing and existing[original]!=item:
                item=copy.deepcopy(item);item['id']='import-'+digest(item)
            if item['id'] in existing:
                if existing[item['id']]!=item:raise ValueError('Конфликт ID связанного справочника.')
            else:destination.append(item);existing[item['id']]=item
            return item['id']
        existing_colors={c['id']:c for c in result['library']['entries']+result['library']['trash']}
        existing_cores={c['id']:c for c in result['inventory']['cores']}
        for section in ('spools','trash'):
            for row in incoming['inventory'][section]:
                if mode=='merge' and row['id'] in known:conflicts+=known[row['id']]!=row;continue
                if row['colorId'] in colors:row['colorId']=dependency(colors[row['colorId']],result['library']['entries'],existing_colors)
                if row['coreId'] in cores:row['coreId']=dependency(cores[row['coreId']],result['inventory']['cores'],existing_cores)
                row['accountedGrams']=current['usage']['totals'].get(row['id'],0)
                result['inventory'][section].append(row)
        active={s['id'] for s in result['inventory']['spools']}
        result['inventory']['heads']=[head if head in active else None for head in current['inventory']['heads']]
    else:raise ValueError('Выберите раздел импорта.')
    return validate_data(result),conflicts


def state_from_raw(raw):
    library = copy.deepcopy(raw.get(KEYS['library'], {'revision': '', 'entries': [], 'trash': []}))
    inventory = copy.deepcopy(raw.get(KEYS['inventory'], {'revision': '', 'spools': [], 'cores': [], 'heads': [None] * 4, 'trash': []}))
    usage = raw.get(KEYS['usage'], {})
    return validate_data({'library': library, 'inventory': inventory,
                          **({'maintenance': copy.deepcopy(raw[MAINTENANCE])} if MAINTENANCE in raw else {}),
                          'usage': {'totals': usage.get('totals', {}), 'records': usage.get('records', []),
                                    **{key: usage[key] for key in ('archivedRecords', 'archivedErrors') if key in usage},
                                    **({'errors': usage['errors']} if 'errors' in usage else {})},
                          'reviews': {key[len('u1_spool_review_'):]: value for key, value in raw.items() if key.startswith('u1_spool_review_')}})


def applied_totals(records):
    totals = {}
    for record in records:
        if record['state'] == 'applied':
            for row in record['rows']:
                totals[row['spoolId']] = totals.get(row['spoolId'], 0) + row['grams']
    return totals


def merge_data(current, imported):
    result = copy.deepcopy(current)
    conflicts = 0
    for section, active_name, trash_name in [('library', 'entries', 'trash'), ('inventory', 'spools', 'trash')]:
        active = result[section][active_name]
        trash = result[section][trash_name]
        known = {item['id']: item for item in active + trash}
        for destination, incoming in [(active, imported[section][active_name]), (trash, imported[section][trash_name])]:
            for item in incoming:
                if item['id'] in known:
                    conflicts += known[item['id']] != item
                else:
                    destination.append(copy.deepcopy(item))
                    known[item['id']] = item
    cores = {core['id']: core for core in result['inventory']['cores']}
    for core in imported['inventory']['cores']:
        if core['id'] in cores:
            conflicts += cores[core['id']] != core
        else:
            result['inventory']['cores'].append(copy.deepcopy(core))
    records = {record['id']: record for record in result['usage']['records']}
    for record in imported['usage']['records']:
        if record['id'] in records:
            conflicts += records[record['id']] != record
        else:
            result['usage']['records'].append(copy.deepcopy(record))
    union_applied = applied_totals(result['usage']['records'])
    for key in ('archivedRecords', 'archivedErrors'):
        if key in result['usage'] or key in imported['usage']:
            result['usage'][key] = sorted(set(result['usage'].get(key, [])) | set(imported['usage'].get(key, [])))
    if 'errors' in imported['usage']:
        result['usage'].setdefault('errors', [])
        known_errors = {event['id']: event for event in result['usage'].get('errors', [])}
        for event in imported['usage']['errors']:
            if event['id'] in known_errors:
                conflicts += known_errors[event['id']] != event
            else:
                result['usage'].setdefault('errors', []).append(copy.deepcopy(event))
                known_errors[event['id']] = event
    totals = result['usage']['totals']
    for ident in set(totals) | set(imported['usage']['totals']) | set(union_applied):
        # Legacy totals may include older jobs absent from either history.
        totals[ident] = round(max(totals.get(ident, 0), imported['usage']['totals'].get(ident, 0), union_applied.get(ident, 0)), 6)
    for ident, decision in imported['reviews'].items():
        result['reviews'].setdefault(ident, copy.deepcopy(decision))
    if 'maintenance' in imported:
        result['maintenance'] = merge_maintenance(result.get('maintenance'), imported['maintenance'])
    return validate_data(result), conflicts


def summary(data):
    inventory = data['inventory']
    return {'colors': len(data['library']['entries']), 'colorTrash': len(data['library']['trash']),
            'spools': len(inventory['spools']), 'spoolTrash': len(inventory['trash']), 'cores': len(inventory['cores']),
            'records': len(data['usage']['records']), 'errors': len(data['usage'].get('errors', [])), 'spentGrams': round(sum(data['usage']['totals'].values()), 3),
            'activeHours': round(maintenance_totals(data['maintenance'])[0] / 3600, 2) if 'maintenance' in data else 0,
            'maintenanceEvents': len(data.get('maintenance', {}).get('history', []))}


class DataStore:
    def __init__(self, api, folder='/userdata/u1-addons/filament-ui-data', calibration_execute=None, print_start=None):
        self.api = api
        self.folder = Path(folder)
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.journal = self.folder / 'transaction.json'
        self.current = self.folder / 'current.json'
        self.last_digest = None
        self.last_cleanup = 0
        self.feeder_settings = None
        self.maintenance = Maintenance(api)
        from u1_scheduler import Scheduler, TimedPause
        self.scheduler = Scheduler(api, self.folder / 'schedule', start=print_start)
        self.timed_pause = TimedPause(api, self.folder / 'timed-pause')
        from u1_recovery import Recovery
        self.recovery = Recovery(api, self.folder / 'recovery')
        from u1_magnet_service import MagnetService
        self.magnets = MagnetService(api, self.folder / 'magnet-pauses')
        from u1_night_mode import NightMode
        self.night = NightMode(api, self.folder / 'night-mode', calibration_execute)
        from u1_dryer_service import Dryer
        self.dryer = Dryer(api, self.folder / 'drying', calibration_execute)
        from u1_calibration_jobs import CalibrationJobs
        self.calibration_jobs = CalibrationJobs(api, self.folder / 'calibration-jobs', calibration_execute)

    def process_calibration_events(self):
        self.calibration_jobs.drain(self)

    def get(self, namespace, key=None, default=None):
        query = {'namespace': namespace}
        if key is not None:
            query['key'] = key
        try:
            return self.api('/server/database/item?' + urllib.parse.urlencode(query))['value']
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            return copy.deepcopy(default)

    def put(self, namespace, key, value):
        self.api('/server/database/item', {'namespace': namespace, 'key': key, 'value': value})

    def delete(self, namespace, key):
        try:
            self.api('/server/database/item?' + urllib.parse.urlencode({'namespace': namespace, 'key': key}), method='DELETE')
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            error.close()

    def raw(self):
        namespace = self.get('fluidd', default={})
        return {key: value for key, value in namespace.items() if key in KEYS.values() or key == MAINTENANCE or key.startswith('u1_spool_review_')}

    def write_file(self, path, value):
        data = canonical(value).encode()
        if shutil.disk_usage(self.folder).free < max(50 * 1024 * 1024, len(data) * 3):
            raise ValueError('Недостаточно места для резервной копии.')
        temporary = path.with_suffix(path.suffix + '.next')
        with temporary.open('wb') as output:
            os.chmod(temporary, 0o600)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        if os.name != 'nt':
            directory = os.open(self.folder, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def snapshot(self, data, reason):
        name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + reason + '-' + uuid.uuid4().hex[:8] + '.json'
        self.write_file(self.folder / name, document(data))
        return name

    def set_control(self, status='ready'):
        self.put('fluidd', CONTROL, {'version': VERSION, 'aiSessionVersion': 1, 'logListsVersion': 1, 'maintenancePeriodsVersion': 1, 'calibrationVersion': 1, 'feederSettingsVersion': 1, 'backgroundCalibrationVersion': 1, 'temperatureProfilesVersion': 1, 'spoolTemperatureOverridesVersion': 1, 'printErrorLogVersion': 1, 'cumulativeStatsVersion': 1, 'maintenanceVersion': 1, 'schedulerVersion': 1, 'timedPauseVersion': 1, 'printPlayerVersion': 1, 'recoveryVersion': 1, 'bedAckVersion': 1, 'magnetPauseVersion': 1, 'nightModeVersion': 1, 'dryerVersion': 1, 'alexaBridgeVersion': 1, 'state': status, 'revision': str(uuid.uuid4()), 'updatedAt': time.time()})

    def require_idle(self, calibration=False):
        state = self.api('/printer/objects/query?print_stats&idle_timeout&machine_state_manager')['status']
        allowed = ('Idle', 'Ready') if calibration else ('Idle',)
        machine = state.get('machine_state_manager', {})
        if (state['idle_timeout']['state'] not in allowed or state['print_stats']['state'] not in ('standby', 'complete', 'cancelled') or
                (calibration and (machine.get('main_state') not in (0, 'IDLE') or machine.get('action_code') not in (0, 'IDLE')))):
            raise ValueError('Изменение разрешено только на свободном принтере.')

    def write_raw(self, desired, known):
        for key in set(known) - set(desired):
            self.delete('fluidd', key)
        for key, value in desired.items():
            if known.get(key) != value or key not in known:
                self.put('fluidd', key, value)

    def recover(self):
        control = self.get('fluidd', CONTROL, {})
        if control.get('version', VERSION) != VERSION:
            raise ValueError('Версия хранилища требует более нового дополнения.')
        if self.journal.exists():
            journal = json.loads(self.journal.read_text())
            self.require_idle()
            applied = journal['phase'] == 'applied'
            actual = self.raw()
            self.check_recovery_values(journal, actual)
            self.write_raw(journal['after'] if applied else journal['before'], actual)
            self.write_file(self.current, document(state_from_raw(self.raw())))
            self.set_control()
            if journal.get('requestId'):
                result = journal['result'] if applied else {'ok': False, 'error': 'Операция прервалась. Предыдущие данные восстановлены.'}
                self.put(RESULTS, journal['requestId'], {**result, 'completedAt': time.time()})
            self.journal.unlink()
        if self.current.exists():
            previous = parse_document(json.loads(self.current.read_text()))
            if previous != state_from_raw(self.raw()):
                self.snapshot(previous, 'before-change')
        self.sync_mirror()
        self.set_control()

    def check_recovery_values(self, journal, actual):
        missing = object()
        for key in set(journal['before']) | set(journal['after']) | set(actual):
            if actual.get(key, missing) not in (journal['before'].get(key, missing), journal['after'].get(key, missing)):
                raise ValueError('Обнаружена внешняя запись во время восстановления. Сохранён журнал для проверки.')

    def sync_mirror(self):
        data = state_from_raw(self.raw())
        fingerprint = digest(data)
        if fingerprint != self.last_digest:
            self.write_file(self.current, document(data))
            self.last_digest = fingerprint

    def commit(self, after, request_id=None, result=None, expected=None):
        before = self.raw()
        before_data = state_from_raw(before)
        if expected is not None and digest(before_data) != expected:
            raise ValueError('Данные изменились. Обновите предварительный просмотр или список.')
        state_from_raw(after)
        backup = self.snapshot(before_data, 'before-change')
        if self.raw() != before:
            raise ValueError('Данные изменились перед записью. Обновите список.')
        result = {'ok': True, 'value': {**(result or {}), 'backup': backup}}
        journal = {'phase': 'writing', 'requestId': request_id, 'before': before, 'after': after, 'result': result}
        self.write_file(self.journal, journal)
        self.set_control('writing')
        try:
            self.write_raw(after, before)
            if self.raw() != after:
                raise ValueError('Обнаружено параллельное изменение данных. Запись остановлена.')
            self.write_file(self.current, document(state_from_raw(after)))
            journal['phase'] = 'applied'
            self.write_file(self.journal, journal)
            self.set_control()
            if request_id:
                self.put(RESULTS, request_id, {**result, 'completedAt': time.time()})
            self.journal.unlink()
            self.last_digest = digest(state_from_raw(after))
            return result['value']
        except Exception:
            # A durable journal retains the complete recovery data if rollback fails.
            if journal['phase'] == 'writing':
                actual = self.raw()
                self.check_recovery_values(journal, actual)
                self.write_raw(before, actual)
                self.write_file(self.current, document(before_data))
                self.set_control()
                self.journal.unlink()
            raise

    def commit_usage(self, usage):
        raw = self.raw()
        after = copy.deepcopy(raw)
        after[KEYS['usage']] = usage
        if state_from_raw(raw)['usage'] == state_from_raw(after)['usage']:
            self.put('fluidd', KEYS['usage'], usage)
        else:
            self.commit(after)

    def handle(self, ident, request):
        operation = request.get('operation')
        payload = request.get('payload', {})
        if operation in ('logs_export', 'logs_prepare_clear', 'logs_clear'):
            from u1_log_lists import export as export_logs, prepare as prepare_logs, clear as clear_logs
            if operation == 'logs_export': return export_logs(self, payload)
            if operation == 'logs_prepare_clear': return prepare_logs(self, payload)
            return clear_logs(self, ident, payload)
        if operation == 'ai_session':
            from u1_ai_session import issue
            return issue(payload)
        if operation in ('alexa_state','alexa_command'):
            from u1_alexa import state as alexa_state, enqueue as alexa_enqueue
            return alexa_state() if operation=='alexa_state' else alexa_enqueue(payload)
        if operation == 'dryer_notifications': return self.dryer.configure_notifications(payload)
        if operation == 'dryer_state': return self.dryer.state()
        if operation == 'dryer_profiles': return self.dryer.profiles()
        if operation == 'dryer_profile_save': return self.dryer.change(payload)
        if operation == 'dryer_action': return self.dryer.action(self,payload)
        if operation in ('calibration_run_start','feeder_apply','feeder_restart_check','import'):
            state_file = self.folder / 'drying' / 'state.json'
            if state_file.exists() and json.loads(state_file.read_text()).get('state') in ('heating','running','paused'):raise ValueError('Сначала отмените сушку.')
        if operation == 'night_configure' and payload.get('mode') != 'off':
            state_file = self.folder / 'drying' / 'state.json'
            if state_file.exists() and json.loads(state_file.read_text()).get('state') in ('heating','running','paused'):raise ValueError('Ночной режим недоступен во время сушки.')
        if operation == 'night_state': return self.night.state()
        if operation == 'night_configure': return self.night.configure(payload)
        if operation == 'print_player_state': return self.timed_pause.player_state()
        if operation == 'magnet_state': return self.magnets.state()
        if operation == 'magnet_prepare': return self.magnets.prepare(self,payload)
        if operation == 'magnet_arm': return self.magnets.arm(payload)
        if operation == 'magnet_action': return self.magnets.action(self,ident,payload)
        if operation == 'recovery_state': return self.recovery.state()
        if operation == 'recovery_prepare': return self.recovery.prepare(self)
        if operation == 'recovery_resume': return self.recovery.resume(self,payload)
        if operation == 'print_player_action': return self.timed_pause.player_action(ident,payload)
        if operation == 'print_player_prepare': return self.scheduler.prepare_start(self,payload)
        if operation == 'print_player_start': return self.scheduler.start_now(self,payload)
        if operation == 'timed_pause_state': return self.timed_pause.state()
        if operation == 'timed_pause_prepare': return self.timed_pause.prepare(self,payload)
        if operation == 'timed_pause_arm': return self.timed_pause.arm(self,payload)
        if operation == 'timed_pause_cancel': return self.timed_pause.cancel(payload)
        if self.timed_pause.active and operation in ('schedule_prepare','schedule_arm','calibration_run_start','feeder_apply','feeder_restart_check','import'):
            raise ValueError('Сначала отмените таймер продолжения печати.')
        if operation == 'schedule_state': return self.scheduler.state()
        if operation == 'schedule_prepare': return self.scheduler.prepare(self,payload)
        if operation == 'schedule_arm': return self.scheduler.arm(self,payload)
        if operation == 'schedule_cancel': return self.scheduler.cancel(payload)
        if self.scheduler.active and operation in ('calibration_run_start','feeder_apply','feeder_restart_check','import'):
            raise ValueError('Сначала отмените отложенный запуск.')
        if operation == 'maintenance_state':
            return self.maintenance.state(self)
        if operation == 'maintenance_change':
            return self.maintenance.change(self, ident, payload)
        if operation in ('calibration_run_state', 'calibration_run_prepare', 'calibration_run_start', 'calibration_run_stop'):
            if operation == 'calibration_run_state':
                return self.calibration_jobs.state()
            if operation == 'calibration_run_prepare':
                return self.calibration_jobs.prepare(payload)
            if operation == 'calibration_run_start':
                return self.calibration_jobs.start(payload)
            return self.calibration_jobs.stop()
        if self.calibration_jobs.active and operation in ('feeder_prepare', 'feeder_apply', 'feeder_restart_check', 'import'):
            raise ValueError('Дождитесь завершения очереди калибровки.')
        if operation in ('feeder_state', 'feeder_prepare', 'feeder_apply', 'feeder_restart_check'):
            if self.feeder_settings is None:
                from u1_feeder_settings import FeederSettings
                self.feeder_settings = FeederSettings(self.api, self.folder / 'feeder-settings')
            if operation == 'feeder_state':
                return self.feeder_settings.state()
            if operation == 'feeder_prepare':
                return self.feeder_settings.prepare(payload)
            if operation == 'feeder_apply':
                return self.feeder_settings.apply(payload)
            return self.feeder_settings.restart_check(payload)
        current_raw = self.raw()
        current = state_from_raw(current_raw)
        if operation == 'export':
            name = self.snapshot(current, 'export')
            scope=payload.get('scope','full')
            return {'document': document(current,scope), 'filename': name if scope=='full' else scope+'-'+name, 'summary': summary(selected_data(current,scope))}
        if operation == 'backups':
            backups = sorted((path for path in self.folder.glob('*.json') if path.name not in ('current.json', 'transaction.json') and '-preview-' not in path.name), reverse=True)
            return {'backups': [path.name for path in backups[:100]], 'current': self.current.exists()}
        if operation == 'load_backup':
            name = payload.get('name')
            if name != 'current.json' and not re.fullmatch(r'\d{8}T\d{6}-(?:before-change|export)-[0-9a-f]{8}\.json', str(name)):
                raise ValueError('Некорректное имя резервной копии.')
            value = json.loads((self.folder / name).read_text())
            return {'document': document(parse_document(value))}
        if operation == 'preview':
            source_document=payload.get('document')
            imported = parse_document(source_document)
            scope=payload.get('scope','full')
            if scope not in SCOPES:raise ValueError('Выберите раздел импорта.')
            if scope=='full' and source_document.get('format')==SELECTION_FORMAT:scope=source_document['scope']
            mode = payload.get('mode')
            if mode not in ('replace', 'merge'):
                raise ValueError('Выберите восстановление или объединение.')
            target, conflicts = (partial_target(current,imported,scope,mode) if scope!='full' else (merge_data(current, imported) if mode == 'merge' else (imported, 0)))
            if MAINTENANCE in current_raw:
                target['maintenance'] = merge_maintenance(current_raw[MAINTENANCE], target['maintenance']) if 'maintenance' in target else copy.deepcopy(current_raw[MAINTENANCE])
            preview_id = str(uuid.uuid4())
            preview = {'version': VERSION, 'createdAt': time.time(), 'sourceHash': digest(current), 'mode': mode, 'scope':scope, 'data': target}
            self.write_file(self.folder / (preview_id + '-preview-data.json'), preview)
            return {'previewId': preview_id, 'mode': mode, 'scope':scope, 'before': summary(current), 'after': summary(target), 'conflicts': conflicts}
        if operation == 'import':
            self.require_idle()
            preview_id = payload.get('previewId', '')
            if not UUID.fullmatch(preview_id):
                raise ValueError('Неверный предварительный просмотр.')
            preview = json.loads((self.folder / (preview_id + '-preview-data.json')).read_text())
            if time.time() - preview['createdAt'] > 1800 or digest(current) != preview['sourceHash']:
                raise ValueError('Данные изменились. Повторите предварительный просмотр.')
            if current_raw.get(KEYS['usage'], {}).get('tracked'):
                raise ValueError('Дождитесь завершения обработки расхода текущей печати.')
            target = validate_data(preview['data'])
            if preview.get('scope','full')!='full':
                after=copy.deepcopy(current_raw)
                for section in ('library','inventory'):
                    if canonical(target[section])!=canonical(current[section]):
                        target[section]['revision']=str(uuid.uuid4());after[KEYS[section]]=target[section]
                self.require_idle()
                return self.commit(after,ident,{'summary':summary(target),'scope':preview['scope']},digest(current))
            target['library']['revision'] = str(uuid.uuid4())
            target['inventory']['revision'] = str(uuid.uuid4())
            after = {KEYS[key]: target[key] for key in KEYS}
            if 'maintenance' in target or MAINTENANCE in current_raw:
                after[MAINTENANCE] = merge_maintenance(current_raw.get(MAINTENANCE), target['maintenance']) if 'maintenance' in target else copy.deepcopy(current_raw[MAINTENANCE])
            after[KEYS['usage']] = {**target['usage'], 'tracked': None, 'active': None, 'checkedAt': time.time()}
            after.update({'u1_spool_review_' + key: value for key, value in target['reviews'].items()})
            self.require_idle()
            return self.commit(after, ident, {'summary': summary(target)}, digest(current))
        if operation in ('library', 'inventory'):
            incoming = copy.deepcopy(payload.get('value'))
            if not isinstance(incoming, dict) or incoming.get('revision') != current[operation]['revision']:
                raise ValueError('Данные изменились на другом устройстве. Обновите список.')
            incoming['revision'] = str(uuid.uuid4())
            current[operation] = incoming
            validate_data(current)
            after = copy.deepcopy(current_raw)
            after[KEYS[operation]] = incoming
            return self.commit(after, ident, {'value': incoming}, digest(state_from_raw(current_raw)))
        if operation == 'calibration':
            self.require_idle(calibration=True)
            if payload.get('libraryRevision') != current['library']['revision'] or payload.get('inventoryRevision') != current['inventory']['revision']:
                raise ValueError('Данные изменились. Откройте калибровку заново.')
            individual = payload.get('individual')
            if type(individual) is not bool or payload.get('kind') not in ('spool', 'color'):
                raise ValueError('Неверный режим калибровки.')
            kind = payload['kind']
            if kind == 'spool':
                spool = next((item for item in current['inventory']['spools'] if item['id'] == payload.get('id')), None)
                if spool is None:
                    raise ValueError('Катушка не найдена.')
                record = spool if individual else next((item for item in current['library']['entries'] if item['id'] == spool['colorId']), None)
            else:
                record = next((item for item in current['library']['entries'] if item['id'] == payload.get('id')), None)
            if record is None:
                raise ValueError('Общий филамент отсутствует в библиотеке. Восстановите его или выберите другую основу катушки.')
            value = copy.deepcopy(payload.get('value'))
            if value is None:
                record.pop('calibration', None)
            else:
                calibration(value)
                record['calibration'] = value
            current['inventory']['individualCalibration'] = individual
            current['inventory']['revision'] = str(uuid.uuid4())
            if kind == 'color' or not individual:
                current['library']['revision'] = str(uuid.uuid4())
            validate_data(current)
            after = copy.deepcopy(current_raw)
            after[KEYS['library']] = current['library']
            after[KEYS['inventory']] = current['inventory']
            self.require_idle(calibration=True)
            return self.commit(after, ident, {'source': 'spool' if kind == 'spool' and individual else 'color'}, digest(state_from_raw(current_raw)))
        if operation == 'review':
            job_id = payload.get('id')
            record = next((item for item in current['usage']['records'] if item['id'] == job_id), None)
            decision = payload.get('value')
            if not isinstance(decision, dict) or not record or record['state'] != 'review' or decision.get('time') != record['time'] or len(decision.get('grams', [])) != len(record['rows']):
                raise ValueError('Запись расхода изменилась. Обновите журнал.')
            current['reviews'][job_id] = decision
            validate_data(current)
            after = copy.deepcopy(current_raw)
            after['u1_spool_review_' + job_id] = decision
            return self.commit(after, ident, expected=digest(state_from_raw(current_raw)))
        raise ValueError('Неизвестная операция с данными.')

    def process_requests(self):
        pending = self.get(REQUESTS, default={})
        for ident, request in list(pending.items())[:10]:
            if not UUID.fullmatch(ident):
                self.delete(REQUESTS, ident)
                continue
            if self.get(RESULTS, ident) is None:
                try:
                    if not isinstance(request, dict) or len(canonical(request).encode()) > LIMIT:
                        raise ValueError('Слишком большой или повреждённый запрос.')
                    result = {'ok': True, 'value': self.handle(ident, request)}
                except Exception as error:
                    if self.journal.exists():
                        raise
                    logging.exception('U1 user-data request failed')
                    result = {'ok': False, 'error': str(error)}
                self.put(RESULTS, ident, {**result, 'completedAt': time.time()})
            self.delete(REQUESTS, ident)
        if time.monotonic() - self.last_cleanup > 60:
            results = self.get(RESULTS, default={})
            ordered = sorted(results, key=lambda key: results[key].get('completedAt', 0), reverse=True)
            for ident in ordered[30:]:
                self.delete(RESULTS, ident)
            for path in self.folder.glob('*-preview-data.json'):
                if time.time() - path.stat().st_mtime > 86400:
                    path.unlink()
            self.last_cleanup = time.monotonic()

