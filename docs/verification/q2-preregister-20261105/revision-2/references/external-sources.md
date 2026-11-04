# Q2 外部独立参考来源核验（external-sources）

> **访问日期**：2026-11-05（Asia/Shanghai）。
> **任务边界**：只读核验；唯一写入文件为本文件；未运行 Geant4，未修改产品/测试/CI，未提交 Git。
> **检索方式**：NIST 官方页面与 CGI 表单、NIST SRD 页面、SR-NIEL 官方计算器、ASTM DOI 页面、PDG PDF、ICRU 官方页面、Crossref DOI 元数据。本会话的 `web_search` 后端不可用，因此所有结论均来自可直接复现的 URL/表单，而不是搜索结果摘要。
> **标记约定**：`已验证` = 本次直接读取官方页面/表单并取得数值或元数据；`部分验证` = 元数据或间接记录可用，但关键字段（付费全文、官方页缺失）未取得；`未验证/需复核` = 不能从可访问来源确认，必须按缺口处理。

## 0. 结论摘要

- 6 个主源中 **4 个完整核验**：NIST PSTAR/ESTAR（版本 2.0.1，2017-07）、NIST XCOM（SRD 8 / XCOM 3.1，数据内容 2010-11）、SR-NIEL（SR-NIEL-7 ver. 11.1）、PDG 2026。
- **2 个部分核验**：ASTM E722-19（题名、DOI、卷号、页数已验证；`95 MeV·mb` 与 Table A1.1 因全文付费未验证）；ICRU Report 37（官方页 404；题名/年份由 1985 年 NIM B 书评的 Crossref 题名间接支持）。
- **数值复现**：仓库 `gamma_attenuation/reference.csv` 的 6 个值全部等于 XCOM “with coherent” 列；`csda_range/reference.csv` 的 7 个值全部等于当前 PSTAR 液态水 / ESTAR 水；`device_dose/reference.csv` 的 4 个 TID 与 3 个 DDD 值全部可在 `mean_energy_MeV` 处由 PSTAR / SR-NIEL 复现。
- **关键警告 1**：`device_dose` 的 TID/DDD 参考值是在 `mean_energy_MeV`（穿过 slab 后的平均能量）处取值，不是名义入射能量。10 MeV 名义点若直接查 PSTAR 10 MeV，TID 会低约 3.8%，超出 2% 容差；DDD 会低约 2.7%，超出 1% 容差。CSV 有 `mean_energy_MeV` 列和注释，但 README 必须明确这一点。
- **关键警告 2**：`device_dose` 的 DDD 参考来自 `scenarios/semiconductor/niel/si_proton.csv` / `si_neutron.csv`，而评分代码也使用同一组表；仓库 README 自己写明 DDD “不检验 NIEL 数据本身”。因此 DDD 是**评分管线一致性测试**，不是独立 NIEL 验证。
- **关键警告 3**：`95 MeV·mb → 2.037e-3 MeV cm²/g` 的算术已核验（95e-27 × N_A / 28.0855 = 2.037006e-3），但 `95` 这个输入值在 ASTM 公开页面上找不到；不能把仓库 README 的断言当作 ASTM 原文已验证。
- **补充文献**：8 篇 NIEL 相关论文的题名/卷期/DOI 已由 Crossref 核验；其中 7 篇是模型/参数化或综述，只有 Summers et al. (1993) 是测量级损伤关联。没有找到独立的、测量级的质子/电子硅 NIEL 表。

---

## 1. NIST PSTAR / ESTAR（质子与电子阻止本领、CSDA 射程）

### 1.1 元数据

| 项目 | PSTAR | ESTAR |
| --- | --- | --- |
| 官方入口 | https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html | https://physics.nist.gov/PhysRefData/Star/Text/ESTAR.html |
| 数据库主页 | https://www.nist.gov/pml/stopping-power-range-tables-electrons-protons-and-helium-ions | 同左 |
| 版本历史 | https://www.nist.gov/pml/stopping-power-and-range-tables-electrons-protons-and-helium-ions-version-history | 同左 |
| 题名 | PSTAR：proton stopping power and range tables；数据库总题名 “Stopping-Power & Range Tables for Electrons, Protons, and Helium Ions” | ESTAR：electron stopping power, density effect, range and radiation yield tables；数据库总题名同左 |
| 数据库编号 | NIST Standard Reference Database 124 | 同左 |
| 版本 | **2.0.1（2017-07）** | **2.0.1（2017-07）** |
| 数据内容最后更新 | **July 2017** | **July 2017** |
| 版本说明 | 2.0.0（2017-04）加入 ICRU Report 90 关键剂量学数据；2.0.1（2017-07）修复“用户自定义 I 值 + 额外能量点”的 bug | 同左 |
| 作者/引用 | Berger, M.J., Coursey, J.S., Zucker, M.A., Chang, J. (2005), *ESTAR, PSTAR, and ASTAR: Computer Programs for Calculating Stopping-Power and Range Tables for Electrons, Protons, and Helium Ions*；NIST 版本历史页的 citation form 仍示例 `version 1.2.3`，当前版本应为 2.0.1（2017-07）；原始报告 NISTIR 4999 (1993) | 同左 |
| DOI | https://dx.doi.org/10.18434/T4NC7P | 同左 |
| 访问日期 | 2026-11-05 | 2026-11-05 |
| 提供内容 | 质子（及 α）在指定材料中的电子/核/总阻止本领、CSDA 射程、投影射程、detour factor | 电子在指定材料中的碰撞/辐射/总阻止本领、CSDA 射程、辐射产额、密度效应参数 |
| 列与单位 | `STOP(e)`、`STOP(n)`、`STOP(t)`：MeV cm²/g；`RANGE(c)`、`RANGE(p)`：g/cm²；`DETOUR`：无量纲 | `CLOSS`、`RLOSS`、`TLOSS`：MeV cm²/g；`CSDA RANGE`：g/cm²；`RADIATION YIELD`：无量纲；`DELTA`：无量纲 |
| 相关量 | Dose/TID（电子阻止本领）、LET（电子阻止本领近似）、CSDA range、shielding | Dose/TID、CSDA range、电子输运 |

> **版本说明的坑**：NIST 版本历史页的“如何引用”示例仍写 `(version 1.2.3)`，但同页明确列出当前版本 **2.0.1（July 2017）**。引用时应写 2.0.1，并保留版本历史 URL；不要把示例里的 1.2.3 当成当前版本。

### 1.2 列与定义

- `STOP(e)`：electronic（collision）stopping power，即入射粒子与材料原子电子碰撞的平均能损，单位 MeV cm²/g。
- `STOP(n)`：nuclear stopping power，即与屏蔽原子核碰撞（含核反冲）的平均能损，单位 MeV cm²/g。
- `STOP(t)`：total stopping power，`STOP(t) = STOP(e) + STOP(n)`，单位 MeV cm²/g。
- `RANGE(c)`：CSDA（continuous slowing-down approximation）range，单位 **g/cm²**（质量厚度），不是 MeV cm²/g。换算成物理厚度：`x[cm] = RANGE(c)[g/cm²] / ρ[g/cm³]`。PSTAR 的 Silicon 密度 2.330 g/cm³；Water, Liquid 密度 1.000 g/cm³。
- `RANGE(p)`：projected range，g/cm²；`DETOUR = RANGE(p)/RANGE(c)`。
- ESTAR 的 `CLOSS` 是碰撞（电子）阻止本领，`RLOSS` 是辐射阻止本领，`TLOSS = CLOSS + RLOSS`；`CSDA RANGE` 单位 g/cm²；`RADIATION YIELD` 是辐射产额；`DELTA` 是密度效应参数。
- **剂量换算**：对薄层、带电粒子平衡、仅电子能损近似，
  `D[Gy] = Φ[cm⁻²] × STOP(e)[MeV cm²/g] × 1.602176634e-10`。
  其中 `1 MeV/g = 1.602176634e-10 Gy`。仓库 `device_dose` 的 TID 参考正是这个换算。

