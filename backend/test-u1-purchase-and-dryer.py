"""Behavior checks for independent purchase prices and protected chamber drying."""
import copy,importlib.util,runpy,unittest
from u1_dryer import Session

class Chamber(unittest.TestCase):
 def make(self):
  s=Session();s.start(70,600,60,0,'chamber',40);return s
 def test_heat_cycles_and_timer_waits_for_chamber(self):
  s=self.make();s.tick(1,70,30,target=70);self.assertEqual(s.remaining,600)
  s.tick(2,70,40,target=70);self.assertFalse(s.heating);self.assertEqual(s.state,'running')
  s.tick(3,60,39,target=0);self.assertEqual(s.state,'running');self.assertFalse(s.heating)
  s.tick(4,55,37,target=0);self.assertTrue(s.heating);self.assertEqual(s.state,'heating')
 def test_watchdog_and_independent_limit_still_pause(self):
  for now,chamber in [(36,30),(1,60)]:
   s=self.make();self.assertTrue(s.tick(now,70,chamber,target=70));self.assertEqual(s.state,'paused')
 def test_rejected_restart_cannot_change_active_control(self):
  s=self.make()
  with self.assertRaises(ValueError):s.start(40,600,60,1,'bed')
  self.assertEqual(s.mode,'chamber');self.assertEqual(s.temp,70)
 def test_resume_resets_heat_expectation(self):
  s=self.make();s.tick(1,70,40,target=70);s.pause('user');s.resume(35,2)
  self.assertTrue(s.heating);self.assertFalse(s.tick(3,60,35,target=70));self.assertEqual(s.state,'heating')
 def test_unsafe_chamber_targets_rejected(self):
  for target in (True,float('nan'),24,56):
   with self.assertRaises(ValueError):Session().start(70,600,60,0,'chamber',target)

class Purchase(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('fixtures','test-spool-accounting.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
  self.f=f.AccountingTest();self.f.setUp();self.addCleanup(self.f.doCleanups)
 def test_default_inheritance_is_snapshotted_separately_from_customer_tariff(self):
  f=self.f;spool=f.inventory['spools'][1];spool.update(colorId='base',pricePerGram=.1)
  color={'id':'base','name':'Base','purchasePrice':20,'purchaseWeight':1000};f.decisions['u1_filament_library_v1']={'entries':[color]}
  f.tick(f.usage);color['purchasePrice']=50;spool['pricePerGram']=.2;f.finish('completed',12000)
  row=f.usage['records'][0]['rows'][0];self.assertEqual(row['purchasePerGram'],.02);self.assertEqual(row['pricePerGram'],.1)
 def test_individual_purchase_and_missing_cost_are_not_invented(self):
  f=self.f;spool=f.inventory['spools'][1];spool.update(inheritPurchasePrice=False,purchasePrice=12,purchaseWeight=500)
  f.tick(f.usage);f.finish('completed',12000);self.assertEqual(f.usage['records'][0]['rows'][0]['purchasePerGram'],.024)

if __name__=='__main__':unittest.main()
