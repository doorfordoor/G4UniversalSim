# G4UniversalSim GUI Agent 开发约束

> **状态与历史的边界（2026-11-04 E4 收尾）**：本文件只记录实现约束与工作规则。阶段完成度以 `docs/ROADMAP.md` 为准，任务级状态以 `docs/collab/CURRENT-SUPERVISION.md` 为准；下方条目中的“作者交付/未验收/未关闭”等文字是历史记录，不构成当前状态。历史全文见 `docs/agent-history.md`，归档快照见 `docs/archive/`。

主题切换须保留焦点、草稿和结果选择。浮动 Dock 和独立向导分别设置数值显示区域，历史草稿校验沿用进程原区域。Qt、图表和 VTK 字体偏好集中在 core/fonts.py。回归入口为 gui_theme_response 和 gui_main_window。

K1 成功且非陈旧的 Generate/Run 完成记录（含 external 无 package）回绑命令预览时，有效 launch 收据的实际 argv 优先；否则显示 record.command 兼容回退，不能把它称为实际启动。逻辑目录来自收据或计划隔离输入树，进程创建目录不同时单列，缺失为未知，不回填编辑项目目录。动作前预览保持原行为，不修改 F5 workspaceRoot。服务 producer 对某项报告 pending 时该项显示进行中，其他层保持各自事实；未知状态保守回退未观测。详见 agent-history 的“K1 命令预览目录与进行中状态”，回归 smoke_k1_workflow.py 与 smoke_k1_panel.py。

K1 搬移配置包时，F5 原始路径草稿只有在与规范模型指向同一已核验资源时才随路径一起重定位；保留首尾空白，不覆盖不同、空白或非法草稿。导入后下一次 GUI 收集不得把规范绝对路径改回无基准相对路径。资源包 staging 与 writer 收据比较规范路径前仍执行原链接拒绝检查；Windows 8.3 拼写不能导致删除后的中间文件被当成外部资源重读。具体反例与验收边界见 docs/agent-history.md 的“K1 配置包搬移与临时目录别名”；候选修复不等于阶段验收。

K1 结果显示绑定实际启动记录的 record_id/run_id/revision；不得凭标签、路径、事件数推断归属。runner 结束后服务尚未核验完成时显示“核验中”，配置变更后顶栏、结果与进度明确标为历史，保留旧日志/计数。显示快照不恢复 F5 内部哨兵或核心验证资格；语言切换、Undo/Redo/恢复和外部资源变化沿同一 state 投影。回归 `smoke_tests/smoke_k1_history_scope.py` 默认组件模式，真实后端模式独立登记；原生可读性仍须实际观察。

目录结果读取、绘图与后处理必须复用 `output/provenance.py`：存在 `run_metadata.json` 时仅使用合法 `generated_files` 清单，校验自身/摘要登记、缺失、重复、路径逃逸及 run 归属；搬移目录按清单原根重定位，不能回读旧路径或自动混入未登记旧文件。缺 metadata 才允许 legacy/unverified 降级并显示警告；清单无内容哈希，不保证文件未被篡改或物理正确。显式文件/list 离线分析保留，但不能借无效清单获取可信运行证据。

external batch/csh 的随机恢复须经过后端守卫，仅支持当前 MixMax/James 原生格式；每事件 restore enable 明确拒绝，MT 不宣称恢复全部 worker。已有 run 后 `/run/initialize`、`/run/reinitializeGeometry`、`/run/physicsModified`、`/run/geometryModified` 拒绝并建议新进程；普通连续 run 保留真实 ID 与文件。测试探针 v3 是保守 assert 入口计数，不是独立命题数量；旧代计数不得直接比较。当前 runner 登记 105 组（static 11 / backend 46 / gui 31 / integration 17），8ecad66冻结矩阵三组全量均105/105通过；实窗与同v3基线门禁亦通过。不能将此工程验收外推为Q2物理正确性。

本文件适用于 gui/。GUI 是 PySide6 外部运行器和配置编辑器，后端 C++/Geant4 的实际实现仍是功能支持的唯一依据。

> 下列历史条目只保留主题索引；全文（含原行号/反例/回归）见
> [docs/agent-history.md](../docs/agent-history.md) 的 2026-11-04 迁移段。

