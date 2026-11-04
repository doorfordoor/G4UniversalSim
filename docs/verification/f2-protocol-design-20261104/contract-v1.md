# F2 会话协议合同提案（20261104）

- 任务：`F2-PROTOCOL-CONTRACT-20261104`（固定清单第二项"协议与证据设计"）。
- 性质：**设计交付**，不是实现；本任务不改产品/测试/CI、不改首轮实验原件、不提交 Git。
- 依据：首轮实验报告 `docs/collab/outbox/20261104-f2-session-baseline.md` 与冻结原件 `out/collab/f2-session-baseline-20261104/`（只读引用，不重跑）；源码读取基于当前 HEAD `5ee240fc`（仅主审 docs 提交，产品同 `92134da0`/`4eebbe9e` 基线）；产品 exe `build_vs2026/Release/G4UniversalSim.exe` sha256 `18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837`、`source_fingerprint=9e40e889…`、`build_git_commit=625cfee2…`。
- 本文件中的"现行行为"均指当前源码；"提案"均明确标注为设计。无法从源码确认的字段/线程语义标 **待验证**。

---

## 0. 结论摘要

1. **推荐方案 B**：新增版本化会话协议 `g4usim-session-v1`（stdin/stdout JSON-lines，带可辨认前缀的帧），后端在 `Idle` 状态接受经白名单校验的逐字段动作，`run` 返回逐轮收据；`cancel` 只在单线程实现，MT 明确拒绝；保留 csh 与 batch 旧路径不变并在 capability 中声明。
2. **方案 A（复用受控 csh）仍然有效**，但只覆盖已验证白名单 + 可一次性接受"命令失败即中止、下一轮新进程"的离线脚本；它无法为原生 GPS、未知命令或 GUI 下一轮面板提供逐命令回执、取消与断线语义。
3. 首轮 A/B/A 事实、原生 GPS 的 Manager/kernel 不一致、多源命令的硬中止，均作为 B 的设计输入，不是 B 存在的唯一理由；A 的三轮事实保留在 §2。
4. 需要用户拍板的一句话在 §10。

---

## 1. 首轮证据与措辞更正

首轮报告中以下三处必须按本文件口径引用（原件不改、不重跑）：

| 项目 | 准确表述 |
| --- | --- |
| 相空间记录 | `[phase_space]` 写的是**目标入射边界记录**（`src/Actions/SteppingAction.cc:81` → `ScoringManager::RecordPhaseSpace`；`src/Scoring/PhaseSpace.cc` 写行），不是"主顶点/首顶点"。只有真空、入射面确认、`trackID=1`、`parentID=0` 且 run/event 与源配置对得上时，才可作为"本实验内核消费证据"。 |
| `x=9.020` | 来自 `5 + 40 × (0.1/0.995)`（方向 `u=0.1` 的归一化分量），不是 `5 + 0.1 × 40`。 |
| 待证字段 | 首轮标"待证"的字段（isotropic/preset/reset、PreInit 的 point/direction/planeBeam、ion/confine/phase_space_file 延迟应用等）**不得自动进入首版可编辑白名单**。 |

首轮实测事实（引用自 `docs/collab/outbox/20261104-f2-session-baseline.md` §2–§6）：

- 同进程 A/B/A：runs 0/1/2 = 100.000/200.000/100.000 MeV proton；各 10/10 事件；`status=completed`、`run_count=3`、exit 0。
- 逐字段：particle→e-、energy→50 MeV、point→x=5.000 mm、direction→u=0.1（边界 x=9.020 mm）、planeBeam radius=5 mm（边界 x∈[-3.089, 3.902] mm）均出现内核消费证据。
- PreInit 缓存回放：初始化前设 300 MeV/e-，内核首轮即 300 MeV e-。
- 原生 `/gps/ene/mono 2 MeV`：内核消费 2.000 MeV，但 `/AIHL/source/print` 与 `run_summary` 仍报 100 MeV（stdout 846/851 行）→ **csh 无法为原生 GPS 给出权威回执**。
- 多命名源 + 单字段命令：`G4Exception(AIHL_SOURCE_001, FatalException)`，进程 exit `3221226505`（0xC0000409），无 `run_summary.txt`、哨兵未执行。
- `/AIHL/output/setDir` 在 `/run/initialize` 后：exit 1、`status=failed`、`run_count=0`、`interactive_command_failure_kind=geant4_illegal_application_state`，哨兵未执行。

---

## 2. 方案 A：复用受控 csh（基线）

### 2.1 可运行范围

A 是"外部驱动 + 一次性 csh 进程"：

```
python/脚本/GUI → stdin 逐行命令 → G4UniversalSim --ui --ui-session csh
```

- 支持：首轮已验证的单源、单线程、Idle 逐字段（particle/energy/point/direction/planeBeam）+ `beamOn` 多轮；PreInit particle/energy 缓存回放（已验证）。
- 不支持：运行期注入（csh 在 `beamOn` 返回前不读下一行）；无法在错误后继续（`beforeCommand` 抛错或 `ApplyCommand` 非零 → 会话停止并最终非零退出，`main.cc:114-160`、`main.cc:1050`）。
- 原生 GPS 可执行但不可审计（§1）。
- 多源单字段命令会在后端内部 Fatal（`src/Source/SourceMessenger.cc:100-108`），A 只能在**外部**先拒绝，不能依赖会话内恢复。

