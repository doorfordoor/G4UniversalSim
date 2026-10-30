"""Freeze CI-only descendant manifest without changing a running product checkout."""
import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
PRODUCT = '7d718d038a00d89995ea773b4772764116b620c3'
CI = 'a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9'

def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True).stdout

def write(name, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    path = BASE / name
    if path.exists():
        assert path.read_bytes() == raw
    else:
        with path.open('xb') as stream:
            stream.write(raw)

assert git('rev-parse', 'HEAD').decode().strip() == PRODUCT
assert not git('status', '--porcelain').strip()
assert git('rev-parse', CI + '^').decode().strip() == PRODUCT
changes = git('diff', '--name-only', PRODUCT, CI).decode().splitlines()
assert changes == ['.github/workflows/linux-geant4.yml'], changes
numstat = git('diff', '--numstat', PRODUCT, CI).decode().strip()
assert numstat == '6\t0\t.github/workflows/linux-geant4.yml', numstat
spec = importlib.util.spec_from_file_location('f4_ci_frozen_registry', ROOT/'scripts/run_m0_tests.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert not module.untracked_source_files()
manifest = dict(head_sha=CI, source_fingerprint=module.workspace_source_fingerprint(),
                tests_content_fingerprint=module.tests_content_fingerprint(),
                profiles={name: [case.name for case in module.CASES if case.layer == name]
                          for name in ('static', 'gui', 'backend', 'integration')})
old = json.loads((BASE.parent/'f4-ci-7d718d0/frozen-case-manifest.json').read_text(encoding='utf8'))
assert all(manifest[key] == old[key] for key in ('source_fingerprint', 'tests_content_fingerprint', 'profiles'))
assert {key: len(value) for key, value in manifest['profiles'].items()} == dict(static=28, gui=44, backend=59, integration=21)
proof = dict(schema='f4_ci_product_identity_mapping_v1', ci_commit=CI,
             local_product_commit=PRODUCT, ci_parent_commit=PRODUCT,
             changed_files=changes, numstat=numstat,
             diff=git('diff', PRODUCT, CI, '--', changes[0]).decode(),
             workflow_before_sha256=hashlib.sha256(git('show', PRODUCT+':'+changes[0])).hexdigest(),
             workflow_after_sha256=hashlib.sha256(git('show', CI+':'+changes[0])).hexdigest(),
             local_checkout_clean=True, all_other_git_tree_entries_equal=True,
             source_fingerprint=manifest['source_fingerprint'],
             tests_content_fingerprint=manifest['tests_content_fingerprint'],
             method='Full git tree diff proves only six CI workflow lines added; clean product checkout and unchanged runner generate manifests matching the prior product freeze. No report identity is rewritten.',
             boundary='CI reports retain a9ad09d head. Windows/native reports retain 7d718d0 head; byte-equal product/test trees do not make commit IDs equal.')
write('ci-product-identity-map.json', proof)
write('frozen-case-manifest.json', manifest)
print(json.dumps({key: proof[key] for key in ('ci_commit','local_product_commit','changed_files','source_fingerprint','tests_content_fingerprint')}, ensure_ascii=False))
