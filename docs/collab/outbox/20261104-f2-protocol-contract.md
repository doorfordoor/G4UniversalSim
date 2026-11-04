# F2 协议合同（v2，首审六组修正版）

日期：2026-11-04。范围：F2 固定清单第二项「协议与证据设计」。
状态：v1 已交主审首审；v1 原字节由主审保存。本文件按首审六组意见修正（C1–C6），仍是**设计材料，不实施生产入口**，供用户做协议选择。产品、测试、CI、首轮实验原件均未改动。

## 0. 摘要、推荐与修正记录

1. **用户已选择方案 B**（`docs/collab/decisions/20261104-f2-protocol-choice.md`，2026-11-04：采用版本化会话接口，保留 csh 与 batch；不再重复请求方向确认）。本文档按 B 定稿，A 作为兼容/回退通道保留：新增版本化会话协议 `g4usim-session-v1`（stdin/stdout JSON-lines，带可辨认前缀帧），后端在 `Idle` 状态接受经白名单校验的逐字段动作，`run` 返回逐轮收据，证据按 E0–E3 分层；保留 csh 与 batch 旧路径不变，并在 capability 中声明能力。
2. **执行线程已改正（C1）**：本项目 MT 构建在 `main.cc:567-574` 的 `CreateRunManager()` 中**无条件创建 `G4MTRunManager`**（serial `G4RunManager` 只在无 `G4MULTITHREADED` 的构建出现）；`--threads 1` 仍是 MT run manager + 1 个 worker，事件级动作（RunAction/EventAction/SensitiveDetector/ScoringManager）在 worker 线程执行。因此 v1 中「threads=1 时 EventAction 在主线程」的判断是**缺陷**，已删除。取消按 MT worker 事件边界设计，但在 Geant4 11.3 的线程安全语义**待实测前不宣称可用**：capability 默认 `cancel: "unsupported"`，实测路径见 §3.8。不把串行 run manager 当作 MT 批处理路径的逐位重放证据。
3. **请求去重与终态归属已封口（C2）**：过期旧请求明确 `request.expired` 且不再执行；同 id 不同 body 是 `request.id_conflict`；同 body 重复在 revision/busy 判断前返回缓存响应。`run_finished` 只归属原 `run` 请求；`cancel` 有自己的回应与 `cancel_request_id`，不改挂、不重发。样例见 §3.4。
4. **应用层级与输入代次分开（C3）**：Manager 接受只写 `manager_accepted: true` + `application_status: unknown` + `evidence_level: E1`，**不得**显示为 applied/GPS updated；真正内核证据用现有 EffectiveConfig 的 `application_status`/`evidence_level` 表达，并由逐 run 收据绑定（E2）。GUI 草稿 `EditSession.revision` 与后端 `state_revision` 是两个域，只记录映射，不直接相等。
5. **输出与现有合同相容（C4）**：首版每进程固定线程数与输出根；沿用现有 `_tN[_rR]` 产物命名；`run_label` 只是会话/GUI 元数据，**不是**后端 `run_name`；每轮终态只在本轮 worker/master 输出关闭且产物实际存在后绑定，不提前引用只在最终化写出的 `run_summary.txt`/`run_metadata.json`；会话记录目录是显式参数且位于输出根之外，不依赖 `logs` 子目录豁免，不改 F1 `generated_files` 规则。
6. **运行中控制与关闭（C5）**：reader 线程只做协议层解析、拒绝与入队，绝不调用 Geant4；主线程的 `beamOn` 阻塞期间，busy/error/ping 由 reader 按不可变协议快照应答；运行中 `set` 一律拒绝、不排队到下一轮。`cancel` 是唯一允许入队的控制请求（仅设置协议原子标志，不调用 Geant4），最终确认由所有者线程重验 run/revision 后发出，详见 §3.8。帧写入串行化，但**不承诺** Geant4 人类日志绝不插帧；损坏帧按协议错误终止，不静默跳过。stdin 阻塞读改为带超时的平台等待，shutdown 有界 join，不 detach。
7. **重放判据（C6）**：主审额外实测（固定 seed 1904、1 worker、A/B/A）24 个 CSV 中 21 个原字节相同，3 个 `scorer_statistics*.csv` 只 `fom_per_s`/`run_wall_time_s` 不同，其余物理字段严格相同。全字节比较失败**原样保留**，不是产品缺陷；比较器只显式排除这些时间/性能列，不删物理统计列、不用容差冒逐位。本实验未捕获引擎初态，不代表最终重放；MT 必须实测并列差异，无事件键的聚合统计仍严格比较。详见 §3.9。
8. **实现范围小**：新增后端会话服务器（一个进程内线程 + 严格最小 JSON 解析，仓库当前无 JSON 依赖——`CMakeLists.txt`/`include`/`src` 中无 nlohmann/rapidjson/jsoncpp）、capability 声明、GUI 会话客户端与下一轮面板。协议锁不保证与 `G4cout` 同锁，见 §3.1。

**修正记录（v1 → v2）**

