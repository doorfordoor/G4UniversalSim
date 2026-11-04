# J3 既有 B/K/C：原问题 → 改动 → 现有证据映射（2026-11-04，更正版）

状态：**文档整理，不构成新验收、不构成阶段通过**。本文只复用仓库内已有证据，未运行测试、
未改产品/测试/CI、未占桌面。

- 产品候选：`92134da062e8e3a203a39ff59fcd2b87bd0ffef1`（冻结；仅测试/CI 环境补丁，产品 GUI/C++ 与 `4eebbe9e` 字节一致，见主审 review）。
- 主审实窗事实来源：`docs/collab/reviews/20261104-j3-closeout-independent.md`。文中“实窗/画面”均为**主审观察**，
  作者未独立复验；“画面”指主审 computer-use 实际画面（可能未归档截图），**不得写成仓库内截图路径**。
- 证据类型定义：`自动`=仓库测试；`图`=**仓库内确实存在的归档截图**；`画面`=主审实窗实际画面（未在仓库归档）；`—`=无。
- 收尾清单：`docs/collab/decisions/20261104-j3-closeout.md` 组 1（B/K/C 四件自然任务）、组 2（三新皮肤）。
  本阶段只验**皮肤显示/合成组件形态**，不新增“真实云任务批准/取消”的产品验收要求。
- 旧矩阵编号（A1–A4、B 组/C 组）见 `docs/collab/outbox/20261103-j3-remaining-acceptance-matrix.md`。

## 1. B/K/C 前后图身份与“原生原图归档”事实

渲染方法：Windows 真实平台插件、`MainWindow` 1560×980 逻辑尺寸、默认项目、125% 缩放抓图；
`before-*` 由旧版工作树 `625cfee22ab612b3e3829e7b6149c56036943d50` 渲染，`after-*` 为 J3 主题 v1 之后渲染
（未记录精确 commit，属身份缺口）。全部 1950×1225。

| 皮肤 | before（旧版） | sha256（前 12 位） | after（J3） | sha256（前 12 位） |
| --- | --- | --- | --- | --- |
| B | `docs/verification/j3-theme-v1-20261102/screens/before-B-page0.png` / `before-B-page2.png` | `b6b6233f8d3a` / `157332aa71c2` | `after-B-page0.png` / `after-B-page2.png` | `f4888f0ba91c` / `de6a5edf3b2a` |
| K | `before-K-page0.png` / `before-K-page2.png` | `70d4eee48b9c` / `9e05e0383f77` | `after-K-page0.png` / `after-K-page2.png` | `5d69d7be59fc` / `809c03f8c8ad` |
| C | `before-C-page0.png` / `before-C-page2.png` | `91e8772ea32c` / `27c29a9e7034` | `after-C-page0.png` / `after-C-page2.png` | `f0b5f5796ab9` / `c9503ac9a9ad` |

J3 自查图（15 皮肤，页 start/configuration/results/palette/shortcuts，均 1950×1225）：
`docs/verification/j3-visual-checks-20261102/screens-v2/{B,K,C}-{start,configuration,results}.png`，
sha256 前 12 位：B `540eaeffedb5` / `c05abe2752cc` / `c0cb31cde679`；
K `6d1c563359af` / `2f366cd02758` / `5b5da2b35ec3`；
C `c4c559bccf2c` / `db4888e61187` / `a40e7577d4c1`。

**原生原图归档现状（只写确实存在的文件）**：`docs/verification/j3-final-20261104/screens/` 目前只有
`windows125-circuit-pending-component.png`（472×690，51,699 B，sha256 `3f7434dfcde9d9dd42a54f5ff2cb2377e0cc6cec6023d41a6a25e2c2a777df4d`）。
其余主审实窗画面**尚未归档**，本表不写它们的截图路径。

**明确缺失**：B/K/C 的悬停/焦点/选中/禁用/成功/警告/失败等**状态前图不存在**，也没有逐状态后图。
按任务限定，不重建旧版、不做新工具补图。“无独立截图”不等于“无实际观察”（见 §4）。

## 2. B/K/C 原问题 → 具体改动 → 证据

