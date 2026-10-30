"""Read-only Git identity proof for the explicitly approved Linux apt-only child."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
PRODUCT='7d718d038a00d89995ea773b4772764116b620c3'
CI='a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9'
FILE='.github/workflows/linux-geant4.yml'
out=ROOT/'out/collab/f4-ci-identity-map-a9ad09d'
assert not out.exists()
def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)
def tree(commit):
    result={}
    for line in git('ls-tree','-r','-z',commit).split(b'\0'):
        if not line:
            continue
        metadata,name=line.split(b'\t',1)
        result[name.decode('utf-8')]=metadata.decode('ascii')
    return result
left,right=tree(PRODUCT),tree(CI)
assert git('rev-list','--parents','-n','1',CI).decode().split()==[CI,PRODUCT]
assert set(left)==set(right)
changed=[name for name in left if left[name]!=right[name]]
assert changed==[FILE],changed
before,after=git('show',PRODUCT+':'+FILE),git('show',CI+':'+FILE)
addition=(b'      - name: Install Linux GUI runtime libraries\n'
          b'        run: |\n'
          b'          sudo apt-get update\n'
          b'          sudo apt-get install --yes --no-install-recommends \\\n'
          b'            libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1\n\n')
anchor=b'      - name: Install micromamba\n'
assert before.count(anchor)==1
assert after==before.replace(anchor,addition+anchor)
assert b'sudo apt-get update\n          sudo apt-get install --yes --no-install-recommends \\\n            libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1' in git('show',PRODUCT+':.github/workflows/m0-static-gui.yml')
frozen=json.loads((ROOT/'out/verification/f4-ci-7d718d0/frozen-case-manifest.json').read_text(encoding='utf-8'))
assert frozen['head_sha']==PRODUCT
payload={'schema':'g4usim_product_ci_identity_map_v1','created_utc':datetime.now(timezone.utc).isoformat(),
    'product_commit':PRODUCT,'ci_commit':CI,'direct_parent_verified':True,
    'product_tree':git('rev-parse',PRODUCT+'^{tree}').decode().strip(),
    'ci_tree':git('rev-parse',CI+'^{tree}').decode().strip(),'changed_files':changed,
    'all_other_tracked_entries_identical':True,'tracked_entries_checked':len(left),
    'exact_approved_addition_verified':True,'no_test_or_gate_removal':True,
    'runtime_install_matches_m0':True,'source_fingerprint':frozen['source_fingerprint'],
    'tests_content_fingerprint':frozen['tests_content_fingerprint'],
    'fingerprint_equivalence_basis':'Every tracked blob/mode is identical except the exact six-line workflow addition; runner fingerprint inputs are unchanged',
    'workflow_before_sha256':hashlib.sha256(before).hexdigest(),
    'workflow_after_sha256':hashlib.sha256(after).hexdigest(),
    'local_head_at_review':git('rev-parse','HEAD').decode().strip(),
    'local_status_at_review':git('status','--porcelain').decode(),
    'acceptance':'identity mapping only; Windows/native/new CI completion must be separately verified',
    'push_status':'not inferred from Git objects; retain original push/run receipts separately'}
out.mkdir()
(out/'workflow-product.yml').write_bytes(before)
(out/'workflow-ci.yml').write_bytes(after)
(out/'git-diff.patch').write_bytes(git('diff','--full-index',PRODUCT,CI))
(out/'product-tree.json').write_text(json.dumps(left,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'ci-tree.json').write_text(json.dumps(right,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'identity-map.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'receipt':str(out/'identity-map.json'),'entries':len(left),'status':'identity_equivalence_verified_not_stage_acceptance'}))
