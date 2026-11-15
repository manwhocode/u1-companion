import tempfile,unittest,json,queue
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from u1_ai.codex_account import Codex
from u1_ai.openai_client import OpenAIError
from u1_ai.read_intents import reads_for
class Tests(unittest.TestCase):
 def test_prefetch_is_small_readonly_and_does_not_match_explanations(self):
  for text in ['Привет','Почему температура скачет?','Какая температура нужна для PLA?','Установи температуру сопла 220','Объясни что такое остаток']:
   self.assertEqual(reads_for(text),[],text)
  self.assertEqual(reads_for('Какая сейчас температура сопла первой головки?'),['get_temperatures'])
  self.assertEqual(reads_for('Сколько грамм осталось на катушке?'),['get_filament_status'])
  self.assertEqual(reads_for('Какой статус принтера?'),['get_printer_status'])
 def test_session_reuses_context_but_isolates_owner_revision_and_chat(self):
  with tempfile.TemporaryDirectory() as root:
   c=Codex(root);c.proc=MagicMock();c.proc.poll.return_value=None;calls=[]
   def rpc(name,params=None,**kwargs):
    calls.append((name,params))
    if name=='thread/start':return {'thread':{'id':'t'+str(len(calls))}}
    if name=='turn/start':
     c.events.put({'method':'item/completed','params':{'threadId':params['threadId'],'item':{'type':'agentMessage','text':json.dumps({'answer':'OK','action':'none','filename':None})}}})
     c.events.put({'method':'turn/completed','params':{'threadId':params['threadId'],'turn':{'status':'completed'}}});return {'turn':{'id':'turn'}}
    return {}
   config={'revision':'r','model':'test','contextChars':24000,'access':'read','keepHistory':True}
   def client(owner='a',chat='chat',request='one'):return SimpleNamespace(owner=owner,chat=chat,cursor=0,private_key=request)
   with patch.object(c,'start'),patch.object(c,'status',return_value={'connected':True}),patch.object(c,'rpc',side_effect=rpc):
    r=c.response(config,[{'role':'developer','content':'Rules'},{'role':'user','content':'old question'}],[],None,client());self.assertFalse(r['performance']['reusedSession'])
    r=c.response(config,[{'role':'developer','content':'Rules'},{'role':'user','content':'old question'},{'role':'assistant','content':'OK'},{'role':'user','content':'new question'}],[],None,client(request='two'));self.assertTrue(r['performance']['reusedSession'])
    self.assertEqual(sum(n=='thread/start' for n,_ in calls),1)
    prompt=[p for n,p in calls if n=='turn/start'][-1]['input'][0]['text'];self.assertNotIn('old question',prompt);self.assertIn('new question',prompt)
    c.response(config,[{'role':'developer','content':'Rules'},{'role':'user','content':'other owner'}],[],None,client(owner='b'));self.assertEqual(sum(n=='thread/start' for n,_ in calls),2)
    c.drop_chat('chat');self.assertFalse(c.sessions)
 def test_account_check_uses_cached_identity_without_forced_token_refresh(self):
  with tempfile.TemporaryDirectory() as root:
   c=Codex(root);c.proc=MagicMock();c.proc.poll.return_value=None
   with patch.object(c,'rpc',return_value={'account':{'type':'chatgpt','planType':'plus'}}) as rpc:
    self.assertTrue(c.status()['connected']);self.assertTrue(c.status()['connected']);rpc.assert_called_once_with('account/read',{'refreshToken':False},timeout=8)
if __name__=='__main__':unittest.main()
