# AR3 相空间动态状态失真修复决定

当前主审根据新原生证据确定修复方向；执行时点和完整恢复机制仍须独立审查。不是阶段签收，不放宽原磁场比较容差。

## 触发证据

`out/collab/20261108-ar0-ar6/ar3-phase-charge-r2/phase-charge-f009_fjc` 的固定磁场连续/重放比较失败：四事件均出现相同 y 偏差约0.0363704 mm，超过原0.01 mm；方向两分量也失败。旧证据保持 failed。

`dynamic-state-probe/REPORT.md` 的独立于输运的小型真实SDK组件表明：同一C12定义，primary电荷5.96566726277173被PrimaryTransformer转为dynamic电荷5，并生成1电子占据；原GPS q2对应4电子占据，动态质量不同。组件没有BeamOn或磁场积分，不把转换失真直接宣称为全部端点偏差的唯一原因。

## 有界修复要求

- 只标记本项目相空间创建的primary，以不可变、逐记录、由event/primary拥有的状态携带来源及数据；不增加全局缓存，不按PDG共享可写状态。
- 恢复发生在真实tracking/step/process初始化以前。优先审查StackingAction的窄接点；不能仅凭PreUserTrackingAction名称断言时序。默认派发分类与普通GPS/secondary行为保持。
- 不只恢复charge。记录和恢复同一边界的实际动态质量、逐轨道电子占据及磁矩；对极化状态明确记录或明确拒绝不支持范围，不能用粒子定义默认值冒充记录事实。
- 只使用SDK公开接口；恢复顺序须处理电子增减对charge/mass的联动，并核实际动量、速度、step初始化可见值。对重复分类、已有step、异常与所有权明确守卫。不得更改共享粒子定义。
- 新数据采用明确的新schema（拟v3），保留原列顺序与v2含义。旧v2离子缺少状态时不能机械补默认列宣称可信恢复；应提前拒绝并建议重录。v1非离子保留已说明的有限历史假设。最终支持范围以独审后的实现和验证为准。

## 验证与派工边界

先由不同执行者核SDK组件与恢复时点/接口方案，再冻结产品修复清单。当前AR3-r2正式兼容矩阵运行期间，不改产品或测试。可以在独立输出目录编译无输运SDK组件，不能以增加事件、换种子或放宽门限追通过。

修后须验证真实Transformer与生产恢复函数、同PDG多状态隔离、普通GPS及secondary不变、重复调用、非法状态拒绝；随后在新候选重新执行预先固定的场景比较。新schema负控、输出识别、兼容说明与独立复验不可省略。有限相空间记录不宣称保存完整随机引擎或过程检查点，也不能用这个限制豁免本次固定比较失败。

原合同 `20261109-ar3-phase-charge-contract.md` 及所有失败身份保留。本决定补充其已证实的状态缺口；实现未完成时AUD10及AR3继续开放。

## 主审SDK时序补核

本机 `G4StackManager.hh:133` 有公开 `GetDefaultClassification()`，`G4UserStackingAction` 保存非拥有的 stackManager 指针。正常恢复后必须保留实际默认分类，不能无条件返回fUrgent覆盖waiting/postpone或显式分类映射。

官方 [G4TrackingManager v11.3.2](https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/tracking/src/G4TrackingManager.cc) 中 SetInitialStep 先于 PreUserTrackingAction；[G4StackManager v11.3.2](https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/event/src/G4StackManager.cc) 先计算默认分类再调用用户分类。这支持选择更早的窄恢复接点，仍需独审实际接线及失败路径，不能据源码阅读代替原生验证。

官方 [G4PrimaryTransformer v11.3.2](https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/event/src/G4PrimaryTransformer.cc) 的离子分支将 primary 电荷换算后转为整数，再据核电荷差添加电子；与本机组件观测吻合。该转换路径及其质量联动是修复依据，不代表已证明全部磁场端点误差的唯一来源。

## 主审恢复边界补充

[官方 G4DynamicParticle v11.3.2](https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/particles/management/src/G4DynamicParticle.cc) 的复制构造保留 primary 指针。因此从该指针看到相空间标记并不足以认定轨迹是待恢复的新主粒子；parentID非零的secondary应在复用守卫前退出恢复，并保持状态和默认分类。必须用真实SDK复制动态粒子构造secondary的组件控制验证，不把合法继承指针误报成用户非法标记。同一primary被另一个parentID零轨迹重复使用的守卫另行保留。

本机 G4DynamicParticle.icc 的 SetKineticEnergy 仅在值改变时使beta缓存失效；同值重设不够。恢复代码须落实独审的缓存失效条件及专门负控，不能凭函数名或错误注释推断行为。

## ion-none规则纠正（主审及独审确认）

此前独审建议的一律拒绝ion-none过宽，已撤回，纠正见 `independent/ar3-phase-charge-review/dynamic-state/ION-NONE-CORRECTION.md`。proton q1/Z1与C12 q6/Z6的Transformer不添加电子，构造后的占据仍为none，可以原样恢复；只有记录none而真实转换路径会新建占据且无法窄接口清除时才提前拒绝。预判须覆盖实际atomicNumber分支与IsIon分配条件，并先验证整数转换和减法可表达；恢复端仍核实际none，不能只依赖预判。

原 `test_gps_sources.py` 的600事件质子记录—重放场景、输入与阈值保持。手写v1质子正例已与新安全合同不相容，应保留为迁移拒绝例；多粒子/权重/循环历史正例改为明确的v1非离子输入。授权将该测试纳入隔离稿精确写集，保存修改前身份，不通过减少原600场景规避兼容问题。

## v3安全构造方案批准

主审批准完整v3先通过primary的DBL_MAX“未指定电荷”哨兵跳过Transformer离子整数/电子构造分支，再由已审stacking接点恢复payload中的实际动态状态。独立真实SDK组件验证见 `independent/ar3-phase-charge-review/sentinel-probe-r1/REVIEW.md`：proton/alpha/e-/C12转换保持definition初值与none、primary payload关联保留，指定分数电荷对照仍复现原损失；无BeamOn，不替代首步/磁场验收。

仅用于完整v3且已验证definition，不扩未知、short-lived或光学光子等范围。v1/v2仍按原有限兼容政策与实际转换安全检查。此方案使真实none可保持，无需因构造器临时制造电子而拒绝可恢复状态；实际恢复端仍核SDK状态，不调用宽副作用SetDefinition。

日志和测试须区分构造哨兵、记录的实际电荷和恢复后真实首步电荷。原primary调试值不能充当物理状态证据；固定磁场终点及600质子原协议不放宽。采用更准确的动态状态观测不构成把原失败改判通过，旧失败与旧构造观测保留。
