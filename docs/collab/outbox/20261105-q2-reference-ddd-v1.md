# REF-DDD-01 交付回执（observability r1 修订，等待独立复验）

日期：2026-11-05
任务：`docs/collab/inbox/20261105-q2-reference-ddd-v1.md`
冻结：`docs/collab/decisions/20261105-q2-ddd-reference-freeze-v1.md` 与同名 JSON
本修订依据：`docs/collab/inbox/20261105-q2-ddd-observability-r1.md`、
`docs/collab/reviews/20261105-q2-ddd-reference-review-r1.md`

## 结论（先看判定）

两例真实运行与两个冻结参考点仍然通过；**整体机器判定为 `limited`，不是 `pass`**。
`compare.py` 共 **263 项：257 pass / 0 fail / 6 limited**。limited 全部来自公开输出无法
证明的观测缺口；没有任何检查被放宽、没有任何容差被修改、没有重跑 Geant4。

首候选的“完整折积验证”结论已按独审撤回：`[pre − Edep, pre]` 能量区间与 5% 宽度门槛不成立，
旧证据（261 项 pass、首轮反例、失败脚本）保留在
`docs/verification/q2-ddd-review-20261105/first-counterexample/`，本修订不覆盖。

## 本修订改了什么

只改候选内 `compare.py`、`tamper.py`、`README.md`、新增合成反例脚本与 `evidence/`、本回执：

1. 删除 `folding_bracket`/`niel_window_bounds`，删除 `MOM-DDD-FOLDING-BRACKET` 与
   `MOM-BRACKET-WIDTH`（每例 2 项，共 4 项旧 pass 撤回）；不发明替代区间。
2. `check()` 增加显式 `limited` 状态；整体判定 `fail` > `limited` > `pass`，有任一 limited 时
   永远不能整体 pass；机器输出分开 `checks_pass`/`checks_failed`/`checks_limited`。
3. 每例报告可见 hits 长度、scorer 长度、gap 与相对值；精确长度对账、可见事件全集、逐步折积
   三项登记为 `limited`。
4. 新增 `counterexample_bracket.py`：pre=100 / post=99.899 / Edep=0.001 / 次级=0.100 MeV 的
   合成能量账本反例，明确标注**不是实测步**，证明旧区间不成立。
5. `tamper.py` 要求反例命中的检查必须是真实 `fail`，baseline 的 `limited` 不能冒充检出；
   baseline 要求 0 失败且 limited=6。
6. 修正复演命令：`reference.py` 没有 `--check`（默认运行即执行 11 项校验）。
7. 没有运行 Geant4、没有改输入/原始输出/冻结 JSON/NIEL 表/产品/正式测试/基准/容差，未提交 Git。

## 冻结身份（未变）

| 项 | 值 |
| --- | --- |
| 冻结 JSON SHA-256 | `65877c33ad74111f5c567d060f495eccea074b378b3c5bd0b9bdd4f6e40b6a7c` |
| 几何来源冻结 | Dose 冻结 `20261105-q2-dose-reference-freeze-v1.json`，SHA-256 `a2a799e90bd941b4969beab62be408013420dfbd684c4e8e52f07775308e498d` |
| 后端 | build `864bc036d6d7752475e52db4efd2b950cabfcc3d`，exe SHA-256 `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`（2 786 304 B） |
| 源码指纹 | `e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7` |
| Geant4 | 11.3.2，`--check-geant4-data` 退出 0 / `required_complete=true` |
| NIEL 表 | `si_proton.csv` 146 行 `[1e-6, 1e4]` MeV，SHA-256 `6c21e35aab18495d4bb2597a76be60c7c35ef0df963224e0108c77c2e4c208d5`；中子表仅登记身份 `a2ad28a9…`，未使用 |

## 运行事实（未重跑）

| 病例 | 后端退出码 | 完成事件 | 用时 (s) | 本次修订 |
| --- | --- | --- | --- | --- |
| `ref_ddd_10` | 0 | 20000 | 1.775 | 复用原始输出，未运行 Geant4 |
| `ref_ddd_100` | 0 | 20000 | 3.296 | 复用原始输出，未运行 Geant4 |

产物 SHA-256（前 16 位）：10 MeV 的 summary `aef1dffcb2b832fa`、metadata `1821c40c3ecf9ded`、
hits `960125abc8627aaf`、DDD 汇总 `606c66ddd03d51be`、统计 `dc3d7d1ec65c1ea1`；100 MeV 的
summary `2ae05e51c97879c1`、metadata `a8a0fa1f40830f75`、hits `d6d835a37b9c8044`、DDD 汇总
`6dbecc3d12e69fef`、统计 `54ea3a3fc24073d7`。`run_metadata.json` 对自身为
`self_reference_excluded`（不要求自哈希），其余产物均按 SHA+大小核对。

