"""Export and reversible clearing of visible journals; accounting/dedup records stay intact."""
import copy
import csv
import datetime
import io
import json
import re
import time
import uuid
from u1_recovery import atomic

USAGE = 'u1_spool_usage_v1'
KINDS = {'usage': ('records', 'archivedRecords'), 'errors': ('errors', 'archivedErrors')}


def kind(value):
    if value not in KINDS:
        raise ValueError('Выберите журнал списаний или ошибок.')
    return KINDS[value]


def visible(usage, name, archived=False):
    source, hidden = kind(name)
    ids = set(usage.get(hidden, []))
    return [copy.deepcopy(row) for row in usage.get(source, []) if archived or row['id'] not in ids]


def cell(value):
    if isinstance(value, (int, float)):
        return value
    text = '' if value is None else str(value)
    normalized = re.sub(r'^[\s\x00-\x1f\ufeff\u200b]+', '', text)
    if normalized.startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r')):
        text = "'" + text
    return text


def iso(timestamp):
    try:
        return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return str(timestamp)


def to_csv(name, records):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';', lineterminator='\r\n')
    if name == 'usage':
        writer.writerow(['UTC', 'Job ID', 'File', 'Status', 'Decision', 'Spool ID', 'Spool', 'Grams', 'Price per gram'])
        for record in records:
            for row in record.get('rows', []) or [{}]:
                writer.writerow([cell(v) for v in [iso(record['time']), record['id'], record.get('filename'), record.get('status'),
                                                   record.get('state'), row.get('spoolId'), row.get('name'), row.get('grams'), row.get('pricePerGram')]])
    else:
        writer.writerow(['UTC', 'Event ID', 'Job ID', 'File', 'Code', 'Message', 'Source'])
        for row in records:
            writer.writerow([cell(v) for v in [iso(row['time']), row['id'], row.get('jobId'), row.get('filename'), row.get('code'), row.get('message'), row.get('source')]])
    return '\ufeff' + stream.getvalue()


def export(store, payload):
    name = payload.get('kind'); kind(name)
    fmt = payload.get('format', 'json')
    if fmt not in ('json', 'csv') or type(payload.get('includeArchived', False)) is not bool:
        raise ValueError('Неизвестный формат экспорта.')
    records = visible(store.raw().get(USAGE, {}), name, payload.get('includeArchived', False))
    result = {'version': 1, 'kind': name, 'exportedAt': time.time(), 'records': records}
    return {'kind': name, 'format': fmt, 'count': len(records), 'content': to_csv(name, records) if fmt == 'csv' else json.dumps(result, ensure_ascii=False, indent=2)}


def prepare(store, payload):
    name = payload.get('kind'); kind(name)
    source = store.raw().get(USAGE, {})
    records = visible(source, name)
    token = str(uuid.uuid4())
    row = {'token': token, 'kind': name, 'time': time.time(), 'ids': [r['id'] for r in records]}
    folder = store.folder / 'log-plans'; folder.mkdir(mode=0o700, exist_ok=True)
    for old in folder.glob('*.json'):
        if old.stat().st_mtime < time.time() - 3600:
            old.unlink()
    if len(list(folder.glob('*.json'))) >= 50:
        raise ValueError('Слишком много неподтверждённых операций с журналом.')
    atomic(folder / (token + '.json'), row)
    return {'token': token, 'kind': name, 'count': len(records), 'review': sum(r.get('state') == 'review' for r in records)}


def clear(store, ident, payload):
    from u1_data_store import digest, state_from_raw
    if payload.get('confirmed') is not True:
        raise ValueError('Подтвердите очистку списка. Учёт расхода и остатки сохраняются.')
    token = payload.get('token')
    if not isinstance(token, str) or str(uuid.UUID(token)) != token:
        raise ValueError('Неверное подтверждение очистки.')
    p = store.folder / 'log-plans' / (token + '.json')
    if p.is_symlink():
        raise ValueError('Неверный план очистки.')
    plan = json.loads(p.read_text())
    if not 0 <= time.time() - plan['time'] < 120:
        raise ValueError('Подтверждение устарело. Откройте очистку заново.')
    _, archived = kind(plan['kind'])
    before = store.raw(); after = copy.deepcopy(before)
    usage = after.setdefault(USAGE, {'totals': {}, 'records': [], 'errors': []})
    usage[archived] = sorted(set(usage.get(archived, [])) | set(plan['ids']))
    result = store.commit(after, ident, {'cleared': len(plan['ids']), 'kind': plan['kind'], 'accountingPreserved': True}, digest(state_from_raw(before)))
    p.unlink(missing_ok=True)
    return result