- Linux原生通道补充（主审已签收）：main已实际操作独立真实X11/xcb桌面，一次固定HTTP计划passed，操作观察时曾停在awaiting_approval、0事件；随后在观察期间触及300秒预算，整任务保留failed／…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 L1本轮验收：阶段签收 **本轮约定范围验收完成**，WSLg **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。冻结246e4f6；真实六本机／十二CI与安装重试、…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[README.md](../docs/verification/l1-final-20261102/README.md)、[agent-history.md#2026-11-02-l1本轮验收与交付](../docs/agent-history.md#2026-11-02-l1本轮验收与交付)
- 2026-11-02 L1 AI布局后续候选：52px导致AI全控件不可读是必须修复的新P2，不以旧F6窄边界豁免。OUT候选仅panel按当前文字／样式计算两列最小宽度及footer inset／reflow，不改workspace…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选](../docs/agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选)
- 2026-11-02 L1 路径显示 raw 修复候选：`ProjectPage.show_generated_paths` 仅回显 config/macro/output 三条路径，实际 K1 display binder 不得为显…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-l1-路径显示-raw-修复候选](../docs/agent-history.md#2026-11-02-l1-路径显示-raw-修复候选)
- 2026-11-02 L1配置Agent实施候选：只写既有体积/单能point固定方向源/运行/reference物理/计分的通用字段白名单，读取范围来自UI捕获上下文。默认仅规划，用户审阅差异后以当前新授权批准同plan，`appr…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[L1配置Agent.md](../docs/L1配置Agent.md)、[agent-history.md#2026-11-02-l1-配置-agent-实施候选](../docs/agent-history.md#2026-11-02-l1-配置-agent-实施候选)
- 2026-11-02 J2/F8与E7本轮约定验收完成：测试冻结2ec5b14，后续仅docs/evidence；History真实Label/buddy/provider、焦点/事务/资源及15/7元数据约定见[最终历史条目](..…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-j2f8与e7本轮验收完成测试冻结2ec5b14](../docs/agent-history.md#2026-11-02-j2f8与e7本轮验收完成测试冻结2ec5b14)、[README.md](../docs/verification/j2-f8-final-20261102/README.md)
- 2026-11-02 J2/F8第三修复候选：相关专项独审已完成，完整新候选验收待进行；History只用三个明确buddy及既有语言刷新链，真实QLayout才可递归count/itemAt；F6窄dock界限不修、不放宽可容纳jo…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J2/F8候选：高级详情原文使用原F5模型/事务，按当前实体与字段定位F4诊断；无源恢复不清空，已导入来源丢失不洗白。v7完整快照仅枚举迁移至v8，离线完整编辑包闭合休眠资源。修改前读 ../docs/agent…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J2/F8第二候选：external Inspect不把休眠generated编辑来源当实际输入，但generated来源检查及完整编辑包闭包不变；焦点延迟显露须绑定仍有效、当前、owned控件，新焦点/关闭取消…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-01 I2/J1 已完成约定验收：本机停靠/主题、3D会话覆盖、代表性DPI与重启/运行中切换已实际检查，未做物理跨屏/热插拔。安装后只追加候选并重新发现，布局不改F5/K1或创建第二runner；源码/冻结身份及关闭…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[README.md](../docs/verification/i2-j1-final-20261101/README.md)
- 2026-11-01 I2/J1 候选：安装完成只追加候选并重新执行 I1 发现，不自动选中或运行；自动候选与安装补充候选分开保存。工作区复用原编辑器/runner/实验服务，布局和主题不进入 F5/K1 项目状态。自检须尊重 clo…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-31 K1 已完成阶段验收：资源路径 P1 与永久回归 P2 已独审关闭；5644e1e 新增精确晚变化测试，产品保持2914b39，原生证据沿原身份映射且保留勘误。详见 `../docs/agent-history.…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[README.md](../docs/verification/k1-final-20261031/README.md)
- 2026-10-31 K1 实施中：主实验入口组合现有 EditSession、G4USimRunner、F4 diagnostics 与 package writer，不能另建事务/进程所有者。验证四层分别显示，初始化和真实事件必须…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-31 F5：已完成；冻结5c1eec5、原生5d身份映射及失败历史见[最终证据](../docs/verification/f5-final-20261031/README.md)。完整契约仍在docs/agent-h…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[README.md](../docs/verification/f5-final-20261031/README.md)、[MODEL-POLICY.md](../docs/collab/MODEL-POLICY.md)
- 2026-10-30 F5候选：Project/Configuration共用完整事务，raw非法草稿必须保留并正常阻断Generate；不能由get_project同步清空。普通项目v7恢复完整编辑内容，历史包仍从当前包材料/几何重…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-30 F4阶段关闭记录（已完成）：产品 `7d718d038a00d89995ea773b4772764116b620c3`；Windows 152/152、49913 个 v3 入口与 F1 原始143/48511同…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）；相关：[identity-map.json](../docs/verification/f4-final-20261030/identity/identity-map.json)、[README.md](../docs/verification/f4-final-20261030/README.md)
- 2026-10-30 F4候选：`core/diagnostics` 是统一结构，producer记录 code/editor/collection/row/field/source，不能从翻译报错反推。导航先检查当前快照和完整目标，…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-30 F1异步预设图：OutputPage.show_plot返回true可表示已排队，并不证明图已显示；意图绑定目录和EvidenceJob请求序号，过期完成丢弃，同根refresh保留选择。未知key在ready和…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-30 F1候选：output/provenance统一严格校验新扩展，旧记录明确unverified；历史输入hash不代表当前源文件复核。当前结果根是唯一自动读取锚点，历史快照路径仅作记录。运行与文件身份分别显示。身…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-30 E6阶段已关闭：自动回归与Windows实窗补验见 `../docs/verification/e6-visible-20261030/README.md`；下方候选条目保留实现契约，不能把历史pending或合…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-30 E6 Qt空数据回归：当前Linux Python3.11/PySide6 6.12缺失combo UserRole读取有实证引用损耗，项目标准模型的空数据读取使用widgets/qt_data.combo_da…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-30 E6候选：迁移副本由core计划/发布，窗口不重写格式规则。未知/冲突/重复JSON/非有限/不合法类型拒绝；旧项目仍可按已知兼容规则打开，不强制旧版只读。显式editor不能因空锚点被整对象默认重置；原始JSO…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-29 R32：执行原生 Geant4 交互会话仅允许显式 `--ui --ui-session csh`；裸 `--ui` 或 INI `interactive=true` 未选择 csh 时在初始化及 macro 执…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-29 Q1 R25–R30 当前边界：后端偏置算符按 worker 私有创建；GUI 解读摘要必须区分 master 几何挂接计划与逐 `(runID, threadID)` 的真实 wrapped process、绑…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-29 Q1：项目保存须同目录临时文件写完并原子替换，失败保留原文件；未来版本/未知字段须拒绝并指出路径，不能静默丢弃。刷新结果先清旧证据；扫描 success 必须有正完成数与逐 run 一致性；后端预览仅发布最后请求…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-29 2C 只读有效配置页：`core/effective_config.py` 读取 `g4usim_effective_config_v1`，上限 4 MiB，（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-28 2B 场景页：`widgets/scenario_page.py` 是屏蔽/涂层场景的端到端入口，不是通用编辑器；字段来自（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-27 GUI 源字段保留：Setup 栏的 summary widgets 只能镜像它真正暴露的标量源字段（preset/particle/energy/position/direction）与 physics/sco…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-27 F6：`core/run_progress.py` 有界增量解析版本化 stdout 进度；runner 每次启动重置，分别增量解码 stdout/stderr，退出先排空尾流再判最终结果。RunPage 未知进…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-26 E2：`core/config_schema.py` 只做字段描述/标量必要条件；`structured` 会要求上下文校验，不能吞掉这个结果并当作可运行。动态源/区域/网格及独立几何模板可查询描述，但不扩大 e…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-22 D 安装包：源码与安装包路径只经 `core/install_layout.py` 判断（冻结时 `sys.executable` 是 GUI 本身）：应用根、默认后端（包内 `bin/` 或 `build_vs…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-22 C3 参数扫描：`core/scan.py`（无 Qt）只扫描配置页编辑器能生成的设置，逐点 `apply_value` 深拷贝基准，先 `validate_scan` 全部通过再写任何文件，再用 `create…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-22 C2 新建仿真向导：业务逻辑在 `core/wizard.py`（无 Qt），只产生编辑器已能生成的子集（NIST 材料、box/tubs、点源 fixed/isotropic 与矩形面源、参考物理列表、hits…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-22 C1 内置图表（2026-10-29 修正归一化口径）：数据读取只放在 `output/plot_data.py`（无 Qt，numpy），页面 `widgets/plot_panel.py` 只选数据集/视图、…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-21 M3/M5 Results JSON 导出原型：`widgets/output_page.py` 通过 `output/extension_runner.py` 的 `QProcess` 运行正式 Python…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-21 Rectangle Source GUI 原型：`source_shape=rectangle` 在 generated 模式仅开放 XY 平面、`center`、有限正 `halfx/halfy`，按 `sha…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-21 Dose GUI 原型已开放：`ScoringSettings` 与 `ScoringEditableModel` 双向保留 `dose`（默认 false），writer 只在选择时写 `dose=true`，…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-21 Fluence GUI 实验性原型：`fluence` 默认 false，配置模型、生成包 writer 与 Results / Fluence (mm^-2) 已接通。GUI 按 `(runID, physic…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-21 Source isotropic 输出约束：`angular_mode=isotropic` 时，generated main.ini 只输出 `isotropic=true`，不输出模型中保留供 fixed 模…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-19 Source Editor 数值门禁：运行包中的 `energy`、`position`、`direction`、`radius` 不允许 `NaN`、`Inf` 和超出有限浮点范围的表示；validator 在…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-19 平面源位置映射：Source Editor 的 `Position` 在 `position_mode=plane` 时必须生成 `[source]/center`（三轴及单位），在 `point` 时生成 `[…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-22 界面刷新：主题色只在 `core/theme.py`（样式表 + `build_palette` 的 Qt palette；“系统”主题读 `styleHints().colorScheme()`，因为应用 pa…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 E1 GUI/后端规则一致：材料名一律经 `parsers/materials_parser.material_reference_status`（自定义名去空白后不区分大小写，NIST 名区分大小写，其他 `G…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 G1 后端几何默认显示：配置页 3D 标签可见且勾选“自动显示 Geant4 几何”时，`schedule_backend_geometry` 在修改后 1.2 秒、切换到该页后 0.1 秒发出 `autoBac…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 G2/G3 3D 视图：后端几何与编辑器草图都转为 `preview3d/view_model.ViewItem` 列表，由 `ViewState` 决定可见性（世界、隐藏、单独显示、按材料）、颜色（常见材料固定…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 E2 配置 schema：GUI 对已迁移字段（`[run]`、`[general]`、`[output]`）的检查用 `core/config_schema.check_value`（与后端解析一致：32 位整…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 G4/G5 草图与源：草图几何只在 `preview3d/sketch_geometry.py`（无 Qt/VTK）：数值按后端解析（`ParseDoubleWithUnit` 无单位为 mm/rad，旋转 `P…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 G6 径迹叠加：`preview3d/trajectories.py` 无 Qt，读取一次 run 的全部 worker 文件（默认最后一轮）并按事件排序，schema/单位、跨文件重复事件、体积索引越界都报 V…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-23 E5 拆分：配置页在 `widgets/config/`，每个编辑器一个模块，内含其控件与布局的 QWidget（`SetupPanel`、`MaterialsEditor`、`GeometryEditor`、`…（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-10-29 完整 2C 查看器候选补充（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J3 实施：皮肤注册表与设计系统（第一阶段）（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J3 第二阶段：外壳、命令面板与状态栏（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J3 第三阶段：工作区面板布局（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J3 第四阶段：按页面适配工作区（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-02 J3 第五阶段：导航时 dock 可见性（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- J3 第六阶段：3D 模型树与体积筛选（2026-11-02，作者交付未验收）（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- J3 第七阶段：帮助菜单、快捷键表与关于对话框（2026-11-02，作者交付未验收）（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）
- 2026-11-03 J3 审查响应（历史全文见 [docs/agent-history.md](../docs/agent-history.md)）

## 1. 分层和数据流

- g4usim_gui/widgets/ 负责页面、信号和用户交互；不要把后端配置语义、文件解析或大量业务校验继续堆进单个页面。
- models/、editors/ 保存可序列化的编辑状态；parsers/ 读取现有配置；validators/ 做 GUI 侧早期提示；writers/ 生成运行包；core/runner.py 只负责进程生命周期、日志和状态。
- 推荐的数据流是“源文件解析 → 编辑模型 → GUI 校验 → writer 生成运行包 → 后端再次校验/运行”。GUI 校验永远不能替代 C++ 后端校验。
- 源 materials.ini、geometry.ini 不得被编辑器直接覆盖。编辑结果写入独立 run package，并在报告中记录 copied 或 generated 来源。
- 项目 JSON schema 当前为 G4UniversalSimProject version 7，完整材料/几何与raw编辑草稿一并持久保存，已知1–6版本兼容。`runInputMode` 只保存 `generated`/`external` 机器值；旧项目缺少该字段时，有 config/macro 路径迁移为 `external`，否则迁移为 `generated`。修改字段必须增加读取兼容或迁移测试，不能静默丢弃旧项目状态。

## 2. 后端能力边界

- 每个 GUI 控件必须有明确的后端映射：配置 section/key 或 macro 命令、单位、默认值、校验、writer 输出和至少一个 smoke 断言。
- 后端未实现的功能不得出现在“可运行/已支持”列表中。若需要保留设计入口，必须同时显示“预览”“实验”或“不可用”，在 validator 中阻止生成可运行配置，并在 validation report 中说明原因。
- 解析到但后端会忽略、空实现、占位模板或只用于预览的字段，不得被 writer 静默写出并宣称生效。未知字段要么原样保留并标记未编辑，要么明确提示会被丢弃后再由用户确认。
- 当前 GUI 可生成的后端子集以 writers/main_ini_writer.py、writers/geometry_ini_writer.py 和 editors/source_physics_scoring_model.py 的真实逻辑为准；不要只根据 combobox 的选项扩展支持矩阵。
- `trd` 普通 hierarchical 体积已在 B3 工作区候选中通过五参数表格编辑、writer 往返、GUI package 和真实后端测试；boolean tool 的 `trd` 及 `trap`、GDML、STL、高级 GPS 分布、手动物理模块、biasing 规则、LET 等能力仍须等待各自后端和测试闭环后再开放生成。Dose 与 Fluence 仅开放实验性敏感体计分子集。
- 3D 预览永远不是 Geant4 几何真值；唯一例外是路线图 A5 的“显示后端几何”，它显示后端 `/AIHL/geometry/exportMesh` 写出的 Geant4 实际网格（`preview3d/backend_mesh.py`；G1 起由 `preview3d/backend_geometry_controller.py` 运行，一次一个导出、忙时只保留最新请求、按 `backend_inputs.GeometryInputs.key` 缓存；generated 模式不需运行包，输入规则见 `preview3d/backend_inputs.py`：未编辑文件原地使用以保持 STL/GDML 相对路径，编辑过的须通过编辑器校验），状态栏与消息须注明来源，不得把编辑器近似预览称为后端几何。replica/parameterised 放置在 validator 中只警告（后端支持、GUI 不可编辑），`assembly` 仍阻断。预览不能修改后端配置语义；缺少 PyVista 或遇到不支持 shape 时应显示降级原因。
- 预览读取 `tubs` 时必须保留内半径；除已验证的 hierarchical 普通体积 `trd` 五字段外，读取后端已支持但 GUI writer 尚未开放的 shape-specific 字段时，只能作为只读预览数据使用，不得借此扩大可生成白名单。

## 3. PySide6 约束

- 使用 PySide6 的信号、槽、模型和 Qt 生命周期；长时间运行的后端或合并任务不得阻塞 Qt 主线程。
- QProcess 的 stdout、stderr、退出码、终止/强制结束和日志文件必须保持可观察；不能吞掉用户需要诊断的错误。
- 页面之间通过项目模型和明确的 signal 同步，不要依赖控件当前文本作为唯一状态来源。编辑后必须更新 dirty 状态，生成包前再次从模型读取。
- Project 页更新必须原位应用到现有 `G4USimProject`，不得新建对象而丢失 geometry/source/physics/scoring editor、pathSettings 或 geometrySettings。新项目默认以 Configuration 页为运行来源；generated 模式的 Run 必须先完整校验和生成新 package，external 模式只传递非空的 config/macro 路径。
- generated package 只在当前配置快照下有效。材料、几何、Source、Physics、Scoring、运行参数、output 或 runs root 变化后必须标记 stale；预览不得继续展示旧包为可运行命令，下一次 Run 必须重新生成。
- C0A 的配置检查与实际启动检查分开：新 generated 项目允许空 config/macro，但 Runner 实际启动要求两者都是现存文件；external 至少提供一个文件。无效模式和目录输入必须拒绝，已有进程运行时不得再次生成 package。专项 `smoke_run_input_modes.py` 设置 `G4USIM_EXE` 后必须覆盖 GUI Run → package → QProcess → 摘要中的实际事件。
- C0B 联合入口现为 Inspect inputs / `--inspect-run`：用实际 Configure 和 macro preflight 得到 macro 执行前配置及来源，外部 Run 自动先查询再启动；失败、输入变化或新版查询接口不可用时均不启动。GUI 不复制 macro parser，不根据计划判定运行成功；新版后端是此入口的前置条件。专项必须覆盖 config-only、macro-only、中文路径和 CLI 冲突阻断，等待 QProcess 时使用 `QProcess.NotRunning`，不得用整数 0 比较 PySide6 枚举。
- C4 工作区候选使用 `core/run_result.py` 一处判定 Runner 与历史状态：成功要求正常退出、本次新摘要、后端 completed、macro 完成、至少一个 run，且逐 run 计划/完成事件一致并与摘要总数相符。退出码 0 的 dry-run、interactive_no_run、no_run、旧/缺失摘要不得显示模拟成功；终止/kill、crash、摘要写入失败分别保留原因。`run_status.json` 的 `resultVersion=1` 和摘要指纹供历史页复核，不得只根据状态字符串或摘要文件存在推断成功。
- E 工作区候选确认 GUI generated 模式没有 process-level biasing 规则编辑器；仅启用 physics hook 会被校验阻断，不得生成一个表面上“启用偏置”而实际无规则的包。external 模式仅在 batch 运行时保留显式配置/macro 的后端校验入口；后端目前拒绝 `--ui` 与启用偏置的配置或偏置修改 macro 组合。运行摘要的 `biasing_process_match_status=validated` 不能当作实际偏置效果或 M2 物理验证。
- 文件路径使用 pathlib.Path，生成文件统一 UTF-8 和 LF 换行；Windows 路径不得手工拼接成只适用于单一平台的字符串。
- 运行包生成失败必须保留清晰的字段/文件上下文；不要用 except Exception 把后端契约错误改写成“生成成功”。

## 4. 国际化约束

- 所有面向用户的标题、按钮、提示、校验错误、状态、日志解释和菜单文本必须使用可翻译的消息键；不得在新代码中继续散落硬编码英文或中文显示文本。
- 使用 Qt 的翻译机制（例如 QTranslator 与 QCoreApplication.translate）或项目统一封装；翻译资源、默认语言、运行时切换、持久化和缺失翻译行为必须一并设计。
- 代码标识符、Geant4 命令、INI section/key、输出列名、文件名和外部错误中的原始 token 保持原样；可以在旁边提供中文解释，但不能翻译接口本身。
- 带数值、路径、文件名和后端错误的消息必须支持参数化，不能通过字符串拼接制造不可翻译的句子。
- 当前 GUI 通过 `core/i18n.py` 提供中文/英文运行时切换和 `QSettings` 持久化，覆盖主框架、核心页面静态控件及关键动态状态。新增用户可见文本必须进入集中词典或参数化翻译封装；原始后端诊断、配置 token 和尚未收录的专业文本保持英文，不得用不完整翻译改变其语义。若后续迁移到 `QTranslator`/`.qm`，必须保留现有语言代码和偏好键的兼容性。
- 几何模式等业务选择器必须使用“本地化显示名 + 稳定机器值”：显示文本进入翻译层，项目和 writer 使用 `currentData()`/`findData()`；不得把 `currentText()` 写入 `geometry.template`。旧模板 token 只能作为显式兼容项加载，不得随语言切换改变。

## 5. 主题和可访问性约束

- 主题由集中式 palette/style token 管理，至少规划浅色、深色和跟随系统三种模式；业务控件不得各自硬编码背景色、文字色或状态色。
- 绿色、橙色、红色只能表达成功、警告、错误等语义，并且必须同时有文字/图标信息，不能只依赖颜色。
- 主题切换后要覆盖表格、日志、原始配置、预览、禁用控件、选中状态和错误状态；检查对比度、字体缩放和高 DPI 布局。
- 主题和语言偏好应通过统一配置持久化（例如 QSettings 封装），不能写入项目 JSON，除非它们确实属于项目复现所需状态。
- 当前工作区 `core/theme.py` 已集中提供浅色/深色/系统主题与偏好持久化；该 GUI 展示改动尚未提交，人工视觉、高 DPI 和可访问性检查尚未完成，不能据此宣称 M3 完成。

## 6. 配置编辑器约束

- 编辑器必须区分“后端支持”“GUI 可编辑”“仅预览”三种状态。状态要在控件、验证消息、原始文件/生成文件预览和中文文档中一致。
- 读取配置时保留 section/key、原始值、来源文件和未知字段信息；重新生成时不能无提示地改变单位、默认值、布尔语义、字段顺序含义或删掉用户配置。
- 材料 parser 的源 schema 错误必须与编辑语义错误分开保存；重复校验和编辑不得清空源错误，公共 errors 视图要稳定合并并去重。只要源错误仍存在，生成预览和 run package 都必须保持不可用，不能通过丢弃未知字段表现为已经修复。
- GUI 工作区诊断计数不可把几何 parser 消息与已合入 GeometryDocument 的源消息再次相加；材料源 warning 仍需由 parser 单独计入，因为 MaterialDocument 的语义校验会重建 warnings。生成前验证若编辑模型对应源文件在磁盘上的内容或路径已经变化，应要求重新加载，不可用旧模型继续生成包。
- 材料独立配置文件采用后端闭合 schema；GUI writer 只能生成 `[NIST]`、`[isotope.<name>]`、`[element.<name>]`、`[material.<name>]` 和 legacy alias 的允许字段。旧包中的 `[material.<name>] type = material` 只作为已弃用兼容输入读取，新 writer 不得继续生成；其他 `type` 值或其他 section 中的 `type` 必须拒绝。未知 section/key、空动态后缀和 implicit global 字段必须阻止生成；`temperature`/`pressure` 显示为后端不可用，不得改写成可运行字段。
- 材料、几何、源、物理和计分之间的依赖必须在生成前校验：材料引用、敏感体与 hits、bias 体与 biasing、histogram 范围、源分布与后端能力等。
- writer 只生成后端实际支持的字段。布尔工具不是普通体积，不得给它写 material、sensitive、bias、region 等无效字段。
- 生成包必须能脱离 GUI 运行，报告必须列出所选输入、复制/生成方式、最终配置路径和警告；源文件永远不因“保存项目”或“生成包”而覆盖。
- project_from_dict() 和生成包快照中的兼容字段要有回归测试；修改编辑模型时同步 snapshot、writer、validator、页面绑定和 smoke。

## 7. 测试和文档

- Python 逻辑修改至少运行 python -m compileall gui 及受影响的 smoke tests；涉及 Qt 页面时优先使用 QT_QPA_PLATFORM=offscreen 的无头测试。
- 配置 writer 修改至少运行项目 IO、解析器、材料/几何/源/运行配置 smoke，并在有可执行文件时运行对应后端 package smoke。
- 只有 GUI 字符串、主题或布局修改也必须测试页面构造、状态切换和关键错误显示；截图或人工视觉检查未做时要明确报告。
- GUI 行为改变时同步 gui/docs/中文快速使用说明.md、根目录 docs/功能支持矩阵.md、docs/开发路线图.md 和本文件；面向人类的说明只使用中文。
- 不把 GUI smoke 的“生成文本正确”当作 Geant4 运行或物理结果验证；后端可执行文件未运行时必须单独标注未验证。

## 8. M0-3B2B1 几何 round-trip 保护

- 几何文档与材料文档一样，必须分开保存 `source_errors/source_warnings` 和编辑语义校验消息；重复 validate、编辑或预览不得清空源问题。
- parser 发现当前模型不能无损保存的字段时必须设置 round-trip blocker。B3 工作区子链路已对 hierarchical 普通体积的 `vis.color/alpha/visible/wireframe`、`cut.gamma/e-/e+/proton` 和 `trd` 五个长度字段，以及 layered 的 `auto_stack`、position/rotation、已知 vis/cut 和 canonical metadata 做值保留、校验和 writer 往返；layered 的 vis/cut/metadata 暂无独立 GUI 编辑控件。未知 `vis.*`/`cut.*`、显式 placement、其他 shape-specific 属性、userProperties 或 boolean tool properties 仍须阻断。editable writer 和 generated package 对剩余 blocker 必须拒绝；用户只能显式选择原始 geometry 文件复制模式，并在报告中标明编辑器验证已绕过。
- Run 不得为了通过 generated package 校验而自动打开 `source_copy_mode`。只有用户显式勾选后才可逐字节复制源 geometry；复制模式不等于编辑器验证通过。

## 9. M0-3B2B2 来源诊断对齐

- `parse_geometry(path, template_name)` 在调用方已知模板时必须优先使用显式模板，不得依赖文本启发式；源 warning、legacy metadata blocker 和 source-copy 状态必须跨重复 validate 保留。
- canonical `metadata.<非空名称>` 在可无损保存的编辑模式中不产生 blocker；legacy 无前缀属性只诊断和保留，不自动改名或删除。array/shielding 仍为 preview-only。
- metadata 编辑框只允许 `metadata.<非空名称>`。runtime 字段和旧式无前缀未知字段不得从 metadata 写出；legacy 字段本阶段只保留并阻断，不能自动改名或删除。
- B3 工作区的后端 `version = 2` 严格几何标记须由 parser、`GeometryDocument`、项目快照和 writer 保留，不得误报为 legacy metadata 或静默删去。已验证的 hierarchical 编辑子集可写回严格标记；其他未知字段与不支持的模式仍保持 round-trip blocker 或 preview-only，source-copy 必须由用户显式选择。
- 即使 section 为空，未知 section 也不能在 editable writer 中静默消失；`[layer.*]` 必须出现在 `[layers]/names`。重复 section 或大小写归一后重复的 key 也须设置 round-trip blocker，用户应先消歧并重新加载源文件。

前述 Manager 子集描述保留为历史验收边界；当前集合候选支持阶段/run/thread、对象摘要与两快照差异，继续使用 v1、4 MiB 单文件限制及累计集合限制，损坏加载保留旧数据并标陈旧。requested/resolved 缺失与 null 分开，configuration_generation/revision 不混用，manager_accepted 不译为内核已应用，跨进程 revision 不推断先后。DeepSeek 实际设计参与见 `../docs/collab/outbox/20261029-deepseek-full2c-design.md`。专项增加 `smoke_effective_config_collection.py`；真实后端驱动窗口与整阶段验收仍待主任务确认，不提升为完整 2C 已完成。

F4依赖维护：安装统一走gui/requirements.txt，当前验证线PySide6>=6.11.1,<6.12；不得独立混装shiboken/Essentials/Addons。升级须保留CPython3.11绑定生命周期回归、原失败集成用例自然退出及Windows/Linux矩阵。完整原因与历史反例见docs/agent-history.md的F4依赖条目；这不是物理能力变更。

- 皮肤与颜色必须从 `gui/g4usim_gui/core/theme.py` 的 `SKINS`/`ThemeColors` 读取：页面、图表、3D 预览不得写死颜色；
  新控件若需要主题色，用 `current_colors()` 的角色，不要复制十六进制。
- 样式表分两层：`_base_stylesheet` 是历史契约（对象名、`uiRole`、`buttonRole`、`statusRole` 等选择器逐字保留，测试依赖它们），
  `_design_stylesheet` 是新视觉层并用 `$token` 替换；改视觉优先动设计层，不改基座选择器。
- **`QMainWindow::separator` 不得设置 `width`/`height`**：设成 1px 会让 `gui_workspace_layout` 在浮动态 dock + offscreen
  下于 `apply_theme` 设置样式表时以 0xC0000005 崩溃（已实测定位）。只改 `background`/`:hover`。
- 不要写 `QDockWidget > QWidget` 选择器：`QDockWidget` 的标题容器也是其直接子 `QWidget`，会破坏标题栏渲染。
- 新增皮肤：在 `theme.py` 的 `_RAW_SKINS` 里加 `Skin(...)`，给出 `mode`/`description`/6 色 `series`；注册表会自动做可访问性归一化，
  `scripts/test_theme_registry.py` 会校验 15 皮肤形状与 23 项对比度，`i18n.ZH_CN` 里补皮肤名与描述中文。
- 外观持久化：`appearance/theme`（mode）、`appearance/light_skin`、`appearance/dark_skin`；`appearance/light_palette`
  只作为 B/K 的历史镜像写入，不能再作为唯一真相。`_set_palette` 保留旧语义；`_set_skin` 选中皮肤时切到它所属的明暗组。
- 页面若在主题变化后需要重画（图表、3D、自绘控件），必须实现 `refresh_theme()` 并在 `_set_theme` 的六页列表里登记；
  纯 QSS 能覆盖的控件不要走重画。
- 证据与截图：离屏（offscreen）在 Windows 下没有字体数据库，截图会全是方块；实窗截图用 `QT_QPA_PLATFORM=windows`。
  本阶段交付与边界见 `docs/verification/j3-theme-v1-20261102/README.md`，不要用截图替代独立复验。

- 侧栏分组来自 `ShellMixin._build_workspace_shell()` 的 `nav_groups`；新增导航页必须同时更新 `page_specs`、`smoke_main_window_ui.py`
  的标题/索引断言、`_command_palette_entries()` 的 Page 分组计数与 `i18n.ZH_CN`。
- 页头 `page_crumb` 由 `_on_page_changed()` 按区域设置（index < 5 为 `Workflow`，否则 `Run & analyze`）；新增区域要同步更新该映射与中英词条。
- 命令面板条目必须通过 `_command_palette_entries()` 提供；过滤顺序是“标签严格匹配 → 类别/说明回退”，`Up/Down` 必须跳过组标题，
  不要恢复成整串子串匹配（那会让 `pa` 命中所有 Page）。
- 外观条目计数（15 个）必须与 `theme.SKINS` 同步，否则 `gui_command_palette` 会失败；选择外观时 `_set_skin()` 会切换到其明暗组。
- 状态栏常驻控件用 `addPermanentWidget`；`statusMeta` 只显示外观名与描述，不放运行证据或后端能力。
- 实窗截图用 `QT_QPA_PLATFORM=windows`；离屏无字体数据库，截图会全是方块。截图不是独立验收。

- 3D 视图的视点/投影控件必须是两行网格（`QGridLayout`），不要改回单行 `QHBoxLayout`：右侧 dock 在某些窗口宽度下
  只有 ~420px，单行会把 “World / Orthographic” 裁出可视区。
- 图例宽度、剖切滑块最小宽与配置 setup 面板宽度是为窄 dock 调过的（168/80/300），改大时先复跑
  `gui_3d_view`、`gui_config_editors`、`gui_workspace_layout` 并在 1560×980 抓图确认不裁剪。
- 状态栏的恢复状态标签是单行 + tooltip（`window/recovery.py`，最大宽 320）；不要再开 `setWordWrap(True)`，
  它会与外观状态标签一起被右缘裁掉。
- 键盘焦点必须可见：`QToolButton:focus` 用 `focus_ring`，侧栏导航 focus 用 `sidebar_hover`；新增自绘控件时补同等焦点样式。
- 撤消/重做的图标来自 `_refresh_icons`，`transactions.py` 建完工具栏会补刷一次；新增工具栏动作要遵循同样的着色路径。

- `WorkspaceLayout.preset_for_page()` 是页面 → 预设的唯一映射（0–4 `configuration`、5 `running`、6–8 `analysis`）；
  新增页面时要同步它、`smoke_command_palette` 的 Actions 计数与 `smoke_workspace_layout` 的预设断言。
- “Fit workspace to current page”（`Ctrl+Shift+L`、`workspaceFocusPage`）与命令面板 Actions 条目都调用
  `focus_current_page()`；该动作只允许 `apply_preset()` + `reveal_current()`，不得改页面内容、项目状态、运行状态，
  也不得在页面切换时自动触发（会覆盖用户的手动预设/隐藏）。

`WorkspacePageStack.reveal_current()` 必须在离开停靠页时隐藏该页 dock；Results 页导航需收起 preview/ai 并显示 logs
（`WorkspaceLayout.focus_analysis_view()`）。截图取证不得在抓图前恢复配置预设。回归见
`gui_workspace_layout` 等 7 例、2022 断言与 `docs/verification/j3-analysis-docks-20261102/`。

- 模型树数据只能由 `gui/g4usim_gui/preview3d/model_tree.py` 的 `build_model_tree()` 从 `GeometryDocument` 生成；
  控件层不得自行推断父子关系或重复实现几何解析。
- 3D 选中与树选中必须双向同步（`select_volume` → `_sync_model_tree_selection`；树 → `volumeSelected`），
  过滤时保留命中节点的父链；`set_model_tree(None)` 同时隐藏标题、过滤框和树。
- 打开「3D Preview」标签自动绘制几何的入口是 `ConfigBuilderPage._on_workspace_tab_changed` +
  `_preview3d_tab_index`；该索引必须用 `tabs.count() - 1` 取（标签页包了 scroll 区域，`indexOf` 返回 -1）。
- 回归：`gui_model_tree`（离屏仅纯函数；widget 联动需 `QT_QPA_PLATFORM=windows` 直接跑）、`gui_3d_view`、
  `gui_config_editors`、`gui_workspace_layout`、`gui_main_window`、`gui_command_palette`、`gui_k1_panel`；
  证据 `docs/verification/j3-modeltree-20261102/README.md`。

- 快捷键表数据只来自 `ShellMixin.shortcut_rows()`；新增/改名快捷键必须同步它、菜单 action 的 `setShortcut()`、导航 tooltip、
  `_refresh_accessibility()` 的描述与 `i18n.ZH_CN`。
- 关于对话框文本只来自 `about_text()`（GUI/PySide6/Qt 版本、`install_layout.application_root()`、`default_backend_executable()`）；
  不要在其他页面重复拼环境事实。
- 快捷键表对话框用 `build_shortcut_dialog()` 构建（测试与截图用非阻塞版本），只有 `show_shortcuts()` 才 `exec()`；
  表单必须放在 `QScrollArea` 里，避免小屏/高缩放下行溢出到按钮下方。
- 回归：`gui_help_menu`（34 断言）与 `gui_main_window`/`gui_command_palette`/`gui_theme_response`/`gui_j1_appearance`；
  证据 `docs/verification/j3-help-20261102/README.md`。

主题切换不得改动编辑器草稿、输出文件选择、当前页面与工作区标签索引；外观偏好只能写入本机 QSettings（`appearance/theme`、`appearance/light_skin`、`appearance/dark_skin`），不得进入项目 JSON 或实验包。回归入口 `gui_theme_state` 与 `gui_theme_response`。运行中任务、K1 输入资格与 Undo/Redo 栈在切皮肤时的行为仍待补测。

- 外观菜单由 `_sync_appearance_actions()` 统一刷新：当前皮肤带“当前使用”，另一明暗组记忆项带“下次使用”；不要只改勾选状态。
- `theme.current_skin()` 读 `QApplication` 属性；把窗口传进去会静默回退默认皮肤，测试里曾因此恒真通过。
- `QLineEdit#paletteSearch` 的边框必须用 `border_strong`（3:1），不能用 `border`。
- 紧凑布局（<1400 逻辑像素）隐藏 AI 面板与 3D 预览，这两个是可选 dock；不要隐藏配置编辑器或 Results 页的停靠页。
- 紧凑区间内的 resize 不得覆盖用户显式打开的可选 dock。三个入口都算显式选择并写入 `_optional_overrides`：dock 自己的 `toggleViewAction`、配置页的 “Show 3D view” 按钮（`_show_preview_from_button`）、恢复已保存布局（`restore()` 按恢复后的可见性记录）。被页面导航自动显露的 AI/3D 没有覆盖，仍按紧凑规则收起；离开区间只恢复被自动收起（`_auto_hidden`）且用户未覆盖的面板。`apply_preset()`/`reset()` 清空覆盖，`restore()` 不询问用户、按保存内容直接记录。永久回归 `gui/smoke_tests/smoke_compact_panels.py`（独立复验的 1200→1205、配置页按钮、保存/恢复两个方向）。
- 视觉证据在 `docs/verification/j3-visual-checks-20261102/screens-v2/`，语义色表在同目录 `semantic-colours.md`。

- 状态标签（`uiRole=statusChip`）的文字不能直接用语义色画在它自己的 veil 上：成功/失败/运行中分别使用
  `status_combinations()` 派生的 `$success_text`/`$danger_text`/`$running_text`。`veil_text()` 会把语义色向可读锚点
  混合到 ≥4.6:1，并保留成功/失败/运行的色相含义；独立 J3 整体验收用真实 QLabel 量到 B/K/苔原的成功文字只有
  4.35/4.35/4.31:1。新增语义色、改 veil 混色比例或新增状态标签时，必须同时更新 `status_combinations()`、
  `scripts/test_theme_registry.py` 的最终组合断言与 `gui/smoke_tests/smoke_theme_response_shell.py` 的真实控件取色。

- F2 GUI 连续运行会话与 RNG 重放（2026-11-04；F2 约定范围已验收，限制见支撑矩阵）：`core/session_model.py` 只放协议常量、
  资格、能量解析与收据校验；`core/session_client.py` 绑定既有 `G4USimRunner`（禁止第二个 QProcess
  所有者），经 `runner.start_session()`/`sessionData` 驱动，不阻塞 Qt 主线程；`widgets/session_panel.py`
  是 Run Console 的四区面板；`window/session.py` 负责生成包、记录根（output 外）、所有者互斥、重放启动。
  文案走 `core/i18n.py`；收据必须按路径/大小/SHA 校验，`receipt_integrity=unavailable` 显示“运行完成但
  记录不可用”。会话正常关闭且清单可重放时按钮才启用，重放在新后端进程/新输出目录执行，不得伪造
  逐位一致，也不得宣称旧 csh/batch 可重放。回归 `gui/smoke_tests/smoke_session_panel.py`、
  `gui/smoke_tests/smoke_session_backend.py`（真实 2 轮源会话 + 按钮重放 2 轮）与
  `scripts/test_session_replay.py`（1/2 worker 正例与拒绝矩阵），注册在 `scripts/run_m0_tests.py`。

## 导出独立 Geant4 工程（K2-2）

- 入口：`main_window` 的 Project 菜单动作只调用 `window/experiment.py` 的 `export_geant4_project()`；真正的数据准备/写入在 `core/export_project.py`（无 Qt），GUI 只做目录/名称选择与消息展示。
- 启用条件：动作在项目不可导出时禁用，原因来自 `core/export_project.py` 的 `project_export_problem()`；不得在 GUI 里另写一套校验或静默降级。
- 后端按进程 cwd 解析路径；导出只重写 `project/main.ini` 中已存在的白名单键（`[output] dir`、`[materials] file`、`[geometry] config`、`[parallel_world] geometry_config`、已有 `[run] macro`），不插入新键，不改变物理/计分语义。
- 模板身份来自 `packaging/export_template_manifest.json` 与安装包 `export-template/`；不得硬编码历史 digest（如 1862a858），checkout 与打包模板必须同身份。
- 导出的工程不含 GUI、后端可执行文件、Geant4 SDK/数据；GUI 不得声称导出成功即代表工程可构建或物理正确。相关事实与限制同步到 `docs/独立工程导出.md`、`docs/功能支持矩阵.md`。

