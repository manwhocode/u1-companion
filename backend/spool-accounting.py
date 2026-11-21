#!/usr/bin/env python3
"""Track spool use from Moonraker history without sending printer commands."""
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from u1_data_store import DataStore
from u1_print_errors import ErrorMonitor, ErrorStream
from u1_scheduler import native_start

BASE = 'http://127.0.0.1:7125'
USAGE = 'u1_spool_usage_v1'
INVENTORY = 'u1_spool_inventory_v1'
JOB_ID = re.compile(r'[0-9A-Fa-f]{1,16}\Z')
STATUS = '/printer/objects/query?print_stats&print_task_config'


def api(path, payload=None, method=None, timeout=4):
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    request = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)['result']


def get_item(key, default=None):
    try:
        return api('/server/database/item?' + urllib.parse.urlencode({'namespace': 'fluidd', 'key': key}))['value']
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        return default


def put_usage(value):
    api('/server/database/item', {'namespace': 'fluidd', 'key': USAGE, 'value': value})


def number(value):
    if type(value) in (int, float) and math.isfinite(value):
        return max(0, value)
    return 0


def demands(metadata, mapping, used):
    weights = metadata.get('filament_weight') or metadata.get('filament_weights')
    lengths = metadata.get('filament_used_mm') or []
    if not isinstance(weights, list) or not isinstance(lengths, list):
        return None
    result = {}
    for logical, grams in enumerate(weights):
        if not number(grams):
            continue
        if logical >= len(mapping):
            return None
        head = mapping[logical]
        if type(head) is not int or head not in range(4) or not used[head]:
            return None
        row = result.setdefault(head, {'head': head, 'required': 0, 'mm': 0})
        row['required'] += grams
        row['mm'] += number(lengths[logical]) if logical < len(lengths) else 0
    return list(result.values()) or None


def snapshot(job, task, inventory, library=None):
    mapping = task.get('extruder_map_table')
    used = task.get('extruders_used')
    if not isinstance(mapping, list) or not isinstance(used, list) or len(used) != 4 or not any(used):
        return None
    rows = demands(job.get('metadata') or {}, mapping, used)
    if rows is None:
        return None
    spools = {spool['id']: spool for spool in inventory.get('spools', [])}
    colors = {entry['id']: entry for entry in (library or {}).get('entries', [])}
    for row in rows:
        head = row['head']
        spool = spools.get(inventory['heads'][head])
        if (spool and task['filament_exist'][head] and spool['material'] == task['filament_type'][head]
                and spool['hex'].upper() == '#' + task['filament_color_rgba'][head][:6].upper()):
            row.update(spoolId=spool['id'], name=spool['name'])
            if spool.get('colorId'):
                row['colorId'] = spool['colorId']
                color = colors.get(spool['colorId'])
                if color:
                    row['colorName'] = color['name']
            basis = colors.get(spool.get('colorId'), {}) if spool.get('inheritPurchasePrice', True) else spool
            purchase, weight = basis.get('purchasePrice'), basis.get('purchaseWeight', 1000)
            if type(purchase) in (int,float) and type(weight) in (int,float) and math.isfinite(purchase) and math.isfinite(weight) and purchase >= 0 and weight > 0:
                row['purchasePerGram'] = purchase / weight
            price = spool.get('pricePerGram')
            if type(price) in (int, float) and math.isfinite(price) and price >= 0:
                row['pricePerGram'] = price
    return {
        'id': job['job_id'], 'filename': job['filename'], 'rows': rows, 'mapping': mapping,
        'replacement': task.get('extruders_replenished'), 'heads': inventory['heads'],
        'signature': [task['filament_type'], task['filament_color_rgba']],
        'estimated': number((job.get('metadata') or {}).get('estimated_time')), 'changed': False,
    }


