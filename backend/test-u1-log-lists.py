import copy
import importlib.util
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from u1_data_store import DataStore, KEYS, document, parse_document, state_from_raw, merge_data
from u1_log_lists import visible, to_csv, cell

spec=importlib.util.spec_from_file_location('log_store_fixtures','test-u1-data-store.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=DataStore(f.Api(),self.tmp.name);self.store.recover()
        raw=self.store.raw();usage=raw[KEYS['usage']]
        usage['records']=[{'id':'ABC','filename':'model.gcode','status':'completed','time':time.time(),'rows':[{'spoolId':'spool-one','head':0,'grams':12}],'state':'applied','method':'measured'}]
        usage['totals']={'spool-one':12}
        usage['errors']=[{'id':'a'*64,'jobId':'ABC','filename':'model.gcode','time':time.time(),'source':'observed','code':'code','message':'message','severity':1,'jobStatus':'completed','spools':[]}]
        self.store.commit(raw)
    def call(self,operation,payload=None):return self.store.handle(str(uuid.uuid4()),{'operation':operation,'payload':payload or {}})
    def test_export_formats_are_independent_and_do_not_write_data(self):
        before=self.store.raw()
        for name in ('usage','errors'):
            result=self.call('logs_export',{'kind':name,'format':'json'})
            self.assertEqual(json.loads(result['content'])['kind'],name);self.assertEqual(result['count'],1)
            self.assertTrue(self.call('logs_export',{'kind':name,'format':'csv'})['content'].startswith('\ufeff'))
        self.assertEqual(before,self.store.raw())
    def test_clear_requires_confirmation_and_preserves_accounting_tracking_and_raw_records(self):
        before=copy.deepcopy(self.store.raw()[KEYS['usage']])
        plan=self.call('logs_prepare_clear',{'kind':'usage'})
        with self.assertRaises(ValueError):self.call('logs_clear',{'token':plan['token']})
        result=self.call('logs_clear',{'token':plan['token'],'confirmed':True})
        after=self.store.raw()[KEYS['usage']]
        for key in ('totals','records','errors'):self.assertEqual(after[key],before[key])
        self.assertEqual(visible(after,'usage'),[]);self.assertEqual(len(visible(after,'usage',True)),1)
        self.assertTrue(result['accountingPreserved']);self.assertTrue(result['backup'])
    def test_clear_errors_does_not_clear_runtime_exceptions_or_spending_log(self):
        plan=self.call('logs_prepare_clear',{'kind':'errors'})
        self.call('logs_clear',{'token':plan['token'],'confirmed':True})
        usage=self.store.raw()[KEYS['usage']]
        self.assertEqual(visible(usage,'errors'),[]);self.assertEqual(len(visible(usage,'usage')),1)
        self.assertEqual(usage['errors'][0]['id'],'a'*64)
    def test_new_events_after_preparation_remain_visible(self):
        plan=self.call('logs_prepare_clear',{'kind':'errors'})
        raw=self.store.raw();event=copy.deepcopy(raw[KEYS['usage']]['errors'][0]);event['id']='b'*64;raw[KEYS['usage']]['errors'].append(event);self.store.commit(raw)
        self.call('logs_clear',{'token':plan['token'],'confirmed':True})
        self.assertEqual([r['id'] for r in visible(self.store.raw()[KEYS['usage']],'errors')],['b'*64])
    def test_archives_survive_full_export_and_import_without_debiting_again(self):
        plan=self.call('logs_prepare_clear',{'kind':'usage'});self.call('logs_clear',{'token':plan['token'],'confirmed':True})
        data=state_from_raw(self.store.raw());restored=parse_document(document(data))
        self.assertEqual(restored['usage']['archivedRecords'],['ABC'])
        merged,_=merge_data(data,restored)
        self.assertEqual(merged['usage']['totals'],{'spool-one':12})
        self.assertEqual(merged['usage']['archivedRecords'],['ABC'])
    def test_current_export_empty_archive_export_complete(self):
        plan=self.call('logs_prepare_clear',{'kind':'errors'});self.call('logs_clear',{'token':plan['token'],'confirmed':True})
        self.assertEqual(self.call('logs_export',{'kind':'errors'})['count'],0)
        self.assertEqual(self.call('logs_export',{'kind':'errors','includeArchived':True})['count'],1)
    def test_unknown_formats_and_csv_formulas_are_not_accepted_as_executable_cells(self):
        with self.assertRaises(ValueError):self.call('logs_export',{'kind':'files','format':'json'})
        with self.assertRaises(ValueError):self.call('logs_export',{'kind':'usage','format':'html'})
        for value in ('=HYPERLINK("https://example.test")',' +SUM(1)','\t=1','\ufeff=1','@SUM(1)'):
            self.assertTrue(cell(value).startswith("'"))
        self.assertEqual(cell(12.5),12.5)


if __name__=='__main__':unittest.main()