### 1.3 PSTAR：硅（nominal 能量）

| T (MeV) | STOP(e) | STOP(n) | STOP(t) | RANGE(c) g/cm² | RANGE(p) g/cm² | DETOUR |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 34.58 | 1.798e-2 | 34.59 | 0.1665 | 0.1657 | 0.9950 |
| 50 | 9.852 | 4.049e-3 | 9.856 | 2.852 | 2.842 | 0.9964 |
| 100 | 5.836 | 2.108e-3 | 5.838 | 9.737 | 9.706 | 0.9968 |
| 200 | 3.627 | 1.094e-3 | 3.628 | 32.40 | 32.31 | 0.9972 |

### 1.4 PSTAR：硅（仓库 mean_energy_MeV 处）

| T_eval (MeV) | STOP(e) | STOP(t) | RANGE(c) g/cm² |
| --- | --- | --- | --- |
| 9.5043 | 35.95 | 35.97 | 0.1525 |
| 49.19 | 9.978 | 9.982 | 2.770 |
| 99.113 | 5.874 | 5.876 | 9.586 |
| 198.65 | 3.642 | 3.643 | 32.02 |

> NIST CGI 会把输入能量按 4 位有效数字取整（9.5043 → 9.504，198.65 → 198.6），所以上表是在 9.504/49.19/99.11/198.6 处读取的；不是对 9.5043 的插值。

### 1.5 PSTAR：液态水（nominal 能量）

| T (MeV) | STOP(e) | STOP(n) | STOP(t) | RANGE(c) g/cm² |
| --- | --- | --- | --- | --- |
| 10 | 45.64 | 2.603e-2 | 45.67 | 0.1230 |
| 50 | 12.44 | 5.691e-3 | 12.45 | 2.227 |
| 100 | 7.286 | 2.944e-3 | 7.289 | 7.718 |
| 150 | 5.443 | 2.001e-3 | 5.445 | 15.77 |
| 200 | 4.491 | 1.522e-3 | 4.492 | 25.96 |

### 1.6 PSTAR：液态水（仓库 mean_energy_MeV 处）

| T_eval (MeV) | STOP(e) | STOP(t) | RANGE(c) g/cm² |
| --- | --- | --- | --- |
| 9.5043 | 47.54 | 47.57 | 0.1124 |
| 49.19 | 12.61 | 12.61 | 2.162 |
| 99.113 | 7.335 | 7.338 | 7.596 |
| 198.65 | 4.510 | 4.512 | 25.66 |

> **易错点**：液态水在 10 MeV 的 STOP(e) 是 **45.64**（nominal），不是 47.54；47.54 是 9.5043 MeV 处的值。两者相差 4.2%。引用 nominal 10 MeV 时不要取 E_mid 值。

### 1.7 ESTAR：硅

ESTAR 页头给出 Silicon：Z/A = 0.498478，Density = 2.3300 g/cm³，I = 173.0 eV。

| T (MeV) | CLOSS | RLOSS | TLOSS | CSDA g/cm² | Radiation yield | DELTA |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.507 | 2.360e-2 | 1.531 | 0.5386 | 8.275e-3 | 0.3424 |
| 10 | 1.697 | 0.3161 | 2.013 | 5.642 | 7.919e-2 | 2.239 |
| 20 | 1.769 | 0.7023 | 2.472 | 10.11 | 0.1514 | 3.323 |

> ESTAR 的文本 CGI 在给定“额外能量点”时只返回阻止本领和密度效应参数，不返回 CSDA range；上表的 CSDA range 来自默认能量网格（`ShowDefault=on`）的输出。

### 1.8 ESTAR：水（用于 CSDA 交叉核对）

| T (MeV) | CLOSS | RLOSS | TLOSS | CSDA g/cm² | Radiation yield | DELTA |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.849 | 1.280e-2 | 1.862 | 0.4367 | 3.579e-3 | 0.2428 |
| 10 | 1.968 | 0.1814 | 2.149 | 4.975 | 4.072e-2 | 2.992 |

### 1.9 仓库交叉核对：PSTAR / ESTAR

| 仓库量 | 仓库值 | 外部复现 | 结论 |
| --- | --- | --- | --- |
| `device_dose` TID，10 MeV | 5.75942e-9 Gy cm² | 5.75942e-9 / 1.602176634e-10 = 35.94747；PSTAR Si @ 9.5043 = 35.95 | 一致（E_mid） |
| `device_dose` TID，50 MeV | 1.59856e-9 | 9.97743；PSTAR @ 49.19 = 9.978 | 一致（E_mid） |
| `device_dose` TID，100 MeV | 9.41143e-10 | 5.87415；PSTAR @ 99.11 = 5.874 | 一致（E_mid） |
| `device_dose` TID，200 MeV | 5.83652e-10 | 3.64287；PSTAR @ 198.6 = 3.642 | 一致（E_mid） |
| `device_dose` TID，10 MeV 若按 nominal | — | 34.58 × 1.602176634e-10 = 5.540e-9 | 比仓库值低 3.8%，超 2% 容差 |
| `csda_range` 质子 10/50/100/150/200 | 0.1230/2.227/7.718/15.77/25.96 g/cm² | PSTAR 液态水 nominal：完全相同 | 一致 |
| `csda_range` 电子 1/10 | 0.4367/4.975 g/cm² | ESTAR 水：完全相同 | 一致 |
| `shielding_range` Al/Si | 仓库另有副本 | 本次仅抽查 Si 的 PSTAR 值与在线表一致；Al 未逐点复核 | 部分验证 |

> PSTAR CGI 的输出按 4 位有效数字显示：例如 49.19 MeV 的真实插值约 9.97743，页面显示 9.978；仓库的 1.59856e-9 对应 9.97743，而不是 9.978。因此上表的“一致”是指在 NIST 显示精度内一致（差异 < 0.01%），不是逐位字符串相等。

**结论**：

1. `device_dose` 的 source 标签 `PSTAR Si STOP(e)` 是**正确的**；4 个 TID 值在 `mean_energy_MeV` 处完全可复现。
2. 仓库 `scenarios/benchmarks/shielding_range/nist/PSTAR_Si.txt` 的 10/50/100/200 MeV 行、`ESTAR_Si.txt` 的 1/10/20 MeV 行与当前 NIST 在线表**数值逐项一致**（见 §8 哈希表）；不存在“仓库用了旧版 PSTAR 导致偏差”的问题。
3. `csda_range` 的 7 个值全部与当前 PSTAR 液态水 / ESTAR 水一致；比较时必须用 `energy_MeV`（nominal），不要拿 E_mid 值去对 CSDA。
4. **必须写进 README 的语义**：`energy_MeV` 是名义入射能量，`mean_energy_MeV` 才是参考值的取值点。10 MeV 点的 2%/1% 容差只有在 E_mid 处才成立。

