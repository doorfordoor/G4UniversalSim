"""Negative controls for the exact F4 mixed-commit exception; no new-CI pass claim."""
from pathlib import Path
from types import SimpleNamespace
import copy
import importlib.util
import json
import shutil
import tempfile
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import f4_archive_identity as ident
spec=importlib.util.spec_from_file_location('helper',Path(__file__).with_name('prepare-f4-archive.py'))
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
work=Path(tempfile.mkdtemp(prefix='f4-mixed-head-selfcheck-',dir=ROOT/'out/collab'))
source=ROOT/'out/collab/f4-ci-identity-map-a9ad09d-v2'
value=ident.read_json(source/'identity-map.json')
product,ci=value['product_commit'],value['ci_commit']
frozen={key:value[key] for key in ('source_fingerprint','tests_content_fingerprint')}
positive=ident.verify_live(ROOT,source/'identity-map.json',product,ci,frozen)
assert positive['tracked_entries_verified']==11340
assert ident.verify_bundle(source,product,ci,frozen)==positive
plan={'expected_head':product,'ci_expected_head':ci,'frozen':frozen,
      'identity_mapping_path':'identity/identity-map.json','identity_mapping':positive}
archive=work/'archive-proof'
archive.mkdir()
shutil.copytree(source,archive/'identity')
assert ident.verify_plan_identity(archive,plan)==positive
assert ident.expected_report_head(plan,'accepted_windows')==product
assert ident.expected_report_head(plan,'accepted_ci')==ci
assert ident.verify_plan_identity(work,{'expected_head':product})['status']=='same_commit'
checks=[]
def reject(name,function,contains=None):
    try:
        function()
    except (ValueError,FileNotFoundError) as error:
        if contains:
            assert contains in str(error),(name,str(error))
        checks.append({'case':name,'rejected':True,'reason':str(error)})
    else:
        assert False,'negative case accepted: '+name
reject('unmapped_heads',lambda:ident.verify_plan_identity(work,{'expected_head':product,'ci_expected_head':ci,'frozen':frozen}),
       'explicit archived mapping')
reject('same_head_with_hidden_mapping',lambda:ident.verify_plan_identity(archive,{**plan,'ci_expected_head':product}),
       'same-head plan')
reject('swapped_heads',lambda:ident.verify_bundle(source,ci,product,frozen),'map heads')
reject('modified_planned_mapping',lambda:ident.verify_plan_identity(archive,{**plan,'identity_mapping':{}}),'planned mapping')
visible=archive/'visible'
visible.mkdir()
(visible/'identity.json').write_text(json.dumps({'gui_head':ci}),encoding='utf-8')
reject('native_ci_sha_cannot_replace_product_sha',lambda:ident.verify_plan_identity(archive,{**plan,
    'files':[{'category':'visible','archive_path':'visible/identity.json'}]}),'visible GUI head differs')
def candidate(name):
    target=work/name
    shutil.copytree(source,target)
    return target
def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def rebind_ci(folder,tree=None,workflow=None,parent=None):
    """Generate internally consistent hostile Git objects in OUT fixtures only."""
    data=ident.read_json(folder/'identity-map.json')
    entries=tree or ident.read_json(folder/'ci-tree.json')
    if workflow is not None:
        (folder/'workflow-ci.yml').write_bytes(workflow)
        entries[ident.WORKFLOW]='100644 blob '+ident.git_hash('blob',workflow)
        import hashlib
        data['workflow_after_sha256']=hashlib.sha256(workflow).hexdigest()
    newtree=ident.tree_hash(entries)
    raw=(folder/'ci-commit.txt').read_bytes()
    oldtree,_=ident.commit_headers(raw,data['ci_commit'])
    raw=raw.replace(('tree '+oldtree+'\n').encode(),('tree '+newtree+'\n').encode(),1)
    if parent:
        raw=raw.replace(('parent '+product+'\n').encode(),('parent '+parent+'\n').encode(),1)
    newhead=ident.git_hash('commit',raw)
    (folder/'ci-commit.txt').write_bytes(raw)
    data['ci_commit'],data['ci_tree']=newhead,newtree
    write_json(folder/'ci-tree.json',entries)
    write_json(folder/'identity-map.json',data)
    return newhead

bad=candidate('changed-product-entry')
tree=ident.read_json(bad/'ci-tree.json')
tree['gui/requirements.txt']='100644 blob '+ident.git_hash('blob',b'PySide6\n')
head=rebind_ci(bad,tree=tree)
reject('changed_dependency_blob_even_with_same_fingerprints',lambda:ident.verify_bundle(bad,product,head,frozen),'changed product')

