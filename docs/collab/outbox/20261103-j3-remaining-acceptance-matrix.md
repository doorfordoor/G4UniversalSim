# J3 剩余可执行验收矩阵（作者整理，2026-11-03，v3 增补）

作者：DeepSeek（J3 实现作者）。用途：供主审独立验收逐项执行。**本文件不是验收证据，不改变 J3 未关闭状态。**

版本说明：v1 曾被主审预审退回五点，本版逐条更正——①不增改门槛，只引用 J3 任务书原文（Windows 125%/150%、三套新皮肤+B/K/C、同机 1.20× 调查线、4.5:1/3:1 建议线）；②Linux 证据是独立 X11/xcb+TigerVNC 代表桌面，不是 WSLg，按“历史代表导航已做、候选/页面/状态仍缺”书写；③D1 明确 Qt150 已做 26×17 宽表内部横滚，OS150 限制单列；④夹具路径已实测（见 §2），`gui_runs/demo`（gitignore）与已入库 gallery 输出分开写，legacy 结果不当作新运行成功；⑤runner 的 `optional_pyvista_coverage` 已改为“注册不等于执行”的显式语义，并重跑留证（E8b）。

⑥（v3 增补，主审 m08349）CI 的 3D 依赖已落实：`.github/workflows/m0-static-gui.yml` 与 `.github/workflows/linux-geant4.yml` 的 GUI 依赖安装增加 `-r gui/requirements-3d.txt`，`--fail-on-skip` 不变；**云 CI 尚未运行**，本地只做 YAML/actionlint 与 Linux `QT_QPA_PLATFORM=offscreen` 有限分支核验（见报告 §2.4）。

## 0. 依据（只列可读原文）

- 任务书：`docs/collab/decisions/20261102-j3-desktop-skins.md`——两部分分别签收（B/K/C 改造 + 三套新皮肤）；B/K/C 四件自然任务；新三皮肤四类内容状态与 8 状态；Windows 125%/150% 各切三套并自然导航；Linux 代表性实际桌面逐套切换；性能同机 1.20× 调查线与重复选择；状态不串改。
- 执行指南：`docs/collab/decisions/20261102-stage-execution-guide.md`。
- 最新独审与增量：`docs/collab/reviews/20261103-j3-n1-independent-r1.md`、`docs/collab/reviews/20261103-1626-j3-native-incremental.md`、`docs/collab/reviews/20261103-j3-whole-acceptance.md`。
- 本轮交付：`docs/collab/outbox/20261103-j3-n1-integration-r2.md`（本报告）。

## 1. 证据身份（引用只写缩写）

| 缩写 | 身份 | 关键事实 | 不可外推 |
|---|---|---|---|
| E1 | `docs/verification/j3-status-contrast-20261103/{static,gui,integration}/report.json` | **唯一干净工作树归档**：head `c082eccc`、dirty=false；static 49/5687、gui 76/10535、integration 33/6830；探针 15/15（最低 4.605，见该目录 README） | 不含 8 态实窗、不含 Windows 150 实窗、不含 Linux、不含 N1 用例 |
| E2 | `docs/verification/j3-close-20261103/…`（head `a1a64ead`，dirty=true） | gui 75/10297、integration 33/6844、static 49/5615 | 非干净候选，历史身份 |
| E3 | `docs/verification/j3-compact-fix2-20261103/…`（head `d4400b26`，dirty=true） | gui 76/10351、integration 33/6826、static 49/5615 | 同上 |
| E4 | `out/verification/j3-n1-independent-20261103/` | 主审首轮 N1：`objects.log`（210 断言 exit0）、`native-r1.log`（Windows native 326）、`linux-native-r2.log`（xcb 326）、`linux-native.log`（首启 exit134 缺 `libxcb-cursor.so.0`，失败保留）、`candidate.json`（uncommitted candidate，visual_review=pending）、`related/…/report.json`（gui 3/299，head `0368abce` dirty） | 不覆盖 8 态、Windows 150 全流程、Linux 完整 VTK |
| E5 | `out/verification/j3-final-native-20261103/` | 独立 **X11/xcb+TigerVNC** 真实 Linux 桌面 + 真实 Windows 125%/Qt150；`native-125-r1/`、`native-qt150-r1/`（identity/exit）、`perf-windows/report.json`、`linux-font-r2.log`、`native-linux-font-r2/`、`PROGRESS.md`、`vtk-axis-default-colors.json` | 系统缩放仍是 125%（远程会话无法改显示器设置）；Qt150 经 `QT_SCALE_FACTOR=1.2` 得 DPR1.5，不等于 OS150；WSLg RAIL 历史限制不在此目录 |
| E6 | `docs/verification/j3-visual-checks-20261102/` | `screens/`(6)、`screens-v2/`(61 图)、`semantic-colours.md`、`state-preservation/report.json`（gui 5/188，head `61145bdf` dirty）、`compact-editors`(6/328)、`compact-output`(4/117)、`theme-switch-latency.txt` | 截图/组件断言，不是实窗操作记录 |
| E7 | `out/verification/j3-whole-native-20261103/` | 整体验收：`perf-baseline-v2/`、`perf-current-v2/`、`status-contrast/`（15 皮肤）、`native-receipts.json` | 该目录 perf/status-contrast 报告无 profile/assertions 字段（见 §4） |
| E8b | `out/verification/j3-n1-registration-r3/20261103-194238-fafe30b9/report.json` | 本轮注册后 runner 实跑：head `0368abce`、dirty=true、1 case `gui_vtk_axes_theme`、210 断言、`vtk3d` 依赖、门禁 OK；`optional_pyvista_coverage` 已写明“注册不等于执行，用例行记录实际断言或依赖失败” | 未提交候选；单例注册不证明普遍覆盖 |

