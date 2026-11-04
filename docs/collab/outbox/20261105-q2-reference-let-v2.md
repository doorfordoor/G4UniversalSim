# Q2-3 REF-LET-01-EM（仅电磁）回执

状态：**作者交付，待独立复验**（2026-11-04T20:18:45Z 生成）。
本回执只覆盖 `docs/collab/decisions/20261105-q2-let-reference-freeze-v2.json` 冻结的
**仅电磁 option4** 两例；未改产品源码、正式测试、正式基准、支持等级或 CI，未提交 Git。
**v1（FTFP_BERT_EMZ）的失败仍保留**，v2 是运行前另行冻结的新前瞻实验，不是对 v1 失败的重贴标签。

## 1. 身份与输入

- 仓库：`D:/Geant4/G4UniversalSim`，branch `roadmap/Q2-scientific-baselines`，
  生成时 HEAD `623f20a2b0de65e28680f214a4311a7d08023a61`。
- 冻结后端：`out/collab/q2-backend-864bc036/G4UniversalSim.exe`，sha256 `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`，
  build `864bc036d6d7752475e52db4efd2b950cabfcc3d`，
  source fingerprint `e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7`，
  Geant4 `1132`。
- 参考数据：`scenarios/benchmarks/shielding_range/nist/PSTAR_Si.txt`，sha256 `71cfaaf13545201276c24195d96a4fafd2341bf5fbd26ed52133cce0b42f2422`，
  与冻结值一致（`matches_freeze=True`）。
- 冻结文件：`docs/collab/decisions/20261105-q2-let-reference-freeze-v2.json`，sha256 `4a5ddbe1067589d8437fe604db79f47c68c61e30f9c69d7c86b9d8104166bf5b`，
  schema `q2_reference_let_freeze_v2`。
- `--check-geant4-data`：exit 0，输出 sha256
  `ec86b695aebaa3a766d75e181c33f9c71c3787acfa787772317681a9d31929ac`。
- 实际物理：主 INI 只写 `[physics] em = option4`（不写 `reference`）；两例 `run_summary.txt`
  均报 `physics_em = G4EmStandardPhysics_option4`、`physics_reference` 为空。
- 几何/源/cut/事件数/种子：Si 10×10×0.02 mm，点源 (0,0,−3) mm、方向 (0,0,1)，1 um cut，
  1 线程，每例 2000 事件，种子 20261211 / 20261212（运行前已在冻结文件固定）。

## 2. 交付文件

| 文件 | sha256（前缀） | 字节 |
| --- | --- | --- |
| `README.md` | `7321d15cbedbdebb…` | 7648 |
| `identity.json` | `ef7923fef44d17ca…` | 3056 |
| `reference.py` | `518da5b50e9fa506…` | 7825 |
| `reference-recompute.json` | `830f9f04750026f8…` | 1850 |
| `setup_inputs.py` | `e02308e109073376…` | 8374 |
| `run_cases.py` | `3df7e883eaa55442…` | 5240 |
| `compare.py` | `c958ae35f888f1ec…` | 19129 |
| `tamper.py` | `95ba52553bd0d9d0…` | 4862 |
| `results.json` | `760a509808804004…` | 47206 |
| `tamper-results.json` | `a9c5c4b27dbe2dc0…` | 1046 |
| `backend-data-check.txt` | `ec86b695aebaa3a7…` | 2240 |
| `inputs/main_ref_let_10.ini` | `79b127b791adc23b…` | 833 |
| `inputs/main_ref_let_100.ini` | `a3fde5a07b9d9844…` | 836 |
| `inputs/geometry_let.ini` | `3802c956bccab42f…` | 220 |
| `inputs/materials.ini` | `fb05cfd6f448f128…` | 67 |

运行产物在 `runs/ref_let_10/`、`runs/ref_let_100/`（`run.mac`、`backend.log`、`record.json`
与 `output/` 的原始产物）；原始输出与日志保留，未复制覆盖。

## 3. 参考重算（独立于冻结值）

`reference.py` 从 PSTAR_Si 原始字节重算（先校验 sha256、解析 132 行），
两例 E_mid/LET 与冻结值逐位一致：10.0 MeV: mid_delta=0.0, let_delta=0.0；100.0 MeV: mid_delta=0.0, let_delta=0.0。结果在 `reference-recompute.json`；
偏差时 `--check` 非零退出。

## 4. 执行与门禁

两例均用冻结后端真实运行：`exit=0`、`completed_events=2000`（约 1.4 s / 1.1 s）。
`results.json` 共 **116 项检查，0 项失败**：

- `EVID-*`: 64 项，全部通过；
- `ID-*`: 12 项，全部通过；
- `MOM-*`: 8 项，全部通过；
- `REF-*`: 8 项，全部通过；
- `STAT-*`: 24 项，全部通过；

