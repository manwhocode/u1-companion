import copy,json,tempfile,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from u1_magnet_service import MagnetService
from u1_magnet_pause import MAGNET_COMMANDS

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.module={'available':True,'commandVersion':2,'state':'idle','runtimeJob':'job','parked':False,'parkingState':None}
        self.stats={'state':'printing','filename':'sample.gcode','info':{'current_layer':3}}
        self.calls=[];self.effect='success';self.timer=[]
        self.store=SimpleNamespace(timed_pause=SimpleNamespace(active=False,update=lambda **v:self.timer.append(v)))
        self.service=MagnetService(self.api,self.tmp.name)
    def api(self,path,payload=None,**kwargs):
        if path.startswith('/printer/objects/query'):
            return {'status':{'u1_magnet_pause':copy.deepcopy(self.module),'print_stats':copy.deepcopy(self.stats)}}
        if path!='/printer/gcode/script':raise AssertionError(path)
        script=payload['script'];self.calls.append(script)
        if self.effect=='no_effect':return 'ok'
        if script.startswith(MAGNET_COMMANDS['pause']):
            self.stats['state']='paused'
            self.module.update(parked=self.effect!='no_parking',parkingState='parked' if self.effect!='no_parking' else None)
        elif script.startswith(MAGNET_COMMANDS['arm']):self.module.update(state='armed',token=script.split('TOKEN=')[1])
        elif script==MAGNET_COMMANDS['clear']:self.module['state']='cancelled'
        return 'ok'
    def pause(self,ident=None):
        return self.service.action(self.store,ident or str(uuid.uuid4()),{'action':'pause','job':'job','confirmed':True})
    def prepared(self):
        token=str(uuid.uuid4());Path(self.tmp.name,token+'-prepared.json').write_text(json.dumps({'createdAt':time.time()}));return token
    def test_pause_requires_readback_of_pause_and_completed_parking(self):
        result=self.pause();self.assertEqual(result['printState'],'paused');self.assertTrue(result['parked'])
        self.assertEqual(self.calls,['COMPANION_MAGNET_PAUSE CONFIRM=1'])
    def test_http_ok_without_execution_is_failure_and_no_retry(self):
        self.effect='no_effect';ident=str(uuid.uuid4())
        with self.assertRaises(ValueError):self.pause(ident)
        with self.assertRaises(FileExistsError):self.pause(ident)
        self.assertEqual(len(self.calls),1)
    def test_paused_but_not_parked_is_not_success(self):
        self.effect='no_parking'
        with self.assertRaises(ValueError):self.pause()
        self.assertEqual(len(self.calls),1)
    def test_old_module_rejected_before_any_command_or_reservation(self):
        self.module.pop('commandVersion')
        with self.assertRaises(ValueError):self.pause()
        self.assertEqual(self.calls,[]);self.assertEqual(list(Path(self.tmp.name).glob('*sent*')),[])
    def test_job_change_and_missing_consent_send_nothing(self):
        self.module['runtimeJob']='other'
        with self.assertRaises(ValueError):self.pause()
        with self.assertRaises(ValueError):self.service.action(self.store,str(uuid.uuid4()),{'action':'pause','job':'other'})
        self.assertEqual(self.calls,[])
    def test_arm_requires_matching_token_and_active_plan_readback(self):
        token=self.prepared();result=self.service.arm({'token':token,'confirmed':True})
        self.assertEqual(result['token'],token);self.assertEqual(result['state'],'armed')
    def test_unknown_arm_command_is_not_reported_as_saved(self):
        self.effect='no_effect';token=self.prepared()
        with self.assertRaises(ValueError):self.service.arm({'token':token,'confirmed':True})
        with self.assertRaises(FileExistsError):self.service.arm({'token':token,'confirmed':True})
        self.assertEqual(len(self.calls),1)
    def test_clear_keeps_print_paused_and_does_not_resume(self):
        self.stats['state']='paused';self.module.update(token='token',state='waiting_insertion')
        result=self.service.action(self.store,str(uuid.uuid4()),{'action':'clear','token':'token','confirmed':True})
        self.assertEqual(result['state'],'cancelled');self.assertEqual(result['printState'],'paused')
        self.assertEqual(self.calls,[MAGNET_COMMANDS['clear']])
    def test_invalid_ident_does_not_write_outside_folder(self):
        with self.assertRaises(ValueError):self.pause('../bad')
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
