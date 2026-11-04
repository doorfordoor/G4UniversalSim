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
### 2026-10-28 阶段 1b：零断言清零、E2-S1 editor→writer 边界用例、线程感知探针

阶段 1.4 的报告 v2 让每个用例报告 `assertions_executed` 后，暴露出 9 个用例为 0：`gui_unsupported_features`、`benchmarks`、`unsupported_features`、`unconsumed_config`、`material_schema`、`geometry_safety`、`gui_backend_agreement`、`gui_sketch_accuracy`、`config_schema`。它们的通过此前只代表进程退出码 0（`raise AssertionError`、`sys.exit(1)` 或收集式 `return 1` 对探针不可见）。

迁移规则（不改语义）：只把**已有的失败判定**改写成 `assert`，不新增也不放宽校验；容差、消息、前置失败条件、退出码语义保持不变。`scripts/test_config_schema.py` 的 `check_gui(failures)` 返回列表式判定改为当场 `assert`（EXE 缺失分支返回 0，GUI 失败已在断言处抛出）；`scripts/test_gui_backend_agreement.py` 删除`mismatches` 列表与 `return 1`，首个不一致即断言失败，消息必须含几何名与 GUI/后端各自 verdict；`scripts/test_sketch_accuracy.py` 在 worker 里收集 `problems`、在主线程 `assert not problems` 聚合（跨线程逐项判定不计入断言数，这是有意的取舍）。

`scripts/run_benchmarks.py` 的断言位置是行为契约，不只是计数问题：断言必须在 `write_report()` 之后做聚合判定。把断言放进逐基准循环会在一项失败时中止后续基准、跳过 `benchmark_report.json/md` 写出，属于回归；正确行为是跑完全部基准、写出报告，再以含 name/case/quantity/deviation/allowed 的 `AssertionError` 非零退出。

探针升级为 `settrace_assert_lines_v2`：`sys.settrace` 只覆盖调用线程，因此同时安装 `threading.settrace`，脚本自己启动的线程（`ThreadPoolExecutor`、`threading.Thread`）里执行的 `assert` 也计数；共享计数用 `threading.Lock` 保护；脚本运行前已存在的线程不计，`--no-assert-probe` 时报告记为 `disabled`。`scripts/check_report_evidence.py` 接受 v1/v2/disabled（保留 v1 以便复核历史归档报告），`scripts/test_m0_runner.py` 增加 worker-thread 反例（worker 3 次 + 主线程 1 次 = 4）。

E2-S1 的六个 editor→writer 边界从被忽略的 `out/verification/e2-audit-20261027/writer_boundary_probe.py` 提升为 static 用例 `writer_boundary`（`scripts/test_writer_boundary.py`，24 条断言）：`energy="1e308 GeV"`、plane circle `radius="1e308 m"`、`radius="0 mm"`、`default_cut="1e308 m"`、直方图 `10 MeV / 1 MeV` 与 `1000 keV / 1 MeV` 全部必须被 editor 校验拒绝且消息含 `Cannot generate main.ini with editor validation errors`；另加 `radius = 2 mm` 接受对照与"writer 不产生任何文件" 的 `rglob` 断言。该用例不需要 Qt/后端，因此放在 static 层。

结果（报告 `out/verification/stage1c-20261028/20261028-002802-d6dbf2ee/report.json`）：79 PASS / 0 FAIL / 0 SKIP（static 6 / gui 26 / backend 33 / integration 14）、`assertions_executed_total=116133`、`assert_sites_total=2387`、`cases_with_zero_assertions=[]`、`assert_probe=settrace_assert_lines_v2`；`source_fingerprint=ba493e73…`（exe 内嵌一致）、`tests_content_fingerprint=497be13f…`、`tracked_source_gate=pass`、`untracked_source_files=[]`。报告与 79 个逐用例日志复制在 `docs/verification/stage1b-20261028/`（`README.md` 如实写明断言数是已执行断言的下界、不证明物理正确性、不覆盖 Linux CI）。

验收口径：断言总数不得下降，且 `cases_with_zero_assertions` 必须为空；新增测试用例时若 helper 用 `raise` 表达失败，报告会显示 0 断言，视为未完成迁移。

### 2026-10-28 E3 Linux 构建、可移植性缺陷与 CI workflow（本机 WSL 验证，Actions 未运行）

**做了什么**：在 WSL Ubuntu 24.04.4 + conda-forge `geant4=11.3.2`（micromamba 装到 `$HOME`，免 sudo）上完成配置、构建（`cmake -S . -B ~/g4build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=~/g4env`，cmake 3.28.3 / g++ 13.3），跑通 `--help`、`--capabilities`、`--check-geant4-data`、`--dry-run` 冒烟，并用统一 runner 跑 `--profile backend`（34/34，109853 断言）与 `--profile integration`（14/14，4324 断言）；两份报告通过严格证据门禁，`source_fingerprint=5bd97ec5…`、`tests_content_fingerprint=6fb23039…` 与 Windows 全量报告相同。

**Linux 才暴露、已修复的缺陷**：
1. `src/Geometry/GeometryExport.cc`：`Escape(material ? material->GetName() : std::string())` —— GCC 报 `operands to '?:' have different types 'const G4String' and 'std::string'`，MSVC 会隐式转换。改为先 `const std::string materialName = material ? std::string(material->GetName()) : std::string();` 再使用。
2. `src/Scoring/TrajectoryRecorder.cc`：`return volume ? volume->GetName() : std::string("OutOfWorld");` 同类问题，改为显式 `std::string(...)`。全仓复查无其它同类三元（`src/Biasing/BiasingMultiParticleXS.cc` 是 G4String:G4String，合法）。
3. PySide6 解释器收尾 `SIGSEGV`（约 4/5 复现）：`gui_plots_backend` 打印 OK、断言全过，但进程以 -11 退出。gdb 栈为 `PySide::runCleanupFunctions()` → `destroyQCoreApplication()` → `Shiboken::BindingManager::visitAllPyObjects()` → `QObject::~QObject()`——PySide 在收尾时统一析构仍存活的 Qt 对象，matplotlib canvas/父子控件被二次删除。修法：`QApplication` 存活时显式 `close()`/`deleteLater()`/`processEvents()`/`del` 控件树（`gui/smoke_tests/smoke_plots.py`、`smoke_plots_backend.py`；产品入口 `gui/g4usim_gui/app.py` 的 `run_app` 同样在 `app.exec()` 后销毁主窗口）。`fsspec`/`asyncio` 线程关闭不能修复此问题。

**测试侧的平台假设（均已修）**：`scripts/test_geant4_data_locator.py` 原写死 `D:/ProgramFiles/Geant4/share/Geant4/data`，Linux 上打印 SKIP 并 exit 0（runner 记为 pass、0 断言）；现改为 `discover()` 先用当前环境跑 `--check-geant4-data` 拿到 `datasets[*].folder/path`，在临时目录按这些名字建符号链接构造数据根，再跑五个子用例；空目录用例只断言“不得 required_complete、缺失项 path 为 None”，不写死缺失数量（conda 布局下 Geant4 仍从编译前缀找到 `PhotonEvaporation6.1` 等）。`scripts/test_backend_capabilities.py` 的 GDML 期望值改为 `G4USIM_EXPECT_GDML` 或扫描 `build*/CMakeCache.txt`。`scripts/check_report_evidence.py` 的 `resolve_log()` 改为报告目录副本优先（报告目录同名 → `logs/` 同名 → 记录里的绝对路径），否则复制证据目录再篡改副本日志会被原始日志掩盖；`--allow-incomplete` 接受没有 `exit_code` 的 skip 记录（未运行没有退出状态）。

**CI**：新增 `.github/workflows/linux-geant4.yml`（`ubuntu-24.04`、`GEANT4_VERSION=11.3.2`、micromamba、`pip install -r gui/requirements.txt`、构建 `build_linux`、`--check-geant4-data`、按 `Geant4Config.cmake` 写 `G4USIM_EXPECT_GDML`、backend/integration 各自报告目录与门禁、篡改副本日志负向对照、`upload-artifact@v4` `if: always()`）。

**未验证 / 不得宣称**：GitHub Actions 上的实际运行（本机无 `gh` CLI）；Geant4 11.2/11.4 矩阵；非 Ubuntu 发行版；GUI 在真实桌面环境（非 offscreen）。E3 因此仍为“进行中”，不得写成 Done。

**环境要点**：conda 的 Geant4 数据在 `$G4_PREFIX/share/Geant4/data/<folder>`，环境变量由 `activate.d/*.sh` 设置，只有 `micromamba run -p <env> -- <cmd>` 才会注入；`LD_LIBRARY_PATH=$G4_PREFIX/lib` 是运行必需。WSL 里 `nohup ... &` 的长跑任务会在实例空闲重启时被杀，长跑必须让 `wsl.exe` 会话保持连接（Windows 侧后台 job），日志/报告写到 `$HOME/reports/` 而不是 `/tmp`。

### 2026-10-28 证据门禁自洽性加强、日志摘要按落盘字节计算

阶段 1b 的报告 v2 把"逐用例断言数"写进了报告，但门禁只检查了"总数 > 0"和"哈希字段非空"两类弱条件。Astra 2026-10-28 审查把这条判为缺陷，实测可复现：把任一通过项 `assertions_executed` 改成 0 并补进 `cases_with_zero_assertions`，或把某个 `log_sha256` 换成 64 个 `0`、把 `assertions_executed_total` 改成 999999，`scripts/check_report_evidence.py` 仍然输出 `report evidence: OK`。

同一轮暴露第二个缺陷：日志摘要与磁盘字节不符。`scripts/run_m0_tests.py` 曾用 `log_path.write_text(...)` 落盘、却对写前内存里的 LF 字符串做 SHA-256；Windows 文本模式把换行写成 CRLF，于是 79 个归档日志**原始字节 0/79 匹配、CRLF→LF 归一后 79/79 匹配**。摘要描述的是读者无法复现的字节序列，证据链在此断开。

现行契约（必须遵守）：

- 日志与 `report.json` 都用 `write_bytes` 写 UTF-8/LF 字节，摘要对**落盘字节**计算；报告级与逐用例都写 `log_digest_algorithm = "sha256_raw_bytes_lf_v2"`。新增任何"带摘要的证据文件"都必须遵守"先定字节、再算摘要"，不得对内存字符串算摘要。
- 门禁顺序：schema/version → `assert_probe` 不得为 `disabled` → `log_digest_algorithm`（严格模式只认 v2）→ `profile` 合法 → 双指纹 64 位小写 hex → `backend_provenance` → 逐用例字段完整、名称唯一、层合法、状态合法 → 发布报告不得含 `fail`/`skip`（`--allow-incomplete` 仅供排查）→ 通过用例 `exit_code == 0` 且 `assertions_executed >= 1` 且 `assert_sites` 合法 → `log_sha256` 64 位 hex 且与实际日志字节一致（先按 `log` 路径找，找不到再找报告目录同名与 `logs/` 同名，供证据副本复核）→ `assertions_executed_total` 等于逐项求和 → `cases_with_assertion_counts` 等于带计数记录数 → `cases_with_zero_assertions` 等于实际零断言列表 → 可选 `--baseline` 比对总数、逐项计数与用例集合（旧用例不得消失）。
- 归档报告（阶段 0/1/1b/1c 之前）保留原样、**不追改**：复核时必须加 `--allow-legacy-digest`（对文件做 CRLF→LF 归一后再比对）与 `--allow-legacy-probe`（v1 探针），并在结论里写明"按 legacy 口径复核"。默认严格模式拒绝它们，避免把旧摘要当成当前口径。
- CI 的 static 与 gui 两个步骤在各自跑完后**分别**调 `scripts/check_report_evidence.py`（每次都校验最新报告），不再只在最后校验一次；`scripts/test_report_evidence.py` 必须覆盖篡改反例（逐项 0 断言、求和不符、计数不符、零断言列表不符、摘要不符、日志缺失、fail/skip、重名、非法层、基线回归、legacy 摘要与 legacy 探针的放行/拒绝、CLI OK/FAIL/无报告/带 baseline）。

回归入口：`python -B scripts/check_report_evidence.py --report <report.json>`、`python -B scripts/test_report_evidence.py`（static 用例 `report_evidence`，38 条断言）。

### 2026-10-28 命令失败传播：交互偏置拒绝、材料生命周期门禁与配置值有限性

来源：Astra 2026-10-28 审查（`docs/collab/inbox/20261028-0947-astra-stage2-design-review.md`）判定为"确定为缺陷"的 D-4/D-5/D-6；反例先实测、再改代码、再补回归。

D-4 交互偏置拒绝只告警：`src/Biasing/BiasingMessenger.cc:214` 在交互会话里对修改类命令只发 `G4Exception(..., JustWarning, ...)`，命令被忽略、会话继续、`/run/beamOn` 照常执行、进程退出 0。反例（实测退出码 0、`status = completed`、`run_count = 1`、`interactive_command_failure_kind = none`，且 `/control/echo BIASING_CONTINUED` 照常打印）：`printf '/AIHL/biasing/enable true
/control/echo BIASING_CONTINUED
/run/initialize
/run/beamOn 1
exit
' | build_vs2026/Release/G4UniversalSim.exe --ui --ui-session csh --config config/main.ini --output <tmp> --threads 1`。修法：`include/Biasing/BiasingManager.hh` 新增 `RecordInteractiveReject`/`GetInteractiveRejectCount`/`GetLastInteractiveReject` 与成员 `interactiveRejectCount_`、`lastInteractiveReject_`；`src/Biasing/BiasingMessenger.cc` 在发 warning 前调用 `manager_->RecordInteractiveReject(command->GetCommandPath(), message + " Command ignored.")`；`main.cc` 交互段记录会话前计数、把它加入 `hasHandlerFailure` 与失败 kinds，`biasing` 作为独立 kind 进入 `interactive_command_failure_kind`，并把最后一条拒绝写进 `interactive_command_failure_message`。修后实测：退出码 1、`status = failed`、`run_count = 0`、`interactive_command_failure_kind = biasing`、`BIASING_CONTINUED` 不再出现。

D-5 材料命令缺生命周期门禁：反例 `/run/initialize` 后执行 `/AIHL/material/addNist nist=G4_WATER name=late_water` 静默成功、会话继续、`status = completed`、`effective_materials_source_status = non_file_mutation`、退出码 0，但几何已建、新材质不被任何体积使用。根因是 `MaterialManager::locked_` 只由 `/AIHL/material/setLocked` 手动设置（`src/Materials/MaterialMessenger.cc` 里是唯一调用点），交互路径没有 `main.cc` 的初始化守卫。修法：`MaterialMessenger` 构造函数对 9 个修改命令（`load`、`addNist`、`addIsotope`、`addElement`、`addElementFromIsotopes`、`addMaterial`、`buildAll`、`setLocked`、`clear`）调用 `AvailableForStates(G4State_PreInit)`；`print`/`list` 保持只读不限状态。修后实测：`/run/initialize` 后调用退出码 1、`status = failed`、`run_count = 0`、`interactive_command_failure_kind = geant4_illegal_application_state`、后续 `/control/echo` 不再执行。注意：Geant4 对非法状态命令同时给出"illegal application state"诊断与非零 UI 状态，`main.cc` 的 kind 计算必须优先报具体诊断，不能让 `geant4_command_status` 把它降级成 `multiple`。

D-6 配置值有限性：`src/Config/ConfigValue.cc` 的 `ParseStrictDouble` 使用 `std::strtod`，接受 `inf`/`nan` 并静默溢出为 `HUGE_VAL`；`ParseStrictInt` 一直有 ERANGE 与 32 位范围检查，double 没有任何检查。反例（`[biasing] enabled = true` + `[biasing.xs.proton.elastic] factor = inf`、`min_weight = nan`，`--dry-run` 曾退出 0 且无警告）。可达字段：`BiasingManager::LoadFromConfig` 的 `factor`/`min_weight`（`config.GetDouble`）与 `SimpleBoxTemplate`/`LayeredDeviceTemplate` 的 `visual.alpha`；几何配置文件的 `vis.alpha` 走 `UnitParser::ParseDouble`（一直拒绝非有限值），不受影响。修法：`strtod` 前 `errno = 0`，解析后 `if (errno == ERANGE || !std::isfinite(parsed))` 抛 `Config value '<v>' is not a finite <type>`；`#include <cmath>`。修后实测：`--dry-run` 退出 1、输出 `G4UniversalSim fatal error: Config value 'inf' is not a finite double`，合法配置仍退出 0。

回归：`scripts/test_interactive_commands.py` 新增 `biasing_interactive_reject`（断言非零退出、`status = failed`、`BIASING_CONTINUED` 不出现、`kind = biasing`、`run_count = 0`）与 `material_after_initialize`（断言非零退出、`MATERIAL_CONTINUED` 不出现、`kind = geant4_illegal_application_state`、`run_count = 0`），原有 `material_failure`（初始化前材料命令异常）仍断言 `kind = material`；新增 backend 用例 `scripts/test_config_value_finiteness.py`（合法配置通过、`factor = inf` 与 `min_weight = nan` 各自非零退出并匹配 `is not a finite double`）。本轮同时把 `main.cc` 的 kind 计算从嵌套三元改成显式 kinds 列表，保留历史 `material_and_output` 映射，并把 `geant4_command_status` 降级为仅在无具体诊断时使用的兜底。

### 2026-10-28 屏蔽场景证据语义（Astra 审查 D-7）

Astra 的 2026-10-28 审查把 `scenarios/shielding_coating/analyze.py` 判为缺陷：缺证据被混作零结果。
复现（真实输出目录）：`statistics()` 在 `scorer_statistics.csv` 不存在时返回空字典，`quantity()` 于是写 `total = 0.0`、
`rel_error = None` 进 `shielding_report.json`；`run_summary.txt` 的 `status` 从未检查（`status = failed` 仍会被分析）；
`events = int(summary["run_0_completed_events"])` 在零事件时除零；相空间文件缺失时静默产出空 `particles` 与
`primary_transmission = 0.0`，与"确实没有粒子穿过"不可区分；陈旧文件与多轮目录同样不报错。

修法（现行契约）：

- 运行事实：`status` 必须是 `completed`，`summary_write_status` 必须是 `completed`，`output_failure_status` 必须是
  `none`/`not_applicable`，`run_count` 必须为 1；`run_metadata.json`（`schema = run_metadata_json_v1`）必须正好列出
  一轮且 `completed_events == planned_events > 0`，并与 `run_0_completed_events` 一致。任一不满足：打印原因、退出码 3、
  **不写** `shielding_report.json`（避免留下看似有效的零结果）。
- 统计证据：`scorer_statistics.csv` 缺失时查 `run_metadata.json` 的 `generated_files`——列出但磁盘没有 = 证据被删/移位
  （退出码 3）；没列出 = 这一轮确实没有统计（零沉积），报告零但每个量带 `evidence = no_statistics_file_zero_deposition`，
  且 `evidence` 段记录该状态与警告。存在其他轮次的 `scorer_statistics_r*.csv` 视为混轮次（退出码 3）。
- 相空间：没有 `phase_space_t*.csv`、文件为空、出现非 0 `runID`、或 `eventID` 超出完成事件数（陈旧文件）都是证据错误。
- 报告新增 `evidence` 段（`run_summary`/`run_status`/`run_count`/`planned_events`/`completed_events`/
  `run_metadata_schema`/`scorer_statistics`/`phase_space_files`/`warnings`），`tid`/`ddd` 各自带 `evidence` 标签。

回归：`scripts/test_shielding_coating.py` 的 `analysis` 用例在原有归一化断言之后新增五种反例——删统计文件、
`status = failed`、零事件、陈旧相空间（完成事件数改成 10 但相空间仍到 199）、真零沉积（删统计文件并从 `generated_files`
移除该项，必须 `exit 0` 且 `tid.total == 0.0`、`tid.evidence == no_statistics_file_zero_deposition`），
每种反例额外断言未写报告。实测 `G4USIM_ASSERTS=14386`、`test_shielding_coating: OK`。

边界：这仍不证明 TID/DDD 的物理正确性（法向入射、涂层阻止本领与 NIEL 数据本身未验证）；证据规则只覆盖本场景包的
`analyze.py`，其他分析脚本与 GUI 结果页不在本契约内。

### 2026-10-28 E3 在 GitHub Actions 上转绿（Linux 四 profile）

**结果**：`a5970ff` 的两次 push 在 `ubuntu-24.04` 上各跑约 12m38s，18 步全绿（`codex` run `40634469313`、`roadmap/F6-live-progress` run `40634465977`）：micromamba → conda-forge `geant4=11.3.2` → 导出数据集变量 → 指向 PySide6 插件 → cmake 配置/构建 → `--check-geant4-data` → 记录 GDML → Linux static → Linux offscreen GUI → Linux backend → Linux integration → 四份报告各自过 `scripts/check_report_evidence.py` → 篡改报告负向对照 → artifact 上传。

**三个只在 CI 出现的失败（均已复现并修复）**：

1. workflow 校验阶段失败、`jobs.total_count = 0`：job 级 `env` 用了 `${{ runner.temp }}`；`actionlint` 报 `context "runner" is not allowed here`。job 级 env 只允许 `github/inputs/matrix/needs/secrets/strategy/vars`。改用 `${{ github.workspace }}/.micromamba` 与 `${{ github.workspace }}/.g4env`（不在 tracked-source 扫描范围内）。
2. 集成套件全部失败：日志为 `qt.qpa.plugin: Could not find the Qt platform plugin "offscreen" in ""`。根因：conda 环境下 `qt-main`（Qt5）把插件放在 `<prefix>/plugins`，Qt6 从 python 可执行文件位置推导搜索路径后只查 `<prefix>/bin/platforms` 与 `<prefix>/plugins/platforms`（Qt 5.15，incompatible），site-packages 里 PySide6 自带的 Qt6 `libqoffscreen.so` 从未被搜索。修复：`QT_PLUGIN_PATH=<site-packages>/PySide6/Qt/plugins`（workflow 中由 `$G4_PREFIX/bin/python` 计算并写 `$GITHUB_ENV`）。本机用 conda 环境（Geant4 11.3.2 + python 3.11 + PySide6 6.12.0）复现了同样的空搜索路径，`QT_QPA_PLATFORM=offscreen` + 该变量后 `QApplication` 正常创建；`QT_QPA_PLATFORM_PLUGIN_PATH` 与 `QT_PLUGIN_PATH` 两种写法都有效。
3. 公开仓库的 Actions 日志需要登录（`GET /actions/runs/{id}/logs` 403，check-runs 也拿不到）。改为失败时把每个失败/跳过用例重发成 `::error`/`::warning` 注解（`scripts/ci_annotate_failures.py`，workflow 中 `if: failure()` 步骤；run 页面的 Annotations 公开可见），日志尾部一并带上；`scripts/test_ci_annotations.py` 用临时报告覆盖"有失败/有跳过/日志缺失/无报告/归档副本"五种情况。定位第 2 条正是靠这个注解。

**未完成、不得混淆**：`M0 static and GUI regression`（`.github/workflows/m0-static-gui.yml`，workflow id 391892216）在仓库设置中是 `disabled_manually`，所以 Windows/Ubuntu 上的 static+GUI 旧 job 不会随 push 触发；其 2026-10-23 的历史运行在 "Run offscreen GUI tests" 步骤失败（步骤 1–5 成功），原因尚需日志才能确认。恢复它需要仓库所有者操作网页或 token（`PUT /repos/{owner}/{repo}/actions/workflows/391892216/enable`）。Geant4 11.2/11.4 矩阵未开始。

