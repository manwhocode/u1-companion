import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from u1_night_mode import NightMode,in_window
class Tests(unittest.TestCase):
 def setUp(self):
  root=Path('local-backups/night-tests');root.mkdir(exist_ok=True,parents=True);self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
  self.p={'mode':1,'power_detected':True,'desired_chamber_temp':42,'critical_chamber_temp':45,'exhaust_fan':{'speed_threshold':.6}}
  self.s={'webhooks':{'state':'ready'},'purifier':self.p,'exception_manager':{'exceptions':[]}}
  self.tempvalue=30;self.calls=[];self.store=SimpleNamespace(calibration_jobs=SimpleNamespace(active=False))
  self.n=NightMode(self.api,self.temp.name,self.execute)
 def api(self,path):
  if 'configfile' in path:return {'status':{'configfile':{'settings':{'purifier':{'external_temp_sensor':'chamber'}}}}}
  if 'temperature_sensor' in path:return {'status':{'temperature_sensor chamber':{'temperature':self.tempvalue}}}
  return {'status':copy.deepcopy(self.s)}
 def execute(self,script):
  self.calls.append(script);self.p['exhaust_fan']['speed_threshold']=0 if 'FAN_SPEED=0 ' in script else .6
 def configure(self,mode):return self.n.configure({'revision':self.n.data['revision'],'mode':mode,'start':'22:00','end':'07:00','zone':'UTC'})
 def tick(self):self.n.tick(self.store,True)
 def test_default_off_no_commands(self):self.tick();self.assertEqual(self.calls,[])
 def test_once_cool_mode_and_restore(self):
  self.configure('on');self.tick();self.tick();self.assertEqual(len(self.calls),1);self.assertIn('DYNAMIC_FAN_CONTROL=1',self.calls[0]);self.assertIn('ALARM_TEMP=45',self.calls[0]);self.configure('off');self.tick();self.assertIn('FAN_SPEED=0.6',self.calls[-1]);self.assertIsNone(self.n.data['saved'])
 def test_hot_preheat_idle_untouched(self):
  self.configure('on')
  for mode in (0,2,3):self.p['mode']=mode;self.tick()
  self.assertEqual(self.calls,[])
 def test_hot_chamber_restores_stock_minimum(self):
  self.configure('on');self.tick();self.tempvalue=42;self.tick();self.assertIn('FAN_SPEED=0.6',self.calls[-1])
 def test_bad_sensor_restores(self):
  self.configure('on');self.tick();self.tempvalue=None;self.tick();self.assertIsNone(self.n.data['saved']);self.assertIn('датчик',self.n.data['message'])
 def test_native_new_mode_wins(self):
  self.configure('on');self.tick();self.p['mode']=3;self.tick();self.assertEqual(len(self.calls),1);self.assertIsNone(self.n.data['saved'])
 def test_cover_error_calibration_cannot_turn_off_fans(self):
  self.configure('on');self.s['exception_manager']['exceptions']=[{}];self.tick();self.assertEqual(self.calls,[])
  self.s['exception_manager']['exceptions']=[];self.p['power_detected']=False;self.tick();self.assertEqual(self.calls,[])
  self.p['power_detected']=True;self.store.calibration_jobs.active=True;self.tick();self.assertEqual(self.calls,[])
 def test_restart_restoration_persists(self):
  self.configure('on');self.tick();self.n=NightMode(self.api,self.temp.name,self.execute);self.configure('off');self.tick();self.assertIn('FAN_SPEED=0.6',self.calls[-1])
 def test_midnight_and_daytime_windows(self):
  self.assertTrue(in_window('22:00','07:00',23*60));self.assertTrue(in_window('22:00','07:00',0));self.assertFalse(in_window('22:00','07:00',7*60));self.assertTrue(in_window('09:00','17:00',10*60));self.assertFalse(in_window('09:00','17:00',20*60))
 def test_stale_revision_and_invalid_times(self):
  with self.assertRaises(ValueError):self.n.configure({'revision':'wrong'})
  with self.assertRaises(ValueError):self.n.configure({'revision':self.n.data['revision'],'mode':'on','start':'25:00','end':'07:00','zone':'UTC'})
 def test_no_other_fan_commands(self):
  self.configure('on');self.tick();self.configure('off');self.tick();self.assertTrue(all(x.startswith('SET_PURIFIER_MODE MODE=1') for x in self.calls))
if __name__=='__main__':unittest.main()
