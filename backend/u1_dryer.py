"""U1 bed-only dryer. Reactor watchdog is independent of the external worker."""
import copy,json,math,os,time
from pathlib import Path
ACTIVE={'heating','running','paused'}
DRYER_COMMAND_PREFIX='COMPANION_DRYER_'

def validate(temp,seconds,limit):
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (temp,seconds,limit)):
        raise ValueError('Параметры должны быть числами.')
    if not 30<=temp<=80 or not 60<=seconds<=28800 or not 25<=limit<=60:
        raise ValueError('Стол 30–80°C, время 1 мин — 8 ч, предел камеры 25–60°C.')

class Session:
    def __init__(self):
        self.state='idle';self.remaining=0.;self.temp=0.;self.limit=60.;self.message='Сушка выключена';self.last=0.;self.lease=0.;self.deadline=0.
    def start(self,temp,seconds,limit,now,mode='bed',chamber_target=None):
        validate(temp,seconds,limit)
        if mode not in ('bed','chamber'): raise ValueError('Invalid drying mode')
        if mode == 'chamber' and (type(chamber_target) not in (int,float) or not math.isfinite(chamber_target) or not 25 <= chamber_target <= min(55,limit-3)): raise ValueError('Chamber target must be 25–55 °C and below the safety limit by 3 °C')
        if self.state in ACTIVE:raise ValueError('Сначала завершите текущую сушку.')
        self.mode, self.chamber_target, self.heating = mode, chamber_target, True
        self.temp,self.remaining,self.limit=temp,seconds,limit
        self.state='heating';self.message='Нагрев стола';self.last=now;self.lease=now+35;self.deadline=now+28800
    def heartbeat(self,now):self.lease=now+35
    def pause(self,message):self.state='paused';self.message=message
    def resume(self,chamber,now):
        if self.state!='paused':raise ValueError('Сессия не на паузе.')
        if now>=self.deadline or self.remaining<=0:raise ValueError('Срок сессии истёк. Создайте новую сессию.')
        if chamber>=self.limit-3:raise ValueError('Камера должна остыть ниже порога минимум на 3°C.')
        self.heating=True
        self.state='heating';self.message='Нагрев после паузы';self.last=now;self.heartbeat(now)
    def tick(self,now,bed,chamber,reason='',target=None):
        dt=max(0,now-self.last);self.last=now
        if self.state not in ACTIVE:return False
        if now>=self.deadline:
            self.state='completed';self.message='Достигнут предел сессии 8 часов; нагрев выключен.';return True
        if reason or now>self.lease:
            self.pause(reason or 'Служба управления не отвечает более 35 секунд.');return True
        if chamber>=self.limit:
            self.pause('Достигнут предел температуры камеры.');return True
        if self.state=='paused':return False
        if target is not None and abs(target-(self.temp if getattr(self,'heating',True) else 0))>.01:
            self.pause('Штатная система или пользователь изменили нагрев.');return True
        if getattr(self,'mode','bed') == 'chamber':
            if chamber >= self.chamber_target: self.heating = False
            elif chamber <= self.chamber_target-2: self.heating = True
            if chamber >= self.chamber_target-2:
                self.state='running';self.message='Идёт сушка; таймер отсчитывается при нагретой камере';self.remaining=max(0,self.remaining-dt)
            else: self.state='heating';self.message='Нагрев камеры'
            if self.remaining<=0:self.state='completed';self.message='Таймер завершён; нагрев выключен.';return True
            return False
        if self.state=='heating' and bed>=self.temp-2:self.state='running';self.message='Идёт сушка; таймер отсчитывается при нагретом столе'
        elif self.state=='running':
            if bed<self.temp-5:self.state='heating';self.message='Восстановление температуры стола'
            else:self.remaining=max(0,self.remaining-dt)
        if self.remaining<=0:self.state='completed';self.message='Таймер завершён; нагрев выключен.';return True
        return False
    def status(self):return {k:copy.deepcopy(v) for k,v in self.__dict__.items() if k not in ('last','lease')}

