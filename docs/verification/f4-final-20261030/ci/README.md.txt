# F4 最终候选 CI：通过

冻结提交 `a9ad09dfd6e99d287fa77ff7f38e7919c475e1b9`。Linux [41056994075](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41056994075)、M0 [41056993987](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41056993987)，本次push第1次执行；未rerun、取消或改写工作流。

CI报告保留 `a9ad09d` 身份；本机Windows与原生实窗报告保留产品提交 `7d718d0` 身份。两提交只差Linux工作流增加6行运行库安装，其他Git树条目、产品与测试指纹相等，见[独立映射](ci-product-identity-map.json)。不把两个commit说成相同。

已收取4个官方ZIP、4份完整connector解码job日志、12份实际报告、448次用例执行。官方ZIP摘要、本地ZIP、解包成员字节、报告与用例日志SHA/断言marker、冻结head/source/tests身份及逐profile有序清单均已核对。严格同平台/同Geant4/profile的F1基线门禁通过12/12；fail0，case skip0。

完整预期为Linux每版本152（static28/gui44/backend59/integration21）、M0每平台72，共448次执行。以下报告为实际取得的原件；没有用缺失/失败轮替代完整验收。

| 官方产物 | Profile | 用例 | 断言 | git_dirty原值 | 严格门禁退出码 | 失败用例 |
|---|---|---:|---:|---|---:|---|
| linux-evidence-11.4.3 | [backend](linux-evidence-11.4.3/linux-backend/20261030-124414-30aa0a05/report.json) | 59 | 39797 | True | 0 | 无 |
| linux-evidence-11.4.3 | [gui](linux-evidence-11.4.3/linux-gui/20261030-124251-313219a4/report.json) | 44 | 2938 | True | 0 | 无 |
| linux-evidence-11.4.3 | [integration](linux-evidence-11.4.3/linux-integration/20261030-125846-f29cc36d/report.json) | 21 | 4423 | True | 0 | 无 |
| linux-evidence-11.4.3 | [static](linux-evidence-11.4.3/linux-static/20261030-124154-6e1eb34d/report.json) | 28 | 2133 | True | 0 | 无 |
| linux-evidence-11.3.2 | [backend](linux-evidence-11.3.2/linux-backend/20261030-124410-181bc528/report.json) | 59 | 40387 | True | 0 | 无 |
| linux-evidence-11.3.2 | [gui](linux-evidence-11.3.2/linux-gui/20261030-124250-06c516a1/report.json) | 44 | 2938 | True | 0 | 无 |
| linux-evidence-11.3.2 | [integration](linux-evidence-11.3.2/linux-integration/20261030-125840-1c58dbf6/report.json) | 21 | 4423 | True | 0 | 无 |
| linux-evidence-11.3.2 | [static](linux-evidence-11.3.2/linux-static/20261030-124157-a6e99cc7/report.json) | 28 | 2133 | True | 0 | 无 |
| m0-report-windows-latest | [static](m0-report-windows-latest/20261030-124035-5b9c7e29/report.json) | 28 | 2124 | False | 0 | 无 |
| m0-report-windows-latest | [gui](m0-report-windows-latest/20261030-124143-737a5b79/report.json) | 44 | 2940 | False | 0 | 无 |
| m0-report-ubuntu-latest | [static](m0-report-ubuntu-latest/20261030-124000-75b141a9/report.json) | 28 | 2133 | False | 0 | 无 |
| m0-report-ubuntu-latest | [gui](m0-report-ubuntu-latest/20261030-124100-bf1644f3/report.json) | 44 | 2938 | False | 0 | 无 |

每份报告的git_dirty保留原值；此通用标志包含Git未跟踪文件，不等同于已跟踪产品源码变化。验收同时要求tracked_source_gate通过、无未登记源码、源码与测试指纹精确匹配。CI依赖/构建目录的状态与本机7d产品checkout的clean状态分别记录，不宣称CI均为clean。
本轮Linux 8份报告git_dirty均为true，M0 4份均为false。Linux日志记录在仓库下创建bin/micromamba、.g4env-*和.micromamba；这些依赖路径未被.gitignore忽略，能解释dirty标志。工作流未保存逐项porcelain清单，不能据此声称已穷举全部dirty条目。build_linux本身被/build*/规则忽略。见[状态范围证据](dirty-flag-scope-final.json)。

Qt运行身份由实际binding smoke日志提供：

- linux-evidence-11.4.3: Python 3.11.18，PySide6/shiboken6/Qt 6.11.3/6.11.3/6.11.3；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查=True）。[原日志](linux-evidence-11.4.3/linux-gui/20261030-124251-313219a4/gui_qt_binding_lifetime.log)
- linux-evidence-11.3.2: Python 3.11.18，PySide6/shiboken6/Qt 6.11.3/6.11.3/6.11.3；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查=True）。[原日志](linux-evidence-11.3.2/linux-gui/20261030-124250-06c516a1/gui_qt_binding_lifetime.log)
- m0-report-windows-latest: Python 3.11.9，PySide6/shiboken6/Qt 6.11.3/6.11.3/6.11.3；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查=True）。[原日志](m0-report-windows-latest/20261030-124143-737a5b79/gui_qt_binding_lifetime.log)
- m0-report-ubuntu-latest: Python 3.11.17，PySide6/shiboken6/Qt 6.11.3/6.11.3/6.11.3；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查=True）。[原日志](m0-report-ubuntu-latest/20261030-124100-bf1644f3/gui_qt_binding_lifetime.log)

辅助程序实际用例收据 6/6；Linux 篡改日志负对照通过 2/2。构建、用例日志及负对照均见机器收据；不以构建成功替代运行验收。

这是CI验收收据。Windows本机全量、原生实窗和最终阶段关闭由root独立记录；CI通过不证明物理验证。Job日志保存的是connector解码后的UTF-8文本，不冒称原始GitHub压缩日志字节。旧5d6f008、096f4b3、7d718d0三轮原件保持原样。

[逐字节独立检查](evidence-integrity-audit.json)、[机器汇总](round-summary.json)、[冻结清单](frozen-case-manifest.json)、[原始CI收集摘要](ci-evidence.json)。
