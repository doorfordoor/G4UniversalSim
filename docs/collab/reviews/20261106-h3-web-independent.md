# H3-2 独立只读架构与代码审查（2026-11-06）

**结论：暂不同意将 H3-2 作为符合冻结合同的候选关闭。** 发现可造成并行计分归属错误的配置遗漏，以及材料匹配证明、输出身份和有效配置收据方面的偏差。首轮为辅助静态审查，随后追加三个冻结版程序的手工 `--dry-run` 配置负例复演。未执行构建、专项自动化测试、真实粒子输运或正式 H3-4 基准。主审已独立复跑通过的 `test_parallel_world.py` 和 `test_parallel_scoring_component.py` 成绩予以保留，不据此覆盖未测反例。

审查基线：当前工作区 `HEAD=83c0b139`，H3-2 文件仍未提交；对照 `docs/collab/CURRENT-SUPERVISION.md`、`docs/collab/decisions/20261106-h3-contract-freeze.md`、`docs/collab/decisions/20261106-h3-closeout.md`、`docs/collab/outbox/20261106-h3-backend.md`、冻结的 `docs/collab/outbox/20261106-h3-contract.md`。以下行号为首轮工作区实读值，各问题条目的静态反例保留原貌；本次实际复演仅覆盖下文指定的三例。

## 追加证据｜冻结版程序的三个配置负例 dry-run（2026-11-06）

- **程序身份**：仅使用 `D:/Geant4/G4UniversalSim/out/collab/h3-independent-r1/bin/G4UniversalSim.exe`，三次执行前核验 SHA256 均为 `9ffb2d02035251cc32e5add90ad173197d90fd5189490b78bdfae19d8076f37d`。未使用并行修复中的产品程序。
- **复演方式**：将各例现成的 `main.ini`、`parallel.ini`、`geometry.ini`、`materials.ini` 复制到 `D:/Geant4/G4UniversalSim/out/collab/h3-independent-r1/web-runtime/<case>/`，以各例目录为 cwd，分别执行 `--config main.ini --dry-run --output <该例目录的绝对 output 路径>`。每例的完整 `stdout.log`、`stderr.log` 和 `output/run_summary.txt` 均留在该目录。结构化执行记录为 `D:/Geant4/G4UniversalSim/out/collab/h3-independent-r1/web-runtime/results.json`。

| 原始负例 | 预期冻结合同拒绝条件 | 实测 exit | stdout / stderr | 最终摘要事实 |
| --- | --- | ---: | --- | --- |
| `overlap` | 同级 `[volume.Slab]` 和 `[volume.Overlap]` 同尺寸同坐标、正体积重叠 | `0` | stdout 明确 `G4UniversalSim dry-run completed`；stderr 0 字节 | `status=dry_run`，`parallel_world_volume_count=2` |
| `derived_name_collision` | `[volume.SlabGrid_0_0_0]` 与 `[grid.SlabGrid]` 的派生 cell 同名 | `0` | stdout 明确完成；stderr 0 字节 | `status=dry_run`，`parallel_world_volume_count=5` |
| `over_cap` | `[grid.SlabGrid]`、`[grid.Other]` 各 16×16×16 个单元，展开总数 8192 超过 4096；两 grid 同时重叠 | `0` | stdout 明确完成；stderr 0 字节 | `status=dry_run`，`parallel_world_volume_count=8192` |

**运行结论**：三个本应在声明/展开校验时拒绝的输入均被该冻结版程序接受并正常完成 dry-run，且摘要写入成功，没有发生 `Access is denied`。因此本次 `exit=0` 有明确的接受证据；主审先前遇到的输出访问拒绝及 `exit=1` 仍保留为不同失败事实，不能视为输入被配置层拒绝。`over_cap` 同时含 grid-grid 重叠，此例证明两种约束均未触发拒绝，不单独隔离某一种原因。dry-run 仅完成 manager 和 Geant4 用户初始化对象创建，未执行事件、真实 ghost SD 命中或完整 Stage B 物理运行，不能据此判断输运数值是否正确。

