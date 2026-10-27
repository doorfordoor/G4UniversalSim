# G4UniversalSim Agent 历史条目（2026-10-19 → 2026-10-27）

本文件保存 AGENTS.md 原先逐日追加的实施契约全文：每条都写明当时的实现、反例、禁止做法与回归脚本。
它们是**历史记录**，但其中仍然有效的操作规则依旧有约束力；根目录 [AGENTS.md](../AGENTS.md) 的“条目索引”给出每条规则的一行摘要。
改动相关模块前请先读对应条目全文（含文件路径与错误文本），只读索引不足以动手。新增条目写在文件末尾，并在 AGENTS.md 索引中加一行。

### 2026-10-27 B1 位移损伤粒子名

2026-10-27 B1 位移损伤粒子名：`[scoring.displacement]` 的键是 Geant4 粒子名，而 `IniReader` 把所有键转小写，所以 `he3` 必须解析为规范名 `He3`（旧实现按小写键存表，He3/GenericIon 类名字永不匹配，DDD 静默为 0）。`G4ParticleTable` 在 physics list 构造前为空，配置阶段通常无法校验，因此 `ScoringManager::LoadFromConfig()` 保留原始键并记录文件/行号，`ScoringManager::ResolvePendingNielNames()` 在 `BeginRun()`（master 与各 worker 克隆各自解析，`CloneForThread` 复制 pending 状态与位置）解析为规范名；未匹配任何粒子时抛错（含主 INI 文件、行号、did-you-mean 候选），run 失败并非零退出，不得静默让 DDD 恒为 0；配置阶段若粒子表已非空则立即失败。`Clear()` 重置 pending 状态。名字校验发生在首个事件前而非配置阶段，文档与 schema 不得写成"配置期失败"。回归 `scripts/test_displacement_damage.py`（`he3` 表得到 `He3` 行且径迹长度吻合、拼错名字报行号与候选且无 DDD 行）。`schema/config_schema.json` 的 `scoring.displacement` 描述与规则已同步，生成物禁止手改。

### 2026-10-27 B2/B3/B4 配置重复声明与命令生命周期

2026-10-27 B2/B3/B4 配置重复声明与命令生命周期：`IniReader` 记录重复 section 头与同一 section 内重复键的首次声明行号（`IniDuplicateInfo`，section 重复时 `key` 为空），`ConfigManager::GetDuplicateWarnings()` 转成 `[ConfigWarning] duplicate declaration <file>:<line> [<section>]/<key> = <value>; earlier declaration at line <n> is overridden by this one; remove one of the declarations`（section 重复写 `repeated section header`），`SimulationManager::ReportConfigWarnings()` 打印并写摘要 `config_duplicate_count`。重复声明仍按最后值生效，这是兼容行为，不得改成拒绝；几何文件 `version = 2` 的严格拒绝与之独立，不能混写。敏感探测器由 `DetectorConstruction` 的 `SetSensitiveDetectorFactory` 工厂按配置的 `sensitiveDetectorName_` 创建（`SimulationManager::CreateSensitiveDetectorFactory()`），不得再硬编码 `AIHLParticleSD`——名字不一致会让改名后重复注册 SD。`/AIHL/detector/enableSD`、`/AIHL/detector/setSDName`、`/AIHL/app/setSeed` 只在 `G4State_PreInit` 可用（`AvailableForStates`）；初始化后执行必须让 batch 非零退出、写 `status=failed` 摘要并停止后续命令，不得只 warn 后改 Manager 缓存；`SimulationManager::SetSeed` 另有初始化后守卫，属 UI 不可达的防御性代码，未单独覆盖，文档不得声称它已被回归验证。回归 `scripts/test_config_duplicate_declarations.py`、`scripts/test_command_state_gating.py`；本项只闭合主 INI 与这三条命令，其他 Messenger 命令族的动态路径仍未审计。

### 2026-10-27 F6

2026-10-27 F6：`Actions/RunProgress` 输出 `[G4USimProgress] ` + `g4usim_progress_v1` JSON，master/sequential Begin/End、worker/sequential EndEvent 聚合，running 全局约 0.5 秒限频。中间计数含到达收尾的 aborted event；终值取 G4Run::GetNumberOfEvent() 与 RecordRun 同口径，不是有效物理历史数。begin 必须早于 source/biasing 准备失败，end/aborted 必须在本轮输出收尾后；final Flush/Close 仍可在 end 后失败。不得调用随机数或改变输出/生命周期来显示进度；零事件无回调不补造消息。GUI 进度不能替代 run_result 的最终判定。契约见 docs/实时运行进度.md，真实回归 scripts/test_live_progress.py。

