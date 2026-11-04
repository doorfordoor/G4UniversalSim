# 实现对照病例（A 组：独立重算 / 因子复现，Q2-2 预注册草案）

本文件只做**预注册设计**：没有运行模拟、没有修改产品/测试/基准/CI。四个病例都用
“另一条独立证据链”重算同一个量，专门回答一个问题：**若 Dose/Fluence/LET/DDD 的
质量、体积或权重因子被错误地重复相乘，这个病例会不会失败？**

与 `cases/reference-cases.md`（B 组，外部物理参考）的分工：

- B 组用 PSTAR / SR-NIEL / 解析真空注量回答“物理量级对不对”；
- 本组（A 组）只用**本次运行的原始输出 + 几何/材料/源配置 + 输入表/权重文件**回答
  “实现有没有把因子乘错”，不重复 B 组的外部参考判据。
- 因此本组的通过判据以**算术恒等**（1e-12～1e-9）为主，物理量级只作 sanity；需要外部
  参考的绝对量（LET 的 S、DDD 的 NIEL 数据）明确交给 REF-LET-01 / REF-DDD-01 /
  REF-DDD-02，不在本组重新冻结容差。
- 权重测试不再单列病例号；它是每个病例的第 5 节，四个病例各注入一次 `weight=2`。

---

## 0. 公共约定

### 0.1 三条独立证据链

每个病例都尽量让“被检验的因子”出现在两条**不同来源**的证据里，而不是拿 scorer 自己的
两列互除：

| 证据链 | 来源 | 独立性 |
| --- | --- | --- |
| G（几何/配置） | `geometry.ini` 的 box 尺寸 + `material.ini` 的密度 | 不经过 scorer；与 `GetMass`/`GetCubicVolume` 代码路径无关 |
| R（原始逐事件/逐 step 输出） | `event_edep_*.csv`、`hits_*.csv` | 与 summary 的累加器分开；但不独立于 SD 的 edep/stepLength 本身 |
| I（输入文件） | `niel_const.csv`、`ps_w1.csv`/`ps_w2.csv` | 表值/权重由输入决定，scorer 只读取 |

**关键原则**：`dose_volume_summary.mass_kg`、`fluence_volume_summary.volume_mm3`、
`let_volume_summary.sum_*` 是**被检验对象**，不能既当答案又当裁判。重算质量/体积时必须
用 G；重算长度/能量时必须用 R；重算权重比时必须用 I。

### 0.2 哪些量从配置几何重算，哪些必须用原始数据

| 量 | 重算来源 | 说明 |
| --- | --- | --- |
| `m_geom`（Dose 质量） | G：`2.33e-6 kg/mm³ × 10×10×t mm³` | box 的 `GetCubicVolume()` 精确；单材料、无 daughter |
| `V_geom`（Fluence/DDD 体积） | G：`10×10×t mm³` | 同上 |
| `ΣE`（Dose 逐事件能量） | R：`event_edep.raw_edep_MeV`（或 `hits.edep_MeV`） | 与 summary 的 `raw_edep_MeV` 对照 |
| `L`/`ΣwL`（Fluence/DDD 长度） | R：`hits.stepLength_mm` 与 `hits.weight` | 只对 `edep>0` 的 step 有行；本组用质子/硅，所有 step 均有沉积 |
| `S`（LET 逐 step 阻止本领） | **无**：hits v3 不输出 `LETstep` | 这是本组最强的 LET 检查被阻塞的原因（见 §7、§10） |
| `NIEL(E)`（DDD） | I：表 + R：`hits.kineticEnergy_MeV`/`edep_MeV` | 常量表时可完全避开 E；实表时 `E_mean≈KE−0.5·edep` 只是近似 |
| `weight`（权重） | I：相空间 CSV 的 `weight` 列 | 全 step 继承 primary 权重；无源级 `weight` 键 |

### 0.3 公共 `main.ini` 模板（每个键都显式给出）

`@...@` 为占位符；把 §2 表中的值代入后即为完整、可运行的 `main.ini`。模板不依赖隐式默认值
（`interactive`、`dry_run`、`biasing`、`check_overlaps` 等都显式写出）。

```ini
[run]
name = @NAME@
threads = 1
seed = @SEED@
interactive = false
verbose = 0
check_overlaps = false
dry_run = false
macro = run.mac

[output]
dir = @OUTDIR@
format = csv

[materials]
file = material.ini

[geometry]
template = simple_box
config = geometry.ini
check_overlaps = false
default_world_material = G4_AIR

[physics]
reference = FTFP_BERT_EMZ
default_cut = 1 mm
biasing = false
verbose = 0

[source]
particle = proton
energy = @E_MEV@ MeV
position_type = plane
shape = square
halfx = @HALF_MM@ mm
center = 0, 0, @Z_MM@ mm
direction = 0, 0, 1
verbose = 0

[scoring]
enabled = true
hits = true
event_edep = @EVENT_EDEP@
edep = false
let = @LET@
dose = @DOSE@
fluence = @FLUENCE@
displacement = @DISP@
auto_create_default_scorers = true
verbose = 0

@EXTRA@
```

`@EXTRA@` 的取值：

- Dose/Fluence：空。
- LET：`[scoring.let]` 换行 `particles = proton`。
- DDD：`[scoring.displacement]` 换行 `proton = niel_const.csv`。

**源位于靶前 0.01 mm**：`@Z_MM@ = −(t/2 + 0.01)`，避免 primary 恰好在靶前表面时
Geant4 导航的边界歧义。0.01 mm 空气的能量损失对 10–100 MeV 质子 <1e-5 MeV，可忽略；
它不在敏感体内，不进入 Fluence/DDD 的长度。

### 0.4 公共 `geometry.ini` / `material.ini` / `run.mac`

`geometry.ini`（`@T_MM@` 为该病例的靶厚；`[visual.*]` 省略，`SimpleBoxTemplate::ApplyVisual`
在 section 不存在时直接返回，见 `src/Templates/SimpleBoxTemplate.cc:25-33`）：

```ini
[world]
size = 10 cm, 10 cm, 10 cm
material = G4_AIR

[target]
name = Target
shape = box
size = 10 mm, 10 mm, @T_MM@ mm
material = SiRef
position = 0 mm, 0 mm, 0 mm
rotation = 0 deg, 0 deg, 0 deg
sensitive = true
bias = false
region = SV
cut.gamma = 1 mm
cut.e- = 1 mm
cut.e+ = 1 mm
cut.proton = 1 mm
```

**为什么用 1 mm 粗 production cut**：本组要的是“总能量守恒/总径迹长度”，不是 δ 电子
平衡。1 mm cut 在 Si 中抑制 δ 电子产生（10 MeV 质子的最大 δ 电子约 22 keV，射程约
5 µm，远低于阈值），使 primary 的能量局部沉积、径迹长度接近直线；LET 的 S 由
`G4EmCalculator::ComputeElectronicDEDX` 给出，与 cut 无关。B 组的 TID 病例用 10 µm cut
追求 δ 平衡，本组不用那个 cut，避免把“δ 电子是否产生”混进因子检查。

`material.ini`（用自定义材料把密度写成**配置值**，使 `m_geom` 不依赖 `G4_Si` 的内置密度）：

```ini
[material.SiRef]
mode = mass_fraction
density = 2.33 g/cm3
components = G4_Si:1
state = solid
```

`run.mac`：

```
/run/initialize
/run/beamOn @N_EVENTS@
```

运行方式（工作目录 = 病例目录，所有相对路径同目录，避免 cwd 与 main_ini 基准不一致）：

```bash
cd <case-dir>
G4UniversalSim --config main.ini --macro run.mac
```

### 0.5 输出文件与列（threads=1，首轮）

| 文件 | 关键列 | 用途 |
| --- | --- | --- |
| `hits_t0.csv` | `runID,eventID,trackID,parentID,particle,edep_MeV,ndep_MeV,stepLength_mm,x0_mm,y0_mm,z0_mm,x1_mm,y1_mm,z1_mm,px,py,pz,kineticEnergy_MeV,process,volume,weight` | 逐 step 的 edep/长度/KE/权重；**无 mass/volume/LETstep** |
| `event_edep_t0.csv` | `runID,eventID,raw_edep_MeV,weighted_edep_MeV` | 逐事件能量和（Dose） |
| `dose_volume_summary_t0.csv` | `runID,volume_path,volume_name,mass_kg,raw_edep_MeV,weighted_edep_MeV,raw_dose_Gy,weighted_dose_Gy,raw_edep_sum_sq_MeV2,weighted_edep_sum_sq_MeV2,n_events` | Dose 汇总（v2，11 列） |
| `fluence_volume_summary_t0.csv` | `runID,volume_path,volume_name,volume_mm3,raw_track_length_mm,weighted_track_length_mm,raw_fluence_mm-2,weighted_fluence_mm-2,raw_track_length_sum_sq_mm2,weighted_track_length_sum_sq_mm2,n_events` | Fluence 汇总（v2，11 列） |
| `let_volume_summary_t0.csv` | `runID,volume_path,volume_name,particles,steps,sum_wl_mm,sum_wSl_MeV,sum_wS2l_MeV2_per_mm,let_t_keV_per_um,let_d_keV_per_um,sum_sq_wl_mm2,sum_sq_wSl_MeV2,sum_sq_wS2l_MeV4_per_mm2,sum_wl_x_wSl_MeV_mm,sum_wSl_x_wS2l_MeV3_per_mm,n_events` | LET 汇总（v2，16 列） |
| `displacement_volume_summary_t0.csv` | `runID,volume_path,volume_name,particle,niel_table,volume_mm3,track_length_mm,out_of_range_track_length_mm,ddd_MeV_g,ddd_sum_sq_MeV2_g2,n_events` | DDD 汇总（v1，11 列；无 raw/weighted 拆分） |
| `scorer_statistics_r1.csv` | `runID,scorer,quantity,key,name,unit,estimator,n_events,entries,value,mean_per_event,std_error,rel_error,fom_per_s,run_wall_time_s,sum,sum_sq,uncertainty_estimator,uncertainty_status` | 跨 worker 合并后的总量/比值与 rel_error |
| `run_summary.txt` | 状态、每 run 的 `completed_events`、生成文件、seed | 运行身份与事件数核对 |

说明：

- 文件名按 `src/Output/OutputManager.cc:288-329` 与 `MakeThreadFilename`：`threads=1`
  首轮为 `_t0.csv`；同目录第二轮会变成 `_t0_rR.csv`。**每例新建输出目录**，不要复用。
