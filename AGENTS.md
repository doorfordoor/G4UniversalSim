# G4UniversalSim Agent 开发约束

本文件是仓库级约束，适用于根目录及其子目录。更具体的目录约束可以由更深层的 AGENTS.md 补充；gui/AGENTS.md 适用于 GUI 目录。

## 0. 条目索引与历史全文

2026-10-19 → 2026-10-27 的 29 条实施契约全文（含文件路径、行号、反例与回归入口）在 [docs/agent-history.md](docs/agent-history.md)。下表只列**仍然有效的操作规则**；改动相关模块前必须先读对应历史条目全文，只读索引不足以动手。新增条目：全文追加到 `docs/agent-history.md`，本表加一行，不要再在本文件堆长段落。

- 2026-10-28 命令失败传播：`/AIHL/biasing/*` 修改类命令在交互会话里被拒绝时必须计入交互失败（`interactive_command_failure_kind = biasing`）、停止会话、写 `status=failed` 并非零退出，不得只 `JustWarning` 后继续跑未偏置物理；`/AIHL/material/*` 的 9 个修改命令只允许 `PreInit`（`print`/`list` 只读不受限），初始化后调用由 Geant4 拒绝并让会话失败（`geant4_illegal_application_state`），batch 的 `main.cc` 守卫保留为纵深防御；`ParseStrictDouble` 拒绝 `inf`/`nan`/溢出值（`Config value '<v>' is not a finite double`），数值配置字段不得以非有限值进入偏置权重或可视化属性。回归 `scripts/test_interactive_commands.py`（biasing/material 两个新用例）、`scripts/test_config_value_finiteness.py`。
- 2026-10-28 证据门禁自洽性：`scripts/check_report_evidence.py` 必须校验逐用例断言 ≥1、`exit_code == 0`、逐项求和与 `assertions_executed_total` 一致、`cases_with_zero_assertions`/`cases_with_assertion_counts` 与实际记录一致、`log_sha256` 与实际日志字节一致，发布报告不得含 fail/skip；日志与报告用 `write_bytes` 写 UTF-8/LF、摘要对落盘字节计算（`log_digest_algorithm = sha256_raw_bytes_lf_v2`），不得对内存字符串算摘要；归档旧报告只能加 `--allow-legacy-digest`/`--allow-legacy-probe` 复核，不得追改或用新口径冒充；CI 的 static/gui 各自跑完分别过门禁。回归 `scripts/test_report_evidence.py`。
- 2026-10-28 测试平台报告 v2：每个用例经 `tools/test_assert_probe.py` 记录已执行 `assert` 数（helper 必须用 `assert` 表达；退出 0 但无 `G4USIM_ASSERTS=` marker 判 fail）；`report.json` v2 带 `tests_content_fingerprint`（scripts/tools/gui smoke/config/scenarios/schema/macros/test，哈希前归一 CRLF）与逐用例 `log_sha256`；`scripts/check_report_evidence.py` 是 CI 证据门禁，`--fail-on-skip` 不得让 skip 冒充绿色；探针 `settrace_assert_lines_v2` 同时跟踪脚本启动的线程（worker pool 内的 `assert` 也计数，但脚本运行前已存在的线程不计）；用 `raise AssertionError` 或收集式 `return 1` 表达的判定不计入断言数，必须改成 `assert`；被原始字节哈希的输入固定 `text eol=lf`。阶段 1b 起 79 个用例全部报告非零断言（`cases_with_zero_assertions=[]`），验收阈值是断言总数不下降且该列表为空；跨线程逐项判定可以先收集再在主线程 `assert not problems` 聚合，但聚合点以外的逐项判定不计入断言数；E2-S1 的六个 editor→writer 边界是 static 用例 `writer_boundary`，基准脚本的断言必须放在 `write_report()` 之后，不得在逐基准循环内提前退出。
- 2026-10-27 B1 位移损伤粒子名：`[scoring.displacement]` 键按 `G4ParticleTable` 大小写不敏感解析为规范名，在 `BeginRun`（首个事件前）校验（配置期粒子表为空）；未知名字报主 INI 文件、行号与候选后失败，不得静默让 DDD 恒为 0；回归 `scripts/test_displacement_damage.py`。
- 2026-10-27 B2/B3/B4：主 INI 重复 section/键只告警 `[ConfigWarning] duplicate declaration` 并写摘要 `config_duplicate_count`，后值生效、不得改成拒绝；敏感探测器按配置名创建（禁硬编码 `AIHLParticleSD`）；`enableSD`/`setSDName`/`setSeed` 仅 `PreInit`，初始化后必须失败而非改缓存；回归 `test_config_duplicate_declarations.py`、`test_command_state_gating.py`。
- 2026-10-27 F6：`Actions/RunProgress` 输出 `[G4USimProgress] ` + `g4usim_progress_v1` JSON，约 0.5 s 限频，终值取 `G4Run::GetNumberOfEvent()`；零事件不补造消息，进度不替代 `run_result` 判定；契约 `docs/实时运行进度.md`、回归 `test_live_progress.py`。
- 2026-10-26 E2 配置 schema：353 个字段条目；改描述/默认/别名/范围必须跑 `scripts/generate_config_schema.py`，C++ 表、Python 数据、矩阵第 5 节与覆盖清单禁手改；`field`/`biasing` 在 excluded，不能说成全仓库统一；回归 `test_config_schema.py`、`test_config_schema_context.py`。
- 2026-10-23 H1 粒子径迹：`[output] trajectories = N` 在 `SteppingAction` 开头记录（步前体积，被杀的步也记录），每 worker 每轮写 `trajectories_tN[_rR].json`，master 不写；回归 `test_trajectories.py`。
- 2026-10-22 D 安装包：`Core/Geant4DataLocator` 仅在无 `GEANT4_DATA_DIR`/G4…DATA 变量时读可执行文件旁 `geant4-data.txt`；`packaging/build_package.py` 只写 git 忽略的 `out/`；打包验证须清空 PATH 与 Geant4 变量；数据集清单按 Geant4 11.3 写死。
- 2026-10-22 B4 探测器响应：脉冲幅度就是 `event_edep` 沉积能（探测器为唯一敏感体），分辨率只在 `analyze_detector.py` 由用户参数施加；γ 源只在包外壳圆锥内抽样，绝对效率乘 `cone_fraction_of_4pi`；参考值全为解析式，不得声称实测效率。
- 2026-10-22 B3 半导体器件：NIEL 表由 `convert_srniel.py` 从 SR-NIEL 生成；Φ_eq 用 ASTM E722 的 95 MeV·mb；TID 病例保持 δ 电子平衡且仅电磁物理；DDD 病例只检验注量与折积，不得称其验证了 NIEL 数据。
- 2026-10-22 B2 屏蔽/涂层：DDD 按 Σ w·l·NIEL(E)/V，不得改用 `GetNonIonizingEnergyDeposit`；NIEL 表必须有出处；屏蔽剂量率仅法向入射；NIST 原表只能由 `make_reference.py` 再生成。
- 2026-10-22 B1 物理基准：`reference.csv` 每行带出处，判据 |模拟−参考| ≤ 容差×参考 + 3σ；CSDA 用仅电磁物理；`G4_WATER` I = 78 eV 造成的约 +0.6 % 偏差不得靠改材料或放宽容差贴合。
- 2026-10-22 A7 电磁场：`FieldSetup` 每线程在 `ConstructSDandField` 开头建场；`G4FieldManager` 由 `G4FieldManagerStore` 删除，不能再用 `G4AutoDelete`；回归 `test_fields_a7.py`。
- 2026-10-22 A6 物理：`[physics.region.<名称>]` 区分大小写（取自 `originalSection`）；`max_track_length` 是自产生总长度、`min_kinetic_energy` 在步开始时判断，均为 Geant4 语义，测试与文档不得改写；`dumpProcesses` 只读；回归 `test_physics_a6.py`。
- 2026-10-22 A5 几何：新实体/`replica|parameterised`/STL/`exportMesh`/GDML 均实验性；新实体只在 master 预计算 `GetCubicVolume()`（避免 worker 惰性缓存竞态），旧实体与布尔实体不得这样做；`assembly`、非 normal placement、A5 实体作布尔工具仍拒绝；Geant4 无 GDML 时配置阶段拒绝；回归 `test_geometry_a5.py`。
- 2026-10-22 A4 高级 GPS 源：`SourceSpec` 多源、能量/位置/角分布高级类型、离子、相空间均实验性；`PrepareForRun()` 应用并记 `source_prepare_run` 失败；多源时单字段 `/AIHL/source/*` 命令必须拒绝；GUI 仍不得生成这些字段；回归 `test_gps_sources.py`。
- 2026-10-22 A3 统计不确定度：逐事件 `sum`/`sum_sq`，worker 在 `Write()` 提交、master 写 `scorer_statistics[_rR].csv`；LET 比值误差用 delta 方法；不得把统计误差说成物理系统误差或已验偏置运行；回归 `test_statistical_uncertainty.py`。
- 2026-10-21 M5 输出后处理原型：registry API v1 只显式加载可信 Python 模块，`dose_json` 独占发布 JSON；无沙箱、无 C++ scorer 动态注册、非任意输出转换；回归 `test_output_extensions.py`。
- 2026-10-21 M1 矩形平面源：仅 XY 平面 `rectangle` + `center` + 正 `halfx/halfy` 传到 GPS；GUI 只写受支持子集并拒绝 square/annulus；首条 sensitive hit 不是 GPS 顶点，未验证采样均匀性。
- 2026-10-21 跨阶段切片策略：不要求 M0 全部完成才做其他阶段原型；实验性 Dose 必须提示无通量/时间归一化与无独立物理基准。
- 2026-10-21 M0 源字段冲突：`isotropic=true` 与显式 `direction` 冲突、point/plane 专有字段混写、省略 `position_type` 时 `center/radius` 不得静默丢弃，全部在配置阶段失败；GUI isotropic writer 不得写 `direction`。
- 2026-10-21 M0 源空值：显式空白 `[source]/preset|particle|energy` 在配置阶段报错；字段缺失才允许沿用默认值或 preset。
- 2026-10-19 M0 数值有限性：`UnitParser` 与 Source setter、GUI 均拒绝 `NaN`/`Inf`/换算后溢出的数值。
- 2026-10-19 M0 固定方向：固定方向必须用 GPS `planar` + 归一化向量（`beam1d` 会恒沿 -Z）；`preset=isotropic_*` 后显式 `isotropic=false` 且无 `direction` 必须前置拒绝。
- 2026-10-19 M0 平面圆心：`SetPlaneBeamAt` 必须传三轴中心，旧 `SetPlaneBeam(radius,z,direction)` 保留 x=y=0 兼容。
- M0 源位置 INI 失败边界：`position_type` 只实现 `point`/`plane`，未知或空值、`point` 缺 `position` 必须在初始化前失败。
- M0 原生 GPS 交错回归：GPS 已创建后单字段 setter 只同步对应字段，首次惰性创建才整体回放；`effective_source_energy_MeV` 是 Manager 缓存，不是原生 GPS 当前采样能量。
- M0 计分生命周期：`ActionInitialization::Build()` 克隆 master `ScoringManager`；`ScoringMessenger` 的修改命令只允许 `PreInit`；`effective_scoring_event_edep_enabled` 才是最终 Manager 值。
- M0 输出后缀：worker 在 `Build()` 强制 `_tN`，`setThreadSuffix false` 必须拒绝，不能造成并发 CSV 覆盖。
- M0 线程数：`/AIHL/app/setNumThreads` 仅 `PreInit` 有效；初始化后必须明确失败，改线程数须新进程。
- M0 输出目录：`/AIHL/output/setDir`、`setThreadSuffix`、`/AIHL/app/setOutputDir` 仅 `PreInit`；失败不得改 context 与来源；`OutputManager::IsInitialized()` 不能替代 Geant4 状态门禁。