## 机器判定与检查分层

| 层 | 项数 | 说明 |
| --- | --- | --- |
| ID | 19 | 后端/冻结/几何来源/表/输入身份 |
| IN | 64 | EM-only、无 reference、cut、计分、线程/种子/源/几何/面积 |
| EVID | 86 | summary/metadata 完成事实、产物 SHA+大小、输出目录、日志、输入 SHA |
| MOM | 42 | hits/DDD 表头、体积、长度下界、越界 0、事件矩；其中 **6 项 limited** |
| STAT | 46 | 两行统计与公开矩独立重算 |
| REF | 6 | 两冻结参考点 1% + 3σ |

6 项 limited（每例 3 项）：

| 检查 id | 含义 |
| --- | --- |
| `MOM-ref_ddd_10-TRACK-LENGTH-FULL`、`MOM-ref_ddd_100-TRACK-LENGTH-FULL` | hits 只含正沉积步，DDD 计分器还会收到零沉积输运步；精确长度对账不可恢复，可见长度只是下界 |
| `MOM-ref_ddd_10-VISIBLE-EVENTS-SUBSET`、`MOM-ref_ddd_100-VISIBLE-EVENTS-SUBSET` | 可见事件集合只是 DDD 贡献事件的下界，不是完整集合 |
| `MOM-ref_ddd_10-FOLDING-STEPWISE`、`MOM-ref_ddd_100-FOLDING-STEPWISE` | 逐步折积需内部步平均动能，公开列没有；旧区间已撤回，不发明替代 |

**退出码语义**：`compare.py` 维持“非全 pass 即非零”的既有约定，`limited` 时返回 1。这是比较器
判定，不是后端失败；两例后端真实退出码均为 0，已在上表分列。

## 可见路径与观测缺口

| 病例 | hits 质子加权长度 (mm) | scorer `track_length_mm` (mm) | gap (mm) | gap 相对值 | hits 行 / 可见事件 |
| --- | --- | --- | --- | --- | --- |
| `ref_ddd_10` | 276.65399240839093 | 276.653992408 | -3.909e-10（打印精度内） | -1.413e-12 | 13828 / 13828 |
| `ref_ddd_100` | 1388.624873981282 | 1388.62550122 | 6.272387e-04 | 4.517e-07 | 17964 / 13889 |

独审在 C 盘独立输出上复算的 100 MeV gap 为 **0.0006272387224726117 mm**（相对 `4.517e-7`）；
用公开 CSV 的 12 位打印值重算得 `6.272387e-04` mm，仅末位不同，不改变结论。差额与“零沉积步
计分但不入普通 hits”的既有语义一致；本候选不断言差额为零、不据此声称产品缺陷或物理正确性。
可见事件数也不是完整 DDD 贡献事件集；N=20000 与零贡献事件保留在分母中不变。

## 已撤回的证明（保留原始证据，不重造）

首候选曾用 `[pre − Edep, pre]` 作为步平均动能的精确区间并据此宣布完整折积。独审的反例（合成账本，
**非实测步**）：

| 量 | 值 (MeV) |
| --- | --- |
| pre / post | 100 / 99.899 |
| 局部 Edep / 次级携能 | 0.001 / 0.100 |
| 前后差 = Edep + 次级 | 0.101 |
| 真实步平均 | 99.9495 |
| 旧区间 `[pre − Edep, pre]` | `[99.999, 100]`（真实平均在区间外） |

本修订把它保存为 `counterexample_bracket.py` 与
`evidence/withdrawn-bracket-counterexample.json`（`synthetic=true`、`not_a_measured_step=true`），
并删除旧 `folding_bracket`/`niel_window_bounds`/`MOM-DDD-FOLDING-BRACKET`/`MOM-BRACKET-WIDTH`。

## 参考比较（两例仍 pass）

