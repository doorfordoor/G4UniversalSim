import csv, hashlib, json, math, os, re, subprocess, time
from pathlib import Path
BASE=Path(__file__).resolve().parent
EXE=Path('D:/Geant4/G4UniversalSim/build_vs2026/Release/G4UniversalSim.exe')
assert hashlib.sha256(EXE.read_bytes()).hexdigest()=='18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837'
SENTINEL='F2_INDEPENDENT_MUST_NOT_EXECUTE'
CASES={
 'three-round':('main.ini',['/run/initialize','/AIHL/source/print','/run/beamOn 10','/AIHL/source/energy 200 MeV','/AIHL/source/print','/run/beamOn 10','/AIHL/source/energy 100 MeV','/AIHL/source/print','/run/beamOn 10','exit']),
 'fields':('main.ini',['/run/initialize','/AIHL/source/particle e-','/run/beamOn 10','/AIHL/source/energy 50 MeV','/run/beamOn 10','/AIHL/source/point 5 0 -50 mm','/run/beamOn 10','/AIHL/source/direction 0.1 0 0.995','/run/beamOn 10','/AIHL/source/planeBeam radius=5 mm z=-50 mm direction=+z','/run/beamOn 10','exit']),
 'native-gps':('main.ini',['/run/initialize','/AIHL/source/print','/run/beamOn 5','/gps/ene/mono 2 MeV','/AIHL/source/print','/run/beamOn 5','exit']),
 'preinit-cache':('main.ini',['/AIHL/source/energy 300 MeV','/AIHL/source/particle e-','/run/initialize','/run/beamOn 5','exit']),
 'refusal-multisource':('main_multisource.ini',['/run/initialize','/AIHL/source/energy 200 MeV','/control/echo '+SENTINEL,'/run/beamOn 4','exit']),
 'refusal-output-state':('main.ini',['/run/initialize','/AIHL/output/setDir '+str(BASE/'must-not-be-created'),'/control/echo '+SENTINEL,'/run/beamOn 4','exit']),
}
def summary(p):
 d={}
 if p.exists():
  for line in p.read_text(encoding='utf-8').splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,v=line.split('=',1);d[k.strip()]=v.strip()
 return d
results=[]
for name,(config,commands) in CASES.items():
 case=BASE/name;out=case/'output';out.mkdir(parents=True)
 data=('\n'.join(commands)+'\n').encode();(case/'stdin.txt').write_bytes(data)
 env=os.environ.copy();env['G4USIM_GEANT4_DATA']='D:/ProgramFiles/Geant4/share/Geant4/data'
 argv=[str(EXE),'--ui','--ui-session','csh','--config',config,'--output',str(out)]
 started=time.monotonic();proc=subprocess.Popen(argv,cwd=BASE/'config',env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 timeout=False
 try: stdout,stderr=proc.communicate(data,timeout=120)
 except subprocess.TimeoutExpired:
  timeout=True;proc.kill();stdout,stderr=proc.communicate()
 (case/'stdout.log').write_bytes(stdout);(case/'stderr.log').write_bytes(stderr)
 s=summary(out/'run_summary.txt');runs={}
 for p in sorted(out.glob('phase_space_t*.csv')):
  with p.open(encoding='utf-8',newline='') as f: rows=list(csv.DictReader(f))
  for row in rows: runs.setdefault(int(row['runID']),[]).append(row)
 record={'case':name,'pid':proc.pid,'argv':argv,'exit_code':proc.returncode,'timed_out':timeout,'duration_s':round(time.monotonic()-started,3),'summary':s,'phase_rows':{str(k):len(v) for k,v in runs.items()},'status':'checking'}
 try:
  assert not timeout
  if name.startswith('refusal-'):
   assert proc.returncode!=0
   assert SENTINEL.encode() not in stdout
   assert not runs and not list(out.glob('hits_t*.csv'))
   if name=='refusal-output-state':
    assert proc.returncode==1 and s['status']=='failed' and s['run_count']=='0'
    assert s['interactive_command_failure_kind']=='geant4_illegal_application_state'
    assert not (BASE/'must-not-be-created').exists()
   else:
    assert b'AIHL_SOURCE_001' in stdout+stderr
    assert not (out/'run_summary.txt').exists()
  else:
   assert proc.returncode==0 and s['status']=='completed'
   expected={'three-round':[(10,'proton',100),(10,'proton',200),(10,'proton',100)],'fields':[(10,'e-',100),(10,'e-',50),(10,'e-',50),(10,'e-',50),(10,'e-',50)],'native-gps':[(5,'proton',100),(5,'proton',2)],'preinit-cache':[(5,'e-',300)]}[name]
   assert int(s['run_count'])==len(expected)
   assert int(s['actual_completed_event_count'])==sum(x[0] for x in expected)
   assert set(runs)==set(range(len(expected)))
   for run,(n,particle,energy) in enumerate(expected):
    assert int(s[f'run_{run}_planned_events'])==n and int(s[f'run_{run}_completed_events'])==n
    rows=runs[run];primary=[r for r in rows if r['trackID']=='1' and r['parentID']=='0']
    assert len(primary)==n and {int(r['eventID']) for r in primary}==set(range(n))
    assert all(r['particle']==particle and math.isclose(float(r['kineticEnergy_MeV']),energy,abs_tol=1e-5) for r in primary)
    assert all(math.isclose(float(r['z_mm']),-10,abs_tol=1e-6) for r in primary)
    if name=='fields' and run==2: assert all(math.isclose(float(r['x_mm']),5,abs_tol=1e-6) for r in primary)
    if name=='fields' and run==3:
     assert all(math.isclose(float(r['x_mm']),5+40*0.1/0.995,abs_tol=1e-6) for r in primary)
     assert all(math.isclose(float(r['u']),0.1/math.sqrt(0.1**2+0.995**2),abs_tol=1e-6) for r in primary)
    if name=='fields' and run==4: assert all(float(r['x_mm'])**2+float(r['y_mm'])**2<=25.000001 for r in primary)
   if name=='native-gps':
    prints=[x for x in stdout.decode(errors='replace').splitlines() if '[SourceManager]' in x and 'monoEnergy' in x]
    assert len(prints)==2 and all('monoEnergy=100' in x for x in prints)
    assert float(s['effective_source_energy_MeV'])==100
    record['manager_prints']=prints
  record['status']='pass'
 except Exception as e:
  record['status']='fail';record['error']=str(e) or type(e).__name__
 record['files']={str(p.relative_to(case)):hashlib.sha256(p.read_bytes()).hexdigest() for p in case.rglob('*') if p.is_file()}
 (case/'receipt.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 results.append(record);print(name,record['status'],proc.returncode,'pid',proc.pid,flush=True)
report={'schema':'g4usim_f2_independent_baseline_v1','exe_sha256':hashlib.sha256(EXE.read_bytes()).hexdigest(),'cases':results,'passed':sum(x['status']=='pass' for x in results),'failed':sum(x['status']!='pass' for x in results),'scope':'Windows single-thread primary entry-boundary observations; not original generator vertices or RNG replay'}
(BASE/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert report['failed']==0, str([(x['case'],x.get('error')) for x in results if x['status']!='pass'])