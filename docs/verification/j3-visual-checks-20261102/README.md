# J3 视觉校验记录（作者侧，2026-11-02）

状态：作者交付，**未独立验收**；J3 仍未关闭。

## 1. 对比度实测表

方法：`out/contrast_table.py`（本地脚本，不进仓库）读取 `gui/g4usim_gui/core/theme.py` 的 15 个
皮肤，用 WCAG 2.x 相对亮度公式计算每对前景/背景的对比度。阈值：正文与可交互控件 ≥ 4.5:1，
非文本边界与焦点环 ≥ 3:1，侧栏选中指示 ≥ 1.15:1（只作位置指示，不作正文）。

| 皮肤 | ID | 明暗 | 正文/画布 | 次要文字/画布 | 强调/画布 | 强调上的文字 | 边界/表面 | 焦点环/画布 | 侧栏文字/侧栏 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B · 晶格 | `B` | light | 14.76 | 5.64 | 4.95 | 4.95 | 3.02 | 5.18 | 16.18 |
| K · 软件 | `K` | light | 14.63 | 5.55 | 4.76 | 5.02 | 3.08 | 4.92 | 16.18 |
| 纸墨 | `paper` | light | 13.27 | 5.33 | 5.96 | 6.82 | 3.10 | 5.96 | 14.29 |
| 砂岩 | `sandstone` | light | 12.84 | 5.34 | 4.78 | 5.47 | 3.11 | 4.78 | 13.99 |
| 苔原 | `botanical` | light | 13.44 | 5.22 | 5.74 | 6.37 | 3.13 | 5.74 | 14.81 |
| 石墨 | `graphite` | light | 15.60 | 5.51 | 7.10 | 7.89 | 3.08 | 7.10 | 15.74 |
| 霜蓝 | `frost` | light | 14.31 | 5.48 | 4.92 | 5.51 | 3.11 | 4.92 | 14.78 |
| 高对比 | `contrast_light` | light | 19.60 | 10.21 | 6.39 | 6.39 | 5.77 | 6.39 | 21.00 |
| C · 夜读 | `C` | dark | 12.92 | 6.30 | 9.90 | 10.47 | 3.10 | 8.77 | 17.34 |
| 午夜蓝 | `midnight` | dark | 16.04 | 7.40 | 6.88 | 6.94 | 3.03 | 8.80 | 16.94 |
| 电路夜班 | `circuit` | dark | 16.30 | 8.27 | 9.96 | 9.83 | 3.05 | 12.56 | 17.06 |
| 板岩 | `slate` | dark | 14.89 | 7.02 | 7.98 | 8.38 | 3.01 | 10.29 | 16.70 |
| 余烬 | `ember` | dark | 15.49 | 7.78 | 8.52 | 8.66 | 3.16 | 10.86 | 16.64 |
| 极光 | `aurora` | dark | 16.11 | 7.80 | 6.91 | 6.87 | 3.13 | 10.06 | 17.04 |
| 夜视对比 | `contrast_dark` | dark | 21.00 | 14.07 | 10.07 | 9.07 | 7.56 | 12.89 | 21.00 |

17 项组合 × 15 皮肤全部达到上述阈值；最低值为 `aurora` 的侧栏选中指示 1.16:1（阈值 1.15，仅指示
位置）。表由计算得出，不替代人工视觉审查。

## 2. 窄窗口与高 DPI（紧凑布局）

- 125%：`QT_SCALE_FACTOR=1.25`，1560×980 逻辑窗口，抓图 1950×1225；配置页三个面板完整，
  无横向裁剪（`screens/scale-125-paper-configuration.png`）。
- 150% + 1280×800 逻辑窗口：曾因工作区最小宽度约 1600 逻辑像素被屏幕裁掉；现在
  `WorkspaceLayout.adapt_to_width()` 在宽度 < 1400 时进入紧凑模式——隐藏 AI 与 3D 两个
  可选 dock（可从 View → Panels 与命令面板重新打开）、收窄 setup 面板与配置分栏、
  调用 `PyVistaPreviewWidget.set_compact()`；材料编辑器按钮改 2×2 与 3+2 排布，
  文件树、数据集下拉、历史表格最小宽度下调。探针测量窗口最小宽度由约 1600 降到 760。
  抓图 `screens/narrow-1180-paper-configuration.png`（1180×760 @1.5，物理 2213×1425）。
- 仍存在：setup 面板在 240 宽时路径行需要水平滚动；紧凑模式下不自动打开 3D 面板，也没有
  针对窄屏的纵向重排（例如把 setup 面板放到编辑器上方）。这些是后续工作，不算已完成。
- 回归：`gui_config_editors`、`gui_workspace_layout`、`gui_main_window`、`gui_3d_view`、
  `gui_model_tree`、`gui_help_menu`（6/6、328 断言）与 `gui_output`、`gui_history`、
  `gui_plots`、`gui_scans`（4/4、117 断言）通过；报告副本见 `compact-editors/`、
  `compact-output/`。

## 3. 主题切换性能（同机、同方法对比父版）

- 当前 HEAD：6 皮肤 × 5 轮，**中位 765.1 ms、最差 891.1 ms**。
- 父版 `625cfee2` 工作树：B/K/C × 5 轮，**中位 752.5 ms、最差 860.2 ms**。
- 倍率约 **1.02×（中位）/ 1.04×（最差）**，低于任务书 1.20× 调查线；方法为 offscreen
  预热窗口后调用 `_set_skin`/`_set_theme` 并跑一次事件循环，包含样式应用与一次绘制。
  脚本 `out/theme_perf.py`、`out/theme_perf_before.py`（本地，不进仓库），数字见
  `theme-switch-latency.txt`。
