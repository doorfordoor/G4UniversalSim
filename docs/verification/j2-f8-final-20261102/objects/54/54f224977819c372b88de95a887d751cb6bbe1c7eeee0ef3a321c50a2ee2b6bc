"""Verify relocation only; execute the frozen evidence checker, never test profiles."""
import hashlib,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
R=Path.cwd();A=R/'out/collab/j2-f8-archive-plan';V=A/'versions/v3-18c5858';S=A/'staging-v3-18c5858';O=V/'relocated-verification';assert not O.exists();O.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def put(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
m=j(V/'manifest.json');lookup={x['logical_path']:x for x in m['entries'] if x['archive_action'].startswith('copy_')};pairs=j(V/'strict-pairs.json')['pairs'];checker=S/'tree/scripts/check_report_evidence.py';assert sha(checker)==lookup['tree/scripts/check_report_evidence.py']['sha256']
spec=importlib.util.spec_from_file_location('_archive_only_checker',checker);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
seen={};runs=[]
def closure(logical):
 if logical in seen:return seen[logical]
 p=S/logical;x=j(p);assert sha(p)==lookup[logical]['sha256'];logs=[]
 for c in x['results']:
  q=mod.resolve_log(c,p);assert q and q.resolve().is_relative_to(S.resolve()),('original fallback forbidden',logical,c['name']);assert sha(q)==c['log_sha256'];logs.append({'case':c['name'],'path':q.relative_to(S).as_posix(),'sha256':sha(q),'status':c['status']})
 assert sum(c['assertions_executed'] for c in x['results'])==x['assertions_executed_total']
 seen[logical]={'report':logical,'sha256':sha(p),'cases':len(x['results']),'assertions':x['assertions_executed_total'],'git_head':x.get('git_head'),'git_dirty':x.get('git_dirty'),'logs':logs,'all_logs_inside_staging':True};return seen[logical]
for pair in pairs:
 for kind,logical,expected in [('historical-baseline',pair['baseline'],0),('original-current',pair['current'],pair['expected_exit'])]:
  closure(logical);cmd=[sys.executable,'-B',str(checker),'--report',str(S/logical)]
  if kind=='original-current':cmd+=['--baseline',str(S/pair['baseline'])]
  p=subprocess.run(cmd,cwd=O,capture_output=True);log=O/(pair['lane']+'-'+kind+'.log');log.write_bytes(p.stdout+p.stderr)
  run={'lane':pair['lane'],'group':pair['group'],'kind':kind,'report':logical,'report_sha256':sha(S/logical),'exit_code':p.returncode,'expected_exit':expected,'log':log.relative_to(A).as_posix(),'log_sha256':sha(log),'command':cmd,'allow_legacy_or_incomplete_flags':False};runs.append(run)
  put(O/'execution-progress.json',{'completed_runs':runs})
  assert p.returncode==expected,run
# Isolated negative derivative: copied bytes, never staged hardlinks.
base=S/pairs[0]['baseline'];d=j(base);negative=O/'tamper-negative';negative.mkdir();(negative/'report.json').write_bytes(base.read_bytes())
for c in d['results']:q=mod.resolve_log(c,base);shutil.copyfile(q,negative/q.name)
c=d['results'][0];q=mod.resolve_log(c,negative/'report.json');assert q and q.parent==negative;q.write_bytes(q.read_bytes()+b'\nARCHIVE_NEGATIVE_CONTROL\n')
p=subprocess.run([sys.executable,'-B',str(checker),'--report',str(negative/'report.json')],capture_output=True);(O/'tamper-negative.log').write_bytes(p.stdout+p.stderr);assert p.returncode==1
# Recheck all immutable copied objects after checker replay and derivative mutation.
unique={x['sha256']:x for x in lookup.values()}
for h,x in unique.items():assert sha(S/x['object'])==h
for path,x in lookup.items():assert (S/path).is_file() and (S/path).stat().st_size==x['bytes']
receipt={'schema':'j2_f8_additive_archive_relocation_v3','integrity_status':'passed','manifest_sha256':sha(V/'manifest.json'),'all_logs_resolved_only_in_staging':True,'report_or_log_bytes_rewritten':False,'strict_replays':runs,'report_closures':list(seen.values()),'baseline_runs_passed':sum(x['kind']=='historical-baseline' for x in runs),'original_runs_expected_pass':sum(x['kind']=='original-current' and x['expected_exit']==0 for x in runs),'original_failures_retained':sum(x['kind']=='original-current' and x['expected_exit']==1 for x in runs),'negative_derivative_exit':p.returncode,'negative_control_not_original_evidence':True,'stage_objects_rehashed':len(unique),'product_or_formal_profiles_run':False,'stage_completed':False}
put(O/'receipt.json',receipt)
print(json.dumps({'integrity':'passed','baseline_pass':receipt['baseline_runs_passed'],'original_pass':receipt['original_runs_expected_pass'],'original_failures_preserved':receipt['original_failures_retained'],'tamper_negative_exit':p.returncode,'staging_objects_rehashed':len(unique)},ensure_ascii=False))