- `scorer_statistics` 在 `runId>0` 时为 `scorer_statistics_r1.csv`；若实际目录给的是
  `scorer_statistics.csv`，以目录清单为准（两种命名都在契约中，见 `docs/输出数据契约.md`）。
- `n_events` 是**完成事件数**（含零贡献事件）；`entries` 只累计非零贡献事件。Fluence/DDD
  的束流比靶大，约 30.6 % 事件零贡献，`entries≈N·p`，**不要拿 entries 当 N** 去算 σ 或
  判断事件数。
- `hits` 默认不写零沉积 step（`src/Hits/SensitiveDetector.cc:92` 的零沉积分支仍计分
  Fluence/LET/DDD，但 `return false`，不写 hits 行）。本组用质子打硅，每个 step 都有
  电离沉积，所以 R 链完整；换成中性粒子或真空层时这条不成立（见 §10 G2）。

### 0.6 容差：算术检查与统计检查分开

| 类别 | 判据 | 适用 |
| --- | --- | --- |
| 同一 summary 行内的恒等式 | `\|recomputed − scored\| ≤ 1e-12 · max(\|scored\|, 1e-300)` | `raw_dose = raw_edep·k/mass`、`fluence = L/V`、`let_t = A/B`、`ddd = 100·L·NIEL/V` |
| 跨 CSV 求和（逐行 12 位有效数字） | `≤ 1e-9 · max(\|scored\|, 1e-300)` | `Σ event_edep = raw_edep`、`Σ hits.stepLength = raw_track_length`、`Σ hits.weight·stepLength = track_length` |
| 任意算术检查的硬上限 | `≤ 1e-6` 相对 | 只要超过 1e-6，不论来源一律失败 |
| 统计/物理检查 | `\|x − x_ref\| ≤ tol·\|x_ref\| + 3σ`，`σ = max(解析σ, scorer_statistics.rel_error·\|x\|)` | `ΣE = N·E`、`Φ = N/A`、`DDD/Φ = NIEL` |
| 权重线性（确定性） | `\|ratio − 2\| ≤ 1e-9·2`；`\|raw_w2 − raw_w1\| ≤ 1e-12·max(\|raw_w1\|,1)` | §5 的 w=1/w=2 对 |

**为什么算术容差能到 1e-12**：summary 的写出用 `setprecision(12)`；同一行的
`raw_edep`、`mass`、`raw_dose` 都来自同一批 double，重算只差最后一位舍入。跨 CSV 求和
有 2 万行的逐行舍入，放宽到 1e-9。若只信任打印的 12 位数字，1e-6 是最后的安全阀。

### 0.7 统计矩一致性（summary ↔ scorer_statistics）

`scorer_statistics` 的 `rel_error` 由 `HistoryStatistics` 用事件矩算出；同一批矩也在
`*_volume_summary` 里。两者必须一致，否则说明 registry 收错了 sum/den/cross：

- 总量（Dose/Fluence/DDD）：
  `R = sqrt(S2/S² − 1/N)`，其中 `S`/`S2` 取 summary 的 `raw_*`/`raw_*_sum_sq`
  （Fluence 是长度；DDD 是 `ddd`/`ddd_sum_sq`），`N = n_events`。与
  `scorer_statistics.rel_error` 比较，容差 1e-9。summary 的物理量乘了常数
  `k=1/m` 或 `1/V` 时，`R` 对常数缩放不变，所以可直接用未缩放的 `S`/`S2`。
- 比值（LET）：
  `R_t² = S2_A/A² + S2_B/B² − 2C/(A·B)`，其中 `A=sum_wSl`、`B=sum_wl`、
  `S2_A=sum_sq_wSl`、`S2_B=sum_sq_wl`、`C=sum_wl_x_wSl`；`let_d` 用
  `A=sum_wS2l`、`B=sum_wSl`、`C=sum_wSl_x_wS2l`。与 `scorer_statistics` 的
  `let_t`/`let_d` 行 `rel_error` 比较，容差 1e-9。
  **这是本组对 LET 不确定度最强的独立检查**：`scorer_statistics` 的 ratio 行本身不写
  sum/sum_sq（`src/Output/OutputManager.cc:288-329` 只在 `!e.ratio` 分支填），但
  `let_volume_summary` 写出了三组和与交叉和，delta 法仍可重算。若只允许使用
  `scorer_statistics` 而不允许读 `let_volume_summary`，则该检查不可做（见 §10 G6）。
- 若 `uncertainty_status != approximate`（`insufficient_events`/`zero_total`/
  `undefined_ratio`），不得把 `value=0` 当成“误差 0”参与判定；该 run 直接失败。
- `value` 与 summary 的对应列：Dose `raw_dose_Gy`/`weighted_dose_Gy`、Fluence
  `raw_fluence_mm-2`/`weighted_fluence_mm-2`、LET `let_t`/`let_d`、DDD `ddd_MeV_g`；
  容差 1e-12。`sum` 对总量行等于 `value`，`mean_per_event = value/N`；ratio 行的
  `sum`/`sum_sq`/`mean_per_event` 为空，**不要误读为 0**。

### 0.8 权重注入：相空间重放（已核对代码）

**结论：当前唯一确认的“精确 factor-2 事件权重”机制是 phase-space 重放**。

- `[source] phase_space_file = a.csv[,b.csv]` 已实现（schema：`path_base=main_ini_directory`；
  `src/Scoring/PhaseSpace.cc` 解析；`src/Source/SourceManager.cc:594`
  `primary->SetWeight(p.weight)`）。
- `phase_space_csv_v1` 表头固定 15 列：
  `runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight`。
  连续相同 `(runID,eventID)` 的行构成一个 history；第 k 个事件重放第 k 个 history；
  `beamOn ≤ histories`（无 recycle 时）。
- 解析器要求方向单位长（`||u,v,w||−1 ≤ 1e-6`）、`kineticEnergy ≥ 0`、`weight > 0`、
  `pdg ≠ 0`、粒子名非空。
- `src/Hits/ParticleHit.cc:157-160` 把 pre-step 的 `TrackWeight()` 写进 hit；
  Dose/Fluence/LET/DDD 都通过 `HitRecord.weight` 拿到它。
- 手册记录了手工权重文件的正向验证：**手写的双粒子、权重 0.5 的历史按一个事件重放且
  权重保持**（`docs/中文使用手册.md` 相空间小节）。所以“手工 CSV + weight 列”不是猜测。
- **没有源级 `weight` 键**；`[source.<name>]/intensity` 是多个命名源之间的选择概率，
  不是事件权重（schema / 手册）。不要用它做 factor-2 测试。
- `[phase_space]` 输出段（`volume`/`particles`/`kill`）存在，但本组不需要它：我们直接
  手写重放文件。使用它录边界再重放是另一条路，但会引入“边界记录时的权重”问题
  （契约 §226 的 Q1 注记），本组不采用。

**相空间文件写法**（Dose 例，`z=@Z_MM@`、`E=10`、`x/y` 用 Halton(2,3) 映射到
`[−halfx,halfx]`）：

```csv
runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight
1,1,1,0,proton,2212,-3.812734,1.204411,-1.01,0,0,1,10,0,1
1,2,1,0,proton,2212,2.117903,-4.330127,-1.01,0,0,1,10,0,1
...
```

- 一个 history 一行（单 primary）；`eventID` 从 1 连续到 N。
- **`u,v,w` 是方向余弦，不是权重**；本例 `u=v=0, w=1`，权重是最后一列。
- `w=2` 文件：**除最后一列外与 `w=1` 文件逐字节相同**。先写 w=1，再复制并把最后一列
  改成 2，保证位置/能量/方向/事件序完全一致。
- `[source]` 段替换为**只有**下面两行（不能再带 `preset/particle/energy/...`）：

```ini
[source]
phase_space_file = ps_w1.csv
verbose = 0
```

- 两个 run 的 `[run] seed` 相同、`[run] name`/`[output] dir` 不同、其余键相同。这样
  weight 不参与传输，**raw 列应逐位一致**（12 位输出内 ≤1e-12），weighted 列严格线性。
- 若相空间文件路径不在 main.ini 同目录，按 schema 的 `main_ini_directory` 基准解析；
  本组把它放在同目录，避免歧义。

### 0.9 已核对键 / 待验证清单（汇总）

| 键/特性 | 本组取值 | 状态 | 依据 |
| --- | --- | --- | --- |
| `[run] threads/seed/macro` | 1/固定/`run.mac` | 已确认 | schema `config_schema.json` `[run]`；`macro` 相对 cwd |
| `[output] format` | `csv` | 已确认 | schema `output.format`（allowed csv/root/both/auto） |
| `[geometry] template` | `simple_box` | 已确认 | `src/Templates/SimpleBoxTemplate.cc` |
| `[target] sensitive/region/cut.*` | true/SV/1 mm | 已确认 | `SimpleBoxTemplate.cc:14-20,42-70`；示例 `config/geometry/simple_box.ini` |
| `[materials] file` + `[material.SiRef]` | mass_fraction/2.33 g/cm³/`G4_Si:1`/solid | 部分**待验证** | `src/Materials/MaterialIniReader.cc:434-459`；单组分不在示例中，见各例 §8 |
| `[physics] reference` | `FTFP_BERT_EMZ` | 已确认 | `src/Physics/PhysicsFactory.cc:326-328` |
| `[physics] default_cut` | 1 mm | 已确认 | 手册 `[physics]`；示例 |
| `[source]` plane/square/halfx/center/direction | 见各例 | 已确认 | 手册 `[source]`；schema |
| `[source] phase_space_file` | `ps_w1.csv` | 机制已确认；大文件**待验证** | `PhaseSpace.cc`；`SourceManager.cc:594`；手册手工权重测试 |
| `[scoring] dose/fluence/let/displacement` | 每例一个 true | 已确认 | `src/Scoring/ScoringManager.cc:651+` |
| `[scoring] auto_create_default_scorers` | true | 已确认（Dose/Fluence/DDD 必需） | `ScoringManager.cc:697-699` |
| `[scoring.let] particles` | `proton` | 已确认 | `ScoringManager.cc:763-780` |
| `[scoring.displacement] proton` | `niel_const.csv` | 已确认 | schema；`ScoringManager`；`NielTable.cc` |
| `[scoring] hits/event_edep` | 按例 | 已确认 | `src/Output/OutputManager.cc:823-830` |
| `hits.volume` 的值 | 期望物理体积名 `Target` | **待验证** | 首次 10 事件小样本核对；若是路径则按后缀匹配 |
| `scorer_statistics` 文件名 | `scorer_statistics_r1.csv` | 代码已确认；实际命名以目录为准 | `OutputManager.cc:288-329` |
| `event_edep` 零事件是否写行 | 本组全命中，不触发 | **待验证**（若改用漏束源） | 契约只规定逐事件 edep |
| `n_events` 语义 | 完成事件数 | 已确认 | 各 Scorer `Write`；契约 :171 |