## 按优先级排序的发现

### P1-1　完全缺少不同声明体积/网格间的空间交叠预检

- **位置**：`src/ParallelWorld/ParallelWorldConfig.cc:249-448` 只解析并追加单元；`:450-487` 只验证质量世界包围盒包含；`src/ParallelWorld/ScoringParallelWorld.cc:53-68` 把所有体积无条件作为 ghost world 同级 daughter 放置，`G4PVPlacement` 的重叠检查参数为 `false`。
- **触发反例**：同一 `parallel.ini` 中 `[volume.Slab]` 与 `[grid.SlabGrid]` 都使用 `size=20,20,2 mm`、`position=0,0,0 mm`，均为 `sensitive=true`，且均以 world 为 parent。现有 Stage A 接受两个独立声明；Stage B 只核质量及世界包含，同级 daughter 相互重叠仍可通过。Geant4 导航在交叠内部的选择不能被当成各单元覆盖或能量守恒的确定保证。两套网格之间的部分交叠同理。
- **合同**：冻结决定第 11 行要求不同 grid/volume 空间交叠预检拒绝、相邻贴边允许；合同 §5/§6.1 要求对象构造前拒绝。
- **最小修复**：在 Stage A 对所有最终生成的轴对齐 box 单元检查正体积交集，排除同一规则网格自身相邻单元，允许仅边界接触；在构造前 fail-fast，并对 box-box、box-grid、grid-grid 和邻接反例补既有专项测试。

### P1-2　派生单元名与显式体积名可碰撞，映射与 Stage B 可能引用错误对象

- **位置**：`src/ParallelWorld/ParallelWorldConfig.cc:255-270` 只检查声明源名，`:405-434` 生成 `<grid>_<ix>_<iy>_<iz>` 后由 `AppendVolume` 直接追加，`:728-733` 按名称返回第一个 `VolumeSpec`；`src/ParallelWorld/ScoringParallelWorld.cc:104-111` 同样按名称返回第一个 logical volume；`src/ParallelWorld/ParallelScoringDetector.cc:52-56,83-90` 使用此查找结果作为参考质量/体积。
- **触发反例**：声明 `[volume.G_0_0_0]` 和 `[grid.G]`（`bins=1,1,1`），两个源名不同，但各生成一个同名 `G_0_0_0` 的 ghost daughter。若二者尺寸或材料不同，命中后可能按另一声明的参考质量/体积计分，或在 Stage B 错把同名首对象当作第二对象；相同尺寸/质量但位置不同的版本也不能得到唯一的声明→内核对象映射。
- **合同**：冻结决定第 11 行明确要求声明名与派生单元名冲突预检拒绝。
- **最小修复**：生成最终扁平单元表时对所有 `VolumeSpec.name` 做唯一性检查，并在构造前拒绝；Stage B 最好同时核真实 placement 的中心/拷贝号，不靠 `FindLogicalVolume(name)` 这一歧义查找。

### P1-3　`material_matches_mass_world=true` 的证明不成立

- **位置**：`src/ParallelWorld/ParallelWorldConfig.cc:510-523,528-559`。代码一旦找到任意同文字材料名且其声明 box 包含计分 box 的质量侧节点，就给出 `true`，但未检查该质量节点内部是否存在异材质子体积、嵌套变换、旋转和实际解析出的材料对象；`ExportEffectiveConfigFields` 在 `:679-688` 将它作为肯定性的有效配置事实输出。
- **触发反例**：质量世界的 `water` 盒中含一个 `G4_W` 子盒；平行计分盒与外层 `water` 盒完全相同。代码报告 `true`，但计分域内一部分真实输运材料为钨。另一个反例是平移的嵌套同材质盒，`ContainsBox` 将子盒相对 parent 的局部 position 当作世界坐标，可误报包含。
- **合同**：冻结决定第 13 行要求**整个**计分 box 与质量材料域对应被证明，否则 `unknown`；相同名字或中心材料均不足以证明。
- **最小修复**：只有经完整世界坐标变换、实际材料对象及子节点异材质占域排除后才置 `true`；难以严格证明的情况输出显式 `unknown`，不要把它伪装为 `false` 的布尔证明。参考质量本身的 `density×volume` 计算与“材料实际一致”需分开报告。

