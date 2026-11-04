# F2 受控会话基线：真实三轮、拒绝反例、白名单与协议提案

日期：2026-11-04
作者：DeepSeek（F2 首交付 `F2-PROTOCOL-EVIDENCE-20261104`）
状态：**作者交付，待主审独立审查**。作者完成不等于 F2 阶段验收。

---

## 1. 范围与身份

| 项 | 值 |
| --- | --- |
| 仓库 HEAD（实验开始时） | `9c268fb08d4b82b536ae024dc6a7883a8d709b5f`（`docs: record J3 integration and active F2 dispatch [skip ci]`；仅文档，无产品变化） |
| 仓库 HEAD（收尾时） | `5ee240fc5912e7e515ee07be7abbb14bcfa00940`（`docs: refine continuous supervision lifecycle and checkpoints [skip ci]`）；`9c268fb0..5ee240fc` 仅 3 个文档文件（`docs/collab/decisions/20261104-f2-automation-prompt.md` 等），产品源码与测试未变 |
| 产品基线 | `92134da0`（J3 签收的产品提交；HEAD 之前仅 docs 提交 `8631af58`、`9c268fb0`） |
| 后端可执行文件 | `build_vs2026/Release/G4UniversalSim.exe`，`sha256 18d58fab815b91e96c6c4b2c94704518d42885f163b54803072164a8a4f9c837`，2,466,304 B |
| 后端自报身份 | `source_fingerprint=9e40e889d49a44250cbe95077bc81d03fe36cb7fd6726df2ce2db9cb34334f0a`，`build_git_commit=625cfee22ab612b3e3829e7b6149c56036943d50` |
| Geant4 数据 | `G4USIM_GEANT4_DATA=D:/ProgramFiles/Geant4/share/Geant4/data` |
| 平台 | Windows 10/11 本机（`DESKTOP-PA6LDOC`），单线程（`[run]/threads = 1`） |
| 实验驱动 | `out/collab/f2-session-baseline-20261104/f2_session.py`，`sha256 3407061bdc4fd42bdb944fcfa0e08f69fa5d102a718d710dd4a33554541ed8ba` |
| 配置 | `config/main.ini` `sha256 e8f6e473a2f2297bbc1784975970a4664530fab20f2ebeede4dc103d8d634f2e`；`config/geometry.ini` `sha256 88311838a07e31a33c638c748bfb2a402b883ceb07d692f2a0794ca435f1ed30`；`config/main_multisource.ini` `sha256 c80d9fb0967a2de5f3c0ca8324241fc6d4914e7be10be5f2890dadc988533106` |

本轮只写 `out/collab/f2-session-baseline-20261104/**` 与本文件；未修改产品、既有测试、CI，未提交 Git，未安装依赖。工作区中被跟踪的唯一改动是用户自己的 `docs/collab/decisions/20261104-f2-automation-prompt.md`（未触碰）。

## 2. 方法：为什么这些数字是“内核实际消费”的记录

- 全部会话走既有审计入口：`G4UniversalSim.exe --ui --ui-session csh --config <ini> --output <dir>`，命令经 stdin 逐行送入，同一进程内 `A → B → A`。
- 每个事件的主顶点证据取自 `[phase_space] volume=Target_PV` 的 `phase_space_t*.csv`：`SteppingAction` 在步状态 `fGeomBoundary` 且 post-step 体积为目标体时写一行（`src/Actions/SteppingAction.cc`、`src/Scoring/PhaseSpace.cc`）。行内容来自该步的粒子/位置/方向/动能，即**内核在该次 run 实际使用的源参数**，不是 Manager 缓存。
- 世界为 `G4_Galactic` 真空，源点到目标体入射面 40 mm，初级粒子在此段几乎无能量损失，因此边界行能量可直接对照命令设定值（观测值精确到 `1e-3 MeV`）。
- `run_summary.txt` 的 `run_count`、`run_<i>_planned_events`、`run_<i>_completed_events`、`status`、`effective_source_*` 与 `phase_space` 按 run 索引一一对应（首轮 `_t0.csv`，后续 `_r1`、`_r2`）。
- 原始 stdin/stdout/stderr、退出码、目录清单与逐轮摘要都在 `evidence/<case>/`；汇总由 `analyze.py` 从原始 CSV/JSON 重新生成，见 `evidence/results-summary.md`、`evidence/results.json`。

## 3. 三轮 A/B/A（单源、单线程、同一进程）