| 编号 | v1 问题 | v2 处理 |
|---|---|---|
| C1 | §3.9/§4.2 把 threads=1 当主线程 EventAction | 改为 MT + N worker 事实，取消标注 unsupported 待实测 |
| C2 | §3.4 最近 16 条缓存未定义过期/冲突/重复顺序 | 重写为 §3.4，含过期、冲突、缓存响应、终态归属 |
| C3 | §3.2 样例 `status:applied` 与 E1 证据矛盾 | §3.5 重写：accepted/configured 与 applied/E2 分离 |
| C4 | §3.6 有 `run_name`/`threads` 参数、每轮换 output | §3.6/§3.7 固定线程/输出根；`run_label` 元数据；产物绑定规则 |
| C5 | §3.10 未写谁在主线程阻塞时应答、reader shutdown | §3.1/§3.7/§3.8 补线程模型、有界关闭、损坏帧策略 |
| C6 | §3.11 用容差/删列的风险表述 | §3.9 改为显式排除时间/性能列，保留物理列与字节失败 |

## 1. 首轮实验事实（F2-PROTOCOL-EVIDENCE-20261104，冻结原件）

- 报告：`docs/collab/outbox/20261104-f2-session-baseline.md`；证据：`out/collab/f2-session-baseline-20261104/`（190 文件 8.3 MB，`evidence/index.json`、`results.json`、`results-summary.md`）；主审已独立复现 8 例。
- 同进程 A/B/A：runs 0/1/2 = 100/200/100 MeV proton，各 10/10 事件，exit 0，`status=completed`，`run_count=3`；Manager print 同步为 100/200/100。第三轮不要求与第一轮逐位相同（随机状态前进）。
- 逐字段：particle→e-、energy→50 MeV、point→边界 x=5.000 mm、direction→边界 x=9.020 mm（=5+40×(0.1/0.995)，不是 5+0.1×40）、planeBeam radius=5→x∈[-3.089, 3.902] mm；PreInit 缓存回放 300 MeV e- 生效。
- 拒绝：多命名源 + 单字段命令 → exit `3221226505`（0xC0000409）硬中止、`G4Exception: AIHL_SOURCE_001`、无 run_summary、哨兵未出现；`/AIHL/output/setDir` 在 `/run/initialize` 后 → exit 1、`status=failed`、`run_count=0`、`interactive_command_failure_kind=geant4_illegal_application_state`、Geant4 status=200、哨兵未出现。
- native GPS 反例：`/gps/ene/mono 2 MeV` 后内核下一轮为 2 MeV，但 `/AIHL/source/print` 与 run_summary 仍报 100 MeV。这只证明「原生 GPS 不经过 SourceManager 缓存、csh 无法给权威回执」，**不能推出**任意命令的有限白名单 csh 在所有场景都不可用。
- 相空间记录（`[phase_space]`）是**目标入射边界记录**，不是「首顶点」概念；本实验在真空、确认 `trackID=1`/`parentID=0` 并核对 run/event 与入射面后才作为消费证据，不能泛化到所有相空间行为。

## 2. 方案 A：复用受控 csh

- 语义：`--ui --ui-session csh` 在同一进程读 stdin 命令（`main.cc:1018` 构造、`main.cc:1050` `SessionStart`）；`AuditedCshSession::ExecuteCommand`（`main.cc:114`）同步 `G4UImanager::ApplyCommand`；源命令错误经 `src/Source/SourceMessenger.cc:100-108` `G4Exception(..., FatalException)` 中止会话并非零退出。
- 可运行范围：单源、PreInit 与 Idle 的 `particle/energy/point/direction/planeBeam` 有实际消费证据（首轮）；单字段失败为会话终止（不可恢复）；无取消、无总线、无重放、无逐轮机器收据；原生 GPS 不可审计。
- 代价：零后端改动；但 UI 只能推断、不能证明，必须保留「命令被接受但内核未复现」的未知态。适合保留为兼容/诊断通道（方案 A 单独可用，但不是 F2 目标）。
- 取用建议：v1 不删除 csh；能力声明 `session_protocol: false` 时 GUI 仍可回退到 csh 的手动流程，但必须显示**不可重放、不可审计**。

### 2.1 A 的错误、取消、关闭、失联与重放语义（对照用）

- 错误：源命令 Fatal（`SourceMessenger.cc:100-108`）直接终止会话并非零退出；无请求级拒绝，只能新进程重来。既有 batch/csh 失败传播保持。
- 取消：无协议级取消；只能 Ctrl-C / 终止进程；不完整 run 由既有 failure registry 与最终摘要按现状记录（exit 非零），但不产生逐轮机器收据。
- 关闭：`exit` 命令或 stdin EOF 结束；没有 `session_finished` 帧，也没有记录目录收据。
- 失联：父进程保持管道但不再写命令时，stdin 读取阻塞，进程可能长期停留；关闭管道则退出；无状态核对接口，重连=新进程+重读文件。
- 重放：无逐轮收据；重放只能靠人工记录命令与比对文件；原生 GPS 不可审计。
- 代价：零后端成本，但上述所有保障都靠人工/外部脚本。

## 3. 方案 B：`g4usim-session-v1`

### 3.1 传输、帧与解析器