---

## 2. NIST XCOM（光子截面 / 质量衰减系数）

### 2.1 元数据

| 项目 | 值 |
| --- | --- |
| 官方入口（表单） | https://physics.nist.gov/PhysRefData/Xcom/html/xcom1.html |
| 数据库主页 | https://www.nist.gov/pml/xcom-photon-cross-sections-database |
| 题名 | **XCOM: Photon Cross Sections Database** |
| 数据库编号 | **NIST Standard Reference Database 8 (XGAM)**；不是 SRD 126 |
| 版本 | **XCOM Version 3.1**（页面提供 “Download Your Own Copy of XCOM Version 3.1”）；数据内容最后更新 **November 2010** |
| 作者 | M.J. Berger, J.H. Hubbell, S.M. Seltzer, J. Chang, J.S. Coursey, R. Sukumar, D.S. Zucker, K. Olsen |
| 报告/DOI | NBSIR 87-3597；https://dx.doi.org/10.18434/T48G6X |
| 能量范围 | 1 keV – 100 GeV |
| 访问日期 | 2026-11-05 |
| 提供内容 | 元素/化合物/混合物的光子质量衰减系数、相干/非相干散射、光电吸收、核场/电子场对产生 |
| 列与单位 | `OutOpt=PIC` 时全部为 cm²/g；列为 Coherent、Incoherent、Photoelectric Absorption、Pair Production in Nuclear Field、Pair Production in Electron Field、Total Attenuation With Coherent Scattering、Total Attenuation Without Coherent Scattering |
| 相关量 | gamma attenuation / shielding；不直接给 dose/TID 或 DDD/NIEL |

### 2.2 数值（cm²/g）

| 材料 | 0.1 MeV（with/without coherent） | 1 MeV（with/without） | 10 MeV（with/without） |
| --- | --- | --- | --- |
| Water (H₂O) | 0.1707 / 0.1654 | 0.07072 / 0.07066 | 0.02219 / 0.02219 |
| Al (Z=13) | 0.1704 / 0.1572 | 0.06146 / 0.06132 | 0.02318 / 0.02318 |
| Pb (Z=82) | 5.549 / 5.336 | 0.07102 / 0.06803 | 0.04972 / 0.04969 |

### 2.3 仓库交叉核对

`scenarios/benchmarks/gamma_attenuation/reference.csv` 注释写的是 “Total mass attenuation coefficient with coherent scattering (cm²/g). Source: NIST XCOM”。仓库的 6 个值：

| 材料 | 能量 | 仓库值 | XCOM with coherent | 结论 |
| --- | --- | --- | --- | --- |
| G4_WATER | 0.1 MeV | 0.1707 | 0.1707 | 精确一致 |
| G4_WATER | 1 MeV | 0.07072 | 0.07072 | 精确一致 |
| G4_WATER | 10 MeV | 0.02219 | 0.02219 | 精确一致 |
| G4_Al | 1 MeV | 0.06146 | 0.06146 | 精确一致 |
| G4_Pb | 0.1 MeV | 5.549 | 5.549 | 精确一致 |
| G4_Pb | 1 MeV | 0.07102 | 0.07102 | 精确一致 |

**结论**：仓库的列声明、单位、数值全部正确，没有 mismatch。注意引用时写 **SRD 8 (XGAM)**，不要写成 SRD 126；XCOM 的“版本”是程序版本 3.1，数据内容日期是 2010-11。

---

## 3. SR-NIEL（NIEL 计算器与硅表）

### 3.1 元数据

| 项目 | 值 |
| --- | --- |
| 官方站点 | https://www.sr-niel.org/ |
| 站点标题 | “SR-NIEL – 7 / Screened Relativistic (SR) Treatment for NIEL Dose / Nuclear and Electronic Stopping Power Calculator” |
| 版本 | **SR-NIEL-7 ver. 11.1**（站点页眉与结果页页眉均显示 `version 11.1`；结果页页眉还显示 `12.May.2026`） |
| 页面更新时间 | NIEL 计算器 2023-10-19；电子计算器 2023-11-09；中子 ASTM 计算器 2023-10-24；cited publications 2024-06-21；bibliography 2024-06-22；codes download 2023-04-26 |
| 访问日期 | 2026-11-05 |
| 提供内容 | 质子/离子、电子、中子的 NIEL（MeV cm²/g）与 NIEL dose（MeV/g、Gy）；电子/核阻止本领；TID/TNID 换算器 |
| 单位 | NIEL：MeV cm²/g；NIEL dose：MeV/g 与 Gy；能量：MeV |
| 相关量 | DDD/NIEL、1 MeV 中子等效、质子/电子/中子位移损伤 |
| 可下载表 | **没有**静态 NIEL 表下载；`codes-available-for-download` 只提供 “SR-Treatment Patches for Geant4 v 10”。计算结果只以 HTML 结果页呈现，页面无 CSV/export 链接 |

### 3.2 计算器设置与仓库声称

| 粒子 | 仓库声称（`scenarios/semiconductor/niel/README.md`） | 站点是否记录 | 核验结果 |
| --- | --- | --- | --- |
| 质子 in Si | 位移阈能 21 eV；Hadron + Coulomb；强子部分不缩放；1e-4 – 1e4 MeV；Robinson 划分；Jun 2003/2004、Jun 2017、Huhtinen 2002 插值 | 是 | **已验证**：结果页输入 `1 H in Si`，Ed 21.00 eV，`IonModel Selected: Hadron+Coulomb`，`Hadronic Contribution: No Scaling`，1.0e-4 – 1.0e+04 MeV |
| 电子 in Si | 指数核形状因子；Ed 21 eV；0.1 MeV – 10 GeV | 部分 | 计算器页提供 Exponential/Gaussian/Uniform 形状因子与 Ed 输入，并给出 “NIEL for electrons in Silicon with Exponential form factor and Ed=21 eV” 示例；**0.1 MeV–10 GeV 的具体范围本次未提交电子查询，未验证/需复核** |
| 中子 in Si | ASTM E722-19 Table A1.1；1e-10 – 19.95 MeV | 是 | **已验证**：结果页输入 `Neutrons in Si / ASTM Standard E722-19`；640 组，19.95 至 1.025e-10 MeV；E722-19 页只注明 GaAs 的 Ed=10 eV，未给 Si 的 Ed 数值 |

> **关于 21 eV**：SR-NIEL 的质子计算器页明确把 Si 的 Ed 作为输入，并列出 Si 的默认/插值参数为 21 eV；仓库的 21 eV 与站点一致。中子 ASTM E722-19 计算器的 Si 表是**损伤函数表**，不是以 Ed=21 eV 为输入；不要把质子/电子的 21 eV 与中子表混为一谈。

### 3.3 数值（MeV cm²/g）

