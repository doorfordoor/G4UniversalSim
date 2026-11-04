# Q2-4 预注册草案 R1：精度边界须修正

2026-11-05；对 round82 草案的独立静态复核，实验尚未授权。当前阻止冻结的最小问题：

## 确定缺陷：省略尾零后的显示文本末位不代表 12 位有效数字精度

`out/collab/q2-uncertainty-proposal-v1/verify_moments.py:63`—67 采用 `Decimal(printed).as_tuple().exponent` 再取半单位；`proposal.json` 的 formulas.half_unit_interval 沿用此定义。生产者 `src/Output/OutputManager.cc:837`—841 和各 scorer 的 Number 则是 `std::setprecision(12)` 的 general 输出，会省略尾零。

反例：

| 显示值 | 草案半宽 | 12 位有效数字应使用的保守半宽 |
| --- | --- | --- |
| 1 | 0.5 | 5e-12 |
| 1000 | 0.5 | 5e-9 |
| 1e-9 | 5e-10 | 5e-21 |

实际接受区间可能被放宽数十亿倍，不能用于正式比较。对非零有限值，显式固定 `h = 0.5 × 10^(floor(log10(abs(d)))−11)`；用 Decimal.adjusted() 等数值量级计算，不按字符串小数位数。量级边界采用较宽一侧仍是保守界。打印的精确零按生产语义单列，不凭空赋 0.5 容差。传播此界到所有原始量/比值/矩的比较；保留已有充分位数示例，并补 1、1000、1e-9、0 的纯数学 fixture。不是统一改成 1e-12 相对门槛。

另两处措辞按现有生产者定稿，无需新实验/接口：

- N=1 以 `insufficient_events` 及真实观测为准；delta 公式在浮点下可能得到极小非零 R，不强制 R 字面等于 0，也不称其为可用置信误差。
- hits=false 的覆盖批次不具备逐事件路径直接观测。已知 geantino 直线路径模型 + entry/K、路径总量和事件二阶矩的一致性可以支撑该有限解析检查；不能声称读到了每个事件的完整路径。无需新增日志补这一点。

其它待决点可按原授权确定：Dose/LET 启用且无有效贡献时写表头并登记文件，见 `DoseScorer.cc:94`—114、`LETScorer.cc:148` 起；scorer_statistics 无 entry 则无文件，见 `OutputManager.cc:290`—291。最小一次性 C++ probe 调实际共享实现可用；保持 em=option4 的 geantino 方案；真实执行失败保留后停止，不补采样。均不需要再请求方向确认。

最小修复范围：现有方案目录内 verify_moments.py、生成器/JSON、cases.md/回执中的精度及上述表述。重新运行纯数学核验、同步 SHA；不编译/运行后端、不动生产或既有冻结参考。修好立即返回合同冻结，不扩工具。

## 同轮结构化合同续审：修正具体检查，避免拒绝合法实验

以下均属当前病例的定义修正，不增加病例或实验：

1. `proposal.json` 的 `UNC-LET-COV` / `LET-COV-RD` 把两个平方矩的分母写反。令 A=Σwl、B=ΣwSl、C=ΣwS²l，则 `R_d² = sum_sq_wS2l/C² + sum_sq_wSl/B² − 2 sum_wSl_x_wS2l/(BC)`。顶层通式正确，逐病例规则、生成器及文案须一致；加入不对称 B/C fixture，避免对称示例掩盖交换错误。这是公式纠正，不新增物理门槛。
2. `TOT-NOT-HITS-ROWS` 声称把 event_edep 的行数当 N 必须被拒绝，但同一方案要求一行一个已完成事件，因此合法完整文件行数就是 N。应拒绝“非零贡献 entries 或普通 hits 行数替代完整 N”，并对缺行/重复行直接拒绝。若实际某病例 entries=N，不得硬说能检出相同值，使用明确不同的副本/已有组件 fixture，保留原种子。
3. `MT-LET-MERGE` 除 A/B/C/BA/BC 外必须把三个二阶矩分别求和后计算误差；不能只合并第一矩及交叉矩。`MT-NO-WORKER-AVERAGE` 不得要求本次实际分配下错误平均必定与合并值不同：N=2 可能同落一个 worker，或数值退化相同。正常稀疏实验仍按真实分配核对；可区分的反例用预先指定的组件/副本 fixture，不换种子强求分配。
4. event_edep 已提供 weighted_edep_MeV，单敏感体下直接累计即可与 weighted dose 对齐，不需要另有逐步 weight 列或先证明全部权重等于 1 才允许此恒等式。顶层 ratio_delta 所谓“unweighted per-event moments”应表述为“对每事件加权 tally 所形成的矩”；当前单位权重病例不等于通式无权重。

R1 的其余判据不变；完成这些局部修正及纯数学复算后即可交冻结复核，不要求额外过程/数据收集。
