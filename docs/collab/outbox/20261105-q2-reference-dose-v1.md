# 回执：Q2-3 REF-DOSE-01 四个冻结参考病例

- 日期：2026-11-05
- 执行：DeepSeek（Lead 执行负责人）
- 依据：`docs/collab/inbox/20261105-q2-reference-dose-v1.md`、
  `docs/collab/decisions/20261105-q2-dose-reference-freeze-v1.md` 与同名 JSON
- 状态：**四例比较通过；真实运行四例均完成 20000 事件；有限反例 7/7 检出；原件未变**
- 写入范围：仅 `out/collab/q2-reference-dose-v1/**` 与本文档；未修改产品、正式测试/基准、
  冻结合同、其它候选、`ROADMAP.md`/`STATUS.md`；未提交 Git。

## 1. 冻结身份（未变更）

| 项目 | 值 |
| --- | --- |
| 冻结 JSON SHA-256 | `a2a799e90bd941b4969beab62be408013420dfbd684c4e8e52f07775308e498d` |
| schema / case | `q2_reference_dose_freeze_v1` / `REF-DOSE-01` |
| 后端 exe SHA-256 | `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f` |
| 后端 build | `864bc036d6d7752475e52db4efd2b950cabfcc3d` |
| 后端 source fingerprint | `e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7` |
| Geant4 | 11.3.2（`G4VERSION_NUMBER = 1132`） |
| PSTAR 表 | `scenarios/benchmarks/shielding_range/nist/PSTAR_Si.txt`，SHA-256 `71cfaaf13545201276c24195d96a4fafd2341bf5fbd26ed52133cce0b42f2422`，10507 B，132 行，0.001–10000 MeV |
| Geant4 数据自检 | 退出码 0，`required_complete = true` |

生成输入均记录 SHA-256（见 `identity.json` 与 README 表）。运行前先核对身份，后比物理。

## 2. 独立参考重算

`reference.py` 只读 PSTAR 原始字节，按冻结方法重算 E_mid、电子阻止本领与 D/Φ，并独立
推算敏感片质量：

- 四例 `dose_per_fluence_relative_delta = 0`、`energy_mid_delta = 0`、`sensitive_mass_delta = 0`；
- 插值区间全部落在表内部；PSTAR 字节 SHA 与冻结一致（`data_matches_freeze = true`）；
- 输出 `reference-recompute.json`（schema `g4usim_q2_ref_dose_recompute_v1`）。

| 病例 | E0 (MeV) | E_mid (MeV) | Se (MeV cm²/g) | 冻结 D/Φ (Gy cm²) |
| --- | --- | --- | --- | --- |
| ref_dose_10 | 10 | 9.50433541620899 | 35.94748529368706 | 5.759422098860403e-09 |
| ref_dose_50 | 50 | 49.19041512400653 | 9.977400889717448 | 1.5985558573556106e-09 |
| ref_dose_100 | 100 | 99.11269531665732 | 5.874150333423087 | 9.41142640881378e-10 |
| ref_dose_200 | 200 | 198.65003216203812 | 3.642867996985731 | 5.836517985516922e-10 |

## 3. 真实运行事实

同一冻结后端，四例仅电磁 option4、10 um cut、1 线程、各 20000 事件，按合同几何
（块前表面 z=0，敏感片在块局部中心，点平面源 z=-1mm）与冻结种子运行：

| 病例 | 种子 | 后端 exit | 完成事件 | 用时 | 记录状态 |
| --- | --- | --- | --- | --- | --- |
| ref_dose_10 | 20261106 | 0 | 20000 | 1.781 s | 复用已验证记录 |
| ref_dose_50 | 20261107 | 0 | 20000 | 3.385 s | 复用已验证记录 |
| ref_dose_100 | 20261108 | 0 | 20000 | 3.15 s | 复用已验证记录 |
| ref_dose_200 | 20261109 | 0 | 20000 | 3.419 s | 复用已验证记录 |

完成事实取自 `run_summary.txt`/`run_metadata.json`；hits 行数不当作事件总数。
四例 `scorer_statistics.csv` 的 `n_events` 均为 20000，`entries`（非零贡献事件数）分别为
13834 / 13894 / 13884 / 13854，符合“漏靶事件按零贡献保留”的合同口径。

复用规则（冻结输入未变不重跑）：冻结 SHA、后端 SHA、生成输入 SHA、记录产物 SHA/大小、
`run_summary.txt` 完成事件数全部一致即复用；最终结果四例均 `reused: true`，未再次模拟。

## 4. 比较结果（四层证据门禁之后）

