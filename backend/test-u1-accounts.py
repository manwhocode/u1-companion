import io,json,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs,urlencode
from u1_ai.accounts import Accounts
from u1_ai.openai_client import parse_events,OpenAIError,ChatGPTClient,api_error
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.a=Accounts(self.tmp.name)
 def pending(self):
  t=self.a.pair('owner');r=self.a.start(t,1455);q=parse_qs(urlsplit(r['url']).query);return t,q
 def test_pkce_host_and_one_shot_start(self):
  t,q=self.pending();self.assertEqual(q['client_id'],['dynamic_agent_client']);self.assertEqual(q['redirect_uri'],['http://127.0.0.1:1455/auth/callback']);self.assertEqual(q['code_challenge_method'],['S256']);self.assertNotIn('code_verifier',q)
  with self.assertRaises(ValueError):self.a.start(t,1455)
  t2,q2=self.pending();self.assertEqual(q['ext_agent_host_id'],q2['ext_agent_host_id']);self.assertNotEqual(q['state'],q2['state'])
 def test_state_wrong_origin_and_expiry_reject_without_network(self):
  t,q=self.pending()
  with patch('u1_ai.accounts.network') as n:
   for u in ['http://127.0.0.1:1455/auth/callback?state=wrong','http://attacker/auth/callback?state='+q['state'][0]]:
    with self.assertRaises(ValueError):self.a.finish(t,u)
   n.assert_not_called()
  p,v=self.a.pending(t);v['expires']=0
  from u1_ai.storage import atomic
  atomic(p,v)
  with self.assertRaises(PermissionError):self.a.start(t,1455)
 def callback(self,q):return q['redirect_uri'][0]+'?'+urlencode({'state':q['state'][0],'client_id':'oaiapp_test','code':'once'})
 def tokens(self):return {'id_token':'signed','access_token':'access-secret','refresh_token':'refresh-secret','scope':'chatgpt.tokens.use.direct','token_type':'Bearer','expires_in':3600}
 def test_success_private_public_no_tokens_and_no_replay(self):
  t,q=self.pending()
  with patch('u1_ai.accounts.network',side_effect=[self.tokens(),{'keys':[]}]),patch('u1_ai.accounts.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'sub':'user','email':'a@example.test'}))):
   self.assertTrue(self.a.finish(t,self.callback(q))['connected'])
  self.assertTrue(self.a.connected());self.assertNotIn('secret',json.dumps(self.a.public()));self.assertEqual(self.a.token(),'access-secret')
  with self.assertRaises(ValueError):self.a.finish(t,self.callback(q))
 def test_signature_or_missing_permission_never_connects(self):
  for signature_ok in [True,False]:
   t,q=self.pending();tokens=self.tokens();tokens['scope']='openid'
   with patch('u1_ai.accounts.network',side_effect=[tokens,{'keys':[]}]),patch('u1_ai.accounts.subprocess.run',return_value=SimpleNamespace(returncode=0 if signature_ok else 1,stdout='{"sub":"user"}')):
    with self.assertRaises(ValueError):self.a.finish(t,self.callback(q))
   self.assertFalse(self.a.connected())
 def test_stream_only_completed_and_size_error(self):
  self.assertEqual(parse_events(io.BytesIO(b'data: {"type":"response.completed","response":{"output":[]}}\n\n')),{'output':[]})
  for data in [b'data: {"type":"response.failed"}\n\n',b'data: {"type":"response.output_text.delta","delta":"hi"}\n\n',b'data: [DONE]\n\n']:
   with self.assertRaises(OpenAIError):parse_events(io.BytesIO(data))
 def test_account_request_omits_api_parameters_and_namespaces_tools(self):
  class R(io.BytesIO):
   def __enter__(self):return self
   def __exit__(self,*args):pass
  class O:
   def open(self,req,timeout):
    p=json.loads(req.data);assert p['stream'] is True and p['store'] is False;assert 'max_output_tokens' not in p;assert p['tools'][0]['type']=='namespace';return R(b'data: {"type":"response.completed","response":{"output":[]}}\n\n')
  ChatGPTClient('token',O()).response({'model':'chosen','maxOutputTokens':2000},[],[])
 def test_quota_and_rate_limit_are_distinct_and_body_is_never_exposed(self):
  import urllib.error
  for code,expected in [('insufficient_quota','лимит оплаты'),('rate_limit_exceeded','частоту'),('unknown','Причина не уточнена')]:
   error=urllib.error.HTTPError('https://api.openai.com',429,'',{},io.BytesIO(json.dumps({'error':{'code':code,'message':'private-secret'}}).encode()))
   text=api_error(error);self.assertIn(expected,text);self.assertNotIn('private-secret',text)
if __name__=='__main__':unittest.main()
