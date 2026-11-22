"""Verified universal bootstrap, executed on U1 using its stock Python."""
CODE = r'''import hashlib,json,os,pathlib,platform,re,secrets,urllib.request
if os.geteuid()!=0 or platform.machine() not in ('aarch64','arm64') or not pathlib.Path('/oem/printer_data/config/printer.cfg').is_file():raise SystemExit('Connect as root to Snapmaker U1')
nonce=secrets.token_hex(12)
class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if not newurl.startswith('https://'):raise SystemExit('Insecure installer redirect')
        return super().redirect_request(request,fp,code,msg,headers,newurl)
opener=urllib.request.build_opener(HTTPSRedirect())
def download(url,limit):
    request=urllib.request.Request(url+('?' if '?' not in url else '&')+'check='+nonce,headers={'Cache-Control':'no-cache','User-Agent':'U1-Companion-Installer'})
    with opener.open(request,timeout=45) as response:data=response.read(limit+1)
    if len(data)>limit:raise SystemExit('Unexpected installer download size')
    return data
release=json.loads(download('https://api.github.com/repos/manwhocode/u1-companion/releases/latest',262144))
tag=release.get('tag_name','')
if release.get('draft') or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',tag):raise SystemExit('Invalid published release metadata')
base='https://github.com/manwhocode/u1-companion/releases/download/'+tag+'/'
checks={}
for line in download(base+'SHA256SUMS',16384).decode('ascii').splitlines():
    match=re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)',line)
    if not match or match[2] in checks:raise SystemExit('Invalid release checksum manifest')
    checks[match[2]]=match[1]
data=download(base+'install.sh',65536)
if hashlib.sha256(data).hexdigest()!=checks.get('install.sh'):raise SystemExit('Bootstrap checksum mismatch')
text=data.decode('utf-8')
if not re.search(r'^VERSION='+re.escape(tag)+r'\r?$',text,re.M):raise SystemExit('Bootstrap version differs from published release')
p=pathlib.Path('/userdata/u1-companion-install.sh')
if p.is_symlink() or p.parent.is_symlink():raise SystemExit('Unexpected installer symlink')
t=p.with_name('.u1-bootstrap-'+secrets.token_hex(12))
try:
    with t.open('xb') as output:output.write(data)
    os.chmod(t,0o700);os.replace(t,p)
finally:t.unlink(missing_ok=True)
print('Published release: '+tag+' | bootstrap SHA256 verified',flush=True)
'''