### 2.2 语义与代价

| 维度 | A 的可做到 | 代价/风险 |
| --- | --- | --- |
| 错误 | 命令失败 → 非零退出 + 摘要（若走到 finalization） | 源错误直接硬中止、无摘要；无法区分"可重试/需重启" |
| 取消 | 无会话内取消；只能 GUI `terminate/kill`（现 `runner.py:149/159`、`experiment_workflow.cancel:1009`） | 进程级终止 → 输出可能半截；无 run 收据 |
| 关闭 | `exit` 后正常收尾、写摘要 | 需先结束 run；无"运行中关闭"协商 |
| 失联 | stdin EOF 只在会话读下一行时被感知；运行中关闭管道不会打断 `beamOn` | GUI 无法区分"仍在跑"与"已失联" |
| 重放 | 记录命令序列 → 新进程重放 `.mac` | 无逐轮身份绑定；随机/线程/构建身份需 GUI 另存 |
| 收益 | 零后端改动；与现有 csh 回归/失败传播完全一致 | 面板只能读日志/摘要猜测"是否已应用" |

**结论（A 的定位）**：适合离线脚本与最小闭环；对"下一轮面板 + 逐轮可审计"不经济，但保留为兼容与逃生通道。

---

## 3. 方案 B：`g4usim-session-v1`

### 3.1 传输与帧格式

- 传输：现有 `--ui` 的 stdin/stdout 管道，不新增 socket/平台依赖；GUI 继续用 `QProcess`。
- 启动参数：`--session-protocol=g4usim-session-v1`（新；与 `--ui` 同用，替代 `--ui-session csh`）。旧后端不识别该参数会退出非零，GUI 必须先查 `--capabilities`（`gui/g4usim_gui/core/backend_capabilities.py:50`）再决定，不静默回退。
- **stdout 不是纯 JSON**：Geant4 `G4cout/G4cerr`、偏置/材料/物理 messenger 输出、以及现有进度帧 `[G4USimProgress] {...}`（`src/Actions/RunProgress.cc:38-72`）都会占用 stdout。因此协议帧必须是**可辨认前缀**：
  - 帧：`[G4USimSession] {"schema":"g4usim_session_v1",...}`，一行一帧，≤ 64 KiB，换行结尾。
  - 读取端容忍任意交错噪声与任意管道分片；只有以该前缀开头的完整行才进入协议解析（与 `ProgressParser` 相同的容错策略，`gui/g4usim_gui/core/run_progress.py`）。
  - 人类可读日志继续原样写 stdout/stderr；GUI 的 `runner._read_stdout`（`gui/g4usim_gui/core/runner.py:175`）继续把原始字节写入 `logs/stdout.log`，**不假设 stdout 纯 JSON**。
- 帧不重复实现进度：`run_progress` 事件仍由现有 `[G4USimProgress]` 帧提供；`g4usim-session` 只在其前后提供 `run_started`/`run_finished` 与身份收据。

### 3.2 握手与最小消息样例

（以下均为设计样例，字段名待实现时冻结；JSON 为单行。）

**client → backend：hello**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"hello","id":1,"client":"g4usim-gui/0.1","protocol_versions":[1],"wait_for_display":true}
```

**backend → client：welcome（或 error，见 §3.7）**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"welcome","id":1,"session_id":"3c6c0b7e...","protocol":1,"state":"idle","threads":1,"build":{"git_commit":"625cfee2...","source_fingerprint":"9e40e889...","geant4":"11.3.2","multithreaded":true},"limits":{"max_frame_bytes":65536,"max_events_per_run":10000000,"cancel":"single_thread_only"},"state_revision":0}
```

**client → backend：set_source（逐字段；request/response）**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"request","id":2,"method":"set_source","params":{"field":"energy","value":"200 MeV"},"expected_state_revision":0}
```

**backend → client：response（accepted + 应用状态）**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"response","id":2,"status":"applied","state_revision":1,"requested":{"field":"energy","value":"200 MeV"},"resolved":{"energy_MeV":200.0},"application_status":"gps_updated","kernel_evidence":{"level":"E1","source":"manager_state","run_id":null,"note":"next run must confirm"},"applied_revision":1}
```

**client → backend：run**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"request","id":3,"method":"run","params":{"events":10,"run_name":"round-b","threads":1},"expected_state_revision":1}
```

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"response","id":3,"status":"accepted","run":{"run_id":1,"run_seq":1,"state":"running","planned_events":10,"state_revision":1}}
[G4USimSession] {"schema":"g4usim_session_v1","frame":"run_finished","id":3,"run_id":1,"run_seq":1,"status":"completed","planned_events":10,"completed_events":10,"state_revision":1,"artifacts":[...],"replay":{...},"config":{"requested":{...},"resolved":{...}}}
```

