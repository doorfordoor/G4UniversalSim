# 独立参考病例（B 组：外部物理参考 / 表级审计 / 解析几何）

本文件只做**预注册设计**：没有运行模拟、没有修改产品/测试/基准/CI。输入、种子、事件数、
比较口径、容差与停止条件在此冻结；正式实现与运行需独审通过后由 Q2-3 执行。参考来源与
版本见 `references/external-sources.md`；冻结时仍缺的数值标 `TODO(freeze)`，不得用模拟结果反推。

## 0. 公共重建口径

- 配置模板沿用 `scripts/run_benchmarks.py` 的 `MAIN`（`[run] threads/seed`、`[output] format=csv`、
  `[materials] file=config/materials/material.ini`、`[geometry] template=hierarchical config=<文件>`、
  `[physics]`、`[scoring] enabled=true hits=<按病例> event_edep=<按病例> auto_create_default_scorers=true`），
  宏固定 `/run/initialize` + `/run/beamOn N`，CLI `G4UniversalSim --config <ini> --macro <mac> --output <dir>`。
- 可执行：`build_vs2026/Release/G4UniversalSim.exe`（`G4USIM_EXE` 优先）；Geant4 11.3.2。
  每例保存 `--capabilities`、`--check-geant4-data` 输出与输入文件 sha256。
- **预注册固定**：`threads = 1`（Q2-3 首轮；MT 作为独立批次另列）、`seed = 20261105 + 序号`、
  事件数按病例；输出目录每次新建，失败原件保留，不覆盖。
- 数据源：`scorer_statistics*.csv`（总量/比值）、各量 `*_volume_summary*.csv`（逐体积聚合）、
  `hits_*` / `event_edep_*`（独立重算时开启）、`run_metadata.json`（事件数/身份）。
- 统一判据 `|sim − ref| ≤ tol·|ref| + 3σ`（同 `scripts/run_benchmarks.py:114-118`）；σ 取对应
  scorer rel_error×value；`insufficient_events`/`zero_total` 不得判通过。
- 每例记录实际输入、构建、Geant4/数据身份、种子、N、threads、wall time；只引用本次原始文件。

## REF-DOSE-01 硅薄层 TID 相对 PSTAR 电子阻止本领

- 目的：用外部 PSTAR 电子阻止本领核对 Dose 的 `Σedep/mass` 绝对量；顺带发现质量/体积因子重复相乘。
- 几何/源（与 `scenarios/benchmarks/device_dose` 同布局，便于复用历史）：world 3 m 方盒 G4_Galactic；
  `Block` 40×40×(2b+t) mm G4_Si；`Slab` 10×10×t mm G4_Si 位于 Block 中心、`sensitive=true`；
  方形平面源 `halfx=6 mm`、`center=0,0,-1 mm`、`direction=0,0,1`；CASES：质子
  (10 MeV,b=50 µm,t=20 µm)、(50,300,100)、(100,600,100)、(200,1500,200)。
- 物理：`em=option4`、`default_cut=10 um`（δ 平衡）。scoring：`dose=true`、`hits=true`。
- 预注册：`threads=1`、`seed=20261106..20261109`、`events=20000`。
- 参考：`D/Φ = S_el(E_mid) × 1.602176634e-10 Gy·g/MeV`，`Φ=N/1.44 cm²`；`S_el` 取
  `scenarios/benchmarks/shielding_range/nist/PSTAR_Si.txt`，`E_mid` 用 PSTAR CSDA 反演（同
  `device_dose/make_reference.py` 算法）。来源记 NIST PSTAR URL/版本/访问日期，仓库副本 SHA-256 入 registry。
- 独立重算（实现层）：`V=10×10×t mm³`、`ρ_Si=2.33 g/cm³` → `mass=ρV`；从 `hits_t*.csv` 按
  `volume=<Slab path>` 求和 `edep` 与 `weight*edep` 得 `D=Σedep/mass`，与 `dose_volume_summary`
  raw/weighted 比较（相对容差 1e-9；weight=1 时 raw=weighted）。
- 判据：物理 `|D/Φ−ref| ≤ 0.02·|ref| + 3σ`；实现层 ≤1e-9；两者都过才通过。
- 能发现：质量重复乘、体积当质量、未扣 daughter；不能发现：PSTAR 与 Geant4 电子阻止本领的系统差。

