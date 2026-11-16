"""Release from tracked source + a clean frontend build + pinned public runtimes.

Never reads a printer, working backup, private state directory or .env file.
"""
from pathlib import Path
import argparse
import gzip
import io
import json
import re
import shutil
import subprocess
import tarfile
from install import sha, VERSION

RUNTIMES = {
    'node-runtime.tar.gz': 'f728182437fc0f67ad80e9904870b857cd36087e2445c938bff17d5386fd9e89',
    'codex-arm64.gz': '37e96e48cd4635733d7654d126870ab7ae69c5d5a0e686cf46e29f119b9f844d',
    'cloudflared-linux-arm64': 'abe54a006acf9faf2d19ee9d953cb0d0804e92f59c5382a162e57b84d086f56f',
}
PRIVATE = re.compile(r'(?i)(?:^|/)(?:[^/]*-private|(?:local-)?backups?|filament-ui-data)(?:/|$)|(?:^|/)(?:\.env[^/]*|auth\.json|control\.key|pairing\.json)$')
CREDENTIAL = re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-(?:proj-)?[A-Za-z0-9_-]{24,}',re.I)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ['dependencies','node-runtime','codex-runtime','cloudflared-runtime','output']:
        parser.add_argument('--'+option,type=Path,required=True)
    parser.add_argument('--denylist',type=Path,help='Optional private local list of values that must never be shipped; not included in the release')
    args=parser.parse_args();repo=Path(__file__).resolve().parent.parent
    denied=[] if args.denylist is None else [v.strip().lower().encode() for v in args.denylist.read_text().splitlines() if v.strip()]
    public_constants=json.loads((repo/'installer/public-vendor-constants.json').read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    files={}
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=repo).decode().split('\0')
    for name in filter(None,tracked):
        path=repo/name
        if PRIVATE.search(name):raise ValueError('Private path tracked: '+name)
        if path.is_symlink() or not path.is_file():continue
        if path.name.startswith('test-') or '.test.' in path.name:continue
        folder,_,tail=name.partition('/')
        if folder=='backend' and (path.suffix in ('.py','.ps1','.cjs') or tail=='u1_voice_messages.json'):files['backend/'+tail]=path
        elif folder=='services':files['services/'+tail]=path
        elif folder=='alexa' and path.suffix in ('.cjs','.json'):files['alexa/'+tail]=path
        elif folder=='remote-access' and path.suffix in ('.conf','.html','.js','.json'):files['remote/'+tail]=path
        elif folder=='LICENSES':files['licenses/'+tail]=path
    dist=repo/'frontend/dist'
    if not (dist/'index.html').is_file():raise ValueError('Build the clean frontend first')
    config=json.loads((dist/'config.json').read_text())
    if config!={'endpoints':[],'hosted':False}:raise ValueError('Frontend has personal endpoint configuration')
    for path in dist.rglob('*'):
        if path.is_file() and not path.is_symlink():files['ui/'+path.relative_to(dist).as_posix()]=path
    # Only npm dependencies from the separately prepared dependency directory.
    for path in args.dependencies.rglob('*'):
        if path.is_file() and not path.is_symlink():
            name='alexa/node_modules/'+path.relative_to(args.dependencies).as_posix()
            if path.suffix.lower() in ('.pem','.key','.crt','.p12','.pfx','.node','.log') or '/.bin/' in name:continue
            files[name]=path
    files['alexa/node_modules/alexa-cookie2/alexa-cookie.js']=repo/'alexa/cookie.vendor.cjs'
    files['alexa/node_modules/alexa-cookie2/lib/proxy.js']=repo/'alexa/proxy.vendor.cjs'
    files.update({'nginx-local.conf':repo/'installer/nginx-local.conf','LICENSE':repo/'LICENSE','NOTICE.md':repo/'NOTICE.md'})
    for name,path in files.items():
        if PRIVATE.search(name) or path.suffix.lower() in ('.key','.pem','.crt','.mobileconfig','.gcode','.3mf','.stl','.log'):
            raise ValueError('Private/device artifact in payload: '+name)
        if path.stat().st_size<20*1024*1024:
            raw=path.read_bytes()
            upstream_constant=name in public_constants and sha(path)==public_constants[name]['sha256']
            if (CREDENTIAL.search(raw) and not upstream_constant) or any(v in raw.lower() for v in denied):
                raise ValueError('Private data / key pattern in payload: '+name)
    for required in ['backend/spool-accounting.py','backend/u1-alexa-bounded-launch.py','ui/index.html','alexa/bridge.cjs','remote/nginx-template.conf','licenses/Node.js-LICENSE.txt','licenses/Codex-LICENSE.txt','licenses/cloudflared-LICENSE.txt']:
        if required not in files:raise ValueError('Release source not staged: '+required)
    with (args.output/'u1-companion.tar.gz').open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as gz,tarfile.open(fileobj=gz,mode='w') as tar:
        for name,path in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=path.stat().st_size;info.mode=0o644
            if name.startswith('services/'):
                raw=path.read_bytes().replace(b'\r\n',b'\n');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
            else:
                with path.open('rb') as source:tar.addfile(info,source)
    for name,source in [('install.py',repo/'installer/install.py'),('uninstall.py',repo/'installer/uninstall.py'),('install.sh',repo/'install.sh'),('u1-service-stop.py',repo/'installer/u1-service-stop.py'),
                        ('node-runtime.tar.gz',args.node_runtime),('codex-arm64.gz',args.codex_runtime),('cloudflared-linux-arm64',args.cloudflared_runtime)]:
        if name in RUNTIMES and sha(source)!=RUNTIMES[name]:raise ValueError('Unverified runtime: '+name)
        if name in ('install.sh','install.py','uninstall.py','u1-service-stop.py'):
            (args.output/name).write_bytes(source.read_bytes().replace(b'\r\n',b'\n'))
        else:shutil.copyfile(source,args.output/name)
    manifest={'version':VERSION,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
              'payloadFiles':len(files),'personalLibraries':'empty on fresh installation','catalog':'built-in Snapmaker catalog only',
              'assets':{p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file() and p.name not in ('SHA256SUMS','release-manifest.json')}}
    (args.output/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    assets=sorted(p for p in args.output.iterdir() if p.is_file() and p.name!='SHA256SUMS')
    (args.output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets),encoding='ascii',newline='\n')
    print('Full release built and privacy checked:',len(files),'payload files,',len(assets),'assets')


if __name__=='__main__':main()
