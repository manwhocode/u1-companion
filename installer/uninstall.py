"""Remove only inventoried Companion files; preserve all personal state."""
from pathlib import Path
import json,re,secrets,shutil,time
from install import CORE,UI,DATA,PRINTER,MODULES,SERVICES,Transaction,sha,no_links,confirm,BOOT_TARGET,without_hook


def allowed(name):
    exact={PRINTER,BOOT_TARGET,'/oem/.debug','/etc/nginx/sites-available/fluidd',
           '/etc/nginx/sites-enabled/u1-companion-local','/etc/nginx/sites-enabled/u1-companion-remote'}
    exact.update('/etc/init.d/'+s for s in SERVICES)
    exact.update('/oem/printer_data/config/'+v[0] for v in MODULES.values())
    exact.update('/home/lava/klipper/klippy/extras/'+name+'.py' for name in MODULES)
    return name in exact or any(name.startswith(p) for p in (CORE+'/',UI+'/',DATA+'/alexa-bridge/',DATA+'/codex-runtime/',DATA+'/remote-access/'))


def preserve(name):
    return name=='/oem/.debug' or name==UI+'/config.json' or name.startswith(CORE+'/tls/') or any(name.startswith(DATA+'/'+d+'/') for d in ('filament-ui-data','ai-private','alexa-private','remote-private'))


def strip_block(text,begin,end):
    if begin not in text and end not in text:return text
    if text.count(begin)!=1 or text.count(end)!=1:raise ValueError('Ambiguous add-on config block')
    start=text.index(begin);finish=text.index(end)+len(end)
    if finish<=start:raise ValueError('Invalid add-on config block')
    return text[:start]+text[finish:]


def config_without_addon(raw):
    text=raw.decode()
    for name,(filename,_) in MODULES.items():
        begin='# BEGIN U1 COMPANION '+name+'\n';end='# END U1 COMPANION '+name+'\n'
        text=strip_block(text,begin,end)
        if filename in text:raise ValueError('Unrecognized module include; removal stopped: '+filename)
    return text.encode()


def nginx_without_addon(raw):
    text=raw.decode()
    for name in ('U1 ADDON ENTRY','U1 COMPANION AI'):
        text=strip_block(text,'    # BEGIN '+name+'\n','    # END '+name+'\n')
    return text.encode()


def uninstall(inst,yes=False):
    inst.preflight()
    registry=inst.p(CORE+'/managed-install.json');no_links(registry)
    if not registry.is_file():raise ValueError('This installation has no safe removal inventory. Update using the unified installer first; legacy/manual installations need migration review.')
    record=json.loads(registry.read_text())
    if record.get('version')!=1 or not isinstance(record.get('files'),dict):raise ValueError('Unsupported removal inventory')
    changes={PRINTER:config_without_addon(inst.p(PRINTER).read_bytes()),'/etc/nginx/sites-available/fluidd':nginx_without_addon(inst.p('/etc/nginx/sites-available/fluidd').read_bytes())}
    if BOOT_TARGET in record['files']:
        no_links(inst.p(BOOT_TARGET))
        changes[BOOT_TARGET]=without_hook(inst.p(BOOT_TARGET).read_bytes())
    files=[]
    for name,expected in record['files'].items():
        if preserve(name):continue
        if not allowed(name):raise ValueError('Invalid inventoried path')
        if name in changes:continue
        path=inst.p(name)
        # Validate every owned file before stopping services or changing files.
        current=Transaction.state(path)
        if current.get('missing'):continue
        if ('link' in expected and current.get('link')!=expected['link']) or ('hash' in expected and current.get('hash')!=expected['hash']):raise ValueError('Modified owned file; removal stopped: '+name)
        files.append(name)
    print('Will stop Companion services, back up/remove owned program files, restore native Fluidd routes and restart idle Klipper.')
    print('Personal libraries, logs, credentials, certificates and /oem/.debug persistence are retained. No print, heat or movement commands.')
    if not yes:confirm('Uninstall U1 Companion? [y/N] ')
    size=sum(inst.p(n).stat().st_size for n in files if inst.p(n).is_file() and not inst.p(n).is_symlink())
    if shutil.disk_usage(inst.p('/userdata')).free<size+100*1024*1024:raise ValueError('Not enough space for removal backup')
    backup=inst.p('/userdata/u1-addons-backups/uninstall-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
    tx=Transaction(inst.root,backup);previous=[];restarted=False
    try:
        for service in SERVICES:
            if inst.p('/etc/init.d/'+service).exists() and inst.stop(service):previous.append(service)
        inst.preflight()
        for name,data in changes.items():
            stat=inst.p(name).stat();tx.write(name,data,stat.st_mode&0o777,(stat.st_uid,stat.st_gid))
        # Old bookmarks and cached clients can recover to native Fluidd.
        retained={UI+'/index.html',UI+'/sw.js'}
        for name in files:
            if name not in retained:tx.remove(name)
        tx.write(UI+'/index.html',b'<!doctype html><meta http-equiv="refresh" content="0;url=/index.html#/"><a href="/index.html#/">Open Fluidd</a>')
        tx.write(UI+'/sw.js',b"self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil((async()=>{await self.registration.unregister();for(const c of await self.clients.matchAll({type:'window'})){if(new URL(c.url).pathname.startsWith('/u1-filaments-ui/'))await c.navigate('/index.html#/');}})()));")
        tx.remove(CORE+'/managed-install.json')
        inst.run('nginx','-t');inst.run('nginx','-s','reload');restarted=True;inst.restore_ready()
        (backup/'success.json').write_text(json.dumps({'uninstalled':True,'personalDataRetained':True}))
        print('UNINSTALLED. Native Fluidd: /index.html#/');print('Backup:',backup)
    except BaseException:
        inst.rollback_guard(restarted);tx.rollback();inst.run('nginx','-t');inst.run('nginx','-s','reload')
        if restarted:inst.restore_ready()
        for service in previous:inst.run('/etc/init.d/'+service,'start')
        raise
