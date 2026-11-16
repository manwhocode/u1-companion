"""Personal Alexa skill relay. HMAC, pairing, expiring confirmation, no raw G-code."""
import datetime,hashlib,hmac,json,os,re,secrets,time,uuid,unicodedata
from pathlib import Path
from u1_recovery import atomic

ROOT=Path('/userdata/u1-addons/filament-ui-data/alexa-voice')

def read(path,default):
    return json.loads(path.read_text()) if path.exists() else default

def config(root=ROOT):
    return read(Path(root)/'config.json',{'enabled':False,'skillId':'','userHash':''})

def settings(action,payload,root=ROOT):
    root=Path(root);root.mkdir(mode=0o700,parents=True,exist_ok=True)
    value=config(root)
    if action=='voice_setup':
        skill=payload.get('skillId','').strip()
        if not re.fullmatch(r'amzn1\.ask\.skill\.[A-Za-z0-9-]{10,100}',skill):raise ValueError('Invalid Alexa Skill ID')
        value={'enabled':False,'skillId':skill,'userHash':'','key':secrets.token_hex(32)}
        atomic(root/'config.json',value)
        atomic(root/'confirmation.json',{})
        return {'enabled':False,'skillId':skill,'linked':False,'bridgeKey':value['key']}
    if action=='voice_enable':
        if not value.get('key'):raise ValueError('Set up the skill first')
        if type(payload.get('enabled')) is not bool:raise ValueError('Invalid enable setting')
        value['enabled']=payload['enabled'];atomic(root/'config.json',value)
    if action=='voice_pair':
        if not value.get('enabled'):raise ValueError('Enable voice control first')
        code=str(secrets.randbelow(1000000)).zfill(6)
        value['pairHash']=hashlib.sha256(code.encode()).hexdigest();value['pairExpires']=time.time()+300
        value['pairAttempts']=0;atomic(root/'config.json',value)
        return {'code':code,'expires':value['pairExpires']}
    try:
        remote=read(root.parent.parent/'remote-private/status.json',{})
        url=remote.get('url','')
        endpoint=url.rstrip('/')+'/u1-alexa/skill' if isinstance(url,str) and url.startswith('https://') else ''
    except (OSError,ValueError):endpoint=''
    return {'enabled':value.get('enabled',False),'skillId':value.get('skillId',''),'linked':bool(value.get('userHash')),'endpoint':endpoint}

def reply(text,end=True):
    return {'version':'1.0','response':{'outputSpeech':{'type':'PlainText','text':text},'shouldEndSession':end}}

TEXT=json.loads(Path(__file__).with_name('u1_voice_messages.json').read_text(encoding='utf-8'))