- 进程参数：`--ui --ui-session g4usim-session-v1 [--session-record-dir <dir>]`；stdin 收请求帧，stdout 发响应/事件帧；每条一行 UTF-8 JSON；帧首固定前缀 `[G4USimSession] `（仿 `RunProgress` 的 `[G4USimProgress] `）。日志/进度仍可占据 stdout 其它行：**帧完整性契约** = 前缀行是一条完整 JSON；不承诺任意人类日志不插帧，不要求调用方把全部 stdout 当纯 JSON（GUI reader 按前缀过滤，已由 `RunProgress` 模式验证）。
- 写线程：所有协议帧由单一 `SessionWriter`（互斥锁）整行写出并 flush；`RunProgress::Emit` 等现有帧保持原样（它们已是原子行）。
- 解析器：**零依赖最小 JSON 解析器**（仓库现无 JSON 库；不新增第三方依赖），约 200 行：只接受 JSON object 根；键必须是 ASCII 且属于固定 schema 集合；字符串支持 `\" \\ \/ \n \t \r` 转义，其余 `\uXXXX` 拒绝（本协议不需要）；数字必须有限（拒绝 NaN/Inf/溢出）；**重复键**→`protocol.duplicate_key`；单帧上限 64 KiB；对象后多余字节→`protocol.trailing_data`；未知字段→`protocol.unknown_field`（除 `_` 前缀扩展字段，首版无）。帧解析错误是**致命协议错误**：写一条 `error{code,terminal:true}`（能写则写）后关闭会话，退出码 2；损坏帧不得静默跳过（避免请求-响应错位）。
- 写入侧同样由解析器的 writer 生成（字符串转义一致），避免手写拼接。
- 关闭：stdin 读取使用平台有界等待（Windows：`PeekNamedPipe`/`WaitForSingleObject` 于 stdin handle，250 ms 轮询；POSIX：`poll` 250 ms），不阻塞在不可中断 read；`shutdown` 后读取线程在 2 s 内 join，超时记录 `reader_join_timeout` 并以退出码 4 结束进程，**不 detach**。
- 已考虑但首版不采用「可靠日志重定向」（把 `G4cout` 全改到 stderr/文件，使 stdout 成为纯 JSON 通道）：它改变 csh/batch 既有日志行为并影响既有测试，且 `RunProgress` 已在 stdout 写帧；首版沿用可识别前缀 + 行帧，GUI reader 按前缀过滤。

### 3.2 握手与能力

请求：

```json
{"frame":"request","id":1,"request_id":"r-6f9d","op":"hello","protocol":"g4usim-session-v1"}
```

响应：

```json
{"frame":"response","id":1,"request_id":"r-6f9d","status":"accepted",
 "result":{"session_id":"s-20261104T1230-4f2a","protocol":"g4usim-session-v1",
  "state":"Idle","state_revision":7,
  "build":{"source_fingerprint":"9e40e889…","build_git_commit":"625cfee2…","geant4_version_number":1132,"multithreaded":true,"process_threads":1},
  "limits":{"frame_bytes":65536,"max_events_per_run":100000,"queued_requests":8,"cancel":"unsupported"},
  "evidence_levels":["E0","E1","E2","E3"]}}
```

- 版本不匹配：`status:"rejected"`，`error.code:"protocol.version_unsupported"`，`terminal:true`，退出码 3。
- capability 扩展：`include/Core/BackendCapabilities.hh` 的 `G4UniversalSimCapabilities` v1 增加 `"session":{"protocol":"g4usim-session-v1","cancel":"unsupported","record_dir":true}`；旧 GUI 忽略未知键。旧后端无 `session` 键 → GUI 判定不支持，走方案 A/手动流程，不伪造会话资格。
- 每请求必须带 `id`（客户端单调递增）与 `request_id`（UUID v4 或等长随机）；两者都回显。

### 3.3 状态机与请求处理

状态：`Starting`（握手前）→ `Idle` ⇄ `Running` → `Cancelling`（仅 cancel 生效时）→ `ShuttingDown` → `Closed`。状态与 `state_revision` 是会话事务计数（后端配置代次），不是 Git SHA，也**不**等于 GUI `EditSession.revision`。

| 操作 | Idle | Running | Cancelling | 备注 |
|---|---|---|---|---|
| `state`/`ping` | 允许 | 允许（reader 按快照应答） | 允许 | 不调用 Geant4 |
| `set_source`/`reset_source` | 允许（白名单+revision 校验） | **拒绝** `session.busy`，不排队 | 拒绝 | 运行中不写入下一轮 |
| `run` | 允许 | 拒绝 `session.busy` | 拒绝 | 同 id 去重见 §3.4 |
| `cancel` | 拒绝 `run.not_running` | 允许（唯一入队控制） | 重复 ack | 见 §3.8 |
| `shutdown` | 允许 | 仅 `--allow-shutdown-during-run`（首版关闭，运行中拒绝 `session.busy`） | 同上 | 关闭前写 `session_finished` |

- 主线程：解析完 hello 后进入请求循环；Idle 时阻塞在队列条件；收到 `run` 调 `beamOn(events)` 阻塞至 run 完成（MT 主线程同样阻塞在 `G4MTRunManager::BeamOn`）。
- reader 线程：只读 stdin、解析、按**不可变协议快照**（原子 state/revision/run_id）拒绝或入队；绝不调用 Geant4、绝不写 Geant4 状态。
- 每个请求由主线程串行执行；延迟执行（排队）只允许 `cancel`；主线程处理排队的 cancel 时重验 `run_id`/`state_revision`/当前 run 是否仍活动，不符则拒绝（`run.not_running`/`state.stale_revision`）。
- 请求顺序：FIFO；主线程在 run 结束后先处理积压的 cancel/shutdown，再回到命令队列。

`get_state` 返回当前配置与下一轮草稿（都只到各自证据层）：

```json
{"frame":"request","id":5,"request_id":"r-2c1d","op":"get_state"}
{"frame":"response","id":5,"request_id":"r-2c1d","status":"accepted",
 "state":"Idle","state_revision":8,"last_run_id":1,
 "current":{"source.particle":{"value":"proton","application_status":"applied","evidence_level":"E2","applied_revision":8},
            "source.energy":{"value":"200 MeV","application_status":"applied","evidence_level":"E2","applied_revision":8}},
 "draft":{"source.energy":{"value":"100 MeV","revision":9,"status":"pending_apply"}},
 "draft_revision_at_apply":8}
```

