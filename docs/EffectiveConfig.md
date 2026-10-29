# 有效配置快照（完整 2C 实施中）

完整 2C 的消费者、三阶段快照、模块策略和只读 GUI 已有工作区候选实现；状态仍为 **in_progress**。当前不能将独立编译、局部专项、旧 configured 子集或 Q1 的绿色报告称作完整 2C 验收。最终结论由主任务在冻结源码后完成干净 Release、Windows 全量、Linux 11.3.2/11.4.3 真实 CI 和严格证据门禁后记录。实施边界见 [开工信](collab/inbox/20261029-1959-astra-full-2c-execution.md)，状态以 [ROADMAP](ROADMAP.md) 为准。

## 使用路径与只读边界

`--dump-effective-config <新JSON文件|->` 复用真实 Configure 和递归 macro preflight；不执行 macro、不初始化 Geant4、不启动事件、不创建运行输出目录。指定文件必须不存在，包括不得覆盖已有硬链接；`-` 写标准输出。配置、预检或写入失败返回非零。此入口只展示 configure 阶段，不能据此宣称宏命令或内核已应用。

正常运行的候选实现写出 `effective_config_configure.json`、逐 run/thread 的 `effective_config_run_<R>_t<T>.json`、线程最终化 `effective_config_final_r<R>_t<T>.json` 和进程 `effective_config_finalization.json`。文件成功关闭后才登记到本轮输出清单，写出失败走输出失败锁存。配置快照保持最初接受的 configure 状态；后续 macro 不反写它。失败、dry-run 和无 run 路径不得补造 run_begin；文件是否产生应结合摘要、manifest 和实际执行路径检查。

上述已登记的快照在摘要与 metadata 的文件格式清单中标注 `g4usim_effective_config_v1`。dry-run 也可生成 configure/finalization 配置证据，但必须为 `execution_performed=false`、`run_id=null`，不能把这些文件计为已执行模拟或运行成功。格式登记仅说明 writer 的协议，不证明文件未被外部篡改。

GUI 第 9 页“有效配置”只读取快照或快照集合。可选择阶段/run/thread、查看对象摘要、类型化值、单位、来源链和应用证据，并比较两份快照的新增、删除和值/类型/来源变化。单文件上限 4 MiB，集合另有累计大小限制；损坏加载保留旧数据并标陈旧。页面不修改项目或运行参数，不能用差异方向、时间字符串或跨进程 revision 推断配置新旧。前端由 DeepSeek 实际 API 参与设计，采纳与纠偏见 [设计记录](collab/outbox/20261029-deepseek-full2c-design.md)；该设计输入不是运行验收。

## 数据与应用证据

- 保留 `g4usim_effective_config_v1`，增量扩展，旧 `effective_*` 摘要和 `run_summary_schema_version=1` 兼容。JSON Pointer 稳定身份保留名称大小写，`~`/`/` 分别转义。
- `requested` 是已记录的请求，`resolved` 是消费者接受的解析值；都是 JSON 类型，缺失与显式 null 不同。未知请求不能从默认值倒推。模式不使用的旧缓存字段不得导出为当前生效值。
- `origins` 按覆盖顺序记录 default/preset/INI/CLI/成功命令及派生原因，保留原始文件/行/别名、shadowed/accepted/derived。输入 SHA-256 来自实际解析的同一份字节；导出时重开文件的哈希不能冒充该证据。
- `revision` 是同一个 registry 成功配置事务的计数；原子替换/删除拒绝时不发布新值或来源，旧快照不可变；空或完全相同事务不加 revision。查看、导出和添加应用收据不增加它，跨进程不能比较先后。
- `configuration_generation` 是模块消费者的配置事务身份，与 registry revision 不同。同值但新来源仍须区分代次，旧收据不能借同值沿用。
- `application_status`、`evidence_level` 与配置值分开。`manager_accepted` 不足以支持 applied；观察证据须绑定对应字段、代次、解析值摘要及真实 run/thread。master 计划不能证明 worker 已应用，进程最终化也不能把单 worker 观察提升为全 worker 结论。
- 三阶段为 configure、run_begin、finalization。未知原生 GPS/Geant4 命令影响必须撤销相关应用确定性并保留命令来源；ApplyCommand 返回 0 本身不足以证明实际生效。

快照不是随机引擎检查点，不保证跨机器逐位重放，不证明物理正确，也不放开 Q1 的命令状态与热重建拒绝边界。

## 11 类真实消费者候选覆盖

下表描述已落盘的适配入口及审查要求，不表示这些病例已经全部通过。字段范围以真实消费者模式投影为准，schema 条数不能替代覆盖判定。

