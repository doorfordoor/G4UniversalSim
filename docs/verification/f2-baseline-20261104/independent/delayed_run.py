import csv,hashlib,json,os,subprocess,time
from pathlib import Path
B=Path(__file__).resolve().parent
exe=Path('D:/Geant4/G4UniversalSim/build_vs2026/Release/G4UniversalSim.exe')
ini=(B/'config/main.ini').read_text(encoding='utf-8').replace('particle = proton','particle = ion\nion = 6 12 2')
(B/'config/main_pending_ion.ini').write_text(ini,encoding='utf-8')
result=[]
for name,commands,ok in [('pending-ion-direct',['/gps/particle proton','/run/initialize','/run/beamOn 5','exit'],True),('pending-ion-nested',['/control/execute missing.mac','/control/echo F2_DELAYED_MUST_NOT_RUN','/run/initialize','/run/beamOn 5','exit'],False)]:
 d=B/name;out=d/'output';out.mkdir(parents=True);data=('\n'.join(commands)+'\n').encode();(d/'stdin.txt').write_bytes(data)
 env=os.environ.copy();env['G4USIM_GEANT4_DATA']='D:/ProgramFiles/Geant4/share/Geant4/data'
 args=[str(exe),'--config','main_pending_ion.ini','--ui','--ui-session','csh','--output',str(out)]
 p=subprocess.Popen(args,cwd=B/'config',env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try: stdout,stderr=p.communicate(data,timeout=120)
 except subprocess.TimeoutExpired: p.kill();stdout,stderr=p.communicate();raise
 (d/'stdout.log').write_bytes(stdout);(d/'stderr.log').write_bytes(stderr)
 s={}
 if (out/'run_summary.txt').exists():
  for line in (out/'run_summary.txt').read_text(encoding='utf-8').splitlines():
   if '=' in line and not line.startswith('#'):
    k,v=line.split('=',1);s[k.strip()]=v.strip()
 rows=[]
 for f in out.glob('phase_space_t*.csv'):
  with f.open(encoding='utf-8',newline='') as x: rows.extend(csv.DictReader(x))
 r={'case':name,'pid':p.pid,'argv':args,'exit_code':p.returncode,'summary':s,'phase_rows':len(rows),'status':'checking'}
 try:
  if ok:
   assert p.returncode==0 and s['status']=='completed' and s['actual_completed_event_count']=='5'
   assert len(rows)==5 and all(x['particle']=='proton' and x['trackID']=='1' and x['parentID']=='0' and float(x['kineticEnergy_MeV'])==100 for x in rows)
  else:
   assert p.returncode!=0 and b'pending ion/confinement' in stdout+stderr
   assert b'F2_DELAYED_MUST_NOT_RUN' not in stdout
   assert not rows and s['run_count']=='0' and s['status']=='failed'
  r['status']='pass'
 except Exception as e: r['status']='fail';r['error']=str(e) or type(e).__name__
 r['files']={str(x.relative_to(d)):hashlib.sha256(x.read_bytes()).hexdigest() for x in d.rglob('*') if x.is_file()}
 (d/'receipt.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');result.append(r);print(name,r['status'],p.returncode,flush=True)
(B/'delayed-report.json').write_text(json.dumps({'cases':result,'passed':sum(x['status']=='pass' for x in result),'failed':sum(x['status']!='pass' for x in result)},indent=2)+'\n',encoding='utf-8')
assert all(x['status']=='pass' for x in result)