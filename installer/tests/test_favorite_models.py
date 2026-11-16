from pathlib import Path
import sys,tempfile,unittest,types
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from u1_companion_info import models

class Models(unittest.TestCase):
    def test_group_variants_and_statistics_without_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs=[{'job_id':'1','filename':'red.gcode','status':'completed','print_duration':10},
                  {'job_id':'2','filename':'blue.gcode','status':'cancelled','print_duration':5},
                  {'job_id':'3','filename':'other.gcode','status':'completed','print_duration':100}]
            store=types.SimpleNamespace(folder=Path(tmp),api=lambda _: {'jobs':jobs},get=lambda *args:{'records':[{'filename':'red.gcode','state':'applied','rows':[{'grams':4,'pricePerGram':0.1}]}]})
            saved=models(store,'models_save',{'name':'Model','files':['red.gcode','blue.gcode','red.gcode']})['models'][0]
            self.assertEqual(len(saved['files']),2)
            stats=models(store,'models_stats',{'id':saved['id']})
            self.assertEqual((stats['prints'],stats['completed'],stats['duration'],stats['grams']),(2,1,15,4))
            self.assertAlmostEqual(stats['cost'],0.4)
            self.assertFalse(stats['truncated'])
            self.assertEqual(models(store,'models_delete',{'id':saved['id']}),{'models':[]})

    def test_rejects_invalid_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=types.SimpleNamespace(folder=Path(tmp))
            for payload in [{'name':'','files':['a.gcode']},{'name':'Model','files':['../a.gcode']},{'name':'Model','files':[]}]:
                with self.assertRaises(ValueError):models(store,'models_save',payload)
            self.assertFalse((store.folder/'favorite-models.json').exists())
