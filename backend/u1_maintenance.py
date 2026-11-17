"""Read-only U1 print-time ledger and user-confirmed maintenance intervals."""
import calendar
import copy
import datetime
import math
import re
import time
import uuid
from zoneinfo import ZoneInfo

KEY = 'u1_maintenance_v1'
MAX_JOBS = 50000
DEFAULT_PERIODS = {
    'service': {'enabled': True, 'hours': 100, 'days': None, 'months': 1, 'prints': None},
    'bed': {'enabled': True, 'hours': 10, 'days': None, 'months': None, 'prints': 5},
}

def periods(data):
    value = copy.deepcopy(data.get('periods', DEFAULT_PERIODS))
    value['bed']['enabled'] = value['bed']['enabled'] and data['bedEnabled']
    return value

def validate_periods(value):
    if not isinstance(value, dict) or set(value) != {'service', 'bed'}:
        raise ValueError('Нужны отдельные периоды обслуживания и калибровки.')
    for row in value.values():
        if not isinstance(row, dict) or set(row) != {'enabled', 'hours', 'days', 'months', 'prints'} or type(row['enabled']) is not bool:
            raise ValueError('Некорректные настройки напоминания.')
        for key, maximum in [('hours', 100000), ('days', 36500), ('months', 120), ('prints', 100000)]:
            v = row[key]
            if v is not None and (type(v) is not int or not 1 <= v <= maximum):
                raise ValueError('Интервал должен быть положительным целым числом; пусто — не учитывать.')
        if row['enabled'] and all(row[key] is None for key in ('hours', 'days', 'months', 'prints')):
            raise ValueError('Для включённого напоминания укажите хотя бы один интервал.')
    return value

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1e12

def validate(value):
    if not isinstance(value, dict) or set(value) - {'periods'} != {'version','revision','createdAt','baseSeconds','jobs','service','bed','bedEnabled','history'}:
        raise ValueError('Некорректные данные обслуживания.')
    if value['version'] != 1 or not isinstance(value['revision'], str) or type(value['bedEnabled']) is not bool:
        raise ValueError('Неизвестная версия обслуживания.')
    if 'periods' in value:
        validate_periods(value['periods'])
    for field in ('createdAt','baseSeconds'):
        if not number(value[field]) or (field == 'createdAt' and value[field] > 1e10): raise ValueError('Некорректный счётчик обслуживания.')
    jobs = value['jobs']
    if not isinstance(jobs, dict) or len(jobs) > MAX_JOBS: raise ValueError('Слишком большой журнал наработки.')
    for key, job in jobs.items():
        if (not isinstance(key, str) or len(key) > 100 or not isinstance(job, dict) or set(job) != {'seconds','completed'}
                or not number(job['seconds']) or type(job['completed']) is not bool):
            raise ValueError('Некорректная запись наработки.')
    def marker(row):
        if not isinstance(row, dict) or set(row) - {'zone'} != {'time','seconds','completed'} or any(not number(row[k]) for k in ('time','seconds','completed')):
            raise ValueError('Некорректное подтверждение обслуживания.')
        if 'zone' in row:
            if not isinstance(row['zone'],str) or len(row['zone']) > 80: raise ValueError('Некорректный часовой пояс.')
            timezone(row['zone'])
        if row['time'] > 1e10 or type(row['completed']) is not int: raise ValueError('Некорректный счётчик печатей.')
    for kind in ('service','bed'):
        if value[kind] is not None: marker(value[kind])
    if not isinstance(value['history'], list) or len(value['history']) > 10000: raise ValueError('Слишком большая история обслуживания.')
    seen = set()
    for event in value['history']:
        if not isinstance(event, dict) or set(event) - {'zone'} != {'id','kind','time','seconds','completed'} or event['kind'] not in ('service','bed'):
            raise ValueError('Некорректная история обслуживания.')
        if not isinstance(event['id'], str) or len(event['id']) > 120 or event['id'] in seen: raise ValueError('Повтор подтверждения обслуживания.')
        seen.add(event['id'])
        marker({k:v for k,v in event.items() if k not in ('id','kind')})
    return value

def totals(data):
    return data['baseSeconds'] + sum(j['seconds'] for j in data['jobs'].values()), sum(j['completed'] for j in data['jobs'].values())

def timezone(name):
    return datetime.timezone.utc if name == 'UTC' else ZoneInfo(name)

def next_month(timestamp, zone='UTC', months=1):
    date = datetime.datetime.fromtimestamp(timestamp, timezone(zone))
    year, month = divmod(date.year * 12 + date.month - 1 + months, 12)
    month += 1
    return date.replace(year=year, month=month, day=min(date.day, calendar.monthrange(year,month)[1])).timestamp()

