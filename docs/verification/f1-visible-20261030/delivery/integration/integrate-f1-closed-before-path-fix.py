from pathlib import Path
import datetime, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[2]
BASE='20ab4f3eb34b41d4004a4e1b9d38d2f2f290f366'
TARGET='7e75d28675427bc900de2c29d713c75022b57ab5'
DEST=ROOT/'docs/verification/f1-visible-20261030/integration-receipt.json'
JOURNAL=ROOT/'out/collab/f1-integration-live-receipt.json'
assert not JOURNAL.exists() and not DEST.exists(), 'Inspect existing receipt; do not replay'
prior=json.loads((ROOT/'out/collab/f1-integration-precheck.json').read_bytes())
INTEGRATION=Path(prior['worktrees']['integration']['path'])
ORIGINAL=Path(prior['worktrees']['original']['path'])
receipt={'schema':'f1_normal_integration_v1','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'stage_close_commit':TARGET,'product_commit':'f176d0ed4cea60b7ca5a80ed81017c9404ec1257',
    'integration_before':BASE,'steps':[],'completed':False}

def save():
    JOURNAL.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def command(cwd,*args):
    p=subprocess.run(['git',*args],cwd=cwd,capture_output=True)
    label=f'{len(receipt["steps"]):02}'
    log=ROOT/f'out/collab/f1-integrate-{label}.log'
    raw=p.stdout+p.stderr;log.write_bytes(raw)
    receipt['steps'].append({'cwd':str(cwd),'args':list(args),'exit_code':p.returncode,'log':str(log),
        'log_sha256':hashlib.sha256(raw).hexdigest(),'stdout':p.stdout.decode('utf-8',errors='replace') if len(p.stdout)<8000 else 'Full output in log'})
    save()
    if p.returncode: raise RuntimeError(f'Git command failed ({p.returncode}); inspect {log}; do not replay')
    return p.stdout.decode('utf-8').strip()

def snapshot(path):
    return {'head':command(path,'rev-parse','HEAD'),'branch':command(path,'branch','--show-current'),
        'status_lines':command(path,'status','--porcelain=v1').splitlines()}

save()
road=snapshot(ROOT);integ=snapshot(INTEGRATION);original=snapshot(ORIGINAL)
assert road['head']==TARGET and road['branch']=='roadmap/F1-output-provenance' and not road['status_lines']
assert integ['head']==BASE and integ['branch']=='codex' and not integ['status_lines']
old=prior['worktrees']['original']
assert original=={k:old[k] for k in ('head','branch','status_lines')}, 'Original workspace changed; inspect'
refs=dict(line.split()[::-1] for line in command(ROOT,'ls-remote','origin','refs/heads/codex','refs/heads/roadmap/F1-output-provenance').splitlines())
assert refs=={'refs/heads/codex':BASE,'refs/heads/roadmap/F1-output-provenance':TARGET}
command(ROOT,'merge-base','--is-ancestor',BASE,TARGET)
command(ROOT,'merge-base','--is-ancestor',receipt['product_commit'],TARGET)
changes=command(ROOT,'diff','--name-only',receipt['product_commit'],TARGET).splitlines()
assert all(p.startswith('docs/') or p in ('AGENTS.md','STATUS.md','CHANGELOG.md') for p in changes)
receipt['precheck']={'roadmap':road,'integration':integ,'original':original,'remote_refs':refs,'documentation_only_paths':len(changes)};save()
command(INTEGRATION,'merge','--ff-only',TARGET)
command(INTEGRATION,'push','origin','codex')
after=snapshot(INTEGRATION);original_after=snapshot(ORIGINAL)
assert after['head']==TARGET and after['branch']=='codex' and not after['status_lines']
assert original_after==original
remote=command(ROOT,'ls-remote','origin','refs/heads/codex','refs/heads/roadmap/F1-output-provenance')
assert all(line.split()[0]==TARGET for line in remote.splitlines()) and len(remote.splitlines())==2
receipt.update(completed=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    integration_after=after,original_workspace_unchanged=True,remote_heads_verified=remote,
    method='normal fast-forward and ordinary push; no force/reset/rebase; original D checkout untouched')
save()
with DEST.open('xb') as f: f.write(JOURNAL.read_bytes())
assert DEST.read_bytes()==JOURNAL.read_bytes()
print(json.dumps({'completed':True,'commit':TARGET,'receipt':str(DEST)}))
