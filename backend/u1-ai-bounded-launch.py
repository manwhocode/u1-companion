"""Root entry point drops privileges before serving or launching any AI runtime."""
from pathlib import Path
import os,pwd,resource
CG=Path('/sys/fs/cgroup/u1-companion-ai')
def main():
 if os.geteuid()!=0:raise RuntimeError('Service launcher must configure limits before dropping privileges')
 CG.mkdir(exist_ok=True)
 limits={'memory.max':'134217728','memory.high':'100663296','memory.swap.max':'0','memory.oom.group':'1','cpu.max':'20000 100000'}
 for name,value in limits.items():
  p=CG/name
  if not p.exists():raise RuntimeError('Required resource isolation unavailable')
  p.write_text(value)
 for name,value in limits.items():
  if (CG/name).read_text().strip()!=value:raise RuntimeError('Resource limit not applied')
 (CG/'cgroup.procs').write_text(str(os.getpid()))
 user=pwd.getpwnam('lava');os.setgroups([]);os.setgid(user.pw_gid);os.setuid(user.pw_uid)
 os.nice(10);resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_NPROC,(256,256))
 os.execv('/usr/bin/python3',['/usr/bin/python3','/home/lava/u1-addons/filament-ui/u1-ai-server.py'])
if __name__=='__main__':main()
