# Q2-5 XS 偏置预注册草案 v1（Q2-5-XS-BIAS）— r1 最小修订

状态：**draft / 未授权执行**。本草案只定义可执行、可独立复验的有限合同与确定性输入，不运行 Geant4、不试种、不读取该病例的任何结果。

r1 修订针对独立审查 `docs/collab/reviews/20261105-q2-biasing-preregister-review-v1.md` 的两项问题：(1) 两组输入原先依赖 `scoring.dose` 的默认值 false，而主终点需要 Dose 计分；(2) 方法说明把完整径迹权重描述为固定的离散倍率，并据整块厚度与辐射长度推断交互次数。r1 已显式启用 Dose、删除未经证明的权重/交互预测，并补充配置事实核验；种子、批次规模、主终点、统计主判据与阈值均未改动。

## 1. 目的与范围

比较**同一几何/源/物理/评分**下：

- **analog 组**：完全不注册偏置算子（不是 `factor=1`；`factor=1` 仍会包裹过程并保留权重算术）。
- **biased 组**：仅对初级电子在 `Target` 内的 `eBrem` 增加截面（`factor=10`）。

唯一主终点是**每个完成事件在单一敏感体积内的加权沉积剂量**（Gy/event）。本草案验证的是“注册的偏置操作在真实输运中产生的权重变化”与两组加权剂量的有限样本差异；它不预测完整径迹权重的具体数值，不是全局无偏性证明，也不覆盖强子过程、次级偏置或其它因子。

适用范围：单机、2 线程、串行启动、同一冻结后端；单能 10 MeV 电子、10 mm G4_Pb 立方体。

## 2. 身份与来源

| 项 | 值 |
| --- | --- |
| 后端 | `out/collab/q2-backend-864bc036/G4UniversalSim.exe`，build `864bc036d6d7752475e52db4efd2b950cabfcc3d`，SHA-256 `f8a8119d…6820f` |
| 引擎 | Geant4 11.3.2（`--check-geant4-data` 需 `required_complete=true`） |
| 基物理 | `FTFP_BERT`，`default_cut = 0.1 mm` |
| 任务来源 | `docs/collab/inbox/20261105-q2-biasing-preregister-v1.md`（SHA-256 `972bf852…20e7`） |
| 设计复核 r1 | `docs/collab/reviews/20261105-q2-biasing-preregister-review-v1.md`（SHA-256 `339b56e8…3aa1`） |
| v1 原稿归档 | 外部 `q2-biasing-preregister-independent/first-draft.zip`，SHA-256 `733286ac…3189`（历史不覆盖） |
| Q2 固定清单 | `docs/collab/decisions/20261105-q2-closeout.md`（SHA-256 `95e4b31b…768d`） |
| 已验证回归入口 | `scripts/test_biasing_step_weight.py`（`d090ea85…9154`）、`scripts/test_biasing_worker_runtime.py`（`8dcd78ac…79c8`） |

## 3. 共同输入（两组逐字节相同）

| 项 | 值 |
| --- | --- |
| 几何 | `inputs/geometry.ini`：world 100 mm box G4_Galactic；`[volume.Target]` 10 mm 立方 G4_Pb，`sensitive=true`，`bias=true`，位于原点 |
| 源 | 单个初级粒子：`e-`，10 MeV，点源 `(0,0,0) mm`，方向 `(0,0,1)`；无额外 gamma 源 |
| 评分 | **显式** `enabled=true`、`hits=true`、`event_edep=true`、`dose=true`、`edep=false`、`let=false`、`fluence=false`、`auto_create_default_scorers=true`；无 mesh、无 LET、无 fluence |
| 运行名 | `q25_biasing_case`（两组相同） |
| 线程 | 2 |
| 输出 | CSV；`--output` 与 `--seed` 由命令行提供，因此两组 INI 除偏置门控外逐字节相同 |

Dose 必须显式启用：`scoring.dose` 的产品默认是 false，v1 输入曾因此不满足主终点；r1 起两组输入都写入 `dose = true`，并由 `verify_config.py` 从渲染输入与配置阶段 facts 双侧核对。

## 4. 两组的唯一差异

- `inputs/main_analog.ini`：`[physics] biasing = false`，**没有** `[biasing]` 段；不注册任何算子。
- `inputs/main_biased.ini`：`[physics] biasing = true`，并追加：

```ini
[biasing]
enabled = true
[biasing.xs.e-.eBrem]
factor = 10
volumes = Target
only_primary = true
apply_to_secondaries = false
min_weight = 0.05
max_interactions = 2
```