---

## IMP-DOSE-01 质量因子与 `D=ΣE/m`

### 1. 目的（可证伪的公式/因子）

目标公式：

```text
D_raw = (Σ_steps E_i[MeV] × 1.602176634e-13 J/MeV) / m_kg
m_geom = ρ_Si × V = 2.33 g/cm³ × 10×10×t mm³
```

本病例要证伪：

1. 质量被**重复乘/除**：`D = ΣE/m²` 或 `D = ΣE·m`；
2. 把**体积当质量**：`m` 位置用了 `200`（mm³）而不是 `4.66e-4`（kg）；
3. `mass_kg` 列本身被错误放大/缩小（例如 `GetMass` 多乘了 2、或用了 cm³ 当 m³）；
4. `weighted_dose` 把权重乘了两次（`w²`）或根本没乘（`w⁰`）。

**不能发现**：

- SD 的 edep 本身错（cut/物理列表/δ 电子逃逸）——scorer 和 R 链用的是同一批 edep；
- 材料密度错但 `material.ini` 与重算用了同一个错密度（G 链是唯一真值来源）；
- 复杂 daughter/replica 几何下 `GetMass(true,false,preStepMaterial)` 的语义错——本组用
  无 daughter 的单 box，不覆盖该情形；
- 时间/源强/每初级归一化（当前 Dose 本来就不做这些归一化）。

### 2. 精确输入

公共模板（§0.3）+ 下表：

| 键 | 值 |
| --- | --- |
| `@NAME@` | `imp-dose-01` |
| `@SEED@` | `20261120` |
| `@OUTDIR@` | `out/imp-dose-01` |
| `@T_MM@` | `2` |
| 靶尺寸 | `10 mm, 10 mm, 2 mm`（V=200 mm³） |
| 材料/密度 | `SiRef`，`2.33 g/cm³`（`material.ini`） |
| `@E_MEV@` | `10` |
| `@HALF_MM@` | `5`（10×10 mm 束，全部打中靶） |
| `@Z_MM@` | `-1.01` |
| `@N_EVENTS@` | `20000` |
| `@EVENT_EDEP@` | `true` |
| `@DOSE@` / `@FLUENCE@` / `@LET@` / `@DISP@` | `true` / `false` / `false` / `false` |
| `@EXTRA@` | 空 |
| physics | `FTFP_BERT_EMZ`，`default_cut=1 mm`，`biasing=false` |
| threads/seed | `1` / `20261120` |

运行：

```bash
cd out/collab/q2-reference-proposal/cases/imp-dose-01   # Q2-3 实际工作目录
G4UniversalSim --config main.ini --macro run.mac
```

权重对：`imp-dose-01-w1` / `imp-dose-01-w2`，`@N_EVENTS@=20000`、`@SEED@=20261130`
（两者相同）、`[source]` 只有 `phase_space_file=ps_w1.csv` / `ps_w2.csv`；几何/材料/
scoring/宏完全相同，`ps_w2.csv` 除最后一列外与 `ps_w1.csv` 逐字节相同。相空间 `x,y`
用 Halton(2,3) 映射到 `[-5,5] mm`，`z=-1.01 mm`，`E=10 MeV`，`u=v=0,w=1`。

### 3. 独立重算路径

读：

- `dose_volume_summary_t0.csv`（1 行：`volume_name=Target`）；
- `event_edep_t0.csv`（20000 行）；
- `hits_t0.csv`（按 `volume` 过滤 `Target`，**全部粒子**求和，不筛质子）；
- `scorer_statistics_r1.csv`（`scorer=dose`，`quantity=raw_dose`/`weighted_dose`）。

独立脚本计算：

```text
t_mm        = 2.0                         # 从 geometry.ini 读，不从 CSV 读
V_mm3       = 10 * 10 * t_mm              # = 200
m_geom_kg   = 2.33e-6 * V_mm3             # = 4.66e-4
MEV_J       = 1.602176634e-13

E_raw_sum   = sum(event_edep.raw_edep_MeV)
E_w_sum     = sum(event_edep.weighted_edep_MeV)
E_hits_sum  = sum(hits.edep_MeV where volume == Target)          # 全粒子
D_raw_calc  = E_raw_sum * MEV_J / m_geom_kg
D_w_calc    = E_w_sum   * MEV_J / m_geom_kg
```

对照：

| 检查 | 对象 | 容差 |
| --- | --- | --- |
| A1 质量 | `mass_kg == m_geom_kg` | 1e-9 相对 |
| A2 raw 恒等 | `raw_dose_Gy == raw_edep_MeV·MEV_J/mass_kg` | 1e-12 |
| A3 weighted 恒等 | `weighted_dose_Gy == weighted_edep_MeV·MEV_J/mass_kg` | 1e-12 |
| A4 逐事件和 | `E_raw_sum == raw_edep_MeV`；`E_w_sum == weighted_edep_MeV` | 1e-9 |
| A5 hits 和 | `E_hits_sum == raw_edep_MeV` | 1e-9 |
| A6 统计值 | `stats(raw_dose).value == raw_dose_Gy`；`sum == value`；`mean == value/N` | 1e-12 |
| A7 统计误差 | `stats(raw_dose).rel_error == sqrt(S2/S²−1/N)`，`S=raw_edep_MeV`、`S2=raw_edep_sum_sq_MeV2`；weighted 同理 | 1e-9 |
| A8 事件数 | `n_events == 20000 == beamOn`；`entries == 20000`（全命中） | 精确 |
| A9 统计状态 | `uncertainty_status == approximate` | 精确 |

**哪些来自 G，哪些来自 R**：A1 的 `m_geom_kg` 来自 G；A2/A3 的 `mass_kg` 是**被检验
列**，所以恒等式只证明“scorer 内部自洽”，不证明质量正确；A4/A5 来自 R；A6/A7 来自
R 的矩 + summary。**A1 才是质量因子的独立裁判**；A2 只能抓“公式里多乘了一个 mass 但
写出的 mass 没变”这种错。两者必须都过。

### 4. 期望解析值/关系（推导）

- 靶体积 `V = 10×10×2 = 200 mm³`；`m = ρV = 2.33 g/cm³ × 0.2 cm³ = 0.466 g = 4.66e-4 kg`。
- 10 MeV 质子在 Si 中的 CSDA 射程约 `0.1665 g/cm² / 2.33 = 0.0715 cm = 0.715 mm`
  （PSTAR Si，仅作量级；不是本病例的通过判据）。靶厚 2 mm > 0.715 mm，质子停在靶内，
  全部动能沉积在敏感体（空气间隙的 0.01 mm 损失 <1e-5 MeV）。
- `ΣE_raw ≈ N·E = 20000 × 10 = 2.000e5 MeV`。
- `D_total = 2.000e5 × 1.602176634e-13 / 4.66e-4 = 6.87629e-5 Gy`。
- `D_per_primary = 10 × 1.602176634e-13 / 4.66e-4 = 3.43815e-9 Gy`。
- 统计检查：`|ΣE − N·E| ≤ 2%·N·E + 3σ`；`σ` 取 `scorer_statistics.rel_error·D`。10 MeV
  质子全部停在 2 mm 内，逐事件 edep 方差很小（核反应/逃逸 <0.5%），N=20000 的统计项
  ≪0.1%，所以 2% 是系统余量；因子 2 错误是 100%，不可能被 2% 掩盖。
- **注意**：这是“整个 2 mm 靶质量上的平均剂量”，不是 Bragg 峰局部剂量；质子只走到
  0.715 mm，后 1.285 mm 没有能量沉积，但分母仍是整个靶质量（scorer 的定义）。不要拿
  “射程处局部剂量”来对比。

### 5. 权重因子测试（w=1 vs w=2）

用 §0.8 的相空间对，两个 run 只差 `ps_w1.csv`/`ps_w2.csv` 的最后一列：

| 量 | w=1 | w=2 | 期望 | 若 w² | 若 w⁰ |
| --- | --- | --- | --- | --- | --- |
| `raw_edep_MeV` / `raw_dose_Gy` | R | R | **逐位相同**（≤1e-12） | 若权重漏进 raw 则变 | 同左 |
| `weighted_edep_MeV` / `weighted_dose_Gy` | W | 2W | 比值 2（≤1e-9） | 比值 4 | 比值 1 |
| `mass_kg` | m | m | 相同 | 相同 | 相同 |
| `stats(weighted).rel_error` | r | r | 相同（≤1e-9） | 相同（R 对公共缩放不变） | 相同 |
| `n_events` / `entries` | 20000 | 20000 | 相同 | 相同 | 相同 |

失败解释：

- weighted 比值 4 → 权重在 Dose 的加权累加里被乘了两次（`edep*w*w`）；
- weighted 比值 1 → 权重没进加权列（或 w 列被忽略）；
- raw 列出现 >1e-12 的差异 → 权重漏进了 raw 累加，或两个 run 的传输/种子不一致
  （先检查 phase-space 文件除最后一列外是否逐字节相同、seed 是否相同）。
- 若 `mass_kg` 本身被错乘 2，**这个权重对不会发现**（两个 run 的质量都错，比值仍是 2）；
  必须靠 A1 的 G 链。这正是“权重对 + 几何质量”两条链缺一不可的原因。

### 6. 样本量 / 种子 / 阈值

- N=20000，seed=20261120（标称）；权重对 seed=20261130（w=1/w=2 相同）。
- 算术检查（A1–A9）：不需要统计量；N 只要 ≥1 就能做，20000 是为了同时做 §4 的物理
  sanity。A4/A5 的 1e-9 容差来自 2 万行 12 位输出的求和舍入。
- 统计检查（S1）：`|ΣE − N·E| ≤ 0.02·N·E + 3σ`；`σ` 取 rel_error×D。若 rel_error>0.5%，
  记“统计不足”，把 N 增到 4×（σ 减半）再预注册；不得放宽 2%。
- 权重对：确定性，`|ratio−2| ≤ 1e-9·2`；raw 差 `≤1e-12·max(|raw|,1)`。若 raw 差在
  1e-12–1e-9 之间，先查输出舍入/文件差异，不直接判失败；>1e-9 判失败。
- 停止条件：`n_events != 20000`、`uncertainty_status != approximate`、缺
  `dose_volume_summary`/`event_edep`/`hits`/`scorer_statistics` 任一文件 → 失败，保留原件。

### 7. 陷阱 / 限制