**cancel（仅在单线程；见 §3.9）**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"request","id":4,"method":"cancel","params":{"run_id":1,"mode":"soft_abort"}}
[G4USimSession] {"schema":"g4usim_session_v1","frame":"response","id":4,"status":"accepted","cancel":{"run_id":1,"mode":"soft_abort","will_abort_after":"current_event"}}
[G4USimSession] {"schema":"g4usim_session_v1","frame":"run_finished","id":4,"run_id":1,"status":"cancelled","planned_events":10,"completed_events":7,"cancel_request_id":4}
```

**拒绝（验证级，不结束会话）**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"error","id":5,"status":"rejected","code":"source.multi_source_unsupported","message":"...","details":{"command":"/AIHL/source/energy 200 MeV","reason":"named sources present"},"state_revision":1,"terminal":false}
```

**正常关闭**

```json
[G4USimSession] {"schema":"g4usim_session_v1","frame":"request","id":6,"method":"shutdown","params":{"cancel_running":false}}
[G4USimSession] {"schema":"g4usim_session_v1","frame":"response","id":6,"status":"accepted","shutdown":{"finalizing":true}}
[G4USimSession] {"schema":"g4usim_session_v1","frame":"bye","id":6,"exit_code":0,"summary":{"status":"completed","run_count":3,"session_id":"3c6c0b7e..."}}
```

### 3.3 状态机

| 状态 | 进入方式 | 允许的客户端请求 | 退出 |
| --- | --- | --- | --- |
| `handshake` | 进程启动、协议参数校验后 | `hello` | `hello` 成功 → `idle`；失败 → 写 `error` 后退出 2 |
| `idle` | 握手完成、内核未初始化或已初始化 | `set_source`（白名单）、`validate`、`state`、`run`、`shutdown`、`ping` | `run` → `running`；`shutdown` → `closing` |
| `running` | `run` 被接受 | `state`、`cancel`（单线程）、`ping`；其它字段 set → `rejected`（busy） | `run_finished` → `idle` |
| `cancelling` | `cancel` 被接受、`AbortRun(true)` 已排队 | 仅 `state`/`ping` | `run_finished(cancelled)` → `idle` |
| `closing` | `shutdown` 被接受 | 无（后续请求 `rejected`） | 写摘要 → `bye` → 退出 0（或摘要失败退出 1） |
| `failed` | 致命执行错误 / 失联收尾失败 | 无 | 进程退出非零，stderr 保留原因 |
| `orphaned`（GUI 侧概念） | `bye` 未收到且管道 EOF/进程消失 | 只读历史/产物 | 不重连，转只读恢复 |

### 3.4 请求生命周期、身份与幂等

| 字段 | 含义 |
| --- | --- |
| `id` | 客户端单调递增请求 ID；同一 `id` 重发视为重试 |
| `request_id` | GUI 会话内唯一 UUID（`ExperimentWorkflow` 记录 `record_id`，`experiment_workflow.py:532-545`）；后端缓存最近 16 条 `id→response` |
| `session_id` | 每进程唯一（UUID）；`bye`/收据中回传 |
| `state_revision` | 后端语义状态（已接受配置）单调递增；`expected_state_revision` 不匹配 → `rejected` + `code=state.revision_changed`（GUI 据此刷新草稿） |
| `run_id` | Geant4 `G4Run::GetRunID()`（`RunAction.cc:56`）；G4MT 下由内核分配 |
| `run_seq` | 会话内从 0 递增；重放/比较按它对齐 |
| `config_revision` | 每个被接受 set/apply 递增；`run` 收据绑定当轮 `config_revision` |

幂等规则：

- 同 `id` 在缓存内重复 → 返回原响应，不再执行（重复 `run` 请求即按此去重）。
- 同 `request_id` 重复但 `id` 不同 → 视为重复提交；若原请求已终态返回缓存收据并标 `duplicate=true`。
- `idle` 时收到 `run`：ok；`running` 时收到第二个 `run` → `rejected` + `code=session.busy`。

### 3.5 逐轮身份与收据

`run_finished` 收据（设计字段）：

```json
{"schema":"g4usim_session_v1","frame":"run_finished","id":3,"run_id":1,"run_seq":1,
 "status":"completed|cancelled|failed|aborted",
 "planned_events":10,"completed_events":10,
 "state_revision":1,"config_revision":1,
 "threads":1,"seed_policy":"continue_from_start",
 "started_at":..., "finished_at":...,
 "output_dir":".../runs/round-b/output",
 "artifacts":[{"path":".../scorer_statistics_t0.csv","sha256":"...","size":...}],
 "summary":{"run_summary":".../run_summary.txt","recorded_run_id":1,"status":"completed"},
 "replay":{"session_id":"...","command_log":[...],"start_seed":12345,"threads":1,"run_events":[10,10,10],"replay_file":".../logs/session/replay.mac"},
 "evidence":{"level":"E2","observations":[{"kind":"phase_space","path":".../phase_space_t0.csv","rows":10,"checked":"trackID=1 parentID=0"}]}}
```

不变量：

- 收据中的 `completed_events` 来自 `G4Run` 最终计数（与 `RunSummary`/`RecordRun` 同口径，`OutputManager.cc:615`、`RunSummary.cc:202-203`），不是进度帧的中间值。
- `artifacts` 列出的文件在收据写出前存在；GUI 的 evidence job 仍会独立重算哈希（`experiment_workflow._run_finished:923` 的 `output_evidence` 模式不变）。
- 任何收据都带 `state_revision`/`config_revision`/`session_id`；无这些身份的收据不得进入面板"已生效"区。

