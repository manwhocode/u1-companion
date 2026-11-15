"""Typed adapters for Companion print-control workflows. Preparation never executes."""
import math

EXTRA = {
 'pause_lower': {}, 'clear_layer_pauses': {}, 'restore_print': {},
 'pause_with_timer': {'minutes': {'type':'number'}},
 'cancel_pause_timer': {}, 'cancel_scheduled_print': {},
 'schedule_print': {'filename': {'type':'string'}, 'minutes': {'type':'number'}},
 'set_layer_pauses': {'layers': {'type':'string'}},
 'set_cover_fan': {'fan': {'type':'string','enum':['inner','exhaust']}, 'percent': {'type':'integer','minimum':0,'maximum':100}}
}
LABELS = {'pause_lower':'Пауза с опусканием стола', 'clear_layer_pauses':'Удалить план пауз по слоям',
 'restore_print':'Восстановить печать из контрольной точки', 'pause_with_timer':'Пауза с продолжением по таймеру',
 'cancel_pause_timer':'Отменить таймер продолжения', 'cancel_scheduled_print':'Отменить отложенный запуск',
 'schedule_print':'Запланировать печать', 'set_layer_pauses':'Паузы по слоям текущей печати', 'set_cover_fan':'Изменить вентилятор крышки'}

def minutes(args):
 v=args['minutes']
 if type(v) not in (int,float) or not math.isfinite(v) or not 0 < v <= 10080:raise ValueError('Интервал должен быть от 0 до 10080 минут.')
 return v

def prepare(moon, name, args):
 if set(args)!=set(EXTRA[name]):raise ValueError('Неизвестные параметры управления.')
 filename=None
 if name=='pause_with_timer':
  plan=moon.relay('timed_pause_prepare',{'minutes':minutes(args)})
  operation='timed_pause_arm';payload={'token':plan['token'],'confirmed':True}
 elif name=='schedule_print':
  filename=args['filename'];plan=moon.relay('schedule_prepare',{'filename':filename,'mode':'delay','mapping':[0,1,2,3],'delayMinutes':minutes(args),'when':None,'preparationMinutes':10,'bedLevel':True,'flowCalibration':False})
  operation='schedule_arm';payload={'planId':plan['id'],'consent':True,'bedClear':True}
 elif name=='restore_print':
  plan=moon.relay('recovery_prepare',{});operation='recovery_resume';payload={'token':plan['token'],'confirmed':True}
 elif name in ('pause_lower','clear_layer_pauses','set_layer_pauses'):
  state=moon.relay('magnet_state',{});filename=state.get('currentFilename')
  if name=='set_layer_pauses':
   if not isinstance(args['layers'],str) or len(args['layers'])>500:raise ValueError('Укажите номера слоёв через запятую.')
   plan=moon.relay('magnet_prepare',{'filename':filename,'layers':args['layers'],'mode':'current','job':state.get('runtimeJob')})
   operation='magnet_arm';payload={'token':plan['token'],'confirmed':True}
  else:
   operation='magnet_action';payload={'action':'pause' if name=='pause_lower' else 'clear','job':state.get('runtimeJob'),'token':state.get('token'),'confirmed':True}
 elif name in ('cancel_pause_timer','cancel_scheduled_print'):
  prefix='timed_pause' if name=='cancel_pause_timer' else 'schedule'
  state=moon.relay(prefix+'_state',{});operation=prefix+'_cancel';payload={'id':state.get('id')}
 else:
  fan=args['fan'];percent=args['percent']
  if fan not in ('inner','exhaust') or type(percent)!=int or not 0<=percent<=100:raise ValueError('Некорректная скорость вентилятора.')
  p=moon.api('/printer/objects/query?purifier')['status']['purifier']
  payload={'fan':fan,'percent':percent};operation='cover_fan'
  cover_script(p,fan,percent)
 if name=='schedule_print':payload['bedClear']=True
 summary=LABELS[name]+' · '+str(args) if args else LABELS[name]
 if name=='schedule_print':summary+=' — подтвердите свободный стол и разрешение автоматического старта по таймеру'
 if name=='restore_print':summary+=' — подтвердите, что модель прочно закреплена и контрольная точка подходит'
 if name in ('pause_lower','set_layer_pauses'):summary+=' — зона движения стола свободна; продолжение после вставки магнитов вручную'
 return {'operation':operation,'payload':payload,'filename':filename,'summary':summary}

def cover_script(p,fan,percent):
 if not p.get('power_detected') or p.get('mode') not in (0,1):raise ValueError('Крышка недоступна или работает прогрев камеры.')
 if fan=='inner' or p['mode']==0:return 'SET_PURIFIER FAN=%s SPEED=%s'%(fan,percent/100)
 desired=p.get('desired_chamber_temp');critical=p.get('critical_chamber_temp')
 if type(desired) not in (int,float) or type(critical) not in (int,float) or not 0<desired<critical or not math.isfinite(critical):raise ValueError('Не подтверждены температурные защиты камеры.')
 return 'SET_PURIFIER_MODE MODE=1 DESIRE_TEMP=%s ALARM_TEMP=%s FAN_SPEED=%s DYNAMIC_FAN_CONTROL=1'%(desired,critical,percent/100)
