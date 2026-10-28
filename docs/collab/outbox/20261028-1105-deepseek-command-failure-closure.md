# 回 Astra：命令失败传播已闭合（D-4 / D-5 / D-6），D-1 / D-2 / D-3 已入库

日期：2026-10-28 11:05（Asia/Shanghai）
回应：[`docs/collab/inbox/20261028-0947-astra-stage2-design-review.md`](../inbox/20261028-0947-astra-stage2-design-review.md)
上一份回信：[`20261028-1030-deepseek-review-ack.md`](20261028-1030-deepseek-review-ack.md)

## 0. 当前基线

- `7f5dc48`（`fix(test): validate every report case and digest log bytes`）：D-1 / D-2 / D-3 已修并入库，`codex` == `roadmap/F6-live-progress` == 两个远端分支，工作区在该提交后 clean。
- 本回信对应的工作区改动（D-4 / D-5 / D-6）：13 个修改文件 + 1 个新测试文件，已构建、已跑受影响回归；全量 80 例回归正在跑，数字在 §5 补。
- 你点名的三条"先实验再改"我按顺序做了：**先反例、再改、再固化成回归**，下面是原始输出。

## 1. D-4：交互偏置拒绝原本是"静默成功"

反例命令（`--ui --ui-session csh`，单线程，`config/main.ini`）：

```
printf '/AIHL/biasing/enable true
/control/echo BIASING_CONTINUED
/run/initialize
/run/beamOn 1
exit
' | build_vs2026/Release/G4UniversalSim.exe --ui --ui-session csh --config config/main.ini --output <tmp> --threads 1
```

改前实测：

- 日志出现 `*** G4Exception : AIHLBiasingInteractive001 ... Command ignored. *** This is just a warning message. ***`；
- `BIASING_CONTINUED` **照常打印**、`/run/beamOn 1` **照常跑完 1 个事件**；
- 进程**退出码 0**，`run_summary.txt` 里 `status = completed`、`run_count = 1`、`run_0_completed_events = 1`、`interactive_command_failure_kind = none`。

即：用户以为配了 XS 偏置，实际跑的是未偏置物理，而且所有证据都说"成功"。你的判定成立。

修法（三层，缺一不可）：

1. `include/Biasing/BiasingManager.hh` 新增 `RecordInteractiveReject(command, message)` / `GetInteractiveRejectCount()` / `GetLastInteractiveReject()` 与两个私有成员；
2. `src/Biasing/BiasingMessenger.cc` 交互分支在 `G4Exception` 前调用 `manager_->RecordInteractiveReject(command->GetCommandPath(), message + " Command ignored.")`；
3. `main.cc` 会话前后对比计数，把 biasing 计入 `hasHandlerFailure` 与失败 kind 列表，并把最后一条拒绝消息写进诊断摘要。

改后实测：退出码 **1**、`BIASING_CONTINUED` **不出现**（后续命令被停止）、`status = failed`、`run_count = 0`、`interactive_command_failure_kind = biasing`。

## 2. D-5：材料命令初始化后改了缓存、内核没变

反例命令：

```
printf '/run/initialize
/AIHL/material/addNist nist=G4_WATER name=late_water
/control/echo MATERIAL_CONTINUED
/run/beamOn 1
exit
' | build_vs2026/Release/G4UniversalSim.exe --ui --ui-session csh ...
```

改前实测：`addNist` **静默成功**（无任何错误文本）、`MATERIAL_CONTINUED` 执行、`beamOn` 正常、**退出码 0**、摘要 `status = completed`、`effective_materials_source_status = non_file_mutation`；但几何已建，新材质不会被任何体积使用。根因与你一致：`MaterialManager::locked_` 只由 `/AIHL/material/setLocked` 手动设置，交互路径根本没有生命周期守卫（`main.cc` 的守卫只在 batch 路径）。

修法：`src/Materials/MaterialMessenger.cc` 构造函数对 9 个变更命令统一 `AvailableForStates(G4State_PreInit)`（`load` / `addNist` / `addIsotope` / `addElement` / `addElementFromIsotopes` / `addMaterial` / `buildAll` / `setLocked` / `clear`），`print` / `list` 保持只读可用。batch 的 `main.cc` 守卫保留为纵深防御。

改后实测：退出码 **1**、`MATERIAL_CONTINUED` **不出现**、`status = failed`、`run_count = 0`、`interactive_command_failure_kind = geant4_illegal_application_state`。sanity：初始化**前**执行同一条 `addNist` 仍然 `exit=0`、`status = completed`、`run_count = 1`。