### 3.6 首版字段白名单

模式：`PreInit`=内核初始化前；`Idle`=内核已初始化、无 run 运行；`Run`=事件循环内。证据级见 §3.8。**首版白名单只收首轮已有证据的字段**。

| 协议方法/字段 | PreInit | Idle | Run | 多命名源 | 延迟 GPS | 首版结论 | 证据来源 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `set_source particle` | 允许（缓存） | 允许 | 拒绝 | 预校验拒绝 | 待验证 | **允许** | 首轮 §3 首三轮 + PreInit 回放 |
| `set_source energy` | 允许（缓存） | 允许 | 拒绝 | 预校验拒绝 | 待验证 | **允许** | 首轮 §3/§4 |
| `set_source point` | 待验证 | 允许 | 拒绝 | 预校验拒绝 | 待验证 | 仅 Idle 允许 | 首轮 §4 |
| `set_source direction` | 待验证 | 允许 | 拒绝 | 预校验拒绝 | 待验证 | 仅 Idle 允许 | 首轮 §4 |
| `set_source planeBeam` | 待验证 | 允许 | 拒绝 | 预校验拒绝 | 待验证 | 仅 Idle 允许 | 首轮 §4 |
| `set_source isotropic/preset/reset` | 待验证 | 待验证 | 拒绝 | 待验证 | 待验证 | **不在首版白名单** | 首轮标待证 |
| `/gps/*` 原生命令 | 拒绝 | 拒绝 | 拒绝 | — | — | **拒绝**（诊断信息指向白名单/重启） | 首轮 §6 Manager/kernel 不一致 |
| run name | 新进程（INI/CLI） | 拒绝 | 拒绝 | — | — | 需新进程 | 首轮白名单 |
| output dir | 新进程（PreInit 仅） | 拒绝 | 拒绝 | — | — | 需新进程 | 首轮 setDir 反例 |
| seed/threads | 新进程 | 拒绝 | 拒绝 | — | — | 需新进程 | 既有 state-gate 测试 |
| 几何/物理/scoring/biasing | 新进程 | 拒绝 | 拒绝 | — | — | 需新进程 | `docs/功能性矩阵`/既有测试 |
| `/random/*` | 新进程（含 CLI 锁） | 拒绝 | 拒绝 | — | — | 需新进程 | `test_random_command_semantics.py` |

补充规则：

- 白名单之外的任意命令 → `rejected` + `code=protocol.command_not_whitelisted`，**不派发给 Geant4**。
- 首次可编辑面板只暴露"允许"行；"仅 Idle"行在 Idle 时可用，PreInit 时只显示当前值/待验证标记。
- 多命名源在**派发前**用 `RequireSingleSourceForCommand` 同等语义预校验（`src/Source/SourceManager.cc:316-320`），失败返回结构化错误而不是让 `G4Exception` 杀死进程（现状见 `SourceMessenger.cc:100-108`）。

### 3.7 错误模型与致命错误边界

三级错误，客户端必须区分：

| 级别 | 例子 | 后端行为 | 会话 | 是否写入 summary |
| --- | --- | --- | --- | --- |
| `rejected`（验证级） | 未知方法、非白名单、参数类型/范围/有限性、状态不匹配、多源冲突 | 不调用 Geant4；返回 `error` | 继续 `idle` | 不需要（GUI 记录 receipt） |
| `rejected_state`（Geant4 状态门） | `/run/initialize` 后改 PreInit-only 字段的等价请求 | 不派发；返回 `code=state.gate` | 继续 `idle` | 可选 `session_command_failure` |
| `fatal`（执行期） | 真实源 Fatal、物理 Fatal、`ApplyCommand` 崩溃 | 进程终止（保持现状传播） | `failed` | 若已进入 finalization 则写；否则没有 |

**不**用外围 try/catch 把 `G4Exception(FatalException)` 变成可恢复：`ReportCommandFailure`（`SourceMessenger.cc:100-108`）在 G4 异常处理器下终止进程；协议层只能通过"先验证、后派发"降低触发面。若白名单校验通过但仍发生 Fatal，会话视为 `failed`，GUI 通过输出目录/进度帧对账，不宣称该命令已应用。

### 3.8 证据分层（面板必须分开显示）

| 级 | 名称 | 含义 | 见证 |
| --- | --- | --- | --- |
| E0 | `config_accepted` | 协议校验通过、被接受进草稿/状态 | `response.status=applied` + `applied_revision` |
| E1 | `gps_object_updated` | `SourceManager`/GPS 对象状态已更新 | `SourceManager::PrintSummary` 等价字段（只作 E1，不作 E2） |
| E2 | `kernel_consumed` | 本 run 的逐事件消费记录（相空间/命中/摘要）与请求绑定 | run 收据的 `evidence.observations` + 产物哈希 |
| E3 | `physics_validated` | 物理正确性基准（外部 benchmark） | 既有 `scenarios/benchmarks/*`，本协议不产生 |

- 只凭 Manager 缓存或 `ApplyCommand` 返回 0 → **最多 E1**，不得写"已生效/已应用"。
- 只凭进度百分比 → 连 E1 都不算。

### 3.9 取消与不完整 run 记账

