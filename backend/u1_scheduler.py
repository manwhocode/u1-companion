"""Persistent U1 scheduler. Only an explicitly armed job may call the stock start API."""
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import time
import urllib.parse
import uuid
from u1_feeder_settings import atomic
from u1_calibration_jobs import QUERY, reason, require_idle

ACTIVE = {'armed','starting'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def numeric(value, low=0, high=1e12):
    return type(value) in (float,int) and math.isfinite(value) and low <= value <= high

async def _native_start(filename, options):
    from tornado.websocket import websocket_connect
    socket = await websocket_connect('ws://127.0.0.1:7125/websocket',connect_timeout=8,max_message_size=4*1024*1024)
    try:
        await socket.write_message(json.dumps({'jsonrpc':'2.0','id':1,'method':'server.files.start_local_print','params':{'path':filename,'options':options}}))
        while True:
            raw = await asyncio.wait_for(socket.read_message(),30)
            if raw is None: raise RuntimeError('Связь потеряна после запроса запуска. Автоматического повтора не будет.')
            response = json.loads(raw)
            if response.get('id') != 1: continue
            if 'error' in response: raise RuntimeError(str(response['error']))
            result = response.get('result',{})
            if not isinstance(result,dict) or result.get('state') != 'success': raise RuntimeError(str(result))
            return result
    finally: socket.close()

def native_start(filename, options):
    return asyncio.run(_native_start(filename,options))


def native_pause_action(action):
    import urllib.request
    if action not in ('pause', 'resume', 'cancel'):
        raise ValueError('Недопустимая команда паузы.')
    request = urllib.request.Request('http://127.0.0.1:7125/printer/print/' + action, method='POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)['result']


class TimedPause:
    """One-shot stock pause/resume. Never restore an armed timer after restart."""
    QUERY = '/printer/objects/query?webhooks&pause_resume&print_stats&virtual_sdcard&toolhead&heater_bed&purifier&machine_state_manager&exception_manager'
    ACTIVE = {'pausing', 'waiting_pause', 'armed', 'resuming', 'checking_resume'}

    def __init__(self, api, folder, control=None, clock=time.time, monotonic=time.monotonic):
        self.api, self.control, self.clock, self.monotonic = api, control or native_pause_action, clock, monotonic
        self.folder = Path(folder); self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = self.folder / 'state.json'; self.plans = {}; self.last_poll = -1e9
        try:
            self.job = json.loads(self.file.read_text()) if self.file.exists() else {'state':'idle', 'message':''}
            if not isinstance(self.job, dict) or self.job.get('state') not in self.ACTIVE | {'idle','cancelled','blocked','resumed','needs_review'}:
                raise ValueError('Invalid timer')
        except Exception:
            self.job = {'state':'needs_review','message':'Таймер повреждён; автоматическое продолжение отключено.'}
        if self.active:
            self.update(state='needs_review', message='Сервис или принтер перезапускался. Продолжите печать вручную после проверки.')
        self.wall, self.mono = self.clock(), self.monotonic()

    @property
    def active(self): return self.job.get('state') in self.ACTIVE

    def update(self, **values):
        value = {**self.job, **values, 'updatedAt':self.clock()}
        atomic(self.file, json.dumps(value, ensure_ascii=False, allow_nan=False).encode()); self.job = value

    def stock_bed_ack_supported(self):
        try:
            return hashlib.sha256(Path('/home/lava/printer_data/config/fluidd.cfg').read_bytes()).hexdigest() == 'ede05f50709c808e0775498f62e9c44a758f33c1f4684f51fb3cf0d87cb2b46e'
        except OSError:
            return False

    def bed_ack_allowed(self, s):
        stats = s.get('print_stats', {}); fault = stats.get('exception', {})
        return (self.stock_bed_ack_supported() and stats.get('state') == 'paused'
                and fault == {'id':532,'index':0,'code':1,'message':'detected dirty bed','level':2}
                and stats.get('info', {}).get('current_layer') == 0
                and stats.get('filament_used') == 0 and stats.get('print_duration') == 0
                and s.get('pause_resume', {}).get('is_paused') is True
                and set('xy').issubset(s.get('toolhead', {}).get('homed_axes', '')))

    def snapshot(self, safety=True, acknowledge_bed=False, manual=False):
        s = self.api(self.QUERY)['status']
        history = self.api('/server/history/list?limit=1').get('jobs', [])
        stats = s.get('print_stats', {}); machine = s.get('machine_state_manager', {})
        magnet = self.folder.parent / 'magnet-pauses' / 'state.json'
        if safety and not manual and magnet.exists() and json.loads(magnet.read_text()).get('requiresManualResume') is True:
            raise ValueError('После установки магнитов продолжите печать вручную. Автотаймер заблокирован.')
        if s.get('webhooks', {}).get('state') != 'ready' or stats.get('state') not in ('printing','paused'):
            raise ValueError('Нет активной печати или Klipper не готов.')
        main = machine.get('main_state'); action = machine.get('action_code')
        if safety and (not (main == 'PRINTING' or (type(main) is int and main == 1)) or not (action == 'IDLE' or (type(action) is int and action == 0))):
            raise ValueError('Дождитесь завершения штатной операции принтера.')
        if safety and (s.get('exception_manager', {}).get('exceptions', [True]) or (stats.get('exception') and not (acknowledge_bed and self.bed_ack_allowed(s)))):
            raise ValueError('На принтере есть ошибка. Автоматическое продолжение запрещено.')
        if safety and s.get('purifier', {}).get('power_detected') is not True:
            raise ValueError('Подключение верхнего кожуха не подтверждено.')
        if not history or history[0].get('status') != 'in_progress' or history[0].get('filename') != stats.get('filename'):
            raise ValueError('Текущее задание не подтверждено историей печати.')
        row = history[0]
        if not row.get('job_id') or not numeric(row.get('start_time'), 1):
            raise ValueError('Не удалось определить экземпляр печати.')
        sd = s.get('virtual_sdcard', {}); position = sd.get('file_position')
        if not sd.get('file_path') or not numeric(position) or not numeric(sd.get('file_size'), 1):
            raise ValueError('Нет состояния штатного файла печати.')
        return s, digest([row['job_id'], row['start_time'], stats['filename'], sd['file_path'], sd['file_size']])

    def state(self):
        try:
            s, identity = self.snapshot(); eligible = True; problem = ''
        except Exception as error:
            s, identity, eligible, problem = {}, None, False, str(error)
        return {**copy.deepcopy(self.job), 'now':self.clock(), 'eligible':eligible, 'reason':problem,
                'printState':s.get('print_stats', {}).get('state'), 'currentJob':identity,
                'currentFilename':s.get('print_stats', {}).get('filename')}

    def player_state(self):
        s = self.api(self.QUERY)['status']; stats=s.get('print_stats',{}); machine=s.get('machine_state_manager',{})
        ready=s.get('webhooks',{}).get('state')=='ready'
        identity=None; safe=False; reason=''; can_ack_bed=False
        if stats.get('state') in ('printing','paused'):
            try:
                _,identity=self.snapshot(False)
                self.snapshot(manual=True);safe=True
            except Exception as error:reason=str(error)
            if self.bed_ack_allowed(s):
                try:
                    self.snapshot(acknowledge_bed=True); can_ack_bed=True
                except Exception: pass
        progress=s.get('virtual_sdcard',{}).get('progress',0)
        return {'ready':ready,'state':stats.get('state','unknown'),'filename':stats.get('filename',''),
                'progress':min(1,max(0,progress)) if numeric(progress) else 0,'duration':stats.get('print_duration',0),'currentJob':identity,'reason':reason,
                'canStart':ready and stats.get('state') in ('standby','complete','cancelled') and machine.get('main_state') in (0,'IDLE') and machine.get('action_code') in (0,'IDLE'),
                'canPause':safe and stats.get('state')=='printing',
                'canResume':safe and stats.get('state')=='paused' and s.get('pause_resume',{}).get('is_paused') is True and set('xyz').issubset(s.get('toolhead',{}).get('homed_axes','')),
                'canAcknowledgeBed':can_ack_bed,
                'canCancel':ready and identity is not None}

    def player_action(self, ident, payload):
        action=payload.get('action')
        if action not in ('pause','resume','cancel','ack_bed'):raise ValueError('Неизвестная команда плеера.')
        if action in ('resume','cancel','ack_bed') and payload.get('confirmed') is not True:raise ValueError('Подтвердите действие с текущей печатью.')
        s,identity=self.snapshot(safety=action!='cancel', acknowledge_bed=action=='ack_bed', manual=True)
        if payload.get('currentJob')!=identity:raise ValueError('Задание изменилось. Проверьте текущую печать.')
        state=s['print_stats']['state']
        if action=='ack_bed' and not self.bed_ack_allowed(s):raise ValueError('Предупреждение или стадия печати изменились. Проверьте U1.')
        if action=='pause' and state!='printing':raise ValueError('Печать уже приостановлена.')
        if action=='resume' and (state!='paused' or s.get('pause_resume',{}).get('is_paused') is not True or not set('xyz').issubset(s.get('toolhead',{}).get('homed_axes',''))):
            raise ValueError('Штатная пауза или позиция осей не подтверждена.')
        ledger=self.folder/'player-requests.json'
        try:requests=json.loads(ledger.read_text()) if ledger.exists() else {}
        except (ValueError,OSError):raise ValueError('Журнал команд повреждён. Автоповтор запрещён; проверьте принтер.')
        if not isinstance(requests,dict):raise ValueError('Журнал команд повреждён.')
        if ident in requests:return {'message':'Этот запрос уже передавался. Проверьте состояние принтера; повтора не будет.'}
        requests={k:v for k,v in requests.items() if isinstance(v,dict) and v.get('job')==identity}
        if len(requests)>=512:raise ValueError('Журнал команд заполнен. Проверьте дополнение; команда не отправлена.')
        requests[ident]={'action':action,'job':identity,'phase':'sending','time':self.clock()}
        atomic(ledger,json.dumps(requests,ensure_ascii=False).encode())
        if self.active:self.update(state='cancelled',message='Таймер отключён ручной командой управления печатью.')
        try:
            self.control('resume' if action=='ack_bed' else action)
            requests[ident]['phase']='accepted';message='Штатный запрос отправлен. Обновляется состояние принтера.'
        except Exception:
            requests[ident]['phase']='unknown';message='Ответ на команду не получен. Автоповтора нет; проверьте принтер.'
        atomic(ledger,json.dumps(requests,ensure_ascii=False).encode())
        return {'message':message}

    def prepare(self, store, payload):
        minutes = payload.get('minutes')
        if not numeric(minutes, 1, 1440): raise ValueError('Укажите интервал от 1 минуты до 24 часов.')
        if self.active or store.scheduler.active or store.calibration_jobs.active:
            raise ValueError('Сначала отмените активный таймер или дождитесь операции.')
        if store.dryer.state().get('state') in ('heating','running','paused','interrupted'):
            raise ValueError('Сначала отмените сушку.')
        s, identity = self.snapshot()
        token = str(uuid.uuid4())
        self.plans = {token:{'createdAt':self.clock(),'identity':identity,'minutes':minutes,'filename':s['print_stats']['filename']}}
        return {**self.plans[token], 'token':token, 'alreadyPaused':s['print_stats']['state']=='paused'}

    def arm(self, store, payload):
        plan = self.plans.pop(payload.get('token'), None)
        if not plan or not 0 <= self.clock()-plan['createdAt'] <= 30 or payload.get('confirmed') is not True:
            raise ValueError('Подтверждение истекло. Проверьте таймер заново.')
        s, identity = self.snapshot()
        if self.active or store.scheduler.active or store.calibration_jobs.active or identity != plan['identity']:
            raise ValueError('Печать или состояние изменились.')
        if self.file.exists(): atomic(self.folder/('before-'+str(uuid.uuid4())+'.json'), self.file.read_bytes())
        self.job = {}
        self.update(id=str(uuid.uuid4()), identity=identity, filename=plan['filename'], seconds=plan['minutes']*60,
                    originalBedTarget=s['heater_bed']['target'], originalBedTemperature=s['heater_bed']['temperature'],
                    state='pausing', message='Запрос штатной паузы отправляется один раз.')
        try:
            if s['print_stats']['state']=='printing': self.control('pause')
            self.update(state='waiting_pause', deadline=self.clock()+45, message='Ожидается подтверждение штатной паузы.')
            self.tick(store, force=True)
        except Exception as error:
            self.update(state='needs_review', message='Результат паузы не подтверждён: '+str(error)+'. Автоповтора нет.')
        return self.state()

    def cancel(self, payload):
        if payload.get('id') != self.job.get('id'): raise ValueError('Таймер изменился. Обновите окно.')
        if self.job.get('state') in ('resuming','checking_resume'): raise ValueError('Запрос продолжения уже отправлен. Используйте штатную паузу.')
        self.update(state='cancelled', message='Таймер отменён. Состояние печати не изменено.')
        return self.state()

    def tick(self, store, force=False):
        if not self.active: return
        now, mono = self.clock(), self.monotonic()
        if abs((now-self.wall)-(mono-self.mono)) > 10:
            self.update(state='needs_review', message='Системное время изменилось. Таймер отключён.'); return
        self.wall, self.mono = now, mono
        if not force and mono-self.last_poll < 2: return
        self.last_poll = mono
        try:
            s, identity = self.snapshot()
            if identity != self.job['identity']: raise ValueError('Текущее задание изменилось.')
            paused = s['print_stats']['state']=='paused' and s.get('pause_resume',{}).get('is_paused') is True
            phase = self.job['state']
            if phase == 'checking_resume':
                if s['print_stats']['state']=='printing' and not s.get('pause_resume',{}).get('is_paused'):
                    self.update(state='resumed', message='Штатное продолжение печати подтверждено.')
                elif now > self.job['deadline']: raise ValueError('Продолжение не подтверждено; автоматического повтора нет.')
                return
            if phase == 'waiting_pause':
                if not paused:
                    if now > self.job['deadline']: raise ValueError('Пауза не подтверждена.')
                    return
                if s['heater_bed']['target'] != self.job['originalBedTarget']:
                    raise ValueError('Во время паузы изменена температура стола.')
                self.update(state='armed', resumeAt=now+self.job['seconds'],
                            position=s['virtual_sdcard']['file_position'], bedTarget=s['heater_bed']['target'],
                            positionSnapshot=s['toolhead']['position'], message='Печать на паузе. Ожидается время продолжения.')
                return
            if phase != 'armed': raise ValueError('Неопределённый результат команды.')
            if not paused: raise ValueError('Пауза снята вручную или печать остановлена.')
            if s['virtual_sdcard']['file_position'] != self.job['position']: raise ValueError('Позиция файла изменилась.')
            if s['toolhead'].get('position') != self.job['positionSnapshot']: raise ValueError('Головка перемещалась во время паузы.')
            if not set('xyz').issubset(s['toolhead'].get('homed_axes','')): raise ValueError('Позиция осей потеряна.')
            bed = s['heater_bed']; target = self.job['bedTarget']
            if bed.get('target') != target or (target > 0 and bed.get('temperature',0) < target-10):
                raise ValueError('Настройка стола изменилась или стол остыл.')
            if self.job['originalBedTemperature'] > 40 and bed.get('temperature',0) < self.job['originalBedTemperature']-10:
                raise ValueError('Стол остыл относительно температуры перед паузой.')
            if now < self.job['resumeAt']: return
            if now-self.job['resumeAt'] > 15: raise ValueError('Время продолжения пропущено.')
            self.update(state='resuming', message='Отправляется одна штатная команда продолжения; без автоповтора.')
            self.control('resume')
            self.update(state='checking_resume', deadline=self.clock()+120, message='U1 принял запрос. Проверяется продолжение печати.')
        except Exception as error:
            self.update(state='blocked', message='Автоматическое продолжение отключено: '+str(error))

class Scheduler:
    def __init__(self, api, folder, root='/home/lava/printer_data/gcodes', start=None, clock=time.time, monotonic=time.monotonic):
        self.api, self.start, self.clock, self.monotonic = api, start, clock, monotonic
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.file=self.folder/'state.json';self.root=Path(root).resolve();self.plans={};self.instant={}
        try:
            self.job=json.loads(self.file.read_text()) if self.file.exists() else {'state':'idle','message':''}
            if not isinstance(self.job,dict) or self.job.get('state') not in ('idle','armed','starting','started','blocked','cancelled','needs_review'):raise ValueError('Некорректное состояние')
            if self.job.get('state')=='armed' and (not numeric(self.job.get('startAt')) or not re.fullmatch(r'[0-9a-f]{64}',str(self.job.get('fingerprint')))):raise ValueError('Повреждён план')
        except Exception:
            self.job={'state':'needs_review','message':'Файл расписания повреждён. Автозапуск отключён; подготовьте новое расписание.'}
        if self.job.get('state') == 'starting' or (self.job.get('state') == 'armed' and self.clock() >= self.job.get('startAt',0)):
            self.update(state='needs_review',message='Сервис перезапускался во время/после срока запуска. Проверьте принтер и перенесите расписание; автоматического повтора не будет.')
        self.last_wall,self.last_mono=self.clock(),self.monotonic()

    @property
    def active(self): return self.job.get('state') in ACTIVE

    def update(self, **values):
        after={**self.job,**values,'updatedAt':self.clock()}
        atomic(self.file,json.dumps(after,ensure_ascii=False,allow_nan=False).encode())
        self.job=after

    def state(self): return {**copy.deepcopy(self.job),'now':self.clock()}

    def path(self, filename):
        if (not isinstance(filename,str) or len(filename)>512 or not filename.lower().endswith('.gcode') or
                any(c in filename for c in '\\"\n\r;#') or filename.startswith('/') or '..' in PurePosixPath(filename).parts):
            raise ValueError('Выберите обычный .gcode внутри gcodes; кавычки, # и служебные символы не поддерживаются.')
        path=self.root/filename
        if path.is_symlink() or not path.resolve().is_relative_to(self.root) or not path.is_file(): raise ValueError('G-code удалён или расположен вне каталога печати.')
        return path

    def file_info(self, filename):
        path=self.path(filename);before=path.stat();sha=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):sha.update(chunk)
        after=path.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Файл изменился при чтении.')
        metadata=self.api('/server/files/metadata?filename='+urllib.parse.quote(filename,safe=''))
        if metadata.get('size') != after.st_size or not numeric(metadata.get('modified')) or abs(metadata['modified']-after.st_mtime)>1:
            raise ValueError('Метаданные ещё не соответствуют файлу. Дождитесь обработки G-code.')
        return path,metadata,{'sha256':sha.hexdigest(),'size':after.st_size,'metadata':digest(metadata)}

    def check(self, store, filename, mapping):
        if store.calibration_jobs.active:raise ValueError('Выполняется калибровка.')
        for name in ('drying','dryer'):
            file=store.folder/name/'state.json'
            if file.exists() and json.loads(file.read_text()).get('state') in ('running','heating','paused','cooling','starting','interrupted'):
                raise ValueError('Активна сушка. Отложенный старт отменён.')
        status=self.api(QUERY+'&heater_bed')['status']
        require_idle(status,cover=True)
        if any(status.get(name,{}).get('target',1)!=0 for name in ('extruder','extruder1','extruder2','extruder3','heater_bed')):
            raise ValueError('Есть активный нагрев или сушка. Сначала выключите нагрев.')
        queue=self.api('/server/job_queue/status')
        if queue.get('queued_jobs') or queue.get('queue_state') not in ('paused','ready'):
            raise ValueError('В штатной очереди есть задания или выполняется переход.')
        path,metadata,file_signature=self.file_info(filename)
        if metadata.get('slicer') not in ('SnapmakerOrca','OrcaSlicer'):raise ValueError('Для расписания нужен G-code Snapmaker Orca / OrcaSlicer с метаданными.')
        weights=metadata.get('filament_weight');lengths=metadata.get('filament_used_mm')
        if not isinstance(weights,list) or not 1<=len(weights)<=4 or any(not numeric(x) for x in weights):raise ValueError('Не определён расход до четырёх филаментов.')
        if not isinstance(lengths,list) or len(lengths)!=len(weights) or any(not numeric(x) for x in lengths):raise ValueError('Не определены длины филаментов.')
        used=[i for i,x in enumerate(weights) if x>0 or lengths[i]>0]
        if not used or any(weights[i]<=0 for i in used):raise ValueError('Не определена масса используемого филамента.')
        if not isinstance(mapping,list) or len(mapping)!=4 or any(type(x) is not int or x not in range(4) for x in mapping) or len({mapping[i] for i in used})!=len(used):
            raise ValueError('Каждому используемому филаменту назначьте отдельную головку.')
        types=(metadata.get('filament_type') or '').split(';');colors=(metadata.get('filament_colour') or '').split(';')
        task=status['print_task_config'];inventory=store.get('fluidd','u1_spool_inventory_v1',{});library=store.get('fluidd','u1_filament_library_v1',{})
        usage=store.get('fluidd','u1_spool_usage_v1',{});spools={s['id']:s for s in inventory.get('spools',[])};presets={p['id']:p for p in library.get('entries',[])}
        rows=[];bindings=[]
        for logical in used:
            head=mapping[logical];why=reason(status,head)
            if why:raise ValueError('Головка '+str(head+1)+': '+why)
            material=task['filament_type'][head].upper();hexcode='#'+task['filament_color_rgba'][head][:6].upper()
            if logical>=len(types) or logical>=len(colors) or types[logical].upper()!=material or colors[logical].upper()!=hexcode:
                raise ValueError('T'+str(logical+1)+': материал/цвет файла не совпадает с головкой '+str(head+1)+'.')
            spool=spools.get((inventory.get('heads') or [None]*4)[head])
            if not spool or spool['material'].upper()!=material or spool['hex'].upper()!=hexcode:raise ValueError('Привяжите подходящую «Мою катушку» к головке '+str(head+1)+'.')
            remaining=spool['grams']-max(0,usage.get('totals',{}).get(spool['id'],0)-spool.get('accountedGrams',0))
            if remaining+0.001<weights[logical]:raise ValueError('Головка '+str(head+1)+': недостаточно филамента ('+str(round(remaining,1))+' г).')
            diameter=metadata.get('nozzle_diameter')
            if not numeric(diameter,.1,1) or abs(status.get('extruder'+(str(head) if head else ''),{}).get('nozzle_diameter',0)-diameter)>.001:
                raise ValueError('Диаметр сопла не совпадает с G-code.')
            rows.append({'logical':logical,'head':head,'material':material,'hex':hexcode,'name':spool['name'],'required':weights[logical],'remaining':remaining})
            bindings.append({'head':head,'spool':spool,'preset':presets.get(spool['colorId']),'spent':usage.get('totals',{}).get(spool['id'],0)})
        data={'library':library,'inventory':inventory}
        from u1_filament_profiles import PrintPlan
        simulated=copy.deepcopy(task);simulated['extruder_map_table']=mapping+[0]*28
        PrintPlan(data,simulated,str(path))
        last=self.api('/server/history/list?limit=1')['jobs']
        firmware=self.api('/printer/info').get('software_version')
        if not isinstance(firmware,str) or not firmware:raise ValueError('Не определена версия прошивки U1.')
        snapshot={'firmware':firmware,'file':file_signature,'bindings':bindings,'individualCalibration':inventory.get('individualCalibration',False),
                  'lastJob':[{k:j.get(k) for k in ('job_id','start_time')} for j in last]}
        return {'fingerprint':digest(snapshot),'rows':rows,'estimated':metadata.get('estimated_time')}

    def prepare_start(self, store, payload):
        if self.active or getattr(getattr(store,'timed_pause',None),'active',False):raise ValueError('Сначала отмените активное расписание или таймер.')
        filename=payload.get('filename');mapping=payload.get('mapping',[0,1,2,3])
        checked=self.check(store,filename,mapping)
        if type(payload.get('bedLevel',True)) is not bool or type(payload.get('flowCalibration',False)) is not bool:
            raise ValueError('Некорректные параметры подготовки.')
        token=str(uuid.uuid4())
        value={**checked,'token':token,'filename':filename,'mapping':mapping,'createdAt':self.clock(),
               'options':{'map_table':json.dumps([[i,h] for i,h in enumerate(mapping)]),
                          'bed_level':int(payload.get('bedLevel',True)),'flow_calibrate':int(payload.get('flowCalibration',False)),'shaper_calibrate':0}}
        self.instant={token:copy.deepcopy(value)};return value

    def start_now(self, store, payload):
        plan=self.instant.pop(payload.get('token'),None)
        if not plan or not 0<=self.clock()-plan['createdAt']<=120:raise ValueError('Проверка запуска истекла. Проверьте файл заново.')
        if payload.get('confirmed') is not True:raise ValueError('Подтвердите свободный стол и запуск печати.')
        if self.active or getattr(getattr(store,'timed_pause',None),'active',False):raise ValueError('Сначала отмените активное расписание или таймер.')
        if self.check(store,plan['filename'],plan['mapping'])['fingerprint']!=plan['fingerprint']:
            raise ValueError('Файл, катушки или параметры изменились. Повторите проверку.')
        if self.file.exists():atomic(self.folder/('before-'+str(uuid.uuid4())+'.json'),self.file.read_bytes())
        self.update(**plan,id=str(uuid.uuid4()),mode='immediate',startAt=self.clock(),state='starting',message='Передаётся один штатный запрос запуска U1.')
        try:
            if self.start is None:raise RuntimeError('Исполнитель запуска не подключён.')
            result=self.start(plan['filename'],plan['options'])
            if not isinstance(result,dict) or result.get('state')!='success':raise RuntimeError('Запуск не подтверждён.')
            self.update(state='started',message='Штатный U1 принял запрос запуска печати.')
        except Exception:
            self.update(state='needs_review',message='Результат запуска не подтверждён. Не повторяйте запуск без проверки принтера.')
        return self.state()

    def prepare(self, store, payload):
        filename=payload.get('filename');mapping=payload.get('mapping',[0,1,2,3]);checked=self.check(store,filename,mapping)
        duration=checked['estimated'];overhead=payload.get('preparationMinutes',10)
        if not numeric(duration,1,30*86400) or not numeric(overhead,0,120):raise ValueError('Нет надёжного прогноза длительности или неверен запас подготовки.')
        duration+=overhead*60;mode=payload.get('mode');now=self.clock()
        if mode=='delay':
            delay=payload.get('delayMinutes')
            if not numeric(delay,1,30*24*60):raise ValueError('Интервал должен быть от 1 минуты до 30 дней.')
            start=now+delay*60
        elif mode in ('at','finish'):
            start=payload.get('when')
            if not numeric(start):raise ValueError('Выберите дату и время.')
            if mode=='finish':start-=duration
        else:raise ValueError('Выберите режим расписания.')
        if not now+60<=start<=now+30*86400:raise ValueError('Начало должно быть через 1 минуту — 30 дней. Для окончания выберите более позднее время.')
        for key in ('bedLevel','flowCalibration'):
            if type(payload.get(key)) is not bool:raise ValueError('Выберите параметры штатной подготовки.')
        plan={'id':str(uuid.uuid4()),'filename':filename,'mapping':mapping,'mode':mode,'startAt':start,'finishAt':start+duration,'duration':duration,
              'preparationMinutes':overhead,'options':{'map_table':json.dumps([[i,h] for i,h in enumerate(mapping)]),'bed_level':int(payload['bedLevel']),'flow_calibrate':int(payload['flowCalibration']),'shaper_calibrate':0},
              **checked,'createdAt':now,'replaces':self.job.get('id')}
        self.plans={plan['id']:copy.deepcopy(plan)}
        return plan

    def arm(self, store, payload):
        plan=self.plans.get(payload.get('planId'))
        if not plan or self.clock()-plan['createdAt']>600 or plan['startAt']<self.clock()+30:raise ValueError('Предпросмотр истёк. Проверьте расписание заново.')
        if self.job.get('id')!=plan['replaces'] or self.job.get('state')=='starting':raise ValueError('Расписание изменилось; обновите окно.')
        if payload.get('consent') is not True or payload.get('bedClear') is not True:raise ValueError('Явно разрешите автоматический запуск и подтвердите свободный стол.')
        if self.check(store,plan['filename'],plan['mapping'])['fingerprint']!=plan['fingerprint']:raise ValueError('Файл, катушки или задание изменились. Повторите проверку.')
        if self.file.exists():atomic(self.folder/('before-'+str(uuid.uuid4())+'.json'),self.file.read_bytes())
        self.update(**plan,state='armed',message='Ожидается назначенное время. Перед стартом будет повторная проверка.')
        self.plans={};return self.state()

    def cancel(self, payload):
        if payload.get('id')!=self.job.get('id'):raise ValueError('Расписание изменилось.')
        if self.job.get('state') not in ('armed','blocked','needs_review'):raise ValueError('Запрос запуска уже отправлен. Для остановки печати используйте штатную отмену.')
        self.update(state='cancelled',message='Автоматический запуск отменён пользователем.');return self.state()

    def tick(self, store):
        now,mono=self.clock(),self.monotonic();jump=abs((now-self.last_wall)-(mono-self.last_mono))>15
        self.last_wall,self.last_mono=now,mono
        if self.job.get('state')!='armed':return
        if jump:
            self.update(state='needs_review',message='Изменилось системное время. Проверьте и перенесите расписание.');return
        if now<self.job['startAt']:return
        if now-self.job['startAt']>30:
            self.update(state='needs_review',message='Время запуска пропущено. Нужна новая проверка и подтверждение.');return
        try:
            checked=self.check(store,self.job['filename'],self.job['mapping'])
            if checked['fingerprint']!=self.job['fingerprint']:raise ValueError('После подтверждения изменились файл, катушки, параметры или история печати.')
        except Exception as error:
            self.update(state='blocked',message='Автоматический старт отменён: '+str(error));return
        if not self.job['startAt']<=self.clock()<=self.job['startAt']+30:
            self.update(state='needs_review',message='Срок изменился или проверка заняла слишком долго. Перенесите запуск.');return
        options=self.job.get('options',{})
        if (set(options)!={'map_table','bed_level','flow_calibrate','shaper_calibrate'} or options.get('map_table')!=json.dumps([[i,h] for i,h in enumerate(self.job['mapping'])]) or
                any(type(options.get(k)) is not int or options[k] not in (0,1) for k in ('bed_level','flow_calibrate','shaper_calibrate'))):
            self.update(state='needs_review',message='Параметры запуска повреждены. Автозапуск отключён.');return
        self.update(state='starting',message='Запрос штатного старта отправляется один раз; повтор после ошибки запрещён.')
        try:
            if self.start is None:raise RuntimeError('Штатный исполнитель не подключён.')
            result=self.start(self.job['filename'],self.job['options'])
            if not isinstance(result,dict) or result.get('state')!='success':raise RuntimeError(str(result))
            self.update(state='started',message='Штатный U1 принял запрос запуска. Следите за состоянием принтера.')
        except Exception as error:
            self.update(state='needs_review',message='Результат запроса не подтверждён: '+str(error)+'. Автоматического повтора не будет; проверьте принтер.')
