# F1第二冻结CI：未通过

冻结提交：`3d1faf1b256a945ac800c08bacf51db57f8ca416`。本轮证据收集完整，阶段验收未通过。Linux run41024949824的11.3.2/11.4.3两个job均failure；M0 run41024949832两job成功。未重跑CI、未构建或运行主全量、未更改tracked或旧证据。

四个官方原ZIP摘要均匹配，安全解包拒绝绝对/盘符/上溯/重复/符号链接成员；12份原报告均保留，所有414条case日志raw SHA与断言marker已核对，包括失败日志。10份成功报告严格门禁exit0；两份失败integration严格门禁非零，另做allow_incomplete仅triage结构检查及全日志哈希检查，不能将其称为绿色。`ci-evidence.json` status=not_passed、complete=true仅指集合完整。

## 两个失败

- linux-evidence-11.3.2：`effective_gdml` exit 1，已执行2条入口；[原case日志](linux-evidence-11.3.2/linux-integration/20261030-083153-b3c72c50/effective_gdml.log)，SHA `aa67d3d6a59e46665b672ae34de8db2ded512e3162d968e94962842b687ebf5c`。helper抛`xercesc_3_3::OutOfMemoryException`后终止，脚本`run.returncode==0`断言失败；不据异常类名认定机器物理内存耗尽。
- linux-evidence-11.4.3：`effective_gdml` exit 1，已执行2条入口；[原case日志](linux-evidence-11.4.3/linux-integration/20261030-082752-810fad59/effective_gdml.log)，SHA `aa67d3d6a59e46665b672ae34de8db2ded512e3162d968e94962842b687ebf5c`。helper抛`xercesc_3_3::OutOfMemoryException`后终止，脚本`run.returncode==0`断言失败；不据异常类名认定机器物理内存耗尽。

## 报告清单

| Artifact | Profile | Cases | 非pass | Strict gate |
|---|---|---:|---|---:|
| linux-evidence-11.3.2 | [backend](linux-evidence-11.3.2/linux-backend/20261030-081715-48563028/report.json) | 59 | 无 | 0 |
| linux-evidence-11.3.2 | [gui](linux-evidence-11.3.2/linux-gui/20261030-081612-05bbfab7/report.json) | 39 | 无 | 0 |
| linux-evidence-11.3.2 | [integration](linux-evidence-11.3.2/linux-integration/20261030-083153-b3c72c50/report.json) | 20 | effective_gdml | 1 |
| linux-evidence-11.3.2 | [static](linux-evidence-11.3.2/linux-static/20261030-081517-64764b63/report.json) | 25 | 无 | 0 |
| linux-evidence-11.4.3 | [backend](linux-evidence-11.4.3/linux-backend/20261030-081628-6f5fd398/report.json) | 59 | 无 | 0 |
| linux-evidence-11.4.3 | [gui](linux-evidence-11.4.3/linux-gui/20261030-081540-4775f775/report.json) | 39 | 无 | 0 |
| linux-evidence-11.4.3 | [integration](linux-evidence-11.4.3/linux-integration/20261030-082752-810fad59/report.json) | 20 | effective_gdml | 1 |
| linux-evidence-11.4.3 | [static](linux-evidence-11.4.3/linux-static/20261030-081458-f2806abd/report.json) | 25 | 无 | 0 |
| m0-report-ubuntu-latest | [static](m0-report-ubuntu-latest/20261030-081325-9aa5aa70/report.json) | 25 | 无 | 0 |
| m0-report-ubuntu-latest | [gui](m0-report-ubuntu-latest/20261030-081422-718f4268/report.json) | 39 | 无 | 0 |
| m0-report-windows-latest | [static](m0-report-windows-latest/20261030-081347-01d08433/report.json) | 25 | 无 | 0 |
| m0-report-windows-latest | [gui](m0-report-windows-latest/20261030-081442-86a8a4cd/report.json) | 39 | 无 | 0 |

原始job日志：[Linux11.4](job-123960735990.log)、[Linux11.3](job-123960736266.log)，以及两份M0日志见evidence-integrity-audit.json。GitHub connector的decoded文本日志按原返回UTF-8保存（含BOM）；原ZIP按二进制保存，官方digest来自对应artifact metadata。未保存临时下载URL或任何凭据。verify helper只执行verify模式，未执行collect或credential fallback。

[汇总](failed-round-summary.json)、[完整逐日志校验](evidence-integrity-audit.json)、[收集与门禁记录](ci-evidence.json)、[verify命令收据](verify-only-receipt.json)。CI通用git_dirty字段按报告原样保留，不以其代替tracked-source gate/双指纹，也不推断其具体来源。可见UI和物理验证均不由本次CI收集完成。
