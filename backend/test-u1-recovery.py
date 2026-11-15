import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from u1_recovery import Recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.native = self.root / 'native'; self.native.mkdir()
        self.gcodes = self.root / 'gcodes'; self.gcodes.mkdir()
        self.source = self.gcodes / 'test.gcode'; self.source.write_text('G1 X1\n')
        self.env = self.native / 'pl_print_file_env.json'
        self.env.write_text(json.dumps({'file_path': str(self.source), 'env_flag': 1}))
        self.s = {'webhooks': {'state': 'ready'}, 'print_stats': {'filename': 'test.gcode', 'state': 'printing', 'info': {'current_layer': 4}},
                  'virtual_sdcard': {'file_position': 123, 'is_active': True, 'pl_env_valid': False},
                  'machine_state_manager': {'main_state': 0, 'action_code': 0},
                  'exception_manager': {'exceptions': []}, 'purifier': {'power_detected': True}}
        for name in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3'): self.s[name] = {'target': 0}
        self.calls = []
        self.fail_send = False
        self.now = 1000
        self.r = Recovery(self.api, self.root / 'recovery', self.native, lambda: self.now)
        self.store = SimpleNamespace(folder=self.root, require_idle=lambda **kw: None,
                                     scheduler=SimpleNamespace(active=False), timed_pause=SimpleNamespace(active=False))

    def tearDown(self): self.tmp.cleanup()

    def api(self, route, payload=None, **kw):
        if route.startswith('/printer/objects/query'): return {'status': copy.deepcopy(self.s)}
        if route == '/server/files/roots': return [{'name': 'gcodes', 'path': str(self.gcodes)}]
        self.calls.append((route, payload))
        if self.fail_send: raise TimeoutError('No acknowledgement')
        return {}

    def valid(self):
        self.s['print_stats']['state'] = 'standby'
        self.s['virtual_sdcard'].update(is_active=False, pl_env_valid=True)

    def test_observations_survive_cancel_and_restart_without_becoming_resumable(self):
        self.r.capture()
        self.s['print_stats']['state'] = 'cancelled'; self.env.unlink(); self.r.capture()
        restarted = Recovery(self.api, self.root / 'recovery', self.native)
        self.assertEqual(restarted.points[0]['endedAs'], 'cancelled')
        self.assertFalse(restarted.points[0]['resumable'])
        self.assertTrue((self.root / 'recovery' / (restarted.points[0]['id'] + '.json')).exists())
        with self.assertRaises(ValueError): restarted.prepare(self.store)
        self.assertEqual(self.calls, [])

    def test_interval_and_retention_bound_archive(self):
        for i in range(40):
            self.now += 16; self.s['virtual_sdcard']['file_position'] += 1; self.r.capture()
        self.assertEqual(len(self.r.points), 30)
        self.assertEqual(len(list((self.root / 'recovery').glob('*.json'))), 31)
        self.r.capture(); self.assertEqual(len(self.r.points), 30)

    def test_native_resume_only_uses_stock_command_after_confirmation(self):
        self.valid(); plan = self.r.prepare(self.store)
        self.assertEqual(self.calls, [])
        with self.assertRaises(ValueError): self.r.resume(self.store, {'token': plan['token']})
        self.r.resume(self.store, {'token': plan['token'], 'confirmed': True})
        self.assertEqual(self.calls, [('/printer/gcode/script', {'script': 'SDCARD_PRINT_PL_RESTORE'})])

    def test_lost_acknowledgement_cannot_repeat_after_restart(self):
        self.valid(); plan = self.r.prepare(self.store); self.fail_send = True
        with self.assertRaises(TimeoutError): self.r.resume(self.store, {**plan, 'confirmed': True})
        restarted = Recovery(self.api, self.root / 'recovery', self.native)
        with self.assertRaises(ValueError): restarted.prepare(self.store)
        self.assertEqual(len(self.calls), 1)

    def test_changed_gcode_and_native_point_invalidate_confirmation(self):
        for change in (lambda: self.source.write_text('G1 X2\n'), lambda: self.env.write_text(json.dumps({'file_path': str(self.source), 'env_flag': 1, 'changed': True}))):
            self.valid(); plan = self.r.prepare(self.store); change()
            with self.assertRaises(ValueError): self.r.resume(self.store, {**plan, 'confirmed': True})
        self.assertEqual(self.calls, [])

    def test_expired_plan(self):
        self.valid(); plan = self.r.prepare(self.store); self.now += 121
        with self.assertRaises(ValueError): self.r.resume(self.store, {**plan, 'confirmed': True})

    def test_machine_cover_errors_and_heaters_fail_closed(self):
        self.valid()
        for key, value in [('machine_state_manager', {'main_state': True, 'action_code': 0}),
                           ('machine_state_manager', {'main_state': 0, 'action_code': 8}),
                           ('purifier', {'power_detected': False}), ('exception_manager', {}),
                           ('exception_manager', {'exceptions': ['fault']}), ('extruder3', {}),
                           ('heater_bed', {'target': 60}), ('webhooks', {'state': 'shutdown'})]:
            before = self.s[key]; self.s[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.r.prepare(self.store)
            self.s[key] = before

    def test_busy_schedule_or_dryer(self):
        self.valid(); self.store.scheduler.active = True
        with self.assertRaises(ValueError): self.r.prepare(self.store)
        self.store.scheduler.active = False
        (self.root / 'drying').mkdir(); (self.root / 'drying/state.json').write_text('{"state":"running"}')
        with self.assertRaises(ValueError): self.r.prepare(self.store)

    def test_source_outside_gcodes_rejected(self):
        self.valid(); other = self.root / 'elsewhere.gcode'; other.write_text('G1 X1')
        self.env.write_text(json.dumps({'file_path': str(other), 'env_flag': 1}))
        with self.assertRaises(ValueError): self.r.prepare(self.store)

    def test_cancelled_history_does_not_validate_native_environment(self):
        self.r.capture(); self.valid(); self.s['virtual_sdcard']['pl_env_valid'] = False
        with self.assertRaises(ValueError): self.r.prepare(self.store)
        self.assertEqual(self.calls, [])

    def test_atomic_index_and_archive_are_readable(self):
        self.r.capture()
        self.assertEqual(json.loads(self.r.path.read_text())['points'], self.r.points)
        self.assertFalse(list(self.r.folder.glob('*.next')))


if __name__ == '__main__': unittest.main()
