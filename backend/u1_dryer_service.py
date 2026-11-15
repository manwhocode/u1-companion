"""Serialized UI bridge for the Klipper bed-only dryer and saved user profiles."""
import copy,json,math,re,time,uuid
from pathlib import Path
from u1_feeder_settings import atomic
from u1_dryer import validate,ACTIVE,DRYER_COMMAND_PREFIX
class Dryer:
 def __init__(self,api,folder,execute=None):
  self.api,self.execute=api,execute;self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True,mode=0o700);self.file=self.folder/'profiles.json';self.last_heartbeat=0
 def notifications(self):
  try:return json.loads((self.folder/'notifications.json').read_text()).get('enabled') is True
  except FileNotFoundError:return True
  except (ValueError,OSError):return False
 def state(self):
  from u1_alexa import state as alexa_state
  a=alexa_state();config=a.get('config',{})
  available=a.get('phase')=='connected' and config.get('enabled') is True and bool(set(config.get('targets',[])) & set(config.get('confirmed',[])))
  return {**self.api('/printer/objects/query?u1_dryer')['status']['u1_dryer'],'alexaNotifications':self.notifications(),'alexaAvailable':available}
 def configure_notifications(self,payload):
  enabled=payload.get('enabled')
  if type(enabled) is not bool:raise ValueError('Некорректная настройка уведомлений.')
  if enabled and not self.state()['alexaAvailable']:raise ValueError('Подключите Alexa и включите уведомления для проверенного устройства в настройках дополнения.')
  target=self.folder/'notifications.json'
  if target.exists():atomic(self.folder/('notifications-before-'+str(uuid.uuid4())+'.json'),target.read_bytes())
  atomic(target,json.dumps({'enabled':enabled}).encode());return self.state()
 def profiles(self):return json.loads(self.file.read_text()) if self.file.exists() else {'revision':'','entries':{}}
 def change(self,payload):
  value=self.profiles()
  if payload.get('revision')!=value['revision']:raise ValueError('Профили изменились. Обновите окно.')
  key=payload.get('key','')
  if not re.fullmatch(r'(?:material:[A-Z0-9_-]{1,20}|color:[a-zA-Z0-9_-]{1,120})',key):raise ValueError('Не выбрана основа профиля.')
  temp,seconds,limit=payload.get('temperature'),payload.get('seconds'),payload.get('limit');validate(temp,seconds,limit)
  value['entries'][key]={'temperature':temp,'seconds':seconds,'limit':limit};value['revision']=str(uuid.uuid4())
  if self.file.exists():atomic(self.folder/('before-'+str(uuid.uuid4())+'.json'),self.file.read_bytes())
  atomic(self.file,json.dumps(value,ensure_ascii=False).encode());return value
 def action(self,store,payload):
  action=payload.get('action')
  if action not in ('start','pause','resume','cancel'):raise ValueError('Неизвестная команда сушки.')
  if self.execute is None:raise ValueError('Исполнитель недоступен.')
  if action in ('start','resume'):
   if payload.get('confirmed') is not True:raise ValueError('Проверьте размещение и термостойкость катушки.')
   if store.calibration_jobs.active or store.scheduler.active:raise ValueError('Сначала отмените расписание печати или дождитесь калибровки.')
   if store.night.data.get('mode')!='off' or store.night.data.get('saved'):raise ValueError('Выключите ночной режим и дождитесь штатного управления крышкой.')
   queue=self.api('/server/job_queue/status')
   if queue.get('queued_jobs') or queue.get('queue_state') not in ('paused','ready'):raise ValueError('В штатной очереди есть задания.')
  if self.state().get('commandVersion',0)<2:raise ValueError('Модуль сушки требует обновления команд. Обновление разрешено только после окончания печати.')
  script=DRYER_COMMAND_PREFIX+action.upper()
  if action=='start':
   temp,seconds,limit=payload.get('temperature'),payload.get('seconds'),payload.get('limit');validate(temp,seconds,limit)
   script+=' TEMP=%g SECONDS=%g LIMIT=%g CONFIRM=1'%(temp,seconds,limit)
  elif action=='resume':script+=' CONFIRM=1'
  self.execute(script)
  result=self.state()
  expected={'start':('heating','running'),'resume':('heating','running'),'pause':('paused',),'cancel':('cancelled',)}
  if result.get('state') not in expected[action]:raise ValueError('Действие сушки не подтверждено принтером. Проверьте состояние; автоматического повтора нет.')
  return result
 def heartbeat(self):
  if time.monotonic()-self.last_heartbeat<10:return
  self.last_heartbeat=time.monotonic()
  try:
   state=self.state()
   if state.get('state') in ACTIVE and state.get('commandVersion',0)>=2 and self.execute:self.execute(DRYER_COMMAND_PREFIX+'HEARTBEAT')
  except Exception:pass # independent Klipper watchdog removes heat when the lease expires
