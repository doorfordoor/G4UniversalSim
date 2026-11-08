# AR4 SPS编辑所有权迁移限定签收

2026-11-09，当前主审对话已回读候选源码、正式报告、实际后端摘要与另一执行者的独立复验，签收本SPS片。**AR4整体仍未关闭，下一片为材料/几何；MR2仍在AR4/AR5后，MR3仍为AR6最终签收。** 本片不增加27项审计问题关闭计数。

## 范围与身份

基线4b3182c884c626621d4968d3e0ac7502190e6fff。作者十文件owned-set为e05ac27e833fc00d36c9d96c5c5fc3762fca01db7f68351b2c62e02a2570ebb8，另由主审增加gui_ar4_sps单条runner注册。逐文件首尾SHA均一致，见[out/collab证据根](../../../out/collab/20261108-ar0-ar6/ar4-sps-r1/candidate.json)与[作者交付](../../../out/collab/20261108-ar0-ar6/ar4-sps-author/REPORT.md)。原用户两暂存及其它历史修改不属于本片，不push。

76个scalar/filter/spectrum绑定、7个raw槽及J2四类行/结构操作迁入现有WorkspaceSnapshot/EditSession；bound读取返回私有投影，capture不再读SPS控件回填。GPS身份由边界给定，其他行采用revision/index/digest守卫；未新增持久控制器、schema或科学能力。整组dirty/settings转换及raw保留/清除由作者调用保存的原槽函数对照，载入时未编辑的settings/editor分歧保持。

有限扩写experiment_workflow只补20个动态accepted映射，非法raw/unknown仍拒；F5测试将复制投影对象的地址断言改为完整source内容及权威session相等，material/geometry原对象身份和其它拒绝断言保持。独审确认其它assert AST及顺序未变。未修改writers/validators、C++或科学定义。

## 正式验证

[正式报告](../../../out/collab/20261108-ar0-ar6/ar4-sps-r1/formal/20261109-060136-5112bd1d/report.json)：11pass、2794项断言、零skip，所有case exit0；主审session40007自然exit0，compileall0。[严格检查](../../../out/collab/20261108-ar0-ar6/ar4-sps-r1/strict-evidence.log)要求候选身份，结果stable。

源码指纹66a027a0acb883a67fed50dbbace6a383353dc7e0e3f4516eb1d2043395adcfe保持；测试指纹4f062f1fa51f5b0d9aef7ed5213e5b4c6f92eba4a99a49ba89a52964e72834ad。复用AR4首片backend53602a799caa843ad45412ca175849212fa2873123f3c7f53c9e008574686670，不重标其旧构建commit。

覆盖config-agent组件56、真实backend消费25、K1window178、F5transactions345、F5editor243、纯模型819、source preservation340、run config34、J2 editors223、run/path479、SPS52。真实run_summary为一个run计划/完成4/4、actual_threads2、completed；另一次输入检查run_count0，不作第二次模拟。模型响应为确定性loopback协议fixture，不外推真实云模型或物理验证。

## 独立复验与原失败

[独立报告](../../../out/collab/20261108-ar0-ar6/independent/ar4-sps-review/candidate-r1/REVIEW.md)通过，无P1/P2阻断：独立数据427、Qt139、真实恢复codec37检查，另有六项受控既有组件重放。10文件及6份受保护writer/validator原字节首尾无漂移；拦截的backend/进程启动为零。getter毒化下真实save/preview/capture继续读权威模型；现代/legacy打开、真实恢复入口、陈旧动作拒绝、双失败冻结及fields迟到/Undo/save不复活均有实际证据。

作者F5首次id断言失败exit1、SPS Qt第三次旧项目投影/回滚双失败及锁清理失败exit -1073741819保留。最终显式新project临时投影上下文修复另行补验，本次正式最终候选通过；不追改原失败。作者run/path长会话跨过候选变化，不作为最终冻结profile；主审本次479为最终身份。

独审自身首轮Qt驱动仅调用apply_workspace而未由EditSession发布，另有直接session fixture对服务epoch的不当预期；修订保留原行数/内容断言，改走真实窗口动作及reset/apply。为独立核实，又实际调用_restore_recovery_payload并比较完整codec。恢复补核首次oracle将部分输入selection与正常保存追加的完整交互选择作错误等同，修订后比较完整实际capture/save payload并保留四类行/选择。所有初始exit1、驱动两版SHA及diff保留；不是修改候选迎合测试。

## 限制与接续

本片不签可见桌面人工观察、材料/几何、完整K1资源搬移、新科学或性能；H3/F3未重跑，原科学身份/限制保持。独审保留的.lock文件14/14可只读exclusive-open后关闭，只证明这些文件未被独占，不冒整机进程审计。全部本片执行会话已结束。

精确提交后按新共享源码SHA激活材料/几何任务及已采纳的C01–04附录，保持单写者。随后完成AR4、AR5、当前对话MR2、AR6及MR3，不以本片签收结束已授权主线。