### P1-4　`run_validated` 收据跨 run 合并、失败时仍可能签发，且输出哈希恒空

- **位置**：`src/Core/SimulationManager.cc:630-638` 累加所有 run 的 `completedEvents`；`:677-685` 已计算 `finalStatus`，但 `:762-766` 仅凭 `completedEvents>0` 就使用最后一个 `runId` 和**所有 run** 事件总数调用 `RecordRunValidated`，传入新建的空 `outputSha256`；`src/ParallelWorld/ParallelWorldConfig.cc:710-720` 直接登记该收据。
- **已有证据/触发反例**：交付的 Case M `run_summary.txt:176,208-213` 记录 run 0 完成 200、run 1 完成 50。当前代码会在 `ParallelWorldConfig` 内部为 `run_id=1` 记录 `completed_events=250`，不会为 run 0 独立记录相应收据；任一 run 已完成事件而后续命令失败或输出异常，也可能在 `finalStatus=failed` 时内部登记 `run_validated`。`output_sha256` 永远是空对象。**由于 P1-5 的导出接线缺失，这些内部记录目前未进入最终有效配置快照，不能把它们称为已输出的真实收据。**
- **合同**：冻结合同 §7 要求收据对应真实 run、真实输出 SHA；失败及未观察事实不得标记 `run_validated`。
- **最小修复**：仅在最终有效完成的相应 run 上逐 run 写收据，填本 run 完成事件数并从已经哈希的真实输出登记取得目标 SHA；`failed/aborted`、输出失败、零事件等分别按实际状态保持 `failed/unknown`，不签成功收据。

### P1-5　并行世界有效配置字段及收据完全未接入实际快照导出链

- **位置**：`src/Core/EffectiveSimulation.cc:136-153` 的 `InitializeEffectiveConfig()` 未调用 `parallelWorldConfig_->AcceptEffectiveConfig(...)`；`:156-170` 的 `RefreshEffectiveConfig()` 未加入 `parallelWorldConfig_->ExportEffectiveConfigFields()`；`:220-240` 的 `EffectiveSnapshot()` 未汇总 `parallelWorldConfig_->ExportEffectiveConfigEvidence()`。相应提供者已在 `src/ParallelWorld/ParallelWorldConfig.cc:600-725` 实现，但没有进入这些消费者。
- **触发反例**：启用平行世界并成功执行一个 run，`run_summary.txt` 可带有部分 `parallel_world_*` 摘要键，但 `effective_config` 快照缺少合同规定的 `parallel_world/enabled`、逐单元材料、参考质量及 `kernel_constructed/run_validated` 证据。即使内部调用 `RecordKernelConstruction()` 和 `RecordRunValidated()`，其收据也不会被聚合到实际运行快照。由此无法审查声明值、消费者接受值、内核观测与最终运行证据的对应关系。
- **合同**：冻结合同 §2“有效配置”、§7 要求这些字段与 manager-accepted → kernel-constructed → run-validated 等级在现有有效配置系统中实际可追踪，冻结决定第 15 行要求配置/schema、摘要和测试分别接线。
- **最小修复**：在上述三个已有有效配置入口加入并行配置的 `Accept`、`ExportFields`、`ExportEvidence`，仅 `enabled=true` 时输出新增字段，复核默认未启用时的旧快照语义；先修 P1-4 中的事件归属和收据真实性，再验证最终快照内容。对单 run、Case M 连续双 run、零事件和失败终态做既有接口级断言。

### P2-1　真实 grid CSV 的 copy 编号违反冻结的统一 `#0` 身份

