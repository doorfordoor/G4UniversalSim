# Q2-1 现有验证覆盖盘点：dose / fluence / LET / DDD / 统计不确定度 / 偏置 / 物理基准

> 用途：给 Q2-1「参考值与用例提案」提供**可引用的既有证据清单**，避免把"自测通过"当成"物理已验证"。
> 方法：只读仓库（源码、测试脚本、归档 README、参考表），**未运行任何 Geant4 模拟、未执行任何测试脚本**。
> 因此本文中的"断言"指测试脚本**代码里写明的**断言与阈值；"归档结果"指对应 `docs/verification/*/README.md` 自报的结果。
> 生成时间：2026-11-05；工作区 `HEAD=556524227c04c8b100c9035cbf29cf911c30b20f`（`docs(Q2): ...`，纯文档提交）。

---

## 0. 结论速览

1. **四个量都有"实现 + 公式自洽 + 同源交叉"的完整链路，但"独立外部参考"只覆盖 dose 和 DDD 的一部分**：
   - dose：仅 `device_dose` 基准用 NIST PSTAR 硅电子阻止本领检验 **TID/注量**（EM-only、δ 电子平衡、10–200 MeV 质子）；无绝对剂量、无时间/源强归一化基准。
   - DDD：`device_dose` 用 SR-NIEL 硅表检验**注量×NIEL 折积**；NIEL 数据本身（SR-NIEL 模型、仅硅）未独立验证。
   - fluence：**没有外部基准**；只有 geantino 解析几何（12 mm/100 mm³→0.12 mm⁻²）与 Geant4 原生 `cellFlux` 的同源对照（<1e-9）。
   - LET：只有**解析 Bethe**（I=75 eV）在 20 µm 水、10/100 MeV 质子、2 % 容差下的对照；无重离子、无厚靶能谱基准。
2. **统计不确定度**：`uncorrected_event_moments_v1` / `uncorrected_delta_ratio_v1` 是**未作有限样本校正**的事件矩近似；测试只断言"独立重算一致"与"20 次 run 的离散/报告误差落在 1/1.5–1.5 倍"以及"池化后 ~√20"，**不构成覆盖率（coverage）验证**。
3. **偏置**：process-level 截面偏置有 worker 级执行/收据/权重非单位证据，但**没有任何 biased-vs-analog 的无偏性或方差缩减测试**；`biasing_effect_observed` 恒为 `unknown`。归档中 `5465dbd` 时期的偏置/权重证据早于 R-09 修复，不可复用。
4. **基准**：`run_benchmarks.py` 共 6 个包、完整模式 39 个 case、`--quick` 24 个 case；容差公式为 `allowed = tolerance·|ref| + 3σ`（`scripts/run_benchmarks.py:114-119`）。测试套件以 `--quick` 调用且不传 `--output`，**报告写入临时目录随后删除**，仓库内没有可复核的 `benchmark_report.json` 身份。
5. 可引用的**最强身份**是 F2 冻结：`864bc036…` + exe `f8a8119d…` + C++ 指纹 `e7de615d…` + **227 用例（49/78/66/34）** + 12 份云报告 708 用例/255163 断言（`docs/verification/f2-final-20261104/README.md`）。

---

## 1. 身份与判定口径（引用任何证据前先对齐）

| 项 | 当前值 | 说明 |
| --- | --- | --- |
| 工作区 HEAD | `556524227c04c8b100c9035cbf29cf911c30b20f`（2026-11-05） | 该提交只改文档；产品身份沿用 F2 冻结 `864bc036`（`git log` 与 F2 README 对照） |
| 产品冻结（F2） | `864bc036d6d7752475e52db4efd2b950cabfcc3d`，分支 `roadmap/F2-controlled-session` | `docs/verification/f2-final-20261104/README.md` |
| C++ 原始字节指纹 | `e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7` | 同上 |
| Windows Release exe SHA-256 | `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f` | 同上 |
| 用例登记 | **227**（static 49 / gui 78 / backend 66 / integration 34） | 解析 `scripts/run_m0_tests.py` 的 `CASES`（本次只读统计） |
| 云矩阵 | 12 报告 / **708 用例** / **255163 断言** | Linux 11.3.2 与 11.4.3 各 49/78/66/34（5665/10911/92116/6881 与 5665/10911/82948/6881）；M0 Ubuntu 49/78（5665/10911）；M0 Windows 49/78（5668/10941） |
| 报告证据门禁 | `scripts/check_report_evidence.py`；报告 `version=2`；断言探针 `settrace_assert_lines_v3`；日志摘要 `sha256_raw_bytes_lf_v2`；CI 必须 `--fail-on-skip` | `scripts/run_m0_tests.py:33-37,559`；`docs/测试平台说明.md` |

**历史冻结不可混用**（用例数随提交增长）：Q1 = 105（11/31/46/17，83770 断言，代码 `8ecad66a…`，`docs/verification/q1-final-20261029/README.md`）；F1 = 143（48511 断言，产品 `f176d0ed…`，`docs/verification/f1-visible-20261030/README.md`）；F4 = 152；F5 = 160；F2 = 227。**Q2 提案若引用"通过 N 项"，必须同时写死提交与用例数。**

---

## 2. 四个量的现有覆盖

约定：
- **同源（same-source）**＝对照对象来自同一次 Geant4 运行的原生计分（`doseDeposit`/`cellFlux`）或同一批 hits 的重算，能证明"记账/单位/合并一致"，**不证明物理正确**。
- **独立（independent）**＝外部表（PSTAR/ESTAR/XCOM/SR-NIEL/PDG）或解析公式（Bethe/Klein–Nishina），能证明"在该条件下与外部数据一致"。

### 2.1 Dose（吸收剂量 / TID，Gy）