| 原问题（旧版 B/K/C 下自然任务困难点） | J3 具体改动（产品） | 现有证据 | 空白 |
| --- | --- | --- | --- |
| ①找不到“当前编辑对象/可改字段”：材料表与被选材料字段分处不同编辑器、无统一状态提示 | 设计令牌统一到 B/K/C（28 色角色 + 可访问性归一化）；材料表/被选材料字段在配置页同一工作台；状态栏与外观菜单显示当前皮肤 | 前后图 `after-{B,K,C}-page2.png`（配置页材料表+被选材料）；`gui_config_editors` 自动用例；主审 150% 画面：B→K→C→纸墨切换后材料行内容保持 | 无逐皮肤“找到字段并修改”的连续实窗步骤记录 |
| ②切换到对应 3D/结果不直接：dock 分散、导航缺分组 | 侧栏分组（WORKFLOW / RUN & ANALYZE）、页头面包屑、Ctrl+K 命令面板、View→Panels 重开、工作区按页适配 | `screens-v2/{B,K,C}-{configuration,results}.png`；`gui_command_palette`、`gui_workspace_layout`、`gui_compact_panels`；主审画面：Windows 会话 12194 为 circuit Results CSV→paper 后选择保持；Linux X11 C 夜读历史轨迹/3D 保留 | B/K 的实窗 3D/结果切换仅图与自动证据；K 无实窗画面记录 |
| ③定位指定运行日志难：日志 dock 与结果混排、切换后丢失 | 分析页只保留 Results+日志布局；恢复时重施页面约束（本候选修复）；日志标签页状态不改写 | 相关 GUI 用例 **4 个合计** 596 断言（`gui_workspace_layout`、`gui_f4_layout`、`gui_compact_panels`、`gui_main_window`，**不是一个 case，也不含生产两次重启**）；主审 150% 画面：B/K/C/纸墨切换期间右侧同一 `stdout.log` 与 200 万事件摘要保持；生产两次重启证据见主审另列 manual receipts | 未逐皮肤演示“从历史运行定位到某指定日志”的完整点击链 |
| ④找不到助手中待批准动作：助手停靠区默认不出现、标题/动作状态不清 | View→工作区可展开助手 dock；合成组件显示待批准状态、禁用动作与 Apply/Cancel、Tab 焦点；生产 adapter 未改 | 主审画面：待批准**合成**组件（三皮肤焦点/许可/禁用明确为合成组件，未归档截图）；`gui_config_agent_panel` 自动用例 | **无真实云任务批准/取消画面**；本阶段只要求皮肤显示，该真实动作**不作为缺口**，保留为边界说明 |

## 3. 原四件自然任务 × B/K/C 证据表

| 任务 | B | K | C |
| --- | --- | --- | --- |
| A1 编辑对象/字段 | 图 after-page2；自动 `gui_config_editors`；画面 150% 材料行保持 | 图；自动；画面 150% 材料行保持 | 图；自动；画面 150% 材料行保持 |
| A2 对应 3D/结果 | 图 results/configuration；自动 `gui_3d_view`/`gui_output`；无该皮肤 3D 实窗画面 | 图；自动；无实窗画面 | 图；自动；**C 夜读**实窗画面（Linux X11 历史轨迹/粒子/3D 保留）——与 circuit 的 Windows CSV 记录分开 |
| A3 指定运行日志 | 画面 150% 日志保持；自动 GUI 用例组 | 同左（150% 序列含 K） | 同左 + Windows 会话 12194 |
| A4 待批准 Agent 动作 | 仅**合成组件**画面（纸墨形态）；自动 `gui_config_agent_panel` | 同左（无 K 专属画面） | 同左（无 C 专属画面）；无真实批准画面（非本阶段缺口） |

## 4. 三新皮肤（paper / circuit / contrast_light）× 八状态

`图`=归档截图；`画面`=主审实际画面（未归档）；`自动`=测试；`—`=无。
语义色表（`semantic-colours.md`）与对比度表只证明令牌数值，**不构成八状态实窗矩阵证据**。

