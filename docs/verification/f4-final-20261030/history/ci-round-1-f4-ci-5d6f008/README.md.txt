# F4 首轮 CI 原始证据：未通过

冻结提交 `5d6f00854e1c7304f677c4ed033772aa2d95ae9d`。候选状态 `historical_candidate_pending_or_failed_native`，不得据此关闭 F4。

Linux [run 41047666520](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41047666520)；M0 [run 41047666580](https://github.com/doorfordoor/G4UniversalSim/actions/runs/41047666580)。全部为本次 push 的第 1 次执行，未 rerun、取消或改写 CI。

已核对 4 个官方 ZIP 摘要和全部解包成员字节、4 份 connector 解码 job 日志、12 份报告与 444 个用例日志原始 SHA/断言 marker。冻结清单每个 profile 的顺序及数目精确匹配 static28/gui43/backend59/integration21；Linux 各151、M0 各71。Job 日志保存的是 connector 解码后 UTF-8 文本，不冒称 GitHub 原始压缩日志字节。

严格同平台、同 Geant4、同 profile 的 F1 基线门禁通过 10/12；失败用例 4，skip 0。失败报告保持原样，无 incomplete/legacy 放宽。后台实际构建身份及源码/测试指纹均核对；git_dirty 原值保留。

| 官方产物 | Profile | 用例 | 断言 | 严格门禁退出码 | 失败用例 |
|---|---|---:|---:|---:|---|
| linux-evidence-11.3.2 | [backend](linux-evidence-11.3.2/linux-backend/20261030-112724-2e369994/report.json) | 59 | 40387 | 0 | 无 |
| linux-evidence-11.3.2 | [gui](linux-evidence-11.3.2/linux-gui/20261030-112608-d1d0a3bb/report.json) | 43 | 2802 | 0 | 无 |
| linux-evidence-11.3.2 | [integration](linux-evidence-11.3.2/linux-integration/20261030-114204-7709d157/report.json) | 21 | 4423 | 1 | gui_f4_inspect_backend, gui_run_inputs |
| linux-evidence-11.3.2 | [static](linux-evidence-11.3.2/linux-static/20261030-112512-4beb1b5f/report.json) | 28 | 2133 | 0 | 无 |
| linux-evidence-11.4.3 | [backend](linux-evidence-11.4.3/linux-backend/20261030-112547-8ed2c533/report.json) | 59 | 39795 | 0 | 无 |
| linux-evidence-11.4.3 | [gui](linux-evidence-11.4.3/linux-gui/20261030-112506-9645b706/report.json) | 43 | 2802 | 0 | 无 |
| linux-evidence-11.4.3 | [integration](linux-evidence-11.4.3/linux-integration/20261030-113427-a2f80f69/report.json) | 21 | 4423 | 1 | gui_f4_inspect_backend, gui_run_inputs |
| linux-evidence-11.4.3 | [static](linux-evidence-11.4.3/linux-static/20261030-112434-c28d43a7/report.json) | 28 | 2133 | 0 | 无 |
| m0-report-windows-latest | [static](m0-report-windows-latest/20261030-112358-b8a09602/report.json) | 28 | 2124 | 0 | 无 |
| m0-report-windows-latest | [gui](m0-report-windows-latest/20261030-112522-59eef0cd/report.json) | 43 | 2804 | 0 | 无 |
| m0-report-ubuntu-latest | [static](m0-report-ubuntu-latest/20261030-112319-34a8259b/report.json) | 28 | 2133 | 0 | 无 |
| m0-report-ubuntu-latest | [gui](m0-report-ubuntu-latest/20261030-112416-6bbf0ae7/report.json) | 43 | 2802 | 0 | 无 |

失败详情：

- linux-evidence-11.3.2 / [gui_f4_inspect_backend](linux-evidence-11.3.2/linux-integration/20261030-114204-7709d157/gui_f4_inspect_backend.log): exit `-6`，断言 `45`；日志 `none_dealloc` 发生于解释器 finalizing，不能以打印 OK/断言通过替代正常退出。
- linux-evidence-11.3.2 / [gui_run_inputs](linux-evidence-11.3.2/linux-integration/20261030-114204-7709d157/gui_run_inputs.log): exit `-6`，断言 `103`；日志 `none_dealloc` 发生于解释器 finalizing，不能以打印 OK/断言通过替代正常退出。
- linux-evidence-11.4.3 / [gui_f4_inspect_backend](linux-evidence-11.4.3/linux-integration/20261030-113427-a2f80f69/gui_f4_inspect_backend.log): exit `-6`，断言 `45`；日志 `none_dealloc` 发生于解释器 finalizing，不能以打印 OK/断言通过替代正常退出。
- linux-evidence-11.4.3 / [gui_run_inputs](linux-evidence-11.4.3/linux-integration/20261030-113427-a2f80f69/gui_run_inputs.log): exit `-6`，断言 `103`；日志 `none_dealloc` 发生于解释器 finalizing，不能以打印 OK/断言通过替代正常退出。

本轮另有 root 报告的实窗几何目标未绘制缺陷，证据位于 `out/verification/f4-visible-5d6f008/native/06-geometry-painted.png`。旧 Windows 全量已由 root 主动中断，CI 收集者未中断任何工作流。此文件只记录这两个官方 CI 运行，不代替 Windows 全量、原生实窗或物理验收。

[逐 ZIP 成员/报告/日志证据检查](evidence-integrity-audit.json)；[简明机器收据](round-summary.json)；[冻结用例清单](frozen-case-manifest.json)。失败诊断线索见 `out/collab/f4-ci-failure-notification.md`，未经实验证实的线索不得写作原因。