本文件是仓库级约束，适用于根目录及其子目录。更具体的目录约束可以由更深层的 AGENTS.md 补充；gui/AGENTS.md 适用于 GUI 目录。

## 1. 事实来源和支持判定

- 后端实际实现是功能支持情况的唯一依据。优先检查 src/、include/、main.cc、配置解析器和可运行测试；不要根据旧文档、类名、配置字段名、GUI 控件或空接口推断功能已经支持。
- “能解析”不等于“能运行”，“能运行”不等于“物理结果已经验证”。文档必须分别说明解析、校验、运行时行为、输出和验证范围。
- 任何 stub、空函数、只注册不计算的类、占位模板、预览模型或兼容字段，都不能被描述为完整支持。
- GUI 不得展示后端尚未实现的功能；如果为了预览、规划或兼容性必须展示，必须在控件、校验消息、生成包报告和人类文档中明确标记为“预览”“实验”或“不可用”，并阻止生成可运行配置，除非后端已经提供对应实现。
- 支持等级以 docs/功能支持矩阵.md 为基线。修改后端后先更新事实，再更新 GUI 和文档；不要为了让矩阵变绿而放宽判定标准。

## 2. 新功能的完整链路

新增或修改功能时，必须同时检查并在任务说明中列出以下环节：

1. 配置解析：INI、macro、CLI 或其他入口是否真正读取字段，路径和单位如何解析。
2. 配置校验：缺失值、非法值、依赖关系、冲突和未知字段如何报错或警告。
3. 运行时实现：Geant4 对象、生命周期、线程模型、依赖和错误路径是否真正执行。
4. GUI：编辑器是否只生成后端支持的配置，预览和不可用状态是否清楚。
5. 测试：至少有与变更层级相符的解析测试、GUI smoke、后端 smoke 或物理基准；不能只测试字符串生成。
6. 文档：同步人类文档、Agent 文档、支持矩阵和必要的示例配置或 macro。

