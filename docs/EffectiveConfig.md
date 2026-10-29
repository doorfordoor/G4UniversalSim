# 有效配置快照（2C 开发中）

当前实现是配置阶段的 **Manager 状态子集**。它用于审查来源与值，不证明 Geant4 内核已应用，也不判定模拟成功。完整模块覆盖、运行开始/最终化快照、模块 off/auto/on 尚未交付。

## 使用路径

后端提供 `--dump-effective-config <JSON路径|->` 只读检查入口，复用真实配置与 macro preflight；不执行 macro、不初始化物理、不启动事件、不创建运行输出目录。显式 JSON 路径是唯一导出目标，必须为不存在的新文件（独占创建，拒绝覆盖输入及已有导出），`-` 写标准输出。与其他独立检查模式同时指定应拒绝，缺失参数/不可写目标/无效配置/宏预检失败应非零退出。

GUI 的“有效配置”页加载后端导出的 JSON。文件最多 4 MiB，页面只读；对象树展示字段，详情展示请求值、解析值、单位、应用状态、证据与来源，原始 JSON 可核对。加载损坏文件时保留上份有效快照并标“陈旧”，不会拼接两份文件。它不会同步修改项目、运行器或物理参数。

## 数据契约

- schema 为 `g4usim_effective_config_v1`；字段身份采用 JSON Pointer 风格，保留名称大小写，转义 `~` 和 `/`。
- `requested`、`resolved` 为 JSON 类型化值。显式 `null` 与字段缺失分别显示；应用未知不代表数值必然未知。
- `revision` 是本 registry 成功事务计数，不是 Git 提交，也不表示运行成功。失败事务不发布新值或来源，旧快照不随之后的变更变化。
- `application_status` 与 `evidence_level` 分离；`manager_accepted` 不能满足 `applied`。只有相应内核/线程/运行应用证据才能声明应用。检查模式不具有这些证据。
- 输入来源链不完整时须说明限制，不能将默认或解析值伪造为用户请求；未知外部命令影响保留 unknown。
- 同一快照稳定排序，但它不是随机引擎检查点，不保证跨机器逐位重放。

## 验证与边界

独立 C++ 模型测试：`python -B scripts/test_effective_config_model.py`（需要 C++17 编译器，支持 CXX）。真实导出测试：`scripts/test_effective_config_export.py` 读取 `G4USIM_EXE`；GUI 测试为 `gui/smoke_tests/smoke_effective_config.py`。新增代码的实际验证结果以 STATUS / ROADMAP 引用的报告为准，本页列入口不等于已经通过。

旧 `effective_*` 摘要字段与 `run_summary_schema_version=1` 保持不变。schema 353 字段不是本快照的完整覆盖承诺；field/biasing、独立材料/几何、多源、逐 run 证据仍须按消费者清单逐项闭合。

## 消费者覆盖清单与后续验收

以下按当前实际源码入口测绘，行号对应本次开发工作区，不是完整 2C 已交付声明。`SimulationManager::ExportEffectiveConfigJson()`（`src/Core/SimulationManager.cc:1313`）最多导出 15 个 Manager 字段；命名源或相空间模式省略不适用的两个旧源字段，非 mono 分布省略单能缓存。所有这些字段只记录 configure 时点，未执行 macro、未取得内核/worker 应用证据。表中“后续病例”是待闭合的验收要求，不表示本次已运行。

