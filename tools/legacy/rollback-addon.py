#!/usr/bin/env python3
"""Restore add-on files/config only; leave firmware and library untouched."""
import argparse, datetime, json, os, pathlib, shutil, subprocess, tarfile, urllib.request
p=argparse.ArgumentParser();p.add_argument('--backup',required=True);args=p.parse_args()
if os.geteuid()!=0:raise SystemExit('Run as root on U1')
home=pathlib.Path('/home/lava/u1-addons/filament-ui')
backup=pathlib.Path(args.backup).resolve()
if not any(backup.is_relative_to(folder.resolve()) for folder in [home/'backups', pathlib.Path('/userdata/u1-addons-backups')]):raise SystemExit('Backup must be inside an add-on backup folder')
job_file=pathlib.Path('/userdata/u1-addons/filament-ui-data/calibration-jobs/state.json')
if job_file.exists() and json.loads(job_file.read_text()).get('state') in ('starting','loading','calibrating','saving','finishing'): raise SystemExit('Wait for the calibration queue to finish')
dry=pathlib.Path('/userdata/u1-addons/filament-ui-data/drying/state.json')
if dry.exists() and json.loads(dry.read_text()).get('state') in ('heating','running','paused','interrupted'): raise SystemExit('Cancel drying and remove spool before changing the installation')
night=pathlib.Path('/userdata/u1-addons/filament-ui-data/night-mode/state.json')
if night.exists() and (json.loads(night.read_text()).get('mode')!='off' or json.loads(night.read_text()).get('saved')): raise SystemExit('Turn off night mode and wait for stock control before changing the installation')
schedule=pathlib.Path('/userdata/u1-addons/filament-ui-data/schedule/state.json')
if schedule.exists() and json.loads(schedule.read_text()).get('state') in ('armed','starting'): raise SystemExit('Cancel the scheduled print before installing or rolling back')
state=json.load(urllib.request.urlopen('http://127.0.0.1:7125/printer/objects/query?print_stats&idle_timeout',timeout=10))['result']['status']
if state['idle_timeout']['state']!='Idle' or state['print_stats']['state'] not in ('standby','complete','cancelled'):raise SystemExit('Wait until the printer is idle')
root=pathlib.Path('/home/lava/fluidd');site=pathlib.Path('/etc/nginx/sites-available/u1-filament-https-addon');enabled=pathlib.Path('/etc/nginx/sites-enabled/u1-filament-https-addon')
init=pathlib.Path('/etc/init.d/S98u1-spool-accounting')
worker=home/'spool-accounting.py'
data_module=home/'u1_data_store.py'
feeder_module=home/'u1_feeder_settings.py'
calibration_module=home/'u1_calibration_jobs.py'
error_module=home/'u1_print_errors.py'
maintenance_module=home/'u1_maintenance.py'
scheduler_module=home/'u1_scheduler.py'
recovery_module=home/'u1_recovery.py'
night_module=home/'u1_night_mode.py'
dryer_service_module=home/'u1_dryer_service.py'
dryer_module=home/'u1_dryer.py'
alexa_module=home/'u1_alexa.py'
entry_install_module=home/'u1_entry_install.py'
dryer_install_module=home/'u1_dryer_install.py'
if init.exists() and '# U1 FILAMENT ADDON spool accounting' not in init.read_text():
    raise SystemExit('Foreign service at add-on path; stopped')