不得用空实现、占位实现或只增加开关/枚举的方式宣称功能已支持。若暂时只能完成部分链路，应保留“部分支持”或“未支持”状态，并说明缺口。

## 3. 后端维护规则

- SimulationManager、各模块 Manager、配置读取器和 Messenger 的行为必须保持一致；新增配置字段不能只加到 GUI writer 或文档。
- 配置优先级必须以代码实际行为为准。M0-1/M0-1b 已对当前启动字段统一为“默认值 < 主配置文件 < macro 运行时命令 < 显式 CLI 参数”：`SimulationCommandLineOverrides` 在 `Configure()` 后重应用显式 CLI，并由 `SimulationManager`、`OutputManager`、`GeometryManager` 阻止低优先级入口改写 `output`、`threads`、`seed`、`check_overlaps` 等字段。它是向完整 `EffectiveConfig` 迁移的过渡层，不代表已经提供来源追踪。
- M0 几何生命周期守卫：`/AIHL/geometry/` 的几何/配置修改命令（含 `markModified`）以及 `/AIHL/app/setCheckOverlaps` 只允许在 Geant4 `PreInit` 状态执行；`print`、`printTree`、`listUserVolumes` 为只读命令，不受此限制。初始化后禁止只改 Manager 缓存却继续以旧 Geant4 world 执行。batch 的 `ApplyCommand` 非零返回须保存失败位置、失败摘要和非零退出；`csh` 的失败返回须停止后续输入。切换几何请在初始化前配置或启动新进程，不能把 `/run/reinitializeGeometry`（尤其含 biasing operator）视为已完成安全验收。实际后端回归见 `scripts/test_run_summary.py`、`scripts/test_interactive_commands.py`。
- M0-2 的 `run_summary.txt` 只在最终生命周期阶段写入（dry-run、正常结束、交互会话结束或失败收尾），并区分计划配置与实际运行事实：状态、每次 run、计划/完成事件数、实际线程数、配置 seed、引擎初始 seed（无法可靠取得时为 `unknown`）、macro seed 修改、最终输出目录、生成文件和失败命令位置。seed 修改只可由当前代码明确识别且成功执行的命令确认；失败摘要必须区分执行失败和 preflight 失败。preflight 没有 `ApplyCommand()` 返回码，必须用 `macro_failure_code_available=false` 表达 `macro_failure_code=0` 的语义。无法取得的运行事实必须写为 `unknown` 或 `not_executed`。
- M0-3C4 的 GUI 结果判定不能仅凭进程退出码：`success` 必须有正常退出、本次新摘要、后端和 macro 完成、至少一个 run 与正数计划事件；每个 run 的计划/完成事件数须一致，逐 run 合计也须与摘要总数一致，不能仅用相等总数掩盖单轮未完成。dry-run、交互无 run、普通无 run、终止、kill、失败和未证实分别保留状态；旧摘要和无摘要不得冒充成功。当前仅是未提交工作区候选，见 `gui/g4usim_gui/core/run_result.py` 和专项 smoke。
- M0-3D 默认复杂示例的无界面验收入口是 `test/macros/run_hierarchical_batch.mac`；`test/macros/vis.mac` 仅用于显式 UI 可视化。复杂源文件的冷却管和颜色修复须由真实后端 overlap、运行摘要和旧坐标反例回归证明，不得因 3D Preview 正常或进程退出码 0 宣称场景可信。`test/main_hierarchical.ini` 已改为逐 process 规则和真实体积；它与批处理 macro 完成 3/3、与完整 macro 完成 100/100 事件且两个目标匹配，但实际偏置效果仍为 `unknown`，不能当作 M2 验证。
- M0-3E 的工作区候选要求以物理初始化后的实际 wrapped process 校验每个启用的 bias 目标；普通 process 名存在但未包裹不算匹配。macro 配置的物理/biasing 修改须在初始化前重绑物理列表，初始化后修改应拒绝；失败在事件前报告粒子、目标、候选和替代建议。摘要分别记录规则、挂接、匹配，未观察实际偏置时必须写 `unknown`，不得把目标匹配当成 M2 物理验证。GUI generated 模式无规则编辑器，启用空 hook 时不得生成运行包。
- biasing operator 已挂接后的 `/run/reinitializeGeometry` 在本机真实后端曾访问违例；当前 batch macro 必须提前拒绝并建议新进程重建。`--ui` 与已启用的 biasing 配置或会修改 biasing 的 macro 不能组合，交互会话内的 biasing 修改命令必须明确拒绝，避免绕过 batch 保护。`/run/physicsModified` 后 `/run/initialize` 的专项通过不等于完整几何重建安全；实际交互 UI 操作尚未自动化验收。
- macro 执行前必须运行静态递归 preflight：检查 `/control/execute` 引入的文件，顶层相对路径按进程工作目录解析，嵌套相对路径只能按发出命令的 macro 文件目录解析。预检生成的规范化命令序列必须直接用于实际执行；拒绝已知 CLI 冲突的项目命令、`/run/numberOfThreads`、`/random/...`，以及无法可靠分析的 `/control/alias`、`/control/loop`、`/control/foreach`。不得声称能够保护任意动态 Geant4 命令；未覆盖命令必须记录为风险或明确不支持。
- `/AIHL/app/setMainConfig` 只能用于 `Configure()` 以前的入口，批处理 macro 已在配置后，必须在 preflight 阶段拒绝切换主 INI；直接调用 `SimulationManager::SetMainConfig()` 在已配置/初始化状态也必须拒绝，避免破坏来源快照与 Manager 一致性。更换主配置须新进程指定 `--config`。
- 配置字段、Geant4 命令、输出列名和项目 JSON 字段属于接口。删除、改名或改变默认值时，必须给出迁移策略和兼容性说明。
- M0-3A 对尚未支持的能力采用统一 fail-fast：`placement=replica|parameterised|assembly`、GDML、材料 `temperature`/`pressure`、`[physics.region.*]`、LET 开启均必须在 Geant4 对象创建或运行前拒绝；替代方案必须出现在错误消息中。Dose 和 Fluence 例外仅为已实现的实验性敏感体计分（需默认 scorer），Fluence 限无 daughter 的 solid 与 track-length 定义，不能推断其他剂量或注量能力已支持。
- M0-3B1 对主配置文件建立字段消费追踪：`IniReader` 保留文件、section、key、原始值和行号；成功 getter 标记字段已消费，`ConfigManager` 在各 Manager 完成配置后稳定输出 `[ConfigWarning]` 未消费字段和未知 section，并写入 `run_summary.txt`。该机制只警告、不改变运行结果；材料文件和几何文件仍由各自解析器独立处理。
- M0-3B2A 对材料独立配置文件使用闭合 schema：隐式 `global`、未知 section、空的动态 section 后缀和未知 key 必须在 Geant4 对象创建前失败，并报告 file、line、section、key、value；`temperature`/`pressure` 继续使用专用的 M0-3A 错误和替代建议。旧 GUI run package 在 `[material.<name>]` 中生成的 `type = material` 是已弃用兼容字段，只可取该值且不得影响 `MaterialDefinition`；新 writer 不再生成。该 schema 不适用于几何独立配置文件，也不实现新的材料能力。
- 输出必须说明文件生成条件、线程后缀、单位/量纲、合并方式和未生成文件的正常原因。没有物理定义或数据契约的 scorer 不得输出看似有效的结果。
- M0-4 工作区 CSV 契约候选采用 `output_csv_schema_version=3`：hits/event 保留 `runID`，首轮仍使用 `_tN`，后续 run 使用 `_tN_rR`；当前已验证的能量/长度列在表头标记 `_MeV`/`_mm`，hits 不再输出未计算的 `LETcalc`/`LETstep` 零值占位。Edep 直方图和分类汇总按 run 独立，摘要根据实际表头区分 v2/v3 或 `unknown`；`run_summary_schema_version=1` 只描述摘要结构，单位标记和目标匹配都不代表物理结果已验证。旧 CSV v1 无可靠的多 run 恢复路径，v2→v3 的字段迁移见 `docs/输出数据契约.md`。
- M0-4 工作区输出文件登记已改为 master/worker 共享的互斥保护登记表，仅在 CSV 显式关闭成功或直方图写出成功后登记；`GetGeneratedFiles()` 不再扫描目录或依赖 mtime，因此外部程序同期创建的文件不会因时间戳被误列。真实双线程运行期间外部文件注入回归见 `scripts/test_run_summary.py`。登记只证明写出组件报告完成且文件仍存在，不证明设备持久化、未被外部修改或物理正确。
- M0-4 工作区候选还在共享登记表中锁存首个 worker 输出失败（`run_id/thread_id/stage/message`）；event/hits 写出错误请求停止 run，worker 收尾阶段捕获并记录异常，batch `beamOn` 返回后以及交互会话结束时检查失败，最终摘要写 `output_failure_*`、`status=failed` 和非零退出码。`G4USIM_TEST_OUTPUT_FAULT=event_row_t0|summary_close_t0` 仅供测试，在真实 Geant4 双线程 worker 路径中验证了事件行和汇总关闭故障；不要在正常生产环境设置此变量。未验证磁盘满/断连、异常进程终止及交互 UI 的全部失败路径，M0-4 仍为部分实现。
- M0-4 主线程最终化补充：`FinalizeRunSummary()` 必须分别尝试最终 `Flush`/`Close`，将首个异常锁存在共享输出失败登记表，尽力写出 `failed` 摘要并返回失败结果；正常结束路径收到失败结果时必须返回非零退出码，不能把已写出的失败摘要误报为摘要写入失败。测试专用 `final_flush_master` / `final_close_master` 在真实最终化分支完成操作后模拟异常，验证失败状态和摘要写出；这不是磁盘错误实测。摘要本身无法写入时仍使用专用 summary failure 错误路径。
- M0-4 运行启动阶段补充：`BeginOfRunAction()` 的 `SetRunId`、run 开始摘要、输出初始化及 `ScoringManager::BeginRun` 共用分阶段异常捕获，锁存首因并请求中止，不允许 worker 启动异常穿出回调。`SetRunId` 切换旧文件失败时使用尝试启动的 run ID 登记错误，避免误归属上一轮；`OutputManager::Flush()` 逐 writer 尝试并重新抛出首个异常。测试专用 `begin_set_run_id_t0` / `begin_scoring_t0` 仅模拟第二轮启动故障，不代表物理介质故障。必须检查首轮 run 与输出保留、失败摘要、非零退出；MT 下 master/worker 的线程编号可能重叠，不能仅以编号判定故障源。
- M0-4 交互式目录冲突补充：`RunAction::BeginOfRunAction()` 在 master/sequential 运行启动时，按实际线程数对所有已知 worker CSV 目标目录先执行 `ValidateOutputTargetDirectories`，失败记入 `run_begin_validate_targets` 并中止 run；batch 仍保留宏命令前的早期检查和精确来源行号。此检查预防已存在目录占用目标文件名，不覆盖后续并发创建、权限变化、实际磁盘或设备故障。真实 `--ui --ui-session csh` 单/双线程首轮与第二轮回归见 `scripts/test_interactive_commands.py`，失败时 `run_count` 可能包含已开始但零完成事件的 run。
- batch macro 中材料 Messenger 的命令执行异常不能只降级成 `JustWarning` 并假装成功；须同时锁存命令失败计数与错误，`ApplyCommand()` 即使返回 0 也应在本条 macro 后拒绝继续、写入来源行号和失败摘要并非零退出。交互 UI 材料命令仍是聚合级失败判定（`MaterialManager` 失败计数汇总为 `interactive_command_failure_kind=material`，不是逐条）；`PreInit` 之外的交互材料修改已由 `AvailableForStates(G4State_PreInit)` 关闭，初始化后调用会被 Geant4 拒绝并以 `geant4_illegal_application_state` 失败（见 2026-10-28 命令失败传播条目）。
- batch macro 的 `/AIHL/output/*` 命令也必须检查 `OutputManager` 记录的 Messenger 命令失败计数；即使 `ApplyCommand()` 返回 0，内部异常仍须中止后续命令、保留失败文件/行号、输出 `macro_failure_code_available=false` 并返回非零。`SimulationManager::SetOutputDir()` 应先让 `OutputManager` 接受目录，再更新 context 和 EffectiveConfig 来源；失败不得冒充成功来源。测试专用 `G4USIM_TEST_OUTPUT_FAULT=messenger_set_dir|manager_set_dir` 分别注入命令处理器和 Manager setter 失败，正常运行不得设置。交互 UI 尚未完成逐命令相同保证。
- 交互会话可用 `--ui --ui-session csh` 选择可脚本输入的 Geant4 命令行 UI。`AuditedCshSession` 复用终端命令路径并在覆写的 `ExecuteCommand()` 中直接取得 `G4UImanager::ApplyCommand()` 数值结果，保留原有诊断文本；本机 Geant4 11.3.2 的 `GetLastReturnCode()` 对错误命令仍返回 0，不能作为证据。未知命令、错误类型、越界和非法状态维持原分类，其他非零数值状态使用 `geant4_command_status`，记录命令与状态码；与材料、输出和物理 Messenger 错误计数合并，失败在会话结束时非零退出、写 `status=failed` 和单行 `interactive_command_failure_kind/message`。真实测试增加 `/gps/pos/type InvalidCandidate` 状态码 500 和常见拒绝路径。受控 `G4UIcsh` shell 在已识别的直接命令失败或 Messenger/输出错误后停止读取下一条命令；仅覆盖脚本化 `csh`，内部 Messenger 返回 0 的路径依靠独立错误计数，不能保证所有嵌套/动态命令、Qt UI、未明确报告的内核失败及完整生命周期均已验证。
- 交互会话物理命令补充：Geant4 physics list 已注册后，`/AIHL/physics/*` 中会修改 PhysicsManager 的命令必须在 `PhysicsMessenger` 拒绝并累计交互错误，不得产生仅修改 Manager、没有重绑内核的假状态；`print`、`listAvailableReferences`、`listAvailableEMReferences` 查询可用。会话收尾记录 `interactive_command_failure_kind=physics`（有其他类别时为 `multiple`）、失败摘要与非零退出；修改物理配置应在新进程的初始化前 batch macro 中完成。该守卫不保证其他原生 Geant4 UI 命令已受审计；真实 `csh` 专项覆盖改前、改后及查询命令。
- batch macro 修改物理配置后若直接进入 `--ui` 而尚未执行 `/run/initialize`，必须在交互 SessionStart 前消费 `physicsListDirty`，重新注册 `sim.CreatePhysicsList()` 并重新准备 Source；否则用户在 csh 内的 `/run/initialize` 会使用旧列表。batch 的 `/AIHL/physics/listAvailableReferences` 和 `listAvailableEMReferences` 是只读命令，允许在内核初始化后查询，不应把它们误分类为物理突变。真实 `csh` 宏转交专项验证了重绑日志、两个事件及只读命令，仍不等同辐射物理结果基准。
- Geant4 对象创建、敏感体、region、biasing、线程本地输出和 reinitialize 生命周期必须有可重复的运行验证。只在内存中保存配置不能算运行时生效。