| 粒子 | 能量 (MeV) | NIEL | 备注 |
| --- | --- | --- | --- |
| 质子 in Si | 9.5 | 9.6687e-3 | 结果页 |
| 质子 in Si | 10 | 9.4037e-3 | 结果页 |
| 质子 in Si | 90 | 3.1841e-3 | 结果页 |
| 质子 in Si | 95 | 3.0762e-3 | 结果页 |
| 质子 in Si | 100 | 2.9757e-3 | 结果页 |
| 中子 in Si | 13.95 | 3.8288e-3 | E722-19 表 |
| 中子 in Si | 14.05 | 3.7858e-3 | E722-19 表 |
| 中子 in Si | 14（几何平均） | 3.8073e-3 | 与仓库 0.0038072 一致 |

**仓库 `device_dose` DDD 复现**：

- 10 MeV 点的 `mean_energy_MeV = 9.5043`；在 SR-NIEL 的 9.5（9.6687e-3）与 10（9.4037e-3）之间做 log-log 插值，得 **0.009666330**；仓库是 **0.00966631**。
- 100 MeV 点的 `mean_energy_MeV = 99.113`；在 95（3.0762e-3）与 100（2.9757e-3）之间插值，得 **0.002992918**；仓库是 **0.00299292**。
- 14 MeV 中子：13.95 与 14.05 的几何平均 **3.8073e-3**；仓库是 **0.0038072**。
- 如果直接查 nominal 10 MeV，SR-NIEL 给 9.4037e-3，比仓库值低 **2.7%**，超出 DDD 的 1% 容差。

### 3.4 引用与文献

SR-NIEL 的 `citedpublications` 页面（https://www.sr-niel.org/index.php/citedpublications，Last Updated 2024-06-21）列出：

| 文献 | 题名 | 出处/DOI | 核验状态 |
| --- | --- | --- | --- |
| I. Jun et al. (2003a) | NIEL for heavy ions: an analytical approach | IEEE TNS 50, 1924-1928；doi 10.1109/TNS.2003.820762 | Crossref：50, **1919-1923**，2003-12（页码与 SR-NIEL 页不一致，见下） |
| I. Jun et al. (2003b) | Proton nonionizing energy loss (NIEL) for device applications | IEEE TNS 50, 1924-1928；doi 10.1109/TNS.2003.820760 | Crossref 与题名/页码一致 |
| I. Jun et al. (2004) | Alpha particle nonionizing energy loss (NIEL) | IEEE TNS 51, 3207-3210；doi 10.1109/TNS.2004.839150 | Crossref 一致 |
| I. Jun (2017) | Private communication regarding hadronic NIEL contribution | 无 DOI；链接到 SR-NIEL long write-up | 不是可引用论文，只能作为站点说明 |
| M. Huhtinen (2002) | Simulation of non-ionising energy loss and defect formation in silicon | NIM A 491, 194-215；doi 10.1016/S0168-9002(02)01227-5 | Crossref 一致 |
| ASTM E722-19 | 见 §4 | doi 10.1520/E0722-19 | 部分验证 |
| ICRU Report 37 | Stopping Powers for Electrons and Positrons | doi 10.1093/jicru_os19.2.iii | 官方页 404（见 §6） |
| ICRU Report 49 | Stopping Powers and Ranges for Protons and Alpha Particles | doi 10.1093/jicru_os25.2.iii | 官方页可用；年份靠 Crossref（见 §6） |
| M. Robinson (1972) | 划分函数（partition function） | — | 站点引用；本次未独立核验原论文 |
| Norgett-Robinson-Torrens (1975) | NRT 位移损伤模型 | doi 10.1016/0029-5493(75)90035-7 | 站点引用；本次未读原文 |

> **SR-NIEL 引用页的页码错误**：`citedpublications` 把 Jun 2003 的重离子论文写成 50, 1924-1928，但 Crossref 的 doi 10.1109/TNS.2003.820762 是 50, **1919-1923**；1924-1928 属于 Jun 2003 的质子 NIEL 论文（doi 10.1109/TNS.2003.820760）。引用时应分别写两篇，不要照抄该页的页码。

### 3.5 仓库交叉核对与独立性

- `scenarios/semiconductor/niel/si_proton.csv` 表头与 SR-NIEL 结果页输入一致：Protons in Si、Robinson partition、SR-NIEL-7 ver. 11.1、检索日期 2026-10-22、Ed 21.00 eV、1e-4–1e4 MeV、Hadron+Coulomb、No Scaling。
- `si_neutron.csv` 使用 ASTM E722-19 Table A1.1；14 MeV 的 0.0038072 与 SR-NIEL 结果页的几何平均一致。
- **独立性**：`device_dose` 的 DDD 参考和评分代码使用同一组 `si_proton.csv` / `si_neutron.csv`；`device_dose/README.md` 明确说 DDD “检验径迹长度注量与折积，不检验 NIEL 数据本身”。因此 DDD 是管线一致性测试，不是外部 NIEL 数据验证。SR-NIEL 本身是**模型计算器**，不是测量数据。

---

## 4. ASTM E722-19（中子 1 MeV 等效损伤函数）

### 4.1 元数据

| 项目 | 值 |
| --- | --- |
| 标准号 | **ASTM E722-19** |
| 题名 | **Standard Practice for Characterizing Neutron Fluence Spectra in Terms of an Equivalent Monoenergetic Neutron Fluence for Radiation-Hardness Testing of Electronics** |
| DOI | https://doi.org/10.1520/E0722-19 |
| 出版者 | ASTM International, West Conshohocken, PA |
| 版本/年份 | 2019 版（标准号 `-19`；公开页未单独印出版年月） |
| Book of Standards | Vol. 12.02 |
| 分委员会 | E10.07 |
| 页数 | 28 |
| ICS | 31.080.01 |
| 访问日期 | 2026-11-05 |
| 获取方式 | DOI 公开摘要页可用（`store.astm.org/e0722-19.html`）；直接 `astm.org/e0722-19.html` 返回 403 CloudFront。全文付费，需 ASTM Compass/机构订阅 |
| 提供内容 | 中子注量谱的 1 MeV 等效表征；SR-NIEL 页面称其 Table A1.1 为 Si 的损伤函数（damage function）、Table A2.1 为 GaAs |
| 单位 | 损伤函数 MeV·mb（ASTM 页面写作 MeV·mbarn）；NIEL_ref MeV cm²/g；注量 cm⁻² |
| 相关量 | DDD/NIEL、1 MeV 中子等效、中子辐照硬度 |

### 4.2 95 MeV·mb：未验证/需复核

| 项 | 值 | 状态 |
| --- | --- | --- |
| 仓库 README 声称的 Si 1 MeV 损伤函数 | 95 MeV·mb | **未验证/需复核**：ASTM 公开摘要页没有 “95 MeV”、没有 “Table A1”、没有 “damage function” 这个短语（只有 “displacement damage” 的泛述）；全文付费 |
| 换算后的 NIEL_ref | 2.037006e-3 MeV cm²/g | **算术已核验**：95e-27 × 6.02214076e23 / 28.0855 = 2.037006e-3；输入 95 本身未从 ASTM 原文核验 |
| SR-NIEL 在 1 MeV 附近的值 | 约 1.6573e-3 – 2.4078e-3 MeV cm²/g | 来自 E722-19 表的计算器输出；同一标准、非独立评价，且没有恰好 1.0000 MeV 的行 |

> **结论**：`95 MeV·mb` 和 `2.037e-3` 可以作为仓库内部换算和 SR-NIEL 输入的一致性说明，但**不能写成“ASTM E722-19 原文已核验”**。Q2 冻结时若需要该值，必须取得 ASTM 全文或机构访问；否则保留“未验证/需复核”。

