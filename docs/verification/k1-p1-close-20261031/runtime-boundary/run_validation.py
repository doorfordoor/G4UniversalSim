"""Dedicated evidence runner, never writes outside this evidence root."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
tracked = ['gui/g4usim_gui/core/experiment_bundle.py', 'gui/smoke_tests/smoke_k1_relocation.py',
           'scripts/test_k1_staging_alias.py', 'tools/test_assert_probe.py',
           'out/collab/k1-relocation-independent-validation/late_reparse.py',
           'out/collab/k1-relocation-independent-validation/late-reparse-exits.json',
           'out/collab/k1-relocation-independent-validation/late-reparse-base/receipt.json',
           'out/collab/k1-relocation-independent-validation/late-reparse-candidate/receipt.json',
           'out/collab/k1-relocation-candidate/README.md',
           'out/collab/k1-relocation-candidate/archive-r2/experiment_bundle.py',
           'out/collab/k1-relocation-candidate/archive-windows-only/test_k1_staging_alias.py']
before = {p: sha(ROOT / p) for p in tracked}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', QT_QPA_PLATFORM='offscreen')
jobs = [('old-r2-junction', 'late_boundary.py', ['--target', 'r2']),
        ('current-r3-junction', 'late_boundary.py', ['--target', 'r3']),
        ('current-r3-content-change', 'late_boundary.py', ['--target', 'r3', '--change', 'content']),
        ('current-r3-real-alias-relocation', 'alias_relocate.py', [])]
rows = []
for name, script, arguments in jobs:
    command = [sys.executable, '-B', str(ROOT / 'tools/test_assert_probe.py'), str(OUT / script), *arguments]
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    log = OUT / (name + '.log')
    log.write_bytes(result.stdout)
    matches = re.findall(rb'G4USIM_ASSERTS=(\d+)', result.stdout)
    row = {'name': name, 'command': command, 'cwd': str(ROOT), 'started_utc': started,
           'finished_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': result.returncode,
           'assert_probe': 'settrace_assert_lines_v3', 'assertions': int(matches[-1]) if matches else None,
           'raw_log_path': str(log), 'raw_log_sha256': sha(log), 'adapter_sha256': sha(OUT / script)}
    rows.append(row)
    print(json.dumps(row), flush=True)
    (OUT / 'validation-receipt.json').write_bytes((json.dumps({'cases': rows, 'protected_before': before}, indent=2) + '\n').encode())
    assert result.returncode == 0, result.stdout.decode('utf-8', errors='replace')[-3500:]
    assert len(matches) == 1 and int(matches[0]) > 0
after = {p: sha(ROOT / p) for p in tracked}
assert before == after
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
status = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
report = {'head': head, 'git_status_short': status, 'python': sys.executable,
          'cases': rows, 'assertions_executed_total': sum(r['assertions'] for r in rows),
          'protected_before': before, 'protected_after': after, 'protected_bytes_unchanged': True,
          'scope': 'Independent Windows P1 late resource and normal alias checks; not whole K1 acceptance',
          'backend': 'not_started', 'linux': 'not rerun; Windows-specific independent gap'}
(OUT / 'validation-receipt.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print('ALL_DEDICATED_VALIDATIONS_PASSED', flush=True)