### 2026-10-26 E2 配置 schema

2026-10-26 E2 配置 schema：`schema/config_schema.json` 现覆盖 run/general/output、source（含命名源/相空间）、physics、scoring（含 mesh/DDD）、主文件引用及六种几何模板/材料独立文件。`field`、`biasing` 明确列在 excluded，不能声称全仓库统一。改字段描述/默认/别名/范围时同步 schema，运行 `scripts/generate_config_schema.py`；C++ 表、Python 数据、矩阵第 5 节和 `schema/config_schema_coverage.json` 均不得手改。静态与动态 section 按原语法分派，材料/几何解析器使用生成键表，跨字段与运行时检查继续由专用后端执行。`independent` 标识可单独验证的启动字段；`structured` 不得被 GUI scalar API 当成普通字符串放行。保留 `source.z`、几何 `recognition=parser_only` 的历史行为和 metadata userProperties。`scripts/test_config_schema.py` 检查启动标量及完整上下文；`test_config_schema_context.py --baseline <旧后端> --probe-scalars` 对照接受/警告/配置摘要；GPS/A5/A6/计分及 E1 回归仍必需。定义与限制见 `docs/配置schema说明.md`。

### 2026-10-23 H1 粒子径迹

2026-10-23 H1 粒子径迹：`[output] trajectories = N` 由 `Scoring/TrajectoryRecorder`（ScoringManager 持有并随 `CloneForThread` 复制设置）在 `SteppingAction` 开头记录（在 kill 体与相空间 kill 之前，被杀的步也记录），每 worker 每轮写 `trajectories_tN[_rR].json`（`g4usim_trajectories_v1`，格式见 `docs/输出数据契约.md`），master 不写。点的体积是该步的步前体积，测试据此检查线段位于所标体积内；不要改成步后体积。写出失败记入 `trajectory_write` 并中止 run。键 `trajectories`、`trajectory_min_energy`、`trajectory_max_points` 已登记在 `ConfigManager` 已知键表。回归见 `scripts/test_trajectories.py`。

### 2026-10-22 Phase D 安装包

2026-10-22 Phase D 安装包：`Core/Geant4DataLocator` 仅在没有 `GEANT4_DATA_DIR` 与任何 G4…DATA 变量时把可执行文件旁 `geant4-data.txt` 的第一行非注释路径设为 `GEANT4_DATA_DIR`（用户环境始终优先），数据集清单按 Geant4 11.3 写死并以 `G4VERSION_NUMBER` 守卫，升级 Geant4 必须同步；`--check-geant4-data` 只报告、不运行模拟。`packaging/build_package.py` 只往 git 忽略的 `out/` 写产物，DLL 由 dumpbin 递归收集（含 Geant4 可视化依赖的 Qt 5），任何缺失都失败；打包验证必须在清空 PATH 与 Geant4 变量的环境中运行后端与冻结 GUI。许可文本在 `packaging/licenses/`，不得删改。不要把 Geant4 数据或项目自身许可写进包内，除非用户决定。回归见 `scripts/test_geant4_data_locator.py`、`packaging/test_installer.py`。

### 2026-10-22 Phase B4 探测器响应

2026-10-22 Phase B4 探测器响应：脉冲幅度只是 `event_edep` 的沉积能量（探测器须为唯一敏感体），分辨率（MCNP GEB）只在 `analyze_detector.py` 中施加且参数由用户给出，不得把默认演示值称为某探测器的分辨率。γ 源只在包住外壳的圆锥内抽样，绝对效率必须乘 `cone_fraction_of_4pi`。基准参考全部是解析式（`scenarios/detector_response/response_physics.py`；硅密度效应参数来自 Geant4 `G4DensityEffectData`，不得凭记忆改写）。康普顿边只在小的低 Z 探测器中作为基准；Landau 众数用半样本众数且需要大量事件（基准 20 万）。Geant4 option4 的薄硅 MPV 比 LVB 高约 +3%（300 µm）到 +5%（100 µm），文档须如实说明。回归见 `scripts/test_detector_response.py`。

