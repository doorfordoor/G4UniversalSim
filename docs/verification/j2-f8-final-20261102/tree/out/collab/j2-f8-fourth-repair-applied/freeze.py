"""Freeze exactly two reviewed tests plus five reviewed documents."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
DRAFT=ROOT/'out/collab/j2-f8-fourth-doc-draft/frozen-v3'
REVIEW=ROOT/'out/collab/j2-f8-fourth-doc-independent-review/receipt.json'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(data):return hashlib.sha256(data).hexdigest()
def git(*args): return subprocess.check_output(['git','-c','core.longpaths=true',*args],cwd=ROOT)
base='18c5858fd6e80a5cb6096beacebfef69c479ad49'
assert git('rev-parse','HEAD').decode().strip()==base
assert not git('diff','--cached','--name-only')
assert not (OUT/'freeze.json').exists()
assert sha(DRAFT/'manifest.json')=='e094037f010be282fc9ee91572103913e58199a9a22009b96333823fa53efbea'
assert sha(DRAFT/'docs.patch')=='3cbdb2975abcb36a88325f49851cddef0d025c2ca6cf8c82a62cb8ce1bcc1a03'
assert sha(REVIEW)=='97e7510c32d850d416321baed4c4eadcc4f996457c5f5712dd8593044ac3c31b'
review=json.loads(REVIEW.read_bytes())
assert review['status']=='pass'
manifest=json.loads((DRAFT/'manifest.json').read_bytes())
assert manifest['base_head']==base and len(manifest['files'])==5
applied=json.loads((OUT/'tests-apply-receipt.json').read_bytes())
assert {n.decode() for n in git('diff','--name-only','-z').split(b'\0') if n}==set(applied['after'])
for name,expected in applied['after'].items(): assert sha(ROOT/name)==expected
f8path=OUT/'f8/receipt.json'
assert sha(f8path)=='ddee1d2dedd01ca6690a13964d1353e659a237534cb468ba703cee7157b8f4e6'
f8=json.loads(f8path.read_bytes())
assert f8['processes_all_finished'] and f8['gui149_unchanged'] and f8['source_before_equals_after']
assert len(f8['runs'])==2 and all(r['exit_code']==0 and r['assertions_v3']==655 for r in f8['runs'])
geometry=json.loads((OUT/'geometry/receipt.json').read_bytes())
assert geometry['status']=='passed' and geometry['assertions_v3']==214
for row in manifest['files']:
    assert sha(ROOT/row['path'])==row['original_sha256']
    assert sha(DRAFT/'proposed'/row['path'])==row['candidate_sha256']
git('apply','--check','--',str(DRAFT/'docs.patch'))
for row in manifest['files']:
    (ROOT/row['path']).write_bytes((DRAFT/'proposed'/row['path']).read_bytes())
after=dict(applied['after'])
after.update({row['path']:row['candidate_sha256'] for row in manifest['files']})
for path,expected in after.items(): assert sha(ROOT/path)==expected
for path,expected in applied['gui149_sha256_unchanged'].items(): assert sha(ROOT/path)==expected
assert {n.decode() for n in git('diff','--name-only','-z').split(b'\0') if n}==set(after)
assert not git('ls-files','--others','--exclude-standard')
git('diff','--check')
linkcheck=subprocess.run([sys.executable,'-B','scripts/check_doc_links.py'],cwd=ROOT,capture_output=True)
(OUT/'doc-links.log').write_bytes(linkcheck.stdout+linkcheck.stderr)
assert linkcheck.returncode==0,(linkcheck.stdout+linkcheck.stderr).decode(errors='replace')[-1500:]
git('add','--',*sorted(after))
assert {n.decode() for n in git('diff','--cached','--name-only','-z').split(b'\0') if n}==set(after)
for path,expected in after.items(): assert digest(git('show',':'+path))==expected, path
git('diff','--cached','--check')
commit=git('commit','-m','Align J2 and F8 smoke checks with platform interface contracts')
(OUT/'commit.log').write_bytes(commit)
head=git('rev-parse','HEAD').decode().strip()
assert not git('status','--porcelain=v1')
for path,expected in after.items(): assert sha(ROOT/path)==expected and digest(git('show',head+':'+path))==expected
before={p:digest(git('show',base+':'+p)) for p in after}
freeze={'status':'committed_clean_candidate_not_stage_acceptance','base_head':base,'head':head,'files':[{'path':p,'before_sha256':before[p],'after_sha256':after[p]} for p in sorted(after)],'product_gui149_unchanged':True,'test_review_plan':'out/collab/j2-f8-fourth-repair-plan/tests.json','test_review_plan_sha256':sha(ROOT/'out/collab/j2-f8-fourth-repair-plan/tests.json'),'docs_manifest_sha256':sha(DRAFT/'manifest.json'),'docs_independent_receipt_sha256':sha(REVIEW),'actual_tracked_validation':{'geometry_assertions':214,'f8_125_assertions':655,'f8_150_assertions':655,'compileall_exit':0,'doc_links_exit':linkcheck.returncode},'formal_matrix':'pending fresh new-head builds, profiles and actual CI','native':'old18c file mapping pending; representative new native pending'}
(OUT/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'head':head,'files':len(after),'status':freeze['status']}))
