# 阶段 2B 收尾 + F6 `sequence` 证据（2026-10-28）

本目录是 F6 进度协议 `sequence` 切片之后的完整回归证据，Windows 本机运行。
报告是 `version: 2` 证据：逐用例断言数、`log_sha256`（按落盘字节）、源码指纹与测试/夹具内容指纹。

## 报告事实

| 项目 | 值 |
| --- | --- |
| 用例 | 87 PASS / 0 FAIL / 0 SKIP（static 10 / gui 27 / backend 35 / integration 15） |
| 已执行断言 | 116681（`assert_sites_total` 2702，`cases_with_zero_assertions` 为空） |
| profile / 版本 | `all` / `version: 2` |
| 断言探针 | `settrace_assert_lines_v2` |
| 日志摘要 | `sha256_raw_bytes_lf_v2`（对落盘 UTF-8/LF 字节计算） |
| 源码指纹 | `68df2107a1faa01d8e3a244acfa04446e517424ab4a8813c72ec6d0087a489d6` |
| 测试/夹具指纹 | `a35868062f7fac03d1286b8f1d63c6aef91baf00ebc7a0875e6ae78b85d3c5a1` |
| 运行提交 | `git_head=5d6b94e`、`git_dirty=true`（本批改动运行前未提交，`src/` 相对 `5d6b94e` 只有 `src/Actions/RunProgress.cc` 的 sequence 改动） |
| 后端 | `build_vs2026/Release/G4UniversalSim.exe`，1734656 B，SHA-256 `272c015a1f695d533ed91c8c209c56eec3edd46ac323c0aaf11c9764c1f16a76`，MSVC 19.51.36246.0 + Geant4 1132 + MT |
| 门禁 | `python -B scripts/check_report_evidence.py --report-root docs/verification/stage2b-f6-20261028` → OK |

## 本次切片改了什么

- `src/Actions/RunProgress.cc`：`State` 增加进程级 `long long sequence`，只在 telemetry mutex 下自增；`Emit()` 在 `run_id` 之后写 `"sequence":<n>`；`Begin()` 不重置它，同一进程内跨 run 单调递增。
- `gui/g4usim_gui/core/run_progress.py`：`ProgressParser` 记录 `_last_sequence`；字段出现时必须是非负整数且严格递增，重复或回退的行丢弃；字段缺失时保持旧行为（旧后端仍可解析）。
- 回归增强：`gui/smoke_tests/smoke_live_progress.py` 增加重复/回退/非整数/缺失四类断言（80 条断言）；`scripts/test_live_progress.py` 的 `validate()` 断言真实消息严格递增且跨 run 单调（198 条断言）。

## 复现

```bash
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage2b-f6-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage2b-f6-20261028
```

## 不证明什么

- 只覆盖本机 Windows + MSVC 构建；Linux 侧同源修复的 CI 结果另见 `docs/Linux构建与验证.md` 与 Actions run 记录。
- 断言数是"已执行断言"的下界，不是覆盖率；`sequence` 只是消息顺序证据，不证明物理历史完整、不改变成功判定。
- 没有新增物理能力、性能结论或跨 Geant4 版本兼容性结论（11.2/11.4 矩阵仍未做）。
