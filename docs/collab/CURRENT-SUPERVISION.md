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
| Q2-1定义/参考/预注册 | 进行中 | 四量参考及NIEL表审计均有独立冻结；统计/偏置专项方案仍待签收 |
| Q2-2确定性单位/实现 | 通过 | Windows四类五运行、201检查及27反例；跨平台正式范围归Q2-6 |
| Q2-3独立参考/适用域 | 限制 | 主审已签收限定范围：LET电磁v2、Dose四点、Fluence；DDD完整观测及NIEL物理评价限制见独审/归档，不外推物理等级 |
| Q2-4统计不确定度 | 进行中 | round82只编制预注册；固定7类病例、64独立批次/种子和有限二项判据，独审冻结前不运行 |
| Q2-5 XS偏置/analog | 未开始 | 实际worker权重与独立批次方案待签收 |
| Q2-6整阶段验收交班 | 未开始 | 支持平台/版本回归、严格证据/云结果和科学范围签收 |

## 本轮结果
NIEL表审计经C盘独立复演：27 pass / 0 fail / 3 limited；60位Decimal另完成17项复算，5个负对照均命中真实fail。两表和冻结合同SHA未变，未运行Geant4。结构/算术通过，95假设输入及ASTM/SR-NIEL表/模型物理评价仍limited，主审按此范围签收。原件和CRC/逐文件SHA见docs/verification/q2-niel-table-audit-20261105，独审docs/collab/reviews/20261105-q2-niel-table-audit-review-v1.md。DDD原错误证明已撤回，修正受限报告和首次反例继续保留；未改产品/参考/容差。

## 运行中任务
原task g4-j3-desktop-20261103、session-9d7a035a-8a42-4f18-885b-beb4a0ec12f4。round82请求q2-uncertainty-preregister-v1-20261105已接单，Flash/Max，按docs/collab/inbox/20261105-q2-uncertainty-preregister-v1.md只写方案/输入草案及纯数学核验；输出out/collab/q2-uncertainty-proposal-v1，回执docs/collab/outbox/20261105-q2-uncertainty-preregister-v1.md。原turn66已完成，无主审后台命令。请求/游标见out/collab/desktop-bridge/context.json。

## 下一轮目标
独审Q2-4病例行存在性、公开矩/精度/真实共享C++组件边界，以及64批有限覆盖判据，冻结后派实施，不先试跑改阈值。数学设计输入docs/collab/decisions/20261105-q2-uncertainty-coverage-design-v1.json不等于实验授权；依据既有预审修正，不扩工具。随后完成Q2-5偏置方案及固定清单后续；Q2仍未关闭，定时阶段不变。

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
