from pathlib import Path
import os,pwd,resource
cg=Path('/sys/fs/cgroup/u1-companion-remote');cg.mkdir(exist_ok=True)
for name,value in {'memory.max':'100663296','memory.high':'83886080','memory.swap.max':'0','memory.oom.group':'1','cpu.max':'15000 100000'}.items():(cg/name).write_text(value)
(cg/'cgroup.procs').write_text(str(os.getpid()))
user=pwd.getpwnam('lava');os.setgroups([]);os.setgid(user.pw_gid);os.setuid(user.pw_uid);os.nice(10)
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_NPROC,(128,128))
os.execv('/usr/bin/python3',['/usr/bin/python3','/home/lava/u1-addons/filament-ui/u1-remote-manager.py'])
