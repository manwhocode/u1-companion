"""Backup-first dedicated Klipper dryer installation; no heater commands."""
import hashlib,json,os,time,urllib.request
from pathlib import Path
from u1_profile_install import guard,atomic
ROOT=Path('/home/lava/u1-addons/filament-ui')
PRINTER=Path('/oem/printer_data/config/printer.cfg')
LINK=Path('/home/lava/klipper/klippy/extras/u1_dryer.py')
BLOCK='# BEGIN U1 BED DRYER\n[include u1-dryer.cfg]\n# END U1 BED DRYER\n'
CONFIG='# U1 FILAMENT ADDON bed-only dryer\n[u1_dryer]\nchamber_sensor: cavity\n'
def api(path,post=False):return json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:7125'+path,method='POST' if post else 'GET'),timeout=10))['result']
def restart(expected):
 api('/printer/restart',True)
 for _ in range(40):
  time.sleep(1)
  try:
   status=api('/printer/objects/query?webhooks'+('&u1_dryer' if expected else ''))['status']
   if status['webhooks']['state']=='ready' and (not expected or status.get('u1_dryer',{}).get('version')==1):return
  except Exception:pass
 raise RuntimeError('Klipper dryer readiness timeout')
def rollback(backup):
 backup=Path(backup);manifest=json.loads((backup/'manifest.json').read_text())
 raw=PRINTER.read_bytes();old=(backup/'printer.cfg').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=manifest['afterHash'] and raw!=old:raise RuntimeError('Config changed; automatic rollback stopped')
 atomic(PRINTER,old,manifest['mode'],tuple(manifest['owner']))
 for key in ('module','include'):
  path=Path(manifest[key]);prior=backup/(key+'.before')
  if prior.exists():atomic(path,prior.read_bytes())
  elif path.exists():path.unlink()
 if LINK.is_symlink() and str(LINK.readlink())==manifest['module']:LINK.unlink()
 if manifest['hadLink']:LINK.symlink_to(manifest['module'])
 restart(manifest['hadLink'])
def install(source,backup):
 guard();source,backup=Path(source),Path(backup);module=ROOT/'u1_dryer.py';include=PRINTER.parent/'u1-dryer.cfg'
 job=Path('/userdata/u1-addons/filament-ui-data/schedule/state.json')
 if job.exists() and json.loads(job.read_text()).get('state') in ('armed','starting'):raise RuntimeError('Cancel schedule first')
 state=Path('/userdata/u1-addons/filament-ui-data/drying/state.json')
 if state.exists() and json.loads(state.read_text()).get('state') in ('heating','running','paused','interrupted'):raise RuntimeError('Cancel drying and remove spool first')
 config=api('/printer/objects/query?configfile')['status']['configfile']['settings']
 if config['purifier'].get('external_temp_sensor')!='cavity':raise RuntimeError('Unknown chamber sensor')
 raw=PRINTER.read_bytes();text=raw.decode();marker='#*# <---------------------- SAVE_CONFIG ---------------------->'
 if 'u1-dryer.cfg' in text:
  if text.count(BLOCK)!=1:raise RuntimeError('Foreign dryer include')
  new=raw
 else:new=(text.replace(marker,BLOCK+'\n'+marker,1) if marker in text else text.rstrip()+'\n\n'+BLOCK).encode()
 if include.exists() and include.read_text()!=CONFIG:raise RuntimeError('Foreign dryer config')
 if (LINK.exists() or LINK.is_symlink()) and (not LINK.is_symlink() or str(LINK.readlink())!=str(module)):raise RuntimeError('Foreign dryer link')
 code=(source/'u1_dryer.py').read_bytes();compile(code,str(module),'exec');backup.mkdir(mode=0o700,parents=True,exist_ok=False)
 (backup/'printer.cfg').write_bytes(raw);stat=PRINTER.stat()
 for key,path in (('module',module),('include',include)):
  if path.exists():(backup/(key+'.before')).write_bytes(path.read_bytes())
 manifest={'module':str(module),'include':str(include),'hadLink':LINK.is_symlink(),'mode':stat.st_mode&0o777,'owner':[stat.st_uid,stat.st_gid],'afterHash':hashlib.sha256(new).hexdigest()}
 (backup/'manifest.json').write_text(json.dumps(manifest));guard()
 try:
  if PRINTER.read_bytes()!=raw:raise RuntimeError('Config changed')
  atomic(module,code);atomic(include,CONFIG.encode())
  if not LINK.is_symlink():LINK.symlink_to(module)
  atomic(PRINTER,new,manifest['mode'],tuple(manifest['owner']));restart(True)
 except BaseException:rollback(backup);raise
 return str(backup)
