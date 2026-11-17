"""Bounded, unprivileged cloudflared supervisor. The origin gateway always requires a pairing-code session."""
import hashlib,hmac,json,os,queue,re,secrets,signal,subprocess,sys,threading,time,socket,select
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from u1_remote import ROOT,URL,read,atomic,origin_allowed
from u1_remote_auth import PairingAuth,login_html
BINARY=Path('/userdata/u1-addons/remote-access/runtime/cloudflared')
EXPECTED='abe54a006acf9faf2d19ee9d953cb0d0804e92f59c5382a162e57b84d086f56f'

def arguments():
 return [str(BINARY),'--no-autoupdate','tunnel','--url','http://127.0.0.1:18088','--protocol','http2','--edge-ip-version','4','--metrics','127.0.0.1:18089']

class Manager:
 def __init__(self,root=ROOT):
  self.root=root;root.mkdir(mode=0o700,parents=True,exist_ok=True)
  self.key=(root/'control.key').read_text().strip()
  self.config=read(root/'config.json',{'email':'','enabled':False})
  self.auth=PairingAuth(root)
  self.proc=None;self.phase='stopped';self.url='';self.error='';self.lock=threading.RLock();self.lines=queue.Queue(maxsize=100);self.start_time=0;self.relays=0;self.retry_at=0;self.retry_delay=5
  self.publish()
 def state(self):
  with self.lock:return {'phase':self.phase,'url':self.url,'hasCode':bool(self.auth.code()),'authMode':'code','accessProtected':True,'enabled':bool(self.config.get('enabled')),'error':self.error,'updatedAt':time.time()}
 def publish(self):atomic(self.root/'status.json',self.state())
 def stop(self):
  with self.lock:
   p=self.proc;self.proc=None;self.phase='stopped';self.url='';self.error='';self.auth.sessions.clear();self.retry_at=0
   if p:
    p.terminate()
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
   self.publish()
 def launch(self):
  if self.config.get('authMode')!='code' or not self.auth.code():raise ValueError('code_required')
  # Refuse to launch if the local origin can serve any API without authentication.
  import urllib.request,urllib.error
  try:
   urllib.request.urlopen('http://127.0.0.1:18088/server/info',timeout=5)
   raise ValueError('gateway_not_protected')
  except urllib.error.HTTPError as e:
   if e.code!=401 or e.headers.get('X-U1-Remote-Gateway')!='code-v1':raise ValueError('gateway_not_protected')
  args=arguments()
  if self.proc and self.proc.poll() is None:raise ValueError('already_running')
  h=hashlib.sha256()
  with BINARY.open('rb') as f:
   for b in iter(lambda:f.read(65536),b''):h.update(b)
  if h.hexdigest()!=EXPECTED:raise ValueError('invalid_runtime')
  self.phase='starting';self.url='';self.error='';self.start_time=time.monotonic();self.retry_at=0
  env={'PATH':'/usr/bin:/bin','HOME':str(self.root),'LANG':'C.UTF-8','GOMEMLIMIT':'64MiB','GOGC':'50','GOMAXPROCS':'1'}
  self.proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env,cwd=self.root)
  process=self.proc
  def reader():
   for line in process.stdout:
    if self.proc is not process:return
    if len(line)>4096:continue
    try:self.lines.put_nowait((process,line))
    except queue.Full:pass
  threading.Thread(target=reader,daemon=True).start();self.publish()
 def retry_later(self):
  delay=self.retry_delay
  self.stop();self.phase='error';self.error='connection_failed'
  self.retry_at=time.monotonic()+delay;self.retry_delay=min(delay*2,300)
  self.publish()
 def restore(self):
  # Keep the owner's enabled choice through transient boot/network failures.
  # Every attempt still verifies pairing, protected origin and runtime digest.
  with self.lock:
   try:self.launch()
   except ValueError as error:
    self.retry_at=0;self.phase='error';self.error=str(error)
    self.config['enabled']=False;atomic(self.root/'config.json',self.config);self.publish()
   except Exception:self.retry_later()
 def command(self,payload):
  if not isinstance(payload,dict):raise ValueError('invalid_request')
  action=payload.get('action')
  with self.lock:
   if action=='rotate':
    if payload.get('confirmed') is not True:raise ValueError('confirmation_required')
    self.auth.rotate();self.config={'authMode':'code','enabled':bool(self.config.get('enabled'))};atomic(self.root/'config.json',self.config);self.error=''
   elif action=='start':
    if payload.get('confirmed') is not True:raise ValueError('confirmation_required')
    if not self.auth.code():raise ValueError('code_required')
    self.config={'authMode':'code','enabled':True};atomic(self.root/'config.json',self.config)
    try:self.launch()
    except Exception:self.retry_at=0;self.config['enabled']=False;atomic(self.root/'config.json',self.config);raise
   elif action=='stop':
    self.config['enabled']=False;atomic(self.root/'config.json',self.config);self.stop()
   else:raise ValueError('invalid_request')
   self.publish();return self.state()
 def tick(self):
  with self.lock:
   while not self.lines.empty():
    process,line=self.lines.get_nowait()
    if process is not self.proc:continue
    m=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',line)
    if m and URL.fullmatch(m[0]):self.url=m[0]
    if 'Registered tunnel connection' in line and self.url:self.phase='running';self.retry_delay=5;self.retry_at=0
   if self.proc and self.proc.poll() is not None:
    self.retry_later()
   if self.proc and self.phase=='starting' and time.monotonic()-self.start_time>120:
    self.retry_later()
   if not self.proc and self.config.get('enabled') and self.retry_at and time.monotonic()>=self.retry_at:self.restore()
   self.publish()

