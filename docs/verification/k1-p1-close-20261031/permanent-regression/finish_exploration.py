import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
linux_script = '/mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim/out/collab/' + OUT.name + '/linux_ext4_explore.py'
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', QT_QPA_PLATFORM='offscreen')
jobs = [('wsl-linux-ext4-current', ['wsl.exe', '-d', 'Ubuntu', '--',
         '/home/u123/venvs/g4-f4-qt-6.11.1-20261030/bin/python', '-B', linux_script], 0),
        ('windows-old-r2', [sys.executable, '-B', str(OUT / 'old_r2_same_test.py')], 1)]
rows = json.loads((OUT / 'exploratory-receipt.json').read_bytes())['cases']
for name, command, expected in jobs:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    log = OUT / (name + '.log')
    log.write_bytes(result.stdout)
    markers = re.findall(rb'G4USIM_ASSERTS=(\d+)', result.stdout)
    row = {'name': name, 'command': command, 'exit_code': result.returncode, 'expected_exit_code': expected,
           'assertions': int(markers[-1]) if markers else None, 'assert_probe': 'settrace_assert_lines_v3',
           'raw_log_sha256': sha(log), 'log': str(log), 'test_sha256': sha(ROOT / 'scripts/test_k1_staging_alias.py')}
    rows.append(row)
    print(json.dumps(row), flush=True)
    assert result.returncode == expected, result.stdout.decode(errors='replace')[-4500:]
    assert len(markers) == 1 and int(markers[0]) > 0
    if expected == 1:
        data = json.loads((OUT / 'windows-old-r2-evidence/late-receipt-link/receipt.json').read_bytes())
        assert data['published'] and data['error'] is None and data['source_restored']
        assert b'AssertionError' in result.stdout and b'post_capture_external_receipt_link' in result.stdout
        row['negative_control'] = 'same_formal_test_failed_at_required_refusal_assertion'
original = subprocess.check_output(['git', 'show', 'HEAD:scripts/test_k1_staging_alias.py'], cwd=ROOT)
current = (ROOT / 'scripts/test_k1_staging_alias.py').read_bytes()
nodes = lambda raw: [ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(raw)) if isinstance(n, ast.Assert)]
old_asserts, new_asserts = nodes(original), nodes(current)
assert all(new_asserts.count(n) >= old_asserts.count(n) for n in old_asserts)
report = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
          'test_sha256': sha(ROOT / 'scripts/test_k1_staging_alias.py'),
          'current_product_sha256': sha(ROOT / 'gui/g4usim_gui/core/experiment_bundle.py'),
          'old_assert_ast_count': len(old_asserts), 'new_assert_ast_count': len(new_asserts),
          'old_asserts_unchanged': True, 'cases': rows, 'scope': 'exploratory dirty test change; not frozen canonical report',
          'initial_wsl_drvfs_failure_retained': True, 'backend': 'not_started'}
(OUT / 'exploratory-complete-receipt.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print('EXPLORATORY_POSITIVE_AND_NEGATIVE_CONTROLS_VERIFIED', flush=True)