| 实际消费者及入口 | 当前子集覆盖与缺口 | 后续真实验收病例 |
| --- | --- | --- |
| 主 INI 与启动参数：`src/Config/ConfigManager.cc:109`；`src/Core/SimulationManager.cc:659`、`:1197`；CLI `main.cc:285` | 已读回输出目录、run 名称、线程、seed、macro 路径；主配置身份、全部别名覆盖链、输入指纹、interactive/dry-run/verbose 尚无字段。现有来源只保留获胜入口，revision 不是持久运行历史。 | 默认→INI→显式 CLI 同字段覆盖；别名同存、重复键后值生效；拒绝事务不改 revision；中文路径及输入内容变化；保存旧快照后再次改配置仍保持旧内容。 |
| 旧式单源：`src/Source/SourceManager.cc:407`、`:532`、`:728`；GPS 应用 `:1206`；运行准备 `:344` | 仅普通单源 `/source/particle` 与 mono 模式的 `/source/energy` 的 Manager 缓存；缺位置、角分布、能谱、离子与限制条件，缓存不代表 GPS 当前采样状态。 | 点源/矩形面源、fixed/isotropic、preset 后显式覆盖；原生 GPS 与项目命令交错；离子初始化前后及能量分布，分别核对请求、解析与实际应用，不用首条 hit 代替源顶点。 |
| 命名源与相空间：`src/Source/SourceManager.cc:407`（命名分支）、`:455`（相空间分支） | 两个 legacy 源字段被省略；未导出具名对象、强度、相空间文件/内容指纹/recycle，不能把缺项当默认源。 | 名称含 `/`、`~` 的稳定对象身份；两具名源跨 run 身份与强度；相空间合法/空/损坏文件及历史耗尽，核对实际生成顶点与输入指纹。 |
| 几何与独立几何文件：`src/Core/SimulationManager.cc:697`、`:711`；`src/Geometry/GeometryManager.cc:223`（模板 `BuildNodesFromFile`）、`:525`（world）、`:558`（region） | 已覆盖 template、config 路径、default world material、check_overlaps；缺各模板对象、形状/放置/布尔/STL/GDML/可视化/region 参数及独立文件字段来源。 | 层级与分层模板、布尔和外部 mesh 的稳定对象映射；单位归一、未知字段与非法几何前置失败；构建后的尺寸/材料/region 与请求一致；初始化后拒绝修改，不把预览当内核证据。 |
| 材料独立配置与命令：`src/Core/SimulationManager.cc:689`；`src/Materials/MaterialManager.cc:52`；`src/Materials/MaterialIniReader.cc:90`；构建 `MaterialManager.cc:138`、`:152`、`:179` | 未覆盖材料文件路径、元素/同位素/材料对象、组分、密度、NIST 选择及来源。主 INI 消费追踪不能替代独立 reader。 | NIST、自定义混合物、同位素组成与单位；未知 section/key 和不支持参数拒绝；macro 材料命令成功/失败保留来源；核对实际 G4Material 密度和组成。 |
| 物理：`src/Physics/PhysicsManager.cc:477`；region 应用 `src/Geometry/GeometryManager.cc:558` | 仅 reference 列表读回；缺 EM 选择来源链、构造器、cuts、限步/限程、region 及偏置包装后的过程。 | reference+EM 的最终列表、各粒子 cut 与 region 覆盖；macro 修改后物理列表重绑；初始化后拒绝修改；区分列表配置、实际 process 构造和物理基准。 |
| 计分与 mesh：`src/Scoring/ScoringManager.cc:618`；线程克隆 `:104`；mesh `src/Scoring/ScoringMeshConfig.cc:148`，由 `src/Core/SimulationManager.cc:733` 保存命令 | 仅 scoring enabled 与 event_edep；这两项没有来源链。缺 hits、直方图、Dose/Fluence/LET/DDD、NIEL、相空间输出及 mesh 对象和各 worker 应用。 | 默认 scorer 依赖、各计分开关与直方图范围；NIEL 路径/哈希和未知粒子名；box/cylinder mesh 命令真正应用；ST/MT 双 run 克隆及输出一致性，计分误差不等于物理验证。 |
| 场及外部场图：`src/Field/FieldConfig.cc:231`、`:145`；`src/Detector/DetectorConstruction.cc:53`；`src/Field/FieldSetup.cc:99` | 完全未覆盖；独立 field parser、场图文件、体积挂接与每线程 field setup 不能用 schema 字段数量代替。 | 均匀磁/电场、场图插值及越界、错误体积；核对各 worker 构造/挂接证据与确定性轨迹弯曲；重复 run 生命周期和失败清理。 |
| 偏置：`src/Biasing/BiasingManager.cc:451`；挂接 `:530`；`src/Core/SimulationManager.cc:735` 启用物理包装 | 仅 biasing enabled 且来源未追踪；缺逐规则粒子/process/因子/体积、operator 挂接和 wrapped process 匹配。 | 显式规则与不存在的粒子/process/体积；配置→物理包装→operator 挂接→匹配逐层证据；初始化后及交互修改拒绝；独立权重/效果验证，不将目标匹配称实际偏置验证。 |
| 输出格式与径迹：`src/Core/SimulationManager.cc:684`；`src/Output/OutputManager.cc:59`、`:125`；径迹配置 `src/Scoring/ScoringManager.cc:618`，运行写出 `:440`、`:453` | 输出仅覆盖目录；缺 csv/root/both、线程/轮次文件名、写出失败和轨迹 events/min_energy/max_points。径迹由 ScoringManager 消费，不能仅审查 OutputManager。 | 格式与依赖拒绝、ST/MT 多 run 后缀、输出失败锁存；轨迹 0/正上限与能量阈值/点数上限、worker 写入与登记；不得把文件登记当设备持久化或物理正确。 |
| macro 与交互命令：预检 `main.cc:635`，执行 `:798`，成功来源记录 `:852` / `src/Core/SimulationManager.cc:432`；csh `main.cc:95` | 当前导出只做递归 preflight，不执行命令；不含 macro 后快照、run_begin/finalization、交互原生命令变化、跨 run/worker 的 revision。 | 嵌套 macro 相对路径、CLI 锁冲突、失败命令不提交来源；两轮 run 间合法变更与被拒绝的非法状态变更；原生命令无法观测时明确 unknown；失败最终化保留真实已完成事实，独立 run_result 判成功。 |