### 3.4 请求身份、去重、过期与终态归属（C2 修正）

- `id`：客户端单会话单调递增整数；`request_id`：客户端唯一字符串。两者都用于幂等。
- 去重缓存：最近 `256` 个完成请求，LRU；条目含 `{id, request_id, body_sha256, response_frame, completed_at, revision}`。**判定顺序**：
  1. 若 `id` 在缓存：body_sha256 相同 → 返回缓存响应帧并加 `"deduplicated":true`，**不**再次执行（在 busy/revision 判断之前）；body 不同 → `status:"rejected"`、`error.code:"request.id_conflict"`、`terminal:false`，不执行。
  2. 若 `id` 不在缓存但 `id <= highest_completed_id` 且已被淘汰 → `status:"rejected"`、`error.code:"request.expired"`、`terminal:false`，不执行；不得按新请求重放。
  3. 其余按 schema 校验 → revision 校验 → busy 校验 → 执行。
- 响应丢失重试：同 id+同 body 返回缓存响应（含原 `run` 的 `accepted` 与 `run_finished` 是否已发生的状态由 `state` 请求确认，不制造新 run）。
- 终态归属：`run_finished` 只属于 `run` 请求（`run_request_id`），且每 run 恰好一条；`cancel` 只有自己的 `accepted` 回应与 `cancel_request_id`；`run_finished` 可带 `cancel_request_id` 说明取消来源，但**不**把终态改挂 cancel 请求，也不重复发两份终态。`cancel` 请求的 `accepted` 不代表 run 已停止（仅表示请求已记录），停止结果只由 `run_finished` 宣告。
- 过期场景样例：`id=20` 已被淘汰、服务器已见 `id=60` → 返回 `request.expired`。
- 冲突样例：

```json
{"frame":"response","id":43,"request_id":"r-99aa","status":"rejected",
 "error":{"code":"request.id_conflict","terminal":false,
  "message":"id 43 already used with a different request body"}}
```

### 3.5 配置接受、内核应用与证据分层（C3 修正）

四层证据（现有 EffectiveConfig 词汇，不改枚举）：

- `E0`：协议请求（requested，客户端意图）——不是后端事实。
- `E1`：Manager 接受（manager 缓存/`SourceManager` 已更新，`manager_accepted:true`）——`application_status` 只能为 `unknown`/`not_applied`，不得为 `applied`。
- `E2`：内核消费（同一 run 的逐 run 收据证明内核对象按该字段运行：如相空间入口记录、每轮事件统计/产物；消费者具体到本任务）——`application_status:"applied"` 只能由 E2 绑定给出。
- `E3`：物理验证（基准/独立物理证据，本协议不产生；引用既有 benchmarks）。

字段级四元组沿用 2C 合同：`requested` / `resolved` / `application_status`（`not_applied|applied|unknown|failed`）/ `applied_revision`，并带 `evidence_level`、`reason`、`manager_accepted`、`kernel_applied`（true/false/unknown，禁止合并成「已应用」）。`EditSession.revision`（GUI 草稿）与 `state_revision`（后端配置代次）只做映射记录（`draft_revision_at_apply`），不直接等号。

`set_source` 响应样例（只到 E1）：

```json
{"frame":"response","id":42,"request_id":"r-8b1c","status":"accepted",
 "state_revision":8,"applied_revision":8,
 "changes":[{"field":"source.energy","requested":"200 MeV","resolved":"200 MeV",
   "application_status":"unknown","manager_accepted":true,"kernel_applied":"unknown",
   "evidence_level":"E1","applied_revision":8,
   "reason":"manager state updated; kernel adoption is proven only by a run receipt"}]}
```

- 若同字段在下一轮 run 的收据中被消费者观测到，`run_finished` 内的 `applied_fields` 追加 E2 记录（`application_status:"applied"`、`evidence_level:"E2"`、`run_id`）。
- 运行中写入的拒绝样例：

```json
{"frame":"response","id":44,"request_id":"r-a001","status":"rejected",
 "error":{"code":"session.busy","terminal":false,
  "message":"state is Running; set_source is rejected, not queued for the next round"}}
```
- 无法观测（如仅 Manager 有值、无消费者）→ 保持 `unknown`，不得猜测 applied。
- 内部执行异常：若异常发生在可变状态更新之后且无法证明已恢复 → 终止会话（退出码 3），保留 `unknown`/`failed`，**不**返回可继续的 `rejected`。
- 拒绝语义：`status:"rejected"` + `error{code,terminal}`；`terminal:false` 表示会话可继续（如 revision 冲突、busy、白名单外字段）；`terminal:true` 表示会话必须关闭（协议/内部错误）。

### 3.6 首版有效编辑白名单

依据首轮实测与既有测试（`scripts/test_interactive_commands.py`、`scripts/test_command_state_gating.py`、`scripts/test_random_command_semantics.py`）：

