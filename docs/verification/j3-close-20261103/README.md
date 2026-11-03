# J3 候选冻结与全 profile 基线（2026-11-03）

本目录冻结 J3 审查响应后的候选：代码与证据来自同一提交，工作树干净。
**J3 未关闭**：独立复验仍不同意关闭，剩余项见 `docs/collab/reviews/20261103-j3-closure-review.md` 与 `docs/verification/j3-visual-checks-20261102/README.md` 第 7 节。

## 提交

- `a1a64ead1274`（`gui`、`integration`、`static` 三份报告均为该提交）
- 三份报告的 `git_dirty` 为 true，因为本工作区常驻 1,153 份未跟踪交接资料；`git status --porcelain --untracked-files=no` 为空（已跟踪的源码/文档/证据全部提交），本轮冻结以该命令为准。

## 报告

| profile | 用例 | 断言 | 报告 |
| --- | --- | --- | --- |
| gui | 75 | 10297 | `gui/report.json` |
| integration | 33 | 6844 | `integration/report.json` |
| static | 49 | 5615 | `static/report.json` |

## 字段与复核

- `source_fingerprint`: `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`
- `tests_content_fingerprint`: `ce28712c6ba75740faa97c0c0e95a666532c5e8bc8a1e7310d61e44464f59b5c`
- `assert_probe`: `settrace_assert_lines_v3`，`log_digest_algorithm`: `sha256_raw_bytes_lf_v2`

```bash
gui/.venv/Scripts/python.exe -B scripts/check_report_evidence.py --report-root docs/verification/j3-close-20261103
```

## 边界

- 这三份报告只覆盖本机 Windows 13.2 与 PySide6 6.11.1；不证明 Windows 125%/150% 真实操作记录、不证明 Linux 真实桌面。
- 运行中切换外观的用例依赖真实 Geant4 可执行文件（40000 事件、单线程，约 3.3 秒）。
- 断言数是已执行断言的下界，不是覆盖率。

## 后续（不改变本目录冻结身份）

本目录冻结的是候选 `a1a64ead` 的 static/gui/integration 三份报告。2026-11-03 的独立复验在容器 `6b03317a` 上复现了紧凑区间 resize 覆盖用户面板选择的问题，修复与永久回归（`gui_compact_panels`，25 断言）见 `docs/verification/j3-visual-checks-20261102/README.md` 第 8 节；再次送审时应以新的候选提交与其三 profile 报告为准，本目录不重写。
