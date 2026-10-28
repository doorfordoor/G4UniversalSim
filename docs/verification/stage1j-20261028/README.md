# 阶段 1j 全量回归证据（2026-10-28）

本目录是 G4UniversalSim 统一测试平台的一次完整回归证据副本，随代码一起提交，用于外部复核“报告与日志未被篡改且自洽”。

## 报告事实

| 项 | 值 |
| --- | --- |
| 报告 | `report.json`（`version: 2`） |
| 运行命令 | `python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage1j-20261028` |
| 结果 | **81 pass / 0 fail / 0 skip** |
| 分层用例数 | static 7 / gui 26 / backend 34 / integration 14 |
| 已执行断言 | `assertions_executed_total = 116226`（静态断言点 2440 处） |
| 零断言用例 | `[]` |
| 断言探针 | `settrace_assert_lines_v2`（`sys.settrace` + `threading.settrace`，计数是“已执行 assert”的下界） |
| 日志摘要算法 | `sha256_raw_bytes_lf_v2`（对落盘 UTF-8/LF 字节计算 SHA-256） |
| 源码指纹 | `5bd97ec5e96e85f83b35b6d33d82ea12493e9d2eb4d78902c8d2ba5165d13206` |
| 测试/夹具内容指纹 | `637f211e5944ebdc726fac091b08bc6c52e3aaaef4a4ef8b2022e8c90a9b31e8` |
| 跟踪源门禁 | `tracked_source_gate = pass`，`untracked_source_files = []` |
| 后端来源 | `source_sha256_manifest_matches_executable` |
| 运行时的 git HEAD | `a5970ffddad0cdeadf4836258a518ad932909cc8`，`git_dirty = True`（运行发生在同一批改动“已暂存但未提交”时，提交内容与运行内容一致；`src/` 自 `a5970ff` 起未变，所以 `source_fingerprint` 与上次一致） |
| 后端构建身份 | MSVC 19.51.36246.0、Geant4 1132、MT、Release |
| 后端可执行文件 | `build_vs2026/Release/G4UniversalSim.exe`，SHA-256 `dd62fd8748fba532a12842881b0a680dff11816a6031724fd4caf9ecd83cde1f`（1734656 B） |

断言最多的用例：`gps_sources` 45645、`trajectories` 24448、`geometry_a5` 20357、`shielding_coating` 14386、`gui_source_glyphs` 3259、`run_summary` 2029。

## 复核方式

```bash
python -B scripts/check_report_evidence.py --report-root docs/verification/stage1j-20261028
```

本目录连同 `logs/`（81 个逐用例日志）一起入库：`.gitignore` 对 `docs/verification/**/logs/*.log` 开了例外，所以克隆仓库后上面这条命令仍能逐字节核对 `log_sha256`，不需要原始工作区。归档目录（`report.json` 直接在目录根）与运行目录（`<report-root>/<run-id>/report.json`）两种布局都由该命令支持。

门禁会逐用例核对：通过用例 `exit_code == 0` 且 `assertions_executed >= 1`、断言总数等于逐项求和、`cases_with_zero_assertions` 与实际一致、`log_sha256` 与本目录 `logs/` 下的日志字节一致、发布报告不含 fail/skip。

## 本轮新增/修复的内容

- Linux CI workflow 现在也跑 static 与 offscreen GUI（连同 backend/integration 共四个 profile），并新增 `if: failure()` 的公开注解步骤（`scripts/ci_annotate_failures.py`）与 static 用例 `ci_annotations`。
- 第 81 个用例 `ci_annotations` 覆盖注解格式、日志尾部、跳过用例的 warning、无报告时的容错。

## 这份证据不能证明什么

- 断言数是**已执行 `assert` 的下界**，不是覆盖率；它只说明这些判定真的执行过。
- 门禁只证明“报告与日志自洽且未被篡改”，不证明断言写得好，也不证明物理结果正确。
- 本报告是 Windows 本机（MSVC 19.51 + Geant4 11.3.2）的结果；Linux 结果见 `docs/verification/linux-wsl-20261028/` 与 GitHub Actions 的 `a5970ff` 运行。
- 未覆盖 `M0 static and GUI regression` workflow（仍被仓库设置禁用）、Geant4 11.2/11.4 矩阵与非 Ubuntu 发行版。
