# 阶段 1b 测试平台证据（2026-10-28）

本目录保存阶段 1b（零断言用例迁移 + E2-S1 editor→writer 边界用例入库 + 线程感知探针）的完整回归报告副本。
`out/` 与 `build*/` 被 `.gitignore` 忽略，原始报告不可复核，因此把关键文件复制进来作为可 review 的验收记录。
报告记录的 `git_head` 是改动前的 `5c6ea1d`，`git_dirty=true` 表示工作区包含本轮改动（本轮尚未提交）。

## 内容

| 文件 | 说明 |
| --- | --- |
| `report.json` | 统一测试平台 `--profile all --require-tracked-sources --fail-on-skip` 报告（`version: 2`），**79 PASS / 0 FAIL / 0 SKIP** |
| `logs/` | 同一轮 79 个逐用例日志（原样复制；每个用例的 `G4USIM_ASSERTS=<n>` marker 在日志末尾） |

## 报告事实（report.json 实测值）

- `schema=G4UniversalSimM0TestReport`、`version=2`、`profile=all`、`assert_probe=settrace_assert_lines_v2`
- `platform=Windows-10-10.0.26200-SP0`、`python=3.11.9`
- `git_head=5c6ea1d1514a40f2eec6bb9f20c280209c3f9467`、`git_dirty=true`（工作区包含本轮改动）
- `source_fingerprint=ba493e735b11ca414fa63bbd9d5c219766a5bb60c838482fa69a884cef558d93`（exe 内嵌指纹与此一致）
- `tests_content_fingerprint=497be13f4d545909ee637f060add8959adebdceef08c0109dc6798efcb65593b`（scripts/tools/gui smoke/gui 包/config/scenarios/schema/macros/test，哈希前归一 CRLF）
- `tracked_source_gate=pass`、`untracked_source_files=[]`
- `backend_provenance=source_sha256_manifest_matches_executable`、`merge_provenance=source_sha256_matches_executable`
- 分层：static 6 / gui 26 / backend 33 / integration 14 = **79**，全部 `pass`
- 断言证据：`assertions_executed_total=116133`、静态断言点 `assert_sites_total=2387`、79 个用例都报告了计数，**`cases_with_zero_assertions=[]`**
- `skip_policy=failure`（本轮没有 skip；`--fail-on-skip` 已生效）

可执行文件 SHA-256（与上述源码指纹对应）：

- `build_vs2026/Release/G4UniversalSim.exe`：`c446ed5e4be6c0380cf80ebeaf9e6596cd8d0bba07b122080fa0a8c79be8d315`

## 本轮解决了什么

- 阶段 1.4 报告里 9 个 `assertions_executed=0` 的用例（`gui_unsupported_features`、`benchmarks`、
  `unsupported_features`、`unconsumed_config`、`material_schema`、`geometry_safety`、`gui_backend_agreement`、
  `gui_sketch_accuracy`、`config_schema`）已把**既有失败判定**改成 `assert` 表达，语义/容差/退出码未变，
  现在每个都报告非零断言数（`config_schema=303`、`geometry_safety=203`、`gui_backend_agreement=107`、
  `material_schema=85`、`gui_sketch_accuracy=56`、`unsupported_features=21`、`config_duplicate_declarations` 等见日志）。
- E2-S1 的六个 editor→writer 边界探针从被忽略的 `out/verification/e2-audit-20261027/writer_boundary_probe.py`
  提升为正式 static 用例 `scripts/test_writer_boundary.py`（`writer_boundary`，24 条断言：6 个拒绝状态 +
  2 个接受对照 + "不产生文件" 检查）。
- 探针升级为 `settrace_assert_lines_v2`：`sys.settrace` 之外再安装 `threading.settrace`，因此脚本自己启动的
  线程（例如 `ThreadPoolExecutor` worker）里执行的 `assert` 也计数；脚本运行前已存在的线程不计。
  `scripts/test_m0_runner.py` 增加对应回归（worker 3 次 + 主线程 1 次 = 4）。
- `scripts/run_benchmarks.py` 的断言放在 `write_report()` 之后做聚合判定：某个基准失败时仍会跑完全部基准、
  仍写出 `benchmark_report.json/md`，然后以 `AssertionError`（含失败条目）非零退出。

## 复现

```powershell
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage1c-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage1c-20261028
```

## 不证明什么

- 不证明 Linux/GitHub CI 上的 backend/integration 用例（CI 仍只跑 `--profile static` 与 `--profile gui`）。
- 断言数是**已执行 `assert` 的下界**（循环内 assert 每迭代计一次），不是覆盖率，也不证明断言本身覆盖了全部风险。
- 不证明物理正确性：本报告只证明"在当前源码指纹、当前可执行文件、当前测试内容指纹下，79 个用例按各自脚本逻辑返回成功"。
- `gui_sketch_accuracy` 的逐 fixture 判定在 worker 线程里以 `problems` 列表收集、在主线程用 assert 聚合，
  因此报告的断言数只反映聚合点，不等于逐体积比较次数（日志里有 130 个体积盒比较的计数）。