def view(data, now=None):
    now = time.time() if now is None else now
    seconds, completed = totals(data)
    service, bed = data['service'], data['bed']
    service_seconds = max(0, seconds-service['seconds']) if service else None
    bed_seconds = max(0, seconds-bed['seconds']) if bed else None
    bed_jobs = max(0, completed-bed['completed']) if bed else None
    settings = periods(data)
    def calendar_due(marker, row):
        if marker is None: return None
        deadlines = []
        if row['days'] is not None:
            date = datetime.datetime.fromtimestamp(marker['time'], timezone(marker.get('zone', 'UTC')))
            deadlines.append((date + datetime.timedelta(days=row['days'])).timestamp())
        if row['months'] is not None:
            deadlines.append(next_month(marker['time'], marker.get('zone', 'UTC'), row['months']))
        return min(deadlines) if deadlines else None
    def is_due(marker, row):
        if not row['enabled']: return False
        if marker is None: return True
        date = calendar_due(marker, row)
        return ((row['hours'] is not None and seconds - marker['seconds'] >= row['hours'] * 3600)
                or (row['prints'] is not None and completed - marker['completed'] >= row['prints'])
                or (date is not None and now >= date))
    due_at = calendar_due(service, settings['service'])
    return {'value':data, 'totalSeconds':seconds, 'completedPrints':completed,
            'serviceSeconds':service_seconds, 'bedSeconds':bed_seconds, 'bedPrints':bed_jobs, 'serviceDueAt':due_at,
            'periods': settings, 'bedDueAt': calendar_due(bed, settings['bed']),
            'serviceDue':is_due(service, settings['service']),
            'bedDue':is_due(bed, settings['bed'])}

def merge(current, imported):
    if not current: return copy.deepcopy(validate(imported))
    result = copy.deepcopy(validate(current)); validate(imported)
    result['baseSeconds'] = max(result['baseSeconds'], imported['baseSeconds'])
    result['createdAt'] = min(result['createdAt'], imported['createdAt'])
    if 'periods' not in result and 'periods' in imported:
        result['periods'] = copy.deepcopy(imported['periods'])
    for key, job in imported['jobs'].items():
        old = result['jobs'].get(key, {'seconds':0,'completed':False})
        result['jobs'][key] = {'seconds':max(old['seconds'],job['seconds']), 'completed':old['completed'] or job['completed']}
    known = {e['id'] for e in result['history']}
    result['history'] += [copy.deepcopy(e) for e in imported['history'] if e['id'] not in known]
    for kind in ('service','bed'):
        newer = imported[kind]
        if newer and (not result[kind] or newer['time'] > result[kind]['time']): result[kind] = copy.deepcopy(newer)
    result['revision'] = str(uuid.uuid4())
    return validate(result)

