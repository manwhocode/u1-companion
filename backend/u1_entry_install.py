"""Reversible U1 entry point. Original Fluidd files remain unchanged."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

BEGIN = '    # BEGIN U1 ADDON ENTRY\n'
END = '    # END U1 ADDON ENTRY\n'
HOME = Path('/home/lava/u1-addons/filament-ui')
WRAPPER = '''// U1 ADDON ENTRY: original Fluidd remains available at /index.html.
const u1EntryURL = value => {
  const url = new URL(value);
  url.pathname = '/u1-filaments-ui/'; url.hash = '/u1-filaments';
  return url.href;
};
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil((async () => {
  await self.clients.claim();
  for (const client of await self.clients.matchAll({type: 'window'})) {
    if (new URL(client.url).pathname === '/') await client.navigate(u1EntryURL(client.url));
  }
})()));
self.addEventListener('fetch', event => {
  if (event.request.mode === 'navigate' && new URL(event.request.url).pathname === '/') {
    event.stopImmediatePropagation();
    event.respondWith(Response.redirect(u1EntryURL(event.request.url), 302));
  }
});
importScripts('/u1-stock-sw.js');
'''

def config(text):
    block = BEGIN + '''    location = / {
        add_header Cache-Control "no-store" always;
        return 302 "/u1-filaments-ui/$is_args$args#/u1-filaments";
    }
    location = /sw.js {
        alias /home/lava/u1-addons/filament-ui/u1-root-entry-sw.js;
        default_type application/javascript;
        add_header Cache-Control "no-store" always;
    }
    location = /u1-stock-sw.js {
        alias /home/lava/fluidd/sw.js;
        default_type application/javascript;
        add_header Cache-Control "no-store" always;
    }
''' + END
    if BEGIN in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1: raise ValueError('Ambiguous entry configuration')
        start = text.index(BEGIN); finish = text.index(END) + len(END)
        text = text[:start] + text[finish:]
    if 'location = / {' in text or 'location = /sw.js {' in text or 'location = /u1-stock-sw.js {' in text:
        raise ValueError('An existing root/SW route needs review')
    anchor = '    location / {\n'
    if text.count(anchor) != 1: raise ValueError('Unexpected Fluidd site structure')
    return text.replace(anchor, block + anchor, 1)

def atomic(path, data, mode=0o644):
    temp = path.with_name(path.name + '.entry-next')
    with temp.open('wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    temp.chmod(mode); os.replace(temp, path)

def install(backup):
    backup = Path(backup); backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not (Path('/home/lava/fluidd/u1-filaments-ui')/'addon-status.json').is_file(): raise RuntimeError('Install U1 UI first')
    stock = Path('/home/lava/fluidd/sw.js')
    original_hash = hashlib.sha256(stock.read_bytes()).hexdigest()
    sites = [Path('/etc/nginx/sites-available/fluidd')]
    tls = Path('/etc/nginx/sites-available/u1-filament-https-addon')
    if tls.exists(): sites.append(tls)
    wrapper = HOME/'u1-root-entry-sw.js'
    paths = sites + [wrapper]
    before = {str(p): p.read_bytes() if p.exists() else None for p in paths}
    updated = {str(p): config(p.read_text()).encode() for p in sites}
    updated[str(wrapper)] = WRAPPER.encode()
    for index, (name, data) in enumerate(before.items()):
        if data is not None: (backup/str(index)).write_bytes(data)
    manifest = [{'path':name, 'old': str(i) if before[name] is not None else None,
                 'after':hashlib.sha256(data).hexdigest()} for i,(name,data) in enumerate(updated.items())]
    (backup/'manifest.json').write_text(json.dumps(manifest))
    try:
        for name,data in updated.items(): atomic(Path(name),data)
        subprocess.run(['nginx','-t'],check=True)
        subprocess.run(['nginx','-s','reload'],check=True)
        assert hashlib.sha256(stock.read_bytes()).hexdigest() == original_hash
    except BaseException:
        for name,data in before.items():
            if data is None: Path(name).unlink(missing_ok=True)
            else: atomic(Path(name),data)
        if subprocess.run(['nginx','-t']).returncode == 0: subprocess.run(['nginx','-s','reload'])
        raise
    return {'backup':str(backup), 'stockFluidd':'/index.html#/', 'stockSwUnchanged':True}

def rollback(backup):
    backup = Path(backup)
    rows = json.loads((backup/'manifest.json').read_text())
    for row in rows:
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['after']:
            raise RuntimeError('Configuration changed since install; restore needs review')
    for row in rows:
        if row['old'] is None: Path(row['path']).unlink()
        else: atomic(Path(row['path']), (backup/row['old']).read_bytes())
    subprocess.run(['nginx','-t'],check=True); subprocess.run(['nginx','-s','reload'],check=True)
