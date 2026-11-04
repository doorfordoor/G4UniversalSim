# F2 GUI 会话面板交付（作者自测，待独立复验）

任务 ID：F2-GUI-SESSION-20261104。作者交付日期 2026-11-04。作者为 D 盘 GUI 单写者，
主审 C 盘冻结候选 `513117f3b7d37c687e1aabc6797e7b02d8a71436`（C++ 指纹 `d8e1081f…`）
未被本任务修改。本次交付**未提交 Git、未推送、未切换分支**，完成后冻结停工等待主审
独立复验。ROADMAP / STATUS / CURRENT-SUPERVISION 的阶段状态未由作者改写。

## 1. 身份与边界

- 分支：`roadmap/F2-controlled-session`；HEAD：`3f665ce1337ac382c4bf60ace20fbd248928afc6`
  （docs-only，`docs(F2): record backend review and GUI dispatch [skip ci]`）。
- 工作树 dirty：18 个已跟踪文件被修改 + 新增 GUI/测试文件未跟踪；其中
  `docs/ROADMAP.md`、`docs/collab/CURRENT-SUPERVISION.md`、`docs/collab/inbox/20261104-f2-replay.md`
  属主审/用户维护内容（保留未动）；用户交接材料同样保留未动。
- 产品侧只改 GUI 与两处**已授权**的后端补丁（`src/Core/SessionServer.cc` +
  `scripts/test_session_protocol.py`，见 §3）。未改物理/计分/几何/CI/主题门槛，
  未重开 J3 视觉验收。
- 数据库/资产：未安装依赖、未占桌面长时间运行、未按进程名终止其它任务。

### 构建身份（重要）

| 字段 | 值 |
| --- | --- |
| exe | `build_vs2026/Release/G4UniversalSim.exe` |
| exe sha256 | `01e3ae27a213be61732852a4b53afa5d53d1bdb926728390826a19487aeeeced` |
| exe bytes | 2,678,784 |
| `--capabilities` source_fingerprint | `c0559899899485d466bb0fc912bb09aa52565423e6713e7b613f86cc46949e76` |
| `--capabilities` build_git_commit | `3f665ce1337ac382c4bf60ace20fbd248928afc6` |
| 编译链 | MSVC Release（`cmake --build build_vs2026 --config Release --target G4UniversalSim`） |

说明：该 exe 在冻结候选 C++ 基础上额外包含本任务 **授权** 的致命帧补丁，因此其
`source_fingerprint` 是 `c0559899…`，**不等于**主审冻结候选的 `d8e1081f…`。它不是
主审 C 盘冻结构建的复本；最终原生验收请以主审在最终候选上的构建为准。作者未改
C++ 以外的后端行为。

## 2. 交付文件与哈希

完整机器可读清单：`out/collab/f2-gui-session-20261104/delivery-files.json`。

