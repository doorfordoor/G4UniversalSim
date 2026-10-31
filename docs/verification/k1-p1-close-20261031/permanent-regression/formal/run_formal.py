"""Capture native canonical runner/gate receipts after root's clean commit."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
status = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
assert head == '5644e1e52b9c2dd5b463217e9e601c8116f8a913' and status == ''
test_sha = sha(ROOT / 'scripts/test_k1_staging_alias.py')
assert test_sha == '0d5cb4db40d50417e16a316ec8825ddd30c7265a0b8d468679529288e9a95de2'
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', QT_QPA_PLATFORM='offscreen')
rows = []
def run(name, command):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    log = OUT / (name + '.log')
    log.write_bytes(result.stdout)
    row = {'name': name, 'command': command, 'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
           'actual_exit_code': result.returncode, 'raw_log_path': str(log), 'raw_log_sha256': sha(log)}
    rows.append(row)
    (OUT / 'parent-process-receipt.json').write_bytes((json.dumps({'head': head, 'test_sha256': test_sha, 'commands': rows}, indent=2) + '\n').encode())
    print(json.dumps(row), flush=True)
    assert result.returncode == 0, result.stdout.decode(errors='replace')[-4000:]
    return result
win_reports = OUT / 'windows-reports'
run('windows-canonical-runner', [sys.executable, '-B', str(ROOT / 'scripts/run_m0_tests.py'), '--profile', 'static',
    '--case', 'k1_staging_alias', '--report-root', str(win_reports), '--require-tracked-sources', '--fail-on-skip'])
reports = list(win_reports.glob('*/report.json'))
assert len(reports) == 1
run('windows-strict-gate', [sys.executable, '-B', str(ROOT / 'scripts/check_report_evidence.py'),
    '--report-root', str(reports[0].parent)])
linux_script = '/mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim/out/collab/k1-p1-permanent-regression-20261031/formal/linux_formal.py'
run('wsl-linux-canonical-and-gates', ['wsl.exe', '-d', 'Ubuntu', '--',
    '/home/u123/venvs/g4-f4-qt-6.11.1-20261030/bin/python', '-B', linux_script])
linux_reports = list((OUT / 'wsl-linux-reports-copy').glob('*/report.json'))
assert len(linux_reports) == 1
run('windows-recheck-linux-copy-gate', [sys.executable, '-B', str(ROOT / 'scripts/check_report_evidence.py'),
    '--report-root', str(linux_reports[0].parent)])
win_data, linux_data = json.loads(reports[0].read_bytes()), json.loads(linux_reports[0].read_bytes())
for report in (win_data, linux_data):
    assert report['git_head'] == head and report['git_dirty'] is False and report['git_status_porcelain'] == ''
    assert report['tracked_source_gate'] == 'pass' and not report['cases_with_zero_assertions']
    assert len(report['results']) == 1 and report['results'][0]['name'] == 'k1_staging_alias'
    assert report['results'][0]['status'] == 'pass' and report['results'][0]['exit_code'] == 0
assert win_data['source_fingerprint'] == linux_data['source_fingerprint']
assert win_data['tests_content_fingerprint'] == linux_data['tests_content_fingerprint']
assert subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True) == ''
report = {'head': head, 'git_status_short': '', 'test_sha256': test_sha,
    'product_sha256': sha(ROOT / 'gui/g4usim_gui/core/experiment_bundle.py'), 'commands': rows,
    'windows_report': str(reports[0]), 'windows_report_sha256': sha(reports[0]),
    'wsl_linux_copied_report': str(linux_reports[0]), 'wsl_linux_report_sha256': sha(linux_reports[0]),
    'source_fingerprint': win_data['source_fingerprint'], 'tests_content_fingerprint': win_data['tests_content_fingerprint'],
    'windows_assertions': win_data['assertions_executed_total'], 'linux_assertions': linux_data['assertions_executed_total'],
    'backend_simulation': 'not_started; static case does not require executable',
    'scope': 'canonical single-case static reports, not a full matrix rerun'}
(OUT / 'formal-validation-receipt.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print('CANONICAL_WINDOWS_LINUX_SINGLE_CASE_AND_STRICT_GATES_PASSED', flush=True)