**规则**：CI 绿必须引用具体 run id 与提交，不得把"workflow 已写"或"本机等价拓扑验证"说成 Actions 已绿；Linux workflow 只覆盖 Geant4 11.3.2 + Ubuntu 24.04（外加本 PR 起在同一 job 内跑 static 与 offscreen GUI）；失败用例注解是公开日志的替代品，不得把它当成完整日志。
- Linux CI 第二次真跑（提交 `7c317e6`）又暴露一个 CI-only 缺陷：static 层的 `doc_links` 在 Linux 上失败——`总体判断.md` 用 Windows 绝对路径（`D:/Geant4/G4UniversalSim/main.cc:170`）写链接，Windows 端 `repo_relative()` 靠工作区前缀解析成功，POSIX 上该字符串变成普通相对路径而断链。修法：`repo_relative()` 在仓库前缀不匹配时再剥离“仓库目录名”段，自检加 Windows 正/反斜杠两种路径的断言；Windows 与 WSL 上 `doc_links` 都是 116 链接 / 68 文件 / 0 断链，Linux static profile 7/7。教训：只有 Windows 跑过的 static 用例不算跨平台通过，提交前至少在本机 WSL 跑一遍 static。
- CI 第三次真跑（提交 `81391e9`）static 已绿、GUI 层失败：`gui/smoke_tests/smoke_main_window_ui.py` 断言配置页几何路径以 `test\geometry\hierarchical_test.ini` 结尾，Windows 分隔符在 POSIX 上不成立。修法：把控件文本与期望都归一成 `/` 再比较（`replace("\\", "/")`），并在断言消息里回显实际值；Windows 与 WSL 上该用例 62 条断言通过、Linux GUI profile 26/26。教训：GUI 冒烟里凡比较路径/文件名字符串，必须归一分隔符或使用 `Path` 比较，不能假设 Windows。
- Linux CI 第四轮（提交 `3291145`）**四 profile 全绿**：`3291145` 的 `codex` run [40640355033](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640355033) 与 roadmap run [40640350911](https://github.com/doorfordoor/G4UniversalSim/actions/runs/40640350911)，static / offscreen GUI / backend / integration 全部 success，各自门禁通过，篡改副本负向对照与 artifact 上传也执行成功。此前三轮分别暴露 job 级 `env` 的 `runner` 上下文、conda Qt5 插件遮蔽 PySide6 Qt6 插件、doc_links 的 Windows 绝对路径与 GUI 冒烟的 Windows 分隔符四个 CI-only 缺陷。引用“Linux CI 全绿”时必须同时给提交与 run id，并说明它只覆盖 Linux。
- 归档证据自洽（2026-10-28 补）：`docs/verification/**/logs/*.log` 现随证据一起入库（`.gitignore` 例外），`scripts/check_report_evidence.py` 的 `find_latest_report()` 同时接受运行目录（`<root>/<run-id>/report.json`）与归档目录（`<root>/report.json`），因此干净克隆上 `--report-root docs/verification/<dir>` 也能逐字节核对 `log_sha256`；回归用例覆盖归档布局。

## 2026-10-28 屏蔽/涂层场景 GUI 端到端（路线图 2B）

- **目标**：把 `scenarios/shielding_coating/` 的生成、运行、分析链路搬进 GUI，并让每个数字都带可核查证据。
- **模型层**：`scenario_model.py` 提供 frozen dataclass `ShieldingSpec`（15 个字段，与 CLI 一一对应）与纯函数
  `render()`/`generate()`；`make_scenario.py` 只保留 argparse 与 `main()`，并把 `CUSTOM`/`ENVIRONMENT`/`NIST_DENSITY`/`UNITS`/
  `length_mm`/`density`/`pore_centres`/`spectrum_from_integral_flux`/`spectrum_points` 再导出——阶段 2B-1 收薄时漏了这一步，
  导致 `scenarios/detector_response/make_detector.py` 与 `scenarios/semiconductor/make_device.py` 在 Linux CI 上 ImportError，
  由 CI 的 backend profile 抓到（本机 WSL 与 Windows 全量回归当时都还没跑到这些用例）。
- **分析层**：`analyze.py` 拆成可导入 `analyze(output_dir) -> dict` 与 `main(argv=None) -> int`，CLI 行为/消息/退出码不变；
  证据语义沿用 D-7（缺证据退出 3、真零沉积带 `no_statistics_file_zero_deposition`）；证据段新增 `niel_tables`。
- **NIEL 溯源**：`render()` 把 `[scoring.displacement]` 表写成 `scenario.json` 的 `niel = [{particle, path, sha256}]`
  （`path` 为 resolve 后的绝对 POSIX 路径，哈希为文件字节的 SHA-256；文件缺失时 `sha256 = None`）；分析把该列表原样带进
  报告的 `evidence.niel_tables`；`scenario_shielding.evidence_items()` 用模板 + 值的形式交给界面翻译，缺记录写 `not recorded`。
- **界面**：`widgets/scenario_page.py` 分基础/高级两组共 15 个字段，三层校验后才允许生成；运行用 QProcess，日志写场景目录
  `backend.log`（视图有行数上限），结束后核对摘要并把 TID/DDD/透射/反照填入五列表格（Group/Label/Value/Unit/Evidence）；
  失败显示 `describe_failure()` 原因，缺证据显示标签而不是零。页序：开始、项目、配置、场景、运行、结果、历史、扫描。
- **新增 GUI 页面时必须同步**：`smoke_main_window_ui.py` 的 `expected_titles` 与 `_nav_buttons` 索引断言、`i18n.ZH_CN`
  （标题/描述/按钮/表头/字段标签与帮助）、`main_window.py` 的页面实例化、`shell.py` 的 `_page_specs` 与 `_set_language`/`_set_theme`
  元组、`icons._PATHS` 的图标键；否则壳层会少图标或断言失败。
- **跨平台教训**：Windows CI 的临时目录可能是 8.3 短路径，`Path.relative_to()` 对未 resolve 的路径失败后不要静默保留旧值
  （`scan._rebase` 现同时尝试原路径与 resolve 后的路径）；比较路径一律 `.resolve()` 或归一成 `/`；只在本机 Windows 跑过的
  smoke 不算跨平台通过。
- **回归入口**：`scripts/test_shielding_scenario_model.py`（生成器与兄弟场景兼容）、`scripts/test_scenario_shielding_core.py`
  （headless 校验/生成/200 事件真跑/证据）、`gui/smoke_tests/smoke_scenario_page.py`（Qt）、`gui/smoke_tests/smoke_scenario_backend.py`
  （12 步端到端真后端）、`scripts/test_shielding_coating.py`（命令行链路与五种证据反例）。
- **限制**：只有法向入射平板几何与这 15 个字段；不做角度分布、非平板几何、光核/活化；本场景不是新物理基准。
- **第二个 CI-only 缺陷（同轮）**：`scripts/test_scenario_shielding_core.py` 写死 `build_vs2026/Release/G4UniversalSim.exe`，
  Linux CI 的 backend profile 因此失败（`backend executable not found`）；runner 已导出 `G4USIM_EXE` 并传 `--executable`。
  新后端/集成测试必须 `Path(os.environ.get("G4USIM_EXE", "") or ROOT / "build_vs2026" / "Release" / ...)`，
  并由 static 用例 `platform_paths`（`scripts/check_test_platform_paths.py`）防止复发：提到 `build_vs2026` 必须同时读 `G4USIM_EXE`，
  不得写死盘符路径（`scripts/check_doc_links.py` 的自检样例除外）。

### 2026-10-28 F6 进度协议加可选 sequence

`[G4USimProgress]` 消息新增可选 `sequence`：`src/Actions/RunProgress.cc` 的 `State` 增加进程级 `long long sequence`（只在 telemetry mutex 下自增），`Emit()` 在 `run_id` 之后写 `"sequence":<n>`；`Begin()` 不重置它，因此同一进程内序号跨 run 单调递增。`gui/g4usim_gui/core/run_progress.py` 的 `ProgressParser` 记录 `_last_sequence`：字段缺失时保持旧行为（兼容旧后端），出现时必须是非负整数且严格递增，重复或回退的行被丢弃；解析器仍保留原有 run_id、计数不回退、终态后拒绝更新等规则。回归：`gui/smoke_tests/smoke_live_progress.py` 增加"重复/回退/非整数/缺失"四类断言，`scripts/test_live_progress.py` 的 `validate()` 断言所有真实消息都带 sequence、严格递增、跨 run 单调（第二轮 begin 大于第一轮 end）。文档 `docs/实时运行进度.md` 的字段表、示例与解析说明同步更新；`scripts/check_report_evidence.py` 等证据链不受影响（消息不进报告）。该字段是顺序证据，不是物理或性能证据，不改变最终结果判定。

### 2026-10-28 Geant4 11.4 兼容性探测与版本矩阵

**动机**：ROADMAP 的 E3 遗留"11.2/11.4 矩阵"。11.4 是当前 conda-forge 的稳定线（`geant4=11.4.3`），需要回答：项目能不能在 11.4 上构建、回归是否成立、需要改什么。

**工具链门槛（本机 WSL Ubuntu 24.04.4）**：Geant4 11.4 的 CMake 检查比 11.3 严，系统库三个都低于下限——

| 依赖 | 系统版本 | Geant4 11.4 下限 | 做法 |
| --- | --- | --- | --- |
| expat | 2.6.1 | 2.8.5 | conda-forge `expat` 2.9.0（`libexpat.so.1.13.0`） |
| zlib | 1.3 | 1.3.2 | conda-forge `zlib` 1.3.2 |
| freetype | 2.13.2 | 2.14.3 | conda-forge `freetype` 2.14.3 |

CMake 需要显式 `-DEXPAT_INCLUDE_DIR=$PREFIX/include -DEXPAT_LIBRARY=$PREFIX/lib/libexpat.so`、`-DZLIB_INCLUDE_DIR`/`-DZLIB_LIBRARY`、`-DFREETYPE_INCLUDE_DIRS=$PREFIX/include/freetype2`/`-DFREETYPE_LIBRARY`；否则 find 模块先命中系统旧库，configure 阶段失败。

**代码改动**：`src/Core/Geant4DataLocator.cc` 的数据集表按 `G4VERSION_NUMBER` 分段，新增 `>= 1140 && < 1150` 分支，12 项：`G4LEDATA=G4EMLOW8.8`、`G4LEVELGAMMADATA=PhotonEvaporation6.1.2`、`G4RADIOACTIVEDATA=RadioactiveDecay6.1.2`、`G4PARTICLEXSDATA=G4PARTICLEXS4.2`、`G4ENSDFSTATEDATA=G4ENSDFSTATE3.0`（前 5 个 required）、`G4NEUTRONHPDATA=G4NDL4.7.1`、`G4PIIDATA=G4PII1.3`、`G4REALSURFACEDATA=RealSurface2.2`、`G4SAIDXSDATA=G4SAIDDATA2.0`、`G4ABLADATA=G4ABLA3.3`、`G4INCLDATA=G4INCL1.3`、`G4CHANNELINGDATA=G4CHANNELING2.0`。升级小版本必须补表，否则构建期 `#error "Update the Geant4 dataset list in Geant4DataLocator.cc for this Geant4 version"`。

**环境变量坑**：`$HOME/g4env114/etc/conda/activate.d/*.sh` 里写的是 `export G4LEDATA=${CONDA_PREFIX}/share/...`；手工 `source` 前必须先 `export CONDA_PREFIX=<prefix>`（或用 `micromamba run -p`），否则 `${CONDA_PREFIX}` 展开成空串，路径变成 `/share/...`，Geant4 初始化报 `G4NuclideTable: ENSDFSTATE.dat is not found`——这是环境问题，不是 11.4 不兼容。

**三个版本相关测试缺陷（都在测试侧修，不是物理差异）**：
1. `scripts/test_geant4_data_locator.py` 写死 `DATASET = "G4EMLOW8.6.1"`（11.3 的文件夹名），11.4 是 `G4EMLOW8.8`。改为先 `discovery = discover(EXE)`、`dataset_folder = discovery["datasets"][0]["folder"]`，用后端报告的事实断言。
2. `scripts/test_physics_a6.py` 与 `scripts/test_gps_sources.py` 用方括号能级精确匹配激发态核名。实测 11.3 是 `Ni60[2505.753]`（3 位小数），11.4 是 `Ni60[2505.75300]`（5 位小数）——同一能级、不同格式化。加 `level_name(particle, nucleus, energy_keV)`：`startswith(nucleus + "[")`、取括号内 `float()`、与期望能级差 ≤ 0.01 keV；断言改为按数值计数。

**结果（本机 WSL，11.4.3）**：构建成功（`$HOME/g4build114/G4UniversalSim`，3,194,760 B），`--check-geant4-data` 报告 `geant4_version` 为 `geant4-11-04-patch-03`、12 个数据集全部 found、`required_complete: true`。四个 profile 全过：backend 35/35（109,942 断言）、static 10/10（391）、GUI 27/27（1,877）、integration 15/15（4,364），合计 87 例 / 116,574 条断言，与 11.3 的用例覆盖一致。

**CI 矩阵**：`.github/workflows/linux-geant4.yml` 加 `strategy.matrix.geant4: ['11.3.2', '11.4.3']`，job 名带版本、`G4_PREFIX`/`REPORT_ROOT` 每版本独立、artifact 名带版本；create env 步骤固定装 `expat zlib freetype`，只有 11.4 leg 的 configure 传六个 `-D*` 参数。GDML 期望值改为问构建出的可执行文件 `--capabilities`（`templates` 里是否有 `gdml` 且 `runtime`），不再 grep `Geant4Config.cmake`（该文件写法跨版本会变）。

**边界**：11.2 未测；Windows + 11.4 未验证（本机 Windows 只有 11.3.2）；11.4 下的真实桌面 GUI、ROOT/uproot、打包流程未验证；不能把 11.3 的物理结论直接搬到 11.4。


## 2026-10-29 2C 配置阶段快照与只读查看器（子集）

- **契约**：`include/Config/EffectiveConfig.hh` / `src/Config/EffectiveConfig.cc` 提供 C++17 类型化值、JSON Pointer 字段/对象路径、来源链、事务 revision 与不可变快照。拒绝非有限值、非法路径、重复事务字段及不充分的 applied 证据；失败不发布候选。requested/resolved 各自可以缺失，与显式 null 分开。revision 不是 Git SHA，序列化稳定不等于随机运行逐位复现。
- **真实接线**：`SimulationManager::ExportEffectiveConfigJson()` 在 Configure + 显式 CLI 覆盖后读取 Manager，仅覆盖启动/几何标量、物理参考、普通单源粒子/mono 能量以及少量计分开关。来源只保留获胜项，未记录输入内容哈希；命名源和相空间源省略单源粒子/能量，非 mono 分布省略缓存 mono 能量。来源缺失不能写成用户请求或 default 的假证据。
- **入口**：`main.cc` 的 `--dump-effective-config <新 JSON 文件|->` 复用真实 Configure 与递归 macro preflight，随后退出；不执行宏、不初始化内核、不写模拟目录。显式导出只允许独占创建，不覆盖已存在文件、输入 INI/macro 或它们的硬链接；写入失败非零退出，新文件可能不完整。与其他检查模式、help、UI、dry-run 互斥。原有 `--inspect-run` 与 `effective_*` 摘要接口不变。
- **GUI**：最多读取 4 MiB；拒绝重复 JSON key/path、无效 revision、非有限值和无相应证据的 applied。整个候选验证成功后才替换；失败保留原快照并显示陈旧。原始 JSON 保留作核对，路径和解码对象名都可搜索，语言切换保留选择。页面不启动 QProcess、不生成配置、不重算或改变物理，不把进度或 Manager 接受当成成功。
- **反例**：已有输出/输入/硬链接目标、缺父目录、坏宏、命名源、相空间源、非 mono 能量、损坏 JSON、重复字段、未知与 null、对象名带斜杠、语言切换。`scripts/test_effective_config_export.py` 用真实后端且读 G4USIM_EXE，并将真实输出交给 GUI parser；`gui/smoke_tests/smoke_effective_config.py` 测页面和读取器；`scripts/test_effective_config_model.py` 需 C++17 编译器，独立验证事务与不可变性。模型测试是独立附加证据，不混入 Python-only static profile。
- **未交付**：运行开始/最终化接线、所有模块/对象消费者、完整来源链与输入哈希、内核/worker 应用证据、off/auto/on、GUI 快照差异。数据模型能表示三个阶段不等于真实接入三个阶段；2C 保持进行中，验证报告入口以 STATUS 为准。

## 2026-10-29 R-01/R-02 命令拒绝与元数据失败传播

- **修前反例**：`70a1aba` 中，csh 的 `/AIHL/app/setMainConfig` 在 Configure 后被 JustWarning 拒绝，但继续读 echo/beamOn 并运行旧配置、返回 0；metadata 目标被目录占用则在文本成功摘要写出后退出 1，文本仍为 completed/exit0，目录还被预列为生成文件。原始复现见 `docs/verification/m0-known-defects-20261029/`。
- **R-01**：`AppMessenger` 在拒绝主配置切换时增加 `SimulationManager` 的 app 失败计数与诊断；`main.cc` 将它并入 csh 的停止条件和收尾失败类别，单项为 `interactive_command_failure_kind=app`。不得为了让命令成功而重新 Configure，原配置及来源保持不变。仅为受审计 csh 的直接命令保证，不扩大成 Qt UI/任意动态命令保证。
- **R-02**：`RunSummary::MetadataWriteError` 携带结构化阶段，metadata 的目录准备/打开、flush/write、close 失败分别登记 `run_metadata_open`、`run_metadata_write`、`run_metadata_close`。`OutputManager` 保留首个失败，不以次生 metadata 错误覆盖先前 worker/finalize 错误。文本/JSON 只在成功关闭后登记，重复写前撤销旧登记。
- **纠正摘要**：`FinalizeRunSummary` 捕获 metadata 异常，更新 status=failed、program_exit_code 非零和 output_failure_*，从成功产物列表剔除 metadata，尽力重写文本摘要；文本本身失败仍抛出并走真实 summary failure 路径。`summary_write_status=completed` 仅指文本成功关闭；不代表 metadata 或模拟成功。没有跨文件原子提交/断电恢复保证，失败的 JSON 可能残缺或看似完整，均不可作为成功产物。
- **反例回归**：`scripts/test_interactive_commands.py` 覆盖单/双线程 × PreInit/已初始化拒绝、停止后续命令、零 run、原来源保持；`scripts/test_run_summary.py` 覆盖真实目录碰撞与 `G4USIM_TEST_OUTPUT_FAULT=metadata_write_master|metadata_close_master`、单/双线程、多 run 保留、已有输出保留、正常 text/JSON 一致、首因不被覆盖。注入只是规定分支测试，不是实际磁盘故障。生产环境禁止设置该变量。
- **验收范围**：构建/真实回归结果见 STATUS 链接的本轮证据；不能把这两个修复当作 R-03–R-07 或完整 2C 已完成。


## 2026-10-29 Q1 数值、统计证据与 GUI 数据安全

- NumericChecks 对事件累计、平方矩与跨 worker 合并检查有限性；HistoryTally/Submit 先构造候选再提交。ScoringManager 在 BeginEvent/EndEvent/聚合回调锁存首因并中止；失败事件不再发布最终统计。LET 必须先检查有限性再处理零长度/中性哨兵。仅 ROOT 模式同样在 master 检查合并后的 mesh，worker 有限不代表合并有限。组件回归 tools/scoringNumericCheck.cc；真实单/双 worker、CSV/ROOT/both、多 run 与 LET/DDD 压力反例 scripts/test_scoring_numeric.py。极值反例验证错误传播，不是物理模型基准。
- V01 保持原未修正事件矩近似与 delta 比值公式，scorer/mesh CSV v2 末尾追加 uncertainty_estimator、uncertainty_status；N<2、分母零、总量零分别不可用，旧零数值只为兼容。ROOT 布局仍 v4；稀疏 scorer/mesh 的完整 N 只能来自同 run 元数据或显式可靠计数，损坏/矛盾不得猜测。详见 docs/输出数据契约.md 与 docs/collab/decisions/20261029-q1-uncertainty.md。
- 绘图和扫描使用 per_event，旧 per_primary API 保留数值并弃用警告，冲突参数拒绝；LET ratio 不得再除 N，跨 cell 投影缺协方差不画合成误差。scripts/test_q1_postprocessing.py 与 test_q1_results_backend.py 分别验证合成和真实多初级/稀疏 worker/跨 cell 反例。
- 项目保存用同目录临时文件 flush/fsync 后原子替换；失败保留原字节，未来版本和未知字段拒绝，不提供 E6 自动迁移。结果刷新清旧证据，扫描成功核对正事件数和逐轮一致；预览只发布最后请求。主窗口关闭只清理自己持有的各类 QProcess 和队列；不能按名称结束其他应用。合并工具显式指定优先，其次选定后端同目录精确文件名，再沿用原搜索。回归 smoke_q1_public_paths.py、smoke_output_tools.py；Windows 实际窗口另有 smoke_q1_windows.py，不用 offscreen 冒充。
- 本条记录实现契约；阶段关闭与平台证据仅看 ROADMAP/STATUS 链接，不以文档存在宣布 Q1 完成。


## 2026-10-29 Q1 几何、材料、源与场运行边界

- R03：Dose 本体质量用 GetMass(true,false,步前材料)，扣除 daughter 体积而不包括其质量；普通/参数化母体、不同副本材料和子体按真实 touchable 分开，零/负质量经 scoring_dose 失败。R04：GDML auxiliary SD 绑定按实际 LV 指针，显式名称限当前 world 且拒绝完全同名歧义。R15：现有 biasing 名称接口无法表达大小写碰撞时明确拒绝，不能丢掉一个对象继续成功；最终摘要刷新实际 attached/count，不能残留配置期零值。R24：导入时拒绝同母普通 placement 重复(name,copyNo)和daughter名称含斜线，保持不同副本号/不同父路径及已有replica/parameterised行为。回归 test_dose_scoring.py、test_geometry_a5.py、test_gdml_bias_identity.py、test_gdml_touchable_identity.py。
- R09：材料数字解析拒绝NaN/Inf/ERANGE/整数窄化溢出，构造前再检查量纲换算、质量、组分累加；简单与同位素元素在当前Geant4 11.3/11.4壳层表允许的舍入Z=1..104范围内，版本升级须重审，不能把118当此构造函数的支持上限。独立isotope与元素构造的范围分开；同位素混Z、重复真实元素atom计数int溢出、分子质量溢出均拒绝。test_material_numeric.py要求普通失败而非原生崩溃。
- R08：局部场按最近显式祖先解析完整图，以后代优先SetFieldManager(false)安装；完全同名LV、多个显式场、共享LV继承冲突先在master建world后验证并正常失败，不以worker FatalException代替可追踪摘要。V02：默认StepLimiter只对带电粒子生效，不改gamma/neutron物理。test_fields_a7.py和test_max_step_scope.py核对真实径迹/做功/过程。
- R12：isotropic重设完整theta/phi范围，不能继承旧cone窗口。R13：延迟ion/confine以实际G4SingleParticleSource身份管理，受审计直接原生GPS命令可取消对应旧配置；删除/增加/clear不能靠列表索引重放。pending期间非csh UI及csh无法审计的alias引用/定义、execute/loop/foreach、条件动态派发明确拒绝；getEnv生成的已有alias引用也必须拦截。宏仍依既有静态preflight。配置缓存不是原生GPS实际状态。R14：biasing动态section的process后缀从originalSection保留大小写；不能把hIoni改成hioni。test_gps_sources.py读取实际初级、能量与confinement顶点，test_biasing_target_contract.py核对真实wrapped process。
- R23：SD Initialize/ProcessHits捕获std与unknown异常，scoring_sd_initialize/scoring_transport_context经共享首因锁存并中止；collection/命中对象在成功移交前使用局部独占所有权。G4USIM_TEST_OUTPUT_FAULT的sd_initialize_t0、sd_initialize_unknown_t0、sd_context_t0、sd_context_unknown_t0仅在测试构造时读，worker0第二run单次注入。test_sd_context_failure.py检查首轮保留/第三轮停止/失败轮无合并统计；不代表真实内存耗尽、磁盘故障或Geant4原生致命异常都可恢复。
- 以上是当前代码契约；完整验收状态、平台与证据指纹以ROADMAP/STATUS为准。

## 2026-10-29 Q1：worker偏置、随机语义、来源与计分权重

- R25：master几何挂接只冻结按真实LV身份合并的计划，不证明worker生效。worker在ConstructSDandField建立线程私有算符并一次G4AutoDelete登记，不能每run删除（Geant4 TLS列表不注销）；BeginRun检查真实wrapped process与TLS绑定，EndRun提交按run/thread的完成收据。最终摘要须覆盖实际线程数×每个run且所有EndRun完成，缺收据必须失败，旧master字段另有scope。proposal/applied只是调用证据，不是无偏性或方差收益。派生factor*XS非有限/非正锁存失败并AbortRun，不得静默analog成功。
- R26：batch preflight/csh直接命令校验setSeeds为2–99个完整非零long且拒绝LONG_MIN；原生ApplyCommand=0不能作为忽略命令的成功证据。安全restore只支持当前MixMax/James原生格式，读一次快照→独立引擎验证→提交，坏文件不触碰真实状态；unsupported engine/legacy格式明确拒绝，建议setSeeds。每事件restore enable暂拒绝。csh命令alias展开后规范化重复斜杠，守卫与执行同一路径；动态/条件/嵌套csh拒绝，batch递归execute使用预检序列。非csh原生UI执行入口按R32明确拒绝，MT恢复只证明master状态。
- R27：有run_metadata.json时，GUI/目录后处理以合法generated_files为唯一自动输入；必须登记自身、run_summary，名单文件缺失/重复/逃逸/损坏失败。复制目录按manifest原根重定位，不能读取旧机器路径；旧文件不删除。无metadata保留legacy/unverified提示；显式单文件/list离线分析仍可用。无JSON依赖的mergeHistograms对有metadata的--input目录拒绝，改用GUI或明确文件列表；没有metadata目录明确legacy警告。
- R28：探针v3按AST作用域和行入口计数，表达式frame不能冒充assert，用户generator真实assert仍计；这是保守入口下界，不是独立命题数。v1/v2旧报告仅显式legacy复核，不改写；跨probe baseline禁止比较，必须重建同代基线后比较总数和逐例。不能通过排序fixture或增加无意义断言填补计数差异。
- R29：ParticleHit和HitRecord的weight是步前统计权重，与Geant4原生energyDeposit/cellFlux和项目fallback一致。不能用track当前/步后weight为同一步Edep、Dose、Fluence计分。phase_space是其边界采样权重，不能一并改为步前。CSV表头版本不变，此处是原有weight语义错误的修复；历史偏置结果须重算。

回归：biasing_worker_runtime、biasing_step_weight、random_command_semantics（含98检查C++组件）、output_provenance/backend/GUI、merge_histograms、report_evidence。专项与最终平台验收分开记录，阶段是否关闭以ROADMAP和正式证据为准。

### R30：已有run后的内核重初始化

Geant4 MT Initialize执行内部BeamOn(0)后将master runIDCounter重置0。旧main在每个偏置beamOn之前重复Initialize，导致master run0/run0而worker run0/run1，覆盖摘要及master统计。自动初始化仅允许首次（!kernelInitialized），普通连续beamOn保留。已有run后batch/csh明确拒绝/run/initialize、/run/reinitializeGeometry、/run/physicsModified、/run/geometryModified，建议新进程；首run前物理初始化仍允许。csh错误类型run_lifecycle，不伪造Geant4返回码。新回归run_reinitialization，保留多run真正ID/worker/统计一致性验证，不以总事件数相等替代。

### R31/R32：验收调度假设与原生UI旁路

R31是测试缺陷：不同history工作量不能保证分配到不同worker。ROOT-only极值回归须保留失败/有限性首因/禁止统计发布判据，允许worker先检出或master合并时检出并记录实际分支；不能每次冒称master分支已覆盖。历史修前成功反例与修后master实测保留，不用调度hook改变产品行为。

R32关闭绕过R26/R30的非csh默认UI入口。最终context为interactive且非dry-run时，若未显式选择csh，在现有biasing预检之后、Initialize和macro执行之前失败；CLI裸--ui与INI interactive=true均覆盖。原G4UIExecutive分支删除并保留防御拒绝，不提供unsafe开关，不静默改默认。迁移为--ui --ui-session csh；Python桌面GUI正常运行/几何预览不依赖原生UI。dry-run和只读配置检查不启动会话。测试覆盖CLI/INI/带合法macro均零run且sentinel未执行，以及dry-run正例。完整任意原生Qt命令审计不被宣称完成。


## 2026-10-29 完整 2C 工作区候选补充（in_progress）

完整消费者、三阶段与模块策略的当前说明见 [EffectiveConfig](EffectiveConfig.md)。这是对同日“配置阶段 Manager 子集”和 source 待实现描述的后续实现补充，不追改历史证据、不扩大旧子集验收结论。11 类消费者适配已落盘，requested/resolved、registry revision、consumer configuration_generation 与内核/worker applied 收据必须分别解释；收据不能增加配置 revision，同值新来源不得继承旧代次收据，未知原生命令须保持 unknown。

configure 为冻结的配置阶段快照，run_begin/finalization 按实际 run/thread 产生；不得在无 run/失败路径补造运行事实。模块 scoring/biasing/field/trajectories 的 off/auto/on 不改变缺失 mode 的旧语义，不创造规则或物理参数，基础模块不能关闭。输入哈希须来自实际解析字节，文件关闭成功后才登记。GUI 集合/差异是只读审查，DeepSeek 参与设计不等于验收。完整阶段仍进行中，最终 Windows/Linux/GUI 与证据门禁待主任务裁决，Q1 拒绝边界继续有效。

完整 2C 本轮文档/runner 审查补充（随候选修正更新）：此前 off 静默覆盖活跃请求的缺口已由 `ApplyModuleModes()` 严格冲突判定和 `test_effective_modules.py` 矩阵修正，仍待真实后端矩阵验收。缺失 mode 保留 legacy 默认，显式 auto 只据明确活跃请求及依赖启用；mesh-only 不启独立 SD gate，phase_space 与 trajectories 不受 SD scoring 抑制，trajectory 另由自身模块策略处理。auto/on 与显式 false 旧开关冲突拒绝，空 biasing hook/wrapper 不代替规则；不将缺失 mode 记录成用户请求 auto。静态 CI 的 Windows job 已通过 vswhere/VsDevCmd 显式初始化 MSVC x64 并设置 CXX=cl，独立 C++17 static 前提仍须满足，不放宽 fail-on-skip；workflow 静态校验不是云端运行通过证据。


### 完整 2C 新反例：偏置 macro 非法数值的受控失败链（待修后验收）

本轮 build03 真实负例见 `out/verification/2c-bias-negative/run.log`：`BiasingMessenger::SetNewValue` 对 `proton hIoni -1` 报 `AIHLBiasingMessenger002`，随后 `Fatal Exception` / `Aborting execution`，进程直接中止而未产生受控失败摘要。此病例未被旧 Q1 冻结测试范围覆盖；保留原 Q1 已验证范围，不追改或撤销其冻结证据，但此新反例必须在完整 2C 中闭合。

修复契约：非法 biasing macro 必须进入受控失败路径，停止后续输入，输出 `status=failed`、非零退出和可取得的 macro 文件/行/命令位置；交互 csh 保留其可取得的失败来源，不能虚构 batch 行号。失败命令不得发布 EffectiveConfig 值、来源、configuration_generation 或 revision。BiasingMessenger 的 ParseDouble 必须拒绝 NaN/Inf、数值溢出及非有限结果；非法 factor 等 Manager 校验错误不得通过 FatalException 直接 abort 来绕过摘要和最终化。

Geant4 `ApplyCommand()` 返回 0 不足以确认命令成功；沿用材料命令模式，由 BiasingManager 的受控内部失败计数/错误记录捕获 Messenger 失败，main 的 batch/csh 链在命令后检查，先拒绝再停止后续命令，不登记成功来源。内部失败与实际 Geant4 非零返回须保持各自证据，不能伪造返回码。当前为修前证明与修复约束，修后真实 macro/csh、非有限数值、未执行 sentinel、失败摘要和不发布 revision 的验收结果由主任务统一补录；本条不宣称已通过。

### 2026-10-29 完整 2C 首轮全量回归衔接

冻结 fee88d2 的 Windows 全量为113 PASS/5 FAIL/0 SKIP（118项）；真实 Linux run40884097773 的11.3.2/11.4.3均未过backend，integration未执行；M0 run40884097335两平台static/gui通过。原始报告保留，不能用局部绿覆盖失败。以下为修复契约，最终验收仍看STATUS/ROADMAP：

- RunSummary为已登记的configure/run_begin/thread-final/process-final快照标注g4usim_effective_config_v1。dry-run仅四种本轮产物（摘要、metadata、configure/finalization），两个快照均execution_performed=false且run_id=null，不产生run_begin；真实run快照的manifest/schema和JSON协议相符。
- SD Initialize/ProcessHits及CSV数据行是否被调用取决于实际worker分配。保留sd_*_t0、event_row_t0、summary_close_t0用于单worker；对应*_any_worker仅在测试环境变量显式启用后，由实际非master线程到达所选回调时atomic-once竞争。SD仍限run1，event row不在表头注入，summary close不在其他文件注入。不改变生产调度、不加barrier/sleep、不用更多事件冒称确定触发。
- test_sd_context_failure/test_live_progress/test_run_summary/test_interactive_commands核对真实失败worker范围、stage、非零退出、失败摘要；保留首轮结果、后续停止、失败文件不登记、失败轮无合并统计等原保证。这是受控回调异常，不代表真实磁盘满或内存耗尽验收。
- ROOT稀疏几何只保证单个worker有贡献，不保证它处理的历史少于总数。test_q1_results_backend保留N=32与CSV逐值/误差一致，报告本轮是否观察到稀疏分母缺口；确定性数值反例由test_q1_postprocessing提供。原ROOT副本缺metadata必须拒绝推断N，即使存在events ntuple也不可绕过。
- 同字节NIEL读取的缺文件错误必须保留[scoring.displacement]/粒子、INI路径及准确行号、解析后的缺文件绝对路径并在事件前拒绝。受审计csh成功命令现在具有真实interactive来源；旧摘要兼容枚举macro，不伪造macro文件或行号，完整快照必须明确interactive及原命令。不得再测试其必为runtime_unattributed。
### 2026-10-29 完整 2C 关闭补记

前述完整候选和偏置失败契约已在f4770b0完成真实验收：Windows118/118、40628个v3入口、干净工作区，Linux11.3.2/11.4.3实际run40892017436各118，M0 run40892017433两平台各47；12份CI门禁与归档后的14份门禁均通过。非法偏置命令六类负例及正常路径共302入口，普通非零失败、来源位置/未发布revision/未执行后续命令均验证；空em来源和连续不同mutation请求保留亦闭合。最终可见Windows窗口2run/2worker/8事件/14快照、10类程序化检查和6图通过。

同生产Q1代码仅加同五份测试overlay重新测量105项/36269入口，当前候选通过原逐例/总数门禁；其余100项与历史入口数完全一致，五项变化有逐项对照。旧83770及原失败报告不改写，不能把新固定不变量入口数与旧逐记录重复入口数当作覆盖质量排名。完整来源、未知边界、复制清单与集成收据见docs/verification/2c-full-20261029/README.md；E6、Q2、完整编辑/安装器仍各自独立。历史条目中的待验收字样描述当时状态，当前阶段事实以此报告与ROADMAP为准。

## 2026-10-30 E6 兼容与迁移候选

实施契约见 `docs/collab/inbox/20261029-2355-astra-e6-execution.md`，使用说明见 `docs/配置兼容与迁移.md`；本条记录候选行为，阶段完成仍须最终证据。schema 增加 field/biasing 五类 section 与主版本标记，共394项，生成文件禁手改。场/偏置专用解析、dormant短路、process大小写、运行绑定与模块三态不变；未知命令或表格文件仍不在通用schema中。

主 INI `[general]/schema_version` 缺失为legacy1，显式仅接受`1`，future/非法词法在候选reader发布前拒绝；重复声明仍后值生效并告警。ConfigManager 的 `LoadGeometryConfigBytes` 专用于独立几何，不能调用主版本校验；几何的版本仍为 `[global]/version`。有效配置的 `/configuration/main_ini_schema_version` 只记录格式接受和来源，不提供内核应用收据。GUI 标量与迁移scanner使用ASCII空白、INI按LF分行，不能用Python Unicode strip/splitlines误收后端会拒绝的版本/数值。

迁移计划只读源并带实际字节SHA，publish复核源身份后以同目录临时文件flush/fsync及exclusive hard link发布，不覆盖已有目标/链接；失败不改源。发布是提交点，之后清理临时链接失败返回warning，不能将已成功目标报告为失败或删除目标。主INI副本限定同目录以保留相对资源；几何相对STL/GDML/copies路径确定性转成原资源绝对路径；K1资源包仍未实现。项目兼容1–6/缺省及列明的旧preview/别名，未知/冲突/重复JSON/nonfinite拒绝；正常保存保持原子替换，Save As成功后才切project_file。迁移不自动启source-copy，不解除原编辑blocker，格式检查不等于后端/物理验证。

诊断C++排序和相等共用完整字段身份，GUI源问题以位置/类别/严重度识别，避免重复校验/重载累加。专项为`test_main_config_version`（含component）、`test_main_ini_migration`、`test_field_biasing_schema`、`test_config_migration`、`test_config_migration_backend`、`test_geometry_diagnostic_identity`、`smoke_config_migration_ui`；旧schema/几何/项目/来源及平台全量继续保留。独立审查发现的类型静默转换和preview类型等值问题已修复并由不同写者用原始5例、14组合法旧版本复核，见`docs/collab/reviews/20261030-e6-migration-cross-review.md`；完整冻结验收仍待后续证据，不因本文写入而视为完成。

### 2026-10-30 E6 首轮回归修复边界

首轮冻结cb837e6的Windows全量126pass/1fail/0skip，41462个v3入口；最近项目缺失文件触发critical模态，本机经核验只停止该用例进程后完成报告，退出4294967295，不能写成本机timeout。真实Linux40911355023/M040911355092四job均GUI同例600秒timeout，static各19/19、GUI各32/33，Linux后端/集成未执行。原报告/日志和官方归档摘要保留，不覆盖或声称通过。

修复候选保持Open critical、Recent/Snapshot warning及原标题；文件导入在发布对象/路径/页面/运行包状态前，读取实际SpinBox上下界检查真实投影字段，越界明确拒绝，不让Qt静默限幅或OverflowError后留下半更新对象。未投影的scoringSettings.trajectory_events不单独套上限；GUI上限不改变INI/CLI范围。向导先对候选副本预检，以免新增guard在原位应用后拒绝。空combo清除当前选择，未知选项仍保留，不新增枚举白名单；已有物理量文本校验继续负责无效单位/数值。

独立复核还发现此前已存在的显式editor空锚点整对象回退：现在只在editor对象缺失时from_settings；显式空particle/reference或bins<=0不丢其他标量。原始JSON的sourceEditor.position_mode/type同时给出且不同则拒绝，只有一个时复制原值补另一个；程序内历史SourceEditableModel(position_mode='plane')构造仍可保存，project_to_dict仅在导出副本按既有mode权威语义对齐别名，不修改caller。保证针对已覆盖的解析/兼容/GUI投影错误，不宣称任意IO/Qt异常全部可回滚。不同写者复核与新的完整冻结证据后续单独登记。

### 2026-10-30 E6 真实运行包恢复与复制候选

真实writer快照包含runPackage、材料/几何摘要等专用envelope，不能直接用普通项目loader或全局丢弃unknown字段。core/project_snapshot专用读取严格校验已知结构、版本、类型、标准同包layout与资源；恢复包内当前材料/几何及快照编辑参数。材料摘要只有组分计数，不重建草稿；清config/macro/output进入generated待生成，旧success/运行期EffectiveConfig/手改main-macro不恢复。无envelope的legacy普通项目分支保留；一旦出现envelope键，缺项不能降级。旧duplicate的材料/几何路径仅接受同旧包标准后缀成对遗留值，并完全不读取旧位置。当前文件SHA不是历史运行身份。

标准duplicate修复材料file、几何config和output dir三个主INI路径及完整包路径，只支持明确定义的标准生成资源集合/宏，外部依赖或歧义拒绝；日志/输出不复制。write/JSON失败不吞掉返回成功；已写出但GUI无法载入时须明确副本路径与未运行状态。新main writer显式格式1，旧缺失仍兼容。

复制并运行的CLI线程/seed/name必须读取副本当前main，而非当前项目或陈旧snapshot。read_generated_run_settings只读这三字段，严格ASCII整数；seed缺省None、显式0保留。前端在候选副本对齐flat/runSettings并投影预检后才发布；保留用户已选择的backend。runName两处GUI trim仅去ASCII空白，尾NBSP等Unicode字符不得被额外去掉。无一般INI反向导入或物理验证承诺。

不同写者29导入载荷/42版本alias、88控件边界、13snapshot路径、duplicate核心与最后8组CLI状态原反例复核均已通过；原失败证据保留。新增正式用例包含project_snapshot_compat、duplicate_generated_package_model/backend、gui_project_import_projection、gui_project_snapshot_restore、gui_duplicate_history_cli。最终清单133项，下一步新冻结全量/真实CI，实窗仍等待解锁，不能把此条当作阶段关闭。

### 2026-10-30 E6 第二轮平台失败与 Qt 空数据读取

冻结 `5bf479d` Windows全量133/133、42786个v3入口、2C基线40628门禁通过；Linux真实run40926120374两版本和M0 run40926120368的Ubuntu均在gui_project_import_projection的393个断言后以Python `none_dealloc`、exit -6失败。M0 Windows通过；实际只产生8/12份报告，Linux backend/integration未执行。原始报告与日志保留，不能用打印ok或断言数改称成功。

原有WSL Python3.11.18/PySide6-shiboken6 6.12.0复现：没有MainWindow的QComboBox在缺失UserRole时反复currentData/itemData，使None引用计数随调用下降，正常解释器收尾可崩溃；有字符串userdata/currentText对照稳定。PlotPanel.current_dataset与ScanPage.current_metric默认无数据状态的1000次实际调用各下降999，但该有限调用实验正常退出，因此不能夸大为单击必崩。历史QObject析构-11另有旧证据，不能用旧栈替代本次原因。

窄修通过widgets/qt_data.py读取项目使用的标准模型role map，以Python处理缺失键，保留rootModelIndex、modelColumn、0/False/空字符串等值；不改变数据、不补造None引用、不强退、不忽略退出码或锁定未经验证的依赖版本。用于已确认的绘图/扫描空数据路径、明确可能为空的初始化/选择入口及测试状态快照；没有将所有字符串选项机械替换。该接口不宣称解决任意自定义模型或嵌套QVariant的所有绑定问题。原导入assert AST保持一致；gui_qt_combo_data登记标准模型语义及空数据重复读取回归，清单增至134项。新冻结的平台和实窗验收仍须单独完成。

### 2026-10-30 E6 自动验收完成，实窗待验

验收代码a779634：Windows134/134、42815个v3入口，2C基线40628逐例/总数门禁通过；真实Linux40931653660两版本各134、M040931654093两平台各58，12份CI严格门禁、4官方ZIP摘要与384日志SHA通过。三轮原件按字节归档；2711文件及13份release门禁经不同写者复核。Linux git_dirty=true的依赖路径与未知完整状态边界保留，不能冒称整个检出clean。见[E6自动验收报告](verification/e6-full-20261030/README.md)及[独立复核](verification/e6-full-20261030/independent/README.md)。实窗因锁屏待解锁，stage_complete=false，未合主线；原始报告不可用后续证据覆盖。

### 2026-10-30 E6 实窗补验与阶段关闭

用户解锁后，在838e2e3文档检出上执行a779634同产品/测试：Windows原生12个状态、20张截图由主审实际查看；迁移取消/新副本/拒绝、当前包snapshot恢复与再生成、六组合法duplicate最终命令及1025拒绝，另有真实Inspect→Run的1轮2线程2/2事件。合成Inspect/截获命令仅验证命令构造，独立真实运行另有正常退出0、GUI success、新摘要和metadata。普通Open/Recent/Snapshot越界及普通Open拒绝包envelope的四个真实模态均拒绝并保持完整状态；Open为critical、Recent/Snapshot为warning。主审原生输入负责取消及切换/关闭，其他步骤为程序化Qt，不冒称真人点击。

独立155项证据检查通过，58原资源/13专项源码/完整双指纹/exe身份不变；135份新证据4749003字节逐一SHA核对，旧2711原件及旧README/manifest保持。首个GUI host因一次性launcher未保留退出码记unknown，仅closed+进程消失；补充GUI host执行会话与app.exec均0，不能追改前者。不同写者检查及实际窗口观察共同支持阶段关闭，不新增Q2物理、J2编辑、K1任意资源导出或全DPI/原生Linux桌面承诺。见[E6最终报告](verification/e6-visible-20261030/README.md)；合入事实以机器状态与集成收据为准。

## 2026-10-30 F1 输出身份与来源候选

来源首提交5373d57；本条记录新接口约束，最终阶段状态由STATUS/ROADMAP及新归档决定，不能用定向回归冒充完整验收。

- InputProvenance以实际读缓冲/流记录连续追加序列、kind/role/method与SHA，不在最终化重读源路径。完整读取但解析拒绝仍是读取事实；unknown为null并写原因。覆盖项目读取器，不承诺Geant4内部数据集和任意原生IO。GDML为实际Xerces依赖，STL多次读取保留各自版本，RNG恢复验证先登记已读完整快照，再尝试语义接受。
- OutputManager共享execution_id和显式scope/run/thread登记。关闭后流式hash；登记文件缺失不可静默删除，锁存artifact_integrity并非零失败。文本摘要单独hash，metadata最后写且唯一self_reference_excluded。继续保留R02的metadata失败首因及failed文本收尾。
- build.git_source_state的clean只比较实际C++构建输入raw blob与HEAD，不是整个工作区clean。assume-unchanged/ignored实际源码必须检查，Git不可用/源码归档是unknown。cmake模块属于源码指纹；HEAD/ref/index变化更新下一构建的commit。
- 消费者新扩展严格类型/重复key/schema/身份与SHA校验，缺损不能降级glob。旧v1仍可读但说明未验证。当前根映射是唯一自动消费位置，不要求源路径仍存在，额外未登记文件不加入本轮身份集合。运行结果与字节身份分开。
- GUI后台SHA及历史扫描通过请求序号、取消事件和Qt回传丢弃过期结果；一次操作可复用同一证据，下一独立动作仍fresh SHA，合并执行前强制fresh。主窗口接受关闭也要取消嵌入页任务，ignore关闭不能使页面失效。大数据解析/Matplotlib绘图不因这项改动自动宣称后台执行。
- auto仅显式请求；scoring.enabled且(hits或event_edep)选择ROOT，其余CSV，省略字段仍CSV，不修改计分开关。requested/resolved及选择原因分别记录；PreInit依赖调整保留原策略来源，初始化后拒绝。54次格式及18次缓冲对照未证明256KiB缓冲稳定收益，候选已撤回。
- 定向回归入口test_build_identity、test_f1_input_provenance、test_f1_input_resources_backend、test_f1_output_identity、test_output_auto、smoke_f1_output_identity、smoke_f1_async_identity；既有run_summary/ROOT/GDML/RNG/后处理全量仍须通过。真实窗口与合成夹具、历史性能与最终冻结版本分别计证。

详细接口：[输出身份与来源](输出身份与来源.md)，决策：[F1格式与缓冲](collab/inbox/20261030-1500-astra-f1-format-decision.md)。

## 2026-10-30 F1 首轮冻结失败与异步图表修复

冻结候选cd0f44a：Windows143项141通过/2失败/0跳过，48450个v3入口；报告out/verification/f1-freeze-windows/20261030-154131-deadf201/report.json。真实Linux run41021459195（11.3.2/11.4.3）和M0 run41021459196（Windows/Ubuntu）每job25static通过，GUI38/39；Linux在GUI失败后未运行backend/integration。4官方ZIP摘要与元数据相符，8原报告/4job日志保留out/verification/f1-ci-final，目录名不表示最终通过。

确定缺陷：开始页set_output_dir后立即show_plot时后台尚未发现数据集，返回false并丢失预设选择；实际等待后3/4示例仍显示错误默认图。修复为OutputPage保存目录/key/request serial意图，完成后在同一验证操作内应用；同根refresh保留意图，新根取消旧请求。EvidenceJob明确QueuedConnection防极快future在submit返回前同步发布；去掉重复refresh。ready与queued未知key均取消重画、清空选择和图并明确报错。测试保留所有原图表断言，等待实际任务完成，增加阻塞A/切B/释放A的迟到隔离、同根刷新及未知key两路径。

环境缺口：本轮未传G4USIM_GEANT4_DATA，定位测试退到symlink构造而遭WinError1314。E6原日志已使用该参数指向真实数据根，原基线12入口；同环境控制本次12入口通过。下一全量显式提供该已有参数，不修改系统权限/数据定位源码，不把失败旧报告追改成绿色。

本条描述已审修复及首轮事实，不能作为新冻结/阶段完成结论。后续新提交、新完整Windows报告与真实CI仍须独立验收。

## 2026-10-30 F1 第二轮 GDML 异常与资源收尾

冻结3d1faf1：Windows全量143通过/0失败/0跳过，48511个v3入口，E6同probe逐例/总数门禁通过；M0实际run41024949832两OS通过。Linux run41024949824两Geant4版本static/gui/backend通过，integration的effective_gdml因未捕获Xerces OutOfMemoryException失败。旧报告及原日志不追改；跨平台完整验收仍未成立。

确定缺陷：GdmlInputCapture::Capture在已取得原生句柄后于try外分配FileBuffer，分配失败漏关句柄。独立同harness/原适配器复现opens=4/closes=3；候选将分配移入既有关闭保护后4/4，进一步Xerces读失败为5/5。新故障在宽路径转换完成并释放full path后武装，不再让更早的路径分配消费故障。

测试修复：std::thread经exception_ptr将异常转回join后的调用线程，仅std::bad_alloc与Xerces独立OutOfMemoryException视为预期分配拒绝；catch(...)仅运输或顶层明确返回失败，不当作通过。局部RAII恢复fgFileMgr，正常/异常展开均验证原指针。原31条Check和Python断言保留，增加精确故障及非分配异常传播检查。Windows Xerces3.2独立测试不代表Linux3.3通过；后续新冻结必须实跑双版本CI。

范围与验收见[GDML修复提案](collab/inbox/20261030-1643-astra-f1-gdml-repair.md)。本修复不改解析契约、GUI编辑白名单、输出协议或物理计算，不新增系统内存耗尽/磁盘故障实测承诺。

## 2026-10-30 F1 自动矩阵与不可变归档，实窗待验

最终产品f176d0ed4cea60b7ca5a80ed81017c9404ec1257干净Release构建；Windows正式all143/143、48511个v3入口、0fail/skip/零断言用例，E6同probe逐例和总数门禁通过。实际Linux run41028779177的11.3.2/11.4.3各143项，M0 run41028779326的Windows/Ubuntu各64项全部通过；4官方ZIP摘要、12报告/414次执行及原日志SHA/断言标记核对通过。两个Linux effective_gdml原日志均实见四开四关、故障五开五关、adapter恢复与native capture通过，不只引用CI绿灯。

程序SHA f02d3bdc94121dcf35de05e152773fdec8c87f5c8759e53fd1f95d3f51f43ea8；sourcefp db253b7b1ed5f810789f1322faa75002df311d4aeb04572867dbb130c71d95cc；testfp 57a80e4f5e73a2d07b5b834b6ca91ac482161622ca1d5e1d558cbd37d79b5f35。后续仅文档提交不能冒称已测exe的构建提交。构建输入clean和通用CI git_dirty为不同事实，保留原值。

[自动验收归档](verification/f1-automated-20261030/README.md)按独立审查批准的计划独占发布，2797原件逐字节复制，重新核验严格/E6基线门禁及23个本地链接；两轮失败、54次格式/18次缓冲测量、DeepSeek设计响应、构建收据和独立审查均保留。首轮旧README误称4份joblog已落盘，实际只1份；本轮补收另外3份，新增更正收据，不追改旧README。ZIP/程序/大数据输出保留在清单的本机源位置，归档不等于K1可移植实验包。

最终真实夹具为2线程、2轮各2/2事件、auto实际ROOT，20登记文件身份verified。它尚未完成实窗观察：旧host被其他窗口遮挡，两次激活/恢复失败；17:19只读刷新仍看到遮挡，没有继续输入或把无关窗口截图归档。须用户将验收窗口置前后，正常关闭旧host，再用最终代码host补验及取得正常退出收据。显式状态为visible_acceptance=pending、phase_complete=false、integrated_to_codex=false；不得用合成状态、后台运行或原生UIA树替代实际视觉观察，F1保持进行中。

## 2026-10-30 F1 实窗补验与阶段关闭

产品冻结 f176d0ed4cea60b7ca5a80ed81017c9404ec1257 已通过Windows143/143、48511个v3断言入口及E6逐例/总数门禁；真实Linux run41028779177的11.3.2/11.4.3各143，M0 run41028779326双OS各64，原始日志与官方归档核验通过。来源、格式/异步加载、图表回归和GDML异常收尾分别提交；两轮失败及修复、72次性能测量与撤回缓冲候选均保留。

用户置前后旧host40467正常退出0；最终host85274加载ede037f（相对f176仅文档/证据变化），源码和测试指纹一致。14次原生窗口图像由root直接查看，覆盖构建/输入/产物/折叠JSON、运行失败与字节一致并存、篡改/缺文件/旧格式、历史独立身份和真实auto ROOT。真实CLI夹具2线程、2轮各2/2事件、3次输入读取及20项登记产物重新SHA一致；实窗通过不替代物理验证。

14张原始JPEG与UIA、host身份和退出链由不同写者独立核验。07旧格式图像已观察，但同次UIA滞后，不能拿旧文本证明当前图像；合成历史条目因没有真实退出收据，运行结果保持未证实，身份状态独立。长hash省略/滚动和现有splitter扩宽不算全DPI或J1验收。最终原生Alt+F4，host closed、执行会话exit0、随后无F1窗口；不使用测试控制文件替代关闭。

host原observation_acceptance=pending、真实夹具准备收据pending、build_commit_matches_expected_head=false均原样保留：前两者是采集时程序状态，最后一项反映文档HEAD与产品build确实不同。主审结论和独立核验另行追加；旧自动归档2797原件及38生成核验、旧README/manifest不得追改。F1完整约定范围关闭，详见[最终报告](verification/f1-visible-20261030/README.md)；正常集成事实单独登记，不因本条提前推定已推送。后续F4诊断定位、K1可移植工程与Q2科研验证仍按原依赖推进。

## 2026-10-30 F4 结构化诊断与定位候选

实现范围见[结构化诊断与定位](结构化诊断与定位.md)，阶段状态在ROADMAP。新增纯数据 Diagnostic/SourceLocation/EditorLocation、稳定canonical身份和严格g4usim_diagnostics_v1；生产处记录实际位置，不解析本地化文本。保留ValidationReport三类字符串、顺序、to_text与阻断规则；重复源行/对象虽同文仍分别保留typed身份。参数不可变，身份不依赖调用时cwd，不新增持久项目UUID或schema字段。

来源在真实读取点绑定逻辑文本SHA和快照；不是原始bytes哈希。当前来源变化时仅能以明确historical_source显示合法记录快照，超限/缺身份/行号越界拒绝。GUI定位先验当前模型/草稿/源内容与generation，解析全部目标后再选页/行/滚动/焦点，不写值或dirty；输入修改、重载和换项目使旧报告失效，不因撤回输入而复活。语言/主题不构成业务改变。高级不可编辑字段、任意后端自由文本和派生扫描点均不得假跳当前控件。

覆盖Config既有编辑字段、Project/Run路径检查、向导、扫描及屏蔽场景；跨页setup/project目标需双侧快照守卫。运行包新增validation_diagnostics.json并保留validation_report.txt；生成时校验不证明运行/物理正确。F5撤销与K1/L1执行服务仍是后续范围。专项scripts/test_f4_diagnostics.py、test_f4_producers.py、test_f4_document_diagnostics.py、gui/smoke_tests/smoke_f4_navigation.py和smoke_f4_entrypoints.py；正式矩阵/实窗未完成前不得宣称F4关闭。

F4验收入口追加：smoke_f4_inspect_protocol.py覆盖合成协议及过期回调；smoke_f4_inspect_backend.py覆盖真实后端拒绝原文及无模拟启动；smoke_f4_layout.py覆盖小窗口滚动和字段可达。合成协议测试不得冒充真实Geant4输出。

F4首轮5d6f008实窗反例：重名几何的size诊断虽选中[2,6]，外层滚动却显示空白。修复必须在切页/布局后按visualItemRect映射目标单元格到各滚动视口；不能用整张QTableWidget中心或isVisible()冒充单元格可见。smoke_f4_layout追加实际裁剪区域交集、远端行/布尔/详情及不改值断言。原生失败记录、正常host退出与未完成Windows轮分别保存，不得把过程exit0或部分测试通过算阶段验收。

2026-10-30 F4依赖候选：Linux CPython3.11 / PySide6与shiboken6 6.12.0的缺失属性及普通void返回均可耗减None引用，原CI存在断言完成后none_dealloc/-6；不能以退出前成功文字、强制退出或单一属性绕行掩盖。隔离Linux6.11.1与6.11.3各通过binding8/Inspect45/真实运行103/layout257且自然退出0，暂约束PySide6>=6.11.1,<6.12，配对组件由官方依赖元数据锁定。新增smoke_qt_binding_lifetime登记实际Python/PySide/shiboken/Qt版本与引用变化；Python3.12的immortal None不能替代3.11验证。Linux workflow移除全局conda LD_LIBRARY_PATH以免混载Qt，保留数据环境和PySide插件路径；后端用自身CMake RPATH，新CI仍须覆盖两Geant4版本及辅助程序。当前仅候选，不提前关闭阶段。

## 2026-10-30 F4 阶段关闭记录（已完成）

产品 `7d718d038a00d89995ea773b4772764116b620c3`；Windows 152/152、49913 个 v3 入口与 F1 原始143/48511同代基线门禁；Linux11.3.2 为 152 项、11.4.3 为 152 项（run 41056994075），M0 Windows 为 72 项、Ubuntu 为 72 项（run 41056993987）。CI实际提交 `a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`，与产品的关系见[提交身份映射](verification/f4-final-20261030/identity/identity-map.json)。Windows原生 13 态、19 次实际观察与进程退出 0；[最终证据](verification/f4-final-20261030/README.md)，[独立审查](collab/reviews/20261030-astra-f4-close-review.md)。

实窗GUI提交 `7d718d038a00d89995ea773b4772764116b620c3`，与产品身份关系：实窗GUI与Windows后端均为产品7d718d0，121份GUI源文件清单经独立复核。13个合成诊断状态及主题、语言切换共19次原生观察，独立启动器确认自然退出0；合成导航、真实后端Inspect拒绝与图像观察分别计证，未据此新增物理验证结论。。CI身份关系：CI为产品的直接单父提交子节点，仅在Linux工作流增加六行系统运行库安装；完整11340项Git路径、模式与对象核验确认其他项相同，来源及测试指纹一致。Windows与实窗证据保留7d718d0原身份，CI十二份报告保留a9ad09d原身份；映射证明代码与测试对应关系，不证明跨平台二进制字节相同。。依赖结论：GUI依赖统一经gui/requirements.txt限定PySide6>=6.11.1,<6.12；本轮Windows实窗使用6.11.1。Linux CI采用Python3.11并安装libegl1、libgl1、libxkbcommon0、libdbus-1-3、libfontconfig1，保留数据集环境及PySide6自身QT_PLUGIN_PATH，后端使用本轮已验CI构建的CMake RPATH，Python/GUI不全局注入conda LD_LIBRARY_PATH。旧WSL命令保留历史，不作为当前启动方案。。集成事实：此关闭记录形成时，codex分支尚待正常快进；随后同日回信记录真实集成结果。。

既有编辑器及Project/Run、向导、扫描、屏蔽场景共用结构化诊断；按实际对象/字段/快照定位，表格按目标单元格滚动，旧报告失效，来源只读，原文本和阻断规则兼容。无编辑控件或可靠来源时明确拒绝。这不扩张高级GUI字段或科研物理验证；F5为下一完整阶段，仍待启动，K1/L1/Q2按原依赖推进。

5d6f008几何定位空白反例与Windows中断轮（92 PASS/1 FAIL、无完整report）、旧CI失败/未执行profile，以及096f4b3原生host异常退出均保留历史原件，不计最终通过。QA host的Close事件对象树遍历缺陷只在out辅助程序修正；第三轮7d718d0的Linux CI因缺少libEGL.so.1失败，仅有6份实际报告，后续6个Linux profile未执行；其旧报告与失败日志仍属历史，不能用新CI回填或冒充当轮通过。PID40456、2026-10-30 19:51:06的0xc0000409与缺失退出收据不得改写。合成夹具、离屏交互、真实后端Inspect拒绝与原生图像观察分别计证；本阶段不声称新增模拟或物理基准。

正常原生host SHA256 `aa59397f4711c17f7edcc9a39d927c9c4197e124d98ccafb58b8d1d886c11d6c`。保持Diagnostic/SourceLocation/EditorLocation及JSON v1语义；不新增项目持久UUID。实际来源先核验逻辑文本身份，历史快照明确标注；表格单元格须与所有祖先视口实际裁剪相交。导航不改值/dirty，换项目/重载/任何草稿修改后旧报告不得复活。

## 2026-10-30 F5 候选：配置事务与恢复契约

F5统一主Project/Configuration、材料/组分、几何/层/布尔、Source/Physics/Scoring和运行参数的完整编辑快照；向导成功应用一个事务。独立scan/scenario和未应用向导草稿不保存，需界面说明。无新物理字段；当前验收状态只看STATUS/ROADMAP。

`core/edit_snapshot.py`持久快照携带raw draft、源文本/绝对读取锚点、读取成败及材料/几何模型；瞬态parser对象不序列化。`edit_transactions.py`默认100命令/32MiB编码载荷预算，保存点按语义fingerprint、revision单调，撤销不能使旧F4诊断或运行成功复活。保存/结构/失焦切断输入合并；撤销后新编辑清redo。失败保持旧历史；UI投影和回滚双失败须冻结，不能把坏投影保存或发布为恢复内容。

项目JSON v7新增materialEditor/editingState，已知1–6继续兼容，缺失旧快照与显式空内容有别。`core/edit_sources.py`从捕获原文重建不可编辑源限制，不能信任可清空的诊断缓存；失败读不能伪装为空文本成功。不重读当前磁盘。普通Open恢复完整草稿；E6 run-package adapter仍解析CURRENT包内材料/几何，丢弃历史未输出草稿，不恢复旧执行配置和成功事实。

普通Open的纯投影校验和完整快照容量必须先于界面发布及旧项目保存/丢弃询问；后期历史reset拒绝须回滚，reset已发布后的状态通知失败则保持新view/history/path并提示。`EditSession`只缓存私有深拷贝当前快照的指纹；构造、replace、undo、redo、reset成功时同步维护，任何失败不得发布缓存；外部候选仍完整校验/来源重建，显式`mark_saved(snapshot)`仍独立计算。原F1关闭时延阈值保留，不得通过跳过raw draft捕获或来源校验换取通过。

`workspace_recovery.py`每会话OS lease防活跃窗口接管、严格版本/摘要/路径和原子发布，控制器拒绝迟到revision/同revision换payload/已退役revision复活。恢复为未命名dirty副本，不覆盖原项目/INI/macro，不触发运行。自动保存不等于普通保存，失败保持原有效副本。`ProjectFileReceipt`来自实际读取或本次写入的原始字节；os.replace为保存提交点，发布后不清理已经转移的临时名称。

专项：test_f5_transactions/source_snapshots/project_receipts/recovery；smoke_f5_editor_history/recovery_ui/recovery_process；test_f5_transactions_backend（Undo/Redo生成后真实Geant4的源能量和几何读回，非物理正确性基准）。旧GUI用专用test MainWindow隔离恢复/history并明确Discard，产品不按offscreen绕过恢复或未保存保护。原失败实验/报告保留out，再归档；完整验收尚未完成。


## 2026-10-31 F5 冻结验收与恢复契约

2026-10-31 F5：**已完成**。冻结验收5c1eec5；Windows160/160、50898个v3入口，Linux11.3.2/11.4.3各160、M0两平台各79，原F4逐例与总量门禁通过。原生22份观察/28截图/真实退出0保持5d身份，经明确映射关联新冻结；不新增物理验证结论。[最终证据](verification/f5-final-20261031/README.md)。下方带日期的旧状态保留其历史范围。

保留前述F5候选契约。新冻结仅改DDD测试/runner证据与实施提案，产品不变；5d的DDD44<46原失败门禁、r2强等N假设撤回及原生失败尝试均保存。新DDD按固定不变量检查全部行，保留原物理判据/容差；可见worker去重N<=master N，空表头N未知，不能由稀疏行推导完整N。runner新增独立证据目录和原样Git状态，不放宽v3原始日志/基线门禁。后续模型分工遵循[项目规则](collab/MODEL-POLICY.md)。

## 2026-10-31 K1 候选：共享实验服务、分级证据与配置包

当前为实施契约，尚未宣布整阶段验收。服务文档见[可信实验工作流](可信实验工作流.md)，范围见[K1实施契约](collab/inbox/20261031-k1-execution.md)。

`core/experiment_workflow.py` 是 GUI/CLI 共用动作入口；`EditSession`/`WorkspaceSnapshot` 继续唯一持有配置与撤销历史，已有 `G4USimRunner` 继续唯一控制模拟进程。文件操作在 EvidenceJob 私有快照上执行，Qt对象与事务发布留在所有者线程。apply先校验候选与未接受原文，拒绝不得改变revision/undo/redo；任何begin后异常都须可终结，忙时不能重复启动。

字段/依赖、初始化/几何、事件完成、物理比较四层独立。inspect只表示Configure/preflight；初始化执行规范化macro的首个beamOn前缀及真实几何检查/mesh收据，不能用文本存在或退出零代替。每次运行使用独立UUID和目录，核对实际摘要、逐轮事件、F1读取序列/字节、执行身份和后端构建；环境仅描述实际目录选择与存在，数据内容哈希未观测。环境查询须使用实际执行cwd，不能按父Python目录解析相对数据路径。

记录绑定配置/资源内容、后端、环境、随机设置、事件及判据。字段修改、Undo、输入文件变化与环境重新观测不一致使旧资格陈旧；历史保留。加载历史不能自动恢复当前资格。显式历史evaluate须重新核对身份/输出，写新比较记录，不改写旧结论。取消和迟到回调不得把失败/陈旧提升为passed；终态信号与落盘状态一致。观察到的资格不是对文件以后不变的保证。

物理比较当前限完整逐事件敏感体总沉积能，明确raw/weighted、MeV、per_event、所选run、参考文件/来源/条件及均值标准误；事件身份按整数去重并核对所选run完整样本。单样本误差未知，不能填零。拒绝外来pass/observed/sigma及不匹配定义。合成CSV、真实模拟、geantino零沉积特例与Q2独立物理验证必须分别表述。

`core/experiment_bundle.py` 独占有限资源语法与重定位；项目v7/F5快照不另建模型。原始来源SHA、捕获原文身份、改写后成员SHA与历史运行身份分别保留。清单成员核验后的JSON构造使用同一批已核验字节。原子发布到新目录，已有目标不覆盖；缺失资源/未知依赖语法/不支持GDML外部依赖明确拒绝，分发未知不等于获许可。包包含配置、引用资源、历史与统一CLI重放入口，不含二进制、完整环境或机器私有设置。历史去敏不得丢失已安全投影的环境/构建事实，也不得重新赋予可信资格。

GUI只适配动作/状态/定位，不建立第二套事务或进程。异步改造后的旧生成入口测试须等待真实终态后检查实际文件，不能删原断言或忽略清理失败。I1只读探测与选择独立验收；环境摘要以易读状态为主，原始协议折叠保留。K2工程导出、L1自然语言provider、J1整体工作区和I2安装均不属于本次完成声明。

K1兼容补充：用户run_name原义保留，不能以UUID覆盖；请求归属由独占目录、actual_output_dir/main_config/actual_macro_file与F1实际路径/SHA/size共同核验。仅generated且显式geometry.source_copy_mode、未知语法错误确实来自该geometry时，允许旧writer的本地副本运行；完整snapshot与声明源字节入身份，标local_source_copy_compatibility、递归闭包未观测，任何额外/未观测F1输入拒绝资格。缺失等错误不走fallback，export始终严格。owner关闭前取消活动进程，再等待服务close()/closed()排空读取；不能预先取消EvidenceJob回调使其伪装已排空。

K1独立external Inspect保留原始输入/cwd与来源行号，不以导出语法预先拦截后端诊断；其身份仅观测声明主配置/macro字节，递归闭包与环境未观测，不能取得初始化/事件/物理或导出资格。真正run/initialization的内部Inspect仍针对隔离执行树。导出历史须保留实际build/random_settings/input coverage/exclusions，unknown不能填造；来源路径可显式去敏但不得丢掉随机事实。Geant4公开版本的完整数字`$Name: geant4-…$`格式是字面版本，不是环境变量引用，仅该字段严格格式可保留。


## 2026-10-31 K1 首轮验收反例：Windows 深目录与异步退出

冻结e5ff800的完整Windows173项165pass/8fail/0skip、54851入口不是验收通过；云端41161341378/41161341423在static停止，原报告/四官方ZIP/二进制与实窗失败保持原字节，入口out/verification/k1-e5ff800。真实存在260 UTF16单元cwd经subprocess/QProcess无法创建进程；独立副本manifest实验在短cwd/268字符输出下1/1事件完成，原无manifest失败。不能通过缩短测试根、取消快照或改写旧报告处理该反例。

新增后端--working-directory为唯一、非空、绝对、存在目录，纯解析后且早于SimulationManager构造/Geant4DataLocator/配置/任何检查模式一次性切换；失败直接非零退出，不在启动祖先写摘要。capabilities.launch.working_directory必须是真布尔true。cmake/WindowsRuntime.cmake生成并嵌入MSVC后端longPathAware与activeCodePage=UTF-8，模块受现有cmake源码指纹约束。现代Windows与长路径系统策略是明确前提，不修改机器策略，不声称任意孙进程或第三方库全部支持。

core/backend_launch.py只给启动计划，environment_discovery的后端查询、ExperimentWorkflow原QProcess检查和G4USimRunner最终启动边界共用，不能新建控制器或改变宿主cwd。按UTF16单元保留尾分隔符/NUL余量，固定绝对程序后选真实路径短祖先；logical cwd与launch cwd分别记录。所有配置/嵌套macro/相对数据路径必须在真实目录解释；F4定位、F1输入/UUID输出严格比较不变。普通短目录不加新flag，旧后端拒绝长目录时明确unsupported，不在祖先去掉flag重试冒充ready。通用SDK工具不带后端flag。

回归须使用最终EXE，核验嵌入manifest、真实capability位、含中文/空格/非BMP的深cwd、短祖先同名错误输入、缺值/重复/相对/不存在/文件cwd、真实初始化与3/3事件、effective配置排他临时发布和F1证据；相对geant4-data.txt的目录发现正反对照不能仅检查Python请求cwd回显。空数据目录仅验证目录发现，不用于transport。新增入口为test_backend_launch、smoke_backend_launch、test_backend_working_directory；正式冻结仍待复审与矩阵。旧GUI同步生成/立即close的测试需等待真实异步完成并排空，不忽略清理异常、不手动删除恢复锁，保持原断言与失败场景。

## 2026-10-31 K1 终态发布所有权与启动失败进度

第二冻结c644bb1的Windows原生取消→强制结束反例：runner已killed，工作流记录cancelled但busy永久不清。_run_error先进入_finish，随后_run_finished向同一EvidenceJob提交verify取消了终态发布回调。修复必须让finishing上下文独占终态任务；普通_work不得抢占。_run_finished先保留已观测exit_code/output_dir/RunResult/launch，再停止重复验证；published发现记录变化时补写到盘，成功后只发一次completed并释放busy。不得为防重复而丢掉晚到实际退出事实，不增加第二个进程或事务控制器。存储失败必须显式failed，不保证失败存储中的磁盘与回调相等。

回归scripts/test_k1_terminal_publication.py使用Qt owner线程、真实EvidenceJob和持久化、受控信号时序；覆盖error/finished顺序、取消、重复信号、迟到编辑/取消、落盘失败、终态期间多余工作与后续动作可用。它不代表真实Geant4取消；必须另做原生取消/强制结束/恢复操作及正常关闭。失败host强制清理只能记清理，不能计作关闭通过。

backend_launch在创建QProcess前拒绝请求时，runner仍须冻结progress并发failed状态，不能制造finished信号或覆盖旧run_status。规范化可执行文件/临时目录后的路径比较应使用独立规范化的期望，保留原requestedCommand与实际command区别；Linux符号链接和Windows8.3别名不是不同文件。现有启动/进度断言不得删减。

## 2026-10-31 K1 历史显示范围

窗口只在既有runner实际Starting信号时，以服务公共记录中唯一pending运行/初始化的record_id/run_id/revision绑定显示。缺失/歧义保守显示未验证历史，标签、路径、telemetry run索引和事件数不是身份。显示范围以公共state/history/revision/qualification/busy投影；F1及终态持久化尚未完成不得提前显示当前通过。修改/Undo/Redo/恢复/外部字节变化后，顶栏、结果和进度明确标为历史，并保留原日志、结果和计数。

RunPage保留的显示快照不进入EditSession、不修改RunResult/历史记录/验证资格；不恢复F5内部Not run yet与空进度哨兵。新进程实际启动才替换显示绑定，语言刷新重画范围文字。smoke_k1_history_scope默认components不启动后端；integration显式--mode backend，证据目录由统一runner注入或显式给出。合成公共state只证明投影规则，真实3/3只证明所用输入完成，均不替代原生可读性或物理准确性验收。

## 2026-10-31 K1 配置包搬移与临时目录别名

第三冻结11c92d3的真实Qt导出包搬移后，模型路径已重定位，但F5路径草稿仍为相对路径，回投覆盖控件后，下一动作collect把模型写回相对路径，存在的材料/几何被误报缺失。`experiment_bundle._snapshot_paths`加载时同步四个与原规范资源相同的路径草稿，保留首尾空白；不同、空白、非法草稿继续保留并阻断动作。不能清空全部raw drafts、另建事务、依赖旧项目文件目录，或以load_bundle单独成功代替真实MainWindow导入/收集/运行。

Windows writer收据使用canonical长路径，staging可由8.3短别名创建；清理writer中间文件后，字面包含判断错误地将其当成外部资源重读。归属比较须先沿用`_no_links`检查，再对两侧resolve；原外部资源SHA复核和拒绝边界不变。单纯resolve候选引入的边界回归已有独立部分证据，补回检查后的专项独审仍因上游自动安全审查拒绝而未完成，不能称该专项已关闭。普通别名/搬移功能测试、独立安全边界复审及最终矩阵分别计证。

第三Windows本机179/179及Linux双179通过，不覆盖M0 Windows五项失败和上述实窗反例。原报告、日志、失败候选和独审中断收据保持；后续冻结重新验收。旧异步smoke须先确认真实生成成功和文件存在，再读文件；finally通过已有close_window排空，不忽略清理失败。CLI的两个late-pass夹具不得同时排队竞争的假cancelled终态；仍断言取消请求、中断原因和迟到passed记录，产品取消语义不变。

## 2026-10-31 K1 取消原因与输入变化分离

第四冻结8213ced的普通独立实窗审查发现：取消后的后台返回记录为cancelled，但reason错误使用experiment.inputs_changed，即使没有输入修改。ExperimentWorkflow._work.delivered必须先按已有cancelled标志发布experiment.cancelled；只有未取消且_current不成立才发布stale/experiment.inputs_changed。不新增状态所有者，不改变取消优先级或记录结构，不修改既有历史证据。

test_k1_terminal_publication新增真实EvidenceJob与线程屏障反例：取消时revision和snapshot均不变；另一个分支通过实际EditSession.replace改变输入。两者都不能执行成功accept回调，须一次completed、磁盘与回调一致、后续动作可用，且组件不得伪造模拟结果。旧代码在取消原因断言失败，新候选11组通过。第四实窗取消案例后端实际完成1000000/1000000，服务仍保留cancelled/stopped；这只证明取消请求不被迟到成功覆盖，不能说成事件中途停止。实际完成数和服务取消状态分别记证。

## 2026-10-31 K1 命令预览目录与进行中状态

第四冻结最终普通前端独审发现两项显示缺陷：完成记录的command来自隔离实验，但格式化器无条件附加编辑项目workspaceRoot；服务真实pending状态未列入面板STATUS_TEXT而被显示为未观测。第五仍保留这两个反例，不能以第五取消原因专项通过覆盖它们。旧cwd反例重放第四原生已完成record880d4e7eb8e0481da3cf0c2d380bafbc与保存项目；旧pending反例调用真实ExperimentWorkflow._state producer，均在目标断言失败。

RunMixin._format_command_preview增加仅供显示的显式cwd参数，未传时原预览不变。成功且非陈旧的Generate/Run完成绑定，在launch的program与arguments合法时优先使用实际argv，否则保留record.command兼容显示，不能将其称为实际启动。逻辑目录取launch.working_directory或execution_bundle.path，缺失为Unknown；launch_working_directory不同则单列。尚无启动收据的Generate目录仅为计划输入树。不得回写编辑cwd或改变F5快照、动作记录、历史资格和进程所有权。ExperimentPanel补pending→In progress及集中中文进行中；未知状态保留Unobserved，四层不得由某层进行中/通过推断其他层事实。

首次UI候选仅在有generated package的分支投影，独审复现external完成记录没有package时早返回，仍显示旧目录。命令投影必须独立于generated配置路径回绑，让无package但有command/execution_bundle/launch的真实external记录同样展示。此为同一预览契约的修正；保留第一候选及独审失败证据，并增加无package完成记录反例，不能只从generated记录复制夹具。

smoke_k1_workflow保留旧39个assert站点，新增前置预览完整相等、真实生成完成目录、direct/restore受控launch收据、argv与两类目录、未知事实、中英文和F5不变检查；受控显示收据不声称启动模拟。smoke_k1_panel保留旧67站点，使用真实producer分别给出新运行pending与后台freshness pending，固定断言In progress/进行中而非从消费者字典计算期望；保持payload、历史事实与未知回退。正式冻结矩阵和实际窗口观察另行计证。

## 2026-10-31 K1 资源路径 P1 与阶段验收关闭

用户报告官方解除通知后恢复独审；原 cyber_policy 记录不改写。产品 `experiment_bundle.py` 的 5c1dff03 原字节经独立代码与真实 NTFS 反例审查通过：收据捕获后、最终复核前的链接必须在 resolve 比较前被拒绝，失败不发布并清理暂存；普通内容 SHA 复核、真实 8.3 与离线搬移正例保持。该专项不保证任意并发目录替换。

`5644e1e` 仅在 `scripts/test_k1_staging_alias.py` 新增精确晚变化回归；原 17 个 assert AST 保留。Windows junction/Linux symlink 使用独占临时夹具，旧 r2 在同一新测试的拒绝断言处失败；当前 clean 正式单例 Windows36/Linux33 入口及严格证据门禁通过。首次 WSL /mnt/c 的 renameat2 EINVAL 原失败保留，Linux 验收为本地文件系统，不把该挂载限制说成已修。

P1 与正式防回归 P2 均获独立关闭结论。350 产品字节与第七冻结2914b39一致，只有专项测试追加；原730次正式矩阵与原生适用性各自保留旧身份，新单例单列，禁止回填旧报告或称全矩阵在新指纹下重跑。K1阶段验收通过，I1已独立完成；正常集成事实以[最终证据](verification/k1-final-20261031/README.md)及其后续收据为准。[补充审查与验证](verification/k1-p1-close-20261031/README.md)。

## 2026-11-01 I2/J1 桌面交付实施候选

本条记录实施约束，不关闭阶段。范围和阶段门禁见 docs/collab/inbox/20261031-i2-j1-scope.md；当前工作在 roadmap/I2-J1-desktop。

I2 安装服务（gui/g4usim_gui/core/environment_install.py）只处理已明确选定的新前缀：计划不下载/执行，产物须有实际大小、SHA、完整文件与许可清单；源目录、暂存目录、发布、恢复和卸载保留路径/链接边界。同一前缀的真实 OS 锁覆盖执行、恢复、核验、SDK 探测和卸载，稳定锁文件不因卸载而删除。发布后清理故障保留 published_with_warning；旧事务无原计划只能清理，不能拼造恢复授权。安装收据、I1 发现、K1 仿真成功与物理验证是四种不同事实。

安装界面在发布后追加候选并重新发现，不自动切换项目或运行。自动来源以 candidates=None 保留，additional_candidates 另存；旧探测忙时排队一次新发现，失败收尾亦能继续，关闭中的迟到回调不启动新工作。包版本和 Geant4 声明版本分开显示；SDK 清单明确要求 CMake/C++ 编译器，文件安装不提升为编译通过。SDK 探测仅显式 host 工具允许真实路径解析并记 requested/resolved/hash，安装树链接拒绝不放宽。回归 test_install_plan、test_install_service、smoke_i2_install、smoke_i1_environment。

外层发布目录含 install/catalog.json 和相邻 artifacts；所有组件必须同平台/架构/应用版本/确切 Geant4 版本。移动目录后按当前清单位置解析来源，不保留构建机绝对路径；数据指针是发布时产生的新字节，和原模板 SHA 分别记录。SDK consumer 的编译/链接/API 执行与完整应用源码的编译/capabilities 也分开标 scope，不称为模拟验证。

Windows 冻结失败的已实证原因是 PyInstaller 从宿主 Poppler 路径选择同名 icuuc.dll，缺少 Qt6Core 需要的符号。packaging/windows_freeze.py 使用所选 Python/SystemRoot 子环境并审计真实二进制来源；不是要求用户修改系统 DLL。gui/main.py 的 --self-test 在 app 导入前失败时写新的失败收据并非零退出，不能覆盖旧收据；普通启动仍传播异常。冻结源码前后须一致，dist 内 g4usim-freeze.json 记录源码和实际 payload 字节；复用 GUI/helper 必须在清理前验证来源、平台、3D 档位、内容与目标互不覆盖，复制后复验。自检通过不能替代源码对应关系。回归 test_frozen_startup，真实冻结入口 test_frozen_desktop。

J1 使用原编辑器、3D、结果和日志控件组成原生 Dock；没有第二事务或进程所有者。布局版本、屏幕信息和 Qt 状态只在本机 QSettings，损坏/失联屏幕回退；布局操作不提交草稿。外观覆盖按体积完整路径/材料身份设置，几何身份变化清除，颜色/不透明度不改变物理或验证资格。降级文本视图不提供无效外观控制；AI 面板明确尚未接入。主题 B/K/C 保留明暗与浅色配色的独立偏好。回归 smoke_workspace_layout、smoke_j1_appearance、F4/F5/K1 关联用例；实窗和真实运行另验。

关闭问题的早期 pre-resolve recovery root 方案及“QStandardPaths 初始化顺序”归因明确撤回：该改动把默认 experiment-records 根换成空恢复目录，掩盖历史任务收尾。源码保持原 None 路径语义。真实边界是 close() 返回 False 时仍有既有业务任务，不能直接 DeferredDelete。自检有界等待既有 owner 完成关闭后才析构；超时写失败并保留存活对象与状态目录。永久回归用真实历史任务屏障分别覆盖默认 None 和显式目录，验证拒绝关闭时不删除，释放任务后正常析构。旧崩溃日志和错误候选保留，不追改为通过。

I2 新增 Windows 11.4 实际矩阵暴露两类既有测试前提（不是将旧失败改成通过）。test_run_summary 的两组8事件/2worker检验不能假定每个worker一定有hits文件；新observer逐次核对全部事件、worker归属、真实primary粒子/能量/位置及跨run状态，仅观测覆盖不足才有界独立重试，语义错误立即失败，最多6次仍未实际见到同次每轮双worker则失败。所有attempt原始输出与源/EXE身份保存；新增静态反例 test_run_summary_mt_observation，原16/24事件、容差和两个worker实际参与要求保留。

官方 Windows 11.4.3 SDK 的真实能力是 GDML OFF。geometry_a5、fields_a7、gdml_bias_identity、gdml_touchable_identity 据实际 --capabilities 选择：ON 保留全部原几何、身份、共享场和容差检查；OFF 执行真实输入/导出拒绝、禁止模拟产物，并明确记录尚未进入run或摘要未产生。OFF 不是跳过后冒绿，更不是 GDML 验证；与 Windows 11.3/Linux 的 ON 证据及断言量分开，不拿较少的拒绝分支冒充功能覆盖。

首轮候选 ba81615 的真实 Actions 失败保留：Windows checkout 因历史验收长路径失败，三个 Windows job 必须在检出前启用 runner 内 Git longpaths；Linux static 发现仅本机存在的审查链接，现归档原字节及 SHA 后修链接。平台路径门禁只豁免明确登记的 fixture 顶层常量单字符串声明，文件/名称/原值/用途注释均须精确匹配；声明外运行路径和注释仍检查，不增加整文件免检。回归 test_platform_path_fixture_policy。Linux frozen desktop 自检通过不代替随后失败的 xcb renderer；实际冻结日志列出的五个缺库须补齐并保留 ldd 诊断。Linux SDK 的首轮失败是不存在的 /usr/bin/cmake，commands 为空，不能称编译失败；工作流须使用实际工具路径，交付入口先登记工具身份，最终 SDK 两种编译探测再分别核验该身份。旧 CI、原 GUI 57/59 和 static 42/43 报告不改写。J1 下原 3D scroll 保留在 dock、页签变为激活入口；config_editors 的结构断言按此适配，原实例、尺寸和按钮判据保留，失败时也先完成正常关闭才销毁。上述修订不关闭阶段。


## 2026-11-01 I2/J1 最终验收与测试环境修订

I2/J1 按 docs/collab/inbox/20261031-i2-j1-scope.md 完成既定实现、审查与验收，最终证据集中在 docs/verification/i2-j1-final-20261101/README.md。产品候选 5fe0a1052e33c96d033375d0920f29b15d432dcc；03d2c483afc0082ad464d2d9a1750fd2e4415a3a 只改两个测试，380项产品文件Git对象逐项一致。Windows后端仍报告实际5fe BuildInfo；冻结包、CI、native分别保留其原提交与原字节，不为文档提交伪改身份。源码相同不意味着跨平台二进制相同。

最终测试提交6310969005183e314b05e0b0362450fa6194bea1进一步只修smoke_i2_install的fixture根和失败诊断。03d的Windows M0 GUI在第166行/54入口失败；同源码完整smoke真实C盘长TEMP59通过、8.3短TEMP54失败，实际/期望均为两个候选，仅拼写不同；规范fixture根后短TEMP59通过。当前tracked文件也59/49、strict0，49个原assert谓词和顺序保留，不加等待、不改产品发现/去重，原CI失败不回填。最终M0按631新提交，未改profile及交付按03d/5fe各自实际身份和文件对应关系验收。

Windows临时目录可能有8.3拼写；test_platform_install_layout先规范化fixture根，再比较产品返回的规范路径。真实长短路径及短TEMP反例/修后入口已独审。旧CI失败日志未打印两个操作数，因此“短路径原因”来自独立实证，不冒充原日志已经记载该字符串。

test_effective_gdml是独立Xerces字节捕获组件，不是应用后端GDML能力测试。G4USIM_GDML_CAPTURE_HELPER只允许显式现有文件，选择一次后失踪须失败，不得静默退到编译；未设置时保留邻近helper和编译回退。日志记实际helper路径/字节SHA及当前源SHA，后者单独不证明二进制编译来源；正式构建收据另绑定5份C++源与Xerces输入。新增选择/身份检查保留全部原捕获断言。Windows11.4官方SDK仍GDML OFF，独立helper仅链接Xerces/Threads，不能升级为后端GDML支持。初次独审发现晚消失回退P2，修后确定性反例已关闭，原审查保留。

Windows原生26图、4次host自然退出0/close_drained=true；布局拖动/缩放/浮动/隐藏、三个预设、本机保存重启/复位、B/K/C/系统主题、中英文、125%/150%DPI以及体积/材料颜色和不透明度覆盖均有实际观察。2M和4M真实事件完成，运行中显示动作保持相应编辑快照，不另建run。150%文字fallback与真实PyVista分别记录；未做物理多屏热插拔。SDK/安装、运行完成、渲染画面及物理验证分开计证，未新增物理或性能基准。

历史ba81615 duplicate_history_cli单次断言失败缺原case/count/state；两次定向、正式矩阵及唯一531秒/三轮/36动作追踪未复现，根因未知，不称已经修复。原恰一次与历史保护断言不放宽，后续再现仍按可靠性缺陷处理。负坐标瞬态符合Qt停放，稳定按钮可达性已另验，但没有成功复现原生拖动反例，不把它写成全面通过。所有旧失败、撤回与证据缺口保留。

归档按原SHA无损选取必要原件并脱源复验，历史失败报告依然strict fail。巨大SDK/数据/冻结payload、完整官方ZIP及大CSV没有全部入Git，位置/大小/SHA与遗漏边界明确登记。不能把归档完整性通过改称所有历史测试通过，也不能把本机原件称为永久公开存储。后续J2/F8承接空白创建、完整编辑路径与文案/可访问性，AI任务能力归L1。


## 2026-11-02 J2/F8 编辑链路实施候选

当前尚未冻结验收。契约与人类说明见 [J2编辑覆盖与F8验收](J2编辑覆盖与F8验收.md)。E7 SolidRegistry只归一既有15实体/7工具，A5 master预计算边界不变；GUI元数据由generate_solid_registry.py生成。新增命名GPS/Surface Sphere/multiple_vertex、显式reference构造器替换及高级场/偏置编辑，必须分别证明解析、拒绝、运行时对象及实际输出，不得把组件通过升级为物理验证。

项目v8完整v7快照迁移仅补枚举字段；原恢复载荷摘要不得重新计算掩盖变更。新增行原文存模型，F5捕获/撤销/恢复与F4按当前实体定位复用原服务；详情选择不得伪造编辑。空白/模板无source/raw路径是独立内存文档，丢失的已导入来源不是同一情况；无源Reload/Revert不得清空文档。运行包只复制活动资源，完整可编辑K1包闭合所有保留资源（包括休眠谱），多相空间文件保持顺序与重复引用。

本次独审发现密度单位/换算溢出、几何参数分隔/placement互斥/单位语义、跨INI→macro EM替换冲突及来源恢复边界；各自保留首错并在最终验收前复核。测试入口包括test_solid_registry、test_j2_sources_physics、test_j2_resource_bundle、smoke_j2_blank/materials/geometry/run_editors/workspace及F8专项；完整矩阵和实窗证据另记，不在本条提前宣布关闭。

F8 工作区滚动容器不得让隐藏堆栈页的尺寸决定当前布局：WorkspacePageStack 按实际中央页/占位页提供尺寸建议，仅为当前页保留可读横向宽度，纵向仍允许内容滚动，使日志 dock 保持正常分配。导航和恢复须刷新几何建议；不得通过隐藏同伴 dock、重建控件或放宽 F4 字段/日志可见性断言消除裁切。回归 smoke_f4_layout、smoke_workspace_layout 与 F8 自然导航/焦点专项；旧日志中心裁切及第一候选中央页过窄失败保留。

## 2026-11-02 J2/F8 首轮验收修复

首轮候选56b689f实际完成Windows六份正式报告：300次执行、286通过/14失败，全部有v3断言且总数179468；严格门禁失败。GUI报告git_dirty=true的73条旧长路径删除表象保持原件，子进程必须继承core.longpaths=true并自己确认clean。真实M0/Linux CI失败，后续Linuxprofile未运行；安装及冻结桌面成功不能代替功能矩阵。首轮原生150%发现保留dock后切项目，FocusIn发生在中央页临时零尺寸时，布局完成后字段仍完全不可见；原证据保留。

core/accessibility.py在同步显露之外增加由controller所有的单次计时器，等待布局后补一次既有最小平移；弱引用、Qt对象有效性、当前焦点、owned、可见/启用和关闭守卫缺一不可。新FocusIn取消旧任务，foreign窗口不得滚主窗；祖先布局变化可去抖但不能无限重入或强制滚动归零。smoke_f8_accessibility保留原280入口，新增自然retained-dock路径、全viewport label/field、真实已排队Project→Start覆盖及删除/foreign/业务快照边界；修订后的作者125/150各416，独审单独核验stale段真实排队，不用同页无FocusIn假覆盖。

core/experiment_workflow._field_report的captured editor来源循环仅服务generated模式；external依原实际主配置/宏身份与后端Inspect工作，不清空休眠文档、不跳过真实外部输入核验。切回generated仍拒绝路径/读取状态/内容变化；完整editable bundle继续要求全部保留资源，包括休眠谱，并尊重restricted资源裁决。原smoke_f4_inspect_backend必须通过真实双版后端，永久test_k1_workflow增加模式/来源反例，旧断言不改。

诊断分类由machine path产生，不从显示文案猜测。材料numeric/positive旧分类保留，新的invalid只用于新增单位/有限性/换算约束；density_internal_value接受逻辑不变。未知physics.mode沿旧unsupported，合法manual转用实际依赖校验。完整NIST目录的未知名称为error，直接名称能定位实际字段，显式别名目标不能伪装成别名名称控件。STL/replica从旧不可编辑告警迁移到experimental；box/trd登记器统一产生的code迁移、旧v1 JSON身份不重写及新记录身份差异见[结构化诊断与定位](结构化诊断与定位.md)。

测试fixture必须携带wizard生成的dirty内存材料文档，不回填旧路径；scans保留全部原断言、PSTAR判据与事件数。已开放STL/parameterised应验证资源与往返，并保留真正未知字段/放置拒绝，STL单位键为file_unit。Windows GUI/integration使用完整PyVista环境，内部SKIP不能当完整3D通过；同版本同profile同v3基线逐例/总数门禁不放宽。正式launcher绑定本轮报告head/profile/源码/测试/merge指纹、EXE/merge路径和构建身份，并检查merge/helper/输入首尾SHA；114数据绑定已核验SDK版本与12项目录，不以required_complete冒充版本证明。这些是第二候选约束，尚不宣称阶段验收完成。

## 2026-11-02 J2/F8 第三修复候选（专项独审完成，阶段未关闭）

第二冻结2901f42的已过本机profile、真实CI及原生范围按各自原report/launch/visual-observations登记，详见STATUS当前段。2901f42的四项CI run均attempt1：Linux41336912644/M0 41336912651失败，安装41336912645/桌面41336912646成功；首轮56b689f四run及旧失败另保留，不拼接报告或改绿。第三修复候选包含下述已审产品及测试修复；截至文档快照，113 integration已通过31/31、6790入口及gate0，114 integration已通过31/31、6780入口及gate0；2901f42六份本机profile均已终态passed，合计300/300、180992入口，local-final-audit的errors=[]。完整新候选验收待进行，仍须以新提交及必要构建身份完成同版本/同profile/v3历史strict门禁、真实CI和原生复验。

History修复只为Runs root→runs_root、Search→search、Status→status_filter建立三个显式buddy，复用现有语言刷新链，使QWidget及QAccessible名称随en/zh/en更新；不新增全局QHBox猜配、翻译表或业务事务。QLayout兼容修复先判真实QLayout再按count/itemAt遍历，区分QSpacerItem/QWidgetItem，不把item.layout()的任意绑定返回值当layout。原CI异常、自然环境与受控返回值负向证据分别保留；两产品及组合595专项独审均已通过，仍不能冒充新候选CI/native通过。

F6窄preview dock不在本修复中扩大尺寸/改变布局。可容纳标签+完整控件时仍要求joint完整可见；确实不可同容纳的宽度边界不能伪装成全joint通过，也不得强制滚动归零或更换dock实例。main直接视觉观察排除QQ覆盖；被动矩形containment不能证明无遮挡。2901f42三档原生host退出0及100%真实100事件不关闭150%F6/History开放项；新repair相关scope在三档仍须补验。

K1 final-v1修复以policy规范身份匹配同一普通文件，但不改变closure节点、资源读取路径或source_receipts。原policy绝对拼写必须先_no_links再resolve，并保存原拼写；资源匹配方向也先拒链接再resolve。相同普通文件的重复policy入口明确拒绝，无关/相对unused入口仍拒绝，restricted默认拒绝与显式允许裁决不放宽。collect返回前、export原收据核验后且_publish_directory前，均重新按原policy拼写_no_links→resolve并核对身份，不能入口resolve后丢掉原拼写。真实晚junction反例只改policy原组件也须拒绝，export不发布并清理自身staging；这些确定时点检查不承诺任意并发替换安全。该final-v1补丁f705dc96及其产品4990d9f4/测试80726fb8专项独审已通过：完整603入口／13组、原短路径30入口、真实junction 3+5。该专项已闭合，完整新candidate验收仍待进行，不能据此将旧CI或阶段改为通过。

几何STL file路径回归专项独审已通过；该测试只做规范resolve及samefile的精确同文件断言，不能用endswith/文件名/存在性代替身份，也不为测试改geometry产品语义。当前项目格式v8；普通旧项目及完整v7编辑快照仍按已知枚举迁移，损坏旧字段不泛化默认，有日期历史v7文本不追改。

证据根文字登记为out/verification/j2-f8-2901f42及out/collab中的各冻结独审目录，尚未归档为公共链接；最终入库后由main另链。Native独立文件审计仅核launch/GUI149/SHA/原图引用/记录/离线manifest，overall=false。旧raw、原CI失败、JPEG编码的原图字节以及旧copy/review首败均保留，不以本段更新历史身份。当前条目是第三候选实施契约，不是阶段状态改为完成。


## 2026-11-02 J2/F8 第四修复候选：18c5858平台测试接口与证据映射

18c5858真实CI首败及Windows/原生均按冻结身份保存，不覆盖56b689f/2901f42旧报告或改绿。Linux41344573528/M0 41344573541失败，Desktop41344573534/安装41344573604成功；strict4pass/4fail。Linux三个GUI在F8:659失败，Windows M0是geometry:264成功reload字面锚点断言（195入口），不是旧STL:162；Linuxbackend/integration未执行。18c六份本机均已终态passed，合计300/300、181295入口，原report/launch SHA及算术核对通过，local-final-audit的errors=[]。两项test-only专项独审均已PASS，仍不宣告阶段完成。

成功reload的实际产品合同是expanduser().resolve()后的来源锚点，失败读取仍保留此前原锚点/文档/非法草稿。测试只改成功分支的精确规范身份预期，并保留失败/无源/非法草稿原判据；真实8.3原195fail与候选长/短各214pass是本机实证，不捏造原CI具体路径拼写。Qt6.11.1/6.11.3的Unix Combo实现说明本轮Linux Name使用currentText（空字符串走Qt回退），Windows Name仍为标签；语义标签由实际Label关系表达。测试仅按本轮Windows/Linux真实provider严格验证Name/Value、Role、interface.object、确切Label/buddy及动态语言，不将其泛化为macOS/所有Unix验收。两端各三类9负向（丢buddy、同文本异label、错误control接口）都拒绝；原property/buddy、F5/完整joint/滚动与spacer断言保留。作者Linux完整655不冒充独审全量重跑，不改正确产品。

现有18c149GUI逐文件/三identity映射已经核对，C++源码指纹按原18c报告保留；新HEAD必须在两test与docs提交后才产生，最终产品/C++映射仍pending，完成后才能映射原三档限定scope，不是docs冻结前置，不伪称新执行、完整视觉或物理基准；新完整真实CI仍须通过。150的九页/模板与125的有限导航范围区分；100生产Save/Open/init no_run/run100/100/export闭包与未CLI replay区分。三档main正常退出，Harvey/Ptolemy只做必要链路纯文件审。86原图含QQ，raw只本地保留，公开仅metadata及观察范围。F6窄dock边界不扩写成已修复。第四候选GUI终态后补一轮100/125择一的代表性native（I1/I2打开取消、Import已有offline包、template Finish及重入Back/Esc）仍pending，须按新HEAD/build单独记录，不扩大原18c三档范围、不重做三档，也不是docs冻结前置。原trace/失败/缓存读数局限均保留；正文不引用未归档OUT为公共链接。


## 2026-11-02 J2/F8与E7本轮验收完成（测试冻结2ec5b14）

main接受J2/F8及E7既有15原语/7布尔工具注册与元数据的本轮约定验收。正式构建/测试固定2ec5b14fc823ad837dce3ea6f5d7c5ae3f66a3c8，Windows六份300/300、181357入口，launch gate/runner0、identity_errors=[]、report clean；实际CI四workflow八job attempt1success，12报告636执行/221186入口、strict全部通过。Desktop/Install不伪加case。证据与实际命令见[最终归档](verification/j2-f8-final-20261102/README.md)。后续包含本条的提交仅docs/evidence，不改report/EXE原HEAD，不要求重建/矩阵循环；实际Git树、三锁及main后置字节映射证明交付身份，不自填未来SHA。

CI四M0 clean，Linux八报告原git_dirty=true，原status仅对应版本.g4env-11.3.2或11.4.3、.micromamba、bin三行未跟踪环境目录；tracked_source_gate=pass/untracked_source_files=[]，source/tests/merge与2ec精确匹配。归档按每份原SHA/HEAD/fps及原dirty/status绑定，既不泛称全局clean，也不放任其它dirty。新增归档blanket-notdirty附加检查首败及Sagan独立解释原样保留，原CI checker/报告不改；旧56b/2901/18c红例与本轮12strictpass分开。

E7只完成现有15/7真实factory分派、能力元数据及GUI共源离线表接线；GeometryConfig原数值/关系/来源校验仍在，不冒称全部校验器重写。A5八类只沿原master-owned构建链预计算，旧7类及Boolean不新增GetCubicVolume；查询不构造实体/store/RNG，所有权、单位、生命周期不改。原4registry/VolumeBuilder文件相同与BackendCapabilities整文件后续变化区别保留；构建capabilities及本轮适用组件/双版真实入口分别按其HEAD/源码/EXE证明。关闭不扩实体、assembly、全部Boolean组合、每体积GDML、任意worker安全或科学支持。

两test-only平台接口修复独审通过：成功Reload核对resolve/samefile/SHA，失败分支保留原字面来源/文档/非法草稿；Windows8.3原195红与长短214绿不捏造原CI路径。Windows/Linux真实Combo provider的Name/currentText、Value、Role、interface.object及确切Label关系分开检查，属性/buddy/同文异label/错误接口负向保留；不改正确产品，不泛化所有Unix/macOS，作者655不冒独审全量重跑。

18c三档原生只沿原HEAD/EXE/限定scope映射，149GUI/C++与精确7文件差异byte-map是身份事实，不是新三档执行。2ec125实际I1/I2首屏打开关闭、Import原8文件包/保存、模板Finish/另存/重入NextBackEsc正常退出，main24观察/41JPEG，Ptolemy84原件纯文件核验、Harvey无新增必跑动作合同核对。Import4旧history为stale，当前仅import_history passed imported_count4；没有本轮validate/generate/run新record。取消事件运行后自动几何预览仍会构造后端，不能声称完全没启后端。缓存project/Undo/UIA focus非live F5，文件审非第二次像素审查；18c100的init no_run/run100/100/export未CLI replay及旧scope各自保留。

197张标记local-only原图仅本地，公共objects/tree均排除、只path/size/SHA/范围；opaqueZIP未内容审查只metadata，不能凭SHA判安全。历史Markdown原字节归档为.md.raw及恢复映射，不把旧坏链接或排除图当可读公共入口；原report/log维持可重定位布局并拒绝旧绝对fallback，实际currentWindows6+CI12以原checker和matchingbaseline验证。现有docs/verification/** -text已保证raw，Git blob实测而非新增attrs；最终证据精确清单包含全部文件且不自指。F6内层viewport容不下joint的窄边界、QQ遮挡、物理跨屏/热插拔和H2/H7/Q2等科学基准均不随关闭扩张。dated历史和原独审身份不追改。


## 2026-11-02 L1 配置 Agent 实施候选

用户授权的本轮 L1 正在实施，分支 roadmap/L1-config-agent，开工基线4840e62e；F2在L1之后，L2代码Agent依赖L1/K2另行推进。完整约束见[开工契约](collab/inbox/20261102-l1-execution.md)和[L1使用与接口](L1配置Agent.md)。本条是准备正式验收的候选契约，不是阶段完成，不追改前述J2/F8/E7或更早历史。

本轮只在生成模式（generated）按固定白名单修改既有体积、源、运行、物理、计分字段：体积material/size/position/rotation/sensitive（world仅material/size，size仅已有允许模式的box/tubs）；源仅mono/point/fixed的particle/energy/position/direction；运行beam_on/threads/seed；参考列表模式（reference）物理reference_list/default_cut；计分hits/event_edep/edep/dose/fluence。读取上下文来自UI捕获快照，模型不能扩大写范围；不新增目标，不自动编辑高级源分布、资源路径、任意代码或安装器。Dose/Fluence等原实验性与科学边界不提高。实际事务、校验、初始化、生成、运行、导出复用F5/K1及唯一runner；默认完成性evaluate只查询绑定run资格，不调用K1物理比较，后者须显式参考/判据。

默认plan-only先给差异。用户在UI明确新授权后点击应用，`approve_with_authorization(authorization, auto_run=False, write_scope=None)`复核同base_fingerprint/revision和同plan，建立新TaskJournal与新task_id，保存新授权并记录reason事件`agent.reviewed_from:<旧task_id>`；旧任务取消留史、原授权/预算不改，不再请求模型。恢复实例的`_recovered`阻断此入口；恢复只按旧operation/run/record/action查询并显示历史/未观测，不重发、不接管别人的进程，须新prompt请求才建新task执行。权限或预算不足停在对应步骤，不自动扩授权。取消/超时/关闭只处理本任务绑定工作，不因其它所有者忙而误取消K1。

持久密钥只用系统凭据服务，不能落任务/项目、日志或导出包；Linux可选SecretStorage缺失/服务不可用明确拒绝，不默降明文或session。云接入与本地OpenAI-compatible协议分开计证；本地仅实际HTTP协议夹具，不附权重、不宣称实际本地模型理解质量。journal的checksum/聊天/日志不是授权来源，保存的授权不能恢复执行权。

主线程已收核心专项独审：最终忙状态P2在controller409d6a4a/适配9689acb7定点关闭；面板125%/150%独立组件各108入口、永久边界146入口各按原收据保留，不合并成正式矩阵或实窗。当前开发证据是旧2ec EXE上的固定HTTP双版各24入口，以及真实DeepSeek任务集02的一项4事件/export/Undo、另两项澄清；旧01整体UI线程守卫失败原件不拼绿。新候选重新构建、双版双平台完整矩阵/真实CI、人工时间成功率对照和原生窗口边界仍待；不造未来HEAD、计数或完成声明。


## 2026-11-02 L1 路径显示 raw 修复候选

本条只追加首候选D1后的显示路径修复契约，前文历史与各旧身份不改。D1为 `d1bd57da5a7e61d07fdff6cadc2a1f5f3dadc359`：Windows static48/5031、GUI70/9781、113backend63/82029、114backend63/72536，四原launch/report均按各自原SHA保留，runner/gate0、identity_errors=[]，合计244次执行/169377入口。两integration未执行，不能写完整矩阵通过；这些是D1结果，不是后续未提交候选的结果。

五域真实云Task01七步骤（plan/apply/validate/initialize/generate/run/evaluate）passed、run4完成，但完整F5 capture仅 `/state/drafts/project.threads.raw` 与接受快照不同：ASCII的 `2` 被路径显示回投重格式为 `〢`（U+3022），后续flush触发revision变化/K1 stale。任务总receipt仍failed；当时journal停在awaiting_confirmation，不将“failed-task.json”文件名误写成其state=failed，不把未完成的确认/export/Undo冒称通过。Task01原receipt、快照、diff、原始记录与正式D1四报告不改。

当前最终v3保留 `ProjectPage.show_generated_paths(project)` 三路径显示及实际K1 display binder，并修补同类路径raw边界：作者受控显示探针发现旧transactions将未改显示路径还原为typed原值，丢掉原路径草稿空白，出现两处raw diff/指纹不等。K1 binder现把原snapshot path raw存为内部view tuple第三项；capture_workspace兼容旧2tuple，仅当捕获路径仍等于生成显示值时按原raw还原，非路径raw保持。最终是ProjectPage、window/experiment、window/transactions三产品＋两测试五文件，新只读源freeze为 `out/collab/l1-project-path-display-repair/v3-final/freeze.json`；原v1五文件freeze与文档v2均保留，不改写旧身份。正常load及legacy全量 `set_project` 保留，window/run.py仍为D1原base `3af4daefa4c0818fba9879acffe14e15ece2c8b908d2b26b0526e9fa7e873d56`；不以此描述当前MainWindow的legacy自然缺陷。privacy、codec、locale、完整同指纹和K1资格门禁不放宽，本次文档不改产品、runner或测试。

此前实际K1显示绑定专项通过仅保留旧范围；当前v3作者Qt56通过，旧54及后端25仍属旧开发身份、不重标。r1/r2/r3的夹具路径/设置时序失败及源码日志保留，r4仅修相对路径与设置顺序后56；这些不是新产品失败，隐私拒绝规则未放宽。产品v3 raw-path delta独审已PASS（限定接口/显示/F5资格，不冒backend/formal），新candidate/重新构建/全部formal/真实CI/native及人工对照仍待，不提前填未来HEAD、PASS或阶段完成。使用与当前进度见[L1说明](L1配置Agent.md)。


## 2026-11-02 L1 EE验收快照与原生布局后续候选

正式身份仍为 `ee6f40ded197a59c0b63726b92a09560831867ca`（EE）。本机四份原 Windows 报告终态为 static48/5031、GUI70/9795、11.3 backend63/82029、11.4 backend63/72536，合计 **244次执行／169391个实际入口**；四原 launch 均 runner/gate0、identity_errors=[]，对应 report 的 git_dirty=false。EE 两个 Windows integration 未执行，不以真实专项或 CI integration 补记本机六 profile 通过。EE 真实 CI 四 workflow 均终态成功，12份 profile 原报告 strict/matching baseline 通过，合计662次执行／227634个实际入口；Desktop／安装的独立结果不再算进该数。原证据根为 `out/verification/l1-ee6f40d/`，不迁移到下一候选身份。

Task03 五域真实云链和应用恢复02分别已收 Ptolemy 限定文件独审 PASS：前者是一次真实模型规划、程序化审阅、真实 K1 run4/export/Undo 链，不是原生／人工时间或科学验证；后者仅固定 HTTP 夹具下“K1 terminal 已发布、Agent result 未落盘”的单一受控崩溃点，实际73→0，恢复只查询旧身份且不重发，历史结果陈旧、当前资格不恢复，不扩大为任意中断恢复。两者原失败／脚本及独审身份保留。

native125 的人工操作臂／Agent臂单对描述性比较、原保存与导出文件链，以及另行授权的生产 closed-load 模型 IO 已分别有限通过；closed-load收据1beea485仅允许QtCore import、无QCoreApplication／QApplication实例，不冒第二次实窗或CLI回放；不是受试者成功率／提速结论，文件审不冒像素或第二次原生观察。原EE native150虽正常退出，仍发现52px下L1 AI全控件不可读的布局P2；该次原生失败按原身份保留，不改记原生总体通过。此为L1新缺陷，不套用旧F6按钮82>56的历史窄边界或改写其原结论。真实 NL 诊断修复02已由 main 单次运行，外层原13956／child63728均实际exit0、owned0，作者receipt为1request／8ops／4events／export／Undo passed；其实际链路纯文件独审已限定 PASS：一次真实回复共1295tokens，initial→capture恰5叶差异（4个energy同步表示及派生errors清空），其它raw保持；Undo完整JSON回S_invalid已核。expected/captured只差旧sourceEditor.errors清空，原生产语义指纹相同，不称全JSON相同。该审不代表native／科学／通用NL可靠性或生产load／CLI回放。原01为driver注入夹具失败、0modelcalls，v1/01原件保留，不被02成功替换。

Harvey 的52px布局后续候选已仅在OUT冻结：产品SHA为 `05e4ec9077bbd0d8e08f8381a63b5ada86e3ad8566d436d6b04fae484a3038ae`，仅动态两列可读最小宽度提示及固定footer inset／reflow；测试SHA为 `6f06b0277c10b5ff27a21691a2b7c63f2a2f5d3124602b18a2f1af7cabd748e9`，保留原函数AST（main仅增新调用），新增真实MainWindow自然show的QAction／F6／Tab回归。候选注入后的125%／150%完整组件入口各1216、实际exit0；同一新回归在原产品52px负向实际exit1。workspace layout／core accessibility、Controller／F5／K1和翻译不改。上述作者专项与Ptolemy候选限定独审PASS分别计证；独审按当前focused-target及可容纳标签／控件joint合同关闭原52px P2，无其它确认P1/P2，不冒新candidate正式矩阵或新native通过。retained语言补验仅125%，英→中→英每轮9Tab的当前焦点完整可见、可容纳joint通过，非焦点右列仍可裁剪，不保证全footer同时同屏，新native仍待。main已精确apply已审panel／test两path，实际tracked两档各exit0／1233，另按原收据保留wrapper计数假设失败及更正，不与作者各1216混计；新提交身份、新构建、完整Windows六profile、真实CI和对应原生补验均待，不预填future HEAD或继承EE资格。当前不关闭 L1，F2／L2 顺序及既有白名单、raw／同指纹、授权／预算／只读恢复合同不变。


## 2026-11-02 L1本轮验收与交付

主审阶段签收：**本轮约定范围验收完成**；Linux独立X11/xcb代表性原生：**独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。产品／测试冻结 `246e4f6f1b97cc5e0651ff01262c85cf2e9c28d3`，后续docs/evidence保留原BuildInfo及所有历史HEAD；当前证据见[最终证据](verification/l1-final-20261102/README.md)。

Windows 六 profile **308 次用例／183347 个实际入口**；CI 十二原报告 **662 次用例／228978 个实际入口**，各原报告／日志身份、非零断言及匹配 J2 基线均经严格重放。 本机static48/5031、GUI70/10131、11.3backend63/82029、11.4backend63/72536、11.3integration32/6815、11.4integration32/6805。CI 保留一次显式重试：M0 `41415360785`、Linux 双版 `41415360846`、desktop `41415360995` 均 attempt1；installation `41415360795` 的原 Windows job `125177769617` 在数据集上游 MD5 校验时拒绝，授权仅重试 Windows 后 attempt2 job `125215598259` 成功。原 Linux 安装成功结果沿用，原失败 collection／strict 总状态不改绿；最终以 `passed_with_explicit_retry` 聚合，不称首次全过。 非视觉18报告／970原日志已逐SHA、重定位严格checker及稳定J2匹配基线复核；原EE两个本机integration当时未做的事实不改写为已做，只新246六profile有新终态。

EE→246 的全树精确映射仅 panel、其 smoke 与八文档变化；157 GUI 源中其余156及 Agent 五核心／adapter 未变。真实云五域 Task03、NL 诊断修复02、人工对照及受控恢复／production closed-load 均保留 EE 原 HEAD／EXE／脚本与各自范围，不改签新 246 模型请求、窗口或运行。 五域总三attempt／两失败一成功，Task01 raw数字漂移、Task02 OUT serializer失败保留；Task03真实模型规划与程序化review后run4/export/Undo限定通过。NL诊断修复01是0call夹具失败，02另一次真实1295token/8ops/4events链，expected/captured仅derived errors清空而非完整JSON相同，Undo回S_invalid。不存在通用NL成功率或物理验证主张。

人工操作臂与 Agent 臂仅一对 Codex 操作者案例：原 actions 记录 64／48 行，其中 measured 57／38 行；measured 首尾跨度 1003.298／1015.809 秒，全日志跨度 1088.615／1234.068 秒。包含工具周转、观察等待、修正与不对称 setup，记录行不等于工具或物理输入总数；不推导提速、受试者成功率或统计优势。两臂各完成4事件、资源输入一致，模型 wire 总请求／token 未独立采样，不能借 Task03 的用量补填。 后续production closed-load补齐真实reader／codec，且无Application／事件循环／CLI replay，两包历史stale；早期文件审pending不追改。恢复02仅固定HTTP夹具下“K1 terminal已发布、Agent result未落盘”单点73→0，query-only且旧授权／usage／events保持、当前资格不恢复；正常close退役cancelled不当backend新失败，原恢复01失败保留。

新 246 Windows 125%／150% 仅按受限原生范围计证：AI dock 的自然显示、F6／Tab 当前焦点与可容纳标签＋控件联合范围、只读恢复代表及正常关闭。两档 host 实际 exit0；不承诺所有非焦点 footer 同时同屏，不声称物理多屏热插拔或全面可访问性。旧 EE native150 的 52px 不可读布局失败按原身份保留。 新125首次退出尝试与resumed125/150各按原root保留，不覆盖旧EE150不可读失败，也不凭几何/exit0单独宣称视觉成功。Linux独立X11/xcb代表性原生：**独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**，准备独审与READY只是执行边界，不能冒实际现场。

固定既有对象／字段白名单、默认只规划、审阅后新授权同 plan 建新 task、旧授权留史及恢复仅旧 ID 只读查询不重发保持。默认 evaluate 仅运行完成性；本地仅 OpenAI-compatible HTTP 协议，未测本地权重质量，不执行模型代码，不扩科学验证、任意新目标或 L2 持久代码工作流。 原图、QQ raw 与原 UIA 永久仅本机；最终公共证据只给限定 scope／path／size／SHA／MIME 元数据，不复制、上传、裁剪或 AI 重绘。发布包不含真实密钥、原始云请求／回复、任务 journal、完整 F5 capture、机器 QSettings、EXE／SDK／数据集或巨大 CSV。 不为后续docs-only关闭提交再造模拟或更改报告门槛；受控文档链接、归档字节、重定位strict及最终身份由实际交付复验。F2后续、K2/L2另阶段，不在此次扩大验收或任意科研等级。


Linux原生通道补充（主审已签收）：main已实际操作独立真实X11/xcb桌面，一次固定HTTP计划passed，操作观察时曾停在awaiting_approval、0事件；随后在观察期间触及300秒预算，整任务保留failed／agent.task_timeout，不称整任务成功。原host exit0、slot_released=true、host与显示服务两组remaining_owned均空、HTTP已关闭；显示辅助子进程退出码[0,1,0]（twm非零保留），不能写全部子进程exit0；代表性原生签收结果为 **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。WSLg RAIL任务栏无法展开，第三次host退出且0请求，原失败保留，绝不称该通道成功。Ubuntu实际系统安装x11-xkb-utils，其它本次依赖保持隔离OUT前缀；具体包版本／SHA及安装收据见最终证据，不把早期准备收据system_installs=0外推到之后。


### 2026-11-02 J3 第一阶段：设计系统、皮肤注册表与可访问性下限

**动机**：J3 任务书要求先改善既有 B/K/C 的区域可辨性，再新增可选皮肤。第一步先把“颜色/间距/圆角/字体/状态”从散落的 QSS
常量收成数据，让后续外壳与页面改造有统一来源，而不是继续在 661 行样式表里追加规则。

**实现**：
- `gui/g4usim_gui/core/theme.py`：`ThemeColors` 由 20 个角色扩到 28 个（新增 `canvas_alt`/`surface_hover`/`border_subtle`/
  `focus_ring`/`info`/`grid`/`shadow`/`sidebar_accent`）；15 套皮肤（legacy B/K/C + 12 套新色板，浅 8 深 7），每套带
  `description` 与 6 色 `series`；`SPACE`/`RADIUS`/`CONTROL_HEIGHT`/`ICON_SIZE`/`MOTION_MS` 标尺；`mix`/`relative_luminance`/
  `contrast_ratio`/`on_color`/`on_accent`；`stored_appearance`/`persist_appearance`/`apply_appearance`/`apply_theme`（`palette`
  保留历史语义）；`build_stylesheet = _base_stylesheet + _design_stylesheet`，后者以 `$token` 单遍替换。
- 注册表构建时 `_accessible()` 用 `_until_all`/`_bg_until` 把 `text_muted`、`border_strong`、`accent_soft`、`selection`、
  `sidebar_selected`、`focus_ring` 混合到下限：正文与交互文字 4.5:1、控件边界与焦点 3:1、选中行 1.15:1；`on_color` 取最大对比。
- `gui/g4usim_gui/window/shell.py`：`View → Appearance` 菜单按明暗分组列出全部皮肤，`_set_skin` 激活该皮肤所属明暗组，
  `_set_palette` 保留旧语义；`_sync_appearance_actions` 勾选模式与两组记忆皮肤；侧栏 244px（220 会截断 “Effective Configuration”）。
- `app.py` 启动按 `stored_appearance` 恢复；`icons.py` 新增 `check` 指示器；`i18n.ZH_CN` 增加 34 条皮肤/菜单文案。
- 新增 static 用例 `scripts/test_theme_registry.py`（113 断言点）：15 皮肤形状、23 项对比度、colour maths、持久化迁移、
  `apply_theme` 契约、样式表无残留 token；注册后用例 215（static 49/gui 71/backend 63/integration 32）。

**反例与教训**：
- 第一次对比度审计 13/15 皮肤不达标：`_until_all` 的 `mix` 方向用反（`step/40` 被当成第一参数份额 → 起步 97.5% 朝向目标），
  把 C 的 `border_strong` 推到近白；改成 `mix(fg, toward, 1.0 - step/40)` 后 15/15 通过。
- **Qt 崩溃**：`QMainWindow::separator { width: 1px; height: 1px; }` 会让 `smoke_workspace_layout` 在浮动态 dock + offscreen 下
  于 `apply_theme → app.setStyleSheet` 处 0xC0000005；只保留 `background`/`:hover` 即恢复（149 断言通过）。
- `QDockWidget > QWidget` 选择器会命中标题容器（标题也是直接子 QWidget），导致标题栏渲染异常，不得使用。
- Windows offscreen 平台没有字体数据库，窗口抓图全是方块；实窗对照必须 `QT_QPA_PLATFORM=windows`。
- 本机 Git Bash 的 `mingw64/bin` 会抢在 MSYS2 UCRT64 之前提供旧 `libstdc++`，7 个 C++ 编译类 static 用例因此以
  0xC0000139 失败；跑静态前 `PATH=/d/msys64/ucrt64/bin:$PATH`（与主题改动无关，已写入证据 README）。

**证据**：`docs/verification/j3-theme-v1-20261102/`——B/K/C 改动前后同工程截图 12 张、static 49/49（5,615 断言）、
主题 GUI 4/4（284 断言），归档报告可直接被 `check_report_evidence.py` 复核；完整 GUI profile 另存 `out/verification/j3-gui-v1`。
**边界**：本阶段只做外观基础设施与作者自查，区域层级实窗改造、对比度实测表、125%/150% 与 Linux 桌面、性能基线与独立复验仍待做，
不得据此宣布 J3 完成。

### 2026-11-02 J3 第二阶段：外壳层级、命令面板与外观状态

**实现**：`gui/g4usim_gui/widgets/command_palette.py` 新增 `PaletteEntry(label, category, detail, callback)` 与
`CommandPalette(QDialog)`（objectName `commandPalette`，`search`/`list`/`hint`；`set_entries()` 后默认选中首个可选行）。
`gui/g4usim_gui/window/shell.py` 的 `_build_workspace_shell()` 改为 `nav_groups = ((tr("WORKFLOW"), 0), (tr("RUN & ANALYZE"), 5))`，
在组起点插入 `QLabel#sidebarSection`、组间 `addSpacing(12)`，记录 `_nav_section_labels`/`_nav_section_sources`；页头加 `page_crumb`
（`uiRole=crumb`）与 `palette_button`（Ctrl+K），状态栏 `addPermanentWidget(self.appearance_status)`（objectName `statusMeta`）；
`_command_palette_entries()` 返回 9 页 + 7 操作 + 15 外观，`_show_command_palette()` 执行选中回调；`_refresh_appearance_status()`
显示 `Appearance: 皮肤名` 并带描述 tooltip，在 `_set_theme`/`_sync_appearance_actions` 后刷新。`_set_skin()` 选择皮肤时切到其明暗组，
`_set_palette()` 保留 B/K 旧语义。`core/theme.py` 的 `build_stylesheet()` 变为 `_base + _design + _shell`，`_shell_stylesheet()` 提供
sidebar section/nav 轨道、crumb、statusMeta、`QDialog#commandPalette`、`paletteCategory`、`paletteSearch`、`paletteList`（含
`::item:disabled` 组标题）与 `paletteHint`；菜单栏/`QToolBar`/`QStatusBar` 改用 `$canvas_alt` 与 `$border_subtle`。
命令面板过滤为“标签严格匹配优先，无命中才回退类别+说明”，`Up/Down` 通过 `_selectable_rows()` 跳过组标题。

**陷阱**：`QMainWindow::separator` 设 `width`/`height` 会让浮动态 dock + offscreen 在 `apply_theme` 时 0xC0000005 崩溃；
`QDockWidget > QWidget` 会命中标题容器。两者都已写入 `gui/AGENTS.md`。

**回归**：新增 `gui/smoke_tests/smoke_command_palette.py`（40 断言）注册为 `gui_command_palette`；
完整 GUI profile 72/72、10,227 断言通过（`out/verification/j3-shell-gui`），证据归档
`docs/verification/j3-shell-20261102/`（含 B/C/纸墨/午夜蓝 page0/page2 与命令面板截图）。

**边界**：本阶段只做外壳与交互自查；区域层级实窗改造、对比度实测表、125%/150% 与 Linux 桌面、性能基线与独立复验仍待做，不得据此宣布 J3 完成。


### 2026-11-02 J3 第三阶段：工作区面板与外壳细节

**动机**：第二次实窗截图里 3D 视图停靠面板的视点/投影按钮在窗口右缘被裁（“World / Show Labels / Load Tracks…” 不可点），
配置 setup 面板的 “Browse” 也被裁，状态栏 “Recovery copy: …” 折行后被窗口右缘压住；这些是可用性缺陷，不是审美偏好。

**改动**：
- `preview3d/pyvista_preview_widget.py`：视点按钮 + `Orthographic`/`World` 从单行 `QHBoxLayout` 改成两行 `QGridLayout`；
  `legend`/`particle_legend` 固定宽 190→168；`section_slider` 最小宽 110→80。
- `widgets/config/preview3d.py`：`options` 由水平一行改为两行（自动后端/Show Source 一行，Show Labels 一行）。
- `window/workspace_layout.py`：`setup_panel` 最小宽 260→300，`setSizes([300, 680])`→`[330, 650]`。
- `window/recovery.py`：恢复状态 `setWordWrap(False)`、最大宽 480→320（完整文本在 tooltip）。
- `core/theme.py`：`QTabBar::tab` padding 8/14→7/11、margin-right 4→3；新增 `QToolButton:focus` 焦点描边与
  `QToolButton[navButton="true"]:focus` 背景。
- `core/icons.py` 新增 `undo`/`redo`；`window/shell.py` 的 `_refresh_icons` 为历史工具栏动作着色；
  `window/transactions.py` 在工具栏创建后主动调用一次 `_refresh_icons`（壳先于工具栏构建）。

**验证**：`--profile gui` 72 pass / 0 fail / 0 skip、10,227 断言（`settrace_assert_lines_v3`、`sha256_raw_bytes_lf_v2`、
源码 `9e40e889…`），报告 `out/verification/j3-panels-gui2/20261102-225535-090e83e1/report.json`；门禁通过。
实窗截图用 `QT_QPA_PLATFORM=windows`（离屏无字体数据库），阶段 2 提交 `46241a3d` 的对照图一并归档。
一次全量 GUI 复跑曾出现 `gui_k1_cli` 的 Windows 临时目录删除 `PermissionError`（`tempfile.cleanup`），
单跑通过；第二次全量 72/72，因此记为环境性抖动而非代码回归。

**边界**：未复测 23 项对比度表（调色板未改）、未做 125%/150% 与 Linux 真实桌面、未做独立审查；J3 仍未关闭。
证据：`docs/verification/j3-panels-20261102/README.md`。


### 2026-11-02 J3 第四阶段：按当前页面适配工作区

**动机**：143 行 `workspace_layout.py` 的预设只有 View 菜单入口；实测从 Configuration 跳到 Run Console 时
配置停靠面板仍占 700px，中心页只剩约 330px，按钮与 “Unobserved” 行被裁；结果页/历史页同样被压。属于“好上手”缺陷。

**实现**：
- `WorkspaceLayout.preset_for_page(index)`：0–4 → `configuration`，5 → `running`，6–8 → `analysis`。
- `WorkspaceLayout.focus_current_page()`：`apply_preset(preset_for_page(current))` + `page_stack.reveal_current()`。
- View → Workspace layout 增加 “Fit workspace to current page”（objectName `workspaceFocusPage`、`Ctrl+Shift+L`）。
- `_command_palette_entries()` 增加同名 Action（Actions 7→8）；`i18n.ZH_CN` 增加“按当前页面适配工作区”。

**为什么不自动**：`smoke_workspace_layout` 依赖“首次进入配置页自动显示 3D、手动隐藏后不再自动显示”的行为，
按页面强制预设会覆盖用户自定义布局；因此做成显式命令，保留手动控制。

**验证**：`gui_command_palette` 42 断言（含 Run Console→running、Results→analysis 的映射）；受影响 7 个 GUI 用例
7/7、399 断言，报告 `out/verification/j3-focus/20261102-231056-4659a9b9/report.json`（副本
`docs/verification/j3-focus-20261102/`），门禁通过。

**边界**：未做实窗点击录像与独立复验；未覆盖 125%/150%、Linux 桌面、浮动面板组合；J3 未关闭。

## 2026-11-02 J3 第五阶段：导航时收起旧停靠页与结果页分析视图

背景：第三、四阶段的实窗截图显示，配置编辑器停靠页一旦被展示就会在后续页面继续占宽约 620–700 px，
Run Console 只剩约 330 px，Results 的 `page_stack` 宽度甚至为 0。根因在
`gui/g4usim_gui/window/workspace_layout.py` 的 `WorkspacePageStack.reveal_current()`：它只 `show()` 当前
dock 页与 navigation dock，从不隐藏之前显示过的 dock 页。

修法：`reveal_current()` 开头遍历 `_dock_pages`，对 `index != currentIndex` 且可见的 dock 调 `hide()`；
主窗口 __init__ 里把 layout 与 Results 页索引挂到 stack（`_workspace_layout`、`_analysis_index`），
导航到 Results 时调用 `WorkspaceLayout.focus_analysis_view()` 收起 preview/ai、显示 logs dock。

验证：7 个 GUI 用例（`gui_workspace_layout`、`gui_main_window`、`gui_command_palette`、`gui_3d_view`、
`gui_config_editors`、`gui_k1_panel`、`gui_k1_history_scope`）通过，2022 断言；报告
`20261102-232214-51bfb1b2`，归档 `docs/verification/j3-analysis-docks-20261102/`。
边界：Results 页最终布局仍非理想形态（结果视图与日志上下分割），跨平台缩放/真实桌面/性能基线仍待做；
截图脚本曾因抓图前调用 `apply_preset("configuration")` 造成“旧 dock 仍在”的误判，已删除该调用并改为
`screen.grabWindow(window.winId())`。

### 2026-11-02 J3 第六阶段：3D 模型树与体积筛选

- 动机：用户要求增强界面可用性（“树状表示表现模型子母关系”），3D 面板此前只有平铺图例，无法看出体积父子关系。
- 实现：`preview3d/model_tree.py` 纯函数构建模型树（`build_model_tree`/`flatten`），覆盖 hierarchical 体积链、
  simple_box、layered_device；world 行合并为根；父缺失/父链成环有保护且成环节点不参与选中。
  `PyVistaPreviewWidget` 图例列加入可过滤树、双向联动、双击隔离/双击根显示全部、右键选中/隔离/隐藏/全部显示。
  打开 3D 标签经 `_on_workspace_tab_changed` 自动刷新几何。
- 关键教训：`config_builder_page.py` 用 `_scrolled(panel)` 包装标签页，`tabs.indexOf(panel)` 恒为 -1，
  必须用 `tabs.count() - 1` 记标签索引；`WORLD_NAMES` 不能把体积名 `world` 当哨兵（演示几何的 world 体积本身
  就名为 `world`，其子体积 parent 也是 `world`，否则整棵子树会被当成根）。
- 回归：7 个 GUI 用例、1965 断言通过（`docs/verification/j3-modeltree-20261102/report.json`）；
  Windows 平台作者侧直接运行 `smoke_model_tree.py` 27 断言（含 widget 联动）；离屏 runner 下 widget 部分 SKIP。
- 边界：未做 Linux 实窗、150% 缩放可读性、超大几何性能；不构成独立验收。

### 2026-11-02 J3 第七阶段：帮助菜单、快捷键表与关于对话框

- 动机：用户要求继续做可用性改进（“多做用户方面的换位思考”）；此前所有快捷键只散落在菜单与导航提示里，
  新用户无法一次看到全貌，报告问题时也缺环境事实。
- 实现：`ShellMixin.shortcut_rows()` 提供稳定顺序的 (键, 说明) 表；`build_shortcut_dialog()/show_shortcuts()` 渲染可滚动对话框
  （`shortcutSheet`、`shortcutKeys` 标签），`about_text()/show_about()` 显示版本与环境路径；Help 菜单挂在 Navigate 之后，
  F1 打开快捷键表；侧栏导航按钮 tooltip 统一为“打开 <页面>（Ctrl+Alt+N）”。
- 关键教训：对话框里 `QVBoxLayout` + `QFormLayout` 直接堆 20 行会在小屏溢出到 Close 按钮下方，必须用 `QScrollArea` 包表单；
  `resize()` 固定尺寸时 Qt 不会自动增高，滚动区同时解决 125%/150% 缩放。
- 回归：5 个 GUI 用例、211 断言通过（`docs/verification/j3-help-20261102/report.json`）；截图纸墨/午夜蓝各一张（作者侧实窗）。
- 边界：快捷键表是文档，不证明组合键在所有平台/输入法下可用；Linux 实窗与 150% 缩放未做。

### 2026-11-03 J3 独立审查响应（未关闭）

独立复验（`docs/collab/reviews/20261103-j3-closure-review.md`，基线 `03d1c636`）不同意关闭 J3，列出 H1（候选未冻结）、H2（视觉交付缺失）、M1（菜单未标当前/下次）、M2（README 过度声明）、M3（停靠页契约回归）、M4（150% Results 横向滚动）与若干 L 级缺口。本轮响应：提交 `5fb07ba1` 修正状态用例（`theme.current_skin(window)` 恒真、真实运行中切换用例）、`313618ec` 紧凑布局只隐藏 AI 与 3D 预览、`262ce380` 命令面板边框对比度、`a1a64ead` 外观菜单“当前使用/下次使用”；新增 `screens-v2/`（8 皮肤×start/configuration/results + 命令面板 + 快捷键表 + 150% 采样）与 `semantic-colours.md`；三 profile 在 `a1a64ead` 上重跑并冻结到 `docs/verification/j3-close-20261103/`。仍缺：非法草稿/诊断/结果/Agent 状态图、B/K/C 前后问题清单与独立四件事复验、Windows 125/150 真实操作记录、Linux 真实桌面、自动化重启用例——因此 J3 保持未关闭，不写“已完成”。

### 2026-11-03 紧凑区间 dock 保留修复（作者侧）

独立复验在 `6b03317a` 判定退回：`gui_test_window` 的 offscreen resize 从 1200 到 1205（同一紧凑区间）会隐藏用户刚打开的 AI dock。根因是每次 `resizeEvent` 都调用 `WorkspaceLayout.adapt_to_width()`，compact 分支无条件隐藏 `ai`/`preview`。修复为覆盖状态机：紧凑区间内仍收起未显式打开的可选 dock（页面导航显露的 3D 预览也收起），但用户 `toggleViewAction` 的选择写入 `_optional_overrides` 并在区间内 resize 时跳过收起；被自动收起的记录 `_auto_hidden`，离开区间恢复；`apply_preset()`/`restore()` 清空覆盖。新增 `gui/smoke_tests/smoke_compact_panels.py`（25 断言，永久回归，覆盖 1200→1205、1399/1400 阈值、用户关闭与自动恢复）并注册为 `gui_compact_panels`。J3 仍保持未关闭。

### 2026-11-03 J3 第二次复验：配置页按钮与恢复布局（作者侧）

第二次独立复验（`docs/collab/reviews/20261103-j3-independent-ce9b6283.md`，基线 `ce9b6283`）确认 1200→1205 的菜单入口已修复，但同一份报告里 `gui_theme_state_backend` 的断言入口计数在 33/32 之间变化，且又找到两条会丢失用户选择的入口：配置页 “Show 3D view” 按钮（`_show_preview_from_button`）直接 `setVisible(True)`，没有记覆盖；恢复已保存布局（`restore()`）按预设重建可见性后，仍会在窗口宽度不变时被后续 resize 覆盖。

修复：配置页按钮走 `_record_optional_override("preview", True)`；`restore()` 在加载布局后按恢复出的可见性记录覆盖（`_record_optional_override` 不触发逐条 signal），`reset()` 与 `apply_preset()` 继续清空覆盖。`smoke_compact_panels.py` 从 25 断言扩到 54 断言（配置页按钮 1130→1340 保持可见、保存/恢复两个方向、用户关闭后保持关闭）；`gui_theme_state_backend.py` 把运行中外观切换固定为 5 次（不再依赖定时器次数），入口稳定为 15。受影响直接跑：`gui_compact_panels` 54、`gui_f4_layout` 265、`gui_workspace_layout` 149、`gui_main_window` 51、`gui_theme_state` 13，全部通过。文档同步 `gui/AGENTS.md`（三条显式入口）、`CHANGELOG.md`、`STATUS.md`、`docs/verification/j3-visual-checks-20261102/README.md`。J3 仍保持未关闭。

### 2026-11-03 J3 整体验收 P2：状态标签文字对比度（作者侧）

整体验收退回并新增 P2：`core/theme.py` 的 `_styled()` 把 success 与 surface 混成 veil 作背景，设计层又用原始 `$success` 作小字号文字；真实 QLabel 量到 B/K 苔原成功文字 4.3453/4.3453/4.3097:1，低于正文 4.5。修复不提高静态语义色，而是新增 `veil_text(fg, bg, minimum=4.6)`（向可读锚点混合、保留色相）与 `status_combinations(colors)`（success/failed/warning/running 的最终文字/背景对）；成功、失败、运行中标签分别改用 `$success_text`/`$danger_text`/`$running_text`，基础层与设计层同步。`scripts/test_theme_registry.py` 增加每个皮肤最终混色组合 ≥4.5 的断言（含统计组合）与 `veil_text` 断言；`gui/smoke_tests/smoke_theme_response_shell.py` 对 15 皮肤渲染真实 `statusChip` QLabel，读取 polish 后文字色并采样渲染背景像素，断言两者等于 `status_combinations()` 且对比度 ≥4.5，同时覆盖中性 chip。审查者探针 `docs/verification/j3-whole-review-20261103/status-contrast.py` 复跑退出 0。整体验收的其他未完成门禁（状态矩阵、宽表滚动、Linux 3D 等）不在本条闭合。


### 2026-11-04 J3 本轮范围验收与阶段关闭

冻结92134da062e8e3a203a39ff59fcd2b87bd0ffef1。4eebbe9e实现恢复Results布局不被导航重排、统一字体与VTK轴文字；92134仅最小测试夹具与Windows云OpenGL环境补丁，产品字节不变。真实云Windows原生35条不以对象210替代，Linux离屏18另记真实X11。主审本机49/77/33正式矩阵、改变两例2/1241和云12份原报告696/247580均经严格门禁，云报告的未跟踪环境目录/压缩包dirty事实保留。Windows首轮取消时限失败原job仅重试一次成功，旧失败不改。

恢复布局时只重施页面约束，不show/hide/raise；显式导航仍能按页适配，用户打开的可选dock覆盖继续保留。主题仅视图状态，不进入项目/F5/K1资格；草稿、Undo/Redo、结果/显示覆盖与真实任务身份不串改。N1只改变轴文字字体/配色，保留源箭头、轨迹、材料/透明度和选择含义。

Windows真实系统125/150、双层宽表滚动及反向、向导/浮动/快捷键、运行中200万事件完成、生产两次重启和正常退出；Linux独立X11三新皮肤、中文/N1/选择/4历史轨迹/旋转/恢复/正常退出。twm辅助exit1保留，无自有残留；WSLg RAIL限制不写成功。主审签收本轮范围并关闭J3，同时接受历史after图缺精确提交、旧状态前图及部分逐页八态归档不完备等非阻断证据限制，不称全人工矩阵。约一秒切换未越既定回归线，进一步提速后续安排，不新增前置工具。没有物理基准/真实云Agent批准结论。详见docs/verification/j3-final-20261104/README.md及独审逐动作记录。后续F2先三轮隔离实测和协议提案，既定用户协议选择前不改生产入口。


## 2026-11-04 F2受控多轮会话验收完成

最终产品864bc036、C++指纹e7de615d，正式云12报告708/255163严格通过，Windows125/150和Linux独立X11真实运行/取消/重放/退出验收完成。协议B版本化会话保留csh/批处理，按docs/会话协议.md维护；完整配置、几何、物理、线程修改新进程。重放结构预检在hello/初始化前，依赖粒子表与数值域的语义预检在初始化后/任何BeamOn前，必须ApplySourceEdit(apply=false)无副作用，整计划非法编辑不能先执行前面的run。ReplaySendOp判断真实ACK，不把服务继续布尔当成功。closing.steps_total含所有操作、steps_executed为完成run，GUI根据原因/实际退出/收据轮数判终态。固定构建/数据/随机初态/线程/顺序内比较；不承诺跨平台/线程数逐位一致或独立物理验证。原3b/fd47失败、作者临时bc8c及dirty3b/d378、最终864/e7报告不得混同。Linux辅助twm退出1与WSLg限制保留，不称全部子进程0。最终证据见verification/f2-final-20261104/README.md，后续E4。

## 2026-11-04 E4 文档收尾迁移（原文保留）

> E4-2 把下列**状态性旧文**从当前入口页迁到这里；原日期与原文不变，规则类内容留在规则文件，操作说明留在中文入门。E4-1 映射回执见 `docs/collab/outbox/20261104-e4-facts-map.md`。

### STATUS 旧“一句话定位”

## 一句话定位

2026-10-31：K1 可信实验工作流与配置导出已完成阶段验收，I1 已独立完成。第七产品冻结 `2914b39` 的 Windows 182/182、57181 个 v3 入口及官方 CI 548/548、133720 个入口保持原身份；资源路径 P1 已通过独审，`5644e1e` 永久回归补充在 Windows/Linux 分别 36/33 个入口通过严格门禁。产品字节未变，未新增物理或性能基准；已正常快进集成并推送至 `codex`。详见[验收证据](verification/k1-final-20261031/README.md)及[ROADMAP](ROADMAP.md)。

当前工作：2026-11-01 **I2 辅助安装与双平台交付、J1 可调整工作区已完成阶段验收**。安装计划、受校验获取、发布/取消/恢复/卸载及 runtime/SDK 流程通过 Windows/Linux 实际验证；停靠布局、主题及 3D 颜色/透明度控制通过组件、冻结桌面与 Windows 实窗验收，DeepSeek 已实际参与前端设计。最终测试提交 `6310969` 仅修三个测试，产品文件与 `5fe0a10` 相同；旧失败和未归因的历史偶发失败保留。详见[最终证据与边界](verification/i2-j1-final-20261101/README.md)。下一阶段为 J2/F8，空白创建、多源/物理组合等反馈按既定排期推进，AI 仍未接入。 验收提交`c3276e3`已正常快进并推送至`codex`，见[实际集成收据](verification/i2-j1-close-20261101/README.md)。

配置驱动、可复现、可验证的 Geant4 桌面工作台（C++17 后端 + PySide6 前端 + 场景包/基准/测试平台）。
当前是"有真实物理验证的 Beta"，不是 1.0：核心链路可用，大量高级能力仍是实验性，产品完成度低于工程纪律。

### STATUS 旧“当前计划入口”

## 当前计划入口（2026-10-29 编号整理）

统一工作项、排期波次、依赖、Q1 审查范围与提交节点均在 [ROADMAP](ROADMAP.md) 的“统一代号与排期”一节。本对话作为 **Q1 完整可靠性审查、修复与验收**的主负责人；隔壁审查作为独立证据来源，不必等它全部结束。已有反例按代码基线复用；Q1 已在冻结范围完成验收，见[最终报告](verification/q1-final-20261029/README.md)。

当前顺序：Q1（已完成）→ 2C（已完成）→ E6（已完成）→ F1（已完成）→ F4（已完成）→ F5（已完成）→ K1（已完成，I1 已完成）→ I2/J1（已完成）→ J2/F8 → L1/F2；J2 中实际依赖实体元数据的部分先满足 E7。其后科研波次 Q2/H2/H3、F3/F7，与 K2/L2 按依赖安排；H4–H9 和 M5 保留后续独立阶段。这是导航摘要，具体状态与默认顺序以 ROADMAP 为准。用户一次启动一个完整代号，阶段内的提交和专项测试由负责人连续推进。

2026-10-29 Q1已完成：九域审查、R01–R32闭合并交叉复核；验收代码 `8ecad66`。干净Windows **105 PASS / 0 FAIL / 0 SKIP**，83770个v3入口；旧同代98项基线79303，逐例/总数与原始日志门禁通过。Linux11.3.2/11.4.3真实CI各105（run40855144863），Windows/Ubuntu static+GUI各42（run40855144672），Windows实窗保存/生成/运行/取消/关窗通过。[完整收据](verification/q1-final-20261029/README.md)；旧失败证据保留，历史偏置结果须重跑，原生交互迁移显式csh。

### STATUS 旧“阶段状态（摘要）”

## 阶段状态（摘要，详表见 ROADMAP）

- A 核心功能、B 场景包与基准、C 向导/绘图/扫描、D 安装包、G 3D 预览：已完成。
- E 修复：E1（GUI 与后端规则一致）、E2（配置 schema）、E3（Linux CI，含 Geant4 11.3.2 / 11.4.3 版本矩阵）、E5（GUI 拆分）已完成（E3 见 ROADMAP 的“done for Linux”；M0 workflow 已由所有者启用并在 `402a9f2` 双平台全绿；11.2 未测）；E4 已做部分规范迁移和链接检查，仍需收尾；新增 E6/E7 的范围见 ROADMAP。
- F 优化：F6（实时运行进度）已完成，2026-10-28 追加可选 `sequence`（进程级单调、跨 run 不重置，GUI 拒绝重复/回退行；旧后端仍可解析），契约见 [docs/实时运行进度.md](实时运行进度.md)；F1 输出与来源已完成（见上方验收边界）；F4 校验定位已完成；F2 运行会话、F3 性能/tasking、F5 undo/autosave、F7 二维扫描、F8 GUI 收尾未做。
- H 增量：H1（径迹输出）已完成；H2–H9（过滤计分、平行世界、方差降低、光学、活化、DNA、体素体模、通用直方图）未做。
- M0 全模块 EffectiveConfig / 模块开关归已完成的2C；SolidRegistry 归 E7，仍未实现。M0–M5 是长期目标汇总，不与新工作项重复计算完成度。

### STATUS 旧“正在做 / 下一步（阶段1/2B/2C）”

## 正在做 / 下一步

阶段 1（文档与仓库卫生，进行中）：

1. 已完成：修文档里的反向错误（README 与中文使用手册中“LET/GDML/STL/自动合并未实现”的旧说法）；
2. 已完成：`STATUS.md` 单一入口 + 5 份过期快照归档 `docs/archive/`（含 [归档索引](archive/README.md)）；
3. 已完成：`_backup_git_*` 进 `.gitignore`、25 个本地分支推远端（CI 从零变为逐分支可触发）；
4. 已完成：`AGENTS.md` 48.5 KB → 33.5 KB（29 条日期条目全文迁入 `docs/agent-history.md`，只留索引）、`docs/Agent维护说明.md` 文档地图重写、新增 static 用例 `doc_links`（53 个 Markdown 文件 100 条相对链接全部可解析）；
5. 已完成：历史审计结论对照表 [docs/collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md](collab/outbox/20261028-0120-deepseek-legacy-audit-crosscheck.md)（`总体判断.md`、2026-10-03 现场审计、E2、F6、阶段 0 逐条判定为仍成立/已修复/部分成立/已过时，仍成立的 9 条按阶段归位）；
6. 已完成：报告加断言级计数与工作区/测试内容双哈希、默认报告目录改 `out/verification`、CI 把 skip 当失败（`--fail-on-skip` + `check_report_evidence.py` 门禁）；顺带修复 `.gitattributes` 让 checkout 换行改变源码指纹的真实缺陷；
7. 已完成：支持矩阵第 2–3 节每条功能标注证据类型（外部表 / 解析式 / 同源自洽 / 自测 / 未验证），第 1 节给出判定口径；
8. 已完成：E2-S1 六个 editor→writer 边界升级为 static 用例 `writer_boundary`；9 个零断言用例改写成 `assert` 表达（断言证据从 115305 增至 116133，零断言列表清空）。
9. 已完成：Astra 2026-10-28 审查的 6 条缺陷全部闭合（D-1 证据门禁可篡改绕过、D-2 日志摘要与磁盘字节不符、D-3 文档漂移、D-4 交互偏置拒绝只告警、D-5 材料交互无生命周期门禁、D-6 `ParseStrictDouble` 接受 inf/nan）。
10. 已完成：D-7（`scenarios/shielding_coating/analyze.py` 缺证据当零结果）闭合——运行事实不达标即退出码 3 且不写报告，统计文件用 `run_metadata.json` 的 `generated_files` 区分“被删”与“真零”，相空间跨轮次/越界为证据错误，报告新增 `evidence` 段，回归含五种反例。
11. 已完成：E3 Linux CI 在真实 Actions 上转绿（四 profile + 注解 + 篡改负向对照），并顺带修掉三个 CI-only 缺陷（job 级 `env` 上下文、conda Qt5 插件遮蔽 PySide6 Qt6 插件、公开仓库日志不可读）。

阶段 2（2B 场景已定为**屏蔽 shielding_coating**）：

- 2A：Linux + Geant4 11.3/11.4 CI（E3）——已完成（Actions 双版本矩阵绿，见上）；遗留 11.2 兼容性；
- 2B：屏蔽场景 GUI 端到端 + schema 驱动编辑器——**已完成（2026-10-28，见上节）**；
- 2C：完整 EffectiveConfig + 模块 off/auto/on（Astra 主导设计）——原 DSH 基线的**只读测绘**见 [docs/collab/outbox/20261028-2000-deepseek-effectiveconfig-survey.md](collab/outbox/20261028-2000-deepseek-effectiveconfig-survey.md)：
  现状（13 个 `effective_*` 标量、11 个来源字段、materials 六态、19 个 main_ini section、散落布尔开关、缺 `--dump-effective-config`）、
  六条缺口（无对象 ID、无 requested/resolved/applied 四元组、缺 BeginOfRun 快照、无 off/auto/on 语义、GUI 无结构化入口、验收只能数 353 字段），
  以及当时的切片建议与五个待 Astra 决定的问题。该测绘后的configured子集及最终完整2C已分别验收，见本页开头；不能再将当时“未写代码”的状态应用于当前隔离分支。
- 铁律：阶段 2 冻结新功能，目标是压低 `experimental` 比例，而不是扩大分母。

### GUI 快速入门旧 J2/F8 候选状态段（2026-11-02）

2026-11-02 J2/F8候选提供空白项目、内存材料/几何、命名多源和物理组合编辑，完整流程见[J2/F8说明](J2编辑覆盖与F8验收.md)。外部输入模式检查当前选定的主配置/宏，不因保留的生成模式编辑历史而拒绝；切回生成模式仍检查编辑来源，完整离线编辑包仍要求所有保留资源存在。跨页快捷键和Tab会在停靠区域布局完成后显露当前焦点及可容纳的完整标签/控件；切换焦点不会被旧显露任务抢回。正式阶段验收仍在进行。

### GUI 快速入门旧 F4 完成段（2026-10-30）

2026-10-30 F4 已完成：[验收与边界](verification/f4-final-20261030/README.md)。表格定位应看到确切单元格；源文件变化时只显示明确标记的历史快照。此状态不表示配置已运行或物理正确。

### GUI 快速入门文末历史段（运行判定/F6/2C/Q1/F1，原文）

# 运行结果判定（M0-3C4 工作区候选）

## 实时进度（F6）

运行控制台新增进度条，显示当前 run 的已处理/计划事件数、平均速率与预计剩余时间。初始化、零事件或旧后端未报告进度时显示未知；每轮重新计数。达到 100% 后仍可能在收尾或写出，不能代替下面的最终结果判定。停止或强制结束后保留最后观察进度并显示冻结；Windows 控制台程序不响应停止时可继续强制结束。ETA 只是本轮剩余事件的估算，不含后续轮次和不可预测的写出耗时。

协议及限制见 [实时运行进度](实时运行进度.md)。

## 最终结果

运行页会同时显示进程退出码和模拟结果。退出码为 0 不等于模拟成功：只有本次新生成的 `run_summary.txt` 证实后端和 macro 完成、至少执行一个 run、每轮计划事件全部完成且逐轮合计与摘要总数一致时才显示“模拟成功”。仅配置检查（dry-run）、交互会话结束但未运行、正常退出但无 run 会单独标记；停止、强制结束、摘要缺失或旧摘要不会被历史页误判为成功。历史页对旧版状态文件缺少摘要新鲜度证据的条目保守显示“结果未证实”。


### 2026-10-29：有效配置审查（2C 开发中）

新增配置阶段 Manager 子集导出与只读查看器，完整消费者、运行应用证据与模块三态仍未交付；不提升现有功能支持等级。契约见 [有效配置快照](EffectiveConfig.md)。


2026-10-29 Q1 结果与保存约定：有 `run_metadata.json` 的输出目录只自动读取它登记的本轮文件；旧worker文件不会混入统计。必需登记缺失、元数据清单损坏或已登记文件缺失会显示错误并清除旧显示；没有manifest的目录仍可按legacy读取，但明确未验证。复制结果目录按manifest原根重定位，不访问旧机器路径；合并计划建立后，来源模式、manifest或输入列表改变时须刷新计划后重新开始。这些检查不等于文件内容签名或物理验证。

保存项目采用同目录临时文件和原子替换，写出失败保留原项目。未来版本和无法识别的项目字段明确拒绝，避免重新保存时静默丢失；自动迁移仍在E6。扫描成功须有正事件数、每轮完成和可靠新摘要；关窗终止该窗口持有的进程。正常Python桌面GUI不依赖原生Geant4 UI；若外部INI主动设置interactive，请使用受审计的csh入口，裸UI执行会被拒绝。


2026-10-30 F1 候选：结果摘要与运行历史分别展示运行状态和输出字节身份。新来源扩展按当前目录中的登记文件逐个核对SHA-256及长度；哈希一致只表示相对于记录的文件字节一致，不证明来源认证、物理正确或运行成功。详情保留执行标识、构建身份与实际读取输入的历史记录；原输入后来移动或删除不抹掉记录，也不表示当前输入已核验。旧v1仍可读取，但警告缺少内容哈希。新扩展无效、内容不一致或登记文件缺失时拒绝自动分析，刷新清除旧结果。复制目录仅从新根读取，合并开始前重新核对字节；后处理文件不改写原始清单。此为候选行为，真实窗口和阶段验收以专项记录为准。


F1候选的“结果→概览”和运行历史选中项内嵌身份详情：分别查看构建、输入历史读取与输出文件身份，选中行后可点击复制或按Ctrl+C复制完整路径和SHA。原始JSON默认折叠。输入表是历史实际读取记录，不会为展示而重新读取原输入；元数据自身排除哈希避免循环自引用。错误刷新会清除旧身份表，未登记的额外文件仅不属于自动证据集合，不因此认定内容遭修改。


F1身份校验会在后台运行：开始刷新或切换目录时清除旧身份表，显示“正在校验输出哈希”；过时请求不会覆盖新选择。历史搬移后实际打开当前运行包的output，原快照路径仅作记录显示。同一次刷新复用该次已核验的快照，各次独立刷新及合并执行前仍重新计算内容哈希，不凭时间戳或长度相信旧结果。

## 2026-11-04 E4 规则索引瘦身迁移（原 AGENTS.md §0 历史条目，原文保留）

本段为 E4-2 首轮独审修正：AGENTS.md 只保留主题索引与实现规则，以下为原 §0
历史条目全文（含链接、日期、原失败与回归入口），未改写正文；链接按 docs/ 相对布局归一。

- 2026-11-04 F2已验收：冻结864bc036，协议B保留csh/批处理；重放结构预检与内核初始化后/BeamOn前只读语义预检分开，禁止预检修改SourceManager。closing的steps_total计全部操作、steps_executed计完成run；正常终态需核对实际退出和收据。详见docs/agent-history.md同日F2条目及docs/verification/f2-final-20261104/README.md。

- 2026-11-04 J3：本轮约定范围已验收并关闭，冻结92134da0；Windows125/150与独立X11代表性、云12报告696/247580及严格门禁完成。历史图身份/非逐页八态、WSLg与约一秒切换限制保留，不外推物理/云Agent验证；后续F2。详见docs/agent-history.md同日J3条目及docs/verification/j3-final-20261104/README.md。

- 2026-11-03 J3 独立审查响应：独立复验不同意关闭（`docs/collab/reviews/20261103-j3-closure-review.md`）；外观断言必须用 `theme.current_skin()`（无参读应用属性，传窗口会恒回退 B）；`reveal_current()` 不得隐藏既有停靠页，Results 页整宽由 `focus_analysis_view()` 负责；紧凑布局（<1400 逻辑像素）隐藏 AI 与 3D 预览两个可选 dock，外部面板入口是 View → Panels 而非命令面板；`paletteSearch` 边框用 `border_strong`；候选冻结与三 profile 基线在 `docs/verification/j3-close-20261103/`；J3 仍为未关闭。

- 2026-11-02 J3 第七阶段（作者交付，未验收）：Help 菜单的快捷键表由 `ShellMixin.shortcut_rows()` 提供、对话框由 `build_shortcut_dialog()` 构建（测试/截图用非阻塞版本，`show_shortcuts()` 才 exec）；关于文本由 `about_text()` 生成（含 GUI/PySide6/Qt 版本、应用根目录、后端路径），不要在别处重复拼这些事实。新增菜单项必须进 `i18n.ZH_CN` 与 `_set_language` 覆盖路径；导航 tooltip 与快捷键表、无障碍描述保持同一文案。回归 `gui_help_menu` 及 `gui_main_window`/`gui_command_palette`/`gui_theme_response`/`gui_j1_appearance`；证据 `docs/verification/j3-help-20261102/README.md`（5 例、211 断言）；J3 未关闭。
- 2026-11-02 J3 第六阶段（作者交付，未验收）：3D 模型树在 `gui/g4usim_gui/preview3d/model_tree.py`，从 `GeometryDocument` 构建，widget 侧只渲染与联动、不得自行推断父子关系；树节点与 3D 选中必须双向同步，过滤时保留命中节点的父链；打开 3D 标签自动 `refresh_3d_preview()` 的入口在 `_on_workspace_tab_changed`。回归 `gui_model_tree`（离屏只覆盖纯函数 21 断言，widget 联动需 Windows 平台直接跑 27 断言）及 `gui_3d_view`/`gui_config_editors`/`gui_workspace_layout`/`gui_main_window`/`gui_command_palette`/`gui_k1_panel`；证据 `docs/verification/j3-modeltree-20261102/README.md`（7 例、1965 断言）；J3 未关闭。
- 2026-11-02 J3 第五阶段（作者交付，未验收）：`WorkspacePageStack.reveal_current()` 离开停靠页时必须隐藏该页 dock（否则配置编辑器会在 Run Console/Results/Run History/Parameter Scans 继续占宽）；导航到 Results 页时 `WorkspaceLayout.focus_analysis_view()` 收起 3D 预览与 AI 面板并显示日志 dock。回归入口 `gui_workspace_layout`/`gui_main_window`/`gui_command_palette`/`gui_3d_view`/`gui_config_editors`/`gui_k1_panel`/`gui_k1_history_scope`；证据 `docs/verification/j3-analysis-docks-20261102/README.md`（7 例、2022 断言）；J3 未关闭。

- 2026-11-02 J3 第四阶段（作者交付，未验收）：`WorkspaceLayout.preset_for_page()` 按页面映射 configuration/running/analysis（0–4 / 5 / 6–8），`focus_current_page()` 只切停靠面板并 `reveal_current()`；View → Workspace layout 的 “Fit workspace to current page”（`Ctrl+Shift+L`、`workspaceFocusPage`）与命令面板 Actions 同名条目都走它；该动作不得自动触发、不得改页面内容/项目状态/运行状态，手动预设与隐藏面板必须继续生效。证据 `docs/verification/j3-focus-20261102/README.md`（7 个 GUI 用例、399 断言）；J3 未关闭。

2026-11-02 J3 第三阶段（作者交付，未验收）：3D 视图视点/投影控件用两行 `QGridLayout`（窄 dock 不再横向裁剪），图例 190→168、剖切滑块最小宽 80；3D 预览选项分行；配置 setup 面板最小宽 300、分栏 330/650；配置标签 padding 7/11；状态栏恢复提示单行 max 320；`QToolButton:focus` 用 `focus_ring`、侧栏 focus 用 `sidebar_hover`；`undo`/`redo` 图标由 `_refresh_icons` 统一着色、`transactions` 建完工具栏补刷一次。证据 `docs/verification/j3-panels-20261102/README.md`（gui 72/0/0、10227 断言）；J3 未关闭。

2026-11-02 J3 第二阶段（作者交付，未验收）：侧栏 `WORKFLOW`/`RUN & ANALYZE` 分组与选中轨道、页头面包屑、Ctrl+K 命令面板
  （`gui/g4usim_gui/widgets/command_palette.py`：Pages/Actions/Appearances 分组、标签严格匹配优先、Up/Down 跳过组标题、Enter 运行/Esc 关闭、
  选外观会切到所属明暗组）、状态栏 `Appearance: <皮肤名>`、菜单栏/编辑历史工具条/状态栏统一用皮肤浅表面；新增用例 `gui_command_palette`，
  完整 GUI profile 72/72、10227 断言通过。新增外观条目必须同时进 `_command_palette_entries()` 与 `gui_command_palette` 的分组计数，
  否则命令面板与测试不一致。证据 `docs/verification/j3-shell-20261102/README.md`；区域层级实窗改造/对比度实测/性能/独立复验仍未做。
- 2026-11-02 J3 第一阶段（作者交付，未验收）：外观改为 28 颜色角色 + 15 套皮肤注册表（历史 B/K/C + 纸墨/砂岩/苔原/石墨/霜蓝/高对比/午夜蓝/电路夜班/板岩/余烬/极光/夜视对比），注册表构建时把 muted/border/selection/focus 归一化到正文 4.5:1、边界与焦点 3:1；样式表 = 历史基座 + 新视觉层（`$token` 单遍替换），`View → Appearance` 按明暗分组、分别记忆 `appearance/light_skin`/`dark_skin`（旧 `light_palette` 仅 B/K 镜像），`_set_skin` 会切到该皮肤自己的明暗组；新增 static `theme_registry`（113 断言点）与 `check` 图标。**QSS 陷阱：`QMainWindow::separator` 不得设 `width/height`（1px 会在浮动态 dock + offscreen 下使 Qt 崩溃）；`QDockWidget > QWidget` 会命中内部标题容器，不要写。** 证据见 [第一阶段证据](verification/j3-theme-v1-20261102/README.md)。

- 2026-11-02 L1 本轮验收与交付：阶段签收 **本轮约定范围验收完成**；冻结246e4f6，Windows六profile308/183347、CI十二原报告662/228978，Windows安装显式attempt2且原失败保留。新Windows125/150仅受限原生，WSLg **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**；EE真实云／人工单对／只读恢复按原身份映射，不扩NL质量／提速／科学等级。完整操作合同见[同名历史](agent-history.md#2026-11-02-l1本轮验收与交付)与[最终证据](verification/l1-final-20261102/README.md)。

- 2026-11-02 L1 EE验收快照与原生布局后续候选：EE四本机／十二CI报告、真实云与受控恢复的限定证据分开；native150原失败保留、布局候选限定独审PASS，下一候选仍待，阶段未关闭，见[同名历史条目](agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选)。

- 2026-11-02 L1 路径显示 raw 修复候选：K1 生成包显示只回绑三条路径，不能重排非路径草稿或改变 F5/K1 资格；正常业务载入与 legacy 全量投影保持原行为。首候选失败与后续身份分开，见[同名历史条目](agent-history.md#2026-11-02-l1-路径显示-raw-修复候选)。

- 2026-11-02 L1 配置 Agent 实施候选：固定白名单、同计划新授权新任务、只读恢复及待正式验收边界，见[同名历史条目](agent-history.md#2026-11-02-l1-配置-agent-实施候选)与[L1说明](L1配置Agent.md)。

- 2026-11-02 J2/F8与E7本轮验收：测试／构建冻结2ec5b14；15/7注册元数据、真实平台接口、限定原生及docs-only身份合同见[同名历史条目](agent-history.md#2026-11-02-j2f8与e7本轮验收完成测试冻结2ec5b14)和[最终证据](verification/j2-f8-final-20261102/README.md)。旧失败／历史身份保留，不扩实体或科学等级。

- 2026-11-02 J2/F8第四修复候选：test-only接口、字节映射及未关闭边界见[同名历史条目](agent-history.md#2026-11-02-j2f8-第四修复候选18c5858平台测试接口与证据映射)。

- 2026-11-02 J2/F8第三修复候选：相关专项独审已完成，完整新候选验收待进行；2901f42本机已过范围不代表CI/原生整体通过；History三显式buddy/动态语言、QLayout类型递归、K1 policy规范身份与原拼写首尾guard的候选边界见 docs/agent-history.md 同名新条目。原失败与旧身份保留，未宣告阶段关闭。

- 2026-11-02 J2/F8候选：E7实体元数据、命名源/显式构造器替换与v8快照已接线；完整验收未关闭。修改前读 docs/agent-history.md 同日条目及 docs/J2编辑覆盖与F8验收.md，保持原source/运行/物理证据边界。

- 2026-11-02 J2/F8首轮验收修复：external与generated来源核验按实际输入模式分开，完整编辑包闭包保持；F8延迟显露只能服务仍当前的owned焦点。诊断code兼容/迁移、完整PyVista环境及首尾构建/报告身份门禁见同日历史条目，旧失败证据不得改写。

- 2026-11-01 I2/J1 已完成：6310969仅补测试，380产品文件与5fe0a10相同；Windows/Linux runtime/SDK、冻结工具、正式矩阵与26图/4次正常退出的原生范围已验。布局/3D覆盖不进F5/K1，安装与环境/运行/物理四事实分开。长短TEMP、独立Xerces helper和历史未归因失败边界见 `docs/agent-history.md` 的“I2/J1 最终验收与测试环境修订”及[最终证据](verification/i2-j1-final-20261101/README.md)。

- 2026-11-01 I2/J1 实施候选：安装、环境就绪和模拟成功分别核验；发布包版本与 Geant4 版本独立。冻结程序必须隔离宿主 DLL 搜索路径、核对源码及产物身份，不能凭自检可启动复用旧 GUI。布局沿用单实例与原业务所有者，外观仅视图状态。完整约定、旧失败与撤回见 `docs/agent-history.md` 的“I2/J1 桌面交付实施候选”；当前阶段是否关闭仍看 STATUS/ROADMAP。

- 2026-10-31 K1 验收关闭：资源路径 P1 与永久回归 P2 经独审和 Windows/Linux 正式单例关闭；5644e1e 仅追加回归，350 产品字节保持2914b39，原矩阵与原生证据按原身份沿用。晚变化链接仍须在 resolve 前拒绝；WSL /mnt/c 发布限制及旧失败不抹去。全文见 `docs/agent-history.md` 的“K1 资源路径 P1 与阶段验收关闭”，[最终证据](verification/k1-final-20261031/README.md)。

- 2026-10-31 K1 显示契约：成功且非陈旧的生成/运行命令投影覆盖 external 无 package；有效 launch 的实际 argv 优先，兼容计划命令不冒实际事实，目录未知不回填编辑 cwd。pending 按服务逐项显示，不联动其他层。全文见 `docs/agent-history.md`，回归 `smoke_k1_workflow.py`、`smoke_k1_panel.py`。

- 2026-10-31 K1 配置包搬移：匹配资源的四个路径草稿随规范路径搬移，非法草稿保留；staging 与 writer 收据先检查链接再比较规范路径。真实 GUI 下一动作、Windows 别名及旧异步 smoke 反例见 `docs/agent-history.md`；第三冻结失败和未完成独审不得用局部通过覆盖。

- 2026-10-31 K1 实施中：统一动作服务复用 F4/F5/runner，四层验证独立；输入变化及 Undo 后历史不得恢复当前资格。资源包重写路径后的哈希与原始读取证据分别保存；I1 只给环境事实。范围与验收见 `docs/collab/inbox/20261031-k1-execution.md`，不得以专项通过提前关闭 K1。
- 2026-10-31 K1 终态发布：finishing 上下文独占 EvidenceJob，迟到 finished 先保留退出事实再停止重复验证；成功落盘后一次 completed，存储失败显式 failed。后台返回时取消原因用 `experiment.cancelled`，未取消且输入变化才用 `experiment.inputs_changed`；不追改历史。启动前拒绝仍发 failed 进度、不造 finished。全文见 `docs/agent-history.md`，回归 `scripts/test_k1_terminal_publication.py`、`gui/smoke_tests/smoke_live_progress.py`；组件回归不代替真实取消复验。
- 2026-10-31 K1 深目录启动：`--working-directory` 必须在 Manager/数据发现前生效，失败不读写启动祖先；Windows manifest 和共用 `backend_launch` 只改变创建进程入口，不能改 F1/F4 路径身份或增加进程所有者。旧后端明确拒绝，不在错误目录重试。完整契约及首轮失败见 `docs/agent-history.md`；真实深目录回归 `scripts/test_backend_working_directory.py`。

- 2026-10-31 F5：已完成；冻结5c1eec5、原生5d身份映射及失败历史见[最终证据](verification/f5-final-20261031/README.md)。完整契约仍在docs/agent-history.md及配置撤销与恢复；稀疏worker去重N仅为master完整N的下界，空表头N未知。后续分派按[模型规则](collab/MODEL-POLICY.md)，不让常规子任务继承最高推理档。下方旧状态按原日期理解。

- 2026-10-30 F5候选：主编辑快照/事务统一Undo/Redo，v7保留材料/几何及raw drafts，源阻断从捕获原文重建；旧包恢复仍遵守E6当前包语义。每会话恢复OS锁、单调revision和已退役屏障；发布后清理不能反转保存成功。双投影失败须冻结，不能保存坏view。改相关入口前读 `docs/agent-history.md` 的F5条目及 `docs/配置撤销与恢复.md`；完整验收状态看STATUS/ROADMAP。

- 2026-10-30 F4阶段关闭记录（已完成）：产品7d718d038a00d89995ea773b4772764116b620c3，正式矩阵/原生退出/独立审查见[最终证据](verification/f4-final-20261030/README.md)。保留下方候选与失败契约；单元格可见性、旧快照拒绝、逻辑文本与原始字节身份分开。全文追加到docs/agent-history.md；F5未启动。

- 2026-10-30 F4候选：诊断身份、字段和来源须由规则生产，不能解析翻译文本猜位置；旧文本报告与blocking保持，重复源行保留独立记录。定位不修改模型，编辑/重载/切项目后旧快照失效；源内容只读且区分逻辑文本SHA与F1原始字节SHA。完整契约见 `docs/agent-history.md` 同日F4条目及 `docs/结构化诊断与定位.md`；阶段验收以ROADMAP为准。

- 2026-10-30 F1阶段关闭：产品f176d0e自动矩阵及14次Windows原生观察/正常退出、独立复核通过；GUI ede037f仅文档差异，不能伪改构建commit相等。合成历史行仍为结果未证实，07图像与滞后UIA分开解释；原自动归档pending保持原字节。完整契约见agent-history同日关闭条目与 `docs/verification/f1-visible-20261030/README.md`。
- 2026-10-30 F1自动矩阵历史节点：产品f176d0e，Windows143/48511v3及E6基线、Linux双版本各143、M0双OS各64通过；自动归档原件保持。该节点实窗pending、阶段未关闭；最终状态见上条，不得追改历史收据。详情见agent-history同日自动归档条目及 `docs/verification/f1-automated-20261030/README.md`。

- 2026-10-30 F1 GDML 收尾：原生句柄取得后的缓冲分配必须在关闭保护范围内；测试线程异常须转回调用线程，仅 `std::bad_alloc`/Xerces `OutOfMemoryException` 作为预期分配拒绝，全局测试适配器须异常安全恢复。Windows通过不能覆盖Linux异常族差异。详情见agent-history同日第二轮条目。

- 2026-10-30 F1首轮回归：后台加载时预设图表必须绑定当前目录/请求序号，完成后再选择；未知key必须清空旧图并明确报错，不能仅加等待掩盖默认图。Qt回传显式排队，旧请求完成不得覆盖新请求。Windows全量显式传实际 `G4USIM_GEANT4_DATA`，沿用E6普通权限路径，不更改系统链接权限。详见agent-history同日F1首轮失败条目。

- 2026-10-30 F1候选：来源扩展严格区分读取/接受/运行/字节一致；不得重读源文件伪造历史hash。产物显式scope，metadata唯一自排除，新协议缺损不得降级；auto仅显式选择、默认CSV不变。GUI每次新动作后台重验，搬移锚定当前根。完整契约及候选验收边界见 `docs/agent-history.md` 同日F1条目与 `docs/输出身份与来源.md`。

- 2026-10-30 E6阶段关闭：实现a779634的自动矩阵与12状态实窗补验通过；合成Inspect命令检查、真实运行与原生截图观察分开计证，旧自动归档pending不得追改。完整范围与首个GUI host退出码unknown边界见 `docs/agent-history.md` 同日“E6 实窗补验与阶段关闭”及 `docs/verification/e6-visible-20261030/README.md`。

- 2026-10-30 E6候选：主INI版本标记与独立几何版本严格分开，版本拒绝须保持旧reader；迁移副本源SHA复核/exclusive发布，发布后清理失败仅warning；旧项目已知兼容、未知/类型冲突拒绝；schema394项，GUI编辑范围不扩。改动前读 `docs/agent-history.md` 同日E6条目与 `docs/配置兼容与迁移.md`，阶段证据以STATUS/ROADMAP为准。

- 2026-10-29 完整 2C 回归衔接：有效配置文件按 `g4usim_effective_config_v1` 登记；dry-run 配置证据不是模拟执行。故障注入的 `_t0` 仅用于单 worker 确定性覆盖，多 worker 使用 `_any_worker` 在实际回调原子竞争一次，不能假定 worker0 分到事件。稀疏 ROOT 总 N 必须来自可靠 metadata，不能假定所有 worker 都工作。全文及正反例见 `docs/agent-history.md` 的“完整 2C 首轮全量回归衔接”。

- 2026-10-29 Q1 运行边界：Dose 用扣 daughter 的本体质量；GDML SD 保留真实对象，无法表达的 bias 名碰撞和持久 touchable 路径歧义须拒绝；材料解析/实际构造都检查数值及版本壳层范围；局部场最近显式祖先、冲突在 master 拒绝；延迟 GPS 按真实源身份管理，pending 动态/别名命令必须拒绝；SD 回调异常锁存并中止。更改这些路径前读 `docs/agent-history.md` 的 Q1 几何、材料、源与场条目及其回归。

- 2026-10-29 Q1 数值与统计口径：非有限值/事件矩/worker 合并溢出须锁存失败，不限幅伪造结果；仅 ROOT 也检查 master mesh。scorer/mesh CSV v2 追加估计方法与可用状态，N<2/零分母/零总量不能显示零误差条；ROOT 稀疏行不提供完整 N。保持原近似公式，按事件归一化不得标为按初级粒子；LET 比值不得再除 N，网格投影无协方差不得画合成误差。全文与回归见 `docs/agent-history.md` 的 Q1 条目。

- 2026-10-29 R-01/R-02 失败证据：csh 中配置后 `setMainConfig` 拒绝必须登记 app 失败、停止后续输入并非零退出；不实现热重载。
  metadata 打开/写入/关闭失败锁存 `run_metadata_open/write/close`，可写文本摘要纠正为 failed，失败 JSON 不列入产物；
  `summary_write_status=completed` 仅指文本摘要成功关闭，不等于 JSON/模拟成功。回归 `test_interactive_commands.py`、`test_run_summary.py`；全文见 `docs/agent-history.md`。

- 2026-10-29 历史2C配置快照子集：`Config/EffectiveConfig` 区分缺失值与显式 null，事务拒绝不得改变 revision；
  `--dump-effective-config <新文件|->` 只 Configure + preflight，不执行 macro/事件、不创建运行输出目录，拒绝覆盖已有文件（含硬链接）。
  该次验收仅配置阶段Manager子集；命名源/相空间源不导出旧单源缓存，非mono不导出mono energy。其历史范围不扩大；当前完整2C见文末验收索引，配置值仍不能直接证明内核应用。
  回归 `test_effective_config_model.py`、`test_effective_config_export.py`、`smoke_effective_config.py`；全文见 `docs/agent-history.md`。

2026-10-19 → 2026-10-27 的 29 条实施契约全文（含文件路径、行号、反例与回归入口）在 [docs/agent-history.md](agent-history.md)。下表只列**仍然有效的操作规则**；改动相关模块前必须先读对应历史条目全文，只读索引不足以动手。新增条目：全文追加到 `docs/agent-history.md`，本表加一行，不要再在本文件堆长段落。

- 2026-10-28 Geant4 11.4 支持与版本矩阵：`src/Core/Geant4DataLocator.cc` 的数据集表按 `G4VERSION_NUMBER` 分段，新增
  `>= 1140 && < 1150` 分支（12 个数据集，前 5 个 required）；升级 Geant4 小版本必须同步这张表，否则构建期 `#error`。
  11.4 的构建门槛是 expat ≥ 2.8.5、zlib ≥ 1.3.2、freetype ≥ 2.14.3（Ubuntu 24.04 的系统库都不够），CMake 必须显式传
  `-DEXPAT_INCLUDE_DIR/-DEXPAT_LIBRARY/-DZLIB_INCLUDE_DIR/-DZLIB_LIBRARY/-DFREETYPE_INCLUDE_DIRS/-DFREETYPE_LIBRARY`
  指向安装前缀；`.github/workflows/linux-geant4.yml` 用 `matrix.geant4: ['11.3.2', '11.4.3']` 双版本构建，只有 11.4 leg 传这些参数。
  测试脚本不得断言 Geant4 版本相关的字面量：数据文件夹从 `--check-geant4-data` 的 discovery 取（`datasets[0].folder`），
  激发态核名用数值容差匹配（11.3 `Ni60[2505.753]` vs 11.4 `Ni60[2505.75300]` 只是格式化差异），不得按字符串精确相等。
  回归 `scripts/test_geant4_data_locator.py`、`scripts/test_physics_a6.py`、`scripts/test_gps_sources.py`；
  环境细节见 [docs/Linux构建与验证.md](Linux构建与验证.md) §8。
- 2026-10-28 F6 进度协议 `sequence`：`src/Actions/RunProgress.cc` 的 `Emit()` 在 `run_id` 后写进程级单调 `sequence`
  （只在 telemetry mutex 下自增，`Begin()` 不重置，跨 run 递增）；`gui/g4usim_gui/core/run_progress.py` 的 `ProgressParser` 必须在字段出现时
  要求非负整数且严格递增、重复或回退即丢弃，字段缺失时保持旧行为（旧后端仍可解析）。该字段只是顺序证据，不得用来判定模拟成功或物理完整。
  回归 `gui/smoke_tests/smoke_live_progress.py`（重复/回退/非整数/缺失四类断言）与 `scripts/test_live_progress.py`（所有真实消息严格递增、跨 run 单调）；
  契约见 [docs/实时运行进度.md](实时运行进度.md)。
- 2026-10-28 2B 屏蔽/涂层场景 GUI 端到端：场景页 `gui/g4usim_gui/widgets/scenario_page.py` 与 headless 驱动
  `gui/g4usim_gui/core/scenario_shielding.py` 只能调用 `scenario_model.render()/generate()` 与 `analyze.analyze(output_dir)`，
  不得在 GUI 里拼 INI、重算 TID/DDD 或把缺证据写成零；生成前必须三层校验（字段解析 → `problems()` → `config_schema`），
  运行后必须核对 `run_summary.txt` 的 `status`/完成事件数并显示证据列与 NIEL 表 sha256；新增页面要同步
  `gui/smoke_tests/smoke_main_window_ui.py` 的页数/导航索引断言与 `core/i18n.py` 的 `ZH_CN`。`make_scenario.py` 必须继续导出
  `CUSTOM`/`ENVIRONMENT`/`NIST_DENSITY`/`UNITS`/`length_mm`/`density`/`pore_centres`/`spectrum_from_integral_flux`/`spectrum_points`
  （兄弟场景生成器从它导入，漏掉会在 Linux CI 的 backend profile 暴露）。回归 `scripts/test_shielding_scenario_model.py`、
  `scripts/test_scenario_shielding_core.py`、`gui/smoke_tests/smoke_scenario_page.py`、`gui/smoke_tests/smoke_scenario_backend.py`；
  新增后端/集成测试必须读 `G4USIM_EXE`（runner 注入；`--executable` 指向 Linux `build_linux/G4UniversalSim`），
  不得写死 `build_vs2026` 或盘符路径——static 用例 `platform_paths` 会检查。  契约见 `docs/屏蔽涂层场景端到端.md`。
- 2026-10-28 D-7 屏蔽场景证据语义：`scenarios/shielding_coating/analyze.py` 不得把缺证据当零结果——运行事实（`status`/`summary_write_status`/`output_failure_status`/`run_count`/`completed_events == planned_events > 0`）不满足即退出码 3 且不写报告；统计文件用 `run_metadata.json`（`schema = run_metadata_json_v1`）的 `generated_files` 区分"被删"（退出码 3）与"这一轮确实没统计"（按零报告但带 `evidence = no_statistics_file_zero_deposition`）；相空间缺失/为空/跨轮次/事件号超出完成事件数为证据错误；报告新增 `evidence` 段。回归 `scripts/test_shielding_coating.py` 覆盖五种反例（删统计文件、失败摘要、零事件、陈旧相空间、真零沉积）。全文见 `docs/agent-history.md`。

- 2026-10-28 命令失败传播：`/AIHL/biasing/*` 修改类命令在交互会话里被拒绝时必须计入交互失败（`interactive_command_failure_kind = biasing`）、停止会话、写 `status=failed` 并非零退出，不得只 `JustWarning` 后继续跑未偏置物理；`/AIHL/material/*` 的 9 个修改命令只允许 `PreInit`（`print`/`list` 只读不受限），初始化后调用由 Geant4 拒绝并让会话失败（`geant4_illegal_application_state`），batch 的 `main.cc` 守卫保留为纵深防御；`ParseStrictDouble` 拒绝 `inf`/`nan`/溢出值（`Config value '<v>' is not a finite double`），数值配置字段不得以非有限值进入偏置权重或可视化属性。回归 `scripts/test_interactive_commands.py`（biasing/material 两个新用例）、`scripts/test_config_value_finiteness.py`。
- 2026-10-28 证据门禁自洽性：`scripts/check_report_evidence.py` 必须校验逐用例断言 ≥1、`exit_code == 0`、逐项求和与 `assertions_executed_total` 一致、`cases_with_zero_assertions`/`cases_with_assertion_counts` 与实际记录一致、`log_sha256` 与实际日志字节一致，发布报告不得含 fail/skip；日志与报告用 `write_bytes` 写 UTF-8/LF、摘要对落盘字节计算（`log_digest_algorithm = sha256_raw_bytes_lf_v2`），不得对内存字符串算摘要；归档旧报告只能加 `--allow-legacy-digest`/`--allow-legacy-probe` 复核，不得追改或用新口径冒充；CI 的 static/gui 各自跑完分别过门禁。回归 `scripts/test_report_evidence.py`。
- 2026-10-28 E3 Linux CI：`.github/workflows/linux-geant4.yml` 在真实 GitHub Actions 上转绿（`a5970ff`，`codex` run 40634469313 与 roadmap run 40634465977），`ubuntu-24.04` + conda-forge Geant4 11.3.2 上 static / offscreen GUI / backend / integration 四个 profile 全部通过并各自过证据门禁，随后用篡改副本做负向对照——引用 CI 绿时必须给 run id 与提交，不得用“workflow 已写”或“本机 WSL 等价拓扑”冒充。三条硬约束：①job 级 `env` 不能用 `${{ runner.temp }}` 等非允许上下文（workflow 校验阶段就会零 job，先用 `actionlint` 查）；②conda 前缀下必须把 `QT_PLUGIN_PATH` 指向 PySide6 自带的 `Qt/plugins`，否则 Qt6 找不到 offscreen 插件（`qt.qpa.plugin: ... in ""`），GUI 用例全灭；③公开仓库的 Actions 日志需登录，失败用例由 `scripts/ci_annotate_failures.py` 发成公开的 `::error`/`::warning` 注解（workflow 中 `if: failure()`），它只是日志的替代品、不是完整日志。另：`m0-static-gui.yml` 仍是 `disabled_manually`（需仓库所有者启用；历史 GUI 步骤失败原因待日志），Geant4 11.2/11.4 矩阵未开始；本机修掉的两个 GCC-only 三目缺陷、PySide6 退出 `SIGSEGV` 与 `scripts/test_geant4_data_locator.py` 的数据集目录推导规则继续有效。全文见 `docs/agent-history.md`。
- 2026-10-28 测试平台报告 v2：每个用例经 `tools/test_assert_probe.py` 记录已执行 `assert` 数（helper 必须用 `assert` 表达；退出 0 但无 `G4USIM_ASSERTS=` marker 判 fail）；`report.json` v2 带 `tests_content_fingerprint`（scripts/tools/gui smoke/config/scenarios/schema/macros/test，哈希前归一 CRLF）与逐用例 `log_sha256`；`scripts/check_report_evidence.py` 是 CI 证据门禁，`--fail-on-skip` 不得让 skip 冒充绿色；探针 `settrace_assert_lines_v2` 同时跟踪脚本启动的线程（worker pool 内的 `assert` 也计数，但脚本运行前已存在的线程不计）；用 `raise AssertionError` 或收集式 `return 1` 表达的判定不计入断言数，必须改成 `assert`；被原始字节哈希的输入固定 `text eol=lf`。阶段 1b 起 79 个用例全部报告非零断言（`cases_with_zero_assertions=[]`），验收阈值是断言总数不下降且该列表为空；跨线程逐项判定可以先收集再在主线程 `assert not problems` 聚合，但聚合点以外的逐项判定不计入断言数；E2-S1 的六个 editor→writer 边界是 static 用例 `writer_boundary`，基准脚本的断言必须放在 `write_report()` 之后，不得在逐基准循环内提前退出。
- 2026-10-27 B1 位移损伤粒子名：`[scoring.displacement]` 键按 `G4ParticleTable` 大小写不敏感解析为规范名，在 `BeginRun`（首个事件前）校验（配置期粒子表为空）；未知名字报主 INI 文件、行号与候选后失败，不得静默让 DDD 恒为 0；回归 `scripts/test_displacement_damage.py`。
- 2026-10-27 B2/B3/B4：主 INI 重复 section/键只告警 `[ConfigWarning] duplicate declaration` 并写摘要 `config_duplicate_count`，后值生效、不得改成拒绝；敏感探测器按配置名创建（禁硬编码 `AIHLParticleSD`）；`enableSD`/`setSDName`/`setSeed` 仅 `PreInit`，初始化后必须失败而非改缓存；回归 `test_config_duplicate_declarations.py`、`test_command_state_gating.py`。
- 2026-10-27 F6：`Actions/RunProgress` 输出 `[G4USimProgress] ` + `g4usim_progress_v1` JSON，约 0.5 s 限频，终值取 `G4Run::GetNumberOfEvent()`；零事件不补造消息，进度不替代 `run_result` 判定；契约 `docs/实时运行进度.md`、回归 `test_live_progress.py`。
- 2026-10-26 E2原验收353个字段；2C增加modules四项，E6候选增加field/biasing及主版本标记37项，共394。改描述/默认/别名/范围必须跑 `scripts/generate_config_schema.py`，C++ 表、Python 数据、矩阵第 5 节与覆盖清单禁手改；macro/CLI和辅助文件仍用专用解析器，不把字段登记当物理验证。回归 `test_config_schema.py`、`test_config_schema_context.py`、`test_field_biasing_schema.py`。
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

- 2026-10-29 Q1 R25–R30：偏置须worker TLS私有算符、真实绑定与逐run/thread完整EndRun收据，master挂接不证明运行；派生XS溢出/下溢锁存失败。RNG命令须语义守卫，setSeeds 2–99非零long、safe restore仅受支持格式，不能以原生返回0确认忽略命令。目录后处理以metadata名单为准并支持复制重定位，legacy明确未验证；原生mergeHistograms有metadata时只允许显式输入。v3断言探针不计表达式frame，旧报告不改、跨probe不比较；ParticleHit权重必须步前，phase_space边界权重保持。已有run后拒绝会重置MT主线程run ID的内核重初始化，偏置自动Initialize只做首次；普通多run须保留master/worker相同ID。完整契约及回归见docs/agent-history.md同日条目。

- 2026-10-29 Q1 R32：交互执行必须显式 `--ui --ui-session csh`；裸 `--ui` 或 INI interactive 未选 csh 在 macro 执行前拒绝（dry-run 例外），不能恢复未经审计的 G4UIExecutive 旁路。Python 桌面 GUI 不依赖此入口。R31 极值测试不得把工作量差当作 worker 分配证明，须记录实际溢出捕获阶段。全文见 `docs/agent-history.md`。

## 2026-11-04 E4 规则索引瘦身迁移（原 gui/AGENTS.md 历史条目，原文保留）

本段为 E4-2 首轮独审修正：gui/AGENTS.md 只保留索引与现行 GUI 规则，以下为原历史条目全文，
未改写正文；链接按 docs/ 相对布局归一。

Linux原生通道补充（主审已签收）：main已实际操作独立真实X11/xcb桌面，一次固定HTTP计划passed，操作观察时曾停在awaiting_approval、0事件；随后在观察期间触及300秒预算，整任务保留failed／agent.task_timeout，不称整任务成功。原host exit0、slot_released=true、host与显示服务两组remaining_owned均空、HTTP已关闭；显示辅助子进程退出码[0,1,0]（twm非零保留），不能写全部子进程exit0；代表性原生签收结果为 **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。WSLg RAIL任务栏无法展开，第三次host退出且0请求，原失败保留，绝不称该通道成功。Ubuntu实际系统安装x11-xkb-utils，其它本次依赖保持隔离OUT前缀；具体包版本／SHA及安装收据见最终证据，不把早期准备收据system_installs=0外推到之后。

2026-11-02 L1本轮验收：阶段签收 **本轮约定范围验收完成**，WSLg **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。冻结246e4f6；真实六本机／十二CI与安装重试、两档有限原生见[最终证据](verification/l1-final-20261102/README.md)和[完整历史](agent-history.md#2026-11-02-l1本轮验收与交付)。原F5／K1所有者不变；恢复只查询旧身份不重发、不恢复授权／当前资格，默认evaluate仅完成性。已有EE云任务与一对操作者记录不冒新native／模型质量／提速；图像/UIA永久local-only。原日期候选规则保留。

2026-11-02 L1 AI布局后续候选：52px导致AI全控件不可读是必须修复的新P2，不以旧F6窄边界豁免。OUT候选仅panel按当前文字／样式计算两列最小宽度及footer inset／reflow，不改workspace／core／F5／K1或翻译；125%／150%各1216组件入口与原产品负向分别保留，候选已收限定独审PASS并由main精确apply两path；按当前focused-target及可容纳joint合同核验，retained125非焦点右列可裁剪、不保证全footer同时同屏；新候选完整验收及新native仍待。见[候选历史](agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选)。

2026-11-02 L1 路径显示 raw 修复候选：`ProjectPage.show_generated_paths` 仅回显 config/macro/output 三条路径，实际 K1 display binder 不得为显示刷新其它控件原文、revision 或验证资格；正常业务载入和 legacy 全量投影仍走原 `set_project`。原 D1 五域任务失败、窄修及后续待验身份分别计证，见[候选历史](agent-history.md#2026-11-02-l1-路径显示-raw-修复候选)。

2026-11-02 L1配置Agent实施候选：只写既有体积/单能point固定方向源/运行/reference物理/计分的通用字段白名单，读取范围来自UI捕获上下文。默认仅规划，用户审阅差异后以当前新授权批准同plan，`approve_with_authorization`复核同快照并新建task，旧task取消留史、原授权不改、reason记reviewed_from，不重调模型；恢复实例不得借此提权，只查旧operation/run/record并只读显示，执行须新prompt新task。权限不足停步，事务/runner仍归F5/K1，取消/关闭不得误停其它所有者。密钥不落任务/项目/日志，系统存储缺失明确拒绝；本地仅兼容协议，不附权重或宣称其质量。核心专项独审已过但目前只有旧2ec EXE开发链与真实云模型任务集02，新候选重新构建/正式矩阵/CI/实窗待验，默认evaluate仅完成性，非物理比较。完整接口见[L1说明](L1配置Agent.md)与[候选历史](agent-history.md#2026-11-02-l1-配置-agent-实施候选)；下方J2历史字节保留。

2026-11-02 J2/F8与E7本轮约定验收完成：测试冻结2ec5b14，后续仅docs/evidence；History真实Label/buddy/provider、焦点/事务/资源及15/7元数据约定见[最终历史条目](agent-history.md#2026-11-02-j2f8与e7本轮验收完成测试冻结2ec5b14)和[最终证据](verification/j2-f8-final-20261102/README.md)。18c三档映射与2ec125补验分开，文件审不冒视觉；旧dated候选原文保留，不扩大科学等级。

2026-11-02 J2/F8第三修复候选：相关专项独审已完成，完整新候选验收待进行；History只用三个明确buddy及既有语言刷新链，真实QLayout才可递归count/itemAt；F6窄dock界限不修、不放宽可容纳joint判据。K1 policy final-v1专项独审已通过603入口，完整新候选验收仍待进行；原拼写安全检查不得被canonical匹配替代。详见 ../docs/agent-history.md 同名条目；2901f42旧raw不改，新修复三档原生补验仍待完成。

2026-11-02 J2/F8候选：高级详情原文使用原F5模型/事务，按当前实体与字段定位F4诊断；无源恢复不清空，已导入来源丢失不洗白。v7完整快照仅枚举迁移至v8，离线完整编辑包闭合休眠资源。修改前读 ../docs/agent-history.md 同日条目与 ../docs/J2编辑覆盖与F8验收.md；尚未正式验收。

2026-11-02 J2/F8第二候选：external Inspect不把休眠generated编辑来源当实际输入，但generated来源检查及完整编辑包闭包不变；焦点延迟显露须绑定仍有效、当前、owned控件，新焦点/关闭取消旧任务。诊断code迁移须按结构化事实及明确文档，旧JSON保持原身份。详见同日历史“首轮验收修复”，原失败报告不得改绿。

2026-11-01 I2/J1 已完成约定验收：本机停靠/主题、3D会话覆盖、代表性DPI与重启/运行中切换已实际检查，未做物理跨屏/热插拔。安装后只追加候选并重新发现，布局不改F5/K1或创建第二runner；源码/冻结身份及关闭所有权约束保留。安装GUI测试的临时根须规范化后与I1返回路径比较，不能放宽候选集合或增加等待掩盖差异。详见 `../docs/agent-history.md` 同日最终条目及[最终证据](verification/i2-j1-final-20261101/README.md)；下方候选段保留历史时点。

2026-11-01 I2/J1 候选：安装完成只追加候选并重新执行 I1 发现，不自动选中或运行；自动候选与安装补充候选分开保存。工作区复用原编辑器/runner/实验服务，布局和主题不进入 F5/K1 项目状态。自检须尊重 close 被业务收尾拒绝的事实，不强制析构仍活动的窗口，也不能改默认历史目录来掩盖关闭竞态。完整说明见 `../docs/agent-history.md` 的“I2/J1 桌面交付实施候选”；尚不宣称阶段验收完成。

2026-10-31 K1 已完成阶段验收：资源路径 P1 与永久回归 P2 已独审关闭；5644e1e 新增精确晚变化测试，产品保持2914b39，原生证据沿原身份映射且保留勘误。详见 `../docs/agent-history.md` 的“K1 资源路径 P1 与阶段验收关闭”及[最终证据](verification/k1-final-20261031/README.md)；下方实施中/未关闭条目按历史节点理解。

2026-10-31 K1 实施中：主实验入口组合现有 EditSession、G4USimRunner、F4 diagnostics 与 package writer，不能另建事务/进程所有者。验证四层分别显示，初始化和真实事件必须有各自证据；环境选择不触发模拟，导入包不自动继承历史通过。DeepSeek 面板交付及修复须分开署实，离屏/实窗/真实模拟分别验收。完整契约见 `../docs/collab/inbox/20261031-k1-execution.md`；当前不宣称阶段完成。

2026-10-31 F5：已完成；冻结5c1eec5、原生5d身份映射及失败历史见[最终证据](verification/f5-final-20261031/README.md)。完整契约仍在docs/agent-history.md及配置撤销与恢复；稀疏worker去重N仅为master完整N的下界，空表头N未知。后续分派按[模型规则](collab/MODEL-POLICY.md)，不让常规子任务继承最高推理档。下方旧状态按原日期理解。

2026-10-30 F5候选：Project/Configuration共用完整事务，raw非法草稿必须保留并正常阻断Generate；不能由get_project同步清空。普通项目v7恢复完整编辑内容，历史包仍从当前包材料/几何重建。Undo/恢复使包与F4诊断身份失效，不恢复旧运行成功；自动保存独立于普通保存。投影及回滚双失败需冻结保存/生成/运行并保留最后可证实快照。测试必须显式隔离recovery/history，产品不得按offscreen旁路交互。详见 `../docs/配置撤销与恢复.md` 和agent-history；下方F4“F5未启动”仅是旧关闭时记录。

2026-10-30 F4阶段关闭记录（已完成）：产品 `7d718d038a00d89995ea773b4772764116b620c3`；Windows 152/152、49913 个 v3 入口与 F1 原始143/48511同代基线门禁；Linux11.3.2 为 152 项、11.4.3 为 152 项（run 41056994075），M0 Windows 为 72 项、Ubuntu 为 72 项（run 41056993987）。CI实际提交 `a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`，与产品的关系见[提交身份映射](verification/f4-final-20261030/identity/identity-map.json)。Windows原生 13 态、19 次实际观察与进程退出 0；[最终证据](verification/f4-final-20261030/README.md)，[独立审查](collab/reviews/20261030-astra-f4-close-review.md)。原生观察须使用产品Fusion和主题初始化；QA生命周期修正不冒充产品修复。保留下方旧候选原文，F5未启动。

2026-10-30 F4候选：`core/diagnostics` 是统一结构，producer记录 code/editor/collection/row/field/source，不能从翻译报错反推。导航先检查当前快照和完整目标，不得改业务值或dirty；旧报告不可重绑定到新项目。无控件/源身份/完整预览范围就明确拒绝，源文本只能只读。瞬态记录不进入dataclass持久快照；Project与Config跨页也须失效守卫。运行包保留txt并写diagnostics v1 JSON。全文见 `../docs/结构化诊断与定位.md`，此条不宣称完整验收。

2026-10-30 F1异步预设图：OutputPage.show_plot返回true可表示已排队，并不证明图已显示；意图绑定目录和EvidenceJob请求序号，过期完成丢弃，同根refresh保留选择。未知key在ready和queued两路径都清旧图并报错。Qt回传显式QueuedConnection；示例入口不能重复刷新丢失请求。测试等真实任务完成并断言预设dataset/current_plot，不能只加sleep或接受默认第一图。

2026-10-30 F1候选：output/provenance统一严格校验新扩展，旧记录明确unverified；历史输入hash不代表当前源文件复核。当前结果根是唯一自动读取锚点，历史快照路径仅作记录。运行与文件身份分别显示。身份SHA和历史扫描后台执行，新请求/关窗取消且拒绝过期发布；一次操作内复用、下一动作fresh SHA、Merge执行前强制fresh，不用mtime缓存。父窗口接受关闭也须清理嵌入页任务，关闭被ignore不能永久禁用页面。见 `../docs/输出身份与来源.md` 与agent-history；本条不宣称阶段完整验收。

2026-10-30 E6阶段已关闭：自动回归与Windows实窗补验见 `../docs/verification/e6-visible-20261030/README.md`；下方候选条目保留实现契约，不能把历史pending或合成Inspect当当前验收结论。

2026-10-30 E6 Qt空数据回归：当前Linux Python3.11/PySide6 6.12缺失combo UserRole读取有实证引用损耗，项目标准模型的空数据读取使用widgets/qt_data.combo_data；保持root/column和0/False/空字符串语义。不得用os._exit、忽略非零退出或补造None引用绕过；原GUI导入393断言全部保留。诊断和适用边界见 `../docs/agent-history.md` 的“E6 第二轮平台失败与 Qt 空数据读取”，正式回归smoke_qt_combo_data与smoke_project_import_projection。

2026-10-30 E6候选：迁移副本由core计划/发布，窗口不重写格式规则。未知/冲突/重复JSON/非有限/不合法类型拒绝；旧项目仍可按已知兼容规则打开，不强制旧版只读。显式editor不能因空锚点被整对象默认重置；原始JSON位置双别名冲突拒绝，缺失单别名可派生。导入发布前按实际控件范围检查整数，禁止静默限幅；空选项明确显示空，未知选项保留。不得将GUI范围升级为后端物理限制。Recent/Snapshot错误保持warning，普通Open为critical。主INI新副本限同目录；几何资源保持原目标，不自动启source-copy或解除J2编辑blocker。已有目标/链接绝不能覆盖；发布后cleanup_warning须显示为成功附警告。只有保存成功后才切project_file，打开副本必须显式；格式检查不称模拟成功。完整契约见 `../docs/配置兼容与迁移.md` 和agent-history，候选不等于阶段已验收。

2026-10-29 R32：执行原生 Geant4 交互会话仅允许显式 `--ui --ui-session csh`；裸 `--ui` 或 INI `interactive=true` 未选择 csh 时在初始化及 macro 执行前明确拒绝并写失败摘要，不自动降级。dry-run 不开启会话，仍可使用裸 `--ui`。Python 桌面 GUI 正常 Run/后端几何预览继续使用 batch config/macro，不受此限制；不要把桌面 GUI 与原生 Qt UI 会话混称。修复已在8ecad66真实Windows及Linux双版本回归通过，证据见 `docs/verification/q1-final-20261029/README.md`。

2026-10-29 Q1 R25–R30 当前边界：后端偏置算符按 worker 私有创建；GUI 解读摘要必须区分 master 几何挂接计划与逐 `(runID, threadID)` 的真实 wrapped process、绑定和 EndRun 完成收据，缺收据失败，proposal/applied 计数只证明调用。hits/HitRecord 的 `weight` 已纠正为步前统计权重，Edep/Dose/Fluence/LET/DDD 使用同一口径；相空间保留边界采样权重。历史偏置计分须重算；同次运行与原生 energyDeposit/cellFlux 的有限专项对照不等于一般无偏性、方差收益或全自动物理验证。generated 模式仍无 biasing 规则编辑器。

2026-10-29 Q1：项目保存须同目录临时文件写完并原子替换，失败保留原文件；未来版本/未知字段须拒绝并指出路径，不能静默丢弃。刷新结果先清旧证据；扫描 success 必须有正完成数与逐 run 一致性；后端预览仅发布最后请求。主窗口关闭只停止其持有的主 run/scan/geometry/inspect/merge/extension/scenario 进程与队列，有界等待后确认停止；不能按进程名杀其他任务。完整回归 `smoke_q1_public_paths.py`，真实 Windows 窗口另见 `smoke_q1_windows.py`。绘图总量按完成事件数归一化，LET 比值不再归一化；旧 per_primary API 弃用但保留旧数值。小样本/零分母/零总量误差不可用，网格跨 cell 投影无协方差不画误差。全文与迁移见 `docs/输出数据契约.md` 和 `docs/agent-history.md`。

2026-10-29 2C 只读有效配置页：`core/effective_config.py` 读取 `g4usim_effective_config_v1`，上限 4 MiB，
拒绝重复 key/path、非有限值及无运行证据的 applied；缺失 requested/resolved 显示未知，显式 JSON null 保持 null。
`widgets/effective_config_page.py` 仅加载与查看文件，不运行后端、不编辑项目、不推断模拟成功；失败加载保留旧快照并标陈旧。
搜索同时匹配 canonical path 与解码对象名；语言切换按 canonical path 保留选择。当前数据是 Manager 子集，
不能把 manager_accepted 译为已在 Geant4 生效。页序新增“有效配置”在场景与运行之间，共 9 页；导航、i18n、
`smoke_main_window_ui.py` 必须同步。专项 `smoke_effective_config.py` 和真实导出 `scripts/test_effective_config_export.py`。

2026-10-28 2B 场景页：`widgets/scenario_page.py` 是屏蔽/涂层场景的端到端入口，不是通用编辑器；字段来自
`core/scenario_shielding.py` 的 `ShieldingSpec`（基础 7 + 高级 8），校验三层（字段解析 → `problems()` → `config_schema`），
有任一问题不得生成或运行。页面不重复实现物理与文件格式：生成走 `scenarios/shielding_coating/scenario_model.py` 的纯函数
`render()/generate()`（`make_scenario.py` 只是 CLI 包装，二者逐字节一致），分析走 `analyze.py` 的 `analyze(output_dir)`；
不得在页面里拼 INI 或重算 TID/DDD。运行必须核对 `run_summary.txt` 的 `status` 与完成事件数，缺证据时按 `evidence_items()`
显示标签（`no_statistics_file_zero_deposition` 等）或失败原因，不得把缺失写成零。结果表五列（Group/Label/Value/Unit/Evidence）
必须每行带证据；DDD 行必须显示 NIEL 表路径与 sha256。进程生命周期：`start_run()` 用 QProcess、`stop_run()` kill、`closeEvent` kill；
日志写入场景目录 `backend.log` 且视图有行数上限。新增页面必须同步 `smoke_main_window_ui.py` 的页数/导航索引断言与
`core/i18n.py` 的 `ZH_CN` 键（表头与动态文本走页面自己的 `refresh_language()`）。回归：`smoke_scenario_page.py`（Qt）、
`smoke_scenario_backend.py`（12 步真后端）、`scripts/test_scenario_shielding_core.py`、`scripts/test_shielding_scenario_model.py`、
`scripts/test_shielding_analysis.py`。

2026-10-27 GUI 源字段保留：Setup 栏的 summary widgets 只能镜像它真正暴露的标量源字段（preset/particle/energy/position/direction）与 physics/scoring 字段；源几何与角分布（`position_mode`/`position_type`/`source_shape`/`center`/`halfx`/`halfy`/`radius`/`isotropic`/`angular_mode`）属于 Source editor，任何槽都不得无条件重置为 `point`/`fixed`——`widgets/config/run_config.py` 曾这么做，导致 plane/rectangle/isotropic 源在用户改一个数字后静默退回点源+固定束流、生成的 main.ini 丢字段而运行仍“成功”。回归 `gui/smoke_tests/smoke_source_field_preservation.py`（端到端写 main.ini 后断言字段仍在，含 point 反向 sanity）；同类重置只允许带明确条件（空值补默认、旧别名归一化）。进度终态文案走既有 `Result: {state}`；stdout/stderr/merged 三个日志视图必须有行数上限，merged 前缀只在行首插入，runner 的日志 tag 解析必须跨 chunk 缓冲完整行。

2026-10-27 F6：`core/run_progress.py` 有界增量解析版本化 stdout 进度；runner 每次启动重置，分别增量解码 stdout/stderr，退出先排空尾流再判最终结果。RunPage 未知进度不造百分比，计数全到但未 end 显示收尾中；停止/强杀/失败时进度条保留最后观察值，状态文字改用终态文案（结果：模拟成功／用户停止／强制结束／结果未证实），不再输出“进度已冻结”。end 不代表成功，最终状态仍由 run_result.py 决定。新消息版本、噪声前缀、坏 JSON、非有限数、超长行、倒序、跨 run、无换行 EOF 必须保留测试；smoke_live_progress.py 和 smoke_live_progress_backend.py 分别验证协议/Qt 与真实 Geant4，契约见 docs/实时运行进度.md。

2026-10-26 E2：`core/config_schema.py` 只做字段描述/标量必要条件；`structured` 会要求上下文校验，不能吞掉这个结果并当作可运行。动态源/区域/网格及独立几何模板可查询描述，但不扩大 editor/writer 白名单。源长度/能量、physics.default_cut 和 Edep 直方图复用 schema；跨字段 max>min 等仍由 editor 验证。材料已知键从生成数据读取，元素/同位素仍原文保留。writer 不再生成未消费的 physics.mode，参考模式仍由 reference 决定。四份生成产物一律由 scripts/generate_config_schema.py 更新。

2026-10-22 D 安装包：源码与安装包路径只经 `core/install_layout.py` 判断（冻结时 `sys.executable` 是 GUI 本身）：应用根、默认后端（包内 `bin/` 或 `build_vs2026/Release`）、运行包目录（冻结时为“文档\G4UniversalSim\gui_runs”）、脚本目录与运行辅助脚本的 Python（冻结时找 `G4USIM_PYTHON` 或 PATH 中的 python，找不到则禁用并说明）。不要再用 `Path(__file__).parents[...]` 或 `sys.executable` 定位仓库与 Python。`app.py --self-test <报告.json>` 供打包验证，冻结窗口程序没有控制台，必须写文件。

2026-10-22 C3 参数扫描：`core/scan.py`（无 Qt）只扫描配置页编辑器能生成的设置，逐点 `apply_value` 深拷贝基准，先 `validate_scan` 全部通过再写任何文件，再用 `create_run_package` 生成普通运行包并写 `scan.json`（G4UniversalSimScan v1）；`core/scan_runner.py` 逐点复用 `G4USimRunner`（日志、`run_status.json`、`evaluate_run_result` 判定一致），以 attempt 令牌保证每点只结束一次（启动失败只有 errorOccurred、崩溃两者都有），并传入该点自己的 seed，不能用基准 seed 覆盖 `run.seed` 扫描。结果只读该点合并的 `scorer_statistics.csv`。QWidget 子类属性不得与 Qt 虚方法同名（`metric` 曾覆盖 `QPaintDevice.metric()` 导致绘制时访问违例）。冒烟测试中的计时器要可停止，退出前在 QApplication 仍存在时删除带 QProcess 的页面。专项 `smoke_scans.py`、`smoke_scans_backend.py`。

2026-10-22 C2 新建仿真向导：业务逻辑在 `core/wizard.py`（无 Qt），只产生编辑器已能生成的子集（NIST 材料、box/tubs、点源 fixed/isotropic 与矩形面源、参考物理列表、hits/event_edep/Edep/Dose/Fluence），不得借向导写出编辑器之外的后端字段；结果通过 `apply_to_project` 原位写入现有 `G4USimProject` 并由 `_set_project` 刷新页面，生成包必须走 `create_run_package`。校验消息与摘要以 (模板, 参数) 返回再 `ui_format`。向导页面在 `initializePage` 填控件时须屏蔽信号回读（`_loading`），否则半填的控件会覆盖 spec。新增 ZH_CN 键前检查重复：字典字面量中重复键会静默覆盖。专项 `smoke_new_simulation_wizard.py`（模型、对话框、主窗口与生成包；须替换模态 QMessageBox）与 `smoke_new_simulation_backend.py`（五个场景真实运行与物理合理性）。

2026-10-22 C1 内置图表（2026-10-29 修正归一化口径）：数据读取只放在 `output/plot_data.py`（无 Qt，numpy），页面 `widgets/plot_panel.py` 只选数据集/视图、用 matplotlib 绘制并导出；图中数值必须与后端文件一致（scorer_statistics 的 value/std_error，网格 CSV 或 ROOT 的 sum 与 rel_error，box 网格坐标取 `run_metadata.json` 的 bins/size_mm（半宽）/center_mm）。每事件归一化用 `run_summary.txt` 的 `run_<R>_completed_events`，不能称为每初级粒子。说明文字以 (模板, 参数) 返回再经 `ui_format` 翻译。视图 combobox 的 data 用字符串（`profile:<轴>`、`map:<x>:<y>`），PySide6 的 `findData` 不能匹配 Python tuple。matplotlib 缺失时输出页仍须可用。专项 `smoke_plots.py`（合成逐值）与 `smoke_plots_backend.py`（真实后端，CSV/ROOT 网格一致）。

2026-10-21 M3/M5 Results JSON 导出原型：`widgets/output_page.py` 通过 `output/extension_runner.py` 的 `QProcess` 运行正式 Python CLI `dose_json`/`fluence_json`；只在存在模拟输出目录且目标为尚不存在的 JSON 文件时允许启动，重复启动拒绝，支持取消、启动/退出失败报告与页面关闭时子进程清理。GUI 对 schema、version、extension ID/version、data、warnings 和无效 JSON 常量执行读取校验，刷新文件列表；`smoke_output_extensions_gui.py` 覆盖真实 Qt 子进程和错误路径。导出成功只说明发现的 CSV 被后处理，必须提示检查上游 run_summary、worker 文件完整性及独立物理 benchmark，不能提升实验性 Dose/Fluence 的支持等级。

2026-10-21 Rectangle Source GUI 原型：`source_shape=rectangle` 在 generated 模式仅开放 XY 平面、`center`、有限正 `halfx/halfy`，按 `shape=rectangle` 写出且不混入 `radius`；fixed/isotropic 两种角分布遵循方向字段互斥；square、annulus、其他高级分布继续阻止运行包。`gui/smoke_tests/smoke_source_editor_v2.py` 检查生成及非法输入；C++ 真实采样专项见 `scripts/test_run_summary.py`。普通预览不代表源平面任意旋转受支持。

2026-10-21 Dose GUI 原型已开放：`ScoringSettings` 与 `ScoringEditableModel` 双向保留 `dose`（默认 false），writer 只在选择时写 `dose=true`，且必须依赖默认 scorer 自动创建；Results / Dose (Gy) 使用 `read_dose_summaries()` 合并已发现的 worker 数据，质量不能跨线程累加，缺失/损坏文件需提示。GUI smoke 入口 `gui/smoke_tests/smoke_dose_results.py`；尚未独立物理标定，文案必须标明实验性。

2026-10-21 Fluence GUI 实验性原型：`fluence` 默认 false，配置模型、生成包 writer 与 Results / Fluence (mm^-2) 已接通。GUI 按 `(runID, physical touchable path)` 聚合已发现的 worker CSV，只累加 raw/weighted track length、每体积只取一次并重新计算 mm^-2；拒绝 schema、非有限值、坏文件及 worker 体积冲突，缺失 worker 只能提示风险。专项 `gui/smoke_tests/smoke_fluence_results.py`；零 Edep Geantino 和 ST/MT 双 run 真实验证见 `scripts/test_fluence_scoring.py`。仅适用于 daughter-free sensitive solid，不能宣称 surface fluence 或独立物理基准已通过。

2026-10-21 Source isotropic 输出约束：`angular_mode=isotropic` 时，generated main.ini 只输出 `isotropic=true`，不输出模型中保留供 fixed 模式使用的 `direction` 字段；后端明确拒绝 `isotropic=true` 与显式 `direction` 冲突。点源写 `position`，圆形平面源写 `center`/`radius`；禁止混写两种位置字段。`smoke_source_editor_v2.py` 同时验证点源和平面源的 isotropic writer。

2026-10-19 Source Editor 数值门禁：运行包中的 `energy`、`position`、`direction`、`radius` 不允许 `NaN`、`Inf` 和超出有限浮点范围的表示；validator 在生成前拒绝，后端 `UnitParser` 保留最终约束。由 `gui/smoke_tests/smoke_source_editor_v2.py` 覆盖。该门禁不表示全部单位和参数组合已完成 GUI 验证。

2026-10-19 平面源位置映射：Source Editor 的 `Position` 在 `position_mode=plane` 时必须生成 `[source]/center`（三轴及单位），在 `point` 时生成 `[source]/position`；GUI 预览中心、writer 和 Geant4 GPS 实际采样必须一致。`gui/smoke_tests/smoke_source_editor_v2.py` 检查偏移 4 mm 的生成配置，`scripts/test_run_summary.py` 核对真实后端 hits。旧 `planeBeam` 命令保留零 x/y 的兼容语义，不能扩大为任意空间分布已验证。

2026-10-22 界面刷新：主题色只在 `core/theme.py`（样式表 + `build_palette` 的 Qt palette；“系统”主题读 `styleHints().colorScheme()`，因为应用 palette 已是自定义的）；图标只用 `core/icons.py` 的 SVG 线条图标，主题切换时由 `MainWindow._refresh_icons` 和各页 `refresh_theme` 重绘，样式表中的箭头图片由 `_svg_url` 写到临时目录。matplotlib 图用 `plot_panel.style_axes`/`draw_empty`，字体族列表带 CJK 回退（`font.family` 而非 `font.sans-serif`，否则不逐字回退）。开始页 `widgets/start_page.py` 的示例在 `core/examples.py`（无 Qt）登记：示例 = 向导 spec + `examples/gallery/<id>/` 附带结果，载入走 `apply_simulation_wizard`，附带文件只读、输出仍写运行目录；附带结果只能由 `examples/gallery/build_gallery.py` 用真实后端生成，卡片描述须与数据一致（`smoke_start_page.py` 核对）。`core/scan.load_manifest` 支持相对路径与目录移动后的改基；运行包缺失的扫描只读（`ScanPage.is_read_only`）。页序：开始、项目、配置、运行、结果、历史、扫描；结果页分组为 `tabs`（概览、图表、表格、文件、工具）及 `data_tabs`/`file_tabs`/`tool_tabs`，配置页消息/原始文件/NIST 在 `details_tabs`。Tab 文字不能含 `&`（会被当作助记符）。

2026-10-23 E1 GUI/后端规则一致：材料名一律经 `parsers/materials_parser.material_reference_status`（自定义名去空白后不区分大小写，NIST 名区分大小写，其他 `G4_` 名只警告），与后端 `MaterialManager::GetMaterial` 一致；`[material.X]` 定义 X，`[NIST]`/`[element.*]`/`[isotope.*]` 不是材料行，原文保存在 `preserved_sections` 并由 writer 写在材料之前；组分保留 `名称:数值`；体积分数材料无 density 即 auto；材料循环引用报错。后端支持而编辑器不支持的形状（`geometry_editor_model.BACKEND_SHAPES`，与 `GeometryUtils.cc` 的 `ParseShape` 同步）是编辑器限制：提示原始文件复制模式，勾选后降为警告。默认演示项目用 `test/materials/test_materials.ini`。新规则差异由 `scripts/test_gui_backend_agreement.py`（统一平台 `gui_backend_agreement`）发现：新增几何/材料夹具会自动加入，判定不一致必须修正 GUI 或在 `EXPECTED` 中写明原因。

2026-10-23 G1 后端几何默认显示：配置页 3D 标签可见且勾选“自动显示 Geant4 几何”时，`schedule_backend_geometry` 在修改后 1.2 秒、切换到该页后 0.1 秒发出 `autoBackendGeometryRequested`；导出期间显示编辑器草图并注明近似。writer 不得在调用方文档上做校验（`generate_geometry_ini_text` 校验副本），否则会抹掉页面的材料错误。专项 `smoke_backend_geometry_auto.py`（真实后端：无运行包导出、缓存、去抖、忙时合并、编辑器错误、后端错误、关闭自动）。

2026-10-23 G2/G3 3D 视图：后端几何与编辑器草图都转为 `preview3d/view_model.ViewItem` 列表，由 `ViewState` 决定可见性（世界、隐藏、单独显示、按材料）、颜色（常见材料固定色，其余按名称顺序取调色板）、样式（容器半透明、敏感体实心、选中描边且其余变淡）和剖切平面；`pyvista_preview_widget.py` 只把它们映射到 VTK 属性，不在控件里写判定逻辑。体积名：后端物理/逻辑体名去掉 `_PV`/`_LV` 即编辑器名；`volumeSelected` 与体积表双向联动（`select_geometry_row` 屏蔽信号避免回环）。点击与拖动以 4 像素区分。VTK 在 Windows 上不能用 Qt offscreen 平台渲染，`smoke_3d_view.py` 的控件部分切换到 windows 平台、无显示时跳过；独立 QtInteractor 关闭前先 `_plotter.close()`，否则测试退出时 wglMakeCurrent 报错。

2026-10-23 E2 配置 schema：GUI 对已迁移字段（`[run]`、`[general]`、`[output]`）的检查用 `core/config_schema.check_value`（与后端解析一致：32 位整数、布尔词、能量单位、空值取默认等），不要再手写同类规则；GUI 自己更严的上限写在 schema 字段的 `gui` 中（如 trajectories 的 1000）。编辑某字段的控件用 `i18n.set_schema_tooltip(widget, section, key)` 设置提示，语言切换时由 `apply_language` 按 schema 重写。`core/config_schema_data.py` 是生成文件。

2026-10-23 G4/G5 草图与源：草图几何只在 `preview3d/sketch_geometry.py`（无 Qt/VTK）：数值按后端解析（`ParseDoubleWithUnit` 无单位为 mm/rad，旋转 `ParseAngle` 逐分量，`SplitVectorText` 分割），放置为 `G4PVPlacement(R, t)`、R = Rz·Ry·Rx 是坐标系旋转，实体按 R⁻¹ 转动，沿父链组合；各实体参数顺序照 `VolumeBuilder::Create*Solid`，改后端实体时须同步并跑 `scripts/test_sketch_accuracy.py`（统一平台 `gui_sketch_accuracy`；把旋转约定改错会失败）。`PreviewVolume.vertices/faces` 是世界坐标网格，画不出的写 `not_drawn` 原因并进消息，不得静默跳过；A5/placement 键存于只读 `preview_properties`（不写回，不算 legacy metadata）。源图元由 `source_builder._build_glyphs` 生成：平面源固定在 XY 平面（GPS 不用 normal），只有 point/circle/rectangle × fixed/isotropic 为 `generated`，其余淡色并标注仅预览；描述是 (模板, 值) 嵌套元组，由 `describe_source` 逐层 `ui_format`。Geant4 几何上只在 generated 模式叠加源（`show_backend_geometry(with_source=...)`）。专项 `smoke_source_glyphs.py` 用 H1 径迹核对真实初级粒子的起点与方向。

2026-10-23 G6 径迹叠加：`preview3d/trajectories.py` 无 Qt，读取一次 run 的全部 worker 文件（默认最后一轮）并按事件排序，schema/单位、跨文件重复事件、体积索引越界都报 ValueError；`TrackFilter` 按事件（None 为全部）、隐藏粒子、仅初级和次级最低初始能量筛选，初级径迹不受能量阈值影响；粒子颜色固定。`pyvista_preview_widget.py` 每种粒子一个线集 actor（不可拾取、不重置相机），`_render` 清场后重画；有径迹时 `ViewState.tracks_shown` 使未选中体积不透明度不超过 0.15。`load_tracks` 依次尝试项目输出目录、Output 页目录，最后才弹目录对话框；`_on_finished` 以 quiet 方式自动加载。配置页各编辑器标签页包在 `_scrolled` 的 QScrollArea（`editorScroll`）中，测试取标签页内容须解包；3D 页索引用 `preview3d_tab_index()`。截图脚本必须替换 `QMessageBox` 的 warning/information，否则会在用户桌面留下模态框。专项 `smoke_trajectory_view.py`（含真实后端 Generate and Run）。

2026-10-23 E5 拆分：配置页在 `widgets/config/`，每个编辑器一个模块，内含其控件与布局的 QWidget（`SetupPanel`、`MaterialsEditor`、`GeometryEditor`、`Preview3DPanel`、`RunConfigEditor`、`DetailsPanel`，可单独构建）和其逻辑 mixin（另有 `layers.py`、`booleans.py`）；`ConfigBuilderPage` 只保存共享状态（文档与模型）、组合这些控件并做跨编辑器协调，通过 `_adopt` 把各控件挂到页面属性上（重名即报错）。标签页的构建顺序决定共用控件的最终位置（布尔表在“Boolean Ops”、3D 消息框在“Messages and files”），改顺序即改界面。`_connect_signals` 按原顺序调用各模块的连接函数，同一信号的槽按此顺序执行。主窗口行为在 `window/`（shell、project、run、content 四个 mixin），`main_window.py` 只剩构造、信号连接和关闭；测试替换模块函数时要替换其所在模块（例如 `window.run.create_run_package`）。新控件属性名在整页内必须唯一（`add_volume_button` 曾被材料和几何两处共用）。专项 `smoke_config_editors.py`。

## 2026-10-29 完整 2C 查看器候选补充

## 2026-11-02 J3 实施：皮肤注册表与设计系统（第一阶段）

## 2026-11-02 J3 第二阶段：外壳、命令面板与状态栏

## 2026-11-02 J3 第三阶段：工作区面板布局

## 2026-11-02 J3 第四阶段：按页面适配工作区

## 2026-11-02 J3 第五阶段：导航时 dock 可见性

## J3 第六阶段：3D 模型树与体积筛选（2026-11-02，作者交付未验收）

## J3 第七阶段：帮助菜单、快捷键表与关于对话框（2026-11-02，作者交付未验收）

## 2026-11-03 J3 审查响应