## 4. GUI、国际化和人类文档

- GUI 只是后端能力的编辑和运行入口，不是功能定义者。后端未支持的能力不得被 GUI 默认生成或静默降级。
- 面向人类的说明文档只使用中文。代码标识符、Geant4 命令、文件名、配置 section/key、输出列名和外部 API 名称保持原样，不翻译成另一个接口。
- 每项开发完成后同步人类文档和 Agent 文档；至少检查 docs/功能支持矩阵.md、docs/开发路线图.md、相关模块说明和相关目录的 AGENTS.md 是否仍然准确。
- GUI 的 PySide6、国际化、主题、配置编辑器和生成包约束见 gui/AGENTS.md，不得在根目录规则之外另行发明一套支持口径。
- 状态入口唯一：当前快照、阶段进度、验收证据与已知缺口以仓库根 `STATUS.md` 为入口；阶段状态只登记在 `docs/ROADMAP.md`，长期目标在 `docs/开发路线图.md`。不得再新建“交接/检查点/执行规划”类状态文档；带日期的历史快照放 `docs/archive/` 并登记到 `docs/archive/README.md`。
- 本文件只保留规则与条目索引：新增实施契约全文追加到 `docs/agent-history.md` 末尾，同时在 §0 索引加一行摘要；不得再在 AGENTS.md 内堆长篇日期条目。

