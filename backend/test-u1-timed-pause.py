import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from u1_scheduler import TimedPause


class Tests(unittest.TestCase):
    def setUp(self):
        root=Path('local-backups/timed-pause-tests'); root.mkdir(parents=True,exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root); self.addCleanup(self.tmp.cleanup)
        self.now = 2000000000.; self.mono = 100.; self.calls = []
        self.s = {'webhooks':{'state':'ready'},'print_stats':{'state':'printing','filename':'a.gcode','exception':{}},
                  'machine_state_manager':{'main_state':'PRINTING','action_code':'IDLE'},
                  'exception_manager':{'exceptions':[]},'purifier':{'power_detected':True},
                  'pause_resume':{'is_paused':False},'virtual_sdcard':{'file_path':'/gcodes/a.gcode','file_position':100,'file_size':10000},
                  'toolhead':{'position':[0,0,10,2],'homed_axes':'xyz'},'heater_bed':{'temperature':65,'target':65}}
        self.h = {'job_id':'a','start_time':1000,'status':'in_progress','filename':'a.gcode'}
        self.store = SimpleNamespace(scheduler=SimpleNamespace(active=False),calibration_jobs=SimpleNamespace(active=False),
                                     dryer=SimpleNamespace(state=lambda:{'state':'idle'}))
        self.timer = self.new()

    def new(self):
        return TimedPause(self.api,Path(self.tmp.name)/'timer',self.control,lambda:self.now,lambda:self.mono)

    def api(self,path):
        if path.startswith('/printer/objects/query'): return {'status':copy.deepcopy(self.s)}
        if path.startswith('/server/history/list'): return {'jobs':[copy.deepcopy(self.h)]}
        raise AssertionError(path)

    def control(self,action):
        self.calls.append(action)
        self.s['print_stats']['state'] = 'paused' if action=='pause' else 'printing'
        self.s['pause_resume']['is_paused'] = action=='pause'
        return 'ok'

    def arm(self):
        plan = self.timer.prepare(self.store,{'minutes':1})
        return self.timer.arm(self.store,{'token':plan['token'],'confirmed':True})

    def advance(self,n):
        self.now += n; self.mono += n; self.timer.tick(self.store)

    def test_normal_one_shot_and_readback(self):
        self.assertEqual(self.arm()['state'],'armed'); self.assertEqual(self.calls,['pause'])
        self.advance(59); self.assertEqual(self.calls,['pause'])
        self.advance(2); self.assertEqual(self.calls,['pause','resume'])
        self.advance(2); self.assertEqual(self.timer.job['state'],'resumed')
        self.advance(300); self.assertEqual(self.calls,['pause','resume'])

    def test_existing_pause_does_not_pause_again(self):
        self.control('pause'); self.calls=[]; self.arm(); self.assertEqual(self.calls,[])

    def test_magnet_insertion_blocks_timer_but_keeps_manual_resume(self):
        import json
        self.control('pause'); self.calls=[]
        folder=Path(self.tmp.name)/'magnet-pauses'; folder.mkdir()
        (folder/'state.json').write_text(json.dumps({'requiresManualResume':True}))
        self.assertTrue(self.timer.player_state()['canResume'])
        with self.assertRaises(ValueError): self.timer.prepare(self.store,{'minutes':1})
        self.assertEqual(self.calls,[])

    def test_magnet_insertion_prevents_an_already_armed_timer_resuming(self):
        import json
        self.arm()
        folder=Path(self.tmp.name)/'magnet-pauses'; folder.mkdir()
        (folder/'state.json').write_text(json.dumps({'requiresManualResume':True}))
        self.advance(61)
        self.assertEqual(self.calls,['pause'])

    def test_cancel_keeps_print_paused(self):
        job=self.arm(); self.timer.cancel({'id':job['id']}); self.advance(60)
        self.assertEqual(self.calls,['pause']); self.assertEqual(self.s['print_stats']['state'],'paused')

    def test_restart_never_resumes(self):
        self.arm(); self.timer=self.new(); self.advance(60)
        self.assertEqual(self.timer.job['state'],'needs_review'); self.assertEqual(self.calls,['pause'])

    def test_expired_or_replayed_plan(self):
        p=self.timer.prepare(self.store,{'minutes':1}); self.now+=31; self.mono+=31
        with self.assertRaises(ValueError): self.timer.arm(self.store,{'token':p['token'],'confirmed':True})
        self.assertEqual(self.calls,[])

    def test_consent_and_input(self):
        for v in [0,1441,True,'1',float('nan')]:
            with self.assertRaises(ValueError):self.timer.prepare(self.store,{'minutes':v})
        p=self.timer.prepare(self.store,{'minutes':1})
        with self.assertRaises(ValueError):self.timer.arm(self.store,{'token':p['token']})
        self.assertEqual(self.calls,[])

    def test_job_changes_before_arm(self):
        p=self.timer.prepare(self.store,{'minutes':1}); self.h['start_time']+=1
        with self.assertRaises(ValueError):self.timer.arm(self.store,{'token':p['token'],'confirmed':True})
        self.assertEqual(self.calls,[])

    def test_protection_changes_block_resume(self):
        changes=[('print_stats','state','cancelled'),('webhooks','state','shutdown'),
                 ('purifier','power_detected',False),('exception_manager','exceptions',['fault']),
                 ('pause_resume','is_paused',False),('toolhead','homed_axes','xy'),
                 ('toolhead','position',[1,0,10,2]),('heater_bed','target',0),
                 ('heater_bed','temperature',40),('virtual_sdcard','file_position',101),
                 ('machine_state_manager','action_code','TOOL_CHANGE')]
        for obj,key,value in changes:
            with self.subTest(obj=obj,key=key):
                before=copy.deepcopy(self.s); self.arm(); self.s[obj][key]=value; self.advance(60)
                self.assertEqual(self.timer.job['state'],'blocked'); self.assertNotIn('resume',self.calls)
                self.s=before; self.calls=[]

    def test_new_job_same_filename_blocks(self):
        self.arm(); self.h['job_id']='b'; self.advance(60); self.assertEqual(self.timer.job['state'],'blocked')

    def test_time_jump_blocks(self):
        self.arm(); self.now+=60; self.timer.tick(self.store)
        self.assertEqual(self.timer.job['state'],'needs_review'); self.assertEqual(self.calls,['pause'])

    def test_missed_deadline_blocks(self):
        self.arm(); self.advance(80); self.assertEqual(self.timer.job['state'],'blocked')

    def test_uncertain_pause_never_retries(self):
        def fail(action):self.calls.append(action);raise TimeoutError()
        self.timer.control=fail; self.arm(); self.advance(60)
        self.assertEqual(self.calls,['pause']); self.assertEqual(self.timer.job['state'],'needs_review')

    def test_uncertain_resume_never_retries(self):
        self.arm()
        def fail(action):self.calls.append(action);raise TimeoutError()
        self.timer.control=fail; self.advance(60); self.advance(2)
        self.assertEqual(self.calls,['pause','resume']); self.assertEqual(self.timer.job['state'],'blocked')

    def test_pause_not_confirmed_never_arms(self):
        self.timer.control=lambda action:self.calls.append(action)
        self.arm(); self.advance(46); self.assertEqual(self.timer.job['state'],'blocked')

    def test_initial_idle_has_no_effect(self):
        self.s['print_stats']['state']='complete'
        self.assertFalse(self.timer.state()['eligible']); self.timer.tick(self.store); self.assertEqual(self.calls,[])

    def test_wrong_cancel_id(self):
        self.arm()
        with self.assertRaises(ValueError):self.timer.cancel({'id':'other'})

    def test_real_u1_json_numeric_printing_state(self):
        import json
        self.s['machine_state_manager']=json.loads('{"main_state":1,"action_code":0}')
        self.control('pause');self.calls=[]
        self.assertTrue(self.timer.state()['eligible'])
        self.assertEqual(self.arm()['state'],'armed')
        self.advance(60);self.assertEqual(self.calls,['resume'])

    def test_other_machine_states_are_not_printing(self):
        for value in [0,2,3,4,7,True,'1']:
            self.s['machine_state_manager']['main_state']=value
            self.assertFalse(self.timer.state()['eligible'],repr(value))

    def test_player_controls_follow_pause_state(self):
        self.s['machine_state_manager']['main_state']=1
        state=self.timer.player_state();self.assertTrue(state['canPause']);self.assertFalse(state['canResume'])
        self.control('pause')
        state=self.timer.player_state();self.assertTrue(state['canResume']);self.assertFalse(state['canPause'])

    def test_manual_resume_disarms_timer(self):
        self.arm();identity=self.timer.player_state()['currentJob']
        self.timer.player_action('resume-request',{'action':'resume','currentJob':identity,'confirmed':True})
        self.advance(60);self.assertEqual(self.calls,['pause','resume']);self.assertEqual(self.timer.job['state'],'cancelled')

    def test_unknown_command_reply_is_not_replayed_after_restart(self):
        identity=self.timer.player_state()['currentJob']
        def fail(action):self.calls.append(action);raise TimeoutError()
        self.timer.control=fail
        p={'action':'pause','currentJob':identity}
        self.timer.player_action('one-request',p)
        self.timer=self.new();self.timer.player_action('one-request',p)
        self.assertEqual(self.calls,['pause'])

    def test_cancel_is_available_with_cover_fault_but_resume_is_not(self):
        self.control('pause');self.calls=[];identity=self.timer.player_state()['currentJob']
        self.s['purifier']['power_detected']=False;self.s['exception_manager']['exceptions']=['cover']
        state=self.timer.player_state();self.assertTrue(state['canCancel']);self.assertFalse(state['canResume'])
        self.timer.player_action('cancel-request',{'action':'cancel','currentJob':identity,'confirmed':True})
        self.assertEqual(self.calls,['cancel'])

    def test_player_rejects_different_job_and_missing_consent(self):
        identity=self.timer.player_state()['currentJob']
        for payload in [{'action':'pause','currentJob':'different'},{'action':'cancel','currentJob':identity}]:
            with self.assertRaises(ValueError):self.timer.player_action('bad-request',payload)
        self.assertEqual(self.calls,[])


