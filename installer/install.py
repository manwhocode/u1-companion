#!/usr/bin/env python3
"""Guided, backup-first U1 installation. Default action is a read-only check."""
import argparse
import gzip
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.request
import urllib.error

VERSION = 'v0.1.1-alpha.7'
RELEASE = 'https://github.com/manwhocode/u1-companion/releases/download/' + VERSION
CORE = '/home/lava/u1-addons/filament-ui'
UI = '/home/lava/fluidd/u1-filaments-ui'
DATA = '/userdata/u1-addons'
PRINTER = '/oem/printer_data/config/printer.cfg'
SERVICES = ['S98u1-spool-accounting', 'S97u1-ai', 'S96u1-remote', 'S99u1-alexa-bridge']
MODULES = {'u1_filament_profiles': ('u1-filament-profiles.cfg', '[u1_filament_profiles]\n'),
           'u1_dryer': ('u1-dryer.cfg', '[u1_dryer]\nchamber_sensor: cavity\n'),
           'u1_magnet_pause': ('u1-magnet-pauses.cfg', '[u1_magnet_pause]\n')}
NATIVE = {'/home/lava/printer_data/config/fluidd.cfg': 'ede05f50709c808e0775498f62e9c44a758f33c1f4684f51fb3cf0d87cb2b46e',
          '/home/lava/klipper/klippy/extras/virtual_sdcard.py': '38e769f078ee637c3393008e8d0dbb87dc4261ea1f1cd6ae9061fdb23673dc1e'}


def confirm(prompt):
    while True:
        try: answer=input(prompt).strip().casefold()
        except EOFError: raise ValueError('Confirmation input closed; operation cancelled without changes') from None
        if answer in ('y','yes','да','д','у'): return
        if answer in ('','n','no','нет','н'): raise ValueError('Operation cancelled; no changes were made')
        print('Confirmation not understood. Enter y / yes / да to continue, or n / no / нет to cancel.')


def no_links(path):
    """Check the lexical path, including every existing parent, before resolving."""
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink(): raise ValueError('Unexpected symlink: ' + str(part))
    return path


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'): raise ValueError('Insecure download redirect')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def https(url, timeout=60):
    if not url.startswith('https://'): raise ValueError('HTTPS required')
    return urllib.request.build_opener(HTTPSRedirect()).open(url, timeout=timeout)


def checksums(raw):
    result = {}
    for line in raw.decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)', line)
        if not match or match[2] in result: raise ValueError('Invalid release checksum manifest')
        result[match[2]] = match[1]
    return result


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''): digest.update(chunk)
    return digest.hexdigest()


def extract(archive, destination, limit=250 * 1024 * 1024):
    """No links, absolute paths, duplicate names, devices, or decompression bombs."""
    no_links(destination)
    if any(Path(destination).iterdir()): raise ValueError('Extraction directory must be empty')
    with tarfile.open(archive) as tar:
        members = tar.getmembers(); seen = set(); total = 0
        if len(members) > 15000: raise ValueError('Too many archive entries')
        for item in members:
            path = PurePosixPath(item.name)
            normalized = path.as_posix()
            if (not item.isfile() or not path.parts or path.is_absolute() or '..' in path.parts
                    or '\\' in item.name or ':' in item.name or normalized in seen
                    or normalized != item.name or item.size < 0): raise ValueError('Unsafe archive')
            seen.add(normalized); total += item.size
            if total > limit: raise ValueError('Archive size limit exceeded')
        for item in members:
            target = Path(destination) / item.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(item) as src, target.open('xb') as dst: shutil.copyfileobj(src, dst, 65536)


def fetch(url, target, digest):
    target = no_links(target)
    if not re.fullmatch('[0-9a-f]{64}', digest): raise ValueError('Invalid checksum')
    if target.exists() and sha(target) == digest: return target
    if not url.startswith('https://'): raise ValueError('HTTPS required')
    temporary = target.with_name(target.name + '.partial-' + secrets.token_hex(6))
    try:
        with https(url) as source, temporary.open('xb') as output:
            shutil.copyfileobj(source, output, 65536)
        if sha(temporary) != digest: raise ValueError('Download checksum mismatch: ' + target.name)
        temporary.replace(target)
    finally: temporary.unlink(missing_ok=True)
    return target


def include(raw, name):
    text = raw.decode('utf-8'); filename, config = MODULES[name]
    if filename in text:
        # Preserve the previously installed owned include, never append duplicates.
        if text.count('[include ' + filename + ']') != 1: raise ValueError('Ambiguous include: ' + filename)
        return raw
    block = '# BEGIN U1 COMPANION ' + name + '\n[include ' + filename + ']\n# END U1 COMPANION ' + name + '\n'
    marker = '#*# <---------------------- SAVE_CONFIG ---------------------->'
    return (text.replace(marker, block + '\n' + marker, 1) if marker in text else text.rstrip() + '\n\n' + block).encode()


