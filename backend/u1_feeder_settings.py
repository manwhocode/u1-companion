"""Restricted U1 feeder mapping editor. Never restarts Klipper itself."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid

SECTIONS = ('filament_feed left', 'filament_feed right', 'gcode_macro _FILAMENT_FEED_VARIABLE')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def entries(data):
    source = data.decode('utf-8-sig')
    headers = list(re.finditer(r'^\s*\[([^\]\r\n]+)\][ \t]*(?:[#;][^\r\n]*)?\r?$', source, re.M))
    found = {}
    for section in SECTIONS:
        matches = [(i, m) for i, m in enumerate(headers) if m.group(1).strip() == section]
        if len(matches) != 1:
            raise ValueError('Ожидается ровно один раздел [' + section + '] в printer.cfg.')
        i, match = matches[0]
        end = headers[i + 1].start() if i + 1 < len(headers) else len(source)
        block = source[match.end():end]
        keys = ('filament_ch_1', 'filament_ch_2') if section.startswith('filament_feed') else ('variable_module_sequence', 'variable_channel_sequence')
        for key in keys:
            rows = list(re.finditer(r'^([ \t]*' + re.escape(key) + r'[ \t]*:[ \t]*)([^#;\r\n]*)([^\r\n]*)\r?$', block, re.M))
            if len(rows) != 1:
                raise ValueError('Неоднозначное поле ' + key + ' в [' + section + '].')
            row = rows[0]
            raw = row.group(2).rstrip()
            found[(section, key)] = (raw, match.end() + row.start(2), match.end() + row.start(2) + len(raw))
    return source, found


def inspect(data):
    _, found = entries(data)
    value = lambda section, key: found[(section, key)][0]
    try:
        modules = ast.literal_eval(value(SECTIONS[2], 'variable_module_sequence'))
        sequence = ast.literal_eval(value(SECTIONS[2], 'variable_channel_sequence'))
        left = tuple(int(value(SECTIONS[0], key)) for key in ('filament_ch_1', 'filament_ch_2'))
        right = tuple(int(value(SECTIONS[1], key)) for key in ('filament_ch_1', 'filament_ch_2'))
    except (ValueError, SyntaxError, TypeError) as error:
        raise ValueError('Неверный формат схемы податчиков.') from error
    if tuple(modules) != ('left', 'left', 'right', 'right') or left not in ((1, 0), (0, 1)) or right not in ((2, 3), (3, 2)):
        raise ValueError('Обнаружена неподдерживаемая схема U1. Автоматическая запись остановлена.')
    expected = left + ((0, 1) if right == (2, 3) else (1, 0))
    if tuple(sequence) != expected or any(type(x) is not int for x in sequence):
        raise ValueError('filament_ch и variable_channel_sequence не согласованы. Запись остановлена.')
    return {'swap12': left == (0, 1), 'swap34': right == (3, 2), 'hash': sha(data)}


def rewrite(data, swap12, swap34):
    if type(swap12) is not bool or type(swap34) is not bool:
        raise ValueError('Переключатели должны быть галочками.')
    inspect(data)
    source, found = entries(data)
    left = (0, 1) if swap12 else (1, 0)
    right = (3, 2) if swap34 else (2, 3)
    sequence = left + ((1, 0) if swap34 else (0, 1))
    desired = {(SECTIONS[0], 'filament_ch_1'): str(left[0]), (SECTIONS[0], 'filament_ch_2'): str(left[1]),
               (SECTIONS[1], 'filament_ch_1'): str(right[0]), (SECTIONS[1], 'filament_ch_2'): str(right[1]),
               (SECTIONS[2], 'variable_channel_sequence'): ','.join(map(str, sequence))}
    edits = []
    current = inspect(data)
    if current['swap12'] == swap12 and current['swap34'] == swap34:
        return data
    for key, replacement in desired.items():
        value, begin, end = found[key]
        # Preserve the original formatting for unchanged values.
        old = ast.literal_eval(value)
        new = ast.literal_eval(replacement)
        if old != new:
            edits.append((begin, end, replacement))
    for begin, end, replacement in sorted(edits, reverse=True):
        source = source[:begin] + replacement + source[end:]
    result = (b'\xef\xbb\xbf' if data.startswith(b'\xef\xbb\xbf') else b'') + source.encode('utf-8')
    after = inspect(result)
    if after['swap12'] != swap12 or after['swap34'] != swap34:
        raise ValueError('Проверка подготовленного printer.cfg не пройдена.')
    return result


def atomic(path, data, mode=0o600):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        if os.name != 'nt':
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class FeederSettings:
    def __init__(self, api, folder, config='/home/lava/printer_data/config/printer.cfg'):
        self.api = api
        self.folder = Path(folder)
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.config = Path(config).resolve(strict=True)
        self.instance = uuid.uuid4().hex

    def active(self):
        cfg = self.api('/printer/objects/query?configfile')['status']['configfile']['config']
        text = ''
        for section in SECTIONS:
            keys = ('filament_ch_1', 'filament_ch_2') if section.startswith('filament_feed') else ('variable_module_sequence', 'variable_channel_sequence')
            text += '[' + section + ']\n' + ''.join(key + ': ' + str(cfg[section][key]) + '\n' for key in keys)
        return inspect(text.encode())

    def state(self):
        data = self.config.read_bytes()
        disk = inspect(data)
        try:
            running = self.active()
        except (KeyError, ValueError, OSError):
            running = None
        return {**disk, 'activeSwap12': running['swap12'] if running else None, 'activeSwap34': running['swap34'] if running else None,
                'pendingRestart': running is None or (disk['swap12'], disk['swap34']) != (running['swap12'], running['swap34'])}

    def require_safe(self):
        names = 'webhooks&print_stats&idle_timeout&machine_state_manager&exception_manager&heater_bed&extruder&extruder1&extruder2&extruder3'
        status = self.api('/printer/objects/query?' + names)['status']
        machine = status.get('machine_state_manager', {})
        if (status.get('webhooks', {}).get('state') != 'ready' or status.get('print_stats', {}).get('state') not in ('standby', 'complete', 'cancelled') or
                status.get('idle_timeout', {}).get('state') not in ('Idle', 'Ready') or machine.get('main_state') not in (0, 'IDLE') or
                machine.get('action_code') not in (0, 'IDLE') or status.get('exception_manager', {}).get('exceptions', [True])):
            raise ValueError('Настройки применяются только на свободном принтере без ошибок.')
        if any(status.get(name, {}).get('target') != 0 for name in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3')):
            raise ValueError('Сначала выключите нагрев стола и всех головок.')
        self.active()

    def prepare(self, payload):
        self.require_safe()
        data = self.config.read_bytes()
        if sha(data) != payload.get('hash'):
            raise ValueError('printer.cfg изменился. Обновите настройки.')
        target = rewrite(data, payload.get('swap12'), payload.get('swap34'))
        ident = str(uuid.uuid4())
        plan = {'instance': self.instance, 'created': time.time(), 'before': sha(data), 'after': sha(target),
                'swap12': payload['swap12'], 'swap34': payload['swap34']}
        atomic(self.folder / (ident + '.plan'), json.dumps(plan).encode())
        return {'previewId': ident}

    def apply(self, payload):
        ident = payload.get('previewId', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', ident):
            raise ValueError('Неверный предпросмотр настроек.')
        plan = json.loads((self.folder / (ident + '.plan')).read_text())
        if plan['instance'] != self.instance or not 0 <= time.time() - plan['created'] <= 60:
            raise ValueError('Подтверждение устарело. Обновите настройки и повторите сохранение.')
        self.require_safe()
        data = self.config.read_bytes()
        if sha(data) != plan['before']:
            raise ValueError('printer.cfg изменился после подтверждения. Запись отменена.')
        target = rewrite(data, plan['swap12'], plan['swap34'])
        if sha(target) != plan['after']:
            raise ValueError('Контрольная сумма новых настроек не совпала.')
        if data == target:
            return {**self.state(), 'backup': ''}
        backup = time.strftime('%Y%m%d-%H%M%S') + '-' + ident + '.printer.cfg'
        atomic(self.folder / backup, data)
        self.require_safe()
        if self.config.read_bytes() != data:
            raise ValueError('printer.cfg изменился перед записью. Сохранение отменено.')
        atomic(self.config, target, stat.S_IMODE(self.config.stat().st_mode))
        if self.config.read_bytes() != target:
            raise ValueError('Принтер не подтвердил сохранение printer.cfg.')
        # No deferred restart or reboot; restart is a separate explicit UI action.
        return {**self.state(), 'backup': backup}

    def restart_check(self, payload):
        self.require_safe()
        value = self.state()
        if value['hash'] != payload.get('hash'):
            raise ValueError('printer.cfg изменился. Обновите настройки перед перезапуском.')
        return value
