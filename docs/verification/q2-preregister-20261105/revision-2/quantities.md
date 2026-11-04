# Q2-1 四量定义（消费者 / 单位 / 归一化 / 权重 / 输出列）

本文件逐量记录“当前实现实际计算什么”，每个结论都给消费者位置。定义以源码为准，
不以历史文档或类名推断；矩阵等级只说明现有验证范围（见 docs/功能支持矩阵.md）。

通用约定：
- 事件计数 N 一律取 `G4Run::GetNumberOfEvent()`（含零贡献事件），见 `docs/输出数据契约.md:171`。
- 逐事件统计量 `x_i` 在 `HistoryStatistics::Close()` 才结算：`entries` 只累计非零贡献事件，
  `n_events` 仍是完整 N。总量 rel_error = sqrt(max(0, S2/S² − 1/N))（`src/Scoring/HistoryStatistics.cc:49-51`）。
- 比值量用一阶 delta 方法：R² = S2_B/B² + S2_A/A² − 2·Σab/(A·B)（`HistoryStatistics::RatioRelativeError`）。
- 已发布 CSV 的 ratio 行 **不写 sum/sum_sq**（`src/Output/OutputManager.cc:288-329` 只在 `!e.ratio`
  分支填 sum/sumSq），因此仅凭 `scorer_statistics*.csv` 无法反算 delta 交叉项；Q2-4 若要求
  独立复核比值误差，需要新增可核验输出（见 cases/uncertainty-cases.md 的数据需求）。
- 所有量只描述“本次运行抽样波动”，不包含截面/材料/NIEL 模型等系统误差
  （`docs/输出数据契约.md:180`）。

## 1. 吸收剂量 Dose（Gy）

| 项 | 内容 | 位置 |
| --- | --- | --- |
| 消费者 | `DoseScorer` | `src/Scoring/DoseScorer.cc` |
| 逐事件贡献 | 同一敏感 physical touchable 的 `x_i = Σ_steps edep_i [MeV]`；跳步条件 `hit.edep == 0`（`ScoreHit` 首行） | `DoseScorer.cc:40-42,46-66` |
| 本体归一化 | 质量 `doseMass = logical->GetMass(true, false, preStepMaterial)`（扣除 daughters、用步前材料）；同一 path 质量变化超过 `1e-9*volume.mass` 直接抛错 | `include/Scoring/DoseContext.hh` `PopulateDoseContext`；`DoseScorer.cc:54-57` |
| 单位换算 | `gyPerEdep = 1.0 / joule / (mass / kg)`；`value_Gy = Σedep · gyPerEdep`（CLHEP 能量/质量单位常量） | `DoseScorer.cc:72-79` |
| 权重 | `weightedEdep += edep * hit.weight`；raw 与 weighted 分别提交 | `DoseScorer.cc:59-60` |
| 输出列 | `dose_volume_summary_tN[_rR].csv`：runID,volume_path,volume_name,mass_kg,raw_edep_MeV,weighted_edep_MeV,raw_dose_Gy,weighted_dose_Gy,raw_edep_sum_sq_MeV2,weighted_edep_sum_sq_MeV2,n_events；统计行 scorer=dose, quantity=raw_dose/weighted_dose | `DoseScorer.cc:96-107`；`OutputManager.cc:288-329` |
| 交叉验证 | 与 Geant4 原生 `doseDeposit` 相对差 <1e-9（同源自洽，不是独立物理参考，矩阵 `:158`） | `docs/功能支持矩阵.md` |
| 错误可发现性（本案设计目标） | 若对同一体积把质量重复乘两次或把体积当质量，`REF-DOSE-01/REF-GEOM-01` 用“独立几何质量 + 逐事件 edep 重算”可发现；若仅拿 rel_error 或 Dose 数值互比无法发现 | cases/reference-cases.md |

## 2. 注量 Fluence（mm^-2）

