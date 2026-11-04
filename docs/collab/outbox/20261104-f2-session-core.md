# F2-SESSION-CORE-20261104 交付回执（作者自测版）

状态：作者实现与自测完成，**待主审独立复验**；未提交 Git、未推送、未改 GUI/CI/
旧 csh 与 batch 行为。J3 已按主审口径范围关闭，本任务不改变其关闭状态。

## 1. 任务范围

按 `docs/collab/decisions/20261104-f2-protocol-choice.md` 选择 B 后，实现
`g4usim-session-v1` 后端第一版：`--session-server` 模式的 JSON-lines 会话、
受控源编辑、运行/取消/关闭、逐轮收据与 artifacts 证据、记录目录、能力自描述、
严格 JSON 解析器（固定版本）、本机真实自测与协议文档。不做 GUI 接入、不做
旧入口重写、不改 csh/batch 的失败传播。

## 2. 改动文件（均在任务允许清单内）

新增：

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `include/Core/SessionServer.hh` | 2,239 | `ba63beca…` |
| `src/Core/SessionServer.cc` | 58,736 | `51719507…` |
| `include/Core/SessionJson.hh` | 1,503 | `1b09cfc2…` |
| `src/Core/SessionJson.cc` | 4,933 | `83e95760…` |
| `include/ThirdParty/SessionJsonDependency.hh` | 919,975 | `9bea4c80…` |
| `docs/licenses/session-json.md` | 2,182 | `ee93e0d3…` |
| `scripts/test_session_protocol.py` | 20,973 | `1c3d24ce…` |
| `scripts/test_session_cancel_mt.py` | 10,377 | `c22bd8ba…` |
| `docs/会话协议.md` | 7,684 | `59b3c9d2…` |

修改（+203/−5，行数来自 `git diff --stat`）：`main.cc`（+54：参数、互斥校验、
入口条件、session 分支）、`include/Core/BackendCapabilities.hh`（+9）、
`include/Source/SourceManager.hh`（+24）/`src/Source/SourceManager.cc`（+48，
仅会话安全校验与实际读回）、`include/Actions/RunProgress.hh`（+2）/
`src/Actions/RunProgress.cc`（+18）、`src/Actions/EventAction.cc`（+10）、
`src/Actions/RunAction.cc`（+7）、`include/Output/OutputManager.hh`（+5）/
`src/Output/OutputManager.cc`（+29）、`scripts/run_m0_tests.py`（+2，仅注册两个
新用例）。

未改动：GUI、`.github/workflows`、旧 csh/批处理行为、既有测试、既有限制与门禁。
`session_cancel_mt` 用例中的取消依赖 TLS RunManager 的 `AbortRun(true)`；未做
“跨事件边界取消物理结果正确”的声明。

## 3. 构建与身份

- HEAD：`7ba92df4 docs(F2): record chosen protocol B and start backend implementation [skip ci]`
- 工作树：dirty（本任务新增/修改文件均未提交；另有历史未跟踪用户材料）
- 构建：`cmake --build build_vs2026 --config Release --target G4UniversalSim`
  成功（无新增 warning 需要处理）。
- 可执行文件：`build_vs2026/Release/G4UniversalSim.exe`，sha256
  `83be899f49d5246712d43e538e9876ccdcbba051728aa5f9acca387717ce0aa1`，
  `--capabilities` 报告 `build_git_commit=7ba92df4…`、
  `source_fingerprint=6ec4965905148761…`。
- 依赖：nlohmann/json 3.11.3 单头文件（sha256 `9bea4c80…`，MIT，许可证正文见
  `docs/licenses/session-json.md`），固定随仓库提供，不联网下载。

## 4. 协议与实现要点

- 帧：每行一个顶层 JSON 对象，≤65,536 字节；`hello` 握手后方可请求；
  `seq` 严格 +1、幂等窗口、`request_id` 去重、`state_revision` 控制并发编辑。
- 操作：`get_state`、`initialize`、`set_source`、`run`、`cancel`、`ping`、
  `shutdown`。变更类请求（除 `get_state`）必须带当前 revision；`cancel`/`ping`
  在读取线程内以原子标志快速处理，不排队等待 `beamOn` 返回。
- 源编辑白名单：单源、`particle`/`energy`/`position`/`direction`/`plane_beam`；
  多命名源、相空间源、高级 GPS 源与离子源拒绝并给出原因。响应区分
  `requested`/`resolved`/`application_status=configured`/
  `evidence_level=unknown`/`kernel_evidence=not_observed`；不把 Manager 接受
  说成内核已应用。
