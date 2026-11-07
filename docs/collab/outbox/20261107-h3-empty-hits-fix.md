# H3-4 空 hits 表头最小修复回执（2026-11-07）

依据主审决定（m24939）：原 72 项正式批次执行与分析已由主审独立复算；本轮只做两个最小修复，
不重跑 B/C、不改科学判据、不改 manifest/prepare/runner/18 输入、不提交 Git、H3 未关闭。

## 1. 纯分析器修复（r_comp）

`out/collab/20261107-h3-4-benchmarks/scripts/analyze.py` 的 `parallel_mass_kg` 原先把
`0.0008` 的 Decimal-12 半单位区间与退化点对 `(0.0008, 0.0008)` 比较，按构造恒假；真实记录值
精确为 `0.0008`。改为 Decimal 原值等于预期常量。**只重算已有 72 项输出，未重跑任何模拟**。

复算结果（`corrected-analysis-20261107/results.json`，SHA-256
`18bbfbad9408ca1e6555ad0293c6432af198a0be6b457ea996c4e0e123d08835`）：
A / R-SAME / A2 / A2f / B / C / M / **R-COMP pass**；R-RUNTIME fail（原因见下），
整体 `status=wiring_failed`。旧 `wiring_failed` 分析副本保留在
`original-analysis-20261107/`（results/summary/log 原样）。

## 2. 合同字面产物修复（R-RUNTIME 空 hits CSV）

冻结合同要求启用平行计分、质量层不敏感、`hits=true` 时 hits CSV 存在且 0 行。旧候选从未
调用 `ScoringManager::ScoreHit`，惰性 writer 从不打开，`Close()` 不会登记文件，故旧 72 项
输出中 R-RUNTIME 无 `hits_t0.csv`；原分析用「缺失或空」掩盖了该字面缺口。

修复（仅 `ParallelScoringDetector::Initialize(G4HCofThisEvent*)`，Scope::WorldRoot）：
从真实线程本地 `ScoringManager` 取其真正的 `OutputManager`；当 scoring 启用、
`IsHitOutputEnabled()`、CSV 输出且 writer 未打开时调用既有 `OpenHitFile()` 写表头；异常走
既有 `ReportScoringFailure("parallel_world_hits", ...)`；不使用 master 输出指针，不写任何
ghost 行；run 收尾仍由既有 `OutputManager::Close()` 关闭并登记。默认未启用平行世界、所有
计分/输运/RNG/量定义不变。

新候选身份：exe `802ad812fb6e618bf1839320d798c5d4dfc899e1e48cebaf454662b8e3b6786d`、
组件 `3cf4f095158f23ca12d69806cac6132722157e3a56d3803c976e0917cd8c961f`、
source_fingerprint `879f00c3ca8925dd76dea5360888fc24aa77ea935c67e7d95470157875288e61`。
旧候选（`3700e272…` / `34066c13…`）字节已另存 `original-candidate/bin/`。

## 3. 新候选 R-RUNTIME 自测（一次）

冻结输入（SHA 复核一致）：`main_R_runtime.ini`、`macro_2000.mac`、`materials.ini`、
`geometry_mass_insensitive.ini`、`parallel_box.ini`；2000 事件、seed 20261400、threads 1；
输出 `out/collab/20261107-h3-empty-hits-fix/runs/R_RUNTIME_new/output`；exit 0。

| 验收点 | 实际 |
| --- | --- |
| hits CSV 存在且仅表头 | `hits_t0.csv` 158 B，0 数据行，SHA `8e86f6f3cceac416cdfd16e899f80c7d7a9978cd097510931b5a66e12de15d4a` |
| 真实 writer 登记 | schema `hits_csv_v3`、`integrity_status=hashed`，出现在 `run_metadata.json` 与 `run_summary.txt`；`generated_file_count=13` |
| 事件 | `status=completed`、`run_0_completed_events=2000`、event_edep 2000 行全 0 |
| 平行 dose/fluence 非零 | `/ScoringWorld#0/GhostSlab#0`，dose 4.00424076271e-06 Gy；fluence 3.10314330351 mm^-2；n_events=2000 |
| 无质量分计分行 | dose/fluence 均只有平行行 |
| 无 ghost 写入 hits | hits 数据行 0 |
| 科学量不变 | dose/fluence/event_edep 与旧 R-RUNTIME 输出逐字节一致；`scorer_statistics.csv` 仅时间/FOM 列不同 |

## 4. 其它验证（未重跑 B/C、未新增物理病例）

- `python -B scripts/test_parallel_world.py`：OK（含 R-RUNTIME 表头断言、R-SAME、Case M 多线程
  生命周期、默认关闭、box/grid/别名、Stage A/B、r1–r3 回归）。
- `scripts/test_parallel_scoring_component.py`：OK（21 checks）；`analyze.py --self-test`：20/20。
- 旧 72 项输出、旧分析、旧候选二进制、旧回执全部保留；正式批次未重跑。

## 5. 边界

- 修复文件仅：`include/src ParallelWorld/ParallelScoringDetector.hh/.cc`、局部 `analyze.py`
  两处、既有 `scripts/test_parallel_world.py` R-RUNTIME 断言、`docs/并行世界计分.md`、
  `docs/输出数据契约.md`；manifest/prepare/runner/18 输入未改。
- 未改产品其它代码、schema、GUI、固定合同/清单、CURRENT/ROADMAP/H8；未提交 Git。
- H3-4 仍未通过；R-RUNTIME 旧输出的字面缺口保留，待主审对旧批次与本修复候选的裁定。
- 证据与最小 diff：`out/collab/20261107-h3-empty-hits-fix/`（`fix/*.diff`、`identities.json`、
  `README.md`、`runs/R_RUNTIME_new/`、`corrected-analysis-20261107/`、`logs/`）。

停写等待独立评审。