bad=candidate('changed-test-entry')
tree=ident.read_json(bad/'ci-tree.json')
tree['gui/smoke_tests/smoke_f4_layout.py']='100644 blob '+ident.git_hash('blob',b'pass\n')
head=rebind_ci(bad,tree=tree)
reject('changed_test_blob_even_with_same_fingerprints',lambda:ident.verify_bundle(bad,product,head,frozen),'changed product')

bad=candidate('alternative-workflow-body')
workflow=(bad/'workflow-ci.yml').read_bytes().replace(b'libegl1 ',b'libegl-mesa0 ')
head=rebind_ci(bad,workflow=workflow)
reject('different_apt_body_same_path',lambda:ident.verify_bundle(bad,product,head,frozen),'exactly the approved')

bad=candidate('changed-workflow-mode')
tree=ident.read_json(bad/'ci-tree.json')
tree[ident.WORKFLOW]=tree[ident.WORKFLOW].replace('100644','100755',1)
head=rebind_ci(bad,tree=tree)
reject('changed_workflow_mode',lambda:ident.verify_bundle(bad,product,head,frozen),'bytes/mode')

bad=candidate('not-direct-parent')
head=rebind_ci(bad,parent='f176d0ed4cea60b7ca5a80ed81017c9404ec1257')
reject('wrong_direct_parent',lambda:ident.verify_bundle(bad,product,head,frozen),'direct single-parent')

bad=candidate('forged-commit-object')
(bad/'product-commit.txt').write_bytes((bad/'product-commit.txt').read_bytes()+b'\n')
reject('modified_raw_product_commit',lambda:ident.verify_bundle(bad,product,ci,frozen),'raw commit object')
reject('wrong_frozen_fingerprint',lambda:ident.verify_bundle(source,product,ci,{**frozen,'source_fingerprint':'0'*64}),'fingerprint mismatch')

bad=candidate('invalid-map-json')
raw=(bad/'identity-map.json').read_text(encoding='utf-8')
(bad/'identity-map.json').write_text(raw.replace('{','{"ci_commit":"bad",',1),encoding='utf-8')
reject('duplicate_map_key',lambda:ident.verify_bundle(bad,product,ci,frozen),'duplicate JSON key')

bad=candidate('missing-proof-member')
(bad/'ci-commit.txt').unlink()
reject('missing_raw_commit_proof',lambda:ident.verify_bundle(bad,product,ci,frozen),'missing or linked')

# This is the original successful F1 CI, used only to exercise strict routing.
# New a9 CI is pending and is never turned into a successful fixture.
old_ci=ROOT/'out/verification/f1-gdml-ci'
old_head='f176d0ed4cea60b7ca5a80ed81017c9404ec1257'
unmapped_args=SimpleNamespace(destination=work/'f4-unmapped-plan',ci_receipt=old_ci/'ci-evidence.json',
    windows_report=helper.BASELINE,baseline_report=helper.BASELINE,expected_head=old_head,ci_head=ci,identity_map=None)
reject('planner_unmapped_ci_flag',lambda:helper.make_plan(unmapped_args),'require --identity-map')
third=helper.history_record(ROOT/'out/verification/f4-ci-7d718d0','ci')
assert third['recorded_status']=='failed' and third['recorded_complete'] is True
assert third['profile_coverage_complete'] is False and len(third['missing_profiles'])==6
assert third['release_accepted'] is False and len(third['reports'])==6
reject('stale_ci_receipt_wrong_head',lambda:helper.engine.validate_ci_topology(old_ci,ci),'summary identity')
copied=work/'historical-ci-negative'
shutil.copytree(old_ci,copied)
report=next(copied.glob('m0-report-windows-latest/**/report.json'))
data=ident.read_json(report)
data['git_head']=ci
write_json(report,data)
reject('one_mixed_old_new_profile',lambda:helper.engine.validate_ci_topology(copied,old_head),'actual report profile/head')

# Existing archive helper remains byte-for-byte intact; only the new F4 copy differs.
assert (ROOT/'out/collab/archive-f1.py').read_bytes()==(ROOT/'out/collab/f4-mixed-head-helper-before/archive-f1.py').read_bytes()
receipt={'status':'passed','positive_mapping':positive,'negative_cases':checks,
         'third_ci_history_retains_failed_complete_collection_incomplete_profiles':True,
         'old_f1_helper_unchanged':True,'new_ci_acceptance_claimed':False,'formal_docs_published':False}
write_json(work/'checks.json',receipt)
print(json.dumps({'status':'passed','negative_cases':len(checks),'receipt':str(work/'checks.json')}))
