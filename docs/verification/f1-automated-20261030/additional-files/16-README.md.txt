# F1 历史失败摘要归档兼容修复

本次只修改 ignored `out/collab/archive-f1.py`；没有修改 tracked、CI 原证据目录或生产程序，没有执行归档发布。

旧 helper SHA-256：`017d26fa8fbd9e28c8126474426a64ed5c6c8373b1c3b4d69b9eeb192cc7f3a6`。
新 helper SHA-256：`e803a3c9f76aa12cae23b11e34dc8044415c38b0cfcd80b8f1fbf4d7711a8f24`。

`helper.patch` 是两版本完整差异，`archive-f1-before.py` 保留原版本；`check.py` 是新增验证入口，`receipt.json` 记录结果。

## 变化

- 精确认识已保存的两种 `failed-round-summary.json`：首轮 compact（head/status/reports/boundary）和第二轮 audited（head_sha/收集完成/非通过状态/详细报告、产物、日志及合计）。未知或缺字段格式拒绝。
- 历史摘要与冻结清单、实际报告集合、用例集合/失败列表、原 workflow/job 的完成步骤交叉核对。首轮未执行 backend/integration 必须由原步骤的 skipped 证明，不能当作缺失报告已通过。
- 核对历史四份官方 ZIP 的摘要、原元数据关联和全部解包文件字节。ZIP 留在原证据根；plan 新增 `historical_zip_digest_checks`，review/execute 前再次核对原 ZIP，归档的原元数据与报告/日志不改写。
- 历史状态仍为 failed，收集完整和阶段通过分开。最终 `validate_ci_topology`、`report_gates`、`verify_existing`、`execute` 的 AST 均与旧版一致；失败历史进入最终 CI 门禁的负例仍被拒绝。
- `.patch/.cc/.hh` 仅允许由 `--include-file` 或 `--review-file` 显式选入，不扩大递归树的后缀白名单；仍检查 UTF-8、NUL 和凭据模式。原 `--plain-markdown-source` 行为保持。

## 实际验证

34 项检查，含 30 个拒绝负例；两处原 CI 树的全部落盘文件 SHA 前后相同。负例覆盖未知/不完整 schema、伪造通过状态、遗漏/重复报告、合计/摘要/失败列表/门禁声明错误、原 run/job 关联、缺日志、篡改 ZIP/解包字节、路径逃逸，以及显式源码的 NUL/凭据拒绝。

`plan-real-round-1.json` 和 `plan-real-round-2.json` 使用真实 E6 成功报告作为“最终证据”控制输入，分别把真实 F1 首轮/第二轮加入历史；仅测试 plan 兼容，不构成 F1 通过结论。首轮纳入 8 报告，第二轮纳入 12 报告；两个 plan 均保留全部原 JSON/日志和关键 GDML 显式源码、补丁。第二轮 plan 无阻断项；两者均未创建发布目标。

## 必须补收的原证据

首轮当前实际只存在 `job-123949509175.log`，旧 README 声称所有任务日志已在目录内，与文件事实不一致。以下三个文件在读取时缺失，首轮 plan **正确保持阻断**：

- `out/verification/f1-ci-final/job-123949508758.log`：Linux Geant4 11.4.3，run 41021459195。
- `out/verification/f1-ci-final/job-123949508802.log`：Linux Geant4 11.3.2，run 41021459195。
- `out/verification/f1-ci-final/job-123949508743.log`：Windows M0，run 41021459196。

需由采集负责人取得对应原 job logs 并补入，不能用摘要或占位文字代替。本次没有写这些目录，也没有绕过该阻断。日志补齐后重新生成正式 plan；旧 README 原字节保留，最终归档说明实际补收时间与边界。

## 实窗 pending 决策

可以生成单独的自动验收归档，只要其 README 显著写明实窗 pending/F1 未关闭，不把 pending 夹具称为实窗观察。helper policy 本来只证明归档字节与测试报告，不能建立 UI 完成。为减少后续误读，建议在正式 plan 的交付说明中显式记录 `visible_acceptance=pending` 与 `phase_complete=false`；本次未增加会影响旧 CLI 的新参数。实际窗口观察应另建闭合证据，不追改自动归档的原 README。
