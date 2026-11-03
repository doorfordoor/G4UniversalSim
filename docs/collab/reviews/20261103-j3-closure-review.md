# J3 桌面皮肤与可读性阶段：独立审查（2026-11-03）

审查者不是 J3 代码作者。本文件是本次审查唯一写入；未修改产品、测试或证据，未执行 git 写操作。

## 1. 审查范围与基线

- 仓库 `D:\Geant4\G4UniversalSim`，分支 `roadmap/gui-theme-response`，HEAD `03d1c636`（`test(gui): keep editor and result state when the skin changes`）。契约是 `docs/collab/decisions/20261102-j3-desktop-skins.md`：B/K/C 改造与三套新皮肤两部分分别签收，且每部分都要有实装与实窗证据、独立审查后才可关闭 J3。
- 工作树含未提交在制品，且审查期间被并发修改（修改者不是本次审查）。本审查固定 2026-11-03 09:20 快照，引用文件 sha256 如下：`gui/g4usim_gui/window/workspace_layout.py`=662940a6…、`gui/g4usim_gui/core/i18n.py`=537c3a4f…、`gui/smoke_tests/smoke_theme_state.py`=008f2988…、`scripts/run_m0_tests.py`=281e5a44…、未跟踪 `gui/smoke_tests/smoke_theme_state_backend.py`=4d6286dc…。此后的任何修改不在本审查范围。
- 已读：契约全文；`docs/verification/j3-visual-checks-20261102/README.md`；`j3-theme-v1`、`j3-shell`、`j3-panels`、`j3-focus`、`j3-analysis-docks`、`j3-modeltree`、`j3-help` 各 README；`docs/ROADMAP.md:306/416/421`；`theme.py`、`shell.py`、`workspace_layout.py`、`model_tree.py`、`command_palette.py` 及 9 个相关测试脚本；`git log --oneline -14` 与 11 个 J3 提交的 `show --stat`。
- 实际运行的测试（`PATH="/d/msys64/ucrt64/bin:$PATH" gui/.venv/Scripts/python.exe -B tools/test_assert_probe.py …`，runner 设 offscreen）：`test_theme_registry` 587 断言；`gui_theme_state` 11；`gui_theme_state_backend` 40（真实 40000 事件运行中切换 30 次，最终 success）；`gui_help_menu` 34；`gui_model_tree` 21（widget 段 SKIP）；`gui_command_palette` 42；`gui_theme_response_shell` 55；`gui_j1_appearance` 29；`gui_workspace_layout` 149，均 exit 0。另独立重算 15 皮肤对比度、两进程 QSettings 重启探针、1280/1400 宽度 dock 探针、Results 页最小宽探针，并在与作者不同时刻复跑 `out/theme_perf.py` 与父版 worktree `625cfee2` 的 `out/theme_perf_before.py`。`state-preservation`、`compact-editors`、`compact-output` 三份归档报告均通过 `check_report_evidence.py`。
- 本审查没有做真正的实窗人工操作（Windows 原生 125%/150% 会话、Linux 真实桌面、鼠标可用性流程），因此这些项只能判“未独立复现”，不能判通过。
- 本审查只新建本文件；工作树其余改动均为审查期间已存在的在制品，本次审查未执行任何 git 写操作，也未修改产品、测试或证据。

## 2. 逐条验收对照