| 实现与单位/公式 | 现有测试/证据（脚本 + 断言要点） | 实际证明了什么 | 未覆盖/缺口 |
| --- | --- | --- | --- |
| `[scoring] dose=true` + `auto_create_default_scorers=true`；按 `(runID, physical touchable path)`（含 copy number）聚合原始/逐 hit 加权 Edep；`dose_Gy = Σ edep_MeV × 1.602176634e-13 / mass_kg`；质量取 `GetMass(true,false,preStepMaterial)`（扣 daughter）。输出 `dose_volume_summary_tN[_rR].csv`（v2 增 `raw/weighted_edep_sum_sq_MeV2, n_events`）。来源：`docs/输出数据契约.md:77,80`；`docs/功能支持矩阵.md:161` | `scripts/test_dose_scoring.py`：表头 11 列；10×10×1 mm 硅解析质量 2.329e-4 kg（rel 1.5 %）；`dose=edep×1.602176634e-13/mass` rel 2e-9；40 事件、单/双线程、两轮；母/子解析质量 0.007 kg 与 0.001/0.01135 kg；parameterised 嵌套 0.007/0.01631；负/零质量 → `status=failed`、`DoseScorer requires a positive Geant4 physical-volume mass`、`output_failure_stage=scoring_dose`；dose 与 LET 共存 | 质量获取与换算在**这些几何**上正确；失败路径可控 | 复杂 daughter/replica 的 `GetMass` 语义未专项验证（`docs/输出数据契约.md:80`）；无绝对剂量/源强/时间归一化 |
| 统计链：每轮 master 写 `scorer_statistics[_rR].csv`，`dose/raw_dose` 与 `dose/weighted_dose` 两行，`key=touchable 路径` | `scripts/test_statistical_uncertainty.py`：10 个 `(scorer,quantity)` 齐备；每行 `n_events==400`；dose `value==Σedep×1.602176634e-13/mass`（rel 1e-9）；`dose rel_error == edep_volume rel_error`（1e-7）；`std_error=value×rel_error`；每 worker 可加列求和后 rel_error 一致（1e-7）；ROOT 经 `g4usim_io` value 1e-8 / rel_error 1e-6；FOM `=1/(R²T)` 1e-6 | 合并与统计口径自洽 | 估计量本身未校正（见 §3） |
| 同源交叉：原生 `/score/quantity/doseDeposit` | `scripts/test_scoring_mesh.py:229-230`：`rel_close(native dose mean, Σ DoseScorer raw_dose_Gy, 1e-9)` | DoseScorer 与 Geant4 原生剂量计分**在同一 run 内一致** | 同源，不是独立参考 |
| 独立参考：`device_dose` 基准（PSTAR Si 电子阻止本领） | `scenarios/benchmarks/device_dose/reference.csv`（`source=PSTAR Si STOP(e)`）；`scripts/run_benchmarks.py:268-307`：`per_fluence = dose/events × 1.44 cm²`，σ=per_fluence×rel_error，容差 TID **2 %**；quick 保留 (tid,10)、(tid,100)、(ddd,p,100)；物理 `em=option4`、cut 10 µm、4000/20000 事件 | 10–200 MeV 质子、δ 电子平衡薄层内 **TID/注量**与 PSTAR 一致（2026-10-22 完整模式 −0.38…+0.14 %，`scenarios/benchmarks/device_dose/README.md`） | 仅硅、仅质子/EM-only、依赖 build-up 平衡假设；SiO₂ 剂量无参考表（矩阵 L140）；不是"任意几何绝对剂量"基准 |
| 加权剂量与权重传播 | `scripts/test_biasing_step_weight.py`：`weighted_edep` vs 原生 `energyDeposit`、`event_edep` vs `dose`、hits 乘积 vs `dose`，容差=12 位有效数字舍入界 + 32·eps 累加界（hits 对比另加 1e-11·|project|）；`--baseline` 复现修复前不匹配 | 步前统计权重在**该偏置算例**中与原生计分一致 | 只测权重乘积，不测加权估计量的方差/协方差 |
| GUI 后处理 | `gui/smoke_tests/smoke_dose_results.py`（用例 `gui_dose_results`，`scripts/run_m0_tests.py:179`）：伪造 worker CSV → 合并、`thread_ids={0,1}`、质量只取一次、6 条坏文件 warning、页面表行数 | 读取/合并/坏文件策略 | 不涉及物理 |

### 2.2 Fluence（注量，mm⁻²）

| 实现与单位/公式 | 现有测试/证据（脚本 + 断言要点） | 实际证明了什么 | 未覆盖/缺口 |
| --- | --- | --- | --- |
| `[scoring] fluence=true`；每 step（**含零 Edep**）累计 `ΣstepLength` 与 `Σ(stepLength×weight)`，除以无 daughter 敏感 solid 体积 → `mm⁻²`；Q1/R29 起权重为**步前统计权重**。输出 `fluence_volume_summary_tN[_rR].csv`（v2 增 `raw/weighted_track_length_sum_sq_mm2, n_events`）。来源：`docs/输出数据契约.md:78,82`；矩阵 L163 | `scripts/test_fluence_scoring.py`：12 事件 geantino 穿 100 mm³ → `raw_track_length_mm≈12.0`（rel 1e-6）、`fluence=length/volume`（rel 2e-9，即 0.12 mm⁻²）；零 Edep 不伪造 hits；2 线程×2 run → 4 个 `dose_volume_summary` 并存；M5 `fluence_json` 导出 `physical_validation="not_established"`、两 run 的 `thread_ids=[0,1]`、跨线程求和 1e-9；关闭 `auto_create_default_scorers` → exit 1 且无文件；说明：`geantino` 支路证明零沉积仍计径迹长度 | 单位、体积分母、零沉积支路、跨线程可加性 | **无外部基准**；仅无 daughter 敏感 solid；非 surface-crossing；复杂复制几何未测 |
| 同源交叉：原生 `/score/quantity/cellFlux` | `scripts/test_scoring_mesh.py:231-232`：`rel_close(native cellFlux mean/100, Σ FluenceScorer raw_fluence_mm-2, 1e-9)`（cm⁻²→mm⁻²） | 与 Geant4 原生 track-length flux 一致 | 同源，不是独立参考 |
| 偏置下注量 | `scripts/test_biasing_step_weight.py`：`weighted_fluence` vs 原生 `cellFlux×0.01`，同一 run、eBrem factor 0.1/1/10、单/双 worker | 步前权重在偏置算例中与原生注量一致 | 只到"权重乘积"层 |
| 统计链 | `scripts/test_statistical_uncertainty.py`：fluence 两行、`n_events==400`、每 worker 可加列 1e-7、批量 20×100 的离散/报告误差比与 √20 池化 | 合并与估计量口径自洽 | 覆盖率未验证 |
| GUI 后处理 | `gui/smoke_tests/smoke_fluence_results.py`（用例 `gui_fluence_results`，`scripts/run_m0_tests.py:194`）：合并、体积只取一次、6 条坏文件、非有限值告警 | 读取/合并/坏文件策略 | 不涉及物理 |

**判定**：FluenceScorer 目前**只有同源交叉 + 解析几何（geantino）+ 权重乘积**三类证据；`run_benchmarks.py` 的 6 个基准包**没有任何一个读取 FluenceScorer**（gamma/屏蔽用的是原生 `[phase_space]`，CSDA 用的是 hits 的 `stepLength`）。这是 Q2 最明确的外部基准空白。

### 2.3 LET（LET_t / LET_d，keV/µm）

