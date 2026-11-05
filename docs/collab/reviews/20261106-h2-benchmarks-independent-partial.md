# H2-4 V6a与DDD独审补充
2026-11-06。本次在桌面桥仍不可连接时完成不依赖派工的审查。

V6a从原始hits CSV用Decimal50位和12位打印区间独立计算每个谱桶与总量，质量来自原dose表，MeV转J常数1.602176634e-13。factor2共4048个非单位权重步，Σwq约1.85770883843e-8，Σw²q约4.22952897825e-8，区间明确分离；逐bin/总量与谱及dose表相交。factor1非单位步0。证据out/collab/h2-benchmarks/independent-v6a-review.json。只证明计分权重一次，不证明factor2输运无偏。

DDD实际独立执行新组件工具exit0（85项ok），输出独立新目录independent-ddd-component，日志independent-ddd-component.log。另从原si_proton.csv读取1/10MeV节点，按(4*NIEL1+NIEL10)*100/10独立计算2.6317170，与真实scorer CSV及谱和精确相等、完整N2；见independent-ddd-review.json。不扩NIEL物理适用域。

V7首事件前拒绝仍失败且尚未修复；本补充不关闭H2-4。桌面桥/tasks/get本轮仍WinError10061，未再循环重试或重复派工。