---

## 5. PDG：Passage of Particles Through Matter

### 5.1 元数据

| 项目 | 值 |
| --- | --- |
| URL | https://pdg.lbl.gov/2026/reviews/rpp2026-rev-passage-particles-matter.pdf |
| 题名 | **34. Passage of Particles Through Matter** |
| 版本/年份 | **PDG 2026**（Review of Particle Physics）；该综述正文最后修订 **2023-08** |
| 出版信息 | F. Takahashi et al. (Particle Data Group), *Int. J. Mod. Phys. A* **41**, 2630011 (2026)，2026-06-01 |
| 作者 | D.E. Groom (LBNL), S.R. Klein (NSD LBNL; UC Berkeley) |
| 访问日期 | 2026-11-05 |
| 提供内容 | 重带电粒子电子能损、能损涨落（Landau–Vavilov）、多次散射、光子/电子相互作用、电磁簇射、μ 子能损、Cherenkov/TR |
| 单位 | dE/dx：MeV g⁻¹ cm²；MPV：MeV；角度：rad；辐射长度：g cm⁻² |
| 相关量 | LET/能损、探测器响应 MPV、能量歧离；不直接给 NIEL/DDD |
| 独立性 | 理论综述/编译，不是测量数据；适合作为公式来源，不适合作为“实测验证” |

### 5.2 章节名（逐字）

- 34.1 Notation
- 34.2 Electronic energy loss by heavy particles
  - 34.2.1 Moments and cross sections
  - 34.2.2 Maximum energy transfer to an electron in a single collision
  - 34.2.3 Stopping power at intermediate energies
  - 34.2.4 Mean excitation energy
  - 34.2.5 Density effect
  - 34.2.6 Energy loss at low energies
  - 34.2.7 Energetic knock-on electrons
  - 34.2.8 Restricted energy loss rates for relativistic ionizing particles
  - 34.2.9 Fluctuations in energy loss
  - 34.2.10 Energy loss in mixtures and compounds
  - 34.2.11 Ionization yields
- 34.3 Multiple scattering through small angles
- 34.4 Photon and electron interactions in matter
  - 34.4.1 Collision energy losses by e±
  - 34.4.2 Radiation length
  - 34.4.3 Bremsstrahlung energy loss by e±
  - 34.4.4 Critical energy
  - 34.4.5 Energy loss by photons
  - 34.4.6 Bremsstrahlung and pair production at very high energies
  - 34.4.7 Photonuclear and electronuclear interactions at still higher energies
- 34.5 Electromagnetic cascades
- 34.6 Muon energy loss at high energy
- 34.7 Cherenkov and transition radiation

### 5.3 Landau–Vavilov–Bichsel

- 仓库 `detector_response` 引用 “PDG Landau-Vavilov-Bichsel (Eq. 34.12)”；PDF 中 **Eq. (34.12)** 位于 §34.2.9 “Fluctuations in energy loss”，是 Landau–Vavilov 的最概然能损（MPV）公式。
- PDF 正文还出现 “Landau-Vavilov-Bichsel p/x in silicon” 的表述；本次核验到公式位置和正文引用，**未做符号级转录**，也未重新计算仓库的三个 MPV 数值。
- 仓库的 MPV 数值（Si 300 µm；μ⁻ 4 GeV 0.0825318 MeV；质子 300 MeV 0.15582；质子 1000 MeV 0.0897595）本次未独立复算；属于“公式来源已验证、数值待复算”。

---

## 6. ICRU Report 49 / Report 37

### 6.1 ICRU Report 49（质子与 α）

| 项目 | 值 |
| --- | --- |
| 题名 | **ICRU Report 49, Stopping Power and Ranges for Protons and Alpha Particles** |
| 出版者 | International Commission on Radiation Units and Measurements (ICRU), Bethesda, MD |
| 年份 | **1993**（Crossref：JICRU 25(2)，1993-05；官方页面未印年份） |
| DOI | https://doi.org/10.1093/jicru_os25.2.iii |
| 官方页 | https://www.icru.org/report/stopping-power-and-ranges-for-protons-and-alpha-particles-report-49/ |
| 访问日期 | 2026-11-05 |
| 提供内容 | 73 种材料；质子 1 keV–10000 MeV、α 到 1000 MeV；碰撞/核/总阻止本领、csda range、detour factor |
| 单位 | 阻止本领 MeV cm²/g；csda range g/cm²；detour factor 无量纲 |
| 相关量 | Dose/TID、LET（阻止本领近似）、CSDA range；质子/α 输运 |
| 状态 | 题名/摘要/覆盖范围**已验证**；年份**部分验证**（官方页无年份，Crossref 支持 1993） |

### 6.2 ICRU Report 37（电子与正电子）

| 项目 | 值 |
| --- | --- |
| 题名 | **Stopping Powers for Electrons and Positrons** |
| 出版者 | ICRU, Bethesda, MD |
| 年份 | **1984**（Crossref：JICRU 19(2)，1984-12；官方页不可达） |
| DOI | https://doi.org/10.1093/jicru_os19.2.iii |
| 官方页（尝试） | https://www.icru.org/report/stopping-powers-for-electrons-and-positrons-report-37/ → **404** |
| 访问日期 | 2026-11-05 |
| 提供内容 | 电子/正电子在材料中的碰撞/辐射/总阻止本领、csda range、辐射产额、密度效应参数 |
| 单位 | 阻止本领 MeV cm²/g；csda range g/cm²；辐射产额/密度效应无量纲 |
| 相关量 | 电子 Dose/TID、CSDA range；PSTAR/ESTAR 方法基础 |
| 状态 | **部分验证**：官方 ICRU 页面 404；ICRU WP 搜索未返回 Report 37；DOI 重定向到 SAGE 后被阻断。题名/出版者/年份由 1985 年 Elsevier 书评的 Crossref 题名支持：*Stopping powers for electrons and positrons (ICRU report 37; International commission on radiation units and measurements, Bethesda, Maryland, USA, 1984)*，NIM B 12(1), 187-188，doi 10.1016/0168-583X(85)90718-9；但这不是 ICRU 官方页，仍需按“未取得官方页”处理 |

> ICRU 37/49 是 PSTAR/ESTAR 方法所依据的标准；它们与 NIST 表不是同一份文件。引用时应把“标准”和“NIST 评价表”分开写。

---

## 7. 其他可引用的 NIEL 文献（SR-NIEL 之外）

以下 8 篇的题名/卷期/DOI 已由 Crossref 核验（访问日期 2026-11-05）；**未读全文**，因此只登记“文献存在与类型”，不把摘要外的数值当作已验证。

