"""Offline terminal receipt inventory, run only after final original job is collected."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HEAD='2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
public=load(ROOT/'public-push-runs-final.json')
runs=public['raw_pages'][0]['workflow_runs']
assert len(runs)==4 and all(r['head_sha']==HEAD and r['event']=='push' and r['status']=='completed' and r['run_attempt']==1 for r in runs)
runids={r['id'] for r in runs}
catalog={}
for path in ROOT.glob('artifacts-*.json'):
    raw=load(path);raw=raw.get('structuredContent',raw)
    for row in raw.get('artifacts',[]):
        if row['id'] in catalog:assert row['digest']==catalog[row['id']]['digest']
        catalog[row['id']]=row
assert len(catalog)==8
files=[]
for row in catalog.values():
    assert row['workflow_run']['head_sha']==HEAD and row['workflow_run']['id'] in runids and not row['expired']
    path=ROOT/'artifacts'/f'{row["name"]}-{row["id"]}.zip'
    assert path.stat().st_size==row['size_in_bytes'] and 'sha256:'+sha(path)==row['digest']
    files.append(dict(role='github_original_artifact_zip',path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=sha(path),artifact_id=row['id'],run_id=row['workflow_run']['id']))
jobs=load(ROOT/'jobs-final.json')['jobs']
assert len(jobs)==8 and len({j['id'] for j in jobs})==8
initial_jobs=[j for p in ROOT.glob('jobs-initial-*.json') for j in load(p)['structuredContent']['jobs']]
assert {j['id'] for j in initial_jobs}=={j['id'] for j in jobs}, 'Do not substitute jobs from a later attempt'
linux_run=next(r['id'] for r in runs if r['path'].endswith('/linux-geant4.yml'))
negative_controls=[dict(job_id=j['id'],conclusions=[s['conclusion'] for s in j['steps']
                    if s['name']=='Verify the evidence gate rejects a tampered report'])
                   for j in jobs if j['run_id']==linux_run]
negative_controls_verified=len(negative_controls)==2 and all(r['conclusions']==['success'] for r in negative_controls)
for job in jobs:
    assert job['run_id'] in runids and job['status']=='completed'
    path=ROOT/f'job-{job["id"]}.log';assert path.is_file()
    files.append(dict(role='github_connector_decoded_complete_job_log',path=path.name,bytes=path.stat().st_size,sha256=sha(path),job_id=job['id'],run_id=job['run_id']))
gates=load(ROOT/'report-gates-current.json')
assert gates['candidate_head']==HEAD
actual_profiles=[(r['lane'],r['profile']) for a in gates['artifacts'] for r in a['reports']]
assert len(actual_profiles)==len(set(actual_profiles)), 'Ambiguous duplicate profile reports'
expected_profiles={(lane,profile) for lane in ('m0-linux','m0-windows') for profile in ('static','gui')}
expected_profiles|={(lane,profile) for lane in ('linux113','linux114') for profile in ('static','gui','backend','integration')}
missing_profiles=sorted(expected_profiles-set(actual_profiles))
unexpected_profiles=sorted(set(actual_profiles)-expected_profiles)
semantics={}
for name in ('desktop-linux-checked.json','desktop-win32-checked.json','installation-linux-checked.json','installation-windows-checked.json'):
    value=load(ROOT/name);assert value['candidate_head']==HEAD and value['status']=='independently_verified'
    semantics[name]=dict(sha256=sha(ROOT/name),status=value['status'])
result=dict(candidate_head=HEAD,workflow_completion='all_completed',runs=[{k:r[k] for k in ('id','path','head_sha','event','status','conclusion','run_attempt')} for r in runs],files=files,strict_pass=gates['strict_pass'],strict_fail=gates['strict_fail'],actual_profiles=sorted(actual_profiles),missing_profiles=missing_profiles,unexpected_profiles=unexpected_profiles,desktop_installation_semantic_receipts=semantics,release_accepted=all(r['conclusion']=='success' for r in runs) and gates['strict_fail']==0 and not missing_profiles and not unexpected_profiles,acceptance_scope='CI workflow/report evidence only; not stage acceptance, new native observation or physical validation.',note='Run HEAD binds jobs through run_id; connector jobs do not supply head_sha. Initial attempt-1 job IDs must match. Original artifact ZIPs and complete decoded job logs are distinct formats. No workflow rerun or relaxed evidence gate.')
result['ci_tamper_negative_control_steps']=negative_controls
result['ci_tamper_negative_controls_verified']=negative_controls_verified
result['release_accepted']=result['release_accepted'] and negative_controls_verified
path=ROOT/'collected-files-final.json';assert not path.exists();path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(files=len(files),strict_pass=result['strict_pass'],strict_fail=result['strict_fail'],release_accepted=result['release_accepted'])))
