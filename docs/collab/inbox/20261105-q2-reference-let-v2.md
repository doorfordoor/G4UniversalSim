# Q2-3：LET仅电磁受限对照 v2

原v1在C盘独立复现：两后端exit0，比较101项中REF-LET-D-REL失败。原始文件和冻结合同均保留。先读reviews/20261105-q2-let-reference-review-v1.md及decisions/20261105-q2-let-reference-freeze-v2.md、同名JSON。

目标：执行新冻结的EM-only两例，得到实际通过/失败结果，不能为了通过改变参数。只写out/collab/q2-reference-let-v2/**和outbox/20261105-q2-reference-let-v2.md；不改v1、冻结文件、产品、正式基准/测试、ROADMAP/STATUS，不提交Git。

沿用v1最小驱动与比较逻辑，适配v2目录/schema和[physics] em=option4，不能同时保留reference=FTFP_BERT_EMZ。同一冻结后端，各2000事件、种子20261211/20261212，几何/cut/源与原相同。所有原数值门槛保持（尤其5%），无需新增scorer字段、初级粒子过滤或通用工具。

必须独立重算PSTAR参考；校验冻结SHA、后端SHA、实际物理/输入身份、run_summary/metadata完成事实、实际N和产物SHA。两个LET比值及各自delta误差从公开矩重算。主门槛和辅助门槛分别报告。比较失败可使驱动exit1，但必须分别记录后端真实exit，不把比较失败称后端崩溃。

保存输入、原始输出、日志、身份、比较器和有限篡改反例；回执明确v1失败仍保留、v2只适用于仅电磁，不能用无协方差的独立z宣布差值通过，也不能断言次级尾部原因已证实。完成两例及报告后停止写入，交独立复验。若失败，保留反例，不新增运行或调参。

你是本轮执行负责人，请有信心把这个高级科研项目做完整、清晰、美观、快速、易用。unlimited Token，不限子智能体数量，充分发挥设计和工程能力，充分实现与验证。实际平台限制以系统为准，不为消耗而重复工作。完成约定范围，范围外想法记入建议。