- 单线程：客户端发 `cancel`；读线程置 `cancel_requested` 原子标志；主线程在 `EventAction::EndOfEventAction`（`src/Actions/EventAction.cc:41-56`）检查后调用 `G4RunManager::AbortRun(true)`；G4 头文件说明 softAbort=true 在**当前事件结束后**中止事件循环（`G4RunManager.hh:190-197`）。`RunAction::EndOfRunAction`（`RunAction.cc:259`）把 `RunProgress::End(..., cancelled)` 与逐 run 记账写出；`completed_events` 取 `G4Run` 最终计数。
- 不完整 run 记账：`run_summary.txt` 仍按现有 `RecordRun` 记 `run_<i>_planned_events`/`run_<i>_completed_events`（`RunSummary.cc:202-203`），并拟新增（实现计划 S1）`run_<i>_outcome=cancelled|completed|failed`、`run_<i>_cancel_request_id`；会话摘要另加 `session_status`、`session_cancel_count`。**不把"取消"写成失败 run**，也不把半截 run 当完成。
- MT：`EventAction` 在 worker 线程执行；在 worker 回调里调用 `AbortRun` 的线程安全性在 Geant4 11.3 未文档化（**待验证**）。首版 `threads>1` 时 `cancel` 返回 `rejected` + `code=cancel.unsupported_multi_thread`，GUI 明确提示"停止当前运行需要终止并重新启动（会丢失本 run 收据）"。MT 的协作取消作为 S3 之后议题，不在首版承诺。

### 3.10 关闭、断线与重连

| 事件 | 设计行为 |
| --- | --- |
| `shutdown`（idle） | 写最终 summary、`bye{exit_code:0}`、退出 0 |
| `shutdown`（running） | `rejected` + `code=session.busy`；客户端必须先 `cancel`（单线程）或终止（MT） |
| stdin EOF（idle） | 视同 `shutdown`；写 summary、exit 0 |
| stdin EOF（running） | 置取消标志（若单线程）→ soft abort → `run_finished(cancelled)` 后写 summary、exit 0；摘要与收据标 `disconnect_during_run=true` |
| 进程死亡（崩溃/kill） | GUI 侧 `orphaned`；只用输出目录/历史记录做只读对账；**不重连**同进程（stdin 已消费、会话状态不可恢复） |
| 心跳 | 客户端 2 s `ping`；后端 `pong`；连续 10 s 无响应 GUI 标记 `lost`，仅允许 terminate/kill 与只读恢复 |

重连给未来的可选形态（不在首版）：同进程重连需要独立控制通道（如命名管道）且进程未退出；本设计明确**stdin/stdout 管道 EOF 不等于可重连**。

### 3.11 重放

- 收据携带 `replay` 块：会话命令序列（含 run 边界与事件数）、启动 seed、threads、构建身份、`source_fingerprint`、INI/源文件哈希、输出目录。GUI 在 `output_dir/logs/session/replay.mac` 写宏（**放在 logs 子目录，避免混入 run_metadata 的生成文件清单**；实现 S1 需确认 evidence job 不将其视为未登记文件——**待验证**）。
- 重放执行：走现有 batch/`--macro` 入口（`main.cc` 的 macro 预检/执行路径），不经过协议；比较工具断言：
  - 单线程：逐 run 的 `planned/completed`、`run_<i>_*`、相空间逐事件（`eventID`+`trackID`+`parentID` 排序）与收据逐项严格一致；
  - MT：按真实事件映射比较（同一 seed/线程数下按 `eventID` 排序的相空间行、逐 run 摘要）；若某产物无事件键（如聚合直方图），列为"缺口"并由 `replay_compare` 输出 `unmapped_artifacts`，不得用统计相近替代严格一致。
- 随机策略：首版重放新进程从相同初始 seed 重放完整命令/事件序列（`seed_policy=continue_from_start`）；不提供"从中间 run 开始"的精确续跑。MT 的逐事件随机可分性 **待验证**，验证不了就保持为缺口。

### 3.12 旧后端与降级

- capability 增加 `"session":{"protocols":[1],"progress":"g4usim_progress_v1","cancel":"single_thread_only"}`（`include/Core/BackendCapabilities.hh:14` 的现有 JSON 扩展）。
- 旧后端：无 `session` 段 → GUI 只提供"一次性运行"（现有 `runner.start` 语义），不冒充会话可用；无 `--session-protocol` 参数时进程会因未知参数退出（`main.cc` 参数解析），不得作为会话失败静默重试。
- 明确不伪造：旧后端不能给出 `applied_revision`/`run` 收据/取消，面板显示 `legacy_one_shot`。

### 3.13 实现代价（初估，供排期）

| 部分 | 初估 |
| --- | --- |
| 后端 SessionServer + 分发/校验 + 收据 + capability | 3–5 人日 |
| 后端取消（单线程）+ 不完整 run 记账 + 测试 | 2–3 人日 |
| GUI 会话客户端 + 下一轮面板 + i18n | 3–4 人日 |
| 重放生成/比较工具 + 收据桥接 | 2–3 人日 |
| 证据/矩阵/文档与跨平台回归 | 2–3 人日 |

A 的硬化版（仍无收据/取消/断线）初估 1–2 人日，但每遇拒绝/崩溃都需重启进程，面板体验与证据质量不可比。

