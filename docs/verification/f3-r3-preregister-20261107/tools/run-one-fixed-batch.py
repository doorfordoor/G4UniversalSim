from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,hashlib,subprocess,time,importlib.util,traceback
sys.stdout.reconfigure(encoding='utf-8')
r=Path('D:/Geant4/G4UniversalSim');base=Path(sys.argv[1]).resolve();plan_bytes=(base/'run-plan.json').read_bytes();plan=json.loads(plan_bytes)
assert plan['authorized'] and plan['events']==2000 and plan['simulation_invocations']==36
assert plan['state']=='frozen_r3_after_independent_review'
plan_sha256=hashlib.sha256(plan_bytes).hexdigest()
assert plan_sha256==json.loads((base/'approval.json').read_bytes())['plan_sha256']
assert base==Path(plan['root']).resolve()
with (base/'job-started.json').open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'started_utc':datetime.now(timezone.utc).isoformat()},f)
state={'status':'running','phase':'preflight','pid':os.getpid(),'root':str(base),'started_utc':datetime.now(timezone.utc).isoformat(),'simulations_completed':0,'science_completed':0}
def save():
 p=base/'job-state.json';q=p.with_suffix('.tmp');q.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8',newline=chr(10));os.replace(q,p)
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def verify():
 assert digest(base/'run-plan.json')==plan_sha256,'frozen plan changed'
 for item in plan['identity'].values():assert digest(item['path'])==item['sha256'],item['path']
 a=json.loads((r/'out/collab/f3-preflight-independent/r2/active-baseline.json').read_bytes());assert Path(a['root']).resolve()==base,'active-baseline changed; do not run another batch'
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
cn=module('r3_compare',r/'out/collab/f3-noise-r3/author/compare_n.py')
wait_deadline=time.monotonic()+12*3600
wait_logged=False
def ready(phase):
 global wait_logged
 while True:
  verify();x=cn.readiness();state.update(phase=phase,resource_readiness=x);save()
  if x['ready']:
   if not wait_logged:return
   print('RESOURCES_READY',x['available_bytes'],flush=True);wait_logged=False;return
  if not wait_logged:print('WAITING_FOR_RESOURCES',x['available_bytes'],'minimum',x['min_bytes'],flush=True);wait_logged=True
  if time.monotonic()>=wait_deadline:raise RuntimeError('resource_wait_expired_without_loosening_boundary')
  time.sleep(30)
def command(argv,name,timeout=None):
 verify();state.update(phase=name,child_pid=None);save()
 with (base/(name+'.driver.log')).open('wb') as out:
  p=subprocess.Popen(argv,cwd=r,env=env,stdout=out,stderr=subprocess.STDOUT);state['child_pid']=p.pid;save()
  try:rc=p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   p.kill();p.wait();raise
 state['child_pid']=None;state[name+'_exit_code']=rc;save();assert rc==0,(name,rc)
 print('COMPLETED',name,flush=True)
