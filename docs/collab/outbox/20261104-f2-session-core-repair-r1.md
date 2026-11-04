# F2-SESSION-CORE 修复回执（A–E 与 round40 增量指导）

状态：**作者修复完成，已冻结，等待主审独立复验**。未提交 Git、未推送、未改 GUI/CI/旧 csh/batch 行为。

## 1. 任务与范围

- 依据：`docs/collab/reviews/20261104-f2-session-core-review-r1.md`（首审 A–E 五组缺陷）与 round40 增量指导（合法目标 + 过期 revision 的独立校验、幂等指纹覆盖 `op`、记录失败锁存的跨线程保护）。
- 改动范围仅：`main.cc`、`src/Core/SessionServer.cc`、两个会话测试、`docs/会话协议.md`、本回执；`out/` 下补丁脚本被 gitignore，不计入候选。

## 2. 修复清单

| 组 | 缺陷 | 修复 | 反例/正例覆盖 |
| --- | --- | --- | --- |
| A | server 分支早于宏路径，INI `[run] macro` 被静默忽略 | `main.cc` 在 `Configure()` 后按实际 `SimulationContext` 判断，发现预置 macro 直接失败并给出消息 `--session-server does not support a preconfigured macro from the main INI ...` | `test_session_protocol.ini_macro_refusal`：非零退出、无 `run_started`、无事件 |
| B | 记录目录边界用词法+大小写敏感比较，误放行相对输出/大小写别名/前缀链接 | `main.cc` 新增 `NormalizedAbsolutePath`（`weakly_canonical`）、`FolderKeyOf`（Windows 小写）、`PathIsInsideDirectory`；`--output` 与 `--session-record-dir` 都按规范化绝对路径判断 | `record_boundary_cases`：相对 output + 内嵌 record 拒绝；外部相对 record 接受并由服务端创建；Windows 大小写别名拒绝 |
| C | 读取线程 cancel/ping/busy 未共享主路径身份规则（stale revision/错误目标仍被接受并取消真实 run） | 读取线程统一 `ValidateReaderFrame` + `TryReaderControl`：`cancel` 必须带合法整数 `state_revision`、目标类型/目标值匹配；非法控制不修改取消标志；拒绝与主路径一样消费 `seq`；幂等指纹改为 `{op, params}` 稳定哈希 | `test_session_cancel_mt`：合法目标 + stale revision、缺失 revision、错误类型 revision、错误目标类型、错误 run 目标、错误 run_id 类型均拒绝，随后 ping 仍 `running`，再合法 cancel 生效；`test_session_protocol`：同 `request_id` 不同 `op` 返回 `idempotency_conflict` 且无副作用 |
| D | 记录根由调用方创建/新会话覆盖旧记录/写入与关闭无锁 | 记录根由服务端创建，每次会话使用唯一 `session-<id>` 子目录；`RecordLine`/`run_finished`/最终关闭全部在 `recordMutex` 下串行化；`recordFailed`/`recordError` 写入加锁，`exitCode` 为 `std::atomic<int>`；关闭失败锁存并非零退出 | `two_sessions_keep_history`：第二会话不改写第一份 `session.jsonl`（shutdown 后字节冻结）、两份收据并存；`mt16_terminal_case`：`get_state` 的 `record_root`/`session_root` 关系与收据路径 |
| E | 16 worker 时 `run_finished` 超 64 KiB 被替换为裸 `frame_too_large`，终态丢失且 exit 0 | 终态帧有界化：超限时发送 `artifacts_truncated=true`、`artifact_count`、`receipt_ref{path,schema,sha256,size_bytes}`（已关闭收据承载完整列表）；仍超限则带归属错误而非静默成功 | 真实 16 worker、32 事件：`run_finished` `status=completed`、32/32、`artifacts_truncated=true`、`artifact_count=129`、`receipt_ref` 指向 `run-0000.json`（sha256 `52e5fac1…`，39,356 B），无裸超限帧；单线程 6 事件小载荷路径保持内联 `artifacts` |

## 3. 文件与哈希（工作区当前，未提交）

