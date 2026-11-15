"""Nonblocking local mailbox for the independent Alexa bridge. No Amazon secrets in UI."""
import json,time,uuid,ipaddress,re
from pathlib import Path
from u1_feeder_settings import atomic
ROOT=Path('/userdata/u1-addons/alexa-private')
def state():
 try:
  value=json.loads((ROOT/'status.json').read_text())
  if time.time()-value.get('updatedAt',0)>45:
   return {'phase':'offline','message':'Служба Alexa не отвечает. Уведомления не подтверждены.','devices':[],'loginUrl':None}
  return value
 except (OSError,ValueError):return {'phase':'offline','message':'Мост Alexa ещё не установлен или не запущен.','devices':[],'loginUrl':None}
def enqueue(payload):
 action=payload.get('action');args=payload.get('payload',{})
 if action not in ('login','passkey','complete_passkey','logout','save','test','heard'):raise ValueError('Недопустимая операция Alexa.')
 if not isinstance(args,dict) or len(json.dumps(args).encode())>12000:raise ValueError('Некорректные параметры Alexa.')
 if action in ('login','passkey'):
  host=args.get('host','')
  if not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}',host):raise ValueError('Некорректный адрес принтера.')
  # The login gateway must be reached on this printer, never on an arbitrary external host.
  import socket
  import fcntl,struct
  local={'127.0.0.1'}
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
   for _,name in socket.if_nameindex():
    try:local.add(socket.inet_ntoa(fcntl.ioctl(probe.fileno(),0x8915,struct.pack('256s',name.encode()[:15]))[20:24]))
    except OSError:pass
  try:valid=str(ipaddress.IPv4Address(host)) in local
  except ValueError:valid=host in (socket.gethostname(),socket.gethostname()+'.local')
  if not valid:raise ValueError('Откройте интерфейс по LAN-адресу этого принтера.')
 if action in ('test','heard'):
  if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',str(args.get('id',''))):raise ValueError('Некорректное устройство.')
 if action=='complete_passkey':
  url=args.get('url')
  if not isinstance(url,str) or len(url)>8000:raise ValueError('Нужен адрес страницы Amazon после входа.')
 folder=ROOT/'requests';folder.mkdir(mode=0o700,parents=True,exist_ok=True)
 if len(list(folder.glob('*.json')))>30:raise ValueError('Слишком много запросов. Дождитесь ответа моста.')
 ident=str(uuid.uuid4());atomic(folder/(ident+'.json'),json.dumps({'id':ident,'action':action,'payload':args,'time':time.time()},ensure_ascii=False).encode())
 return {'id':ident,'accepted':True}
