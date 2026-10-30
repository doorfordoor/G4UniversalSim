"""Audit completed Windows report/logs/registry and append archive inputs only.

Runs evidence gates, never tests, a backend, CI, Qt or desktop automation.
"""
from __future__ import annotations
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'out/collab'
PRODUCT = '7d718d038a00d89995ea773b4772764116b620c3'
CI_HEAD = 'a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9'
REPORT = ROOT / 'out/verification/f4-release-windows/20261030-202435-a53c3ee6/report.json'
BASELINE = ROOT / 'docs/verification/f1-automated-20261030/windows/final-1/report.json'
ROOT_ACCEPTANCE = OUT / 'f4-windows-7d718d0-acceptance.json'
ROOT_GATE = OUT / 'f4-windows-7d718d0-gate.log'
RUNNER_LOG = OUT / 'f4-release-windows-runner.log'
SCRIPT = ROOT / 'scripts/check_report_evidence.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def receipt(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def write_json(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def git(*argv):
    return subprocess.check_output(['git', *argv], cwd=ROOT)


report = read(REPORT)
baseline = read(BASELINE)
root_receipt = read(ROOT_ACCEPTANCE)
protected_before = {str(path): sha(path.read_bytes()) for path in (REPORT, BASELINE, ROOT_ACCEPTANCE, ROOT_GATE, RUNNER_LOG)}
assert report['git_head'] == PRODUCT and report['git_dirty'] is False
assert root_receipt['product_commit'] == PRODUCT
assert root_receipt['actual_exit_code'] == 0 and root_receipt['session_id'] == 16898
assert root_receipt['gate_exit_code'] == 0
for field, path in [('report_sha256', REPORT), ('gate_log_sha256', ROOT_GATE), ('runner_log_sha256', RUNNER_LOG)]:
    assert root_receipt[field] == sha(path.read_bytes()), field
assert baseline['git_head'] == 'f176d0ed4cea60b7ca5a80ed81017c9404ec1257'
assert baseline['assertions_executed_total'] == 48511 and len(baseline['results']) == 143
assert report['profile'] == baseline['profile'] == 'all'
assert report['assert_probe'] == baseline['assert_probe'] == 'settrace_assert_lines_v3'

# Product registry comes from the exact report commit, not mutable HEAD.
registry_raw = git('show', PRODUCT + ':scripts/run_m0_tests.py')
assert git('show', CI_HEAD + ':scripts/run_m0_tests.py') == registry_raw
registry_snapshot = OUT / 'f4-windows-independent-7d718d0-registry.py.txt'
write_new(registry_snapshot, registry_raw)
tree = ast.parse(registry_raw.decode('utf-8-sig'))
assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and
                  any(isinstance(target, ast.Name) and target.id == 'CASES' for target in node.targets))
assert isinstance(assignment.value, ast.Tuple)
registry = []
for node in assignment.value.elts:
    assert isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Case'
    args = [ast.literal_eval(value) for value in node.args]
    kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
    row = dict(zip(('name', 'script', 'layer', 'requirements', 'timeout', 'args'), args))
    row.update(kwargs)
    registry.append(row)
assert len(registry) == 152 and len({row['name'] for row in registry}) == 152
assert [row['name'] for row in registry] == [row['name'] for row in report['results']]
assert Counter(row['layer'] for row in registry) == {'static': 28, 'gui': 44, 'backend': 59, 'integration': 21}

# Import only the runner's read-only definitions; no main/test dispatch.
spec = importlib.util.spec_from_file_location('f4_windows_readonly_runner_fingerprints', ROOT / 'scripts/run_m0_tests.py')
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)
assert (ROOT / 'scripts/run_m0_tests.py').read_bytes().replace(b'\r\n', b'\n') == registry_raw
assert runner.workspace_source_fingerprint() == report['source_fingerprint']
assert runner.tests_content_fingerprint() == report['tests_content_fingerprint']
assert not runner.untracked_source_files()
assert report['tracked_source_gate'] == 'pass' and report['untracked_source_files'] == []