### 2026-10-22 Phase B3 半导体器件

2026-10-22 Phase B3 半导体器件：`scenarios/semiconductor/niel/si_*.csv` 由 `convert_srniel.py` 从 SR-NIEL 计算器结果页生成（经用户同意提交公开计算器表单），只在最低能量为 0 时补 1 eV 零值行；改表须重新从来源生成并更新 README 中的设置。Φ_eq 使用 ASTM E722 的 95 MeV·mb（2.037e-3 MeV cm²/g），不得改用共振中子表在 1 MeV 的插值。`device_dose` 的 TID 病例必须保持 δ 电子平衡（前后硅层厚于最快 δ 电子射程）且用仅电磁物理；DDD 病例只检验注量与折积，文档不得称其验证了 NIEL 数据。`make_device.py` 复用 `shielding_coating/make_scenario.py` 的辅助函数。回归见 `scripts/test_semiconductor_device.py`。

### 2026-10-22 Phase B2 屏蔽/涂层

2026-10-22 Phase B2 屏蔽/涂层：`DisplacementScorer`（`Scoring/NielTable` 读 `energy_MeV,niel_MeV_cm2_g`）在 daughter-free 敏感 touchable 上按 Σ w·l·NIEL(E_平均)/V 计 DDD，零沉积步经 `SensitiveDetector` 的零沉积分支进入，`HitRecord::meanKineticEnergy` 由 `PopulateDoseContext` 填写；不得改用 Geant4 `GetNonIonizingEnergyDeposit`（只是局部反冲能）。NIEL 表只能来自有出处的数据（目前仅 `scenarios/semiconductor/niel` 的 SR-NIEL 硅表），不得编造或凭记忆写入；`[scoring.displacement]` 键为 Geant4 粒子名（INI 键被转小写，须解析为规范名，见 2026-10-27 B1 条目）。`scenarios/shielding_coating` 的剂量率只适用于法向入射。`scenarios/benchmarks/shielding_range/nist/` 是用户提供的 NIST 原表，`reference.csv` 只能由 `make_reference.py` 重新生成。回归见 `scripts/test_displacement_damage.py`、`scripts/test_shielding_coating.py`。

### 2026-10-22 Phase B1 物理基准

2026-10-22 Phase B1 物理基准：`scenarios/benchmarks/<包>/reference.csv` 每行带出处，`scripts/run_benchmarks.py` 判据为 |模拟−参考| ≤ 系统容差×参考 + 3σ，统一测试平台 `benchmarks` 用例运行 `--quick`。CSDA 用仅电磁物理（CSDA 不含核反应）；质子射程约 +0.6 % 的偏差来自 `G4_WATER` I = 78 eV，不得为了贴合参考值放宽或改动材料参数而不说明。新增基准必须写明粒子、能量、材料、物理列表与容差来源。

### 2026-10-22 A7 电磁场

2026-10-22 A7 电磁场：`Field/FieldConfig` 解析 `[field]`/`[field.<名称>]`（单位表与场图格式见文件头注释），`Field/FieldSetup` 在 `DetectorConstruction::ConstructSDandField` 开头（敏感体关闭时也执行）每线程构建场对象；纯磁场 `G4Mag_UsualEqRhs`，含电场 `G4EqMagElectricField`，`G4DormandPrince745`。`G4FieldManager` 由 `G4FieldManagerStore` 删除，不能再用 `G4AutoDelete` 登记（曾导致退出时崩溃）。局部场 `SetFieldManager(manager, false)`。INI 几何的 `volumes` 在配置阶段经 `GeometryManager::HasConfiguredVolume` 校验。回归见 `scripts/test_fields_a7.py`。

### 2026-10-22 A6 物理

2026-10-22 A6 物理：`[physics.region.<名称>]`（区分大小写，名称取自 `GetSectionInfo().originalSection`）由 `GeometryManager::ApplyRegionPhysics()` 在每次建世界后施加，INI 几何在配置阶段由 `ValidateRegionPhysicsNames()` 先校验；限制经 `G4StepLimiterPhysics`（`PhysicsFactory::ApplyRegionAndDecaySettings`，reference 与手动列表都调用）。`max_track_length` 是自产生起的总长度，`min_kinetic_energy` 在步开始时判断，均为 Geant4 语义，测试与文档不得改写。`[physics.radioactive_decay]` 不重复注册已有衰变物理，`time_threshold` 写入 `G4HadronicParameters`。`/AIHL/physics/dumpProcesses` 为只读（main.cc 与 PhysicsMessenger 的只读列表都已登记），Idle 状态可用。回归见 `scripts/test_physics_a6.py`。

