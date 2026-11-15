import pathlib,json,tempfile,uuid,unittest,importlib.util
from unittest.mock import patch
from u1_ai.storage import Settings,atomic
from u1_ai.agent import Agent
from u1_ai.gateway import Gateway
spec=importlib.util.spec_from_file_location('f','test-u1-ai.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class Client:
 def __init__(self,*a,**k):self.count=0
 def response(self,*a):
  self.count+=1
  if self.count==1:return {'readTools':['get_printable_files'],'output':[]}
  return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Предложение'}]}],'u1Action':{'name':'start_print','arguments':{'filename':'test.gcode'}}}
class Moon(f.Moon):
 def api(self, route, payload=None):
  if route.startswith('/server/files/list'):return [{'path':'test.gcode','modified':1}]
  if route.startswith('/server/history/list'):return {'jobs':[{'filename':'test.gcode','status':'completed'}]}
  return super().api(route,payload)
class Tests(unittest.TestCase):
 def test_structured_proposal_uses_gateway_and_never_confirms(self):
  with tempfile.TemporaryDirectory() as root:
   st=Settings(root);v=st.get();st.change({'revision':v['revision'],'apiKey':'test-key','model':'test','enabled':True,'consent':True,'access':'control'},True)
   v=st.get();atomic(st.path,{**v,'provider':'codex'})
   moon=Moon();moon.player['canStart']=True;g=Gateway(st,root,moon);agent=Agent(st,g,root)
   with patch('u1_ai.agent.CodexClient',Client):r=agent.chat('Запусти последнюю печать',str(uuid.uuid4()),'owner')
   self.assertEqual(len(r['message']['proposals']),1);self.assertNotIn('print_player_start',[name for name,_ in moon.calls]);self.assertFalse(r['message']['proposals'][0]['executed'])
 def test_filename_absent_from_printer_never_reaches_prepare(self):
  with tempfile.TemporaryDirectory() as root:
   st=Settings(root);v=st.get();st.change({'revision':v['revision'],'apiKey':'test-key','model':'test','enabled':True,'consent':True,'access':'control'},True);atomic(st.path,{**st.get(),'provider':'codex'})
   moon=f.Moon();moon.player['canStart']=True;agent=Agent(st,Gateway(st,root,moon),root)
   with patch('u1_ai.agent.CodexClient',Client):r=agent.chat('Запусти печать',str(uuid.uuid4()),'owner')
   self.assertEqual(r['message']['proposals'],[]);self.assertNotIn('print_player_prepare',[name for name,_ in moon.calls])
unittest.main()
