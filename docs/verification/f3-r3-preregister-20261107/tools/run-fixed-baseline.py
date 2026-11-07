from pathlib import Path
import json,subprocess,os,sys,hashlib,time,traceback
from datetime import datetime,timezone
sys.stdout.reconfigure(encoding='utf-8')
r=Path('D:/Geant4/G4UniversalSim');active=r/'out/collab/f3-preflight-independent/r2/active-baseline.json';info=json.loads(active.read_text(encoding='utf-8'));base=Path(info['root']);plan=json.loads((base/'run-plan.json').read_text(encoding='utf-8'));env=os.environ.copy();env.update(TEMP=str(base/'tmp'),TMP=str(base/'tmp'),PYTHONIOENCODING='utf-8');state={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),'phases':[],'simulation_invocations_completed':0,'plan':str(base/'run-plan.json')}
def save(): (base/'execution.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
def verify():
 for item in plan['identity'].values():
  assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256'],item['path']
try:
 save();print('BASELINE_STARTED '+str(base),flush=True)
 for command in plan['commands']:
  verify();phase=command['phase'];state['current_phase']=phase;save();began=time.perf_counter();log=base/(phase+'.driver.log');print('PHASE_STARTED '+phase,flush=True)
  with log.open('wb') as handle:result=subprocess.run(command['argv'],cwd=r,env=env,stdout=handle,stderr=subprocess.STDOUT)
  row={'phase':phase,'exit_code':result.returncode,'duration_s':time.perf_counter()-began,'log':str(log)};state['phases'].append(row);save();assert result.returncode==0,phase+' failed; see '+str(log)
  report=Path(command['output'])/'report.json';data=json.loads(report.read_bytes());count=len(data.get('memory_samples',[])) if phase=='memory' else len(data['samples']);assert count==command['expected_simulation_invocations'],(phase,count);row.update(simulation_invocations=count,report=str(report),report_sha256=hashlib.sha256(report.read_bytes()).hexdigest());state['simulation_invocations_completed']+=count;save();verify();print('PHASE_COMPLETED '+phase+' '+str(count),flush=True)
 state['status']='completed_pending_independent_analysis';state['finished_utc']=datetime.now(timezone.utc).isoformat();save();print('BASELINE_EXECUTION_COMPLETED36',flush=True)
except BaseException as error:
 state.update(status='failed',error=str(error),traceback=traceback.format_exc(),finished_utc=datetime.now(timezone.utc).isoformat());save();print('BASELINE_FAILED '+str(error),flush=True);raise