def finish(tracked, job):
    rows = tracked['rows']
    total_mm = sum(row['mm'] for row in rows)
    measured = number(job.get('filament_used'))
    complete = job['status'] == 'completed'
    ratio = measured / total_mm if total_mm else 0
    if complete and not (measured and total_mm):
        ratio = 1
    cancelled_with_measurement = job['status'] == 'cancelled' and len(rows) == 1 and total_mm and measured
    unusual_split = complete and len(rows) > 1 and not 0.8 <= ratio <= 1.2
    review = tracked['changed'] or unusual_split or (not complete and not cancelled_with_measurement)
    charges = []
    for row in rows:
        if 'spoolId' not in row:
            continue
        estimate = round(row['required'] * ratio, 3)
        charges.append({**row, 'grams': estimate})
    return {
        'id': job['job_id'], 'filename': job['filename'], 'status': job['status'],
        'time': job.get('end_time') or time.time(), 'rows': charges,
        'state': 'review' if review else 'applied',
        'method': 'estimate' if review or len(rows) != 1 or not (total_mm and measured) else 'measured',
    }


def debit(usage, record):
    for row in record['rows']:
        spool_id = row['spoolId']
        usage['totals'][spool_id] = round(usage['totals'].get(spool_id, 0) + row['grams'], 3)


def check_reviews(usage):
    for record in usage['records']:
        if record['state'] != 'review':
            continue
        decision = get_item('u1_spool_review_' + record['id'])
        if not isinstance(decision, dict) or decision.get('time') != record['time']:
            continue
        amounts = decision.get('grams')
        if not isinstance(amounts, list) or len(amounts) != len(record['rows']):
            continue
        if any(type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 100000 for value in amounts):
            continue
        for row, grams in zip(record['rows'], amounts):
            row['grams'] = grams
        debit(usage, record)
        record['state'] = 'applied'
        record['method'] = 'manual'


def live_rows(tracked, stats, inventory, totals):
    spools = {spool['id']: spool for spool in inventory.get('spools', [])}
    planned_time = tracked['estimated']
    elapsed = number(stats.get('print_duration'))
    length = sum(row['mm'] for row in tracked['rows'])
    progress = min(1, number(stats.get('filament_used')) / length) if length else 0
    result = []
    for row in tracked['rows']:
        spool = spools.get(row.get('spoolId'))
        if not spool:
            result.append({**row, 'remaining': None})
            continue
        spent = max(0, totals.get(spool['id'], 0) - spool.get('accountedGrams', 0))
        remaining = max(0, spool['grams'] - spent)
        shortage = max(0, row['required'] - remaining)
        # Assumes an even average rate over this print, not a layer prediction.
        seconds = max(0, planned_time * remaining / row['required'] - elapsed) if shortage and planned_time else None
        result.append({**row, 'remaining': round(max(0, remaining - row['required'] * progress), 2),
                       'shortage': round(shortage, 2), 'seconds': seconds})
    return result


def tick(usage):
    inventory = get_item(INVENTORY, {'spools': [], 'heads': [None] * 4})
    check_reviews(usage)
    tracked = usage.get('tracked')
    if tracked:
        try:
            job = api('/server/history/job?' + urllib.parse.urlencode({'uid': tracked['id']}))['job']
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            job = {'job_id': tracked['id'], 'filename': tracked['filename'], 'status': 'history_missing'}
        if job['status'] != 'in_progress':
            record = finish(tracked, job)
            if record['rows'] and not any(existing['id'] == record['id'] for existing in usage['records']):
                if record['state'] == 'applied':
                    debit(usage, record)
                usage['records'].insert(0, record)
            usage['lastJob'] = job['job_id']
            usage['tracked'] = tracked = None
    usage['active'] = None
    if not tracked and not any(inventory.get('heads', [])):
        return
    try:
        status = api(STATUS)['status']
    except urllib.error.HTTPError:
        return
    stats = status.get('print_stats', {})
    task = status.get('print_task_config', {})
    if stats.get('state') not in ('printing', 'paused'):
        return
    if not tracked:
        jobs = api('/server/history/list?limit=1')['jobs']
        if not jobs:
            return
        job = jobs[0]
        if (job['status'] != 'in_progress' or job['filename'] != stats.get('filename')
                or job['job_id'] == usage.get('lastJob') or not JOB_ID.fullmatch(job['job_id'])
                or not -5 <= time.time() - number(job.get('start_time')) <= 90):
            return
        tracked = snapshot(job, task, inventory, get_item('u1_filament_library_v1', {}))
        if not tracked:
            return
        usage['tracked'] = tracked
    if stats.get('filename') != tracked['filename']:
        return
    if (task.get('extruder_map_table') != tracked['mapping']
            or task.get('extruders_replenished') != tracked['replacement']
            or inventory['heads'] != tracked['heads']
            or [task.get('filament_type'), task.get('filament_color_rgba')] != tracked['signature']):
        tracked['changed'] = True
    usage['active'] = {
        'filename': tracked['filename'], 'paused': stats['state'] == 'paused',
        'changed': tracked['changed'], 'rows': live_rows(tracked, stats, inventory, usage['totals']),
    }


