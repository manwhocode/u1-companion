import copy,re,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
from u1_dryer_service import Dryer
from u1_dryer import DRYER_COMMAND_PREFIX

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.state={'state':'idle','commandVersion':2};self.calls=[];self.effect=True
  self.store=SimpleNamespace(calibration_jobs=SimpleNamespace(active=False),scheduler=SimpleNamespace(active=False),night=SimpleNamespace(data={'mode':'off'}))
  self.mock=patch('u1_alexa.state',return_value={});self.mock.start();self.addCleanup(self.mock.stop)
  self.service=Dryer(self.api,self.tmp.name,self.execute)
 def api(self,path):
  if path.startswith('/printer/objects/query'):return {'status':{'u1_dryer':copy.deepcopy(self.state)}}
  if path=='/server/job_queue/status':return {'queued_jobs':[],'queue_state':'ready'}
  raise AssertionError(path)
 def execute(self,script):
  self.calls.append(script)
  if self.effect:
   command=script.split()[0].removeprefix(DRYER_COMMAND_PREFIX)
   if command!='HEARTBEAT':self.state['state']={'START':'heating','RESUME':'heating','PAUSE':'paused','CANCEL':'cancelled'}[command]
  return 'ok'
 def start(self):return self.service.action(self.store,{'action':'start','confirmed':True,'temperature':50,'seconds':600,'limit':40})
 def test_start_uses_valid_command_and_reads_back_state(self):
  self.assertEqual(self.start()['state'],'heating')
  self.assertEqual(self.calls,['COMPANION_DRYER_START TEMP=50 SECONDS=600 LIMIT=40 CONFIRM=1'])
  parts=re.split('([A-Z_]+|[A-Z*])',self.calls[0]);self.assertEqual(''.join(parts[:3]).strip(),'COMPANION_DRYER_START')
 def test_old_module_cannot_receive_new_commands(self):
  self.state.pop('commandVersion')
  with self.assertRaises(ValueError):self.start()
  self.assertEqual(self.calls,[])
 def test_http_ok_without_state_change_is_failure(self):
  self.effect=False
  with self.assertRaises(ValueError):self.start()
  self.assertEqual(len(self.calls),1)
 def test_heartbeat_and_pause_cancel_commands_are_updated(self):
  self.start();self.service.heartbeat();self.assertEqual(self.calls[-1],'COMPANION_DRYER_HEARTBEAT')
  self.service.action(self.store,{'action':'pause'});self.assertEqual(self.state['state'],'paused')
  self.service.action(self.store,{'action':'cancel'});self.assertEqual(self.state['state'],'cancelled')
 def test_start_still_needs_consent_and_no_heating_is_attempted(self):
  with self.assertRaises(ValueError):self.service.action(self.store,{'action':'start'})
  self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
