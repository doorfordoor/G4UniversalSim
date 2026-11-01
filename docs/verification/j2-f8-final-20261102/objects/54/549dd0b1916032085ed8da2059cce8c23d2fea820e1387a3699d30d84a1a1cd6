"""Pure stdlib/read-only Git identity mapping. Never executes runtime code or Git writes."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = '18c5858fd6e80a5cb6096beacebfef69c479ad49'
EXE = '01e0fb795f93772ccfa818d625fee145d8da1ad3ad80894372a9a855f0af108a'
CPP_FP = '9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a'
NATIVE = 'out/verification/j2-f8-18c5858'
SCOPE = 'out/collab/j2-f8-18c5858-main-acceptance-scope.md'
SMOKES = {'gui/smoke_tests/smoke_f8_accessibility.py', 'gui/smoke_tests/smoke_j2_geometry.py'}
SCALES = ('100', '125', '150')
FILES = ('identity.json', 'launch.json', 'exit.json', 'visual-observations.json')


class Rejected(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Rejected(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key: ' + key)
        value[key] = item
    return value


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(Rejected('Nonfinite JSON: ' + x)))


def full_head(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{40}', value), 'A full lowercase Git HEAD is required')
    return value


def sha_value(value, nullable=False):
    require((nullable and value is None) or
            (type(value) is str and re.fullmatch('[0-9a-f]{64}', value)), 'Invalid SHA256')


def relative(value):
    require(type(value) is str and value and '\\' not in value and ':' not in value
            and not any(ord(c) < 32 for c in value), 'Invalid repository path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')), 'Ambiguous repository path')
    return value


def git(*args, input=None):
    # No shell, config write, checkout, index write, dispatch or executable launch.
    result = subprocess.run(['git', '-c', 'core.longpaths=true', *args], cwd=REPO,
                            input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0, 'Git read failed: ' + result.stderr.decode(errors='replace')[:1200])
    return result.stdout


def tree(head):
    result = {}
    for item in git('ls-tree', '-r', '-z', '--full-tree', full_head(head)).split(b'\0'):
        if not item:
            continue
        header, name = item.split(b'\t', 1)
        mode, kind, oid = header.decode().split()
        name = relative(name.decode('utf-8'))
        require(name not in result, 'Duplicate Git tree path')
        result[name] = {'mode': mode, 'kind': kind, 'oid': oid}
    return result


def blobs(head, paths):
    paths = list(dict.fromkeys(relative(p) for p in paths))
    raw = git('cat-file', '--batch', input=''.join(head + ':' + p + '\n' for p in paths).encode())
    offset, result = 0, {}
    for path in paths:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        require(len(header) == 3 and header[1] == b'blob', 'Missing/non-blob Git path: ' + path)
        size = int(header[2])
        start = end + 1
        result[path] = raw[start:start + size]
        require(raw[start + size:start + size + 1] == b'\n', 'Invalid Git batch framing')
        offset = start + size + 1
    require(offset == len(raw), 'Unexpected trailing Git batch output')
    return result


def cpp_paths(entries):
    fixed = {'main.cc', 'CMakeLists.txt', 'include/Core/BuildInfo.hh.in'}
    return sorted(p for p in entries if p in fixed or
                  (p.startswith('src/') and p.endswith('.cc')) or
                  (p.startswith('include/') and p.endswith('.hh')) or
                  (p.startswith('cmake/') and p.endswith('.cmake')))


def cpp_fingerprint(head, entries):
    paths = cpp_paths(entries)
    require(all(entries[p]['mode'] == '100644' and entries[p]['kind'] == 'blob' for p in paths), 'Nonordinary C++ implementation path')
    values = blobs(head, paths)
    return digest(''.join(p + ':' + digest(values[p]) + '\n' for p in sorted(values)).encode())


def origin_anchor():
    base_tree = tree(BASE)
    records, common = {}, None
    for scale in SCALES:
        folder = REPO / NATIVE / ('native' + scale)
        values = {name: read_json(folder / name) for name in FILES}
        identity, launch, exit_record = (values[n] for n in FILES[:3])
        require(identity['head'] == launch['head'] == launch['ending_head'] == BASE, 'Native original HEAD mismatch')
        require(identity['exe_sha256'] == launch['exe_sha256'] == launch['ending_exe_sha256'] == EXE, 'Native original EXE identity mismatch')
        require(identity['host_sha256'] == launch['host_sha256'], 'Native host identity mismatch')
        require(launch['status'] == 'exited' and type(launch['process_exit_code']) is int
                and launch['process_exit_code'] == 0 and type(exit_record['exit_code']) is int
                and exit_record['exit_code'] == 0, 'Original exit evidence is incomplete')
        require(launch['ending_git_status'] == '' and launch['qpa'] == 'windows', 'Unexpected original launch environment')
        caps = launch['capabilities']
        require(caps['build_git_commit'] == BASE and caps['source_fingerprint'] == CPP_FP
                and caps['geant4_version_number'] == 1132, 'Original capabilities mismatch')
        gui = identity['gui_files']
        require(type(gui) is dict and len(gui) == 149, 'Expected exact 149-file native GUI identity')
        expected_gui = {p for p in base_tree if p.startswith('gui/g4usim_gui/') and p.endswith('.py')}
        require(set(gui) == expected_gui, 'Native GUI identity omitted or substituted an original Python file')
        for p, sha in gui.items():
            relative(p); sha_value(sha)
            require(p.startswith('gui/g4usim_gui/') and p.endswith('.py')
                    and base_tree.get(p, {}).get('mode') == '100644', 'Unexpected native GUI identity path')
        require(common is None or gui == common, 'Three native GUI identities differ')
        common = gui
        require(type(values[FILES[3]]) is list and values[FILES[3]], 'Missing visual observation metadata')
        records[scale] = {'original_head': BASE, 'original_exe_sha256': EXE,
                          'original_exe_path': identity['exe'], 'host_sha256': identity['host_sha256'],
                          'host_pid': identity['pid'], 'launcher_pid': launch['pid'],
                          'scale_factor': identity['scale_factor'], 'visual_metadata_records': len(values[FILES[3]]),
                          'files': {str((folder / n).relative_to(REPO)).replace('\\', '/'):
                                    digest((folder / n).read_bytes()) for n in FILES}}
    baseline_gui = blobs(BASE, common)
    require(all(digest(baseline_gui[p]) == sha for p, sha in common.items()), 'Native GUI bytes differ from original Git blobs')
    require(cpp_fingerprint(BASE, base_tree) == CPP_FP, 'Original C++ source fingerprint mismatch')
    return {'schema': 'g4usim_native_mapping_origin_v1', 'status': 'prepared_pending_future_head',
            'original_native_head': BASE, 'original_exe_sha256': EXE, 'cpp_source_fingerprint': CPP_FP,
            'gui_files': common, 'native': records, 'scope_path': SCOPE,
            'scope_sha256': digest((REPO / SCOPE).read_bytes()),
            'future_head': None, 'future_mapping_executed': False,
            'no_new_native_execution': True, 'no_visual_reinspection': True,
            'screenshots_opened_or_copied': False, 'live_executable_rehashed': False}


def docs_path(path):
    return path in {'AGENTS.md', 'STATUS.md', 'README.md', 'gui/AGENTS.md'} or path.startswith(('docs/', 'gui/docs/'))


def allowlist(value, future, anchor):
    require(type(value) is dict and set(value) == {'schema', 'status', 'frozen_by', 'base_head',
            'candidate_head', 'scope_sha256', 'allowed_changes'}, 'Invalid allowlist object/fields')
    require(value.get('schema') == 'g4usim_native_mapping_allowlist_v1' and
            value.get('status') == 'frozen' and value.get('frozen_by') == 'main', 'Main frozen allowlist required')
    require(value.get('base_head') == BASE and value.get('candidate_head') == future, 'Allowlist HEAD mismatch')
    require(value.get('scope_sha256') == anchor['scope_sha256'], 'Scope identity mismatch')
    entries, smokes = {}, set()
    require(type(value.get('allowed_changes')) is list, 'Explicit changed-file list required')
    for row in value['allowed_changes']:
        require(set(row) == {'path', 'kind', 'before_sha256', 'after_sha256'}, 'Invalid allowlist record')
        path = relative(row['path'])
        require(path not in entries, 'Duplicate allowlist path')
        sha_value(row['before_sha256'], True); sha_value(row['after_sha256'], True)
        require(row['before_sha256'] != row['after_sha256'], 'Unused/unchanged allowlist entry')
        if row['kind'] == 'smoke':
            require(path in SMOKES and row['before_sha256'] is not None and row['after_sha256'] is not None,
                    'Only the two fixed existing smoke files may change')
            smokes.add(path)
        else:
            require(row['kind'] == 'docs' and docs_path(path), 'Runtime path cannot be declared as docs')
        entries[path] = row
    require(smokes == SMOKES, 'Both explicitly frozen smoke changes are required')
    return entries


def changed_paths(before, after):
    return {p for p in set(before) | set(after) if before.get(p) != after.get(p)}


def check_diff(before, after, entries, old_bytes, new_bytes):
    changes = changed_paths(before, after)
    require(changes == set(entries), 'Unapproved or unused changed paths: ' + repr(sorted(changes ^ set(entries))))
    for path in changes:
        a, b, row = before.get(path), after.get(path), entries[path]
        for item in (a, b):
            require(item is None or (item['mode'] == '100644' and item['kind'] == 'blob'), 'Reject mode/link/submodule change: ' + path)
        require((digest(old_bytes[path]) if a else None) == row['before_sha256'], 'Original allowed blob mismatch: ' + path)
        require((digest(new_bytes[path]) if b else None) == row['after_sha256'], 'Frozen candidate allowed blob mismatch: ' + path)


def write_new(path, value):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE) and path != HERE, 'Output must be inside this OUT preparation directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--anchor', type=Path, required=True)
    p = sub.add_parser('check')
    p.add_argument('--anchor', type=Path, required=True); p.add_argument('--anchor-sha256', required=True)
    p.add_argument('--candidate-head', required=True); p.add_argument('--allowlist', type=Path, required=True)
    p.add_argument('--allowlist-sha256', required=True); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        anchor = origin_anchor(); write_new(args.anchor, anchor)
        print(json.dumps({'status': anchor['status'], 'origin_gui_files': len(anchor['gui_files']),
                          'anchor_sha256': digest(args.anchor.read_bytes()), 'future_mapping_executed': False}))
        return 0
    future = full_head(args.candidate_head)
    require(future != BASE, 'A genuinely new candidate HEAD is required; original HEAD is not a future mapping')
    sha_value(args.anchor_sha256); sha_value(args.allowlist_sha256)
    require(digest(args.anchor.read_bytes()) == args.anchor_sha256, 'Origin anchor changed')
    require(digest(args.allowlist.read_bytes()) == args.allowlist_sha256, 'Main allowlist changed')
    anchor = read_json(args.anchor)
    require(anchor == origin_anchor(), 'Original native evidence or scope changed')
    git('merge-base', '--is-ancestor', BASE, future)
    entries = allowlist(read_json(args.allowlist), future, anchor)
    before, after = tree(BASE), tree(future)
    changes = changed_paths(before, after)
    old = blobs(BASE, [p for p in changes if p in before])
    new = blobs(future, [p for p in changes if p in after])
    check_diff(before, after, entries, old, new)
    gui = blobs(future, anchor['gui_files'])
    require(all(digest(gui[p]) == sha and after[p]['mode'] == '100644' for p, sha in anchor['gui_files'].items()), 'Future runtime GUI changed')
    require(cpp_fingerprint(future, after) == CPP_FP, 'Future C++ implementation changed')
    result = {'schema': 'g4usim_native_file_identity_mapping_v1', 'status': 'file_identity_mapping_verified_only',
              'original_native_head': BASE, 'candidate_head': future, 'original_exe_sha256': EXE,
              'gui_files_unchanged': 149, 'cpp_source_fingerprint': CPP_FP,
              'allowed_changes': [entries[p] for p in sorted(entries)],
              'anchor_sha256': args.anchor_sha256, 'allowlist_sha256': args.allowlist_sha256,
              'original_native_evidence': anchor['native'], 'scope_path': SCOPE, 'scope_sha256': anchor['scope_sha256'],
              'new_build_executed_natively': False, 'visuals_reobserved': False,
              'native_claims_extended': False, 'runtime_behavior_tests_executed': False,
              'new_build_matrix_acceptance': 'separate_pending_not_inferred',
              'boundaries': ['Preserve each original scale-specific scope; no universal three-scale full-workflow claim.',
                             'External QQ images remain local only; no screenshot copy or visual reinspection.',
                             'No new live F5 observation or offline CLI replay claim.',
                             'C++ fingerprint maps implementation only; original EXE identity remains 01e0fb79...',
                             'Host/launcher PID evidence is not a full parent-child process-tree proof.']}
    require(anchor == origin_anchor(), 'Original evidence changed while checking')
    write_new(args.output, result)
    print(json.dumps({'status': result['status'], 'candidate_head': future, 'gui_files_unchanged': 149}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Rejected, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print('MAPPING_REJECTED: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