class Transaction:
    def __init__(self, root, backup):
        self.root, self.backup, self.rows = Path(root), Path(backup), []
        self.owned = {}
        self.directories = []
        no_links(self.backup); self.backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.backup.chmod(0o700)

    @staticmethod
    def state(path):
        if path.is_symlink(): return {'link': os.readlink(path)}
        if not path.exists(): return {'missing': True}
        if not path.is_file(): raise ValueError('Target is not a regular file')
        stat = path.stat()
        return {'hash': sha(path), 'mode': stat.st_mode & 0o777, 'uid': stat.st_uid, 'gid': stat.st_gid}

    def target(self, name):
        if not name.startswith('/') or '..' in PurePosixPath(name).parts: raise ValueError('Invalid target')
        path = self.root / name.lstrip('/')
        for parent in [path.parent, *path.parent.parents]:
            if parent.is_symlink(): raise ValueError('Symlink parent: ' + str(parent))
            if parent == self.root: break
        return path

    def write(self, name, data=b'', mode=0o644, owner=None, link=None, source=None):
        path = self.target(name)
        before = self.state(path)
        after_hash = sha(source) if source else hashlib.sha256(data).hexdigest()
        self.owned[name] = {'link':link} if link is not None else {'hash':after_hash}
        self.prepare_parents(path.parent)
        if (link is not None and before == {'link': link}) or (link is None and before.get('hash') == after_hash
                and before['mode'] == mode and (not owner or (before['uid'], before['gid']) == tuple(owner))): return
        if any(row['path'] == name for row in self.rows): raise ValueError('Duplicate transaction target')
        row = {'path': name, 'old': None, 'link': None, 'after': (sha(source) if source else hashlib.sha256(data).hexdigest()) if link is None else link, 'afterLink': link is not None}
        if path.is_symlink(): row['link'] = os.readlink(path)
        elif path.exists():
            if not path.is_file(): raise ValueError('Target is not a regular file')
            stat = path.stat(); row.update(mode=stat.st_mode & 0o777, uid=stat.st_uid, gid=stat.st_gid)
            row['old'] = str(len(self.rows)); shutil.copy2(path, self.backup / row['old'])
        row['before'] = before
        self.rows.append(row); self.save()
        temp = path.with_name(path.name + '.u1-install-' + secrets.token_hex(6))
        try:
            if link is not None: temp.symlink_to(link)
            else:
                with temp.open('xb') as stream:
                    if source:
                        with Path(source).open('rb') as incoming: shutil.copyfileobj(incoming,stream,65536)
                    else: stream.write(data)
                    stream.flush(); os.fsync(stream.fileno())
                temp.chmod(mode)
                if owner and hasattr(os, 'chown'): os.chown(temp, *owner)
            if self.state(path) != before: raise ValueError('Target changed during installation: ' + name)
            os.replace(temp, path)
        finally: temp.unlink(missing_ok=True)

    @staticmethod
    def program_directory(name):
        return any(name == base or name.startswith(base + '/') for base in
                   (CORE, UI, DATA+'/alexa-bridge', DATA+'/codex-runtime', DATA+'/remote-access'))

    def prepare_parents(self, parent):
        # umask 077 protects downloads and secrets, but lava must traverse public code.
        for directory in reversed((parent, *parent.parents)):
            if directory == self.root or self.root not in directory.parents: continue
            if not directory.exists():
                directory.mkdir(mode=0o755); directory.chmod(0o755)
            else:
                name='/' + directory.relative_to(self.root).as_posix()
                mode=directory.stat().st_mode & 0o777
                if self.program_directory(name) and mode & 0o555 != 0o555:
                    self.directories.append({'path':name,'before':mode,'after':mode | 0o555})
                    self.save(); directory.chmod(mode | 0o555)

    def save(self):
        path = self.backup / 'journal.json'; temp = path.with_suffix('.next')
        with temp.open('w') as stream:
            stream.write(json.dumps({'version': 1, 'files': self.rows, 'directories':self.directories})); stream.flush(); os.fsync(stream.fileno())
        temp.chmod(0o600); temp.replace(path)

    def validate_rollback(self):
        # Validate every target before changing any of them.
        for row in getattr(self,'directories',[]):
            path=self.target(row['path'])
            if (not self.program_directory(row['path']) or path.is_symlink() or not path.is_dir()
                    or path.stat().st_mode & 0o777 not in (row['before'],row['after'])):
                raise ValueError('Changed program directory; rollback stopped: '+row['path'])
        for row in self.rows:
            path = self.target(row['path']); current = self.state(path)
            if current == row['before']: continue
            expected = current.get('missing') is True if row.get('afterMissing') else current.get('link') == row['after'] if row['afterLink'] else current.get('hash') == row['after']
            if not expected: raise ValueError('Changed target; rollback stopped: ' + row['path'])
            if row['old'] is not None and sha(no_links(self.backup / row['old'])) != row['before']['hash']:
                raise ValueError('Backup checksum mismatch')

    def rollback(self):
        self.validate_rollback()
        for row in reversed(self.rows):
            path = self.target(row['path'])
            if self.state(path) == row['before']: continue
            temp = path.with_name(path.name + '.u1-rollback-' + secrets.token_hex(6))
            if row['link'] is not None:
                temp.symlink_to(row['link']); os.replace(temp, path)
            elif row['old'] is None: path.unlink(missing_ok=True)
            else:
                shutil.copy2(self.backup / row['old'], temp); temp.chmod(row['mode'])
                if hasattr(os, 'chown'): os.chown(temp, row['uid'], row['gid'])
                os.replace(temp, path)
        for row in reversed(getattr(self,'directories',[])):
            self.target(row['path']).chmod(row['before'])

    def remove(self, name):
        path=self.target(name);before=self.state(path)
        if before.get('missing'):return
        row={'path':name,'old':None,'link':before.get('link'),'before':before,'after':None,'afterLink':False,'afterMissing':True}
        if 'hash' in before:
            row.update(mode=before['mode'],uid=before['uid'],gid=before['gid']);row['old']=str(len(self.rows));shutil.copy2(path,self.backup/row['old'])
        self.rows.append(row);self.save()
        if self.state(path)!=before:raise ValueError('Target changed during uninstall')
        path.unlink()