### 2026-10-22 A5 几何

2026-10-22 A5 几何：hierarchical 普通体积新增 `ellipsoid`、`eltube`、`torus`、`para`、`hype`、`polycone`、`polyhedra`、`tessellated`（STL，`Geometry/StlReader` 要求封闭一致定向流形）与 `placement=replica|parameterised`（Geant4 要求母体只含该子体积；切片尺寸、`count×width`、phi 中心/offset 在创建首个几何对象前校验，`VolumeBuilder` 再检查一次）。这些新实体在 master 构建时预先计算 `GetCubicVolume()`，因 Geant4 惰性缓存在 worker 并发首次调用时可读到部分和；勿对旧实体或布尔实体这样做（其估算消耗随机数、改变既有结果）。`DoseContext` 以步前材料调用 `GetMass` 以支持逐副本材料。`/AIHL/geometry/exportMesh` 只读写出 `g4usim_geometry_mesh_v1`，GUI“显示后端几何”经 QProcess 调用。`assembly`、macro `add*` 的非 normal placement、A5 实体作布尔工具仍拒绝；GDML 由 `Geometry/GdmlIO`（`G4USIM_HAVE_GDML`，仅在 `Geant4_gdml_FOUND` 时编译）实现：`template = gdml` 导入、`/AIHL/geometry/exportGDML` 导出（拒绝覆盖）；GDML 不保存 world/replica/parameterised 物理体名，读回后 touchable 路径改名，测试用 `gdml_path()` 映射。Geant4 无 GDML 时必须继续在配置阶段拒绝。本机环境：唯一 Geant4 为 Windows `D:/ProgramFiles/Geant4`（11.3.2 + GDML，XercesC 头文件/库已并入该前缀，用户变量 `XercesC_ROOT` 指向它），WSL 中的 11.2.1 已停用。回归见 `scripts/test_geometry_a5.py`、`gui/smoke_tests/smoke_backend_geometry.py`。

### 2026-10-22 A4 高级 GPS 源

2026-10-22 A4 高级 GPS 源：`SourceManager` 以 `SourceSpec` 列表描述源，`[source]` 旧字段与错误消息保持兼容；`energy_type`、`position_type=volume|beam`、plane `annulus/ellipse/square`、`rot1/rot2`、`confine`、`angular`、`[source.<名称>]` 多源与 `intensity`、`particle=ion`、`[phase_space]` 写出及 `[source] phase_space_file` 重放均为实验性。离子、confine 与相空间粒子定义在 master `BeginOfRunAction` 的 `SourceManager::PrepareForRun()` 中应用，失败记入 `source_prepare_run` 并非零退出（GPS 本会静默忽略不存在的 confine 体）。多源时 `/AIHL/source/*` 单字段命令必须拒绝。相空间事件 k 重放历史 k，与 worker 分配无关。`scripts/test_gps_sources.py` 以敏感水体内初级粒子首步的位置、方向、动能验证；GUI 仍阻止生成这些字段，不得宣称 GUI 已支持。Geant4 ≥ 11.2 的放射性衰变 1 年时间阈值会跳过 Co-60 等长寿命核素，属 A6。

### 2026-10-22 A3 统计不确定度

2026-10-22 A3 统计不确定度：Edep/Dose/Fluence/LET 计分器逐事件累计 `sum`/`sum_sq`（`Scoring/HistoryStatistics`），worker 在 `Write()` 提交到互斥合并登记表，master 在本轮 `EndOfRunAction` 写 `scorer_statistics[_rR].csv`（任何输出格式，N 取 `run->GetNumberOfEvent()`）；每 worker CSV/ROOT 只追加可相加列（ROOT `g4usim_root_v4`）。LET 比值误差为 delta 方法。`scripts/test_statistical_uncertainty.py` 以原始 hits 独立重算及 20 次独立 run 的实际离散对账；不得把统计误差描述为物理系统误差或已验证偏置运行。

### 2026-10-21 M5 输出后处理原型

