"""Night policy for U1 cover only. Native dynamic temperature control stays enabled."""
import copy,datetime,json,math,re,time,uuid,urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo
from u1_feeder_settings import atomic
QUERY='/printer/objects/query?webhooks&print_stats&purifier&exception_manager&heater_bed&extruder&extruder1&extruder2&extruder3'

def zone(name):
    return datetime.timezone.utc if name=='UTC' else ZoneInfo(name)

def in_window(start,end,minute):
    a,b=int(start[:2])*60+int(start[3:]),int(end[:2])*60+int(end[3:])
    return a<=minute<b if a<b else minute>=a or minute<b

def validate(data):
    if data.get('mode') not in ('off','on','schedule'):raise ValueError('Неверный режим.')
    for key in ('start','end'):
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',str(data.get(key,''))):raise ValueError('Время должно быть ЧЧ:ММ.')
    if data['start']==data['end']:raise ValueError('Начало и окончание должны различаться.')
    zone(data['zone'])
    return data

class NightMode:
    def __init__(self,api,folder,execute=None):
        self.api,self.execute=api,execute
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True,mode=0o700);self.file=self.folder/'state.json'
        self.data=json.loads(self.file.read_text()) if self.file.exists() else {'mode':'off','start':'22:00','end':'07:00','zone':'UTC','revision':str(uuid.uuid4()),'saved':None,'message':'Выключен'}
        validate(self.data);self.last_poll=0
    def save(self):atomic(self.file,json.dumps(self.data,ensure_ascii=False,allow_nan=False).encode())
    def state(self):return copy.deepcopy(self.data)
    def configure(self,payload):
        if payload.get('revision')!=self.data['revision']:raise ValueError('Настройки изменились. Обновите окно.')
        value=validate({k:payload.get(k) for k in ('mode','start','end','zone')})
        if self.file.exists():atomic(self.folder/('before-'+str(uuid.uuid4())+'.json'),self.file.read_bytes())
        self.data={**self.data,**value,'revision':str(uuid.uuid4()),'message':'Настройки сохранены; ожидается проверка U1.'};self.save();self.last_poll=0
        return self.state()
    def command(self,script):
        if self.execute is None:raise ValueError('Исполнитель не подключён.')
        self.execute(script)
    def owned(self,p):
        saved=self.data['saved']
        return saved and p.get('mode')==1 and p.get('desired_chamber_temp')==saved['desired_chamber_temp'] and p.get('critical_chamber_temp')==saved['critical_chamber_temp'] and p.get('exhaust_fan',{}).get('speed_threshold')==0
    def restore(self,p):
        saved=self.data['saved']
        if not saved:return
        if self.owned(p):
            self.command('SET_PURIFIER_MODE MODE=1 DESIRE_TEMP=%g ALARM_TEMP=%g FAN_SPEED=%g DYNAMIC_FAN_CONTROL=1'%(saved['desired_chamber_temp'],saved['critical_chamber_temp'],saved['threshold']))
        # A new native mode/threshold takes priority; never overwrite it.
        self.data['saved']=None;self.save()
    def tick(self,store,force=False):
        if not force and time.monotonic()-self.last_poll<5:return
        self.last_poll=time.monotonic()
        try:
            s=self.api(QUERY)['status'];p=s.get('purifier',{})
            if s.get('webhooks',{}).get('state')!='ready':raise ValueError('Klipper недоступен; ожидается возврат штатного управления.')
            now=datetime.datetime.now(zone(self.data['zone']));wanted=self.data['mode']=='on' or self.data['mode']=='schedule' and in_window(self.data['start'],self.data['end'],now.hour*60+now.minute)
            if not wanted:
                self.restore(p);message='Выключен; управление штатное.'
            elif not p.get('power_detected') or s.get('exception_manager',{}).get('exceptions',[True]) or store.calibration_jobs.active:
                self.restore(p);message='Ограничен: ошибка, калибровка или крышка не подключена.'
            elif p.get('mode')!=1:
                self.restore(p);message='Ожидание: в режиме прогрева/горячей камеры и простоя управление полностью штатное.'
            else:
                config=self.api('/printer/objects/query?configfile')['status']['configfile']['settings']['purifier']
                sensor=config.get('external_temp_sensor')
                if not sensor:raise ValueError('Не найден датчик температуры камеры; ночной режим не применяется.')
                chamber=self.api('/printer/objects/query?temperature_sensor%20'+urllib.parse.quote(sensor,safe=''))['status']['temperature_sensor '+sensor].get('temperature')
                if type(chamber) not in (float,int) or not math.isfinite(chamber) or not 0<chamber<100:raise ValueError('Некорректный датчик камеры.')
                if not 0<p.get('desired_chamber_temp',0)<p.get('critical_chamber_temp',0):raise ValueError('Нет штатных температурных порогов.')
                if chamber>=p['desired_chamber_temp']:
                    self.restore(p);message='Ограничен: камера требует штатного охлаждения.'
                else:
                    if self.data['saved'] and not self.owned(p):self.data['saved']=None;self.save()
                    if not self.data['saved']:
                        self.data['saved']={'desired_chamber_temp':p['desired_chamber_temp'],'critical_chamber_temp':p['critical_chamber_temp'],'threshold':p.get('exhaust_fan',{}).get('speed_threshold',.6)};self.save()
                        self.command('SET_PURIFIER_MODE MODE=1 DESIRE_TEMP=%g ALARM_TEMP=%g FAN_SPEED=0 DYNAMIC_FAN_CONTROL=1'%(p['desired_chamber_temp'],p['critical_chamber_temp']))
                    message='Включён: минимальная вытяжка 0%; штатная динамика может поднять скорость. Внутренний вентилятор — штатный режим охлаждения.'
            if self.data.get('message')!=message:self.data['message']=message;self.save()
        except Exception as error:
            # Leave pending restoration durable. Do not send a blind fan-off command.
            try:
                if 'p' in locals() and s.get('webhooks',{}).get('state')=='ready':self.restore(p)
            except Exception:pass
            self.data['message']='Не применяется: '+str(error);self.save()
