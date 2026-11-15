"""Simulate U1 messages in temporary files. Never send printer commands."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from u1_print_errors import ErrorMonitor, ErrorStream, Inbox, normalize


class ErrorTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent / 'local-backups' / 'print-error-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.data = {'library': {'entries': [{'id': 'c', 'name': 'Blue', 'material': 'PLA', 'hex': '#112233'}]},
                     'inventory': {'heads': ['s', None, None, None], 'spools': [{'id': 's', 'colorId': 'c', 'name': 'Blue spool', 'material': 'PLA', 'hex': '#112233'}]}}
        self.job = {'job_id': '000001', 'filename': 'test.gcode', 'status': 'in_progress', 'start_time': 100, 'end_time': None}
        self.error = {'id': 523, 'index': 0, 'code': 6, 'level': 3, 'message': 'Nozzle fault', 'timestamp': 120}
        self.status = {'print_stats': {'filename': 'test.gcode', 'state': 'printing', 'message': '', 'exception': {}},
                       'print_task_config': {'extruders_used': [True, False, False, False], 'filament_type': ['PLA'] * 4, 'filament_color_rgba': ['112233FF'] * 4},
                       'exception_manager': {'exceptions': []}, 'webhooks': {'state': 'ready'}}
        self.usage = {'records': [], 'totals': {}, 'tracked': None}
        self.monitor = ErrorMonitor(self.api, self.item)
        (Path(self.tmp.name)/'current.json').write_text(json.dumps({'data': self.data}))
        self.stream = ErrorStream(self.tmp.name)
        self.stream.on_message({'id': 1, 'result': {'status': self.status}})
        self.stream.on_message({'id': 2, 'result': {'jobs': [self.job]}})

    def api(self, path):
        if path.startswith('/printer/objects/query'): return {'status': copy.deepcopy(self.status)}
        if path.startswith('/server/history/job?'): return {'job': copy.deepcopy(self.job)}
        if path.startswith('/server/history/list?'): return {'jobs': [copy.deepcopy(self.job)]}
        raise AssertionError(path)

    def item(self, key, default=None):
        if key == 'u1_spool_inventory_v1': return copy.deepcopy(self.data['inventory'])
        if key == 'u1_filament_library_v1': return copy.deepcopy(self.data['library'])
        return default

    def notification(self, **values):
        self.stream.on_message({'method': 'notify_exception_notification', 'params': [{**self.error, **values}]})

    def drain(self):
        ack = self.monitor.consume(self.usage, self.stream.inbox.peek(), 130)
        self.stream.inbox.ack(set(ack))

    def test_native_notification_and_cache_reconnect_are_one_record(self):
        self.notification()
        self.stream.on_message({'method': 'notify_exception_status', 'params': [{'exceptions': [self.error]}]})
        self.drain()
        self.notification()
        self.drain()
        self.assertEqual(len(self.usage['errors']), 1)
        row = self.usage['errors'][0]
        self.assertEqual(row['spools'][0]['spoolId'], 's')
        self.assertEqual(row['spools'][0]['colorId'], 'c')
        self.assertEqual(row['code'], '0003-0523-0000-0006')
        self.assertEqual(self.usage['totals'], {})

    def test_short_oneshot_is_saved_even_without_polling_active_error(self):
        self.notification()
        self.status['print_stats']['exception'] = {}
        self.drain()
        self.monitor.poll(self.usage, 130)
        self.assertEqual(len(self.usage['errors']), 1)

    def test_poll_first_then_exact_event_merges_sources(self):
        self.status['print_stats']['exception'] = self.error
        self.monitor.poll(self.usage, 121)
        self.assertEqual(self.usage['errors'][0]['source'], 'observed')
        self.notification()
        self.drain()
        self.assertEqual(len(self.usage['errors']), 1)
        self.assertEqual(self.usage['errors'][0]['time'], 120)
        self.assertEqual(self.usage['errors'][0]['source'], 'u1')
        self.monitor.poll(self.usage, 130)
        self.assertEqual(len(self.usage['errors']), 1)

    def test_restart_replays_durable_inbox_without_duplicates(self):
        self.notification()
        events = self.stream.inbox.peek()
        self.monitor.consume(self.usage, events, 130)
        # Simulate a crash after DB commit but before inbox acknowledgement.
        restored = json.loads(json.dumps(self.usage))
        inbox = Inbox(self.tmp.name)
        monitor = ErrorMonitor(self.api, self.item)
        ack = monitor.consume(restored, inbox.peek(), 135)
        inbox.ack(set(ack))
        self.assertEqual(len(restored['errors']), 1)
        self.assertEqual(inbox.peek(), [])

    def test_persistent_poll_is_deduplicated_across_restart(self):
        self.status['exception_manager']['exceptions'] = [self.error]
        self.monitor.poll(self.usage, 120)
        restored = json.loads(json.dumps(self.usage))
        ErrorMonitor(self.api, self.item).poll(restored, 125)
        self.assertEqual(len(restored['errors']), 1)

    def test_clear_then_recurrence_is_a_new_event(self):
        self.status['print_stats']['exception'] = self.error
        self.monitor.poll(self.usage, 120)
        self.status['print_stats']['exception'] = {}
        self.monitor.poll(self.usage, 125)
        self.status['print_stats']['exception'] = self.error
        self.monitor.poll(self.usage, 140)
        self.assertEqual(len(self.usage['errors']), 2)

    def test_two_real_native_raises_have_distinct_timestamps(self):
        self.notification()
        self.notification(timestamp=135)
        self.drain()
        self.assertEqual(len(self.usage['errors']), 2)

    def test_manual_pause_and_cancel_are_not_errors(self):
        self.status['print_stats']['state'] = 'paused'
        self.monitor.poll(self.usage, 120)
        self.job.update(status='cancelled', end_time=130)
        self.monitor.poll(self.usage, 131)
        self.assertEqual(self.usage.get('errors', []), [])

    def test_failed_job_without_message_has_one_honest_result_record(self):
        self.monitor.poll(self.usage, 110)
        self.job.update(status='error', end_time=140)
        self.status['print_stats']['state'] = 'error'
        self.monitor.poll(self.usage, 145)
        self.monitor.finish(self.usage, self.job, [], 150)
        self.assertEqual(len(self.usage['errors']), 1)
        self.assertEqual(self.usage['errors'][0]['source'], 'history')
        self.assertEqual(self.usage['totals'], {})

    def test_late_native_detail_replaces_generic_result_not_job_outcome(self):
        self.monitor.poll(self.usage, 110)
        self.job.update(status='error', end_time=140)
        self.monitor.poll(self.usage, 145)
        self.notification()
        self.drain()
        self.assertEqual(len(self.usage['errors']), 1)
        self.assertEqual(self.usage['errors'][0]['source'], 'u1')
        self.assertEqual(self.usage['errors'][0]['jobStatus'], 'error')

    def test_job_result_does_not_duplicate_native_error(self):
        self.notification()
        self.drain()
        self.job.update(status='klippy_shutdown', end_time=140)
        self.monitor.finish(self.usage, self.job, [], 140)
        self.assertEqual(len(self.usage['errors']), 1)
        self.assertEqual(self.usage['errors'][0]['jobStatus'], 'klippy_shutdown')

    def test_snapshots_survive_rename_color_edit_and_deletion(self):
        self.notification()
        self.data['inventory']['spools'].clear()
        self.data['library']['entries'].clear()
        self.drain()
        self.assertEqual(self.usage['errors'][0]['spools'][0]['name'], 'Blue spool')
        self.assertEqual(self.usage['errors'][0]['spools'][0]['colorName'], 'Blue')

    def test_wrong_spool_binding_is_not_attached(self):
        self.stream.status['print_task_config']['filament_type'][0] = 'ABS'
        self.notification()
        self.drain()
        self.assertEqual(self.usage['errors'][0]['spools'], [])

    def test_no_historical_backfill_with_current_spools(self):
        stream = ErrorStream(Path(self.tmp.name)/'second')
        stream.status = {'print_stats': {'state': 'standby'}}
        stream.set_job({**self.job, 'status': 'error', 'end_time': 140}, True)
        stream.native(self.error)
        self.assertEqual(stream.inbox.peek(), [])

    def test_old_cached_event_does_not_receive_current_spool_binding(self):
        self.stream.on_message({'id': 3, 'result': {'exceptions': [self.error]}})
        self.drain()
        self.assertEqual(len(self.usage['errors']), 1)
        self.assertEqual(self.usage['errors'][0]['spools'], [])

    def test_new_filename_before_history_notification_resolves_correct_job(self):
        self.job = {**self.job, 'job_id': '000002', 'filename': 'next.gcode'}
        self.stream.on_message({'method': 'notify_status_update', 'params': [{'print_stats': {'filename': 'next.gcode', 'state': 'printing'}}, 0]})
        self.notification()
        self.drain()
        self.assertEqual(self.usage['errors'][0]['jobId'], '000002')

    def test_missing_history_closes_watch_without_inventing_error(self):
        self.monitor.poll(self.usage, 110)
        original = self.monitor.api
        def missing(path):
            if path.startswith('/server/history/job?'): raise urllib.error.HTTPError(path, 404, 'missing', {}, None)
            return original(path)
        self.monitor.api = missing
        self.monitor.poll(self.usage, 120)
        self.assertIsNone(self.usage['_errorWatch']['job'])
        self.assertEqual(self.usage.get('errors', []), [])

    def test_shutdown_history_is_recorded_even_when_status_query_fails(self):
        self.monitor.poll(self.usage, 110)
        self.job.update(status='klippy_shutdown', end_time=140)
        original = self.monitor.api
        def disconnected(path):
            if path.startswith('/printer/objects/query'): raise urllib.error.HTTPError(path, 503, 'offline', {}, None)
            return original(path)
        self.monitor.api = disconnected
        self.monitor.poll(self.usage, 145)
        self.assertEqual(self.usage['errors'][0]['source'], 'history')

    def test_dropped_inbox_messages_are_visible_and_persisted(self):
        inbox = self.stream.inbox
        inbox.data['events'] = [{'inboxId': str(index)} for index in range(1000)]
        inbox.append({'kind': 'test'})
        restored = Inbox(self.tmp.name)
        self.assertEqual(restored.data['dropped'], 1)
        self.assertEqual(len(restored.peek()), 100)

    def test_encoded_error_and_untrusted_text_are_plain_data(self):
        value = normalize('{"coded":"0003-0523-0000-0006","msg":"<script>test</script>"}')
        self.assertEqual(value['code'], '0003-0523-0000-0006')
        self.assertEqual(value['message'], '<script>test</script>')


if __name__ == '__main__': unittest.main()
