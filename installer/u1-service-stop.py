"""Stop only an identified Companion process and its dedicated bounded group."""
from pathlib import Path
import os
import signal
import sys
import time

CORE = '/home/lava/u1-addons/filament-ui/'
SERVICES = {
    'S98u1-spool-accounting': ('u1-spool-accounting', [CORE+'spool-accounting.py'], None),
    'S97u1-ai': ('u1-ai', [CORE+'u1-ai-bounded-launch.py', CORE+'u1-ai-server.py'], 'ai'),
    'S96u1-remote': ('u1-remote', [CORE+'u1-remote-launch.py', CORE+'u1-remote-manager.py'], 'remote'),
    'S99u1-alexa-bridge': ('u1-alexa-bridge', [CORE+'u1-alexa-bounded-launch.py', '/userdata/u1-addons/alexa-bridge/bridge.cjs'], 'alexa'),
}


def identity(proc):
    try:
        return ((proc/'stat').read_text().rsplit(')',1)[1].split()[19],
                (proc/'cmdline').read_bytes().split(b'\0'))
    except FileNotFoundError:
        return None


def stop(name, root=Path('/'), sleep=time.sleep, kill=os.kill):
    pidname, programs, group = SERVICES[name]
    pidfile = root / ('run/'+pidname+'.pid')
    if pidfile.is_symlink(): raise ValueError('Unexpected service PID symlink')
    if not pidfile.exists():
        # Refuse orphaned bounded work; never install over a live untracked service.
        if group:
            procs=root/('sys/fs/cgroup/u1-companion-'+group+'/cgroup.procs')
            if procs.exists() and procs.read_text().strip(): raise ValueError('Live service without PID file: '+name)
        return False
    raw=pidfile.read_text(); pid=int(raw.strip())
    if pid < 2: raise ValueError('Invalid service PID')
    proc=root/('proc/'+str(pid)); original=identity(proc)
    if not original and group:
        procs=root/('sys/fs/cgroup/u1-companion-'+group+'/cgroup.procs')
        if procs.exists() and procs.read_text().strip(): raise ValueError('Service children remain without their parent: '+name)
    if original and not any(p.encode() in original[1] for p in programs):
        raise ValueError('Foreign PID; service was not stopped: '+name)
    if original:
        # A pidfd prevents signalling a reused Linux PID.
        fd=None
        try:
            if root == Path('/') and hasattr(os,'pidfd_open'):
                fd=os.pidfd_open(pid)
            if identity(proc) == original:
                if fd is not None: signal.pidfd_send_signal(fd,signal.SIGTERM)
                else: kill(pid,signal.SIGTERM)
            for _ in range(100):
                if identity(proc) != original: break
                sleep(.1)
            else: raise ValueError('Service did not stop; installation stopped: '+name)
        except ProcessLookupError: pass
        finally:
            if fd is not None: os.close(fd)
        # A terminating AI server may have left a Codex child. Its dedicated
        # cgroup contains no native printer processes; terminate only that group.
        if group:
            cg=root/('sys/fs/cgroup/u1-companion-'+group)
            procs=cg/'cgroup.procs'
            if procs.exists() and procs.read_text().strip():
                if not (cg/'cgroup.kill').exists(): raise ValueError('Service children remain: '+name)
                (cg/'cgroup.kill').write_text('1')
                for _ in range(50):
                    if not procs.read_text().strip(): break
                    sleep(.1)
                else: raise ValueError('Service group did not stop: '+name)
    if pidfile.read_text() != raw: raise ValueError('PID file changed while stopping service')
    pidfile.unlink()
    return original is not None


if __name__ == '__main__':
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in SERVICES: raise ValueError('Specify a Companion service')
        stop(sys.argv[1])
    except Exception as error:
        print(str(error),file=sys.stderr);sys.exit(1)