| 消费者 | 候选实现与核验边界 |
| --- | --- |
| 启动参数/主 INI | ConfigManager、SimulationManager 合并默认/INI/CLI，记录输入身份和已接受字段；CLI 锁定及拒绝事务须保持原语义。 |
| 旧式单源 | SourceManager 导出实际源模式适用的位置、角度、能量、粒子/离子和 preset 来源；单能缓存不得冒充所有能谱。 |
| 命名源/相空间 | 使用稳定源对象名和输入文件身份、强度/recycle；相空间实际读取与 GPS 默认分离，核对 histories/particles 和耗尽路径。 |
| 几何 | GeometryManager/模板、STL/GDML 输入捕获、真实构建对象观察；独立文件来源、单位及对象身份需一致，预览不能替代内核证据。 |
| 材料 | MaterialIniReader/MaterialManager 记录元素/同位素/材料定义、同字节输入与实际 G4Material 观察；失败加载不得污染旧状态。 |
| 物理 | PhysicsManager 记录 reference/EM/构造器、cuts 与限制条件，结合真实初始化观察；过程存在不等于物理基准通过。 |
| 计分与 mesh | ScoringManager、ScoringMeshConfig、NIEL/相空间输入记录模式适用设置及 worker 观察；逐线程克隆、统计与 mesh 实际应用分开。 |
| 场 | FieldConfig/FieldSetup 记录均匀场、场图输入及实际每线程挂接；局部最近祖先和冲突拒绝保留。 |
| 偏置 | BiasingManager 记录逐规则配置、真实 worker TLS 算符/绑定和逐 run 收据；master 挂接、proposal/applied 次数不证明一般无偏性。 |
| 输出与径迹 | OutputManager 与 ScoringManager 共同覆盖格式、文件策略、径迹上限和实际线程输出观察；登记只证明组件报告写出。 |
| macro/交互 | MacroPreflight 和成功命令确认接来源事务、三阶段快照；失败命令不提交，原生命令不可观测时明确 unknown。 |

## 模块策略

可选 `[modules]` 键为 `scoring`、`biasing`、`field`、`trajectories`，取 `off|auto|on`。**缺失 mode 与显式 auto 分开**：缺失保留 legacy 默认（包括默认 SD scoring），显式 `auto` 只依据明确活跃请求或确定性依赖决定，没有请求时禁用；快照保留这一区别，不能把缺失伪造成用户请求 auto。geometry/source/physics 为基础模块，禁止关闭。

当前候选中，`off` 与显式活跃请求冲突即拒绝；`on` 要求已有有效活跃配置，空 hook 或只有 physics wrapper 不是完整 biasing 规则；`auto/on` 与相关显式 false 旧开关冲突也拒绝。不创造规则、场定义或轨迹上限。biasing 新旧规则语法的候选解析与最终策略分开，缺失 mode 保留旧门控语义。

scoring 策略覆盖 sensitive scorer 和 mesh 请求，但 mesh-only 不启用独立 SD scoring 门控；`[scoring]/enabled=false` 可与有效 mesh 共存。phase_space 边界输出和 trajectories 不依赖 sensitive scorer 门控；scoring off/auto 的抑制不得清除两者。trajectories 按独立模块策略处理，需要显式正事件上限才构成活跃请求；有效场定义才构成 field 请求。后续命令不能绕过已锁定 off，GUI 不因此获得完整配置编辑能力。

此前 off 静默覆盖请求的候选缺口已由严格判定与模块矩阵更新替换；本段是源码审查结论，**仍待本轮真实模块矩阵和完整平台验收**，不能以脚本存在或静态审查宣称通过。

## 测试入口与交付门槛

统一入口 `scripts/run_m0_tests.py`：static 注册 `test_effective_config_model.py`、`test_input_provenance.py`、`test_effective_consumer_state.py`，需要可用 C++17 编译器（支持 CXX）；backend 注册原有导出与 geometry/materials（显式 `--backend`）、source/physics、output/mesh、biasing、scoring、modules；integration 注册生命周期和 GDML 捕获 helper；gui 注册旧查看器和集合专项。后端用 `G4USIM_EXE` 指向本轮新二进制；GDML helper 必须随构建生成，不能借旧二进制或独立 Xerces 编译代替完整 GDML 运行验收。

这些注册只使测试进入平台，不意味着已通过。最终需 ST/MT、多 run、失败/无 run/dry-run、未知原生命令、输入变化与拒绝事务反例，真实 GUI 中英/明暗/小窗检查，以及本轮完整平台报告和同 v3 基线证据门禁。历史子集清单与 source“待实现”说明已由本页当前候选说明取代，其旧验收范围不追溯扩大。
