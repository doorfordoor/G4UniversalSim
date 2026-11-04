# Q2-3 REF-LET-01 外部参考病例回执

状态：**作者交付，待独立复验**（2026-11-04T19:45:00Z 生成）。
本回执只覆盖 `docs/collab/decisions/20261105-q2-let-reference-freeze-v1.json` 冻结的两个病例；
未改产品源码、正式测试、正式基准、支持等级或 CI，未提交 Git。

## 1. 身份

- 仓库：`D:/Geant4/G4UniversalSim`，branch `roadmap/Q2-scientific-baselines`，生成时 HEAD `c9c76e3b6779bb8913822ab89c131294e2836134`（病例运行于 `9ed087f2`）。
- 冻结后端：`out/collab/q2-backend-864bc036/G4UniversalSim.exe`，sha256 `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`，
  build `864bc036d6d7752475e52db4efd2b950cabfcc3d`，source fingerprint `e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7`，
  Geant4 `1132`。
- 参考数据：`scenarios/benchmarks/shielding_range/nist/PSTAR_Si.txt`，sha256 `71cfaaf13545201276c24195d96a4fafd2341bf5fbd26ed52133cce0b42f2422`，
  与冻结值一致。
- 冻结文件：`docs/collab/decisions/20261105-q2-let-reference-freeze-v1.json`，sha256 `b22b7d6535d226f632719f759003b391d2153f28802a348ae4b071a178136af1`。
- `--check-geant4-data`：exit 0，输出 sha256
  `ec86b695aebaa3a766d75e181c33f9c71c3787acfa787772317681a9d31929ac`。

## 2. 交付文件

| 文件 | sha256（前缀） | 字节 |
| --- | --- | --- |
| `README.md` | `3b722f760747cf24…` | 7926 |
| `identity.json` | `5e010a33404bba5a…` | 3053 |
| `reference.py` | `3767222c42f38a32…` | 7825 |
| `reference-recompute.json` | `29e95761f400f7b7…` | 1847 |
| `setup_inputs.py` | `036632ab86f58ae1…` | 8201 |
| `run_cases.py` | `ae6b2d566a964a73…` | 5104 |
| `compare.py` | `84fd246239c3d8a0…` | 16637 |
| `tamper.py` | `fbb7ddc1aa001683…` | 4751 |
| `results.json` | `70585313dadfa7cd…` | 42099 |
| `tamper-results.json` | `dcc35a5756b208a0…` | 1043 |
| `backend-data-check.txt` | `ec86b695aebaa3a7…` | 2240 |
| `inputs/main_ref_let_10.ini` | `872a00c950569f59…` | 846 |
| `inputs/main_ref_let_100.ini` | `0fcb374151344657…` | 849 |
| `inputs/geometry_let.ini` | `3802c956bccab42f…` | 220 |
| `inputs/materials.ini` | `fb05cfd6f448f128…` | 67 |

运行产物在 `runs/ref_let_10/`、`runs/ref_let_100/`（含 `run.mac`、`backend.log`、
`record.json` 与 `output/`）；完整执行原始文件保留，未复制覆盖。

## 3. 参考重算（独立于冻结值）

`reference.py` 从 PSTAR 原始字节按冻结方法重算：输入表 sha256 校验通过、132 行数据，
两例 E_mid/LET 与冻结值比较为 `mid_delta=0`、`let_delta=0`（相对差 0.0）。结果在
`reference-recompute.json`，失败时 `--check` 非零退出。

## 4. 运行与门禁

两例均真实运行（冻结后端、1 线程、2000 事件、seed 20261111/20261112），`exit=0`、
`completed_events=2000`。`results.json` 的 101 项检查中：

- 身份门禁 `ID-*`：全过；
- 运行证据门禁 `EVID-*`：全过（摘要/metadata 生命周期、冻结 N、资产 sha256/size、
  scorer_statistics 事件数、无 hits）；