| 实现与单位/公式 | 现有测试/证据（脚本 + 断言要点） | 实际证明了什么 | 未覆盖/缺口 |
| --- | --- | --- | --- |
| `[scoring] let=true` + `[scoring.let] particles=<列表>`；在步平均动能处取 `G4EmCalculator::ComputeElectronicDEDX`（非限制电子阻止本领）；累计 `Σw·l`、`Σw·S·l`、`Σw·S²·l`；`LET_t=ΣwSl/Σwl`、`LET_d=ΣwS²l/ΣwSl`；中性粒子与零长步不计，零沉积带电步计入。输出 `let_volume_summary_tN[_rR].csv`。来源：`docs/输出数据契约.md:150`；矩阵 L159 | `scripts/test_let_scoring.py`：20 µm 水、2 线程、seed 31415、300 事件、100/10 MeV 质子；解析 Bethe（I=75 eV、z/A=0.555087、k=0.307075，无壳/密度修正）与步中心能量修正；`|LET_t/Bethe −1| < 0.02`；`LET_d ≥ LET_t(1−1e-12)` 且 `LET_d < 1.05·LET_t`；ROOT `let` ntuple 的 `steps/sum_wl/sum_wSl/sum_wS2l` 与 CSV 求和 1e-9；`particles=all` 步数增加且有限；γ 束 0 步；macro `/AIHL/scoring/let true` 被拒（提示 `main INI [scoring]`） | 薄靶单能质子的 LET_t 与解析 Bethe 在 2 % 内；LET_d 的排序与量级 | 仅质子 10/100 MeV、仅 20 µm 水；无重离子、无厚靶/能谱、无次级电子主导的 LET_d 重尾基准；GUI 至今**禁止生成** LET（矩阵 L196） |
| 统计链（比值估计量） | `scripts/test_statistical_uncertainty.py`：`let/let_t`、`let/let_d` 行 `n_events==400`、`estimator=ratio`、`sum/sum_sq/mean_per_event` 为空；批量 20×100 对两个比值做 `1/1.5 < observed/predicted < 1.5`，**不参与**池化 √20 检查（池化只含 `estimator=total` 的 dose/fluence） | delta 方法合并后与 run 间离散量级一致 | 小样本/重尾/分母接近 0 的覆盖率未验证（Q1 决定与独立审查均保留） |
| 独立参考 | 只有上式解析 Bethe（无外部表文件，公式在测试内）；矩阵 L159 记录 0.55 %/1.4 % 的实测偏差 | 该条件下与 Bethe 一致 | 无 PSTAR/ICRU 表文件化参考，无第二独立来源 |

### 2.4 DDD（位移损伤剂量，MeV/g）

| 实现与单位/公式 | 现有测试/证据（脚本 + 断言要点） | 实际证明了什么 | 未覆盖/缺口 |
| --- | --- | --- | --- |
| `[scoring] displacement=true` + `[scoring.displacement] <粒子>=<NIEL 表>`；对无 daughter 敏感 touchable，按粒子累计径迹长度注量并折积 `DDD=Σ w·l·NIEL(E_mean)/V`（MeV/g）；含零沉积步；每 touchable×粒子一行；表外能量只累计 `out_of_range_track_length_mm` 不进入 DDD；log-log 插值。输出 `displacement_volume_summary_tN[_rR].csv`。来源：`docs/输出数据契约.md:54`；矩阵 L162 | `scripts/test_displacement_damage.py`：1 GeV μ⁻ 穿 1 mm Si、表 `NIEL=2e-6·E`（log-log 精确）→ 径迹长度与 hits 求和 1e-9、DDD 与独立重算 1e-3、`ddd_total/ddd_mu-/sum_sq` 与 CSV 1e-9、`unit=MeV/g`、`n_events=200`；e⁻ 表外能量 → `ddd=0`、`out_of_range≥hits 长度`且 >0；1 MeV 中子穿 100 µm Si（零沉积步）、常表 2e-3 → `DDD=2e-3·100·events/(100·100)`（rel 0.005）；He3 大小写解析 rel 0.02；非法表/表外设置 → 事件前失败（`NIEL must be finite and >= 0`、`[scoring.displacement]/proton` + 文件行号）；ROOT-only 仍写统计 | 折积公式、零沉积路径、表外策略、非法表拒绝、逐 worker/合并一致 | **NIEL 数据本身未验证**；仅硅表；无"位移损伤效应"（如器件退化）基准 |
| 独立参考：`device_dose` DDD/注量 | `reference.csv`（`source=SR-NIEL si_proton.csv / si_neutron.csv`）；`run_benchmarks.py:268-307`，容差 **1 %**；`make_reference.py:29-33,74-88`：`E_mid = R⁻¹(R(E) − ρ(b+t/2)/10)`（PSTAR Si CSDA 反演），`ddd = NIEL(E_mid)`（与 scorer 相同的 log-log 插值）；quick 只留 (ddd,p,100)，完整模式含 p10/p100/n14 | 注量×NIEL 折积与 SR-NIEL 表在 10/100 MeV 质子与 14 MeV 中子上一致（+0.67/−0.22/+0.01 %，`device_dose/README.md`） | 只检验"径迹长度注量与参考表折积"，**不检验 NIEL 数据**（`make_reference.py` docstring 明示） |
| 场景包交叉 | `scenarios/semiconductor/analyze_device.py`；`scripts/test_semiconductor_device.py`：各 substrate slice 的 DDD 与"盖板后能量（PSTAR Al/Si CSDA 反演）处的 SR-NIEL 质子 NIEL"一致，`Φ_eq = DDD / 2.037e-3`（ASTM E722 95 MeV·mb）；`convert_srniel.py` 可重建表 | 分层器件里的 DDD/Φ_eq 折积链 | 同样不验证 NIEL；1 MeV 中子等效注量用的是 ASTM 参考值而非表插值 |
| 数据来源与局限 | `scenarios/semiconductor/niel/README.md`：SR-NIEL 网页计算器（SR-NIEL-7 ver. 11.1，2026-10-22 默认设置）；Si 位移阈能 21 eV；质子 0.1 keV–10 GeV（Hadron+Coulomb，强子不缩放）；电子 0.1 MeV–10 GeV；中子 ASTM E722-19 Table A1.1（1e-10–19.95 MeV 分群中点）；`convert_srniel.py` 在 1 eV 补 0（延续源表零值）；局限：仅硅（氧化层仍按硅表，仅供参考）、NIEL 为模型量、不同文献质子强子部分存在差异、**仓库未独立验证这些表** | 表来源/版本/设置可追溯 | 数据库版本、能量网格、文献差异均未量化 |

---

## 3. 统计与不确定度：估计量、状态、列、断言

### 3.1 定义（`docs/输出数据契约.md:161-171`）

