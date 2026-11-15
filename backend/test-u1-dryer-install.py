import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import u1_dryer_install as m
class Tests(unittest.TestCase):
 def setUp(self):
  root=Path('local-backups/dryer-install-tests');root.mkdir(exist_ok=True,parents=True);self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  self.home=self.root/'home';self.home.mkdir();self.config=self.root/'printer.cfg';self.raw=b'[printer]\nkinematics: corexy\n#*# <---------------------- SAVE_CONFIG ---------------------->\n';self.config.write_bytes(self.raw)
  self.link=self.root/'extras'/'u1_dryer.py';self.link.parent.mkdir();self.source=self.root/'source';self.source.mkdir();(self.source/'u1_dryer.py').write_text('def load_config(config):return None\n')
  self.backup=self.root/'backup'
  for key,value in [('ROOT',self.home),('PRINTER',self.config),('LINK',self.link),('guard',lambda:None),('restart',lambda expected:None),('api',lambda p:{'status':{'configfile':{'settings':{'purifier':{'external_temp_sensor':'cavity'}}}}})]:
   patcher=patch.object(m,key,value);patcher.start();self.addCleanup(patcher.stop)
 def test_additive_config_and_backup(self):
  if __import__('os').name=='nt':self.skipTest('U1 symlink permissions tested on Linux')
  m.install(self.source,self.backup);self.assertIn(m.BLOCK,self.config.read_text());self.assertTrue(self.link.is_symlink());self.assertEqual((self.backup/'printer.cfg').read_bytes(),self.raw)
  m.rollback(self.backup);self.assertEqual(self.config.read_bytes(),self.raw);self.assertFalse(self.link.exists())
 def test_foreign_config_rejected(self):
  (self.config.parent/'u1-dryer.cfg').write_text('foreign')
  with self.assertRaises(RuntimeError):m.install(self.source,self.backup)
  self.assertEqual(self.config.read_bytes(),self.raw)
 def test_foreign_link_rejected(self):
  self.link.write_text('foreign')
  with self.assertRaises(RuntimeError):m.install(self.source,self.backup)
 def test_unknown_sensor_rejected(self):
  with patch.object(m,'api',return_value={'status':{'configfile':{'settings':{'purifier':{'external_temp_sensor':'unknown'}}}}}):
   with self.assertRaises(RuntimeError):m.install(self.source,self.backup)
if __name__=='__main__':unittest.main()
