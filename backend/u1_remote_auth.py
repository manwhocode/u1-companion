"""High-entropy local pairing codes and bounded remote browser sessions."""
import hashlib,hmac,json,re,secrets,time
from http.cookies import SimpleCookie,CookieError
from u1_remote import atomic,read
COOKIE='__Host-u1-companion'
TTL=12*60*60
class PairingAuth:
 def __init__(self,root,clock=time.time):
  self.root=root;self.clock=clock;self.sessions={};self.attempts={}
 def code(self):return (read(self.root/'pairing.json',{}) or {}).get('code','')
 def rotate(self):
  raw=secrets.token_hex(16).upper();code='-'.join(raw[i:i+8] for i in range(0,32,8))
  atomic(self.root/'pairing.json',{'code':code});self.sessions.clear();return code
 def valid(self,cookie):
  try:
   value=SimpleCookie();value.load(cookie or '');token=value[COOKIE].value
  except (CookieError,KeyError):return False
  if not re.fullmatch(r'[0-9a-f]{64}',token):return False
  digest=hashlib.sha256(token.encode()).hexdigest();expiry=self.sessions.get(digest,0)
  return expiry>self.clock()
 def login(self,code,ip):
  now=self.clock();self.attempts={k:[x for x in v if x>now-60] for k,v in self.attempts.items() if any(x>now-60 for x in v)}
  if len(self.attempts)>256:return None
  for key,limit in [('*',120),(ip,12)]:
   if len(self.attempts.get(key,[]))>=limit:return None
  self.attempts.setdefault('*',[]).append(now);self.attempts.setdefault(ip,[]).append(now)
  normalized=re.sub(r'[-\s]','',code).upper() if isinstance(code,str) else ''
  expected=self.code().replace('-','')
  if not expected or not re.fullmatch(r'[0-9A-F]{32}',normalized) or not hmac.compare_digest(normalized,expected):return None
  self.sessions={k:v for k,v in self.sessions.items() if v>now}
  if len(self.sessions)>=64:self.sessions.pop(next(iter(self.sessions)))
  token=secrets.token_hex(32);self.sessions[hashlib.sha256(token.encode()).hexdigest()]=now+TTL
  return f'{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={TTL}'
 def logout(self,cookie):
  try:
   c=SimpleCookie();c.load(cookie or '');self.sessions.pop(hashlib.sha256(c[COOKIE].value.encode()).hexdigest(),None)
  except (CookieError,KeyError):pass
  return f'{COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0'

def login_html(language,strings):
 import html
 # Language is selected from bundled static translations, never interpolated input.
 fallback=strings['en'];lang=next((x.strip().split(';')[0] for x in language.split(',') if x.strip()),'en')
 key=lang if lang in strings else ('zh-HK' if lang.lower().startswith('zh-hant') else 'zh-CN' if lang.startswith('zh') else lang.split('-')[0]);s=strings.get(key,fallback)
 nonce=secrets.token_hex(16)
 page='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>U1 Companion</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#191a1b;color:#eee;font:16px system-ui}main{box-sizing:border-box;margin:5px;padding:24px;max-width:440px;width:calc(100% - 10px);border:1px solid #555;border-radius:16px;background:#252628}h1{margin-top:0}input,button{box-sizing:border-box;width:100%;padding:12px;border-radius:7px;font:inherit}input{background:#18191a;color:white;border:1px solid #888;margin:8px 0 16px}button{background:#9bcb43;color:#172008;border:0;cursor:pointer}#error{color:#ff9393;min-height:1.3em}</style></head><body><main><h1>U1 Companion</h1><p>__HELP__</p><form id="login"><label for="code">__CODE__</label><input id="code" type="password" autocomplete="current-password" spellcheck="false" maxlength="64" required><button id="submit">__LOGIN__</button><p id="error" role="alert"></p></form></main><script nonce="__NONCE__">const form=document.getElementById('login'),button=document.getElementById('submit');form.addEventListener('submit',async e=>{e.preventDefault();button.disabled=true;document.getElementById('error').textContent='';try{const r=await fetch('/u1-remote/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',redirect:'error',body:JSON.stringify({code:document.getElementById('code').value})});if(!r.ok)throw Error();location.replace('/u1-remote/open')}catch{document.getElementById('error').textContent=__ERROR__}finally{button.disabled=false}})</script></body></html>'''
 page=page.replace('__HELP__',html.escape(s[7])).replace('__CODE__',html.escape(s[0])).replace('__LOGIN__',html.escape(s[3])).replace('__ERROR__',json.dumps(s[8],ensure_ascii=False).replace('<','\\u003c')).replace('__NONCE__',nonce)
 return page.encode(),f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
