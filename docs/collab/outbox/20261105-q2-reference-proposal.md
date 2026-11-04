# Q2-1 量定义、独立参考与实验预注册（退回修订后交付）

- 任务：Q2-1（固定清单“量定义、独立参考与实验预注册”）
- 工作目录：`D:/Geant4/G4UniversalSim`（Git top `D:/Geant4/G4UniversalSim`）
- 分支：`roadmap/Q2-scientific-baselines`；**HEAD `fd93e799e5415b932d20196396bf084b44391787`**
- 日期：2026-11-05
- 状态：**作者修订已交，等待独立审阅冻结参考值**；Q2-1 不运行 Geant4、不改产品/测试/正式基准/CI、不提交 Git
- 上一版：v1（2026-11-05 早）已按主审 m14726 的限定四项修订；本文件即修订版回执

## 1. 交付内容

证据包：`out/collab/q2-reference-proposal/`

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `README.md` | 7,305 | `1288eac9878950a4db29da9bd3d167b7d098fdf6277ee6cc740007a22ff71ea4` |
| `registry.json` | 34,225 | `e99fa2e31ee02c81a826caee95a7ac1bb66e616f8c9837065398b200e23dee6f` |
| `quantities.md` | 10,598 | `0c1e67d23b5f5c2d48681e5d7e9b172285f559cf42b925b7b176effa41523343` |
| `cases/reference-cases.md` | 10,302 | `6a45ebe5fd2b003cfc74b1e434e30aef039c02e2bb32f30ea3b0e5c227afe01c` |
| `cases/implementation-cases.md` | 66,393 | `ff2fe95ef9be1f6ee1a6a7585ac93ee161ae34f614a7cb73c2a0e877cb91f92b` |
| `cases/uncertainty-cases.md` | 7,685 | `d963fdb23cbb977d949ce36399fcfc02d1f5fa261737f13e1b8b725ae0e12ff7` |
| `cases/biasing-cases.md` | 8,272 | `d54812df351793914a50ddf5bb85035d50025a2138823714f02be0f646ba7979` |
| `references/external-sources.md` | 44,626 | `68b666d1f11a1d77013c5a3ec306ea296d13a4bfbc442fcde08629ccd53809d6` |
| `references/existing-evidence.md` | 45,071 | `5b1f2f9a2d17d3e455a20d3f7124b8d7055cdd13f01ba639bc300f61fda84a27` |
| `references/values-q2-1.csv` | 6,780 | `3c342660e6381a96fe2ac63f3798ad40ff6e1b2ca6d1277858419dc3ddf99ca1` |
| `references/ddd-table-audit.md` | 5,134 | `f76b914b2604c595e75c63fb993b2aa1c040a36c4336577501e42c497e152389` |
| `raw/scorer-facts.md` | 65,822 | `deb2d7dc27d9cdeb56abf946363c0ffba920df72d0ccefaaf428e0c193cee2ae` |
| `raw/benchmarks-and-contracts.md` | 46,148 | `6a13421d1a5cfce2bee5e8abfbaed040421efc577049d20438a691c877fc78d2` |

生成/校验脚本（在 `out/`，不随包提交）：`out/make_q2_registry.py`、`out/patch_q2_registry.py`。

`registry.json` schema `g4usim_q2_1_prereg_v1`，内容：18 个 case、14 个冻结条目、
10 条限制、12 个包内文件哈希、工作区身份（HEAD 如上）、执行规则与 `next`。

## 2. 对主审 m14726 四项的答复

### 2.1 UNC-RATIO-01：交叉项可以重算，撤回“必须新增产品列”

`src/Scoring/LETScorer.cc:150-153` 已输出 delta 所需全部矩：`sum_wl_mm`、
`sum_wSl_MeV`、`sum_wS2l_MeV2_per_mm`、`sum_sq_wl_mm2`、`sum_sq_wSl_MeV2`、
`sum_sq_wS2l_MeV4_per_mm2`、`sum_wl_x_wSl_MeV_mm`、`sum_wSl_x_wS2l_MeV3_per_mm`、`n_events`。

- `let_t = A/B`（A=sum_wSl，B=sum_wl）：`R_t² = S2_A/A² + S2_B/B² − 2·Σab/(A·B)`，
  其中 `S2_A=sum_sq_wSl`、`S2_B=sum_sq_wl`、`Σab=sum_wl_x_wSl`。