class Voice:
    def __init__(self,moon,root=ROOT,clock=time.time):
        self.moon,self.root,self.clock=moon,Path(root),clock
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)

    def receive(self,raw,signature):
        import fcntl
        if len(raw)>65536:raise PermissionError('Request too large')
        cfg=config(self.root)
        authenticated_key=cfg.get('key','')
        expected=hmac.new(authenticated_key.encode(),raw,hashlib.sha256).hexdigest()
        if not cfg.get('enabled') or not cfg.get('key') or not hmac.compare_digest(expected,signature or ''):raise PermissionError('Voice authentication failed')
        body=json.loads(raw);request=body.get('request',{});system=body.get('context',{}).get('System',{})
        session=body.get('session',{});user=system.get('user',{}).get('userId','')
        app=system.get('application',{}).get('applicationId')
        if app!=cfg.get('skillId') or session.get('application',{}).get('applicationId',app)!=app or not user:raise PermissionError('Wrong Alexa account or skill')
        stamp=datetime.datetime.fromisoformat(request.get('timestamp','').replace('Z','+00:00')).timestamp()
        if abs(self.clock()-stamp)>150:raise PermissionError('Expired Alexa request')
        request_id=request.get('requestId','');session_id=session.get('sessionId','')
        if not isinstance(request_id,str) or not 1<=len(request_id)<=250:raise PermissionError('Invalid request ID')
        lang=request.get('locale','').split('-')[0].lower();text=TEXT.get(lang,TEXT['en'])
        with (self.root/'voice.lock').open('a') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return reply(text['unknown'])
            cfg=config(self.root)
            if not cfg.get('enabled') or not hmac.compare_digest(cfg.get('key',''),authenticated_key):raise PermissionError('Voice disabled')
            ledger_path=self.root/'requests.json';ledger=read(ledger_path,{})
            ident=hashlib.sha256(request_id.encode()).hexdigest()
            if ident in ledger:return ledger[ident].get('reply',reply(text['unknown']))
            ledger={k:v for k,v in ledger.items() if self.clock()-v['time']<86400}
            ledger=dict(sorted(ledger.items(),key=lambda item:item[1]['time'])[-999:])
            if sum(self.clock()-v['time']<60 for v in ledger.values())>=30:return reply(text['blocked'])
            ledger[ident]={'time':self.clock()};atomic(ledger_path,ledger)
            user_hash=hashlib.sha256(user.encode()).hexdigest()
            intent=request.get('intent',{});name=intent.get('name');kind=request.get('type')
            if name=='LinkPrinterIntent':
                code=str(intent.get('slots',{}).get('code',{}).get('value','')).replace(' ','')
                if re.fullmatch(r'\d{1,6}',code):code=''.join(str(unicodedata.decimal(c)) for c in code).zfill(6)
                valid=cfg.get('pairExpires',0)>self.clock() and cfg.get('pairAttempts',0)<5 and re.fullmatch(r'\d{6}',code) and hmac.compare_digest(cfg.get('pairHash',''),hashlib.sha256(code.encode()).hexdigest())
                cfg['pairAttempts']=cfg.get('pairAttempts',0)+1
                if valid:cfg.update(userHash=user_hash,pairExpires=0,pairHash='')
                atomic(self.root/'config.json',cfg);result=reply(text['linked'] if valid else text['badcode'])
            elif not hmac.compare_digest(cfg.get('userHash',''),user_hash):result=reply(text['pair'])
            else:
                try:result=self.dispatch(kind,name,intent,session_id,user_hash,str(uuid.uuid5(uuid.NAMESPACE_URL,request_id)),text)
                except Exception:result=reply(text['unknown'])
            ledger[ident]['reply']=result;atomic(ledger_path,ledger)
            return result

    def dispatch(self,kind,name,intent,session,user,ident,text):
        path=self.root/'confirmation.json';pending=read(path,{})
        if kind not in ('IntentRequest','LaunchRequest','SessionEndedRequest'):return reply(text['blocked'])
        if kind=='SessionEndedRequest':
            if pending.get('session')==session:atomic(path,{})
            return reply(text['no'])
        if name in ('AMAZON.NoIntent','AMAZON.CancelIntent','AMAZON.StopIntent'):
            if pending.get('session')==session:atomic(path,{})
            return reply(text['no'])
        if name=='AMAZON.YesIntent':
            atomic(path,{})
            if pending.get('session')!=session or pending.get('user')!=user or pending.get('expires',0)<self.clock():return reply(text['expired'])
            self.moon.relay(pending['operation'],pending['payload'],request_id=ident,timeout=4,expires_at=self.clock()+6)
            return reply(text['sent'])
        atomic(path,{})
        if kind=='LaunchRequest' or name in ('AMAZON.HelpIntent','AMAZON.FallbackIntent'):return reply(text['help'],False)
        if name in ('StatusIntent','RemainingTimeIntent','ErrorStatusIntent'):
            s=self.moon.api('/printer/objects/query?webhooks&print_stats&virtual_sdcard&exception_manager')['status'];stats=s.get('print_stats',{});progress=s.get('virtual_sdcard',{}).get('progress',0)
            state_name=text['states'].get(stats.get('state'),text['states']['unknown'])
            if name=='StatusIntent':return reply(text['status'].format(state=state_name,percent=round(progress*100)))
            if name=='ErrorStatusIntent':
                errors=list(s.get('exception_manager',{}).get('exceptions',[]))
                if stats.get('exception') and stats['exception'] not in errors:errors.append(stats['exception'])
                descriptions=[]
                for fault in errors[:3]:
                    if not isinstance(fault,dict):descriptions.append(str(fault)[:160]);continue
                    if fault.get('id')==523 and fault.get('code')==38:descriptions.append(text['tangled'])
                    elif fault.get('id')==532 and fault.get('code')==1:descriptions.append(text['dirtyBed'])
                    else:descriptions.append(str(fault.get('message') or fault.get('msg') or fault.get('code',''))[:160])
                return reply(text['status'].format(state=state_name,percent=round(progress*100))+' '+text['activeErrors'].format(count=len(errors))+' '+' '.join(descriptions))
            if stats.get('state') not in ('printing','paused') or progress<=0:return reply(text['unavailable'])
            minutes=max(0,round(stats.get('print_duration',0)*(1/progress-1)/60))
            return reply(text['remaining'].format(minutes=minutes))
        operation=None;payload={};question=None
        if name in ('PausePrintIntent','ResumePrintIntent','CancelPrintIntent'):
            state=self.moon.relay('print_player_state',{},timeout=3)
            action={'PausePrintIntent':'pause','ResumePrintIntent':'resume','CancelPrintIntent':'cancel'}[name]
            if action=='resume' and state.get('canAcknowledgeFault') and state.get('pauseFaultToken'):
                if not session or not state.get('currentJob'):return reply(text['blocked'])
                atomic(path,{'session':session,'user':user,'expires':self.clock()+60,'operation':'print_player_action','payload':{'action':'ack_fault','currentJob':state.get('currentJob'),'faultToken':state['pauseFaultToken'],'confirmed':True}})
                return reply(text['untangle'],False)
            if not state.get({'pause':'canPause','resume':'canResume','cancel':'canCancel'}[action]):return reply(text['blocked'])
            operation='print_player_action';payload={'action':action,'currentJob':state['currentJob'],'confirmed':action!='pause'}
            if action=='pause':self.moon.relay(operation,payload,request_id=ident,timeout=4,expires_at=self.clock()+6);return reply(text['sent'])
            question=text[action]
        elif name=='PauseLowerIntent':
            state=self.moon.relay('magnet_state',{},timeout=3)
            operation='magnet_action';payload={'action':'pause','job':state.get('runtimeJob'),'token':state.get('token'),'confirmed':True};question=text['lower']
        elif name in ('RepeatPrintIntent','FavoritePrintIntent'):
            if name=='RepeatPrintIntent':
                jobs=self.moon.api('/server/history/list?limit=1').get('jobs',[])
                if not jobs:return reply(text['blocked'])
                filename=jobs[0]['filename']
            else:
                query=intent.get('slots',{}).get('model',{}).get('value','').strip().casefold()
                if not query:return reply(text['blocked'])
                rows=self.moon.relay('models_state',{},timeout=3)['models']
                if text is TEXT['nl']:
                    index=int(query) if query.isdecimal() else 0
                    matches=[rows[index-1]] if 1<=index<=len(rows) else []
                else:matches=[m for m in rows if m['name'].casefold()==query] or [m for m in rows if query in m['name'].casefold()]
                if len(matches)!=1:return reply(text['blocked'])
                filename=matches[0]['files'][0]
            plan=self.moon.relay('print_player_prepare',{'filename':filename,'mapping':[0,1,2,3],'bedLevel':True,'flowCalibration':False},timeout=4)
            operation='print_player_start';payload={'token':plan['token'],'confirmed':True};question=text['repeat'].format(file=Path(filename).name)
        elif name in ('NightModeOnIntent','NightModeOffIntent'):
            state=self.moon.relay('night_state',{},timeout=3)
            payload={k:state[k] for k in ('revision','start','end','zone')};payload['mode']='on' if name=='NightModeOnIntent' else 'off'
            self.moon.relay('night_configure',payload,request_id=ident,timeout=4,expires_at=self.clock()+6);return reply(text['night'])
        elif name=='MaintenanceIntent':
            state=self.moon.relay('maintenance_state',{},timeout=3)
            extra=''
            if not state.get('serviceDue') and state.get('serviceDueAt'):
                import math
                days=max(0,math.ceil((state['serviceDueAt']-self.clock())/86400))
                extra=' '+text['deadline'].format(days=days)
            return reply(text['maintenance'].format(service=text['yes'] if state.get('serviceDue') else text['noWord'],bed=text['yes'] if state.get('bedDue') else text['noWord'])+extra)
        elif name=='TimedPauseIntent':
            raw=intent.get('slots',{}).get('minutes',{}).get('value','')
            minutes=int(raw)
            if not 1<=minutes<=1440:return reply(text['blocked'])
            plan=self.moon.relay('timed_pause_prepare',{'minutes':minutes},timeout=3)
            operation='timed_pause_arm';payload={'token':plan['token'],'confirmed':True}
            question=text['timer'].format(minutes=minutes)
        elif name=='CancelTimedPauseIntent':
            state=self.moon.relay('timed_pause_state',{},timeout=3)
            self.moon.relay('timed_pause_cancel',{'id':state.get('id')},request_id=ident,timeout=4,expires_at=self.clock()+6)
            return reply(text['sent'])
        else:return reply(text['help'],False)
        if not session:return reply(text['blocked'])
        atomic(path,{'session':session,'user':user,'expires':self.clock()+60,'operation':operation,'payload':payload})
        return reply(question,False)