- 运行：`run` 在未初始化时拒绝；运行中 `busy` 拒绝其它变更请求；运行结束发送
  `run_finished`，带逐轮收据路径、`artifacts`（来自 OutputManager 登记表）与
  receipts（`g4usim_session_run_receipt_v1`）。重复 `request_id` 返回
  `duplicate=true` 且不重复运行。
- 取消：读取线程登记目标 run id（无目标用 -1 哨兵，避免 run 0 被误判取消），
  主线程在事件边界软中止；`run_finished.status=cancelled`、
  `cancel_requested=true`、`completed_events<planned_events`，随后下一轮不受影响。
- 关闭：`shutdown` 空闲时发送 `closing` 并以 0 退出；stdin EOF 同样 0 退出，
  但按实现只在记录文件写 `direction=meta`、`event=eof_close`，不伪造 `closing` 帧。
- 错误分级：请求级拒绝（`status=rejected`，会话可继续）；协议级错误
  （`kind=error`，非零退出）；非有限数、重复键、非对象根、深层嵌套、非法 UTF-8
  转义均在解析阶段拒绝，不会以未捕获异常终止进程。
- 记录：`--session-record-dir`（绝对路径、不能位于 `--output` 之下）内写
  `session.jsonl` 与 `run-<runID>.json`；收据只证会话层完成与文件登记，不能替代
  物理基准。

## 5. 自测证据（实际执行）

| 命令 | 结果 |
| --- | --- |
| `python -B tools/test_assert_probe.py scripts/test_session_protocol.py` | PASS，278 断言，exit 0 |
| `python -B tools/test_assert_probe.py scripts/test_session_cancel_mt.py` | PASS，121 断言，exit 0 |
| `python -B scripts/run_m0_tests.py --profile backend --case session_protocol --case session_cancel_mt` | 2 pass / 0 fail / 0 skip；asserts=282/79、116/45；报告 `out/verification/f2-session-final2/20261104-131351-b8bf67b7/` |
| 兼容回归：`--case interactive_commands --case random_command_semantics --case command_state_gating` | 3 pass / 0 fail；asserts=23/6、309/168、302/23；报告 `out/verification/f2-session-compat/20261104-130455-fcc68124/` |
| `--capabilities` | 含 `session` 段（协议、transport、launch/record 参数、handshake、白名单、取消等级 `experimental`、解析器版本与 sha） |

协议用例覆盖：握手/状态、Unicode 字段、中文与 emoji、数组参数、`set_source`
配置语义、未初始化 run 拒绝、旧 revision 拒绝、幂等冲突、未知 op、initialize/
already_initialized、真实 6 事件运行与收据/artifacts 一致性、重复 run 不重复、
shutdown、记录日志逐行可解析、stdout 混入 Geant4 日志时的帧识别、终端拒绝
（未握手、协议不支持、非法 JSON、非对象根、重复键）、CLI 拒绝（缺记录目录、
与 `--ui` 组合、记录目录位于输出目录内）与 EOF 退出。取消用例覆盖：多 worker
运行中 ping、busy 拒绝、cancel 接受与 cancelled 收据、完成后第二轮正常。

原件：`out/collab/f2-session-core-20261104/`（runner 报告、兼容报告、exe sha）。

## 6. 已知限制与未验证

- 取消只在 Windows 双线程、默认物理配置下实测；Linux、大物理列表、取消期间
  文件完整性未验证，能力仍标 `experimental`。
- 未做断线重连、仅只读历史恢复、多线程逐事件重放比较、引擎初态重放。
- 未验证 `position`/`direction`/`plane_beam` 在 PreInit 阶段的行为；首版白名单
  只声明 Idle 生效。
- 不提供配置整体切换、输出目录切换、seed/线程变更、原生 `/gps/*` 编辑。
- GUI/外部驱动未接入；`cancel` 的物理正确性与旧 csh 语义差异需单独评估。
- 工作树 dirty：本任务文件未提交，属于“作者候选”，不能当作干净候选证据。

## 7. 复现步骤

```
cmake --build build_vs2026 --config Release --target G4UniversalSim
python -B tools/test_assert_probe.py scripts/test_session_protocol.py
python -B tools/test_assert_probe.py scripts/test_session_cancel_mt.py
python -B scripts/run_m0_tests.py --profile backend \
  --case session_protocol --case session_cancel_mt \
  --report-root out/verification/f2-session-final2
```

## 8. 边界

本回执只声明“作者实现 + 本机自测 + 证据路径”；不声明阶段验收通过。未提交
Git、未推送、未改 GUI/CI、未改旧入口行为、未安装依赖、未占用桌面。等待主审按
协议合同与实施合同独立复验。
