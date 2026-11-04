# Q2-4 预注册独立数学证据

2026-11-05；**这不是统计实验验收报告，尚未运行本方案的 Geant4 批次**。

设计输入：[有限覆盖设计](../../collab/decisions/20261105-q2-uncertainty-coverage-design-v1.json)。[独立 Decimal 程序](independent-design/check_finite_design.py)以 60 位精度计算二项概率，并用整数不等式判定覆盖集合；[原结果](independent-design/results.json)保存设计 SHA。

核验所得：N=2000、p=25/36、±2 倍未修正事件矩标准误差时，覆盖 K=1347…1429，覆盖概率约 0.95591371153155945；64 批少于 57 批覆盖的概率约 0.00698051532398271，少于 58 批则约 0.02237031361186788。中央 99% 总 K 区间为 [88464,89313]。两个各 1% 的检验只声明联合误拒绝率上界 2%。

数值确认只支持运行前阈值计算，不证明实际抽样覆盖、模型正确或普适置信水平。完整输入/行存在性/观测量与精度规则待方案交付后独审冻结；任务入口见[预注册指令](../../collab/inbox/20261105-q2-uncertainty-preregister-v1.md)。

## R1 独立复验与冻结

原草案的精度/公式及计数规则失败保留在[初次快照](precision-first-draft.zip)、[快照清单](precision-first-draft-manifest.json)、[精度反例](precision-counterexample.json)和[R1审查](../../collab/reviews/20261105-q2-uncertainty-preregister-r1.md)。没有追改旧件。

修订后 C 盘独立复演覆盖 19 项、矩/精度 22 项及额外 6 项核对通过，17 输入身份一致；[R2结论](../../collab/reviews/20261105-q2-uncertainty-preregister-r2.md)准予[冻结合同](../../collab/decisions/20261105-q2-uncertainty-freeze-v1.json)实施。[机器签收](r1-acceptance-receipt.json)明确 simulations_executed=0、cpp_component_executed=false。

[执行方案原件](author-r1.zip)与[独立复演原件](independent-r1.zip)均含相应源文件和冻结合同；[归档清单](r1-archives-manifest.json)逐文件核对 SHA/CRC。当前只签收预注册，不代表 Q2-4 的真实实验通过；下一步是[固定实施任务](../../collab/inbox/20261105-q2-uncertainty-execute-v1.md)。