1. **质量列自洽 ≠ 质量正确**：A2 的恒等式用 summary 自己的 `mass_kg`；若 `mass_kg` 被
   错乘 2，A2 仍然过。必须看 A1 的 `2.33e-6×V`。这是本病例的核心设计。
2. **体积不参与 Dose**：Dose 只用质量；把体积当质量的错误会先在 A1 暴露（`mass_kg=200`
   vs `4.66e-4`），但“体积因子乘了两次”这种 Fluence 式错误在 Dose 里没有定义，不要
   把 Dose 当成体积检查。
3. **靶厚 2 mm 不是射程**：10 MeV 质子只到 0.715 mm；`ΣE=N·E` 仍成立，因为质子停在
   靶内。若把靶厚改成 0.5 mm（<射程），质子会穿出，`ΣE<N·E`，§4 的判据会失败——这不
   是 scorer 错，是几何选错。**不要把靶厚改到小于射程。**
4. **1 mm cut 的影响**：δ 电子被抑制，能量局部沉积；总 edep 仍守恒。若把 cut 改成
   10 µm，δ 电子会增加 hits 行、并在靠近表面处少量逃出，但 2 mm 靶足够厚，总 edep 仍近似守恒；不过
   hits 的逐 step 结构和 A5 的 1e-9 会更难满足。本组固定 1 mm。
5. `hits` 只写 `edep>0` 的 step；质子打硅每个 step 都有沉积，所以 A5 完整。若出现
   `edep=0` 的质子 step（边界/零长度），A5 会比 summary 少；此时以 `event_edep` 为准，
   并记录缺失 step 数，不要直接判 scorer 错。
6. `GetMass(true,false,preStepMaterial)` 在 daughter/replica 几何下的语义未专项验证
   （契约 :80）。本组用无 daughter 的单 box；换成 layered_device 需另立质量审计。
7. `event_edep` 是否为零事件写行未验证；本组全命中，不触发。若改用 12×12 束（30.6%
   零贡献），先用 10 事件样本确认行数，再决定 A4 用 `entries` 还是 `N`。
8. 权重对的 raw 列“逐位相同”依赖两个 run 的 RNG 序列完全相同；phase-space 源不消耗
   位置抽样 RNG，weight 不参与物理，理论上成立。若实际有差异，先查文件/种子，再查
   scorer 是否把 weight 带进了 raw。

### 8. 配置有效性说明

| 键/特性 | 状态 | 说明 |
| --- | --- | --- |
| `dose=true` + `auto_create_default_scorers=true` | 已确认 | `ScoringManager.cc:697-699`；缺后者会在首事件前抛错 |
| `event_edep=true` | 已确认 | `OutputManager.cc` 逐事件写 `raw/weighted_edep_MeV` |
| `hits=true` | 已确认 | v3 表头见 §0.5 |
| `mass_kg` v2 列 | 已确认 | `DoseScorer.cc:96-107`；文档仍写 `dose_volume_csv_v1` 8 列，是文档漂移，以代码 11 列为准 |
| `[material.SiRef]` 单组分 `G4_Si:1` | **待验证** | 解析器只拒绝空列表（`MaterialIniReader.cc:454-458`），但示例没有单组分；若运行期拒绝，回退 `material = G4_Si`（NIST 密度 2.33 g/cm³），并在脚本里把密度来源改成 `G4_Si` 的内置值 |
| `@Z_MM@=-1.01` 的 `center` 语法 | 已确认 | 手册 `center = 0,0,-30 mm` 同型 |
| `scorer_statistics_r1.csv` 命名 | 代码已确认，实际以目录为准 | `runId>0` 加 `_r<R>` |
| `hits.volume` 值 | **待验证** | 期望 `Target`；首次 10 事件小样本核对，若是路径则按后缀 `Target` 匹配 |

---

## IMP-FLU-01 体积因子与 `Φ=ΣL/V`

### 1. 目的（可证伪的公式/因子）

目标公式：

```text
Φ_raw = Σ_steps L_i[mm] / V_mm3
V_geom = 10×10×t mm³
```

本病例要证伪：

1. 体积被**重复除**：`Φ = L/V²`；
2. 体积被换成**质量**：`Φ = L/(ρV)`；
3. `volume_mm3` 列本身被错乘/错除（cm³/mm³ 混淆、用了源面积而不是靶面积）；
4. 长度被**重复计**（边界 step 两次、worker 合并时长度加了两次）；
5. `weighted_fluence` 把权重乘了两次/没乘。

**不能发现**：

- 中性粒子/零沉积 step 的注量：`hits` 默认不写这些 step（summary 仍计分），R 链会短；
  本组用质子打硅，所有 step 有沉积，避免了这个盲区；
- 表面穿越定义（surface crossing）与 track-length 定义的差异：scorer 是 track-length，
  本组也按 track-length 重算；若有人拿“穿越次数/面积”对比，薄靶/斜束会不同；
- 非 box 敏感体的 `GetCubicVolume()` 近似误差（本组用 box）；
- 源面积/束流均匀性本身错（G 链用同一个源配置；解析 1/A 假设均匀方束，实际 GPS 方束
  是均匀的，但若源形状写错，重算也会跟着错）。

### 2. 精确输入

公共模板（§0.3）+ 下表：

| 键 | 值 |
| --- | --- |
| `@NAME@` | `imp-flu-01` |
| `@SEED@` | `20261121` |
| `@OUTDIR@` | `out/imp-flu-01` |
| `@T_MM@` | `0.1` |
| 靶尺寸 | `10 mm, 10 mm, 0.1 mm`（V=10 mm³） |
| 材料/密度 | `SiRef`，`2.33 g/cm³` |
| `@E_MEV@` | `100` |
| `@HALF_MM@` | `6`（12×12 mm 束；靶 10×10，几何命中率 p=100/144） |
| `@Z_MM@` | `-0.06` |
| `@N_EVENTS@` | `20000` |
| `@EVENT_EDEP@` | `false` |
| `@DOSE@` / `@FLUENCE@` / `@LET@` / `@DISP@` | `false` / `true` / `false` / `false` |
| `@EXTRA@` | 空 |
| physics | `FTFP_BERT_EMZ`，`default_cut=1 mm`，`biasing=false` |
| threads/seed | `1` / `20261121` |

运行命令同 §0.4。权重对：`imp-flu-01-w1`/`w2`，`N=20000`、`seed=20261131`（相同）、
相空间 `x,y` 用 Halton(2,3) 映射到 `[-6,6] mm`，`z=-0.06 mm`，`E=100 MeV`，其余同 §0.8。

### 3. 独立重算路径

读：

- `fluence_volume_summary_t0.csv`（1 行，`volume_name=Target`）；
- `hits_t0.csv`（按 `volume=Target` 过滤；**全部粒子**求和，不筛质子）；
- `scorer_statistics_r1.csv`（`scorer=fluence`，`quantity=raw_fluence`/`weighted_fluence`）。

脚本：

```text
t_mm      = 0.1
V_mm3     = 10 * 10 * t_mm            # = 10
p_geom    = (10*10) / (12*12)         # = 100/144 = 0.694444...
L_raw     = sum(hits.stepLength_mm where volume == Target)
L_w       = sum(hits.weight * hits.stepLength_mm where volume == Target)
Phi_raw   = L_raw / V_mm3
Phi_w     = L_w   / V_mm3
Phi_ana   = N * p_geom * t_mm / V_mm3 # = N / A_beam = N/144
```

对照：

| 检查 | 对象 | 容差 |
| --- | --- | --- |
| A1 体积 | `volume_mm3 == 10` | 1e-9 |
| A2 raw 恒等 | `raw_fluence_mm-2 == raw_track_length_mm/volume_mm3` | 1e-12 |
| A3 weighted 恒等 | `weighted_fluence_mm-2 == weighted_track_length_mm/volume_mm3` | 1e-12 |
| A4 hits 长度 | `L_raw == raw_track_length_mm` | 1e-9 |
| A5 hits 加权长度 | `L_w == weighted_track_length_mm` | 1e-9 |
| A6 统计值 | `stats(raw_fluence).value == raw_fluence_mm-2`；`sum == value`；`mean == value/N` | 1e-12 |
| A7 统计误差 | `stats(raw_fluence).rel_error == sqrt(S2/S²−1/N)`，`S=raw_track_length_mm`、`S2=raw_track_length_sum_sq_mm2`；weighted 同理 | 1e-9 |
| A8 事件数 | `n_events == 20000`；`entries ≈ N·p = 13889`（允许 4σ 二项波动） | 精确 / 4σ |
| A9 统计状态 | `approximate` | 精确 |

**G vs R**：A1 的 `V_mm3` 来自 G；`volume_mm3` 是**被检验列**，A2 只证明 scorer 内部
自洽；A4/A5 来自 R；A1/A4 联合才能抓“体积列错”和“长度重复计”。

### 4. 期望解析值/关系（推导）

- `V = 10×10×0.1 = 10 mm³`。
- 12×12 mm 方束打 10×10 mm 靶：几何命中率 `p = 100/144 = 0.694444`。
- 每个命中初级在 0.1 mm 硅中近似直线穿过，贡献 `t=0.1 mm` 径迹长度；100 MeV 质子的
  多次散射角很小（≪1°），路径增加可忽略；核反应 secondary 的附加长度 <0.1%。
- `L_raw ≈ N·p·t = 20000×0.694444×0.1 = 1388.889 mm`。
- `Φ_raw = 1388.889/10 = 138.8889 mm^-2`；每初级 `Φ/N = 1/144 = 6.94444e-3 mm^-2`。
- 统计：每次初级贡献 `t`（概率 p）或 0；`σ_Φ/Φ = sqrt((1−p)/(pN)) = 0.00469 = 0.469%`。
  `2% / 0.469% = 4.26σ`；N=20000 足够。若要把 3σ 压到 1%，需 `N ≥ (1/0.01)²(1−p)/p
  = 4400`；20000 已超过。
- 判据：`|Φ_raw − N/A_beam| ≤ 0.02·(N/A_beam) + 3σ`；`A_beam=144 mm²`。因子 2 的体积
  错误是 100%，远超 2%。

### 5. 权重因子测试（w=1 vs w=2）

| 量 | w=1 | w=2 | 期望 | 若 w² | 若 w⁰ |
| --- | --- | --- | --- | --- | --- |
| `raw_track_length_mm` / `raw_fluence_mm-2` | R | R | 逐位相同（≤1e-12） | 若权重漏进 raw 则变 | 同左 |
| `weighted_track_length_mm` / `weighted_fluence_mm-2` | W | 2W | 比值 2（≤1e-9） | 比值 4 | 比值 1 |
| `volume_mm3` | V | V | 相同 | 相同 | 相同 |
| `stats(weighted).rel_error` | r | r | 相同（≤1e-9） | 相同 | 相同 |
| `n_events` / `entries` | 20000 / ~13889 | 同 | 相同 | 相同 | 相同 |