命令序列（`evidence/three-round/stdin.txt`）：

```
/run/initialize
/AIHL/source/print
/run/beamOn 10
/AIHL/source/energy 200 MeV
/AIHL/source/print
/run/beamOn 10
/AIHL/source/energy 100 MeV
/AIHL/source/print
/run/beamOn 10
exit
```

| run | planned | completed | phase_space 行 | 粒子 | 内核消费能量 (MeV) | Manager `/AIHL/source/print` |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 10 | 10 | 10 | proton | 100.000 | `monoEnergy=100`（stdout:846） |
| 1 | 10 | 10 | 10 | proton | 200.000 | `monoEnergy=200`（stdout:851） |
| 2 | 10 | 10 | 10 | proton | 100.000 | `monoEnergy=100`（stdout:856） |

- 会话 `exit_code=0`，`status=completed`，`run_count=3`，`actual_completed_event_count=30`；无 sentinel。
- 第三轮回到 100 MeV，但 RNG 状态已前进，本证据不要求第三轮与第一轮逐位一致（事件数 10，相位空间顶点数值一致是几何确定性，不是 RNG 回放）。
- 结论：受控 csh 在单源、Idle 状态下可以做到同一进程三轮且内核确实消费新能量；Manager 的 `print` 与内核一致（受管路径）。**但该“一致”只对受管 `/AIHL/source/*` 成立**，见 §6 反例。

## 4. 单字段设置（同一进程，逐字段真实消费）

| 轮 | 命令 | 内核消费证据（phase_space） | 结论 |
| --- | --- | --- | --- |
| 0 | `/AIHL/source/particle e-` | 粒子 `e-`，能量 100 MeV（原 INI 能量） | 粒子已换，能量未动 |
| 1 | `/AIHL/source/energy 50 MeV` | `e-`，能量 50.000 MeV | 能量生效 |
| 2 | `/AIHL/source/point 5 0 -50 mm` | 边界 `x=5.000 mm` | 位置生效 |
| 3 | `/AIHL/source/direction 0.1 0 0.995` | `u=0.100`，边界 `x=9.020 mm`（5+0.1×40） | 方向生效 |
| 4 | `/AIHL/source/planeBeam radius=5 mm z=-50 mm direction=+z` | 粒子 `e-`，能量 50 MeV，边界 `x∈[-3.089, 3.902]`（落在半径 5 mm 内） | 圆形平面源生效 |

`exit_code=0`，`run_count=5`，`status=completed`，`actual_completed_event_count=50`。第 0 轮同时说明：单字段 setter 只改该字段，这是 F2 面板需要逐字段 receipt 的直接依据。

## 5. 拒绝反例（独立进程；拒绝后不得继续）

两个反例都在拒绝命令后追加了 sentinel echo 与 `/run/beamOn`；两者都没有出现 sentinel，也没有任何 run 产物。

### 5.1 多命名源：单字段命令被拒 → 硬中止

`config/main_multisource.ini` 有两个 `[source.protons]`/`[source.electrons]`：

```
/run/initialize
/AIHL/source/energy 200 MeV
/control/echo F2_REFUSAL_SENTINEL_DID_NOT_RUN
/run/beamOn 4
exit
```

- `exit_code=3221226505`（`0xC0000409`，进程中止，`core dump` 提示），**没有 `run_summary.txt`**，无结构化失败字段。
- stderr 原文：`*** G4Exception : AIHL_SOURCE_001` / `Source command /AIHL/source/energy failed for input '200 MeV': SourceManager energy cannot target one of several [source.<name>] sources; edit the sources in the main INI or use native /gps/source/... commands.` / `*** Fatal Exception *** core dump ***`。
- 拒绝语义正确（拒绝、未执行后续），但错误通道是**进程级致命异常**，不是可解析的会话回执。原因：`SourceMessenger::ReportCommandFailure` 走 `G4Exception(..., FatalException)`（`src/Source/SourceMessenger.cc`）。

### 5.2 `/AIHL/output/setDir` 在 `/run/initialize` 后：状态门拒绝 → 干净失败

```
/run/initialize
/AIHL/output/setDir <...>/evidence/must-not-be-used
/control/echo F2_REFUSAL_SENTINEL_DID_NOT_RUN
/run/beamOn 4
exit
```

