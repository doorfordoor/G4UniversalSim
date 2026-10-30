"""Independent read-only audit of the published F1 visible evidence copy."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/'docs/verification/f1-visible-20261030'
OUTPUT=ROOT/'out/collab/f1-visible-published-evidence-final.json'
PRODUCT='f176d0ed4cea60b7ca5a80ed81017c9404ec1257'
GUI='ede037f26db63f606e3ca086d5d586f222f428df'
SOURCE='db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc'
TESTS='57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35'
EXE='f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def sha(path):return digest(path.read_bytes())
def load(path):
    def unique(rows):
        result={}
        for key,value in rows:
            assert key not in result,('duplicate JSON key',key)
            result[key]=value
        return result
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def local(root,value):
    p=root/value
    assert not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),value
    return p
def verify(path,row):
    assert path.is_file() and path.stat().st_size==row['size_bytes'] and sha(path)==row['sha256'],str(path)

m=load(ARCHIVE/'copy-manifest.json')
v=load(ARCHIVE/'copy-verification.json')
p=load(ARCHIVE/'prior-archive-preservation.json')
c=load(ARCHIVE/'closure-state.json')
assert m['schema']=='f1_visible_copy_manifest_v1' and m['count']==len(m['files'])==102
assert m['total_bytes']==sum(r['size_bytes'] for r in m['files'])==4544178
assert v['status']=='passed' and v['copied_files']==102 and v['copied_bytes']==4544178
assert v['copy_manifest_sha256']==sha(ARCHIVE/'copy-manifest.json')
assert len({r['path'].casefold() for r in m['files']})==102
for row in m['files']:
    verify(local(ARCHIVE,row['path']),row)
    verify(Path(row['source']),row)
expected={r['path'] for r in m['files']}
actual={q.relative_to(ARCHIVE).as_posix() for q in (ARCHIVE/'evidence').rglob('*') if q.is_file()}
assert actual==expected

# Independently anchor old archive bytes to both the saved list and GUI Git tree.
assert p['baseline_commit']==GUI and p['count']==len(p['files'])==v['prior_archive_files_preserved']==2850
prior={r['path']:r for r in p['files']}
assert len(prior)==2850
old_roots=['docs/verification/f1-automated-20261030','docs/verification/f1-automated-review-20261030']
tree=git('ls-tree','-r','-z',GUI,'--',*old_roots)
blobs={}
for record in tree.split(b'\0'):
    if not record:continue
    header,path=record.split(b'\t',1)
    mode,kind,oid=header.decode().split()
    assert kind=='blob' and mode!='120000'
    blobs[path.decode('utf-8')]=oid
assert set(blobs)==set(prior)
raw=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,
                   input=''.join(oid+'\n' for oid in blobs.values()).encode(),capture_output=True,check=True).stdout
offset=0
for path,oid in blobs.items():
    end=raw.index(b'\n',offset)
    returned,kind,length=raw[offset:end].decode().split()
    assert returned==oid and kind=='blob'
    size=int(length)
    body=raw[end+1:end+1+size]
    assert raw[end+1+size:end+2+size]==b'\n'
    offset=end+2+size
    row=prior[path]
    assert row['size_bytes']==len(body) and row['sha256']==digest(body),path
    verify(local(ROOT,path),row)
assert offset==len(raw)
actual_old={q.relative_to(ROOT).as_posix() for root in old_roots for q in (ROOT/root).rglob('*') if q.is_file()}
assert actual_old==set(prior)
old_readme=(ROOT/old_roots[0]/'README.md').read_text(encoding='utf-8')
assert '实窗观察仍 pending' in old_readme and '阶段未关闭' in old_readme

changed=[x for x in git('diff','--name-only','-z',PRODUCT,GUI).decode('utf-8').split('\0') if x]
assert changed and all(x.startswith('docs/') or x in ('AGENTS.md','README.md','ROADMAP.md','STATUS.md','CHANGELOG.md') for x in changed)
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'gui')]
import run_m0_tests as runner
from g4usim_gui.output.provenance import output_evidence
assert runner.workspace_source_fingerprint()==SOURCE and runner.tests_content_fingerprint()==TESTS
assert sha(ROOT/'out/build-f1/Release/G4UniversalSim.exe')==EXE

visible=ARCHIVE/'evidence/visible'
host=load(visible/'host-state.json')
process=load(visible/'process-receipt.json')
observations=load(visible/'observations.json')
post=load(visible/'post-close-windows.json')
assert host['ready'] is True and host['closed'] is True and host['pid']==process['final_host_pid']==38052
assert host['observation_acceptance']=='pending' and process['phase_complete'] is False
assert process['old_host_exit_code']==process['final_host_exit_code']==0
assert process['host_state_sha256']==sha(visible/'host-state.json')
assert post['windows']==[] and 'Alt' in process['close_method']
assert observations['product_commit']==PRODUCT and observations['gui_checkout']==GUI
entries=observations['entries']
assert len(entries)==process['observations']==14 and len({r['label'] for r in entries})==14
from PIL import Image
for row in entries:
    image=visible/row['image']
    assert sha(image)==row['sha256'] and image.read_bytes().startswith(b'\xff\xd8\xff')
    with Image.open(image) as bitmap:
        assert bitmap.size==(row['width'],row['height']) and bitmap.format=='JPEG'
    assert row['observation']=='direct_native_tool_image_seen_by_root'
    assert (visible/(row['label']+'.txt')).stat().st_size>0
    assert row['window']['id']==593824 and GUI[:12] in row['window']['title']
    assert host['identity_at_load']['captured_utc']<=row['saved_utc']<host['closed_utc']
assert host['closed_utc']<process['recorded_utc'] and host['closed_utc']<post['recorded_utc']
for key in ('identity_before_import','identity_at_load','identity_at_exit'):
    identity=host[key]
    assert identity['git_head']==GUI and identity['source_fingerprint']==SOURCE and identity['tests_content_fingerprint']==TESTS
    assert identity['host_sha256']==sha(ARCHIVE/'evidence/review/f1-visible-final-host.py')
for row in host['real_output_records']:
    assert row['identity_status']=='verified' and row['source_matches_loaded_code'] is True
    assert row['recorded_build']['git_commit']==PRODUCT and row['build_commit_matches_expected_head'] is False

# Verify the copied outputs at the new root without changing or re-running them.
real=ARCHIVE/'evidence/real-backend'
fixture=load(real/'fixture-receipt.json')
evidence=output_evidence(real,fresh=True)
assert evidence.status=='verified' and len(evidence.files)==20
assert evidence.manifest_digest==fixture['manifest_sha256']==sha(real/'run_metadata.json')
assert fixture['backend_exit_code']==0 and fixture['actual_threads']=='2'
assert [(r['run_id'],r['planned_events'],r['completed_events']) for r in fixture['runs']]==[(0,2,2),(1,2,2)]
assert fixture['output_format_requested']=='auto' and fixture['output_format_actual']=='root'
assert len(evidence.document['provenance']['inputs'])==3
assert fixture['visible_observation']=='pending'

assert c['phase_complete'] is True and c['phase']=='F1' and c['product_commit']==PRODUCT and c['visible_gui_checkout']==GUI
assert c['automatic_acceptance']=='passed' and c['visible_acceptance']=='passed_root_direct_native_observations'
assert c['independent_evidence_review']=='approved' and c['scope_review']=='approved'
assert c['visible_observation_count']==14 and c['final_host_exit_code']==0 and c['previous_records_unchanged'] is True
assert c['next_phase']=='F4' and 'separately' in c['integration_boundary']
readme=(ARCHIVE/'README.md').read_text(encoding='utf-8')
assert '阶段已完成' in readme and PRODUCT in readme and GUI in readme
assert '滞后' in readme and '未证实' in readme
assert '原自动归档中的实窗pending' in readme and 'Q2' in readme and 'K1' in readme and 'J1' in readme
assert '**F4' in readme and '另行登记' in readme
for name in ('f1-visible-final-audit-review.md','f1-final-scope-review.md'):
    text=(ARCHIVE/'evidence/review'/name).read_text(encoding='utf-8')
    assert ('APPROVE' in text if 'audit-review' in name else '可以进入' in text)

docs={
 'AGENTS.md':['F1阶段关闭','f1-visible-20261030/README.md'],
 'CHANGELOG.md':['F1已关闭','f1-visible-20261030/README.md'],
 'STATUS.md':['F1阶段已关闭','f1-visible-20261030/README.md'],
 'docs/ROADMAP.md':['F1 and F6 done','| **F1**','已完成：产品f176d0e','| **F4**'],
 'docs/agent-history.md':['F1 实窗补验与阶段关闭','F1完整约定范围关闭'],
 'docs/功能支持矩阵.md':['F1已验收','f1-visible-20261030/README.md','不提升任何物理功能等级'],
 'docs/输出身份与来源.md':['F1已关闭','f1-visible-20261030/README.md'],
}
doc_records=[]
for name,phrases in docs.items():
    path=ROOT/name
    text=path.read_text(encoding='utf-8')
    assert all(phrase in text for phrase in phrases),name
    doc_records.append({'path':name,'sha256':sha(path),'current_phase_statement_consistent':True})
result={'status':'approved_for_closure_documentation_commit_and_normal_integration',
 'checked_utc':datetime.now(timezone.utc).isoformat(),'archive':str(ARCHIVE),
 'product_commit':PRODUCT,'gui_checkout':GUI,'head_at_audit':git('rev-parse','HEAD').decode().strip(),
 'copy_count':102,'copy_bytes':4544178,'all_source_and_archive_sha_size_match':True,
 'copy_manifest_sha256':sha(ARCHIVE/'copy-manifest.json'),'copy_verification_sha256':sha(ARCHIVE/'copy-verification.json'),
 'prior_files':2850,'prior_current_and_baseline_git_bytes_match':True,'old_pending_unmodified':True,
 'documentation_only_changed_paths':len(changed),'source_fingerprint':SOURCE,'tests_content_fingerprint':TESTS,
 'original_image_bytes_and_dimensions_verified':14,'auditor_performed_visual_inspection':False,
 'visual_basis':'Root direct native observations; previous independent evidence review approved',
 'host_closed':True,'old_and_final_host_exit_code':0,'post_close_windows_empty':True,
 'relocated_real_fixture_strict_identity':evidence.status,'relocated_generated_files':20,
 'raw_host_fixture_pending_preserved':True,'live_docs':doc_records,'phase_complete':True,
 'actual_integration_performed_by_this_audit':False,'original_evidence_modified':False,
 'audit_script_sha256':sha(Path(__file__))}
with OUTPUT.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps(result,ensure_ascii=False))
