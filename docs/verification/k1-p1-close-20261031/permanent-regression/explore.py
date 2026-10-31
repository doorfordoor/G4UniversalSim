"""Exploratory checks before root commits the single formal-test change."""
import ast
from datetime import datetime, timezone
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
test = ROOT / 'scripts/test_k1_staging_alias.py'
original = subprocess.check_output(['git', 'show', 'HEAD:scripts/test_k1_staging_alias.py'], cwd=ROOT)
assertions = lambda raw: [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.Assert)]
old_asserts, new_asserts = assertions(original), assertions(test.read_bytes())
assert all(new_asserts.count(item) >= old_asserts.count(item) for item in old_asserts)
old_module = ast.parse(original)
new_module = ast.parse(test.read_bytes())
old_body = next(n for n in old_module.body if isinstance(n, ast.FunctionDef) and n.name == 'exercise').body
new_body = next(n for n in new_module.body if isinstance(n, ast.FunctionDef) and n.name == 'exercise').body
old_statements = [ast.dump(n, include_attributes=False) for n in old_body]
new_statements = [ast.dump(n, include_attributes=False) for n in new_body]
assert [n for n in new_statements if n in old_statements] == old_statements
(OUT / 'test-change.diff').write_bytes(subprocess.check_output(['git', 'diff', '--', 'scripts/test_k1_staging_alias.py'], cwd=ROOT))
product_sha = sha(ROOT / 'gui/g4usim_gui/core/experiment_bundle.py')
assert product_sha == '5c1dff0338e80a673ba8f3427aeb7bfe1abe9d2b5315efca564310be8118385a'
linux_root = '/mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim'
linux_out = linux_root + '/out/collab/' + OUT.name
linux_python = '/home/u123/venvs/g4-f4-qt-6.11.1-20261030/bin/python'
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', QT_QPA_PLATFORM='offscreen')
jobs = [('windows-current', [sys.executable, '-B', str(ROOT / 'tools/test_assert_probe.py'), str(test),
                             '--evidence-root', str(OUT / 'windows-current-evidence')], 0),
        ('wsl-linux-current', ['wsl.exe', '-d', 'Ubuntu', '--', linux_python, '-B',
                               linux_root + '/tools/test_assert_probe.py', linux_root + '/scripts/test_k1_staging_alias.py',
                               '--evidence-root', linux_out + '/wsl-linux-current-evidence'], 0),
        ('windows-old-r2', [sys.executable, '-B', str(OUT / 'old_r2_same_test.py')], 1)]
rows = []
for name, command, expected in jobs:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    log = OUT / (name + '.log')
    log.write_bytes(result.stdout)
    matches = re.findall(rb'G4USIM_ASSERTS=(\d+)', result.stdout)
    row = {'name': name, 'command': command, 'started_utc': started, 'exit_code': result.returncode,
           'expected_exit_code': expected, 'assertions': int(matches[-1]) if matches else None,
           'assert_probe': 'settrace_assert_lines_v3', 'raw_log_sha256': sha(log), 'log': str(log),
           'test_sha256': sha(test), 'product_sha256': product_sha if expected == 0 else '34db09d96260841411dc92306f4eab438d75792a4f74abacde3322c10b3d66c2'}
    rows.append(row)
    print(json.dumps(row), flush=True)
    (OUT / 'exploratory-receipt.json').write_bytes((json.dumps({'cases': rows}, indent=2) + '\n').encode())
    assert result.returncode == expected, result.stdout.decode('utf-8', errors='replace')[-4000:]
    assert len(matches) == 1 and int(matches[0]) > 0
    if expected == 1:
        data = json.loads((OUT / 'windows-old-r2-evidence/late-receipt-link/receipt.json').read_bytes())
        assert data['published'] and data['error'] is None and data['source_restored']
        assert b'AssertionError' in result.stdout and b'post_capture_external_receipt_link' in result.stdout
        row['negative_control'] = 'same_formal_test_failed_at_required_refusal_assertion'
report = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
          'test_sha256': sha(test), 'current_product_sha256': product_sha,
          'old_assert_ast_count': len(old_asserts), 'new_assert_ast_count': len(new_asserts),
          'old_asserts_and_exercise_statements_unchanged_in_order': True,
          'cases': rows, 'scope': 'exploratory dirty test change; not frozen canonical report', 'backend': 'not_started'}
(OUT / 'exploratory-receipt.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print('EXPLORATORY_POSITIVE_AND_NEGATIVE_CONTROLS_VERIFIED', flush=True)
