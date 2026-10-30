# F4 最终候选 CI：未通过

冻结提交 `7d718d038a00d89995ea773b4772764116b620c3`。Linux [41054895374](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41054895374)、M0 [41054895506](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41054895506)，本次push第1次执行；未rerun、取消或改写工作流。

已收取4个官方ZIP、4份完整connector解码job日志、6份实际报告、200次用例执行。官方ZIP摘要、本地ZIP、解包成员字节、报告与用例日志SHA/断言marker、冻结head/source/tests身份及逐profile有序清单均已核对。严格同平台/同Geant4/profile的F1基线门禁通过4/6；fail10，case skip0。

完整预期为Linux每版本152（static28/gui44/backend59/integration21）、M0每平台72，共448次执行。以下报告为实际取得的原件；没有用缺失/失败轮替代完整验收。

| 官方产物 | Profile | 用例 | 断言 | 严格门禁退出码 | 失败用例 |
|---|---|---:|---:|---:|---|
| linux-evidence-11.4.3 | [static](linux-evidence-11.4.3/linux-static/20261030-122510-e811ca08/report.json) | 28 | 804 | 1 | f4_producers, f4_document_diagnostics, config_migration, project_snapshot_compat, duplicate_generated_package_model |
| linux-evidence-11.3.2 | [static](linux-evidence-11.3.2/linux-static/20261030-122515-53015885/report.json) | 28 | 804 | 1 | f4_producers, f4_document_diagnostics, config_migration, project_snapshot_compat, duplicate_generated_package_model |
| m0-report-ubuntu-latest | [static](m0-report-ubuntu-latest/20261030-122318-eece386b/report.json) | 28 | 2133 | 0 | 无 |
| m0-report-ubuntu-latest | [gui](m0-report-ubuntu-latest/20261030-122400-b954aa4a/report.json) | 44 | 2938 | 0 | 无 |
| m0-report-windows-latest | [static](m0-report-windows-latest/20261030-122401-9291506b/report.json) | 28 | 2124 | 0 | 无 |
| m0-report-windows-latest | [gui](m0-report-windows-latest/20261030-122531-f8cb355c/report.json) | 44 | 2940 | 0 | 无 |

Qt运行身份由实际binding smoke日志提供：

- m0-report-ubuntu-latest: Python 3.11.17，PySide6/shiboken6/Qt 6.11.3/6.11.3/6.11.3；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查=True）。[原日志](m0-report-ubuntu-latest/20261030-122400-b954aa4a/gui_qt_binding_lifetime.log)
- m0-report-windows-latest: Python 3.11.9，PySide6/shiboken6/Qt 6.11.3/6.11.3/6.11.3；100次普通void/空属性读取的4组delta均0，且用例正常退出（核查=True）。[原日志](m0-report-windows-latest/20261030-122531-f8cb355c/gui_qt_binding_lifetime.log)

辅助程序的实际构建完成记录见机器收据。由于两Linux job在static阶段即失败，本轮effective_gdml/scoring_numeric/random_command_semantics均未执行，篡改日志负对照亦未执行；不能以构建成功替代这些验收。

未执行/缺失profile：`[['linux-evidence-11.3.2', 'backend'], ['linux-evidence-11.3.2', 'gui'], ['linux-evidence-11.3.2', 'integration'], ['linux-evidence-11.4.3', 'backend'], ['linux-evidence-11.4.3', 'gui'], ['linux-evidence-11.4.3', 'integration']]`。不得据此宣称完整矩阵。

Linux本轮具体失败原因是导入PySide6.QtGui时缺少系统库`libEGL.so.1`，共5种用例×2个Geant4版本，在执行断言前退出1。这是新增的CI系统依赖缺口，与前两轮none_dealloc失败分开记录。M0两个job均成功，实际Qt运行版本均为6.11.3。

未通过项：

- Run 41054895374: failure
- Negative-control evidence absent for job 124059813413
- Job 124059813413: failure
- Negative-control evidence absent for job 124059813917
- Job 124059813917: failure
- Strict baseline gate failed: linux-evidence-11.4.3/static
- Nonpassing cases in linux-evidence-11.4.3/static: ['f4_producers', 'f4_document_diagnostics', 'config_migration', 'project_snapshot_compat', 'duplicate_generated_package_model']
- Strict baseline gate failed: linux-evidence-11.3.2/static
- Nonpassing cases in linux-evidence-11.3.2/static: ['f4_producers', 'f4_document_diagnostics', 'config_migration', 'project_snapshot_compat', 'duplicate_generated_package_model']
- Missing profiles after workflow failure: [('linux-evidence-11.3.2', 'backend'), ('linux-evidence-11.3.2', 'gui'), ('linux-evidence-11.3.2', 'integration'), ('linux-evidence-11.4.3', 'backend'), ('linux-evidence-11.4.3', 'gui'), ('linux-evidence-11.4.3', 'integration')]
- Four actual GUI runtime-version receipts required
- All three helper cases required on both Linux versions

这是CI验收收据。Windows本机全量、原生实窗和最终阶段关闭由root独立记录；CI通过不证明物理验证。Job日志保存的是connector解码后的UTF-8文本，不冒称原始GitHub压缩日志字节。旧5d6f008和096f4b3两轮原件保持原样。

[逐字节独立检查](evidence-integrity-audit.json)、[机器汇总](round-summary.json)、[冻结清单](frozen-case-manifest.json)、[原始CI收集摘要](ci-evidence.json)。