| 文献 | 类型 | 内容/用途 | DOI | 独立性/备注 |
| --- | --- | --- | --- | --- |
| Huhtinen (2002) | 模型/模拟 | Si 中非电离能损与缺陷形成；SR-NIEL 的 Si 高能强子部分（1–24 GeV）来源 | 10.1016/S0168-9002(02)01227-5 | 模型参数化；与 SR-NIEL 同源 |
| Jun et al. (2003a) | 模型/解析 | 重离子 NIEL 解析方法 | 10.1109/TNS.2003.820762 | 模型参数化；IEEE TNS 50, 1919-1923 |
| Jun et al. (2003b) | 模型/解析 | 质子 NIEL for device applications | 10.1109/TNS.2003.820760 | 模型参数化；IEEE TNS 50, 1924-1928 |
| Jun et al. (2004) | 模型/解析 | α 粒子 NIEL | 10.1109/TNS.2004.839150 | 模型参数化；IEEE TNS 51, 3207-3210 |
| Jun, Kim, Evans (2009) | 模型/解析 | 电子 NIEL for device applications | 10.1109/TNS.2009.2033692 | 模型参数化；IEEE TNS 56, 3229-3235 |
| Akkerman & Barak (2006) | 模型/计算 | 低能离子在 Si 中的划分因子 | 10.1109/TNS.2006.884382 | 模型计算；IEEE TNS 53, 3667-3674 |
| Leroy & Rancoita (2007) | 综述 | Si 器件辐射环境中的粒子相互作用与位移损伤 | 10.1088/0034-4885/70/4/R01 | 综述/模型级；Rep. Prog. Phys. 70, 493-625 |
| Summers et al. (1993) | **测量级损伤关联** | γ/电子/质子辐照的半导体损伤关联 | 10.1109/23.273529 | 实验损伤关联；IEEE TNS 40, 1372-1379。注意 10.1109/23.273536 是另一篇 |

**判断**：

- 这些文献中，Jun 系列、Huhtinen、Akkerman、Leroy–Rancoita 都是**模型/参数化**，而且 SR-NIEL 明确把它们作为计算器输入；用它们去“验证”SR-NIEL 或仓库的 NIEL 表，属于同一模型族内的自洽检查，不是独立测量。
- Summers et al. (1993) 是**测量级损伤关联**，但它给的是损伤常数/关联，不是一张可直接替换 SR-NIEL 的质子/电子 Si NIEL 表；若要使用，需要把实验条件、注量、损伤常数一起复核。
- 本次**没有找到**独立的、测量级的质子/电子 Si NIEL 表。若 Q2 需要“独立 DDD 验证”，可选的现实路径是：ASTM E722-19 损伤函数（中子，但全文付费且与 SR-NIEL 同源输入）、Summers 1993 的实验关联（需复核适用性），或明确把 DDD 标为 table-dependent consistency，不声称独立验证。

---

## 8. 仓库交叉核对汇总

### 8.1 基准文件与来源声明

| 仓库文件 | 声称来源 | 外部核验 | 结论 |
| --- | --- | --- | --- |
| `scenarios/benchmarks/device_dose/reference.csv` TID | PSTAR Si `STOP(e)` × 1.602176634e-10 at E_mid | PSTAR 2.0.1 在 9.504/49.19/99.11/198.6 处与 4 个值一致 | 来源/列正确；必须注明 E_mid |
| `scenarios/benchmarks/device_dose/reference.csv` DDD | SR-NIEL `si_proton.csv` / `si_neutron.csv` at E_mid | SR-NIEL 11.1 的 log-log/几何插值与 3 个值一致 | 数值一致；但与评分代码同表，**非独立 NIEL 验证** |
| `scenarios/benchmarks/gamma_attenuation/reference.csv` | NIST XCOM “with coherent” | 6/6 精确一致 | 正确 |
| `scenarios/benchmarks/csda_range/reference.csv` | PSTAR/ESTAR 液态水 | 7/7 精确一致 | 正确 |
| `scenarios/benchmarks/detector_response/reference.csv` | PDG Landau–Vavilov–Bichsel Eq. 34.12 | 公式位置/章节已验证；MPV 数值未复算 | 来源正确；数值待复算 |
| `scenarios/benchmarks/shielding_range/` | PSTAR/ESTAR Al/Si | 仅抽查 Si；Al 未逐点复核 | 部分验证 |

### 8.2 README 声称逐条核对

| README 声称 | 核验结果 |
| --- | --- |
| SR-NIEL-7 ver. 11.1 | **已验证**（站点页眉与结果页页眉） |
| 质子 Si 位移阈能 21 eV | **已验证**（结果页输入 Ed 21.00 eV） |
| Hadron + Coulomb | **已验证**（结果页 `IonModel Selected: Hadron+Coulomb`） |
| 强子部分不缩放 | **已验证**（`Hadronic Contribution: No Scaling`） |
| Jun 2003/2004、Jun 2017、Huhtinen 2002 插值 | **已验证**（计算器页/ citedpublications 页；Jun 2017 是 private communication，不是论文） |
| 中子 ASTM E722-19 Table A1.1 | **已验证**（计算器页与结果页输入）；ASTM 公开页不含该表 |
| 1 MeV 等效使用 95 MeV·mb | **未验证/需复核**（ASTM 全文付费；公开页无此值）；换算 2.037e-3 的算术正确 |
| DDD “不检验 NIEL 数据本身” | **仓库 README 自己已写明**；本次确认该声明与代码结构一致 |

### 8.3 仓库副本哈希（本次复核）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `scenarios/benchmarks/shielding_range/nist/PSTAR_Si.txt` | 10,507 | `71cfaaf13545201276c24195d96a4fafd2341bf5fbd26ed52133cce0b42f2422` |
| `scenarios/benchmarks/shielding_range/nist/PSTAR_Al.txt` | 10,507 | `54cde16d6f14fa4cb9a9b9d7d23f9ca648210e8e7f1c9e0ca575eda59ffcab11` |
| `scenarios/benchmarks/shielding_range/nist/ESTAR_Si.txt` | 6,183 | `0791fb386f15215c2ea8124b40e341da93cfc14cf446356c220a1612e75c96e6` |
| `scenarios/benchmarks/shielding_range/nist/ESTAR_Al.txt` | 6,184 | `5ea939520f9d6ac7b2d7b7e8f8faf8650724b161d28e39c1b8fbc7255624dcd5` |
| `scenarios/semiconductor/niel/si_proton.csv` | 2,617 | `6c21e35aab18495d4bb2597a76be60c7c35ef0df963224e0108c77c2e4c208d5` |
| `scenarios/semiconductor/niel/si_neutron.csv` | 12,088 | `a2ad28a9fcce3500fca363946e09e19125d084f1b596eff76662b272c242034f` |
| `scenarios/semiconductor/niel/si_electron.csv` | 1,917 | `e26af764ceaf9b388434f440c337a8a1b297f1f86862b045499a52b5cc7d8b87` |

> 以上哈希均为本次直接计算（`sha256sum`），不是从证据包转抄；`PSTAR_Si.txt` 的 10/50/100/200 MeV 行、`ESTAR_Si.txt` 的 1/10/20 MeV 行均与当前 NIST 在线表数值逐项一致。`si_electron.csv` 的数值本次未与 SR-NIEL 电子计算器逐点比对。

---

## 9. 可替代/独立程度评估