- `exit_code=1`；`status=failed`；`run_count=0`；`actual_completed_event_count=0`；`interactive_command_failure_kind=geant4_illegal_application_state`；`interactive_command_failure_message=illegal application state -- command refused; Geant4 UI status=200 for command: /AIHL/output/setDir ...`；sentinel 未出现。
- 拒绝后没有 `must-not-be-used` 目录、没有 run，说明后续命令未执行。输出目录里只有正常收尾产物（`run_summary.txt`、`run_metadata.json`、两个 `effective_config_*.json`），没有 `hits_*`/`phase_space_*`。

### 5.3 既有反例（本轮未重复全跑，仅作白名单依据）

- `/random/setSeeds` 非法值：`scripts/test_random_command_semantics.py` 断言 `exit != 0`、`status=failed`、`actual_completed_event_count=0`、`macro_seed_modified=false`、sentinel 缺失。
- 初始化后 `/AIHL/app/setSeed`、`/AIHL/detector/setSDName`、`/AIHL/detector/enableSD`：`scripts/test_command_state_gating.py` 断言 Geant4 `status=200`、batch `failed`、无 run；PreInit 时接受。
- 交互期修改几何/物理/biasing：既有合同为拒绝（`/run/reinitializeGeometry` 与 biasing 保护，见 `docs/agent-history.md` 与相关测试）。

## 6. 反例：原生 `/gps` 交错，Manager 回执与内核不一致

```
/run/initialize
/AIHL/source/print
/run/beamOn 5
/gps/ene/mono 2 MeV
/AIHL/source/print
/run/beamOn 5
exit
```

- run 0：phase_space 能量 100.000 MeV；run 1：phase_space 能量 **2.000 MeV**（内核确实换了）。
- 两次 `/AIHL/source/print` 都仍打印 `particle=proton, monoEnergy=100`（stdout:846、851）。
- 最终 `run_summary.txt` 的 `effective_source_energy_MeV=100`。
- 结论：原生 `/gps/*` 命令绕过了 SourceManager 缓存；**csh 会话无法给出“已应用值”的权威回执**。这是 F2 协议必须解决的第一类问题（协议必须审计或明确禁止原生 GPS 交错）。

## 7. 有限白名单（本轮证据；仅列首交付需要的字段）

图例：`允许`=本轮实证内核消费；`拒绝`=本轮或既有测试实证被拒且后续未执行；`待证`=未用本轮真实会话证明（不得当作允许）；`不可用`=会话模型不允许。

| 字段 / 命令 | 单源 PreInit | 单源 Idle | 事件运行中 | 多命名源 | 延迟 GPS（ion/confine/phase_space_file） | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| `/AIHL/source/particle` | 允许（preinit-cache） | 允许（fields run0） | 不可用（csh 同步阻塞） | 拒绝（硬中止） | 待证 | 本轮 §4/§5.1；`test_gps_sources.py` |
| `/AIHL/source/energy` | 允许（preinit-cache 300 MeV） | 允许（three-round 100/200/100） | 不可用 | 拒绝（硬中止） | 待证 | §3/§5.1 |
| `/AIHL/source/point` | 待证 | 允许（fields run2 x=5 mm） | 不可用 | 拒绝（同类命令，待补） | 待证 | §4 |
| `/AIHL/source/direction` | 待证 | 允许（fields run3 u=0.1） | 不可用 | 拒绝（同类命令，待补） | 待证 | §4 |
| `/AIHL/source/planeBeam` | 待证 | 允许（fields run4 圆内分布） | 不可用 | 拒绝（同类命令，待补） | 待证 | §4 |
| `/AIHL/source/isotropic` | 待证 | 待证 | 不可用 | 待证 | 待证 | 未运行 |
| `/AIHL/source/preset` | 待证 | 待证 | 不可用 | 待证 | 待证 | 未运行 |
| `/AIHL/source/reset` | 待证 | 待证 | 不可用 | 待证 | 待证 | 未运行 |
| `/AIHL/source/print`（只读） | 允许（只读命令） | 允许（本轮多次） | 不可用（阻塞） | 允许（只读） | — | §3/§6 |
| 原生 `/gps/ene/mono` 等 | Geant4 允许但**不可审计** | 同左（§6 反例） | 不可用 | 需 `/gps/source/...` 指定 | 同左 | §6 |
| 运行名 | 仅 INI/CLI（无会话命令） | 拒绝（无命令入口） | 不可用 | — | — | 命令表无 `/AIHL/run/*` |
| `/AIHL/output/setDir`、`setFormat`、`setThreadSuffix` | 允许（PreInit；既有测试） | 拒绝（本轮 setDir：status=200、failed） | 不可用 | — | — | §5.2；`test_run_summary.py` |
| `/AIHL/app/setSeed`、`setNumThreads`、几何/物理/scoring/biasing 修改 | 允许（PreInit） | 拒绝（既有测试） | 不可用 | — | — | `test_command_state_gating.py`、F6/Astra 记录 |
| `/random/*` | 允许（合法值） | 拒绝（非法值，既有测试） | 不可用 | — | — | `test_random_command_semantics.py` |

