"""Personal Alexa-hosted skill relay. Configure config.json privately in Amazon."""
import hashlib,hmac,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlsplit

MESSAGES=json.loads(Path(__file__).with_name('voice_messages.json').read_text(encoding='utf-8'))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def lambda_handler(event,context):
    language=event.get('request',{}).get('locale','').split('-')[0].lower()
    text=MESSAGES.get(language,MESSAGES['en'])
    failure=text['failure']
    try:
        cfg=json.loads(Path(__file__).with_name('config.json').read_text())
        application=event.get('context',{}).get('System',{}).get('application',{}).get('applicationId')
        if not cfg.get('skillId') or application!=cfg['skillId'] or not event.get('request',{}).get('requestId'):raise ValueError('wrong_skill')
        if not cfg.get('url') and not cfg.get('key'):
            return {'version':'1.0','response':{'outputSpeech':{'type':'PlainText','text':text['setup']},'shouldEndSession':True}}
        url=urlsplit(cfg['url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.path!='/u1-alexa/skill' or url.query or url.fragment:raise ValueError('invalid_endpoint')
        if not isinstance(cfg.get('key'),str) or len(cfg['key'])!=64:raise ValueError('invalid_key')
        # Send only routing/intent data, never Alexa API tokens or session attributes.
        system=event.get('context',{}).get('System',{});session=event.get('session',{});request=event.get('request',{})
        allowed={k:request[k] for k in ('type','requestId','timestamp','locale') if k in request}
        if 'intent' in request:
            intent=request['intent'];allowed['intent']={'name':intent.get('name'),'slots':{k:{'value':v.get('value','')} for k,v in intent.get('slots',{}).items() if k in ('code','minutes','model')}}
        minimal={'context':{'System':{'application':{'applicationId':application},'user':{'userId':system.get('user',{}).get('userId','')}}},
                 'session':{'sessionId':session.get('sessionId',''),'application':{'applicationId':session.get('application',{}).get('applicationId',application)}},'request':allowed}
        raw=json.dumps(minimal,separators=(',',':')).encode()
        if len(raw)>65536:raise ValueError('request_too_large')
        signature=hmac.new(cfg['key'].encode(),raw,hashlib.sha256).hexdigest()
        req=urllib.request.Request(cfg['url'],data=raw,headers={'Content-Type':'application/json','X-U1-Voice-Signature':signature})
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=6) as response:result=json.loads(response.read(65537))
        if result.get('version')!='1.0' or not isinstance(result.get('response'),dict):raise ValueError('invalid_response')
        return result
    except Exception:
        # Never log the envelope, HMAC key, pairing code or Amazon identifiers.
        return {'version':'1.0','response':{'outputSpeech':{'type':'PlainText','text':failure},'shouldEndSession':True}}
