# REF-DDD-02 回执：硅 NIEL 表只读审计（等待独立复验）

日期：2026-11-05
任务：`docs/collab/inbox/20261105-q2-niel-table-audit-v1.md`
冻结合同：`docs/collab/decisions/20261105-q2-niel-table-audit-freeze-v1.json`
（SHA-256 `92cfff501fcdff2fc0ea40010f02b23f3eabf45cb3b16c1d9a027c08a7702bb4`，1 811 B）

## 结论

| 维度 | 判定 |
| --- | --- |
| 结构审计 | **pass**（两表 SHA/表头/行数/能量域/严格递增/有限非负值全过） |
| 算术重算 | **pass**（95 MeV·mb 单位换算、中子 1 MeV log-log 与线性插值均在 1e-6 相对容差内） |
| 物理评价 | **limited**（冻结合同自身限定：95 输入未核实、无独立表全文核验、无物理 pass/fail 门槛） |
| 机器总判定 | **limited**：27 pass / 0 fail / 3 limited |

**没有整体 NIEL 物理验证通过**；结构/算术通过不等于物理评价通过。本任务未运行 Geant4，未改两张表、
产品代码、冻结合同、正式测试/基准、阶段状态，未提交 Git。

## 冻结合同与表身份

| 项 | 值 |
| --- | --- |
| 冻结合同 | `schema=q2_niel_table_audit_preregister_v1`，`case=REF-DDD-02` |
| 质子表 | `scenarios/semiconductor/niel/si_proton.csv`，SHA-256 `6c21e35aab18495d4bb2597a76be60c7c35ef0df963224e0108c77c2e4c208d5`，146 行，`[1e-06, 10000.0]` MeV |
| 中子表 | `scenarios/semiconductor/niel/si_neutron.csv`，SHA-256 `a2ad28a9fcce3500fca363946e09e19125d084f1b596eff76662b272c242034f`，640 行，`[1.025e-10, 19.95]` MeV |
| 表头 | 两表均为 `energy_MeV,niel_MeV_cm2_g` |

来源声明（仅身份记录，不是独立物理证据）：两表注释声明来自 SR-NIEL 网页计算器（`sr-niel.org`，
SR-NIEL-7 ver. 11.1，retrieved 2026-10-22）；质子表声明阈值 21 eV、`Hadron+Coulomb`、强子不缩放；
中子表声明 ASTM E722-19 损伤函数（Table A1.1）分群值。`identity.json` 原样保存注释与声明匹配结果。
本次审计**未取得 ASTM/SR-NIEL 原始发布物全文**，注释本身不构成验证。

## 结构审计（全部 pass）

两表：SHA 与冻结一致；表头精确匹配；行数 146 / 640 与冻结一致；首末能量与冻结域一致；
能量为正、有限、严格递增；NIEL 全部有限且非负；无畸形行（列数错误/非数值）；LF、末尾换行。
质子表 11 行注释 + 表头 + 146 行数据；中子表 8 行注释 + 表头 + 640 行数据。质子表注释中的
`added: 1e-06 MeV ... NIEL 0` 是既有生成说明；本审计不补点、不改表。

## 算术重算（独立脚本，单位与公式显式）

使用冻结参数 `A[Si]=28.0855 u`、`u=1.6605390666e-24 g`、1 mb = `1e-27 cm²`。

| 量 | 公式 | 复算值 | 冻结值 |
| --- | --- | --- | --- |
| 硅原子质量 | `A*u` | `4.66370699549943e-23 g` | 同值 |
| 95 MeV·mb 假设输入 | `(95 MeV·mb × 1e-27 cm²/mb)/m_Si` | `0.0020370061861021047 MeV·cm²/g` | 同值 |
| 中子 1 MeV log-log | `ln y = ln y0 + ln(E/E0)/ln(E1/E0)·(ln y1−ln y0)`，节点 0.98/1.05 MeV，`E=1` | `0.0021583350121061676 MeV·cm²/g` | 同值 |
| 中子 1 MeV 线性 | `y = y0 + (E−E0)/(E1−E0)·(y1−y0)` | `0.0021933714285714283 MeV·cm²/g` | 同值 |
| 两算法相对差 | `(linear−loglog)/loglog` | `1.6233076083527528e-02`（≈1.6233%） | 同值 |

原始节点：`0.98 MeV → 0.0024078`、`1.05 MeV → 0.0016573` MeV·cm²/g（中子表原行，非新补点）。
单位方向：`mb → cm²` 乘 `1e-27`；`MeV·mb` 是能量×面积，结果量纲 `MeV·cm²/g`。
所有比较使用 1e-6 **算术复现**相对容差，不是物理容差。

**算法差与对参考点差分开记录（不推断成因）**：1.6233% 是两种插值算法之间的相对差；中子表 1 MeV
log-log 值相对“95 MeV·mb 假设输入”的点差为 `1.2132882600406287e-04 MeV·cm²/g`（相对 5.9562%），
线性为 `1.563652424693236e-04`（相对 7.6762%）。95 输入未经权威全文核实、表注释不是独立物理证据，
因此**不把约 6% 差异判定为缺陷，也不推断评价方法/能量依赖/模型选择的成因**；它们只是算术记录。

