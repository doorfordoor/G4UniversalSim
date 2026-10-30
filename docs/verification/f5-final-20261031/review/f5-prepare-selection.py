"""Prepare explicit raw-byte archive selection after all final receipts exist."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
NATIVE_HEAD = '5d56187392a2e7b888d5ce13f8da05a295cba6d4'
sys.path.insert(0, str(ROOT / 'scripts'))
from check_report_evidence import validate_report

# Use the independently checked path rules before resolving any alias.
copy_path = ROOT / 'out/collab/f5-copy-evidence.py'
assert hashlib.sha256(copy_path.read_bytes()).hexdigest() == '672cedbaad6a7715eb8afd266482b1e889db1118f32d041be54662347f219dbc'
copy_spec = importlib.util.spec_from_file_location('f5_copy_paths', copy_path)
copy_paths = importlib.util.module_from_spec(copy_spec)
copy_spec.loader.exec_module(copy_paths)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    HEAD = args.head
    short = HEAD[:7]
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == HEAD
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    reports = list((ROOT / f'out/verification/f5-release-windows-{short}').rglob('report.json'))
    assert len(reports) == 1, 'Need exactly one completed final Windows report'
    report_path = reports[0]
    report = read(report_path)
    assert report['git_head'] == HEAD and report['git_dirty'] is False
    baseline_path = ROOT / 'docs/verification/f4-final-20261030/windows/final-1/report.json'
    validate_report(report, report_path=report_path, baseline=read(baseline_path))
    assert len(report['results']) == 160
    native = ROOT / 'out/collab/f5-native-5d56187-1'
    assert read(native / 'identity.json')['gui_head'] == NATIVE_HEAD
    assert read(native / 'launcher.json')['actual_process_exit'] == 0
    mapping_path = ROOT / f'out/collab/f5-identity-map-{short}.json'
    mapping = read(mapping_path)
    assert mapping['status'] == 'passed' and mapping['automated_matrix_commit'] == HEAD
    assert mapping['native_observed_commit'] == NATIVE_HEAD
    assert digest(native / 'identity.json') == mapping['native_identity_sha256']
    assert digest(native / 'gui-file-hashes.json') == mapping['native_gui_hashes_sha256']
    independent_path = ROOT / f'out/collab/f5-identity-map-{short}-independent.json'
    independent = read(independent_path)
    assert independent['status'] == 'passed' and independent['new_candidate'] == HEAD
    assert independent['mapped_receipt_sha256'] == digest(mapping_path)
    ci = ROOT / f'out/verification/f5-ci-{short}'
    assert (ci / 'ci-evidence.json').exists(), 'Need final official CI audit'
    frozen = read(ci / 'frozen-case-manifest.json')
    assert report['source_fingerprint'] == frozen['source_fingerprint']
    assert report['tests_content_fingerprint'] == frozen['tests_content_fingerprint']
    ci_audit = read(ci / 'evidence-integrity-audit.json')
    assert ci_audit['head_sha'] == HEAD and ci_audit['status'] == 'passed'
    assert ci_audit['evidence_collection_complete'] is True and not ci_audit['problems']
    assert ci_audit['report_count'] == 12 and ci_audit['case_executions'] == 478
    assert digest(ci / 'archive-file-manifest.json') == '05256f15daa258fde451931ab579fbd3dd58360c6ce306ef9abe8004c3a2a723'
    files = []
    destinations = set()

    def add(source, target, expected=None, size=None):
        source = copy_paths.within_repository(source)
        assert source.is_file()
        sha = digest(source)
        count = source.stat().st_size
        if expected is not None:
            assert sha == expected and count == size, f'Pinned evidence changed: {source}'
        if target.endswith('.md'):
            target += '.txt'  # historic links are historical data, not current docs
        assert target.casefold() not in destinations, target
        destinations.add(target.casefold())
        files.append({'source': source.relative_to(ROOT).as_posix(), 'destination': target,
                      'sha256_raw': sha, 'bytes': count})

    def tree(source, prefix):
        source = copy_paths.within_repository(source)
        assert source.is_dir(), f'Missing required evidence directory: {source}'
        count_before = len(files)
        for p in sorted(source.rglob('*')):
            copy_paths.within_repository(p)
            if p.is_file():
                assert not p.is_symlink()
                if '__pycache__' in p.parts or p.suffix == '.pyc':
                    continue
                add(p, prefix + '/' + p.relative_to(source).as_posix())
        assert len(files) > count_before, f'Empty required evidence directory: {source}'

    def pinned_tree(source, prefix, manifest_path, excluded=()):
        source = copy_paths.within_repository(source)
        assert source.is_dir(), source
        manifest = read(manifest_path)
        rows = manifest['files']
        assert rows, manifest_path
        names = [row['path'] for row in rows]
        assert len(names) == len(set(names)), 'Duplicate pinned source paths'
        actual = set()
        for path in source.rglob('*'):
            copy_paths.within_repository(path)
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                actual.add(path.relative_to(source).as_posix())
        assert actual == set(names) | set(excluded), (source, actual ^ (set(names) | set(excluded)))
        for row in rows:
            safe_relative = copy_paths.relative_path(row['path'])
            add(source / safe_relative, prefix + '/' + row['path'], row['sha256'], row['bytes'])

    tree(report_path.parent, 'windows/final-1')
    pinned_tree(ci, 'ci', ci / 'archive-file-manifest.json', ('archive-file-manifest.json',))
    add(ci / 'archive-file-manifest.json', 'ci/archive-file-manifest.json')
    native_manifest_path = ROOT / 'out/collab/f5-native-final-file-manifest.json'
    native_manifest = read(native_manifest_path)
    assert digest(native_manifest_path) == '948ada6fb125f4aa80d88bf53710541a28784b26bed138104eb834c8c3f764cb'
    assert native_manifest['mapped_candidate'] == HEAD
    assert native_manifest['verification']['independent_mapping_receipt_sha256'] == digest(independent_path)
    pinned_tree(native, 'visible/final-1', native_manifest_path)
    add(native_manifest_path, 'visible/native-file-manifest.json')
    tree(baseline_path.parent, 'baseline/f4-windows')
    inventory = read(ROOT / 'out/collab/f5-history-copy-preflight-20261031.json')
    original_copyable = read(ROOT / 'out/collab/f5-evidence-copyable.json')
    assert digest(ROOT / original_copyable['inventory_path']) == original_copyable['inventory_sha256_raw']
    for row in inventory['verified_files']:
        add(ROOT / row['path'], 'history/' + row['path'], row['sha256_raw'], row['bytes'])
    for item in inventory['changed_or_missing']:
        row = item['original_entry']
        # Keep the changed current receipt as a separately named version. The
        # original pin remains recorded as unavailable in the supplement.
        if item['current'] is not None:
            add(ROOT / row['path'], 'history/current-receipts/' + Path(row['path']).name,
                item['current']['sha256_raw'], item['current']['bytes'])
    old_ci = ROOT / 'out/verification/f5-ci-5d56187'
    old_manifest = read(old_ci / 'archive-file-manifest.json')
    for row in old_manifest['files']:
        add(old_ci / row['path'], 'history/ci-attempt-5d56187/' + row['path'], row['sha256'], row['bytes'])
    add(old_ci / 'archive-file-manifest.json', 'history/ci-attempt-5d56187/archive-file-manifest.json')
    tree(ROOT / 'out/verification/f5-release-windows-5d56187', 'history/windows-5d56187')
    for folder in ('f5-ddd-stable-dev', 'f5-ddd-stable-r2-dev', 'f5-ddd-stable-r3-dev', 'f5-runner-evidence-dev'):
        tree(ROOT / 'out/verification' / folder, 'history/' + folder)
    for name in ('f5-evidence-inventory.json', 'f5-evidence-copyable.json',
                 'f5-copy-evidence.py', 'f5-copy-evidence-selfcheck-r2.json',
                 'f5-native-5d56187-independent-review.md', 'f5-native-5d56187-independent-integrity.json',
                 'f5-fingerprint-cache-independent-review.md', 'f5-fingerprint-cache-independent.log',
                 'f5-f1-async-independent-after-cache-v3.log', 'f5-copy-evidence-independent-review.md',
                 'f5-copy-evidence-independent-recheck-r2.md', 'f5-copy-evidence-independent-recheck-r2.json',
                 'f5-history-copy-preflight-20261031.json', 'f5-create-identity-map.py',
                 'f5-ddd-baseline-diagnosis.md', 'f5-ddd-stable-checkpoint.md',
                 'f5-ddd-stable-evidence-check.json', 'f5-windows-5d56187-baseline-gate.log',
                 'f5-ddd-stable-r3-handoff.md', 'f5-ddd-independent-review.md',
                 'f5-ddd-independent-review.json', 'f5-ddd-independent-recheck-r3.md',
                 'f5-ddd-independent-recheck-r3.json', 'f5-native-identity-mapping-independent-review.md',
                 'f5-identity-map-ui-review.md', 'f5-identity-map-ui-review-current.json',
                 'f5-prepare-selection-ui-review.md', 'f5-selection-ui-readonly-probe.json',
                 'f5-prepare-selection-ui-recheck-r3.md', 'f5-selection-ui-recheck-r3.json',
                 'f5-prepare-selection-reviewed-r3.py', 'f5-selection-final-addendum.md',
                 'f5-close-profile-independent-after-cache-v3.log', 'f5-prepare-selection.py',
                 'f5-configure-5d56187.log', 'f5-build-5d56187.log', 'f5-windows-5d56187.log'):
        add(ROOT / 'out/collab' / name, 'review/' + name)
    add(mapping_path, 'identity/identity-map.json')
    add(independent_path, 'identity/identity-map-independent.json')
    add(ROOT / f'out/collab/f5-identity-map-{short}-independent.md', 'identity/identity-map-independent.md')
    for name in (f'f5-configure-{short}.log', f'f5-build-{short}.log', f'f5-windows-{short}.log'):
        add(ROOT / 'out/collab' / name, 'review/' + name)
    add(ROOT / 'out/collab/f5-deepseek-design.json', 'design/design-response.json')
    add(ROOT / 'docs/collab/outbox/20261030-2155-deepseek-f5-design.md', 'design/design-receipt.md')
    output = ROOT / 'out/collab/f5-final-selection.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(files, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'files': len(files), 'bytes': sum(f['bytes'] for f in files),
                      'windows_report': str(report_path), 'selection': str(output)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
