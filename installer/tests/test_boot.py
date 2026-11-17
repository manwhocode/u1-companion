"""Regression for init filename expansion before U1's overlay pivot."""
import importlib.util
from pathlib import Path
import sys
import os
import shlex
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'installer'))
import install as installer
spec=importlib.util.spec_from_file_location('boot_starter',REPO/'backend/u1-boot-start.py')
boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)


class Boot(unittest.TestCase):
    @unittest.skipUnless(os.name=='posix','POSIX boot-shell check runs on Linux CI')
    def test_existing_init_keeps_native_exit_and_only_launches_on_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);marker=root/'started';recorder=root/'record.py'
            recorder.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("started")\n')
            raw=installer.with_hook(b'#!/bin/sh\nexit 7\n').decode()
            raw=raw.replace('/home/lava/u1-addons/filament-ui/u1-boot-start.py',shlex.quote(str(recorder)))
            raw=raw.replace('/usr/bin/python3',shlex.quote(sys.executable))
            raw=raw.replace('/run/u1-companion-boot.log',shlex.quote(str(root/'boot.log')))
            script=root/'native-init';script.write_text(raw)
            self.assertEqual(subprocess.run(['sh',str(script),'stop']).returncode,7)
            self.assertFalse(marker.exists())
            self.assertEqual(subprocess.run(['sh',str(script),'start']).returncode,7)
            deadline=time.monotonic()+3
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(marker.exists())

    def test_hook_is_idempotent_and_reversible_without_changing_native_script(self):
        native=b'#! /bin/sh\n[ -f /usr/bin/input-event-daemon ] || exit 0\nexit 7\n'
        patched=installer.with_hook(native)
        self.assertLess(patched.index(installer.BOOT_BEGIN.encode()),patched.index(b'[ -f /usr/bin'))
        self.assertEqual(installer.with_hook(patched),patched)
        self.assertEqual(installer.without_hook(patched),native)
        self.assertEqual(installer.without_hook(patched+b'# user edit\n'),native+b'# user edit\n')

    def test_modified_hook_is_not_silently_overwritten(self):
        patched=installer.with_hook(b'#!/bin/sh\nexit 0\n')
        for invalid in (patched.replace(b'u1-boot-start.py',b'changed.py',1),patched+installer.BOOT_BLOCK.encode()):
            with self.assertRaises(ValueError):installer.with_hook(invalid)
            with self.assertRaises(ValueError):installer.without_hook(invalid)

    def test_overlay_pivot_starts_missing_owned_services_once(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);init=root/'etc/init.d';init.mkdir(parents=True)
            native=init/Path(installer.BOOT_TARGET).name
            native.write_bytes(b'#!/bin/sh\nexit 0\n')
            (init/'S60klipper').write_text('# native')
            original_init_list=tuple(init.glob('S??*'))
            # S01aoverlayfs restores these only AFTER rcS expands its list.
            for name in boot.SERVICES:(init/name).write_text('# owned')
            self.assertTrue(all(init/name not in original_init_list for name in boot.SERVICES))
            self.assertIn(native,original_init_list)
            native.write_bytes(installer.with_hook(native.read_bytes()))
            self.assertIn(b'u1-boot-start.py',native.read_bytes())
            calls=[]
            def run(args,**kwargs):
                name=Path(args[0]).name;calls.append(name)
                self.assertEqual(args[1:],['start'])
                pidname,programs,_=boot.SERVICES[name];pid=100+len(calls)
                p=root/('run/'+pidname+'.pid');p.parent.mkdir(exist_ok=True);p.write_text(str(pid))
                p=root/('proc/'+str(pid));p.mkdir(parents=True)
                (p/'cmdline').write_bytes(b'/usr/bin/python3\0'+programs[0].encode()+b'\0')
                return SimpleNamespace(returncode=0)
            self.assertTrue(all(r['state']=='start_requested' for r in boot.start_missing(root,run)))
            self.assertCountEqual(calls,boot.SERVICES)
            self.assertTrue(all(r['state']=='already_running' for r in boot.start_missing(root,run)))
            self.assertEqual(len(calls),4)

    def test_foreign_pid_and_orphan_group_are_left_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'etc/init.d').mkdir(parents=True);(root/'run').mkdir()
            for name in boot.SERVICES:(root/'etc/init.d'/name).write_text('# owned')
            (root/'run/u1-spool-accounting.pid').write_text('77')
            p=root/'proc/77';p.mkdir(parents=True);(p/'cmdline').write_bytes(b'/usr/bin/klipper\0')
            p=root/'sys/fs/cgroup/u1-companion-ai';p.mkdir(parents=True);(p/'cgroup.procs').write_text('88')
            calls=[]
            def run(args,**kwargs):calls.append(Path(args[0]).name);return SimpleNamespace(returncode=0)
            results=boot.start_missing(root,run)
            self.assertEqual([r['state'] for r in results[:2]],['error','error'])
            self.assertNotIn('S98u1-spool-accounting',calls);self.assertNotIn('S97u1-ai',calls)
            self.assertEqual((root/'run/u1-spool-accounting.pid').read_text(),'77')


if __name__=='__main__':unittest.main()
