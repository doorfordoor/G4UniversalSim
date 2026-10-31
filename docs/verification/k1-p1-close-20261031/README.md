# K1 资源路径 P1 关闭证据

原 P1 与补验发现的正式防回归 P2 均已关闭。[独立最终裁决](independent-review/addendum-02-final-closure.md.txt)批准当前修复及永久回归；K1 整阶段结论见[最终验收记录](../k1-final-20261031/README.md)。

产品保持第七冻结 `2914b3962167325628ede699b1c14a9d224dec41` 的原字节。本次只在 `5644e1e52b9c2dd5b463217e9e601c8116f8a913` 为 `scripts/test_k1_staging_alias.py` 追加 73 行，保留原 17 个断言语法节点。[身份映射](final-identity.json)与[独立核对](independent-review/addendum-02-identity-check.json)确认 350 个产品文件不变，全部其他测试及工作流不变。新测试指纹单列，不改写原完整矩阵。

| 本次证据 | 结论 | 原件 |
| --- | --- | --- |
| 独立 Windows 边界补验 | 旧 r2 错误发布；当前 r3 拒绝晚变化链接、清理暂存并恢复源；普通字节变化仍拒绝；真实 8.3 与离线搬移成功。四项退出 0，共 71 个适配器断言入口 | [报告](runtime-boundary/README.md.txt)、[收据](runtime-boundary/validation-receipt.json) |
| 正式 Windows 单例 | 1 PASS / 0 FAIL / 0 SKIP，36 个 v3 入口，runner 与严格门禁退出 0 | [report.json](permanent-regression/formal/windows-reports/20261031-204100-503276c4/report.json) |
| 正式 Linux 单例 | 1 PASS / 0 FAIL / 0 SKIP，33 个 v3 入口；原件、复制件及 Windows 复核门禁通过 | [report.json](permanent-regression/formal/wsl-linux-reports-copy/20261031-204115-b1ea9108/report.json)、[34 文件复制清单](permanent-regression/formal/wsl-copy-identity.json) |
| 同一新测试加载旧 r2 | 预期退出 1，在新增“必须拒绝”断言处失败；观察到错误发布，源恢复通过 | [失败日志](permanent-regression/windows-old-r2.log)、[探索收据](permanent-regression/exploratory-complete-receipt.json) |

两份正式报告均绑定 clean 提交 `5644e1e`，跟踪源码门禁通过。[正式进程收据](permanent-regression/formal/formal-validation-receipt.json)及[独立证据核验](independent-review/addendum-02-formal-evidence-check.json)记录退出事实、日志 SHA 和计数。Linux 为 WSL Ubuntu、Python 3.11.18、PySide6 6.11.1，在同提交的干净临时检出及本地文件系统运行；此专项不启动 Geant4，不声称重跑两个 Geant4 版本或原生 GUI。

首次 WSL 在 `/mnt/c` 的原 control 发布遇到 `renameat2 EINVAL`，失败日志保留；本地临时文件系统的通过不表示 Windows 挂载盘限制已修复。原 P1 关闭针对已确认的“收据捕获后、最终复核前出现目录链接”回归，不扩大为任意并发文件系统变动的保证，也不增加物理或性能基准结论。

恢复审查基于用户报告已收到官方解除通知，[恢复依据](resumption-notice.json)明确未由本助手登录账户独立核验。本轮正常调用没有新的拒绝，未改变保护设置；[旧拒绝诊断](../k1-final-20261031/p1-refusal-metadata.json)仍保留。

[复制清单](copy-manifest.json)记录 326 个补充证据文件、444111 字节的原始 SHA；历史 Markdown 仅改扩展名为 `.md.txt`，内容字节不变。清单不含本索引及后续交付复核，不覆盖或重封存既有完整矩阵归档。

[最终交付独立复核](delivery-review.md.txt)及[机器收据](delivery-review.json)核验归档、两报告、350 份产品身份与活动文稿，未发现阻断项。[入库字节检查](staged-archive-check.json)保留当时 338 个暂存文件的范围；这三份后续交付记录不纳入先前 326 项复制清单。

正常快进集成及推送已完成，见[实际集成收据](integration/receipt.json)与[检出后字节核验](integration/checkout-verification.json)。这些后续交付记录同样不纳入先前 326 项复制清单。