历史 E8（`j3-n1-registration-r2/…`，210 断言）保留；其 coverage 字段措辞已被 E8b 取代。

## 2. 夹具与成本边界（路径已实测）

- runner 当前 **222** 个 Case：static/gui/backend/integration 分层；`gui/smoke_tests/` 92 个脚本中 91 条 Case 覆盖 87 个唯一脚本（5 个未注册：`async_wait.py`、`audit_q1_public_paths.py`、`gui_test_window.py`、`smoke_hier_boolean_geometry_editor.py`、`smoke_q1_windows.py`）。
- requirements 词表：`qt`、`cxx`、`exe`、`merge`、`uproot`、`vtk3d`；`vtk3d` 缺依赖时 runner 记录 skip，`--fail-on-skip` 下判失败。
- 已实测夹具：
  - 宽表 fixture：`examples/gallery/shielding_slab/output/scorer_statistics.csv`——**git 已跟踪**，26 数据行 × 17 列；这是 gallery 历史输出，**不是新运行、不证明物理正确性**。
  - demo 项目：`gui_runs/demo/`——**存在但被 `.gitignore` 忽略**（`.gitignore:30 /gui_runs/`）；它是本机演示工程，不是可复现 fixture，也不等于 gallery 输出。
  - 窄屏/缩放图：E6 `screens/`、`screens-v2/`。
- 可复用入口：
  - 单例 runner：`gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py --profile gui --case <name> --fail-on-skip --report-root out/verification/<slice>`；门禁 `python -B scripts/check_report_evidence.py --report-root out/verification/<slice>`。
  - 单 smoke 直跑：`python -B tools/test_assert_probe.py gui/smoke_tests/<file>.py`。
  - 原生宿主模板（评审既有，非仓库工具）：`out/verification/j3-final-native-20261103/host.py`、`out/verification/j3-n1-independent-20261103/visual_host.py`；如需仓库化，见 §6 非门禁建议。
- 不要重跑全部 222 例或已冻结的 E1/E2/E3；剩余验收只跑对应单例与原生会话。

## 3. 剩余验收矩阵

### 3.1 B/K/C 四件自然任务（Windows，实窗）