| 病例 | 参考 D/Φ | 模拟 D/Φ | 绝对差 | 相对差 | σ | 允许误差 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ref_dose_10 | 5.759422098860403e-09 | 5.7375158097023994e-09 | −2.1906289158003958e-11 | −3.804e-03 | 2.756847456982235e-11 | 1.9789386568667512e-10 | pass |
| ref_dose_50 | 1.5985558573556106e-09 | 1.5936261401015997e-09 | −4.929717254010895e-12 | −3.084e-03 | 7.878024735804674e-12 | 5.5605191354526236e-11 | pass |
| ref_dose_100 | 9.41142640881378e-10 | 9.367205891472e-10 | −4.422051734178057e-12 | −4.699e-03 | 5.02734376149564e-12 | 3.390488410211448e-11 | pass |
| ref_dose_200 | 5.836517985516922e-10 | 5.7873788827704e-10 | −4.913910274652172e-12 | −8.419e-03 | 3.230626399903765e-12 | 2.136491517074514e-11 | pass |

- 判据：`|D/Φ − 参考| ≤ 0.02·参考 + 3σ`，`D/Φ = weighted_dose_Gy × 1.44 / 实际完成 N`，
  `σ = D/Φ × weighted_dose rel_error`；统计量使用真实 N（含零贡献事件），未按结果调整门槛；
- `results.json.evaluation`：**pass，494 项检查，0 失败**；检查分层为
  ID（身份）/ IN（输入）/ EVID（运行证据）/ MOM（原始矩与实现对账）/ STAT（统计量）/
  REF（参考比较）；
- 实现自洽：raw=weighted 剂量（权重恒 1），由 hits 与独立几何质量从零重算的 D/Φ 与产品
  路径相差约 1e-21 Gy cm²（远小于 1e-9 相对约束）；
- 体积/质量口径：`dose_volume_summary_t0.csv` **没有** `volume_mm3` 列；敏感片体积由
  10 mm × 10 mm × t 的几何定义和 2.33 g/cm³ 密度独立推算，再与 CSV 的 `mass_kg` 对账，
  未把推算值称为 CSV 原字段；注量面积 1.44 cm² 是 12 mm × 12 mm 方束面积，不是 1.0 cm²
  的片面积。

## 5. 有限反例（副本）

`tamper.py` 只在 JSON 副本与硬链接影子上变异，不回写原件；完成后复核原件 SHA 未变化
（`originals_unchanged: true`）。7/7 变异均使评估 fail closed：

| 反例 | 检测到的检查 |
| --- | --- |
| missing_metadata | `EVID-METADATA-FILE` |
| reference_plus_6pct | `REF-DPHI-ABS`（四例） |
| energy_mapping_swapped | `IN-SOURCE-ENERGY`、`IN-SEED` |
| mass_unit_factor | `EVID-ASSET-SHA-dose_volume_summary_t0.csv`、`EVID-OUTPUT-DIR` |
| fluence_area_factor_100 | `IN-SOURCE-AREA`（四例） |
| artifact_sha_tampered | `EVID-RECORDED-hits_t0.csv` |
| freeze_mass_unit_factor | `MOM-MASS-MATCHES-FREEZE`（算术层） |

质量单位因子的输出文件变异先被证据层拒绝；其算术层由 `freeze_mass_unit_factor` 与正例的
`MOM-MASS-INDEPENDENT` 覆盖。

## 6. 执行驱动问题（已保留记录，非物理失败）

1. 初次方源多写 `halfy`，后端在运行前拒绝：
   `G4UniversalSim fatal error: SourceManager plane square uses halfx only.`。
   这是输入字段契约问题，不是物理比较失败；修正为方源只写 `halfx`，四例随后成功完成。
   原失败后端日志已被后续成功运行覆盖，`driver-notes.md` 保留原始错误文本、修正方式与证据边界。
2. 复用判断曾把“旧记录缺少后来新增身份字段”误报为 `freeze changed`，导致重复模拟；冻结
   文件字节 SHA 实际始终为 `a2a799e9…`、未变更。修正后的复用只比较 SHA/大小/完成事件，
   最终四例均复用，未再重跑。详见 `driver-notes.md`。

## 7. 复现

```powershell
cd D:\Geant4\G4UniversalSim\out\collab\q2-reference-dose-v1
python setup_inputs.py
python reference.py --check
python run_cases.py
python compare.py --results results.json --update
python tamper.py
```

## 8. 边界

- 仅电磁质子、碰撞平衡薄层 TID 的四个冻结能量点与本后端/本 PSTAR 表；不覆盖强子输运、
  厚靶、次级粒子不平衡或实验测量验证；
- 未声明完整强子剂量、NIEL 或活化能力；
- 本轮未提交 Git；是否冻结/提交由监督端决定。

## 9. 文件与校验

- `out/collab/q2-reference-dose-v1/`：`setup_inputs.py`、`reference.py`、`run_cases.py`、
  `compare.py`、`tamper.py`、`identity.json`、`reference-recompute.json`、`results.json`、
  `tamper-results.json`、`backend-data-check.txt`、`driver-notes.md`、`README.md`、
  `inputs/`、`runs/`、`tampered/`
- `docs/collab/outbox/20261105-q2-reference-dose-v1.md`（本回执）
- `check_doc_links.py` 与 `git status` 结果见提交消息外的执行记录：候选目录与回执为新增，
  未触碰被跟踪的产品/基准文件；`docs/ROADMAP.md` 的既有监督端改动保持原样。
