from pathlib import Path
import subprocess,json,os
root=Path.cwd();out=root/'out/collab/f8-layout-item-compat-independent';rows=[]
for mode in ['frozen-item','frozen-root','frozen-child','candidate']:
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
 with (out/(mode+'.log')).open('wb') as f:p=subprocess.run(['D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe','-u','-B',str(out/'review.py'),mode],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=90)
 text=(out/(mode+'.log')).read_text(encoding='utf-8',errors='replace')
 row={'mode':mode,'exit_code':p.returncode,'AttributeError_count':"QSpacerItem' object has no attribute 'count'" in text,'RuntimeWarning':'RuntimeWarning' in text};rows.append(row);print(row,flush=True)
 if mode=='candidate':assert p.returncode==0 and row['RuntimeWarning'],text[-2000:]
 else:assert p.returncode==1 and row['AttributeError_count'],text[-2000:]
(out/'processes.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