| 字段 | 单源 | 多源/延迟 | PreInit | Idle | Running | 依据 |
|---|---|---|---|---|---|---|
| particle | 允许 | 拒绝（单源命令） | 允许（缓存回放实测） | 允许 | 拒绝 | 首轮；`SourceManager.cc:316-320` |
| energy | 允许 | 拒绝 | 允许（300 MeV 回放实测） | 允许 | 拒绝 | 首轮 |
| point/position | 允许 | 拒绝 | 待证 | 允许（x=5.000 实测） | 拒绝 | 首轮；PreInit 未单独实测 |
| direction | 允许 | 拒绝 | 待证 | 允许（u=0.1 实测） | 拒绝 | 首轮 |
| planeBeam/shape | 允许 | 拒绝 | 待证 | 允许（radius=5 实测） | 拒绝 | 首轮 |
| isotropic/preset/reset | 待证 | 拒绝 | 待证 | 待证 | 拒绝 | 未进入首版可编辑白名单 |
| 运行名（后端 `run_name`） | 仅 INI/CLI | — | 仅 INI/CLI | 不允许 | 不允许 | 首版每进程固定；`run_label` 只是会话元数据 |
| 线程数/输出根/格式/后缀 | 仅 INI/CLI | — | 仅进程启动 | 拒绝 | 拒绝 | 现有 PreInit 守卫；setDir 本轮实测拒绝 |
| seed/geometry/physics/scoring/biasing | 仅 INI/CLI | — | 仅进程启动 | 拒绝 | 拒绝 | 既有测试 |
| 原生 GPS（`/gps/*`） | 允许但不可审计 | — | — | 允许 | 拒绝 | 首轮反例：内核生效、Manager/摘要不更新 |

约束：

- 首版**每进程固定线程数与输出根**；运行名不可在会话中改；`run_label` 仅用于记录/UI，不传入后端 `run_name`。
- 多源（`[source.<name>]`）、`phase_space_file`、延迟 ion/confine 不在首版可编辑范围；需新进程。
- 白名单字段在 PreInit/Idle 的允许状态必须由实施时的真实测试确认；本表「待证」不得自动升级为可编辑。
- 原生 GPS 的未知由 `native_gps_unobserved` 明确回报，不得伪造 GPS 更新。

**安全调用入口**：`SessionServer` 在派发前完成 schema、白名单、状态（PreInit/Idle）、`state_revision`、单源、值域（单位/有限性/方向非零）校验，绝不把未校验字符串交给 setter；校验失败一律 `rejected{terminal:false}`，不构造 Geant4 对象、不改变 Manager 状态。仍可能触发的 Fatal（如内核态变化）与 csh/batch 一样按 `G4Exception` 终止，**不使用外围 try/catch 假装可恢复**；物理类不可恢复错误保持终止。

### 3.7 run 请求、逐轮收据与产物绑定（C4 修正）

请求（不含线程/输出根/后端运行名）：

```json
{"frame":"request","id":43,"request_id":"r-99aa","op":"run","events":10,"run_label":"round-b"}
```

`run_started` 事件：

```json
{"frame":"event","event":"run_started","run_id":1,"run_request_id":"r-99aa","run_label":"round-b","planned_events":10}
```

`run_finished`（在 worker/master 输出关闭、产物存在性检查之后，由 master `RunAction::EndOfRunAction` 尾部发出——现有 `RunProgress::End` 附近，`src/Actions/RunAction.cc:255-266`）：

```json
{"frame":"event","event":"run_finished","run_id":1,"run_request_id":"r-99aa",
 "state":"completed","planned_events":10,"completed_events":10,"aborted_events":0,
 "cancel_request_id":null,
 "artifacts":[{"path":"scorer_statistics_r1.csv","bytes":512,"scope":"run"},
              {"path":"event_edep_t0_r1.csv","bytes":2048,"scope":"run"}],
 "records":{"dir":"session-records/s-…/run-1/"},
 "applied_fields":[{"field":"source.energy","resolved":"200 MeV",
   "application_status":"applied","evidence_level":"E2","consumer":"event_edep_t0_r1.csv"}]}
```

- 命名沿用 `docs/输出数据契约.md:46`：首个 run 为 `*_tN.csv`/`scorer_statistics.csv`，后续 run（Geant4 run ID `R`）为 `*_tN_rR.csv`/`scorer_statistics_rR.csv`；产物清单按本轮 run ID 与命名规则枚举并核对存在/大小，**不**使用 `run_summary.txt`/`run_metadata.json`（二者只在最终化写，`src/Core/SimulationManager.cc:751-795`）。
- 哈希/证据复核由独立证据任务在会话收据目录写 `run-evidence.json`（重算 sha256），运行时不阻塞算大文件哈希；收据只绑定路径/大小，复核执行时间另记。
- `--session-record-dir`：显式参数，必须位于输出根之外；缺省不猜，若未提供则 `run_finished` 只含 artifacts，写 `records.dir: null` 与 `records.reason:"record_dir_not_configured"`；GUI 默认传 `<output_root>/../session-records/`。该目录不进入 F1 `generated_files`，不改变现有输出合同。
- run 请求的 `events` 上限见 limits（默认 100000）；超出 `error.code:"run.events_out_of_range"`（rejected，不执行）；`events<=0` 拒绝。

### 3.8 取消、运行中控制与 MT 现实（C1/C5 修正）