| 病例 | DDD (MeV/g) | DDD/Phi (MeV·cm²/g) | 参考 | 绝对差 | 相对差 | σ | 允许 | 判据 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ref_ddd_10` | `133.691937374` | `9.625819490927999e-03` | `9.666310206360261e-03` | `-4.049071543226271e-05` | `-4.188849e-03` | `4.548226878772154e-05` | `2.3310990842676725e-04` | pass |
| `ref_ddd_100` | `41.5611752708` | `2.9924046194976e-03` | `2.9929239738930983e-03` | `-5.19354395498231e-07` | `-1.735274e-04` | `1.4040181148458543e-05` | `7.20497831843066e-05` | pass |

统计：`n_events = 20000`，`entries = 13828 / 13889`，`rel_error = 4.72502822545e-03 /
4.69193940451e-03`，`uncertainty_estimator = uncorrected_event_moments_v1`、
`uncertainty_status = approximate`；比较器用公开矩独立重算上述量。参考重算两例相对差
`-7.178e-16` 与 `0`。

## 负例（7/7 真实 fail，原件 SHA 未变）

`tamper-results.json` schema `g4usim_q2_ref_ddd_tamper_v2`：baseline
（263/257/0/6，`zero_real_failures=true`），7 个反例均以真实 `fail` 命中预期检查，
`originals_unchanged=true`，`status=pass`。

| 反例 | 检出项（真实 fail） |
| --- | --- |
| 删除 metadata | `EVID-METADATA-FILE` |
| DDD 体积列 ×2 | `MOM-DDD-VOLUME-COLUMN` |
| 冻结束面积 ×100 | `REF-DDD-PHI-ABS` |
| 冻结参考值 ×1.06 | `REF-DDD-PHI-ABS` |
| identity 中质子表 SHA 改为 0 | `ID-TABLE-SHA-PROTON` |
| summary 完成事件改为 19999 | `EVID-RUN-0-COMPLETED-EVENTS`、`EVID-ACTUAL-COMPLETED-EVENT-COUNT` |
| 篡改 hits 后保留旧记录 SHA | `EVID-RECORDED-hits_t0.csv` |

反例只在 `tampered/` 临时副本进行并在运行后删除；正例原件从未被覆盖。

## 复现（仅比较/反例，不重跑后端）

```bash
cd out/collab/q2-reference-ddd-v1
python -B setup_inputs.py            # 冻结/后端/表身份，生成 inputs/ 与 identity.json
python -B reference.py               # 11 项参考校验；没有 --check 参数（传 --check 返回 2）
python -B run_cases.py               # 输入未变时复用；reused=true 时不重跑后端
python -B compare.py --update        # 263 项：257 pass / 0 fail / 6 limited，退出 1
python -B tamper.py                  # baseline=limited，7/7 反例真实 fail，退出 0
python -B counterexample_bracket.py  # 合成账本反例，退出 0
```

## 交付物与 SHA

候选：`out/collab/q2-reference-ddd-v1/`

| 文件 | SHA-256 前缀 |
| --- | --- |
| `compare.py` | `ac28944a83c7bd6a…` |
| `tamper.py` | `cf85fcca73c42a4c…` |
| `counterexample_bracket.py` | `d7096a3e737bba8e…` |
| `identity.json` | `11f27eb0ab5a700b…` |
| `reference-recompute.json` | `3c4ce05ccb6ffa05…` |
| `results.json` | `667504b609509aa0…` |
| `tamper-results.json` | `a6a87db76443753d…` |
| `evidence/withdrawn-bracket-counterexample.json` | `cb1bd717d07796f1…` |
| `README.md` | `—`（本回执不含自身哈希） |

旧证据归档：`docs/verification/q2-ddd-review-20261105/first-counterexample/`
（author-v1.zip、independent-v1.zip、首轮 counterexample、失败脚本、manifest；未覆盖）。

## 边界与声明

- 只检验**两个冻结参考点 + 可见长度下界 + 公开事件矩**；不验证 SR-NIEL 数据/截面/物理列表选择
  （REF-DDD-02 另案），不声称完整折积验证通过。
- 不声称逐步折积已重放；公开 hits CSV 只有步前动能列，旧区间已撤回且不建立替代区间。
- 两例、两个能点、单线程、仅电磁 `option4`、固定几何/源/cut/种子；不覆盖强子输运、中子、活化、
  非平板几何或其他容差。
- 未修改产品、正式测试/基准、冻结文件、表数据、其它候选、ROADMAP/STATUS；未提交 Git。
- 交付后停写，等待监督端独立复验。

## 历史（保留，不覆盖）

首候选（原 turn64）两例运行 exit 0、261 项 pass（ID 19 / IN 64 / EVID 86 / MOM 40 /
STAT 46 / REF 6）、7 反例检出；独审以“hits 非完整计分路径”和“`[pre − Edep, pre]` 区间不成立”
拒绝其完整折积结论。本修订撤回每例 `MOM-DDD-FOLDING-BRACKET` 与 `MOM-BRACKET-WIDTH`
（共 4 项旧 pass），新增 6 项 limited，其余 257 项保留并通过；两冻结参考点仍 pass。
