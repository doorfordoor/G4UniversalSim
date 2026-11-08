# AR0 重审：AR0–AR6 有限差异合同（r3）

日期：2026-11-08。状态：主审草案，待独立复审冻结；不表示 AR1 已实施。

本合同按[最新授权](20261108-ar0-ar6-primary-ownership.md)补齐完整架构迁移的比较边界。原 r2（SHA-256 `c873566f74e5d7f247cb02fe484375d493f4a22798479c4b97ce60705a084a2d`）和[原冻结附注](20261108-ar0-contract-freeze.md)保留；未被本文件明确修订的事实、外部格式及原科学判据继续有效。旧 AR0 通过是历史事实，本次重审不记作产品失败。

## 1. 有限差异及理由

|编号|修订|理由与边界|
|---|---|---|
|R1|实施范围扩到 AR0–AR6；本地主审及非 web 子代理实现、独验|来自用户新决定。AR2 不再暂停；DeepSeek/web 至完整架构验收后才恢复。F3 不追加测量|
|R2|区分已接受几何来源与全局“实际读取”账本|`InputProvenance.cc:86–123`在解析接受前记录实际读入字节；失败 B 被读到是事实，不能为事务回滚而删除。AR1 回滚的是已接受模型/来源，不是审计历史|
|R3|事务比较以调用 `LoadGeometryConfig(B)` 前的状态为准|此前成功的 `SetTemplate`/用户编辑是独立动作；不要求跨命令回滚，也不宣称任意初始化后 Geant4 重建回滚|
|R4|H3 工程与科学入口分别绑定具体脚本/输入/判据|原 `parallel_world` 工程测试不能证明 B/C 科学等价；本次定位可执行入口，按实际影响触发有限比较，不重新开放旧科学适用域|
|R5|增加 AR3 的运行编排、配置时序和失败收尾比较合同|旧 r2 只有来源/生命周期测试集合，未给运行编排迁移的责任和阶段界限|
|R6|增加 AR4 的真实状态拥有者及无 QWidget 编辑验收|旧 r2 明确将该测试留在批外；扩大授权后需要覆盖，继续保留 raw 草稿和交互状态|
|R7|明确 AR5/AR6 的新模板、双平台包和安装后实际导出要求|旧 K2 安装证据为限定组合，不能自动抵作本次规划中的实际安装入口操作|
|R8|统一候选/报告复用、逐阶段冻结和回退约定|用真实变更影响控制验证成本，不把“重审”变成重跑 K2 全矩阵或新验收平台|

## 2. 身份、版本和不变量

- 产品基线：固定标签 `k2-closed-pre-architecture-20261108`，提交 `25487eb13432c5f4e968aa405607056f6a8febce`；不移动标签。D 盘为交付工作树；C 盘 `h2-final/G4UniversalSim` 为独审工作树，其旧 HEAD `55ef3d62` 不冒作新候选。
- 本次接管逐文件快照：`out/collab/20261108-ar0-ar6/independent/takeover-baseline.json`，672 个受跟踪源码/测试/GUI/打包文件；接管时产品内容 diff 与暂存均为空。大量既有文档/证据保留，逐文件归属，不全仓暂存或清理。
- 外部 INI/macro/CLI、项目 schema v8、已有 CSV/ROOT/JSON 语义及 K1/K2 路径合同默认不变。内部值结构不构成新文件格式。确需改变公开格式必须在该阶段实现前另列兼容决定；不能临时静默改默认值。
- 最终架构交付应用版本 `V_AR=1.1.0`，与 Geant4 11.3.2/11.4.3 版本独立；AR5 冻结稳定源码时同步实际版本源，AR6 两平台包/后端/安装信息须一致。GUI Python 模块当前独立版本为0.1.0（`gui/g4usim_gui/__init__.py`），不能从其About显示反推应用包版本；本次不以无依据的统一改号掩盖身份差异。当前旧应用1.0.0产物保持原身份，不提前改其记录。
- 仅同配置、同平台/编译配置/数据/种子/线程模式、同算术顺序且可确定的量要求严格相同；其余沿用原数值/统计判据。自然变化白名单沿 r2 §9，仍检查新时间/路径/commit/执行 ID 与实际产物一致。
- `entries` 是非零贡献 history 数；`n_events` 包含零贡献 history。按实际 scope/run/thread 对账；不得强令 entries 等于事件数。H2/H3 质量、ghost、步权重、分母、边界和普通 hits 隔离维持旧合同。
- 带电 XS factor10 原失败、factor1.2 限定病例、强子 LET/DDD/NIEL 未验证域、WSLg RAIL 失败及 F3 inconclusive 均保留。不因架构通过扩大科学结论。