- 事实：`main.cc:567-574` MT 构建无条件 `G4MTRunManager` + `SetNumberOfThreads`；`--threads 1` 为 1 worker，不是串行 `G4RunManager`。`G4MTRunManager::AbortRun` 覆写声明在 `G4MTRunManager.hh:184`；`G4RunManager::AbortRun(softAbort)` 语义头注释在 `G4RunManager.hh:190-199`（soft=true 当前事件处理后中止事件循环）；worker 的 `G4WorkerRunManager` 继承 `G4RunManager`（`G4WorkerRunManager.hh:48`），本仓库既有的错误中止路径在 action 内调用它（`src/Actions/RunAction.cc:78,139,144`、`src/Hits/SensitiveDetector.cc:158`、`src/Scoring/ScoringManager.cc:500,527,560,570,599`、`src/Biasing/BiasingXS.cc:314`）。这些是**错误中止**的既有先例，不等于用户取消在 MT 下已验证。
- v1 设计：`cancel` 请求入队；主线程在 run 活动时设置原子 `cancel_requested(run_id)`（不调用 Geant4），worker 在 `EventAction::EndOfEventAction`（`src/Actions/EventAction.cc:41-55`）检查该标志并调用 `G4RunManager::GetRunManager()->AbortRun(true)`（与既有错误中止同一 API 路径）。主线程在 `BeamOn` 返回后写 `run_finished(state:"cancelled", cancel_request_id)`。重启 run 前清标志。
- **状态声明**：首版 capability 写 `cancel:"unsupported"`，不宣称可用；只有通过下述实测后，才改为 `supported` 并进入验收快照：
  - 实验 C1a：Windows/Linux、`--threads 1`、200 事件，运行第 ~20 事件后 cancel；期望 run 在 ≤1 个事件边界内停止、`run_finished.completed_events < planned`、state=cancelled、会话回 Idle、无崩溃、收据含已完成事件数。
  - 实验 C1b：`--threads 4` 重复；期望 ≤4 个事件边界（每 worker 一个）内停止，`completed_events ≤ planned`，summary 计数一致。
  - 实验 C1c：Idle 时 cancel 被拒绝 `run.not_running`；重复 cancel 返回同 `cancel_request_id` 的幂等 ack。
  - 若任一失败：cancel 保持 unsupported，GUI 取消仍走显式 `terminate/kill` 并要求用户确认数据丢失；不得偷偷用串行 run manager 实现取消后再以 MT 批处理路径作逐位比较。
- 不完整 run 记账：cancel 生效的 run 仍写一条 `run_finished(state:"cancelled")`，`completed_events` 为已完整结束的事件数，`aborted_events` 记录 `event->IsAborted()` 计数（`EventAction::EndOfEventAction` 已把该值传给 `RunProgress`）；产物只列已关闭文件，未关闭项写 `artifacts_not_closed`；既有 `run_summary.txt` 仍由最终化按现状写一次，`status` 按既有失败登记，协议不伪造 completed 计数。
- 运行中 `set/run/shutdown` 一律拒绝 `session.busy`，不排队到下一轮（防止「静默延后执行」）；reader 只按快照拒绝；主线程处理积压 cancel 时重验 run 与 revision。

### 3.9 关闭、断线、重放与比较器（C6 修正）

- EOF/断线：若在 `Idle`，视为客户端关闭：写 `session_finished{reason:"client_eof"}`，退出码 0。若在 `Running`，视为失联：置 `client_disconnected`，按 unsupported cancel 路径处理（当前退回进程 hard abort + 退出码 4），保留已写产物与 `run_interrupted` 记录；**不**把 stdin EOF 解释为可重新接入同一进程。重连只能新建 session（新 session_id），通过 `state` 读回真实状态，不伪造旧会话。只读历史恢复：GUI 可以只读 `--session-record-dir` 的收据/日志重建历史面板，这不等于重连活进程，也不得把历史记录标成新会话证据。
- 重复 `run` 请求：同 id+同 body 返回缓存响应，绝不启动第二个 run；不同 body → `request.id_conflict`。若 id 已淘汰、run 可能已完成 → `request.expired` 并用 `state` 查询真实状态。
- 正常关闭：`shutdown` → `session_finished` → 停 reader（有界 join）→ 关输出 → 退出码 0。收尾失败写 `session_finalize_failed`，退出码 3。
- 重放（设计目标，非本阶段实施）：
  - 固定：构建指纹、Geant4 数据集、`[run] seed`、线程数（首版 1，MT 另测）、事件数、命令/事件顺序；A/B/A 在**新进程**各起会话（或同会话多 run），比较 run A1 与 A2 的产物。
  - 字节比较优先；失败时用显式比较器：按 `docs/输出数据契约.md` 的每类 CSV 表头做列对齐，**只排除显式时间/性能列**（`scorer_statistics*.csv` 中的 `fom_per_s`、`run_wall_time_s`；如未来新增同类列，必须在比较器配置文件中先声明并给出理由），其余列（含所有物理量、计数、sum/sum_sq）按文本严格相等；行按数据键（`runID,eventID,trackID,…`）排序后逐行比较；直方图按 bin 排序逐行比较。
  - 主审实测（seed 1904、1 worker、A/B/A）：24 CSV 中 21 个原字节相同；3 个 `scorer_statistics` 仅上述两列不同，其余全等。该结果**不是**产品缺陷，也**不是**最终重放验收：引擎初态未捕获、MT 未测。MT 必须另行实测并列差异（事件键能精确比较的聚合统计不得以「无事件键」豁免）。
  - 已知非确定来源：随机数引擎状态、线程调度、计时字段；不允许用容差替代逐位目标。
- 有界性：reader join ≤2 s，shutdown 总时长 ≤5 s；超时记录并强制退出码 4，但不 detach。

### 3.10 旧后端、版本协商与退出码

