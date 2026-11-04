# 当前监督接续索引

更新2026-11-05。覆盖保存当前状态；详细历史留在各分项验收报告。

## 当前阶段
Q2科研基准与适用范围。阶段未切换，定时提示保持Q2；J3/F2/E4已关闭，不重新开启。

## 清单文件
docs/collab/decisions/20261105-q2-closeout.md

## 候选身份
D盘roadmap/Q2-scientific-baselines；应用产品冻结864bc036d6d7752475e52db4efd2b950cabfcc3d，后端SHA f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f。当前独立科学运行均为Windows/Geant4 11.3.2；不冒充Linux/11.4或新云CI。C盘j3-final独立构建与原工作区保留，q1-final为codex集成区。D盘另一路H8的ROADMAP未提交改动保持原样，逐路径暂存。

## 清单状态表
| 清单项 | 状态 | 责任与证据 |
| --- | --- | --- |
| Q2-1定义/参考/预注册 | 进行中 | 四量参考/NIEL表审计及Q2-4统计合同已独审冻结；Q2-5偏置专项方案待签收 |
| Q2-2确定性单位/实现 | 通过 | Windows四类五运行、201检查及27反例；跨平台正式范围归Q2-6 |
| Q2-3独立参考/适用域 | 限制 | 主审已签收限定范围：LET电磁v2、Dose四点、Fluence；DDD完整观测及NIEL物理评价限制见独审/归档，不外推物理等级 |
| Q2-4统计不确定度 | 进行中 | R1预注册独审通过并冻结，round85/turn70已开始实施；69次后端运行及真实C++组件结果尚待交付 |
| Q2-5 XS偏置/analog | 未开始 | 实际worker权重与独立批次方案待签收 |
| Q2-6整阶段验收交班 | 未开始 | 支持平台/版本回归、严格证据/云结果和科学范围签收 |

## 本轮结果
Q2-4 R1预注册经C盘独立复演通过：覆盖19项、矩/精度22项，另6项新独立核对；17个输入及24个源文件SHA一致。省略尾零误差界、LET_d分母、事件N/MT退化分配及加权量对账已修正，原失败快照保留。合同docs/collab/decisions/20261105-q2-uncertainty-freeze-v1.json，SHA5768cc413d7e05b586fdbe8074342e52ec14cdbf27fbc037163604775e0381b6。独审docs/collab/reviews/20261105-q2-uncertainty-preregister-r2.md；原件/CRC/逐文件SHA和签收见docs/verification/q2-uncertainty-preregister-20261105。签收仅限方案/数学；该节点Geant4和真实C++均未执行，不能称Q2-4实验通过。未改产品/既有参考/物理容差。

## 运行中任务
原task g4-j3-desktop-20261103、session-9d7a035a-8a42-4f18-885b-beb4a0ec12f4。round83/84已于turn69完成；round85请求q2-uncertainty-execute-v1-20261105已实际进入turn70，Flash/Max。按docs/collab/inbox/20261105-q2-uncertainty-execute-v1.md，仅实现/运行冻结Q2-4；输出out/collab/q2-uncertainty-v1，回执docs/collab/outbox/20261105-q2-uncertainty-v1.md。完整69次、130123计划事件与真实共享C++组件待实际收据，不凭接单称完成。请求/游标见out/collab/desktop-bridge/context.json；无主审后台命令。

## 下一轮目标
跟进原turn70，不重派；准备独立审查运行器/比较器/反例及C++真实实现链接，交付后核原始事件/worker矩/完成状态和产物SHA。路径矩与注量矩按V分别换算；单批未覆盖是正常观察，64批结束才判覆盖数及总K，不替换种子/扩大门槛。独立复演不合并为128独立批次。随后按docs/collab/reviews/20261105-q2-biasing-preregister-review.md推进Q2-5。Q2尚未关闭，定时阶段不变；不重跑既签收参考或GUI矩阵，不扩工具。

## 待用户决定/限制
| 项 | 决定 | 影响/动作 |
| --- | --- | --- |
| LET完整强子混合谱 | 主审已签收适用域限制，v1仍失败 | EM-only两能点已验证；完整强子LET_d未获外部验证，不能据v2外推；统计相关仍归Q2-4 |
| DDD逐步观测 | 主审已签收受限范围，整体limited | 普通hits不是计分步/事件全集，且缺步平均动能；错误证明已撤回，完整逐步验证未获证明；未确定后端结果缺陷 |
| NIEL表物理评价 | 主审已签收适用域限制 | 结构/算术已独审通过；95假设输入及ASTM/SR-NIEL原值/模型未获独立物理对齐，不称数据物理验证通过 |
| WSL挂载运行根Errno22 | 主审已签收 | Linux自身文件系统复演成功，原入门恢复路径保留 |
| F2参数unknown/run0摘要横线 | 主审已签收后续 | 逐轮数据与回执完整 |
| J3主题响应与WSLg限制 | 主审已签收 | 原最终报告范围维护 |

## 后续待办
Q2→H2→H3→F3→F7及ROADMAP后续。Windows/Linux统一版本、分平台打包。额外想法不增加阶段前置；D盘交付，C盘独立复核。Q2关闭后才同步阶段状态与定时任务，并实际启动H2。若需更强折积观测/能量相关解析补证，另立后续任务，不作为Q2新增前置。
