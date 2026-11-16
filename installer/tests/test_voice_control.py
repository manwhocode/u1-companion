import datetime,hashlib,hmac,json,os,sys,tempfile,types,unittest,uuid,io,importlib.util,threading,urllib.request,urllib.error,re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
import u1_voice_control as v

class Moon:
    def __init__(self):self.calls=[];self.fail=False
    def relay(self,op,payload,**kwargs):
        self.calls.append((op,payload,kwargs))
        if op=='print_player_state':return dict(canPause=True,canResume=True,canCancel=True,currentJob='job1')
        if op=='print_player_prepare':return {'token':'start-token'}
        if op=='magnet_state':return {'runtimeJob':'job1','token':'magnet-token'}
        if op=='night_state':return {'revision':'r1','start':'22:00','end':'07:00','zone':'UTC'}
        if op=='timed_pause_prepare':return {'token':'timer-token'}
        if op=='timed_pause_state':return {'id':'timer-id'}
        if op=='models_state':return {'models':[{'name':'Cube','files':['cube.gcode']}]}
        if op=='maintenance_state':return {'serviceDue':True,'bedDue':False}
        if self.fail:raise TimeoutError('response lost')
        return {'message':'accepted'}
    def api(self,path):
        self.calls.append((path,{},{}))
        if 'history/list' in path:return {'jobs':[{'filename':'last.gcode'}]}
        return {'status':{'print_stats':{'state':'printing','print_duration':300},'virtual_sdcard':{'progress':0.5},'exception_manager':{'exceptions':[]},'webhooks':{'state_message':'Ready'}}}

