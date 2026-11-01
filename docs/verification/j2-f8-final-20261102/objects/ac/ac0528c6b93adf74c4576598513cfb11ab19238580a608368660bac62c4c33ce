"""Audit six whole reports from one frozen candidate; never splice case rows."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'out/verification/j2-f8-18c5858'
HEAD='18c5858fd6e80a5cb6096beacebfef69c479ad49'
EXPECTED={'windows-static':46,'windows-gui':66,'windows113-backend':63,
          'windows114-backend':63,'windows113-integration':31,'windows114-integration':31}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
result={'head':HEAD,'purpose':'six complete frozen local reports; not CI/native/stage acceptance','profiles':{},'errors':[]}
for name,count in EXPECTED.items():
    folder=BASE/name
    launch_path=folder/'launch.json'
    if not launch_path.exists():
        result['errors'].append(name+': launch absent');continue
    launch=json.loads(launch_path.read_text())
    if launch['status'] not in ('passed','failed'):
        result['errors'].append(name+': not terminal');continue
    report_path=Path(launch['report'])
    assert report_path.is_relative_to(folder)
    payload=json.loads(report_path.read_text())
    baseline=json.loads(Path(launch['baseline']['path']).read_text())
    previous={r['name']:r for r in baseline['results']}
    rows=payload['results']
    errors=[]
    for condition,label in [
        (launch['status']=='passed','launcher status'),
        (launch['runner_exit_code']==launch['gate_exit_code']==0,'process/gate status'),
        (not launch['identity_errors'],'launch identity'),
        (sha(report_path)==launch['report_sha256'],'report SHA'),
        (len(rows)==count,'case count'),
        (payload['git_head']==HEAD and payload['git_dirty'] is False,'git identity'),
        (payload['assert_probe']=='settrace_assert_lines_v3','probe'),
        (payload['tests_content_fingerprint']==launch['starting_sources']['tests_content_fingerprint'],'tests identity'),
        (payload['cases_with_zero_assertions']==[],'zero assertions'),
        (all(r['status']=='pass' and r['exit_code']==0 and r['assertions_executed']>0 for r in rows),'case status'),
        (sum(r['assertions_executed'] for r in rows)==payload['assertions_executed_total'],'assertion sum'),
        (set(previous)<={r['name'] for r in rows},'missing baseline cases')]:
        if not condition: errors.append(label)
    drops=[]
    for row in rows:
        log=Path(row['log']) if 'log' in row else report_path.parent/(row['name']+'.log')
        if not log.is_absolute(): log=ROOT/log
        if sha(log)!=row['log_sha256']:errors.append('log SHA '+row['name'])
        if row['name'] in previous and row['assertions_executed']<previous[row['name']]['assertions_executed']:
            drops.append(row['name'])
    if drops:errors.append('baseline drops '+','.join(drops))
    result['profiles'][name]={'report':str(report_path.relative_to(ROOT)),'report_sha256':sha(report_path),
        'launch_sha256':sha(launch_path),'cases':len(rows),'assertions':payload['assertions_executed_total'],
        'baseline_assertions':baseline['assertions_executed_total'],'errors':errors}
    result['errors'].extend(name+': '+item for item in errors)
result['cases']=sum(r['cases'] for r in result['profiles'].values())
result['assertions']=sum(r['assertions'] for r in result['profiles'].values())
result['status']='passed' if not result['errors'] and result['cases']==300 else 'incomplete_or_failed'
(BASE/'local-final-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'cases':result['cases'],'assertions':result['assertions'],'errors':result['errors']}))
raise SystemExit(0 if result['status']=='passed' else 1)