| 契约项 | 作者声明 | 独立核验方式 | 结论 |
| --- | --- | --- | --- |
| 15 皮肤注册表、可访问性归一化、颜色集中登记 | 已完成，`theme_registry` 113 断言点 | 读 `theme.py:375-455`；跑 `test_theme_registry` 587 断言 | 复现 |
| 外观菜单按明暗分组、浅/深各记忆、跟随系统、旧 `light_palette` 迁移与坏值回退 | 已完成，重启恢复 | 读 `shell.py:364-388/623-669`、`theme.py:655-696`；两进程 QSettings 探针：`_set_skin(paper)`→`_set_skin(midnight)` 后重启恢复 `(dark,paper,midnight)` | 部分：机制可复现，但仓库无自动化重启用例（仅 `stored_appearance` 单测） |
| 菜单勾选项与画面吻合，跨明暗组时说明“当前使用/下次使用”并由测试锁定 | 声称已按契约处理 | 探针：初始勾选 `{B,C}`，切 paper 后 `{paper,C}`，切 midnight 后 `{paper,midnight}`；源码 `shell.py:623-632` 令浅、深两组记忆皮肤同时 checked；测试 `smoke_theme_response_shell.py:91` 只锁 B/K 旧镜像 | **未复现**：无任何“当前/下次”文案，浅深记忆同时打勾（见 M1） |
| 正文/可交互控件文字 ≥4.5:1，焦点与关键控件边界 ≥3:1；提交实际前景/背景表 | 17 项组合 × 15 皮肤全部达标，最低 aurora 1.16 | 自写 WCAG 脚本读 `theme.py`；复跑 `out/contrast_table.py`；与 README 表逐位比对 | 部分：B/K/C/paper/midnight 的 7 列逐位复现，587 断言通过；但表只覆盖作者选定的 17 对，命令面板搜索框正常态边框用 `$border`（1.22–2.62:1，见 L4），`border_strong` 对 canvas/surface_alt 邻接未测 |
| B/K/C 同工程同页同缩放前后画面、问题清单（改哪/改善什么/局限）、未参与设计者按正常入口完成四件事 | 有前后截图与区域改造 | 归档 12 张 before/after（`j3-theme-v1/screens`，1950×1225）；`grep` 全库无“问题清单”；`j3-panels/README.md:60-65` 自承截图不能替代四件事 | 部分：有前后图，无问题清单，无未参与设计者操作记录 |
| 三套新皮肤同内容对照（非法草稿/阻断诊断/已完成运行/结果图/待批准 Agent）、普通/悬停/焦点/选中/禁用/成功/警告/失败状态、中英标签、整体+窄面板稿、语义色表 | 纸墨/电路夜班/高对比已完成并检查 | 盘点全部 J3 归档截图 43 张；`grep -icE 'circuit|contrast'`=0；仅 paper、midnight 有归档截图，且只有配置页/起始页 | **未复现**：电路夜班与高对比 0 张归档截图；状态图、非法草稿/诊断/结果图/Agent 场景、窄面板稿、语义色表均无 |
| Windows 125% 与 150% 各切三套，编辑器/结果/日志/Agent 自然导航，中英长文案、向导、浮动 dock、图例、VTK 标签 | 125% 三面板完整无横向裁；150% 紧凑可用 | 校验截图尺寸与内容：`scale-125` 实为 2438×1531（README:34 称 1950×1225），只见侧栏+setup+材料，无 3D 面板；`scale-150` 来自 `3ec37a11`（紧凑隐藏 dock 之前的中间态），显示 3D dock 右侧被裁，README 正文未引用；150% 只有 paper 一套 | **未复现**：只有 paper 一套，125% 声明与图不符，150% 证据为旧中间态 |
| Linux 代表性真实桌面逐套切换并检查中文字体与深色；记录显示通道/DPR/退出/清理；WSLg RAIL 限制单列 | WSLg X11 截图 3 张 | 读 README §4 与 `linux-x11-paper-zh-page2.png`（中文界面/深色可渲染）；README:69 明说 WSLg 不是完整桌面、不能替代真实桌面 | **未复现**：仅有 WSLg，无真实桌面；作者已如实记录限制 |
| 状态不串改：草稿原文、Undo/Redo 栈、结果选择、页索引、显示覆盖、K1 有效性、任务 ID/计数；偏好不进项目/实验包；不触发提交/生成/运行 | 已有 5 例 188 断言，“这些仍属未完成项” | `smoke_theme_state`（11 断言：run_name 草稿、文件树行数与选中、页索引、tab、QSettings、状态栏）；`smoke_theme_response_shell`（55：项目/草稿/revision/页/日志/图表数据集快照相等、`settingsChanged.count()==0`、重复同色板不重绘）；grep 项目/写入器无 appearance 键 | 部分：草稿/结果选择/页/tab/QSettings/项目快照已覆盖；Undo/Redo、K1 资格、非法草稿恢复、显示覆盖仍未测（作者自认） |
| 运行中任务切皮肤不破坏运行 | 新增 backend 用例 | 未提交 `smoke_theme_state_backend.py` 实跑 40 断言：30 次切换中 progress 消息数不变，最终 `success`、`completed_events=40000`、`page._progress_state=success` | 复现（但文件未跟踪，见 H1） |
| 性能：同机、同项目、同测量边界、父版基线、每场景≥5 次、中位/最慢/重复选择开销；首次冻结以父版同机中位数 1.20× 为调查线；分报实窗/离屏 | 765.1 vs 752.5 ms ≈1.02×，低于 1.20× | 复跑当前脚本 all median 881.7/worst 1054.7；父版 625cfee2 脚本 all median 875.2/worst 1000.3，倍率≈1.007×（<1.20×）；绝对中位数不可复现；两脚本皮肤集不同（当前 6 套不含 K，父版 3 套 B/K/C）；均 offscreen；无实窗计时、无重复选择计时；脚本在 gitignored `out/` | 部分：倍率结论可复现，绝对数与“同集合/同边界”声明不可复现（见 L1） |
| 自动回归与收据：扩充既有用例、新增 ID/迁移/重启/焦点/图表/VTK 反例、严格核验报告与逐例日志、覆盖 GUI 正式矩阵与实窗、记录可回退提交号、源码/可执行/截图/统计分账 | 各阶段报告均通过证据门禁 | 三份归档报告 `check_report_evidence` OK，但均为 `git_dirty=true`；`state-preservation` 的 `git_head=61145bdf` 早于被测用例提交 `03d1c636`，且其中的 `theme_state` 用例在生成报告时尚未提交 | 部分：报告可机器复核，但候选/证据身份不冻结（见 H1） |
| 帮助菜单/模型树/按页适配/命令面板/面板细节各阶段回归 | 各阶段断言通过 | 复跑：help 34、model_tree 21（widget 段 skip）、command_palette 42、workspace_layout 149、j1_appearance 29 | 部分：纯函数部分复现；`j3-modeltree` 声称的 Windows 平台 27 断言无归档记录（见 L3） |

