"""Native bed-job lifecycle and real durable maintenance ledger, without hardware."""
import copy
import importlib.util
import tempfile
import time
import unittest
from unittest.mock import patch
from u1_calibration_jobs import CalibrationJobs
from u1_maintenance import KEY, totals

spec = importlib.util.spec_from_file_location('maintenance_fixtures', 'test-u1-maintenance.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)

class Api(fixtures.Api):
    def __init__(self):
        super().__init__()
        self.mesh = {'profile_name': 'default', 'progress': {'probe_state': 'completed'}, 'probed_matrix': [[0.0]*3 for _ in range(3)]}
        self.logs = [{'time': 1, 'type': 'response', 'message': '// Mesh Bed Leveling Complete'}]
    def __call__(self, path, payload=None, method=None):
        if path.startswith('/server/gcode_store'):
            return {'gcode_store': copy.deepcopy(self.logs)}
        result = super().__call__(path, payload, method)
        if path.startswith('/printer/objects/query'):
            result['status'].update(webhooks={'state': 'ready'}, exception_manager={'exceptions': []}, bed_mesh=copy.deepcopy(self.mesh))
            for name in ('heater_bed', 'extruder', 'extruder1', 'extruder2', 'extruder3'):
                result['status'][name] = {'target': 0}
        return result

class BedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.api = Api(); self.calls = []; self.mode = 'success'
        self.store = fixtures.DataStore(self.api, self.temp.name, calibration_execute=self.execute)
        self.store.recover(); self.store.maintenance.poll(self.store, force=True)
        self.jobs = self.store.calibration_jobs
    def execute(self, script):
        self.calls.append(script)
        if script.startswith('G28'):
            if self.mode == 'timeout': raise TimeoutError('native response unknown')
            if self.mode != 'old_log':
                self.api.logs.append({'time': 2, 'type': 'response', 'message': '// Mesh Bed Leveling Complete'})
            if self.mode == 'aborted': self.api.mesh['progress']['probe_state'] = 'aborted'
            if self.mode == 'error': self.api.logs.append({'time': 3, 'type': 'response', 'message': '!! probe failed'})
    def start(self):
        plan = self.jobs.prepare_bed()
        self.jobs.start_bed({**plan, 'confirmed': True})
        return plan
    def finish(self):
        deadline = time.monotonic()+3
        while self.jobs.active and time.monotonic() < deadline:
            self.store.process_calibration_events(); time.sleep(.005)
        self.jobs.thread.join(1)
        self.assertFalse(self.jobs.active)
    def test_success_records_once_preserves_counters_and_runs_without_browser(self):
        before = totals(self.store.get('fluidd', KEY)); self.api.idle_state = 'Ready'
        plan = self.start(); self.finish()
        data = self.store.get('fluidd', KEY)
        self.assertEqual(self.jobs.state()['state'], 'completed')
        self.assertIsNotNone(data['bed']); self.assertEqual(totals(data), before)
        self.assertEqual(len(data['history']), 1)
        self.jobs.start_bed({**plan, 'confirmed': True})
        self.store.maintenance.record_bed(self.store, self.jobs.state()['id'])
        self.assertEqual(len(self.store.get('fluidd', KEY)['history']), 1)
        self.assertEqual(self.calls, ['G28\nAUTO_BED_MESH_CALIBRATE', 'M140 S0'])
    def test_abort_error_timeout_and_old_success_do_not_mark_completed(self):
        for mode in ('aborted', 'error', 'timeout', 'old_log'):
            with self.subTest(mode=mode):
                calls_before = len(self.calls)
                self.mode = mode; self.api.mesh['progress']['probe_state'] = 'completed'; self.api.logs = self.api.logs[:1]
                self.start(); self.finish()
                self.assertEqual(self.jobs.state()['state'], 'failed')
                self.assertIsNone(self.store.get('fluidd', KEY)['bed'])
                self.assertEqual(self.calls[calls_before:], ['G28\nAUTO_BED_MESH_CALIBRATE', 'M140 S0'])
    def test_unsafe_state_and_unconfirmed_or_expired_plan_never_send_commands(self):
        self.api.idle = False
        with self.assertRaises(ValueError): self.jobs.prepare_bed()
        self.api.idle = True; plan = self.jobs.prepare_bed()
        with self.assertRaises(ValueError): self.jobs.start_bed(plan)
        self.jobs.plans[plan['token']]['created'] -= 31
        with self.assertRaises(ValueError): self.jobs.start_bed({**plan, 'confirmed': True})
        self.assertEqual(self.calls, [])
    def test_plan_cannot_be_used_to_start_head_calibration(self):
        plan = self.jobs.prepare_bed()
        with self.assertRaises(ValueError): self.jobs.start(plan)
        self.assertEqual(self.calls, [])
    def test_restart_does_not_resume_or_mark_interrupted_job(self):
        self.jobs.job.update(kind='bed', state='calibrating'); self.jobs.update()
        jobs = CalibrationJobs(self.api, self.jobs.folder, self.execute)
        self.assertEqual(jobs.state()['state'], 'interrupted'); self.assertEqual(self.calls, [])
        self.assertIsNone(self.store.get('fluidd', KEY)['bed'])

if __name__ == '__main__': unittest.main()