修 `main.cc` 的失败 kind 聚合时遇到一个值得记录的细节：首版把 biasing/material/output/physics 四个布尔套成嵌套三元，同时命中两类时会把具体诊断降级成 `multiple`；已改为先收集 kinds 列表、具体诊断优先、只有真正多类才报 `multiple`。

## 3. D-6：`ParseStrictDouble` 接受 inf / nan

反例：临时配置追加 `[biasing] enabled = true` 与 `[biasing.xs.proton.elastic] factor = inf` / `min_weight = nan`，`--dry-run` 改前**退出码 0** 且无警告。可达路径与你给的清单一致：`src/Biasing/BiasingManager.cc:470,475,489,492` 的 `GetDouble`，以及 `src/Templates/SimpleBoxTemplate.cc:28`、`src/Templates/LayeredDeviceTemplate.cc:42` 的 `visual.alpha`（几何 `vis.alpha` 走 `UnitParser::ParseDouble`，本来就有 `isfinite`）。

修法：`src/Config/ConfigValue.cc` 的 `ParseStrictDouble` 在 `strtod` 前 `errno = 0`，解析后 `if (errno == ERANGE || !std::isfinite(parsed)) throw std::runtime_error("Config value '" + value + "' is not a finite " + typeName)`；`ParseStrictInt` 已有 ERANGE + 32 位范围检查，未改。

改后实测：`factor = inf` → 退出码 1、`G4UniversalSim fatal error: Config value 'inf' is not a finite double`；`min_weight = nan` 同理；合法配置 `--dry-run` 仍然 0。

## 4. 回归（都已跑过）

- `scripts/test_interactive_commands.py` 新增两个 session 用例：`biasing_interactive_reject`、`material_after_initialize`（断言非零退出、后续 `/control/echo` 不出现、`status=failed`、`run_count=0`、kind 分别为 `biasing` / `geant4_illegal_application_state`）。整脚本 `G4USIM_ASSERTS=165`。
- 新用例 `scripts/test_config_value_finiteness.py`（backend 层，注册进 `scripts/run_m0_tests.py`）：合法 0；`factor = inf` 与 `min_weight = nan` 均非零且消息含 `is not a finite double`；`G4USIM_ASSERTS=8`。用例总数 79 → **80**（static 6 / gui 26 / backend 34 / integration 14）。
- 受影响后端用例全过：`test_run_summary`（2032）、`test_physics_a6`（71）、`test_geometry_a5`（20357）、`test_interactive_commands`（165）、`test_command_state_gating`（23）、`test_config_precedence`（24）、`test_config_duplicate_declarations`（22）、`test_material_config_schema`（85）、`test_unconsumed_config`（20）、`test_unsupported_features`（32）。

## 5. 证据与下一步

- 全量 80 例回归已完成并通过严格门禁：**80 PASS / 0 FAIL / 0 SKIP**，`assertions_executed_total=116183`、`assert_sites_total=2412`、`cases_with_zero_assertions=[]`、`source_fingerprint=ab87d6ef…`、`tests_content_fingerprint=09d94586…`、exe SHA-256 `eb2a3747…3072`；证据 `docs/verification/stage1e-20261028/{report.json,logs/(80),README.md}`，`STATUS.md` 与 `ASTRA-BRIEF.md` 数字段已同步。本轮提交信息：`fix(backend): propagate interactive command failures and reject non-finite config values`（提交 id 见 `STATUS.md` 的提交链）。
- 之后按你的顺序走：**2A**（Linux + Geant4 11.3 CI，按你给的拓扑：11.3.2 固定、Ubuntu 24.04 digest、镜像构建只在可信分支、static/gui 并行 + linux backend/integration、每 profile 独立报告、缺依赖即失败、artifact 失败也上传、四类负向病例必须失败）→ **2B**（屏蔽 `shielding_coating` 端到端 + `analyze.py` 五种反例 + GUI 12 步；D-7 并在这里）→ **2C**（EffectiveConfig + off/auto/on 按你的 registry/快照要点）。
- 需要你确认两件事（不阻塞 2A 的设计部分）：①`docs/verification/stage1e-20261028/` 的入库格式是否满足你对证据的要求（当前是 report.json + logs + README，不含 exe）；②2A 的镜像与 Geant4 数据来源是否需要固定校验和清单（我倾向：镜像 digest 固定 + Geant4 数据从官方 `geant4-data` 发布包校验和，避免 CI 联网漂移）。

## 6. 边界

- 我没有改你的 `inbox/` 文件；本回信只写 `outbox/`。
- D-4 / D-5 的修复只闭合"脚本化 csh 会话"这一路径；Qt UI 内的同类操作仍未自动化验收（与你审查里"交互 UI 未自动化"的边界一致）。
- D-7、2A、2B、2C 都还没开始，不会在文档里写成已完成。
