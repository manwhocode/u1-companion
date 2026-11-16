"""Targeted removal/rollback checks against an isolated simulated U1."""
import json,unittest
from unittest.mock import patch
from test_installer import Fixture,LINKS
import install as m
from uninstall import uninstall


@unittest.skipUnless(LINKS,'Linux filesystem test')
class Removal(Fixture):
    def prepare(self):
        self.original=self.p(m.PRINTER).read_bytes()
        self.inst.install(self.package,self.work,'192.168.1.100',True)
        self.put(m.DATA+'/filament-ui-data/current.json',b'personal inventory fixture')
    def test_removal_restores_native_config_and_preserves_personal_state(self):
        self.prepare();uninstall(self.inst,yes=True)
        self.assertEqual(self.p(m.PRINTER).read_bytes().strip(),self.original.strip())
        self.assertFalse(self.p(m.CORE+'/managed-install.json').exists())
        self.assertFalse(self.p('/etc/init.d/S97u1-ai').exists())
        self.assertEqual(self.p(m.DATA+'/filament-ui-data/current.json').read_bytes(),b'personal inventory fixture')
        self.assertTrue(self.p('/oem/.debug').exists())
        self.assertIn(b'/index.html#/',self.p(m.UI+'/index.html').read_bytes())
    def test_modified_owned_file_blocks_before_any_removal(self):
        self.prepare();self.put(m.CORE+'/spool-accounting.py',b'local user changes')
        with self.assertRaisesRegex(ValueError,'Modified owned file'):uninstall(self.inst,yes=True)
        self.assertTrue(self.p('/etc/init.d/S97u1-ai').exists())
    def test_failed_removal_restores_installed_program(self):
        self.prepare();before=self.p(m.PRINTER).read_bytes();self.nginx_failure=True
        with self.assertRaisesRegex(RuntimeError,'injected nginx'):uninstall(self.inst,yes=True)
        self.assertEqual(self.p(m.PRINTER).read_bytes(),before)
        self.assertTrue(self.p(m.CORE+'/managed-install.json').exists())
        self.assertTrue(self.p('/etc/init.d/S97u1-ai').exists())


if __name__=='__main__':unittest.main()