| 文件 | 变更 | sha256 | bytes |
| --- | --- | --- | --- |
| `gui/g4usim_gui/core/session_model.py` | 新增 | `5d74c07a0e1bf8d1737de7cad1f8c01a2f0ddabc2314744c3e66b6d686e6dcd6` | 12,522 |
| `gui/g4usim_gui/core/session_client.py` | 新增 | `816fe1168b448f9e43a11476f3d4cfb8680d19f121e39780b7562ada4c90b18b` | 28,904 |
| `gui/g4usim_gui/widgets/session_panel.py` | 新增 | `321f15762019bbb9b8fb4f86d2eefdf789223844234681bbd55123d47622e0c4` | 27,830 |
| `gui/g4usim_gui/window/session.py` | 新增 | `a1670832d06a616908c20dc5565017786edba4429e569fe33d626b604dca70cf` | 14,204 |
| `gui/g4usim_gui/core/runner.py` | 修改 | `4b0f8c8a962dc9168cb2086332fe4064b4196abcbc504b80e746e5bce2c3ca59` | 17,581 |
| `gui/g4usim_gui/widgets/run_page.py` | 修改 | `8b72cb988a7d562ca1e24aeb80d15ed6f53b40fd5b3b810e026fe9b9af07c876` | 16,560 |
| `gui/g4usim_gui/window/run.py` | 修改 | `743fc725c258674c19ca47b345ade81152ed588426afdb32bee4325fb9f5a111` | 20,342 |
| `gui/g4usim_gui/main_window.py` | 修改 | `0fe29b02aa86f0a3b25a82354808f11480cefa63cbfd482dbfcd0094f32538a9` | 13,227 |
| `gui/g4usim_gui/core/i18n.py` | 修改 | `4df5ad24c2262b13bb3cbb2eff1c25dcd610f87410ae70572be0a272ff152cec` | 143,698 |
| `gui/g4usim_gui/core/run_result.py` | 修改 | `a827e8d46a5af50d166d451bf6b7706bae51d65b3544602e0196eed084cb629f` | 4,577 |
| `gui/smoke_tests/smoke_session_panel.py` | 新增 | `2497dbbbfb357ef71d8d3504138c2076e276103ecf1cf039c61087808b5d6522` | 12,066 |
| `gui/smoke_tests/smoke_session_backend.py` | 新增 | `44e09ce7ef561e5b42c379dadf11a91b4c802f6e24e2a02649c6100a6be8ca0d` | 7,714 |
| `gui/smoke_tests/smoke_run_result.py` | 修改 | `bbc9b6bce36a3f4c7170a0e277680ea67ee615064d0bf62c34477935b2bd161b` | 4,757 |
| `gui/smoke_tests/smoke_history.py` | 修改 | `edcbc3a629b0cf2e472f27673bfccda7c2ca92c1faedaa42aaa424d399184e40` | 5,399 |
| `scripts/run_m0_tests.py` | 修改 | `67f81163741049cea0d0f0861fcd7c7ee9798d808fc671301cefa67a0ebe6ec8` | 41,707 |
| `scripts/test_session_protocol.py` | 修改（授权补丁测试） | `6e2908cfc7892981310b17dc9c3b86590a1fb7a4a510cdc8d1afa521548c2599` | 35,826 |
| `src/Core/SessionServer.cc` | 修改（授权补丁） | `cfd375bfcf68afdd514c9e75506897edd1192a7606c0bb3fac6140ab77f56ff9` | 78,703 |
| `docs/会话协议.md` | 修改 | `cf5191b3642b2da70ee53dbe9821b098b681bec085264290f9c7f55ea3973527` | 11806 |
| `docs/功能支持矩阵.md` | 修改 | `0cd3a6973c9d7223ff26d83a7b0fb1488b9379819cc22d1440d70c02a61af9c3` | 198,651 |
| `gui/docs/中文快速使用说明.md` | 修改 | `fddcc142771a154f1eef00f76156bbe86ab2a701af5d6ec7563afcb40364e35a` | 46,940 |
| `gui/AGENTS.md` | 修改 | `07d35fb7fd285c6a4db9bec6744b7506626f7e8276922996451bec9524907723` | 65,239 |


## 3. 授权后端补丁：运行中损坏帧必须失败

主审反例（`docs/collab/reviews/20261104-f2-protocol-fatal-during-run.md`，原件
`out/collab/f2-protocol-fatal-r1/` 未覆盖修改）：2 worker / 200000 事件，`run_started`
之后写入 `{"kind":` 并关闭 stdin，旧实现只把 Fatal 入队，EOF 让主循环返回，进程
exit 0、无 `protocol_error`。

最小修复（仅 `src/Core/SessionServer.cc` + 原会话测试）：

- ReaderLoop 发现协议错误（无效 JSON、超长帧、EOF 遗留残片）时在 stateMutex 下
  **锁存失败并写入原子取消意图**；运行中取消目标为当前 run，否则登记 pending。
- 主路径在 `BeamOn` 返回后先检查锁存再处理 `eofShutdown`；锁存后发送一次
  `protocol_error` 并以 exit code 3 结束；EOF 不再吞掉失败。
- 坏帧原始输入被截断后写入 c2s 记录；不重复记录 Fatal 原始行。

验证（`scripts/test_session_protocol.py` 整跑 **exit 0**）：

1. 坏行 + EOF（2 worker / 200000 事件）：exit 3、`protocol_error`、唯一
   `run_started`/`run_finished`、终态 cancelled/aborted、completed < planned、
   `session.jsonl` meta `exit_code=3`、原始坏行出现在 c2s。
2. 超长帧（70000 字节 + 换行，stdin 不关）：有界 exit 3、`frame_too_large`、唯一终态。
3. 短残片 EOF（发 `{'kind':` 后关 stdin）：exit 3、`protocol_error`、记录退出码非零。