| 项 | 内容 | 位置 |
| --- | --- | --- |
| 消费者 | `FluenceScorer`（仅 track-length 定义）；配置要求默认 scorer + 敏感体 | `src/Scoring/FluenceScorer.cc` |
| 逐事件贡献 | `x_i = Σ_steps stepLength_mm`；跳过零步长；要求非空 path 与有限正 volume | `FluenceScorer.cc:50-66` |
| 本体归一化 | `fluenceVolume = logical->GetSolid()->GetCubicVolume()`，**仅当** `logical->GetNoDaughters()==0`；有 daughter 的敏感体为 0 → hit 被跳过 | `include/Scoring/DoseContext.hh` |
| 单位 | `fluence = track_length_mm / volume_mm3`，unit `"mm-2"` | `FluenceScorer.cc:81-85` |
| 权重 | `weightedLength += stepLength * hit.weight` | `FluenceScorer.cc:65-66` |
| 输出列 | `fluence_volume_summary_tN[_rR].csv`：runID,volume_path,volume_name,volume_mm3,raw_track_length_mm,weighted_track_length_mm,raw_fluence_mm-2,weighted_fluence_mm-2,raw_track_length_sum_sq_mm2,weighted_track_length_sum_sq_mm2,n_events；统计行 quantity=raw_fluence/weighted_fluence | `FluenceScorer.cc:93-113` |
| 交叉验证 | 与 Geant4 原生 `cellFlux` 相对差 <1e-9（同源，不是独立参考） | 矩阵 `:161` |
| 可发现性 | `REF-FLU-01` 用“单位面积穿过注量 = N/A”与独立几何体积重算可发现重复体积/面积因子 | cases/reference-cases.md |

## 3. 线性能量转移 LET（keV/um）

| 项 | 内容 | 位置 |
| --- | --- | --- |
| 消费者 | `LETScorer`；配置开启见 `docs/中文使用手册.md:528-545` | `src/Scoring/LETScorer.cc` |
| 逐事件贡献 | 对每个“正 LET 步”（非中性、有阻止本领、步长>0、权重>0）累计 `wl=w·l`、`wSl=w·l·S`、`wS2l=w·l·S²`；`S = LETstep/(MeV/mm)` 来自 `G4EmCalculator::ComputeElectronicDEDX(meanKineticEnergy, particle, preStepMaterial)`（步前材料、pre/post KE 均值，仅电子阻止本领） | `src/Hits/SensitiveDetector.cc:286-300`；`LETScorer.cc:55,106-114` |
| 粒子过滤 | `[scoring.let] particles = all`（默认全部带电）或逗号分隔粒子名；空集即 all_charged | `src/Scoring/ScoringManager.cc:763-780`；手册 `:536` |
| 定义 | track-averaged `LET_t = ΣwSl / Σwl`；dose-averaged `LET_d = ΣwS2l / ΣwSl`，unit `keV/um` | `LETScorer.cc:112-114`；手册 `:543` |
| 输出列 | `let_volume_summary_tN[_rR].csv`：…,particles,steps,sum_wl_mm,sum_wSl_MeV,sum_wS2l_MeV2_per_mm,let_t_keV_per_um,let_d_keV_per_um,sum_sq_wl_mm2,sum_sq_wSl_MeV2,sum_sq_wS2l_MeV4_per_mm2,sum_wl_x_wSl_MeV_mm,sum_wSl_x_wS2l_MeV3_per_mm,n_events；统计行 quantity=let_t/let_d（ratio） | `LETScorer.cc:121-138` |
| 现有验证 | 20 µm 水层 100 MeV/10 MeV 质子 LET_t 与 Bethe(I=75 eV) 差 0.6%/1.4%，与 PSTAR 约 1%（历史声明，需按本提案重新预注册）；`scripts/test_let_scoring.py` 覆盖实现；重离子/厚靶未验 | 手册 `:543`；矩阵 |
| 可发现性 | `REF-LET-01` 用外部 PSTAR 电子阻止本领与独立几何核对，可发现 LETstep 用错材料/能量、分子分母错配套；仅看 let_t/let_d 互比不能证明物理 | cases/reference-cases.md |

## 4. 位移损伤剂量 DDD（MeV/g）

| 项 | 内容 | 位置 |
| --- | --- | --- |
| 消费者 | `DisplacementScorer` + `NielTable`；按粒子名绑定表（`--niel 粒子=表.csv`） | `src/Scoring/DisplacementScorer.cc`、`src/Scoring/NielTable.cc` |
| 逐事件贡献 | `lengthMm = weight * stepLength/mm`；`NIEL = Evaluate(meanKineticEnergy)`（step 前/后 KE 平均）；`ddd_i = lengthMm * NIEL * 100 / (volume_mm3)`（MeV/g） | `DisplacementScorer.cc:60-90` |
| 能域 | 区间外 `Evaluate` 返回 false，长度计入 `out_of_range_track_length_mm`（不计入 ddd） | `NielTable.cc:52-61,67` |
| 本体归一化 | daughter-free 敏感体的 `GetCubicVolume()`；含 daughter 则跳过 | `DoseContext.hh` |
| 权重 | 已含在 `lengthMm = weight*stepLength`；注量加权与高度加权不混同 | `DisplacementScorer.cc` |
| 输出列 | `displacement_volume_summary_tN[_rR].csv`：runID,volume_path,volume_name,particle,niel_table,volume_mm3,track_length_mm,out_of_range_track_length_mm,ddd_MeV_g,ddd_sum_sq_MeV2_g2,n_events；统计行 quantity=ddd_total / ddd_<particle>（key=volume path） | `DisplacementScorer.cc:90-102` |
| 参考边界 | `device_dose` 的 DDD 只检验“注量 × 折积实现”，表本身未独立验证；NIEL 是模型量 | `scenarios/benchmarks/device_dose/README.md:6`；`scenarios/semiconductor/niel/README.md:17` |
| 可发现性 | `REF-DDD-01` 用 NIEL 表值 × 独立长度/体积；`REF-DDD-02` 用 ASTM E722-19 的 1 MeV 值核对表本身（表级审计，不是 scorer 折积） | cases/reference-cases.md |

