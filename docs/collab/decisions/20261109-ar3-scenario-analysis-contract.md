# AR3 B3/B4 分析修复兼容合同

2026-11-09，主审在用户已授权的AR3审计范围内作此实现决定。针对AUD09、AUD16及R-02-B4；不改变后端统计/物理公式，不新增科学基准或扩大科学结论。首配置切片的冻结运行结束前不修改以下产品/测试。

## 所有权与共同入口

允许一个无Qt的 `scenarios/analysis_evidence.py`，只服务B3/B4的严格场景分析准入与输入绑定。复用现有 `g4usim_gui.output.provenance.output_evidence/evidence_operation` 的登记/范围/完整性规则，不另造全局缓存或第二套路径策略。实际消费的摘要/CSV原始字节必须与已验证登记SHA相符，随后从这些字节解析，不先验路径后又读取未经绑定的新内容。单次分析使用同一证据快照。

对外明确证据等级：经验证输出中的完成摘要，不伪造独立操作系统进程退出观察。完整性verified不等于模拟成功或科学正确；未知/缺失不默认成功。默认正式入口要求完整当前格式，旧无完整性数据目录明确拒绝并给重跑/查看原始文件的建议，不静默legacy降级。本轮不增加legacy-unverified分析开关。

运行事实要求：摘要结构无重复关键字段，文本与metadata相符；单run、正计划事件、逐run及总计划=完成、摘要program_exit_code=0、status=completed、simulation_executed=true、macro完成、摘要写完、无output failure、身份相符。failed/aborted/取消/0事件/缺或矛盾事实均不得发布新的普通成功分析结果。多run仍按这两个既有场景的单run范围拒绝，不改变通用GUI多run能力。

## 结果格式与兼容

- 保留可计算旧数值键、单位及正常路径算式；分析输出新增 `analysis_schema_version=2`、`analysis_status`、`run_status`、证据等级/执行身份及每量状态、理由、样本数/误差状态。模型预测与实测估计分开。
- 所有不可用数值JSON写null、CSV空单元格；禁止NaN/Infinity，不补0。`zero`仅用于有充分覆盖/计数/身份且实值为0的量；`unavailable`用于缺量或不可估量。
- 完整可信运行但B3必需区域/量缺证据，保留其它可核量，`analysis_status=partial`、该量null/reason，CLI exit2。必需输入/schema/身份无效则非零拒绝，不发布新的普通成功报告。
- B4低计数导致某个派生量不可估，但必需事件输入完整可信时，仍可 `analysis_status=completed`、CLI exit0；不可估量及样本数必须显式表示。这不是该物理指标通过验证。
- 下游 `scripts/run_benchmarks.py` 对null/partial明确给不可评/非通过，不能TypeError、当0或继续标pass；由主审单独集成，不属分析作者默认写权。原报告保留原schema/身份，不回改旧结果。
- 发布前完成校验与结果计算；新分析文件临时写入后原子替换。原始run输入/输出/metadata不得修改；失败不得先写成功标记。

## B3具体边界

不再对缺scorer_statistics、缺区域/quantity或未登记统计回填零；查重run/scorer/quantity/key、单位、估计方法、n_events、误差状态及有限数。保留稀疏后端语义：未命中可能无文件/无行，没有充分独立覆盖证据时是unavailable，不强制空闲worker生成统计行。

当前场景元数据的实际分析字段须与运行时已读取的main/material/geometry/NIEL/spectrum字节及角色绑定，再核区域/材料/尺寸/源面积一致。不能将当前文件重算SHA称历史观测，不能只看同名文件存在；scenario.json未被后端读取的事实必须保留。只使用实际生成格式及已有解析工具的有限解释，不能从region名字猜材料。若所需语义无法绑定，明确拒绝或partial并报告缺口，不静默相信当前scenario字段。

已知GateOxide使用Si NIEL表等旧适用域限制不因身份一致而获得科学认证；如实保留模型假设/警告，不在此修改NIEL公式或生成器物理参数。

## B4具体边界

20/30/50keV的Compton空窗口/无计数支持返回不可用；保留其它效率、原谱和理论值。光峰n=0/1的实测宽度不可用，n=1位置可有带样本数的值；n>=2保持原样本方差定义。Si无正沉积时检测率可为真零，条件正沉积均值/MPV等不可用。

半样本mode与原20批误差算法不换模型、不自适应改批数；有可用点估计则保留，不足批次的误差明确不可用。空/全零直方图、缺半高左右交点或截断不得冒测量宽度；正常完整交点的插值公式保持。非法bin/smear参数明确拒绝。

## 验证与作者范围

先保存旧源码及有限合成修前反例，清楚标记synthetic_fixture；新结果目录另起，不改旧SHA。合成矩阵按 `ar3-preparation/b3-b4-audit-plan.md`：低能/N1/2/峰n0/1/2、无正沉积、正常公式正控；B3显式零/缺量/错单位/重复/非法计数/材料身份；完整输出哈希正控与重哈希后的语义负控分开。不可用口径必须由独立oracle检查。

允许后续分派写入两个analyzer、response_physics、单一analysis_evidence及两份新增静态测试。原生有限代表性B3/B4及真实run后失败由主审统一执行并保完整证据；不跑高统计原科学批次追通过。GUI共享输出模块、生成器、C++、CMake、runner注册及benchmark消费者由主审持有，需真实依赖才作另行具体分派。