| 类别 | 来源 | 独立程度 | 适用/限制 |
| --- | --- | --- | --- |
| 外部评价表（独立于 Geant4 实现） | NIST PSTAR/ESTAR 2.0.1 | 高（不同实现/评价体系） | Dose/TID、LET 近似、CSDA range；不是原始测量，但可作为外部参考 |
| 外部评价表 | NIST XCOM (SRD 8) | 高 | Gamma 衰减/屏蔽；与 NIEL 无关 |
| 标准 | ICRU 49 / 37 | 高（标准文件） | PSTAR/ESTAR 的方法基础；37 官方页未验证 |
| 理论综述 | PDG 2026 | 中（理论/编译） | Landau–Vavilov MPV、能损公式；不是测量，不能证明涨落模型 |
| 标准/损伤函数 | ASTM E722-19 | 中（共识标准） | 中子 1 MeV 等效；全文付费，95 MeV·mb 未验证 |
| 模型参数化 | Jun 2003/2004/2009、Huhtinen 2002、Akkerman 2006、Leroy–Rancoita 2007 | 低–中（模型级） | 可作为公式/系数来源；与 SR-NIEL 同族，不能当独立测量 |
| **同模型 Web 计算器** | **SR-NIEL-7 ver. 11.1** | **低（模型级计算器）** | 仓库 NIEL 表的直接来源；用它验证仓库表是自洽检查 |
| 测量级损伤关联 | Summers et al. (1993) | 中（实验关联） | 可作测量级参考，但不是可直接替换的 NIEL 表；需复核适用条件 |

**结论**：

1. **Dose/TID**：PSTAR 是真正外部的评价表，且与仓库的 4 个 TID 值在 E_mid 处一致；这是目前最可靠的独立参考。
2. **Gamma attenuation**：XCOM 是真正外部评价，6/6 精确一致；可靠。
3. **CSDA/range**：PSTAR/ESTAR 是真正外部评价，7/7 精确一致；可靠。
4. **DDD/NIEL**：SR-NIEL 是**模型计算器**，不是测量；仓库 DDD 又使用同一组表，因此只能证明“评分管线能把 NIEL 表折积成 DDD”，不能证明 NIEL 表本身正确。若 Q2 要声称“独立 DDD 验证”，必须换用测量级数据或独立实现；否则应在报告中明确写“table-dependent consistency”。
5. **PDG**：适合作为 MPV 公式来源；不是测量数据，不能替代探测器响应实测。
6. **没有找到**独立的、测量级的质子/电子 Si NIEL 表。SR-NIEL 的“可替代”选项目前只有模型论文（同族）和 ASTM 中子损伤函数（同源输入、全文付费），不构成真正的独立替代。

---

## 10. 缺口

| # | 缺口 | 现状 | 下一步（精确到页面/DOI） | 需要机构访问？ |
| --- | --- | --- | --- | --- |
| 1 | ASTM E722-19 的 Si Table A1.1 与 95 MeV·mb | 公开摘要页无该表/该值；全文付费 | 通过 ASTM Compass 打开 doi 10.1520/E0722-19，查 Table A1.1 与 “1 MeV equivalent” 条款；记录 95 的原文数值与 Si 的 Ed 说明 | 是（ASTM 订阅） |
| 2 | ICRU Report 37 官方页 | `icru.org/report/stopping-powers-for-electrons-and-positrons-report-37/` 404；DOI 重定向 SAGE 被阻断。1985 年 NIM B 书评（doi 10.1016/0168-583X(85)90718-9）题名明确给 ICRU Report 37、Bethesda、1984，但非官方页 | 查 ICRU 出版物目录/图书馆；DOI 10.1093/jicru_os19.2.iii；争取 ICRU 官方页或印刷本核对题名、1984、出版者 | 可能（图书馆/ICRU） |
| 3 | ICRU Report 49 年份 | 官方页无年份；Crossref 记录为 1993-05 | 查 ICRU 目录或 DOI 10.1093/jicru_os25.2.iii 的正式记录；不把 Crossref 的 “Preface” 当完整报告 | 否（可选） |
| 4 | SR-NIEL 可下载表 | 站点只提供 Geant4 patch；结果页无 CSV/export | 保存结果页 HTML/PDF + 查询输入（URL、日期、参数）；若要长期可复现，向 SR-NIEL 申请数据/许可 | 否（但需归档） |
| 5 | SR-NIEL 引用页页码 | Jun 2003 重离子论文写成 1924-1928，Crossref 为 1919-1923 | 分别引用 doi 10.1109/TNS.2003.820762（1919-1923）和 doi 10.1109/TNS.2003.820760（1924-1928）；不要照抄 SR-NIEL 页 | 否 |
| 6 | 独立 NIEL 测量 | 未找到测量级质子/电子 Si NIEL 表 | 检索 IEEE Xplore/Elsevier 的 Summers 1993、Akkerman 2006 全文；确认是否给出可用的 NIEL/损伤常数；否则在 Q2 报告里把 DDD 降级为 table-dependent consistency | 是（IEEE/Elsevier） |
| 7 | XCOM 版本历史 | 只有 XCOM 3.1 下载页 + 数据内容 2010-11；无单独数据版号 | 查 NIST XCOM “Version History” 链接/下载包 README；引用时写 SRD 8 + DOI + last update | 否 |
| 8 | PDG MPV 数值 | Eq. 34.12 位置已验证；仓库 3 个 MPV 数值未复算 | 按 PDG Eq. 34.12 + 仓库材料/厚度参数复算 0.0825318/0.15582/0.0897595 MeV，记录差异 | 否 |
| 9 | `shielding_range` Al/Si | 只抽查 Si；Al 未逐点复核 | 抽取 PSTAR/ESTAR Al/Si 在基准能点的 STOP(e)/CSDA，与 reference.csv 比对 | 否 |
| 10 | `device_dose` 能量语义 | `energy_MeV` 是 nominal，参考值在 `mean_energy_MeV`；10 MeV 点 nominal 与 E_mid 差 3.8%/2.7% | 在 `scenarios/benchmarks/device_dose/README.md` 明确写“参考值取 E_mid”；CSV 注释已写，但 README 需同步 | 否（仓库文档） |

**对 Q2 冻结的建议**：

- 引用 PSTAR/ESTAR 时写 **2.0.1（July 2017）**，不要写“无固定版号”，也不要照抄 NIST 页面示例的 1.2.3。
- 引用 XCOM 时写 **NIST SRD 8 (XGAM), XCOM 3.1, data content 2010-11**，不要写 SRD 126。
- ASTM 95 MeV·mb 在取得全文前保持 **未验证/需复核**；不要把仓库 README 的断言升级为 ASTM 已验证。
- DDD 结论必须写明“SR-NIEL 模型计算器 + 同一表用于评分，非独立 NIEL 验证”；若需要独立结论，先补 §10 第 6 项。
- 10 MeV 的 TID/DDD 参考必须注明 E_mid；否则 nominal 值会超出现有容差。

---

## 11. 数值摘录

> 本节汇总本文件用到的关键数值；单位均为表头所示。未验证项在备注中明确标注。

### 11.1 PSTAR：硅

| T (MeV) | STOP(e) | STOP(n) | STOP(t) | RANGE(c) g/cm² | 备注 |
| --- | --- | --- | --- | --- | --- |
| 10 | 34.58 | 1.798e-2 | 34.59 | 0.1665 | nominal |
| 50 | 9.852 | 4.049e-3 | 9.856 | 2.852 | nominal |
| 100 | 5.836 | 2.108e-3 | 5.838 | 9.737 | nominal |
| 200 | 3.627 | 1.094e-3 | 3.628 | 32.40 | nominal |
| 9.5043 | 35.95 | 1.883e-2 | 35.97 | 0.1525 | 仓库 E_mid；CGI 按 9.504 读取 |
| 49.19 | 9.978 | 4.111e-3 | 9.982 | 2.770 | 仓库 E_mid |
| 99.113 | 5.874 | 2.125e-3 | 5.876 | 9.586 | 仓库 E_mid；CGI 按 99.11 读取 |
| 198.65 | 3.642 | 1.101e-3 | 3.643 | 32.02 | 仓库 E_mid；CGI 按 198.6 读取 |