| 项 | 定义 |
| --- | --- |
| 文件 | `scorer_statistics[_rR].csv`（master 每轮写出，**任何 `[output]/format` 都写**，schema `scorer_statistics_csv_v2`） |
| 列顺序 | `runID, scorer, quantity, key, name, unit, estimator, n_events, entries, value, mean_per_event, std_error, rel_error, fom_per_s, run_wall_time_s, sum, sum_sq`，末尾追加 `uncertainty_estimator, uncertainty_status` |
| `estimator=total` | `value=sum`；`mean_per_event=sum/N`；`R = sqrt(sum_sq/sum² − 1/N)`；`std_error = R·|value|`；方法 `uncorrected_event_moments_v1` |
| `estimator=ratio`（LET） | `value=比值`；`R² = Σb²/B² + Σa²/A² − 2Σab/(AB)`；方法 `uncorrected_delta_ratio_v1`；`sum/sum_sq/mean_per_event` 为空 |
| `n_events` / `entries` | `n_events`=本轮完成事件数（含零贡献）；`entries`=有非零贡献的事件数 |
| `fom_per_s` | `1/(R²·T)`，`T`=master 本轮墙钟（`run_wall_time_s`） |
| 状态值 | `approximate`、`insufficient_events`（N<2）、`zero_total`（零总量/分子）、`undefined_ratio`（比值分母为零）；不可用状态的数值 0 只是兼容哨兵 |
| 能力边界 | `docs/功能支持矩阵.md:160`：限"偏置/加权运行与重尾 LET_d 未专门验证"；"证据=同源自洽" |

### 3.2 测试断言（逐项，可作为 Q2 的现状基线）

| 测试/用例 | 场景 | 断言与容差 |
| --- | --- | --- |
| `scripts/test_statistical_uncertainty.py`（`base`） | 200 µm 水、2 线程、`seed=20261022`、10 MeV 质子、400 事件、`format=both`、hits 开 | 10 个 `(scorer,quantity)` 齐备；每行 `n_events==400`；用 hits 按 `(thread,event)` 重算 `sum/sum_sq`（rel 1e-9）、`rel_error`（1e-7）、`entries`=非零事件数；`event_edep` 行数=事件数且 sum/sum_sq/mean 一致；dose `value=Σedep×1.602176634e-13/mass`（1e-9）、`rel_error` 与 `edep_volume` 一致（1e-7）、`std_error=value×rel_error`；dose/fluence 每 worker 可加列求和后 `rel_error` 一致（1e-7）且 `Σn_events==400`；ROOT（`g4usim_io.load_scorer_statistics`）value 1e-8 / rel_error 1e-6 / `n_events==400`；`FOM=1/(R²·wall)`（1e-6），wall>0 |
| 同上（`batches`，**20 次独立 run × 100 事件**，单进程 20 次 `beamOn`，`format=csv`，hits 关） | `dose/raw_dose`、`fluence/raw_fluence`、`let/let_t`、`let/let_d` | 每个 run `n_events==100`；`observed = std(ddof=1)/mean`，`predicted = sqrt(mean(R²))`；**`1/1.5 < observed/predicted < 1.5`**（0.667–1.5，**不是** 1.04–1.25；1.04–1.25 只是矩阵 L160 记录的实测值）；仅两个 `estimator=total` 量做池化：`scaling = predicted/R(pooled 2000)`，**`0.75·√20 < scaling < 1.33·√20`**（3.354–5.949） |
| 同上（`root_only`） | 50 事件、`format=root` | `scorer_statistics.csv` 存在；无 `dose_volume_summary_t*.csv`；含 `let/let_t` 与 `dose/raw_dose`（即 root-only 仍出统计） |
| `scripts/test_dose_scoring.py` | 40 事件、ST/MT、两轮 | v2 表头 11 列；`raw/weighted_edep_sum_sq_MeV2` 与 `n_events` 存在；换算 rel 2e-9；质量 rel 1.5 % |
| `scripts/test_displacement_damage.py` | μ⁻/中子 | `ddd_sum_sq_MeV2_g2` 与 `ddd_total` 对账 1e-9；`n_events=200`；`unit=MeV/g` |
| `scripts/test_fluence_scoring.py` | 2×2 | 每 worker 行 `Σn_events==events`；`fluence=track_length/volume`（2e-9） |
| `scripts/test_scoring_mesh.py` | 2 线程 2 run | mesh CSV `n_events==events`；ROOT 与 CSV `rel_error` 差 <1e-9；`entries` 求和一致；`rel_error` 与 `sqrt(sum_sq/sum²−1/N)` 公式一致 |

### 3.3 方法风险（已由 Q1 决定与独立审查量化）

- `R² = S2/S² − 1/N` **不是无偏样本标准误**：对 i.i.d. 历史，样本均值标准误平方多 `N/(N−1)` 因子；N=2、贡献 1 与 2 时现行 SE≈0.7071，样本方差法=1（`docs/collab/decisions/20261029-q1-uncertainty.md`）。
- 比值（LET）用一阶 delta 法，**小样本与重尾仍可能不足**；`approximate` 状态不等于已验证覆盖率（同上；`docs/verification/independent-uncertainty-5465dbd-20261029/README.md`）。
- 独立审查（提交 `5465dbd`）用 3 个后端进程/4 个 run/12 个事件做了 `finite_sample_two_histories`（0.1/0.3 MeV）、`zero_contribution_history`、`sparse_workers_two_runs`（双 worker、两轮、一个 worker 无敏感体贡献、关闭 `event_edep`），并明确"不宣称统计覆盖率或物理基准验收通过"。
- 测试都用**单一固定 seed**（`20261022`）；20 次 run 是同一进程内连续 `beamOn`，不是 20 个独立进程/独立种子。

---

## 4. 偏置（process-level XS biasing）

### 4.1 支持状态（`docs/功能支持矩阵.md:164-166`）

| 能力 | 状态 | 关键事实 |
| --- | --- | --- |
| process-level 截面偏置 | 部分支持 | 初始化前重绑 macro 物理并按**实际 wrapped process** 校验；按实际 LV 身份冻结共享只读计划；每 worker **私有** operator；`BeginRun` 验证 TLS 绑定；`EndRun` 逐 run/thread 收据且 coverage 必须完整；master 挂接不能充当 worker 证据 |
| legacy particle-level XS 语法 | 部分支持（兼容） | 仅兼容语法，不是新能力 |
| importance / weight window / splitting / Russian roulette | **未支持** | 无运行时实现（矩阵 L166） |
| 明确拒绝 | — | `/run/reinitializeGeometry`（"not safe in this lifecycle"）、`--ui` 下配置/ macro 修改偏置（"XS biasing is not supported in an interactive session"）、初始化后 `addRule` |
| `biasing_effect_observed` | 恒 `unknown` | `src/Core/SimulationManager.cc:702,1473` |

### 4.2 Worker 收据与断言（`scripts/test_biasing_worker_runtime.py`，seed 93，1/2 线程）