cases = []
for expected, actual in zip(registry, report['results']):
    assert actual['script'] == expected['script'] and actual['layer'] == expected['layer']
    assert actual['status'] == 'pass' and actual['exit_code'] == 0
    assert type(actual['assertions_executed']) is int and actual['assertions_executed'] > 0
    assert actual['assert_probe'] == 'settrace_assert_lines_v3'
    assert actual['log_digest_algorithm'] == 'sha256_raw_bytes_lf_v2'
    log_path = REPORT.parent / (actual['name'] + '.log')
    raw = log_path.read_bytes()
    assert b'\r' not in raw, log_path
    assert sha(raw) == actual['log_sha256']
    log_text = raw.decode('utf-8')
    markers = re.findall(r'^G4USIM_ASSERTS=(\d+)\s*$', log_text, re.M)
    assert markers and int(markers[-1]) == actual['assertions_executed']
    assert runner.parse_assert_marker(log_text) == actual['assertions_executed']
    assert runner.count_assert_sites(ROOT / expected['script']) == actual['assert_sites']
    cases.append({'name': actual['name'], 'script': actual['script'], 'layer': actual['layer'],
                  'registry_requirements': expected.get('requirements', ()), 'registry_args': expected.get('args', ()),
                  'status': actual['status'], 'exit_code': actual['exit_code'],
                  'assertions_executed': actual['assertions_executed'], 'assert_sites': actual['assert_sites'],
                  'raw_log': receipt(log_path), 'all_assert_markers': [int(value) for value in markers]})
assert sum(row['assertions_executed'] for row in cases) == report['assertions_executed_total'] == 49913
assert sum(row['assert_sites'] for row in cases) == report['assert_sites_total'] == 4903
assert report['cases_with_assertion_counts'] == 152 and report['cases_with_zero_assertions'] == []
assert report['skip_policy'] == 'failure'
assert {path.name for path in REPORT.parent.glob('*.log')} == {row['name'] + '.log' for row in cases}
current_counts = {row['name']: row['assertions_executed'] for row in cases}
comparisons = []
for old in baseline['results']:
    assert old['name'] in current_counts
    assert current_counts[old['name']] >= old['assertions_executed']
    comparisons.append({'name': old['name'], 'baseline': old['assertions_executed'],
                        'current': current_counts[old['name']], 'delta': current_counts[old['name']] - old['assertions_executed']})
new_names = sorted(set(current_counts) - {row['name'] for row in baseline['results']})
assert len(new_names) == 9
assert current_counts['gui_qt_binding_lifetime'] == 8
assert current_counts['gui_f4_inspect_backend'] == 45
assert current_counts['gui_run_inputs'] == 103
assert current_counts['gui_f4_layout'] == 257
binding_log = (REPORT.parent / 'gui_qt_binding_lifetime.log').read_text(encoding='utf-8')
binding_identity = json.loads(binding_log.splitlines()[0])
assert binding_identity['PySide6'] == binding_identity['shiboken6'] == binding_identity['Qt'] == '6.11.1'
binding_operations = [json.loads(line) for line in binding_log.splitlines()[1:5]]
assert len(binding_operations) == 4 and all(row['iterations'] == 100 and row['none_ref_delta'] == 0 for row in binding_operations)

# Rerun only canonical evidence gates, keeping actual stdout bytes and exit codes.
gates = []
for name, args in [
    ('f4-windows-7d718d0-independent-gate.log', ['--report', str(REPORT), '--baseline', str(BASELINE)]),
    ('f4-windows-f1-baseline-independent-gate.log', ['--report', str(BASELINE)]),
]:
    argv = [sys.executable, '-B', str(SCRIPT), *args]
    completed = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    path = OUT / name
    write_new(path, completed.stdout)
    gates.append({'argv': argv, 'exit_code': completed.returncode, 'raw_log': receipt(path)})
    assert completed.returncode == 0 and b'report evidence: OK' in completed.stdout

