# H3-4 固定基准独立验收（2026-11-07）

结论：H3-4通过，进入H3-5；H3阶段尚未关闭。合同与阈值不变，未增加批次或更换种子。

科学批次为原72项唯一执行，manifest `da0f7f8c36d53c8a3aabd2225831cfd2cf777a5e29cf3405146874f0bb8fa40a`，程序 `3700e27240a06b865949b0a8a48ba2d47f2af689acc515a428c14f05096c90c3`，源码指纹 `c7de5a3c819079cd14765d89e22c4570aba54523b17ce6fa51d513f1207e4be7`。execution为completed/72、halted=null，A/A2/A2f数值停止门禁均pass。主审独立复核834产物哈希，修复前后原件保持不变。

主审独立从原CSV计算同运行四量、网格稀疏分量和/真实完整路径/谱和、质子过滤hits乘权、R-SAME逐事件隔离、M每进程200/50事件无重漏及跨worker四量/事件平方矩合并。均通过。B/C各16批每批2000事件，独立Welch完整99%差值区间除以均值后分别为B `[-0.0002803129071235632, 0.0003519044802015543]`（边界±0.01）、C `[-0.00038094758248214614, 0.00000473576415505014]`（边界±0.005），均通过。C两臂都取质量薄层，离轴探针只诊断。证据：`out/collab/h3-4-independent-r3/formal-independent-results.json`。这些限定对照不是任意材料/粒子/几何的外部物理验证。

首次分析的R-COMP失败保留：消费者把非零质量的12位舍入区间错误要求为退化单点，真实质量恰为0.0008 kg。只修分析比较并重算已有输出后R-COMP通过，不重跑任何科学批次。原R-RUNTIME的科学隔离通过，但旧候选未生成合同要求的空hits文件。纠正后的旧报告对此保留fail，整体仍为wiring_failed；没有把缺失文件改称通过或补造文件。原失败与原二进制另存 `out/collab/h3-4-independent-r3/formal-original-analysis/`、`formal-candidate/bin/`。

该产物缺口已以最小工程修复闭合：只在H3 WorldRoot事件初始化中，经实际TLS ScoringManager取得其worker OutputManager，按scoring/hits/CSV启用状态确保真实hits writer打开；正常Close负责关闭/登记，ghost记录仍不进入hits。新工程程序 `802ad812fb6e618bf1839320d798c5d4dfc899e1e48cebaf454662b8e3b6786d`，组件 `3cf4f095158f23ca12d69806cac6132722157e3a56d3803c976e0917cd8c961f`，源码指纹 `879f00c3ca8925dd76dea5360888fc24aa77ea935c67e7d95470157875288e61`。运行时只有该SD的声明/初始化改变，计分/输运函数及其余运行时文件不变；B/C沿用原身份，不冒充新构建。

主审用独立冻结程序和独立输出目录，按原R-RUNTIME输入、seed20261400、单线程2000事件复演：真实158字节hits表头、0数据行、metadata/summary登记及SHA一致；2000个零贡献事件；ghost dose/fluence非零且无质量行。事件、dose、fluence三个CSV与原3700病例逐字节一致。证据 `out/collab/h3-empty-hits-independent-r1/results.json`。现有两专项独立运行2pass/0fail/0skip，2431断言，严格证据门禁通过：`verification/20261107-055527-ccd9542d/report.json`，根目录同前。最后的并行世界文档更新单独留SHA，不冒称重新编译/测试。

网页二审确认停止控制流和最小输出方案；其退出码建议由主审通过读取execution.status/halted而非进程exit0落实，病例元数据遗漏不导致跳过显式调用的R-RUNTIME。额外TLS/已有失败前置防护建议不升为本阶段新增验收项目：既有ProcessHits缺失TLS锁存/中止路径保留，打开异常已走原ReportScoringFailure及AbortRun，已复演实际线程链。未外推完整故障穷举。两份辅助回执保存在对应独审目录。

H3-5仍须完成冻结候选正式Windows/Linux回归、严格证据、真实云CI及必要GUI操作，随后才集成和关闭阶段。原Q2科学适用域、历史失败及用户H8工作区改动保持原边界。
