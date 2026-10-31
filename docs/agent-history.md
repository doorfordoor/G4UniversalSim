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
