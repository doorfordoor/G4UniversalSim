"""Owned Windows fixtures for independent r2/r3 resource publication review."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'scripts')]
parser = argparse.ArgumentParser()
parser.add_argument('--target', choices=('r2', 'r3'), required=True)
parser.add_argument('--change', choices=('junction', 'content'), default='junction')
args = parser.parse_args()
assert sys.platform == 'win32'
import g4usim_gui.core
product = (ROOT / 'out/collab/k1-relocation-candidate/archive-r2/experiment_bundle.py'
           if args.target == 'r2' else ROOT / 'gui/g4usim_gui/core/experiment_bundle.py')
expected = {'r2': '34db09d96260841411dc92306f4eab438d75792a4f74abacde3322c10b3d66c2',
            'r3': '5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(product) == expected[args.target]
spec = importlib.util.spec_from_file_location('g4usim_gui.core.experiment_bundle', product)
bundle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bundle
spec.loader.exec_module(bundle)
g4usim_gui.core.experiment_bundle = bundle
from test_k1_bundle import fixture
root = OUT / ('late-' + args.target + '-' + args.change)
assert root.absolute().is_relative_to(OUT.resolve())
root.mkdir(exist_ok=False)
source, backup, destination = root / 'external-source', root / 'external-source-original', root / 'published'
snapshot = fixture(source, generated=False)
before = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
original_material = (source / 'materials.ini').read_bytes()
observations = []
real_inspect = bundle.inspect_bundle

def inspected_change(staging):
    result = real_inspect(staging)
    staging = Path(staging)
    assert staging.resolve().is_relative_to(root.resolve())
    assert source.resolve().is_relative_to(root.resolve())
    assert backup.absolute().is_relative_to(root.resolve())
    if args.change == 'junction':
        source.rename(backup)
        target = staging / 'resources'
        assert target.resolve().is_relative_to(root.resolve())
        linked = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(source), str(target)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        assert linked.returncode == 0, linked.stdout.decode(errors='replace')
        assert source.lstat().st_file_attributes & 0x400
        external = source / 'materials.ini'
        guard_error = None
        try:
            bundle._no_links(external)
        except ValueError as error:
            guard_error = str(error)
        assert guard_error and 'reparse' in guard_error.lower()
        assert external.resolve().is_relative_to(staging.resolve())
        observations.append({'lexical_external': str(external), 'canonical_after_change': str(external.resolve()),
                             'inside_staging_after_resolve': True, 'direct_guard_error': guard_error,
                             'stage': str(staging), 'real_ntfs_junction': True})
    else:
        (source / 'materials.ini').write_bytes(original_material + b'\n# controlled changed source\n')
        assert sha(source / 'materials.ini') != before['materials.ini']
        observations.append({'changed': str(source / 'materials.ini'), 'stage': str(staging)})
    return result

error = None
report = None
try:
    with patch.object(bundle, 'inspect_bundle', side_effect=inspected_change):
        try:
            result = bundle.export_bundle(snapshot, destination)
        except (ValueError, OSError) as failure:
            error = str(failure)
    assert len(observations) == 1
    report = {'target': args.target, 'change': args.change, 'product_path': str(Path(bundle.__file__).resolve()),
              'product_sha256': sha(bundle.__file__), 'error': error,
              'published': destination.is_dir(), 'observations': observations, 'backend': 'not_started'}
    if args.target == 'r2':
        assert args.change == 'junction'
        assert error is None
        assert destination.is_dir()
        assert real_inspect(destination)['manifest']['members']
        report['verdict'] = 'reproduced_old_r2_regression_published'
    else:
        assert error
        assert ('reparse' in error.lower() if args.change == 'junction' else 'Resource changed before publication' in error)
        assert not os.path.lexists(destination)
        assert not Path(observations[0]['stage']).exists()
        report['verdict'] = 'current_r3_correctly_refused_without_publication'
finally:
    if args.change == 'junction' and backup.exists():
        assert source.absolute().is_relative_to(root.resolve())
        assert source.lstat().st_file_attributes & 0x400
        os.rmdir(source)
        assert backup.resolve().is_relative_to(root.resolve())
        backup.rename(source)
    elif args.change == 'content':
        (source / 'materials.ini').write_bytes(original_material)
    after = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
    assert before == after
    assert not source.lstat().st_file_attributes & 0x400
    if report is not None:
        report['source_sha256_before'] = before
        report['source_sha256_after'] = after
        report['owned_link_removed_source_restored'] = True
        (root / 'receipt.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps(report, ensure_ascii=False), flush=True)