未证项不是“允许”；协议层应对 `待证` 字段返回 `application_status=pending` 或拒绝。

## 8. 两个协议方案（供主审选择；本轮不改生产入口）

### 方案 A：复用受控 csh（零后端改动）

- 会话模型：一个进程 + stdin 行命令；每条命令执行完才读下一行；`beamOn` 同步阻塞。
- 回执边界：会话级。只能靠 `run_summary.txt` + 每轮产物 + 退出码判断；单字段命令没有 per-command 回执。
- 错误：状态门拒绝可以在会话结束时给出 `failed` 摘要（§5.2）；但**源命令致命异常直接中止进程**（§5.1），无收据、无法继续会话。
- 取消/关闭/断线：`beamOn` 期间无法取消；关闭 = `exit` 或终止进程；断线 = 进程死亡；重放 = 重发整段命令（无幂等/去重）。
- 旧后端兼容：天然兼容（就是现有入口）。
- 维护成本：后端零；驱动侧高（解析人类 stdout、处理各种硬中止、无法区分“已应用/已排队/被拒绝”）。
- 适用：一次性脚本、离线批量；不适合下一轮的 GUI 会话面板（要求逐字段可审计回执、取消、重连）。

### 方案 B：版本化 JSON-lines 会话协议（`g4usim-session-v1`）

- 传输：`--ui-session session-v1`（或 `--session-proto jsonl://`），stdin/stdout 一行一条 JSON；stderr 保留人类日志。
- 消息：`hello{protocol_versions, backend_version}` → `welcome{selected_version}`；`set{request_id, path, value}` → `receipt{request_id, requested, resolved, application_status(applied|pending|rejected), applied_revision, kernel_evidence}`；`run{events, request_id}` → `run_started{run_id}`、`progress{run_id, completed, planned}`、`run_finished{run_id, planned, completed, status, artifacts}`；`cancel{request_id}` → `cancelled{request_id, completed_before_cancel}`；`shutdown{request_id}` → `closed{request_id}`。
- 错误分级：`validation_error`（可继续会话）、`state_gate_error`（拒绝该命令、会话可继续）、`fatal_error`（会话终止并落 error 回执）；每条回执带可追溯 revision。
- 确认边界：`applied` 只在该字段已写入内核可观测路径后返回；延迟应用（ion/confine/相空间）返回 `pending` + 预计生效 run 边界，并在 `run_finished` 回执里补 `resolved` 值。
- 取消：run 期间协作检查（复用 `RunProgress` 的每事件钩子），返回已完成事件数；关闭：`shutdown` 走正常 finalize 路径；断线：stdin EOF 或心跳超时后按正常 close 收尾；重放：服务端记录 request 日志，客户端可用 `replay{from_revision}`（可选，v1 可只支持客户端重发 + 去重键）。
- 旧后端回退：driver 先读 `--capabilities` 的 `session_protocols`（当前没有）；缺失则回退方案 A，并在 UI 上明确标注“无逐字段回执”。
- 维护成本：后端新增一个 UI session 模块（复用现有 Messenger/Manager 操作即可，不改物理路径），配套 handler 测试与协议版本兼容测试；驱动可测试性显著提高。
- v1 最小范围（推荐）：`set` 只覆盖 §7 中 `允许` 的字段；`run` 覆盖 `beamOn`；错误分级、`cancel`、`shutdown`、per-run 回执必备；其它字段返回 `unsupported` 并附替代入口。

### 对比

| 维度 | A：受控 csh | B：JSON-lines v1 |
| --- | --- | --- |
| 逐字段“已应用”回执 | 无 | 有（requested/resolved/status/revision） |
| 致命错误可控性 | 进程中止（§5.1） | 分级错误，会话可继续 |
| 取消运行 | 不可 | 协作取消 + 完成计数 |
| 断线恢复 | 不可 | 会话收尾/可选重放 |
| 原生 GPS 交错审计 | 不可（§6） | 可声明 `unsupported` 或返回 pending |
| 旧后端 | 天然兼容 | 需回退检测 |
| 后端成本 | 0 | 一个 session 模块 + 测试 |
| 适用下一轮 GUI 面板 | 否 | 是 |

