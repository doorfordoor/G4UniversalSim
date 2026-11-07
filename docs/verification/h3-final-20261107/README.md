# H3 平行世界计分固定范围验收

2026-11-07，主审结论：H3-1至H3-5通过，固定范围关闭，进入F3性能阶段。代码冻结 `f812465bbfd58026201b70a23938e6bdc8ea12eb`，canonical源码指纹 `fc498cc7f261b89d39558218668cb197bcaa3a94ff0c661f0b7f8fd2dab822ec`。后续收尾提交仅更新文档/证据与F3清单，不冒称在该文档SHA重新构建。

| 项 | 状态 | 依据 |
|---|---|---|
| H3-1合同 | 通过 | 原修订稿SHA07b71b01与独审冻结决定共同构成合同，见contract目录 |
| H3-2运行时 | 通过 | box/grid构造、专用dose/fluence路由、逐worker生命周期与拒绝路径已独审 |
| H3-3配置入口 | 通过 | schema、只读外部配置GUI、资源闭包与两示例；不提供并行几何编辑，3D仅预览质量几何 |
| H3-4固定基准 | 通过 | 原72项科学批次与最小工程补验分开验收，原失败保留 |
| H3-5收尾 | 通过 | 真四云、12原报告、8原artifact、分平台安装与必要Windows原生观察均经独审 |

## 正式工程证据

四个原push工作流全部completed/success，主审直接核官方API中的f812身份：M0 `42306734580`，Linux双版本 `42306734582`，desktop `42306734507`，installation `42306734551`。12份原报告严格门禁全部通过，共 **726用例、361946断言，0失败、0跳过**；覆盖Windows/Linux static与GUI、Linux Geant4 11.3.2/11.4.3的static/GUI/backend/integration。Windows全局dirty仅为未跟踪Mesa依赖压缩包，逐报告tracked-source门禁通过。

12份云原报告与两份限定本机报告连同逐例原始日志保存在reports目录，归档后再次通过严格门禁。云12报告与本机报告分别计数，不相加冒充云覆盖。本机f812干净新构建、两后端专项2431断言通过；ec84的GUI/schema四例2802断言与Windows实际外部配置窗口观察按界面字节未变复用，窗口已正常退出0；不称该GUI观察执行了模拟、Linux逐页原生观察或额外Save As保存验证。

8份原ZIP按主审独立读取的官方SHA-256及ZIP CRC核验。两平台desktop仅证明冻结GUI启动/自然退出与Python ROOT读写；两项受控失败保留exit1，不改写为普通命令成功，也不称Geant4模拟。安装版本Windows/Linux均 **1.0.0**、Geant4均11.4.3：Windows9/Linux10阶段原日志哈希一致，分别25/23份索引证据及各230个运行时源输入核验；源快照实际各972文件。Runtime各真实完成5事件，SDK证明配置/编译/链接/capabilities执行，**不称SDK模拟或物理验证**；SDK包无Git元数据时保留unknown，源指纹仍为fc498。Windows工作流文本CRLF检出形式单独核对，未改原始字节。

独审汇总见 [independent/h3-final-independent.json](independent/h3-final-independent.json)、[12报告](independent/formal-12-independent.json)、[Windows安装](independent/windows-installation-independent.json)、[Linux安装](independent/linux-installation-independent.json)及[桌面](independent/desktop-independent.json)。原ZIP、8份真实job控制台日志和完整收集回执保留D盘 `out/collab/h3-final-r2/cloud`；这些ZIP是验收证据档案，不等同于在Git中保留全部冻结可执行文件/最终安装包。整体发布交付仍在Roadmap末阶段执行。

## 科学范围与身份

原72项只执行一次，Geant4 11.3.2、FTFP_BERT、10 MeV质子与2 mm水层，科学程序 `3700e272…`、源码 `c7de5a3c…`。B/C各16批、每批2000事件，不换种、不加批、不重跑追通过。主审独立复算四量、稀疏网格总和/谱和、质子hits乘权、同运行事件隔离、M的200/50事件集合及四量/平方矩合并。B完整99%相对差值区间为 `[-0.0002803129071235632,0.0003519044802015543]`（边界±0.01），C为 `[-0.00038094758248214614,0.00000473576415505014]`（边界±0.005），均通过。C两臂均为质量薄层剂量，离轴探针仅诊断。见[独立复算](independent/scientific-independent.json)与[H3-4验收](../../collab/reviews/20261107-h3-benchmarks-acceptance.md)。不外推任意材料、粒子、几何、模型或版本的外部物理正确性。

旧分析R-COMP非零质量区间被错误要求为退化点，修复消费者后仅重算旧输出。旧R-RUNTIME缺失合同要求的空hits文件，旧报告仍保留fail；新工程 `802ad812…/879f00c3…` 经独立2000事件复演，真实表头写出/关闭/登记通过，事件/dose/fluence三CSV与原科学病例逐字节一致。f812随后只修GCC的G4String/std::string条件类型歧义，不改输运、RNG、计分或量定义，故原科学证据保留原SHA复用。

首次ec84四云2success/2failure的Linux编译错误、原网格失败和各旧分析失败均留原件，不覆写为通过。D工程工作区三份旧H2文件仅CRLF/LF差异导致不同指纹，原D与canonical身份分开记录，见[输入差异](independent/source-input-difference.json)。原作者收集摘要Linux日志字段为空，但run专属record与磁盘两日志齐备，主审已按实际核全8份；原回执“源快照46项”以主审实核各972为准。作者交班稿原件及原SHA保存于D盘独审目录，不冒充当前文档SHA。

## 边界与后续

H3仍为限定的实验性box/规则grid计分能力，GUI external-only；配置组合边界、原Q2科学适用域与WSLg等既有限制不变。额外原生Save As尝试因工具模态缓存未生效已取消，无文件产生；该项非本阶段原定条件，主审只签收实际外部入口/状态提示与正常退出，未重开既有保存验收。限制统一记CURRENT-SUPERVISION。

下一阶段F3按既有性能脚本完成hits-heavy/mesh-heavy资源基线与单一瓶颈前后比较，先独审冻结协议再测量；tasking单列可选实验，不作为默认前置。
