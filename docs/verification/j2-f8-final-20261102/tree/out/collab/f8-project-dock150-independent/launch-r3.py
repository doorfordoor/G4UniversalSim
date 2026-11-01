from pathlib import Path
import os,sys,subprocess,json
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
rows=[]
for scale in ['1.25','1.5']:
    name='candidate'+scale+'-r3';log=OUT/(name+'.log')
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=str(ROOT/'gui')
    with log.open('wb') as f:
        p=subprocess.run(['D:/Geant4/G4UniversalSim/gui/.venv/Scripts/python.exe','-u','-B',str(OUT/'review.py'),name],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
    rows.append({'scale':scale,'exit_code':p.returncode,'log':str(log)})
    print(json.dumps(rows[-1]),flush=True)
(OUT/'processes-r3.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
assert all(r['exit_code']==0 for r in rows),rows


