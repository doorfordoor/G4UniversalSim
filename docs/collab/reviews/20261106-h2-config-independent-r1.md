# H2-3 r1 独立验收
2026-11-06。H2-3配置入口在现有编辑覆盖范围通过；H2-4、H2-5未关闭。

核实turn88 completed/idle。源码整数判定已不再截断，bool拒绝，范围1..1000000；UI同上限。独立执行gui_run_config、gui_h2_volume_config、gui_h2_volume_editor_ui：3pass/0fail/0skip、111断言；严格门禁通过。报告out/collab/h2-config-entry/independent-r1/20261106-041730-8236de71/report.json，source fingerprint 9ebcd8808db6eb22ea7a5aafd45eb2d43366ec09305fac7cade228e0b7d0ab52，tests前缀b116faf3c08c。旧失败报告保留。

独立复制examples/h2_volume_spectrum三个输入到out/collab/h2-config-entry/independent-example-r1并按README实际运行，exit0；summary completed、100事件、谱schema1。CSV唯一非零bin5，amount1、unit mm^-2、n_events100。原后端exe fae758c4…保持。

项目JSON往返与INI section识别按实际范围区分：本阶段未新增INI计分模型导入。displacement沿原手写配置边界，未扩GUI覆盖。当前GUI证据是offscreen组件，真实窗口与平台/云正式验收仍归H2-5。通过不等于整体H2关闭。