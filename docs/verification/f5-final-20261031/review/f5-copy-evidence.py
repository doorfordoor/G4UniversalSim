"""Copy an explicit evidence list, preserving bytes. This is not stage acceptance.

Default only verifies a plan. --execute writes an exclusive new root under
repo/out, never tracked final documents. No Git, network, UI or report gates.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat

ROOT = Path(__file__).resolve().parents[2]
INCOMPLETE = 'copy-incomplete.json'
RECEIPT = 'copy-receipt.json'


def validate_component(component):
    # Apply Windows rules before any filesystem access, including on POSIX.
    # ADS syntax is not covered by PureWindowsPath.is_reserved().
    if (not component or component in ('.', '..')
            or component.endswith(('.', ' '))
            or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in component)
            or PureWindowsPath(component).is_reserved()):
        raise ValueError('Unsafe Windows path component: ' + repr(component))


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value or PureWindowsPath(value).drive:
        raise ValueError('Expected a safe repository-relative POSIX path')
    if value.startswith('/') or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('Absolute paths, empty components and traversal are refused')
    for component in value.split('/'):
        validate_component(component)
    return Path(*value.split('/'))


def within_repository(path):
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('Traversal in archive root or source path is refused')
    if not path.is_relative_to(ROOT):
        raise ValueError('Path is outside the repository')
    # Absolute archive roots skip relative_path; validate their components too.
    # The fixed repository anchor (including its drive colon) is not a name.
    for component in path.relative_to(ROOT).parts:
        validate_component(component)
    for component in (ROOT, *[ROOT.joinpath(*path.relative_to(ROOT).parts[:i])
                              for i in range(1, len(path.relative_to(ROOT).parts) + 1)]):
        if os.path.lexists(component):
            info = component.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
                raise ValueError('Linked or reparse paths are refused')
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Resolved path escapes repository')
    return path


def digest_file(path):
    digest = hashlib.sha256()
    count = 0
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
            count += len(chunk)
    return digest.hexdigest(), count


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def write_file(path, raw, *, exclusive=True):
    with path.open('xb' if exclusive else 'wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def make_plan(rows, destination):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Manifest must be a non-empty list')
    destination = Path(destination)
    if not destination.is_absolute():
        destination = ROOT / relative_path(str(destination))
    destination = within_repository(destination)
    if not destination.is_relative_to(ROOT / 'out') or destination == ROOT / 'out':
        raise ValueError('Copy destination must be a new directory beneath repo/out')
    if os.path.lexists(destination):
        raise FileExistsError('Destination already exists; nothing was overwritten')
    selected = []
    targets = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'source', 'destination', 'sha256_raw', 'bytes'}:
            raise ValueError('Each file needs source, destination, sha256_raw and bytes')
        source = within_repository(ROOT / relative_path(row['source']))
        target_relative = relative_path(row['destination'])
        if target_relative.parts[0].casefold() in {INCOMPLETE, RECEIPT}:
            raise ValueError('Reserved receipt name')
        target_key = row['destination'].casefold()
        if target_key in targets or any(target_key.startswith(previous + '/') or previous.startswith(target_key + '/') for previous in targets):
            raise ValueError('Duplicate or file/directory-conflicting destination')
        targets.add(target_key)
        expected = row['sha256_raw']
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Expected lowercase SHA-256 of raw bytes')
        if type(row['bytes']) is not int or row['bytes'] < 0 or not source.is_file():
            raise ValueError('Invalid size or source is not a regular file')
        if digest_file(source) != (expected, row['bytes']):
            raise ValueError('Source digest/byte-count mismatch: ' + row['source'])
        selected.append(dict(row))
    return {'destination': str(destination), 'files': selected, 'phase_complete': False}


def execute(plan):
    # Repeat every source check immediately before reserving the new directory.
    plan = make_plan(plan['files'], plan['destination'])
    target = Path(plan['destination'])
    target.parent.mkdir(parents=True, exist_ok=True)
    within_repository(target.parent)
    target.mkdir()  # exclusive ownership, no automatic deletion on failure
    marker = target / INCOMPLETE
    write_file(marker, json_bytes({'copy_status': 'incomplete', 'phase_complete': False}))
    try:
        for row in plan['files']:
            source = within_repository(ROOT / relative_path(row['source']))
            destination = target / relative_path(row['destination'])
            within_repository(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            within_repository(destination.parent)
            digest = hashlib.sha256()
            count = 0
            with source.open('rb') as input_file, destination.open('xb') as output_file:
                for chunk in iter(lambda: input_file.read(1024 * 1024), b''):
                    output_file.write(chunk)
                    digest.update(chunk)
                    count += len(chunk)
                output_file.flush()
                os.fsync(output_file.fileno())
            if (digest.hexdigest(), count) != (row['sha256_raw'], row['bytes']):
                raise ValueError('Source changed during copy: ' + row['source'])
        expected_files = {row['destination'] for row in plan['files']} | {INCOMPLETE}
        expected_dirs = {parent.as_posix() for row in plan['files']
                         for parent in relative_path(row['destination']).parents if str(parent) != '.'}
        actual_files, actual_dirs = set(), set()
        for path in target.rglob('*'):
            within_repository(path)
            (actual_dirs if path.is_dir() else actual_files).add(path.relative_to(target).as_posix())
        if actual_files != expected_files or actual_dirs != expected_dirs:
            raise ValueError('Copied member set differs from explicit manifest')
        for row in plan['files']:
            if digest_file(target / relative_path(row['destination'])) != (row['sha256_raw'], row['bytes']):
                raise ValueError('Copied file digest/byte-count mismatch')
        receipt = {'schema': 'g4usim_evidence_copy_receipt_v1', 'copy_status': 'byte_copy_verified',
                   'phase_complete': False, 'acceptance': 'not_evaluated',
                   'created_utc': datetime.now(timezone.utc).isoformat(),
                   'destination': str(target), 'files': plan['files'],
                   'exact_members_verified': True, 'copied_files': len(plan['files']),
                   'copied_bytes': sum(row['bytes'] for row in plan['files'])}
        # Until this final rename, even a partially written receipt retains the
        # incomplete filename. Rename is the only copy-completion publication.
        write_file(marker, json_bytes(receipt), exclusive=False)
        if os.path.lexists(target / RECEIPT):
            raise FileExistsError('Receipt destination unexpectedly exists')
        marker.rename(target / RECEIPT)
        return receipt
    except Exception as exc:
        try:
            write_file(marker, json_bytes({'copy_status': 'incomplete', 'phase_complete': False,
                                          'error': str(exc)}), exclusive=False)
        except OSError:
            pass  # the already-created incomplete marker remains authoritative
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    manifest = Path(args.manifest)
    if not manifest.is_absolute():
        manifest = ROOT / relative_path(args.manifest)
    manifest = within_repository(manifest)
    rows = json.loads(manifest.read_text(encoding='utf-8'))
    plan = make_plan(rows, args.destination)
    if args.execute:
        result = execute(plan)
    else:
        result = {'mode': 'plan', 'write_performed': False, 'phase_complete': False,
                  'destination': plan['destination'], 'files': len(rows),
                  'bytes': sum(row['bytes'] for row in rows)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
