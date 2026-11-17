"""Transient network failures must not erase authorized external-access setup."""
import importlib.util,json,sys,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'backend'))
spec=importlib.util.spec_from_file_location('remote_supervisor',REPO/'backend/u1-remote-manager.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Process:
 def __init__(self,code=None):self.code=code
 def poll(self):return self.code
 def terminate(self):self.code=0
 def wait(self,timeout):return self.code

class Reconnect(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'control.key').write_text('fixture-control-key')
  (self.root/'config.json').write_text(json.dumps({'authMode':'code','enabled':True}))
  self.manager=m.Manager(self.root);self.manager.auth.rotate();self.now=100
  self.clock=patch.object(m.time,'monotonic',lambda:self.now);self.clock.start();self.addCleanup(self.clock.stop)
 def test_boot_failure_preserves_enabled_choice_and_recovers_after_delay(self):
  manager=self.manager
  def recovered():manager.proc=Process();manager.phase='starting'
  attempts=[]
  def attempt():
   attempts.append(True)
   if len(attempts)==1:raise urllib.error.URLError('network not ready')
   recovered()
  with patch.object(manager,'launch',side_effect=attempt) as launch:
   manager.restore();self.assertTrue(manager.config['enabled'])
   self.assertTrue(json.loads((self.root/'config.json').read_text())['enabled'])
   self.now=104;manager.tick();self.assertEqual(launch.call_count,1)
   self.now=105;manager.tick();self.assertEqual(launch.call_count,2)
  self.assertEqual(manager.phase,'starting');process=manager.proc
  manager.lines.put((process,'https://fixture-tunnel.trycloudflare.com'))
  manager.lines.put((process,'Registered tunnel connection'))
  manager.tick();self.assertEqual(manager.phase,'running');self.assertEqual(manager.retry_delay,5)
 def test_exit_retries_but_explicit_stop_cancels_reconnect(self):
  manager=self.manager;manager.proc=Process(1);manager.phase='running'
  manager.tick();self.assertTrue(manager.config['enabled']);self.assertGreater(manager.retry_at,self.now)
  manager.command({'action':'stop'});self.now+=1000
  with patch.object(manager,'launch') as launch:manager.tick();launch.assert_not_called()
  self.assertFalse(manager.config['enabled']);self.assertEqual(manager.retry_at,0)
 def test_security_failures_disable_without_retry(self):
  for error in ('gateway_not_protected','invalid_runtime','code_required'):
   with self.subTest(error=error),patch.object(self.manager,'launch',side_effect=ValueError(error)) as launch:
    self.manager.config['enabled']=True;self.manager.restore();self.now+=1000;self.manager.tick()
    self.assertFalse(self.manager.config['enabled']);self.assertEqual(self.manager.retry_at,0)
    self.assertEqual(launch.call_count,1)
 def test_network_backoff_is_bounded_and_does_not_spin(self):
  manager=self.manager;delays=[]
  with patch.object(manager,'launch',side_effect=urllib.error.URLError('offline')) as launch:
   manager.restore()
   for _ in range(8):
    delays.append(manager.retry_at-self.now)
    manager.tick();self.assertEqual(launch.call_count,len(delays))
    self.now=manager.retry_at;manager.tick()
  self.assertEqual(delays,[5,10,20,40,80,160,300,300])

if __name__=='__main__':unittest.main()