---

## 4. 代码所有者与线程模型

### 4.1 入口与生命周期

| 位置 | 现有职责 |
| --- | --- |
| `main.cc:580` `int main(...)` | 参数解析、`SimulationManager` 创建 |
| `main.cc:654`/`main.cc:695` | `--inspect-run` 的 `Configure()`；正常路径 `sim.Configure()` |
| `main.cc:738` | `sim.Initialize()`（Manager 层配置，非内核） |
| `main.cc:744` | `CreateRunManager`（`main.cc:567-574` 在 MT 构建下用 `G4MTRunManager`） |
| `main.cc:753-761` | detector/physics/actions `SetUserInitialization`；`InitializeSourceAfterPhysicsListRegistered()` |
| `main.cc:782` | `G4UImanager` 取得 |
| `main.cc:1050` | `ui.SessionStart()`：现有交互会话入口 |
| `main.cc:1157` 起 | `FinalizeRunSummary` + 退出码 |
| `main.cc:82-235` | `AuditedCshSession` 类；`main.cc:114` `ExecuteCommand` 在主线程同步执行 `ApplyCommand` |
| `main.cc:69-80` | `FailFastCshShell::GetCommandLineString`：从 stdin 同步读命令 |

协议模式应在 `sim.Configure()`（`main.cc:695`）之后、`runManager->Initialize()`（由 `/run/initialize` 触发）之前启动 SessionServer；宏预检/交互守护沿用现有分支（`main.cc:1018` 附近），只是把 `ui.SessionStart()` 换成 `SessionServer::Serve()`。

### 4.2 线程

| 线程 | 职责 | 约束 |
| --- | --- | --- |
| Qt GUI 线程 | `G4USimRunner` 拥有 `QProcess`（`runner.py:20/88`）、写 stdin、读 stdout、驱动面板；`ExperimentWorkflow` 也必须在 owner 线程调用（`experiment_workflow.py:406`） | 不在 GUI 线程做阻塞 Geant4 或长文件哈希 |
| 后端 reader 线程（新） | 只读 stdin、解析帧、入有界队列、置取消/断线标志、写 `pong` 前的轻量状态 | 不调用任何 Geant4 API、不写 Geant4 输出 |
| 后端主线程（Geant4 用户线程） | 从队列取请求、执行白名单校验与 `ApplyCommand`/`beamOn`、写 response、执行 soft abort | 所有 Geant4 调用只在此线程；单线程模式下 `EventAction` 也在该线程 |
| 后端 writer（可并入主线程） | 串行化 `[G4USimSession]` 帧写 stdout（互斥），不与 `G4cout` 争用同一行 | 帧写完整后 flush |
| 证据线程（现有 `EvidenceJob`） | GUI 侧哈希/证据核验（`experiment_workflow.py:37-45` 注释与 `_work`），不碰 QProcess | 沿用现有 job 线程模型 |

取消路径（单线程）：GUI 写 `cancel` → reader 线程置原子标志 → 主线程在 `EventAction::EndOfEventAction`（`EventAction.cc:41`）读到标志 → `G4RunManager::AbortRun(true)`（`G4RunManager.hh:190-197`：softAbort 在当前事件结束后中止事件循环）→ `RunAction::EndOfRunAction`（`RunAction.cc:259`）写 `RunProgress::End` 与 run 记账 → 主线程发 `run_finished`。MT 取消首版明确不支持（§3.9）。

### 4.3 GUI 现有所有者

| 位置 | 现有职责 | 协议模式下的变化 |
| --- | --- | --- |
| `gui/g4usim_gui/core/runner.py:20` | `G4USimRunner`；`start()` 88 组装 CLI、重定向 stdout/stderr 到 `logs/`、`_read_stdout` 175 解析进度帧 | 新增 `start_session(...)` 或 `session` 句柄；帧解析走新的 `SessionClient`，进度帧仍由现有 parser 消费 |
| `runner.py:149/159` | `terminate()`/`kill()` | 保留为强制逃生；正常路径优先发 `cancel`/`shutdown` |
| `gui/g4usim_gui/core/experiment_workflow.py:349` | K1 动作服务；`run()` 797、`_run_finished` 923 用 `output_evidence`/`parse_run_summary` 做 E2；`cancel` 1009 目前 terminate/kill | 会话收据作为 E0/E1 快事实接入；`cancel` 先发协议 cancel，超时才 terminate |
| `gui/g4usim_gui/core/experiment_workflow.py:532-545` | 记录 `g4usim_experiment_record_v1`（`session_id`/`run_id`/`revision`/`level`/`status`） | 增加 `protocol_session_id`、`applied_revision`、`evidence_level` 字段（向后兼容可选） |
| `gui/g4usim_gui/core/edit_transactions.py:50` | `EditSession.current()/revision`：下一轮草稿来源 | 面板用 `current()` 生成草稿，`revision` 做 `expected_state_revision` 的本地对应 |
| 新 `gui/g4usim_gui/core/session_protocol.py` | 帧编解码、请求 ID、超时、重连边界、错误映射 | 由 `G4USimRunner`/`ExperimentWorkflow` 共同使用，不重复实现传输 |
| 新 `gui/g4usim_gui/widgets/next_round_panel.py` | 下一轮面板 | 见 §5 |