**推荐：方案 B（v1 最小范围）。** 直接依据：§6 证明受控 csh 的 Manager 回执可以与内核不一致；§5.1 证明校验失败会中止会话而不是返回结构化错误；§4 证明逐字段 setter 是产品现状，面板必须逐字段确认。方案 A 保留为无协议后端的兼容路径。

## 9. 未验证/限制

- 单线程；多线程（`threads>1`）的会话合并与回执未测。
- `ion`/`confine`/`[phase_space] replay` 等延迟应用路径未在本轮实测（仅引用既有测试与源码），白名单标 `待证`。
- `/AIHL/source/isotropic`、`preset`、`reset` 未运行。
- 只在 Windows 本机跑；Linux/其他 Geant4 版本未验证（同一源码路径，但本轮无跨平台证据）。
- 未测 ROOT/合并工具、几何/物理/线程切换（按合同应走新进程，未在本轮重复验证）。
- 原生 `/gps/*` 仅用 `ene/mono` 一个反例；其它原生命令的审计缺口范围待后续轮次界定。
- 证据里 `refusal-multisource` 的退出码 `3221226505` 是 Windows 进程中止码；Linux 上等价场景的退出码未测。

## 10. 复现

```bash
cd D:/Geant4/G4UniversalSim
G4USIM_GEANT4_DATA=D:/ProgramFiles/Geant4/share/Geant4/data \
  python -B out/collab/f2-session-baseline-20261104/f2_session.py --all
python -B out/collab/f2-session-baseline-20261104/analyze.py
```

单例：`--case three-round`（另有 `fields`/`native-gps`/`preinit-cache`/`refusal-multisource`/`refusal-output-state`）。
预期：六例都被执行；`refusal-multisource` 非零中止、`refusal-output-state` exit 1；其余 exit 0。逐例原始文件在 `evidence/<case>/`。

## 11. 证据清单

产物身份（本轮实际字节）：

| 文件 | sha256 | 大小 |
| --- | --- | --- |
| `out/collab/f2-session-baseline-20261104/f2_session.py` | `3407061bdc4fd42bdb944fcfa0e08f69fa5d102a718d710dd4a33554541ed8ba` | 13,337 B |
| `out/collab/f2-session-baseline-20261104/analyze.py` | `ec8b69c6a109e2aa92ee283cdccc0f68ebef7aa39ad33791c3cc6cc520e80d08` | 6,511 B |
| `out/collab/.../evidence/index.json` | `cba04241b6a2d6871957b56fe03e66728338d6164e2e2ac71f642ec78b28a81e` | 626,489 B |
| `out/collab/.../evidence/results.json` | `9a85fb0e77e5cdf9f27f7d1a95522e4a86349277169955db1fb6805ec9bbcefc` | 12,760 B |
| `out/collab/.../evidence/results-summary.md` | `fafb92a1783e0c1747769b1364b8a2e004de3361429d1e7873e9750c4260a82f` | 3,656 B |

（`index.json` 每次重跑因时间戳/耗时不同会变；引用以逐例原始文件与 `results-summary.md` 为准。）

- `evidence/index.json`：全部会话的记录（命令、退出码、run 摘要、逐轮 phase-space 汇总），由 `f2_session.py` 生成；每次重跑因时间戳/耗时不同哈希会变，逐例原始文件与 `results-summary.md` 才是报告引用依据。
- `evidence/results-summary.md`、`evidence/results.json`：由 `analyze.py` 从原始文件重算的汇总。
- `evidence/<case>/{stdin.txt,stdout.log,stderr.log,session.json,run_summary.txt?,output/}`：原始 stdin/stdout/stderr、进程记录、摘要与逐轮产物（`phase_space_t*.csv`、`hits_t*.csv` 等）。
- 配置：`config/main.ini`、`config/geometry.ini`、`config/main_multisource.ini`。

## 12. 边界声明

- 本轮没有产品/测试/CI 改动，没有 Git 提交或推送，没有安装依赖，没有占桌面。
- 作者是实施者，不是独立审查者；两协议与白名单供主审选择与独立复验，F2 阶段是否通过不由本报告决定。
