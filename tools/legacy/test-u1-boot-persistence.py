"""Installer must fail before changing persistent config if its modules would vanish."""
import importlib.util
import contextlib
from pathlib import Path
import sys
import unittest
import types
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('u1_owned_installer', Path(__file__).with_name('install-addon.py'))
installer = importlib.util.module_from_spec(spec)
try:
    import pwd
    platform_import = contextlib.nullcontext()
except ImportError:
    # The guards under test return before Linux account lookup.
    platform_import = patch.dict(sys.modules, {'pwd': types.ModuleType('pwd')})
with platform_import: spec.loader.exec_module(installer)


class BootPersistenceTests(unittest.TestCase):
    def run_guard(self, persistent, message):
        with patch.object(installer.os, 'geteuid', return_value=0, create=True), \
             patch.object(sys, 'argv', ['install-addon.py', '--ip', '192.168.1.100']), \
             patch.object(installer.pathlib.Path, 'is_file', return_value=persistent), \
             patch.object(installer.pathlib.Path, 'is_dir', return_value=False), \
             patch.object(installer.pathlib.Path, 'mkdir') as mkdir, \
             patch.object(installer.shutil, 'copy2') as copy, \
             patch.object(installer.urllib.request, 'urlopen') as api, \
             patch.object(installer.subprocess, 'run') as command:
            with self.assertRaisesRegex(SystemExit, message): installer.main()
            mkdir.assert_not_called(); copy.assert_not_called()
            api.assert_not_called(); command.assert_not_called()

    def test_without_persistence_installation_stops_before_any_change(self):
        self.run_guard(False, 'System persistence is disabled')

    def test_with_persistence_regular_platform_guards_still_apply(self):
        self.run_guard(True, 'Snapmaker U1 web layout not found')


if __name__ == '__main__': unittest.main()