## 5. 统计不确定度与输出契约（Q2-4 依据）

| 项 | 内容 | 位置 |
| --- | --- | --- |
| 总量 | `R² = S2/S² − 1/N`；`R=NaN` 当 N<2/零总量；状态 `approximate/insufficient_events/zero_total` | `HistoryStatistics.cc:49-51`；`docs/输出数据契约.md:159-171` |
| 比值 | delta 法；状态 `undefined_ratio`（分母为 0）；比值不可用时 value=0 是兼容哨兵，不得解释为“零不确定度” | `HistoryStatistics.cc:70-120`；契约 `:174` |
| 合并 | 先按 `(scorer,quantity,key)` 求和所有 `sum`/`sum_sq`/`den`/`cross`/`entries`，N 取 run_metadata 的 `runs[].completed_events`，禁止平均 rel_error | 契约 `:171`；`OutputManager.cc:288-329` |

> **LET 比值误差可复算**：`let_volume_summary*.csv` 已输出 `sum_wl/sum_wSl/sum_wS2l`、
> `sum_sq_wl/sum_sq_wSl/sum_sq_wS2l`、`sum_wl_x_wSl`、`sum_wSl_x_wS2l` 与 `n_events`
> （`src/Scoring/LETScorer.cc:150-153`），因此 `let_t`/`let_d` 的 delta 比值误差可从公共 CSV
> 独立重算（公式与判据见 `cases/uncertainty-cases.md` 的 UNC-RATIO-01）；无需新增
> `scorer_statistics` 列。零贡献事件仍进入 N，不进入 S/S2/entries。
| 统计 vs 系统 | scorer_statistics 只含抽样波动；截面/材料/NIEL 模型误差不在其中 | 契约 `:180` |
| 已验证 | `test_statistical_uncertainty.py` 与 hits 独立重算一致；20 次独立 run 实测/报告比 1.04–1.25、1/√N 成立；偏置/加权与重尾 LET_d 未验证 | 矩阵；测试脚本 |
| 数据缺口 | 公共 CSV 无法核对 ratio 的交叉项与 entries/权重的完整参与集（ratio 行不写 sum/sumSq；hits v3 不输出 LETstep） | Q2-4 cases 的数据需求 |

## 6. 权重 / 归一化语义汇总

- `hit.weight` 来自 GPS 权重（若无权重机制则 1.0）；Geant4 的 `TrackWeight()` 由 `G4Track` 传入（`SensitiveDetector` 构造 `HitRecord.weight`）。
- Dose 与 Fluence 的 weighted 列是**线性权重**（`x·w`）；LET 的权重同时出现在分子分母（`ΣwSl/Σwl`，比值对共同权因子有抵消性，但会改变步的权重分布）。
- DDD 的 `lengthMm = weight*stepLength` 把权重当作径迹长度缩放，与注量加权等价（薄靶极限）。
- 任何“重复乘质量/体积/权重”的错误，只有在独立重算中使用**不同来源**的几何/权重时才能被发现；用同一实现的两列互除（如 raw_dose 与 weighted_dose）只能发现线性系数差 2 之类错误，不能证明绝对正确。这正是 cases 设计的原则。

## 7. 本文件未覆盖（明确记录）

- XS biasing 的加权是否无偏：见 cases/biasing-cases.md（本轮只设计，不实施）。
- 探测器响应、Bragg 峰、CSDA、gamma 衰减的参考：见 references/ 与 raw/benchmarks-and-contracts.md。
- NIEL 表本身的独立来源核验：见 references/ 与 cases/reference-cases.md 中 REF-DDD-02 的表级审计方案。
