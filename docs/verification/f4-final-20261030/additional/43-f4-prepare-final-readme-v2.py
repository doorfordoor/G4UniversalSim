"""Prepare out-only F4 archive README/input candidates; never publish or close."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'out/collab'
PRODUCT = '7d718d038a00d89995ea773b4772764116b620c3'
CI_HEAD = 'a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9'
OLD_DRAFT = OUT / 'f4-final-readme-draft.md'
NEW_DRAFT = OUT / 'f4-final-readme-v2.md'
RAW_ROOT = OUT / 'f4-native-raw-archive-text-v2'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def save_json(path, value):
    save(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def token(name):
    return '{{' + name + '}}'


old_draft_sha = sha(OLD_DRAFT.read_bytes())
mapping = read(OUT / 'f4-ci-identity-map-a9ad09d/identity-map.json')
assert mapping['product_commit'] == PRODUCT and mapping['ci_commit'] == CI_HEAD
assert mapping['tracked_entries_checked'] == 11340 and mapping['exact_approved_addition_verified']
assert mapping['changed_files'] == ['.github/workflows/linux-geant4.yml']
assert mapping['all_other_tracked_entries_identical'] and mapping['direct_parent_verified']
deepseek = read(OUT / 'f4-deepseek-design.json')
assert deepseek['status'] == 'received' and deepseek['id'] == 'ed8eb74c-0550-4f78-8b5a-14655a61b685'
assert deepseek['requested_model'] == deepseek['returned_model'] == 'deepseek-flash'
native = read(OUT / 'f4-native-7d718d0-independent-final-review.json')
assert native['conclusion'] == 'accepted_no_blocking_defect_found_within_reviewed_scope'
assert len(native['images']) == 19 and native['events']['matched_before_after_pairs'] == 15

# Archive helper currently excludes these otherwise valid raw text suffixes.
# Explicit, byte-identical .txt copies preserve their evidence without changing
# original native files or silently broadening the helper's file policy.
RAW_ROOT.mkdir(exist_ok=False)
raw_rows = []
for name in ('f4-visible-5d6f008', 'f4-visible-096f4b3', 'f4-visible-7d718d0'):
    source_root = ROOT / 'out/verification' / name
    for path in sorted(source_root.rglob('*')):
        if path.is_file() and path.suffix in ('.jsonl', '.stdout', '.stderr'):
            raw = path.read_bytes()
            filename = name + '--' + '--'.join(path.relative_to(source_root).parts) + '.txt'
            target = RAW_ROOT / filename
            save(target, raw)
            assert target.read_bytes() == path.read_bytes() == raw
            raw_rows.append({'source_absolute_path': str(path), 'source_sha256': sha(raw), 'source_bytes': len(raw),
                             'copy_absolute_path': str(target), 'copy_sha256': sha(target.read_bytes()),
                             'copy_bytes': target.stat().st_size, 'suffix_reason': 'Explicit text presentation; raw original bytes unchanged',
                             'historical_failure': name != 'f4-visible-7d718d0'})
save_json(RAW_ROOT / 'raw-text-copy-receipt.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
           'scope': 'archive-safe text copies only; no reinterpretation of historical failure or native acceptance',
           'files': raw_rows, 'all_bytes_sha_equal': True})

relative_sources = [
    'out/verification/f4-build-7d718d0/receipt.json',
    'out/verification/f4-build-7d718d0/capabilities.json',
    'out/collab/f4-build-7d718d0.log',
    'out/collab/f4-configure-7d718d0.log',
    'out/collab/f4-visible-host.py',
    'out/collab/f4-visible-host-v2.py',
    'out/collab/f4-host-v2-delivery.json',
    'out/collab/f4-host-v2-delivery.md',
    'out/collab/test-f4-visible-host-v2.py',
    'out/collab/f4-v2-fusion-full-eventloop.log',
    'out/collab/f4-v2-fusion-full-eventloop-launcher.json',
    'out/collab/f4-v2-fusion-original-sequence.log',
    'out/collab/f4-v2-fusion-original-sequence-launcher.json',
    'out/collab/f4-audit-native-events.py',
    'out/collab/f4-native-7d718d0-independent-final-review.json',
    'out/collab/f4-native-7d718d0-independent-event-audit.json',
    'out/collab/f4-write-native-independent-final.py',
    'out/collab/f4-visible-host-7d718d0.log',
    'out/collab/f4-visible-host-096f4b3.log',
    'out/collab/f4-visible-host-native.log',
    'out/collab/f4-ci-identity-map-a9ad09d/identity-map.json',
    'out/collab/f4-ci-identity-map-a9ad09d/git-diff.patch',
    'out/collab/f4-ci-identity-map-a9ad09d/workflow-product.yml',
    'out/collab/f4-ci-identity-map-a9ad09d/workflow-ci.yml',
    'out/collab/f4-ci-identity-map-a9ad09d/product-tree.json',
    'out/collab/f4-ci-identity-map-a9ad09d/ci-tree.json',
    'out/collab/review-f4-ci-runtime-identity.py',
    'out/collab/f4-ci-runtime-commit.json',
    'out/collab/f4-ci-runtime-push.json',
    'out/collab/f4-linux-runtime-independent-review.json',
    'out/collab/f4-core-qt-final-review.md',
    'out/collab/f4-core-final-form-layout-review.md',
    'out/collab/f4-original-writer-independent-fix-review.md',
    'out/collab/f4-table-overlay-independent-review.md',
    'out/collab/f4-wizard-close-independent-review.md',
    'out/collab/f4-core-archive-review.md',
    'out/collab/f4-ci-7d718d0-failure-note.md',
    'out/collab/f4-freeze-windows-runner.log',
    'out/collab/f4-final-windows-runner.log',
    'out/collab/f4-qt-dependency-archive-input-review.json',
    'out/collab/f4-qt-dependency-collection-receipt.json',
    'out/collab/f4-verify-qt-evidence-archive-input.py',
    'out/collab/f4-prepare-final-readme-v2.py',
]
sources = [ROOT / relative for relative in relative_sources] + sorted(path for path in RAW_ROOT.iterdir() if path.is_file())
assert len(set(sources)) == len(sources)
for source in sources:
    assert source.is_file(), source
    assert source.resolve().is_relative_to((ROOT / 'out').resolve())
    assert source.suffix not in ('.whl', '.exe', '.dll', '.so', '.zip', '.part')
argv = [arg for path in sources for arg in ('--include-file', str(path))]
save_json(OUT / 'f4-final-small-include-file-argv-v2.json', argv)

def archived(path):
    path = Path(path)
    index = sources.index(path) + 1
    return f'additional/{index}-{path.name}' + ('.txt' if path.suffix == '.md' else '')

def a(relative):
    return archived(ROOT / relative)

final_events_copy = next(Path(row['copy_absolute_path']) for row in raw_rows
                         if row['source_absolute_path'] == str(ROOT / 'out/verification/f4-visible-7d718d0/events.jsonl'))
final_stderr_copy = next(Path(row['copy_absolute_path']) for row in raw_rows
                         if row['source_absolute_path'] == str(ROOT / 'out/verification/f4-visible-7d718d0/inspect.stderr'))
qt_argv = read(OUT / 'f4-qt-dependency-include-file-argv.json')
assert qt_argv[::2] == ['--include-file'] * 139
combined = argv + qt_argv
save_json(OUT / 'f4-final-combined-include-file-argv-v2.json', combined)
qt_paths = [Path(value) for value in qt_argv[1::2]]
qt_manifest = OUT / 'f4-qt-dependency-evidence-20261030/manifest.json'
qt_index = len(sources) + qt_paths.index(qt_manifest) + 1
qt_archive_link = f'additional/{qt_index}-manifest.json'

review_files = [OUT / 'f4-native-7d718d0-independent-final-review.md', OUT / 'f4-ci-only-acceptance-review.md']
bindings = {
    'readme_candidate': str(NEW_DRAFT), 'readme_unresolved_placeholders_forbid_publication': True,
    'expected_product_head': PRODUCT, 'required_ci_head': CI_HEAD,
    'mixed_head_helper_support': 'Current helper still has same-HEAD gate; parent must finish/review F4-only --ci-head / --identity-map support. Do not relabel original reports.',
    'identity_map_source': str(OUT / 'f4-ci-identity-map-a9ad09d/identity-map.json'),
    'visible_root_order': [str(ROOT / 'out/verification/f4-visible-7d718d0')],
    'review_file_order': [str(path) for path in review_files],
    'root_final_review': 'Append root final review as later --review-file, then resolve ROOT_FINAL_REVIEW_ARCHIVE_PATH from actual plan',
    'deepseek_response': str(OUT / 'f4-deepseek-design.json'),
    'deepseek_receipt': str(ROOT / 'docs/collab/outbox/20261030-deepseek-f4-design.md'),
    'historical_windows_roots_order': [str(ROOT / 'out/verification/f4-freeze-windows/20261030-192616-7a34aee1'),
                                      str(ROOT / 'out/verification/f4-final-windows/20261030-194526-3f060b82')],
    'historical_ci_roots_order': [str(ROOT / 'out/verification' / name) for name in ('f4-ci-5d6f008', 'f4-ci-096f4b3', 'f4-ci-7d718d0')],
    'historical_visible_roots_order': [str(ROOT / 'out/verification' / name) for name in ('f4-visible-5d6f008', 'f4-visible-096f4b3')],
    'include_order': 'small v2 list FIRST, unchanged Qt139 list SECOND; root may append further files. Reordering changes additional/ links.',
    'combined_argv': str(OUT / 'f4-final-combined-include-file-argv-v2.json'),
    'combined_include_files': len(combined)//2,
    'combined_windows_command_line_chars_excluding_main_args': len(subprocess.list2cmdline(combined)),
    'launch_note': 'Use one Python launcher which reads JSON and sets sys.argv before calling helper.main(); avoid flattening a long Windows process command line. This preparation does not execute helper or authorize phase closure.',
    'small_sources': [{'include_order': i, 'source_absolute_path': str(path), 'archive_path': archived(path),
                       'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())} for i, path in enumerate(sources, 1)],
}
save_json(OUT / 'f4-final-archive-bindings-v2.json', bindings)

content = f'''# F4 结构化诊断与定位：最终归档候选

**阶段状态：待最终验收与归档审查，尚未关闭。** 本候选替代旧待填草稿的用途，旧草稿及旧失败证据保持原字节。Windows 最终152项、CI子提交完整矩阵、复制前后审查均须填写下列明确占位符后由主负责人作关闭决定；原生通过不能单独关闭阶段。

## 范围与身份

实现稳定 code/identity、真实 editor/row/field/source 位置、共享问题列表、切页/展开/选行/滚动定位，以及旧快照失效和只读历史来源。覆盖 Configuration、Project/Run、Scenario、Wizard、Scan；保留旧报告与后端原文，无位置时明确拒绝猜测。定位不改配置，不自动修复；不扩大高级 GUI/物理功能。F5、K1、L1、Q2仍各自独立。

产品及 Windows/实窗绑定 **`{PRODUCT}`**；真实 CI 绑定 **`{CI_HEAD}`**。CI提交仅增加 Linux GUI 系统运行库安装的六行，是产品提交的直接子提交。已逐项核对 **11,340 个 Git 路径/mode/blob 条目**，除此 workflow 外全部相同。两边实际提交身份保留，不能改写为全平台同一 SHA。见[完整身份映射]({a('out/collab/f4-ci-identity-map-a9ad09d/identity-map.json')})和[独立裁决](review/2-f4-ci-only-acceptance-review.md.txt)。

[干净构建收据]({a('out/verification/f4-build-7d718d0/receipt.json')})：Release/MSVC、Geant4 11.3.2；exe SHA `8055edd08ef07aa6eee7d710c8d360b83e8bec60cb410160f4b89aad61d6f25b`。source fingerprint=`db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc`；tests fingerprint=`92c2c470814b0bea95d918e3393394a9c39ff5897fc3d57e64d33ef7e6174ddb`。指纹相同之外的 workflow/requirements 范围由上述完整 Git 树核对补足。

## 最终矩阵（待完整终态，不推算成功）

| 验收项 | 要求 | 实际终态 / 原件 |
| --- | --- | --- |
| Windows all，产品7d | 152项，28 static / 44 GUI / 59 backend / 21 integration | `{token('FINAL_WINDOWS_PASSED')}` / `{token('FINAL_WINDOWS_CASE_COUNT')}`；`{token('FINAL_WINDOWS_ASSERTIONS')}` 个v3断言；[报告](windows/final-1/report.json) |
| Linux Geant4 11.3.2，CI a9 | 全部152项、四profile | `{token('FINAL_LINUX_113_RESULT')}` |
| Linux Geant4 11.4.3，CI a9 | 全部152项、四profile | `{token('FINAL_LINUX_114_RESULT')}` |
| M0 Windows / Ubuntu，CI a9 | 各72项 | `{token('FINAL_M0_WINDOWS_RESULT')}` / `{token('FINAL_M0_UBUNTU_RESULT')}` |
| CI完整性 | 4官方artifact、12实际报告、448次用例执行 | `{token('FINAL_CI_ARTIFACT_REPORT_CASE_COUNTS')}`；[CI原始收据](ci/ci-evidence.json) |
| 严格门禁 | 无fail/skip/零断言，原日志SHA；同v3 F1逐例/总量及反例检查 | `{token('FINAL_STRICT_GATE_RESULT')}`；[F1原基线](baseline/1/report.json) |

Windows原始报告来源：`{token('FINAL_WINDOWS_SOURCE_REPORT_PATH')}`。CI原始收据来源：`{token('FINAL_CI_SOURCE_RECEIPT_PATH')}`。真实 run：[Linux {token('FINAL_LINUX_CI_RUN_ID')}](https://github.com/doorfordoor/G4UniversalSim/actions/runs/{token('FINAL_LINUX_CI_RUN_ID')})、[M0 {token('FINAL_M0_CI_RUN_ID')}](https://github.com/doorfordoor/G4UniversalSim/actions/runs/{token('FINAL_M0_CI_RUN_ID')})；最终结论 `{token('FINAL_CI_RUN_CONCLUSIONS')}`。不得拿旧7d的M0绿色填补a9缺失报告。

## 已确认的 Windows 原生验收

产品7d、[host v2身份](visible/1-f4-visible-7d718d0/identity.json)，13种合成状态、19张实际查看的JPG、15对输入前后业务hash一致（12次完成定位/查看源、2次选行、1次Esc相关输入）。几何第三行size、材料density、第二层thickness、布尔operation、场景高级字段、向导早期页和扫描Enter定位均准确可见；旧报告禁用定位，当前源/历史源说明分明。已观察浅色/深色、中英产品界面；[逐图独立审查](review/1-f4-native-7d718d0-independent-final-review.md.txt)包含适用边界。

[真实Inspect原文]({archived(final_stderr_copy)})对应正常非零拒绝 exit1，`--inspect-run` 不启动模拟、无run_summary，GUI未伪造位置。host requested return0与[launcher实际进程退出0](visible/1-f4-visible-7d718d0/launcher.json)分开确认，session19960；[事件原字节文本副本]({archived(final_events_copy)})和[独立机器审查]({a('out/collab/f4-native-7d718d0-independent-final-review.json')})可对账。原件中的pending/not_claimed是生成时历史状态，未追改。

03图不能排除高亮定时器同时清除，**不作Esc独占因果证明**；源文件两态是独立解析器夹具，不证明当前生成配置被执行。哈希证明限已记录输入；主题/语言菜单没有单独事件配对，其严格身份不变另由自动回归证明。本轮不是Linux原生桌面、所有DPI/主题或物理验证。

## DeepSeek 与依赖修复

实际设计咨询：`deepseek-flash`，response `ed8eb74c-0550-4f78-8b5a-14655a61b685`，2255 tokens（504/1751），UTC 10:27:53。[原始响应与调用收据](design/design-response.json)、[采纳与纠偏记录](design/design-receipt.md.txt)。角色是前端设计咨询，不宣称它实现产品或完成视觉验收。

Linux CPython3.11 + PySide6/shiboken6 6.12.0 的 None 引用负例与原CI异常退出均保留。采用 `PySide6>=6.11.1,<6.12`，两个稳定版本定向各413断言正常退出；移除全局conda库注入，a9补足干净Linux runner系统GUI库。见[依赖证据清单]({qt_archive_link})；此局部实验不替代最终矩阵。几何滚动缺陷按实际单元格修复，QA host Close异常仅修out辅助程序。

## 原样保留的历史轮次

| 原轮次 | 已发生事实 | 归档入口 |
| --- | --- | --- |
| Windows5d中止 | 92 PASS + 1 FAIL 后终止，无完整report；不补造后续结果 | [中止收据](history/windows-round-1-20261030-192616-7a34aee1/interruption.json) |
| Windows096旧完整轮 | 151/151，49,905个v3断言；属于旧候选，不能替换新152项 | [原报告](history/windows-round-2-20261030-194526-3f060b82/report.json) |
| CI5d | 12报告、444执行，440 pass/4 fail | [原汇总](history/ci-round-1-f4-ci-5d6f008/round-summary.json) |
| CI096 | 8报告、284执行，281 pass/3 fail；4个后续profile未执行 | [原汇总](history/ci-round-2-f4-ci-096f4b3/round-summary.json) |
| CI7d | 6报告、200执行，190 pass/10 fail；6个Linux profile未执行，缺libEGL | [原汇总](history/ci-round-3-f4-ci-7d718d0/round-summary.json) |
| 原生5d / 096 | 前者目标不可见、host退出0；后者QA host异常退出-1073740791 | [5d收据](history/visible-round-1-f4-visible-5d6f008/launcher.json)、[096收据](history/visible-round-2-f4-visible-096f4b3/launcher.json) |

最终4个官方ZIP按原始摘要验证，原容器保留在来源；历史CI容器作为失败历史保存。所有日志/JSON/图像按原字节归档，历史Markdown采用`.md.txt`呈现，后缀不符的历史图像不转码。事件和stderr的`.txt`副本仅加呈现后缀，原路径与SHA见[副本收据]({archived(RAW_ROOT / 'raw-text-copy-receipt.json')})。

## 关闭门槛（仍待主负责人）

混合产品/CI身份的F4归档helper必须独立复审，保留各自HEAD门禁，不放宽为任意混搭；当前同HEAD helper不能直接发布。补齐本页全部`{{{{...}}}}`占位符后，核查归档plan的实际路径、原件/副本SHA、完整成员集合、前后严格门禁和暂存区。[最终总审查]({token('ROOT_FINAL_REVIEW_ARCHIVE_PATH')})：`{token('FINAL_ARCHIVE_REVIEW_RESULT')}`；集成结果 `{token('FINAL_INTEGRATION_RESULT')}`；阶段关闭决定 `{token('FINAL_PHASE_CLOSURE_DECISION')}`。
'''
save(NEW_DRAFT, content.encode('utf-8'))
assert sha(OLD_DRAFT.read_bytes()) == old_draft_sha

# Verify byte-safe input policy and planned link destinations without invoking
# archive publication, any matrix, or the in-progress mixed-head helper.
spec = importlib.util.spec_from_file_location('f4_readme_input_policy', OUT / 'archive-f1.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
for source in sources + qt_paths + review_files:
    assert source.suffix in engine.TEXT_SUFFIXES | engine.EXPLICIT_SOURCE_SUFFIXES, source
    engine.check_text(source.read_bytes(), source)
for row in raw_rows:
    assert sha(Path(row['source_absolute_path']).read_bytes()) == row['source_sha256']
    assert sha(Path(row['copy_absolute_path']).read_bytes()) == row['source_sha256']
local_links = re.findall(r'\]\(([^)]+)\)', content)
unresolved = sorted(set(re.findall(r'\{\{([A-Z_0-9]+)\}\}', content)))
assert unresolved and all('\\' not in link for link in local_links)
receipt = {'created_utc': datetime.now(timezone.utc).isoformat(), 'candidate': str(NEW_DRAFT),
           'candidate_sha256': sha(NEW_DRAFT.read_bytes()), 'old_draft_sha256_unchanged': old_draft_sha,
           'small_include_files': len(sources), 'small_include_bytes': sum(path.stat().st_size for path in sources),
           'qt_include_files': 139, 'combined_include_files': len(combined)//2,
           'combined_windows_argv_chars': len(subprocess.list2cmdline(combined)),
           'raw_native_text_copies': len(raw_rows), 'unresolved_placeholders': unresolved,
           'all_selected_files_exist_and_pass_current_text_policy': True,
           'portable_link_policy': 'helper exact prefixes; small-first/Qt-second and two review-file order specified by bindings JSON. Final plan and links must still be verified.',
           'matrix_or_phase_acceptance': 'pending', 'published': False, 'tracked_files_modified': False}
save_json(OUT / 'f4-final-readme-v2-preparation-receipt.json', receipt)
print(json.dumps(receipt, ensure_ascii=False, indent=2))