## 3. AR1 真实事务合同

**调用边界：**已有合法配置 A 和用户附加体积，直接使用当前 Manager 公共接口调用 B；先保留旧实现失败证据，随后候选修复。覆盖重复名、缺 parent、第二个附加节点失败；若某路径被真实接口阻止，记录拒绝位置及不可达证据，不用字符串搜索代替运行。

**必须不变：**失败前后的模板树、最终树、用户覆盖、成功几何路径、Manager `inputFiles_`、effective reader/字段/accepted generation、现有 runtime registry/资格以及 dirty 状态。全局 EffectiveConfig revision 若本次调用未提交，保持不变；不捏造一个 GeometryManager 本来没有的 revision 字段。捕获快照不创建 Geant4 对象或修改被测状态。

**允许变化：**本次失败诊断；全局 `input_provenance::Snapshot()` 按真实读取新增 B 的 `recorded` 条目。该条目是 bytes-read 事实，不能成为 B 已接受/已应用的证据。加载前已成功的 SetTemplate/用户编辑不回退。成功 C 必须整体更新模型和已接受来源，并按原合法时点标 dirty。

实现先构造可验证候选及其来源，再一次发布。发布前的分配/字段投影/用户附加校验均不作用于现有有效模型；不得只保护 root 指针。`ConsumerState::Accept` 是可分配的状态操作，不能简单放在已换树之后再声称强事务。测试覆盖实际异常点，不要求制造任意 OS/内存故障全集。

box/tubs 为第二个独立切片：保持半长/角度/单位/别名及 boolean tool 语义；C++ VolumeNode 代码构造与文件读取均消费同一规范参数。其余形状保留有名兼容适配，不扩全部 typed 形状。GUI Python 预览和 H3 自有 G4Box 构造不是质量世界 builder 的直接消费者；仅按实际共享语义补验。

最小入口沿原 geometry_safety/diagnostics/a5、有效几何来源和 roundtrip；实际构造变更才扩大到默认几何/H3 边界/K2 S-A/S-B。新增真实事务探针和受控参数测试归 AR1，不归 AR0 重审。

## 4. AR2 描述、工厂与线程合同

沿原 AR0/规划：不可变配置描述 → 已登记工厂 → 每线程独立实例 → 每 run/event 累计 → 既有输出通道。描述不持有可变 writer/累计器；共享大表须证明只读。实际 Action/SD/parallel 消费点迁移，不仅新增一张无人调用的注册表。

空工厂/空实例、重复 id、未知 type 为负控；legacy `RegisterScorer(unique_ptr)` 必须有明确重建适配或在进入不支持的运行克隆路径前拒绝，不能静默丢失。`ActionInitialization::Build` 的 sequential 和 worker 都调用 clone，故只阻止 MT 不足；直接调用 Manager 的旧对象注册与经 Action 构造的运行路径分别验证。不得以新增强制纯虚方法破坏旧实现。worker 构造失败要有实际失败收据，不能写成功摘要。

确定性测试 scorer 只证明扩展接线，不新增科研能力。1/2/4 worker、连续两个 run、零贡献事件、实例/事件集合隔离及异常路径是必要比较；sequential 构造另用真实可用入口或明确的 Action/组件调用覆盖，不能把 MT 单 worker 写成非 MT 内核已测。新扩展仅需实现/登记/测试，不改 main 或中央内置分支。内置 Edep/Dose/Fluence/LET/DDD 原数值及 H2/H3 输入/统计/输出语义保持。共享统计和输出算法原则上不改。

## 5. AR3 运行协调与会话合同

当前事实：`SimulationManager::Configure`（基线 898–1047 行）依次解析主输入、配置材料/几何/物理/场/源/计分/mesh/偏置/parallel，随后重应用 CLI、应用模块模式、捕获来源，再设置 configured；`main.cc`承担预检、内核装配、macro/csh/session-server 分流和退出映射。`FinalizeRunSummary`集中 Flush/Close、失败锁存和输出身份。移动代码不改变这些合法时点及依赖顺序。

先抽配置协调，再抽运行会话和收尾；每片独立候选，保留 SimulationManager 兼容外观。迁移计划引用已接受值及 generation/资源身份，是配置的表示，不建立另一套可写 Manager 缓存或把读取 INI 当成 kernel/thread applied。合法 PreInit macro 和多 run 继续生效，需真实粒子/几何的检查仍在原阶段。