## 5. 工作区和改动范围

- 不修改无关代码，不覆盖工作区已有改动。开始工作前检查 git status；对未跟踪文件、暂存内容和用户已改文件保持原样。
- 优先做小范围、可审查的修改。不要借整理文档之机重排代码、清理旧输出、修改 .gitignore 或删除示例。
- 不使用破坏性 Git 操作覆盖用户内容，例如未经明确要求不得执行 git reset --hard 或 git checkout --。

## 6. 测试和交付

- 每个任务必须运行相应测试，并在最终报告中区分“已验证”和“未验证”。文档任务至少运行链接/路径检查和受影响的 GUI 或配置 smoke；涉及后端行为时还要运行可用的构建、--help、dry-run 或后端 smoke。
- 配置优先级回归测试入口为 `python scripts/test_config_precedence.py`；M0-2 摘要回归测试入口为 `python scripts/test_run_summary.py`。涉及 M0-1/M0-1b 的改动至少覆盖配置-only、配置 macro、配置 dry-run/interactive、CLI-only、配置/CLI 冲突、macro preflight、真实 `beamOn`、无效参数、重复参数和缺失路径；涉及摘要时还必须覆盖多次 `beamOn`、失败收尾、无 run、输出目录切换和摘要写入失败。
- 测试失败时先区分代码失败、环境缺失和未覆盖场景，不得把“命令成功退出”当作物理正确性证明。
- M0-5 工作区统一测试入口为 `scripts/run_m0_tests.py`，按 static/GUI/backend/integration 分层，报告 pass/fail/skip 和日志；后端用例必须核对 `--capabilities.source_fingerprint` 与当前 C++ 工作区。CTest skipped 不等于完整通过，不能只看总退出码；详情见 `docs/测试平台说明.md`。
- 若真实 Geant4 可执行文件、Qt/PySide6、3D 依赖或特定工具链不可用，必须明确记录未验证部分和复现命令。
- 统一测试入口的报告是 `version: 2` 证据：每用例经 `tools/test_assert_probe.py` 记录 `assertions_executed`，报告带 `tests_content_fingerprint` 与逐用例 `log_sha256`；`scripts/check_report_evidence.py` 必须对最新报告通过。验证 helper 写成 `assert`，`raise AssertionError` 不会被计数。CI 的 profile 步骤必须带 `--fail-on-skip`，缺失 Qt/uproot/后端的 skip 不得以退出码 2 变绿。
- 被指纹按原始字节哈希的输入（`src/`、`include/`、`main.cc`、`CMakeLists.txt`）与测试内容指纹覆盖的目录，任何改动都不得让 `git checkout`/`merge` 改变磁盘字节：`.gitattributes` 已对 `*.cc`/`*.hh`/`*.h`/`*.in`/`*.py`/`*.json`/`*.ini`/`*.mac`/`*.csv` 与 `CMakeLists.txt` 固定 `text eol=lf`；新增被哈希的文件类型必须同时加 eol 规则或先归一化。
- 完成前复核 git diff、 新增文件编码、文档中的支持等级和工作区状态，确保没有把用户已有改动混入本任务。

