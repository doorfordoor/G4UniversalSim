# AR4 材料/几何文档与阶段整体主审签收

2026-11-09，当前主审对话签收AR4材料/几何文档域，并合并已签首片与SPS，关闭AR4约定范围。MR2、MR3尚未签收。

候选基线585f4d191c02007a054ac1f089b0ebdbd7e59025。文档域14作者路径和主审runner/生成registry共16路径，完整原字节身份见candidate-r3.json。r3相对r2仅两产品接线和一个新增测试变化；纯文档动作模型、事务引擎以及其它作者路径不变。材料、volume、layer、boolean沿用WorkspaceSnapshot/EditSession单一权威；raw/pending、source和选择保留，控件仅投影，程序化输入和键入均进入同一动作通道。选择交互不产生语义revision；结构动作按revision/index/payload拒绝陈旧引用。源读取在边界一次完成，失败保留旧文档但不回退用户所选坏路径，generated准入仍拒绝来源不一致。成功与回滚的概要、表格和来源同步。

C04明确改变失败reload旧行为，因此只有限适配两个既有smoke的失败重载/可变对象身份断言，改核完整payload、来源、原始草稿、行排列及坏路径拒绝；未删除功能负控。生成solid registry来自原真实backend与现generator，15项metadata不变，仅原陈旧源码SHA更新，原表和差异均保留。

独立r3为22场景组/23part，329次显式guard，3子进程及launcher exit0，Qt未捕获0，16路径及179依赖首尾稳定；成功通知时读取概要/表格/session/source一致，实际一次源读取，缺失源、容量拒绝和投影后回滚保持完整旧状态，实际保存新reader和消费者准入重放通过。r2原38组37通过/1失败保留；D07额外禁止导入Qt模块超出原不创建QApplication/QWidget合同，主审复核原合同和既有i18n后按窄补证接受数据动作边界，不称无PySide6依赖。此例外交MR2。

r3 Windows实窗补验21项通过：材料/几何实际Reload首次可见3/3，缺失B保旧、实际SaveAs/reopen保持B路径与A内容/计数。主审直接查看009原图确认同屏Geometry3与三行；可选pyvista缺失不算渲染通过。host30544/session53880正常exit0、无所属残留，backend尝试0。r2六段键入/结构/撤销/保存证据按r2身份引用，不冒r3全量实窗。主审核120原生产物+140独验产物SHA以及16源码一致。

r1正式13pass/3fail、r2作者9pass/1fail、原Qt退出0但回调异常、r1原生SaveAs拒绝及r2概要0/表3均保留，不追改。r2正式17pass3364仅作原候选证据。旧后端53602a799caa843ad45412ca175849212fa2873123f3c7f53c9e008574686670保持其真实构建身份，C++source66a027a0acb883a67fed50dbbace6a383353dc7e0e3f4516eb1d2043395adcfe未改，不重标GUI提交为后端构建。

本次整体签收合并既有[AR4首片](20261109-ar4-first-slice-acceptance.md)和[SPS签收](20261109-ar4-sps-acceptance.md)：不新建第二控制器，不扩J4流程或材料/几何物理能力；不追加H3/F3测量。27正式问题仍19关闭/8待AR5，AR4文档不重复计问题数。接续AR5目标/导出/安装/资源修复，随后当前对话MR2，AR6双平台新交付与MR3。用户原暂存和历史dirty不并入本阶段提交。

## 最终正式证据

报告（`out/collab/20261108-ar0-ar6/ar4-document-r3/formal/20261109-080453-663be3a1/report.json`）为17pass、3419断言、0fail/0skip；session84223自然exit0，compileall0。严格检查（`out/collab/20261108-ar0-ar6/ar4-document-r3/strict-evidence.log`）通过且candidate stable。测试指纹`e7e43894455804fc684d36520ebdc0289b70e50a0fdce5ae9656777363858b20`。16源码尾核一致，文档同步发生于验证之后，不更改已验产品/测试字节。

独验（`out/collab/20261108-ar0-ar6/independent/ar4-document-review/candidate-r3/REPORT.md`） · 原生补验（`out/collab/20261108-ar0-ar6/independent/ar4-document-native/candidate-r3-attempt1/REVIEW.md`） · 主审SHA回读（`out/collab/20261108-ar0-ar6/ar4-document-primary-preparation/r3-primary-readback.json`） · D07裁定（`out/collab/20261108-ar0-ar6/ar4-document-primary-preparation/D07-DISPOSITION.md`） · 候选16路径（`out/collab/20261108-ar0-ar6/ar4-document-primary-preparation/candidate-r3.json`）。
