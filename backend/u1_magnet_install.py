"""Owned additive module installation; ready/idle-only, full rollback, no motion."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from u1_profile_install import guard, atomic

ROOT = Path('/home/lava/u1-addons/filament-ui')
PRINTER = Path('/oem/printer_data/config/printer.cfg')
LINK = Path('/home/lava/klipper/klippy/extras/u1_magnet_pause.py')
BLOCK = '# BEGIN U1 MAGNET PAUSES\n[include u1-magnet-pauses.cfg]\n# END U1 MAGNET PAUSES\n'
CONFIG = '# U1 Companion magnet pauses\n[u1_magnet_pause]\n'


def api(path, post=False):
    return json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:7125'+path, method='POST' if post else 'GET'), timeout=10))['result']


def restart(expected):
    api('/printer/restart', True)
    for _ in range(40):
        time.sleep(1)
        try:
            s = api('/printer/objects/query?webhooks'+('&u1_magnet_pause' if expected else ''))['status']
            if s['webhooks']['state'] == 'ready' and (not expected or s['u1_magnet_pause'].get('available') is True): return
        except Exception: pass
    raise RuntimeError('Модуль пауз не стал готов. Выполняется откат.')


def rollback(backup):
    backup = Path(backup); m = json.loads((backup/'manifest.json').read_text())
    raw = PRINTER.read_bytes()
    if raw != (backup/'printer.cfg').read_bytes() and hashlib.sha256(raw).hexdigest() != m['afterHash']:
        raise RuntimeError('printer.cfg изменился, автоматический откат остановлен.')
    atomic(PRINTER, (backup/'printer.cfg').read_bytes(), m['mode'], tuple(m['owner']))
    for name in ('module', 'include'):
        path = Path(m[name]); old = backup/(name+'.before')
        if old.exists(): atomic(path, old.read_bytes())
        elif path.exists(): path.unlink()
    if LINK.is_symlink() and str(LINK.readlink()) == m['module']: LINK.unlink()
    if m['hadLink']: LINK.symlink_to(m['module'])
    restart(m['hadLink'])


def install(source, backup):
    guard()
    if not Path('/oem/.debug').is_file(): raise RuntimeError('Сначала включите сохранность установки с согласия владельца.')
    # Fail closed on firmware/macro variants not audited for source offsets and resume.
    for path, expected in [('/home/lava/printer_data/config/fluidd.cfg', 'ede05f50709c808e0775498f62e9c44a758f33c1f4684f51fb3cf0d87cb2b46e'),
                           ('/home/lava/klipper/klippy/extras/virtual_sdcard.py', '38e769f078ee637c3393008e8d0dbb87dc4261ea1f1cd6ae9061fdb23673dc1e')]:
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected: raise RuntimeError('Неизвестная версия штатных пауз U1; установка остановлена.')
    for name, phases in [('schedule', ('armed','starting')), ('timed-pause', ('armed','pausing','waiting_pause','resuming','checking_resume')), ('drying', ('heating','running','paused','interrupted'))]:
        state = Path('/userdata/u1-addons/filament-ui-data')/name/'state.json'
        if state.exists() and json.loads(state.read_text()).get('state') in phases: raise RuntimeError('Сначала завершите ' + name)
    source, backup = Path(source), Path(backup)
    module, include = ROOT/'u1_magnet_pause.py', PRINTER.parent/'u1-magnet-pauses.cfg'
    raw = PRINTER.read_bytes(); text = raw.decode(); marker = '#*# <---------------------- SAVE_CONFIG ---------------------->'
    if 'u1-magnet-pauses.cfg' in text:
        if text.count(BLOCK) != 1: raise RuntimeError('Чужое подключение пауз.')
        updated = raw
    else: updated = (text.replace(marker, BLOCK+'\n'+marker, 1) if marker in text else text.rstrip()+'\n\n'+BLOCK).encode()
    if include.exists() and include.read_text() != CONFIG: raise RuntimeError('Чужой конфиг пауз.')
    if (LINK.exists() or LINK.is_symlink()) and (not LINK.is_symlink() or str(LINK.readlink()) != str(module)):
        raise RuntimeError('Чужой модуль по пути дополнения.')
    code = (source/'u1_magnet_pause.py').read_bytes(); compile(code, str(module), 'exec')
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    (backup/'printer.cfg').write_bytes(raw); stat = PRINTER.stat()
    for name, path in [('module', module), ('include', include)]:
        if path.exists(): (backup/(name+'.before')).write_bytes(path.read_bytes())
    m = {'module':str(module),'include':str(include),'hadLink':LINK.is_symlink(),'mode':stat.st_mode&0o777,'owner':[stat.st_uid,stat.st_gid],'afterHash':hashlib.sha256(updated).hexdigest()}
    (backup/'manifest.json').write_text(json.dumps(m)); guard()
    try:
        if PRINTER.read_bytes() != raw: raise RuntimeError('Конфигурация изменилась.')
        atomic(module, code); atomic(include, CONFIG.encode())
        if not LINK.is_symlink(): LINK.symlink_to(module)
        atomic(PRINTER, updated, m['mode'], tuple(m['owner'])); restart(True)
    except BaseException:
        rollback(backup); raise
    return str(backup)
