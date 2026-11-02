# J3 第一阶段证据：设计系统、皮肤注册表与可访问性下限

**状态：作者交付，待独立审查；J3 阶段未关闭。** 本目录只记录本阶段实际完成的范围与可复核证据，
不把"皮肤数量"或"截图"当成 J3 完成，也不代替任务书要求的实窗验收、对比度实测与独立复查。

## 交付范围（第一阶段，外观基础设施）

- `gui/g4usim_gui/core/theme.py` 重写为**设计系统 + 皮肤注册表**：`ThemeColors` 从 20 个颜色角色扩展到 28 个
  （新增 `canvas_alt`、`surface_hover`、`border_subtle`、`focus_ring`、`info`、`grid`、`shadow`、`sidebar_accent`），
  15 套皮肤（历史 B/K/C + 新增 12 套：纸墨、砂岩、苔原、石墨、霜蓝、高对比、午夜蓝、电路夜班、板岩、余烬、极光、夜视对比），
  每套含 6 色图表序列；`SPACE`/`RADIUS`/`CONTROL_HEIGHT`/`ICON_SIZE`/`MOTION_MS` 间距与圆角标尺。
- **可访问性归一化**：注册表构建时把 `text_muted`、`border_strong`、`accent_soft`、`selection`、
  `sidebar_selected`、`focus_ring` 向目标色混合到满足下限（正文与交互文字 4.5:1、控件边界与焦点 3:1、
  选中行 1.15:1），`on_color` 取最大对比文字色；`test_theme_registry` 以 23 项/皮肤复核，15/15 通过。
- **样式表分层**：历史 `_base_stylesheet` 逐字保留（旧对象名与测试选择器不变），新增 `_design_stylesheet`
  作为视觉层，用 `$token` 单遍替换；两层拼接，避免破坏既有契约。
- **外壳与持久化**：`View → Appearance` 菜单列出浅色/深色两组全部皮肤，勾选状态与
  `appearance/theme`、`appearance/light_skin`、`appearance/dark_skin` 同步，旧
  `appearance/light_palette` 作为 B/K 镜像兼容迁移；`app.py` 启动按记忆恢复；`_set_palette` 保留旧语义，
  选择皮肤会切到该皮肤自己的明暗组（否则菜单点了看不到变化）。
- **图标**：新增 `check` 图标用于复选框指示器（`gui/g4usim_gui/core/icons.py`）。
- **测试**：新增 static 用例 `theme_registry`（113 个断言点、实际执行 587 条）；注册后用例总数 215
  （static 49 / gui 71 / backend 63 / integration 32）。

## 证据

| 证据 | 结果 | 文件 |
|---|---|---|
| static profile | **49/49 pass**，5,615 条断言 | `static/report.json`、`static/logs/` |
| 主题相关 GUI 用例 | **4/4 pass**，284 条断言（j1_appearance 29、theme_response 55、main_window 51、workspace_layout 149） | `gui-theme/report.json`、`gui-theme/logs/` |
| 完整 GUI profile | **71/71 pass**，10,187 条断言 | `gui-profile/report.json`、`gui-profile/logs/` |

报告字段：`source_fingerprint=9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`、
`probe=settrace_assert_lines_v3`、`digest sha256_raw_bytes_lf_v2`；归档副本可直接被
`scripts/check_report_evidence.py --report-root docs/verification/j3-theme-v1-20261102/<name>` 复核。

## 截图（作者自查，非独立实窗验收）

`screens/` 含 B/K/C 三套旧外观在改动前（`before-*`，由 `625cfee2` 工作树渲染）与改动后
（`after-*`）的同一工程/同尺寸对照，页面为起始页与配置页。渲染方式：Windows 真实平台插件、
`MainWindow` 1560×980 逻辑尺寸、默认项目、125% 缩放下抓图；不经过 pixmap 合成，也不代表独立观察者复验。
新增 12 套皮肤仅作者离屏/实窗自查，尚未做任务书要求的对比度实测表、125%/150% 实窗与 Linux 桌面检查。

## 复现

```bat
gui\.venv\Scripts\python.exe -B scripts/run_m0_tests.py --profile static --report-root out/verification/j3-static
gui\.venv\Scripts\python.exe -B scripts/run_m0_tests.py --profile gui --case gui_j1_appearance --case gui_theme_response --case gui_main_window --case gui_workspace_layout --report-root out/verification/j3-gui-theme
gui\.venv\Scripts\python.exe -B scripts/check_report_evidence.py --report-root out/verification/j3-static
```

static 用例中的 C++ 编译/运行类用例需要 PATH 上有一个可运行的 C++17 编译器；本机 Git Bash 的
`D:\Program Files (x86)\Git\mingw64\bin` 会抢在 MSYS2 UCRT64 之前提供旧 `libstdc++-6.dll`，
先 `PATH=/d/msys64/ucrt64/bin:$PATH` 再跑（否则 7 个编译类用例以 `0xC0000139` 失败，与主题改动无关）。

## 不证明什么

- 不证明 J3 完成：实窗/DPI/Linux 桌面/独立复验、对比度实测表、性能基线与重复切换开销仍待做。
- 不证明新皮肤已被最终接受：名称、配色与视觉方向仍可由设计复核调整。
- 不改变任何物理、后端或支持等级。
