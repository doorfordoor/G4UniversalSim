# F2 首轮基线及独立复验原件

2026-11-04，F2尚未整体验收。本包支持固定清单第一项，不是发布验收、跨平台结论或物理基准。

- author/：作者首轮驱动、配置、原始输出、索引及汇总，保持冻结字节。
- author-delivery.md：作者报告的字节副本；独审限定修正在[主审报告](../../collab/reviews/20261104-f2-baseline-independent.md)，未改原件。
- independent/：主审独立Windows驱动、配置、8个真实进程案例与原始bytes stdout/stderr。report.json为6/0，delayed-report.json为2/0；每例保存PID及产物SHA256。
- manifest.json：以上复制原件405文件、16733190字节，逐文件比对SHA256一致。该清单不自包含自身或本说明。

实际后端SHA256为18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837。产品源指纹9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a；原构建commit625cfee保留，通过源码字节映射引用，不称新构建。

同进程A/B/A三轮30/30、五字段50/50、原生GPS交错、PreInit回放、两拒绝和延迟离子正反例均满足其限定断言。源命令硬中止退出3221226505、输出状态门失败退出1保留，不能写所有运行成功。观察记录是主轨迹进入Target的边界行，不是生成顶点；本例真空且核对run/event/track/parent后作消费证据。

F2协议设计、实现、GUI、重放、正式矩阵与最后集成仍按原清单推进，本包不提前关闭阶段。