| ID | 任务（任务书原文） | 夹具/步骤 | 通过条件（任务书口径） | 可引用 | 剩余缺口 |
|---|---|---|---|---|---|
| A1 | ①找到当前编辑对象和可改字段 | 真实 MainWindow（宿主脚本隔离 QSettings）；进 Configuration→Materials/Geometry 选中当前对象行；B/K/C 各一次 | 能独立完成、不误入别区、不需提示（有歧义记录具体控件）；字段可聚焦/可改 | E6 三皮肤 configuration 静态图；E1 `gui_config_editors`、`gui_f4_layout` 组件断言 | 缺实窗连续操作与记录；C 深色下 B/K 对照；中文界面同流程 |
| A2 | ②切到对应 3D/结果 | 复用 gallery 屏蔽平板示例；Configuration→3D 预览→显示 3D→Results→打开输出；B/K/C | 区域辨认正确、不误入别区；画布/文件列表可用，不崩溃 | E5 `native-125-r1`（Results 26×17 内部横滚）、`native-qt150-r1`（配置→3D 预览→显示 3D 视图+模型树）；E4 `visual-*.json` | 缺 B/K/C 三皮肤下 A2 完整实窗（现有 E5 为纸墨与默认 B）；C 深色 3D 轴/图表色 |
| A3 | ③定位指定运行的日志 | gallery 两次运行记录；Run History 按 run name 选中→打开 stdout/stderr/摘要 | 选中行与日志一致（run/时间/退出码）；能独立完成 | E1 `gui_history`（组件级） | 缺实窗 History→日志；中文长 run 名 |
| A4 | ④找到助手中待批准动作 | 复用 `smoke_config_agent_panel` 合成会话（固定回复）；打开 Agent→待批准→观察批准/拒绝 | 能定位待批准、说清会执行什么；控件不越权；B/K/C 可辨 | E1 `gui_config_agent_panel`、`gui_agent_actions`、`gui_config_agent` | 缺实窗待批准→批准/拒绝操作；键盘路径 |

### 3.2 新三皮肤 × 四类内容状态（各 3 行）

任务书要求：每套画出/实装“有非法草稿的配置表、一条阻断诊断、已完成运行、结果图及等待批准的 Agent”（设计稿不算，实窗记录才算）。下表按皮肤组织。

| ID | 皮肤/内容态 | 夹具/步骤 | 通过条件 | 可引用 | 缺口 |
|---|---|---|---|---|---|
| B1/B5/B9 | paper/circuit/contrast_light / 非法草稿 | 复用 `gui_unsupported_features`、`gui_geometry_safety`、`gui_project_import_projection` 非法夹具；实窗粘入非法值提交 | 明确阻断、指向具体控件；文字 4.5:1、焦点/边界 3:1（任务书建议线）；不写入/不运行 | E1 三组件用例；E6 三皮肤 configuration 静态 | 三皮肤实窗非法草图；中文提示可读性 |
| B2/B6/B10 | 同上 / 阻断诊断 | 复用 `gui_geometry_diagnostics`、`gui_f4_layout`；实窗制造阻断→打开诊断 | 诊断列出原因/位置、可复制；各状态有文字/图形/轮廓线索（不单靠颜色）；深色下不淹没 | E1 组件断言 | 三皮肤实窗诊断面板 |
| B3/B7/B11 | 同上 / 完成运行 | 复用 `gui_scenario_backend`/`gui_run_inputs`/`gui_live_progress_backend` 小事件真跑；实窗跑一次→摘要→Results→History | 完成态可辨、摘要事件一致、无伪成功；数字/单位可读 | E1 integration 用例；E5 Windows 125/150 Results（纸墨/默认 B） | 三皮肤“完成→Results→History”一条龙实窗；失败/中断对照 |
| B4/B8/B12 | 同上 / 待批准 Agent | 同 A4；三皮肤各一次 | 待批准说清执行内容；批准/拒绝可用；来源/目标可读 | E1 `gui_config_agent_panel` 等；E7 15 皮肤对比度 | 三皮肤实窗 Agent 流程+中文提示 |

### 3.3 8 种状态 × 三皮肤（任务书：普通/悬停/焦点/选中/禁用/成功/警告/失败）

| ID | 皮肤 | 方法 | 通过条件 | 可引用 | 缺口 |
|---|---|---|---|---|---|
| C1 | paper | 实窗逐态：侧栏、页内标签、主按钮、状态 chip、输入框、表格选中行；每态记录 | 每态有文字/图形/轮廓线索；文字对实际背景 ≥4.5:1、焦点/关键边界 ≥3:1（任务书建议线） | E1 `gui_j1_appearance`、`gui_theme_response`；E7 15 皮肤对比度（最低 4.605）；E6 `semantic-colours.md` | 缺成组实窗 8 态（现有截图不是 8 态成组） |
| C2 | circuit | 同上（重点：焦点环、禁用文字、选中行、日志时间戳） | 深色下 8 态可分；普通状态不照成报警色（任务书） | 同上；E6 circuit 静态 | 缺 circuit 实窗 8 态；深色焦点/禁用实测 |
| C3 | contrast_light | 同上（重点：失焦选中行、禁用控件、菜单勾选、缩放后对话框默认按钮） | 选中与键盘焦点可同时识别；8 态可辨且不单靠颜色 | 同上；E7 探针 | 缺实窗 8 态与菜单勾选/对话框默认按钮 |

