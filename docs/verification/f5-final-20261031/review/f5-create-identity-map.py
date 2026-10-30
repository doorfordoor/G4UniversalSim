"""Verify the explicit F5 GUI evidence mapping after a test-only correction."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
NATIVE_HEAD = '5d56187392a2e7b888d5ce13f8da05a295cba6d4'
NATIVE = ROOT / 'out/collab/f5-native-5d56187-1'
ALLOWED = {'scripts/test_displacement_damage.py', 'scripts/run_m0_tests.py',
           'docs/collab/inbox/20261030-2155-astra-f5-execution.md'}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--head', required=True)
    parser.add_argument('--capabilities', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert git('rev-parse', 'HEAD').decode().strip() == args.head
    assert not git('status', '--porcelain').strip()
    changed = git('diff', '--name-only', NATIVE_HEAD, args.head).decode().splitlines()
    assert changed and set(changed) <= ALLOWED, changed
    assert not git('diff', NATIVE_HEAD, args.head, '--', 'gui', 'src', 'include', 'main.cc', 'CMakeLists.txt')
    identity = read(NATIVE / 'identity.json')
    assert identity['gui_head'] == NATIVE_HEAD
    assert read(NATIVE / 'launcher.json')['actual_process_exit'] == 0
    hashes = read(NATIVE / 'gui-file-hashes.json')
    assert len(hashes) == identity['gui_file_count'] == 129
    assert sha(json.dumps(hashes, sort_keys=True).encode('utf-8')) == identity['gui_files_sha256']
    for path, expected in hashes.items():
        raw = (ROOT / path).read_bytes()
        assert sha(raw) == expected['sha256_raw'], path
        assert sha(raw.replace(b'\r\n', b'\n')) == expected['sha256_lf'], path
        assert git('show', f'{NATIVE_HEAD}:{path}') == git('show', f'{args.head}:{path}'), path
    caps = read(args.capabilities)
    assert caps['build_git_commit'] == args.head
    assert caps['build_git_source_state'] == 'clean'
    compared = ('source_fingerprint', 'build_configuration', 'compiler_id',
                'compiler_version', 'geant4_version_number', 'multithreaded')
    for key in compared:
        assert caps[key] == identity['capabilities'][key], key
    record = {
        'status': 'passed', 'native_observed_commit': NATIVE_HEAD,
        'automated_matrix_commit': args.head, 'changed_files': changed,
        'gui_files_raw_and_git_blob_equal': len(hashes),
        'product_tree_diff_empty': True,
        'compared_backend_properties': {key: caps[key] for key in compared},
        'native_identity_sha256': sha((NATIVE / 'identity.json').read_bytes()),
        'native_gui_hashes_sha256': sha((NATIVE / 'gui-file-hashes.json').read_bytes()),
        'new_capabilities_sha256': sha(args.capabilities.read_bytes()),
        'boundary': 'Native interaction was observed at native_observed_commit. '
                    'The later commit changes only tests and review documentation; '
                    'its automated matrix is validated separately. No claim of native '
                    'interaction or binary byte equality at the later commit.'
    }
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': 'passed', 'gui_files': len(hashes), 'output': str(args.output)}))

if __name__ == '__main__':
    main()