| 状态 | paper | circuit | contrast_light |
| --- | --- | --- | --- |
| 普通 | 图 start/config/results；画面 VTK/中文图表 | 图三页；画面 VTK、CSV | 图三页；画面 VTK |
| 悬停 | 无归档截图；主审操作过程有实际画面（未归档），但 review 未把悬停列为交叉确认项 | 同左 | 同左 |
| 焦点 | 自动 focus_ring≥3:1；画面：合成组件 Tab 焦点 | 自动；画面：合成组件焦点 | 自动；画面：实际控件焦点（review 82 交叉确认） |
| 选中 | 图（导航选中）；自动 theme_state；画面 Detector 选择保持 | 图；自动；画面 Detector 轮廓保持 | 图；自动；画面 VTK 选择保持 |
| 禁用 | 图（Build command 禁用）；画面合成组件禁用动作 | 图；画面合成组件禁用动作；**归档图** `docs/verification/j3-final-20261104/screens/windows125-circuit-pending-component.png` | 图；画面合成组件禁用动作 |
| 成功 | 自动 `gui_theme_response_shell`（success chip）；画面 125% 运行控制台保留上一 200 万成功日志（标“上次运行（配置已变更）”） | 自动；画面 200 万事件运行完成（摘要在，非 UI 成功态截图） | 自动；画面（review 82 交叉确认） |
| 警告 | 自动（warning chip）；画面 150% 非法 seed 警告图标/字段路径/原值可读 | 自动；画面同上（circuit 150% 校验） | 自动；画面（review 82） |
| 失败 | 自动（danger chip）；画面 125% K1 字段/依赖失败（分列） | 自动；画面 K1 失败/非法 seed 拒绝 | 自动；画面（review 82） |

## 5. 组 2 四项（三新皮肤）现有证据

| 要求 | 现有证据 | 空白 |
| --- | --- | --- |
| 非法草稿 | 主审 150% 画面：**纸墨与高对比均**对同一 `j3-invalid-seed` 校验，明确拒绝并显示 `config.seed`、原值保持；Undo/Redo 往返 | 逐皮肤独立截图；其余皮肤未逐套 |
| 阻断诊断 | 同上（警告图标/字段路径/原值/OK 可读）；125% 高对比运行控制台 K1 字段/依赖失败、初始化/物理未观测、事件陈旧分列保留 | 逐皮肤独立截图 |
| 完成运行与结果 | 150% 高对比→circuit 的 200 万事件运行最终 2000000/2000000、`output_failure_status=none`；125% 保留同一成功运行日志并标“上次运行（配置已变更）”；Linux X11 载入 4 事件历史轨迹、旋转、粒子/材料/透明度与 C 夜读保留 | 成功态逐皮肤 UI 截图；contrast 专属结果页观察 |
| 待批准 Agent | 合成组件画面（三皮肤焦点/许可/禁用、Apply/Cancel、Tab 焦点可辨）；归档图 `windows125-circuit-pending-component.png` | 真实云任务待批准/批准/取消画面——**本阶段不作为缺口**（只验皮肤显示） |

## 6. 环境中重要事实（避免误读旧观察）

- Windows 系统已由 150% **恢复为 125%**（`review` 第 80 行）；本文 150% 记录属恢复前观察，后续复现须声明缩放。
- 125% 下已观察：高对比/纸墨/circuit 导航与运行控制台、K1 字段/依赖失败、初始化/物理未观测、事件陈旧分列。
- 150% 下已观察：纸墨/高对比非法 seed 校验（同一 invalid seed，原值保持；Undo/Redo）。
- 三新皮肤八态：主审以实际控件/原有真实运行/语义色回归**交叉确认**，但未形成逐皮肤逐状态归档截图（review 82 明确）。
- 物理正确性未验证；历史轨迹是已有 4 事件快照，不是新物理运行。

## 7. 剩余空白与边界

- 无 B/K/C 逐状态前后图；旧版 `before-*` 仅起始页/配置页普通态。
- 三新皮肤八状态**悬停**无归档截图，review 未将其列为交叉确认项（不等于主审从未返回过画面）；其余状态为“画面/自动/部分图”，不是完整矩阵。
- A4 无真实 Agent 批准画面，本阶段不作为缺口；合成组件不得称真实批准成功。
- 未覆盖：其余 12 皮肤、125%/150% 全清单、逐页八态截图、物理/轨迹正确性。
- **Linux 92134 同一真实 X11 重启、恢复布局/4 历史轨迹、画布旋转、正常 File→Exit（exit0）已由主审实窗观察**（review 66/74/80 行），不再列为“未覆盖”；WSLg 历史限制保留。
- J3 仍未关闭；STATUS/ROADMAP 未改。
