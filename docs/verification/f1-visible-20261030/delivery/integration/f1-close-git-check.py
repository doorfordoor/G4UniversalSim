from pathlib import Path
import hashlib, json, re, subprocess, sys
sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[2]
ARCH='docs/verification/f1-visible-20261030'

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

changed=[p for p in git('diff','--cached','--name-only','-z').decode().split('\0') if p]
allowed={'AGENTS.md','CHANGELOG.md','STATUS.md','docs/ROADMAP.md','docs/agent-history.md','docs/功能支持矩阵.md','docs/输出身份与来源.md','docs/collab/ASTRA-BRIEF.md','docs/collab/reviews/20261030-astra-f1-close-review.md'}
assert changed and all(p in allowed or p.startswith(ARCH+'/') for p in changed)
assert not git('diff','--name-only'), 'Unstaged tracked changes'
assert not git('diff','--name-only','ede037f','--','docs/verification/f1-automated-20261030','docs/verification/f1-automated-review-20261030')
rows=[]
for record in git('ls-files','--stage','-z','--',ARCH).split(b'\0'):
    if not record: continue
    meta,name=record.split(b'\t',1)
    path=name.decode();mode,oid,stage=meta.decode().split()
    assert stage=='0'
    raw=(ROOT/path).read_bytes()
    actual=git('hash-object','--no-filters','--',path).decode().strip()
    assert oid==actual, path
    rows.append({'path':path,'size_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_object':oid})
assert {str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/ARCH).rglob('*') if p.is_file()}=={r['path'] for r in rows}
links=[]
readme=ROOT/ARCH/'README.md'
for url in re.findall(r'\]\(([^)]+)\)',readme.read_text(encoding='utf-8')):
    if '://' in url or url.startswith('#'):continue
    target=(readme.parent/url.split('#')[0]).resolve()
    assert target.exists(),url
    links.append(url)
sys.path.insert(0,str(ROOT/'scripts'))
import run_m0_tests as runner
source=runner.workspace_source_fingerprint();tests=runner.tests_content_fingerprint()
assert source=='db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc'
assert tests=='57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35'
receipt={'status':'passed','staged_paths':len(changed),'archive_raw_git_blobs':len(rows),'source_fingerprint':source,
    'tests_content_fingerprint':tests,'new_readme_local_links_checked':links,'files':rows}
target=ROOT/'out/collab/f1-close-staged-integrity.json'
with target.open('xb') as stream: stream.write((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in receipt.items() if k!='files'},ensure_ascii=False))