2026-10-21 M5 输出后处理原型：`scripts/output_extension_registry.py` 的 API v1 只允许显式加载可信 Python 模块；`scripts/run_output_extension.py` 独占发布 JSON，内置 `dose_json` 读取并按 run/touchable 合并实验性 Dose worker CSV。`scripts/test_output_extensions.py` 覆盖接口与失败路径，`scripts/test_dose_scoring.py` 对真实 Geant4 双线程双 run 原始 CSV 和 JSON 做独立对账。无需宣称插件沙箱、C++ scorer 动态注册、任意输出转换或独立物理 benchmark 已完成；接口与限制见 `docs/输出扩展原型说明.md`，统一平台含 `output_extensions` 静态用例。

### 2026-10-21 M1 矩形平面源原型

2026-10-21 M1 矩形平面源原型：`[source]/position_type=plane` + `shape=rectangle` + `center` + 正 `halfx/halfy` 已传递至 GPS `Plane/Rectangle`；矩形固定于 XY 平面，可用既有 fixed/isotropic 角分布。GUI generated 可写出受支持子集并拒绝 square/annulus、负半宽、字段混写；`scripts/test_run_summary.py` 在敏感硅体真实运行 128 事件验证初级粒子命中位置范围和正向束流、非法源参数前置失败。首条 sensitive hit 是输运后的步进，不能将其位置或动量当作精确 GPS 顶点。尚未独立验证源采样均匀性、旋转矩形与其他高级形状；原型不构成 M0/M1 总验收。

### 2026-10-21 开发策略改为 M0–M5 跨阶段功能切片，不以 M0 全部完成为其他阶

2026-10-21 开发策略改为 M0–M5 跨阶段功能切片，不以 M0 全部完成为其他阶段原型开发的前提。首条真实端到端功能是实验性敏感 physical touchable Dose：以 hit Edep 和 `GetMass(true,true)` 算 Gy、每 worker/run 独立 CSV、GUI 仅以沉积求和后除单份质量，必须提示无通量/时间归一化与独立物理 benchmark。后端专项 `scripts/test_dose_scoring.py`，GUI 专项 `gui/smoke_tests/smoke_dose_results.py`。完整物理验收及 M0 未完成项仍须分别追踪。

### 2026-10-21 M0 源字段冲突失败边界

2026-10-21 M0 源字段冲突失败边界：`[source]/isotropic=true` 与显式 `direction` 同时出现时在配置阶段失败；`position_type=point` 不得同时配置 plane 专有的 `center`/`radius`，`position_type=plane` 不得同时配置 point 专有的 `position`；省略 `position_type` 时 `center`/`radius` 不允许静默丢弃。原 `plane` 的 center/radius 兼容默认值和无类型的旧 `position` 点源继续可用。GUI 的 isotropic writer 不得写 `direction`；真实负向与兼容回归见 `scripts/test_run_summary.py`，GUI 见 `smoke_source_editor_v2.py`。此外点源/平面源 isotropic 使用置于敏感硅体内的 1 MeV 质子各完成 64 事件，hits 初级方向各分量均观察到正负方向且模长为 1；这仅验证 GPS 实际采样存在方向变化，不证明统计均匀性。其他 Source/GPS 组合仍属 M0 缺口。

### 2026-10-21 M0 源配置显式空值

2026-10-21 M0 源配置显式空值：`SourceManager::LoadFromConfig()` 对显式存在但为空白的 `[source]/preset`、`particle`、`energy` 在配置阶段报错；字段完全缺失仍允许沿用默认值或 preset。先前 `energy =` 在真实 Windows Release `--inspect-run` 中被静默视为已消费并返回成功。负向回归见 `scripts/test_run_summary.py`，GUI 原有 `validate_source_model()` 对三字段已有空值拦截。此修复只闭合三个字段的失败边界，不代表全源 schema 或 GPS 实际状态已全部验收。

### 2026-10-19 M0 数值有限性修复

2026-10-19 M0 数值有限性修复：`UnitParser` 拒绝 `NaN`、`Inf` 及单位换算后溢出的数值；`SourceManager` 直接 setter 拒绝非有限能量、位置、方向和圆盘半径，方向使用安全归一化。GUI Source Editor 对生成字段提前拒绝非有限值。旧 Windows Release `--inspect-run` 曾接受 `direction=NaN,0,1`；负向回归分别在 `scripts/test_run_summary.py`、`gui/smoke_tests/smoke_source_editor_v2.py`。完整源 schema 和物理 benchmark 仍需独立验收。