class DryerNotifications(unittest.TestCase):
    def test_persists_choice_and_requires_live_connection_for_enable(self):
        from unittest.mock import patch
        from u1_dryer_service import Dryer
        root=Path('local-backups/timed-pause-tests');root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            d=Dryer(lambda path:{'status':{'u1_dryer':{'state':'idle'}}},folder)
            with patch('u1_alexa.state',return_value={'phase':'offline'}):
                self.assertFalse(d.configure_notifications({'enabled':False})['alexaNotifications'])
                with self.assertRaises(ValueError):d.configure_notifications({'enabled':True})
            with patch('u1_alexa.state',return_value={'phase':'connected','config':{'enabled':True,'targets':['one'],'confirmed':['one']}}):
                self.assertTrue(d.configure_notifications({'enabled':True})['alexaNotifications'])
                self.assertTrue(Dryer(lambda path:{'status':{'u1_dryer':{'state':'idle'}}},folder).notifications())
                with self.assertRaises(ValueError):d.configure_notifications({'enabled':'yes'})

class BedAcknowledgementTests(unittest.TestCase):
    new, api, control = Tests.new, Tests.api, Tests.control

    def setUp(self):
        Tests.setUp(self)
        self.timer.stock_bed_ack_supported = lambda: True
        self.s['print_stats'].update(state='paused', exception={'id':532,'index':0,'code':1,'message':'detected dirty bed','level':2},
                                     info={'current_layer':0}, filament_used=0, print_duration=0)
        self.s['pause_resume']['is_paused'] = True
        self.s['toolhead']['homed_axes'] = 'xy'

    def test_manual_ack_visible_but_automatic_resume_stays_blocked(self):
        state = self.timer.player_state()
        self.assertTrue(state['canAcknowledgeBed'])
        self.assertFalse(state['canResume'])
        self.assertFalse(self.timer.state()['eligible'])
        self.assertEqual(self.calls, [])

    def test_ack_requires_confirmation_and_current_job(self):
        _, identity = self.timer.snapshot(False)
        for payload in ({'action':'ack_bed','currentJob':identity}, {'action':'ack_bed','currentJob':'old','confirmed':True}):
            with self.assertRaises(ValueError): self.timer.player_action('bad',payload)
        self.assertEqual(self.calls, [])
        self.timer.player_action('ack',{'action':'ack_bed','currentJob':identity,'confirmed':True})
        self.assertEqual(self.calls,['resume'])

    def test_ack_rejects_other_faults_later_layers_and_changed_firmware(self):
        baseline = copy.deepcopy(self.s)
        changes = [lambda: self.s['print_stats']['exception'].update(code=2),
                   lambda: self.s['print_stats']['info'].update(current_layer=1),
                   lambda: self.s['print_stats'].update(filament_used=1),
                   lambda: self.s['print_stats'].update(print_duration=1),
                   lambda: self.s['exception_manager'].update(exceptions=['fault']),
                   lambda: self.s['purifier'].update(power_detected=False),
                   lambda: self.s['toolhead'].update(homed_axes=''),
                   lambda: setattr(self.timer,'stock_bed_ack_supported',lambda: False)]
        for change in changes:
            self.s = copy.deepcopy(baseline); self.timer.stock_bed_ack_supported = lambda: True; change()
            state = self.timer.player_state()
            self.assertFalse(state['canAcknowledgeBed'])
            with self.assertRaises(ValueError): self.timer.player_action('no',{'action':'ack_bed','currentJob':state['currentJob'],'confirmed':True})
        self.assertEqual(self.calls, [])

