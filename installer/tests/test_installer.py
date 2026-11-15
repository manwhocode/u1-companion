"""Isolated filesystem/API simulation; never contacts or controls a printer."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch
import urllib.error

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'installer'))
sys.path.insert(0, str(REPO/'backend'))
import install as m
spec=importlib.util.spec_from_file_location('service_stop',REPO/'installer/u1-service-stop.py')
stopper=importlib.util.module_from_spec(spec);spec.loader.exec_module(stopper)


def symlinks_available():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'link'
        try:p.symlink_to('missing');p.unlink();return True
        except OSError:return False


LINKS=symlinks_available()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'printer';self.root.mkdir()
        self.package=Path(self.tmp.name)/'package';self.package.mkdir()
        self.work=Path(self.tmp.name)/'work';self.work.mkdir()
        self.commands=[];self.posts=[];self.live={};self.health_failure=False;self.nginx_failure=False
        self.status={'webhooks':{'state':'ready'},'print_stats':{'state':'standby'},
                     'idle_timeout':{'state':'Idle'},'machine_state_manager':{'main_state':0,'action_code':0},
                     'exception_manager':{'exceptions':[]},'print_task_config':{k:[False]*4 for k in ['filament_type','filament_exist','filament_edit','filament_color_rgba']}}
        for n in ['extruder','extruder1','extruder2','extruder3','heater_bed']:self.status[n]={'target':0}
        self.put(m.PRINTER,b'# Native user config\n[printer]\nkinematics: corexy\n')
        self.put('/etc/nginx/sites-available/fluidd',b'server {\n    listen 80;\n    location / {\n        root /home/lava/fluidd;\n    }\n}\n')
        self.p('/etc/nginx/sites-enabled').mkdir()
        self.put('/home/lava/klipper/klippy/extras/virtual_sdcard.py',b'# stock virtual sd\n')
        self.put('/home/lava/printer_data/config/fluidd.cfg',b'# stock pause macros\n')
        for name in ['cgroup.controllers','cgroup.subtree_control']:self.put('/sys/fs/cgroup/'+name,b'cpu memory io\n')
        self.native={name:m.sha(self.p(name)) for name in m.NATIVE}
        self.addCleanup(patch.stopall);patch.object(m,'NATIVE',self.native).start()
        if hasattr(os,'chown'):patch.object(os,'chown',lambda *args:None).start()
        patch.dict(sys.modules,{'pwd':types.SimpleNamespace(getpwnam=lambda name:types.SimpleNamespace(pw_uid=0,pw_gid=0))}).start()
        # These source bytes are verified public fixtures, not a live device export.
        for name in ['u1_entry_install.py','u1_ai/install.py','u1_ai/__init__.py']:
            p=self.package/'backend'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPO/'backend'/name,p)
        for name in m.MODULES:self.package_file('backend/'+name+'.py',b'# fixture module\n')
        self.package_file('backend/spool-accounting.py',b'# fixture accounting\n')
        self.package_file('ui/index.html',b'<title>U1 Companion</title>')
        self.package_file('ui/config.json',b'{"endpoints":[],"hosted":false}')
        for name in m.SERVICES:self.package_file('services/'+name,b'#!/bin/sh\n# fixture service\n')
        self.package_file('alexa/bridge.cjs',b'// fixture bridge\n')
        for name in ['node','codex','cloudflared']:self.package_file('runtime/'+name,b'fixture-runtime-'+name.encode())
        self.package_file('remote/nginx-template.conf',(REPO/'remote-access/nginx-template.conf').read_bytes())
        self.package_file('nginx-local.conf',(REPO/'installer/nginx-local.conf').read_bytes())
        self.inst=m.Installer(self.root,self.api,self.command,sleep=lambda _:None)
        self.inst.health=self.health;self.inst.stop=self.stop;self.inst.tls_and_proxy=self.tls

    def p(self,name):return self.root/name.lstrip('/')
    def put(self,name,data):
        p=self.p(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
    def package_file(self,name,data):
        p=self.package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    def api(self,path,post=False):
        if post:self.posts.append(path);return 'ok'
        if path=='/server/info':return {'klippy_state':'ready'}
        if path.endswith('?configfile'):return {'status':{'configfile':{'settings':{'purifier':{'external_temp_sensor':'cavity'},'temperature_sensor cavity':{}}}}}
        if 'u1_filament_profiles&' in path:return {'status':{'webhooks':{'state':'ready'},'u1_filament_profiles':{'version':1},'u1_dryer':{'version':1},'u1_magnet_pause':{'available':True}}}
        if path.startswith('/printer/objects/query?'):return {'status':copy.deepcopy(self.status)}
        if 'database/item?' in path:
            if path.endswith('namespace=u1_addon_requests'):return {'value':{}}
            raise urllib.error.HTTPError(path,404,'missing',{},None)
        raise AssertionError(path)
    def command(self,*args):
        self.commands.append(args)
        if args[:2]==('nginx','-t') and self.nginx_failure:
            self.nginx_failure=False;raise RuntimeError('injected nginx failure')
        if args[0].startswith('/etc/init.d/'):self.live[Path(args[0]).name]=True
        return ''
    def stop(self,name):return self.live.pop(name,False)
    def tls(self,tx,package,work,ip,owner):
        raw=self.p('/etc/nginx/sites-available/fluidd').read_text()
        tx.write('/etc/nginx/sites-available/fluidd',self.inst.proxy_text(raw).encode())
        tx.write('/etc/nginx/sites-enabled/u1-companion-local',b'# fixture TLS proxy\n')
        tx.write(m.UI+'/addon-status.json',b'{"name":"U1 Companion"}')
    def health(self,since):
        if self.health_failure:raise ValueError('injected health failure')
        if set(self.live)!=set(m.SERVICES):raise ValueError('missing service')
    def tx(self):return m.Transaction(self.root,Path(self.tmp.name)/'backup')


class Guards(Fixture):
    def test_idle_compatible_read_only(self):
        original=self.p(m.PRINTER).read_bytes();self.inst.preflight()
        self.assertEqual(self.posts,[]);self.assertEqual(self.commands,[]);self.assertEqual(original,self.p(m.PRINTER).read_bytes())
    def test_busy_paused_heating_errors_are_rejected_without_mutation(self):
        cases=[('print_stats','state','printing'),('print_stats','state','paused'),('extruder1','target',200),
               ('heater_bed','target',60),('exception_manager','exceptions',[1]),('webhooks','state','shutdown'),
               ('idle_timeout','state','Printing'),('machine_state_manager','action_code',10)]
        for section,key,value in cases:
            with self.subTest(section=section,key=key,value=value):
                old=self.status[section][key];self.status[section][key]=value
                with self.assertRaises(ValueError):self.inst.preflight()
                self.status[section][key]=old
        self.assertFalse(self.posts or self.commands)
    def test_unknown_firmware_rejected(self):
        self.put('/home/lava/klipper/klippy/extras/virtual_sdcard.py',b'other firmware')
        with self.assertRaisesRegex(ValueError,'firmware'):self.inst.preflight()
    def test_active_jobs_and_external_access_block_installation(self):
        for folder,state in [('schedule','armed'),('drying','running'),('timed-pause','armed'),('calibration-jobs','calibrating'),('magnet-pauses','active')]:
            p=self.put(m.DATA+'/filament-ui-data/'+folder+'/state.json',json.dumps({'state':state}).encode())
            with self.assertRaises(ValueError):self.inst.preflight()
            p.unlink()
        self.put(m.DATA+'/remote-private/config.json',b'{"enabled":true}')
        with self.assertRaisesRegex(ValueError,'external access'):self.inst.preflight()
    def test_no_memory_isolation_rejected(self):
        self.put('/sys/fs/cgroup/cgroup.controllers',b'cpu')
        with self.assertRaisesRegex(ValueError,'isolation'):self.inst.preflight()
    def test_existing_foreign_https_is_not_overwritten(self):
        self.put('/etc/nginx/sites-enabled/custom',b'server {\n listen [::]:443 ssl;\n}')
        with self.assertRaisesRegex(ValueError,'migration'):self.inst.layout_check()
    def test_persistence_consent_before_writes(self):
        with self.assertRaisesRegex(ValueError,'consent'):self.inst.install(self.package,self.work,'192.168.1.100')
        self.assertFalse(self.p('/oem/.debug').exists());self.assertFalse(self.p(m.CORE).exists())
    def test_failed_restart_configuration_can_be_rolled_back(self):
        self.inst.api=lambda path,post=False:{'klippy_state':'error'} if path=='/server/info' else (_ for _ in ()).throw(ValueError('not ready'))
        self.inst.rollback_guard(True)


class Transactions(Fixture):
    def test_restores_existing_and_removes_new_files(self):
        self.put('/owned/file',b'before');tx=self.tx();tx.write('/owned/file',b'after');tx.write('/owned/new',b'new')
        tx.rollback();self.assertEqual(self.p('/owned/file').read_bytes(),b'before');self.assertFalse(self.p('/owned/new').exists())
    def test_rollback_refuses_all_changes_if_any_target_changed(self):
        tx=self.tx();tx.write('/owned/a',b'a');tx.write('/owned/b',b'b');self.put('/owned/a',b'user edit')
        with self.assertRaisesRegex(ValueError,'Changed target'):tx.rollback()
        self.assertEqual(self.p('/owned/b').read_bytes(),b'b')
    def test_failed_atomic_replace_preserves_old_bytes(self):
        self.put('/owned/file',b'before');tx=self.tx();real=os.replace
        def fail(src,dst):
            if Path(dst)==self.p('/owned/file'):raise OSError('injected disk failure')
            return real(src,dst)
        with patch.object(m.os,'replace',side_effect=fail):
            with self.assertRaises(OSError):tx.write('/owned/file',b'after')
        tx.rollback();self.assertEqual(self.p('/owned/file').read_bytes(),b'before')
        self.assertEqual(list(self.p('/owned').glob('*.u1-install-*')),[])
    def test_streams_large_source_without_read_bytes(self):
        source=Path(self.tmp.name)/'runtime';source.write_bytes(b'x'*1000000);tx=self.tx()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('whole file read')):tx.write('/owned/runtime',source=source)
        self.assertEqual(m.sha(source),m.sha(self.p('/owned/runtime')))
    @unittest.skipUnless(LINKS,'OS symlink privilege required; covered on Linux CI')
    def test_symlink_rollback_and_symlink_parent_refusal(self):
        self.p('/link').symlink_to('/old-target');tx=self.tx();tx.write('/link',link='/new-target');tx.rollback()
        self.assertEqual(os.readlink(self.p('/link')),'/old-target')
        self.p('/unsafe').symlink_to(self.work,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Symlink parent'):tx.write('/unsafe/file',b'no')
    @unittest.skipUnless(LINKS,'OS symlink privilege required; covered on Linux CI')
    def test_failed_new_symlink_write_can_rollback(self):
        tx=self.tx();real=os.replace
        def fail(src,dst):
            if Path(dst)==self.p('/new-link'):raise OSError('injected disk failure')
            return real(src,dst)
        with patch.object(m.os,'replace',side_effect=fail):
            with self.assertRaises(OSError):tx.write('/new-link',link='/target')
        tx.rollback();self.assertFalse(self.p('/new-link').is_symlink())


class Archives(Fixture):
    def archive(self,names):
        p=Path(self.tmp.name)/'payload.tar.gz'
        with tarfile.open(p,'w:gz') as tar:
            for name,kind in names:
                info=tarfile.TarInfo(name);info.type=kind;info.size=1 if kind==tarfile.REGTYPE else 0;info.linkname='../outside'
                tar.addfile(info,io.BytesIO(b'x') if info.size else None)
        return p
    def test_traversal_links_duplicates_and_noncanonical_names_rejected(self):
        cases=[[('../escape',tarfile.REGTYPE)],[('/absolute',tarfile.REGTYPE)],[('a',tarfile.SYMTYPE)],
               [('a',tarfile.REGTYPE),('a',tarfile.REGTYPE)],[('a/./b',tarfile.REGTYPE)],[('a\\b',tarfile.REGTYPE)]]
        for names in cases:
            with self.subTest(names=names):
                with self.assertRaises(ValueError):m.extract(self.archive(names),self.work)
                self.assertEqual(list(self.work.iterdir()),[])
    def test_size_limit(self):
        with self.assertRaisesRegex(ValueError,'size limit'):m.extract(self.archive([('a',tarfile.REGTYPE)]),self.work,limit=0)
    def test_valid_archive(self):
        m.extract(self.archive([('backend/a.py',tarfile.REGTYPE)]),self.work)
        self.assertEqual((self.work/'backend/a.py').read_bytes(),b'x')
    def test_corrupt_download_does_not_replace_existing(self):
        dest=Path(self.tmp.name)/'download';dest.write_bytes(b'old')
        with patch.object(m,'https',return_value=io.BytesIO(b'corrupt')):
            with self.assertRaisesRegex(ValueError,'checksum'):m.fetch('https://example.test/payload',dest,'1'*64)
        self.assertEqual(dest.read_bytes(),b'old');self.assertEqual(list(dest.parent.glob('*.partial-*')),[])
    def test_manifest_and_https_redirect_validation(self):
        with self.assertRaises(ValueError):m.checksums(b'abc  payload')
        with self.assertRaises(ValueError):m.checksums(('1'*64+'  ../payload').encode())
        with self.assertRaises(ValueError):m.HTTPSRedirect().redirect_request(None,None,302,'',{},'http://example.test/a')


@unittest.skipUnless(LINKS,'OS symlink privilege required; covered on Linux CI')
class FullInstallation(Fixture):
    def test_fresh_install_full_components_and_empty_user_libraries(self):
        stock={name:self.p(name).read_bytes() for name in self.native}
        backup=self.inst.install(self.package,self.work,'192.168.1.100',enable_persistence=True)
        self.assertTrue((backup/'success.json').exists());self.assertEqual(self.posts,['/printer/restart'])
        self.assertEqual(set(self.live),set(m.SERVICES))
        for path in ['/alexa-bridge/runtime/node','/codex-runtime/codex','/remote-access/runtime/cloudflared']:self.assertTrue(self.p(m.DATA+path).is_file())
        for name,raw in stock.items():self.assertEqual(self.p(name).read_bytes(),raw)
        self.assertEqual(json.loads((backup/'user-data.json').read_text())['records'],{})
        self.assertEqual(json.loads(self.p(m.UI+'/config.json').read_text())['endpoints'],[])
        self.assertFalse(json.loads(self.p(m.DATA+'/remote-private/config.json').read_text())['enabled'])
        self.assertFalse(self.p(m.DATA+'/ai-private/settings.json').exists())
        self.assertFalse(self.p(m.DATA+'/alexa-private/auth.json').exists())
    def test_nginx_failure_restores_printer_and_native_site(self):
        before=self.p(m.PRINTER).read_bytes();site=self.p('/etc/nginx/sites-available/fluidd').read_bytes();self.nginx_failure=True
        with self.assertRaisesRegex(RuntimeError,'injected nginx'):self.inst.install(self.package,self.work,'192.168.1.100',True)
        self.assertEqual(self.p(m.PRINTER).read_bytes(),before);self.assertEqual(self.p('/etc/nginx/sites-available/fluidd').read_bytes(),site)
        self.assertFalse(self.p('/oem/.debug').exists());self.assertEqual(self.posts,[])
    def test_health_failure_stops_all_and_rolls_back(self):
        self.health_failure=True;before=self.p(m.PRINTER).read_bytes()
        with self.assertRaisesRegex(ValueError,'health check'):self.inst.install(self.package,self.work,'192.168.1.100',True)
        self.assertEqual(self.p(m.PRINTER).read_bytes(),before);self.assertFalse(self.live)
        self.assertEqual(self.posts,['/printer/restart','/printer/restart'])
    def test_user_inventory_and_credentials_are_preserved(self):
        files={m.DATA+'/filament-ui-data/current.json':b'{"fixture":"user inventory"}',m.DATA+'/ai-private/settings.json':b'{"fixture":"private API config"}',m.DATA+'/alexa-private/auth.json':b'{"fixture":"private Amazon config"}'}
        for name,raw in files.items():self.put(name,raw)
        self.inst.install(self.package,self.work,'192.168.1.100',True)
        for name,raw in files.items():self.assertEqual(self.p(name).read_bytes(),raw)


class StopService(Fixture):
    def proc(self,pid,program,start='123'):
        self.put('/proc/'+str(pid)+'/cmdline',b'/usr/bin/python3\0'+program.encode()+b'\0')
        self.put('/proc/'+str(pid)+'/stat',(str(pid)+' (python3) '+' '.join(['S']+['0']*18+[start])).encode())
        self.put('/run/u1-spool-accounting.pid',str(pid).encode())
    def test_foreign_pid_is_never_signalled(self):
        self.proc(42,'/native/klipper.py');signals=[]
        with self.assertRaisesRegex(ValueError,'Foreign PID'):stopper.stop('S98u1-spool-accounting',self.root,lambda _:None,lambda *args:signals.append(args))
        self.assertFalse(signals);self.assertTrue(self.p('/run/u1-spool-accounting.pid').exists())
    def test_identified_owned_process_stops(self):
        self.proc(42,m.CORE+'/spool-accounting.py');signals=[]
        def kill(pid,sig):signals.append((pid,sig));shutil.rmtree(self.p('/proc/'+str(pid)))
        self.assertTrue(stopper.stop('S98u1-spool-accounting',self.root,lambda _:None,kill))
        self.assertEqual(len(signals),1);self.assertFalse(self.p('/run/u1-spool-accounting.pid').exists())
    def test_stale_pid_file_is_removed_without_signal(self):
        self.put('/run/u1-spool-accounting.pid',b'42');signals=[]
        self.assertFalse(stopper.stop('S98u1-spool-accounting',self.root,lambda _:None,lambda *args:signals.append(args)))
        self.assertFalse(signals)


@unittest.skipUnless(shutil.which('openssl'),'OpenSSL integration check runs on Linux CI')
class Certificates(Fixture):
    def test_unique_local_ca_valid_chain_and_neutral_entry_configuration(self):
        def command(*args):
            if args[0]=='openssl':return subprocess.run(args,check=True,capture_output=True,text=True).stdout
            return self.command(*args)
        self.inst.run=command
        tx=self.tx()
        m.Installer.tls_and_proxy(self.inst,tx,self.package,self.work,'192.168.1.100',(0,0))
        tls=self.p(m.CORE+'/tls')
        subprocess.run(['openssl','verify','-CAfile',str(tls/'ca.crt'),str(tls/'server.crt')],check=True,capture_output=True)
        cert=subprocess.check_output(['openssl','x509','-in',str(tls/'server.crt'),'-noout','-ext','subjectAltName'],text=True)
        self.assertIn('192.168.1.100',cert)
        self.assertNotEqual((tls/'ca.key').read_bytes(),(tls/'server.key').read_bytes())
        site=self.p('/etc/nginx/sites-available/fluidd').read_text()
        self.assertIn('/u1-filaments-ui/',site);self.assertIn('/u1-ai/api/',site)
        self.assertEqual(json.loads(self.p(m.CORE+'/remote-config.json').read_text())['endpoints'],[])


if __name__=='__main__':unittest.main()
