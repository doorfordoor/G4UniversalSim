# J3 布局恢复修复独立复验（2026-11-04）

结论：限定修复通过，J3整体未关闭。

- HEAD 0368abceb95469350e1408cc67a36f17fff0c5f7，叠加已有未提交候选。workspace_layout.py SHA da297463859f4513202f3667673d2bd6abf1b58d1df1328076c5995b12909918；smoke_workspace_layout.py SHA 99c8c1f0e72b2264049e7c29f87956aa1ae1a58690df850149f32453632ac9b4。
- 独立审查：恢复入口只应用页面尺寸约束，不执行show/hide/raise；显式导航仍走原显示逻辑；不更改配置与物理逻辑。
- 主审独立运行 workspace_layout / compact_panels / f4_layout / main_window：4通过、0失败、0跳过、596断言，exit0。报告 out/verification/j3-layout-independent-20261104/20261104-002651-15e55491/report.json。check_report_evidence --report 独立通过；首次误传位置参数的命令仅参数错误，已纠正，不是产品测试失败。
- 正常生产薄入口，本地Windows DPR1.25，主审实际观察两次启动：结果区占上方主要空间，日志位于下方；重启未再出现结果区约100px的退化。两次Alt+F4正常退出0（43833、56269）。收据 out/collab/j3-production-startup-r1/state-independent/receipts/manual-20261104-002714-win32-windows-manual.* 及 manual-20261104-002753-win32-windows-manual.*；日志 native-layout-fixed-restart-20261104.log。
- 图中demo是历史legacy/失败输出，不代表新模拟或物理验收。此次未覆盖150%、完整皮肤状态、Linux新候选或最终云CI；旧GUI77不能冒充本修复后全量证据。
