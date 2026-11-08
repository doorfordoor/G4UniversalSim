# 架构规划源码核对记录

日期：2026-11-08。性质：主审针对用户审查文件的有限静态核对，不是全仓审计、独立物理复现或实施验收。

## 基线与范围

- 先读取 CURRENT-SUPERVISION，再查看实际 HEAD/dirty。HEAD `55ef3d623ea6a1ed6a70314c07a40d175ba1f603`；原 K2 工程 `64bacb3e`、产品 `b1a7ffbc`、模板 `b2285d11` 保持原身份。
- 用户原审查基于 `83c0b139`。本轮未下载或运行该旧版本，只比对其具体论点与当前源码；不声称已完成两版本全 diff。
- 输入文档 SHA-256：`42d96b0039539ec2ec5137045655e8f3eae68f697e5e0a815e777ba4c64fe08a`。
- 18 项源码/文档样本的原始字节哈希、5 项已有 dirty 的保护哈希及输入身份保存在 `out/collab/20261108-architecture-plan/baseline.json`。本轮没有执行产品测试、创建新模型会话、派发作者任务或恢复自动化。
- 本轮读到的工作树源码与行号用于定位；不把这些抽样阅读冒称整套产品已在本轮复验。

## 论点核对

|编号|实际位置（本轮行号）|观察|证据等级及决定|
|---|---|---|---|
|E1|`src/Geometry/GeometryManager.cc:234`、`:255`、`:481`|LoadGeometryConfig 先替换 templateRoot/root，再 ApplyUserAddedVolumes；循环中验证、重名检查可抛异常；之后才更新路径和 EffectiveConfig|控制流风险成立；未运行反例。AR1 验证实际可达失败及事务范围，不声称已有 GUI 数据损坏|
|E2|`src/Scoring/ScoringManager.cc:235`、`:481`；`include/Scoring/ScorerBase.hh:9`|注册保存对象；线程复制设置后仅 EnsureDefaultScorers；基类无线程构造合同|当前扩展接口缺口仍存在；限定到该路径，不称内置计分失效。AR2 计划补明确工厂及兼容处理|
|E3|`src/Core/SimulationManager.cc:898`、`:983`；`main.cc`|Configure 串联多 Manager、来源及 H3 依赖；main 共 1374 行，SimulationManager 共 1918 行|职责集中可见；行数不等于复杂度指标，没有开发速度/运行速度因果测量|
|E4|`include/Geometry/VolumeNode.hh:22`；`src/Geometry/GeometryConfig.cc:515`；`src/Geometry/SolidRegistry.cc:72`|通用 parameters 与 userProperties 仍在；已有 SolidRegistry，能力与 factory 共一记录|应复用注册表，改进明确描述/校验，不再建设平行注册机制|
|E5|`gui/g4usim_gui/core/project.py:38`；`window/transactions.py:266`、`:278`；`main_window.py:33`|typed 与 flat 兼容状态并存；捕获快照读控件和 pending table editor；MainWindow 由多个 mixin 共享 self|状态边界值得迁移，不据此认定现有事务已失效|
|E6|`gui/g4usim_gui/core/edit_transactions.py:50`；`core/experiment_workflow.py` 文件说明|已有 EditSession、私有快照、历史预算、异步任务归属与 evidence 分层|保留现有事务/编排资产，只迁移缺少的数据所有权与适配入口|
|E7|`include/Config/EffectiveConfig.hh:33`、`:48`|已有 requested/resolved、origins、application status、evidence level、revision 和 generation|新计划与这些字段衔接，禁止重复建来源/实际应用系统|
|E8|`include/ParallelWorld/ParallelScoringDetector.hh:19`、`:51`；H3 最终报告|已有 leaf/root/envelope 归属和不得把 ghost step 写入普通 hits 的合同；H3 已验收|原报告“实现 H3 前规划”时点过期，迁移按当前合同保护；旧科学结果按原身份复用|
|E9|`CMakeLists.txt:44`、`:80`、`:127`、`:151`、`:143`|生产 src 全量收集；应用与组件目标组织不同，H2 CTest 已显式 source root|可规划 target 责任收敛；未完成依赖图/编译成本测量，不声称存在确定的循环依赖或速度收益|

## 当前事实的校正

K2 已完成独立工程导出链及固定范围验收，不再是未来方案；H3 已完成限定平行世界计分，不能按旧审查重新开阶段。GUI 已有独立事务核心，几何已有能力注册表。外部报告关于保留既有技术路线、区分科学验证与结构优化、渐进迁移的建议与当前证据一致。

本轮只建议改进内部模块边界；关于“早期架构已较严重拖慢”的程度暂无法量化。AR0 将建立代表性变更影响清单，AR6 再报告事实性对照。F3 三批 inconclusive 与 Q2 已签科学限制均不改标签。

## 规划交付与验证边界

主计划：[架构优化与渐进迁移规划](../../架构优化规划.md)。本轮只新增规划/核对文档并更新 CURRENT 的当前目标，不修改生产代码、测试、模板或 ROADMAP 用户讨论。

文件保护与链接核验结果记录在 `out/collab/20261108-architecture-plan/verification.json`。本轮无运行时/物理新通过结论；实施状态保持未开始。阶段实现前需按主计划 AR0 冻结比较合同与输入，再进行真实反例和受影响验证。