最低比较：`config_precedence`、`macro_plan`、`command_state_gating`、`run_summary`、`interactive_commands`、`effective_lifecycle`及直接受影响 effective_*；涉及受控服务/重放时必须包括 `session_protocol`、`session_cancel_mt`、`session_replay`。覆盖 configure-only/inspect/dry-run/batch/csh、无 run/正常/取消/多 run/失败收尾；保留原首因、命令来源行号、preflight 无返回码语义及非零退出。内部 Messenger 返回 0 的失败计数仍可阻断后续执行。收尾最多一次，不能因拆层重试 BeamOn/重复发布文件。

需要改变随机数派发、物理装配次序或公开命令默认值时停止相关切片，先形成行为变更决定；不能混入结构整理。

## 6. AR4 编辑状态合同

GUI专项见 `out/collab/20261108-ar0-ar6/independent/ar0-gui-build-review.md` §2；基线 `window/transactions.py:278–332 capture_workspace()`先读Project控件、调用J2/明细采集修改页内模型，再拼快照，不能视为纯读取。`apply_workspace():398–505`负责反向投影；`EditSession.transact/replace(expected_revision, apply=...)`已有无需QWidget的事务引擎。迁移复用它们，不再新造事务框架。

|字段组|基线实际写入口/拥有者|迁移后的有限比较|
|---|---|---|
|run/path|ProjectPage.apply_to_project、config/setup_panel/run_config、G4USimProject的flat/settings|数据编辑入口写候选快照；旧显式flat/typed不一致按原加载规则保留，实际编辑才按对应入口同步；保留seed原文和生成路径显示回绑|
|source/physics/scoring|ConfigBuilderPage活动model及J2 collect_into/明细apply_row|字段/扩展行顺序、无效raw和writer语义保留；L1受限Apply仍需验证，人工无效草稿可以暂存，两者共享session不混淆准入规则|
|material/geometry|活动文档、明细raw、表文本/pending cell、捕获源文本/summary|模型动作能编辑/恢复文档与未提交文本；保留None与显式空文档、原文/读取失败/blockers；恢复不重新读源文件替换证据|
|运行证据|ExperimentWorkflow持有同一session/runner/inspection；session_id/revision/epoch绑定|不进入Undo快照；显示binding不是新所有者；取消/旧epoch拒绝，历史结果不成为当前资格|

按 run/path → source/physics/scoring → material/geometry 串行切片，每组用有限数据转换（稳定绑定/实体标识、原始文本→新快照）进入原事务，capture只保留未迁移内容及窗口交互采集，已迁移领域值从模型取得。raw/表格/选择的完整codec比较不能只看snapshot fingerprint：原fingerprint排除selection及派生值，selection-only不增加dirty/revision/history的合同继续保持。投影失败/回滚失败分别保留，故障状态继续阻断保存、生成、运行。

无需 QWidget 可编辑、序列化、恢复已迁移领域值和无效草稿；界面适配只提交动作/显示投影，焦点/选择等交互事实允许来自控件。运行证据按 request/revision 保持历史，Undo 不恢复当前运行资格。真实窗口覆盖半输入、未提交单元格、坏路径、外部材料变化、保存/重载/Undo/Redo/恢复，以及取消/切项目迟到结果拒绝。L1/K1 沿同一事务入口；不同时实施 J4 界面流程改版。

有限复用case：共用static `f5_transactions/f5_source_snapshots/f5_project_receipts/project_snapshot_compat`及gui `gui_f5_editor_history/gui_project_import_projection`；run/path用`gui_run_config/gui_k1_window/gui_k1_relocation`及integration `gui_run_inputs`；S/P/S用`gui_source_field_preservation/gui_j2_run_editors/gui_config_agent`及`gui_config_agent_backend`；文档用`gui_j2_materials/gui_j2_geometry/gui_geometry_diagnostics`；恢复/历史用`f5_recovery/gui_f5_recovery/gui_f5_recovery_process/gui_k1_workflow/gui_k1_history_scope/k1_history_scope_backend`。同一共用代码不变时不重复整套。`gui_k1_workflow`是组件入口，不充当实窗证据。

仅需一个新增static case（拟名`ar4_edit_model`，实施时注册）逐组覆盖实际数据入口的run_path_without_widgets、sps_without_widgets、documents_without_widgets、publication_failure_without_widgets；不创建QApplication/QWidget，不只手工组快照证明旧codec可用。至少含`seed='1e'`/空值/空白坏路径、源能量/物理/scorer及J2扩展行、一行材料/几何/pending cell、旧revision/容量/转换失败。实际投影/回滚仍用原回调合同，不伪称无窗口测试证明实窗可用。

## 7. AR5/AR6 构建和交付合同

