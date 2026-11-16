#!/bin/sh
# Run on the printer over SSH. No desktop application or PC dependencies.
set -eu
umask 077
VERSION=v0.1.1-alpha.4
WORK="/userdata/u1-addons/downloads/$VERSION"
command -v python3 >/dev/null 2>&1 || { echo "Stock Python 3.11 is required on U1"; exit 1; }
# Python uses the system CA store. No insecure TLS flags or shell pipelines.
python3 - "$WORK" "$VERSION" <<'PY'
import hashlib,os,pathlib,platform,re,secrets,shutil,sys,urllib.request
if platform.system()!='Linux' or platform.machine() not in ('aarch64','arm64') or os.geteuid()!=0:
    sys.exit('Open an SSH session as root on your Snapmaker U1 first.')
if sys.version_info<(3,11): sys.exit('Python 3.11 or newer is required.')
root=pathlib.Path(sys.argv[1])
for path in (root,*root.parents):
    if path.is_symlink():sys.exit('Unexpected symlink in installer download path.')
root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
base='https://github.com/manwhocode/u1-companion/releases/download/'+sys.argv[2]
class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if not newurl.startswith('https://'):raise ValueError('Insecure download redirect')
        return super().redirect_request(request,fp,code,msg,headers,newurl)
opener=urllib.request.build_opener(Redirect())
with opener.open(base+'/SHA256SUMS',timeout=60) as response:raw=response.read(16384).decode('ascii')
checks={}
for line in raw.splitlines():
    m=re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)',line)
    if not m or m[2] in checks:raise ValueError('Invalid release checksum manifest')
    checks[m[2]]=m[1]
for name in ('install.py','u1-service-stop.py'):
    target=root/name
    if target.is_symlink():raise ValueError('Unexpected download symlink')
    temp=root/(name+'.download-'+secrets.token_hex(6))
    try:
        with opener.open(base+'/'+name,timeout=60) as src,temp.open('xb') as dst:shutil.copyfileobj(src,dst,65536)
        if hashlib.sha256(temp.read_bytes()).hexdigest()!=checks[name]:raise ValueError('Checksum mismatch: '+name)
        temp.replace(target)
    finally:temp.unlink(missing_ok=True)
print('U1 Companion - verified full SSH installer')
PY
# Keep the terminal as stdin so the single installation confirmation works.
if [ "$#" -eq 0 ]; then set -- --install; fi
exec python3 "$WORK/install.py" "$@"