`make_inputs.py` 在生成时断言两组文本除上述门控与追加段外完全一致；`--check` 复核磁盘字节。

## 5. 偏置规则与权重观测（r1 修订）

- `analogXS = 1/interactionLength`；`biasedXS = factor × analogXS`；`factor = 10`。
- 实现使用 `G4BOptnChangeCrossSection`：算子提出截面变更，**实际赋予径迹的完整权重是输运结果**，取决于内核实际提出/应用了哪些操作，以及哪些输运段没有发生交互。因此不能由 `factor` 或截面比推出完整径迹的权重集合，也不能要求权重落在某个固定离散值上。
- 既有 `scripts/test_biasing_worker_runtime.py` 已包含“无交互存活权重”信号；该证据来自真实运行，不是本草案可预测的量。
- 几何只能给出运动学事实：源在立方体中心，初始前向到最近边界的距离是 5 mm。G4_Pb 的辐射长度不是 `eBrem` 的平均自由程，5 mm 也不足以推断交互次数；交互次数、存活权重与最终权重必须由实际内核运行与 worker 回执观测。
- `max_interactions = 2` 与 `min_weight = 0.05` 是停止偏置的配置上限，不构成对权重取值的预测。
- 新 gamma/电子次级不参与偏置（`only_primary=true`），其权重仅继承。

r1 保留的检验只要求**证据形态**，不要求具体数值：正有限权重；analog 组单位权重；biased 组每批至少一个非单位有限正权重并由 worker 回执证明已应用偏置操作。任一批次缺少该签名即判失败。

## 6. 批次、种子与顺序（未改动）

- 每组 16 个独立批次，每批 2000 事件、2 线程；共 **32 次运行、64 000 计划事件**。
- 新种子块 **20260801–20260832**：analog `20260801–20260816`，biased `20260817–20260832`；与冻结/已用 Q2 种子清单（dose/fluence/DDD/uncertainty/LET/覆盖设计/旧草案）无交集，`seed-order.json` 记录清单与 `disjoint_from_used=true`。
- 固定顺序：第 k 对中 k 为偶数时 analog 先、奇数时 biased 先，共 8/8 平衡；完整 32 条顺序见 `seed-order.json`。顺序只用于平衡时间漂移，不构成配对设计。

## 7. 主终点与证据对账

每个完成事件 i：

```
D_i = weighted_edep_MeV(i) × 1.602176634e-13 / mass_kg        [Gy/event]
mean_b = (1/N) Σ D_i, N = 2000（零沉积事件保留并计 0）
S = Σ D_i,  S2 = Σ D_i²,  R = sqrt(S2/S² − 1/N),  σ_event = R·mean_b
```

必须通过对账（任一项失败即该批失败）：

1. **EP-COMPLETED**：`run_summary` 的 `status=completed`、`program_exit_code=0`、`actual_completed_event_count=2000`。
2. **EP-EVENT-ROWS**：worker `event_edep_tN.csv` 的 eventID 并集恰为 `0..1999`，每批 2000 行；缺行失败。
3. **EP-MASS**：`dose_volume_summary` 的 `mass_kg` 与 `ρ·V`（G4_Pb 11.35 g/cm³、1 cm³）在 12 位有效数字半单位区间内一致；以 CSV 值为准，独立值仅核对。
4. **EP-DOSE-RECON**：worker 加权剂量行求和 == `Σ D_i`（半单位区间 + 累加误差界）。
5. **EP-STATS-RECON**：`scorer_statistics.csv` 的 S、S2、R 与事件行独立重算一致；`entries` 等于非零剂量事件数。
6. **EP-SCORING-ENABLED**：有效配置与配置阶段 facts 必须显示 `scoring.dose=true`、`let=false`、`fluence=false`、`hits=true`、`event_edep=true`；依赖默认 `dose=false` 即输入失败。
7. **EP-WEIGHT-POSITIVE**：hits 中每个非零权重有限且 >0；hit 加权沉积求和与事件 weighted_edep 在舍入内一致。
8. **EP-WEIGHT-NONUNIT**：biased 组每批至少一个有限正权重 ≠1；analog 组所有 hit 权重 ==1；**不要求**任何固定离散值（r1 修订）。
9. **EP-WORKER-EVIDENCE**：biased 每次运行每个 (run,thread) 有真实 `[G4USimBiasing]` 回执：`operators=1`、`matched_rules=1`、`tls_verified`、`end_run_completed`、`proposals>0`、`applied_callbacks>0`、无 failure；analog 不得出现已挂接算子。`biasing_effect_observed=unknown` 或“配置被接受”不能作为权重证据。
10. **EP-NO-UNKNOWN**：任何以 unknown/配置接受替代实测权重的记录按失败处理。