- 后端 capability 无 `session` → GUI 判 `session_protocol: unsupported`，只能走方案 A/手动，不显示 v1 面板的「可取消/可重放」能力。
- 协议版本：请求 `protocol` 与服务器支持列表求交；无交集 → `protocol.version_unsupported`（terminal，退出码 3）。
- 退出码：0 正常关闭；2 协议致命（帧/解析）；3 内部/终态写入失败；4 失联/强制中止；5 不支持的操作集（初始化时）。
- 兼容：旧 GUI 忽略新 capability 键；新 GUI 对旧后端降级显示「未知/不支持」，不伪造。

### 3.11 代码所有者与线程

| 组件 | 位置（现状） | 首版职责 | 线程 |
|---|---|---|---|
| 入口/参数 | `main.cc:364-380`（`--output/--threads` 解析；用法文本 `main.cc:257-268`）、`main.cc:695/738/744`（Configure/Initialize/CreateRunManager） | 新增 `--ui-session g4usim-session-v1`、`--session-record-dir`；创建 `SessionServer` | main |
| run manager | `main.cc:567-574` `CreateRunManager()` → `G4MTRunManager`；`main.cc:744` | 事实来源；不在会话中替换 run manager | main |
| 会话服务器 | 新增 `include/Core/SessionServer.hh`、`src/Core/SessionServer.cc`、`include/Core/SessionJson.hh`、`src/Core/SessionJson.cc` | 解析/状态机/白名单/收据/帧写入/reader 生命周期 | reader + main（writer 锁） |
| 源配置 | `src/Source/SourceManager.cc`、`SourceMessenger.cc:100-108,160-235` | 会话 set 调用与现有 csh 相同 setter；派发前做白名单/类型校验，避免 FatalException；无法避免的 Fatal 仍按旧路径终止 | main |
| 进度/取消 | `src/Actions/EventAction.cc:41-55`、`src/Actions/RunAction.cc:255-266`、`src/Actions/RunProgress.cc:38-72` | EventAction 检查 cancel 原子；RunAction 尾发 run_finished；RunProgress 原帧保留 | worker/main |
| 产物 | `include/Output/OutputManager.hh:112/122`、`src/Output/OutputManager.cc:662` | 新增「按 run ID 枚举本轮产物」查询（不改 F1 登记规则） | main |
| GUI 客户端 | `gui/g4usim_gui/core/runner.py:76` 起（`--output`）、`experiment_workflow.py:349/406/797/800/923/1009/1022` | 新 `session_client.py`；ExperimentWorkflow 适配会话；取消状态机 | GUI 主线程 + reader |
| 草稿/代次 | `gui/g4usim_gui/core/edit_transactions.py:50` | `EditSession.revision` 与 `state_revision` 映射记录 | GUI 主线程 |
| 下一轮面板 | 新增 `gui/g4usim_gui/widgets/session_panel.py`（或扩展现有运行页） | 五区展示（§3.12） | GUI 主线程 |

- 线程纪律：reader 不解析 Geant4 状态、不调用任何 Geant4 API；主线程独占 run manager、配置 setter、beamOn；worker 只在 EventAction/RunAction 内触碰线程本地 Geant4 对象；协议 writer 由互斥锁串行化。`RunProgress::Emit` 现有实现也在持锁下 `fwrite`，与本协议 writer 互不共享锁（允许交错，前缀可辨识）。
- 运行后总结/摘要仍由 `SimulationManager::FinalizeRunSummary`（`src/Core/SimulationManager.cc:745-815`）在最终化写；协议不改其语义，只在其前发 `session_finished`。

### 3.12 下一轮面板数据契约（五区）

1. **本轮**：`run_id`、state、planned/completed/aborted、速率/ETA（复用 `RunProgress` 帧）、`run_label`。
2. **逐轮收据**：每 run 的 artifacts 列表 + 证据复核状态 + `applied_fields`（E2/E3 分离）+ 记录目录打开入口。
3. **可编辑草稿**：白名单字段、当前值/请求值、`application_status`、`manager_accepted`、`kernel_applied`、`evidence_level`、reason；待证/不支持字段禁用并解释；原生 GPS 单独标灰「不可审计」。
4. **会话与协议**：连接状态（Idle/Running/Cancelling/ShuttingDown/Disconnected）、capability（含 cancel 是否 supported）、record dir、重连/新会话按钮；旧后端显示「不支持」。
5. **问题与证据**：警告/unknown/failed、拒绝原因（request.id_conflict/expired/busy/白名单外）、失联与不完整 run 的保留清单；不得把 E1 显示成 E2。

### 3.13 代价与维护

- 方案 A：零后端改动；无逐轮收据、无取消、无重放；GUI 只能靠 csh 解析，错误不可恢复。维护成本低。
- 方案 B：新增约 1,200–1,600 行 C++（服务器 700–900、JSON 解析 200、capability/产物/取消钩子/头文件 300），GUI 客户端与面板约 600–900 行，新增 3–4 个专项测试文件；无第三方依赖；风险集中在 MT 取消语义与产物绑定（见 §6）。收益：逐轮可重放收据、机器可校验应用层级、明确拒绝而非会话终止、可取消（实测后）、可重连新会话。
- 旧 csh 与 batch 路径不删除（兼容与诊断），但在 capability 中如实声明其限制。

## 4. 允许改动的文件与提交节点

**S1（后端会话核心，一次提交）**：`main.cc`、`include/Core/SessionServer.hh`、`src/Core/SessionServer.cc`、`include/Core/SessionJson.hh`、`src/Core/SessionJson.cc`、`include/Core/BackendCapabilities.hh`、`include/Output/OutputManager.hh`、`src/Output/OutputManager.cc`、`src/Actions/EventAction.cc`、`src/Actions/RunAction.cc`、`CMakeLists.txt`（+必要时 `src/Core/SimulationManager.cc` 仅在需要暴露 run 事件时；不改其语义）。