- **位置**：`src/ParallelWorld/ScoringParallelWorld.cc:52,65-71` 对每个独立命名单元执行 `copyNo++`，而 `include/Scoring/DoseContext.hh:36-41` 如实将 copy 号写入 touchable 路径。
- **已有证据**：`out/collab/20261106-h3-2/evidence/grid/output/run/dose_volume_summary_t0.csv:2-5` 真实行分别含 `SlabGrid_0_0_0#0`、`SlabGrid_1_0_0#1`、`SlabGrid_0_1_0#2`、`SlabGrid_1_1_0#3`；`scripts/test_parallel_world.py:270` 只校验路径前缀，不核 `#0`。
- **合同**：冻结决定第 11 行，所有层均 `#copy`，示例为 `/ScoringWorld#0/SlabGrid_0_0_0#0`；合同 §3.2 的单元均按唯一名称建立，规定路径模板末段为 `#0`。
- **最小修复**：独立命名的每个 daughter placement 用 `copyNo=0`，路径仍保留完整 touchable 结构；补断言完整 `volume_path` 并校验 4×4×1 所有单元。旧候选的输出身份需标记为已发生的差异。

### 合同形式偏差（观察项）　并行世界实际注册发生在 `Construct()` 内

- **位置**：`src/Detector/DetectorConstruction.cc:30-34` 的 `SetParallelWorldConfig` 仅保存共享配置，实际 `RegisterParallelWorld` 在 `:46-56` 的 `Construct()` 中执行；`src/Core/SimulationManager.cc:1183-1193` 返回 detector 后由 `main.cc:816-820` 先交给 RunManager。
- **差异与证据**：冻结合同 §5.2 写明在 `CreateDetectorConstruction()` 返回前注册。当前代码晚至 `Construct()` 执行注册，但 Geant4 当前初始化顺序是在此之后调用 `ConstructParallelGeometries()`，且现有真实正例可构造并输出并行计分。**本轮没有发现由此导致的可复演故障，不列为阻断级运行缺陷。**
- **最小处理范围**：请主审裁定是否需要与合同的注册时点严格统一。如要求统一，可将构造/注册移动到 `SetParallelWorldConfig()` 或 `CreateDetectorConstruction()` 返回前，同时复核 MT worker 初始化。避免仅因时序形式差异扩大本轮修复。

### P2-2　ghost 计分直接复用了明确禁止的质量世界 `PopulateDoseContext`

- **位置**：`src/ParallelWorld/ParallelScoringDetector.cc:65-70`；`include/Scoring/DoseContext.hh:23-25` 调用 `logical->GetMass(true,false,pre->GetMaterial())`，该 `pre->GetMaterial()` 是复制步上的质量侧材料；`:36-41` 同时构造路径。随后 `ParallelScoringDetector.cc:83-84` 才覆盖参考质量和体积。
- **触发反例**：质量世界材料为水，平行声明材料为另一有合法密度的材料。ghost hit 首先以质量侧材料强制计算 ghost logical 的 mass，并写入 Geant4 的线程本地质量缓存，虽然之后覆盖 `HitRecord.doseMass`，中间副作用依然存在；也多做不需要的质量计算。当前成功 CSV 的参考质量来自后续覆盖，不能据此推出全部输出数值有错。
- **合同**：冻结合同 §2“计分上下文”明确禁止直接复用并要求独立 ghost 上下文。
- **最小修复**：建立专用平行上下文，仅由 ghost touchable 生成完整路径并从 `VolumeSpec` 填入参考质量、体积；保留 `ParticleHit::FromStep` 的步前动能、权重和长度来源。

### P2-3　Stage B/失败路径对线程本地 SD 缺失缺少可核对的失败锁存