- 比值 4 → `weightedStep = stepLength*weight*weight`；
- 比值 1 → 权重没进加权列；
- raw 差异 >1e-12 → 权重漏进 raw，或两个 run 的文件/种子不一致；
- 体积错乘 2 不会改变这个比值（两个 run 都错），必须靠 A1 + A4 的 G/R 链。

### 6. 样本量 / 种子 / 阈值

- N=20000，seed=20261121；权重对 seed=20261131（相同）。
- 解析 σ=0.469%；`tol=2%` 是 4.26σ。若实测 `entries` 偏离 `N·p` 超过 4σ
  （`σ_entries = sqrt(Np(1−p)) ≈ 65`），先查源形状/靶位置，不要直接判 scorer 错。
- 算术检查 A1–A7 用 1e-12/1e-9；A8/A9 精确。
- 权重对：确定性，`|ratio−2| ≤ 1e-9·2`；raw 差 ≤1e-12。
- 停止条件：`n_events != N`、`entries` 与 `N·p` 差 >4σ、缺文件、`uncertainty_status !=
  approximate` → 失败并保留原件。

### 7. 陷阱 / 限制

1. **体积列自洽 ≠ 体积正确**：A2 用 summary 自己的 `volume_mm3`；若它被错乘 2，A2 仍过。
   A1 的 `10×10×t` 才是独立裁判；A4 的 `L_raw` 与 summary 的长度对照能抓“长度重复计”，
   但抓不到“体积错”。
2. **hits 只含 edep>0 的 step**：质子打硅全有沉积，A4 完整；若用 geantino/中性粒子，
   hits 会缺行，A4 失败是**预期**的，不是 scorer 错。此时只能信 summary（它走零沉积分支），
   或改用 `test_fluence_scoring.py` 的 geantino 场景（那是既有测试，不是本病例）。
3. **束流/靶面积**：解析值 `1/A_beam` 用 12×12 的源面积；若把 `halfx` 改成 5，`p=1`，
   期望变成 `1/100`，判据必须同步改。**不要把源面积和靶面积混用**：`p=100/144` 是靶/
   源面积比，不是 `1/144` 的笔误。
4. **斜束**：`direction=0,0,1` 固定；若倾斜，径迹长度按 `t/cosθ` 变，`1/A` 不再成立。
5. **厚靶**：0.1 mm 足够薄，多次散射/核反应 <0.1%；若把 t 加到 mm 级，路径增加和
   secondary 会进入 2% 预算，需重新预注册。
6. **非 box 体积**：`GetCubicVolume()` 对圆柱/复杂 solid 是近似（契约 :80 未验证）；
   本组用 box。
7. **worker 合并**：threads=1 不涉及；若改 MT，summary 是 per-worker，消费者必须先把
   长度相加、体积只取一次（消费者的合并逻辑必须先加长度、体积只取一次）。因子检查在
   MT 下要另立合并审计，本组不覆盖。
8. **`hits.volume` 值**：期望 `Target`；首次小样本核对，若是路径则按后缀匹配。否则 A4
   会因过滤不到而“0 长度”，看起来像 scorer 错。

### 8. 配置有效性说明

| 键/特性 | 状态 | 说明 |
| --- | --- | --- |
| `fluence=true` + `auto_create_default_scorers=true` | 已确认 | `ScoringManager.cc:697-699` |
| daughter-free 敏感体 | 已确认 | `DoseContext.hh`：`GetNoDaughters()==0` 才给 `fluenceVolume`；单 box 满足 |
| `volume_mm3` v2 列 | 已确认 | `FluenceScorer.cc:118-120`；文档仍写 v1 8 列，是漂移 |
| `hits.stepLength_mm` / `weight` | 已确认 | `OutputManager.cc:823-830` |
| `[scoring] hits=true` | 已确认 | 需要 R 链 |
| `[material.SiRef]` 单组分 | **待验证** | 同 IMP-DOSE-01 §8 |
| `hits.volume` 值 | **待验证** | 同 §0.9 |
| 12×12 方束的均匀性 | 已确认（GPS plane/square） | 手册 `[source]`；若实际有边缘效应，A4 会看出来 |

---

## IMP-LET-01 比值分子/分母与权重标度

### 1. 目的（可证伪的公式/因子）

目标公式（`s=LETstep/(MeV/mm)`，`l=stepLength/mm`，`w=weight`）：

```text
wl   = w·l
wSl  = w·l·s
wS2l = w·l·s²
LET_t = ΣwSl / Σwl          [keV/µm]
LET_d = ΣwS2l / ΣwSl        [keV/µm]
```

本病例要证伪：

1. 分子/分母**错配**：`LET_t = ΣwS2l/Σwl` 或 `LET_d = ΣwSl/ΣwS2l`；
2. 权重只进分子/只进分母（`w²` 进 `wSl` 但 `w` 进 `wl`，或反之）；
3. `sum_wl`/`sum_wSl`/`sum_wS2l` 的**步集合**与 `hits` 不一致（漏 step、重复 step、
   粒子过滤失效）；
4. `scorer_statistics` 的 ratio 行与 summary 的矩不一致（delta 法的 A/B/C 收错）。

**不能发现**：

- **质量/体积因子**：LET 的公式里根本没有 mass/volume；`LETScorer.cc` 不引用它们。
  所以 LET 病例**不能**用来抓“质量乘两次/体积乘两次”，不要这样宣称。
- `S` 本身的模型错（`G4EmCalculator::ComputeElectronicDEDX` 用错材料/能量、电子阻止
  本领 vs 总阻止本领）：hits v3 不输出 `LETstep`，公共输出里没有独立的逐 step S 可对。
  绝对 S 的检查交给 REF-LET-01（PSTAR，1.5%+3σ）。
- 一个**与 w 无关的常数因子**同时乘到三个 sum 上：比值不变、权重标度也不变；只有绝对
  S 检查（REF-LET-01）能发现。

### 2. 精确输入

公共模板（§0.3）+ 下表。LET 有两个能量子例（100 MeV 与 10 MeV），用来做“S 随能量
下降”的定性排序；权重对用 100 MeV。

| 键 | 100 MeV 子例 | 10 MeV 子例 |
| --- | --- | --- |
| `@NAME@` | `imp-let-01-100` | `imp-let-01-10` |
| `@SEED@` | `20261122` | `20261123` |
| `@OUTDIR@` | `out/imp-let-01-100` | `out/imp-let-01-10` |
| `@T_MM@` | `0.02` | `0.02` |
| 靶尺寸 | `10 mm, 10 mm, 0.02 mm` | 同左 |
| 材料/密度 | `SiRef`，`2.33 g/cm³` | 同左 |
| `@E_MEV@` | `100` | `10` |
| `@HALF_MM@` | `5`（10×10 束，全命中） | 同左 |
| `@Z_MM@` | `-0.02` | 同左 |
| `@N_EVENTS@` | `2000` | `2000` |
| `@EVENT_EDEP@` | `false` | `false` |
| `@DOSE@` / `@FLUENCE@` / `@LET@` / `@DISP@` | `false`/`false`/`true`/`false` | 同左 |
| `@EXTRA@` | `[scoring.let]` + `particles = proton` | 同左 |
| physics | `FTFP_BERT_EMZ`，`default_cut=1 mm` | 同左 |
| threads/seed | `1` / `20261122` | `1` / `20261123` |

权重对：`imp-let-01-w1`/`w2`，`N=2000`、`seed=20261132`（相同）、相空间 `x,y` 用
Halton(2,3) 映射到 `[-5,5] mm`、`z=-0.02 mm`、`E=100 MeV`；`[source]` 只有
`phase_space_file`；其余同 100 MeV 子例。

### 3. 独立重算路径

读：

- `let_volume_summary_t0.csv`（1 行，`volume_name=Target`，`particles` 应为 `proton`）；
- `hits_t0.csv`（按 `volume=Target` 且 `particle=proton` 过滤）；
- `scorer_statistics_r1.csv`（`scorer=let`，`quantity=let_t`/`let_d`，`estimator=ratio`）。

脚本：

```text
t_mm    = 0.02
L_hits  = sum(hits.stepLength_mm where volume==Target and particle==proton)
steps   = count(hits rows where volume==Target and particle==proton)

A_t = sum_wSl_MeV;              B_t = sum_wl_mm
A_d = sum_wS2l_MeV2_per_mm;     B_d = sum_wSl_MeV
let_t_calc = A_t / B_t
let_d_calc = A_d / B_d

R_t = sqrt(sum_sq_wSl/A_t^2 + sum_sq_wl/B_t^2
           - 2*sum_wl_x_wSl/(A_t*B_t))
R_d = sqrt(sum_sq_wS2l/A_d^2 + sum_sq_wSl/B_d^2
           - 2*sum_wSl_x_wS2l/(A_d*B_d))
```

对照：

| 检查 | 对象 | 容差 |
| --- | --- | --- |
| A1 比值定义 | `let_t == sum_wSl/sum_wl`；`let_d == sum_wS2l/sum_wSl` | 1e-12 |
| A2 不等式 | `let_d ≥ let_t`（Jensen/Cauchy–Schwarz，任意正权重） | `≥ −1e-12·let_t` |
| A3 长度 | `sum_wl_mm == L_hits` | 1e-9 |
| A4 步数 | `steps == count(hits proton rows)` | 精确 |
| A5 统计误差 | `stats(let_t).rel_error == R_t`；`stats(let_d).rel_error == R_d` | 1e-9 |
| A6 统计值 | `stats(let_t).value == let_t`；`stats(let_d).value == let_d` | 1e-12 |
| A7 事件数 | `n_events == 2000`；`entries` 应接近 2000 | 精确 |
| A8 状态 | `approximate` | 精确 |
| S1 能量序 | `let_t(10 MeV) > let_t(100 MeV)` | 定性 |
| S2 PSTAR 量级 | 100 MeV ≈1.36 keV/µm；10 MeV ≈8.06 keV/µm | ±2% 仅 sanity；REF-LET-01 的 1.5% 判据不在此重复 |

**G vs R**：LET 没有 G 链（质量/体积不参与）；R 链给出 `L_hits`/`steps`；I 链给出
权重；`S` 本身没有独立来源。A1/A2/A5 是“同一批矩的自洽”，A3/A4 是“scorer 的步集合
与 hits 的步集合一致”，§5 是“权重只进一次”。三条合起来是本组能给出的最强检查。

