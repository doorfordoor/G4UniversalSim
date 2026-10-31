# K1 UI candidate v2 — ready for parent/Averroes independent review

Base `f9a9ddbfcabe69067707a5a209caff005748f510`, tracked clean. 唯一写者Tesla，模型按本任务gpt-6.1-sol/high，消耗未知。仅OUT四产品/两smoke，未提交、未改tracked、未触碰第五正式进程。原 `k1-final-ui-candidate` 是不可变v1；39个文件逐SHA核对未变。原独审REQUEST_CHANGES保留，不改写为通过。

v2相对v1仅改 `window/experiment.py` 与 `smoke_k1_workflow.py`。提取 `_project_experiment_command`，generated package绑定末尾和external无package分支都执行同一显示投影。合法actual launch program/arguments优先，随后兼容record.command；launch-only也能显示。logical cwd取launch或execution_bundle，缺事实为Unknown；physical launch cwd不同时单列。F5编辑路径、生成路径绑定、前置preview与资格/进程所有者保持原责任。

新增回归调用真实 `ExperimentWorkflow._prepare(..., 'run')` 的external分支，输入来自本smoke真实完成Generate文件，保留原F5草稿/源证据，仅同步四个fixture路径/模式草稿。仅环境probe为ready fixture；准备不运行后端。产物先断言can_run、无package、真实执行目录与command；随后完成status和launch为明确受控显示收据，通过真实 `_experiment_completed` 测显示，不当模拟成功。覆盖direct/restore、observed argv覆盖刻意不同planned argv、非法launch回退record.command、launch-only、缺cwd Unknown、双语与F5不变。

## 原因果负例与正例

- `v1-negative-external.log/json` 首轮是fixture四条raw draft未同步，失败于can_run，**不是目标负例**；如实保留。
- `v1-negative-external-r2.log/json` 修正fixture后，未改v1产品，先通过真实准备与无package断言，然后精确失败于completed external cwd断言；日志显示仍是editor-planned-command及编辑cwd。exit1，68个入口。
- 同一回归+全部原workflow步骤在v2 exit0，178入口。五种记录形状×中英文共10次完成显示。原generated direct/restore/unknown、真实Generate及完整前置preview检查全部保留。
- panel exit0/1629；既有真实completed record cwd重放exit0/3；真实producer pending exit0/2。
- 原workflow39 / v1 57 / v2 74个assert AST站点完整保留；panel原67/v1与v2 74完整保留。入口计数是v3保守计数，非独立命题数。
- 六源码compile、git apply --check、tracked HEAD/clean与v1全部39文件身份检查通过。全部日志SHA取实际原字节，不冒正式矩阵证据门禁或LF发布报告。

## 交付与边界

`candidate.patch` 相对冻结基线；`v1-to-v2.patch` 仅增量。`manifest.json`包含六文件完整SHA、日志/收据SHA；`static-checks.json`包含原/v1断言完整性。overlay harness只在内存加载候选、正式__file__定位fixture，TEMP仅新OUT，无修改tracked或runner。

旧8213/f9前端两发现与v1独审仍为历史原件。v2等待父/Averroes独立审查及父后续冻结，作者测试不自签；不关闭K1，不接资源边界/late-reparse范围。原第四coverage不变；新append-only coverage另行输出。

| 文件 | v2 SHA256 | 相对v1 |
|---|---|---|
| gui/g4usim_gui/window/run.py | `3af4daefa4c0818fba9879acffe14e15ece2c8b908d2b26b0526e9fa7e873d56` | unchanged |
| gui/g4usim_gui/window/experiment.py | `0ff241b88dfa03dc24743a9a10145db681e542006c00f4c8e55d53f3f9252d8f` | changed |
| gui/g4usim_gui/widgets/experiment_panel.py | `01f91f3db0081536110e2acc9958ec76783af485dbbc1f378ec52231f94133f3` | unchanged |
| gui/g4usim_gui/core/i18n.py | `002de76b33480160415c3c4b2fb9e38455b2ce94b1aedacfcd83121387ecdf0a` | unchanged |
| gui/smoke_tests/smoke_k1_workflow.py | `8eac62b07e0c1fc9411037eafe2ea066165a954af4b0557cf013abbb9e1faffc` | changed |
| gui/smoke_tests/smoke_k1_panel.py | `658fcb292ca0b2ab60b8ef73bd3a4d285593c13824076850e4bd8cfbef8d38a0` | unchanged |

复核命令（需复制至另一个OUT目录再跑，避免覆盖本轮日志）：

```powershell
python -B out/collab/k1-final-ui-candidate-v2/run_candidate.py smoke_k1_workflow.py --v1-products
python -B out/collab/k1-final-ui-candidate-v2/run_candidate.py smoke_k1_workflow.py
python -B out/collab/k1-final-ui-candidate-v2/run_candidate.py smoke_k1_panel.py
```