### 11.2 PSTAR：液态水

| T (MeV) | STOP(e) | STOP(n) | STOP(t) | RANGE(c) g/cm² | 备注 |
| --- | --- | --- | --- | --- | --- |
| 10 | 45.64 | 2.603e-2 | 45.67 | 0.1230 | nominal |
| 50 | 12.44 | 5.691e-3 | 12.45 | 2.227 | nominal |
| 100 | 7.286 | 2.944e-3 | 7.289 | 7.718 | nominal |
| 150 | 5.443 | 2.001e-3 | 5.445 | 15.77 | nominal |
| 200 | 4.491 | 1.522e-3 | 4.492 | 25.96 | nominal |
| 9.5043 | 47.54 | 2.730e-2 | 47.57 | 0.1124 | 仓库 E_mid |
| 49.19 | 12.61 | 5.780e-3 | 12.61 | 2.162 | 仓库 E_mid |
| 99.113 | 7.335 | 2.969e-3 | 7.338 | 7.596 | 仓库 E_mid |
| 198.65 | 4.510 | 1.532e-3 | 4.512 | 25.66 | 仓库 E_mid |

### 11.3 ESTAR：硅

| T (MeV) | CLOSS | RLOSS | TLOSS | CSDA g/cm² | Radiation yield | DELTA |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.507 | 2.360e-2 | 1.531 | 0.5386 | 8.275e-3 | 0.3424 |
| 10 | 1.697 | 0.3161 | 2.013 | 5.642 | 7.919e-2 | 2.239 |
| 20 | 1.769 | 0.7023 | 2.472 | 10.11 | 0.1514 | 3.323 |

### 11.4 ESTAR：水（CSDA 交叉核对）

| T (MeV) | CLOSS | TLOSS | CSDA g/cm² |
| --- | --- | --- | --- |
| 1 | 1.849 | 1.862 | 0.4367 |
| 10 | 1.968 | 2.149 | 4.975 |

### 11.5 XCOM：质量衰减系数（cm²/g）

| 材料 | 0.1 MeV | 1 MeV | 10 MeV |
| --- | --- | --- | --- |
| Water，with coherent | 0.1707 | 0.07072 | 0.02219 |
| Water，without coherent | 0.1654 | 0.07066 | 0.02219 |
| Al，with coherent | 0.1704 | 0.06146 | 0.02318 |
| Al，without coherent | 0.1572 | 0.06132 | 0.02318 |
| Pb，with coherent | 5.549 | 0.07102 | 0.04972 |
| Pb，without coherent | 5.336 | 0.06803 | 0.04969 |

### 11.6 SR-NIEL：质子/中子硅 NIEL（MeV cm²/g）

| 粒子 | 能量 (MeV) | NIEL | 备注 |
| --- | --- | --- | --- |
| 质子 | 9.5 | 9.6687e-3 | SR-NIEL 结果页 |
| 质子 | 10 | 9.4037e-3 | SR-NIEL 结果页 |
| 质子 | 90 | 3.1841e-3 | SR-NIEL 结果页 |
| 质子 | 95 | 3.0762e-3 | SR-NIEL 结果页 |
| 质子 | 100 | 2.9757e-3 | SR-NIEL 结果页 |
| 中子 | 13.95 | 3.8288e-3 | E722-19 表 |
| 中子 | 14.05 | 3.7858e-3 | E722-19 表 |
| 中子 | 14（几何平均） | 3.8073e-3 | 与仓库 0.0038072 一致 |
| 质子 | 9.5043（log 插值） | 9.66633e-3 | 仓库 DDD 0.00966631 |
| 质子 | 99.113（log 插值） | 2.992918e-3 | 仓库 DDD 0.00299292 |

### 11.7 ASTM E722-19 的 95 MeV·mb

| 量 | 值 | 状态 |
| --- | --- | --- |
| Si 1 MeV 损伤函数 | 95 MeV·mb | **未验证/需复核**（ASTM 全文付费；公开页无此值） |
| 换算 NIEL_ref | 2.037006e-3 MeV cm²/g | 算术核验：95e-27 × 6.02214076e23 / 28.0855 |
| SR-NIEL 1 MeV 附近 | 1.6573e-3 – 2.4078e-3 MeV cm²/g | E722-19 表计算器输出；非独立 |

### 11.8 仓库 `device_dose` 的复现值

| 量 | 能量 (MeV) | 仓库值 | 外部复现 | 差异 |
| --- | --- | --- | --- | --- |
| TID | 10 | 5.75942e-9 Gy cm² | 35.94747 × 1.602176634e-10 | 一致（E_mid） |
| TID | 50 | 1.59856e-9 | 9.97743 × 1.602176634e-10 | 一致（E_mid） |
| TID | 100 | 9.41143e-10 | 5.87415 × 1.602176634e-10 | 一致（E_mid） |
| TID | 200 | 5.83652e-10 | 3.64287 × 1.602176634e-10 | 一致（E_mid） |
| DDD | 10 | 0.00966631 MeV cm²/g | 0.009666330 | 一致（E_mid） |
| DDD | 100 | 0.00299292 | 0.002992918 | 一致（E_mid） |
| DDD | 14（中子） | 0.0038072 | 0.0038073 | 一致 |

---

## 12. 复现命令与页面（供第二人复核）

```bash
# PSTAR silicon nominal
curl -s -X POST \
  --data-urlencode "prog=PSTAR" --data-urlencode "matno=014" \
  --data-urlencode $'Energies=10\n50\n100\n200' \
  https://physics.nist.gov/cgi-bin/Star/ap_table-t.pl

# PSTAR liquid water nominal
curl -s -X POST \
  --data-urlencode "prog=PSTAR" --data-urlencode "matno=276" \
  --data-urlencode $'Energies=10\n50\n100\n150\n200' \
  https://physics.nist.gov/cgi-bin/Star/ap_table-t.pl

# ESTAR silicon default grid (includes CSDA range)
curl -s -X POST \
  --data-urlencode "prog=ESTAR" --data-urlencode "matno=014" \
  --data-urlencode "ShowDefault=on" \
  https://physics.nist.gov/cgi-bin/Star/e_table-t.pl
```

- XCOM 表单：`https://physics.nist.gov/cgi-bin/Xcom/xcom2`（`Method=Elem`，`Output2=Hand`），第二步 `xcom3_1` 用 `ZNum=13/82` 或 `xcom3_2` 用 `Formula=H2O`；`OutOpt=PIC`。
- SR-NIEL 质子结果页：`https://www.sr-niel.org/Simulation/407763niel_p.html`；中子结果页：`https://www.sr-niel.org/Simulation/296234niel_n.html`。结果页 URL 带会话 ID，长期引用时应同时保存 HTML/PDF 和查询参数。
- 本文件的所有外部页面访问日期均为 2026-11-05；若冻结日晚于该日期，应重新核对版本/页面可用性，尤其是 SR-NIEL 结果页和 ASTM 公开页。