**为什么 A2 是有意义的**：`let_d = E_w[S²]/E_w[S]`，`let_t = E_w[S]`；由 Jensen，
`E[S²] ≥ E[S]²`，所以 `let_d ≥ let_t`（正权重）。若分子分母错配（例如 `let_d` 用了
`ΣwS2l/Σwl`），这个不等式可能被破坏。薄层下 S 近似常数，`let_d≈let_t`，不等式是
“近似等号”，所以它的主要价值是抓**明显错配**，不是抓 0.1% 的偏差。

### 4. 期望解析值/关系（推导）

- 靶 `10×10×0.02 mm`，V=2 mm³（LET 不用 V）。
- 10×10 束全命中；每个 100 MeV 质子在 0.02 mm 硅中近似单步，`l=0.02 mm`，`w=1`。
- `Σwl = N·l = 2000×0.02 = 40 mm`；`steps=2000`。
- `S` 由 Geant4 EM calculator 在步平均能量处给出；用 PSTAR Si 的电子阻止本领做量级：
  `S(100 MeV)=5.836 MeV cm²/g`，`LET = S·ρ·0.1 = 5.836×2.33×0.1 = 1.3598 keV/µm`；
  `S(10 MeV)=34.58`，`LET=8.0571 keV/µm`；比值 `34.58/5.836=5.925`。
- 薄层能量损失：100 MeV 在 0.02 mm Si 中 `dE≈5.836×2.33×0.002=0.0272 MeV`（0.027%）；
  10 MeV 约 `0.161 MeV`（1.6%）。所以 `S` 在步内近似常数，`let_d≈let_t`。
- 若 `ΣwSl ≈ 40×1.36 = 54.39 MeV`、`ΣwS2l ≈ 40×1.36² = 73.96 MeV²/mm`，则
  `let_t≈let_d≈1.36 keV/µm`；10 MeV 子例 `ΣwSl≈322.29`、`ΣwS2l≈2596.7`，
  `let_t≈8.06`。这些数是**量级 sanity**，不是本病例的独立通过判据；实际 Geant4 S 与
  PSTAR 可能差 ~1%（历史水层 100 MeV 0.55%、10 MeV 1.4%），绝对判据见 REF-LET-01。
- 定性排序：10 MeV 的 S 应明显大于 100 MeV（约 5.9×）；若反了，说明能量/材料/粒子
  过滤有严重错。

### 5. 权重因子测试（w=1 vs w=2）

这是本病例最强的一节，因为 LET 的比值对公共权重是**不变**的，但三个 sum 的**标度指数**
会暴露权重被乘了几次：

| 量 | w=1 | w=2 | 期望标度 | 若 w² 进线性 sum | 若 w⁰ |
| --- | --- | --- | --- | --- | --- |
| `sum_wl_mm` | B | 2B | ×2 | ×4 | ×1 |
| `sum_wSl_MeV` | A | 2A | ×2 | ×4 | ×1 |
| `sum_wS2l_MeV2_per_mm` | C | 2C | ×2 | ×4 | ×1 |
| `sum_sq_wl_mm2` | B2 | 4B2 | ×4（每事件值平方，w²） | ×16 | ×1 |
| `sum_sq_wSl_MeV2` | A2 | 4A2 | ×4 | ×16 | ×1 |
| `sum_sq_wS2l_MeV4_per_mm2` | C2 | 4C2 | ×4 | ×16 | ×1 |
| `sum_wl_x_wSl_MeV_mm` | X | 4X | ×4 | ×16 | ×1 |
| `sum_wSl_x_wS2l_MeV3_per_mm` | Y | 4Y | ×4 | ×16 | ×1 |
| `let_t` / `let_d` | T/D | T/D | **不变** | 若只错一侧则 ×2/×0.5 | 不变 |
| `steps` / `n_events` | 2000 | 2000 | 相同 | 相同 | 相同 |
| `stats(let_t/let_d).rel_error` | r | r | 相同（公共缩放不变） | 若矩错位则变 | 相同 |

判据：

- `sum_wl`、`sum_wSl`、`sum_wS2l` 的 `ratio` 必须 =2（1e-9 相对）；
- 五个平方/交叉和的 `ratio` 必须 =4（1e-9 相对）；
- `let_t`、`let_d` 的 `ratio` 必须 =1（1e-9 相对）；
- `steps`、`n_events`、`rel_error` 必须不变。

失败解释：

- 线性 sum ×4 → 权重在 `wl` 里就被乘了两次（`w²·l`），或 `wSl` 用了 `w²`；
- 平方和 ×16 → 权重在 per-event 值里已经是 `w²`，再平方成 `w⁴`；
- 线性 sum ×1 → 权重没进（`w⁰`）；
- `let_t` 变了而 sum 标度看起来“正常” → 分子/分母不是同一批步（A3/A4 会先暴露）；
- `rel_error` 变了 → delta 法的 A/B/C 不是同一批矩，或权重只进了部分累加器。

**注意**：薄层下 `let_t≈let_d`，不要用“交换 let_t/let_d 后不相等”来证明定义区分——
它们本来就近似相等（旧草案的“交换检查”在这个几何下不可区分）。本病例改用**权重标度 +
矩一致性 + 步集合**，不依赖两者数值差异。

### 6. 样本量 / 种子 / 阈值

- N=2000（每个能量子例），seed=20261122（100 MeV）/20261123（10 MeV）；
  权重对 seed=20261132（w=1/w=2 相同）。
- 算术检查 A1–A7 用 1e-12/1e-9；A8 精确。N 只要 ≥2 就能算矩；2000 是为了让
  `rel_error` 稳定、且 `entries≈N`。
- 权重对：确定性，线性 sum 比值 2±1e-9；平方/交叉和 4±1e-9；比值 1±1e-9。
- 统计检查：`let_t` 的绝对量级用 REF-LET-01 的 1.5%+3σ，本病例不重复；本病例只要求
  S1 的能量序（10 MeV > 100 MeV）和 S2 的 ±2% 量级 sanity。若 S2 超 2%，先查 PSTAR
  引用/单位（`MeV cm²/g × g/cm³ × 0.1 = keV/µm`），不要直接判 scorer 错。
- 停止条件：`n_events != 2000`、`steps != hits proton rows`、`let_d < let_t`、
  `uncertainty_status != approximate`、缺文件 → 失败并保留原件。

### 7. 陷阱 / 限制

1. **hits v3 没有 `LETstep`**：无法从公共输出逐 step 独立重算 `S`。本病例的 A1/A2/A5
   是“同一批矩的自洽”，A3/A4 是“步集合一致”，§5 是“权重标度”；它们**不能**证明
   `S` 的物理正确。绝对 S 必须走 REF-LET-01 的 PSTAR 检查。这是本组最强的 LET 检查
   被阻塞的地方（§10 G1）。
2. **步集合**：LET 的零沉积分支（`SensitiveDetector.cc:92`）会把 `edep≤0` 但
   `stepLength>0` 的带电 step 计进 LET，却不写 hits 行。质子打硅每个 step 都有沉积，
   所以 A3/A4 完整；若换成中性粒子/真空，`sum_wl > L_hits` 是**预期**的，不是
   scorer 错。此时只能用 summary + 权重标度，A3/A4 标 `not_applicable`。
3. **`steps` 是 LET 步数**，不是 hits 行数（两者在本几何相等）；若粒子过滤写成
   `all`，电子/次级会进来，`steps` 变大、`sum_wl` 变大，A3/A4 会失败——这正是粒子
   过滤失效的信号。
4. **薄层近似**：`let_t≈let_d`；不要用两者差值做判据（旧草案的交换检查不可区分）。
   若要放大 `let_d−let_t`，需要厚层/多能量混合，但那时 S 的变化会让“常数 S”推导失效，
   应另立病例。
5. **权重标度**：`sum_sq_*` 是“每事件值的平方”之和，所以对 w 的标度是 `w²`（×4 for
   w=2），不是 `w⁴`；`sum_wS2l` 是线性的（×2），不是平方。把这两个搞混会误判。
6. **`let_d ≥ let_t`** 是数学不等式，不是物理精度判据；薄层下近似等号，允许
   `−1e-12·let_t` 的舍入。若明显违反，先查分子/分母是否用了不同的权重/步集合。
7. **`[scoring.let] particles=proton`**：这是 scorer 的过滤器；hits 里仍有电子/次级。
   A3/A4 必须按 `particle=proton` 过滤，否则会把 hits 的全部粒子长度与 proton 的
   `sum_wl` 比，得到假失败。
8. **统计量**：`scorer_statistics` 的 ratio 行 `sum`/`sum_sq`/`mean` 为空；不要把它们
   当 0，也不要用它们重算 `R`。用 `let_volume_summary` 的三组和/交叉和（§0.7）。
9. **能量序**：10 MeV 的 S 大于 100 MeV，但若束流/靶厚/材料写错，序可能反；S1 是
   定性检查，不能替代绝对 S。

### 8. 配置有效性说明

| 键/特性 | 状态 | 说明 |
| --- | --- | --- |
| `let=true` | 已确认 | `ScoringManager.cc:651+`；LET 不在 GUI generated 子集，但 CLI/INI 可用 |
| `[scoring.let] particles=proton` | 已确认 | `ScoringManager.cc:763-780`；大小写/逗号列表 |
| `let_volume_summary` v2 列 | 已确认 | `LETScorer.cc:149-160`；`sum_wl_x_wSl` 等交叉和存在 |
| `scorer_statistics` ratio 行 | 已确认 | `estimator=ratio`，`sum/sum_sq/mean` 空；`rel_error` 是 delta 法 |
| `hits` 无 `LETstep` | **已知缺口** | `OutputManager.cc:823-830`；v2 的 LET 列只是 schema 识别字符串 |
| `sum_wl == hits` | **待验证**（首次 10 事件） | 零沉积分支不写 hits；本几何应相等，先用小样本确认 |
| `steps == hits proton rows` | **待验证**（同上） | 同上 |
| `[material.SiRef]` 单组分 | **待验证** | 同 IMP-DOSE-01 §8 |

---

## IMP-DDD-01 体积因子、100 换算与 NIEL 折积

### 1. 目的（可证伪的公式/因子）

目标公式（`l=stepLength/mm`，`w=weight`，`V=volume_mm3`，`NIEL` 单位 MeV cm²/g）：

```text
L_w  = Σ w·l                         [mm]
DDD  = 100 · L_w · NIEL(E_mean) / V  [MeV/g]
```

本病例要证伪：