## 3. 发现的问题

### high

- **H1 候选未冻结，归档证据含恒真断言。** `state-preservation/report.json` 的 `git_head=61145bdf`、`git_dirty=true`；HEAD 提交版 `gui/smoke_tests/smoke_theme_state.py:73` 是 `assert theme.current_skin(window).id == "B"`，而 `current_skin(window)` 读不到 `window` 的 `resolvedSkin` 属性，会回退到默认 light B，断言恒真。真正有效的那行只存在于未提交修改（`theme.current_skin().id`）；新增 backend 用例整个文件未跟踪，`scripts/run_m0_tests.py` 的登记也未提交，且没有用修改后的快照重生成 `state-preservation` 报告。因此“188 断言”不能作为冻结候选的证据，HEAD、工作树、归档报告三者不是同一身份。
- **H2 契约要求的三套新皮肤视觉交付缺失。** 全部 J3 归档截图 43 张中，文件名含 circuit/contrast 的为 0；只有 paper、midnight 进入归档，且都是配置页/起始页。契约要求的非法草稿配置表、阻断诊断、已完成运行、结果图、等待批准 Agent，普通/悬停/焦点/选中/禁用/成功/警告/失败状态，中英标签，每套整体+窄面板稿，以及语义颜色表均未交付。本地 `out/verification/j3-skins/` 有 30 张真实字体实窗图（15 皮肤×2 页），但目录被 gitignore，仓库不可复核。作者在 `j3-theme-v1/README.md:42/58-59` 已承认这部分未做，按契约这仍属作者侧交付缺口，不是可留给独立审查的内容。

### medium

