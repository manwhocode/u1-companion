"""Job orchestration tests with simulated APIs only. No hardware commands."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from u1_calibration_jobs import CalibrationJobs, measured, reason


class JobsTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent / 'local-backups' / 'calibration-job-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.state = {'webhooks': {'state': 'ready'}, 'print_stats': {'state': 'standby'},
                      'idle_timeout': {'state': 'Idle'}, 'machine_state_manager': {'main_state': 0, 'action_code': 0},
                      'exception_manager': {'exceptions': []}, 'purifier': {'power_detected': True},
                      'print_task_config': {'filament_type': ['PLA'] * 4, 'filament_color_rgba': ['000000FF'] * 4}}
        for slot in range(4):
            self.state['filament_motion_sensor e%d_filament' % slot] = {'enabled': True, 'filament_detected': True}
            self.state['extruder' if slot == 0 else 'extruder%d' % slot] = {'pressure_advance': .02, 'target': 0}
            side = 'filament_feed left' if slot < 2 else 'filament_feed right'
            self.state.setdefault(side, {})['extruder%d' % slot] = {'module_exist': True, 'filament_detected': True,
                'disable_auto': False, 'channel_error': 'ok', 'channel_error_state': 'none', 'channel_state': 'preload_finish'}
        self.logs, self.commands, self.saved = [], [], []
        self.raw = {'u1_filament_library_v1': {'revision': 'l', 'entries': [{'id': 'c', 'name': 'Black', 'calibration': {'flowRatio': .98}}]},
                    'u1_spool_inventory_v1': {'revision': 's', 'heads': ['s'] * 4, 'spools': [{'id': 's', 'colorId': 'c', 'name': 'My spool', 'material': 'PLA', 'hex': '#000000'}]}}
        self.jobs = CalibrationJobs(self.api, self.tmp.name, self.execute)

    def api(self, path):
        if path.startswith('/printer/objects/query'): return {'status': copy.deepcopy(self.state)}
        if path.startswith('/server/gcode_store'): return {'gcode_store': copy.deepcopy(self.logs)}
        if path.startswith('/server/database/item'): return {'value': copy.deepcopy(self.raw)}
        raise AssertionError(path)

    def execute(self, script):
        self.commands.append(script)
        if script.startswith('AUTO_FEEDING'):
            slot = int(script.split('EXTRUDER=')[1][0])
            self.state['filament_motion_sensor e%d_filament' % slot]['filament_detected'] = True
        if 'FLOW_CALIBRATE' in script:
            slot = int(script[1])
            name = 'extruder' if slot == 0 else 'extruder%d' % slot
            self.state[name]['pressure_advance'] = .024
            for message in ('// start flow calibration for ' + name, '// Got pressure advance: 0.024'):
                self.logs.append({'time': len(self.logs) + 1, 'type': 'response', 'message': message})

    def start(self, heads=(0, 1), save=False):
        plan = self.jobs.prepare({'heads': list(heads), 'saveResults': save})
        self.jobs.start(plan)
        return plan

    def finish(self):
        deadline = time.monotonic() + 3
        outer = self
        class Store:
            def handle(self, ident, request): outer.saved.append(request)
        while self.jobs.active and time.monotonic() < deadline:
            self.jobs.drain(Store())
            time.sleep(.005)
        self.jobs.thread.join(1)
        self.assertFalse(self.jobs.active)

    def test_background_queue_without_browser_and_duplicate_start(self):
        plan = self.start()
        self.finish()
        self.jobs.start(plan)
        self.assertEqual(len(self.commands), 2)
        self.assertEqual(self.jobs.state()['state'], 'completed')
        self.assertEqual(len(self.jobs.state()['results']), 2)

    def test_save_k_preserves_hidden_legacy_value(self):
        self.start((0,), True)
        self.finish()
        self.assertEqual(self.saved[0]['payload']['value']['pressureAdvance'], .024)
        self.assertEqual(self.saved[0]['payload']['value']['flowRatio'], .98)

    def test_stop_finishes_current_only(self):
        original = self.execute
        def stop(script):
            original(script)
            self.jobs.stop()
        self.jobs.execute = stop
        self.start()
        self.finish()
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.jobs.state()['state'], 'stopped')

    def test_cover_loss_before_start_no_commands(self):
        plan = self.jobs.prepare({'heads': [0], 'saveResults': False})
        self.state['purifier']['power_detected'] = False
        with self.assertRaises(ValueError): self.jobs.start(plan)
        self.assertEqual(self.commands, [])

    def test_cover_loss_stops_next_head(self):
        original = self.execute
        def disconnect(script):
            original(script)
            self.state['purifier']['power_detected'] = False
        self.jobs.execute = disconnect
        self.start()
        self.finish()
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.jobs.state()['state'], 'failed')

    def test_loading_verified_before_calibration(self):
        self.state['filament_motion_sensor e0_filament']['filament_detected'] = False
        self.start((0,))
        self.finish()
        self.assertTrue(self.commands[0].startswith('AUTO_FEEDING'))
        self.assertIn('FLOW_CALIBRATE', self.commands[1])

    def test_loading_failure_never_calibrates(self):
        self.state['filament_motion_sensor e0_filament']['filament_detected'] = False
        self.jobs.execute = lambda script: self.commands.append(script)
        self.start((0,))
        self.finish()
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.jobs.state()['state'], 'failed')

    def test_expired_plan_and_empty_head(self):
        plan = self.jobs.prepare({'heads': [0], 'saveResults': False})
        self.jobs.plans[plan['token']]['created'] -= 31
        with self.assertRaises(ValueError): self.jobs.start(plan)
        self.state['filament_feed left']['extruder0']['filament_detected'] = False
        with self.assertRaises(ValueError): self.jobs.prepare({'heads': [0], 'saveResults': False})
        self.assertEqual(self.commands, [])

    def test_restart_does_not_resume(self):
        self.jobs.update(state='calibrating', heads=[0])
        restored = CalibrationJobs(self.api, self.tmp.name, self.execute)
        self.assertEqual(restored.state()['state'], 'interrupted')
        self.assertEqual(self.commands, [])

    def test_cleanup_only_touched_head_and_stays_active(self):
        original = self.execute
        def run(script):
            if script.startswith('M104'):
                self.assertTrue(self.jobs.active)
            else:
                original(script)
                self.state['extruder']['target'] = 170
                self.state['filament_feed left']['extruder1']['filament_detected'] = False
        self.jobs.execute = run
        self.start()
        self.finish()
        self.assertEqual(self.commands, ['T0 A0\nFLOW_CALIBRATE\nM400'])
        self.assertEqual(self.jobs.state()['state'], 'failed')

    def test_admission_tpu_head_or_feeder_other_feeder(self):
        self.state['filament_feed left']['extruder0']['filament_detected'] = False
        self.assertTrue(reason(self.state, 0))
        self.state['print_task_config']['filament_type'][0] = 'TPU'
        self.assertEqual(reason(self.state, 0), '')

    def test_abort_or_factory_default_is_not_measurement(self):
        rows = [{'time': 1, 'type': 'response', 'message': '// start flow calibration for extruder'},
                {'time': 2, 'type': 'response', 'message': '// abort calibration'},
                {'time': 3, 'type': 'response', 'message': '// Got pressure advance: 0.02'}]
        with self.assertRaises(ValueError): measured(rows, 0, 0)


if __name__ == '__main__': unittest.main()
