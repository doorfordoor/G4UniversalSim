from pathlib import Path
import os,subprocess,json
root=Path.cwd();out=root/'out/collab/f8-history-label-independent';rows=[]
for scale in ['1.25','1.5']:
 env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
 with (out/('scale'+scale+'.log')).open('wb') as f:p=subprocess.run(['D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe','-u','-B',str(out/'review.py'),scale],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 rows.append({'scale':scale,'exit_code':p.returncode});print(rows[-1],flush=True)
(out/'processes.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');assert all(r['exit_code']==0 for r in rows)