env=os.environ.copy();env.update(TEMP=str(base/'tmp'),TMP=str(base/'tmp'),PYTHONIOENCODING='utf-8')
try:
 save();verify();ready('waiting_resources_before_measurement')
 state['phase']='fixed_30s_settle';save();time.sleep(30);ready('readiness_after_settle')
 # Let the reviewed inner runner own each backend/observer timeout and cleanup.
 # Never kill only its orchestration parent while its owned descendants may run.
 command([sys.executable,'-B',str(r/'out/collab/f3-preflight-independent/r2/run-fixed-baseline.py')],'measurement')
 execution=json.loads((base/'execution.json').read_bytes());assert execution['simulation_invocations_completed']==36
 state['simulations_completed']=36;save()
 command([sys.executable,'-B',str(r/'out/collab/f3-preflight-independent/r2/resource-independent.py')],'resource-independent',60)
 command([sys.executable,'-B',str(r/'out/collab/f3-preflight-independent/r2/memory-independent.py')],'memory-independent',60)
 timing=json.loads((base/'timing/report.json').read_bytes());memory=json.loads((base/'memory/report.json').read_bytes())
 assert len(timing['samples'])==20 and len(memory['memory_samples'])==12
 m=module('r3_measure',r/'scripts/measure_output_performance.py');hash_count=0
 state['phase']='independent_artifact_audit';save()
 for phase,samples in [('timing',timing['samples']),('memory',memory['memory_samples'])]:
  for s in samples:
   assert s['events']==2000 and s['exit_code']==0
   n=f"{s['label']}-{s['workload']}-{s['format']}-{s['repeat']}"
   folder=base/'timing'/n if phase=='timing' else base/'memory/memory'/('memory-'+n)
   assert digest(folder/'main.ini')==s['config_sha256'];assert digest(folder/'run.mac')==s['macro_sha256'];assert digest(folder/'backend.log')==s['log_sha256']
   assert (folder/'main.ini').read_bytes()==m.render_config(s['workload'],s['format'],2000)
   assert (folder/'run.mac').read_bytes()==m.render_macro(s['workload'],2000)
   for filename,h in s['artifact_sha256'].items():assert digest(folder/'output'/filename)==h;hash_count+=1
   if phase=='memory':
    raw=json.loads((folder/'memory.json').read_bytes());assert raw==s['memory'];m.validate_memory(n,raw,s['launch'],raw['pid'])
 (base/'artifact-independent.json').write_text(json.dumps({'status':'pass','samples':32,'artifact_hashes_verified':hash_count,'events':2000},indent=2),encoding='utf-8',newline=chr(10))
 batch=module('r3_science_batch',r/'out/collab/f3-noise-r3/author/science_batch.py')
 comparisons=batch.comparison_plan(base/'timing',base/'memory/memory','baseline');assert len(comparisons)==32 and not batch.discover(comparisons)
 out=base/'independent-analysis';out.mkdir();rows=[]
 for entry in comparisons:
  ready('waiting_resources_before_science_'+entry['name'])
  verify();target=out/(entry['name']+'.json');log=out/(entry['name']+'.log')
  argv=[sys.executable,'-B',str(r/'out/collab/f3-noise-r3/author/compare_n.py'),'compare','--baseline',entry['baseline'],'--candidate',entry['candidate'],'--workload',entry['workload'],'--format',entry['format'],'--events','2000','--out',str(target)]
  state.update(phase='science_'+entry['name']);save()
  with log.open('wb') as h:
   p=subprocess.Popen(argv,cwd=r,env=env,stdout=h,stderr=subprocess.STDOUT);state['child_pid']=p.pid;save()
   try:rc=p.wait(timeout=600)
   except subprocess.TimeoutExpired:p.kill();p.wait();raise
  state['child_pid']=None;save();assert rc==0,(entry['name'],rc)
  report=json.loads(target.read_bytes());assert report['status']=='pass' and not report['failures'];assert report['events_binding']['events']==2000
  rows.append({'name':entry['name'],'kind':entry['kind'],'status':'pass','report':str(target),'report_sha256':digest(target),'log_sha256':digest(log)})
  state['science_completed']=len(rows);save()
  (out/'science-summary.json').write_text(json.dumps({'status':'pass','rows':rows,'artifact_hashes_verified':hash_count},indent=2),encoding='utf-8',newline=chr(10))
  print('SCIENCE',len(rows),entry['name'],'pass',flush=True)
 resource=json.loads((base/'resource-independent.json').read_bytes());verify()
 final={'schema':'g4usim_f3_r3_independent_v1','status':resource['status'],'simulation_invocations':36,'events_per_process':2000,'science_comparisons':32,'science_status':'pass','artifact_hashes_verified':hash_count,'resource_rows':resource['rows'],'prior_batches_unchanged':True,'optimization_started':False,'stage_closed':False,'source_program_commit':'f812465bbfd58026201b70a23938e6bdc8ea12eb','scope':'engineering replay and resource baseline; not external physical validation or a unified-test v2 report'}
 (base/'baseline-independent-final.json').write_text(json.dumps(final,indent=2),encoding='utf-8',newline=chr(10))
 if resource['status']=='pass':
  bn=module('old_bottleneck',r/'out/collab/20261107-f3-baseline/preflight/bottleneck.py');selection=bn.analyse(timing);selection['scope']='target ranking only; function hotspot localization still required';(base/'target-selection.json').write_text(json.dumps(selection,indent=2),encoding='utf-8',newline=chr(10));state['status']='baseline_pass_pending_bottleneck_localization'
 else:state['status']='completed_inconclusive_stop_no_further_batch'
 state.update(phase='completed',finished_utc=datetime.now(timezone.utc).isoformat());save();print('R3_FINAL',state['status'],flush=True)
except BaseException as error:
 state.update(status='stopped_incomplete',error=str(error),traceback=traceback.format_exc(),finished_utc=datetime.now(timezone.utc).isoformat());save();print('R3_STOPPED',str(error),flush=True);raise