class Voice(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        if os.name!='posix':
            fake=types.SimpleNamespace(flock=lambda *a:None,LOCK_EX=1,LOCK_NB=2)
            context=patch.dict(sys.modules,{'fcntl':fake});context.start();self.addCleanup(context.stop)
        self.skill='amzn1.ask.skill.1234567890-test';self.key='a'*64;self.now=1700000000
        self.cfg={'enabled':True,'key':self.key,'skillId':self.skill,'userHash':hashlib.sha256(b'user1').hexdigest()}
        v.atomic(self.root/'config.json',self.cfg);self.moon=Moon();self.voice=v.Voice(self.moon,self.root,lambda:self.now)
    def body(self,name,request=None,session='session1',user='user1',slots=None):
        return {'context':{'System':{'application':{'applicationId':self.skill},'user':{'userId':user}}},'session':{'sessionId':session,'application':{'applicationId':self.skill}},'request':{'type':'IntentRequest','requestId':request or str(uuid.uuid4()),'timestamp':datetime.datetime.fromtimestamp(self.now,datetime.timezone.utc).isoformat(),'locale':'de-DE','intent':{'name':name,'slots':{k:{'value':value} for k,value in (slots or {}).items()}}}}
    def send(self,body):
        raw=json.dumps(body).encode();sig=hmac.new(self.key.encode(),raw,hashlib.sha256).hexdigest()
        return self.voice.receive(raw,sig)
    def writes(self):return [x for x in self.moon.calls if x[0] in ('print_player_action','print_player_start','magnet_action','night_configure','timed_pause_arm','timed_pause_cancel')]

    def test_authentication_timestamp_and_application_fail_closed(self):
        raw=json.dumps(self.body('PausePrintIntent')).encode()
        with self.assertRaises(PermissionError):self.voice.receive(raw,'bad')
        body=self.body('PausePrintIntent');body['request']['timestamp']='2020-01-01T00:00:00Z'
        with self.assertRaises(PermissionError):self.send(body)
        body=self.body('PausePrintIntent');body['context']['System']['application']['applicationId']='other'
        with self.assertRaises(PermissionError):self.send(body)
        self.assertFalse(self.moon.calls)

    def test_pairing_required_and_single_use_code(self):
        self.cfg['userHash']='';v.atomic(self.root/'config.json',self.cfg)
        self.send(self.body('PausePrintIntent'));self.assertFalse(self.moon.calls)
        self.cfg.update(pairHash=hashlib.sha256(b'001234').hexdigest(),pairExpires=self.now+100,pairAttempts=0);v.atomic(self.root/'config.json',self.cfg)
        self.send(self.body('LinkPrinterIntent',slots={'code':'1234'}))
        self.assertEqual(v.config(self.root)['userHash'],hashlib.sha256(b'user1').hexdigest())
        self.send(self.body('LinkPrinterIntent',user='user2',slots={'code':'1234'}))
        self.assertEqual(v.config(self.root)['userHash'],hashlib.sha256(b'user1').hexdigest())

    def test_pause_replay_is_deduplicated_even_after_handler_restart(self):
        body=self.body('PausePrintIntent');first=self.send(body)
        self.voice=v.Voice(self.moon,self.root,lambda:self.now);self.assertEqual(self.send(body),first)
        self.assertEqual(len(self.writes()),1)
        uuid.UUID(self.writes()[0][2]['request_id'])
        self.assertEqual(self.writes()[0][2]['expires_at'],self.now+6)

    def test_filament_fault_resume_requires_explicit_voice_confirmation(self):
        original=self.moon.relay
        def relay(op,payload,**kwargs):
            if op=='print_player_state':return {'canResume':False,'canAcknowledgeFault':True,'pauseFaultToken':'fault1','currentJob':'job1'}
            return original(op,payload,**kwargs)
        self.moon.relay=relay
        answer=self.send(self.body('ResumePrintIntent'))
        self.assertFalse(answer['response']['shouldEndSession']);self.assertFalse(self.writes())
        self.send(self.body('AMAZON.YesIntent'))
        self.assertEqual(self.writes()[0][1],{'action':'ack_fault','currentJob':'job1','faultToken':'fault1','confirmed':True})

    def test_error_status_includes_latched_print_stats_fault(self):
        self.moon.api=lambda path:{'status':{'print_stats':{'state':'paused','exception':{'id':523,'code':38,'message':'detect filament tangled!'}},'virtual_sdcard':{'progress':.68},'exception_manager':{'exceptions':[]}}}
        body=self.body('ErrorStatusIntent');body['request']['locale']='en-US'
        self.assertIn('Filament tangling',self.send(body)['response']['outputSpeech']['text'])

    def test_stale_mailbox_commands_are_rejected_before_dispatch(self):
        from u1_data_store import DataStore
        from u1_ai.gateway import Moonraker
        for deadline in (self.now-1,True,None,float('nan'),float('inf'),'later'):
            with patch('u1_data_store.time.time',return_value=self.now):
                with self.assertRaisesRegex(ValueError,'expired'):
                    DataStore.handle(None,'test',{'operation':'print_player_action','payload':{'action':'resume'},'expiresAt':deadline})
        class Capture(Moonraker):
            def api(self,path,payload=None,timeout=8):
                if payload is not None:self.queued=payload['value'];return {}
                return {'value':{'ok':True,'value':'accepted'}}
        moon=Capture()
        self.assertEqual(moon.relay('print_player_action',{'action':'pause'},expires_at=self.now+6),'accepted')
        self.assertEqual(moon.queued['expiresAt'],self.now+6)

    def test_resume_cancel_lower_repeat_and_timer_need_same_session_confirmation(self):
        for name,slots,operation in [('ResumePrintIntent',{},'print_player_action'),('CancelPrintIntent',{},'print_player_action'),('PauseLowerIntent',{},'magnet_action'),('RepeatPrintIntent',{},'print_player_start'),('TimedPauseIntent',{'minutes':'10'},'timed_pause_arm'),('FavoritePrintIntent',{'model':'cube'},'print_player_start')]:
            self.moon.calls=[];answer=self.send(self.body(name,slots=slots));self.assertFalse(answer['response']['shouldEndSession']);self.assertFalse(self.writes())
            self.send(self.body('AMAZON.YesIntent'));self.assertEqual(len(self.writes()),1);self.assertEqual(self.writes()[0][0],operation)
            self.send(self.body('AMAZON.YesIntent'));self.assertEqual(len(self.writes()),1)

    def test_wrong_session_user_expiry_and_stop_never_execute(self):
        for next_body in [lambda:self.body('AMAZON.YesIntent',session='other'),lambda:self.body('AMAZON.YesIntent',user='other'),lambda:self.body('AMAZON.StopIntent')]:
            self.send(self.body('RepeatPrintIntent'));self.send(next_body());self.assertFalse(self.writes())
        self.send(self.body('ResumePrintIntent'));self.now+=61;self.send(self.body('AMAZON.YesIntent'));self.assertFalse(self.writes())

    def test_no_response_is_not_retried(self):
        self.moon.fail=True;body=self.body('PausePrintIntent');self.send(body);self.send(body)
        self.assertEqual(len(self.writes()),1)

    def test_night_uses_guarded_policy_and_read_requests_do_not_move(self):
        self.send(self.body('NightModeOnIntent'));self.assertEqual(self.writes()[0][0],'night_configure');self.assertEqual(self.writes()[0][1]['mode'],'on')
        self.moon.calls=[]
        for name in ['StatusIntent','RemainingTimeIntent','ErrorStatusIntent','MaintenanceIntent','UnknownIntent']:self.send(self.body(name))
        self.assertFalse(self.writes())

    def test_disabled_control_rejects_valid_signed_requests(self):
        self.cfg['enabled']=False;v.atomic(self.root/'config.json',self.cfg)
        with self.assertRaises(PermissionError):self.send(self.body('PausePrintIntent'))
        self.assertFalse(self.moon.calls)

    def test_night_off_cancel_timer_and_invalid_timers(self):
        self.send(self.body('NightModeOffIntent'));self.assertEqual(self.writes()[-1][1]['mode'],'off')
        self.send(self.body('CancelTimedPauseIntent'));self.assertEqual(self.writes()[-1][0],'timed_pause_cancel')
        count=len(self.writes())
        for minutes in ['0','-1','1441','not a number']:
            self.send(self.body('TimedPauseIntent',slots={'minutes':minutes}))
        self.assertEqual(len(self.writes()),count)

    def test_preparation_rejects_unknown_file_group_without_start(self):
        self.send(self.body('FavoritePrintIntent',slots={'model':'not found'}));self.send(self.body('AMAZON.YesIntent'))
        self.assertFalse(self.writes())

    def test_models_have_matching_handlers_and_confirmation_intents(self):
        root=Path(__file__).resolve().parents[2]
        for path in (root/'alexa-skill/models').glob('*.json'):
            model=json.loads(path.read_text(encoding='utf-8'))['interactionModel']['languageModel'];names={row['name'] for row in model['intents']}
            self.assertTrue({'AMAZON.YesIntent','AMAZON.NoIntent','LinkPrinterIntent','NightModeOffIntent','TimedPauseIntent','FavoritePrintIntent'}.issubset(names))
            self.assertEqual(len(names),len(model['intents']))
            for intent in model['intents']:
                for sample in intent.get('samples',[]):
                    self.assertNotIn('’',sample,path.name)
                    self.assertIsNone(re.search(r'\S\{|\}\S',sample),path.name+': '+sample)

    def test_all_voice_languages_have_complete_templates_and_confirmations(self):
        from string import Formatter
        root=Path(__file__).resolve().parents[2]
        self.assertEqual(set(v.TEXT),{'en','de','fr','es','it','pt','nl','ja','ar'})
        self.assertEqual(v.TEXT,json.loads((root/'alexa-skill/lambda/voice_messages.json').read_text(encoding='utf-8')))
        for language,catalog in v.TEXT.items():
            self.assertEqual(set(catalog),set(v.TEXT['en']))
            for key,value in catalog.items():
                if isinstance(value,dict):self.assertEqual(set(value),set(v.TEXT['en'][key]));continue
                fields=lambda s:{name for _,name,_,_ in Formatter().parse(s) if name}
                self.assertTrue(value.strip());self.assertEqual(fields(value),fields(v.TEXT['en'][key]))
            self.moon.calls=[]
            body=self.body('ResumePrintIntent');body['request']['locale']=language+'-XX'
            self.assertEqual(self.send(body)['response']['outputSpeech']['text'],catalog['resume'])
            self.assertFalse(self.writes())
            body=self.body('AMAZON.NoIntent');body['request']['locale']=language+'-XX';self.send(body)
            self.assertFalse(self.writes())
        locales={p.stem for p in (root/'alexa-skill/models').glob('*.json')}
        self.assertEqual(locales,{'ar-SA','de-DE','en-AU','en-CA','en-GB','en-IN','en-US','es-ES','es-MX','es-US','fr-CA','fr-FR','it-IT','ja-JP','nl-NL','pt-BR'})

    def test_arabic_pairing_digits_and_dutch_numbered_favorites(self):
        self.cfg.update(userHash='',pairHash=hashlib.sha256(b'001234').hexdigest(),pairExpires=self.now+100,pairAttempts=0)
        v.atomic(self.root/'config.json',self.cfg)
        body=self.body('LinkPrinterIntent',slots={'code':'٠٠١٢٣٤'});body['request']['locale']='ar-SA'
        self.assertEqual(self.send(body)['response']['outputSpeech']['text'],v.TEXT['ar']['linked'])
        for invalid in ['0','2','-1','cube']:
            body=self.body('FavoritePrintIntent',slots={'model':invalid});body['request']['locale']='nl-NL'
            self.assertEqual(self.send(body)['response']['outputSpeech']['text'],v.TEXT['nl']['blocked'])
        body=self.body('FavoritePrintIntent',slots={'model':'1'});body['request']['locale']='nl-NL'
        answer=self.send(body);self.assertIn('cube.gcode',answer['response']['outputSpeech']['text']);self.assertFalse(self.writes())
        self.send(self.body('AMAZON.YesIntent'));self.assertEqual(self.writes()[0][0],'print_player_start')

    def test_hosted_unconfigured_skill_answers_without_contacting_printer(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('voice_lambda_offline',root/'alexa-skill/lambda/lambda_function.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.object(module.Path,'read_text',return_value=json.dumps({'skillId':self.skill,'url':'','key':''})),patch.object(module.urllib.request,'build_opener') as opener:
            for language in v.TEXT:
                body=self.body('StatusIntent');body['request']['locale']=language+'-XX'
                self.assertEqual(module.lambda_handler(body,None)['response']['outputSpeech']['text'],v.TEXT[language]['setup'])
            wrong=self.body('StatusIntent');wrong['context']['System']['application']['applicationId']='wrong'
            self.assertEqual(module.lambda_handler(wrong,None)['response']['outputSpeech']['text'],v.TEXT['de']['failure'])
            opener.assert_not_called()

    def test_only_voice_gateway_route_bypasses_browser_auth_and_still_has_hmac(self):
        root=Path(__file__).resolve().parents[2];text=(root/'remote-access/nginx-template.conf').read_text()
        self.assertIn('"POST::/u1-alexa/skill" 0;',text);self.assertIn('proxy_set_header X-U1-Voice-Signature $http_x_u1_voice_signature;',text)
        self.assertIn('auth_request /__u1_remote_authorize;',text);self.assertIn('~^(POST|PUT|PATCH|DELETE):: 1;',text)

    def test_hosted_lambda_signs_real_envelope_and_never_retries(self):
        root=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('voice_lambda',root/'alexa-skill/lambda/lambda_function.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cfg={'url':'https://printer.example/u1-alexa/skill','key':self.key,'skillId':self.skill}
        body=self.body('StatusIntent');body['context']['System']['apiAccessToken']='must-not-forward';body['session']['attributes']={'private':'must-not-forward'};calls=[]
        def opened(request,timeout):
            calls.append(request);self.assertEqual(timeout,6)
            self.assertNotIn(b'must-not-forward',request.data)
            result=self.voice.receive(request.data,request.get_header('X-u1-voice-signature'))
            return io.BytesIO(json.dumps(result).encode())
        with patch.object(module.Path,'read_text',return_value=json.dumps(cfg)),patch.object(module.urllib.request,'build_opener',return_value=types.SimpleNamespace(open=opened)):
            self.assertEqual(module.lambda_handler(body,None)['version'],'1.0');self.assertEqual(len(calls),1)
            wrong=self.body('PausePrintIntent');wrong['context']['System']['application']['applicationId']='other'
            module.lambda_handler(wrong,None);self.assertEqual(len(calls),1)
        with patch.object(module.Path,'read_text',return_value=json.dumps(cfg)),patch.object(module.urllib.request,'build_opener') as opener:
            opener.return_value.open.side_effect=TimeoutError('lost')
            result=module.lambda_handler(self.body('PausePrintIntent'),None)
            self.assertTrue(result['response']['shouldEndSession']);opener.return_value.open.assert_called_once()

    def test_http_endpoint_uses_hmac_while_ai_routes_keep_session_auth(self):
        from http.server import ThreadingHTTPServer
        from u1_ai.server import handler
        def denied(_):raise PermissionError('session required')
        app=types.SimpleNamespace(authenticate=denied)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(app));server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        raw=json.dumps(self.body('StatusIntent')).encode();signature=hmac.new(self.key.encode(),raw,hashlib.sha256).hexdigest()
        try:
            with patch.object(v,'Voice',return_value=self.voice):
                request=urllib.request.Request(base+'/u1-alexa/skill',data=raw,headers={'Content-Type':'application/json','X-U1-Voice-Signature':signature})
                with urllib.request.urlopen(request,timeout=3) as response:self.assertEqual(json.load(response)['version'],'1.0')
                request=urllib.request.Request(base+'/u1-alexa/skill',data=raw,headers={'Content-Type':'application/json','X-U1-Voice-Signature':'wrong'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request,timeout=3)
                self.assertEqual(error.exception.code,403);error.exception.close()
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(base+'/u1-ai/api/state',timeout=3)
                self.assertEqual(error.exception.code,403);error.exception.close()
            self.assertFalse(self.writes())
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
