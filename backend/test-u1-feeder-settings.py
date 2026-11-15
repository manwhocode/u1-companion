"""Isolated file tests. No real printer config or restart is used."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from u1_feeder_settings import FeederSettings, entries, inspect, rewrite

SAMPLE = '''# U1 — preserve comments and unrelated settings
[printer]
max_velocity: 500
[filament_feed left]
# extruder
filament_ch_1: 1 # keep left comment
filament_ch_2: 0
port_ch_1_pin: PA3
[filament_feed right]
filament_ch_1: 2
filament_ch_2: 3
port_ch_2_pin: PA0
[gcode_macro _FILAMENT_FEED_VARIABLE]
variable_module_sequence: 'left','left','right','right'
variable_channel_sequence: 1,0,0,1
gcode:
[idle_timeout]
timeout: 300
'''.encode()

def cfg(data):
    _, found = entries(data)
    result = {}
    for (section, key), (value, _, _) in found.items():
        result.setdefault(section, {})[key] = value
    return result

class Api:
    def __init__(self):
        self.active = cfg(SAMPLE)
        self.state = {'webhooks': {'state': 'ready'}, 'print_stats': {'state': 'standby'}, 'idle_timeout': {'state': 'Idle'},
                      'machine_state_manager': {'main_state': 0, 'action_code': 0}, 'exception_manager': {'exceptions': []}}
        for name in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3'):
            self.state[name] = {'target': 0}
    def __call__(self, path):
        if 'configfile' in path:
            return {'status': {'configfile': {'config': copy.deepcopy(self.active)}}}
        return {'status': copy.deepcopy(self.state)}

class FeederTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).parent.resolve() / 'local-backups' / 'feeder-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.temporary.name)
        self.config = self.folder / 'printer.cfg'
        self.config.write_bytes(SAMPLE)
        self.api = Api()
        self.store = FeederSettings(self.api, self.folder / 'backups', self.config)
    def tearDown(self):
        self.temporary.cleanup()
    def plan(self, a=True, b=False):
        return self.store.prepare({'hash': inspect(self.config.read_bytes())['hash'], 'swap12': a, 'swap34': b})
    def test_all_transitions_round_trip_and_only_five_values_change(self):
        for a in (False, True):
            for b in (False, True):
                data = rewrite(SAMPLE, a, b)
                self.assertEqual((inspect(data)['swap12'], inspect(data)['swap34']), (a, b))
                self.assertEqual(rewrite(data, a, b), data)
                self.assertEqual(rewrite(data, False, False), SAMPLE)
                for x in (False, True):
                    for y in (False, True):
                        self.assertEqual(rewrite(data, x, y), rewrite(SAMPLE, x, y))
                before = SAMPLE.splitlines()
                after = data.splitlines()
                changes = [line for line, other in zip(before, after) if line != other]
                self.assertTrue(all(line.startswith((b'filament_ch_', b'variable_channel_sequence:')) for line in changes))
                self.assertIn(b'port_ch_1_pin: PA3', data)
                self.assertIn(b'# keep left comment', data)
    def test_bom_crlf_and_user_instruction(self):
        source = b'\xef\xbb\xbf' + SAMPLE.replace(b'\n', b'\r\n')
        changed = rewrite(source, True, False)
        self.assertTrue(changed.startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'variable_channel_sequence: 0,1,0,1\r\n', changed)
        self.assertNotIn(b'\n', changed.replace(b'\r\n', b''))
        self.assertEqual(rewrite(changed, False, False), source)
    def test_mismatched_or_duplicate_config_is_rejected(self):
        for bad in (SAMPLE.replace(b'1,0,0,1', b'0,1,0,1'), SAMPLE + b'\n[filament_feed left]\n',
                    SAMPLE.replace(b'filament_ch_1: 1', b'filament_ch_1: 3'), SAMPLE.replace(b"'left','left'", b"'right','left'")):
            with self.assertRaises(ValueError):
                rewrite(bad, True, False)
    def test_apply_backup_and_pending_restart_without_any_restart(self):
        old_mode = self.config.stat().st_mode
        result = self.store.apply(self.plan(True, True))
        self.assertTrue(result['pendingRestart'])
        self.assertEqual((self.store.folder / result['backup']).read_bytes(), SAMPLE)
        self.assertEqual(self.config.stat().st_mode, old_mode)
        self.assertEqual(self.api.active, cfg(SAMPLE))
        self.api.active = cfg(self.config.read_bytes())
        self.assertFalse(self.store.state()['pendingRestart'])
    def test_stale_file_plan_service_restart_and_expiration_are_rejected(self):
        plan = self.plan()
        self.config.write_bytes(SAMPLE + b'# edited\n')
        with self.assertRaises(ValueError): self.store.apply(plan)
        self.config.write_bytes(SAMPLE)
        other = FeederSettings(self.api, self.store.folder, self.config)
        with self.assertRaises(ValueError): other.apply(plan)
        path = self.store.folder / (plan['previewId'] + '.plan')
        value = json.loads(path.read_text()); value['created'] -= 90; path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.store.apply(plan)
        self.assertEqual(self.config.read_bytes(), SAMPLE)
    def test_busy_hot_or_failed_printer_cannot_prepare_or_apply(self):
        plan = self.plan()
        original = copy.deepcopy(self.api.state)
        for change in [('print_stats', 'state', 'paused'), ('machine_state_manager', 'main_state', 4),
                       ('heater_bed', 'target', 60), ('extruder2', 'target', 220), ('webhooks', 'state', 'shutdown'),
                       ('exception_manager', 'exceptions', ['fault'])]:
            self.api.state = copy.deepcopy(original)
            section, key, value = change; self.api.state[section][key] = value
            with self.assertRaises(ValueError): self.plan()
            with self.assertRaises(ValueError): self.store.apply(plan)
            self.assertEqual(self.config.read_bytes(), SAMPLE)
    def test_failed_atomic_replace_keeps_original_file_and_backup(self):
        plan = self.plan()
        import os
        original_replace = os.replace
        def replace(source, dest):
            if Path(dest) == self.config: raise OSError('injected disk error')
            return original_replace(source, dest)
        with patch('u1_feeder_settings.os.replace', side_effect=replace):
            with self.assertRaises(OSError): self.store.apply(plan)
        self.assertEqual(self.config.read_bytes(), SAMPLE)
        self.assertEqual(next(self.store.folder.glob('*.printer.cfg')).read_bytes(), SAMPLE)

if __name__ == '__main__': unittest.main()