---

## 5. 下一轮面板数据契约（设计）

面板五区（不合并）：

| 区 | 数据来源 | 必须字段 | 不可显示为 |
| --- | --- | --- | --- |
| 本轮已生效 | 最近一次 `run_finished` 收据 + `run_summary` | `run_seq`、`config_revision`、requested/resolved、E2 证据 | "物理已验证"（E2 不是 E3） |
| 下一轮草稿 | `EditSession.current()` 快照（`edit_transactions.py:50`）+ 待提交动作 | 草稿 revision、目标字段旧值/新值、需重启标记 | "已发送/已应用" |
| 待确认 | 会话 `accepted` 未 `run_finished` 的请求；`ExperimentWorkflow` 的 pending record（`_begin` 532） | request_id、状态、预计事件数 | "已完成" |
| 拒绝 | 最后一则 `error{status:rejected}` | code、message、恢复建议（字段级） | "已尝试并失败"而无 code |
| 需重启 | 白名单"需新进程"字段被修改 | 字段、原因、重启后生效 | 自动重启/自动提交 |

交互：正常菜单入口（非命令面板 hack）；三轮流程 = 草稿→提交→`run`→收据→下一轮草稿保留；取消/关闭走 §3.9/§3.10；旧后端显示 `legacy_one_shot` 只读区，不显示"会话"字样。i18n 中文文案走 `core/i18n.py`（现有约定，新 key 必须补 `ZH_CN`）。

---

## 6. 实施计划

### 6.1 允许修改文件清单（若批准实施 B）

后端（含新增）：

- `main.cc`（新 `--session-protocol` 参数与启动分支）
- 新 `include/Core/SessionServer.hh`、`src/Core/SessionServer.cc`
- `include/Core/SimulationManager.hh`、`src/Core/SimulationManager.cc`（会话安全的状态读取、白名单派发入口；不改 batch/csh 语义）
- `include/Core/BackendCapabilities.hh`（capability `session` 段）
- `include/Source/SourceManager.hh`、`src/Source/SourceManager.cc`（新增 `ValidateSessionCommand` 预校验；既有 Fatal 路径不改）
- `include/Actions/RunProgress.hh`、`src/Actions/RunProgress.cc`（新增 `CancelRequested()`/每 run 结束标记；进度帧格式不变）
- `src/Actions/EventAction.cc`（单线程取消检查）
- `src/Actions/RunAction.cc`（run 级 outcome/cancel 记账）
- `include/Output/RunSummary.hh`、`src/Output/RunSummary.cc`（新增 `run_<i>_outcome` 等字段；既有键不变）
- `include/Output/OutputManager.hh`、`src/Output/OutputManager.cc`（可选的 `RecordRunOutcome`）
- `CMakeLists.txt`（新增源文件）

GUI：

- 新 `gui/g4usim_gui/core/session_protocol.py`
- `gui/g4usim_gui/core/runner.py`
- `gui/g4usim_gui/core/experiment_workflow.py`
- `gui/g4usim_gui/core/backend_capabilities.py`
- 新 `gui/g4usim_gui/widgets/next_round_panel.py`
- `gui/g4usim_gui/window/shell.py`、`gui/g4usim_gui/main_window.py`
- `gui/g4usim_gui/core/i18n.py`
- `gui/smoke_tests/smoke_main_window_ui.py`（若新增页面/停靠导致页数或导航断言变化）

测试与文档：

- 新 `scripts/test_session_protocol.py`（真实后端集成；`scripts/run_m0_tests.py` 注册，`requires ("exe",)`）
- 新 `gui/smoke_tests/smoke_session_protocol.py`（Qt/Python 客户端契约与错误映射）
- 新 `gui/smoke_tests/smoke_next_round_panel.py`（面板五区、i18n、旧后端降级、取消按钮可用性）
- `scripts/run_m0_tests.py` 注册
- 新 `docs/会话协议.md`；`docs/实时运行进度.md` 补会话帧说明；`docs/功能支持矩阵.md` 增加"会话协议（未验收）"行
- `STATUS.md`、`CHANGELOG.md`、`AGENTS.md` §0、`gui/AGENTS.md`、`docs/agent-history.md`、`docs/测试平台说明.md`

### 6.2 三个内部提交节点

| 节点 | 内容 | 验收关卡 |
| --- | --- | --- |
| S1 后端骨架 | capability `session`、帧编解码、hello/welcome、白名单 `set_source`、`state`、`run` 收据、`shutdown`；单线程 cancel + `run_<i>_outcome` 记账；`scripts/test_session_protocol.py` 真实后端 A/B/A + 拒绝 + 重复 + 取消 + EOF；`check_report_evidence` 通过 | 不接 GUI；csh/batch 既有回归全绿；无收据乱写 |
| S2 GUI 客户端 + 下一轮面板 | `session_protocol.py`、`runner`/`experiment_workflow` 接入、`next_round_panel.py`、i18n、旧后端降级；`smoke_session_protocol`/`smoke_next_round_panel` 通过 | 三轮菜单操作；取消/关闭/失联/旧后端；不改变现有 runner 一次性路径 |
| S3 重放 + 证据/文档 | `replay.mac` 生成、`replay_compare`、单线程严格比较、MT 事件映射或缺口；文档/矩阵/AGENTS；全量四层矩阵与严格门禁 | 干净 worktree 证据、无 skip、无未验证声明 |

