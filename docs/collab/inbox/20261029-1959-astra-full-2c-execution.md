# 完整2C启动：实施边界与验收

基线：f25da40（已集成Q1）；分支roadmap/2c-effective-config；工作区C:/Users/123/.codex/worktrees/effective-config/G4UniversalSim。用户已授权整阶段连续实现、审查与验收，并要求DeepSeek参与前端设计。本信是实施提案和分工，不是完成声明。

## 保持的设计决定

沿用1010开工信和EffectiveConfig消费者清单：11类真实消费者全部接入，不能抄schema条数冒充覆盖。保留JSON Pointer稳定身份、类型化请求/解析值、完整来源链、失败不提交revision、不可变旧快照、配置与应用证据分离。读入指纹来自实际解析的同一份字节；不能导出时重开文件计算。

三时点configure、run_begin、finalization接统一registry；配置revision只随成功配置事务变化，不因查看/导出/应用收据增加。run_begin逐run及真实worker独立收据，master缓存不能作为worker证据。未知原生GPS/Geant4修改明确unknown并保留命令来源，不把任意ApplyCommand返回0都当生效。失败最终化保留真实已有事实，不制造run_begin。

新增[modules]可选开关scoring/biasing/field/trajectories=off|auto|on；缺失mode保持旧语义，基础geometry/source/physics禁止关闭。off与活跃显式请求冲突即拒绝；auto只由明确请求和确定性依赖启用、说明reason，不引入新物理。biasing on/auto需要完整显式规则，field需要有效定义/挂接，trajectories需要显式正数事件上限。显式旧布尔与mode结果矛盾拒绝。实际各配置键与schema由消费者代码核对后冻结，不能修改旧默认以便测试。

旧--dump-effective-config和summary字段兼容；正常运行新增快照文件须成功关闭后登记，与输出失败锁存和本轮manifest一致。只读导出不能执行macro/初始化/创建运行目录。

## 写者与文件范围

- root：SimulationManager/main、动作/Detector生命周期、ConfigManager消费桥接、Source/Physics/Scoring/Field/Output适配与外部输入、模块依赖、schema生成、统一runner、文档集成及最终裁决。按实际负荷可在信箱中明确移交独占文件。
- q1_field（Sol）：EffectiveConfig模型、IniReader、公共InputProvenance工具及基础专项。先发准确共享API再实现。
- q1_geometry（Sol）：Materials/Geometry/Biasing消费者与真实对象应用证据、新消费者专项；先与root对齐接口，禁止同时改root生命周期文件。
- f6_design（Sol协调DeepSeek）：DeepSeek实际API前端设计；effective_config读取器/差异模型/对象摘要页面及专项。共享i18n/导航需先登记单写者。
- 实现者之外的代理交叉复核，root审查所有证据并集成；DSH原D盘工作区保留，不并发写入。

## 验收与提交节点

1. 基础契约：事务替换/删除、重复及别名来源、默认/preset/INI/CLI/命令覆盖、解析同字节哈希、拒绝事务原子性和不可变快照独立测试。
2. 完整消费者：11类分别有配置正反例；源高级分布/具名源/相空间、独立材料/几何/GDML/STL、物理/场/mesh/NIEL/偏置、输出/径迹均按真实模式投影，量纲明确，未使用缓存不导出。
3. 运行接线：配置→合法macro→ST/MT/多run→最终化；失败/无run/dry-run/原生命令未知边界；worker收据与实际内核对象相符，输入变化不篡改旧快照。
4. 模块mode：缺失保持旧语义，off/on/auto和旧布尔的全部冲突/依赖/原因；schema与GUI不暗中产生未支持值。
5. GUI：真实后端快照加载、阶段/run/thread选择、对象摘要、类型/单位/来源链、两快照新增/删除/变化、损坏加载保留旧数据并标陈旧；中英/明暗/实际Windows窗口。
6. 冻结后干净Release、Windows全量与Linux11.3.2/11.4.3真实CI、严格证据门禁和Q1同v3基线对照，归档原始失败及修后证据。只读review不能代替这些测试。

提交按可审查的基础模型、消费者、运行证据、GUI/mode、整体验收节点进行，内部节点不要求用户继续。阶段是否完成仍只维护ROADMAP；过程证据在各review，当前接续摘要更新STATUS，不新增平行状态页。2C不承诺物理正确性、随机逐位重放或安全内核热重建，Q1拒绝边界保留。
