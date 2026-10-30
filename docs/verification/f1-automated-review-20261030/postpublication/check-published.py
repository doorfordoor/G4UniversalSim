from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
ARCHIVE=ROOT/'docs/verification/f1-automated-20261030'
HEAD='f176d0ed4cea60b7ca5a80ed81017c9404ec1257'
SOURCE='db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc'
TESTS='57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    def unique(rows):
        result={}
        for k,v in rows:
            assert k not in result,('duplicate JSON key',k)
            result[k]=v
        return result
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique)
def local(value):
    p=ARCHIVE/value
    assert not p.is_symlink() and p.resolve().is_relative_to(ARCHIVE.resolve()),value
    return p
def bytes_match(path,row):
    assert path.is_file() and path.stat().st_size==row['size'] and sha(path)==row['sha256'],str(path)

m=load(ARCHIVE/'archive-manifest.json')
v=load(ARCHIVE/'archive-verification.json')
c=load(ARCHIVE/'archive-complete.json')
assert sha(ARCHIVE/'archive-manifest.json')==c['manifest_sha256']
assert sha(ARCHIVE/'archive-verification.json')==c['verification_sha256']
assert m['expected_head']==m['frozen']['head_sha']==HEAD
assert m['frozen']['source_fingerprint']==SOURCE and m['frozen']['tests_content_fingerprint']==TESTS
assert not m['missing_sources'] and not m['preflight_blockers']
assert len(m['files'])==v['files_sha256_matched']==2797
members=[r['archive_path'] for r in m['files']]
assert len(members)==len(set(x.casefold() for x in members))
source_count=0
for row in m['files']:
    bytes_match(local(row['archive_path']),row)
    source=Path(row['source'])
    assert source.is_file(),str(source)
    bytes_match(source,row)
    source_count+=1
generated=[r['path'] for r in v['generated_verification_files']]
assert len(generated)==38 and len(generated)==len(set(generated))
assert not set(members)&set(generated)
for row in v['generated_verification_files']:bytes_match(local(row['path']),row)
expected=set(members)|set(generated)|{'archive-started.json','archive-manifest.json','archive-verification.json','archive-complete.json'}
actual={p.relative_to(ARCHIVE).as_posix() for p in ARCHIVE.rglob('*') if p.is_file()}
assert actual==expected,{'extra':sorted(actual-expected),'missing':sorted(expected-actual)}
readme=(ARCHIVE/'README.md').read_text(encoding='utf-8')
assert '阶段未关闭' in readme and '实窗观察仍 pending' in readme and '尚未合入 codex' in readme

categories=Counter(r['category'] for r in v['reports'])
assert categories=={'baseline':1,'accepted_windows':1,'accepted_ci':12,'historical_ci':20,'historical_windows':2}
release=[]
history=[]
for row in v['reports']:
    data=load(local(row['report']))
    if row['category'] in ('accepted_windows','accepted_ci'):
        assert row['strict_gate_exit_code']==0 and row['all_pass'] and row['meaning']=='release evidence'
        assert data['git_head']==HEAD and data['source_fingerprint']==SOURCE and data['tests_content_fingerprint']==TESTS
        assert all(r['status']=='pass' and r['exit_code']==0 and r['assertions_executed']>0 for r in data['results'])
        assert sum(r['assertions_executed'] for r in data['results'])==data['assertions_executed_total']
        release.append(row)
    elif row['category'].startswith('historical'):
        assert row['report'].startswith('history/') and row['meaning']=='retained original history, not release acceptance'
        history.append({'path':row['report'],'category':row['category'],'failed_cases':sum(r['status']=='fail' for r in data['results']),
                        'strict_gate_exit_code':row['strict_gate_exit_code']})
assert len(release)==13 and len(history)==22
assert any(r['failed_cases']>0 for r in history)
assert [(r['recorded_status'],r['reports']) for r in m['historical_rounds'] if r['category']=='historical_ci']==[('failed',8),('failed',12)]