### 2026-10-19 M0 固定方向实际输运修复

2026-10-19 M0 固定方向实际输运修复：原 `SourceManager::ApplyAngularDistributionToGPS()` 使用 `beam1d`，Geant4 GPS 的零展宽 beam1d 在真实主粒子 hits 中总沿 -Z，忽略 `[source]/direction = 0,0,1`。固定方向必须用 `planar` 并传归一化向量；正 Z、负 Z、斜向及 preset 覆盖需按初级粒子 `px/py/pz` 真实验证。`[source]/preset=isotropic_neutron` 后显式 `isotropic=false` 且无 `direction` 必须前置拒绝，不能静默继承 isotropic。`scripts/test_run_summary.py` 的输出文件登记测试使用单独朝外束流配置，避免方向纠正后 5000 事件穿靶带来的多 GB hits；这是测试夹具，不改变生产配置。

### 2026-10-19 M0 平面圆形源中心修复

2026-10-19 M0 平面圆形源中心修复：主 INI 的 `[source]/position_type = plane` 使用 `center = x,y,z` 和 `radius`，三个中心坐标必须传入 Geant4 GPS；旧实现仅保留 z，忽略 x/y，尽管 `beamOn` 和摘要均报告成功。`SetPlaneBeamAt` 接受三轴中心，旧 `SetPlaneBeam(radius,z,direction)` 仍以 x=y=0 兼容。`scripts/test_run_summary.py` 以真实 `hits_t0.csv` 初级粒子轨迹校验 x/y/z，GUI writer 对 plane 写 `center` 而不写 point 的 `position`。此测试限圆形平面位置，不代表高级 GPS/物理基准全部完成。

### M0 源位置 INI 失败边界

M0 源位置 INI 失败边界：`[source]/position_type` 目前只实现 `point` 与 `plane`。未知或空值必须在初始化前失败，`point` 必须提供非空 `[source]/position`（三长度分量），不得保留 preset 的旧位置后静默运行。2026-10-19 实测 `unsupported_ellipsoid` 修复前完成了 2 个事件，修复后非零退出且无 hits。反例与测试见 `scripts/test_run_summary.py`；尚未形成全部源配置的闭合 schema。

### M0 原生 GPS 交错回归

M0 原生 GPS 交错回归：SourceManager 已创建 GPS 后，单字段 setter 只能同步其对应字段；首次惰性创建才可整体回放缓存。2026-10-19 真实反例 `/gps/ene/mono 2 MeV` 后 `/AIHL/source/particle proton` 曾把采样能量回退为缓存的 1 MeV；现双线程三轮主粒子实测 1/2/2 MeV。`effective_source_energy_MeV` 是 Manager 缓存，不能声称记录了原生 GPS 当前采样能量。见 `scripts/test_run_summary.py`。

### M0 计分生命周期

M0 计分生命周期：`ActionInitialization::Build()` 在 Geant4 初始化时将 master `ScoringManager` 配置克隆到各 worker。真实双线程反例表明 `/run/initialize` 后或两次 `beamOn` 之间执行 `/AIHL/scoring/eventEdep false` 曾返回成功、worker 却继续写出 `event_edep_tN[_rR].csv`。`ScoringMessenger` 的所有修改命令（含直方图与 verbose）现在只允许 `G4State_PreInit`，只读 `print` 保留初始化后可用；batch 与 `csh` 非法状态必须拒绝，保留已完成 run 与文件。摘要原 `scoring_event_edep_enabled` 属于早期初始化快照，新增 `effective_scoring_event_edep_enabled` 是最终 Manager 值；不得把任一字段当成 Geant4 物理标定。改动限于 Messenger 状态门禁与该字段，不表示其他动态命令路径已验证。

### M0 输出后缀安全边界

M0 输出后缀安全边界：真实 MT 后端在 `ActionInitialization::Build()` 强制 worker 使用 `_tN`，因此 `/AIHL/output/setThreadSuffix false` 即使在 `PreInit` 执行，也不能更改 worker 文件名。Messenger 现必须拒绝 `false` 并记录失败；`true` 保持默认 `_tN`。不得关闭后缀造成并发 CSV 覆盖，也不得把主线程的标志变化当作 worker 已应用。真实回归见 `scripts/test_run_summary.py`，物理结果另行验证。