def handler(manager):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def reply(self,code,value,headers=None):
   data=json.dumps(value,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));
   for k,v in (headers or {}).items():self.send_header(k,v)
   self.end_headers();self.wfile.write(data)
  def do_GET(self):self.handle_request()
  def do_POST(self):self.handle_request()
  def handle_request(self):
   if not hmac.compare_digest(self.headers.get('X-U1-Remote-Key',''),manager.key):self.reply(403,{'error':'forbidden'});return
   host=self.headers.get('X-U1-Remote-Host','');origin=self.headers.get('X-U1-Remote-Origin','');cookie=self.headers.get('X-U1-Remote-Cookie','')
   origin_ok=origin_allowed('https://'+host,manager.root) and (not origin or origin=='https://'+host)
   authorized=False
   if origin_ok and cookie:
    with manager.lock:authorized=manager.auth.valid(cookie)
   if self.path=='/websocket':
    if not authorized or self.command!='GET' or origin!='https://'+host:self.reply(401,{});return
    if self.headers.get('Upgrade','').lower()!='websocket':self.reply(400,{});return
    wskey=self.headers.get('Sec-WebSocket-Key','')
    if not re.fullmatch(r'[A-Za-z0-9+/]{22}==',wskey):self.reply(400,{});return
    with manager.lock:
     if manager.relays>=16:self.reply(503,{});return
     manager.relays+=1
    try:
     with socket.create_connection(('127.0.0.1',7125),timeout=5) as upstream:
      handshake=f'GET /websocket HTTP/1.1\r\nHost: 127.0.0.1:7125\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {wskey}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://127.0.0.1\r\n\r\n'
      upstream.sendall(handshake.encode());headers=b''
      while not headers.endswith(b'\r\n\r\n') and len(headers)<16384:
       byte=upstream.recv(1)
       if not byte:raise OSError('closed upstream')
       headers+=byte
      if not headers.startswith(b'HTTP/1.1 101 '):self.reply(502,{});return
      self.connection.sendall(headers);self.connection.settimeout(5)
      while True:
       with manager.lock:live=manager.auth.valid(cookie)
       if not live:break
       ready,_,_=select.select([self.connection,upstream],[],[],1)
       for stream in ready:
        chunk=stream.recv(65536)
        if not chunk:return
        (upstream if stream is self.connection else self.connection).sendall(chunk)
    except OSError:pass
    finally:
     with manager.lock:manager.relays-=1
     self.close_connection=True
    return
   if self.path=='/authorize':self.reply(200 if authorized else 401,{});return
   if self.path=='/state' and self.command=='GET':self.reply(200,manager.state());return
   if self.path=='/code' and self.command=='GET':self.reply(200,{'code':manager.auth.code()});return
   if self.path=='/login':
    if not origin_ok:self.reply(403,{});return
    if self.command=='GET':
     strings=read(Path(__file__).with_name('remote-translations.json'),{})
     page,csp=login_html(self.headers.get('Accept-Language','en'),strings)
     self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',csp);self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page);return
    if self.command!='POST' or origin!='https://'+host:self.reply(403,{});return
    try:
     size=int(self.headers.get('Content-Length','0'))
     if not 0<size<=2048:raise ValueError()
     value=json.loads(self.rfile.read(size))
     with manager.lock:session=manager.auth.login(value.get('code'),self.headers.get('X-U1-Remote-IP','unknown'))
     self.reply(200 if session else 403,{'ok':bool(session)},{'Set-Cookie':session} if session else {})
    except (ValueError,AttributeError):self.reply(400,{})
    return
   if self.path=='/logout' and self.command=='POST':
    if not origin_ok or origin!='https://'+host:self.reply(403,{});return
    with manager.lock:cleared=manager.auth.logout(cookie)
    self.reply(200,{}, {'Set-Cookie':cleared});return
   if self.path=='/session' and self.command=='POST':
    if not authorized or origin!='https://'+host:self.reply(401,{});return
    from urllib.parse import urlsplit
    from u1_ai_session import issue
    self.reply(200,issue({'origin':origin},hosts={urlsplit(origin).hostname}));return
   if self.path!='/command' or self.command!='POST':self.reply(404,{});return
   try:
    length=int(self.headers.get('Content-Length','0'))
    if not 0<length<=2048:raise ValueError('invalid_request')
    payload=json.loads(self.rfile.read(length));self.reply(200,manager.command(payload))
   except Exception as error:self.reply(400,{'error':str(error) if isinstance(error,ValueError) else 'failed'})
 return Handler

def main():
 manager=Manager();server=ThreadingHTTPServer(('127.0.0.1',4548),handler(manager))
 threading.Thread(target=server.serve_forever,daemon=True).start()
 def stop(*args):manager.stop();sys.exit(0)
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 if manager.config.get('enabled'):manager.restore()
 while True:manager.tick();time.sleep(1)
if __name__=='__main__':main()