| 断言对象 | 期望 | 出处 |
| --- | --- | --- |
| analog（无规则） | 所有 hits `weight==1` | 同上 |
| `factor=1`（中性对照） | 所有 `weight==1`，但 `proposals>0` | 同上 |
| `factor=0.1 / 10`（2 run） | 至少一个 `|weight−1|>1e-8`；每 run `proposals>0` 且 `applied_callbacks>0` | 同上 |
| `min_weight=2` / `max_interactions=0` | 权重全 1，且 `proposals==applied_callbacks==0` | 同上 |
| 薄中子透射（`factor=100`，无 SD） | 4 条 `phase_space` crossing 且 `weight>1`；`proposals>0` | 同上 |
| 收据 | `biasing_worker_coverage_complete=true`；`biasing_worker_evidence_count == biasing_expected_worker_evidence_count == threads×runs`；`biasing_worker_<i>_end_run_completed=true`；`operators==1`；`matched_rules==1`（别名 2）；`tls_verified`；`failed=false`；`(run_id,thread_id)` 集合完整 | 同上 |
| 故障注入 | construct 失败 → `output_failure_stage=biasing_thread_begin`；缺 receipt/缺 end receipt → `biasing_worker_evidence` + `coverage=false` 且计数差 1 或某 `_end_run_completed=false`；溢出/下溢（1e308/1e-300）→ `biasing_cross_section` 且消息含 `factor * analogXS`，**不写** `scorer_statistics` | 同上；`src/Core/SimulationManager.cc:700-720` |
| 脚本自述 | 结尾打印 `PASS (execution only; no unbiasedness/FOM claim)` | 同上 |

其他偏置测试：`scripts/test_biasing_target_contract.py`（20 事件；`biasing_process_match_status=validated`、`matched rule count=1`、`biasing_effect_observed=unknown`；无效 process 在 `/run/initialize` 前失败；2 线程、两 run 2+3、`physicsModified` 重建；`/run/reinitializeGeometry` 与 `--ui` 拒绝）；`scripts/test_effective_biasing.py`（`/biasing/…/application_status=not_applied`；worker 证据 JSON `observed==2`、`tls_verified`、`physical_effect_status="unknown"`；6 条非法命令 → `status=failed`、`macro_failure_code_available=false`、失败行 1、0 完成事件、revision 不变）；`scripts/test_biasing_step_weight.py`（R29 步前权重；4 组同 run 对账；`--baseline` 复现修复前不匹配；结尾 `not a global unbiasedness benchmark`）。

### 4.3 是否测过 biased-vs-analog 的无偏性/方差收益？

**没有。** 证据链只到"算符被真实调用 + 权重非单位 + 收据完整 + 权重乘积与原生计分一致"。

- 独立审查（`docs/collab/reviews/20261029-1314-astra-5465dbd-biasing-weight-review.md`）在 `5465dbd` 上复现了 **R-09：MT worker 未创建/挂接偏置算符**——当时 eIoni factor 0.1/1/10 的 4 事件共 128 条 hits 除 process 名外逐行相同、权重全为 1；薄中子 factor=100 也全为 1；`event_edep` 与 analog 字节相同。Q1 阶段的后续实现（`4ed7233`、`cb54669`、`5ffe9b6`、`8ecad66`）补上了 worker 线程私有算符与步前权重，但**该历史说明：任何早于 Q1 的偏置/权重归档都不能作为"偏置生效"证据**（`docs/verification/q1-final-20261029/README.md` 的限制段亦明确"调用收据/原生同 run 对照不证明无偏性、方差收益"）。
- 审查建议的验收组合是"worker 挂接证据 + 实际 operation 调用/权重变化证据 + **独立 biased/analog 或解析验证**"；仓库目前只有前两项。审查同时给出一个可解析检验的非相互作用生存权重关系：`w_out/w_in = exp[(f−1)·Σ_elastic·L]`（f=100、Σ>0、L>0 时不应恒为 1）——这是 Q2 可预注册的解析路径之一，**仓库尚未实现该断言**。
- 独立归档 `docs/verification/independent-biasing-weight-5465dbd-20261029/`（16 进程/15 完成/16 run/70 事件/324 文件 1,903,172 字节）只证明"恒定历史权重的传播与聚合"（`weights_one/var/three`，N=4 时 `rel_error=0.390700016426` 为公式核对），并明确"没有宣称完整偏置物理、动态权重估计量、方差缩减性能"。

---

## 5. 物理基准（`scripts/run_benchmarks.py` + `scenarios/benchmarks/*`）

### 5.1 用例、参考与容差（当前编码）

| 基准包 | 量（单位） | 参考数据/版本（`reference.csv` 的 `source` 列） | 容差（代码） | quick 用例/事件 | 完整用例/事件 |
| --- | --- | --- | --- | --- | --- |
| `csda_range` | 水中 CSDA 射程（g/cm²） | NIST PSTAR（质子）/ESTAR（电子），水 I=75 eV | 质子 1.5 %，电子 3 %（`:146`） | 5 例（p10/100/200，e⁻1/10；各 p 200、e⁻300 事件） | 7 例（p 200/1000，e⁻ 300/2000 事件） |
| `bragg_peak` | 150 MeV 质子 R80（mm） | PSTAR CSDA × 迂回因子 0.998（Bortfeld 1997） | 1 %，σ 硬编码 **0.1 mm**（`:183`） | 1 例，1000 事件 | 1 例，5000 事件 |
| `gamma_attenuation` | 窄束 μ/ρ（cm²/g） | NIST XCOM 总截面（含相干） | 2 %（`:213`），σ 由二项传播 | 6 例，各 4000 事件 | 6 例，各 20000 事件 |
| `shielding_range`（csda） | Al/Si 中 CSDA（g/cm²） | PSTAR/ESTAR（`nist/` 原表） | 质子 1.5 %，电子 3 %（`:242`） | 4 例（Al/Si 的 p100 与 e⁻1；p 150、e⁻ 300 事件） | 7 例（p 1000、e⁻ 2000 事件） |
| `shielding_range`（residual） | 穿板平均能量（MeV） | PSTAR CSDA 反演 `R(E)−t` 的 log-log 反插 | 1 %（`:258`），σ=样本标准误；**要求 ≥99 % 质子穿出**否则 `RuntimeError` | 2 例（Al 50/5 mm、Si 30/2 mm；各 300 事件） | 4 例，各 2000 事件 |
| `device_dose` | TID/注量（Gy·cm²）、DDD/注量（MeV·cm²/g） | PSTAR Si `STOP(e)` × `1.602176634e-10`；SR-NIEL `si_proton.csv`/`si_neutron.csv` | TID 2 %、DDD 1 %（`:300`） | 3 例（tid p10、tid p100、ddd p100；各 4000 事件） | 7 例（各 20000 事件） |
| `detector_response` | 康普顿边/逃逸峰（MeV）、Landau MPV（MeV） | Klein–Nishina；`E−mₑc²`/`E−2mₑc²`；PDG Landau–Vavilov–Bichsel Eq. 34.12 | 边 1 %、逃逸 1 keV（`tolerance=0.0` + 1 keV 峰值定位）、MPV 3 %（`:345-356`）；σ=0.001/√12 | 3 例（边 0.662、单逃逸 4.44、MPV 4000；Si 40000 / γ 30000 事件） | 7 例（Si 200000 / γ 100000 事件） |