### M0 线程数生命周期

M0 线程数生命周期：`/AIHL/app/setNumThreads` 仅允许在 Geant4 `PreInit` 期间改变 worker 数。初始化后 `G4MTRunManager::SetNumberOfThreads` 实测会发 `Run0112` warning 并忽略请求；不得先修改 `SimulationContext` 或有效来源再宣称已应用。Messenger 须在非法状态返回可检测的失败，`SimulationManager::SetNumThreads` 也须先检查状态。原始反例与 batch/`csh` 实际回归见 `docs/测试平台说明.md`；初始化后变更须新进程重新启动。

### M0 输出目录生命周期

M0 输出目录生命周期：`/AIHL/output/setDir`、`/AIHL/output/setThreadSuffix` 与 `/AIHL/app/setOutputDir` 只能在 Geant4 `PreInit` 执行；`SimulationManager::SetOutputDir` 也必须在修改 context 与来源前验证状态。真实双 run 反例显示，初始化后修改主线程输出目录会令 CSV 留在旧目录、最终摘要写到新目录且进程错误地返回 0。已在 `scripts/test_run_summary.py` 为两种时机和三个命令增加拒绝/文件保留回归；`PreInit` 无显式 CLI 锁的目录切换仍允许，`OutputManager::IsInitialized()` 可能在 macro 前已为 true，不得以此取代 Geant4 状态门禁。未测试其他 UI 的全部动态命令途径，M0-4 仍为部分支持。

### 2026-10-28 测试平台报告 v2（断言级证据与指纹稳定）

2026-10-28 测试平台报告 v2：`scripts/run_m0_tests.py` 现在经 `tools/test_assert_probe.py` 运行每个用例，探针用 `runpy.run_path` 执行脚本、`sys.settrace` 只统计目标文件内已执行 `assert` 行的次数并打印 `G4USIM_ASSERTS=<n>`，原样透传 argv、退出码与未捕获异常；runner 解析该 marker，退出 0 但缺少 marker 判 fail。`report.json` 升 `version: 2`：逐用例 `assertions_executed`、`assert_sites`、`assert_probe`（`settrace_assert_lines_v1` 或 `marker_missing`）、`log_sha256`，报告级 `assertions_executed_total`、`assert_sites_total`、`cases_with_assertion_counts`、`cases_with_zero_assertions`、`tests_content_fingerprint`、`skip_policy`。计数是"已执行断言下界"（循环内 assert 每次迭代都计）；验证 helper 必须用 `assert` 表达，写成 `raise AssertionError` 时探针看不见——`cases_with_zero_assertions` 只表示"尚未迁移到 assert"，不等于未验证。`tests_content_fingerprint` 覆盖 `scripts/`、`tools/`、`gui/smoke_tests/`、`gui/g4usim_gui/`、`config/`、`scenarios/`、`schema/`、`macros/`、`test/` 的全部文件并归一 CRLF；`workspace_source_fingerprint` 仍按原始字节哈希编译输入。`scripts/check_report_evidence.py`（static 用例 `report_evidence`）校验最新报告的 schema、version、断言计数、两种指纹、逐用例日志哈希与 `backend_provenance`，CI 跑完测试后必须执行它。`--report-root` 默认改为 `out/verification`（Git 忽略），`--fail-on-skip` 让缺失 Qt/uproot/后端的 skip 变成失败（CI 两个 profile 步骤都启用），不得用退出码 2 的 skip 冒充绿色。

同轮修复"指纹被换行劫持"：`.gitattributes` 原来的 `* text=auto` 让 Windows checkout 写入 CRLF，实测 79/195 个编译输入因此是 CRLF；一次普通 `git checkout`/`git merge` 会改变磁盘字节却不产生 `git diff`，使工作区指纹与可执行文件内嵌指纹不一致、所有 backend 用例被 skip 成"需要重建"。现在对 `*.cc`、`*.hh`、`*.h`、`*.in`、`*.py`、`*.json`、`*.ini`、`*.mac`、`*.csv` 与 `CMakeLists.txt` 固定 `text eol=lf`；新增会被原始字节哈希的文件类型必须同时加 eol 规则，或改为归一化后再哈希。换行只是 checkout 产物，不是证据内容。
