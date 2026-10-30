"""Exact Git-bound proof for the approved Linux-runtime-only F4 CI child.

The archive proof is self-contained: raw commit objects bind full recursive tree
listings, and both workflow byte snapshots bind their Git blob IDs. No changed
product/test entry or alternative workflow edit is accepted by this exception.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

WORKFLOW='.github/workflows/linux-geant4.yml'
M0='.github/workflows/m0-static-gui.yml'
ADDITION=(b'      - name: Install Linux GUI runtime libraries\n'
          b'        run: |\n'
          b'          sudo apt-get update\n'
          b'          sudo apt-get install --yes --no-install-recommends \\\n'
          b'            libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1\n\n')
ANCHOR=b'      - name: Install micromamba\n'
FILES=('identity-map.json','product-tree.json','ci-tree.json','workflow-product.yml',
       'workflow-ci.yml','git-diff.patch','product-commit.txt','ci-commit.txt')

def need(condition,message):
    if not condition:
        raise ValueError('F4 identity mapping: '+message)

def unique(pairs):
    result={}
    for key,value in pairs:
        need(key not in result,'duplicate JSON key')
        result[key]=value
    return result

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique)

def git_hash(kind,raw):
    return hashlib.sha1(kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def tree_hash(entries):
    """Reconstruct SHA-1 Git trees from complete recursive ls-tree leaves."""
    need(isinstance(entries,dict) and entries,'empty/malformed tree')
    root={}
    for name,metadata in entries.items():
        need(isinstance(name,str) and '\\' not in name and '\0' not in name,'invalid Git path')
        path=PurePosixPath(name)
        need(not path.is_absolute() and path.as_posix()==name and all(p not in ('','.','..') for p in path.parts),'noncanonical Git path')
        need(isinstance(metadata,str),'invalid tree metadata')
        fields=metadata.split(' ')
        need(len(fields)==3,'invalid mode/type/object tuple')
        mode,kind,object_id=fields
        need((mode,kind) in {('100644','blob'),('100755','blob'),('120000','blob'),('160000','commit')} and
             re.fullmatch('[0-9a-f]{40}',object_id) is not None,'unsupported tree leaf')
        node=root
        for part in path.parts[:-1]:
            need(part not in node or isinstance(node[part],dict),'file/directory collision')
            node=node.setdefault(part,{})
        need(path.name not in node,'duplicate tree entry')
        node[path.name]=(mode,object_id)
    def encode(node):
        records=[]
        for name,item in node.items():
            folder=isinstance(item,dict)
            mode,object_id=('40000',encode(item)) if folder else item
            records.append((name.encode('utf-8')+(b'/' if folder else b''),
                            mode.encode()+b' '+name.encode('utf-8')+b'\0'+bytes.fromhex(object_id)))
        return git_hash('tree',b''.join(raw for _,raw in sorted(records)))
    return encode(root)

def commit_headers(raw,expected):
    need(git_hash('commit',raw)==expected,'raw commit object does not match declared SHA')
    headers=raw.split(b'\n\n',1)[0].splitlines()
    trees=[line[5:].decode('ascii') for line in headers if line.startswith(b'tree ')]
    parents=[line[7:].decode('ascii') for line in headers if line.startswith(b'parent ')]
    need(len(trees)==1 and re.fullmatch('[0-9a-f]{40}',trees[0]) is not None,'invalid commit tree header')
    return trees[0],parents

def verify_bundle(folder,product,ci,fingerprints):
    folder=Path(folder)
    need(product!=ci,'a mixed-head mapping is unnecessary for same-head evidence')
    for value in (product,ci):
        need(isinstance(value,str) and re.fullmatch('[0-9a-f]{40}',value) is not None,'full SHA-1 commit required')
    for name in FILES:
        path=folder/name
        need(path.is_file() and not path.is_symlink(),'missing or linked proof member '+name)
    value=read_json(folder/'identity-map.json')
    need(value.get('schema')=='g4usim_product_ci_identity_map_v1','unknown map schema')
    need(value.get('product_commit')==product and value.get('ci_commit')==ci,'map heads differ from accepted identities')
    left=read_json(folder/'product-tree.json')
    right=read_json(folder/'ci-tree.json')
    product_tree,_=commit_headers((folder/'product-commit.txt').read_bytes(),product)
    ci_tree,parents=commit_headers((folder/'ci-commit.txt').read_bytes(),ci)
    need(parents==[product],'CI must be the direct single-parent child of the product')
    need(tree_hash(left)==product_tree==value.get('product_tree'),'product tree is not bound to its commit')
    need(tree_hash(right)==ci_tree==value.get('ci_tree'),'CI tree is not bound to its commit')
    need(set(left)==set(right),'added/deleted tracked entry refused')
    changed=sorted(name for name in left if left[name]!=right[name])
    need(changed==[WORKFLOW] and value.get('changed_files')==changed,'changed product or extra workflow entry refused')
    need(value.get('tracked_entries_checked')==len(left),'tree entry count mismatch')
    for key in ('direct_parent_verified','all_other_tracked_entries_identical','exact_approved_addition_verified','no_test_or_gate_removal'):
        need(value.get(key) is True,'missing verified property '+key)
    before=(folder/'workflow-product.yml').read_bytes()
    after=(folder/'workflow-ci.yml').read_bytes()
    for entries,raw,key in ((left,before,'workflow_before_sha256'),(right,after,'workflow_after_sha256')):
        need(entries[WORKFLOW]=='100644 blob '+git_hash('blob',raw),'workflow bytes/mode not bound to Git tree')
        need(hashlib.sha256(raw).hexdigest()==value.get(key),'workflow SHA256 mismatch')
    need(before.count(ANCHOR)==1 and after==before.replace(ANCHOR,ADDITION+ANCHOR),
         'CI workflow must contain exactly the approved six-line apt insertion')
    for key in ('source_fingerprint','tests_content_fingerprint'):
        expected=fingerprints.get(key)
        need(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected) is not None,'missing frozen fingerprint')
        need(value.get(key)==expected,'mapped/frozen fingerprint mismatch: '+key)
    return {'status':'verified_exact_linux_runtime_child','product_commit':product,'ci_commit':ci,
            'tracked_entries_verified':len(left),'changed_files':changed,
            'source_fingerprint':fingerprints['source_fingerprint'],
            'tests_content_fingerprint':fingerprints['tests_content_fingerprint'],
            'phase_acceptance':False}

def verify_live(repo,mapping,product,ci,fingerprints):
    """Check the archived proof and re-bind it to the actual repository objects."""
    mapping=Path(mapping)
    need(mapping.name=='identity-map.json','expected exact map filename')
    result=verify_bundle(mapping.parent,product,ci,fingerprints)
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=repo)
    for head,label in ((product,'product'),(ci,'ci')):
        need(git('cat-file','commit',head)==(mapping.parent/(label+'-commit.txt')).read_bytes(),
             'raw commit proof differs from repository object')
        entries={}
        for line in git('ls-tree','-r','-z',head).split(b'\0'):
            if line:
                metadata,name=line.split(b'\t',1)
                entries[name.decode('utf-8')]=metadata.decode('ascii')
        need(entries==read_json(mapping.parent/(label+'-tree.json')),'full Git tree differs from proof')
    expected=git('diff','--full-index',product,ci)
    need(expected==(mapping.parent/'git-diff.patch').read_bytes(),'Git diff proof differs from actual commits')
    # Keep the independent M0 match factual, but it does not replace new CI.
    install=ADDITION.split(b'          sudo apt-get update',1)[1].rstrip()+b'\n'
    need(install.rstrip() in git('show',product+':'+M0),'approved runtime command differs from existing M0')
    return result

def expected_report_head(plan,category):
    if category=='accepted_windows':
        return plan['expected_head']
    if category=='accepted_ci':
        return plan.get('ci_expected_head',plan['expected_head'])
    raise ValueError('Only accepted Windows/CI reports have a release head')

def verify_plan_identity(folder,plan):
    product=plan['expected_head']
    ci=plan.get('ci_expected_head',product)
    relative=plan.get('identity_mapping_path')
    for item in plan.get('files',[]):
        if item['category']=='visible' and PurePosixPath(item['archive_path']).name=='identity.json':
            visible=read_json(Path(folder)/item['archive_path'])
            if 'gui_head' in visible:
                need(visible['gui_head']==product,'accepted visible GUI head differs from product; CI mapping does not relabel native observations')
    if product==ci:
        need(relative is None and not plan.get('identity_mapping'),'same-head plan must not hide a mapping')
        return {'status':'same_commit','product_commit':product,'ci_commit':ci}
    need(relative=='identity/identity-map.json','mixed heads require an explicit archived mapping')
    result=verify_bundle(Path(folder)/'identity',product,ci,plan['frozen'])
    need(plan.get('identity_mapping')==result,'planned mapping differs from archived proof')
    return result