- **M1 菜单不说明“当前使用/下次使用”，也无测试锁定。** 契约第③条明确要求跨明暗组选择时菜单说明当前/下次并用测试锁定；`shell.py:623-632` 对每个皮肤项设 `checked = skin_id in (light_id, dark_id)`，独立探针显示初始 `{B,C}`、切 paper 后 `{paper,C}`、切 midnight 后 `{paper,midnight}`，画面是 paper 而 C 同时打勾；无 current/next 文案。`smoke_theme_response_shell.py:91` 只断言 `_palette_actions['K'].isChecked()`，锁的是 B/K 历史镜像，不是该契约行为。
- **M2 验收文档与证据不符/过度声明。** `j3-visual-checks/README.md:34-35` 称 125% “配置页三个面板完整，无横向裁剪（screens/scale-125-paper-configuration.png）、抓图 1950×1225”，实际文件 2438×1531 且图中无 3D 面板；`:40` 称“探针测量窗口最小宽度由约 1600 降到 760”，但 `setMinimumSize(760,480)` 在 J3 之前的首个 GUI 提交 `049d4f00` 已存在（`main_window.py:40`），`probe_minwidth.py` 仍报 output page 最小宽 1397，这不是本阶段测量的变化；`:38` 称紧凑 dock “可从 View → Panels 与命令面板重新打开”，实际菜单名为 `View → Workspace layout`（`workspace_layout.py:356`），命令面板 32 条（9 Page+8 Action+15 Appearance，`shell.py:740-768`）没有任何 dock 开关；且 `workspace_layout.py:210-217` 只在 compact 时 hide，没有恢复分支，重开后任一 resize 会再次收起。`:42-44` 的 remaining 列表也未记录 150% 下 Results 页面横向滚动与重开 3D dock 的裁剪。
- **M3 09:20 工作树回归第五阶段契约且无测试/文档同步。** 未提交的 `workspace_layout.py` 删除了 `reveal_current()` 中“离开停靠页隐藏该页 dock”的循环（`workspace_layout.py:114-140`），并把 compact 分支改为只藏 AI、保留 3D preview、分栏改 `[250,480]`（`workspace_layout.py:189-213`），`focus_analysis_view()` 顺带隐藏 configuration dock（`:215-234`）。独立探针：Results 页→返回 Configuration 后 results+logs dock 仍可见，违反 `AGENTS.md` 第五阶段“离开停靠页必须隐藏该页 dock”及 `j3-analysis-docks/README.md` 的记录；`gui_workspace_layout` 仍 149 通过，说明测试没有锁定该行为；同时 compact 现在保留 3D，与 README:36-41 和 AGENTS 的“选项 dock 自动收起”描述相反。无论最终采用哪种行为，这份在制品都不能按“作者侧完成”提交。
- **M4 150% 下 Results/分析页未适配。** 1280 逻辑宽、compact 时 Results 页 `OutputPage` 宽 1529、`minimumSizeHint` 1529，视口只有 1006（`workspaceResultsScroll` 1018），只能横向滚动；page 8 最小宽 1092。契约要求 150% 下“结果自然导航”，README:42-44 未把分析页此项列为已记录限制。

### low

- **L1 性能证据的绝对数和测量身份不可复现。** 作者 765.1/752.5 ms（1.02×）；我同机复跑 881.7/875.2 ms（1.007×），“约 1.0×、低于 1.20×”可复现，但绝对中位数不同；当前脚本 6 皮肤（无 K）对父版 3 皮肤（B/K/C），并非同集合；脚本只在 gitignored `out/`，未入库；没有实窗计时，也没有契约要求的“重复选择同一皮肤”专项计时（重复选择“不重绘”仅由 `smoke_theme_response_shell` 断言，不是计时）。
- **L2 重启恢复没有自动化回归。** 两进程探针复现 `(dark,paper,midnight)` 恢复；但仓库只有 `stored_appearance` 单测，没有“关闭并重启 GUI”的归档用例，契约要求新增重启反例。
- **L3 模型树 widget 断言不可复核。** `j3-modeltree/README.md` 称 Windows 平台直跑 27 断言（widget 联动），离屏只 21 断言且打印 `SKIP widget part`；归档报告没有 27 断言记录，本机复现只有 21。
- **L4 对比度表的配对范围窄于契约措辞。** `theme.py:1611-1613` 的 `QLineEdit#paletteSearch` 正常态边框是 `$border`，与 surface/input 对比度约 1.22–2.62:1（仅 contrast_dark 4.09），命令面板是 J3 新增关键控件；17 对表只测 `border_strong`，不含此边框，也不含 `border_strong` 对 canvas/surface_alt 的邻接。按“关键控件边界 ≥3:1”严格读，这一项未达标；按作者表内 17 对读，表本身可复现。
- **L5 交付流程与证据目录不完整。** 契约要求把候选 SHA、复现步骤、自动和实窗证据、残留问题写入 outbox，`docs/collab/outbox/` 无 J3 交付文档；`AGENTS.md` 要求的 B/K/C “问题清单”在全库无产物。工作树对 `i18n.py` 的删除使 About 标签由“后端可执行文件”变为另一既有重复键的“后端程序”（HEAD 的 `i18n.py:154/734` 重复键、`734` 被删），属未记录的小幅文案变化，未影响测试。
- **L6 汇总层表述比证据强。** 各阶段 README 的“不证明什么”边界写得诚实，但 `docs/ROADMAP.md:421` 以“125% 与 1180 逻辑宽 @150% 紧凑布局可用”等总结性措辞收录，未带上 README 的“只有 paper 一套、Results 横向滚动未测”等限定；在补齐证据前，汇总层也应按证据降级措辞。

