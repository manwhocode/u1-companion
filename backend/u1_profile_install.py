"""Install/remove only the owned U1 profile module and one marked config include."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

BEGIN = '# BEGIN U1 FILAMENT PRINT PROFILES'
END = '# END U1 FILAMENT PRINT PROFILES'
BLOCK = BEGIN + '\n[include u1-filament-profiles.cfg]\n' + END + '\n'
CONFIG = '# U1 FILAMENT ADDON print profiles\n[u1_filament_profiles]\n'
ROOT = Path('/home/lava/u1-addons/filament-ui')
PRINTER = Path('/oem/printer_data/config/printer.cfg')
EXTRAS = Path('/home/lava/klipper/klippy/extras/u1_filament_profiles.py')


def api(path, post=False):
    request = urllib.request.Request('http://127.0.0.1:7125' + path, method='POST' if post else 'GET')
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)['result']


def guard():
    query = '/printer/objects/query?webhooks&print_stats&idle_timeout&machine_state_manager&exception_manager&extruder&extruder1&extruder2&extruder3&heater_bed'
    state = api(query)['status']
    if (state['webhooks']['state'] != 'ready' or state['print_stats']['state'] not in ('standby', 'complete', 'cancelled') or
        state['idle_timeout']['state'] != 'Idle' or state['machine_state_manager'].get('main_state') not in (0, 'IDLE') or
        state['machine_state_manager'].get('action_code') not in (0, 'IDLE') or state['exception_manager'].get('exceptions', [True]) or
        any(state[name]['target'] != 0 for name in ('extruder', 'extruder1', 'extruder2', 'extruder3', 'heater_bed'))):
        raise RuntimeError('Wait for idle U1 with all heater targets zero and no active errors')
    job = Path('/userdata/u1-addons/filament-ui-data/calibration-jobs/state.json')
    if job.exists() and json.loads(job.read_text()).get('state') in ('starting', 'loading', 'calibrating', 'saving', 'finishing'):
        raise RuntimeError('Calibration queue active')


def include_config(raw):
    text = raw.decode('utf-8')
    if BEGIN in text:
        if text.count(BLOCK) != 1 or text.count(BEGIN) != 1 or text.count(END) != 1:
            raise ValueError('Modified add-on include; stopped')
        return raw
    if 'u1-filament-profiles.cfg' in text or END in text:
        raise ValueError('Unexpected existing print-profile include; stopped')
    marker = '#*# <---------------------- SAVE_CONFIG ---------------------->'
    if marker in text:
        text = text.replace(marker, BLOCK + '\n' + marker, 1)
    else:
        text = text.rstrip('\n') + '\n\n' + BLOCK
    return text.encode('utf-8')


def atomic(path, data, mode=0o644, owner=None):
    path = Path(path)
    temporary = path.with_name(path.name + '.u1-profiles-next')
    with temporary.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(mode)
    if owner and hasattr(os, 'chown'):
        os.chown(temporary, *owner)
    os.replace(temporary, path)


def restart(expect_module):
    api('/printer/restart', True)
    last = 'not ready'
    for _ in range(40):
        time.sleep(1)
        try:
            query = '/printer/objects/query?webhooks' + ('&u1_filament_profiles' if expect_module else '')
            status = api(query)['status']
            if status['webhooks']['state'] == 'ready' and (not expect_module or status.get('u1_filament_profiles', {}).get('version') == 1):
                return
            last = status['webhooks'].get('state_message', str(status))
        except Exception as error:
            last = str(error)
    raise RuntimeError('Klipper did not become ready: ' + last)


def rollback(backup, do_restart=True):
    backup = Path(backup)
    manifest = json.loads((backup / 'profiles-manifest.json').read_text())
    printer, include, module, link = [Path(manifest[key]) for key in ('printer', 'include', 'module', 'link')]
    current = printer.read_bytes()
    if current == (backup / 'printer.cfg').read_bytes() or hashlib.sha256(current).hexdigest() == manifest['afterHash']:
        original = (backup / 'printer.cfg').read_bytes()
    else:
        # Preserve calibration/SAVE_CONFIG or other user edits made since install.
        text = current.decode('utf-8')
        if text.count(BLOCK) != 1:
            raise RuntimeError('Config changed and include cannot be removed safely')
        original = text.replace(BLOCK, '', 1).encode()
    atomic(printer, original, manifest['mode'], tuple(manifest['owner']))
    for name, path in (('include', include), ('module', module)):
        old = backup / (name + '.before')
        if old.exists():
            atomic(path, old.read_bytes())
        elif path.exists():
            path.unlink()
    if link.is_symlink() and str(link.readlink()) == str(module):
        link.unlink()
    if manifest['hadLink']:
        link.symlink_to(module)
    if do_restart:
        restart(manifest['hadLink'])


def install(source, backup, printer=PRINTER, module=ROOT / 'u1_filament_profiles.py', link=EXTRAS):
    source, backup, printer, module, link = map(Path, (source, backup, printer, module, link))
    guard()
    raw = printer.read_bytes()
    rewritten = include_config(raw)
    include = printer.parent / 'u1-filament-profiles.cfg'
    if include.exists() and include.read_text() != CONFIG:
        raise RuntimeError('Foreign profile config; stopped')
    if (link.exists() or link.is_symlink()) and (not link.is_symlink() or str(link.readlink()) != str(module)):
        raise RuntimeError('Foreign module at print-profile path; stopped')
    code = (source / 'u1_filament_profiles.py').read_bytes()
    compile(code, str(module), 'exec')
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    (backup / 'printer.cfg').write_bytes(raw)
    for name, path in (('include', include), ('module', module)):
        if path.exists():
            (backup / (name + '.before')).write_bytes(path.read_bytes())
    stat = printer.stat()
    manifest = {'printer': str(printer), 'include': str(include), 'module': str(module), 'link': str(link),
                'hadLink': link.is_symlink(), 'mode': stat.st_mode & 0o777, 'owner': [stat.st_uid, stat.st_gid],
                'afterHash': hashlib.sha256(rewritten).hexdigest()}
    (backup / 'profiles-manifest.json').write_text(json.dumps(manifest))
    guard()
    if printer.read_bytes() != raw:
        raise RuntimeError('Config changed during preparation; nothing installed')
    try:
        atomic(module, code)
        atomic(include, CONFIG.encode())
        if not link.is_symlink():
            link.symlink_to(module)
        atomic(printer, rewritten, manifest['mode'], tuple(manifest['owner']))
        restart(True)
    except BaseException:
        rollback(backup)
        raise
    return str(backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root on U1')
    if not args.backup.resolve().is_relative_to(Path('/userdata/u1-addons-backups')):
        raise SystemExit('Backup must be inside /userdata/u1-addons-backups')
    if args.rollback:
        guard()
        rollback(args.backup)
    else:
        print('Profile backup:', install(args.source, args.backup))