root_runner_text = RUNNER_LOG.read_text(encoding='utf-8')
runner_lines = re.findall(r'^PASS ([^:]+): asserts=(\d+)/(\d+)\s*$', root_runner_text, re.M)
assert len(runner_lines) == 152
assert [name for name, _, _ in runner_lines] == [row['name'] for row in cases]
assert all(int(count) == current_counts[name] for name, count, _ in runner_lines)
assert '152 pass / 0 fail / 0 skip of 152 cases; assertions executed 49913' in root_runner_text
assert 'Report:' in root_runner_text
native = read(OUT / 'f4-native-7d718d0-independent-final-review.json')
assert native['product_head'] == PRODUCT and native['conclusion'] == 'accepted_no_blocking_defect_found_within_reviewed_scope'
assert native['events']['matched_before_after_pairs'] == 15 and len(native['images']) == 19
build = read(ROOT / 'out/verification/f4-build-7d718d0/receipt.json')
assert build['commit'] == PRODUCT and build['source_fingerprint'] == report['source_fingerprint']
assert build['tests_content_fingerprint'] == report['tests_content_fingerprint']
assert sha(Path(report['backend_executable']).read_bytes()) == build['exe_sha256'] == native['backend_exe_sha256']
current_head = git('rev-parse', 'HEAD').decode().strip()
current_status = git('status', '--porcelain').decode().strip()
assert current_head == CI_HEAD and current_status == ''
assert git('diff', '--name-only', PRODUCT, CI_HEAD).decode().splitlines() == ['.github/workflows/linux-geant4.yml']
assert git('diff', PRODUCT, CI_HEAD, '--', 'scripts/run_m0_tests.py', 'scripts/check_report_evidence.py',
           'gui/requirements.txt', 'gui', 'src', 'include', 'tools', 'config', 'scenarios', 'schema', 'macros', 'test', 'cmake') == b''
mapping = read(OUT / 'f4-ci-identity-map-a9ad09d/identity-map.json')
assert mapping['product_commit'] == PRODUCT and mapping['ci_commit'] == CI_HEAD and mapping['tracked_entries_checked'] == 11340
for path, digest in protected_before.items():
    assert sha(Path(path).read_bytes()) == digest

