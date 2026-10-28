# 阶段 1e 验收证据（2026-10-28）

本目录是**阶段 1e（命令失败传播：交互偏置拒绝、材料生命周期门禁、配置值有限性）**的全量回归证据副本。

- 报告：`report.json`（`version: 2`，`profile: all`，80 例全部 pass）
- 逐用例日志：`logs/`（80 个，报告内 `log_sha256` 与这些文件的**原始字节**一致；本目录由 `docs/verification/** -text` 保证不被换行改写）

## 报告事实（可直接复核）

| 字段 | 值 |
| --- | --- |
| 基线提交 | `7f5dc48`（上一轮提交；本轮改动工作区未提交，`git_dirty=true`） |
| 用例 | 80 pass / 0 fail / 0 skip（static 6 / gui 26 / backend 34 / integration 14） |
| 断言证据 | `assertions_executed_total=116183`、`assert_sites_total=2412`、`cases_with_zero_assertions=[]`、`assert_probe=settrace_assert_lines_v2` |
| 摘要算法 | `log_digest_algorithm=sha256_raw_bytes_lf_v2` |
| 源码指纹 | `ab87d6ef696da23ad31460ccedf53e2d3e295beb78b0ae195479431267a8fca5` |
| 测试/夹具内容指纹 | `09d94586b54b56e3f930c96f58afa9a164cbf2a0e589ef864ec4c0e77b9cc2ab` |
| 后端 | `G4UniversalSim.exe` SHA-256 `eb2a374773b093995d3d1b543a942522855adb34f17bc047c6e31f971f1a3072`（1735168 B），MSVC 19.51.36246.0 + Geant4 1132 + MT |
| 运行环境 | Windows-10-10.0.26200-SP0，Python 3.11.9 |
| 门禁 | `python -B scripts/check_report_evidence.py --report-root out/verification/stage1e-20261028` → `report evidence: OK` |

## 本轮闭合的三个缺陷（Astra 2026-10-28 审查 D-4 / D-5 / D-6）

三条都是"改了缓存/只告警、内核没变、进程仍退出 0"的静默失败路径，改前都先做了真实 `--ui --ui-session csh` 反例（原始输出见 `docs/collab/outbox/20261028-1105-deepseek-command-failure-closure.md`）：

1. **交互偏置拒绝只 `JustWarning`**（`src/Biasing/BiasingMessenger.cc`）：反例里出现 `AIHLBiasingInteractive001` 警告后，后续命令照常执行、`/run/beamOn 1` 跑完 1 个事件、退出码 0、摘要 `status=completed`、`interactive_command_failure_kind=none`——用户以为配了 XS 偏置，实际是未偏置物理。现在拒绝被记录到 `BiasingManager`，计入 csh 失败、停止会话、`status=failed`、`run_count=0`、kind `biasing`、退出码 1。
2. **material 交互命令无生命周期门禁**（`src/Materials/MaterialMessenger.cc`）：反例里 `/run/initialize` 之后 `addNist` 静默成功、退出码 0、摘要 `status=completed`，但几何已建、新材质不被任何体积使用。现在 9 个变更命令统一 `AvailableForStates(G4State_PreInit)`，初始化后由 Geant4 拒绝（kind `geant4_illegal_application_state`、`status=failed`、`run_count=0`、退出码 1）；`print`/`list` 仍只读可用，batch 的 `main.cc` 守卫保留为纵深防御。
3. **`ParseStrictDouble` 接受 `inf`/`nan`**（`src/Config/ConfigValue.cc`）：反例里 `[biasing.xs.proton.elastic] factor = inf`、`min_weight = nan` 时 `--dry-run` 退出码 0 且无警告。现在拒绝 `errno == ERANGE` 与非有限值，报 `Config value '<v>' is not a finite double`；合法配置不受影响。

顺带修正了一处聚合缺陷：`main.cc` 的失败 kind 计算首版用嵌套三元，同时命中两类时把具体诊断降级成 `multiple`；现改为先收集 kinds、具体诊断优先、只有真正多类才报 `multiple`。

## 新增/更新的回归

- `scripts/test_interactive_commands.py`：新增 `biasing_interactive_reject`、`material_after_initialize` 两个 session 用例（断言非零退出、后续 `/control/echo` 不出现、`status=failed`、`run_count=0`、失败 kind）。
- `scripts/test_config_value_finiteness.py`（新，backend 层，已注册进 `scripts/run_m0_tests.py`）：合法配置 0；`factor = inf` 与 `min_weight = nan` 均非零且消息含 `is not a finite double`。
- 受影响后端用例复跑全过：`test_run_summary`、`test_physics_a6`、`test_geometry_a5`、`test_command_state_gating`、`test_config_precedence`、`test_config_duplicate_declarations`、`test_material_config_schema`、`test_unconsumed_config`、`test_unsupported_features`。

## 复现

```bash
python -B scripts/run_m0_tests.py --profile all --require-tracked-sources --fail-on-skip --report-root out/verification/stage1e-20261028
python -B scripts/check_report_evidence.py --report-root out/verification/stage1e-20261028
```

## 这份证据不证明什么

- 不包含 Linux 或 GitHub Actions 上的后端运行（E3/2A 未建立）；CI 目前只跑 static+gui。
- 只覆盖脚本化 `--ui --ui-session csh`；Qt UI 里的同类操作仍未自动化验收。
- 断言数是**已执行 `assert` 的下界**，不是覆盖率；门禁只证明报告与日志自洽且未被篡改，不证明断言写得好。
- 不证明任何物理结果的正确性。
