# R-03 / R-04 接续修复提案

基线：`d286577` 加 R-01/R-02 工作区候选；分支 `roadmap/2c-effective-config`。新构建哈希、反例输入和输出见 [当前复现](../../verification/r03-r04-current-20261029/README.md)。本文件先定范围；R-03/R-04 尚未修改，统一回归期间代码冻结。

## R-03：确定为缺陷

`include/Scoring/DoseContext.hh:14-25` 注释与实际 `GetMass(true,true,material)` 不符；`src/Scoring/DoseScorer.cc:43-60` 的分子是本体沉积，分母却包含子体质量。新构建已复现水母体/铅子体算例，叶体对照正确。Geant4 的 [11.3.2 GetMass 接口](https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/geometry/management/include/G4LogicalVolume.hh) 明确 propagate=false 才是减去子体占位后的本体质量。

决定：恢复既有 per-touchable 本体 Dose 定义，不增加“整树剂量”功能；质量应使用步前材料，保持副本身份与单位。不能只改标签，也不能同时改分子来掩盖错误。旧含子体的 Dose 输出应标记需重新计算；文件列可保持，但须记录行为修正及适用范围。

允许文件：`include/Scoring/DoseContext.hh`、必要时 `src/Scoring/DoseScorer.cc`，`scripts/test_dose_scoring.py`、已有 `scripts/test_geometry_a5.py` 对应质量对照，输出契约、支持矩阵、agent-history/AGENTS、CHANGELOG、ROADMAP/STATUS。若实现发现额外生命周期变动，先补提案，不借机做整套计分重构。

验收：无子体叶体结果不变；同密度/异密度子体均以独立体积×材料密度计算正确本体质量；母子均敏感时沉积分开且分母范围一致；原 replica/逐副本异材料路径不回退；单/双 worker 与多 run 对账；质量非正/非有限明确失败。结果与原始 hits 的能量和独立解析质量比较，不把复制新实现的公式当唯一判据。嵌套参数化几何若不能可靠验收，应明确限制，不能泛称全部复杂几何已支持。

## R-04：确定为缺陷

`src/Geometry/GeometryManager.cc:645-664` 按名字登记 GDML 体积；`src/Geometry/GeometryRegistry.cc:56-59,102-107,152-154` 将名字小写归一，`src/Detector/DetectorConstruction.cc:70-71,109-110` 只绑定归一后名单。新构建 mesh 与实际命中均确认 `Sensor/sensor` 丢失后者。

决定：GDML 导入的 SD 绑定以实际逻辑体身份为准；继续保持 INI 的大小写兼容规则，不全仓改变命名接口。优先给 registry 增加按真实逻辑体登记的路径，去重按同一对象而非 lowercase 名字。运行时指针不得作为持久对象 ID。显式名单若匹配多个完全同名对象，应明确拒绝歧义或给出可验证的选择规则，不静默任选。

允许文件：`include/Geometry/GeometryRegistry.hh`、`src/Geometry/GeometryRegistry.cc`、`src/Geometry/GeometryManager.cc`，必要时 `src/Geometry/GdmlIO.cc` / `src/Detector/DetectorConstruction.cc`，`scripts/test_geometry_a5.py` 及对应文档/约束。bias/region 映射目前是需另审，不以本次 SD 反例直接宣告已修或有缺陷。

验收：GDML auxiliary 和显式 sensitive_volumes 两条入口，大小写不同双体分别放源都产生正确 hits；普通不同名对照；同一对象重复指定不重复绑定/计分；INI 旧名称行为保持；单/双 worker 与多 run；无 GDML 构建仍按既有能力拒绝。原 source/scoring/geometry 回归及最终完整平台无 FAIL/SKIP，通过证据门禁后才关闭问题。

方法风险 V-01、R-05/R-06/R-07 的实现不并入这两个补丁；它们仍在同一可靠性批次内，分别确定估计口径、兼容策略和验收。
