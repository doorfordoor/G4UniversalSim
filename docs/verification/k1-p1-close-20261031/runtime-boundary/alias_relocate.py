"""Run archived real 8.3 fixture unchanged, then verify a relocated bundle."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'scripts')]
os.environ['K1_WORKSPACE_ROOT'] = str(ROOT)
from g4usim_gui.core import experiment_bundle as bundle
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(bundle.__file__) == '5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a'
script = ROOT / 'out/collab/k1-relocation-candidate/archive-windows-only/test_k1_staging_alias.py'
case = OUT / 'real-alias-relocation'
assert case.absolute().is_relative_to(OUT.resolve())
sys.argv = [str(script), '--evidence-root', str(case)]
runpy.run_path(str(script), run_name='__main__')
receipt = json.loads((case / 'receipt.json').read_bytes())
assert receipt['samefile'] and '~' in receipt['short_root']
assert receipt['export_error'] is None and not receipt['missing_reads']
assert max(row['canonical_utf16_units'] for row in receipt['writer_receipts']) > 260
original = Path(receipt['long_root']) / 'candidate-short'
moved = case / 'relocated' / '中文 moved bundle'
assert original.resolve().is_relative_to(case.resolve())
assert moved.absolute().is_relative_to(case.resolve())
shutil.copytree(original, moved)
before = {str(p.relative_to(original)): sha(p) for p in original.rglob('*') if p.is_file()}
assert before == {str(p.relative_to(moved)): sha(p) for p in moved.rglob('*') if p.is_file()}
hidden_source = case / 'source-inputs-unavailable'
(case / 'source-inputs').rename(hidden_source)
hidden_export = original.with_name('candidate-short-unavailable')
original.rename(hidden_export)
try:
    assert not original.exists() and not (case / 'source-inputs').exists()
    checked = bundle.inspect_bundle(moved)
    loaded = bundle.load_bundle(moved)
    for path in (loaded.project.pathSettings.materials_config, loaded.project.pathSettings.geometry_config):
        assert Path(path).is_file() and Path(path).resolve().is_relative_to(moved.resolve())
    assert checked['manifest']['members']
    assert before == {str(p.relative_to(moved)): sha(p) for p in moved.rglob('*') if p.is_file()}
    output = {'verdict': 'current_r3_real_8dot3_export_and_relocation_passed',
              'product_path': str(Path(bundle.__file__).resolve()), 'product_sha256': sha(bundle.__file__),
              'actual_alias_receipt': receipt, 'old_sources_and_export_unavailable_during_load': True,
              'moved': str(moved), 'member_sha256': before, 'backend': 'not_started'}
    (case / 'relocation-receipt.json').write_bytes((json.dumps(output, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps(output, ensure_ascii=False), flush=True)
finally:
    assert hidden_source.resolve().is_relative_to(case.resolve())
    assert hidden_export.resolve().is_relative_to(case.resolve())
    hidden_source.rename(case / 'source-inputs')
    hidden_export.rename(original)
