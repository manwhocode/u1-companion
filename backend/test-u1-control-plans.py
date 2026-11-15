import unittest,json
from u1_ai.control_plans import EXTRA,prepare,cover_script
from u1_ai.codex_account import parse_plan
class Moon:
 def __init__(self):self.calls=[]
 def relay(self,op,payload):
  self.calls.append(op)
  return {'token':'plan','id':'one','runtimeJob':'job','currentFilename':'x.gcode'}
 def api(self,path):return {'status':{'purifier':{'power_detected':True,'mode':1,'desired_chamber_temp':40,'critical_chamber_temp':60}}}
class Tests(unittest.TestCase):
 def test_all_preparations_are_read_or_prepare_only(self):
  for name,props in EXTRA.items():
   with self.subTest(name=name):
    moon=Moon();args={k:{'minutes':5,'filename':'x.gcode','layers':'5,10','fan':'exhaust','percent':0}[k] for k in props}
    value=prepare(moon,name,args)
    self.assertTrue(value['operation']);self.assertTrue(all(op.endswith(('_state','_prepare')) for op in moon.calls))
 def test_fan_zero_keeps_native_thermal_protection(self):
  script=cover_script({'power_detected':True,'mode':1,'desired_chamber_temp':40,'critical_chamber_temp':60},'exhaust',0)
  self.assertIn('DYNAMIC_FAN_CONTROL=1',script);self.assertIn('ALARM_TEMP=60',script)
  with self.assertRaises(ValueError):cover_script({'power_detected':True,'mode':2},'inner',0)
 def test_typed_parameters(self):
  p=parse_plan(json.dumps({'answer':'timer','action':'pause_with_timer','filename':None,'parameters':{'minutes':5,'fan':None,'layers':None,'percent':None}}),True)
  self.assertEqual(p['u1Action']['arguments'],{'minutes':5})
  with self.assertRaises(ValueError):prepare(Moon(),'pause_with_timer',{'minutes':True})
unittest.main()