### 3.4 Windows 125% / 150% 实窗导航与宽表

任务书：Windows 125% 和 150% 各切三套，在编辑器、结果页、日志和 Agent 之间自然导航，检查中英文长文案、向导、浮动 dock、图例及 VTK 标签；记录实际显示通道、DPR、正常退出与进程清理。

| ID | 已做（E5 原文） | 通过条件 | 仍缺 |
|---|---|---|---|
| D1 | Windows125 真实 qpa=windows DPR1.25：Results 表格 26 行×17 列，实际拖内部横向条到最右，`sum_sq` 可见；切纸墨后表格内容保留。Qt150（`QT_SCALE_FACTOR=1.2`，DPR1.5，系统仍 125%）：内部横滚到最右，`sum_sq` 列头与 `1.66501951858e-18` 等数值完整可见；切电路夜班后数据与内部横向位置保留 | 两档下宽表内部横滚可用、数值可读；切皮肤不丢内容/横向位置 | 125% 与 Qt150 下“各切三套皮肤”的全部记录（现只有纸墨→电路）；表格配色随皮肤；OS150 限制单列（见下） |
| D2 | Qt150 紧凑配置布局下实际拖 Results 外层横向条，右侧“刷新/打开输出目录”可达；与内部横滚分开计证 | 外层横滚可达右侧动作 | 缩窄后内部最右数值仍可能局部裁剪——review 增量明确“不能扩大为所有布局无裁剪”；不列为已通过 |
| D3 | 两水平滚动条互不干扰（review 增量 §2 已实测） | 先外层后内部再反向的顺序、150% 下同一序列 | 完整的“外层→内部→反向”序列记录 |
| D4 | OS150：远程会话无法更改显示器设置（E5/PROGRESS 明确），未冒称；Qt150 是 `QT_SCALE_FACTOR` 模拟 | 记录为环境限制，不作为通过或失败 | 真实 OS 150 显示器操作（需另处环境） |

### 3.5 向导 / 浮动 dock / 长中英文 / 焦点 / 重启

| ID | 方法 | 通过条件 | 可引用 | 缺口 |
|---|---|---|---|---|
| Ew1 | 实窗 File→New Simulation 向导（含中英文长文案）；125%/Qt150 各一遍 | 每步可前进/后退；生成按钮可用；文本不截断/不重叠 | E1 `gui_new_simulation_wizard`、integration `gui_new_simulation_backend` | 向导实窗（含中文长场景名） |
| Ef1 | 实窗把 3D dock 拖成浮动→调大小→双击还原；恢复布局 | 浮动后内容可用；还原正常；尺寸记忆；窄 dock 标题仍说明用途 | E5 Qt150：浮动按钮有效、初始浮动高度很小（观察）；E1 `gui_main_window`（含 `setFloating`）、`gui_workspace_layout` | 完整浮动流程（含重启记忆）；初始高度是否缺陷待主审定 |
| Et1 | 长中文/英文：项目名、run name、材料名、日志行；实窗标题/页头/表格/日志 | 不重叠；省略号+tooltip 或换行；列可拉伸 | 现有 `gui_main_window`/`gui_start_page` 只覆盖短文本 | 长文本夹具与实窗（见 §6 非门禁建议） |
| Efo | 实窗 Tab 环游主控件；Ctrl+K 筛选/Enter；F1 快捷键表；窄 dock 焦点可见 | 焦点环全皮肤 ≥3:1；Tab 顺序稳定；键盘可操作 | E1 `gui_f8_accessibility`、`gui_command_palette`、`gui_help_menu` | 实窗环游与面板操作；窄 dock 焦点 |
| Er | 实窗改布局/皮肤/最近项目→正常退出→重启→恢复；初装/旧 B/K/C 设置/未知 ID/系统明暗 | 皮肤、布局、最近项目、恢复副本均恢复；勾选/文案与画面一致；损坏值回退 | E1 `gui_theme_state`、`gui_workspace_layout`；E6 `state-preservation`(5/188，dirty) | 真实两次启动记录；初装/未知 ID 实窗 |

### 3.6 状态不串改 / 运行 / Undo / K1

