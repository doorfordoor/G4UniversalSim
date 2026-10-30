"""Write independent review after actual view_image observation of all 19 images.

This is evidence bookkeeping, not automated vision or a second desktop run.
Original native artifacts are read-only; reports are exclusive new out files.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
COLLAB = ROOT / 'out/collab'
EVIDENCE = ROOT / 'out/verification/f4-visible-7d718d0'
HEAD = '7d718d038a00d89995ea773b4772764116b620c3'
EXE_SHA = '8055edd08ef07aa6eee7d710c8d360b83e8bec60cb410160f4b89aad61d6f25b'
HOST_SHA = 'aa59397f4711c17f7edcc9a39d927c9c4197e124d98ccafb58b8d1d886c11d6c'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def record(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}


def write_new(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


identity = load(EVIDENCE / 'identity.json')
state = load(EVIDENCE / 'state.json')
launcher = load(EVIDENCE / 'launcher.json')
host_exit = load(EVIDENCE / 'exit.json')
build = load(ROOT / 'out/verification/f4-build-7d718d0/receipt.json')
audit_path = COLLAB / 'f4-native-7d718d0-independent-event-audit.json'
audit = load(audit_path)
events = [json.loads(line) for line in (EVIDENCE / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
native_observations = [json.loads(line) for line in (EVIDENCE / 'native/observations.jsonl').read_text(encoding='utf-8').splitlines()]
assert audit['mechanical_checks_passed'] and not audit['failures']
assert identity['gui_head'] == build['commit'] == launcher['commit'] == HEAD
assert identity['gui_status'] == ''
assert identity['executable_sha256'] == build['exe_sha256'] == EXE_SHA == sha(Path(identity['executable']).read_bytes())
assert identity['host_sha256'] == launcher['host_sha256'] == HOST_SHA == sha((COLLAB / 'f4-visible-host-v2.py').read_bytes())
assert identity['capabilities']['build_git_commit'] == HEAD
assert identity['capabilities']['build_git_source_state'] == 'clean'
assert identity['capabilities'] == load(ROOT / 'out/verification/f4-build-7d718d0/capabilities.json')
assert identity['capabilities'] == load(EVIDENCE / 'backend-capabilities.stdout')
assert identity['capabilities']['source_fingerprint'] == build['source_fingerprint']
assert state['window_size'] == [1366, 768]
assert host_exit['exit_code'] == 0 and host_exit['close_requested'] and host_exit['event_loop_used']
assert launcher['process_exit_code'] == 0 and launcher['normal_completion'] and launcher['session_id'] == 19960
assert launcher['log_sha256'] == sha((COLLAB / 'f4-visible-host-7d718d0.log').read_bytes())
assert 'Traceback' not in (COLLAB / 'f4-visible-host-7d718d0.log').read_text()
assert 'F4 QA host exit 0' in (COLLAB / 'f4-visible-host-7d718d0.log').read_text()
current_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
current_status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
assert current_head == HEAD and current_status == ''
manifest = load(EVIDENCE / 'gui-file-hashes.json')
for relative, digest in manifest.items():
    assert sha((ROOT / relative).read_bytes().replace(b'\r\n', b'\n')) == digest
assert sha(json.dumps(manifest, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')) == identity['gui_files_sha256']
assert len(audit['matched_pairs']) == 15 and all(pair['model_unchanged'] for pair in audit['matched_pairs'])
assert not audit['discarded_callbacks'] and not audit['unmatched_before_sequences']
assert state['business_sha256'] == audit['matched_pairs'][-1]['business_sha256']
finished = next(row for row in events if row['kind'] == 'actual_backend_finished')
assert finished['exit_code'] == 1 and finished['exit_status'] == 0
assert finished['stderr_sha256'] == sha((EVIDENCE / 'inspect.stderr').read_bytes())
assert finished['stderr'] == (EVIDENCE / 'inspect.stderr').read_bytes().decode('utf-8', errors='replace')
assert not finished['runner_running'] and not finished['run_summary_files'] and finished['simulation_requested'] is False
assert list(Path(identity['inputs']).rglob('run_summary.txt')) == []
historical_source = Path(identity['inputs']) / 'standalone-source-audit.ini'
assert 'mystery' not in historical_source.read_text(encoding='utf-8')
assert historical_source.read_text(encoding='utf-8').startswith('# changed after the actual parser read')

# Authored from the reviewer's actual tool-rendered image observations, not from
# the host's claims or root's note strings. Every image was separately opened.
seen = [
    ('01-energy-before', 'energy', '浅色配置页显示 energy 错误的列表与原文；Locate 可用，Source 灰显，未先跳转。', 'pass'),
    ('02-energy-highlight', 'energy', 'Run Config / Source 已打开；invalid-energy 字段完整可见，绿边框和文本光标可见。', 'pass'),
    ('03-energy-after-escape', 'energy', '同一输入仍为 invalid-energy，边框恢复细线；不将此图单独归因为 Esc，定时器也可能已清除高亮。', 'pass_with_caveat'),
    ('04-geometry-cell', 'geometry', '几何表第三行的 size/parameters=bad 完整可见并选中；不是旧轮白色空区域。名称列横向在视口外，重名身份结合模型/事件 cell[2,6] 核对。', 'pass'),
    ('05-material-density', 'material', '所选材料详情显示 SameMaterial、density=bad 和启用状态；目标输入可见。第二个同名对象身份由 row=1 事件与夹具确定，不从名称猜测。', 'pass'),
    ('06-layer-thickness', 'layer', 'Second 层详情的 thickness=bad 完整可见并高亮；G4_Si、启用及其他字段保留。', 'pass'),
    ('07-boolean-operation', 'boolean', '布尔表可见 Sensor / index=2 / operation=invalid-operation；operation 单元格被选中，表格可见。', 'pass'),
    ('08-stale-report', 'stale', '原 source 错误仍保留；输入已变化、诊断已过期的警告可读，Locate 与 Source 均灰显；重新校验仍可用。', 'pass'),
    ('09-current-source', 'source', '运行页源查看器显示五行真实文本及选中的 mystery=bad；标明行5、快照一致和 source_only。底部 QA 提示明确是独立源文件审计夹具。', 'pass'),
    ('10-historical-source', 'history', '查看器仍显示记录时 mystery=bad / 行5，并明确警告正在显示记录时的源文本快照、当前文件已改变或不可用。', 'pass'),
    ('11-project-crosspage', 'project', 'Project 页空的可执行程序输入框已聚焦并绿框标记，下方缺少路径错误仍存在；没有自动填值。', 'pass'),
    ('12-scenario-advanced', 'scenario', '场景高级字段勾选并展开，已滚到孔隙率输入2，目标字段完整可见且高亮。', 'pass'),
    ('13-wizard-prior-page', 'wizard', '向导位于材料和几何页，空材料选择框完整可见并高亮；世界材料、厚度、横向尺寸仍显示。', 'pass'),
    ('14-scan-enter', 'scan', '扫描取值框获焦、高亮且仍为空，仅有占位提示；scan.values 错误及已定位 values、配置值未改变的状态可读。Enter 手势由原生动作记录和 KeyPress 旁证确定。', 'pass'),
    ('15-backend-raw-no-location', 'backend', '运行控制台显示未运行、后端错误和无可编辑位置；Locate/Source 灰显。详情在下方，另由图16观察。', 'pass'),
    ('16-backend-raw-detail', 'backend', '滚动后后端原始错误可读：子文件.mac 第2行 setdir 与显式 CLI 输出目录冲突；下方明确未提供结构化编辑位置，按钮仍灰显。', 'pass'),
    ('17-dark-backend', 'backend', '深色主题下原始错误、无位置说明及两禁用按钮仍可辨读；未把 raw 原文翻译重写。', 'pass'),
    ('18-english-dark-backend', 'backend', '英文深色下表头 Severity/Code/Location/Message、Locate field/View source 等控件已英文显示；生成时中文消息前缀及后端原文保留，Location unavailable 理由可读。', 'pass'),
    ('19-english-dark-energy-highlight', 'energy', '英文深色 Configuration/Run Config/Source 中 Energy=invalid-energy 完整可见、聚焦、高亮；这轮实际定位仍可用。', 'pass'),
]
assert len(seen) == 19 == len(native_observations) == launcher['completed_observation_files']
assert {row['name'] for row in native_observations} == {name for name, *_ in seen}
inventory = {Path(row['path']).name: row for row in audit['image_inventory']}
observations = []
for name, case, note, outcome in seen:
    path = EVIDENCE / 'native' / (name + '.jpg')
    item = record(path)
    assert item['sha256'] == inventory[path.name]['sha256']
    sidecar = load(EVIDENCE / 'native' / (name + '.json'))
    assert sidecar['image'] == path.name
    observations.append({**item, 'case': case, 'outcome': outcome, 'actual_image_observed': True,
                         'observation_method': 'tools.view_image returned image, directly inspected by independent agent',
                         'independent_observation': note, 'capture_sidecar': record(EVIDENCE / 'native' / (name + '.json'))})

old_geometry = load(ROOT / 'out/verification/f4-visible-5d6f008/launcher.json')
old_crash = load(ROOT / 'out/verification/f4-visible-096f4b3/launcher.json')
assert old_geometry['native_acceptance'] == 'failed_geometry_cell_not_visible'
assert old_crash['process_exit_code'] == -1073740791 and old_crash['normal_completion'] is False
original_files = [record(path) for path in sorted(EVIDENCE.rglob('*')) if path.is_file()]
result = {
    'schema': 'f4_native_independent_final_review_v1', 'reviewed_utc': datetime.now(timezone.utc).isoformat(),
    'reviewer': '/root/f4_acceptance_audit',
    'scope': 'Ended Windows native F4 diagnostic-navigation QA round, 13 synthetic states plus theme/language observations; independent read-only event/byte/source/image review',
    'conclusion': 'accepted_no_blocking_defect_found_within_reviewed_scope',
    'product_head': HEAD, 'product_clean_verified': True, 'backend_exe_sha256': EXE_SHA,
    'backend_build_git_commit': identity['capabilities']['build_git_commit'],
    'backend_source_fingerprint': identity['capabilities']['source_fingerprint'],
    'gui_manifest_files_checked': len(manifest), 'host_version': 2, 'host_sha256': HOST_SHA,
    'window_client_size': state['window_size'],
    'events': {'audit': record(audit_path), 'count': 48, 'unique_states': 13, 'prepared_states_total': 14,
               'matched_before_after_pairs': 15, 'all_business_hashes_equal': True,
               'completed_navigation_or_source_actions': 12, 'selection_only_pairs': 2, 'escape_related_pair': 1,
               'unmatched_or_ambiguous_pairs': 0, 'discarded_callbacks': 0,
               'final_business_hash_matches_last_after': True},
    'images': observations,
    'real_inspect': {'program': finished['program'], 'arguments': finished['arguments'],
                     'exit_code': 1, 'qprocess_exit_status': 'NormalExit', 'simulation_requested': False,
                     'runner_running': False, 'run_summary_count': 0, 'stderr': record(EVIDENCE / 'inspect.stderr'),
                     'raw_stderr_matches_recorded_process_receipt': True,
                     'gui_no_position_evidence': 'actual images 15-18 plus current product raw-diagnostic producer; final state JSON later belongs to energy',
                     'gui_exact_raw_bytes_boundary': 'Captured QProcess bytes are SHA verified. Original backend-state GUI record was not separately persisted; screenshot text and static producer corroborate display, not a fabricated saved GUI JSON equality assertion.'},
    'exit': {'host_requested_return': host_exit, 'independent_launcher': launcher,
             'launcher_log': record(COLLAB / 'f4-visible-host-7d718d0.log'),
             'launcher_log_sha_matches': True, 'actual_session_process_exit': 0, 'session_id': 19960,
             'no_traceback_in_process_log': True},
    'caveats': [
        '03 only observes a cleared highlight after an Esc-related input; elapsed highlight timer is a competing cause, so no exclusive Esc-clear claim.',
        'Current/history source states are an independent actual-parser fixture, not the current generated project config or evidence that a simulation consumed it.',
        'Image04 proves third-row size cell visible; names are offscreen horizontally. Exact repeated-name identity is established with row/cell events and fixture, not the rendered name alone.',
        'Source viewer content and warning are visually observed. Readonly widget enforcement is not established by a screenshot alone; existing product/regression checks own that property.',
        'Business equality covers the 15 recorded product input pairs and final unchanged state. Theme/language menu changes do not have separate observer pairs; images establish appearance and existing automated tests own strict identity invariance.',
        'The observer samples 80 ms after press. Its hashes are bounded completed-action evidence, not a universal transactional guarantee or all possible delayed effects.',
        'Stale/backend disabled navigation is a successful guard observation, not a fabricated successful navigation action.',
        'Native covers this Windows build/client size and selected light/dark Chinese/English states; not Linux native desktop, every theme/DPI/layout, all error types, simulation success or physical validation.',
        'Event parser intentionally remains mechanical-only. This separate review adds actual image observation; original receipts retain not_claimed/pending review wording.',
    ],
    'blocking_findings': [],
    'historical_failures_retained': {'5d6f008': old_geometry, '096f4b3': old_crash},
    'original_evidence_files': original_files,
    'original_evidence_modified_by_review': False,
    'desktop_control_or_backend_runs_performed_by_reviewer': False,
    'stage_closure': 'This accepts native review scope only; parent owns final automated matrix, archival review and phase closure.',
}
json_path = COLLAB / 'f4-native-7d718d0-independent-final-review.json'
write_new(json_path, (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

lines = ['# F4 7d718d0 Windows 原生独立最终审查', '',
         '**结论：通过本轮原生审查，已审范围内未发现阻塞缺陷。** 这是结束后的证据与实际图像独立复核，不代替父任务的完整自动矩阵和阶段关闭。', '',
         f'产品 `{HEAD}` clean；实际 Release/Geant4 11.3.2 exe SHA `{EXE_SHA}`；host v2 SHA `{HOST_SHA}`。构建收据、capabilities、当前 exe 字节、宿主字节、GUI 已跟踪文件清单均独立对账一致。客户端窗口尺寸 1366×768。', '',
         '48 个事件，13 个不同合成状态（energy 在英文深色下再次准备，共14次准备），15 对完整 before/after，全部业务 hash 相等、无歧义/未配对/丢弃；其中12次完成定位或查看源，2次仅选行，1次 Esc 相关输入。退出时业务 hash 仍与最后 after 相等。', '',
         '真实 QProcess `--inspect-run` 返回正常非零拒绝（exit=1，NormalExit），256 字节原始 stderr 与收据 SHA 相符；CLI 输出锁冲突未被转换为猜测的 GUI 位置。runner 未启动，夹具中无 run_summary。host exit.json 的 requested return=0 与 session19960 独立 launcher 的实际进程退出0/normal_completion=true 分开核对；413字节进程日志 SHA 匹配，无 traceback。', '',
         '## 实际图像观察', '',
         '下列19张 JPG 均通过 `tools.view_image` 打开并直接观察，未以截图文件名、root观察文字、UIA或自动状态替代。每张图片及其原生捕获 sidecar 的 SHA 已记录在同名 JSON 报告中。', '',
         '| 图像 | 独立观察 | 结论 |', '| --- | --- | --- |']
for name, case, note, outcome in seen:
    lines.append(f'| `{name}.jpg` | {note} | {"通过（有归因边界）" if outcome == "pass_with_caveat" else "通过"} |')
lines.extend(['', '## 范围与边界', ''])
for caveat in result['caveats']:
    lines.append('- ' + caveat)
lines.extend(['', '两轮历史失败仍原样保留：5d6f008 为几何目标实际不可见，096f4b3 为 QA host 异常退出 -1073740791。本轮成功没有追改其状态。当前原件中的 pending independent review/not_claimed 仍是生成时状态，不追改；本文件是后续独立审查。', '',
              '机械审查：`out/collab/f4-native-7d718d0-independent-event-audit.json`。完整独立图像、身份、退出及原件 SHA 清单：`out/collab/f4-native-7d718d0-independent-final-review.json`。', '',
              '本审查只读原证据、产品与旧失败记录；仅写 out 新报告。未操作桌面、未重跑后端、未修改产品或原证据。'])
md_path = COLLAB / 'f4-native-7d718d0-independent-final-review.md'
write_new(md_path, ('\n'.join(lines) + '\n').encode('utf-8'))
for item in original_files:
    assert sha(Path(item['path']).read_bytes()) == item['sha256'], item['path']
print(json.dumps({'conclusion': result['conclusion'], 'images_actually_observed': len(observations),
                  'business_equal_pairs': 15, 'original_files_unchanged': len(original_files),
                  'json': record(json_path), 'markdown': record(md_path)}, ensure_ascii=False, indent=2))