result = {
    'schema': 'f4_windows_independent_acceptance_review_v1', 'reviewed_utc': datetime.now(timezone.utc).isoformat(),
    'conclusion': 'accepted_windows_scope_no_blocking_defect',
    'product_head': PRODUCT, 'reported_git_dirty': False, 'current_checkout_head': current_head,
    'current_checkout_status': current_status, 'current_checkout_boundary': 'a9 is workflow-only CI child; report/registry/native/build keep actual product7d identity',
    'report': receipt(REPORT), 'baseline': receipt(BASELINE),
    'registry_snapshot': receipt(registry_snapshot), 'registry_source_git_blob': git('rev-parse', PRODUCT + ':scripts/run_m0_tests.py').decode().strip(),
    'registry_exact_order_script_layer_match': True, 'missing_or_extra_cases': [], 'duplicate_cases': [],
    'case_counts': dict(Counter(row['layer'] for row in cases)), 'passed': 152, 'failed': 0, 'skipped': 0,
    'assertions_executed_total': 49913, 'assert_sites_total': 4903, 'zero_assertion_cases': [],
    'all_152_case_exit_codes_zero': True, 'all_152_log_raw_sha_lf_utf8_verified': True,
    'all_152_last_assert_markers_match': True, 'exact_case_log_file_set': True,
    'assert_probe': 'settrace_assert_lines_v3', 'digest': 'sha256_raw_bytes_lf_v2',
    'current_source_fingerprint': report['source_fingerprint'], 'current_tests_fingerprint': report['tests_content_fingerprint'],
    'fingerprints_recomputed_without_running_tests': True, 'required_tracked_sources_present': True,
    'baseline_comparison': {'baseline_cases': 143, 'baseline_assertions': 48511, 'current_assertions': 49913,
                            'delta_total': 1402, 'all_original_cases_retained': True, 'per_case_regressions': [],
                            'new_cases': new_names, 'comparisons': comparisons},
    'cases': cases, 'independent_evidence_gates': gates,
    'binding_runtime': {'identity': binding_identity, 'operations': binding_operations, 'assertions': 8, 'exit_code': 0},
    'root_actual_runner_completion': {'acceptance_receipt': receipt(ROOT_ACCEPTANCE), 'runner_log': receipt(RUNNER_LOG),
                                      'root_gate_log': receipt(ROOT_GATE), 'session_id': 16898, 'actual_exit_code': 0,
                                      'attribution': 'Actual outer process exit is recorded by parent from original session; this independent review verifies its persisted receipt and matching original completion log, not a new wait of that already-ended session.',
                                      'all_152_runner_pass_lines_match_report': True},
    'native_scope': {'review': receipt(OUT / 'f4-native-7d718d0-independent-final-review.json'),
                     'unique_states': 13, 'images_actually_reviewed': 19, 'business_equal_input_pairs': 15,
                     'actual_process_exit': 0, 'session_id': 19960,
                     'scope': 'Previously independently accepted Windows native navigation; Esc timer/source-fixture/theme-menu boundaries retained, not reobserved by this report audit'},
    'limitations': ['No tests, backend, GUI, CI or desktop were rerun; only report gates read existing evidence.',
                    'Assertion counts are executed v3 assertion statements, not physical correctness or complete unexercised behavior coverage.',
                    'All report rows were checked against actual product7d registry, not just expected total152.',
                    'Optional PyVista coverage remains not_proven_by_this_runner as in original report.',
                    'Final CI a9 remains pending; Windows/native acceptance does not close F4 or substitute old CI reports.'],
    'original_evidence_unchanged': True, 'phase_closure': 'pending_final_ci_and_archive_review',
}
json_path = OUT / 'f4-windows-7d718d0-independent-review.json'
write_json(json_path, result)
md = f'''# F4 Windows 产品7d独立验收审查

**结论：Windows 范围通过独立审查，未发现阻塞缺陷。F4仍待最终CI与归档审查，不在此关闭。**

原报告：`out/verification/f4-release-windows/20261030-202435-a53c3ee6/report.json`，实际产品 `{PRODUCT}` / clean；SHA `{sha(REPORT.read_bytes())}`。当前工作树已是 `{CI_HEAD}` / clean，只增加Linux CI运行库安装；原报告、构建、原生和本次Registry均保持7d身份，没有改写为a9。

## 完整清单、断言与原字节

- 从 `git show 7d:scripts/run_m0_tests.py` 直接解析152项Registry，与报告逐项顺序、name、script、layer一致，无缺失/重复/额外项。分层28 static、44 GUI、59 backend、21 integration。
- 152 PASS、0 FAIL、0 SKIP；每例exit0且断言≥1。全部152份本地日志UTF-8/LF原字节SHA匹配，每份最终 `G4USIM_ASSERTS` 与报告一致；目录日志集合正好等于清单。
- 实际断言逐项和 **49,913**；152例均有计数，无零断言。静态assert站点总数4,903亦逐脚本复核，但没有把静态站点数当实际执行数。
- source/tests fingerprint只读重算一致；受跟踪源码门禁通过。9个新增项明确列在JSON，未用新增断言掩盖旧例下降。
- Qt绑定专项实物记录Windows Python3.11.9 / PySide6=shiboken6=Qt6.11.1；四项100次调用的None引用delta均0，8断言、正常退出。原Inspect45、Run Inputs103、Layout257均完整保留。

## F1同口径基线

F1原件143例、48,511个 `settrace_assert_lines_v3` 断言，本轮同probe为49,913（+1,402）。143旧例全部仍在，逐例无下降。独立执行现有严格证据门禁两次：当前报告+F1比较 exit0；F1原件自身含日志SHA检查 exit0。仅读取已存在证据，**未重跑全量或任何测试用例**。命令、原始门禁输出与SHA见JSON。

## 正常完成与原生范围

root从原session16898确认实际进程exit0；持久化acceptance收据、runner日志及其152条PASS/终态汇总均独立对账，三个记录的报告/门禁/runner SHA一致。本审查没有重新等待已结束的父任务session；外层实际退出的直接观察归属root原会话，逐用例exit0及报告内容由本审查复核。

已通过的7d实窗仍是13态、19张实际查看截图、15对业务hash相等、session19960实际exit0。Windows报告与该原生审查对应同一产品/构建。Esc可能同时遇到高亮定时器、来源是独立解析器夹具、主题/语言菜单没有单独hash配对等边界保持，不因本轮自动通过而扩大。

## 后续

仅新增out审查文件；报告、152份日志、F1基线和root收据保持原字节。可接受Windows+原生这两部分；a9完整真实CI、混合HEAD归档门禁、归档前后独立审查和主负责人关闭决定仍待完成。计数不代表物理验证，optional PyVista仍保持原报告的not_proven。
'''
md_path = OUT / 'f4-windows-7d718d0-independent-review.md'
write_new(md_path, md.encode('utf-8'))