### 6.3 验收正反例矩阵

| # | 类型 | 场景 | 期望 |
| --- | --- | --- | --- |
| 1 | 正 | 同进程 A/B/A（真实三轮） | 每轮收据 `config_revision/run_id` 正确；E2 证据与请求绑定 |
| 2 | 正 | 白名单每字段（particle/energy/point/direction/planeBeam） | `applied` + E1；随后的 run 给出 E2 |
| 3 | 正 | `shutdown`（idle） | 写 summary、`bye{0}`、exit 0 |
| 4 | 正 | 单线程 `cancel` | `run_finished(cancelled)`、`completed<planned`、摘要 `outcome=cancelled`、会话仍可继续下一轮 |
| 5 | 正 | EOF（running） | soft abort + 摘要 `disconnect_during_run`、exit 0；GUI 记 `orphaned` |
| 6 | 负 | 多源 + 单字段命令 | `rejected source.multi_source_unsupported`，不派发、不崩溃、会话继续 |
| 7 | 负 | 原生 `/gps/ene/mono` | `rejected protocol.command_not_whitelisted`（诊断指白名单） |
| 8 | 负 | `run` 进行中再发 `run` | `rejected session.busy`；无第二个 run |
| 9 | 负 | 同一 `id` 重复 `run` | 返回缓存 `run_finished`，不产生第二次执行 |
| 10 | 负 | MT `cancel` | `rejected cancel.unsupported_multi_thread`，明确提示需终止重启 |
| 11 | 负 | 旧后端（无 capability/session 参数） | GUI 降级一次性运行；不假装会话可用 |
| 12 | 负 | 白名单外修改（seed/threads/geometry/output） | `rejected` + `needs_new_process`；不派发 |
| 13 | 重放 | 单线程会话收据 → 新进程 replay | 逐 run 收据与相空间逐事件严格一致 |
| 14 | 重放 | MT 同线程数 replay | 按 `eventID` 映射比较；无键产物列缺口，不用统计近似 |
| 15 | 正 | 关窗（idle） | `shutdown` → `bye` → 进程退出；GUI 无残留子进程 |
| 16 | 负 | 失联（进程崩溃） | 收据 `unknown`、无"已完成"；只读恢复可读历史，不重连 |

### 6.4 不做的事

- 不把 csh 既有失败传播语义改成"吞错继续"（batch/csh 回归必须保持）。
- 不为原生 GPS 伪造回执；不允许协议模式接受任意非白名单命令。
- 不在 reader 线程/worker 线程直接调用 Geant4。
- 不在首版承诺 MT 取消、同进程重连、从中间 run 精确续跑。
- 不用统计"大致一致"替代重放的严格比较。

---

## 7. 风险与待验证

| # | 风险 | 处置 |
| --- | --- | --- |
| 1 | MT `AbortRun` 从 worker 回调调用的线程安全性未文档化 | 首版 MT 取消 `rejected`；S3 再验证 |
| 2 | `G4Exception` Fatal 无法被协议层捕获 | 预校验 + 白名单；Fatal 即 `failed`，不宣称已应用 |
| 3 | stdout 交错导致帧被截断/黏连 | 前缀+行帧+容忍扫描（复刻 ProgressParser 的容错）；单帧≤64 KiB；GUI 保留原始 stdout 日志 |
| 4 | MT 逐事件随机可分性 | S3 验证；失败则 MT replay 记缺口 |
| 5 | `replay.mac`/收据写入输出目录会否触发"未登记文件" | 放 `logs/session/`；S1 用 evidence job 验证，否则改用独立目录 |
| 6 | 旧后端参数不识别 | GUI 先查 capability；不重试、不静默降级 |
| 7 | 取消后 `run_summary` 与收据口径不一致 | 收据计数取 `G4Run` 最终值（同 `RecordRun`），S1 用真实反例对账 |
| 8 | GUI 线程阻塞（证据哈希/文件） | 沿用 `EvidenceJob` 线程；协议客户端不在 GUI 线程做阻塞 IO |
| 9 | 白名单外"任意命令"的安全边界被误解为全面支持 | 文档/矩阵显式写"白名单外拒绝"，不写进支持矩阵 |

---

## 8. 建议（不阻塞，不新增清单前置）

1. 把 `run_progress` 帧与 session 帧统一为同一 telemetry schema 的 v1 子集（已有 `sequence`，`RunProgress.cc:27/52`），减少两套解析。
2. 将来可加独立控制通道（命名管道/本地 socket）以实现同进程重连，但必须先解决"进程未退出且会话状态可恢复"的身份与锁问题。
3. `replay_compare` 可作为独立只读工具，不并入产品 GUI；先服务证据，再考虑入面板。

---

## 9. 给用户的决定句

**"选 B（版本化 `g4usim-session-v1`，csh 保留为兼容/逃生路径）还是选 A（只复用受控 csh，接受无逐命令回执、无取消、失败即重启）？"**

推荐 B；若选 A，§6 全部后端条目删除，仅保留 GUI 面板读摘要/日志与一次性运行，且面板必须明示"无逐命令回执"。