旧 csh / batch 行为未变：`scripts/test_command_state_gating.py`、
`scripts/test_random_command_semantics.py` 等兼容用例未修改并通过（见主审报告）。

## 4. GUI 实现概要

- **单一进程所有者**：会话不另建 QProcess。`G4USimRunner` 新增 `start_session()`、
  `sessionData(bytes, bool)`、`processStarted`、`write_session_data()`；会话模式只在
  读路径写原始日志并转发字节，不再按单次运行解析/汇总结果。`SessionClient` 绑定
  runner 的既有进程，`is_active()` 取决于 runner 是否仍在运行；普通运行/扫描/实验/
  Agent 与会话共用同一所有权守卫（`_session_owner()` 六道检查 + `session_owns_process()`
  在普通运行入口拒绝并提示）。
- **协议状态机**（`core/session_client.py`）：hello/welcome/initialize 自动握手；
  `seq`、request `id`/`request_id`、mutating `state_revision`、幂等/去重、请求超时、
  `busy` 本地拒绝（运行中提交走 `roundRejected` 而不是伪造失败）；`set_source` 链
  先 particle 后 energy 再 `run`；`cancel`/`shutdown`/`kill`；`run_finished` 校验收据
  后入轮次记录；stdout 行按前缀分流（进度、JSON 帧、普通日志）。
- **面板**（`widgets/session_panel.py`）：Run Console 顶部「连续运行会话」四区
  （当前会话与本轮 / 下一轮参数 / 轮次记录 / 操作反馈），状态 chip 区分
  Starting/Initializing/Ready/Running/Closing/Closed/Failed；可编辑字段仅后端
  `CanAcceptSessionEdit` 允许的单源简单字段 + 事件数，几何/物理/线程/输出根提示
  “需新建会话”；轮次表保留 request/run/参数/事件数/状态/收据并支持 tooltip 明细。
- **收据与历史**：inline receipt 校验 schema/run_id/run_request_id/status；
  `receipt_integrity=unavailable`、未知值、缺失或校验失败显示“运行完成但记录不可用”，
  不显示完整成功；thin `receipt_ref` 按路径、字节数、SHA-256 复核后读取；历史/结果页
  只做只读刷新，不把旧轮次重新授予当前配置的成功资格。
- **会话面板资格**：模型层 `session_eligibility` 与后端
  `SourceManager::CanAcceptSessionEdit` 对齐（多源、phase_space、deferred、advanced、
  ion 才拒绝；已解析的简单 preset 标签不拒绝），拒绝只作用于会话内编辑而不改写生成包。
- **生命周期**：关窗时 `stop_session_before_close()` 先 shutdown 再有界 kill；会话期间
  普通运行按钮禁用、普通单次运行的状态标签/进度条隐藏，关闭后恢复；历史/结果保留。

## 5. 自测与证据

### 本轮最终聚焦回归（改动后）

`out/verification/f2-gui-final/20261104-154156-b7ebc59e/report.json`

```
5 pass / 0 fail / 0 skip of 5 cases
assertions executed 184（gui_session_panel 53、gui_session_backend 44、
gui_history 9、gui_run_result 27、gui_main_window 51）
probe settrace_assert_lines_v3, source c05598998994..., tests 9a9bf4533a13...
```

`python -B scripts/check_report_evidence.py --report-root out/verification/f2-gui-final`
→ `report evidence: OK`。

### 主审已核对的原有报告（保留，不重复）

- 7 个 GUI 用例 / 1062 断言：`out/verification/f2-gui-session/20261104-152515-8808a738/report.json`、
  `20261104-152615-6becabd3/report.json`。
- 真实 `gui_session_backend` / 44 断言：`20261104-152056-1560a129`、`20261104-152642-db6e8499`。
- `gui_session_panel` / 53 断言：`20261104-152128-3f96aa32`。

### 真实后端三轮与取消（作者自测）

`out/collab/f2-gui-session-20261104/evidence.json`：

- `three_rounds=true`：A/B/A = 100 / 200 / 100 MeV，各 5 事件，`completed`、
  `receipt_ok=true`（同一后端进程，run/request 身份互异）。
- `cancelled_round=true`：20000 计划，取消后 `cancelled`、completed 3012、
  `receipt_ok=true`。
- `round_after_cancel=true`、`closed=true`（关窗有界释放所有者）。
- 会话记录副本：`out/collab/f2-gui-session-20261104/session-records/`（welcome/
  initialize/run_started/run_finished）。