构建专项见上述GUI/构建报告§3/4。基线应用使用107个src源；parallelScoringCheck重复全部源，h2VolumeScoringCheck列22个生产源，另有gdmlInputCaptureCheck/scoringNumericCheck/randomCommandGuardCheck；HistoryStatistics/InputProvenance等已有多个真实消费者。mergeHistograms独立于Geant4，应保持。只有存在独立消费者或测试的纯逻辑/Geant4适配/应用装配才拆target，同一生产源有明确归属；不迁全仓目录、不升级依赖、不重做安装器。

冻结target→源/头/定义/includes/link libs映射；同时核CMake枚举、Python fingerprint选择器、K2模板、SDK/source snapshot的各自消费者闭包，不能要求不同集合机械相同。新后缀/嵌套cmake须同步枚举；当前模板只收顶层cmake，需按实际新增依赖补全。source/header/build-input fingerprint与实际构建一致；在隔离副本以`shared_target_header_rebuild`受控探针验证真实依赖目标重建，无依赖目标不要求SHA改变。保留K2既有单行SimulationManager.cc修改对照，不增加编译性能测量。

最小复用static `build_identity/k2_project_export/solid_registry/install_ci_delivery/frozen_startup/platform_install_layout`、gui `gui_export_project`，模板check及独立CMake/CTest。standalone ON仍不注册m0_*，组件标签恰为`h2_volume_scoring_check`/`parallel_scoring_component`；Windows用已有vs2026-x64，Linux沿已验Unix Makefiles配方，不猜Linux preset。R1–R12拒绝、临时staging/目标不变语义继续由既有用例保护。

稳定候选重新生成模板闭包，成员数由实际依赖决定，不固定 309。Windows/Linux 原生构建和 Linux 11.3.2/11.4.3 范围保留；仓库外 S-A200/S-B1000、两个 component、拒绝路径、一行 C++ 修改后重建均需新候选证据。直接安装版导出入口必须实际操作验证；不拿旧源码入口/模板检查组合抵替。安装/卸载使用明确隔离测试目标，保留用户既有安装与数据。

AR6冻结最终源码/测试/模板/版本身份后运行原正式profiles：`.github/workflows/m0-static-gui.yml`的Windows/Ubuntu static+gui；`linux-geant4.yml`的11.3.2/11.4.3各static/gui/backend/integration；另`desktop-package.yml`/`full-installation.yml`产生真实双平台桌面及完整安装证据。原12报告734/376754只按64bac原身份引用，新数量允许合法重组，旧合同/负控须映射；逐报告`--require-tracked-sources --fail-on-skip`及严格证据检查，skip/环境拒绝/unknown不记通过。

每平台从新包真实安装prefix启动冻结GUI，工作目录在安装树/仓库外且不借开发PYTHONPATH，记录程序/模板/backend实际根及SHA。两个固定输入均由安装程序实际导出，每平台至少一次完整Project→Export Geant4 project菜单动作；可自动应答文件对话框但记录范围并真实查看结果。导出前后核manifest/逐成员/template identity，随后承接仓库外构建运行及正常退出；不能把构建后新增产物混作原始导出清单。构建、安装、运行、卸载、命名及可分发包SHA分别取证，证据ZIP不冒安装实物。完成组件扩展指南、迁移/回退说明及真实“修改组件→测试→独立导出继续开发”路径。

## 8. 科学比较入口和证据复用

H3 已定位完整历史执行链，详见 `out/collab/20261108-ar0-ar6/independent/ar0-h3-executable-review.md`。本次子审实核 18 输入及 834 产物哈希，并只读复算原 B/C 区间一致；未执行新模拟。历史根 `out/collab/20261107-h3-4-benchmarks` 的 `scripts/prepare.py → run_benchmarks.py → analyze.py` 为真实入口；独审根 `out/collab/h3-4-independent-r3` 保存原 gate、程序和复算。旧脚本写固定输出，**不能原地重跑**，也不能仅设置 G4USIM_EXE 冒称已切换候选。

身份：原 manifest `da0f7f8c36d53c8a3aabd2225831cfd2cf777a5e29cf3405146874f0bb8fa40a`；原程序 `3700e27240a06b865949b0a8a48ba2d47f2af689acc515a428c14f05096c90c3`；原组件 `34066c138f518e8533f10543759f860cd8f47a01c833bc359217a1fe2ca5c4cd`；原 source fingerprint `c7de5a3c819079cd14765d89e22c4570aba54523b17ce6fa51d513f1207e4be7`。旧执行 git_head 83c0b139 与本次标签不同，不混写。prepare/runner/当前修正 analyze 的 SHA 及旧 gate analyze 差异详见专项报告；B/C算法未改，R-RUNTIME/R-COMP纠正与旧失败均保留。