**S2（GUI 客户端与面板，一次提交）**：`gui/g4usim_gui/core/session_client.py`（新增）、`gui/g4usim_gui/core/experiment_workflow.py`、`gui/g4usim_gui/core/runner.py`、`gui/g4usim_gui/widgets/session_panel.py`（新增）、`gui/g4usim_gui/window/shell.py`、`gui/g4usim_gui/core/i18n.py`、`gui/AGENTS.md`。

**S3（测试、证据与文档，一次提交）**：`scripts/test_session_protocol.py`（新增）、`scripts/test_session_cancel_mt.py`（新增）、`scripts/run_m0_tests.py`（注册）、`gui/smoke_tests/smoke_session_panel.py`（新增）、`docs/输出数据契约.md`（仅记录 `--session-record-dir` 与收据目录不在 generated_files 的说明，不改既有规则）、`docs/验证/…`（证据）、`STATUS.md`/`ROADMAP.md`/`CHANGELOG.md`/`AGENTS.md`/`docs/agent-history.md`。

不让 agent 改：`src/Source/*`（只读，除白名单校验外不改行为）、`src/Scoring/*`、`src/Geometry/*`、`src/Physics/*`、现有测试、CI workflow、首轮实验原件。

## 5. 验收正反例（16 类，与既有条目对应）

1. 真实三轮 A/B/A（同进程、单源、10–20 事件）：run 编号、事件数、产物、E2 收据齐全。
2. 真实拒绝反例：多源 set 被拒（不执行、会话可继续），并与 csh 致命中止对照。
3. 白名单外字段/待证字段拒绝，且不写入任何后端状态。
4. 运行中 set/run/shutdown 被拒 `session.busy`，不延后执行。
5. 运行期 cancel（1 worker / 4 workers 两实验）：见 §3.8 C1a/C1b/C1c；未通过则 capability 保持 unsupported（负面验收）。
6. 请求去重：同 id 同 body 返回缓存响应不重启 run；同 id 不同 body 冲突；过期 id 拒绝且不执行。
7. 终态归属：run_finished 只属 run 请求；cancel ack 不等于终态；不重复终态。
8. 应用层级：E1 响应不得出现 applied；E2 收据只能来自本轮消费者观测；unknown 保持 unknown。
9. 产物绑定：`_tN[_rR]` 命名、run ID 对应、存在性/大小校验；不引用最终化产物。
10. 输出根/线程固定：运行期改 setDir/线程被拒；`run_label` 不写后端 `run_name`。
11. 失联：Running 时 EOF → 有界中断、收据 `run_interrupted`、退出码 4；Idle EOF 退出码 0。
12. 关闭：shutdown 有界 join、session_finished、退出码 0；reader join 超时 → 退出码 4。
13. 重放：固定 seed A/B/A 字节比较保留失败记录；显式时间列排除后 24/24 物理列严格相等；比较器不删物理列。
14. MT 重放：4 worker 实测列差异并记录；不能豁免可精确比较的聚合统计。
15. 旧后端/能力协商：无 session 能力 → 降级、不伪造；版本不匹配 → 退出码 3。
16. 崩溃/异常：FatalException 路径与旧 csh 一致；内部异常后不返回可继续的 rejected；不完整 run 记账。

## 6. 主要风险

1. MT 取消线程安全（最高）：worker `AbortRun` 与 master 协调语义未实测；C1a/C1b 未过则 cancel 保持 unsupported。
2. 引擎初态未捕获：当前 A/B/A 只证明本实验内可重复，不证明跨进程最终重放；需要在 S3 先做初态捕获实验，未完成前不宣称逐位重放。
3. 产物绑定窗口：worker 关闭与 master 收据之间存在短暂窗口；收据只列已关闭文件，未关闭/失败文件明确记录 `not_closed`，不冒充证据。
4. stdout 插帧：不保证人类日志不插帧；损坏帧按协议错误终止可能导致误杀（可接受，优于静默错位）。
5. 白名单待证字段：首版禁入，防止把 E0 当 E2。
6. 记录目录权限/磁盘：写失败 → `records.dir:null` + 警告，run 结果不受影响。
7. 请求 id 域：客户端重启后 id 从 0 重新计数，会话级 id 必须与 session_id 绑定，跨会话不复用缓存。

## 7. 范围外建议（不实施）

- 把 `device`/scoring 动态编辑纳入协议；协议级二进制帧（长度前缀）以提高吞吐；会话内多项目切换；把 phase-space 记录扩展为可配置顶点记录；rollback/undo 事务；把 csh 的 `print` 解析成结构化收据。

## 8. 协议选择状态与实施入口

**已决（2026-11-04）**：用户选择 B（`docs/collab/decisions/20261104-f2-protocol-choice.md`）——采用版本化会话接口并保留 csh/batch；本文件定稿供实施。A 保留为兼容/回退，无逐轮收据/取消/重放能力。实施按 §4 的三个内部提交节点：S1 后端会话核心与 capability（含三轮收据、E0–E3 分层、安全入口）→ S2 GUI 会话客户端与下一轮面板 → S3 测试、证据与文档；取消在 §3.8 的 MT 单/多 worker 实验通过前保持 `unsupported`，通过后才升级 capability 与验收快照。正式矩阵、证据冻结与阶段验收仍按另行安排执行；作者完成实现不构成 F2 阶段验收。
