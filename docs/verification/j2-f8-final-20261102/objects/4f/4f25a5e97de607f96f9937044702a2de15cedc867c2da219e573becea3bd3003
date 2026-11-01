"""Offline terminal receipt inventory, run only after final original job is collected."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HEAD='2901f4254303c3a9089c9025717908c0d77ff190'
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
for job in jobs:
    assert job['run_id'] in runids and job['status']=='completed'
    path=ROOT/f'job-{job["id"]}.log';assert path.is_file()
    files.append(dict(role='github_connector_decoded_complete_job_log',path=path.name,bytes=path.stat().st_size,sha256=sha(path),job_id=job['id'],run_id=job['run_id']))
gates=load(ROOT/'report-gates-current.json')
assert gates['candidate_head']==HEAD
semantics={}
for name in ('desktop-linux-checked.json','desktop-win32-checked.json','installation-linux-checked.json','installation-windows-checked.json'):
    value=load(ROOT/name);assert value['candidate_head']==HEAD and value['status']=='independently_verified'
    semantics[name]=dict(sha256=sha(ROOT/name),status=value['status'])
result=dict(candidate_head=HEAD,workflow_completion='all_completed',runs=[{k:r[k] for k in ('id','path','head_sha','event','status','conclusion','run_attempt')} for r in runs],files=files,strict_pass=gates['strict_pass'],strict_fail=gates['strict_fail'],desktop_installation_semantic_receipts=semantics,release_accepted=all(r['conclusion']=='success' for r in runs) and gates['strict_fail']==0,note='Run HEAD binds jobs through run_id; connector jobs do not supply head_sha. Original artifact ZIPs and complete decoded job logs are distinct formats. No workflow rerun or relaxed evidence gate.')
path=ROOT/'collected-files-final.json';assert not path.exists();path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(files=len(files),strict_pass=result['strict_pass'],strict_fail=result['strict_fail'],release_accepted=result['release_accepted'])))