- `let_d = A/B`（A=sum_wS2l，B=sum_wSl）：`R_d² = S2_A/A² + S2_B/B² − 2·Σab/(A·B)`，
  其中 `S2_A=sum_sq_wS2l`、`S2_B=sum_sq_wSl`、`Σab=sum_wSl_x_wS2l`。
- 判据：重算的 rel_error 与 `scorer_statistics*.csv` ratio 行相差 ≤ `max(1e-12, 1e-9·rel_error)`；
  零贡献事件仍进 N（entries 只计非零贡献）。
- 结论：**不需要为 Q2-4 新增产品 CSV 列**；该“数据需求”从 registry 删除。

### 2.2 REF-DDD-02：取消未经核实的 0.1% 物理门槛

`references/ddd-table-audit.md` 与 `values-q2-1.csv` 的 REF-DDD-02 行分开记录：

- **单位换算（算术已核验）**：`95 MeV·mb = 9.5e-26 MeV·cm²/atom`；Si 原子质量
  `4.6637e-23 g` → `2.037006e-3 MeV·cm²/g`。
- **离散表插值（算术已核验）**：`si_neutron.csv` 无 1.000 MeV 节点，邻点
  `0.98=2.4078e-3`、`1.05=1.6573e-3`；log-log = `2.158335e-3`，线性 = `2.193371e-3`；
  相对 ASTM 算术值 `2.037006e-3` 为 `+5.957%` / `+7.677%`（插值算法本身差约 1.6pp）。
- **评价/版本/归一化差异**：ASTM `95 MeV·mb` 是 1 MeV 硬度参数/归一化量，SR-NIEL 的
  ASTM 模式是连续损伤函数在其离散网格上的值；不同版本、Ed（硅 21 eV 以外）与网格约定都
  会改变数值；ASTM 全文付费，`95` 输入未核验。
- **结论**：该约 6% 差异是数据产品/定义差异，**不能定为程序或数据缺陷**；本任务不补点、
  不改表、不设物理容差。REF-DDD-02 只作算术审计，`freeze_status=arithmetic_only_not_physical`；
  `limited_unverified_input` 用于 ASTM 算术行。其它实现算例可独立冻结。

### 2.3 预注册缺口：机器可读材料与 E_mid 追溯

- `references/values-q2-1.csv`（新增）：逐行 `case/quantity/item/energy/reference/unit/source/
  version/access_date/input_file/input_sha256/method/tolerance/seed/events/freeze_status/notes`；
  覆盖 REF-DOSE-01 的 4 个 E_mid 行 + 4 个 nominal 追溯行、REF-FLU-01/02、REF-LET-01 的 2 行、
  REF-DDD-01 的 2 行、REF-DDD-02 的 3 行（算术/R 受限）。
- E_mid 形成方法：`E_mid = R^-1(R(E0) − ρt/2)`，在 `make_reference.py` 与 LET 预注册中
  **预先固定**，不作为“从本轮模拟观测再挑参考”的条件化观测；nominal S_el 行仅作追溯，
  明确标注 `informational_not_used`，不可用于 pass 判据。
- 无可核验参考值的项单列限制（L1–L10），不把整个 registry 串在这些限制上；可执行算例仍可
  独立冻结。

### 2.4 BIAS-01/02：16 对独立批次 + 先定判据

- BIAS-01：16 对批次（analog `20261201..20261216`、biased `20261217..20261232`，不重叠，
  第 i 对配对），各 200000 事件、`threads=1`；偶数对先 analog 后 biased、奇数对相反；记录
  `started_at/finished_at`（UTC）、`run_metadata` wall time、频率策略/负载限制。
- 无偏性判据预先固定：逐对 `|μ_b−μ_a| ≤ 3√(σ_b²+σ_a²) + 0.5%·|μ_a|`；汇总 16 对差值均值
  95% CI 含 0。
- BIAS-02：主判据 = 16 个配对 FOM 比值对数均值的 95% t 区间；bootstrap 10000 次（固定
  seed）只作描述性辅助，**不替代独立批次数**。区间下界 >1.0 才算有收益；无收益/更差是
  允许的实际结论，不得为 CI 下界>1 换种子或调参。
