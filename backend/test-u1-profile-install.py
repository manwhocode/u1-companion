"""Only temporary files and mocked restarts; no real U1 paths are modified."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import u1_profile_install as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent / 'local-backups' / 'profile-install-tests'
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.original = b'[printer]\nmax_velocity: 500\n\n#*# <---------------------- SAVE_CONFIG ---------------------->\n#*# [extruder]\n#*# pressure_advance = 0.024\n'

    def test_include_preserves_native_and_save_config_and_is_idempotent(self):
        changed = installer.include_config(self.original)
        self.assertEqual(changed.count(installer.BLOCK.encode()), 1)
        self.assertLess(changed.index(installer.BEGIN.encode()), changed.index(b'#*# <---'))
        self.assertEqual(changed.replace((installer.BLOCK + '\n').encode(), b''), self.original)
        self.assertEqual(installer.include_config(changed), changed)

    def test_foreign_or_modified_include_is_rejected(self):
        for value in (b'[include u1-filament-profiles.cfg]\n', (installer.BEGIN + '\nchanged\n' + installer.END).encode()):
            with self.assertRaises(ValueError): installer.include_config(value)

    def fixture(self):
        source = self.folder / 'source'
        source.mkdir()
        (source / 'u1_filament_profiles.py').write_text('TEST_MODULE = True\n')
        printer = self.folder / 'printer.cfg'
        printer.write_bytes(self.original)
        module = self.folder / 'owned.py'
        link = self.folder / 'u1_filament_profiles.py'
        backup = self.folder / 'backup'
        return source, printer, module, link, backup

    @unittest.skipIf(os.name == 'nt', 'Real symlink install is validated on Linux U1 in isolation')
    def test_install_then_rollback_preserves_later_user_edits(self):
        source, printer, module, link, backup = self.fixture()
        with patch.object(installer, 'guard'), patch.object(installer, 'restart') as restart:
            installer.install(source, backup, printer, module, link)
            restart.assert_called_once_with(True)
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.read_bytes(), module.read_bytes())
            self.assertEqual((backup / 'printer.cfg').read_bytes(), self.original)
            printer.write_bytes(printer.read_bytes() + b'# user calibration saved after install\n')
            installer.rollback(backup)
            self.assertIn(b'# user calibration saved after install', printer.read_bytes())
            self.assertNotIn(installer.BEGIN.encode(), printer.read_bytes())
            self.assertFalse(link.exists())
            self.assertFalse(module.exists())

    @unittest.skipIf(os.name == 'nt', 'Real symlink install is validated on Linux U1 in isolation')
    def test_startup_failure_restores_original_files(self):
        source, printer, module, link, backup = self.fixture()
        module.write_bytes(b'PREVIOUS_MODULE = True\n')
        with patch.object(installer, 'guard'), patch.object(installer, 'restart', side_effect=[RuntimeError('mock startup failure'), None]):
            with self.assertRaises(RuntimeError): installer.install(source, backup, printer, module, link)
        self.assertEqual(printer.read_bytes(), self.original)
        self.assertEqual(module.read_bytes(), b'PREVIOUS_MODULE = True\n')
        self.assertFalse(link.exists())

    def test_failure_before_config_write_can_rollback(self):
        source, printer, module, link, backup = self.fixture()
        with patch.object(installer, 'guard'), patch.object(installer, 'restart'):
            real_atomic = installer.atomic
            def write(path, data, *args):
                if Path(path) == module:
                    raise OSError('mock disk failure')
                return real_atomic(path, data, *args)
            with patch.object(installer, 'atomic', side_effect=write):
                with self.assertRaises(OSError): installer.install(source, backup, printer, module, link)
        self.assertEqual(printer.read_bytes(), self.original)


if __name__ == '__main__': unittest.main()