hits 只作**已输出沉积步与权重**的见证，不当作事件全集或计分步全集；路径类量不从 hits 行数推断。

## 8. 唯一主比较（未改动）

一次双侧 Welch 99% 区间（两组各 16 个独立批次均值）：

```
Δ = mean_biased − mean_analog
SE = sqrt(var_biased/16 + var_analog/16)          （样本方差，n−1）
df = (v_b + v_a)² / (v_b²/15 + v_a²/15),  v = var/n
CI = Δ ± t(0.995, df) · SE
```

判定语义：

- **区间排除 0**：报告“在该分辨率下检测到差异”；**不**归因于后端缺陷，也不称偏置因子错误。
- **区间包含 0**：报告“在该分辨率下未发现超出预设误差的差异”；这不是等价性，也不是全局无偏性证据。
- **退化**（SE=0）：只报告冻结模型下的精确算术结果，不声明 99% 覆盖率。
- **异常**：任一缺失证据/非有限值/失败检查即停止比较；批次不得剔除，异常批次只作描述性列出，不做逐对显著性检验。
- 禁止逐对 3σ、重复显著性、看到数据后改方法/剔除批次/延长采样。

局限：16 批/组的 Welch 区间在非正态/异方差下只是近似；批均值独立但非配对；顺序平衡不能排除慢漂移。

## 9. 规模依据（设计先验，非实测，未改动）

每组 16 批 × 每批 2000 事件，批均值的相对标准误差为 `CV/√2000`，组均值相对 SE 再除以 `√16`；99% 区间半宽约为 `t(0.995,df)·√2·组相对 SE`。按设计先验：

| 每事件 CV 假设 | 单批相对 SE | 组相对 SE | 预期 99% 半宽（相对） |
| --- | --- | --- | --- |
| 0.10 | 2.236e-3 | 5.590e-4 | 0.217% |
| 0.20 | 4.472e-3 | 1.118e-3 | 0.435% |
| 0.30 | 6.708e-3 | 1.677e-3 | 0.652% |

即该设计在 CV ≤ 0.3 的先验下可在 99% 置信度分辨约 0.2%–0.7% 的相对差异；更小的差异只能声明“在该分辨率下兼容”。CV 先验不是测量结果，也不涉及权重取值假设；执行报告必须给出实际 R 与区间。

资源依据：32 次 × 2000 事件、同主机 2 线程串行；同类 2000 事件冻结 Q2 病例在本机为低个位数秒量级，整个 campaign 属分钟量级。草案不承诺任何墙钟数字。

## 10. 效率与时间（未改动）

- 真实计时字段：`scorer_statistics.csv` 的 `run_wall_time_s`；主机墙钟由执行驱动单独记录，**不得**替代或填补生产字段。
- 可复算 FOM：`FOM = 1/(R² · run_wall_time_s)`，由打印矩与时间重算。
- 报告组内时间/FOM 分布与组间比较；**没有收益甚至更差是有效科学结论**。
- 条件：同主机、2 线程、串行启动、等事件预算。

## 11. 失败与限制规则（未改动）

- 后端非零退出、`status != completed`、缺 summary/事件/统计文件、完成事件数 ≠ 2000、缺事件行、非有限值、缺/重复 worker 回执、缺非单位权重签名、非 `approximate` 状态 → 该批失败；禁止补批、重采样、换种子。
- 证据不完整的批次如实报告为失败，不用剩余批次静默替换；campaign 停止并保留原始证据。
- 统计异常（某批均值远离组内）只作描述，不转化为后端缺陷结论。

## 12. 执行期反例（只改副本，未改动）

CE-ANALOG-REGISTERED、CE-WEIGHT-MISSING、CE-WORKER-RECEIPT-MISSING、CE-DROP-EVENT-ROW、CE-ANALOG-WEIGHT、CE-STATS-S2、CE-DROP-BATCH；每项须由其目标检查真实 fail 检出，原件字节不变，baseline 的其它失败不得冒充检出。

## 13. 数学与配置核验（r1 增补）

