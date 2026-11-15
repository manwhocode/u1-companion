"""Official public-client OAuth. Pairing grants login only, never printer control."""
import base64,hashlib,hmac,json,re,secrets,subprocess,threading,time,uuid
from pathlib import Path
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.request import Request,build_opener
from .openai_client import NoRedirect
from .storage import atomic,read
AUTH='https://auth.openai.com'
RESOURCE='https://api.openai.com/v1'
LOCK=threading.RLock()
def network(path,form=None):
    if path not in ('/api/accounts/oauth/token','/.well-known/jwks.json'):raise ValueError('Unknown auth route')
    req=Request(AUTH+path,data=None if form is None else urlencode(form).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with build_opener(NoRedirect()).open(req,timeout=15) as r:
            raw=r.read(1000001)
            if len(raw)>1000000:raise ValueError()
            return json.loads(raw)
    except Exception:raise ValueError('OpenAI не подтвердил вход. Начните новую попытку; автоматического повтора нет.') from None
class Accounts:
    def __init__(self,root):self.root=Path(root);self.path=self.root/'chatgpt-accounts.json'
    def data(self):return read(self.path,{'host':'urn:uuid:'+str(uuid.uuid4()),'active':None,'profiles':{}})
    def public(self):
        d=self.data();return {'active':d['active'],'profiles':[{'id':i,'label':v.get('email') or 'ChatGPT '+i[:6],'connected':bool(v.get('access_token'))} for i,v in d['profiles'].items()]}
    def connected(self):
        d=self.data();return bool(d['profiles'].get(d['active'],{}).get('access_token'))
    def pair(self,owner,profile=None):
        with LOCK:
            d=self.data();atomic(self.path,d)
            if profile is not None and profile not in d['profiles']:raise ValueError('Аккаунт не найден.')
            token=secrets.token_hex(32)
            folder=self.root/'login-pairs';folder.mkdir(mode=0o700,exist_ok=True)
            for p in folder.glob('*.json'):
                if p.stat().st_mtime<time.time()-900:p.unlink()
            if len(list(folder.glob('*.json')))>30:raise ValueError('Слишком много попыток входа.')
            atomic(folder/(hashlib.sha256(token.encode()).hexdigest()+'.json'),{'owner':owner,'expires':time.time()+600,'profile':profile,'state':'new'})
            return token
    def pending(self,token):
        if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{64}',token):raise PermissionError('Недействительный код подключения.')
        path=self.root/'login-pairs'/(hashlib.sha256(token.encode()).hexdigest()+'.json');p=read(path)
        if not p or p['expires']<time.time():raise PermissionError('Код подключения истёк.')
        return path,p
    def start(self,token,port):
        with LOCK:
            path,p=self.pending(token)
            if p['state']!='new' or type(port)is not int or not 1024<=port<=65535:raise ValueError('Нужна новая попытка входа.')
            d=self.data();old=d['profiles'].get(p['profile'],{});client=old.get('client_id','dynamic_agent_client')
            p.update(state='waiting',nonce=secrets.token_urlsafe(32),oauthState=secrets.token_urlsafe(32),verifier=secrets.token_urlsafe(48),redirect='http://127.0.0.1:'+str(port)+'/auth/callback',client=client)
            atomic(path,p)
            args={'client_id':client,'ext_agent_host_id':d['host'],'response_type':'code','redirect_uri':p['redirect'],'scope':'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct','resource':RESOURCE,'state':p['oauthState'],'nonce':p['nonce'],'code_challenge_method':'S256','code_challenge':base64.urlsafe_b64encode(hashlib.sha256(p['verifier'].encode()).digest()).decode().rstrip('=')}
            if client=='dynamic_agent_client':args['agent_name_hint']='U1 Companion'
            return {'url':AUTH+'/api/accounts/authorize?'+urlencode(args)}
    def finish(self,token,callback):
        with LOCK:
            path,p=self.pending(token);u=urlsplit(callback)
            if len(callback)>16000 or p['state']!='waiting' or u.scheme+'://'+u.netloc+u.path!=p['redirect'] or u.fragment:raise ValueError('Неверный адрес подтверждения.')
            q=parse_qs(u.query)
            if any(len(v)!=1 for v in q.values()) or not hmac.compare_digest(q.get('state',[''])[0],p['oauthState']):raise ValueError('Проверка state не пройдена.')
            p['state']='consumed';atomic(path,p)
            if q.get('error'):raise ValueError('Вход отменён на странице OpenAI.')
            client=q.get('client_id',[p['client']])[0]
            if not re.fullmatch(r'oaiapp_[A-Za-z0-9_-]{1,200}',client) or p['client']!='dynamic_agent_client' and client!=p['client'] or not q.get('code'):raise ValueError('OpenAI не вернул регистрацию приложения.')
            # Retain issued registration even if its one-time code exchange fails.
            d=self.data();profile=p['profile'] or str(uuid.uuid4());d['profiles'].setdefault(profile,{}).update(client_id=client);atomic(self.path,d)
            t=network('/api/accounts/oauth/token',{'grant_type':'authorization_code','client_id':client,'code':q['code'][0],'code_verifier':p['verifier'],'redirect_uri':p['redirect'],'resource':RESOURCE})
            jwks=network('/.well-known/jwks.json')
            node=Path('/userdata/u1-addons/alexa-bridge/runtime/node')
            r=subprocess.run([str(node),str(Path(__file__).with_name('verify-id.cjs'))],input=json.dumps({'token':t.get('id_token',''),'jwks':jwks,'client':client,'nonce':p['nonce']}),text=True,capture_output=True,timeout=10)
            if r.returncode:raise ValueError('Подпись или срок ID-токена OpenAI не подтверждены.')
            identity=json.loads(r.stdout);old=d['profiles'][profile]
            if old.get('sub') and old['sub']!=identity['sub']:raise ValueError('Вошли в другой аккаунт. Добавьте его отдельно.')
            scopes=t.get('scope','').split()
            if 'chatgpt.tokens.use.direct' not in scopes or t.get('token_type','').lower()!='bearer' or not t.get('access_token') or not t.get('refresh_token'):raise ValueError('Разрешение использовать лимит ChatGPT не выдано.')
            old.update(identity);old.update({k:t[k] for k in ('access_token','refresh_token','id_token')});old.update(refreshUncertain=False,expires=time.time()+min(int(t.get('expires_in',3600)),3600),scopes=scopes)
            d['active']=profile;atomic(self.path,d)
            return {'connected':True}
    def select(self,profile):
        with LOCK:
            d=self.data()
            if not d['profiles'].get(profile,{}).get('access_token'):raise ValueError('Сначала войдите в этот аккаунт.')
            d['active']=profile;atomic(self.path,d)
            return self.public()
    def token(self):
        with LOCK:
            d=self.data();v=d['profiles'].get(d['active'],{})
            if not v.get('access_token'):raise ValueError('Войдите через аккаунт ChatGPT.')
            if v.get('refreshUncertain'): raise ValueError('Обновление сессии не подтверждено. Повторно войдите в ChatGPT.')
            if v['expires']<time.time()+60:
                v['refreshUncertain']=True;atomic(self.path,d)
                t=network('/api/accounts/oauth/token',{'grant_type':'refresh_token','client_id':v['client_id'],'refresh_token':v['refresh_token'],'resource':RESOURCE})
                if not t.get('access_token') or not t.get('refresh_token'):raise ValueError('Нужно повторно войти в ChatGPT.')
                v.update(refreshUncertain=False,access_token=t['access_token'],refresh_token=t['refresh_token'],expires=time.time()+min(int(t.get('expires_in',3600)),3600));atomic(self.path,d)
            return v['access_token']