1. 体积被**重复除**（`DDD = 100·L·NIEL/V²`）或体积列本身错；
2. **漏乘/多乘 100**（`mm²/cm²` 换算）；
3. 权重乘了两次（`w²`）或没乘（DDD 的 `track_length_mm` 本身就是加权长度，没有 raw 列）；
4. 长度的步集合与 hits 不一致（漏 step/重复 step）；
5. 能量域边界处理错（`out_of_range_track_length_mm != 0`）；
6. 用**质量**代替体积（`DDD = 100·L·NIEL/m`，会被 A1/A3 抓）。

**不能发现**：

- NIEL 表本身的绝对正确性：常量表是输入，实表折积也用同一张表；表级审计是
  REF-DDD-02 的事；
- 逐 step 的 `E_mean` 精确值：hits 只给 pre-step `kineticEnergy_MeV` 和 `edep_MeV`，
  `E_mean≈KE−0.5·edep` 是近似；精确的 `NIEL(0.5(pre+post))` 只在 scorer 内部；
- 非 box 敏感体的 `GetCubicVolume()` 近似；
- 时间/源强归一化（DDD 不做）。

### 2. 精确输入

公共模板（§0.3）+ 下表：

| 键 | 值 |
| --- | --- |
| `@NAME@` | `imp-ddd-01` |
| `@SEED@` | `20261124` |
| `@OUTDIR@` | `out/imp-ddd-01` |
| `@T_MM@` | `0.1` |
| 靶尺寸 | `10 mm, 10 mm, 0.1 mm`（V=10 mm³） |
| 材料/密度 | `SiRef`，`2.33 g/cm³` |
| `@E_MEV@` | `100` |
| `@HALF_MM@` | `6`（12×12 束；p=100/144） |
| `@Z_MM@` | `-0.06` |
| `@N_EVENTS@` | `20000` |
| `@EVENT_EDEP@` | `false` |
| `@DOSE@` / `@FLUENCE@` / `@LET@` / `@DISP@` | `false`/`false`/`false`/`true` |
| `@EXTRA@` | `[scoring.displacement]` + `proton = niel_const.csv` |
| physics | `FTFP_BERT_EMZ`，`default_cut=1 mm`，`biasing=false` |
| threads/seed | `1` / `20261124` |

`niel_const.csv`（放在 main.ini 同目录；能量单位 MeV，NIEL 单位 MeV cm²/g）：

```csv
energy_MeV,niel_MeV_cm2_g
1e-12,0.003
1e6,0.003
```

说明：两行 NIEL 相同，`NielTable` 的 log-log 插值在任意 E 都返回 0.003（常数），
所以这个子例把“能量依赖”从算术检查里剔除，专门检验 `100·L/V` 因子。100 MeV 质子在
0.1 mm 硅中 `E_mean≈99.93 MeV`，落在 [1e-12,1e6] 内，`out_of_range=0`。

权重对：`imp-ddd-01-w1`/`w2`，`N=20000`、`seed=20261133`（相同）、相空间
`x,y` 用 Halton(2,3) 映射到 `[-6,6] mm`、`z=-0.06 mm`、`E=100 MeV`；`[source]` 只有
`phase_space_file`；其余同标称。

实表子例（可选，同一几何，把 `niel_const.csv` 换成仓库的
`scenarios/semiconductor/niel/si_proton.csv`；路径按 main_ini_directory 解析）：
`@NAME@=imp-ddd-01-real`，其余相同；用来做 §4 的实表量级检查，**不改变**常量表子例的
算术判据。

### 3. 独立重算路径

读：

- `displacement_volume_summary_t0.csv`（1 行，`volume_name=Target`，`particle=proton`，
  `niel_table` 指向输入表）；
- `hits_t0.csv`（按 `volume=Target` 且 `particle=proton` 过滤）；
- `scorer_statistics_r1.csv`（`scorer=displacement`，`quantity=ddd_total`/`ddd_proton`）。

常量表脚本：

```text
t_mm   = 0.1
V_mm3  = 10 * 10 * t_mm                # = 10
NIEL0  = 0.003
L_w    = sum(hits.weight * hits.stepLength_mm where volume==Target and particle==proton)
DDD_calc = 100 * L_w * NIEL0 / V_mm3
```

实表脚本（近似逐 step 折积，标 weaker）：

```text
for each hit row (proton, Target):
    E_mean ≈ kineticEnergy_MeV - 0.5*edep_MeV
    NIEL_i = loglog_interp(E_mean, table)     # 与 NielTable 同规则
    DDD_fold += 100 * weight * stepLength_mm * NIEL_i / V_mm3
```

对照：

| 检查 | 对象 | 容差 |
| --- | --- | --- |
| A1 体积 | `volume_mm3 == 10` | 1e-9 |
| A2 hits 长度 | `track_length_mm == L_w` | 1e-9 |
| A3 常量表恒等 | `ddd_MeV_g == 100·track_length_mm·0.003/volume_mm3` | 1e-12 |
| A4 能域 | `out_of_range_track_length_mm == 0` | 精确 |
| A5 统计值 | `stats(ddd_total).value == ddd_MeV_g`；`stats(ddd_proton).value == ddd_MeV_g`（只有 proton 有表时） | 1e-12 |
| A6 统计误差 | `stats(ddd_total).rel_error == sqrt(S2/S²−1/N)`，`S=ddd_MeV_g`、`S2=ddd_sum_sq_MeV2_g2` | 1e-9 |
| A7 事件数 | `n_events == 20000`；`entries ≈ N·p = 13889` | 精确 / 4σ |
| A8 状态 | `approximate` | 精确 |
| S1 实表量级 | `DDD ≈ N·100·NIEL(99.93)/A_beam`（NIEL≈2.976e-3） | 2%；REF-DDD-01 的 1% 不在此重复 |
| S2 hits 近似折积 | `DDD_fold` vs `ddd_MeV_g` | ≤1%（weaker；先查 KE 定义） |

**G vs R vs I**：A1 来自 G；A2 来自 R；A3 来自 I 的常量表；A4 是 scorer 的边界列；
S1/S2 是物理量级。**A1/A3 联合**抓“体积重复除”和“漏 100”，A2 抓“长度重复计”，
§5 抓“权重乘两次”。

### 4. 期望解析值/关系（推导）

- `V=10×10×0.1=10 mm³`；12×12 束，`p=100/144`。
- `L_w ≈ N·p·t = 20000×0.694444×0.1 = 1388.889 mm`（权重=1）。
- 常量表 `NIEL0=0.003`：`DDD = 100×1388.889×0.003/10 = 41.6667 MeV/g`；每初级
  `2.08333e-3 MeV/g`。
- 用注量表达：`DDD/N = 100·NIEL0·Φ_mm^-2 = 100×0.003×0.006944 = 2.08333e-3`；
  与 `DDD/Φ = NIEL0`（Φ 用 cm^-2）一致。**100 的来源**：`L(mm)·NIEL(MeV cm²/g)`
  得到 `MeV·mm·cm²/g`，乘 100（1 cm²=100 mm²）再除 `V(mm³)` 才是 `MeV/g`；漏 100
  会得到 0.4167 而不是 41.67。
- 实表：`si_proton.csv` 在 100 MeV 为 `0.0029757`，在 99.93 MeV 的 log-log 插值约
  `0.002976`；`DDD ≈ 100×1388.889×0.002976/10 = 41.33 MeV/g`。这与 REF-DDD-01 的
  `DDD/Φ=NIEL(E_mid)` 是同一关系；本病例只用它做 2% 量级 sanity。
- 100 MeV 质子在 0.1 mm Si 中能量损失 `~0.136 MeV`（0.136%），所以 `E_mean≈99.93`
  与 100 的 NIEL 差 <0.1%；实表折积的误差主要来自 hits 近似，不来自能量损失。

### 5. 权重因子测试（w=1 vs w=2）

DDD 的 `track_length_mm` 本身就是加权长度，没有 raw 列；w=1 的 run 是 baseline：

| 量 | w=1 | w=2 | 期望 | 若 w² | 若 w⁰ |
| --- | --- | --- | --- | --- | --- |
| `track_length_mm` | L | 2L | 比值 2（≤1e-9） | 比值 4 | 比值 1 |
| `ddd_MeV_g` | D | 2D | 比值 2 | 比值 4 | 比值 1 |
| `out_of_range_track_length_mm` | 0 | 0 | 0 | 0 | 0 |
| `volume_mm3` | 10 | 10 | 相同 | 相同 | 相同 |
| `stats(ddd_total).rel_error` | r | r | 相同（≤1e-9） | 相同 | 相同 |
| `n_events` / `entries` | 20000 / ~13889 | 同 | 相同 | 相同 | 相同 |

- 比值 4 → 权重在 `lengthMm = weight*stepLength` 之后又乘了一次；
- 比值 1 → 权重没进（`lengthMm` 用了裸 stepLength）；
- 体积错乘不会改变这个比值（两个 run 都错），必须靠 A1/A3；
- `out_of_range` 在 w=2 时也是 0（常量表域 [1e-12,1e6]，E 不变）；若变成非零，说明
  权重/能量被误用，先查表/能量。

### 6. 样本量 / 种子 / 阈值

- N=20000，seed=20261124；权重对 seed=20261133（相同）。
- 常量表子例的 A1–A6 是确定性的（给定 hits），1e-12/1e-9；N=20000 是为了同时做
  §4 的物理量级和 `entries` 统计。
- 实表 S1：`σ` 取 rel_error×DDD；`tol=2%`（REF-DDD-01 的 1% 不在此重复）。若
  rel_error>0.5%，增加 N；不得放宽 2%。
- S2：`|DDD_fold − DDD| ≤ 1%·DDD`；这是 weaker，先确认 hits 的 `kineticEnergy_MeV`
  是 pre-step（本组假设）、`edep` 是该 step 的沉积；若差异 >1%，记录为“近似折积
  不确定”，不直接判 scorer 错。
- 停止条件：`n_events != 20000`、`out_of_range != 0`、`volume_mm3 != 10`、
  `track_length_mm` 与 hits 差 >1e-9、缺文件、`uncertainty_status != approximate`
  → 失败并保留原件。

### 7. 陷阱 / 限制

1. **没有 raw/weighted 拆分**：`track_length_mm` 就是加权长度；w=2 时它翻倍。不要拿
   “raw 列”做对照——DDD 没有 raw 列。权重对必须用两个 run。
2. **常量表不是物理**：`0.003` 是为了算术可判定而选的输入，不代表任何真实 NIEL。
   实表检查（S1/S2）是量级，表级审计是 REF-DDD-02；不要把常量表结果写进物理结论。
