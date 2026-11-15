from pathlib import Path
import os,signal,time
pidfile=Path('/run/u1-remote.pid')
try:pid=int(pidfile.read_text().strip())
except (OSError,ValueError):raise SystemExit(0)
proc=Path('/proc')/str(pid)
def identity():
 try:
  cmd=(proc/'cmdline').read_bytes()
  group=(proc/'cgroup').read_text()
  if b'/home/lava/u1-addons/filament-ui/u1-remote-' not in cmd or '/u1-companion-remote' not in group:return None
  return (proc/'stat').read_text().rsplit(')',1)[1].split()[19]
 except OSError:return None
original=identity()
if original:
 os.kill(pid,signal.SIGTERM)
 for _ in range(80):
  if identity()!=original:break
  time.sleep(.1)
 if identity()==original:os.kill(pid,signal.SIGKILL)
try:pidfile.unlink()
except FileNotFoundError:pass
