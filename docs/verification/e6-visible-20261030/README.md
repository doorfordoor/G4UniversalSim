# E6 最终验收（2026-10-30）

**E6 阶段已完成。** 实现冻结于 `a779634483d1f077357433c532ccb0d9e3dc5517`；最后实窗执行检出为 `838e2e366f433037f85b07cd6cfb7c76ba87b6fe`，后者仅追加文档/证据，产品与测试指纹不变。阶段与实际主线集成分别登记于[机器状态](../e6-full-20261030/acceptance-state.json)。本次补验未修改产品或测试源码。

## 交付范围

394项schema登记、主INI版本边界、保留原文件的迁移副本、诊断身份去重，以及现有编辑子集的项目兼容、标准运行包恢复与复制。主负责人最终审查，Sol分别实现、测试及交叉复核；[DeepSeek真实前端设计记录](../../collab/outbox/20261029-deepseek-e6-design.md)保留。完整使用及兼容差异见[配置兼容与迁移](../../配置兼容与迁移.md)。

## 验收证据

| 层级 | 结果 | 证据 |
| --- | --- | --- |
| 冻结Windows全量 | 134/134，0 fail/skip，42815个v3断言入口；同v3的2C基线门禁通过 | [原自动报告](../e6-full-20261030/README.md) |
| 真实Linux CI | Geant4 11.3.2/11.4.3各134/134；run 40931653660；M0 run 40931654093两平台各58/58 | [原CI记录](../e6-full-20261030/ci/README.md) |
| 原自动证据完整性 | 12份CI严格门禁、4份官方归档摘要、384份CI用例日志SHA；原2711文件再次匹配 | [原独立复核](../e6-full-20261030/independent/README.md) |
| Windows实际窗口 | 12个观察状态、20张原生截图；迁移、恢复、拒绝路径与结果呈现通过 | [主审视觉记录](evidence/independent/e6-root-visual-review.md) |
| 真正Inspect→Run | 2线程、seed43、1轮2/2事件；退出0、GUI success、摘要completed，无输出失败 | [操作收据](evidence/visible/receipts.json)、[后端摘要](evidence/visible/runs/20261030_073310_writer_run_copy/output/run_summary.txt)、[metadata](evidence/visible/runs/20261030_073310_writer_run_copy/output/run_metadata.json) |
| 独立证据核验 | 155项通过；58原资源、13专项源码、完整源码/测试指纹、exe身份、输入重生成与运行事实一致 | [独立核验](evidence/independent/e6-visible-independent-verification.json) |
| 可见导入负向补充 | 普通Open错误、Recent/Snapshot警告、普通Open拒绝包专用格式；四次拒绝后完整状态不变 | [补充收据](evidence/visible/import-supplement/receipts.json)、[实际进程退出0](evidence/visible/import-supplement/process-exit.json) |

源码指纹 `ab79c6c2227518bd7f38d5109998ed0998d8fd53ad500cfbe714d544eb19a474`；测试指纹 `e9b4f852e36dca85971d40da2c63ed6fd184055358ca965116babba6b16fafd4`；Windows exe SHA256 `09dd7521be81f21c1c2a6f1b751eb1c6b171c70c4b206814a821b3e8b73aa3a5`。

## 可见证据如何解释

实际Windows窗口由程序化Qt驱动，主审通过原生Windows捕获直接观察，并原生执行取消、标签切换及关闭弹窗；不是Qt自渲染截图，也不声称真人逐项点击。典型状态：[迁移预览](evidence/visible/native/01-migration-preview-1.png)、[恢复材料](evidence/visible/native/05-snapshot-materials-0.png)、[真实运行成功](evidence/visible/native/08-real-run-result-0.png)、[普通打开错误](evidence/visible/native/09-import-open-1.png)、[最近项目警告](evidence/visible/native/10-import-recent-1.png)。20张图包括同次主窗口和对话框，不是20个独立用例。

六组合法复制参数使用合成Inspect和截获最终命令，覆盖seed缺省/0、当前main优先于旧snapshot、Unicode及ASCII空白；第七组1025检查拒绝。这七组没有执行仿真。1025的首次可见警告由截获的真实产品消息重建为非阻塞窗口，不能与随后四个未经替换的真实导入模态混称。真正2事件运行单独保留原始输入、日志、摘要及metadata。

首个GUI host已closed并消失，但启动器未保留退出码，明确为unknown；不由此推定0。补充GUI的app.exec和执行会话均0，后端真实运行退出0。原自动报告中的“实窗pending”是当时状态，原README也在不可变清单内，本报告追加终态而不追改它。

## 归档与边界

[复制清单](copy-manifest.json)登记135个原件、4749003字节及逐文件SHA；原始绝对路径为执行来源，归档相对路径才是可携带证据入口。清单SHA256为 `2be2d241eec4cb61cc845b8fe5215c489300ecfedc1e456c265ed02216f02db4`。本README及后续交付检查、集成收据不冒充这135份运行原件。

Linux原报告保留git_dirty=true：指纹覆盖内容匹配，但完整dirty清单未采集，不能声称整个检出clean。迁移格式接受、运行完成与物理正确性仍分别解释；不增加Q2科研验证、J2高级编辑、K1任意资源包或全DPI/原生Linux桌面支持。GUI旧threads=0现在明确拒绝，其他兼容差异见使用说明。

下一完整阶段为 **F1 输出身份与来源**，其后F4/F5/K1；I1按既定依赖可并行。

## 已发生的集成

阶段关闭交付 `b7c6a4c8a8aaadda455c93d4f93672f56130579e` 已正常推送至 `roadmap/E6-config-compat`；独立 `q1-final` 工作区的 `codex` 从 `c6bf8ad` 快进到同一提交并普通推送，远端两分支已核对一致。见[集成收据](integration-receipt.json)。本补记只登记已发生事实，原D盘DSH检出保持独立，无强推或产品改动。
