"""Portable filesystem/exporter regression, without backend execution.

The controlled equivalent spelling calls the real exporter, not a second
containment implementation. Actual symlink/junction inputs remain rejected.
Windows additionally uses an actual 8.3 alias when available, never a fake one.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(os.environ.get('K1_WORKSPACE_ROOT', Path(__file__).resolve().parents[1]))
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'scripts')]


def exercise(root):
    from test_k1_bundle import fixture
    from g4usim_gui.core import experiment_bundle as bundle
    from g4usim_gui.writers import package_writer
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    snapshot = fixture(root / 'source-inputs', generated=True)
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    source_hashes = {str(p): digest(p) for p in (root / 'source-inputs').rglob('*') if p.is_file()}
    receipt = {'platform': sys.platform, 'backend': 'not_started', 'cases': [],
               'original_CI_complete_temp_path': 'not archived; exact cause unknown'}
    def persist():
        (root / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    control = bundle.export_bundle(snapshot, root / 'control')
    assert bundle.inspect_bundle(control['path'])['manifest']['members']
    writer_receipts = []
    real_writer = package_writer.create_run_package
    def observed_writer(**kwargs):
        result = real_writer(**kwargs)
        main = Path(result[0].main_ini_path)
        writer_receipts.append({'path': str(main), 'exists_at_return': main.is_file()})
        return result
    # A real existing parent_navigation/.. spells the actual staging directory.
    # All link guards stay active; only mkdtemp's returned spelling is controlled.
    real_mkdtemp = tempfile.mkdtemp
    navigation = root / 'parent_navigation'
    navigation.mkdir()
    spellings = []
    def equivalent_staging(*args, **kwargs):
        actual = Path(real_mkdtemp(*args, **kwargs))
        lexical = actual.parent / navigation.name / '..' / actual.name
        assert actual.resolve().is_relative_to(root)
        assert lexical.is_dir() and os.path.samefile(actual, lexical)
        assert lexical != actual.resolve()
        spellings.append({'lexical': str(lexical), 'canonical': str(actual.resolve()), 'samefile': True})
        return str(lexical)
    failure = None
    with patch.object(bundle.tempfile, 'mkdtemp', side_effect=equivalent_staging), \
            patch.object(package_writer, 'create_run_package', side_effect=observed_writer):
        try:
            result = bundle.export_bundle(snapshot, root / 'equivalent-staging')
        except OSError as error:
            failure = str(error)
    receipt['cases'].append({'kind': 'controlled_real_parent_navigation_spelling',
        'spelling': spellings, 'writer_receipts': writer_receipts, 'export_error': failure,
        'scope': 'portable controlled regression, not the original Linux/CI cause'})
    persist()
    assert writer_receipts and all(row['exists_at_return'] for row in writer_receipts)
    assert failure is None, ('Equivalent staging must not reread deliberately deleted writer inputs', failure)
    assert bundle.inspect_bundle(result['path'])['manifest']['members']
    # Static real link fixture: current policy rejects linked input parents.
    # This is not an in-flight mutation, race or guard bypass.
    link_target = root / 'link-target'
    link_target.mkdir()
    linked = root / 'linked-parent'
    assert link_target.resolve().is_relative_to(root)
    short_root = None
    if sys.platform == 'win32':
        get_short = ctypes.windll.kernel32.GetShortPathNameW
        get_short.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        get_short.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(32768)
        count = get_short(str(link_target), buffer, len(buffer))
        if count and count < len(buffer) and '~' in buffer.value:
            short_root = Path(buffer.value)
            assert os.path.samefile(short_root, link_target)
        junction = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(linked), str(link_target)],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert junction.returncode == 0, junction.stdout.decode(errors='replace')
        link_kind = 'real_windows_directory_junction'
    else:
        linked.symlink_to(link_target, target_is_directory=True)
        assert linked.is_symlink()
        link_kind = 'real_posix_directory_symlink'
    try:
        assert os.path.samefile(linked, link_target)
        assert linked.resolve() == link_target.resolve()
        error = None
        try:
            bundle.export_bundle(snapshot, linked / 'must-not-publish')
        except ValueError as rejected:
            error = str(rejected)
        assert error and ('linked path' in error or 'reparse point' in error), error
        assert not (link_target / 'must-not-publish').exists()
        receipt['cases'].append({'kind': link_kind, 'samefile': True, 'error': error,
                                 'expected_behavior': 'refused_by_existing_link_policy'})
    finally:
        # Remove only the link itself before the owned temp root is cleaned.
        if sys.platform == 'win32':
            linked.rmdir()
        else:
            linked.unlink()
    if short_root is not None:
        exported = bundle.export_bundle(snapshot, short_root / 'actual-8dot3-export')
        assert bundle.inspect_bundle(exported['path'])['manifest']['members']
        receipt['cases'].append({'kind': 'real_windows_8dot3_alias', 'samefile': True,
                                 'path': str(short_root), 'export': 'passed'})
    elif sys.platform == 'win32':
        receipt['windows_8dot3'] = 'unavailable; real junction refusal covered, not claimed as 8.3'
    assert {path: digest(path) for path in source_hashes} == source_hashes
    persist()
    print(json.dumps({'platform': sys.platform, 'cases': [r['kind'] for r in receipt['cases']],
                      'backend': 'not_started'}, ensure_ascii=False), flush=True)
    print('test_k1_staging_alias: OK; portable filesystem/exporter regression, links remain refused')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-root')
    args = parser.parse_args()
    if args.evidence_root:
        exercise(args.evidence_root)
    elif os.environ.get('G4USIM_TEST_EVIDENCE_DIR'):
        parent = Path(os.environ['G4USIM_TEST_EVIDENCE_DIR']).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        exercise(parent / ('k1-staging-' + uuid4().hex))
    else:
        with tempfile.TemporaryDirectory(prefix='k1-staging-') as directory:
            exercise(Path(directory).resolve() / 'evidence')


if __name__ == '__main__':
    main()