# Never downgrade the strict data validator while new profile fields exist.
with tarfile.open(backup/'before.tar.gz') as archive:
    old_name='accounting/data_module'
    if old_name in archive.getnames():
        old_source=archive.extractfile(old_name).read()
        def has_temperatures(records):
            return any('nozzleTemperature' in row or 'bedTemperature' in row for row in records)
        if b'nozzleTemperature' not in old_source:
            library=json.load(urllib.request.urlopen('http://127.0.0.1:7125/server/database/item?namespace=fluidd&key=u1_filament_library_v1',timeout=10))['result']['value']
            if has_temperatures(library.get('entries',[])+library.get('trash',[])):
                raise SystemExit('Temperature data exists. Use the print-profile-only rollback to keep the library compatible.')
        if b'MAINTENANCE_COUNTERS' not in old_source:
            namespace=json.load(urllib.request.urlopen('http://127.0.0.1:7125/server/database/item?namespace=fluidd',timeout=10))['result']['value']
            if 'u1_maintenance_v1' in namespace:
                raise SystemExit('Maintenance counters exist. Keep the current data validator and maintenance worker when rolling back.')
        if b'CUMULATIVE_FILAMENT_STATS' not in old_source:
            usage=json.load(urllib.request.urlopen('http://127.0.0.1:7125/server/database/item?namespace=fluidd&key=u1_spool_usage_v1',timeout=10))['result']['value']
            if any('colorId' in row or 'colorName' in row for record in usage.get('records',[]) for row in record.get('rows',[])):
                raise SystemExit('Color snapshots exist in usage history. Keep the current data validator when rolling back.')
        if b'PRINT_ERROR_LOG' not in old_source:
            usage=json.load(urllib.request.urlopen('http://127.0.0.1:7125/server/database/item?namespace=fluidd&key=u1_spool_usage_v1',timeout=10))['result']['value']
            if 'errors' in usage:
                raise SystemExit('Print-error history exists. Keep the current data validator when rolling back to preserve export/import compatibility.')
        if b'SPOOL_TEMPERATURE_OVERRIDES' not in old_source:
            inventory=json.load(urllib.request.urlopen('http://127.0.0.1:7125/server/database/item?namespace=fluidd&key=u1_spool_inventory_v1',timeout=10))['result']['value']
            if has_temperatures(inventory.get('spools',[])+inventory.get('trash',[])):
                raise SystemExit('Spool temperature overrides exist. Use the print-profile-only rollback to keep the inventory compatible.')
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');safety=pathlib.Path('/userdata/u1-addons-backups')/('before-rollback-'+stamp);safety.mkdir(mode=0o700,parents=True)
with tarfile.open(safety/'ui.tar.gz','w:gz') as t:
    t.add(root/'u1-filaments-ui',arcname='u1-filaments-ui')
    t.add('/etc/nginx',arcname='nginx')
    if init.exists():t.add(init,arcname='accounting/init')
    if worker.exists():t.add(worker,arcname='accounting/worker')
    if data_module.exists():t.add(data_module,arcname='accounting/data_module')
    if feeder_module.exists():t.add(feeder_module,arcname='accounting/feeder_module')
    if calibration_module.exists():t.add(calibration_module,arcname='accounting/calibration_module')
    if error_module.exists():t.add(error_module,arcname='accounting/error_module')
    if maintenance_module.exists():t.add(maintenance_module,arcname='accounting/maintenance_module')
    if scheduler_module.exists():t.add(scheduler_module,arcname='accounting/scheduler_module')
    for filename in ('u1_magnet_pause.py','u1_magnet_service.py','u1_magnet_install.py'):
        if (home/filename).exists():t.add(home/filename,arcname='accounting/magnets/'+filename)
    if recovery_module.exists():t.add(recovery_module,arcname='accounting/recovery_module')
    if night_module.exists():t.add(night_module,arcname='accounting/night_module')
    if dryer_service_module.exists():t.add(dryer_service_module,arcname='accounting/dryer_service_module')
    if dryer_module.exists():t.add(dryer_module,arcname='accounting/dryer_module')
    if alexa_module.exists():t.add(alexa_module,arcname='accounting/alexa_module')
    if entry_install_module.exists():t.add(entry_install_module,arcname='accounting/entry_install_module')
    if dryer_install_module.exists():t.add(dryer_install_module,arcname='accounting/dryer_install_module')
if (backup/'entry/manifest.json').exists():
    from u1_entry_install import rollback as rollback_entry
    rollback_entry(backup/'entry')
if (backup/'magnet-pauses/manifest.json').exists():
    from u1_magnet_install import rollback as rollback_magnets
    rollback_magnets(backup/'magnet-pauses')
if (backup/'dryer/manifest.json').exists():
    from u1_dryer_install import rollback as rollback_dryer
    rollback_dryer(backup/'dryer')
if (backup/'print-profiles/profiles-manifest.json').exists():
    from u1_profile_install import rollback as rollback_profiles, guard as profiles_guard
    profiles_guard()
    rollback_profiles(backup/'print-profiles')
if init.exists():subprocess.run([str(init),'stop'],check=True)
with tarfile.open(backup/'before.tar.gz') as t:
    for member in t.getmembers():
        prefix='fluidd/u1-filaments-ui/'
        if member.name.startswith(prefix) and member.isfile():
            rel=pathlib.PurePosixPath(member.name[len('fluidd/'):])
            if '..' in rel.parts:raise ValueError('Unsafe backup path')
            dest=root/str(rel);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(t.extractfile(member).read())
    old='nginx/sites-available/u1-filament-https-addon'
    if old in t.getnames():site.write_bytes(t.extractfile(old).read())
    elif site.exists() and '# U1 FILAMENT HTTPS ADDON' in site.read_text():site.unlink()
    old_enabled='nginx/sites-enabled/u1-filament-https-addon'
    if old_enabled not in t.getnames() and enabled.is_symlink():enabled.unlink()
    for filename in ('u1_magnet_pause.py','u1_magnet_service.py','u1_magnet_install.py'):
        entry='accounting/magnets/'+filename
        if entry in t.getnames(): (home/filename).write_bytes(t.extractfile(entry).read())
        else: (home/filename).unlink(missing_ok=True)
    for name,dest,mode in [('accounting/init',init,0o755),('accounting/worker',worker,0o644),('accounting/data_module',data_module,0o644),('accounting/feeder_module',feeder_module,0o644),('accounting/calibration_module',calibration_module,0o644),('accounting/error_module',error_module,0o644),('accounting/maintenance_module',maintenance_module,0o644),('accounting/scheduler_module',scheduler_module,0o644),('accounting/recovery_module',recovery_module,0o644),('accounting/dryer_module',dryer_module,0o644),('accounting/dryer_service_module',dryer_service_module,0o644),('accounting/dryer_install_module',dryer_install_module,0o644),('accounting/alexa_module',alexa_module,0o644),('accounting/entry_install_module',entry_install_module,0o644),('accounting/night_module',night_module,0o644)]:
        if name in t.getnames():
            dest.write_bytes(t.extractfile(name).read())
            dest.chmod(mode)
        else:dest.unlink(missing_ok=True)
subprocess.run(['nginx','-t'],check=True);subprocess.run(['nginx','-s','reload'],check=True)
if init.exists():subprocess.run([str(init),'start'],check=True)
print('Add-on restored. Firmware and filament library were not changed. Safety backup:',safety)