## 7. M0-3B2B1 几何安全闭环

- M0-3B2B1 只闭合会造成静默失效或晚失败的几何字段：production cut 只允许 `cut.gamma`、`cut.e-`、`cut.e+`、`cut.proton`，且所在普通 volume 必须有非空 `region`；shape 参数、`copyNo` 和 M0-3A placement 拒绝必须在首个 Geant4 geometry object 创建前完成。
- `simple_box` target 和 `array` element 只允许 `shape=box`；`layered_device`、`shielding` 继续固定为 box。hierarchical 普通 volume 和 boolean tool 使用严格的逐 shape 参数数量及 shape-specific 字段契约。
- `VolumeBuilder` 的 `created_geometry_object_count` 是 B2B1 前置失败测试的可观察事实，不能用日志先后顺序替代。
- B2B1 本身没有建立完整几何闭合 schema；普通未知字段、legacy metadata warning、`run_summary.txt` 诊断已由 B2B2 补齐，自动迁移及 `version=2` 留给 M0-3B3。

## 8. M0-3B2B2 几何来源诊断与兼容 warning

- 几何配置诊断使用 `GeometryConfigDiagnostic`，必须保留文件、行号、原始 section/key/value、code/category、message 和 suggestion；输出统一为 `[GeometryConfigWarning] file:line [section]/key = value: message; suggestion`。
- `unknown_section`、`unconsumed_key`、`legacy_metadata`、`ignored_boolean_key` 按文件、行号、section、key 稳定排序去重，并通过 `GeometryManager`、`SimulationManager` 和 `run_summary.txt` 统一输出；`config_warning_count` 仍只统计主 INI，几何 warning 使用独立 `geometry_config_warning_count`。
- canonical `metadata.<非空名称>` 仅作为保存属性，不参与 Geant4 运行；hierarchical/layered 的无前缀未知属性继续保留并建议迁移到 `metadata.<原key>`，不得自动改写。B3 工作区候选允许在几何文件 `[global]` 显式写 `version = 2`，此时现有四类来源诊断在创建几何对象前变为错误；无版本或 `version = 1` 保持兼容 warning。GUI 已可在受支持编辑子集里保留版本标记并写回，项目快照不得丢失它；其他 round-trip blocker 仍须阻止 editable 生成。自动迁移和完整无损 round-trip 仍未完成。
- B3 严格几何源中的重复 section/key 也须在首个几何对象前拒绝，避免 `IniReader` 的后值覆盖前值；GUI 对空未知 section、未列于 `[layers]/names` 的层以及重复声明设置 round-trip blocker。无版本或版本 1 的重复声明暂保留原兼容行为，升级到版本 2 前须人工消歧。

