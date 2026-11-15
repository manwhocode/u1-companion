"""Private control helpers for the optional authenticated remote-access addon."""
import json,os,re,secrets,time,urllib.request
from pathlib import Path
ROOT=Path('/userdata/u1-addons/remote-private')
EMAIL=re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,185}[A-Za-z0-9])?\.[A-Za-z]{2,63}\Z")
URL=re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com\Z')
def valid_email(value):return isinstance(value,str) and len(value)<=254 and bool(EMAIL.fullmatch(value)) and '..' not in value and '*' not in value

def read(path,default=None):
 try:
  if path.stat().st_size>65536 or path.is_symlink():return default
  return json.loads(path.read_text())
 except (OSError,ValueError):return default

def atomic(path,value):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 temp=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
 with temp.open('x') as f:os.chmod(temp,0o600);json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
 os.replace(temp,path)

def origin_allowed(origin,root=ROOT,clock=time.time):
 s=read(root/'status.json',{})
 return isinstance(origin,str) and bool(URL.fullmatch(origin)) and s.get('url')==origin and s.get('phase')=='running' and s.get('accessProtected') is True and s.get('authMode')=='code' and 0<=clock()-s.get('updatedAt',0)<45

def request(action,payload=None):
 if action not in ('state','command','code'):raise ValueError('Unknown remote operation')
 key=(ROOT/'control.key').read_text().strip()
 req=urllib.request.Request('http://127.0.0.1:4548/'+action,data=None if payload is None else json.dumps(payload,allow_nan=False).encode(),headers={'Content-Type':'application/json','X-U1-Remote-Key':key})
 with urllib.request.urlopen(req,timeout=8) as r:return json.load(r)