| ID | 方法 | 通过条件（任务书） | 可引用 | 缺口 |
|---|---|---|---|---|
| F1 | 含非法草稿项目、可运行包、已载入结果、运行中任务分别切皮肤 | 草稿原文、Undo/Redo 效果、结果选择、显示覆盖、K1 有效性、任务 ID/计数不变；皮肤偏好不进项目 JSON/包；不触发提交/生成/新运行 | E1 `gui_theme_state`、`gui_theme_state_backend`（真跑 40000 事件）、`gui_f5_editor_history`、`gui_f5_recovery`、`gui_k1_*` | 实窗四态分别切换的完整记录（现有为组件/离屏） |
| F2 | 运行中切皮肤（Run Console 进度） | 运行不中断、进度不丢、结果正确 | E1 `gui_theme_state_backend`；E5 `perf-windows`（空结果中位 926.69ms/最慢 1070.56ms；六数据集 907.93/962.30ms；重复 9.20/17.89ms；同机旧版历史样本 1088.7/1113.5 与 1051.7/1073.1 本轮未重跑） | 实窗一次真实运行+进度记录；约 1 秒等待仍在，不得称已解决 |
| F3 | Undo/Redo 与恢复副本 | Undo/Redo 只影响语义；跨页导航仍可用；恢复副本不覆盖用户原文件 | E1 `gui_f5_editor_history`(241)、`gui_f5_recovery`(62)、`gui_f5_recovery_process`(12) | 实窗 Undo/Redo 与主题切换叠加 |
| F4 | K1 面板/资格 | 资格与摘要一致；无资格禁用且原因可读；不误报 | E1 `gui_k1_window`(178)、`gui_k1_panel`(1629)、`gui_k1_workflow`(260)、`k1_workflow_backend`(485) | K1 实窗状态矩阵与中文提示 |

### 3.7 Linux 代表性实际桌面（E5 = 独立 X11/xcb+TigerVNC，非 WSLg）

任务书：Linux 代表性实际桌面逐套切换并检查中文字体与深色状态；记录实际显示通道、DPR、正常退出和进程清理；WSLg RAIL 的旧限制单列（E5 即“其他桌面”完成的观察）。

| ID | 已做（E5/PROGRESS） | 仍缺 |
|---|---|---|
| G1 | 独立 X11/xcb 真实桌面（TigerVNC 显示服务，session 正常退出、监听端口清理）：纸墨、电路夜班、高对比实际切换；VTK 几何/模型树/XYZ/图例可见；几何颜色与不透明度保持。字体：旧 Matplotlib 缓存无中文字体，独立 `mpl-fresh` 可发现文泉驿，新缓存第二窗口无 Glyph 警告；原空状态未专门驻留复验 | 当前候选是 `c082eccc`（历史）；未提交 N1 轴文字改动未在 Linux 实桌面重验；页面覆盖与深色 8 状态明细仍缺 |
| G2 | N1 缺陷正是在此环境发现：电路夜班 VTK 轴文字黑色（X/Y/Z 均 `[0,0,0]`），组件探针见 E4；修复在未提交工作树，E4 的 xcb 326 是修复后对象/原生组件测试，不是实桌面视觉签收 | Linux 实桌面 N1 轴文字视觉复核（修复候选）；完整 VTK 覆盖（颜色/透明度/轨迹/选择） |
| G3 | 首启缺 `libxcb-cursor.so.0` 的失败保留（`linux-native.log` exit134）；隔离库补齐后 `linux-native-r2.log` 通过 | 按实际发行版记录依赖；WSLg RAIL 限制单列，不混入本项 |

## 4. 证据引用规则（防误引）

1. 只引用 `docs/verification/j3-*` 与 `out/verification/j3-*` 的原始报告；`out/verification/j3-final-integration`、`j3-final-static` 有日志无 report，禁止作为通过证据。
2. 干净候选只有 E1；E2/E3/E4/E6-state-preservation/E8b 均 dirty=true，引用时必须注明身份。
3. 字段缺失：`j3-status-contrast-replay`、`j3-whole-native-20261103/status-contrast` 顶层是 15 条皮肤数组，无 profile/git_head/assertions；`perf-*` 报告只有 `head/qt/qpa/DPR/font/scenes`，无 profile/assertions——不得当 profile 证据。
4. 历史 `fail>0` 运行保留原身份，不可追改或引用为通过（示例：`j3-close-gui` 72/3、`j3-close-integration` 31/2、`j3-compact-gui` 75/1、`j3-final-gui` 74/1、`j3-panels-gui` 71/1、`j3-static` 42/7、`j3-theme-v2/…1e5d4c67` 3/1、`j3-theme-v2b` 3/1、`j3-theme-v2c` 0/1）。
5. 视觉基线（E6 61 图、`semantic-colours.md`）只作旧视觉身份引用，不能替代操作记录。
6. gallery 输出（如 `examples/gallery/shielding_slab/output/…`）是历史夹具，不是本轮新运行，也不证明物理正确性；`gui_runs/demo` 被 gitignore，非可复现夹具。