class FilamentAck(unittest.TestCase):
    def setUp(self):
        Tests.setUp(self)
        self.timer.stock_bed_ack_supported=lambda:True
        self.s['print_stats'].update(state='paused',exception={'id':523,'index':0,'code':38,'message':'detect filament tangled!','level':2},print_duration=1179,filament_used=4939,info={'current_layer':34})
        self.s['pause_resume']['is_paused']=True

    new=Tests.new
    api=Tests.api
    control=Tests.control

    def test_manual_confirmation_only_with_same_job_and_fault(self):
        state=self.timer.player_state()
        self.assertTrue(state['canAcknowledgeFault']);self.assertFalse(state['canResume'])
        self.assertFalse(self.timer.state()['eligible']);self.assertEqual(self.calls,[])
        payload={'action':'ack_fault','currentJob':state['currentJob'],'faultToken':state['pauseFaultToken'],'confirmed':True}
        for bad in ({**payload,'confirmed':False},{**payload,'currentJob':'old'},{**payload,'faultToken':'old'}):
            with self.assertRaises(ValueError):self.timer.player_action('bad',bad)
        self.assertEqual(self.calls,[])
        self.timer.player_action('ok',payload);self.assertEqual(self.calls,['resume'])

    def test_other_errors_guards_changed_fault_and_firmware_stay_blocked(self):
        baseline=copy.deepcopy(self.s);initial=self.timer.player_state()
        changes=[lambda:self.s['print_stats']['exception'].update(code=39),lambda:self.s['print_stats']['exception'].update(level=3),
                 lambda:self.s['print_stats']['exception'].update(index=1),lambda:self.s['exception_manager'].update(exceptions=['other fault']),
                 lambda:self.s['purifier'].update(power_detected=False),lambda:self.s['toolhead'].update(homed_axes='xy'),
                 lambda:setattr(self.timer,'stock_bed_ack_supported',lambda:False)]
        for change in changes:
            self.s=copy.deepcopy(baseline);self.timer.stock_bed_ack_supported=lambda:True;change()
            with self.assertRaises(ValueError):self.timer.player_action('no',{'action':'ack_fault','currentJob':initial['currentJob'],'faultToken':initial['pauseFaultToken'],'confirmed':True})
        self.assertEqual(self.calls,[])

if __name__=='__main__': unittest.main()
