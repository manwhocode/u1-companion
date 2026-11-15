"""Bounded optional Alexa bridge; no printer commands."""
from pathlib import Path
import os,pwd,resource
cg=Path('/sys/fs/cgroup/u1-companion-alexa');cg.mkdir(exist_ok=True)
for name,value in {'memory.max':'134217728','memory.high':'100663296','memory.swap.max':'0','memory.oom.group':'1','cpu.max':'10000 100000'}.items():(cg/name).write_text(value)
(cg/'cgroup.procs').write_text(str(os.getpid()))
user=pwd.getpwnam('lava');os.setgroups([]);os.setgid(user.pw_gid);os.setuid(user.pw_uid);os.nice(10)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
node='/userdata/u1-addons/alexa-bridge/runtime/node'
os.execv(node,[node,'--max-old-space-size=64','/userdata/u1-addons/alexa-bridge/bridge.cjs'])