## REF-FLU-01 真空宽束注量的解析值

- 目的：用解析 `Φ=N·p/A`（p=束斑内命中比例、A=敏感面积）核对 Fluence 的 `Σ步长/体积`，发现体积/面积因子错误。
- 几何：world 3 m G4_Galactic；`Slab` 10×10×0.1 mm G4_Galactic，原点，`sensitive=true`。
- 源：质子 100 MeV、`position_type=plane`、`shape=square`、`halfx=6 mm`（12×12 束斑）、
  `center=0,0,-2 mm`、`direction=0,0,1`。物理 `em=option4`、`default_cut=0.7 mm`。
  scoring：`fluence=true`、`hits=true`。
- 预注册：`threads=1`、`seed=20261110`、`events=20000`。
- 参考（解析，与实现无关）：束斑 12×12 mm 均匀覆盖 10×10 mm 敏感面，命中比例
  `p=(10/12)^2=100/144`；真空且薄片内无散射，每命中初级贡献步长积分 `t=0.1 mm`：
  `L/N = p·t = (100/144)·0.1 mm = 0.0694444 mm`，`Φ/N = L/(N·V) = p·t/V`
  = `(100/144)·0.1/10 mm^-2 = 1/144 mm^-2`。N=20000 时期望
  `L=1388.888… mm`、`Φ=138.888… mm^-2`。
- 判据：物理容差 1e-6（相对）；同时用 hits 逐行 `Σ stepLength` 独立复核（1e-9，REF-FLU-02）。
- 能发现：体积因子重复/漏乘、cm²/mm² 混淆、把源面积当敏感面积、束斑/敏感面混淆；
  不能发现：边界步重复计数（由 REF-FLU-02 核对）。

## REF-FLU-02 真空注量的 hits 逐行复核

- 与 REF-FLU-01 同配置同 seed（20000 事件、seed=20261110）；脚本按 `hits_t*.csv` 逐行筛选
  Slab 求和 `Σ stepLength_mm`，`Φ_hits=ΣL/V`，与 `fluence_volume_summary` 及
  `scorer_statistics` 总量比较（1e-9）；期望值等于 REF-FLU-01 的 138.888… mm^-2。
- 若 hits 行数/长度与 summary 不符即失败并保留差异行；这是实现层独立重算，不是新物理参考。

## REF-LET-01 硅薄层 LET 相对 PSTAR

- 目的：用外部 PSTAR 电子阻止本领核对 LET_t/LET_d 的物理量级与材料/能量依赖；发现 LETstep
  用错材料/能量、分子分母错配、粒子过滤失效。
- 几何：world G4_Galactic；`Slab` 10×10×20 µm G4_Si（daughter-free），原点，`sensitive=true`；
  源：质子 100 MeV 与 10 MeV 两个子例，`plane/square/halfx=6 mm/center=0,0,-2 mm/direction=0,0,1`。
- 物理：`em=option4`、`default_cut=1 um`。scoring：`let=true`、`[scoring.let] particles=proton`、`hits=true`。
- 预注册：`threads=1`、`seed=20261111/20261112`、`events=2000`。
- 参考：`LET[keV/um] = S_el[MeV cm²/g] × ρ[g/cm³] × 0.1`（1 MeV/cm=0.1 keV/µm），`S_el` 取 PSTAR Si
  在 E_mid 的值；E_mid 用与 device_dose 相同的 CSDA 反演 `E_mid=R^-1(R(E0)-ρ·t/2)`
  （PSTAR Si、ρ=2.33 g/cm³、t=20 µm），10 MeV→**9.91864 MeV**、100 MeV→**99.98639 MeV**；
  S_el=34.7962/5.8366 MeV cm²/g → LET_t 期望 **8.1075/1.3599 keV/µm**。E_mid 由预先固定的
  CSDA 算法与几何算出，不是从本轮模拟结果反推；参考值见 `references/values-q2-1.csv`。
- 判据：LET_t `|Δ| ≤ 0.015·ref + 3σ`（tol=1.5%，对齐历史“约 1%”）；`LET_d ≥ LET_t` 且
  `|LET_d−LET_t|/LET_t ≤ 0.05`（超出要记录 straggling 解释并标 `待审`，不自动放宽）。
  实现层：由 `let_volume_summary` 的 sum_wl/sum_wSl/sum_wS2l 独立重算 let_t/let_d（≤1e-12）。