- **合计**：完整 39 例（`reference.csv` 行数 7+1+6+11+7+7），`--quick` 24 例（5+1+6+6+3+3）。quick 的裁剪是**不对称的**：`device_dose` 丢掉 ddd p10 与 ddd n14，`shielding_range` 只留 p100/e⁻1 与两种厚度，`csda_range` 的 e⁻10 因能量集合巧合被保留。
- 判定公式：`allowed = tolerance·|expected| + 3.0·sigma`，`passed = |expected−observed| ≤ allowed`（`scripts/run_benchmarks.py:114-119`）；`sigma` 来源按包不同（样本标准误 / 二项传播 / 硬编码 0.1 mm / 1 keV·12⁻⁰·⁵ / `per_fluence×rel_error`）。
- 物理列表：csda/shielding `em=option4`；bragg `QGSP_BIC_EMZ`；gamma `FTFP_BERT_EMZ`；device TID `em=option4`、DDD 质子亦 `em=option4`、中子 `QGSP_BIC_HP`；cut 默认 0.7 mm，device 10 µm。
- 参考生成：`scenarios/benchmarks/device_dose/make_reference.py`（`RHO_SI=2.33`、`GY_PER_MEV_G=1.602176634e-10`，`:29-30`；`CASES` 7 条 `:33`；PSTAR Si 取 col0 E/col1 STOP(e)/col4 CSDA `:74`；`E_mid` `:80-81`；`tid` `:85`；`ddd` `:88`；docstring 明示"NIEL 数据本身不验证"）。其余 5 包为**静态 `reference.csv`**（含 `source` 列），由各包 README 记录来源与 2026-10-22 完整模式结果。

### 5.2 运行方式、seed 与可复核性

| 项 | 事实 |
| --- | --- |
| 套件调用 | `Case("benchmarks", "scripts/run_benchmarks.py", "backend", ("exe",), args=("--quick",))`（`scripts/run_m0_tests.py:255`）→ `python -B scripts/run_benchmarks.py --quick` |
| 报告落盘 | 不传 `--output` 时写 `<temp>/report/benchmark_report.{json,md}`，`finally` 中 `shutil.rmtree(work)`；**套件运行结束不保留报告**（`scripts/run_benchmarks.py:408,431-434`） |
| 失败语义 | 跑完全部用例、写报告，再以含 `name/case/quantity/deviation/allowed` 的 `AssertionError` 非零退出（`:426-431`）；返回码 = `failed==0 ? 0 : 1` |
| seed | 每个用例一次 run，`seed = 1000 + backend.count`（`:94`）；detector_response 生成器另用 `--seed 1000+count`（`:332`）；**无固定全局 seed、无 RNG 状态导出/恢复** |
| 线程 | `--threads` 默认 4（`:397`），套件未覆盖，故 quick 用 4 线程 |

### 5.3 已记录的完整模式结果（2026-10-22，4 线程，Geant4 11.3.2，`scenarios/benchmarks/README.md`）

`device_dose`（20000 事件/例）：TID p10 −0.38 %、p50 −0.28 %、p100 +0.14 %、p200 −0.16 %；DDD p10 +0.67 %（1.5σ，统计误差 0.46 %）、p100 −0.22 %、n14 +0.01 %。其余 5 包同日全部通过（README 表格）。

### 5.4 基准层的已知编码限制

1. **不覆盖 FluenceScorer 与 LET scorer**：6 个包没有读取 `fluence_volume_summary` 或 `let_volume_summary`；gamma/屏蔽用的是原生 `[phase_space]`。
2. **报告不作为归档证据**：套件调用没有 `--output`，仓库内只有 README 表格，没有可复核的 `benchmark_report.json` 身份/日志 SHA。
3. **σ 的口径不统一**：bragg 硬编码 0.1 mm、detector 用 1 keV/√12、device 用 `per_fluence×rel_error`；`3σ` 与系统容差混用，`allowed` 不是置信区间声明。
4. **quick 覆盖不对称**：24/39 用例、事件数下调 5–10 倍，device 的 ddd n14 与 p10 不在 quick 内。
5. **参考表与代码分离**：除 device_dose 外，参考值不在仓库内可重算（无生成脚本、无上游原始表以外的版本锁）；`source` 列是自由文本。

---

## 6. 可复用证据（无需重跑即可引用）