| 文件 | bytes | sha256 前缀 |
| --- | --- | --- |
| `main.cc` | 62,362 | `de650497785a4671` |
| `src/Core/SessionServer.cc` | 72,604 | `98776f6627fbec15` |
| `scripts/test_session_protocol.py` | 29,374 | `de6d6e66fc0e0864` |
| `scripts/test_session_cancel_mt.py` | 12,534 | `348df9cdf0b2be33` |
| `docs/会话协议.md` | 9,268 | `673fce40cd6ce7be` |
| `docs/collab/CURRENT-SUPERVISION.md` | — | 主审维护，随本轮同步 |

## 4. 构建与证据身份

- 构建：`cmake --build build_vs2026 --config Release --target G4UniversalSim` 成功；exe `build_vs2026/Release/G4UniversalSim.exe` sha256 `9f0234f3f1cd793dbc5ab3e8ad4aa0e9d321290763ad2d4d198053b8616354cf`（2,676,224 B）。
- 源码身份：HEAD `9f4d73de6026c3c1b7735229a276df9168301ada`（首候选提交），`git_dirty=true`；报告 `source_fingerprint=d8e1081f98f485a5…`、`tests_content_fingerprint=7a0014c49d8e…`。因修复未提交，报告身份为“9f4 + 工作区修复”，不是干净候选；主审复验时应以本回执哈希为准。
- 门禁：`scripts/check_report_evidence.py --report-root <每份报告>` 全部通过（v2、`settrace_assert_lines_v3`、`sha256_raw_bytes_lf_v2`）。

## 5. 测试证据（`out/verification/f2-repair-r1/`）

| 用例 | 报告 | 断言 | 结果 |
| --- | --- | --- | --- |
| session_protocol | `20261104-140353-d4298379` | 563 | PASS |
| session_cancel_mt | `20261104-140413-1288628a` | 148 | PASS |
| command_state_gating | `20261104-140421-d49d360c` | 23 | PASS |
| interactive_commands | `20261104-140437-17295d2a` | 309 | PASS |
| random_command_semantics | `20261104-140526-34cf0f74` | 302 | PASS |

直接 probe 复跑：`test_session_protocol.py` 530 断言、`test_session_cancel_mt.py` 133 断言均 exit 0（runner 计数含其附加断言，以报告值为准）。旧 csh/batch 三个兼容用例全 PASS。

## 6. 未验证 / 限制

- 仅 Windows 11.3.2 实测；Linux 构建与运行未在本修复轮重跑。
- 16 worker 截断路径只验证“完成/截断/有界终态”，未验证海量 artifacts 的磁盘/时间压力。
- 同一记录根并发两个会话未测（当前设计按会话子目录隔离，未验证并发创建竞争）。
- 取消仍是读取线程登记 + 事件边界软中止（实验性）；跨平台、真实复杂物理列表的取消未验证。
- `--session-server` 的宏拒绝只覆盖主 INI 的 `[run] macro` 及等价字段；未覆盖命令行宏组合（CLI 已由参数校验拒绝）。
- 记录目录“写入/关闭失败”资格用锁存与关闭核验覆盖，未做真实磁盘故障注入。

## 7. 复现命令

```bash
cd D:/Geant4/G4UniversalSim
cmake --build build_vs2026 --config Release --target G4UniversalSim
python -B tools/test_assert_probe.py scripts/test_session_protocol.py
python -B tools/test_assert_probe.py scripts/test_session_cancel_mt.py
python -B scripts/run_m0_tests.py --profile backend --case session_protocol --report-root out/verification/f2-repair-r1
python -B scripts/run_m0_tests.py --profile backend --case session_cancel_mt --report-root out/verification/f2-repair-r1
```

## 8. 声明

- 本轮不新增功能、不改旧 CLI/csh/batch/GUI/CI 语义；A–E 与 round40 三点为同一范围的最小修复。
- 未提交 Git；是否冻结为第二候选、以及提交/推送由主审决定。
- 作者完成不等于验收：等待主审独立复验 A–E、真实路径/控制/记录/多 worker 终态与双平台构建。
