# E6 下一候选归档角色机制（仅out，未执行）

第二轮5bf479d CI失败已经封存，不能继续使用先前`archive-e6-final-arguments.json`作为下一SHA的release参数。该旧文件、旧plan及旧证据保留原样，明确只对应5bf轮次。

## 新角色

- 下一轮正式CI根：`out/verification/e6-ci-release`；下一SHA与Windows新报告路径**尚未绑定**，不猜测。
- `out/verification/e6-ci-final`：显式`--historical-ci-root`，保留5bf的4归档摘要、8/12实际报告、Linux退出-6等失败事实；`complete=false`表示未通过完整12profile要求，不是将已封存失败改写为成功。
- `out/verification/e6-final-windows`：显式`--historical-windows-root`，终态后只作5bf历史/控制，不计新SHA release。若尚未写report，archiver会阻止正式归档，不能悄悄漏掉控制报告。
- 原`e6-ci`和`e6-full-windows`继续按默认历史保留cb837首轮CI/Windows失败。

`archive-e6.py`新增两类history参数，在manifest `historical_rounds`逐轮记录真实head/status/report分布；历史报告只核原字节和日志一致性并保留strict gate的失败值，不承担release身份。正式Windows和CI仍必须等于显式expected-head/双指纹/冻结用例集合；final和history同根会拒绝。

## 下一身份确定后的绑定

使用`out/collab/prepare-e6-release-archive-arguments.py`，必须显式传：

```text
--head <新的40位SHA>
--windows-report <新候选独立目录内真实report.json>
--destination <不存在的最终归档目录>
--output <新的参数JSON>
```

CI默认新`e6-ci-release`；需要时显式`--ci-root`。工具只继承原参数中的20个include-root及binary身份JSON，**不继承**旧head/Windows/CI release角色，加入上述5bf历史角色。新freeze/report存在时立即核SHA；旧cb837/5bf SHA、旧CI根、5bf Windows根作为release会被拒绝。它没有execute功能，只生成新参数，root终态裁决后仍须先规划再另行批准实际归档。

`archive-e6-release-unbound-template.json`记录未绑定的下一轮和完整历史角色；head/windows_report为null，不是可执行的伪完成参数。`e6-archive-role-guard-check.json`记录两个旧失败SHA被拒绝、无新参数文件、未执行归档。

所有源码/参数/报告变更仅在out。tracked状态仍干净；`docs/verification/e6-final-20261030`未创建。media和锁屏条件不在本工具中绕过；旧selfcheck/凭据/二进制继续排除。等待最终身份与终态。
