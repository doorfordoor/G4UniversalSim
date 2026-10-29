import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'out/verification/e6-visible-20261030'
PREP=BASE.parent/'e6-visible-acceptance-a779634'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(label,ok,detail=None):checks.append(dict(label=label,passed=bool(ok),detail=detail))
resources=read(PREP/'resource-hashes.json')
for r in resources:check('fixture:'+r['path'],sha(PREP/r['path'])==r['sha256'])
prep=read(PREP/'preparation-manifest.json')
for r in prep['current_source_files']:check('source:'+r['path'],sha(ROOT/r['path'])==r['sha256'])
sys.path.insert(0,str(ROOT/'scripts'));import run_m0_tests as m
frozen=read(ROOT/'docs/verification/e6-full-20261030/windows/final-1/report.json')
check('source_fingerprint',m.workspace_source_fingerprint()==frozen['source_fingerprint'])
check('tests_fingerprint',m.tests_content_fingerprint()==frozen['tests_content_fingerprint'])
build=read(ROOT/'docs/verification/e6-full-20261030/additional-files/1-e6-repair-build-identity.json')
check('exe_sha',sha(Path(frozen['backend_executable']))==build['executable_sha256'])
receipts=read(BASE/'receipts.json');stages={r['stage']:r for r in receipts};check('no_ERROR','ERROR' not in stages)
required=['migration-preview','migration-refusals','snapshot-restored','snapshot-regenerated','real-run-started','real-run-result','closed']
for s in required:check('receipt:'+s,s in stages)
index=read(PREP/'resource-index.json')
for c in index['duplicate_cases']:
 r=stages.get('duplicate-'+c['case']);check('duplicate_receipt:'+c['case'],r is not None)
 if not r:continue
 check('scope:'+c['case'],'no simulation' in r.get('scope',''))
 if c['case']=='projection1025':check('projection_rejection',bool(r['boxes']) and not r['command'] and not r['inspection']);continue
 cmds=r['command'];check('one_final_command:'+c['case'],len(cmds)==1)
 if not cmds:continue
 cmd=cmds[0]
 def arg(k):return cmd[cmd.index(k)+1] if k in cmd else None
 check('threads:'+c['case'],arg('--threads')==str(c['threads']))
 check('seed:'+c['case'],arg('--seed')==(None if c['seed'] is None else str(c['seed'])))
 check('name:'+c['case'],arg('--run-name')==c['run_name'])
r=stages.get('snapshot-regenerated')
if r:
 for rel in ['config/materials/material.ini','config/geometry/geometry.ini']:
  check('regenerated:'+rel,(Path(r['package'])/rel).read_bytes()==(Path(index['snapshot']['package'])/rel).read_bytes())
r=stages.get('real-run-result')
if r:
 result=r['result'];check('real_gui_success',result.get('state')=='success',result)
 check('real_gui_events',result.get('planned_events')==result.get('completed_events')==2 and result.get('run_count')==1)
 output=Path(r['output']);summary=output/'run_summary.txt';check('real_summary_exists',summary.exists())
 if summary.exists():
  pairs={}
  for line in summary.read_text(encoding='utf-8-sig').splitlines():
   if '=' in line:
    k,v=line.split('=',1);pairs[k.strip()]=v.strip()
  check('real_summary_status',pairs.get('status')=='completed',pairs.get('status'))
  check('real_summary_events',pairs.get('planned_event_count')==pairs.get('actual_completed_event_count')=='2', {k:v for k,v in pairs.items() if 'event' in k})
  check('real_summary_output_ok',pairs.get('output_failure_status')=='none',pairs.get('output_failure_status'))
  check('real_summary_run0',pairs.get('run_0_planned_events')==pairs.get('run_0_completed_events')=='2')
  check('real_summary_run_count',pairs.get('run_count')=='1')
  check('real_summary_write',pairs.get('summary_write_status')=='completed')
  check('real_summary_threads',pairs.get('actual_threads')=='2')
  check('real_summary_seed',pairs.get('configured_seed')=='43',{k:v for k,v in pairs.items() if 'seed' in k})
supp=BASE/'import-supplement'
supp_receipts=read(supp/'receipts.json');supp_stages={r['stage']:r for r in supp_receipts}
check('supplement_no_ERROR','ERROR' not in supp_stages)
check('supplement_closed','closed' in supp_stages)
for name in ['open','recent','snapshot','envelope']:
 r=supp_stages.get('passed-'+name,{})
 check('supplement_'+name+'_returned_false',r.get('returned') is False)
 check('supplement_'+name+'_state_unchanged',r.get('state_unchanged') is True)
 check('supplement_'+name+'_resources_unchanged',r.get('resources_unchanged') is True)
 check('supplement_'+name+'_real_modal',r.get('real_product_modal') is True)
check('supplement_app_exec_exit0',read(supp/'gui-exit.json').get('app_exec_exit_code')==0)
check('supplement_tool_exit0',read(supp/'process-exit.json').get('result',{}).get('exit_code')==0)
check('original_host_exit_unknown_retained',read(BASE/'process-exit.json').get('exit_code') is None)
native=[dict(path=str(p.relative_to(ROOT)),action=read(p).get('action')) for p in sorted((BASE/'native').glob('*.json'))]
report={'scope':'Read-only independent receipt/hash/backend checks; no UI operation; screenshot existence is not visual inspection','fixture_count':len(resources),'source_count':len(prep['current_source_files']),'checks':checks,'passed':all(x['passed'] for x in checks),'missing_required':[s for s in required if s not in stages],'native_root_receipts':native,'visual_review':'Root must separately record observed content and final screenshot review; this verifier does not view images','synthetic_scope':'Seven duplicate variants inspect/intercept commands only; real simulation is only the separate real-run receipt and backend evidence'}
Path(ROOT/'out/collab/e6-visible-independent-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'checks':len(checks),'failed':[x for x in checks if not x['passed']],'native_receipt_count':len(native)},ensure_ascii=False,indent=2))
sys.exit(0 if report['passed'] else 1)