- 能发现：材料/能量取错、粒子过滤失效；不能发现：G4EmCalculator 与 PSTAR 的系统差（tol 来源）。

## REF-DDD-01 硅薄层 DDD 相对 NIEL 表（实现折积）

- 目的：用表值×独立几何长度/体积核对 DDD 折积实现；明确“只检验实现，不检验 NIEL 数据”。
- 输入：device_dose 质子 10 MeV（b=50,t=20 µm）与 100 MeV（b=600,t=100 µm）；`em=option4`、cut 10 µm；
  scoring `displacement=true`、`[scoring.displacement] proton=scenarios/semiconductor/niel/si_proton.csv`、
  `hits=true`。预注册：`threads=1`、`seed=20261113/20261114`、`events=20000`。
- 参考：`DDD/Φ = NIEL(E_mid)`，E_mid 用 PSTAR CSDA 反演、log-log 插值；能域 0.1 keV–10 GeV。
- 实现层独立重算：hits 求和 `Σ(w·stepLength)`，独立几何 V 得 `Σ(w·l)/V`；但 hits 不含逐 step NIEL，
  因此只能核对长度/体积因子，完整的逐 step 折积证据保留在现有 `test_displacement_damage.py` 与历史
  基准记录，本病例标**有限**并记录缺口（若要求逐 step 独立核对，需 hits 增加 NIEL 列或 scorer 导出
  逐 step 值——数据需求）。
- 判据：物理 `|DDD/Φ−ref| ≤ 0.01·ref + 3σ`（tol=1%，同现行 device_dose）；长度折积实现层 1e-9。
- 能发现：长度/体积/权重因子错误；不能发现：NIEL 表本身错误（交 REF-DDD-02）。

## REF-DDD-02 NIEL 表级审计（不跑模拟；算术可复核，物理判定受限）

- 目的：把“表本身”与“实现折积”分开核对；**不以未核验的 95 MeV·mb 值作 0.1% 物理判据**。
- 输入：`si_neutron.csv`（sha256 `a2ad28a9…`）、`si_proton.csv`（`6c21e35a…`）、ASTM 公开摘要
  （仅确认适用范围）、SR-NIEL-7 ver.11.1 说明；详见 `references/ddd-table-audit.md`。
- 可执行检查（只读，全部算术可复算）：
  1. 表头/单位/单调/有限非负（`NielTable.cc` 读取约束；现有 README 已声明）；
  2. 95 MeV·mb→MeV cm²/g 的**单位换算**：`95 mb=9.5e-26 MeV·cm²/atom`，除以 Si 原子质量
     `4.66370e-23 g` 得 `2.037006e-3`（换算算术已验证；`95` 输入未从付费全文核验）；
  3. `si_neutron.csv` 1.000 MeV 邻域 `0.98→2.4078e-3`、`1.05→1.6573e-3`；log-log 插值
     `2.158335e-3`、线性 `2.193371e-3`（算法敏感度 1.6 pp）；与 2.037006e-3 之比
     1.0596/1.0768。**缺 1.000 节点与约 6% 差异本身不是程序或数据缺陷**；
  4. 仅在“模型、Ed、标准版本、数值输入均有据”时才作物理一致性判定；当前 ASTM 全文/Table A1.1
     不可得、SR-NIEL 为另一评价/归一化路径，因此**不设物理通过门槛**，只登记差异与限制。
- 判据：算术项全过（1e-6 相对）；表格结构项按 `NielTable` 约束；物理一致性标 `limited`，
  不判 pass/fail；不补点、不改表、不跑模拟。
- 停止条件：算术不符或表结构不符 → failed；参考不可得 → limited；任何情况下不得修改数据表。
- 能发现：单位换算/插值算法/表网格实现错误；不能发现：两种评价之间的模型差异、Ed 差异。

## 复用而不重做

`csda_range`、`bragg_peak`、`gamma_attenuation`、`shielding_range` 为外部数据参考；
`detector_response` 为仓内解析式（非外部实测数据）。本文件不重做这些包；Q2-3 仅执行四量新病例。
