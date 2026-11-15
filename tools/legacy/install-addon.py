#!/usr/bin/env python3
"""Offline Snapmaker U1 add-on installer. Run as root beside ui.tar.gz."""
import argparse, base64, datetime, hashlib, ipaddress, json, os, pathlib, plistlib, pwd, re, shutil, subprocess, tarfile, time, urllib.request, uuid

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ip', required=True)
    parser.add_argument('--https', action='store_true')
    args = parser.parse_args()
    ip = str(ipaddress.ip_address(args.ip))
    if os.geteuid() != 0: raise SystemExit('Run with sudo/root on the U1')
    if not pathlib.Path('/oem/.debug').is_file():
        raise SystemExit('System persistence is disabled: U1 erases installed modules on boot. Obtain owner consent and enable /oem/.debug before installation. No changes made.')
    root = pathlib.Path('/home/lava/fluidd')
    original = pathlib.Path('/etc/nginx/sites-available/fluidd')
    if not root.is_dir() or not original.is_file(): raise SystemExit('Snapmaker U1 web layout not found. No changes made.')
    job_file=pathlib.Path('/userdata/u1-addons/filament-ui-data/calibration-jobs/state.json')
    if job_file.exists() and json.loads(job_file.read_text()).get('state') in ('starting','loading','calibrating','saving','finishing'): raise SystemExit('Wait for the calibration queue to finish')
    dry=pathlib.Path('/userdata/u1-addons/filament-ui-data/drying/state.json')
    if dry.exists() and json.loads(dry.read_text()).get('state') in ('heating','running','paused','interrupted'): raise SystemExit('Cancel drying and remove spool before changing the installation')
    night=pathlib.Path('/userdata/u1-addons/filament-ui-data/night-mode/state.json')
    if night.exists() and (json.loads(night.read_text()).get('mode')!='off' or json.loads(night.read_text()).get('saved')): raise SystemExit('Turn off night mode and wait for stock control before changing the installation')
    schedule=pathlib.Path('/userdata/u1-addons/filament-ui-data/schedule/state.json')
    if schedule.exists() and json.loads(schedule.read_text()).get('state') in ('armed','starting'): raise SystemExit('Cancel the scheduled print before installing or rolling back')
    state = json.load(urllib.request.urlopen('http://127.0.0.1:7125/printer/objects/query?print_stats&idle_timeout', timeout=10))['result']['status']
    if state['idle_timeout']['state'] != 'Idle' or state['print_stats']['state'] not in ('standby', 'complete', 'cancelled'):
        raise SystemExit('Wait until the printer is idle. No changes made.')
    # U1 firmware omits some private commands from gcode/help. Check its actual
    # four-head status object instead of falsely rejecting stock firmware.
    live = json.load(urllib.request.urlopen('http://127.0.0.1:7125/printer/objects/query?print_task_config', timeout=10))
    task = live.get('result', {}).get('status', {}).get('print_task_config', {})
    if any(len(task.get(key, [])) != 4 for key in ['filament_type', 'filament_color_rgba', 'filament_exist', 'filament_edit']): raise SystemExit('U1 four-head API not found. No changes made.')
    source = pathlib.Path(__file__).resolve().parent / 'ui.tar.gz'
    expected = (source.parent / 'ui.sha256').read_text().split()[0]
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected: raise SystemExit('Build checksum mismatch')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    home = pathlib.Path('/home/lava/u1-addons/filament-ui')
    init = pathlib.Path('/etc/init.d/S98u1-spool-accounting')
    worker = home/'spool-accounting.py'
    data_module = home/'u1_data_store.py'
    feeder_module = home/'u1_feeder_settings.py'
    calibration_module = home/'u1_calibration_jobs.py'
    error_module = home/'u1_print_errors.py'
    maintenance_module = home/'u1_maintenance.py'
    scheduler_module = home/'u1_scheduler.py'
    recovery_module = home/'u1_recovery.py'
    night_module = home/'u1_night_mode.py'
    dryer_service_module = home/'u1_dryer_service.py'
    dryer_module = home/'u1_dryer.py'
    dryer_install_module = home/'u1_dryer_install.py'
    alexa_module = home/'u1_alexa.py'
    entry_install_module = home/'u1_entry_install.py'
    data_folder = pathlib.Path('/userdata/u1-addons/filament-ui-data')
    if data_folder.is_symlink() or data_folder.parent.is_symlink(): raise SystemExit('Unexpected data directory symlink')
    if init.exists() and '# U1 FILAMENT ADDON spool accounting' not in init.read_text():
        raise SystemExit('Foreign service at add-on path; stopped')
    backup = pathlib.Path('/userdata/u1-addons-backups') / ('install-' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    backup.chmod(0o700)
    with tarfile.open(backup/'before.tar.gz', 'w:gz') as tar:
        tar.add(root, arcname='fluidd')
        tar.add('/etc/nginx', arcname='nginx')
        if (home/'tls').exists(): tar.add(home/'tls', arcname='tls')
        if init.exists(): tar.add(init, arcname='accounting/init')
        if worker.exists(): tar.add(worker, arcname='accounting/worker')
        if data_module.exists(): tar.add(data_module, arcname='accounting/data_module')
        if feeder_module.exists(): tar.add(feeder_module, arcname='accounting/feeder_module')
        if calibration_module.exists(): tar.add(calibration_module, arcname='accounting/calibration_module')
        if error_module.exists(): tar.add(error_module, arcname='accounting/error_module')
        if maintenance_module.exists(): tar.add(maintenance_module, arcname='accounting/maintenance_module')
        if scheduler_module.exists(): tar.add(scheduler_module, arcname='accounting/scheduler_module')
        if recovery_module.exists(): tar.add(recovery_module, arcname='accounting/recovery_module')
        if night_module.exists(): tar.add(night_module, arcname='accounting/night_module')
        if dryer_service_module.exists(): tar.add(dryer_service_module, arcname='accounting/dryer_service_module')
        if dryer_module.exists(): tar.add(dryer_module, arcname='accounting/dryer_module')
        if alexa_module.exists(): tar.add(alexa_module, arcname='accounting/alexa_module')
        if entry_install_module.exists(): tar.add(entry_install_module, arcname='accounting/entry_install_module')
        if dryer_install_module.exists(): tar.add(dryer_install_module, arcname='accounting/dryer_install_module')
        for name in ('u1_magnet_pause.py','u1_magnet_service.py','u1_magnet_install.py'):
            if (home/name).exists(): tar.add(home/name,arcname='accounting/magnets/'+name)
    (backup/'before.tar.gz').chmod(0o600)
    for name, endpoint in [
        ('library.json', '/server/database/item?namespace=fluidd&key=u1_filament_library_v1'),
        ('spool-inventory.json', '/server/database/item?namespace=fluidd&key=u1_spool_inventory_v1'),
        ('spool-usage.json', '/server/database/item?namespace=fluidd&key=u1_spool_usage_v1'),
        ('printer-state.json', '/printer/objects/query?print_stats&print_task_config'),
    ]:
        try: (backup/name).write_bytes(urllib.request.urlopen('http://127.0.0.1:7125'+endpoint, timeout=10).read())
        except urllib.error.HTTPError as e:
            if e.code != 404: raise
            (backup/name).write_text('{"missing":true}')
    site = pathlib.Path('/etc/nginx/sites-available/u1-filament-https-addon')
    enabled = pathlib.Path('/etc/nginx/sites-enabled/u1-filament-https-addon')
    if site.exists() and '# U1 FILAMENT HTTPS ADDON' not in site.read_text(): raise SystemExit('Foreign config at add-on path; stopped')
    if site.exists(): shutil.copy2(site, backup/'previous-https-site')
    had_enabled = enabled.is_symlink()
    target = root/'u1-filaments-ui'
    if target.is_symlink(): raise SystemExit('Unexpected web directory symlink')
    target.mkdir(exist_ok=True)
    target.chmod(0o755)
    service_touched = False
    profiles_installed = False
    magnets_installed = False
    try:
        with tarfile.open(source) as tar:
            members = tar.getmembers()
            for member in members:
                path = pathlib.PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()): raise ValueError('Unsafe package path')
            # Publish entry point last. Old hashed assets remain valid for open clients.
            for member in members:
                if member.name.lstrip('./') != 'index.html':
                    tar.extract(member, target)
                    destination = target/member.name
                    if member.isfile(): destination.chmod(0o644)
                    parent = destination if member.isdir() else destination.parent
                    while parent != target.parent:
                        parent.chmod(0o755)
                        parent = parent.parent
            index = next(m for m in members if m.name.lstrip('./') == 'index.html')
            data = tar.extractfile(index).read()
            (target/'index.next.html').write_bytes(data)
            (target/'index.next.html').chmod(0o644)
            os.replace(target/'index.next.html', target/'index.html')
        status = {'installed': True, 'https': False, 'ip': ip, 'backup': str(backup)}
        if args.https:
            tls = home/'tls'; tls.mkdir(exist_ok=True); tls.chmod(0o700)
            ca_key, ca_cert = tls/'ca.key', tls/'ca.crt'
            if not ca_key.exists():
                run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '3650', '-subj', '/CN=U1 Local Camera CA ' + uuid.uuid4().hex[:12], '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0', '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', str(ca_key), '-out', str(ca_cert))
            ca_key.chmod(0o600)
            extensions = tls/'server.ext'
            extensions.write_text(f'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:{ip},DNS:u1.local\n')
            reuse = (tls/'server.key').exists() and (tls/'server.crt').exists()
            if reuse:
                try:
                    run('openssl', 'verify', '-CAfile', str(ca_cert), str(tls/'server.crt'))
                    run('openssl', 'x509', '-in', str(tls/'server.crt'), '-checkend', '2592000', '-noout')
                    run('openssl', 'x509', '-in', str(tls/'server.crt'), '-checkip', ip, '-noout')
                except subprocess.CalledProcessError: reuse = False
            if not reuse:
                run('openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', f'/CN={ip}', '-keyout', str(tls/'server.next.key'), '-out', str(tls/'server.csr'))
                run('openssl', 'x509', '-req', '-in', str(tls/'server.csr'), '-CA', str(ca_cert), '-CAkey', str(ca_key), '-CAcreateserial', '-days', '365', '-sha256', '-extfile', str(extensions), '-out', str(tls/'server.next.crt'))
                (tls/'server.next.key').chmod(0o600)
                os.replace(tls/'server.next.key', tls/'server.key'); os.replace(tls/'server.next.crt', tls/'server.crt')
            shutil.copy2(ca_cert, target/'u1-local-ca.crt')
            (target/'u1-local-ca.crt').chmod(0o644)
            der = subprocess.check_output(['openssl', 'x509', '-in', str(ca_cert), '-outform', 'DER'])
            profile = {'PayloadContent': [{'PayloadCertificateFileName': 'U1-Local-Camera-CA.crt', 'PayloadContent': der, 'PayloadDescription': 'Local HTTPS for your Snapmaker U1', 'PayloadDisplayName': 'U1 Local Camera CA', 'PayloadIdentifier': 'local.u1.camera.root', 'PayloadType': 'com.apple.security.root', 'PayloadUUID': str(uuid.uuid4()), 'PayloadVersion': 1}], 'PayloadDisplayName': 'U1 Camera HTTPS', 'PayloadIdentifier': 'local.u1.camera.profile', 'PayloadOrganization': 'Your local Snapmaker U1', 'PayloadType': 'Configuration', 'PayloadUUID': str(uuid.uuid4()), 'PayloadVersion': 1, 'PayloadRemovalDisallowed': False}
            (target/'U1-Camera.mobileconfig').write_bytes(plistlib.dumps(profile))
            (target/'U1-Camera.mobileconfig').chmod(0o644)
            conf = original.read_text()
            conf = re.sub(r'listen\s+80;', 'listen 443 ssl;', conf)
            conf = re.sub(r'listen\s+\[::\]:80;', 'listen [::]:443 ssl;', conf)
            additions = f'''server {{
    ssl_certificate {tls}/server.crt;
    ssl_certificate_key {tls}/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    location = /u1-filaments-ui/U1-Camera.mobileconfig {{ default_type application/x-apple-aspen-config; }}
    location = /u1-filaments-ui/u1-local-ca.crt {{ default_type application/x-x509-ca-cert; }}'''
            conf = conf.replace('server {', additions, 1)
            # An isolated HTTP provisioning port serves the iOS profile before
            # its CA is trusted. The original port-80 site is left byte-for-byte intact.
            provisioning = '''
server {
    listen 8081;
    listen [::]:8081;
    server_name _;
    root /home/lava/fluidd/u1-filaments-ui;
    location = /U1-Camera.mobileconfig { default_type application/x-apple-aspen-config; }
    location = /u1-local-ca.crt { default_type application/x-x509-ca-cert; }
    location / { return 404; }
}
'''
            site.write_text('# U1 FILAMENT HTTPS ADDON\n'+conf+provisioning)
            if not enabled.exists(): enabled.symlink_to(site)
            run('nginx', '-t'); run('nginx', '-s', 'reload')
            status.update(https=True, certificate_sha256=hashlib.sha256(der).hexdigest())
        state = json.load(urllib.request.urlopen('http://127.0.0.1:7125/printer/objects/query?print_stats&idle_timeout', timeout=10))['result']['status']
        if state['idle_timeout']['state'] != 'Idle' or state['print_stats']['state'] not in ('standby', 'complete', 'cancelled'):
            raise RuntimeError('Printer became busy. Service update deferred.')
        service_touched = True
        if init.exists(): run(str(init), 'stop')
        data_folder.mkdir(parents=True, exist_ok=True)
        data_folder.parent.chmod(0o711)
        data_folder.chmod(0o700)
        account = pwd.getpwnam('lava')
        os.chown(data_folder, account.pw_uid, account.pw_gid)
        shutil.copy2(source.parent/'spool-accounting.py', worker)
        shutil.copy2(source.parent/'u1_data_store.py', data_module)
        shutil.copy2(source.parent/'u1_feeder_settings.py', feeder_module)
        shutil.copy2(source.parent/'u1_calibration_jobs.py', calibration_module)
        shutil.copy2(source.parent/'u1_print_errors.py', error_module)
        shutil.copy2(source.parent/'u1_maintenance.py', maintenance_module)
        shutil.copy2(source.parent/'u1_scheduler.py', scheduler_module)
        shutil.copy2(source.parent/'u1_recovery.py', home/'u1_recovery.py')
        shutil.copy2(source.parent/'u1_night_mode.py', night_module)
        shutil.copy2(source.parent/'u1_dryer_service.py', dryer_service_module)
        shutil.copy2(source.parent/'u1_dryer.py', dryer_module)
        shutil.copy2(source.parent/'u1_dryer_install.py', dryer_install_module)
        shutil.copy2(source.parent/'u1_alexa.py', alexa_module)
        alexa_module.chmod(0o644)
        shutil.copy2(source.parent/'u1_entry_install.py', entry_install_module)
        entry_install_module.chmod(0o644)
        for name in ('u1_magnet_pause.py','u1_magnet_service.py','u1_magnet_install.py'):
            shutil.copy2(source.parent/name,home/name);(home/name).chmod(0o644)
        worker.chmod(0o644)
        data_module.chmod(0o644)
        feeder_module.chmod(0o644)
        calibration_module.chmod(0o644)
        error_module.chmod(0o644)
        maintenance_module.chmod(0o644)
        scheduler_module.chmod(0o644)
        night_module.chmod(0o644)
        dryer_service_module.chmod(0o644)
        dryer_module.chmod(0o644)
        dryer_install_module.chmod(0o644)
        subprocess.run(['python3', '-c', 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); t=p/".write-check"; t.write_text("ok"); t.unlink()', str(data_folder)], user=account.pw_uid, group=account.pw_gid, check=True)
        init.write_text((source.parent/'S98u1-spool-accounting').read_text(encoding='utf-8-sig').replace('\r\n', '\n'))
        init.chmod(0o755)
        started_at = time.time()
        run(str(init), 'start')
        for attempt in range(20):
            try:
                request_url = 'http://127.0.0.1:7125/server/database/item?namespace=fluidd&key=u1_data_storage_v1'
                storage = json.load(urllib.request.urlopen(request_url, timeout=3))['result']['value']
                if storage.get('version') == 1 and storage.get('state') == 'ready' and storage.get('updatedAt', 0) >= started_at:
                    break
            except (urllib.error.URLError, ValueError, KeyError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Data service did not become ready. See /tmp/u1-filament-data.log')
        from u1_profile_install import install as install_profiles
        install_profiles(source.parent, backup/'print-profiles')
        profiles_installed = True
        from u1_dryer_install import install as install_dryer
        install_dryer(source.parent, backup/'dryer')
        dryer_installed = True
        from u1_magnet_install import install as install_magnets
        install_magnets(source.parent, backup/'magnet-pauses')
        magnets_installed = True
        status['magnet_pauses_version'] = 1
        shutil.copy2(source.parent/'u1_profile_install.py', home/'u1_profile_install.py')
        status['print_profiles_version'] = 1
        status['spool_accounting'] = True
        status['data_storage_version'] = 1
        (target/'addon-status.json').write_text(json.dumps(status, indent=2))
        (target/'addon-status.json').chmod(0o644)
        from u1_entry_install import install as install_entry
        install_entry(backup/'entry')
        entry_installed = True
        shutil.copy2(pathlib.Path(__file__), home/'install-addon.py')
        (backup/'install.json').write_text(json.dumps(status, indent=2))
        print(json.dumps(status, indent=2))
    except Exception:
        if locals().get('entry_installed'):
            from u1_entry_install import rollback as rollback_entry
            rollback_entry(backup/'entry')
        if locals().get('magnets_installed'):
            from u1_magnet_install import rollback as rollback_magnets
            rollback_magnets(backup/'magnet-pauses')
        if locals().get('dryer_installed'):
            from u1_dryer_install import rollback as rollback_dryer
            rollback_dryer(backup/'dryer')
        if locals().get('profiles_installed'):
            from u1_profile_install import rollback as rollback_profiles
            rollback_profiles(backup/'print-profiles')
        if service_touched and init.exists():
            subprocess.run([str(init), 'stop'], check=False)
        # Restore only owned entry point and owned HTTPS config, never firmware.
        with tarfile.open(backup/'before.tar.gz') as tar:
            name = 'fluidd/u1-filaments-ui/index.html'
            if name in tar.getnames():
                (target/'index.html').write_bytes(tar.extractfile(name).read())
                (target/'index.html').chmod(0o644)
            for member in tar.getmembers():
                if member.name.startswith('tls/') and member.isfile():
                    dest = home/member.name
                    dest.parent.mkdir(exist_ok=True)
                    dest.write_bytes(tar.extractfile(member).read())
                    if dest.suffix == '.key': dest.chmod(0o600)
            if service_touched:
                for filename in ('u1_magnet_pause.py','u1_magnet_service.py','u1_magnet_install.py'):
                    entry='accounting/magnets/'+filename
                    if entry in tar.getnames(): (home/filename).write_bytes(tar.extractfile(entry).read())
                    else: (home/filename).unlink(missing_ok=True)
                for name, dest in [('accounting/init', init), ('accounting/worker', worker), ('accounting/data_module', data_module), ('accounting/feeder_module', feeder_module), ('accounting/calibration_module', calibration_module), ('accounting/error_module', error_module), ('accounting/maintenance_module', maintenance_module), ('accounting/scheduler_module', scheduler_module), ('accounting/recovery_module', recovery_module), ('accounting/dryer_module', dryer_module), ('accounting/dryer_service_module', dryer_service_module), ('accounting/dryer_install_module', dryer_install_module), ('accounting/alexa_module', alexa_module), ('accounting/entry_install_module', entry_install_module), ('accounting/night_module', night_module)]:
                    if name in tar.getnames():
                        dest.write_bytes(tar.extractfile(name).read())
                        dest.chmod(0o755 if dest == init else 0o644)
                    else:
                        dest.unlink(missing_ok=True)
                if init.exists(): subprocess.run([str(init), 'start'], check=False)
        if (backup/'previous-https-site').exists(): shutil.copy2(backup/'previous-https-site', site)
        elif site.exists(): site.unlink()
        if not had_enabled and enabled.is_symlink(): enabled.unlink()
        if subprocess.run(['nginx', '-t'], check=False).returncode == 0 and args.https:
            subprocess.run(['nginx', '-s', 'reload'], check=False)
        raise

if __name__ == '__main__': main()
