"""Start missing Companion services after U1 has restored its root overlay.

rcS expands S??* before S01aoverlayfs pivots the root. New init filenames in
the persistent overlay are therefore absent from that boot's original list.
An owned block in an existing late native script invokes this helper instead.
No printer API or native service is called here.
"""
from pathlib import Path
import json
import subprocess

CORE = '/home/lava/u1-addons/filament-ui/'
SERVICES = {
    'S98u1-spool-accounting': ('u1-spool-accounting', (CORE+'spool-accounting.py',), None),
    'S97u1-ai': ('u1-ai', (CORE+'u1-ai-bounded-launch.py', CORE+'u1-ai-server.py'), 'ai'),
    'S96u1-remote': ('u1-remote', (CORE+'u1-remote-launch.py', CORE+'u1-remote-manager.py'), 'remote'),
    'S99u1-alexa-bridge': ('u1-alexa-bridge', (CORE+'u1-alexa-bounded-launch.py', '/userdata/u1-addons/alexa-bridge/bridge.cjs'), 'alexa'),
}


def start_missing(root=Path('/'), run=subprocess.run):
    results = []
    for name, (pidname, programs, group) in SERVICES.items():
        try:
            service = root / ('etc/init.d/'+name)
            if service.is_symlink() or not service.is_file():
                raise ValueError('Missing or linked service script')
            pidfile = root / ('run/'+pidname+'.pid')
            if pidfile.is_symlink():
                raise ValueError('Linked PID file')
            if pidfile.exists():
                pid = int(pidfile.read_text().strip())
                if pid < 2:
                    raise ValueError('Invalid PID')
                proc = root / ('proc/'+str(pid))
                if proc.exists():
                    args = (proc/'cmdline').read_bytes().split(b'\0')
                    if not any(p.encode() in args for p in programs):
                        raise ValueError('Foreign PID; left unchanged')
                    results.append({'service':name, 'state':'already_running'})
                    continue
            if group:
                procs = root / ('sys/fs/cgroup/u1-companion-'+group+'/cgroup.procs')
                if procs.exists() and procs.read_text().strip():
                    raise ValueError('Untracked service group; left unchanged')
            for proc in (root/'proc').glob('[0-9]*'):
                try:
                    args = (proc/'cmdline').read_bytes().split(b'\0')
                    if any(p.encode() in args for p in programs):
                        raise ValueError('Untracked process; left unchanged')
                except FileNotFoundError:
                    continue
            result = run([str(service),'start'], check=False, timeout=20,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode:
                raise ValueError('Service start failed')
            results.append({'service':name, 'state':'start_requested'})
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            results.append({'service':name, 'state':'error', 'error':str(error)})
    return results


def main():
    import fcntl
    with open('/run/u1-companion-boot.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        results = start_missing()
        for result in results:
            print(json.dumps(result), flush=True)
        return int(any(r['state']=='error' for r in results))


if __name__ == '__main__':
    raise SystemExit(main())
