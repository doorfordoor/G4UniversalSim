"""Canonical Linux report on native filesystem, verified copy to shared evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import PySide6

OUT = Path(__file__).resolve().parent
SHARED_ROOT = OUT.parents[3]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', QT_QPA_PLATFORM='offscreen')
owned = Path(tempfile.mkdtemp(prefix='k1-p1-canonical-20261031-'))
assert owned.is_absolute() and owned.parent == Path(tempfile.gettempdir()).resolve()
ROOT = owned / 'source'
setup = subprocess.run(['git', 'clone', '--shared', '--no-checkout', '/mnt/d/Geant4/G4UniversalSim', str(ROOT)],
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=100)
(OUT / 'wsl-native-source-clone.log').write_bytes(setup.stdout)
assert setup.returncode == 0, setup.stdout.decode(errors='replace')
checkout = subprocess.run(['git', '-C', str(ROOT), 'checkout', '--detach', '5644e1e52b9c2dd5b463217e9e601c8116f8a913'],
                          env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=100)
(OUT / 'wsl-native-source-checkout.log').write_bytes(checkout.stdout)
assert checkout.returncode == 0, checkout.stdout.decode(errors='replace')
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, env=env, text=True).strip()
assert head == '5644e1e52b9c2dd5b463217e9e601c8116f8a913'
assert subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, env=env, text=True) == ''
assert sha(ROOT / 'scripts/test_k1_staging_alias.py') == sha(SHARED_ROOT / 'scripts/test_k1_staging_alias.py')
report_root = owned / 'reports'
rows = []
def run(name, command):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=200)
    log = OUT / (name + '.log')
    log.write_bytes(result.stdout)
    row = {'name': name, 'command': command, 'actual_exit_code': result.returncode,
           'started_utc': started, 'raw_log_path': str(log), 'raw_log_sha256': sha(log)}
    rows.append(row)
    (OUT / 'wsl-native-process-receipt.json').write_bytes((json.dumps({'head': head, 'commands': rows}, indent=2) + '\n').encode())
    print(json.dumps(row), flush=True)
    assert result.returncode == 0, result.stdout.decode(errors='replace')[-4000:]
run('wsl-native-canonical-runner', [sys.executable, '-B', str(ROOT / 'scripts/run_m0_tests.py'), '--profile', 'static',
    '--case', 'k1_staging_alias', '--report-root', str(report_root), '--require-tracked-sources', '--fail-on-skip'])
reports = list(report_root.glob('*/report.json'))
assert len(reports) == 1
run('wsl-native-strict-gate', [sys.executable, '-B', str(ROOT / 'scripts/check_report_evidence.py'), '--report-root', str(reports[0].parent)])
copied = OUT / 'wsl-linux-reports-copy'
assert copied.absolute().is_relative_to(OUT.resolve())
shutil.copytree(report_root, copied)
digests = lambda root: {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}
original_hashes, copied_hashes = digests(report_root), digests(copied)
assert original_hashes == copied_hashes
run('wsl-copied-strict-gate', [sys.executable, '-B', str(ROOT / 'scripts/check_report_evidence.py'),
    '--report-root', str(copied / reports[0].parent.name)])
receipt = {'head': head, 'commands': rows, 'python': sys.executable, 'python_version': sys.version,
    'pyside6': PySide6.__version__, 'platform': sys.platform, 'native_report_root': str(report_root),
    'native_original_retained': True, 'copied_report_root': str(copied), 'source_sha256': original_hashes,
    'copied_sha256': copied_hashes, 'all_files_byte_identical': True,
    'native_source_root': str(ROOT), 'native_source_checkout': head,
    'native_source_reason': 'clean detached temporary checkout avoids DrvFS status stalls; no shared repository config change',
    'source_clone_log_sha256': sha(OUT / 'wsl-native-source-clone.log'),
    'source_checkout_log_sha256': sha(OUT / 'wsl-native-source-checkout.log')}
(OUT / 'wsl-copy-identity.json').write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print('WSL_NATIVE_AND_COPIED_STRICT_GATES_PASSED', flush=True)