3. **`E_mean` 近似**：hits 的 `kineticEnergy_MeV` 是 pre-step KE；`edep` 是该 step 的
   沉积。`E_mean≈KE−0.5·edep` 忽略了结合能/δ 电子逃逸/核反冲，误差通常 <0.1%，但
   不是精确的 `0.5(pre+post)`。S2 的 1% 容差就是给这个近似的；若超差，先查 hits 的
   KE 定义，不要直接判 scorer 错。
4. **零沉积 step**：hits 不写 `edep=0` 的 step；100 MeV 质子打 0.1 mm 硅每个 step 都有
   沉积，A2 完整。若换成中性粒子/真空，`track_length_mm` 会大于 hits 和，A2 失败是
   **预期**的；此时只能用 summary。
5. **`out_of_range`**：表域 [1e-12,1e6] 覆盖 99.93 及低能次级质子；若把表改成窄域
   （如 [10,1000]）并把能量降到 10 MeV，质子会停在靶内、`E_mean` 降到 <10 MeV，
   `out_of_range>0`，A4 失败——不是 scorer 错，是表域选错。本组用宽域常量表，
   避免这个歧义。
6. **`niel_table` 列**：只写路径，不写表 SHA-256（`NielTable` 算了 sha 但没输出，见
   raw facts #3）；如果 Q2-3 要证明“用的是哪一版表”，必须另存输入文件哈希。
7. **只有 proton 有表**：`ddd_total` 是总量，`ddd_proton` 是分粒子；若以后加第二张表，
   `ddd_total` 会包含两个粒子，A5 不能假设 `total == proton`。本组只有一张表。
8. **质量代替体积**：DDD 的分母是体积，不是质量；若实现误用质量，A1 的
   `volume_mm3==10` 和 A3 的 `100·L·NIEL/V` 会同时失败（质量 kg 2.33e-5 vs 体积 10 mm³）。不要用
   Dose 的质量检查来替代 DDD 的体积检查。

### 8. 配置有效性说明

| 键/特性 | 状态 | 说明 |
| --- | --- | --- |
| `displacement=true` + `auto_create_default_scorers=true` | 已确认 | `ScoringManager.cc:697-699` |
| `[scoring.displacement] proton=niel_const.csv` | 已确认 | schema/`ScoringManager`；路径 main_ini-relative |
| `niel_const.csv` 表头/两行/单调 | 已确认 | `NielTable.cc` 要求 `energy_MeV,niel_MeV_cm2_g`、≥2 行、严格递增 |
| 常量表 log-log 插值 | 已确认 | 两值相同 → 任意 E 返回 0.003 |
| `track_length_mm` 是加权长度 | 已确认 | `DisplacementScorer.cc:71` |
| 无 raw/weighted 拆分 | **已知缺口** | `displacement_volume_csv_v1` 11 列，只有加权长度 |
| `hits.kineticEnergy_MeV` 是 pre-step | **待验证**（首次 10 事件） | 若实际是 post-step/其他，S2 的 `E_mean` 公式要改 |
| `hits.volume` 值 | **待验证** | 同 §0.9 |
| 实表子例的 `si_proton.csv` | 已确认（文件存在） | 但 `QGSP_BIC_HP` 不在当前 physics 允许列表（见 §10 G7），本组用 `FTFP_BERT_EMZ` 质子，不受影响 |

---

## 9. 汇总矩阵：能发现 / 不能发现

### 9.1 因子重复的检测矩阵

| 错误 | IMP-DOSE-01 | IMP-FLU-01 | IMP-LET-01 | IMP-DDD-01 |
| --- | --- | --- | --- | --- |
| 质量 ×2（存储值也 ×2） | **抓**：A1 `mass_kg` vs `2.33e-6·V` | n/a | n/a（公式无质量） | n/a |
| 质量 ×2（只进公式，列不变） | **抓**：A2 `D=ΣE·k/m²` | n/a | n/a | n/a |
| 体积当质量 | **抓**：A1（200 vs 4.66e-4） | **抓**：A1（2.33e-5 vs 10） | n/a | **抓**：A1/A3（2.33e-5 vs 10） |
| 体积 ×2（存储值） | n/a | **抓**：A1 `volume_mm3` vs G | n/a | **抓**：A1 |
| 体积 ×2（只进公式） | n/a | **抓**：A2 `Φ=L/V²` | n/a | **抓**：A3 `DDD∝1/V²` |
| 权重 ×2（w²） | **抓**：§5 weighted/raw=4 | **抓**：§5 =4 | **抓**：§5 线性 sum=4、平方和=16 | **抓**：§5 track/DDD=4 |
| 权重 ×0 | **抓**：§5 =1 | **抓**：§5 =1 | **抓**：§5 线性 sum=1 | **抓**：§5 =1 |
| 漏 100（DDD） | — | — | — | **抓**：A3 41.67 vs 0.4167 |
| 长度重复计 | — | **抓**：A4 `L_hits` vs summary | **抓**：A3 `sum_wl` vs hits | **抓**：A2 |
| 分子/分母错配（LET） | — | — | **抓**：A1/A2 | — |
| 统计矩错位 | **抓**：A7 | **抓**：A7 | **抓**：A5 | **抓**：A6 |
| `S` 模型错（LET） | — | — | **不能**（交 REF-LET-01） | — |
| NIEL 表错（DDD） | — | — | — | **不能**（交 REF-DDD-02） |
| edep 物理错（cut/列表） | **不能**（同一 SD edep） | — | — | — |
| 非 box 体积近似 | — | **不能**（用 box） | — | **不能**（用 box） |

### 9.2 每个病例一句话

- **IMP-DOSE-01**：`m_geom=ρV` 是独立裁判，`D=ΣE·k/m` 只证明内部自洽；权重对证明
  `w` 只乘一次。它抓质量因子，不抓体积/物理。
- **IMP-FLU-01**：`V_geom=10×10×t` 与 `L_hits=ΣstepLength` 是两条独立链；权重对证明
  `w` 只乘一次。它抓体积/长度因子，不抓中性粒子/表面穿越定义。
- **IMP-LET-01**：没有 mass/volume，别宣称能抓它们；它抓分子/分母错配、步集合、
  权重标度、delta 矩一致性。绝对 S 是 REF-LET-01 的事。
- **IMP-DDD-01**：常量 NIEL 表把 `100·L/V` 变成纯算术；权重对证明 `w` 只乘一次。
  它抓体积/100/长度，不抓 NIEL 表数据本身。

---

## 10. 功能缺口（阻塞“最强检查”的地方）

| # | 缺口 | 影响 | 本组的替代检查 | 需要什么才能最强 |
| --- | --- | --- | --- | --- |
| G1 | `hits_*` v3 无 `LETstep`（也无 NIEL 列） | LET 无法逐 step 独立重算 `S`；DDD 的实表折积只能用 `E_mean≈KE−0.5edep` 近似 | LET：A1/A2/A5 + A3/A4 + §5 权重标度；DDD：常量表 A3 + 实表 S2（1%） | hits 增加 `LETstep_MeV_per_mm`/`NIEL_MeV_cm2_g` 或 scorer 导出逐 step 值（数据需求，不改产品由本任务完成） |
| G2 | hits 默认不写零沉积 step（`SensitiveDetector.cc:92` 的零沉积分支 `return false`） | 中性粒子/真空层的 Fluence/DDD 长度、LET 的零沉积带电 step 在 hits 里缺失；R 链不完整 | 本组用质子打硅，所有 step 有沉积；A3/A4 在该几何成立 | 增加“零沉积 hits”配置键（当前只有 C++ setter `EnableZeroEdepHits`，未找到调用者）或 hits 增加零沉积行 |
| G3 | DDD 无 raw/weighted 拆分，`track_length_mm` 只有加权值；无逐 step `E_mean` | 权重测试必须跑两个 run；实表折积只能近似 | §5 的 w=1/w=2 对；S2 的 1% 近似 | 增加 `raw_track_length_mm` 与逐 step NIEL/E_mean 列 |
| G4 | NIEL 表的 SHA-256 算了但没输出（`NielTable.cc` 计算，CSV 只有路径） | 无法从输出证明用的是哪一版表；复现需另存输入哈希 | 本组在 registry 里另存 `niel_const.csv`/`si_proton.csv` 的 sha256 | CSV 增加 `niel_table_sha256` 列 |
| G5 | 没有源级 `weight` 键；`[source.<name>]/intensity` 是选择概率不是权重 | factor-2 只能靠 phase-space 重放；GUI 不暴露；需要手写/录制 CSV | §0.8 的手工相空间对（手册已验证权重保持） | 增加源级 `weight` 键，或 GUI 暴露 phase-space 重放 |
| G6 | `scorer_statistics` 的 ratio 行不写 `sum/sum_sq/cross` | 只读 `scorer_statistics` 时无法独立重算 LET 的 delta 误差 | 用 `let_volume_summary` 的三组和/交叉和重算（§0.7）；这是公共 CSV，但不是 `scorer_statistics` | 在 ratio 行补 `sum/sum_sq/den_sum/den_sum_sq/cross_sum`，或明确契约允许 summary 作为矩来源 |
| G7 | `device_dose/README.md` 写中子用 `QGSP_BIC_HP`，但 `PhysicsFactory.cc:326-328` 的允许列表没有它 | 中子 DDD 病例不能照 README 直接跑；本组只用质子，不受影响 | 质子 `FTFP_BERT_EMZ`；若做中子，改用 `FTFP_BERT_HP`/`Shielding` 并**待验证**物理保真度 | 更新 README 或把 `QGSP_BIC_HP` 加入允许列表（需产品变更，非本任务） |
| G8 | `GetMass(true,false,preStepMaterial)` 在 daughter/replica 下语义未验证（契约 :80） | 本组只能用无 daughter 单 box；layered_device 的质量审计另立 | A1 的 `ρV` 对单 box 精确 | 专门的质量审计病例（多 daughter/复制） |
| G9 | 文档把 Dose/Fluence summary 写成 `*_v1` 8 列，代码是 v2 11 列 | 消费者若按文档 8 列解析会错位；本组按代码表头 | §0.5 的 11 列表头 | 修文档（非本任务） |
| G10 | `event_edep` 零事件是否写行未验证 | 漏束源下 A4 的行数/求和口径不确定 | 本组 Dose 全命中，不触发 | 10 事件零沉积样本验证；或契约明确 |

**阻塞“最强检查”的只有 G1/G2/G3**：它们让 LET 的逐 step S、DDD 的逐 step
NIEL/E_mean、以及零沉积步的 R 链无法从公共输出独立重建。G4–G10 是复现性/文档/
配置口径问题，不改变本组四个病例的可执行性，但必须在 Q2-3 的 registry 里记录。