- 矩复算 `MOM-*`：全过；
- 统计估计 `STAT-*`：全过（`estimator=ratio`、`uncertainty_estimator=uncorrected_delta_ratio_v1`、
  `approximate`、有限非负误差）；
- 参考比较 `REF-*`：10 MeV 全过；100 MeV `REF-LET-D-REL` 失败（唯一 fail）。

## 5. 结果

| 能量 | 参考 LET | let_t | 相对误差 | 允许 | let_d | let_d−let_t | 相对 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 MeV | 8.10751145090545 | 8.1006542922 | -8.457785e-04 | 0.122106 | 8.10076799456 | 1.137e-04 | 1.404e-05 | **pass** |
| 100 MeV | 1.3599232692852166 | 1.37634949516 | 1.207879e-02 | 0.068893 | 1.66627194324 | 0.289922 | 0.2106 | **fail** |

`let_d−let_t` 的独立误差上界：10 MeV z=0.488，
100 MeV z=0.958
（σ_d=0.3022，σ_t=0.016165）。

## 6. 失败项、诊断提案与未通过范围

100 MeV 的 `relative(let_d−let_t)=21.06%` 超过冻结的 5% 辅助判据，因此 REF-LET-01 按冻结规则
**整体 fail**；`let_t` 与参考的对照本身通过（+1.21%，允许 5.07%）。失败项的关键数据：

- `let_d` 的 delta 方法相对误差为 18.1346%，
  `let_t` 为 1.1745%；
- 差值 0.2899 keV/µm 与 σ_d=0.3022 keV/µm 同量级（保守独立 z≈0.96）；
- 10 MeV 同几何在相同 2000 事件下差值仅 1.4e-5，说明 100 MeV 的 `let_d` 被少数高 LET 步骤/次级
  主导，而不是实现公式造成的一致偏移。

最小诊断提案（需新的预注册冻结，本轮**不执行、不调参**）：

1. 输出 `let_t` 与 `let_d` 的交叉矩，或逐事件矩，用于计算差值自身的 delta 方法误差；
2. 按 Q2-4 预注册 `let_d` 方差与所需 N，用独立批次判定而非单点 5% 阈；
3. 先冻结“是否只算初级质子”的 LET 口径，区分实现错误与核反应次级贡献。

在判据/参考/样本/物理被主审重新冻结前，不改变本病例输入、容差、cut 或事件数。

## 7. 负例

`tamper.py` 在**拷贝**上构造并全部检出（3/3）：

- `REF-NUMERIC-SHIFT`：copy of the frozen reference with 10 MeV LET +6% → 期望 REF-LET-T-ABS，检出 exit 1。
- `REF-SOURCE-MAPPING`：copy of results where the 10 MeV case claims the 100 MeV energy → 期望 REF-LET-T-ABS，检出 exit 1。
- `REF-DATA-SHA`：copy of PSTAR_Si.txt with one stopping-power digit changed → 期望 data_sha256 mismatch，检出 exit 1。

原件与冻结文件未被修改；`tampered/` 可整体删除后重跑 `tamper.py`。

## 8. 复现与校验

```
python -B out/collab/q2-reference-let-v1/setup_inputs.py
python -B out/collab/q2-reference-let-v1/reference.py --check
python -B out/collab/q2-reference-let-v1/run_cases.py     # overall fail：仅 REF-LET-D-REL
python -B out/collab/q2-reference-let-v1/tamper.py        # 3/3 检出
```

`compare.py` 可独立读取 `results.json` 重放判据；`check_doc_links` 对回执/README 的相对链接有效。
实际工具输出、事件数、退出码与哈希均见 `results.json`/`identity.json`/`tamper-results.json`。

## 9. 限制与停止声明

- 仅 Windows、单线程、2000 事件、冻结两例；统计覆盖率、其它能量/材料、MT、GUI 不在本任务。
- `let_d` 大误差的物理归因仍属未决；本交付不给“物理已通过”结论，也不以调参方式消除失败。
- 作者自测不是独立复验；已停写，等待主审独立复跑与签收。
