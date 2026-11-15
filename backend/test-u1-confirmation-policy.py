import unittest,tempfile,uuid,importlib.util
from unittest.mock import patch
from u1_ai.storage import Settings,atomic,read
from u1_ai.gateway import Gateway
from u1_ai.agent import Agent
spec=importlib.util.spec_from_file_location('f','test-u1-ai.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class Client:
 def __init__(self,*a,**k):pass
 def response(self,*a):return {'status':'completed','output':[],'u1Action':{'name':'pause_print','arguments':{}}}
class Tests(unittest.TestCase):
 def test_default_requires_click_and_opt_out_executes_exactly_once(self):
  for required in (True,False):
   with self.subTest(required=required),tempfile.TemporaryDirectory() as d:
    st=Settings(d);self.assertTrue(st.get()['requireConfirmation']);st.change({'revision':st.get()['revision'],'apiKey':'test-key','model':'test','enabled':True,'consent':True,'access':'control','requireConfirmation':required},True)
    atomic(st.path,{**st.get(),'provider':'codex'});moon=f.Moon();a=Agent(st,Gateway(st,d,moon),d)
    with patch('u1_ai.agent.CodexClient',Client):r=a.chat('Пауза',str(uuid.uuid4()),'owner')
    self.assertEqual(sum(op=='print_player_action' for op,_ in moon.calls),0 if required else 1)
 def test_invalid_toggle_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   st=Settings(d)
   with self.assertRaises(ValueError):st.change({'revision':st.get()['revision'],'requireConfirmation':'false'},True)
unittest.main()