- 截图 9 张在 `screenshots/`：**仅作者自测，不是独立实窗验收**，主审不以其替代
  Windows/Linux 原生操作。

### 其他

- `scripts/test_session_cancel_mt.py`：EXIT=0（包含真实取消与取消后下一轮）。
- `scripts/test_session_protocol.py`：EXIT=0（含上述三个致命帧反例）。

## 6. 文档

- `docs/会话协议.md`：新增 §7 GUI 会话面板、§8 未完成；改正旧“GUI 尚未接入”的
  过期表述；把取消措辞改为“各 worker 在自身 TLS RunManager 完成本事件记账后调用
  `G4RunManager::AbortRun(true)`（`src/Actions/EventAction.cc:60`）”，未改取消算法。
- `gui/docs/中文快速使用说明.md`：增加连续运行会话的使用步骤与边界。
- `docs/功能支持矩阵.md`：新增“GUI 连续运行会话”行（部分支持 / 作者交付待独立复验）。
- `gui/AGENTS.md`：新增 F2 会话面板现行约束（单一 runner 所有者、收据校验、
  回归入口、状态与历史资格分离）。
- ROADMAP / STATUS / CURRENT-SUPERVISION：作者未改写最终状态，留给主审收尾。

## 7. 已修复的失败（保留记录）

1. 后端协议：运行中损坏帧/E0F 被吞（主审反例）→ §3 补丁，修后三个反例 exit 3。
2. 后端 smoke 首次超时：运行中提交走通用 failure 而非 busy 拒绝 → 调整
   `SessionClient.start_round` 守卫顺序（先 handshake、再 busy 本地拒绝、最后 phase）；
   现在 `roundRejected(busy)` 可见且后续状态正确。
3. 面板 smoke 退出期崩溃/锁错误：`deleteLater` 在 offscreen 下偶发 139，恢复目录
   `.lock` 在解释器退出时残留 → 关闭显式释放 + finalizer detach；现 exit 0。
4. 探针 0 轮空转：资格曾因简单 preset 标签被拒 → 改为与
   `SourceManager::CanAcceptSessionEdit` 对齐（不改生成包、不伪造热修改）。
5. 会话模式进度处理：`ProgressParser.feed` 返回列表、需要前缀；已遍历处理，不再
   丢进度或抛 AttributeError。

原失败证据保留：`out/collab/f2-protocol-fatal-r1/` 未改；作者未覆盖任何旧报告。

## 8. 限制与未验证（作者口径）

- 作者只在 Windows 上完成 GUI 自测；Linux 桌面与 Windows 125%/150% 缩放的原生
  操作、最终真实收据不可用反例的 GUI 实窗路径，均由主审在最终候选统一复验。
- 真实后端三轮/取消证据只覆盖单源、单线程简单源与两种拒绝；断线重连、完整随机
  初态重放、MT 大物理列表下的取消、热改几何/物理/线程/输出根均未实现（另按固定
  清单推进）。
- 未覆盖多窗口并存的会话；会话期间普通运行拒绝是设计边界，不是并发保证。
- 本任务不顺带扩通用 Agent/编排框架，也未重开 J3 全套视觉验收。

## 9. 复现

```bash
# 构建（已授权补丁后的 C++）
cmake --build build_vs2026 --config Release --target G4UniversalSim

# 作者聚焦回归 + 证据门禁
QT_QPA_PLATFORM=offscreen gui/.venv/Scripts/python.exe -B scripts/run_m0_tests.py \
  --profile all --case gui_session_panel --case gui_session_backend \
  --case gui_main_window --case gui_run_result --case gui_history \
  --executable build_vs2026/Release/G4UniversalSim.exe --report-root out/verification/f2-gui-final
python -B scripts/check_report_evidence.py --report-root out/verification/f2-gui-final

# 后端协议（含致命帧反例）
python -B scripts/test_session_protocol.py
python -B scripts/test_session_cancel_mt.py

# 真实 GUI 三轮/取消自测（Windows 实窗；产物 out/collab/f2-gui-session-20261104/）
env -u QT_QPA_PLATFORM gui/.venv/Scripts/python.exe -B out/f2_gui_session_evidence.py
```

## 10. 冻结声明

作者实现与自测到此结束：不提交 Git、不推送、不切换分支、不再扩展截图或验收工具。
等待主审独立复验；最终 Windows/Linux 原生操作与阶段验收由主审完成。
