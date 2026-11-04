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
| Q2-3独立参考/适用域 | 进行中 | LET仅电磁v2、Dose四能点及Fluence已签收；DDD修订受限报告已独审签收，NIEL表审计进行中 |
| Q2-4统计不确定度 | 未开始 | 当前矩复算可引用，专项覆盖/边界/MT实验待预注册 |
| Q2-5 XS偏置/analog | 未开始 | 实际worker权重与独立批次方案待签收 |
| Q2-6整阶段验收交班 | 未开始 | 支持平台/版本回归、严格证据/云结果和科学范围签收 |

## 本轮结果
DDD原261项通过中的错误完整折积证明已撤回，首次反例及失败脚本保留。R1经C盘独立复核：整体limited，263项中257 pass / 0 fail / 6 limited；两个冻结参考点仍满足原1%加3σ。7个反例命中预定真实fail，51项可核实数据复算通过并另列观测限制。D/C各34个原始输入/输出/identity及C运行记录未变，没有重跑后端。主审接受修正后受限报告，不签收完整路径/事件全集/逐步折积；证据docs/verification/q2-ddd-reference-20261105，独审docs/collab/reviews/20261105-q2-ddd-reference-review-r2.md。未修改产品、冻结参数或容差。

## 运行中任务
原task g4-j3-desktop-20261103、session-9d7a035a-8a42-4f18-885b-beb4a0ec12f4。round81请求q2-niel-table-audit-v1-preregistered-20261105已接单，实际Flash/Max并运行。合同docs/collab/decisions/20261105-q2-niel-table-audit-freeze-v1.json，只读审计两张表、单位转换和插值，不运行Geant4；输出out/collab/q2-niel-table-audit-v1，回执docs/collab/outbox/20261105-q2-niel-table-audit-v1.md。原R1 turn65已结束，无主审后台命令。游标/回执在out/collab/desktop-bridge/context.json。

## 下一轮目标
独立复核表结构/原始SHA、95假设输入单位算术和1MeV插值、真实反例，物理评价保留limited，不以不同评价数值差推定缺陷。其后先按docs/collab/reviews/20261105-q2-uncertainty-preregister-review.md修正统计期待值，冻结Q2-4/5的有限批次/种子/判据，再实施。保持Q2未关闭和当前定时阶段，不重跑既签收参考或扩展观察工具。

## 待用户决定/限制
| 项 | 决定 | 影响/动作 |
| --- | --- | --- |
| LET完整强子混合谱 | 主审已签收适用域限制，v1仍失败 | EM-only两能点已验证；完整强子LET_d未获外部验证，不能据v2外推；统计相关仍归Q2-4 |
| DDD逐步观测 | 主审已签收受限范围，整体limited | 普通hits不是计分步/事件全集，且缺步平均动能；错误证明已撤回，完整逐步验证未获证明；未确定后端结果缺陷 |
| NIEL表物理评价 | 尚未独立验证 | 95假设输入与版本/模型数值未获权威全文对齐；先完成表级算术审计，不称数据物理验证通过 |
| WSL挂载运行根Errno22 | 主审已签收 | Linux自身文件系统复演成功，原入门恢复路径保留 |
| F2参数unknown/run0摘要横线 | 主审已签收后续 | 逐轮数据与回执完整 |
| J3主题响应与WSLg限制 | 主审已签收 | 原最终报告范围维护 |

## 后续待办
Q2→H2→H3→F3→F7及ROADMAP后续。Windows/Linux统一版本、分平台打包。额外想法不增加阶段前置；D盘交付，C盘独立复核。Q2关闭后才同步阶段状态与定时任务，并实际启动H2。若需更强折积观测/能量相关解析补证，另立后续任务，不作为Q2新增前置。
