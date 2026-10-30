# F4 第二轮 CI 原始证据：未通过

冻结提交 `096f4b37c15aac0a12206914b9b02ee1b8a3d976`。Linux [41050259071](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41050259071)、M0 [41050258833](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41050258833) 均已结束，均为 push 第1次执行；未 rerun、取消或改写工作流。

M0 Windows 成功；两个 Linux Geant4 job 和 M0 Ubuntu 在 `gui_f4_layout` 的257断言后 `none_dealloc`、exit -6失败。后端及集成步骤因前置GUI失败而 skipped，官方只产生8份报告，不能称12份完整矩阵。用例报告内部skip为0，与4个未执行profile分开记录。

已完整收取4个官方ZIP和4份connector解码job日志。官方ZIP摘要、本地ZIP与解包成员字节、8份报告及284条用例日志SHA/断言marker、逐profile清单和冻结源码/测试指纹已核对。严格同平台F1基线门禁通过5/8，3份GUI报告按失败拒绝；未使用incomplete/legacy放宽。完整清单151项仍为static28/gui43/backend59/integration21，本轮每平台实际只执行static+gui71项。

| 官方产物 | Profile | 用例 | 断言 | 严格门禁退出码 | 失败用例 |
|---|---|---:|---:|---:|---|
| linux-evidence-11.4.3 | [gui](linux-evidence-11.4.3/linux-gui/20261030-114741-099e7cf1/report.json) | 43 | 2930 | 1 | gui_f4_layout |
| linux-evidence-11.4.3 | [static](linux-evidence-11.4.3/linux-static/20261030-114648-8bee0b77/report.json) | 28 | 2133 | 0 | 无 |
| linux-evidence-11.3.2 | [gui](linux-evidence-11.3.2/linux-gui/20261030-114752-110e65d1/report.json) | 43 | 2930 | 1 | gui_f4_layout |
| linux-evidence-11.3.2 | [static](linux-evidence-11.3.2/linux-static/20261030-114656-8d3ccc0f/report.json) | 28 | 2133 | 0 | 无 |
| m0-report-ubuntu-latest | [static](m0-report-ubuntu-latest/20261030-114510-2ff87a6f/report.json) | 28 | 2133 | 0 | 无 |
| m0-report-ubuntu-latest | [gui](m0-report-ubuntu-latest/20261030-114608-505a6641/report.json) | 43 | 2930 | 1 | gui_f4_layout |
| m0-report-windows-latest | [static](m0-report-windows-latest/20261030-114606-6fa32e60/report.json) | 28 | 2124 | 0 | 无 |
| m0-report-windows-latest | [gui](m0-report-windows-latest/20261030-114729-fa45c7eb/report.json) | 43 | 2932 | 0 | 无 |

后端/integration未执行，因此本轮不声称完成后端运行或对应build identity验收。job日志为connector解码后UTF-8文本，不冒称GitHub原始压缩日志字节。Windows本机全量和原生实窗状态由root另外验收，本CI收据不代替它们。

独立诊断见 `out/collab/f4-ci-independent-diagnosis.md`：现有PySide6.12/Python3.11存在更广的None引用损耗，不能只修改highlighter getter便宣布修复。该目录只保存当前失败轮次，旧5d6f008证据在兄弟目录且未覆盖。

[完整逐字节核对](evidence-integrity-audit.json)、[简明机器收据](round-summary.json)、[冻结用例清单](frozen-case-manifest.json)。