- `verify_math.py`：**24/24 pass**（`verify_math_results.json`）。覆盖 Student-t 分位数独立反演与出版常数对照、正例、负例（正态分位替代 t、事件级伪重复、剔除最差批次、零方差、无穷批均值）、种子唯一/无交集、顺序成对平衡、设计分辨率先验表。
- `verify_math.py` **不含**任何关于完整径迹权重取值、交互次数或存活概率的假设；这些只能由执行期真实运行观测（见 §5）。
- `verify_config.py`：**27/27 pass**（`verify_config_results.json`）。核验：两组渲染输入逐字节确定性；显式评分字段（`dose=true`、`let=false`、`fluence=false`）存在且两组一致；两组只差偏置门控；`--inspect-run` 的配置阶段 facts 中这些评分字段均为 `consumed=true`，且 `execution_performed=false`、无 warnings、宏 preflight 通过、`/run/beamOn 2000`。inspect 仅证明配置阶段接受，不冒充运行。

## 14. 复演与文件哈希

```
cd out/collab/q2-biasing-proposal-v1
python -B make_inputs.py --check
python -B verify_math.py --write
python -B verify_config.py
python -B build_proposal.py
```

| 文件 | 字节 | SHA-256 |
| --- | --- | --- |
| `proposal.json` | 29 733 | `a7f590fd85a56749af1487207c6cbc238a9b6d4b04fb2d28ba5e6e31d4f54d9a` |
| `make_inputs.py` | 9 901 | `1b8b6c23c8119d9fa00e92b01c3f6cae45df6a43e5634a5c697dea6228fc296a` |
| `verify_math.py` | 14 018 | `7fffc6ae18655dd594ede47bd4d34c182b2877cfa1f92c35a1fdd8175eefc049` |
| `verify_math_results.json` | 4 130 | `6d36e5beca1492749d4d256150f9d4fb561007fe30f7693f2285dc3702bfd985` |
| `verify_config.py` | 7 465 | `d938df64b8603c3eff2ecdb46c840a4633abdaf89770d25c5b089742d6b9ad70` |
| `verify_config_results.json` | 5 098 | `f43e6830ec079b67285d1419fa8c7b0227c555dbd1e813384bd8e46eca411d80` |
| `build_proposal.py` | 22 785 | `3f2b84ba4f61f4a30919c08cc5b9c7061c27248a764b081a181df8969ee61cd5` |
| `inputs_manifest.json` | 1 022 | `1e7bf7d1cefd9bb1b2a8527072aef637c793ab747997ccc339b66a87805c97aa` |
| `seed-order.json` | 6 257 | `2615ae075708b4a4e24708c49a8862d58f0a3fbea99aacd681964732b2adb702` |
| `inputs/geometry.ini` | 344 | `11a04452702285ab5d972f32813b84e8daa55c37fa507739c539a27bebdfa9e8` |
| `inputs/main_analog.ini` | 627 | `a82265c8fe1fabc24a860361672b7e53c20e655937645251f6ca69325502737b` |
| `inputs/main_biased.ini` | 1 161 | `6cae4bcb87cb497fee1146b2e65bab982894d9b982ed66ddcc271d677c7bcce0` |
| `inputs/run.mac` | 169 | `3e03251ece7c954720dbb27209c093390b3ea48acdac9e4a9e79a1c95dce18da` |
| `inspect_analog.json` | 3 949 | `d163c8042ccde444ec56a5e6a2e67420e11c4effbfab79e70c4b388e5e70d3c8` |
| `inspect_biased.json` | 4 600 | `9702ee21b1ed45731331e6293d67752e2574487238b8eabe6884145b69c33a48` |

## 15. 边界与范围外建议

- 本草案不运行、不试种、不读取该病例结果；执行需独立复核后的单独授权。
- 只覆盖一个粒子、一个过程、一个材料、一个几何、一个因子；不对其它粒子/过程/材料/因子或次级偏置作任何声明。
- **不预测**完整径迹权重、交互次数或存活概率；这些必须由真实运行证据观测。
- 区间只是有限样本兼容性陈述，不是全局无偏性或等价性证明。
- 范围外建议：次级偏置与多因子扫描应另立预注册；完整截面/表数据审计属于独立证据层，不用本实验的权重算术通过代替。

## 16. 当前状态

v1 已被独立审查退回；r1 已完成最小修订：显式 Dose、删除未经证明的离散权重/辐射长度推论、补充配置 facts 核验。草案仍为 **draft / execution_authorized=false**；等待独立数学与输入复演后再决定是否冻结与授权执行。本轮未修改产品代码、测试、基准、冻结参考、种子、规模或统计主判据，未提交 Git。
