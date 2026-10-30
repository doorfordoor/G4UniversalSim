# 5d56187 CI 取证检查点（非完成报告）

唯一候选 `5d56187392a2e7b888d5ce13f8da05a295cba6d4`，Linux官方run41082364530 / M0官方run41082364655。M0双平台success，Linux11.4.3 success，Linux11.3.2尚integration。

已到档：M0 Ubuntu/Windows各79case，Linux11.4.3共160case，合计8report/318case。三ZIP官方SHA匹配、安全解包；报告严格门禁已逐case核对日志摘要与v3 marker，M0四份及Linux static/gui/integration的F4逐例基线通过。

**未通过项**：11.4.3 backend当前39795 < F4基线39797，唯一下降case displacement_damage 44<46；其源码和探针与F4无diff，日志除计数行以外字节相同。worker summary行循环是候选解释，没有原始CSV证据，不豁免。原失败门禁与告警保持。待11.3.2终态后统一生成正式审计JSON，即使官方全success也会如实标记此基线拒绝。

Linux11.4.3报告git_dirty=true，M0报告false；原值保留。无原始runner porcelain，不把源/测试指纹一致说成工作树clean。本轮不修改源/正式测试/workflow/历史报告，不创建新CI运行。

关键路径：`partial-m0-audit.json`、`linux-1143-ready-gates.log`、`baseline-gates/linux-evidence-11.4.3-backend.log`；详细进度与告警在`out/collab/f5-ci-5d56187-status.md`及`f5-ci-5d56187-baseline-alert.md`。