## 物理评价：limited（3 项显式限制）

| 检查 id | 内容 |
| --- | --- |
| `PHY-95-INPUT-NOT-VERIFIED` | 95 MeV·mb 输入在冻结中自述“未核实 ASTM 输入，仅算术练习”；本次未取得权威全文数值 |
| `PHY-TABLE-MODEL-NOT-INDEPENDENTLY-CHECKED` | 未独立验证 ASTM E722-19 Table A1.1 分群内容与 SR-NIEL 计算模型/版本选择；注释只是来源声明 |
| `PHY-NO-PHYSICAL-PASS-THRESHOLD` | 冻结合同没有物理 pass/fail 门槛，本次不能给 NIEL 物理评价判 pass |

机器判定分开 pass/fail/limited：`results.json` 的 `counts` 为 27/0/3，`status=limited`，
`status_detail.structure_and_arithmetic=pass`、`status_detail.physical_evaluation=limited`。
`audit.py` 对 limited 返回退出码 1，输出明确“overall limited, not a script error”，
防止任何下游把结构/算术 pass 读成整体物理通过。**这不是后端退出失败**（本任务无后端运行）。

## 反例（副本，5/5 真实 fail，原件 SHA 未变）

| 反例 | 变更 | 命中真实 fail 的检查 |
| --- | --- | --- |
| `wrong_unit_factor` | 1 mb 当 1 barn（`1e-24 cm²`） | `AR-MB-CM2-FACTOR`、`AR-95-MEV-MB-TO-NIEL` |
| `table_sha_changed` | 中子副本末行 NIEL +1e-6 | `ID-TABLE-SHA-NEUTRON` |
| `non_monotonic` | 质子副本重复首行能量 | `STRUCT-ENERGY-INCREASING-PROTON` |
| `non_finite` | 质子副本某行 NIEL 改 `nan` | `STRUCT-NIEL-FINITE-NONNEG-PROTON` |
| `header_changed` | 中子副本表头改名 | `STRUCT-HEADER-NEUTRON` |

反例只在 `tampered/` 临时副本进行，结束删除；`tamper-results.json` 记录 baseline=limited
（27/0/3）、5/5 detected、`originals_unchanged=true`、status=`pass`。baseline 的 limited 未被当作
任何反例的检出。

## 复演

```bash
cd out/collab/q2-niel-table-audit-v1
python -B audit.py      # 无 CLI 选项（--help 可用），写 results.json / identity.json
python -B tamper.py     # 副本反例，写 tamper-results.json
```

两个脚本都没有 `--check`、`--force` 或其它未实现选项；复演命令按 `--help` 实际参数验证。
`audit.py` 退出码 1 表示 overall limited（本任务预期，因物理评价受限）或存在 fail，
终端逐行打印实际状态；`tamper.py` 退出码 0 表示 5/5 检出且原件未变。

## 交付物

`out/collab/q2-niel-table-audit-v1/`：`audit.py`、`tamper.py`、`results.json`、`identity.json`、
`tamper-results.json`、`README.md`（10 节：结论、冻结身份、结构、算术、物理限制、反例、复演、
SHA、边界、范围外建议）。候选位于 gitignore 的 `out/` 下。

| 文件 | SHA-256 前缀 |
| --- | --- |
| `audit.py` | `c0f894c4a71dc308…` |
| `tamper.py` | `a3c9ebbdab0f4b42…` |
| `results.json` | `e6197f9fcd8bcf49…` |
| `identity.json` | `5fb85c0c3d051c38…` |
| `tamper-results.json` | `ddb88fc2045edc44…` |

## 边界与未验证项

- 只审计两张硅 NIEL 表的结构、SHA、注释身份、95 MeV·mb 单位算术与中子表 1 MeV 两点插值；
  不验证 NIEL 物理模型、截面、损伤函数、ASTM/SR-NIEL 原始发布值或评价方法。
- 不检查其他粒子/材料表；不补 1 MeV 节点、不改表、不下载付费材料；不新增物理门槛。
- 不重跑 REF-DDD-01 折积；折积候选的 limited 观测限制仍按该候选回执执行。
- 未修改产品、正式测试/基准、冻结合同、数据表、阶段状态；未提交 Git；候选与回执之外未写文件。
- 校验：`check_doc_links` 结果见提交时输出；`git status` 仅监督端既有 `M docs/ROADMAP.md`；
  `scenarios/semiconductor/niel/` 两表零改动。

## 范围外建议（不执行）

1. 若需物理评价 pass，需另行冻结可核实的 ASTM E722-19 全文/版本、SR-NIEL 计算器输入与服务端
   版本记录，并定义可复现的物理比对方法；需监督方确认数据许可与范围。
2. 后续若 REF-DDD-01 需要更强表证据，应作为独立合同追加，不用本审计的 limited 状态支撑折积结论。