| 路径/身份 | 覆盖 | 可直接引用的事实 | 范围与限制 |
| --- | --- | --- | --- |
| `docs/verification/f2-final-20261104/README.md` | 当前产品身份 + 全量矩阵 | `864bc036…`、C++ 指纹 `e7de615d…`、exe `f8a8119d…`、227 用例（49/78/66/34）、12 报告 708 用例/255163 断言、云 run 41820515533/41820515013/41820515045/41820515620 | 工程验收；明确"工程一致性检查不等于科学物理基准验证"；重放只对固定构建/数据/随机初态/线程成立 |
| `docs/verification/q1-final-20261029/README.md` | Q1 数值/统计/偏置生命周期 | `8ecad66a…`、105 用例（11/31/46/17）、83770 断言、Windows/Linux(11.3.2/11.4.3) 各 105、exe `688f1a45…`、源码指纹 `d9c4378a…`、测试指纹 `5bcb7ac1…` | 明确"调用收据/原生同 run 对照不证明无偏性、方差收益"；"V01 统计估计量与小样本覆盖率、Q2 外部物理基准未完成" |
| `docs/verification/f1-visible-20261030/README.md` | 输出身份/来源 | 产品 `f176d0ed…`、143 用例、48511 断言、exe `f02d3bdc…`、源码 `db253b7b…`、测试 `57a80e4f…` | 不增加 Q2 物理验证 |
| `docs/verification/independent-uncertainty-5465dbd-20261029/` | 统计估计量方法风险（V-01） | 提交 `5465dbdd…`；3 后端进程/4 run/12 事件；`finite_sample_two_histories`（0.1/0.3 MeV）、`sparse_workers_two_runs`；ROOT 与独立副本 SHA `3ad1e212…`；后端 SHA `f78fa2fb…` | 不用统一 v2 schema；**不宣称覆盖率或物理基准**；MSVC 后端与 GCC 辅助程序不可混称同一构建 |
| `docs/verification/independent-scoring-5465dbd-20261029/` | Edep/Dose/Fluence 快速对账 | 5 进程/12 事件；`two_primaries_one_history`（R-05）、`weighted_st/mt`（0.5/2/3）、`geantino_zero_edep`、`edep_weight_overflow`（1e308×2 MeV）；103 文件清单 | 早期快速验证；非完整回归；后端同为 `f78fa2fb…` |
| `docs/verification/independent-biasing-weight-5465dbd-20261029/` | 偏置/权重传播（R-09 证据） | 16 进程/15 完成/16 run/70 事件；electron bias 0.1/1/10 的 128 条 hits 除 process 名外逐行相同、权重全 1；thin neutron factor=100 权重 1；`weights_one/var/three` 恒定权重传播；N=4 `rel_error=0.390700016426`；324 文件/1,903,172 字节 | **R-09 未修复时的证据**：不能用于"偏置生效"或"无偏性"；不含动态权重/方差缩减 |
| `docs/verification/independent-rng-repro-5465dbd-20261029/` | RNG 可复现性 | 13 进程/12 完成、14 run/46 事件；`seed93_a/b` 独立进程重复、`seed94/cli94/app_macro94` 等价、`native123456_a/b`、`two_runs_a/mt`、`ignored_single_seed`（R-12）、`state_store/saved_rng`（3 个 MIXMAX 状态文件，仅生成未恢复）；285 文件/1,306,508 字节 | 不宣称 RNG 统计质量、跨平台逐位、状态恢复或修复后回归；旧 stage2b 报告身份不同（87 pass/116681 断言）不可混用 |
| `docs/collab/decisions/20261029-q1-uncertainty.md` | 统计口径裁决 | `uncorrected_event_moments_v1` / `uncorrected_delta_ratio_v1`；四状态；"不得靠放宽容差隐藏方法差"；完整方法验证归 Q2 | 只是口径决定，不是验证报告 |
| `scenarios/benchmarks/README.md` + 6 个包 README/`reference.csv` | 基准参考与容差 | 6 包来源（PSTAR/ESTAR/XCOM/PDG/SR-NIEL/Bortfeld）、容差表、2026-10-22 完整模式结果；device_dose 7 例偏差表 | 参考表非全部可重算；2026-10-22 结果无归档报告文件 |
| `scenarios/semiconductor/niel/README.md` | NIEL 数据来源与局限 | SR-NIEL-7 ver. 11.1、2026-10-22 设置、能量区间、ASTM E722-19、`2.037e-3 MeV cm²/g` 1 MeV 中子等效注量、仅硅 | 仓库未独立验证表；氧化层按硅表仅供参考 |
| `scenarios/semiconductor/README.md`、`scenarios/detector_response/`、`scenarios/shielding_coating/` | 场景包 | 分层器件 TID/DDD/Φ_eq 链；探测器响应包；屏蔽包 | 场景包是生成器+分析器，物理结论仍依赖上述参考表 |
| `scripts/test_*.py`（dose/fluence/let/displacement/statistical_uncertainty/scoring_mesh/biasing_*） | 用例定义本身 | 每个断言的场景、阈值、拒绝消息 | 代码即契约；**运行结果需重新执行**，本轮未执行 |

**引用建议**：Q2-1 提案引用"现有覆盖"时用 **F2 身份（227 用例）+ 具体测试脚本 + 具体断言**；引用"物理参考"时只引 PSTAR/ESTAR/XCOM/PDG/SR-NIEL 与对应包，不要把同源 `doseDeposit`/`cellFlux` 对照写进"独立验证"。

---

## 7. 缺口（需要新测/预注册，不能靠现有证据外推）

### 7.1 逐量

