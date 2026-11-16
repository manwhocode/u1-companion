"""Build the portable EXE from an isolated environment on Windows."""
from pathlib import Path
import argparse,hashlib,importlib.metadata,json,subprocess,sys

repo=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
work=a.output/'work';work.mkdir(exist_ok=True)
notices=work/'THIRD-PARTY-NOTICES.txt'
parts=['U1 Companion Windows launcher: GPL-3.0. Source: https://github.com/manwhocode/u1-companion\n']
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.is_file():parts.append('\n=== Python runtime license ===\n'+python_license.read_text(encoding='utf-8'))
for package in ['paramiko','cryptography','bcrypt','PyNaCl','cffi','pycparser','packaging','pyinstaller']:
    try:dist=importlib.metadata.distribution(package)
    except importlib.metadata.PackageNotFoundError:continue
    parts.append('\n\n=== '+package+' '+dist.version+' ===\n')
    for file in dist.files or []:
        if any(word in str(file).upper() for word in ['LICENSE','COPYING','NOTICE']):
            path=dist.locate_file(file)
            if path.is_file():parts.append(path.read_text(encoding='utf-8',errors='replace'))
notices.write_text('\n'.join(parts),encoding='utf-8')
command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--console','--noupx','--name','U1-Companion-Setup',
         '--distpath',str(a.output),'--workpath',str(work/'pyinstaller'),'--specpath',str(work),
         '--add-data',str(repo/'LICENSE')+':.','--add-data',str(repo/'desktop/AGREEMENT.ru.txt')+':desktop',
         '--add-data',str(repo/'desktop/AGREEMENT.en.txt')+':desktop','--add-data',str(notices)+':.',str(repo/'desktop/launcher.py')]
compat=Path(sys.base_prefix)/'abi3t-compat/python3t.dll'
if compat.is_file():command[-1:-1]=['--add-binary',str(compat)+':.']
subprocess.run(command,check=True,cwd=repo)
exe=a.output/'U1-Companion-Setup.exe';subprocess.run([str(exe),'--self-test'],check=True)
digest=hashlib.sha256(exe.read_bytes()).hexdigest();(a.output/'SHA256SUMS').write_text(digest+'  '+exe.name+'\n',encoding='ascii')
(a.output/'BUILD.json').write_text(json.dumps({'sha256':digest,'bytes':exe.stat().st_size,'moduleVersion':'not embedded','bootstrap':'official repository main/install.sh','selfTest':'passed','codeSigned':False},indent=2)+'\n')
print('EXE built:',exe,exe.stat().st_size,'bytes')