windows=load(local('windows/final-1/report.json'))
baseline=load(local('baseline/1/report.json'))
assert windows['assert_probe']==baseline['assert_probe']=='settrace_assert_lines_v3'
assert windows['cases_with_zero_assertions']==[] and baseline['cases_with_zero_assertions']==[]
assert len(windows['results'])==143 and len(baseline['results'])==134
current={r['name']:r['assertions_executed'] for r in windows['results']}
assert all(current[r['name']]>=r['assertions_executed'] for r in baseline['results'])
assert windows['assertions_executed_total']==48511>=baseline['assertions_executed_total']==42815
assert v['baseline_comparisons']==[{'report':'windows/final-1/report.json','baseline':'baseline/1/report.json','exit_code':0}]

topology={'linux-evidence-11.3.2':{'static','gui','backend','integration'},
          'linux-evidence-11.4.3':{'static','gui','backend','integration'},
          'm0-report-windows-latest':{'static','gui'},'m0-report-ubuntu-latest':{'static','gui'}}
pairs=[]
executions=0
for row in release:
    if row['category']!='accepted_ci':continue
    data=load(local(row['report']))
    artifact=Path(row['report']).parts[1]
    pairs.append((artifact,data['profile']))
    assert {r['name'] for r in data['results']}==set(m['frozen']['profiles'][data['profile']])
    executions+=len(data['results'])
assert len(set(pairs))==12 and set(pairs)=={(a,p) for a,profiles in topology.items() for p in profiles}
assert executions==414
workflows={41028779177:('.github/workflows/linux-geant4.yml',{'ubuntu-24.04 / Geant4 11.3.2','ubuntu-24.04 / Geant4 11.4.3'}),
           41028779326:('.github/workflows/m0-static-gui.yml',{'windows-latest / Python 3.11','ubuntu-latest / Python 3.11'})}
artifacts=[]
for run_id,(workflow,names) in workflows.items():
    raw=load(local(f'ci/{run_id}-run.json'))
    jobs=load(local(f'ci/{run_id}-jobs.json'))['jobs']
    assert raw['id']==run_id and raw['path']==workflow and raw['head_sha']==HEAD
    assert raw['status']=='completed' and raw['conclusion']=='success' and raw['event']=='push' and raw['run_attempt']>0
    assert len(jobs)==2 and {r['name'] for r in jobs}==names
    for job in jobs:
        assert job['run_id']==run_id and job['status']=='completed' and job['conclusion']=='success'
        assert local(f"ci/job-{job['id']}.log").stat().st_size>0
    official=load(local(f'ci/{run_id}-artifacts.json'))['artifacts']
    for artifact in official:
        assert artifact['workflow_run']['id']==run_id and artifact['workflow_run']['head_sha']==HEAD
        artifacts.append(artifact['name'])
assert len(artifacts)==4 and set(artifacts)==set(topology)

result={'status':'approved_automated_archive_only','checked_utc':datetime.now(timezone.utc).isoformat(),
        'archive':str(ARCHIVE),'tested_product_head':HEAD,'manifest_file_count':2797,
        'archive_and_current_source_sha_size_matches':source_count,'generated_verification_file_count':38,
        'complete_manifest_sha256':c['manifest_sha256'],'complete_verification_sha256':c['verification_sha256'],
        'actual_file_set_exact':True,'release_reports':13,'historical_reports':22,'report_categories':dict(categories),
        'historical_failure_case_executions':sum(r['failed_cases'] for r in history),
        'windows_cases':143,'windows_assertions':48511,'e6_baseline_cases':134,'e6_baseline_assertions':42815,
        'same_probe_per_case_baseline_nondecrease':True,'ci_case_executions':414,'ci_artifacts':artifacts,
        'ci_original_success_run_ids':list(workflows),'readme_phase_open_and_visible_pending':True,
        'visible_acceptance':'pending','phase_complete':False,'archive_bytes_modified':False}
(HERE/'independent-bytes-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
