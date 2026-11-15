import unittest,json,tempfile,time,importlib.util
from pathlib import Path
from u1_ai.codex_account import parse_plan,plan_schema
from u1_ai.openai_client import OpenAIError
from u1_ai.storage import Settings
from u1_ai.gateway import Gateway
spec=importlib.util.spec_from_file_location('fixtures','test-u1-ai.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
class Tests(unittest.TestCase):
 def test_plan_validation(self):
  self.assertEqual(plan_schema(False)['properties']['action']['enum'],['none'])
  for value,control in [({'answer':'x','action':'pause_print','filename':None},False),({'answer':'x','action':'shell','filename':None},True),({'answer':'x','action':'start_print','filename':None},True)]:
   with self.assertRaises(OpenAIError):parse_plan(json.dumps(value),control)
  p=parse_plan('{"answer":"Prepare","action":"pause_print","filename":null}',True);self.assertEqual(p['u1Action']['name'],'pause_print')
 def test_start_proposal_does_not_start_or_move(self):
  with tempfile.TemporaryDirectory() as root:
   settings=Settings(root);c=settings.get();settings.change({'revision':c['revision'],'apiKey':'test-key','enabled':True,'consent':True,'model':'test','access':'control'},True)
   moon=fixture.Moon();moon.player['canStart']=True;g=Gateway(settings,root,moon)
   result=g.call('start_print',{'filename':'test.gcode'},'owner','chat')
   self.assertFalse(result['executed']);self.assertEqual(result['status'],'requires_confirmation')
   self.assertTrue(all(name in ('print_player_state','print_player_prepare') for name,_ in moon.calls));self.assertNotIn('print_player_start',[name for name,_ in moon.calls])
   with self.assertRaises(ValueError):g.confirm(result['actionId'],'owner',False)
if __name__=='__main__':unittest.main()
