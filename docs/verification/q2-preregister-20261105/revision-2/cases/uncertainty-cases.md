# 统计不确定度病例（C 组，Q2-4 预注册草案）

本文件只做预注册设计；不运行、不改产品/测试/CI。所有病例的 seed/events/判据在此冻结，
Q2-4 执行时不得临时放宽。数据口径与公式依据见 `quantities.md` §5、`docs/输出数据契约.md`。

## 关键约束（先记）

1. `let_volume_summary*.csv` **已经输出 delta 法所需的全部矩**（`src/Scoring/LETScorer.cc:150-153`）：
   `sum_wl_mm`、`sum_wSl_MeV`、`sum_wS2l_MeV2_per_mm`、`sum_sq_wl_mm2`、`sum_sq_wSl_MeV2`、
   `sum_sq_wS2l_MeV4_per_mm2`、`sum_wl_x_wSl_MeV_mm`、`sum_wSl_x_wS2l_MeV3_per_mm`、`n_events`。
   因此 `let_t`/`let_d` 的 delta 比值误差**可以从公共输出独立重算**，不需要新增 CSV 列；
   `scorer_statistics` 的 ratio 行不写这些和，只作为被核对对象（见 UNC-RATIO-01）。
2. 比值误差公式与消费者：`HistoryStatistics::RatioRelativeError()`（`src/Scoring/HistoryStatistics.cc`）
   实现 `R²=S2_A/A²+S2_B/B²−2Σab/(A·B)`（`uncorrected_delta_ratio_v1`，与 V-01 契约一致；
   不另乘或除 N）。`OutputManager::WriteScorerStatisticsCsv`（`src/Output/OutputManager.cc:288-329`）
   把 `rel_error=sqrt(max(0,R²))` 写入 ratio 行。
3. `hits_*.csv` v3 不含 `LETstep`/`NIEL`，因此 LET 的绝对 S 与 DDD 的逐 step 折积仍无法从 hits
   独立重算（这是本组不覆盖的部分，不是 delta 误差的阻塞）。
4. N 一律取 `run_metadata.json` 的 `runs[].completed_events`（含零贡献事件）；`entries` 只计
   非零贡献事件；`n_events` 同 N。零贡献事件进入 N，不进入 S/S2/entries。
5. 任何 `insufficient_events`/`zero_total`/`undefined_ratio` 均不得当成“误差 0”参与通过判定。

## UNC-TOT-01 总量公式的精确复核（可独立重算）

- 目的：验证 `R²=S2/S²−1/N`、`entries` 与 `n_events` 语义；发现把 entries 当 N、把
  S2 少乘或未扣除等错误。
- 输入：复用 REF-DOSE-01 的 10 MeV 质子病例配置（geometry/source/physics/cut 相同），但：
  `events = 20`、`threads = 1`、`seed = 20261120`，`dose = true`、`event_edep = true`、`hits = false`。
- 独立重算：脚本读取 `event_edep_t*.csv` 的全部事件行（N=20，含零沉积行，若该输出记录零事件
  则直接使用；若只记录非零事件，改用 REF-DOSE-01 的 hits 方案并记录此差异），按体积求和得
  每事件 `x_i`（MeV），再从几何算 `mass`，得 `x_i^Gy`；计算 `S=Σx`、`S2=Σx²`、`entries=#{x>0}`、
  `R²=S2/S²−1/N`、`rel_error=sqrt(max(0,R²))`，与 `scorer_statistics` 的 sum/sum_sq/entries/
  n_events/rel_error 比较：**相对容差 1e-12**（同一事件集合的算术恒等，允许浮点舍入）。
- 判据：全部字段一致才通过；任一不一致保留原始差异并判失败。
- 能发现：entries/N 混用、S2 与 S 比例错误、edep 未换算单位；不能发现：物理参考偏差。

## UNC-TOT-02 N<2 与零贡献状态

- 目的：验证 `insufficient_events`/`zero_total` 状态与“不可用值保留 0”的语义，防止把 0 当成功。
- 输入 A：与 UNC-TOT-01 同配置，`events = 1`、`seed = 20261121`。预期：
  `n_events=1`，`uncertainty_status=insufficient_events`，`rel_error=0`，`value=sum`（仍保留数值）。
- 输入 B：同配置但源瞄准敏感体之外（例如 `center = 0,0,-1 mm` 不变、把 Slab 换成 2×2×0.02 mm
  的极小块并保持束流，`events = 100`、`seed = 20261122`），使全部事件零沉积。预期：
  `entries=0`、`n_events=100`，总量状态 `zero_total`，value=0，rel_error=0；
  **不得**把该行当作“剂量为 0 ± 0”的物理结论，报告中必须注明状态。