**限定触发：**AR2 改默认 scorer 构造/spec 适配/TLS/run-event 回调，或改 dose/fluence 路由、分母、过滤/谱/累计，必须执行一次预先冻结的新候选 H3 比较任务。纯文档及证明不影响这些量的变更不触发；AR1 质量世界 builder 变化先分析共享语义，不因 H3 自造 G4Box 就机械重跑。H2 同时使用真实 `test_h2_benchmarks.py --work-root <新目录> --json <新报告>`，显式 G4USIM_EXE；工程 `parallel_world` 仍独立保留。

**协议不变：**H3 原 72 项为 71 后端进程+1组件，不是72次独立批次。A/A2/A2f先行通过才进科学批次。B 两臂各16×2000事件：mass种子20261401–20261416、parallel种子20261417–20261432；C 两臂各16×2000：enabled种子20261433–20261448、disabled种子20261449–20261464。threads=1、Geant4 11.3.2、FTFP_BERT、cut0.1mm、10MeV质子及18输入维持原身份/顺序；逐批CLI种子不能被INI首种子替代。B取mass/ghost的每事件加权剂量；C两臂都取质量层，不把probe剂量作端点。完整 Welch 99% CI须落在±1%/±0.5%两臂均值内；跨边界=inconclusive，不能limited签过。不换种、不增删批、不看结果后改容差。

**AR2实施期的有限适配工作：**在新的 `out/collab/<候选名>/scripts` 复制已核脚本（保持既有parents[4]目录约定），只参数化候选 EXE/组件/实际source fingerprint、输出根及脚本/合同身份。准备、runner、analyze必须读取同一冻结候选，不能只在准备进程内临时改变量而让runner重新导入旧常量。新manifest重新生成argv/cwd/output路径，18输入内容、72项顺序/种子/N按原manifest逐项对账；纠正新manifest的generated_by/rebuilt身份和R-RUNTIME真实hits表头说明，旧manifest不改。新analyze从manifest的contract.sha256/freeze.sha256读真实合同身份，不能保留错误字段导致null。适配器源码/新manifest由独审检查后才执行。该项只为复用原有限科学协议，不建设新通用平台。

执行命令固定为新目录内 `python -B <trial>/scripts/run_benchmarks.py`，先独核 execution.status=completed、halted=null、executed_runs=72、run_order及各项退出/预期产物，再 `python -B <trial>/scripts/analyze.py`。runner exit0并不保证完整执行，analyze exit0也可能inconclusive；须检查全部case verdict和完整B/C区间、实际产物SHA、原R-SAME/M/R-RUNTIME/R-COMP工程不变量。原独算脚本会写历史结果且绑旧analyze SHA，不能直接运行覆盖；新独算另设输出目录。SciPy/数据集/DLL/程序实际能力在新候选预检核实，不把旧文件存在当可启动。

科学等价与迁移前后保持分别取证：原B/C协议验证限定科学关系；原内置数值测试和同配置可确定量比较保护绝对单位/分母/计数，不能只凭两臂共同偏差仍过B/C宣布迁移正确。新候选实际结果未知，本次复算旧区间不作新AR2通过。

每阶段先最小反例/直接消费者，稳定后再扩大正式层。旧报告仅在源码/输入/测试/行为影响确实未变时按原 SHA 引用；新编译产物不冒用旧 source_fingerprint。长任务留 session 和日志，不重复启动。两次有证据的同类环境失败后换方法，不能无穷增加批次。F3 时间/内存测量与本合同完全分开。

统一测试命令形态（路径使用该候选真实绝对值）：`python -B scripts/run_m0_tests.py --profile <static|gui|backend|integration> --case <已登记名称> --executable <candidate> --report-root <新证据目录> --fail-on-skip`；正式门禁再加 `--require-tracked-sources`，报告用 `scripts/check_report_evidence.py --report-root <报告根>`独核。实际命令与 exit/日志 SHA 入收据；仅帮助或静态读取不称测试通过。

## 9. 冻结和回退

本 r3 完成专项补齐后由未编写本文的独立审查者核对，主审签收形成冻结收据。AR1 才开始产品修改；各阶段开始前再冻结有限文件/接口清单，阶段后保留可回退提交、原反例、实现自测和独验结果。

只暂存本次明确归属的文件。回退按切片撤销生产变更，不删除原失败/测试证据、不原地改用户项目。新文件进入正式门禁前须在 Git 中受跟踪；不能用放宽门禁掩盖新增源码不入库。AR6 未完成前不恢复 DS/web，不用阶段内自测冒称整架构验收。
