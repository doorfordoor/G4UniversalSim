from pathlib import Path
import subprocess,os,json
root=Path.cwd();out=root/'out/collab/f8-linux-name-independent';script=out/'review.py'
path='/mnt/c/'+script.as_posix().split(':',1)[1].lstrip('/')
commands=[('windows',['D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe','-u','-B',str(script)]),('linux',['wsl.exe','-d','Ubuntu','--','/home/u123/venvs/g4-f4-qt-6.11.3-20261030/bin/python','-u','-B',path])]
rows=[]
for name,cmd in commands:
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
 with (out/(name+'.log')).open('wb') as stream:p=subprocess.run(cmd,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=90)
 rows.append({'platform':name,'command':cmd,'exit_code':p.returncode});print(name,p.returncode,flush=True)
 assert p.returncode==0,(out/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-2000:]
(out/'processes.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