闭合顺序应是：各真实消费者记录已接受的请求/解析值与稳定对象身份，保留完整来源和输入内容指纹；随后在实际内核/线程生命周期记录应用证据；最后把 configure、run_begin、finalization 接入统一 registry。只有独立模型、配置导出或 GUI 字符串回归通过，都不足以宣称上述运行链路完成。


## 下一批接入约束：source（待实现）

先闭合 source 的配置阶段消费者，再接应用证据。沿用 `GetSources()` 只读读取，增加一次性返回源模式、各源配置副本及来源元数据的接口；导出不得调用 `GetGPS()`、setter 或 `IniReader::GetString()`，后者会改变 consumed 状态。具名对象使用配置名称，旧 `[source]` 使用明确固定身份。

字段必须按实际模式投影：gauss 的 monoEnergy 是均值，uniform/points 等不能输出这个未使用成员；位置/角分布同时依据类型与 presence flags；相空间单独导出文件顺序、recycle、实际读取 histories/particles，禁止补入已重置的 GPS 默认值。全局 `presetName_` 不能重建逐源 preset 覆盖链。

来源记录须在真实成功解析/赋值处随配置事务发布，保留 default→preset→显式覆盖及派生原因。现有 `GetFields()` 只保存获胜声明，完整重复声明链需要 reader 保留历史；主 INI、谱文件、相空间文件的哈希必须来自实际解析的同一份字节，不能解析后重新打开文件计算并冒充已接受输入。解析失败不提交来源或 revision。源模式切换时还须事务性移除已不适用的旧字段；当前 registry 的增量合并接口尚未提供模块替换/删除契约，不能把残留字段当成本轮配置。

后续验收包含八类：无副作用导出；带 `/`/`~` 的多源稳定身份；preset/重复键完整覆盖链；七种能量分布适用字段；离子解析与表准备分离；位置/角分布依赖；多文件相空间哈希/耗尽/回收；成功/失败项目命令、原生 GPS 未知状态及跨 run/worker 独立证据。`gpsConfigDirty_` 与 `deferredApplied_` 不自动成为逐字段应用证明。这些是设计要求，当前尚未实现或验收。
