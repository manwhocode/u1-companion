import copy
import datetime
import importlib.util
from pathlib import Path
import tempfile
import unittest
import uuid
from u1_data_store import DataStore, document, parse_document, state_from_raw
from u1_maintenance import DEFAULT_PERIODS, KEY, view, validate_periods, next_month, merge

spec = importlib.util.spec_from_file_location('maintenance_fixtures', 'test-u1-maintenance.py')
fixtures = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixtures)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = DataStore(fixtures.Api(), self.tmp.name); self.store.recover()
        self.m = self.store.maintenance; self.m.poll(self.store, force=True)
    def change(self, **payload):
        return self.m.change(self.store, str(uuid.uuid4()), {'revision': self.store.get('fluidd', KEY)['revision'], **payload})
    def test_disable_both_notifications_keeps_history_and_counters(self):
        self.change(action='service', confirmed=True); self.change(action='bed', confirmed=True)
        before = copy.deepcopy(self.store.get('fluidd', KEY)); periods = copy.deepcopy(DEFAULT_PERIODS)
        periods['service']['enabled'] = periods['bed']['enabled'] = False
        result = self.change(action='periods', value=periods)
        self.assertFalse(result['serviceDue']); self.assertFalse(result['bedDue'])
        for key in ('jobs', 'baseSeconds', 'service', 'bed', 'history'):
            self.assertEqual(result['value'][key], before[key])
    def test_custom_hours_days_and_print_counts_are_independent(self):
        data = copy.deepcopy(self.store.get('fluidd', KEY))
        marker = {'time': 1000, 'seconds': 0, 'completed': 0}
        data.update(service=marker, bed=marker, periods=copy.deepcopy(DEFAULT_PERIODS))
        data['periods']['service'].update(hours=1, months=None)
        data['periods']['bed'].update(hours=None, prints=2, days=1)
        self.assertFalse(view(data, now=2000)['serviceDue'])
        data['baseSeconds'] = 3600
        self.assertTrue(view(data, now=2000)['serviceDue'])
        self.assertFalse(view(data, now=2000)['bedDue'])
        self.assertTrue(view(data, now=1000+86400)['bedDue'])
    def test_legacy_bed_toggle_is_compatible_with_new_preferences(self):
        self.change(action='periods', value=copy.deepcopy(DEFAULT_PERIODS))
        self.change(action='bed_enabled', enabled=False)
        result=self.change(action='bed_enabled', enabled=True)
        self.assertTrue(result['periods']['bed']['enabled']);self.assertTrue(result['value']['bedEnabled'])
    def test_invalid_and_empty_enabled_periods_reject(self):
        for bad in (0, -1, 1.5, True, float('nan'), 100001):
            value=copy.deepcopy(DEFAULT_PERIODS);value['service']['hours']=bad
            with self.assertRaises(ValueError):validate_periods(value)
        value=copy.deepcopy(DEFAULT_PERIODS);value['service'].update(hours=None, months=None)
        with self.assertRaises(ValueError):validate_periods(value)
        value['service']['enabled']=False;validate_periods(value)
    def test_multiple_calendar_months_do_not_accumulate_february_clamping(self):
        start=datetime.datetime(2026,1,31,tzinfo=datetime.timezone.utc).timestamp()
        end=datetime.datetime.fromtimestamp(next_month(start,months=2),datetime.timezone.utc)
        self.assertEqual((end.month,end.day),(3,31))
    def test_legacy_import_cannot_reenable_current_disabled_reminders(self):
        data=copy.deepcopy(self.store.get('fluidd',KEY));new=copy.deepcopy(data)
        new['periods']=copy.deepcopy(DEFAULT_PERIODS);new['periods']['service']['enabled']=False
        merged=merge(new,data)
        self.assertFalse(merged['periods']['service']['enabled'])
    def test_export_import_roundtrip_retains_preferences(self):
        periods=copy.deepcopy(DEFAULT_PERIODS);periods['service'].update(days=14,hours=50,months=None)
        self.change(action='periods',value=periods)
        data=state_from_raw(self.store.raw())
        restored=parse_document(document(data))
        self.assertEqual(restored['maintenance']['periods'],periods)


if __name__ == '__main__':unittest.main()