class Installer:
    def __init__(self, root='/', api=None, runner=None, sleep=time.sleep):
        self.root = Path(root); self.api = api or self.http; self.run = runner or self.command; self.sleep = sleep
    def p(self, name): return self.root / name.lstrip('/')
    @staticmethod
    def command(*args): return subprocess.run(args, check=True, capture_output=True, text=True).stdout
    @staticmethod
    def http(path, post=False):
        request = urllib.request.Request('http://127.0.0.1:7125' + path, method='POST' if post else 'GET')
        with urllib.request.urlopen(request, timeout=10) as response: return json.load(response)['result']

    def preflight(self):
        required = [PRINTER, '/etc/nginx/sites-available/fluidd', '/home/lava/klipper/klippy/extras/virtual_sdcard.py']
        if any(not self.p(path).is_file() or self.p(path).is_symlink() for path in required): raise ValueError('Snapmaker U1 layout not found')
        status = self.api('/printer/objects/query?webhooks&print_stats&idle_timeout&print_task_config&machine_state_manager&exception_manager&extruder&extruder1&extruder2&extruder3&heater_bed')['status']
        if (status['webhooks']['state'] != 'ready' or status['print_stats']['state'] not in ('standby','complete','cancelled')
                or status['idle_timeout']['state'] != 'Idle' or status['machine_state_manager'].get('main_state') not in (0,'IDLE')
                or status['machine_state_manager'].get('action_code') not in (0,'IDLE') or status['exception_manager'].get('exceptions', [True])
                or any(status[name]['target'] != 0 for name in ['extruder','extruder1','extruder2','extruder3','heater_bed'])):
            raise ValueError('Printer must be ready, idle, without errors and with every heater target zero')
        if any(len(status['print_task_config'].get(key, [])) != 4 for key in ['filament_type','filament_exist','filament_edit','filament_color_rgba']): raise ValueError('U1 four-head API not found')
        settings = self.api('/printer/objects/query?configfile')['status']['configfile']['settings']
        if settings.get('purifier', {}).get('external_temp_sensor') != 'cavity' or 'temperature_sensor cavity' not in settings:
            raise ValueError('Unsupported U1 chamber sensor configuration')
        cg = self.p('/sys/fs/cgroup')
        if any(not {'cpu','memory'}.issubset(set((cg/name).read_text().split())) for name in ('cgroup.controllers','cgroup.subtree_control')):
            raise ValueError('Required CPU/memory cgroup isolation is unavailable')
        active = {'schedule':('armed','starting'), 'timed-pause':('armed','pausing','waiting_pause','resuming','checking_resume'),
                  'drying':('heating','running','paused','interrupted'), 'calibration-jobs':('starting','loading','calibrating','saving','finishing'),
                  'magnet-pauses':('armed','active','pausing','waiting_insertion')}
        for folder, states in active.items():
            path = self.p(DATA + '/filament-ui-data/' + folder + '/state.json')
            if path.exists() and json.loads(path.read_text()).get('state') in states: raise ValueError('Finish/cancel active ' + folder)
        night = self.p(DATA + '/filament-ui-data/night-mode/state.json')
        if night.exists() and (json.loads(night.read_text()).get('mode') != 'off' or json.loads(night.read_text()).get('saved')): raise ValueError('Turn night mode off first')
        remote = self.p(DATA + '/remote-private/config.json')
        if remote.exists() and json.loads(remote.read_text()).get('enabled'): raise ValueError('Disable external access before updating; use local SSH')
        if any(sha(self.p(path)) != digest for path, digest in NATIVE.items()): raise ValueError('This firmware version has not been checked for full U1 Companion compatibility; no installation was performed')
        try: pending = self.api('/server/database/item?namespace=u1_addon_requests')['value']
        except urllib.error.HTTPError as error:
            if error.code != 404: raise
            pending = {}
        if pending: raise ValueError('Wait for pending Companion requests to finish')
        return status

    def layout_check(self):
        for site in self.p('/etc/nginx/sites-enabled').iterdir():
            if site.name not in ('u1-companion-local','u1-companion-remote') and re.search(r'(?m)^\s*listen\s+(?:[^;\s]*:)?(?:443|3443|8081|18088)\b', site.read_text()):
                raise ValueError('Existing HTTPS/provisioning site needs migration before unified install: ' + site.name)
        # Fail before mutation when the stock nginx layout cannot be transformed.
        self.proxy_text(self.p('/etc/nginx/sites-available/fluidd').read_text())
        for name, (filename, contents) in MODULES.items():
            path = self.p('/oem/printer_data/config/' + filename)
            if path.is_symlink() or (path.exists() and [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')] != contents.strip().splitlines()):
                raise ValueError('Modified include file: ' + filename)
            link=self.p('/home/lava/klipper/klippy/extras/'+name+'.py')
            if (link.exists() or link.is_symlink()) and (not link.is_symlink() or os.readlink(link)!=CORE+'/'+name+'.py'):
                raise ValueError('Foreign Klipper module: '+name)

    @staticmethod
    def proxy_text(text):
        # Imports are read from the verified release package, never from runtime state.
        from u1_ai.install import nginx as ai_proxy
        from u1_entry_install import config as entry_config
        return entry_config(ai_proxy(text))

    def snapshot_data(self, backup):
        """Read selected Moonraker records; no credential namespaces or DB files."""
        keys = ['u1_filament_library_v1','u1_spool_inventory_v1','u1_spool_usage_v1','u1_maintenance_v1']
        values = {}
        for key in keys:
            try: values[key] = self.api('/server/database/item?namespace=fluidd&key=' + key)['value']
            except urllib.error.HTTPError as error:
                if error.code != 404: raise
        raw = json.dumps({'format':'u1-installation-data-snapshot','records':values},ensure_ascii=False).encode()
        if len(raw) > 32*1024*1024: raise ValueError('Data snapshot exceeds size limit; export your data first')
        path = backup/'user-data.json'; path.write_bytes(raw); path.chmod(0o600)

    def ui_health(self):
        expected=self.p(UI+'/index.html').read_bytes()
        if not expected or len(expected)>256*1024: raise ValueError('Unexpected UI entry file size')
        with urllib.request.urlopen('http://127.0.0.1/u1-filaments-ui/',timeout=2) as response:
            served=response.read(len(expected)+1)
        if served!=expected: raise ValueError('UI health check failed: served entry differs from installed index.html')

    def health(self, since):
        with urllib.request.urlopen('http://127.0.0.1:4547/health',timeout=2) as response:
            if json.load(response).get('service') != 'u1-companion-ai': raise ValueError('AI health check failed')
        self.ui_health()
        c = self.api('/server/database/item?namespace=fluidd&key=u1_data_storage_v1')['value']
        usage = self.api('/server/database/item?namespace=fluidd&key=u1_spool_usage_v1')['value']
        if c.get('state') != 'ready' or c.get('updatedAt',0) < since or usage.get('checkedAt',0) < since:
            raise ValueError('No fresh accounting heartbeat')
        for directory in ['remote-private','alexa-private']:
            state = json.loads(self.p(DATA+'/'+directory+'/status.json').read_text())
            if state.get('updatedAt',0) < since: raise ValueError('No fresh ' + directory + ' heartbeat')
        for group, limits in [('ai',{'memory.max':'134217728','cpu.max':'20000 100000'}),
                              ('remote',{'memory.max':'100663296','cpu.max':'15000 100000'}),
                              ('alexa',{'memory.max':'134217728','cpu.max':'10000 100000'})]:
            cg = self.p('/sys/fs/cgroup/u1-companion-' + group)
            if any((cg/name).read_text().strip() != value for name,value in {**limits,'memory.swap.max':'0'}.items()):
                raise ValueError('Resource isolation check failed: ' + group)
        # The public gateway must require authentication even before it is enabled.
        try: urllib.request.urlopen('http://127.0.0.1:18088/server/info',timeout=2)
        except urllib.error.HTTPError as error:
            if error.code == 401 and error.headers.get('X-U1-Remote-Gateway') == 'code-v1': return
        raise ValueError('External gateway is not protected')

    def stop(self, name):
        # This helper also validates the exact program and PID start time.
        from importlib.util import spec_from_file_location, module_from_spec
        spec=spec_from_file_location('u1_service_control',Path(__file__).with_name('u1-service-stop.py'))
        module=module_from_spec(spec); spec.loader.exec_module(module)
        return module.stop(name, root=self.root, sleep=self.sleep)

    def install(self, package, work, ip, enable_persistence=False):
        import pwd
        sys.path.insert(0,str(package/'backend'))
        self.preflight(); user = pwd.getpwnam('lava'); owner = (user.pw_uid,user.pw_gid)
        self.layout_check()
        registry=self.p(CORE+'/managed-install.json')
        prior=json.loads(registry.read_text()) if registry.exists() else {'version':1,'files':{}}
        if prior.get('version')!=1 or not isinstance(prior.get('files'),dict):raise ValueError('Unknown installation registry')
        if not self.p('/oem/.debug').exists() and not enable_persistence: raise ValueError('Persistence consent required')
        backup = self.p('/userdata/u1-addons-backups/unified-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
        tx = Transaction(self.root, backup); started = []; previous = []
        print('[3/7] Saving an installation backup...')
        old_printer = self.p(PRINTER).read_bytes(); expected = old_printer; restarted=False
        try:
            for name in SERVICES:
                if self.p('/etc/init.d/' + name).exists() and self.stop(name): previous.append(name)
            self.preflight()
            self.snapshot_data(backup)
            (backup/'services.json').write_text(json.dumps(previous))
            for p in package.rglob('*'):
                if not p.is_file(): continue
                rel = p.relative_to(package).as_posix()
                if rel.startswith('backend/') and p.suffix in ('.py','.ps1','.cjs'): target = CORE + '/' + rel[len('backend/'):]
                elif rel.startswith('ui/'): target = UI + '/' + rel[len('ui/'):]
                elif rel.startswith('remote/') and p.name != 'nginx-template.conf': target = CORE + '/' + p.name
                elif rel.startswith('licenses/'): target = CORE + '/' + rel
                elif rel.startswith('runtime/'):
                    runtime_targets={'node':DATA+'/alexa-bridge/runtime/node','codex':DATA+'/codex-runtime/codex','cloudflared':DATA+'/remote-access/runtime/cloudflared'}
                    if p.name not in runtime_targets: continue
                    tx.write(runtime_targets[p.name],mode=0o755,owner=(0,0),source=p);continue
                elif rel.startswith('services/'):
                    target = '/etc/init.d/' + p.name
                elif rel.startswith('alexa/'): target = DATA + '/alexa-bridge/' + rel[len('alexa/'):]
                else: continue
                tx.write(target, mode=0o755 if rel.startswith('services/') else 0o644, owner=(0,0), source=p)
            # Root service control is also shipped beside the standalone installer.
            tx.write(CORE+'/u1-service-stop.py',mode=0o644,owner=(0,0),source=Path(__file__).with_name('u1-service-stop.py'))
            for name in ['filament-ui-data','ai-private','remote-private','alexa-private']:
                directory = self.p(DATA + '/' + name)
                no_links(directory)
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                if directory.stat().st_uid != user.pw_uid: os.chown(directory,*owner)
                directory.chmod(0o700)
            private = self.p(DATA + '/remote-private/control.key')
            if not private.exists(): tx.write(DATA + '/remote-private/control.key',secrets.token_hex(32).encode(),0o600,owner)
            control = private.read_text().strip()
            if not re.fullmatch('[0-9a-f]{64}',control): raise ValueError('Invalid existing remote control key')
            config = self.p(DATA + '/remote-private/config.json')
            if not config.exists(): tx.write(DATA + '/remote-private/config.json',b'{"authMode":"code","enabled":false}',0o600,owner)
            gateway = (package/'remote/nginx-template.conf').read_text().replace('__CONTROL_KEY__',control)
            tx.write('/etc/nginx/sites-enabled/u1-companion-remote',gateway.encode(),0o600)
            for name in MODULES:
                filename, contents = MODULES[name]; path = '/oem/printer_data/config/' + filename
                if self.p(path).exists() and [line.strip() for line in self.p(path).read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')] != contents.strip().splitlines(): raise ValueError('Modified include file: ' + filename)
                tx.write(path,('# U1 Companion\n'+contents).encode())
                link = '/home/lava/klipper/klippy/extras/' + name + '.py'
                if self.p(link).exists() or self.p(link).is_symlink():
                    if not self.p(link).is_symlink() or os.readlink(self.p(link)) != CORE+'/'+name+'.py': raise ValueError('Foreign Klipper module')
                tx.write(link,b'',link=CORE+'/'+name+'.py'); expected = include(expected,name)
            if not self.p('/oem/.debug').exists():
                if not enable_persistence: raise ValueError('Persistence consent required')
                tx.write('/oem/.debug',b'',0o600)
            # Never overwrite a concurrent native SAVE_CONFIG/edit.
            if self.p(PRINTER).read_bytes() != old_printer: raise ValueError('printer.cfg changed during installation')
            print('[4/7] Installing owned modules and local HTTPS...')
            stat=self.p(PRINTER).stat();tx.write(PRINTER,expected,stat.st_mode&0o777,(stat.st_uid,stat.st_gid))
            self.tls_and_proxy(tx, package, work, ip, owner)
            self.preflight()
            self.run('nginx','-t'); self.run('nginx','-s','reload')
            print('[5/7] Restarting idle Klipper and checking modules...')
            restarted=True;self.api('/printer/restart',True)
            for _ in range(60):
                try:
                    s = self.api('/printer/objects/query?webhooks&u1_filament_profiles&u1_dryer&u1_magnet_pause')['status']
                    if s['webhooks']['state']=='ready' and s['u1_filament_profiles'].get('version')==1 and s['u1_dryer'].get('version')==1 and s['u1_magnet_pause'].get('available'): break
                except Exception: pass
                self.sleep(1)
            else: raise ValueError('Klipper readiness check failed')
            since=time.time()
            print('[6/7] Starting services with CPU and memory limits...')
            for name in SERVICES:
                self.run('/etc/init.d/'+name,'start'); started.append(name)
            health_error=None
            for _ in range(60):
                try:
                    self.health(since); break
                except Exception as error: health_error=error
                self.sleep(1)
            else: raise ValueError('Companion service health check failed: '+str(health_error)) from health_error
            tx.write(CORE+'/managed-install.json',json.dumps({'version':1,'moduleVersion':VERSION,'files':{**prior['files'],**tx.owned}}).encode(),0o600,(0,0))
            (backup/'success.json').write_text(json.dumps({'version':VERSION,'ip':ip,'time':time.time()}))
            print('[7/7] Installation verified. Open this address in your browser:')
            print('INSTALLED:', 'http://'+ip+'/u1-filaments-ui/#/u1-filaments')
            print('Backup/rollback:', backup)
            return backup
        except BaseException as original:
            try:
                self.rollback_guard(restarted)
                # A failed start can still leave a process behind.
                for name in reversed(SERVICES):
                    if self.p('/etc/init.d/'+name).exists(): self.stop(name)
                tx.rollback()
                self.run('nginx','-t'); self.run('nginx','-s','reload')
                if restarted:self.restore_ready()
                for name in previous: self.run('/etc/init.d/'+name,'start')
            except BaseException as rollback_error:
                raise RuntimeError('Installation failed; rollback requires review. Backup: '+str(backup)+'; '+str(rollback_error)) from original
            print('Installation changes rolled back. Backup:',backup,file=sys.stderr)
            raise

    def tls_and_proxy(self, tx, package, work, ip, owner):
        # Keep existing validated certificates. Fresh installs generate unique keys.
        tls = self.p(CORE+'/tls'); staging = work/'tls'; staging.mkdir(exist_ok=True)
        for name in ['ca.key','ca.crt','server.key','server.crt']:
            if (tls/name).exists(): shutil.copy2(tls/name,staging/name)
        if not (staging/'ca.key').exists():
            self.run('openssl','req','-x509','-newkey','rsa:2048','-sha256','-nodes','-days','3650','-subj','/CN=U1 Companion Local CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign','-keyout',str(staging/'ca.key'),'-out',str(staging/'ca.crt'))
        ext=staging/'server.ext';ext.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:'+ip+',DNS:u1.local\n')
        self.run('openssl','req','-new','-newkey','rsa:2048','-nodes','-subj','/CN='+ip,'-keyout',str(staging/'server.key'),'-out',str(staging/'server.csr'))
        self.run('openssl','x509','-req','-in',str(staging/'server.csr'),'-CA',str(staging/'ca.crt'),'-CAkey',str(staging/'ca.key'),'-CAcreateserial','-days','365','-sha256','-extfile',str(ext),'-out',str(staging/'server.crt'))
        self.run('openssl','verify','-CAfile',str(staging/'ca.crt'),str(staging/'server.crt'))
        for name in ['ca.key','ca.crt','server.key','server.crt']: tx.write(CORE+'/tls/'+name,(staging/name).read_bytes(),0o600 if name.endswith('.key') else 0o644,owner if name=='server.key' else None)
        tx.write(UI+'/u1-local-ca.crt',(staging/'ca.crt').read_bytes())
        import plistlib,uuid
        der=subprocess.check_output(['openssl','x509','-in',str(staging/'ca.crt'),'-outform','DER'])
        profile={'PayloadContent':[{'PayloadCertificateFileName':'u1-local-ca.crt','PayloadContent':der,'PayloadDisplayName':'U1 Companion CA','PayloadIdentifier':'local.u1.companion.root','PayloadType':'com.apple.security.root','PayloadUUID':str(uuid.uuid4()),'PayloadVersion':1}],'PayloadDisplayName':'U1 Companion HTTPS','PayloadIdentifier':'local.u1.companion','PayloadType':'Configuration','PayloadUUID':str(uuid.uuid4()),'PayloadVersion':1}
        tx.write(UI+'/U1-Camera.mobileconfig',plistlib.dumps(profile))
        sys.path.insert(0,str(package/'backend'))
        from u1_entry_install import WRAPPER
        tx.write(CORE+'/u1-root-entry-sw.js',WRAPPER.encode())
        tx.write(UI+'/addon-status.json',json.dumps({'name':'U1 Companion','version':VERSION}).encode())
        tx.write(CORE+'/remote-config.json',b'{"endpoints":[],"hosted":false}')
        native=self.p('/etc/nginx/sites-available/fluidd');stat=native.stat()
        tx.write('/etc/nginx/sites-available/fluidd',self.proxy_text(native.read_text()).encode(),stat.st_mode&0o777,(stat.st_uid,stat.st_gid))
        template=(package/'nginx-local.conf').read_text()
        tx.write('/etc/nginx/sites-enabled/u1-companion-local',template.replace('__IP__',ip).encode())

    def rollback_guard(self, restarted):
        # A failed Klipper configuration cannot pass the normal ready check.
        # It is safe to restore that configuration, but never a running print.
        if restarted:
            info=self.api('/server/info')
            if info.get('klippy_state') in ('error','shutdown','disconnected','startup'): return
        self.preflight()

    def restore_ready(self):
        self.api('/printer/restart',True)
        for _ in range(60):
            try:
                if self.api('/printer/objects/query?webhooks')['status']['webhooks']['state']=='ready': return
            except Exception: pass
            self.sleep(1)
        raise ValueError('Restored files, but Klipper did not become ready; review the backup and printer error')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--install',action='store_true');mode.add_argument('--check',action='store_true')
    mode.add_argument('--update',action='store_true');mode.add_argument('--uninstall',action='store_true')
    p.add_argument('--yes',action='store_true');p.add_argument('--ip')
    p.add_argument('--enable-persistence',action='store_true');p.add_argument('--rollback',type=Path)
    p.add_argument('--download-dir',type=Path,default=Path('/userdata/u1-addons/downloads/'+VERSION))
    args=p.parse_args()
    if platform.system()!='Linux' or platform.machine() not in ('aarch64','arm64') or os.geteuid()!=0: raise ValueError('Run as root over SSH on Snapmaker U1 (Linux ARM64)')
    if sys.version_info < (3,11): raise ValueError('Stock Python 3.11 or newer is required')
    os.umask(0o077)
    # Do not let two install/rollback sessions race. A read-only check needs no lock.
    if args.install or args.update or args.uninstall or args.rollback:
        import fcntl
        lock_path=no_links('/run/u1-companion-install.lock')
        lock=lock_path.open('a');lock_path.chmod(0o600)
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('Another Companion installer is already running')
    for command in ['nginx','openssl','start-stop-daemon','python3']:
        if not shutil.which(command): raise ValueError('Missing required stock dependency: '+command)
    installer=Installer()
    if args.uninstall:
        with https(RELEASE+'/SHA256SUMS',timeout=30) as response:checks=checksums(response.read(16384))
        module_path=fetch(RELEASE+'/uninstall.py',Path(__file__).with_name('uninstall.py'),checks['uninstall.py'])
        from importlib.util import spec_from_file_location,module_from_spec
        spec=spec_from_file_location('u1_uninstall',module_path);module=module_from_spec(spec);spec.loader.exec_module(module)
        module.uninstall(installer,args.yes);return
    if args.update:
        if not installer.p(UI+'/index.html').is_file():raise ValueError('U1 Companion is not installed; choose Install')
        args.install=True
    if args.rollback:
        backup=no_links(args.rollback).resolve()
        if backup.parent!=Path('/userdata/u1-addons-backups') or not backup.name.startswith('unified-'): raise ValueError('Use the exact unified backup path')
        installer.rollback_guard(True)
        journal=json.loads((backup/'journal.json').read_text());tx=Transaction.__new__(Transaction);tx.root=Path('/');tx.backup=backup;tx.rows=journal['files'];tx.directories=journal.get('directories',[])
        # Backups are root-only; do not accept journals that target unrelated paths.
        allowed=[CORE+'/',UI+'/',DATA+'/', '/etc/init.d/S9','/etc/nginx/sites-enabled/u1-companion','/home/lava/klipper/klippy/extras/u1_','/oem/printer_data/config/u1-']
        if any(row['path'] not in (PRINTER,'/oem/.debug','/etc/nginx/sites-available/fluidd') and not any(row['path'].startswith(a) for a in allowed) for row in tx.rows): raise ValueError('Invalid rollback journal')
        if journal.get('version')!=1 or any(row['old'] is not None and not re.fullmatch('[0-9]+',row['old']) for row in tx.rows): raise ValueError('Invalid backup file reference')
        tx.validate_rollback()
        if not args.yes: confirm('Restore this installation backup and restart idle Klipper? [y/N] ')
        previous=json.loads((backup/'services.json').read_text())
        if not isinstance(previous,list) or any(name not in SERVICES for name in previous): raise ValueError('Invalid service backup')
        for name in SERVICES:
            if installer.p('/etc/init.d/'+name).exists(): installer.stop(name)
        tx.rollback();installer.run('nginx','-t');installer.run('nginx','-s','reload');installer.restore_ready()
        for name in previous: installer.run('/etc/init.d/'+name,'start')
        print('Installation files restored; current user data preserved');return
    print('[1/7] Checking the printer and firmware...')
    installer.preflight()
    if not args.ip:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock: sock.connect(('198.51.100.1',9));args.ip=sock.getsockname()[0]
    args.ip=str(ipaddress.IPv4Address(args.ip))
    if ipaddress.ip_address(args.ip).is_loopback: raise ValueError('Specify printer LAN IP with --ip')
    print('Compatible idle U1:',args.ip, '| full installation')
    if not args.install: print('Read-only check passed. Add --install to install.');return
    needs_persistence=not Path('/oem/.debug').exists()
    if needs_persistence: print('Persistence: /oem/.debug will be enabled so Companion survives reboot. Other system changes will also persist.')
    if needs_persistence and args.yes and not args.enable_persistence: raise ValueError('Unattended installation requires --enable-persistence')
    print('Will back up owned files, add owned config includes, install local HTTPS, and restart idle Klipper. No print/heating/motion commands.')
    if not args.yes: confirm('Install U1 Companion? [y/N] ')
    if needs_persistence: args.enable_persistence=True
    minimum=1500*1024*1024
    if shutil.disk_usage('/userdata').free<minimum: raise ValueError('At least 1.5 GiB free /userdata space is needed for installation and backup; no existing files were deleted')
    directory=no_links(args.download_dir)
    if not directory.resolve().is_relative_to(Path('/userdata/u1-addons/downloads')): raise ValueError('Unsafe download directory')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700);directory.chmod(0o700)
    # SHA256SUMS is fetched from this fixed release over verified HTTPS.
    with https(RELEASE+'/SHA256SUMS',timeout=30) as response: checks=checksums(response.read(16384))
    # Direct invocation and the shell bootstrap use the same verified helper.
    fetch(RELEASE+'/u1-service-stop.py',Path(__file__).with_name('u1-service-stop.py'),checks['u1-service-stop.py'])
    payload=fetch(RELEASE+'/u1-companion.tar.gz',directory/'u1-companion.tar.gz',checks['u1-companion.tar.gz'])
    print('[2/7] Downloading and verifying full application components...')
    work=directory/('staging-'+secrets.token_hex(8));work.mkdir(mode=0o700);package=work/'package';package.mkdir();extract(payload,package)
    runtimes=['node-runtime.tar.gz','cloudflared-linux-arm64','codex-arm64.gz']
    runtime_plan=[]
    for name in runtimes:
        print('Download/verify:',name)
        file=fetch(RELEASE+'/'+name,directory/name,checks[name]);runtime_plan.append((name,file))
    # Prepare runtime files on persistent storage; never decompress large files in RAM or /tmp.
    for name,file in runtime_plan:
        if name=='node-runtime.tar.gz':
            with tarfile.open(file) as archive:
                member=archive.getmember('node-v22.23.4-linux-arm64/bin/node');target=package/'runtime/node';target.parent.mkdir(exist_ok=True)
                with archive.extractfile(member) as src,target.open('wb') as dst: shutil.copyfileobj(src,dst,65536)
        elif name=='codex-arm64.gz':
            target=package/'runtime/codex'
            with gzip.open(file,'rb') as src,target.open('wb') as dst: shutil.copyfileobj(src,dst,65536)
        else: shutil.copy2(file,package/'runtime/cloudflared')
    # Runtime bytes join the same transaction and private ownership rules.
    try:
        installer.install(package,work,args.ip,args.enable_persistence)
    finally:
        # Only this invocation's generated staging directory is disposable.
        no_links(work)
        if work.parent!=directory or not re.fullmatch('staging-[0-9a-f]{16}',work.name): raise ValueError('Unsafe staging cleanup')
        shutil.rmtree(work)
    # Verified compressed runtime caches are replaceable; backups are retained.
    for name,_ in runtime_plan: no_links(directory/name).unlink(missing_ok=True)


if __name__=='__main__':
    try: main()
    except Exception as error: print('INSTALLATION STOPPED:',str(error),file=sys.stderr);sys.exit(1)
