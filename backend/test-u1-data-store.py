"""Regression checks for legacy migration, imports and interrupted writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.parse
import uuid

from u1_data_store import CONTROL, KEYS, RESULTS, DataStore, document, merge_data, parse_document, state_from_raw


def color(ident='color'):
    return {'id': ident, 'name': 'Blue', 'material': 'PLA', 'hex': '#5EBDDB', 'manufacturer': 'Snapmaker', 'fullSpectrum': True}


def sample_raw():
    return {
        KEYS['library']: {'revision': 'colors-old', 'entries': [color()], 'trash': []},
        KEYS['inventory']: {'revision': 'spools-old', 'spools': [], 'cores': [], 'heads': [None] * 4},
        KEYS['usage']: {'totals': {}, 'records': [], 'tracked': None, 'active': None, 'checkedAt': 10},
    }


class Api:
    def __init__(self):
        self.namespaces = {'fluidd': sample_raw()}
        self.fail_key = None
        self.crash_key = None
        self.idle = True
        self.idle_state = 'Idle'
        self.machine_state = 0

    def __call__(self, path, payload=None, method=None):
        if path.startswith('/printer/objects/query'):
            return {'status': {'idle_timeout': {'state': self.idle_state if self.idle else 'Printing'},
                               'machine_state_manager': {'main_state': self.machine_state, 'action_code': 0},
                               'print_stats': {'state': 'standby' if self.idle else 'printing'}}}
        if payload is not None:
            key = payload['key']
            if key == self.fail_key:
                self.fail_key = None
                raise OSError('Injected write failure')
            self.namespaces.setdefault(payload['namespace'], {})[key] = copy.deepcopy(payload['value'])
            if key == self.crash_key:
                self.crash_key = None
                raise SystemExit('Injected process crash')
            return {}
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
        namespace = query['namespace'][0]
        values = self.namespaces.get(namespace, {})
        key = query.get('key', [None])[0]
        if method == 'DELETE':
            values.pop(key, None)
            return {}
        if key is not None and key not in values:
            raise urllib.error.HTTPError(path, 404, 'missing', {}, None)
        return {'value': copy.deepcopy(values if key is None else values[key])}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.test_root = Path(__file__).resolve().parent / 'local-backups' / 'stage1-tests'
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=self.test_root)
        self.api = Api()
        self.store = DataStore(self.api, self.temporary.name)
        self.store.recover()

    def tearDown(self):
        self.assertTrue(Path(self.temporary.name).resolve().is_relative_to(self.test_root))
        self.temporary.cleanup()

    def preview(self, data, mode='replace'):
        return self.store.handle(str(uuid.uuid4()), {'operation': 'preview', 'payload': {'document': document(data), 'mode': mode}})

    def test_usage_color_snapshots_round_trip_and_merge(self):
        raw = sample_raw()
        record = {'id': '001', 'filename': 'part.gcode', 'status': 'completed', 'time': 1,
                  'rows': [{'head': 0, 'spoolId': 'deleted', 'name': 'Old spool', 'grams': 10,
                            'colorId': 'deleted-color', 'colorName': 'Old blue', 'pricePerGram': .02}],
                  'state': 'applied', 'method': 'measured'}
        raw[KEYS['usage']].update(totals={'deleted': 10}, records=[record])
        data = state_from_raw(raw)
        self.assertEqual(parse_document(document(data))['usage']['records'][0], record)
        merged, _ = merge_data(state_from_raw(sample_raw()), data)
        self.assertEqual(merged['usage']['records'][0], record)
        record['rows'][0].pop('colorId')
        with self.assertRaises(ValueError):
            state_from_raw(raw)

    def test_legacy_missing_trash_is_migrated_without_rewriting_source(self):
        self.assertNotIn('trash', self.api.namespaces['fluidd'][KEYS['inventory']])
        exported = self.store.handle(str(uuid.uuid4()), {'operation': 'export'})['document']
        self.assertEqual(exported['data']['inventory']['trash'], [])
        self.assertEqual(exported['version'], 1)
        self.assertNotIn('checkedAt', exported['data']['usage'])
        self.assertNotIn('tracked', exported['data']['usage'])
        self.assertEqual(parse_document(exported)['library']['entries'][0], color())

    def test_import_is_repeatable_without_duplicate_records(self):
        data = state_from_raw(sample_raw())
        data['library']['entries'].append(color('second'))
        preview = self.preview(data, 'merge')
        ident = str(uuid.uuid4())
        self.store.handle(ident, {'operation': 'import', 'payload': {'previewId': preview['previewId']}})
        current = state_from_raw(self.store.raw())
        second = self.preview(data, 'merge')
        self.store.handle(str(uuid.uuid4()), {'operation': 'import', 'payload': {'previewId': second['previewId']}})
        self.assertEqual(len(state_from_raw(self.store.raw())['library']['entries']), 2)
        self.assertEqual(current['inventory']['heads'], [None] * 4)
        self.assertTrue(self.api.namespaces[RESULTS][ident]['ok'])

    def test_write_failure_rolls_back_both_lists(self):
        before = self.store.raw()
        data = state_from_raw(before)
        data['library']['entries'] = [color('new')]
        preview = self.preview(data)
        self.api.fail_key = KEYS['inventory']
        with self.assertRaises(OSError):
            self.store.handle(str(uuid.uuid4()), {'operation': 'import', 'payload': {'previewId': preview['previewId']}})
        self.assertEqual(self.store.raw(), before)
        self.assertFalse(self.store.journal.exists())
        self.assertEqual(self.api.namespaces['fluidd'][CONTROL]['state'], 'ready')

    def test_process_crash_recovers_from_durable_journal(self):
        before = self.store.raw()
        data = state_from_raw(before)
        data['library']['entries'] = [color('new')]
        preview = self.preview(data)
        self.api.crash_key = KEYS['library']
        ident = str(uuid.uuid4())
        with self.assertRaises(SystemExit):
            self.store.handle(ident, {'operation': 'import', 'payload': {'previewId': preview['previewId']}})
        self.assertTrue(self.store.journal.exists())
        recovered = DataStore(self.api, self.temporary.name)
        recovered.recover()
        self.assertEqual(recovered.raw(), before)
        self.assertFalse(self.api.namespaces[RESULTS][ident]['ok'])

    def test_stale_preview_and_active_print_are_rejected(self):
        preview = self.preview(state_from_raw(self.store.raw()))
        self.api.namespaces['fluidd'][KEYS['library']]['revision'] = 'another-device'
        with self.assertRaisesRegex(ValueError, 'изменились'):
            self.store.handle(str(uuid.uuid4()), {'operation': 'import', 'payload': {'previewId': preview['previewId']}})
        self.api.idle = False
        with self.assertRaisesRegex(ValueError, 'свободном'):
            self.store.handle(str(uuid.uuid4()), {'operation': 'import', 'payload': {'previewId': preview['previewId']}})

    def test_duplicate_ids_and_future_version_rejected(self):
        data = state_from_raw(self.store.raw())
        value = document(data)
        value['version'] = 999
        with self.assertRaises(ValueError):
            parse_document(value)
        data['library']['entries'].append(color())
        with self.assertRaises(ValueError):
            document(data)

    def test_existing_snapshot_survives_primary_database_loss(self):
        self.api.namespaces['fluidd'] = {}
        recovered = DataStore(self.api, self.temporary.name)
        recovered.recover()
        copies = list(Path(self.temporary.name).glob('*before-change*.json'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(json.loads(copies[0].read_text())['data']['library']['entries'][0], color())

    def calibration_fixture(self):
        raw = self.api.namespaces['fluidd']
        inventory = raw[KEYS['inventory']]
        inventory['cores'] = [{'id': 'core', 'name': 'Plastic', 'kind': 'Пластик', 'grams': 150}]
        inventory['spools'] = [{**color(ident), 'colorId': 'color', 'coreId': 'core', 'coreName': 'Plastic', 'grams': 1000, 'tare': 150} for ident in ('spool-a', 'spool-b')]
        inventory['heads'] = ['spool-a', None, None, None]
        return raw

    def save_calibration(self, individual, value):
        state = state_from_raw(self.store.raw())
        return self.store.handle(str(uuid.uuid4()), {'operation': 'calibration', 'payload': {
            'kind': 'spool', 'id': 'spool-a', 'individual': individual, 'value': value,
            'libraryRevision': state['library']['revision'], 'inventoryRevision': state['inventory']['revision']}})

    def test_calibration_modes_preserve_values_and_physical_spool_identity(self):
        self.calibration_fixture()
        common = {'pressureAdvance': 0.024, 'flowRatio': 0.98, 'date': '2026-11-07', 'method': 'Вручную'}
        own = {**common, 'pressureAdvance': 0, 'flowRatio': 1.02}
        self.save_calibration(False, common)
        self.save_calibration(True, own)
        self.save_calibration(False, common)
        data = state_from_raw(self.store.raw())
        self.assertEqual(data['library']['entries'][0]['calibration'], common)
        self.assertEqual(data['inventory']['spools'][0]['calibration'], own)
        self.assertNotIn('calibration', data['inventory']['spools'][1])
        self.assertFalse(data['inventory']['individualCalibration'])
        self.assertEqual(data['inventory']['heads'], ['spool-a', None, None, None])
        exported = self.store.handle(str(uuid.uuid4()), {'operation': 'export'})['document']
        self.assertEqual(parse_document(exported), data)
        merged, _ = merge_data(data, parse_document(exported))
        self.assertEqual(merged, data)
        # Exact restore into a separate fake device, without writing the real printer.
        preview = self.preview(data)
        self.store.handle(str(uuid.uuid4()), {'operation': 'import', 'payload': {'previewId': preview['previewId']}})
        restored = state_from_raw(self.store.raw())
        self.assertEqual(restored['inventory']['spools'], data['inventory']['spools'])
        self.assertEqual(restored['library']['entries'], data['library']['entries'])

    def test_calibration_reset_preserves_other_scope_inventory_and_backup(self):
        self.calibration_fixture()
        common = {'pressureAdvance': 0.024, 'date': '2026-11-07', 'method': 'U1'}
        own = {**common, 'pressureAdvance': 0.031}
        self.save_calibration(False, common)
        self.save_calibration(True, own)
        before = state_from_raw(self.store.raw())
        self.save_calibration(False, None)
        after = state_from_raw(self.store.raw())
        self.assertNotIn('calibration', after['library']['entries'][0])
        self.assertEqual(after['inventory']['spools'], before['inventory']['spools'])
        self.assertEqual(after['inventory']['heads'], before['inventory']['heads'])
        copies = list(self.store.folder.glob('*before-change*.json'))
        self.assertTrue(any(parse_document(json.loads(path.read_text(encoding='utf-8'))) == before for path in copies))
        self.save_calibration(False, common)
        self.save_calibration(True, None)
        after = state_from_raw(self.store.raw())
        self.assertEqual(after['library']['entries'][0]['calibration'], common)
        self.assertNotIn('calibration', after['inventory']['spools'][0])

    def test_spool_temperature_override_export_and_reset_do_not_change_base(self):
        self.calibration_fixture()
        current = state_from_raw(self.store.raw())
        before_color = copy.deepcopy(current['library'])
        inventory = current['inventory']
        inventory['spools'][0].update(nozzleTemperature=245, bedTemperature=70)
        self.store.handle(str(uuid.uuid4()), {'operation': 'inventory', 'payload': {'value': inventory}})
        saved = state_from_raw(self.store.raw())
        self.assertEqual(saved['library'], before_color)
        exported = self.store.handle(str(uuid.uuid4()), {'operation': 'export'})['document']
        self.assertEqual(parse_document(exported), saved)
        invalid = copy.deepcopy(saved['inventory'])
        invalid['spools'][0]['bedTemperature'] = 101
        with self.assertRaises(ValueError):
            self.store.handle(str(uuid.uuid4()), {'operation': 'inventory', 'payload': {'value': invalid}})
        self.assertEqual(state_from_raw(self.store.raw()), saved)
        inventory = saved['inventory']
        del inventory['spools'][0]['nozzleTemperature']
        del inventory['spools'][0]['bedTemperature']
        self.store.handle(str(uuid.uuid4()), {'operation': 'inventory', 'payload': {'value': inventory}})
        after = state_from_raw(self.store.raw())
        self.assertEqual(after['library'], before_color)
        self.assertNotIn('nozzleTemperature', after['inventory']['spools'][0])
        self.assertEqual(after['inventory']['heads'], current['inventory']['heads'])

    def test_temperature_profiles_round_trip_and_invalid_writes(self):
        current = state_from_raw(self.store.raw())
        library = current['library']
        library['entries'][0].update(nozzleTemperature=235, bedTemperature=60)
        self.store.handle(str(uuid.uuid4()), {'operation': 'library', 'payload': {'value': library}})
        saved = state_from_raw(self.store.raw())
        self.assertEqual(saved['library']['entries'][0]['nozzleTemperature'], 235)
        exported = self.store.handle(str(uuid.uuid4()), {'operation': 'export'})['document']
        self.assertEqual(parse_document(exported), saved)
        for field, value in [('nozzleTemperature', 0), ('nozzleTemperature', 301), ('nozzleTemperature', True),
                             ('bedTemperature', 101), ('bedTemperature', -1), ('bedTemperature', '60')]:
            bad = copy.deepcopy(saved['library'])
            bad['entries'][0][field] = value
            before = self.store.raw()
            with self.assertRaises(ValueError):
                self.store.handle(str(uuid.uuid4()), {'operation': 'library', 'payload': {'value': bad}})
            self.assertEqual(before, self.store.raw())

    def test_error_history_export_merge_restore_validation_and_totals(self):
        from u1_print_errors import ErrorMonitor
        job = {'job_id': '000001', 'filename': 'print.gcode', 'status': 'in_progress', 'start_time': 100}
        usage = copy.deepcopy(self.api.namespaces['fluidd'][KEYS['usage']])
        monitor = ErrorMonitor(None, None)
        monitor.add(usage, job, {'code': '0003-0523-0000-0006', 'message': 'test only', 'severity': 3}, 120,
                    [{'head': 0, 'spoolId': 'old-spool', 'colorId': 'old-color', 'name': 'Deleted spool', 'colorName': 'Deleted color', 'hex': '#112233'}])
        before_totals = copy.deepcopy(usage['totals'])
        self.store.commit_usage(usage)
        actual = state_from_raw(self.store.raw())
        exported = self.store.handle(str(uuid.uuid4()), {'operation': 'export'})['document']
        self.assertEqual(parse_document(exported), actual)
        merged, _ = merge_data(actual, parse_document(exported))
        self.assertEqual(len(merged['usage']['errors']), 1)
        self.assertEqual(merged['usage']['totals'], before_totals)
        for field, bad in [('severity', True), ('time', -1), ('id', 'duplicate?')]:
            document_bad = copy.deepcopy(exported)
            document_bad['data']['usage']['errors'][0][field] = bad
            with self.assertRaises(ValueError): parse_document(document_bad)
        preview = self.preview(actual)
        self.store.handle(str(uuid.uuid4()), {'operation': 'import', 'payload': {'previewId': preview['previewId']}})
        restored = state_from_raw(self.store.raw())
        self.assertEqual(restored['usage']['errors'], actual['usage']['errors'])
        self.assertEqual(restored['usage']['totals'], before_totals)

    def test_calibration_invalid_values_and_busy_printer_do_not_write(self):
        self.calibration_fixture()
        good = {'pressureAdvance': 0.024, 'date': '2026-11-07', 'method': 'U1'}
        before = self.store.raw()
        for bad in ({**good, 'pressureAdvance': -1}, {**good, 'pressureAdvance': True},
                    {**good, 'pressureAdvance': 1.1}, {**good, 'flowRatio': 0}, {**good, 'flowRatio': 100},
                    {**good, 'date': '2026-02-31'}, {**good, 'surprise': 1}):
            with self.assertRaises(ValueError):
                self.save_calibration(True, bad)
            self.assertEqual(self.store.raw(), before)
        self.api.idle = False
        with self.assertRaises(ValueError):
            self.save_calibration(False, good)
        self.assertEqual(self.store.raw(), before)

    def test_calibration_stale_revision_and_missing_base_do_not_write(self):
        self.calibration_fixture()
        before = self.store.raw()
        with self.assertRaises(ValueError):
            self.store.handle(str(uuid.uuid4()), {'operation': 'calibration', 'payload': {
                'kind': 'spool', 'id': 'spool-a', 'individual': True, 'value': None,
                'libraryRevision': 'stale', 'inventoryRevision': 'spools-old'}})
        self.assertEqual(self.store.raw(), before)
        self.api.namespaces['fluidd'][KEYS['inventory']]['spools'][0]['colorId'] = 'missing'
        with self.assertRaises(ValueError):
            self.save_calibration(False, None)

    def test_calibration_save_after_native_moves_ready_but_not_busy_machine(self):
        self.calibration_fixture()
        self.api.idle_state = 'Ready'
        value = {'pressureAdvance': 0.024, 'flowRatio': 0.98, 'date': '2026-11-07', 'method': 'U1'}
        self.save_calibration(False, value)
        self.api.machine_state = 4
        before = self.store.raw()
        with self.assertRaises(ValueError):
            self.save_calibration(False, value)
        self.assertEqual(before, self.store.raw())

    def test_merge_does_not_double_count_overlapping_history(self):
        current = state_from_raw(sample_raw())
        record = {'id': 'A', 'filename': 'part.gcode', 'time': 10, 'state': 'applied', 'status': 'completed', 'method': 'measured',
                  'rows': [{'head': 0, 'spoolId': 'spool', 'grams': 40}]}
        current['usage'] = {'totals': {'spool': 100}, 'records': [record]}
        incoming = copy.deepcopy(current)
        merged, _ = merge_data(current, incoming)
        self.assertEqual(merged['usage']['totals']['spool'], 100)
        self.assertEqual(len(merged['usage']['records']), 1)
        incoming['usage']['records'].append({**record, 'id': 'B'})
        incoming['usage']['totals']['spool'] = 80
        merged, _ = merge_data(current, incoming)
        self.assertEqual(merged['usage']['totals']['spool'], 100)


if __name__ == '__main__':
    unittest.main()