- 判据：state 字符串与 n_events/entries 完全匹配；任何 NaN/Inf 判失败。

## UNC-RATIO-01 LET 比值 delta 法（可从公共输出独立重算）

- 目的：验证 `uncorrected_delta_ratio_v1` 的数值与状态；发现分子/分母交换、矩错配、
  entries/N 误用。
- 输入：REF-LET-01 的 100 MeV 质子病例，`events=2000`、`threads=1`、`seed=20261123`；
  scoring `let=true`、`particles=proton`、`hits=true`。
- 独立重算（全部来自 `let_volume_summary*.csv` 同一行，无需新增字段）：
  - `let_t = sum_wSl / sum_wl`（A=sum_wSl、B=sum_wl）；
    `R_t² = sum_sq_wSl/A² + sum_sq_wl/B² − 2·sum_wl_x_wSl/(A·B)`，
    `rel_t = sqrt(max(0,R_t²))`；
  - `let_d = sum_wS2l / sum_wSl`（A=sum_wS2l、B=sum_wSl）；
    `R_d² = sum_sq_wS2l/A² + sum_sq_wSl/B² − 2·sum_wSl_x_wS2l/(A·B)`，
    `rel_d = sqrt(max(0,R_d²))`；
  - 与 `scorer_statistics` 的 `let_t`/`let_d` 行比较：`value` 相对 1e-12、
    `rel_error` 绝对 `max(1e-12, 1e-9·rel)`；`estimator=ratio`、
    `uncertainty_estimator=uncorrected_delta_ratio_v1`、`n_events` 与 run 事件数一致、
    `entries>0`。
  - 四线程/多 run 合并时只对 sum/sum_sq/交叉项求和（不平均 rel_error），N 取各 run 合计。
- 边界：`sum_wl=0`（例如源换成 gamma）→ `undefined_ratio`/行缺失；`N<2` → `insufficient_events`；
  `entries=0` 不得显示有效误差；value=0 保留但必须写状态。
- 判据：value/rel_error/status 全部一致（容差如上）；任何 NaN/Inf 判失败。
- 能发现：delta 公式实现错、交叉项符号错、N 用法错、比值定义（track vs dose）混用；
  不能发现：G4EmCalculator 与 PSTAR 的系统差（属 REF-LET-01），也不能验证 hits 层的逐 step S。

## UNC-SPARSE-01 多线程稀疏合并

- 目的：验证 MT 下 N 与 entries 的分布、sum 的可加性；发现把平均 rel_error 或按线程平均
  合并的错误。
- 输入：REF-DOSE-01 的 10 MeV 病例但 `events = 5`、`threads = 4`、`seed = 20261124`；
  `dose=true`、`hits=true`。
- 独立重算：从 `hits_t0..t3.csv` 按 run/volume 汇总 Σedep 与 Σedep²（hits 无 per-event 分组时，
  按 `runID,eventID` 分组重建每事件 x_i；若同一 event 跨线程分片则合并同键）；得 S/S2/entries/N；
  与 `scorer_statistics` 的 sum/sum_sq/entries 比较（1e-12）；N 与 `run_metadata.json` 一致。
- 判据：合计值/entries/N 全一致；若线程间 eventID 分配不可恢复，则记录“不可恢复”并降级为
  “仅核对合计与 N，entries 上限 ≤N”，不得静默通过。
- 能发现：用线程平均代替求和、N 用 threads 事件数、零事件泄漏到 entries。

## UNC-ZERO-DEN-01 零分母与 N<2 的比值边界

- 目的：覆盖 `undefined_ratio`/`NaN`/`0` 语义。
- 输入 A：REF-LET-01 配置但源换 `gamma`（无带电步）→ `sum_wl=0`，检查 let 行状态。
- 输入 B：LET 配置 `events=1` → ratio 的 N<2 状态（`insufficient_events`）与 value 语义。
- 判据：状态字符串与 contract 一致；不得输出 NaN/Inf；value=0 时报告中必须写状态与原因。
  具体期望（row 是否缺失 vs 写 undefined）在冻结前用小规模试运行确认并写回本文件；
  试运行本身也属 Q2-4 执行，需在独审通过后进行。

## 复用与边界

- 已有 `scripts/test_statistical_uncertainty.py`（20 个独立 run 的 1.04–1.25 实测/报告比、
  hits 独立重算）可作为“实现自洽”既有证据，但**不能替代**本组的预注册种子批次与 MT 合并复核。
- 本组不验证加权/偏置下的方差；那属 `biasing-cases.md`。重尾 LET_d 覆盖不足属已知缺口，
  UNC-RATIO-01 只覆盖单能质子薄层，不声称覆盖重尾谱。