| 编号 | 缺口 | 现状证据 | 需要新增 |
| --- | --- | --- | --- |
| G-D1 | 绝对剂量无独立基准 | 只有 device_dose 的 TID/**注量**（EM-only、δ 平衡、硅） | 混合场/多材料绝对剂量（Gy）与外部表或解析 kerma 的对照；明确源强/时间/事件归一化口径 |
| G-D2 | 质量语义未覆盖复杂几何 | `test_dose_scoring` 只测 mother/child/parameterised 四组 | daughter/replica/assembly/嵌套 parameterised 的 `GetMass(true,false,preStepMaterial)` 对照（解析质量） |
| G-D3 | SiO₂ 剂量无参考 | 矩阵 L140 明示 | SiO₂ 电子阻止本领/剂量参考（表或解析） |
| G-F1 | FluenceScorer 无外部基准 | 只有 geantino 解析几何 + 原生 `cellFlux` 同源对照 | 外部注量参考：薄靶透射/阻止本领表、或与解析 track-length 积分对照（含面源、斜入射、多层） |
| G-F2 | 非 track-length 定义未支持/未测 | 仅无 daughter solid、非 surface-crossing（契约 `:82`） | surface-crossing 注量与边界穿越统计（若 Q2 需要） |
| G-F3 | 复杂复制几何/含 daughter 未测 | 同上 | replica/parameterised 体积的注量分母验证 |
| G-L1 | LET 仅质子薄靶 | `test_let_scoring`：10/100 MeV、20 µm 水、2 % | 重离子、厚靶能谱、次级电子主导的 LET_d、与 PSTAR/ICRU 表文件化对照 |
| G-L2 | LET_d 重尾/比值覆盖率 | Q1 决定与独立审查均"保留" | 独立 run 集合上的区间覆盖率；分母接近 0 的策略 |
| G-L3 | GUI 不能生成 LET | 矩阵 L196 | 若 Q2 需要 GUI 用例，先补编辑器/生成资格 |
| G-N1 | NIEL 数据本身未验证 | `make_reference.py` docstring；niel README | 与 SR-NIEL 原表/其他文献的独立复核（能量网格、质子强子部分差异），或明确把"NIEL 数据"列为外部输入假设 |
| G-N2 | 位移损伤"效应"未验证 | 无器件退化/损伤因子基准 | 若 Q2 要声称 DDD 物理意义，需要 NIEL→损伤的额外模型与参考（当前不应声称） |
| G-N3 | 表外能量策略只是记账 | `out_of_range_track_length_mm` | 表外能量对 DDD 的影响上界/敏感性分析 |

### 7.2 统计

| 编号 | 缺口 | 现状 | 需要新增 |
| --- | --- | --- | --- |
| G-S1 | 估计量未校正 | `R²=S2/S²−1/N`；Q1 决定保留 | 预注册：继续用 `uncorrected_*`（并在结论中声明）还是新增 `N/(N−1)` 版本；两者不得混用 |
| G-S2 | 无覆盖率验证 | 只有"20 run 离散/报告误差 ∈ 1/1.5–1.5"与池化 √20 | 独立 run 集合（建议 ≥100 次独立进程/独立种子）上的区间覆盖率、偏差、FOM 稳定性；明确名义置信水平 |
| G-S3 | 比值（LET）小样本/重尾 | delta 法 + 单 seed | 比值分母分布、重尾、事件数扫描；`undefined_ratio` 触发率 |
| G-S4 | 加权/偏置统计未测 | 矩阵 L160 明示 | 真实 occurrence biasing 下的加权估计量方差/协方差；与 analog 的方差比 |
| G-S5 | 多 worker 异质性 | 只测总数一致 | 每 worker 贡献分布、线程数变化对 R 的影响 |
| G-S6 | FOM 口径 | `1/(R²T)`，单轮墙钟 | 归一化口径（每初级/每秒）与跨机可比性 |

### 7.3 偏置

| 编号 | 缺口 | 现状 | 需要新增 |
| --- | --- | --- | --- |
| G-B1 | **无 biased-vs-analog 无偏性测试** | 只有执行/收据/权重非单位 | 同一几何/源/事件数下 analog 与多组 factor 的估计量对照（均值、方差、FOM 比、置信区间）；预注册等价界 |
| G-B2 | 无方差缩减/FOM 声明 | `biasing_effect_observed=unknown` | 方差缩减比与所需事件数的预注册实验 |
| G-B3 | 动态权重/次级权重未验证 | 审查 V-03 保留 | 次级粒子权重、`min_weight`/`max_interactions` 真实触发（非"全 analog"分支）、多次散射/多过程同时偏置 |
| G-B4 | 解析生存权重未断言 | 审查给出 `w_out/w_in = exp[(f−1)ΣL]` | 常截面薄靶的解析权重检验（可作零成本先导用例） |
| G-B5 | 历史归档不可复用 | R-09 修复前证据（`5465dbd`） | 只能用 Q1 之后（`8ecad66a`/`864bc03`）的运行重做偏置结论 |

### 7.4 基准与可复现性

| 编号 | 缺口 | 现状 | 需要新增 |
| --- | --- | --- | --- |
| G-P1 | 基准报告不落盘 | 套件 `--quick` 无 `--output`；临时目录删除 | Q2 运行必须 `--output` 并归档 `benchmark_report.json/md` + 日志 SHA + exe/源码指纹 |
| G-P2 | quick 覆盖不足 | 24/39 用例；device 缺 ddd p10/n14 | 预注册用例清单（哪些 quick、哪些完整）与事件数依据 |
| G-P3 | σ 口径不统一 | bragg 0.1 mm、detector 1 keV/√12、device rel_error | 预注册每例 σ 来源；`3σ` 与系统容差的关系写成公式 |
| G-P4 | 无 Fluence/LET 基准 | 6 包均不读这两个 scorer | 新增 Fluence/LET 基准包（外部表或解析） |
| G-P5 | 参考表不可全重算 | 仅 device_dose 有生成脚本 | 其余包补生成脚本/上游原表锁版本，或在提案中声明"外部表静态引用" |
| G-P6 | 固定 seed/无 RNG 状态 | seed=1000+序号；无状态导出 | 预注册 seed 策略（固定 seed 集或每 case 独立 seed + 记录）；需要逐位复现时用 F2 replay 而非基准 |
| G-P7 | 套件级逐位复现未覆盖统计用例 | F2 replay 证明固定构建/数据/线程下 `event_edep`/`hits` 多重集逐行一致 | 若 Q2 要"可复现统计"，需把 replay 与统计用例组合，或至少记录每 run 的 seed 与 R |

---

## 8. 本轮核查边界（诚实声明）

- 只做了**静态读取**：`docs/`、`scripts/`、`scenarios/`、`src/Core/SimulationManager.cc`、`docs/verification/*/README.md`、`docs/collab/reviews/*`、`docs/collab/decisions/*`；用 `python` 只读统计了 `run_m0_tests.py` 的用例数与 `reference.csv` 行数。
- **未运行**任何 Geant4 可执行文件、未执行任何 `scripts/test_*.py`、未运行 `run_benchmarks.py`、未运行 M0 测试平台；因此文中"通过/断言"均为**代码与归档自述**，不是本轮复现结果。
- 未修改产品代码、测试、基准、CI、文档；唯一写入是本文件。
- 归档 README 的 SHA/指纹均按原文转抄；引用前建议在目标提交上复核 `docs/verification/<阶段>/report.json` 与 `scripts/check_report_evidence.py`（本轮未运行该门禁）。

---

## 附：关键 file:line 索引

| 事实 | 位置 |
| --- | --- |
| 基准容差公式 `allowed = tolerance·|expected| + 3σ` | `scripts/run_benchmarks.py:114-119` |
| 基准 seed `1000+count` | `scripts/run_benchmarks.py:94`（detector 生成器 `:332`） |
| csda 容差 1.5 %/3 % | `scripts/run_benchmarks.py:146` |
| bragg σ=0.1 mm、容差 1 % | `scripts/run_benchmarks.py:183` |
| gamma 容差 2 % | `scripts/run_benchmarks.py:213` |
| shielding 容差（csda 1.5 %/3 %；residual 1 %） | `scripts/run_benchmarks.py:242,258` |
| device_dose 容差 2 %/1 % | `scripts/run_benchmarks.py:300` |
| detector 容差 3 %/1 %/1 keV | `scripts/run_benchmarks.py:345-356` |
| 基准在套件中的注册 `--quick` | `scripts/run_m0_tests.py:255` |
| 报告默认临时目录并删除 | `scripts/run_benchmarks.py:408,431-434` |
| device_dose 参考生成（常数/CASES/E_mid/tid/ddd） | `scenarios/benchmarks/device_dose/make_reference.py:29-30,33,74-88` |
| scorer_statistics 列与公式 | `docs/输出数据契约.md:161-171` |
| dose/fluence CSV 列与 MVP 边界 | `docs/输出数据契约.md:77-82` |
| DDD CSV 列 | `docs/输出数据契约.md:54` |
| LET CSV 列 | `docs/输出数据契约.md:150` |
| mesh `rel_error` 公式 | `docs/输出数据契约.md:141` |
| 四量/统计/偏置支持等级 | `docs/功能支持矩阵.md:140,158-166,172,191` |
| 偏置收据字段 | `src/Core/SimulationManager.cc:700-720` |
| `biasing_effect_observed=unknown` | `src/Core/SimulationManager.cc:702,1473` |
| 原生 doseDeposit/cellFlux 同源对照 | `scripts/test_scoring_mesh.py:229-232` |
| LET Bethe 对照 2 % | `scripts/test_let_scoring.py`（`main` 内 `abs(ratio-1)<0.02`） |
| 统计 20-run 比值 1/1.5–1.5、池化 0.75√20–1.33√20 | `scripts/test_statistical_uncertainty.py:209,214` |
| 偏置执行/收据断言 | `scripts/test_biasing_worker_runtime.py`（`main`，尾行打印 `PASS (execution only; no unbiasedness/FOM claim)`） |
| R-09（MT worker 无算符）证据 | `docs/collab/reviews/20261029-1314-astra-5465dbd-biasing-weight-review.md` |
| 统计估计量裁决 | `docs/collab/decisions/20261029-q1-uncertainty.md` |
| NIEL 来源/局限 | `scenarios/semiconductor/niel/README.md` |
