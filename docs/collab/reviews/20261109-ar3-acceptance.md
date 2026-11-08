# AR3 运行编排及关联修复：主审签收

2026-11-09，当前主审正式签收本轮AR3合同。r4正式验证、独审及R1-R-02-B4独立原生补证均完成，随后执行本对话MR1。本记录不签 AR4–6、MR2/MR3 或扩大科学适用域。配置协调首片已在 d3b5e078 独立提交，其后运行会话、收尾、分析/证据服务及相空间行为修复分别审查、冻结和验证，最终以相互依赖的集成树收口。

## 冻结身份

证据根为 `out/collab/20261108-ar0-ar6/`。最终 D 候选 `ar3-integrated-r4/freeze.json`：source `afe7518fc93ed2bb7a44b67f2bfea630f6c8d543b2e035c7206d10b0c9944ee6`，tests `dc72245baac3694c0e8e9e5395beb4fd3da16b39dbd6f92c888a269535a781f2`；构建时 HEAD 为 d3b5e078，dirty 保留。实际 backend SHA `72a061c99eb19553c23632edc4ee29bb6e03a94810267dfcc68114abe9051481`。模板动态闭包338成员、identity `718fca17ac62b1ff8bdd25afbb21ae3b6a055106d569fdf1527a822697d54421`，check有效。71产品/测试/模板及三文档与冻结字节一致；主审另核71文件无漂移，不以 HEAD 代替工作区身份。

## 实现和证据

- 配置协调复用原 Manager 所有者及合法调用次序；运行会话使用同步借用的 NativeExecutionPort，main/SessionServer 选择真实 Geant4 适配器；最终摘要发布及一次收尾单独承担职责。不增加第二份配置权威，不变随机数派发或物理装配次序。接口替身、实际内核/ROOT资源及整进程回归分别计证。
- ROOT Write 失败仍尝试 Close，保留首因；早期 bias 校验失败锁存，未开始 timer 不产生伪统计。实际资源组件、受控故障与正式兼容结果共同支持，不把 callback 组件冒作完整 BeamOn/MT 失败路径。
- 相空间 v3 的22列保存实际 charge/mass/electron occupancy/magnetic moment/polarization；不可变 primary payload 在首次 tracking 初始化前恢复，构造哨兵不是物理电荷。保留默认分类，secondary 先排除，同一轨迹再次分类不覆盖演化状态。v1/v2离子（含 proton）明确要求重新记录；非离子 legacy 假设明示。没有声称保存完整 RNG/过程 checkpoint 或任意介质电荷交换。
- 源命令原 FatalException 在真实 GPS case22 导致 0xc0000409，已改为记录诊断、停止 batch/csh 后续命令、正常 failed 摘要和 exit1。新增 batch/csh 正反四路检查真实 primary/事件与原宏位置。unknown catch 保持静态覆盖限制，不把另一个端口的异常注入算作此分支动态验证。
- 同窗运行许可、持久结果服务/history、B3/B4和发布服务分别沿既有切片报告；AUD02扫描消费及R2-10 GUI消费者仍归AR4，不因服务通过自动关闭。

最终 D 新鲜 configure/build exit0。`phase/20261109-030449-4f2e181b/report.json` 四项通过、1773断言；`compatibility/20261109-030951-195ff08c/report.json` 22项通过、55954断言，均零失败/跳过，严格身份门 stable。独立 `ar3-r4-compat-review/compatibility-results.json` 核22原日志/身份、留存ROOT首因及MT逐run证据，364检查；固定场独核36进程、411产物，原门限不变：最大位置差8.60787e-11mm、时间差2.07057e-6ns、电荷差0。完整组件347 checks与包装器断言分开。

C 使用真实独立源码树与新构建，source/tests完整匹配，真实 HEAD 为55ef3d62而非D HEAD。`independent/ar3-native/r4/REPORT.md`：三项通过487断言、strict stable；58 GPS进程36 exit0/22 exit1，879产物和253输入快照及600 A/B原始数值独核通过；有限 proton/gamma SDK夹具另验。D/C末次限定所属进程检查均0，本轮未强制终止。C三份用户文档保留，其完整模板仍不合格，不将C运行签收外推为C导出通过。

四个旧正向 proton 夹具迁为明确的新合成 SDK 默认态请求，不硬编码质量、不从历史CSV补造状态；前15字段、164原静态断言及科学门限保持。原四项报告为3pass/1fail（缺现有scoringNumericCheck，失败在执行前）；补构建同冻结组件后单项457断言通过。`fixture-composition.json` 显式组合四项5996断言，原失败不改绿；原报告仅作允许不完整的分诊，补报告严格门通过。独立 `ar3-fixture-review/RUNTIME-REVIEW.md` 核49组helper、315行、147进程收据及J2/Q1保留产物；F1/scoring已清理的临时后端产物不能事后逐件独核，采用冻结脚本、执行断言日志和独立helper证据的有限结论，不声称全面原始产物复验或科学签收。

Linux指定验证保留 v3 原身份（source8ab910…、tests8ad439…），不是 r4/Linux执行：新 ext4 构建、config_precedence/phase_space_state 两项64断言及strict通过；独审 `ar3-linux-review/terminal-r2/review.md` 核58镜像原件和三ELF。R2-11 CLI实现随后未变，Windows/Linux类型范围证据按原身份复用，最大seed仅证明解析，不证明引擎已执行该值。AR5/6新完整Linux交付仍待。

## 关闭项及保留范围

本次关闭 R1-AUD-03（同窗口所有权）、R1-AUD-09（B4低计数）、R1-AUD-10（有界相空间实际状态）、R1-AUD-16（B3缺量/失败不冒成功）、R2-11（CLI seed解析）；累计12/27项正式问题关闭，其余15项继续。三项风险中R1-R-02-B4已完成有界防御验证，其余两项按AR4合同继续。B3/B4有限原生11例153事件、553文件/35退出/107原生产物与84条B4 ledger独核沿原105b候选引用，不改名为r4科学执行。

保留原v2磁场失败、旧GPS异常终止及有据强制清理、Linux首个SDK activation失败、首次源码跟踪/缺组件失败和所有审计器编码误读记录。有限真空对照、夹具、替身、Python子进程及实际输运证据各有范围；F3 inconclusive、WSLg、未验证科学域不变。主审随后以累计diff、原始正反例和当前身份执行MR1；AR5真实target边界、AR4模型/消费接线及AR6扩展/安装验收不能由本次通过代替。

## R1-R-02-B4补证签收

主审收口检查发现旧final_flush故障不等于“一个run后追加失败命令”，因此签收前另冻结64总事件的原B4 gamma/seed4242正反两例，仅负例宏追加第3行/control/verbose InvalidValue。两backend正常exit0/1且均32/32；正分析0，负分析因failed状态明确拒绝exit1且不发布产物。独审逐件核94最终文件、两份原CSV一致（32唯一事件，总沉积6.7258962985723MeV）、来源/登记SHA与宏真实code400，见independent/ar3-b4-postrun-command-review/FINAL-REVIEW.md。此为风险有界防御验证，不宣称历史风险已复现为错误成功。

原执行器对所有case额外要求actual_threads=1而exit1；负摘要实际unknown与旧异常收尾语义一致，RunManager已在catch前析构，原测试允许unknown。没有改产品、回填字段或改原PLAN/failed execution。只对同一负输出完成尚未执行的一次分析，未重跑输运；continuation外层0、内部分析1与原计划失败分开。早期artifact-set包含尚未结束的外层日志，保留原时点；最终94项清单在全部外层结束后生成并独核，无所属进程残留。