## 9. M0-3C0B 运行前清单（工作区）

- `--inspect-run` 必须复用真实 `SimulationManager::Configure()` 和 `PreflightMacro`，不初始化/执行 Geant4 run，不写摘要或创建输出目录；JSON `G4UniversalSimRunPlan` v1 使用 `configuration_phase=before_macro` 明确区分配置计划与运行事实。
- 初始配置清单记录当前启动字段、材料/几何输入、默认/主配置/CLI 来源以及主 INI 原文和行号。它尚非全模块 EffectiveConfig，macro 后续修改必须作为待执行命令报告，不能声称已生效。
- GUI 外部 Run 先异步查询同一组实际启动参数，成功且输入未变化才启动；config-only、macro-only、中文路径、CLI 冲突和失败阻断由 `scripts/test_macro_plan.py` 与 GUI `smoke_run_input_modes.py` 验证。实际运行成功由 C4 结合摘要判断。
- 回归脚本的默认输出和随机引擎文件必须留在临时工作区，不能改写仓库示例输出。当前 M0-1/M0-2 脚本复制所需配置/macro fixture 后在临时目录运行。

## 10. M0 有效启动字段来源快照（工作区候选）

- `scripts/test_run_summary.py` 的单线程双 run 源采样回归，通过真实 hits 的主粒子首步记录验证 `/AIHL/source/particle`、`/AIHL/source/energy` 在受控点源、单能配置中实际作用于 Geant4 事件；不得推广为原生 `/gps/*`、多线程或全模块 EffectiveConfig 的应用验证。
- `effective_config_source_coverage=startup_geometry_source_and_physics_reference` 代表六个启动字段 `output_dir`、`run_name`、`threads`、`seed`、`macro_file`、`check_overlaps`、三个几何字段 `geometry_template`、`geometry_config`、`geometry_default_world_material` 及 `source_particle`、`source_energy` 及 `physics_reference` 的来源记录；历史 `startup_geometry_and_source_particle`、`startup_geometry_and_source_particle_energy` 仍须兼容。不能宣称全模块 `EffectiveConfig` 或 Geant4 内核实际应用已验证。
- `effective_<field>_origin_kind/file/line/section/key` 的 `kind` 只能使用 `default`、`main_ini`、`cli`、`macro` 或 `runtime_unattributed`。主 INI 保留原始字段和行号；宏命令须在真实执行成功并通过 Messenger 错误检查后记载来源；CLI 锁定字段不受宏重新归属。无法确定的运行时修改必须明确标为 `runtime_unattributed`。
- `physics_reference` 在主 INI 中通常由 `[physics]/reference` 决定；reference 模式下非空 `[physics]/em` 改变最终 reference 后由 `em` 归属。成功 batch `/AIHL/physics/setReferenceList`、`setBaseReferenceList`、`clearReferenceList` 更新来源；`setEM` 仅在 PhysicsManager 当前处于 reference 模式时更新 reference 来源。`effective_physics_reference` 是 Manager 名称，不能据此推断 Geant4 内核或 biasing 已实际验证。
- 相关回归由 `scripts/test_run_summary.py` 覆盖，几何来源在成功执行已识别 batch macro 后登记；`/AIHL/geometry/clear` 只重新归属 `geometry_config`，不改变模板或默认世界材料。`effective_geometry_default_world_material` 为 Manager 当前值，`effective_config_geant4_applied=unknown` 仍保留。`startup_fields_only`、`startup_and_geometry_fields`、`startup_geometry_and_source_particle`、`startup_geometry_and_source_particle_energy` 是历史摘要枚举值，消费者须兼容。`source_particle` 主 INI 优先记录非空 `[source]/particle`，否则记录 `[source]/preset`；成功 batch macro 的 `/AIHL/source/preset`、`/AIHL/source/particle`、`/AIHL/source/reset` 更新来源，包含重置为空状态。`source_energy` 优先记录非空 `[source]/energy`，否则记录 `[source]/preset`；成功批处理 `/AIHL/source/energy`、`/AIHL/source/preset`、`/AIHL/source/reset` 更新来源。`effective_source_energy_MeV` 是 SourceManager 当前单能值，0 表示未设置或已重置。来源仅针对 SourceManager，原生 `/gps/*` 命令对 Geant4 的直接效果未覆盖；后续若扩展到 physics、materials、scoring，应逐模块校验实际消费与运行生命周期，不能直接把配置表中的初始值当作最终有效值。
