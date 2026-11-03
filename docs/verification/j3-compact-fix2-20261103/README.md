# J3 紧凑区间面板保留：第二次复验修复证据（2026-11-03）

状态：**作者侧交付，待独立复验**。J3 未关闭。

## 1. 身份

| 项 | 值 |
| --- | --- |
| 产品提交 | `d4400b26901b64701ad6e93ea580c1148c56cb49`（`fix(gui): keep optional panels the user opened from every entry`） |
| 基线复验 | 第二次独立复验 `docs/collab/reviews/20261103-j3-independent-ce9b6283.md`（检出 `26cb37a5`，产品修复 `ce9b6283`） |
| source_fingerprint | `9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a` |
| tests_content_fingerprint | `117bad9f871f28b8e4af423db16d5f6b2f51a61261e6ba844a186a38f8b84659` |
| 后端可执行文件 | `build_vs2026/Release/G4UniversalSim.exe`，2,466,304 B，SHA-256 `18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837` |
| 平台 | Windows-10-10.0.26200-SP0，CPython 3.11.9，PySide6（GUI 虚拟环境） |

## 2. 修复范围

第二次复验确认菜单入口已修复，但指出另外两条正常用户入口会丢失面板可见性，并指出 `gui_theme_state_backend` 的断言入口计数在 33/32 之间漂移。

- 配置页 “Show 3D view” 按钮：现在调用 `WorkspaceLayout._show_preview_from_button`，除显示面板外把 `preview` 记为**用户显式覆盖**（`_optional_overrides`）。
- 恢复已保存布局：`restore()` 在恢复布局后按恢复出的可见性记录覆盖（不逐条触发 signal），因此恢复后紧接着的紧凑区间 resize 不再把面板收起；`reset()` 仍清空覆盖。
- 紧凑区间内，未被用户显式打开的可选 dock（页面导航自动显露的 AI/3D 预览）仍按旧契约收起；离开区间只恢复被自动收起的那些。
- `gui_theme_state_backend` 的运行中外观切换改为**固定 5 次**，不再依赖定时器次数；断言入口稳定为 15。

对应提交只包含 8 个文件（代码 1、测试 2、文档 5）：

```text
gui/g4usim_gui/window/workspace_layout.py
gui/smoke_tests/smoke_compact_panels.py
gui/smoke_tests/smoke_theme_state_backend.py
gui/AGENTS.md
CHANGELOG.md
STATUS.md
docs/agent-history.md
docs/verification/j3-visual-checks-20261102/README.md
```

## 3. 复验探针（使用审查者自己的脚本）

`probe/windows-probe.py` 是第二次复验提交的探针原文件（`docs/verification/j3-independent-ce9b6283/windows-probe.py`）的副本，未改动。用 GUI 虚拟环境、`QT_QPA_PLATFORM=windows`、`PYTHONPATH=gui;gui/smoke_tests` 在本候选上运行，完整输出见 `probe/observed.log`：

| 步骤 | 输出（AI, preview 的 isHidden；False = 可见） | 期望 | 结果 |
| --- | --- | --- | --- |
| menu-open 1200 | False False | 可见 | 通过 |
| menu-resize 1205 | False False | 可见 | 通过 |
| float-resize 1210（浮动 AI） | False False | 可见 | 通过 |
| wide 1420 | False False | 可见 | 通过 |
| 配置页按钮可见/可用 | True True | 可交互 | 通过 |
| button-open 1200 | True False | preview 可见 | 通过 |
| **button-resize 1205** | True False | preview 保持可见 | **通过（原反例）** |
| saved 1205 | False False | 保存时两者可见 | 通过 |
| restored 1205 | False False | 恢复后两者可见 | 通过 |
| **restored-resize 1211** | False False | 恢复效果保持 | **通过（原反例）** |

## 4. 三 profile 回归

| profile | 用例 | 断言入口 | 运行目录 |
| --- | --- | --- | --- |
| static | 49/49 通过 | 5,615 | `20261103-114621-939b8dbf` |
| gui | 76/76 通过 | 10,351 | `20261103-114956-cc2370e4` |
| integration | 33/33 通过 | 6,826 | `20261103-115820-37ca8b77` |

三份 `report.json` 与全部日志（49 + 76 + 33 个）在本目录 `static/`、`gui/`、`integration/` 下。归档副本逐份通过：

```bat
python -B scripts/check_report_evidence.py --report-root docs/verification/j3-compact-fix2-20261103\static
python -B scripts/check_report_evidence.py --report-root docs/verification/j3-compact-fix2-20261103\gui
python -B scripts/check_report_evidence.py --report-root docs/verification/j3-compact-fix2-20261103\integration
```

`assert_probe=settrace_assert_lines_v3`，`log_digest_algorithm=sha256_raw_bytes_lf_v2`，`tracked_source_gate=pass`。

## 5. 关于 `git_dirty=true` 与断言计数

- 三份报告的 `git_dirty` 均为 `true`。报告里的 `git_status_porcelain` 显示的是**用户工作区里既有的改动**：`docs/verification/j2-f8-final-20261102/` 下的长路径删除记录，以及一批未跟踪的 Astra 交接材料与 `docs/verification/independent-*-5465dbd-20261029/`。本轮提交未触碰这些路径；`git show --stat d4400b26` 只含上面第 2 节列出的 8 个文件。这一点与被审查的 `ce9b6283` 和更早的 `a1a64ead` 归档一致。
- 第二次复验注意到的 integration 断言 6844→6843（`gui_theme_state_backend` 33→32）：该用例在运行中按定时器切换外观，切换次数受收尾竞争影响，因此入口数不稳定。本轮把它改为固定 5 次切换，入口稳定为 15；这是让计数可比较，不是让模拟结果变化。旧报告 `docs/verification/j3-close-20261103/` 保持原样，没有重写。
- `merge_provenance` 仍提示 `mergeHistograms` 的源码指纹与工作区不同（需要重建）；这与既有归档相同，本候选没有改动合并器源码。

## 6. 不证明什么

- 不关闭 J3。第二次复验列出的视觉与跨平台缺口仍然存在：Windows 125%/150% 真实人工操作记录、Linux 实际桌面、非法草稿/诊断/结果/Agent 状态图、B/K/C 前后问题清单、实窗性能计时、Results 150% 横向滚动。
- 本证据只证明：本候选在紧凑区间内，菜单、配置页按钮、恢复布局三条入口打开的可选面板不被后续 resize 覆盖；以及三 profile 在本机复跑通过。
- 探针由作者运行，不能代替非作者独立复验；窗口操作由 Qt 驱动，不计作人工视觉签收。

## 7. 复现

```bat
set PATH=D:\msys64\ucrt64\bin;%PATH%
gui\.venv\Scripts\python.exe -B scripts\run_m0_tests.py --profile static --report-root out\verification\j3-fix2-static
set QT_QPA_PLATFORM=offscreen
gui\.venv\Scripts\python.exe -B scripts\run_m0_tests.py --profile gui --report-root out\verification\j3-fix2-gui
gui\.venv\Scripts\python.exe -B scripts\run_m0_tests.py --profile integration --report-root out\verification\j3-fix2-int
```

`PATH` 里先放 `D:\msys64\ucrt64\bin` 是因为本机 static 用例会用 g++ 编译测试夹具，Git 自带的 mingw64 DLL 会导致入口点错误（0xC0000139），这不是代码失败。