## 5. 执行顺序建议

1. D1 补 125%/Qt150 各三套皮肤的宽表记录（内部横滚、切皮肤保留）→ D3 双横滚序列。
2. A1–A4（B/K/C 四任务，一次实窗会话串联）。
3. C1–C3（8 态，按皮肤分批）。
4. B1–B12（三皮肤 × 四内容态，可复用 A/F 夹具）。
5. Ew1/Ef1/Er（向导、浮动、重启）→ Et1/Efo（长文本、焦点）。
6. F1–F4（状态不串改、长时间运行、Undo、K1）。
7. G1–G3（Linux 代表桌面：先确认当前候选，再逐项；含 N1 轴文字修复的实桌面复核）。
8. 全部通过后由主审更新 STATUS/ROADMAP/支持矩阵；任一项失败返作者修复，不提前推进。

## 6. 非门禁建议（不在本轮门槛内，需单独批准）

- 新增 `tools/j3_native_window.py`：把既有 `host.py`/`visual_host.py` 泛化为仓库内夹具（参数化皮肤/DPR/页面/向导/settings 隔离），不自动操作 UI。
- 新增 checked-in 宽表 fixture（若现有 gallery 输出会变）：固定 17 列×200 行 CSV，避免重生成改变数值；并新增 offscreen 表滚动 smoke。
- 新增长文本夹具 smoke（中英文长名/长路径，compact 与 150% 逻辑宽）。
- 新增 3 皮肤 × 8 态“产品离屏控件渲染 PNG”smoke（明确非实窗）。
- CI 依赖（已于 2026-11-03 按主审 m08349 落实，不再是待批建议）：两个 workflow 的 GUI 依赖安装都追加 `-r gui/requirements-3d.txt`，`vtk3d` 用例在缺依赖时仍由 `--fail-on-skip` 判失败，不降级为跳过。
  - 风险与边界：CI 未实跑，只有 YAML 解析、`actionlint` 与本地 Linux offscreen 有限分支核验通过；安装 PyVista/VTK 会增加下载体积与作业时长；Linux 上 `import pyvista` 依赖系统 `libGL.so.1`，两个 workflow 已有 `libgl1` 安装步骤（`m0-static-gui.yml:62-65`、`linux-geant4.yml:46-51`）。
  - 离屏分支不变：`pyvista_available()` 在 `QT_QPA_PLATFORM=offscreen` 且未设 `G4USIM_ENABLE_OFFSCREEN_PYVISTA=1` 时恒返回不可用，runner 对所有 profile 都设置 offscreen（`scripts/run_m0_tests.py:476`），因此现有 GUI 测试仍走文本回退分支；本地实测 `smoke_3d_view` 仍打印 SKIP widget part 并 exit 0，`smoke_preview3d` exit 0。
  - 本地 Linux 证据（隔离 venv `/home/u123/venvs/g4-j3-native-20261103`：PyVista 0.48.4 / VTK 9.6.2 / Qt 6.11.3，`QT_QPA_PLATFORM=offscreen`）：`smoke_vtk_axes_theme` objects-only 模式 exit 0、210 断言、最低对比度 4.857。

## 7. 本轮限定范围自查

- 未新增产品代码（N1 两文件保持冻结；仅 runner 注册与 `optional_pyvista_coverage` 措辞）。
- 按主审 m08349 授权只改两处 workflow 的依赖安装（追加 `-r gui/requirements-3d.txt`），未改其它 CI 逻辑；云 CI 未运行。
- 未改 STATUS/ROADMAP、未改阶段关闭状态、未覆盖旧报告、未提交 Git。
- 未重跑与剩余验收无关的全量 profile；本轮只跑 `gui_vtk_axes_theme` 单例（E8b）。
