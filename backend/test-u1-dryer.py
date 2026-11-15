import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from u1_dryer import Session,U1Dryer,ACTIVE,validate
from u1_dryer_service import Dryer
class Core(unittest.TestCase):
 def setUp(self):self.s=Session();self.s.start(45,60,60,0)
 def test_bounds_and_nan(self):
  for v in [(81,60,60),(40,28801,60),(40,60,61),(float('nan'),60,60),(True,60,60)]:
   with self.assertRaises(ValueError):validate(*v)
 def test_timer_starts_after_warming(self):self.s.tick(5,30,25,target=45);self.assertEqual(self.s.remaining,60);self.s.tick(6,44,25,target=45);self.s.tick(7,44,25,target=45);self.assertEqual(self.s.remaining,59)
 def test_completion_switch_off_requested(self):
  self.s.tick(1,45,25);self.s.heartbeat(61);self.assertTrue(self.s.tick(61,45,25));self.assertEqual(self.s.state,'completed')
 def test_service_watchdog(self):self.assertTrue(self.s.tick(36,45,25));self.assertEqual(self.s.state,'paused')
 def test_threshold_switch_off_and_hysteresis(self):
  self.assertTrue(self.s.tick(1,45,60));self.assertEqual(self.s.state,'paused')
  with self.assertRaises(ValueError):self.s.resume(58,2)
  self.s.resume(56,2);self.assertEqual(self.s.state,'heating')
 def test_paused_timer_does_not_run(self):self.s.pause('user');self.s.heartbeat(20);self.s.tick(20,40,30);self.assertEqual(self.s.remaining,60)
 def test_changed_target_is_not_reapplied(self):self.assertTrue(self.s.tick(1,40,25,target=0));self.assertEqual(self.s.state,'paused')
 def test_bad_machine_stops(self):self.assertTrue(self.s.tick(1,40,25,reason='sensor fault'));self.assertEqual(self.s.message,'sensor fault')
 def test_absolute_eight_hour_limit(self):self.s.heartbeat(28800);self.s.tick(28800,30,25);self.assertEqual(self.s.state,'completed')
 def test_resume_after_deadline_denied(self):
  self.s.pause('user')
  with self.assertRaises(ValueError):self.s.resume(20,28801)
 def test_cooling_stops_countdown(self):self.s.tick(1,45,25);self.s.tick(2,35,25);self.assertEqual(self.s.state,'heating');self.assertEqual(self.s.remaining,60)

