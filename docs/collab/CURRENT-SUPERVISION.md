# 当前监督接续索引

更新2026-11-05。当前检查点覆盖保存，阶段历史见最终报告。

## 当前阶段
Q2科研基准与适用范围。E4文档范围与附带安装CI均已完成。

## 清单文件
docs/collab/decisions/20261105-q2-closeout.md

## 候选身份
D盘roadmap/Q2-scientific-baselines，基线1280b44dda2a0e6bf8ccc67388b6ec77b6e46890。E4文档候选f7793dcb、云环境修复92b285d6，应用产品864bc036。codex与roadmap/E4-docs远端均读回1280b44d。C盘j3-final独立构建与effective-config保留，q1-final为codex集成区。D盘另一路H8工作区改动保留，逐路径暂存。

## 清单状态表
| 清单项 | 状态 | 责任与证据 |
| --- | --- | --- |
| Q2-1定义/参考/预注册 | 进行中 | 修订提案已审，四个实现病例与LET、Dose、Fluence参考均有独立冻结；统计/偏置方案仍待签收 |
| Q2-2确定性单位/实现 | 通过 | Windows独立四类五运行exit0、201检查及27反例通过，跨平台正式范围仍归Q2-6 |
| Q2-3独立参考/适用域 | 进行中 | LET仅电磁v2通过独立116项比较、4项误差区间及3反例；完整强子v1失败保留；四个Dose参考病例已派执行 |
| Q2-4统计不确定度 | 未开始 | 固定种子、样本和判据后实验 |
| Q2-5 XS偏置/analog | 未开始 | 实际worker权重与独立批次 |
| Q2-6整阶段验收交班 | 未开始 | 支持平台/版本回归及科学范围签收 |

## 本轮结果
LET v1两后端各exit0，101项比较中100MeV辅助5%项失败，两个LET_t外参项通过；原失败与设计审查已归档。v2回到原提案仅电磁option4范围，全部门槛/N/cut/参考不变，新种子20261211/20261212；C盘独立两运行exit0，各2000事件，116项比较、4项公开矩误差区间与3反例通过。限定签收见docs/collab/reviews/20261105-q2-let-reference-review-v2.md，原始证据及归档CRC/SHA见docs/verification/q2-let-reference-20261105。没有修改产品。Dose四能点及随机宽束Fluence解析值已在运行前冻结。

## 运行中任务
DeepSeek原task/session，round76请求q2-reference-dose-v1-preregistered-20261105已接单；实际Flash/Max。按docs/collab/decisions/20261105-q2-dose-reference-freeze-v1.json运行四个仅电磁PSTAR剂量病例，各20000事件、固定四种子、原2%加3σ，输出只写q2-reference-dose-v1，回执outbox/20261105-q2-reference-dose-v1.md。无主审后台命令。原LET turn61已完成。

## 下一轮目标
独审四Dose病例及hits/质量/注量单位复算、实际完成与产物身份；随后执行已冻结的Fluence解析例、NIEL表审计及Q2-4/5预注册。Q2尚未关闭，不重开J3/F2/E4；阶段不变，定时提示仍为Q2。

## 待用户决定/限制
| 项 | 决定 | 影响/动作 |
| --- | --- | --- |
| LET完整强子混合谱 | 主审已签收适用域限制，v1仍失败 | EM-only两能点已验证；完整强子LET_d未获外部验证，不能据v2外推；统计相关仍归Q2-4，未确定产品缺陷 |
| 双平台安装附带CI | 已闭合 | 原artifact及阶段日志核验通过 |
| WSL挂载运行根Errno22 | 主审已签收 | Linux自身文件系统复演成功，入门有具体恢复路径 |
| F2参数unknown/run0摘要横线 | 主审已签收后续 | 逐轮数据与回执完整 |
| J3主题响应与WSLg限制 | 主审已签收 | 原报告范围维护 |

## 后续待办
Q2→H2→H3→F3→F7及ROADMAP后续。阶段前置严格对应冻结清单；额外CI/工具事项有独立记录。Windows/Linux统一版本分平台打包。D交付、C独立复核。