class Maintenance:
    def __init__(self, api):
        self.api = api
        self.last_poll = -math.inf
        self.health = {'checkedAt':0,'message':'Данные ещё не обновлены.'}

    def poll(self, store, force=False):
        if not force and time.monotonic()-self.last_poll < 30: return
        original = store.get('fluidd', KEY)
        data = copy.deepcopy(original) if original else {'version':1,'revision':str(uuid.uuid4()),'createdAt':time.time(), 'baseSeconds':0,'jobs':{},'service':None,'bed':None,'bedEnabled':True,'history':[]}
        try:
            native_before = self.api('/server/history/totals')['job_totals'] if original is None else None
            start = 0
            active_keys = set()
            while True:
                jobs = self.api('/server/history/list?limit=100&order=desc&start='+str(start))['jobs']
                known_page = bool(original) and bool(jobs)
                for job in jobs:
                    ident, timestamp = str(job.get('job_id','')), job.get('start_time')
                    if not re.fullmatch(r'[0-9a-fA-F]{1,16}',ident) or not number(timestamp): raise ValueError('История U1 вернула неверный ID или время.')
                    key = ident.upper()+':'+format(timestamp,'.6f')
                    known_page = known_page and key in data['jobs']
                    seconds = job.get('print_duration')
                    if not number(seconds): raise ValueError('История U1 не содержит времени активной печати.')
                    old = data['jobs'].get(key, {'seconds':0,'completed':False})
                    # Live native print_duration freezes while paused. Never use wall time.
                    if job.get('status') == 'in_progress':
                        active_keys.add(key)
                        stats = self.api('/printer/objects/query?print_stats')['status']['print_stats']
                        wall = stats.get('total_duration')
                        current = start == 0 and job is jobs[0] and (not number(wall) or abs(time.time()-timestamp-wall) < 30)
                        if current and stats.get('filename') == job.get('filename') and stats.get('state') in ('printing','paused') and number(stats.get('print_duration')):
                            seconds = max(seconds, stats['print_duration'])
                    data['jobs'][key] = {'seconds':max(old['seconds'],seconds), 'completed':old['completed'] or job.get('status') == 'completed'}
                if len(jobs) < 100 or known_page: break
                start += len(jobs)
                if start >= MAX_JOBS: raise ValueError('Достигнут предел истории наработки; данные не перезаписаны.')
            if original is None:
                native_after = self.api('/server/history/totals')['job_totals']
                if native_before != native_after: raise ValueError('История изменилась при первом чтении; повторю подсчёт.')
                native = native_after['total_print_time']
                if not number(native): raise ValueError('Штатный итог времени недоступен.')
                # Native totals contain finished jobs; live job is not in the total yet.
                active = sum(data['jobs'][key]['seconds'] for key in active_keys)
                data['baseSeconds'] = max(0, native-(totals(data)[0]-active))
            validate(data)
            if data != original: store.put('fluidd',KEY,data)
            self.publish_status(store, data)
            self.health = {'checkedAt':time.time(),'message':''}
            self.last_poll = time.monotonic()
        except Exception as error:
            self.health = {**self.health,'message':str(error)[:500]}
            self.last_poll = time.monotonic()
            raise

    def state(self, store):
        data = store.get('fluidd',KEY)
        health = dict(self.health)
        if health['checkedAt'] and time.time()-health['checkedAt'] > 90 and not health['message']:
            health['message'] = 'Наработка давно не обновлялась. Проверьте связь с U1.'
        jobs = getattr(store, 'calibration_jobs', None)
        job = jobs.state() if jobs else {}
        return {**(view(data) if data else {'value':None}), **health,
                'bedCalibration': job if job.get('kind') == 'bed' else None,
                'calibrationActive': bool(jobs and jobs.active)}

    def record_bed(self, store, ident):
        # Only the worker drains a verified native job; use the normal durable ledger.
        store.require_idle(calibration=True)
        self.poll(store, force=True)
        raw = store.raw()
        data = copy.deepcopy(raw.get(KEY))
        if not data:
            raise ValueError('Счётчики ещё не получены.')
        if any(row['id'] == ident for row in data['history']):
            return
        if len(data['history']) >= 10000:
            raise ValueError('История подтверждений заполнена. Экспортируйте данные.')
        seconds, completed = totals(data)
        marker = {'time': time.time(), 'seconds': seconds, 'completed': completed, 'zone': 'UTC'}
        data['bed'] = marker
        data['history'].append({'id': ident, 'kind': 'bed', **marker})
        data['revision'] = str(uuid.uuid4())
        validate(data)
        after = copy.deepcopy(raw)
        after[KEY] = data
        store.require_idle(calibration=True)
        store.commit(after)
        self.publish_status(store, data)

    def publish_status(self, store, data):
        value = view(data)
        store.put('fluidd', 'u1_maintenance_status_v1', {'revision': data['revision'], 'checkedAt': time.time(),
                  **{k: value[k] for k in ('serviceDue', 'bedDue', 'serviceDueAt', 'bedDueAt')}})

    def change(self, store, ident, payload):
        store.require_idle()
        self.poll(store,force=True)
        raw = store.raw()
        data = copy.deepcopy(raw.get(KEY))
        if not data or payload.get('revision') != data['revision']: raise ValueError('Данные изменились. Обновите окно обслуживания.')
        action = payload.get('action')
        if action == 'bed_enabled' and type(payload.get('enabled')) is bool:
            data['bedEnabled'] = payload['enabled']
            if 'periods' in data:
                data['periods']['bed']['enabled'] = payload['enabled']
        elif action == 'periods':
            data['periods'] = copy.deepcopy(validate_periods(payload.get('value')))
            data['bedEnabled'] = data['periods']['bed']['enabled']
        elif action in ('service','bed') and payload.get('confirmed') is True:
            if len(data['history']) >= 10000: raise ValueError('История подтверждений заполнена. Экспортируйте данные.')
            seconds, completed = totals(data)
            marker = {'time':time.time(),'seconds':seconds,'completed':completed,'zone':payload.get('timeZone','UTC')}
            data[action] = marker
            data['history'].append({'id':ident,'kind':action,**marker})
        else: raise ValueError('Подтвердите выполненные работы.')
        data['revision'] = str(uuid.uuid4());validate(data)
        after = copy.deepcopy(raw);after[KEY] = data
        store.require_idle()
        store.commit(after,ident,{**view(data),**self.health})
        self.publish_status(store, data)
        return self.state(store)
