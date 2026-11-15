"""Regression checks for the U1 usage ledger. Run with python test-spool-accounting.py."""
import runpy
import time
import unittest
from unittest.mock import patch


class AccountingTest(unittest.TestCase):
    def setUp(self):
        self.tick = runpy.run_path('spool-accounting.py')['tick']
        self.usage = {'totals': {}, 'records': [], 'tracked': None, 'active': None}
        self.decisions = {}
        self.job = {'job_id': '000001', 'filename': 'test.gcode', 'status': 'in_progress', 'start_time': time.time(),
                    'metadata': {'filament_weight': [20, 10], 'filament_used_mm': [8000, 4000], 'estimated_time': 1800}}
        self.stats = {'filename': 'test.gcode', 'state': 'printing', 'print_duration': 120, 'filament_used': 1000}
        self.task = {'extruder_map_table': [2, 0], 'extruders_used': [True, False, True, False],
                     'extruders_replenished': [0, 1, 2, 3], 'filament_exist': [True] * 4,
                     'filament_type': ['PLA', 'PLA', 'ABS', 'PLA'],
                     'filament_color_rgba': ['000000FF', '000000FF', 'FFFFFFFF', '000000FF']}
        self.inventory = {'heads': ['a', None, 'b', None],
                          'spools': [{'id': 'a', 'name': 'A', 'material': 'PLA', 'hex': '#000000', 'grams': 50},
                                     {'id': 'b', 'name': 'B', 'material': 'ABS', 'hex': '#FFFFFF', 'grams': 12}]}
        mocks = patch.dict(self.tick.__globals__, api=self.api, get_item=self.get_item)
        mocks.start()
        self.addCleanup(mocks.stop)

    def api(self, path):
        if path.startswith('/server/history/job?'):
            return {'job': self.job}
        if path.startswith('/server/history/list?'):
            return {'jobs': [self.job]}
        return {'status': {'print_stats': self.stats, 'print_task_config': self.task}}

    def get_item(self, key, default=None):
        if key == 'u1_spool_inventory_v1':
            return self.inventory
        return self.decisions.get(key, default)

    def finish(self, status, length):
        self.job.update(status=status, filament_used=length, end_time=time.time())
        self.stats['state'] = status
        self.tick(self.usage)
        self.tick(self.usage)

    def test_completed_job_uses_physical_head_mapping_and_charges_once(self):
        self.tick(self.usage)
        short = next(row for row in self.usage['active']['rows'] if row['head'] == 2)
        self.assertEqual((short['shortage'], short['seconds']), (8, 960))
        self.finish('completed', 12000)
        self.assertEqual(self.usage['totals'], {'a': 10, 'b': 20})
        self.assertEqual(len(self.usage['records']), 1)

    def test_cancelled_multicolor_requires_confirmation(self):
        self.tick(self.usage)
        self.finish('cancelled', 3000)
        record = self.usage['records'][0]
        self.assertEqual(record['state'], 'review')
        self.assertEqual([row['grams'] for row in record['rows']], [5, 2.5])
        self.assertEqual(self.usage['totals'], {})
        self.decisions['u1_spool_review_000001'] = {'time': record['time'], 'grams': [4, 1]}
        self.tick(self.usage)
        self.tick(self.usage)
        self.assertEqual(self.usage['totals'], {'a': 1, 'b': 4})

    def test_existing_completed_record_is_never_debited_again(self):
        self.tick(self.usage)
        tracked = self.usage['tracked'].copy()
        self.finish('completed', 12000)
        before = self.usage['totals'].copy()
        self.usage['tracked'] = tracked
        self.tick(self.usage)
        self.assertEqual(self.usage['totals'], before)
        self.assertEqual(len(self.usage['records']), 1)

    def test_cancelled_single_head_uses_measured_length(self):
        self.job['metadata'].update(filament_weight=[20, 0], filament_used_mm=[8000, 0])
        self.task['extruders_used'] = [False, False, True, False]
        self.tick(self.usage)
        self.finish('cancelled', 2000)
        self.assertEqual(self.usage['totals'], {'b': 5})

    def test_auto_replenishment_change_requires_review(self):
        self.tick(self.usage)
        self.task['extruders_replenished'] = [0, 1, 1, 3]
        self.tick(self.usage)
        self.assertTrue(self.usage['active']['changed'])
        self.finish('completed', 11800)
        self.assertEqual(self.usage['records'][0]['state'], 'review')
        self.assertEqual(self.usage['totals'], {})

    def test_color_identity_is_snapshotted_before_spool_reassignment(self):
        spool = self.inventory['spools'][1]
        spool['colorId'] = 'old-color'
        self.decisions['u1_filament_library_v1'] = {'entries': [{'id': 'old-color', 'name': 'Old white'}]}
        self.tick(self.usage)
        spool['colorId'] = 'new-color'
        self.decisions['u1_filament_library_v1']['entries'][0]['name'] = 'Renamed'
        self.finish('completed', 12000)
        row = self.usage['records'][0]['rows'][0]
        self.assertEqual((row['colorId'], row['colorName']), ('old-color', 'Old white'))

    def test_price_is_snapshotted_and_old_records_are_retained(self):
        self.usage['records'] = [{'id': f'old-{i}', 'state': 'applied'} for i in range(45)]
        spool = self.inventory['spools'][1]
        spool['pricePerGram'] = 0.025
        self.tick(self.usage)
        spool['pricePerGram'] = 0.04
        self.finish('completed', 12000)
        self.assertEqual(len(self.usage['records']), 46)
        self.assertEqual(self.usage['records'][0]['rows'][0]['pricePerGram'], 0.025)


if __name__ == '__main__':
    unittest.main()