class U1Dryer:
    def __init__(self,config):
        self.printer=config.get_printer();self.reactor=self.printer.get_reactor();self.gcode=self.printer.lookup_object('gcode');self.session=Session();self.original_timeout=None
        self.file=Path(config.get('state_file','/userdata/u1-addons/filament-ui-data/drying/state.json'))
        self.sensor_name=config.get('chamber_sensor','cavity');self.last_saved=0.;self.heat_started=0.;self.last_chamber_sample=-1e12
        self.bed=None;self.chamber=None;self.bed_read=None;self.chamber_read=None
        if self.file.exists():
            try:old=json.loads(self.file.read_text())
            except Exception:old={'state':'paused'}
            if old.get('state') in ACTIVE or old.get('state')=='interrupted':self.session.state='interrupted';self.session.message='Klipper перезапущен. Нагрев не возобновлён; нужна новая сессия.'
        for name,method in [('START',self.start),('PAUSE',self.pause),('RESUME',self.resume),('CANCEL',self.cancel),('HEARTBEAT',self.heartbeat)]:self.gcode.register_command(DRYER_COMMAND_PREFIX+name,method)
        self.printer.register_event_handler('klippy:ready',self.ready)
        self.printer.register_event_handler('klippy:shutdown',self.shutdown)
    def ready(self):
        self.bed=self.printer.lookup_object('heater_bed').heater;self.chamber=self.printer.lookup_object('temperature_sensor '+self.sensor_name)
        original_sample=self.chamber.temperature_callback
        def sample(read_time,temp):
            original_sample(read_time,temp);self.last_chamber_sample=self.reactor.monotonic()
        self.chamber.sensor.setup_callback(sample)
        vsd=self.printer.lookup_object('virtual_sdcard');original=vsd.do_resume
        def guarded():
            self.check_print();return original()
        vsd.do_resume=guarded
        for name in ('SDCARD_PRINT_FILE','SDCARD_PRINT_FILE_WITH_PARAMETERS','SDCARD_PRINT_PL_RESTORE','M24'):
            old=self.gcode.register_command(name,None)
            if old is not None:
                def guarded_command(gcmd,handler=old):self.check_print();return handler(gcmd)
                self.gcode.register_command(name,guarded_command)
        self.persist()
        self.reactor.register_timer(self.poll,self.reactor.NOW)
    def check_print(self):
        if self.session.state in ACTIVE or self.session.state=='interrupted':raise self.printer.command_error('Сначала отмените сушку и уберите катушки со стола.')
    def persist(self):
        self.file.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        tmp=self.file.with_suffix('.next')
        with tmp.open('w',encoding='utf-8') as f:
            os.chmod(tmp,0o600);f.write(json.dumps(self.get_status(),ensure_ascii=False));f.flush();os.fsync(f.fileno())
        os.replace(tmp,self.file)
    def status(self,name):return self.printer.lookup_object(name).get_status(self.reactor.monotonic())
    def sensors(self):
        if self.reactor.monotonic()-self.last_chamber_sample>5:raise ValueError('Датчик камеры не обновлялся более 5 секунд.')
        b=self.bed.get_status(self.reactor.monotonic());c=self.chamber.get_status(self.reactor.monotonic());bed=self.bed.get_temp(self.reactor.monotonic())[0];chamber=c.get('temperature')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<v<110 for v in (bed,chamber)):raise ValueError('Недостоверные показания датчиков.')
        self.bed_read,self.chamber_read=bed,chamber
        return bed,chamber,b.get('target')
    def guard(self,starting=False):
        if self.status('print_stats')['state'] in ('printing','paused'):raise ValueError('Выполняется печать или пауза печати.')
        m=self.status('machine_state_manager')
        if m.get('main_state') not in (0,'IDLE') or m.get('action_code') not in (0,'IDLE'):raise ValueError('Принтер занят.')
        if self.status('exception_manager').get('exceptions',[True]):raise ValueError('Есть активные ошибки U1.')
        if self.status('purifier').get('power_detected') is not True:raise ValueError('Не подтверждено подключение крышки.')
        for n in ('extruder','extruder1','extruder2','extruder3'):
            if self.status(n).get('target',1)!=0:raise ValueError('Сопла нагреваются. Разрешён только нагрев стола.')
        bed,chamber,target=self.sensors()
        if starting and target!=0:raise ValueError('Стол уже нагревается.')
        return bed,chamber,target
    def set_heat(self,target):
        self.printer.lookup_object('heaters').set_temperature(self.bed,target,False)
    def stop_heat(self):
        if self.bed is not None:self.set_heat(0)
        if self.original_timeout is not None:
            self.gcode.run_script_from_command('SET_IDLE_TIMEOUT TIMEOUT=%g'%self.original_timeout);self.original_timeout=None
    def start(self,gcmd):
        try:
            if gcmd.get_int('CONFIRM',0)!=1:raise ValueError('Подтвердите размещение и термостойкость катушки.')
            bed,chamber,target=self.guard(True)
            temp=gcmd.get_float('TEMP');duration=gcmd.get_float('SECONDS');limit=gcmd.get_float('LIMIT',60)
            validate(temp,duration,limit)
            if bed>temp+5:raise ValueError('Стол слишком горячий для выбранной температуры. Дождитесь охлаждения.')
            if chamber>=limit-3:raise ValueError('Камера слишком горячая для старта.')
            mode=getattr(gcmd,'get',lambda k,d:d)('MODE','bed');chamber_target=gcmd.get_float('CHAMBER',0)
            self.session.start(temp,duration,limit,self.reactor.monotonic(),mode,chamber_target);self.persist()
            self.original_timeout=self.printer.lookup_object('idle_timeout').idle_timeout
            self.gcode.run_script_from_command('SET_IDLE_TIMEOUT TIMEOUT=30000')
            self.heat_started=self.reactor.monotonic();self.set_heat(temp)
        except Exception as error:
            if self.session.state in ('heating','running'):self.session.pause(str(error));self.stop_heat();self.persist()
            raise gcmd.error(str(error))
    def heartbeat(self,gcmd):
        if self.session.state in ACTIVE:self.session.heartbeat(self.reactor.monotonic())
    def pause(self,gcmd):
        if self.session.state not in ACTIVE:raise gcmd.error('Нет активной сушки.')
        self.session.pause('Пауза пользователя. Нагрев выключен.');self.stop_heat();self.persist()
    def resume(self,gcmd):
        try:
            if gcmd.get_int('CONFIRM',0)!=1:raise ValueError('Подтвердите продолжение сушки.')
            bed,chamber,target=self.guard(True);self.session.resume(chamber,self.reactor.monotonic());self.persist()
            self.original_timeout=self.printer.lookup_object('idle_timeout').idle_timeout;self.gcode.run_script_from_command('SET_IDLE_TIMEOUT TIMEOUT=30000')
            self.heat_started=self.reactor.monotonic();self.set_heat(self.session.temp)
        except Exception as error:
            if self.session.state in ('heating','running'):self.session.pause(str(error));self.stop_heat();self.persist()
            raise gcmd.error(str(error))
    def cancel(self,gcmd):
        if self.session.state not in ACTIVE and self.session.state!='interrupted':raise gcmd.error('Нет активной сушки.')
        self.session.state='cancelled';self.session.message='Сушка отменена; нагрев выключен.';self.stop_heat();self.persist()
    def shutdown(self):
        if self.session.state in ACTIVE:
            self.session.state='interrupted';self.session.message='Аварийная остановка Klipper. Нагрев не возобновлять автоматически.'
            try:self.persist()
            except Exception:pass
    def poll(self,now):
        if self.session.state in ACTIVE:
            try:
                bed,chamber,target=self.guard()
                reason='Стол не достиг температуры за 30 минут.' if self.session.state=='heating' and now-self.heat_started>1800 else ''
                off=self.session.tick(now,bed,chamber,reason,target)
                if off:self.stop_heat();self.persist()
                elif self.session.state in ('heating','running') and getattr(self.session,'mode','bed') == 'chamber':
                    wanted=self.session.temp if self.session.heating else 0
                    if target != wanted:self.set_heat(wanted)
                if self.session.state=='paused' and target!=0:self.stop_heat()
                if now-self.last_saved>30:self.persist();self.last_saved=now
            except Exception as error:
                self.session.pause('Защита: '+str(error))
                try:self.stop_heat();self.persist()
                except Exception:self.printer.invoke_shutdown('U1 dryer could not turn off bed safely')
        return now+1
    def get_status(self,eventtime=None):
        if self.bed is not None and self.chamber is not None:
            self.bed_read=self.bed.get_temp(self.reactor.monotonic())[0]
            self.chamber_read=self.chamber.get_status(self.reactor.monotonic()).get('temperature')
        return {'version':1,'commandVersion':3,**self.session.status(),'bedTemperature':self.bed_read,'chamberTemperature':self.chamber_read,'watchdogSeconds':35}

def load_config(config):return U1Dryer(config)
