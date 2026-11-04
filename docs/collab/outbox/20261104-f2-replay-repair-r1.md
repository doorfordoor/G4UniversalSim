# F2-REPLAY-REPAIR-R1 作者交付回执

状态：作者交付，待主审独立复验；未提交 Git、未推送、未切分支。唯一改动为
review `20261104-f2-replay-review-r1.md` 指出的“损坏步骤在执行后才被拒绝”。

## 缺陷与最小修复

- 反例：有效快照 + `replayable=true`，清单首个 run 的 `status` 改为 `cancelled`；
  旧实现执行该 run（5 事件）后才检查 status 并以 exit 4 结束。
- 修复：`PrepareReplay()` 在回复握手/初始化前调用新增 `ValidateReplayPlan()`，
  校验整份清单（有限操作、合法字段/值、run 的 completed 状态、事件数范围、
  `completed_events == events`、run_id/请求 id、至少一个完成 run）；首个或后续
  步骤损坏均拒绝，且 0 run_started / 0 物理 CSv。
- `ExecuteReplay()` 每个 run 前防守检查状态，运行后核对实际终态（completed、
  完成事件数等于清单值），结束时 `steps_executed == run 步数`，否则
  `replay_failed` + 非零退出。

## 文件（sha256 见证据 README）

- `src/Core/SessionServer.cc`
- `scripts/test_session_replay.py`
- `docs/会话协议.md`（§8 增补启动前整份清单校验与终态核对措辞）

## 测试与证据（作者自测）

报告 `out/collab/f2-replay-repair-r1/report/`；证据目录
`out/collab/f2-replay-repair-r1/`（README、counterexample、original、logs）。

- `session_replay`：新增 5 类损坏步骤反例（首轮/后续轮 cancelled、完成计数不一致、
  非法事件数、不支持操作），均非零退出、无 welcome、无 run_started、无物理输出；
  1 worker 三轮与 2 worker 两轮正例继续逐事件一致，并核对 `steps_executed`/
  `steps_total`。
- 回归：`session_protocol`、`session_cancel_mt`、`gui_session_backend`。
- 原失败原件直接复核：用 `original/failing-tampered-cancelled-step/` 对修复后 exe
  重放，退出码 4、stderr `session replay refused: ... step 1 is not a completed
  source run`、无 CSV、无 welcome/run_started（日志在 `counterexample/`）。

## 身份

- HEAD `7173fe82`（候选提交）之后的工作区修复；dirty，报告
  `tracked_source_gate=fail` 属预期。
- exe sha256 `2ac8ed8e619beb4078a2c40affb702fa90b0508313329f138b1e9ad31434ac25`，`source_fingerprint=06f367a0cd51bab0d28d7e7b3e808bec1a9f91ceef4c88cf5b882493178f430e`，
  `build_git_commit=7173fe820bc6e9baeccb8ea7e1509bc0e25a67c4`。

## 限制

- 仅 Windows 作者自测；独立复验、实窗缩放/Linux 原生由主审另验。
- 未改动独立复验原件；未断言跨平台/跨线程分片逐位一致。
