# J3 紧凑区间面板保留修复证据（2026-11-03）

本目录冻结「同一紧凑区间内调整窗口尺寸不得覆盖用户刚打开的可选 dock」这一修复的
测试证据。代码与永久回归见提交 `ce9b6283`（`fix(gui): keep a compact-band panel the user just opened`）。

## 复验反例

独立复验在 `docs/collab/reviews/20261103-j3-independent-retest-6b03317a.md` 记录：
窗口宽 1200 逻辑像素时用菜单打开 AI 面板，再把宽度拉到 1205（仍在紧凑区间），
面板被 `adapt_to_width()` 的下一次 resize 关掉。3D 预览走同一分支。

## 修复契约

- 用户通过 dock 的 `toggleViewAction`（即 `View → Panels` 的菜单项）打开的可选 dock 记为覆盖，
  在整个紧凑区间内跳过收起，任意小幅 resize 都不改变它；
- 未被用户显式打开的可选 dock（例如页面导航显露的 3D 预览）仍按紧凑规则收起；
- 离开紧凑区间时只恢复由本方法自动收起、且用户未覆盖的面板；
- `apply_preset()`/`restore()` 清空覆盖状态（预设/恢复是显式重置面板可见性）。

独立复现脚本（不入库，位于 `out/repro_compact.py`）在离屏环境执行：

```
compact after 1200: 1200 ai hidden: True preview hidden: True
after user opens ai: ai hidden: False
after 1205: 1205 ai hidden: False
REPRO OK: user-opened panels survive in-band resizes and band exit
```

## 报告事实

| profile | 结果 | 断言 | git head | git dirty | source fingerprint |
| --- | --- | --- | --- | --- | --- |
| static | 49/49 pass, 0 fail, 0 skip | 5615 | `ce9b6283b13a` | True | `9e40e889d49a4425` |
| gui | 76/76 pass, 0 fail, 0 skip | 10322 | `ce9b6283b13a` | True | `9e40e889d49a4425` |
| integration | 33/33 pass, 0 fail, 0 skip | 6843 | `ce9b6283b13a` | True | `9e40e889d49a4425` |

每个 profile 同名的 `report.json` 与 `logs/` 由 `scripts/run_m0_tests.py` 生成，
证据门禁：

```
python -B scripts/check_report_evidence.py --report-root docs/verification/j3-compact-panels-20261103/gui
```

（三份报告均已在归档副本上通过门禁。）

## 复现命令

```bash
export PATH=/d/msys64/ucrt64/bin:$PATH   # C++ 静态用例需要 ucrt64 的 libstdc++
export QT_QPA_PLATFORM=offscreen
gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui --require-tracked-sources --fail-on-skip
gui/.venv/Scripts/python.exe -B tools/test_assert_probe.py gui/smoke_tests/smoke_compact_panels.py
```

## 不证明什么

- 只证明该候选上本机 Windows 的分层测试结果；`git_dirty=true` 来自用户工作区里既有的
  `docs/verification/j2-f8-final-*` 长路径删除记录，不属于本候选的源码改动。
- 断言数是执行到的 assert 行数（探针 v3），不是独立命题数；不构成新物理基准。
- 不替代独立复验：真实窗口的 1200→1205 操作、125%/150% 与 Linux 实际桌面仍需复验者确认。
- 新增的 `gui_compact_panels` 只覆盖 AI/3D 两个可选 dock 与紧凑区间，不覆盖全部工作区布局。