- **位置**：`src/Core/SimulationManager.cc:1306-1404` 只查 ghost/尺寸/质量/包围盒，未核实际 worker SD 挂接与当前线程身份；`src/ParallelWorld/ScoringParallelWorld.cc:75-101` 依赖 `FindSensitiveDetector`/`SetSensitiveDetector`，未产出 worker 构造收据；`src/ParallelWorld/ParallelScoringDetector.cc:32-39` 的 TLS manager 为空时只打印并 `AbortRun(true)`，不调用 `RecordOutputFailure`。
- **触发反例**：某 worker 缺失 SD 绑定时，该 worker 的 ghost 命中无法进当前 scorer，但主线程 Stage B 的质量检查仍可报告 `kernel_constructed`；若发生 TLS manager 缺失，用户也只能依赖 abort 的后续归类，缺少合同要求的明确 `parallel_world_sd` 失败锁存。此处为未注入、未实际复演的故障分支。
- **合同**：冻结合同 §5.4–5.5、§6.2.4、§6.2 统一失败策略要求各 worker 正确 SD 路由及失败报告。
- **最小修复**：在每线程的 `ConstructSD()` 验证所有 ghost logical 的当前线程 SD 指针与登记实例一致，启动前汇总可核对的 worker 初始化证据；TLS 缺失必须通过可从 worker 传播的故障登记锁存为 `parallel_world_sd`，避免仅日志/软中止。

### P2-4　名称校验与数值上限尚不闭合

- **位置**：`src/ParallelWorld/ParallelWorldConfig.cc:186-197` 仅检查 root 名和构造前通常为空的 `GeometryRegistry`，未使用 `GeometryManager::HasConfiguredVolume`（`src/Geometry/GeometryManager.cc:622-632`）检查全部质量体积名；`:380-403` 将 4096 上限分别应用于每个 grid，`:445-448` 不限制全部展开单元数；`:536-539` 在质量相加后未检查每项 `referenceMassKg` 与 `totalMassKg` 是否有限。
- **触发反例**：`[parallel_world]/name` 取质量几何的某个子 volume 名可绕过注册前重名预检；两个合法 4096 单元 grid 会合计建立 8192 个 ghost 单元；对于极端合法浮点尺度，有限的密度与体积之积、多个质量之和可能溢出为 `inf`，后续摘要/effective field 不可信。是否要求跨网格累计数量严格 ≤4096 需按冻结决定“上限4096为本阶段工程边界”直接执行。
- **最小修复**：用配置树核验全部质量体积名并验证并行声明名字符合法性；统一限制最终展开单元表数量，完成每项及总参考质量的有限/正数检查后才接收 Stage A。

## 已审与未审边界

- **已审（静态）**：H3 冻结决定与交付回执，`src/ParallelWorld/*`、`include/ParallelWorld/*`、`src/Detector/DetectorConstruction.cc`、`src/Core/SimulationManager.cc` 的新增接线、`src/Core/EffectiveSimulation.cc` 的实际快照消费者、`src/Scoring/ScoringManager.cc::ScoreParallelHit`、`DoseContext`、`ParticleHit`、`DoseScorer`、`FluenceScorer`、`ActionInitialization` 的线程本地 manager 建立、`main.cc`/`SessionServer.cc` 的 Stage B 调用位点；已有 grid CSV、Case M summary、专项测试断言。`ScoreParallelHit` 的显式 dose/fluence 路由与不写 hits/event Edep 结构符合合同 §4.6，未发现该入口本身的广播污染。Geant4 初始化次序与线程局部槽语义以冻结合同列示的上游源码定位和现有成功运行证据为辅助参考，未对所有上游实现路径做本地独立复审。
- **未审/不宣称**：未执行独立构建、单元测试、故障注入或真实输运；未验证 Geant4 11.3.2 在所有平台和所有线程调度下的 SD 实际执行；未覆盖 Q2 biasing、ROOT/mesh/field、Linux/CI、H3-3 GUI 文档、H3-4 Welch 正式统计判据、H3-5 发布验收。交付回执的两个专项及组件 18 项为主审已复跑证据，此审查不替换测试结论。
- **优先建议**：先修 P1-1 至 P1-5，补固定反例；再以同一冻结合同复核 P2 路径、原有通过的两个专项及 H3-4 前置资格。注册时点作为合同形式差异单独裁定。当前阶段标记仍为 **H3-2 待验收**。