## 4. 不能接受的声明

1. **“17 项对比度 × 15 皮肤全部达标”不能作为“所有关键控件边界 ≥3:1”的证明**：它只证明作者选定的 17 对，命令面板搜索框正常态边框仍低（`theme.py:1613`，约 1.22–2.62:1）。该声明必须限定为“表列 17 对通过”。
2. **“125% 配置页三个面板完整、无横向裁剪（抓图 1950×1225）”不能接受**：归档图实际 2438×1531，图中只有侧栏+setup+材料编辑器，没有 3D 面板；该图不能支撑“三个面板完整”。
3. **“紧凑 dock 可从 View → Panels 与命令面板重新打开”不能接受**：菜单实际是 `View → Workspace layout`；命令面板无 dock 条目；且重开后紧凑宽度下任一 resize 会再次隐藏。
4. **“窗口最小宽度由约 1600 降到 760”不能接受**：760 是 J3 之前就有的固定 `setMinimumSize`，不是本阶段实测变化；内容最小宽（Results 页约 1397）并未降到 760。

## 5. 剩余验收缺口

1. 冻结候选：提交 `workspace_layout.py`/`i18n.py`/`smoke_theme_state.py`/`run_m0_tests.py` 与 backend 新用例，重生成全部受影响报告，使报告 `git_head` 与候选一致且 `git_dirty=false`。
2. 修正并重跑 `state-preservation` 证据（`current_skin()` 断言、去掉恒真断言），补重启恢复自动化用例。
3. 实现并测试菜单“当前使用/下次使用”，并补齐 15 皮肤勾选与画面一致性断言。
4. 补 B/K/C 问题清单和“未参与设计者按正常入口完成四件事”记录；补三套新皮肤的状态图、非法草稿/诊断/结果/Agent 场景、整体+窄面板稿与语义色表；把 circuit/高对比证据从 `out/` 移入归档。
5. 补 Windows 原生 125%/150% 各切三套的真实操作记录（含结果/日志/Agent/向导/浮动 dock/VTK），修正 125% 截图/尺寸声明，明确 Results 页横向滚动与重开 3D dock 裁剪为已记录限制或修复。
6. Linux 真实桌面：执行逐套切换并记录显示通道/DPR/退出/清理；若当前环境不可得，契约中的此项保持未完成，不能以 WSLg 替代。
7. 性能：补实窗计时与重复选择同一皮肤计时；用同集合父版候选重测；脚本入库或附可复核命令。
8. 决定 M3 工作树布局改动的去留：若保留，更新 `AGENTS.md`、`j3-analysis-docks` 证据和测试；若不保留，恢复“离开停靠页隐藏 dock”的行为。
9. 命令面板搜索框等 J3 新增控件的边界对比度要么达到 3:1，要么在验收表与 README 中明确列为残余限制。

## 6. 总体结论

**不同意**将当前状态声明为“作者侧完成、J3 可关闭（保留已记录限制）”。

可以复现的部分是实在的：15 皮肤注册表与可访问性归一化、B/K/C/paper/midnight 的对比度表值、外观菜单分组/记忆/迁移、状态在切皮肤时的多数保值、运行中切皮肤不破坏真实运行、命令面板/帮助/模型树/按页适配等自动回归、以及“主题切换约 1.0× 父版、低于 1.20×”的倍率结论，这些我均独立复现或复跑通过。作者在 README 中也主动写明了未独立验收、未做 125%/150%/Linux 等边界，这一点应予肯定。

但按 J3 契约本身，当前仍缺：明确要求的菜单“当前/下次”行为与测试、B/K/C 问题清单、三套新皮肤的视觉状态/场景/窄面板稿（circuit 与高对比归档截图 0 张）、Windows 125%/150% 各切三套的真实操作、Linux 真实桌面、冻结候选与证据身份；此外 09:20 工作树对停靠页/紧凑布局的未提交改动回归了第五阶段行为且无测试/文档同步，验收文档中另有 4 条不能接受的声明。这些不是“独立复验”可以替代的作者侧交付，因此 J3 应保持未关闭，当前状态可记为“实现基本完成、验收证据未完成”，补齐第 5 节后再次申请作者侧完成与独立审查。