# Append-only v3 list: preserve existing 196 paths/order and all README indexes.
v2_path = OUT / 'f4-final-combined-include-file-argv-v2.json'
v2_raw = v2_path.read_bytes()
v2 = json.loads(v2_raw)
assert len(v2) == 392 and v2[::2] == ['--include-file'] * 196
new_sources = [ROOT_ACCEPTANCE, ROOT_GATE, RUNNER_LOG,
               OUT / 'f4-windows-7d718d0-independent-gate.log',
               OUT / 'f4-windows-f1-baseline-independent-gate.log', json_path, md_path, Path(__file__), registry_snapshot]
assert not set(map(str, new_sources)) & set(v2[1::2])
v3 = v2 + [item for path in new_sources for item in ('--include-file', str(path))]
assert v3[:len(v2)] == v2
v3_path = OUT / 'f4-final-combined-include-file-argv-v3.json'
write_json(v3_path, v3)
append_receipt = {'schema': 'f4_archive_append_only_inputs_v1', 'previous_argv': receipt(v2_path),
                  'new_argv': receipt(v3_path), 'previous_196_paths_and_order_unchanged': True,
                  'include_files_total': len(v3)//2,
                  'appended': [{'include_order': i, **receipt(path),
                                'archive_path': f'additional/{i}-{path.name}' + ('.txt' if path.suffix == '.md' else '')}
                               for i, path in enumerate(new_sources, 197)],
                  'windows_command_line_chars_excluding_other_args': len(subprocess.list2cmdline(v3)),
                  'launch_note': 'Read argv JSON inside one Python process and call helper.main with sys.argv; avoid Windows command-line length limit.',
                  'publication_performed': False}
write_json(OUT / 'f4-final-archive-append-v3-receipt.json', append_receipt)
assert v2_path.read_bytes() == v2_raw
for row in cases:
    assert sha(Path(row['raw_log']['path']).read_bytes()) == row['raw_log']['sha256']
for path, digest in protected_before.items():
    assert sha(Path(path).read_bytes()) == digest
print(json.dumps({'conclusion': result['conclusion'], 'cases': 152, 'assertions': 49913,
                  'baseline': 48511, 'baseline_regressions': 0, 'all_raw_logs_verified': 152,
                  'gate_exit_codes': [gate['exit_code'] for gate in gates], 'new_cases': new_names,
                  'review_json': str(json_path), 'review_md': str(md_path),
                  'v3_include_files': len(v3)//2, 'existing_196_preserved': True,
                  'phase': result['phase_closure']}, ensure_ascii=False, indent=2))