- 任务书记录的旧修订 0.61/0.65 s 是包含首帧整树处理的另一种口径，不能与本表直接比较。

## 4. Linux 代表性原生渲染（WSLg X11/xcb）

- 环境：WSL2 Ubuntu 24.04 + WSLg，`DISPLAY=:0`，`QT_QPA_PLATFORM=xcb`。系统缺
  `libxcb-cursor0`，用 `apt-get download libxcb-cursor0` + `dpkg -x` 解到 `$HOME/g4gui-libs`
  并以 `LD_LIBRARY_PATH` 注入（不改系统）。
- 抓图：`screens/linux-x11-paper-page2.png`、`screens/linux-x11-midnight-page2.png`、
  `screens/linux-x11-paper-zh-page2.png`，1560×980。
- 观察：皮肤、导航分组、页头、材料编辑器与 zh_CN 中文界面正常；WSL 的 venv 没有 pyvista，
  3D 面板显示明确回退说明（“No module named 'pyvista' … Install with:
  pip install -r requirements-3d.txt”）。
- 限制：这是 WSLg 的 X11 窗口渲染，不是完整桌面会话（没有窗口管理器装饰），不能替代
  Linux 真实桌面验收；中文界面下 matplotlib 图表仍有缺字形警告（图表字体，不是控件文本）。

## 5. 状态不串改（主题切换）

- 新用例 `gui/smoke_tests/smoke_theme_state.py`（`gui_theme_state`）：打开演示项目后记录运行名输入、输出文件树选中行、当前页面与工作区标签索引，然后依次切到纸墨、午夜蓝、B；断言这些状态逐项保持、外观偏好只写入 QSettings（`appearance/light_skin`、`appearance/dark_skin`）、`current_skin()` 与状态栏显示一致。
- 证据：`state-preservation/`（5 个 GUI 用例，188 断言，含 `gui_theme_state`/`gui_theme_response`/`gui_j1_appearance`/`gui_main_window`/`gui_command_palette`）。
- 未覆盖：运行中任务与 K1 输入资格在切皮肤时的表现、Undo/Redo 栈内容、非法草稿的恢复提示；这些仍属 J3 验收要求里的未完成项，不能把本用例当成全部“状态不串改”验收。

## 6. 复现与边界

- 对比度：`gui/.venv/Scripts/python.exe -B out/contrast_table.py`（本地脚本）。
- 性能：`gui/.venv/Scripts/python.exe -B out/theme_perf.py`；父版在
  `git worktree add ../G4UniversalSim-before 625cfee2` 里跑同构脚本。
- 窄窗口：`SHOTS_DIR=j3-narrow2 SHOT_SIZE=1180x760 QT_SCALE_FACTOR=1.5
  QT_QPA_PLATFORM=windows gui/.venv/Scripts/python.exe -B out/skin_shots2.py "paper" "2" "pa"`。
- Linux：`wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Geant4/G4UniversalSim &&
  LD_LIBRARY_PATH=$HOME/g4gui-libs/usr/lib/x86_64-linux-gnu /home/u123/venv/bin/python -B
  out/linux_shot.py'`。
- **不证明什么**：全部为作者侧自测，没有独立验收；J3 仍未关闭（Linux 真实桌面与独立复验
  未完成）；性能数字只代表本机；截图来自作者运行，不是用户操作记录。

## 7. 独立审查与修正（2026-11-03）

独立复验 `docs/collab/reviews/20261103-j3-closure-review.md` **不同意关闭 J3**，记为“实现基本完成、验收证据未完成”。本节更正前文不再成立的陈述，并记录回应。

- **紧凑布局**：宽度 <1400 逻辑像素时隐藏的是 AI 面板与 3D 预览两个**可选** dock；配置编辑器保留。3D 预览可从 View → Panels 或“按当前页面适配工作区”重新打开。前文“三个面板完整”不成立。
- **dock 重开入口**：菜单是 View → Panels，不是命令面板；命令面板只含页面/动作/外观，没有 dock 开关。
- **窗口最小宽**：约 760 是 J3 之前既有 `setMinimumSize` 值，不是本阶段成果；150% + 1280 逻辑宽下 Results 页内容最小宽约 1529 > 视口 1006，只能横向滚动——这是**剩余限制**，未修复。
- **主题切换性能**：作者与审查的同机测量皮肤集合不同（作者 6 皮肤 765.1/752.5 ms，审查复跑 881.7/875.2 ms），倍率结论 1.0–1.02× 可复现；绝对中位数不可复现；未测重复选择同一皮肤的开销。
- **重启恢复**：用两进程探针手动复现，没有自动化用例。
- **代码修正**：去掉 i18n 重复 key；`reveal_current()` 恢复“导航不隐藏停靠页”的原契约（Results 页改由 `focus_analysis_view()` 收起 configuration/preview/ai）；外观菜单显示“当前使用/下次使用”；`QLineEdit#paletteSearch` 边框改用 `border_strong`（≥3:1）。
- **新增证据**：`screens-v2/`（B/K/C + paper/circuit/contrast_light/midnight/contrast_dark 的 start/configuration/results + 命令面板 + 快捷键表；原生 125% 交叉图；150% 下 B/paper/midnight 整页）、`semantic-colours.md`（15 皮肤语义色表）。
- **仍缺（因此 J3 保持未关闭）**：非法草稿/阻断诊断/结果/Agent 等待批准的状态图与窄面板稿；B/K/C 前后问题清单与未参与设计者的四件事复验；Windows 125%/150% 真实操作记录；Linux 真实桌面（本机只有 WSLg X11/xcb）；自动化重启用例。