比较器的失败语义与后端退出分开：本交付逐例记录后端真实退出码
`{'ref_let_10': 0, 'ref_let_100': 0}`，并在 `results.json` 写
`comparison_exit_is_not_backend_exit=true`；比较驱动 exit 1 表示参考/身份比较失败，
不表示后端崩溃。

## 5. 结果（主判据与辅助判据分开）

### 主判据 `REF-LET-T-ABS`：`|LET_t − LET_ref| ≤ 0.015·LET_ref + 3σ`

| 能量 | LET_t | 绝对差 | 允许值 | 相对差 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 10 MeV | 8.10111615849 | -0.006395292 | 0.122129069 | -7.888108e-04 | **pass** |
| 100 MeV | 1.36016812632 | 0.000244857 | 0.020408642 | 1.800521e-04 | **pass** |

### 辅助判据 `REF-LET-D-GE-T` + `REF-LET-D-REL (≤0.05)`

| 能量 | LET_d | LET_d−LET_t | 相对差 | 结论 |
| --- | --- | --- | --- | --- |
| 10 MeV | 8.10123277098 | 1.166125e-04 | 1.439462e-05 | **pass** |
| 100 MeV | 1.36016814997 | 2.365000e-08 | 1.738756e-08 | **pass** |

### 两个比值的 δ 方法误差（由公开矩独立重算）

| 能量 | σ(LET_t) | σ(LET_d) | rel_error(LET_t) | rel_error(LET_d) |
| --- | --- | --- | --- | --- |
| 10 MeV | 1.721325e-04 | 1.728446e-04 | 2.124800e-05 | 2.133559e-05 |
| 100 MeV | 3.264284e-06 | 3.266974e-06 | 2.399912e-06 | 2.401890e-06 |

**整体结论：两例的全部原判据通过；`evaluation.status = pass`。**
该结论只在仅电磁 option4 的受限适用域内成立，见 §7。

## 6. 负例

`tamper.py` 在拷贝上构造 3 个有限反例，全部检出
（3/3），原件、输入与冻结文件未被修改：

- `REF-NUMERIC-SHIFT`: copy of the frozen reference with 10 MeV LET +6% → 预期 REF-LET-T-ABS，exit 1。
- `REF-SOURCE-MAPPING`: copy of results where the 10 MeV case claims the 100 MeV energy → 预期 REF-LET-T-ABS，exit 1。
- `REF-DATA-SHA`: copy of PSTAR_Si.txt with one stopping-power digit changed → 预期 data_sha256 mismatch，exit 1。

## 7. 解释边界与未通过范围

1. **v1 失败保留**：v1 的 `REF-LET-D-REL=0.2106` 仍是失败，v2 不覆盖、不重分类、不把 v1
   称为通过；v1 冻结材料与原始输出继续保留在 `out/collab/q2-reference-let-v1/`。
2. **只适用于仅电磁**：v2 通过不能给强子混合谱 `LET_d` 背书；完整强子病例的适用范围限制
   继续保留，Q2-3 的最终判定仍由主审结合 v1/v2 做出。
3. **不能用无协方差的独立 z 宣布差值通过**：两个 LET 比值相关，本交付没有完整协方差，
   因此不使用独立 σ 的 z 值作为判据，也不声称“差值显著为零”。5% 辅助判据是冻结规则；
   本次两点估计本身远低于 5%，按规则通过。
4. **次级尾部原因未证实**：v1 的“少数高 LET 步骤/次级主导”仍是待检验假设；v2 的通过
   与该假设相容（EM-only 下按构造几乎无强子次级），但不构成证明。
5. 未新增 scorer 字段、未做初级过滤、未改 cut/N/种子/参考/容差；比较器为独立实现，
   不调用产品内部结论。
6. 范围外：其它能量/材料、MT、GUI、强子混合谱、统计覆盖设计（Q2-4 方向）。

## 8. 复现

```bash
python -B out/collab/q2-reference-let-v2/setup_inputs.py
python -B out/collab/q2-reference-let-v2/reference.py --check
python -B out/collab/q2-reference-let-v2/run_cases.py     # 期望 exit 0（两例 pass）
python -B out/collab/q2-reference-let-v2/tamper.py        # 期望 3/3
```

`results.json` 含完整检查列表、逐例原始/重算矩、统计与后端退出码；`identity.json` 含后端、
数据、冻结文件、输入与 Geant4 数据检查的身份；README 在
`out/collab/q2-reference-let-v2/README.md`。

## 9. 限制与停止声明

- 单平台（Windows）、单线程、冻结两例（10/100 MeV，Si 20 µm，仅电磁 option4）、各 2000 事件。
- 作者自测不是独立复验；交付完成后本目录停止写入，等待主审独立复跑、签收与 Q2-3 判定。
- 若主审要求不同判据/参考/适用域，必须以新的预运行冻结实验处理，不得回改本候选。
