import copy
import datetime
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
import urllib.parse
import uuid
from u1_data_store import DataStore, document, parse_document, state_from_raw, merge_data
from u1_maintenance import KEY, Maintenance, view, totals, next_month, merge, validate
spec=importlib.util.spec_from_file_location('store_tests','test-u1-data-store.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)

def job(ident='01', seconds=120, status='completed', start=100):
    return {'job_id':ident,'start_time':start,'print_duration':seconds,'status':status,'filename':'test.gcode'}

class Api(fixtures.Api):
    def __init__(self):
        super().__init__();self.jobs=[job()];self.total=120;self.live={'filename':'test.gcode','print_duration':0,'state':'standby'}
    def __call__(self,path,payload=None,method=None):
        if path.startswith('/server/history/list'):
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(path).query);start=int(query['start'][0]);return {'jobs':copy.deepcopy(self.jobs[start:start+100])}
        if path=='/server/history/totals':return {'job_totals':{'total_print_time':self.total}}
        if path=='/printer/objects/query?print_stats':return {'status':{'print_stats':self.live.copy()}}
        return super().__call__(path,payload,method)

class Tests(unittest.TestCase):
    def setUp(self):
        folder=Path('local-backups/maintenance-tests');folder.mkdir(exist_ok=True,parents=True)
        self.temp=tempfile.TemporaryDirectory(dir=folder);self.addCleanup(self.temp.cleanup)
        self.api=Api();self.store=DataStore(self.api,self.temp.name);self.store.recover();self.m=self.store.maintenance
        self.m.poll(self.store,force=True)
    def data(self):return self.store.get('fluidd',KEY)
    def poll(self):self.m.poll(self.store,force=True);return self.data()
    def change(self,action,**extra):
        ident=str(uuid.uuid4());result=self.m.change(self.store,ident,{'revision':self.data()['revision'],'action':action,**extra});return result
    def test_bootstrap_preserves_native_total_and_unknown_dates(self):
        self.assertEqual(totals(self.data()),(120,1))
        self.assertTrue(view(self.data())['serviceDue']);self.assertTrue(view(self.data())['bedDue'])
        self.assertIsNone(self.data()['service'])
        self.api.total=1000;self.store.delete('fluidd',KEY);data=self.poll()
        self.assertEqual(totals(data)[0],1000)
    def test_pauses_idle_and_reboot_do_not_add_wall_time(self):
        self.api.jobs.insert(0,job('02',20,'in_progress',200));self.api.live.update(state='printing',print_duration=35)
        self.assertEqual(totals(self.poll())[0],155)
        self.api.live['state']='paused'
        self.assertEqual(totals(self.poll())[0],155)
        Maintenance(self.api).poll(self.store,force=True)
        self.assertEqual(totals(self.data())[0],155)
        self.api.live.update(state='printing',print_duration=45)
        self.assertEqual(totals(self.poll())[0],165)
        self.api.jobs[0].update(status='cancelled',print_duration=47);self.api.live['state']='standby'
        self.assertEqual(totals(self.poll()),(167,1))
    def test_repeated_history_and_counter_reset_do_not_duplicate(self):
        self.poll();self.poll();self.assertEqual(totals(self.data()),(120,1))
        self.api.total=0;self.api.jobs=[];self.assertEqual(totals(self.poll()),(120,1))
        self.api.jobs=[job('01',60,start=300)];self.assertEqual(totals(self.poll()),(180,2))
    def test_bootstrap_pagination_with_active_job(self):
        self.store.delete('fluidd',KEY)
        self.api.jobs=[job('FF',10,'in_progress',500)]+[job(format(n,'X'),1,start=n) for n in range(1,151)]
        self.api.total=150;self.api.live.update(state='paused',print_duration=20)
        self.assertEqual(totals(self.poll()),(170,150))
    def test_cancelled_time_and_completed_prints_are_distinct(self):
        self.api.jobs += [job('02',60,'cancelled',200),job('03',40,'error',300)]
        self.assertEqual(totals(self.poll()),(220,1))
    def test_independent_confirmations_preserve_total_and_history(self):
        self.change('service',confirmed=True);self.change('bed',confirmed=True)
        original=totals(self.data());self.api.jobs.insert(0,job('02',36001,start=200));state=view(self.poll())
        self.assertTrue(state['bedDue']);self.assertFalse(state['serviceDue'])
        self.change('bed',confirmed=True);state=view(self.data());self.assertFalse(state['bedDue']);self.assertEqual(state['bedPrints'],0)
        self.assertEqual(state['serviceSeconds'],36001);self.assertEqual(totals(self.data())[0],original[0]+36001)
        self.assertEqual(len(self.data()['history']),3)
    def test_five_completed_prints_and_toggle(self):
        self.change('bed',confirmed=True)
        self.api.jobs += [job(format(n,'X'),1,start=100+n) for n in range(2,7)]
        self.assertTrue(view(self.poll())['bedDue'])
        self.change('bed_enabled',enabled=False);self.assertFalse(view(self.data())['bedDue'])
        self.change('bed_enabled',enabled=True);self.assertTrue(view(self.data())['bedDue'])
    def test_service_hour_limit(self):
        self.change('service',confirmed=True)
        self.api.jobs.append(job('02',360000,start=200));self.assertTrue(view(self.poll())['serviceDue'])
    def test_calendar_month_handles_leap_year_and_end_of_month(self):
        date=lambda y,m,d:datetime.datetime(y,m,d,tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual(next_month(date(2028,1,31)),date(2028,2,29))
        self.assertEqual(next_month(date(2026,12,31)),date(2027,1,31))
        data=self.data();data['service']={'time':date(2028,1,31),'seconds':120,'completed':1}
        self.assertFalse(view(data,date(2028,2,28))['serviceDue']);self.assertTrue(view(data,date(2028,2,29))['serviceDue'])
    def test_confirmation_requires_idle_and_explicit_consent(self):
        with self.assertRaises(ValueError):self.change('service')
        self.api.idle=False
        with self.assertRaises(ValueError):self.change('service',confirmed=True)
        self.assertEqual(self.data()['history'],[])
    def test_bad_duration_preserves_saved_state(self):
        before=self.data();self.api.jobs[0]['print_duration']=None
        with self.assertRaises(ValueError):self.poll()
        self.assertEqual(self.data(),before);self.assertTrue(self.m.state(self.store)['message'])
    def test_export_import_merge_and_legacy_restore_preserve_counters(self):
        self.change('service',confirmed=True)
        current=state_from_raw(self.store.raw());parsed=parse_document(document(current));self.assertEqual(parsed['maintenance'],current['maintenance'])
        old=copy.deepcopy(current);old.pop('maintenance')
        preview=self.store.handle(str(uuid.uuid4()),{'operation':'preview','payload':{'mode':'replace','document':document(old)}})
        self.store.handle(str(uuid.uuid4()),{'operation':'import','payload':{'previewId':preview['previewId']}})
        self.assertEqual(totals(self.data()),(120,1));self.assertEqual(len(self.data()['history']),1)
        merged,_=merge_data(current,parsed);self.assertEqual(totals(merged['maintenance']),(120,1))
        self.assertEqual(len(merged['maintenance']['history']),1)
    def test_merge_never_loses_progress_or_later_confirmation(self):
        self.change('service',confirmed=True);old=self.data()
        self.api.jobs.append(job('02',50,start=200));new=self.poll()
        merged=merge(new,old);self.assertEqual(totals(merged),(170,2));self.assertEqual(merged['service'],old['service'])
    def test_calendar_month_keeps_local_date_across_dst(self):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: zone=ZoneInfo('Europe/Berlin')
        except ZoneInfoNotFoundError: self.skipTest('IANA tzdata unavailable on this host; required on U1')
        start=datetime.datetime(2026,3,31,0,30,tzinfo=zone).timestamp()
        expected=datetime.datetime(2026,4,30,0,30,tzinfo=zone).timestamp()
        self.assertEqual(next_month(start,'Europe/Berlin'),expected)
        self.change('service',confirmed=True,timeZone='Europe/Berlin')
        self.assertEqual(self.data()['service']['zone'],'Europe/Berlin')
    def test_normal_store_recovery_retains_counters_and_confirmations(self):
        self.change('service',confirmed=True);before=self.data()
        recovered=DataStore(self.api,self.temp.name);recovered.recover();recovered.maintenance.poll(recovered,force=True)
        self.assertEqual(recovered.get('fluidd',KEY),before)
    def test_initial_history_race_does_not_commit_inconsistent_baseline(self):
        self.store.delete('fluidd',KEY)
        original=self.api.__call__
        calls=[]
        def racing(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if path=='/server/history/totals':
                calls.append(path)
                if len(calls)==2:result['job_totals']['total_print_time']+=10
            return result
        with self.assertRaises(ValueError):Maintenance(racing).poll(self.store,force=True)
        self.assertIsNone(self.data())

    def test_stale_in_progress_job_is_not_assigned_current_print_time(self):
        self.api.jobs.insert(0,job('02',20,'in_progress',200))
        self.api.live.update(state='printing',print_duration=900,total_duration=1000)
        self.assertEqual(totals(self.poll())[0],140)

    def test_invalid_imports_rejected(self):
        bad=self.data();bad['jobs']['bad']={'seconds':float('nan'),'completed':False}
        with self.assertRaises(ValueError):validate(bad)
        bad=self.data();bad['bedEnabled']=1
        with self.assertRaises(ValueError):validate(bad)

if __name__=='__main__':unittest.main()
