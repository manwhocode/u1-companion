import io,json,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import u1_companion_info as m

class Updates(unittest.TestCase):
    def setUp(self):
        m._cache.clear();m._refreshing=False
        self.addCleanup(m._cache.clear)
        self.addCleanup(setattr,m,'_refreshing',False)

    def test_daily_cache_manual_check_bypasses_and_does_not_duplicate_worker(self):
        m._cache.update(latest='v0.1.1-alpha.12',checkedAt=time.time(),error=False)
        with patch.object(m.Path,'read_text',return_value=json.dumps({'version':'v0.1.1-alpha.11'})),patch.object(m.threading,'Thread') as thread:
            self.assertTrue(m.info()['updateAvailable']);thread.assert_not_called()
            self.assertTrue(m.info(force=True)['checking']);thread.assert_called_once()
            m.info(force=True);thread.assert_called_once()

    def test_expired_day_starts_background_worker(self):
        m._cache.update(latest='v0.1.1-alpha.11',checkedAt=time.time()-86401,error=False)
        with patch.object(m.Path,'read_text',return_value=json.dumps({'version':'v0.1.1-alpha.11'})),patch.object(m.threading,'Thread') as thread:
            self.assertTrue(m.info()['checking']);thread.assert_called_once()

    def test_failed_network_preserves_previous_update_and_reports_failure(self):
        m._cache.update(latest='v0.1.1-alpha.13',checkedAt=0,error=False);m._refreshing=True
        with patch.object(m.urllib.request,'urlopen',side_effect=OSError('offline')):m.refresh_version()
        self.assertEqual(m._cache['latest'],'v0.1.1-alpha.13');self.assertTrue(m._cache['error']);self.assertFalse(m._refreshing)

    def test_successful_worker_records_actual_release(self):
        m._refreshing=True
        with patch.object(m.urllib.request,'urlopen',return_value=io.BytesIO(b'#!/bin/sh\nVERSION=v0.1.1-alpha.13\n')):m.refresh_version()
        self.assertEqual(m._cache['latest'],'v0.1.1-alpha.13');self.assertFalse(m._cache['error']);self.assertFalse(m._refreshing)
