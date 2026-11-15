import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from u1_ai.server import handler
from u1_ai.install import nginx

from u1_ai.storage import Settings, atomic, read, redact
from u1_ai.gateway import Gateway, schemas
from u1_ai.agent import Agent
from u1_ai.server import Application
from u1_ai.openai_client import OpenAIClient, OpenAIError, NoRedirect
from u1_ai_session import issue


class Moon:
    def __init__(self):
        self.calls = []
        self.player = {'canStart': False, 'canPause': True, 'canResume': False, 'canCancel': True,
                       'currentJob': 'job-one', 'filename': 'model.gcode'}
        self.fail = False
    def api(self, route, payload=None):
        self.calls.append((route, payload))
        if route == '/server/info':
            return {'klippy_connected': True, 'klippy_state': 'ready'}
        if 'configfile' in route:
            return {'status': {'configfile': {'settings': {'extruder': {'max_temp': 300, 'password': 'not-public'}, 'secrets': {'token': 'hidden'}}}}}
        if route == '/printer/gcode/help':
            return {'UNSAFE_EXAMPLE_MACRO': 'not executable by model'}
        return {'status': {'webhooks': {'state': 'ready'}, 'print_stats': {'state': 'printing', 'filename': 'model.gcode'}, 'exception_manager': {'exceptions': []}}}
    def item(self, key, default=None):
        return default
    def relay(self, operation, payload, **kwargs):
        self.calls.append((operation, copy.deepcopy(payload)))
        if operation == 'print_player_state':
            return copy.deepcopy(self.player)
        if operation == 'print_player_prepare':
            return {'token': 'native-plan', 'filename': payload['filename']}
        if self.fail:
            raise TimeoutError('unacknowledged')
        if payload.get('currentJob') != self.player['currentJob'] and operation == 'print_player_action':
            raise ValueError('job changed')
        return {'message': 'confirmed by application'}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.settings = Settings(self.root)
        self.moon = Moon()
        self.now = 1000
        self.gateway = Gateway(self.settings, self.root, self.moon, lambda: self.now)
        self.chat = str(uuid.uuid4())
        self.key = 'unit-test-only-not-a-real-key'
    def enable(self, access='read'):
        return self.settings.change({'revision': self.settings.get()['revision'], 'apiKey': self.key, 'enabled': True,
                                     'consent': True, 'model': 'test-model', 'access': access}, secure=True)
    def propose(self, name='pause_print', args=None):
        self.enable('control')
        return self.gateway.call(name, args or {}, 'owner', self.chat)['actionId']

    def test_disabled_default_no_key_in_public_settings(self):
        self.assertFalse(self.settings.public()['enabled'])
        self.assertNotIn('apiKey', self.settings.public())
        with self.assertRaises(ValueError):self.gateway.call('get_printer_status', {}, 'owner', self.chat)
        self.assertEqual(self.moon.calls, [])
    def test_key_requires_https_and_is_not_echoed(self):
        with self.assertRaises(ValueError):self.settings.change({'revision': '', 'apiKey': self.key})
        result = self.enable()
        self.assertNotIn(self.key, json.dumps(result)); self.assertTrue(result['hasKey'])
        self.assertEqual(self.settings.get()['apiKey'], self.key)
        with self.assertRaises(ValueError):self.settings.change({'revision': self.settings.get()['revision'], 'instructions': self.key}, secure=True)
    def test_deleting_key_also_disables_cloud_requests(self):
        self.enable()
        result = self.settings.change({'revision': self.settings.get()['revision'], 'clearKey': True}, secure=True)
        self.assertFalse(result['hasKey']); self.assertFalse(result['enabled'])
    def test_consent_and_model_required(self):
        for missing in ('apiKey', 'consent', 'model'):
            p = {'revision': '', 'apiKey': self.key, 'consent': True, 'model': 'test-model', 'enabled': True}
            p[missing] = False if missing == 'consent' else ''
            with self.assertRaises(ValueError):self.settings.change(p, secure=True)
    def test_settings_revision_and_unknown_fields_rejected(self):
        self.enable()
        for p in ({'revision': ''}, {'revision': self.settings.get()['revision'], 'endpoint': 'http://attacker'}):
            with self.assertRaises(ValueError):self.settings.change(p, secure=True)
    def test_setting_bounds_booleans_and_unsupported_level(self):
        for k, v in [('contextChars', True), ('maxOutputTokens', 100000), ('access', 'advanced'), ('model', '../model'), ('apiKey', 'key\nheader'), ('enabled', 1)]:
            with self.assertRaises(ValueError):self.settings.change({'revision': '', k: v}, secure=True)
    def test_read_only_never_exposes_control_tools(self):
        self.enable()
        self.assertNotIn('pause_print', [r['name'] for r in schemas('read')])
        with self.assertRaises(ValueError):self.gateway.call('pause_print', {}, 'owner', self.chat)
        self.assertEqual(self.moon.calls, [])
    def test_arbitrary_commands_files_confirmation_tool_and_extra_args_denied(self):
        self.enable('control')
        for name, args in [('execute_gcode', {'script': 'G28'}), ('confirm', {}), ('execute_approved_macro', {'name': 'UNSAFE_EXAMPLE_MACRO'}), ('get_printer_status', {'path': '/etc/passwd'}), ('pause_print', {'confirmed': True})]:
            with self.assertRaises(ValueError):self.gateway.call(name, args, 'owner', self.chat)
        self.assertEqual(self.moon.calls, [])
    def test_read_config_filters_secrets_and_macro_read_does_not_execute(self):
        self.enable()
        result = self.gateway.call('get_current_configuration', {}, 'owner', self.chat)
        self.assertEqual(result, {'extruder': {'max_temp': 300}})
        self.gateway.call('get_available_macros', {}, 'owner', self.chat)
        self.assertFalse(any(payload is not None for _, payload in self.moon.calls))
    def test_proposal_is_not_a_printer_command(self):
        action_id = self.propose()
        self.assertEqual([x[0] for x in self.moon.calls], ['print_player_state'])
        self.assertEqual(read(self.root/'actions'/(action_id+'.json'))['state'], 'pending')
    def test_confirm_needs_click_owner_and_fresh_permissions(self):
        action_id = self.propose()
        for owner, yes in [('owner', False), ('other', True)]:
            with self.assertRaises(ValueError):self.gateway.confirm(action_id, owner, yes)
        self.settings.change({'revision': self.settings.get()['revision'], 'access': 'read'})
        with self.assertRaises(ValueError):self.gateway.confirm(action_id, 'owner', True)
        self.assertEqual([x[0] for x in self.moon.calls], ['print_player_state'])
    def test_confirm_is_one_shot_even_after_restart(self):
        action_id = self.propose();self.gateway.confirm(action_id, 'owner', True)
        other = Gateway(self.settings, self.root, self.moon, lambda:self.now)
        with self.assertRaises(ValueError):other.confirm(action_id, 'owner', True)
        self.assertEqual(len([r for r in self.moon.calls if r[0]=='print_player_action']),1)
    def test_timeout_cannot_retry(self):
        action_id = self.propose();self.moon.fail = True
        with self.assertRaises(ValueError):self.gateway.confirm(action_id, 'owner', True)
        self.assertEqual(read(self.root/'actions'/(action_id+'.json'))['state'],'needs_review')
        with self.assertRaises(ValueError):self.gateway.confirm(action_id, 'owner', True)
        self.assertEqual(len([r for r in self.moon.calls if r[0]=='print_player_action']),1)
    def test_changed_job_is_rejected_by_existing_player_layer(self):
        action_id=self.propose();self.moon.player['currentJob']='other-job'
        with self.assertRaises(ValueError):self.gateway.confirm(action_id,'owner',True)
        self.assertEqual(read(self.root/'actions'/(action_id+'.json'))['state'],'needs_review')
    def test_expired_or_rejected_proposal_does_not_dispatch(self):
        action_id=self.propose();self.now+=121
        with self.assertRaises(ValueError):self.gateway.confirm(action_id,'owner',True)
        self.gateway.reject(action_id,'owner')
        self.now-=121
        with self.assertRaises(ValueError):self.gateway.confirm(action_id,'owner',True)
        self.assertEqual([r[0] for r in self.moon.calls],['print_player_state'])
    def test_start_traversal_and_busy_printer_rejected(self):
        self.enable('control')
        with self.assertRaises(ValueError):self.gateway.call('start_print',{'filename':'file.gcode'},'owner',self.chat)
        self.moon.player['canStart']=True
        for name in ('../file.gcode','/etc/file.gcode','a.gcode\nG28','a.txt'):
            with self.assertRaises(ValueError):self.gateway.call('start_print',{'filename':name},'owner',self.chat)
    def test_start_proposal_reuses_native_preflight_without_starting(self):
        self.enable('control');self.moon.player['canStart']=True
        value=self.gateway.call('start_print',{'filename':'file.gcode'},'owner',self.chat)
        self.assertEqual(value['executed'],False)
        self.assertEqual([r[0] for r in self.moon.calls],['print_player_state','print_player_prepare'])
        self.gateway.confirm(value['actionId'],'owner',True)
        self.assertEqual(self.moon.calls[-1][0],'print_player_start')
    def test_sessions_only_issue_for_local_origin_and_expire(self):
        for origin in ('https://evil.test','https://192.168.1.100/path','https://x@192.168.1.100','https://192.168.1.100:99'):
            with self.assertRaises(ValueError):issue({'origin':origin},self.root,hosts={'192.168.1.100'})
        result=issue({'origin':'https://192.168.1.100'},self.root,hosts={'192.168.1.100'})
        app=Application(self.root,moon=self.moon)
        headers={'X-U1-AI-Session':result['session'],'X-U1-Origin':'https://192.168.1.100'}
        owner,secure=app.authenticate(headers);self.assertTrue(secure)
        self.assertNotEqual(owner,result['session'])
        for changed in ({**headers,'Origin':'https://evil.test'},{**headers,'X-U1-Origin':'http://192.168.1.100'},{**headers,'X-U1-AI-Session':'a'*64}):
            with self.assertRaises(PermissionError):app.authenticate(changed)
        p=self.root/'sessions'/(owner+'.json');row=read(p);row['expires']=0;atomic(p,row)
        with self.assertRaises(PermissionError):app.authenticate(headers)
    def test_agent_function_cycle_preserves_reasoning_and_never_executes_proposals(self):
        self.enable('control');bodies=[]
        responses=[{'output':[{'type':'reasoning','encrypted_content':'opaque'},{'type':'function_call','name':'pause_print','arguments':'{}','call_id':'call-a'}], 'usage':{'input_tokens':10,'output_tokens':5}},
                   {'output':[{'type':'message','content':[{'type':'output_text','text':'Подтвердите в приложении.'}]}], 'usage':{'input_tokens':20,'output_tokens':8}}]
        class Client:
            def response(_,config,items,tools):bodies.append(copy.deepcopy(items));return responses.pop(0)
        a=Agent(self.settings,self.gateway,self.root,lambda key:Client())
        result=a.chat('Поставь на паузу',self.chat,'owner')
        self.assertEqual(len(result['message']['proposals']),1)
        self.assertEqual([r[0] for r in self.moon.calls],['print_player_state'])
        self.assertTrue(any(x.get('encrypted_content')=='opaque' for x in bodies[1]))
        self.assertTrue(any(x.get('type')=='function_call_output' for x in bodies[1]))
        self.assertEqual(read(self.root/'usage.json')['inputTokens'],30)
        self.assertNotIn(self.key,json.dumps(result))
    def test_no_history_mode_and_secret_chat_rejected(self):
        self.enable();self.settings.change({'revision':self.settings.get()['revision'],'keepHistory':False})
        class Client:
            def response(*args):return {'output':[{'type':'message','content':[{'type':'output_text','text':'Hello'}]}]}
        a=Agent(self.settings,self.gateway,self.root,lambda key:Client())
        with self.assertRaises(ValueError):a.chat(self.key,self.chat,'owner')
        a.chat('status',self.chat,'owner')
        self.assertEqual(list((self.root/'chats').glob('*.json')),[])
    def test_restart_does_not_retry_paid_or_control_requests(self):
        p=self.root/'jobs'/(str(uuid.uuid4())+'.json');atomic(p,{'state':'running'})
        Agent(self.settings,self.gateway,self.root)
        self.assertEqual(read(p)['state'],'needs_review');self.assertEqual(self.moon.calls,[])
    def test_routes_do_not_expose_private_file_or_key(self):
        self.enable();app=Application(self.root,moon=self.moon)
        result=app.route('GET','/u1-ai/api/state',{},'owner',True)
        self.assertNotIn(self.key,json.dumps(result))
        for route in ('/settings.json','/u1-ai/api/../settings.json','/u1-ai/api/chats/../../settings.json'):
            with self.assertRaises(ValueError):app.route('GET',route,{},'owner',True)
    def test_redaction_and_redirects(self):
        self.assertNotIn('sk-unitsecret123',redact({'message':'sk-unitsecret123 Bearer abc.def'}))
        self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))
        class Opener:
            def open(_,req,timeout):raise TimeoutError()
        with self.assertRaises(OpenAIError):OpenAIClient(self.key,Opener()).request('responses',{})
        with self.assertRaises(ValueError):OpenAIClient(self.key,Opener()).request('http://attacker',{})

    def test_nginx_patch_is_idempotent_and_does_not_replace_other_routes(self):
        source='server {\n    listen 80;\n    location / { root /home/lava/fluidd; }\n}\n'
        patched=nginx(source)
        self.assertEqual(nginx(patched),patched)
        self.assertIn('location / { root /home/lava/fluidd; }',patched)
        self.assertIn('127.0.0.1:4547',patched)
        self.assertIn('X-U1-Origin "$scheme://$http_host"',patched)
        certificate_server = 'server {\n    listen 8081;\n    location / { return 404; }\n}\n'
        https = source.replace('listen 80;', 'listen 443 ssl;')
        patched_https = nginx(https + certificate_server)
        self.assertTrue(patched_https.endswith(certificate_server))
        self.assertEqual(patched_https.count('location /u1-ai/api/'), 1)
        self.assertEqual(nginx(patched_https), patched_https)
        for invalid in ('server {\n}\nserver {\n}\n','location /u1-ai/api/ {}\nserver {\n}\n'):
            with self.assertRaises(ValueError):nginx(invalid)

    def test_responses_body_no_key_storage_or_model_specific_parameters(self):
        calls=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return b'{"output":[]}'
        class Opener:
            def open(_,req,timeout):calls.append(req);return Response()
        client=OpenAIClient(self.key,Opener())
        self.enable();client.response(self.settings.get(),[{'role':'user','content':'status'}],schemas())
        req=calls[0];body=json.loads(req.data)
        self.assertEqual(req.full_url,'https://api.openai.com/v1/responses')
        self.assertNotIn(self.key,req.data.decode())
        self.assertFalse(body['store']);self.assertFalse(body['parallel_tool_calls'])
        self.assertNotIn('temperature',body)

    def test_real_loopback_http_requires_session_and_never_returns_key(self):
        self.enable();app=Application(self.root,moon=self.moon)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(app));threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url='http://127.0.0.1:'+str(server.server_port)+'/u1-ai/api/state'
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(url)
        self.assertEqual(error.exception.code,403)
        error.exception.close()
        session=issue({'origin':'https://192.168.1.100'},self.root,hosts={'192.168.1.100'})
        req=urllib.request.Request(url,headers={'X-U1-AI-Session':session['session'],'X-U1-Origin':'https://192.168.1.100'})
        with urllib.request.urlopen(req) as response:
            raw=response.read().decode();self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertNotIn(self.key,raw);self.assertTrue(json.loads(raw)['value']['settings']['hasKey'])


if __name__=='__main__':unittest.main()