def run():
    import fcntl
    defaults = {'totals': {}, 'records': [], 'tracked': None, 'active': None}
    with open('/tmp/u1-spool-accounting.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = DataStore(api, calibration_execute=lambda script: api('/printer/gcode/script', {'script': script}, timeout=1800), print_start=native_start)
        error_monitor = ErrorMonitor(api, get_item)
        error_stream = None
        initialized = False
        last_poll = 0
        while True:
            try:
                if not initialized or store.journal.exists():
                    store.recover()
                    initialized = True
                    if error_stream is None:
                        try:
                            error_stream = ErrorStream(store.folder)
                            error_stream.start()
                        except Exception:
                            logging.exception('Error stream initialization failed; polling remains enabled')
                if time.monotonic() - last_poll >= 5:
                    try:
                        store.recovery.capture()
                    except Exception:
                        logging.exception('Checkpoint observation failed; printer recovery files unchanged')
                    usage = get_item(USAGE, defaults.copy())
                    previous = json.dumps(usage, sort_keys=True)
                    tick(usage)
                    acknowledged = []
                    try:
                        usage['errorService'] = {**usage.get('errorService', {}), **(error_stream.health() if error_stream else {
                            'connected': False, 'message': 'Поток событий недоступен; работают периодические наблюдения.'})}
                        if error_stream:
                            acknowledged = error_monitor.consume(usage, error_stream.inbox.peek())
                        error_monitor.poll(usage)
                    except Exception as error:
                        usage.setdefault('errorService', {})['message'] = str(error)[:1000]
                        logging.exception('Print error collection failed; usage accounting remains enabled')
                    now = time.time()
                    if json.dumps(usage, sort_keys=True) != previous or now - usage.get('checkedAt', 0) > 45:
                        usage['checkedAt'] = now
                        store.commit_usage(usage)
                    if error_stream:
                        error_stream.inbox.ack(set(acknowledged))
                    try:
                        store.maintenance.poll(store)
                    except Exception:
                        logging.exception('Maintenance update failed; spool accounting remains enabled')
                    try:
                        from u1_companion_info import poll as poll_companion_update
                        poll_companion_update(store)
                    except Exception:
                        logging.exception('Companion update check unavailable')
                    store.sync_mirror()
                    last_poll = time.monotonic()
                store.dryer.heartbeat()
                store.process_requests()
                store.process_calibration_events()
                store.night.tick(store)
                try:
                    store.timed_pause.tick(store)
                except Exception:
                    logging.exception('Timed pause disabled after an error')
                    if store.timed_pause.active:
                        store.timed_pause.update(state='needs_review',message='Ошибка таймера. Продолжение отключено; проверьте принтер.')
                try:
                    store.scheduler.tick(store)
                except Exception:
                    logging.exception('Scheduler stopped after an error; no automatic retry')
                    if store.scheduler.active:
                        store.scheduler.update(state='needs_review',message='Ошибка планировщика. Проверьте принтер; автоматический повтор отключён.')
            except Exception:
                logging.exception('Spool accounting poll failed')
            time.sleep(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler('/tmp/u1-filament-data.log', maxBytes=512 * 1024, backupCount=1)])
    try:
        run()
    except Exception:
        logging.exception('U1 data service startup failed')
        raise
