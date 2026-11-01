"""Apply exactly the two independently reviewed test files after all six runs."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'out/collab/j2-f8-fourth-repair-applied'
PLAN=Path(__file__).with_name('tests.json')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args): return subprocess.check_output(['git','-c','core.longpaths=true',*args],cwd=ROOT)
assert sha(PLAN)=='c681e18421e4b38503b18b695961bfe10941bc61d635153c1e04259a8ae6ba8c'
plan=json.loads(PLAN.read_bytes())
assert git('rev-parse','HEAD').decode().strip()==plan['base_head']
assert not git('status','--porcelain=v1')
aggregate=ROOT/'out/verification/j2-f8-18c5858/local-final-audit.json'
assert sha(aggregate)=='bff2dd04d5143d33687b08a85ba80f68707d4297b6955e67cc50c640cbd51113'
a=json.loads(aggregate.read_bytes())
assert a['status']=='passed' and a['cases']==300 and not a['errors']
terminal=json.loads((ROOT/'out/verification/j2-f8-18c5858/windows114-integration/terminal-sync.json').read_bytes())
assert terminal['status']=='passed'
native=json.loads((ROOT/'out/verification/j2-f8-18c5858/native100/identity.json').read_bytes())
product_before={name:sha(ROOT/name) for name in native['gui_files']}
assert product_before==native['gui_files']
for row in plan['entries']:
    assert sha(ROOT/row['target'])==row['before']
    assert sha(ROOT/row['candidate'])==row['after']
    assert sha(ROOT/row['patch'])==row['patch_sha']
    assert sha(ROOT/row['review'])==row['review_sha256']
git('apply','--check','--',*[r['patch'] for r in plan['entries']])
OUT.mkdir(exist_ok=False)
before={r['target']:sha(ROOT/r['target']) for r in plan['entries']}
for row in plan['entries']:
    (ROOT/row['target']).write_bytes((ROOT/row['candidate']).read_bytes())
after={r['target']:sha(ROOT/r['target']) for r in plan['entries']}
assert after=={r['target']:r['after'] for r in plan['entries']}
assert product_before=={name:sha(ROOT/name) for name in product_before}
changed={p.decode() for p in git('diff','--name-only','-z').split(b'\0') if p}
assert changed==set(before), changed
git('diff','--check')
receipt={'status':'exact_reviewed_test_bytes_applied','head':plan['base_head'],'plan_sha256':sha(PLAN),'aggregate_sha256':sha(aggregate),'before':before,'after':after,'gui149_sha256_unchanged':product_before,'scope':'Two tests only; docs pending independent freeze. Formal new candidate not started.'}
(OUT/'tests-apply-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':receipt['status'],'files':len(after),'product_unchanged':len(product_before)}))