class Module(unittest.TestCase):
 def setUp(self):
  root=Path('local-backups/dryer-tests');root.mkdir(parents=True,exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.tmp.cleanup)
  self.now=10.;self.bedtemp=30.;self.target=0.;self.chambertemp=25.;self.commands=[];self.targets=[]
  self.d=U1Dryer.__new__(U1Dryer);d=self.d;d.session=Session();d.reactor=SimpleNamespace(monotonic=lambda:self.now);d.file=Path(self.tmp.name)/'state.json';d.original_timeout=None;d.heat_started=0;d.last_saved=0;d.last_chamber_sample=10
  d.bed_read=d.chamber_read=None;d.bed=SimpleNamespace(get_status=lambda now:{'temperature':self.bedtemp,'target':self.target},get_temp=lambda now:(self.bedtemp,self.target));d.chamber=SimpleNamespace(get_status=lambda now:{'temperature':self.chambertemp})
  self.statuses={'print_stats':{'state':'standby'},'machine_state_manager':{'main_state':0,'action_code':0},'exception_manager':{'exceptions':[]},'purifier':{'power_detected':True},**{n:{'target':0} for n in ('extruder','extruder1','extruder2','extruder3')}}
  d.status=lambda name:self.statuses[name]
  def heat(heater,target,wait):self.targets.append(target);self.target=target
  self.idle=SimpleNamespace(idle_timeout=600)
  d.gcode=SimpleNamespace(run_script_from_command=self.commands.append)
  d.printer=SimpleNamespace(lookup_object=lambda name:SimpleNamespace(set_temperature=heat) if name=='heaters' else self.idle,command_error=ValueError,invoke_shutdown=lambda reason:self.fail(reason))
  self.cmd=SimpleNamespace(get_int=lambda key,default=0:1,get_float=lambda key,default=None:{'TEMP':45,'SECONDS':60,'LIMIT':60}.get(key,default),error=ValueError)
 def test_start_pause_cancel_restore_timeout(self):
  self.d.start(self.cmd);self.assertEqual(self.targets[-1],45);self.d.pause(self.cmd);self.assertEqual(self.targets[-1],0);self.assertIn('SET_IDLE_TIMEOUT TIMEOUT=600',self.commands);self.d.cancel(self.cmd);self.assertEqual(self.d.session.state,'cancelled')
 def test_resume_heats_only_after_validation(self):
  self.d.start(self.cmd);self.d.pause(self.cmd);self.chambertemp=59
  with self.assertRaises(ValueError):self.d.resume(self.cmd)
  self.assertEqual(self.target,0)
 def test_cover_loss_switches_off(self):
  self.d.start(self.cmd);self.statuses['purifier']['power_detected']=False;self.d.poll(11);self.assertEqual(self.target,0);self.assertEqual(self.d.session.state,'paused')
 def test_sensor_stale_switches_off(self):self.d.start(self.cmd);self.now=20;self.d.poll(20);self.assertEqual(self.target,0)
 def test_chamber_limit_switches_off(self):self.d.start(self.cmd);self.chambertemp=60;self.d.poll(11);self.assertEqual(self.target,0)
 def test_service_loss_switches_off(self):self.d.start(self.cmd);self.now=50;self.d.last_chamber_sample=50;self.d.poll(50);self.assertEqual(self.target,0)
 def test_print_interlock(self):
  self.d.start(self.cmd)
  with self.assertRaises(ValueError):self.d.check_print()
  self.d.session.state='interrupted'
  with self.assertRaises(ValueError):self.d.check_print()
  self.d.cancel(self.cmd);self.d.check_print()
 def test_shutdown_no_restart(self):self.d.start(self.cmd);self.d.shutdown();self.assertEqual(json.loads(self.d.file.read_text())['state'],'interrupted')
 def test_other_heat_and_busy_rejected(self):
  self.statuses['extruder']['target']=100
  with self.assertRaises(ValueError):self.d.start(self.cmd)
  self.assertEqual(self.targets,[])
 def test_failed_off_invokes_shutdown(self):
  self.d.start(self.cmd);self.statuses['purifier']['power_detected']=False;self.d.stop_heat=Mock(side_effect=OSError('heater fail'));shutdown=Mock();self.d.printer.invoke_shutdown=shutdown;self.d.poll(11);shutdown.assert_called_once()
 def test_no_movement_or_hotend_command(self):self.d.start(self.cmd);self.d.pause(self.cmd);self.assertTrue(all(x.startswith('SET_IDLE_TIMEOUT') for x in self.commands))
 def test_no_consent_denies(self):
  self.cmd.get_int=lambda *args:0
  with self.assertRaises(ValueError):self.d.start(self.cmd)
  self.assertEqual(self.targets,[])
 def test_profile_validation_and_saved_values(self):
  service=Dryer(lambda p:{},self.tmp.name);v=service.change({'revision':'','key':'material:PLA','temperature':40,'seconds':3600,'limit':45});self.assertEqual(v['entries']['material:PLA']['temperature'],40)
  with self.assertRaises(ValueError):service.change({'revision':v['revision'],'key':'bad\nM112'})
 def test_service_refuses_schedule_and_night(self):
  service=Dryer(lambda p:{},self.tmp.name,lambda s:self.fail(s));store=SimpleNamespace(calibration_jobs=SimpleNamespace(active=False),scheduler=SimpleNamespace(active=True),night=SimpleNamespace(data={'mode':'off'}))
  with self.assertRaises(ValueError):service.action(store,{'action':'start','confirmed':True})
  store.scheduler.active=False;store.night.data['mode']='on'
  with self.assertRaises(ValueError):service.action(store,{'action':'resume','confirmed':True})

class Wiring(unittest.TestCase):
 def test_original_print_handler_only_called_when_dryer_is_clear(self):
  from types import SimpleNamespace
  root=Path('local-backups/dryer-tests');root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=root) as folder:
   d=U1Dryer.__new__(U1Dryer);d.file=Path(folder)/'state.json';d.session=Session();d.reactor=SimpleNamespace(monotonic=lambda:0,register_timer=lambda *a:None,NOW=0)
   d.last_chamber_sample=0;d.bed_read=d.chamber_read=None
   called=[];handlers={n:(lambda g,n=n:called.append(n)) for n in ('M24','SDCARD_PRINT_PL_RESTORE','SDCARD_PRINT_FILE','SDCARD_PRINT_FILE_WITH_PARAMETERS')}
   def register(name,handler):old=handlers.get(name);handlers[name]=handler;return old
   d.gcode=SimpleNamespace(register_command=register);vsd=SimpleNamespace(do_resume=lambda:called.append('resume'))
   sensor=SimpleNamespace(get_status=lambda t:{'temperature':25},temperature_callback=lambda t,v:None,sensor=SimpleNamespace(setup_callback=lambda cb:None))
   objects={'heater_bed':SimpleNamespace(heater=SimpleNamespace(get_temp=lambda t:(25,0))),'temperature_sensor cavity':sensor,'virtual_sdcard':vsd}
   d.sensor_name='cavity';d.printer=SimpleNamespace(lookup_object=lambda n:objects[n],command_error=ValueError)
   d.ready();d.session.state='paused'
   for handler in handlers.values():
    with self.assertRaises(ValueError):handler(None)
   with self.assertRaises(ValueError):vsd.do_resume()
   self.assertEqual(called,[])
   d.session.state='idle';handlers['M24'](None);self.assertEqual(called,['M24'])

if __name__=='__main__':unittest.main()