- 权重收据、失败保留与不完整批次处理已写入 registry 的 `checks`/`stop_conditions`。

## 3. 量定义与参考清单（摘要）

四量表在 `quantities.md`：Dose（Gy，本体质量 `GetMass(true,false,preStepMaterial)`，raw/weighted
两种能量）、Fluence（mm⁻²，track-length/体积，daughter-free solid）、LET（keV/µm，
`LET_t=ΣwSl/Σwl`、`LET_d=ΣwS²l/ΣwSl`，可选粒子过滤）、DDD（MeV/g，
`Σ w·l·NIEL(E_mean)/V`，按粒子名分表）；每量列消费者 file:line、现有验证与缺口。

独立参考（`references/external-sources.md`，含 URL/版本/访问日期/仓库副本 SHA-256）：

- NIST PSTAR/ESTAR（质子/电子阻止本领与 CSDA）；NIST XCOM（γ 衰减）；
- SR-NIEL-7 ver.11.1 硅 NIEL 表（质子/电子/中子；中子为 ASTM E722-19 damage function）；
- ASTM E722-19 1 MeV 硅硬度参数 95 MeV·mb（仅公开摘要可核验）；
- PDG/Klein–Nishina/Landau 解析式（探测器响应，属仓内解析参考，不是外部实测）。

现有证据分级见 `references/existing-evidence.md`：F2 产品 `864bc036`（C++ `e7de615d…`、
227 用例、12 份云报告 708/255163）；Q1 `8ecad66a`（105/83770）；F1 `f176d0ed`（143/48511）。
四量的“独立 vs 同源”分级：Dose 的独立外部参考是 device_dose TID（PSTAR Si，2%）；
DDD 独立只是注量×NIEL 折积（表未验证）；Fluence 无外部基准（仅解析/同源）；LET 仅解析
Bethe（PSTAR 1.5%）；统计只有自洽、无覆盖率；偏置无无偏性/方差收益验证。

## 4. 已知限制（registry `limitations`，10 条摘要）

L1 ASTM 全文不可得；L2 NIEL 表无独立第二来源；L3 hits v3 缺 LETstep/逐 step NIEL（LET 比值
误差不受阻）；L4 统计无覆盖率；L5 旧偏置无无偏性与 FOM 收益验证；L6 benchmark quick 不落报告；
L7 输出契约文档 v1/v2 漂移；L8 device_dose README 物理列表漂移；L9 复杂几何质量定义未验证；
L10 MT 偏置仅 4 线程基础。

## 5. 校验与边界

- `python -B out/make_q2_registry.py` → `cases=18`；
  `python -B out/patch_q2_registry.py` → `patched ... cases=18 head=fd93e799e541`；
  `json.load(registry.json)` 通过；`registry.json.files["README.md"].sha256` 与磁盘一致。
- 未运行 Geant4；未改 `src/`/`include/`/`scripts/`/CI/正式基准/矩阵/支持等级；只新增
  `out/collab/q2-reference-proposal/**` 与本回执。
- 工作区另有监督端维护的 `docs/ROADMAP.md`、`docs/collab/CURRENT-SUPERVISION.md` 修改，
  不属本任务，未触碰。
- 未提交 Git、未推送；本回执与证据包构成 Q2-1 作者交付，等待独立审阅冻结参考值。

## 6. 给独立审阅者的复现步骤

```bash
python -B out/make_q2_registry.py
python -B out/patch_q2_registry.py
python - <<'PY'
import json
d=json.load(open('out/collab/q2-reference-proposal/registry.json',encoding='utf-8'))
print(d['schema'], len(d['cases']), len(d['freeze']), len(d['limitations']))
print([c['id'] for c in d['cases']])
PY
```

审阅重点：①REF-DDD-02 是否确无物理门槛且换算/插值/评价差异分列；②UNC-RATIO-01 公式与
`LETScorer.cc` 列名一致、无新增产品前置；③BIAS-01/02 的批次数/种子表/判据/无收益处理是否
先于运行固定；④`values-q2-1.csv` 的 E_mid 方法与 nominal 行标注；⑤限制 L1–L10 是否足以
界定本轮“可冻结”的边界。冻结后由监督端决定 Q2-2/3/4/5 执行。
