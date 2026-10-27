# 阶段 1 测试平台证据（2026-10-28）

本目录保存阶段 1.4（报告 v2：断言级证据、测试内容指纹、CI skip 当失败）的完整回归报告副本。
`out/` 与 `build*/` 被 `.gitignore` 忽略，原始报告不可复核，因此把关键文件复制进来作为可 review 的验收记录。
本轮改动尚未提交为最终提交；报告记录的 `git_head` 是改动前的 `c80a9cf`，`git_dirty=true` 表示工作区包含本轮改动。

## 内容

| 文件 | 说明 |
| --- | --- |
| `report.json` | 统一测试平台 `--profile all --require-tracked-sources --fail-on-skip` 报告（`version: 2`），**78 PASS / 0 FAIL / 0 SKIP** |
| `logs/` | 同一轮 78 个逐用例日志（原样复制；每个用例的 `G4USIM_ASSERTS=<n>` marker 在日志末尾） |

## 报告事实（report.json 实测值）

- `schema=G4UniversalSimM0TestReport`、`version=2`、`profile=all`、`assert_probe=settrace_assert_lines_v1`
- `platform=Windows-10-10.0.26200-SP0`、`python=3.11.9`
- `git_head=c80a9cf2906d79bd0d5d6076042033df2fc3f2ce`、`git_dirty=true`（工作区包含本轮改动，运行时源码与提交前的差距仅本轮修复）
- `source_fingerprint=ba493e735b11ca414fa63bbd9d5c219766a5bb60c838482fa69a884cef558d93`（exe 内嵌指纹与此一致）
- `tests_content_fingerprint=8438d98fef5aa67e1000879277c5a204dfcb6ce07bcad7686cc68a65d08dece5`（scripts/tools/gui smoke/gui 包/config/scenarios/schema/macros/test，哈希前归一 CRLF）
- `tracked_source_gate=pass`、`untracked_source_files=[]`
- `backend_provenance=source_sha256_manifest_matches_executable`、`merge_provenance=source_sha256_matches_executable`
- 分层：static 5 / gui 26 / backend 33 / integration 14 = 78，全部 `pass`
- 断言证据：`assertions_executed_total=115305`、静态断言点 `assert_sites_total=2313`、78 个用例都报告了计数
- `skip_policy=failure`（本轮没有 skip；`--fail-on-skip` 已生效）

可执行文件 SHA-256（与上述源码指纹对应）：

- `build_vs2026/Release/G4UniversalSim.exe`：`c446ed5e4be6c0380cf80ebeaf9e6596cd8d0bba07b122080fa0a8c79be8d315`

## 9 个"零断言"用例（如实列出）

`gui_unsupported_features`、`benchmarks`、`unsupported_features`、`unconsumed_config`、`material_schema`、
`geometry_safety`、`gui_backend_agreement`、`gui_sketch_accuracy`、`config_schema` 报告了 `assertions_executed=0`。
它们的通过目前只代表进程退出码为 0，**不代表有断言级证据**；其中一部分脚本用 `raise`/`sys.exit` 表达失败，
探针看不见。把这些脚本改成 `assert` 表达是后续工作，不得在文档中把它们当作"已验证全部断言"。

## 复现

```powershell
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage1-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage1-20261028
```

## 不证明什么

- 不证明 Linux/GitHub CI 上的 backend/integration 用例（CI 仍只跑 `--profile static` 与 `--profile gui`）。
- 不证明 9 个零断言用例的断言内容，见上。
- 不证明物理正确性：本报告只证明"在当前源码指纹、当前可执行文件、当前测试内容指纹下，78 个用例按各自脚本逻辑返回成功"。
