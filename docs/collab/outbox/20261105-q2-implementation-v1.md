# Q2-2 实现层四病例交付回执（v1，作者交付，待独立复验）

任务：Q2-2 IMP-DOSE-01 / IMP-FLU-01 / IMP-LET-01 / IMP-DDD-01（冻结文件
`docs/collab/decisions/20261105-q2-implementation-freeze-v1.md`，优先于 Q2-1 registry 冲突项）。
本回执只列作者实际执行的事实；产品源/后端/测试/正式基准/CI 未改，未提交 Git。

## 1. 身份与环境

- 工作区：`D:/Geant4/G4UniversalSim`，分支 `roadmap/Q2-scientific-baselines`，
  运行起点 HEAD `9ed087f22d7891bff01724dcb284d6559addd3c3`（前序 `fd93e799`）。
- 冻结后端：`out/collab/q2-backend-864bc036/G4UniversalSim.exe`，
  sha256 `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f`，2,786,304 B；
  `build_git_commit=864bc036d6d7752475e52db4efd2b950cabfcc3d`，
  `source_fingerprint=e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7`。
- Geant4：`D:/ProgramFiles/Geant4`（11.3.2），
  `--check-geant4-data` 的 `required_complete=True`；
  `--capabilities` 原文见 `out/collab/q2-implementation-v1/backend_capabilities.json`。
- 平台：Windows，1 线程全部病例；作者自测，非独立复验。

## 2. 输入（确定性生成，无随机选择）

`setup_inputs.py` 由冻结文件生成，输入 sha256 见下表；主 INI / 几何 / 材料 / 合成 NIEL 表：

- 剂量：G4_Si 10×10×2 mm、10 MeV 质子正入射、N=20000、seed 20261120；
- 注量与 DDD：10×10×0.1 mm G4_Galactic、geantino 点源 (0,0,-2) mm、N=20000、
  seed 20261121 / 20261124；合成 NIEL 恒 0.003 MeV·cm²/g（1e-12–1e6 MeV）；
- LET：G4_Si 10×10×0.02 mm、10 / 100 MeV 质子、N=2000、seed 20261122 / 20261123。

**实现选择（非冻结参数）**：IMP-DOSE-01 `default_cut = 10 mm`。1 µm cut 时 hits 增长到
9.1 GB / 约 17 分钟，停止后改 10 mm（无 δ 电子），总 150,456 行 hits；剂量归一
（Σedep/mass）不变。该选择在运行前固定，未按结果调整。

## 3. 真实运行

每例命令：`G4UniversalSim.exe --config inputs/main_imp_<case>.ini --macro runs/<case>/run.mac
--output runs/<case>/output --threads 1 --seed <冻结 seed>`；`run.mac` 仅
`/run/initialize` + `/run/beamOn N`。全部 exit 0：

| 病例 | exit | 耗时 | run_summary sha256 前缀 | 时间（UTC） |
| --- | --- | --- | --- | --- |
| IMP-DOSE-01 | 0 | 5.16 s | 8fea13a89646e26e… | 2026-11-04T18:49:06Z → 2026-11-04T18:49:11Z |
| IMP-FLU-01 | 0 | 1.86 s | 080a745d4582302c… | 2026-11-04T18:49:11Z → 2026-11-04T18:49:13Z |
| IMP-LET-01-10MeV | 0 | 1.77 s | ef14aee1abc3ab50… | 2026-11-04T18:49:13Z → 2026-11-04T18:49:15Z |
| IMP-LET-01-100MeV | 0 | 1.53 s | adf9d6a2ea543e38… | 2026-11-04T18:49:15Z → 2026-11-04T18:49:16Z |
| IMP-DDD-01 | 0 | 1.71 s | 5eecdb580c9447cd… | 2026-11-04T18:49:16Z → 2026-11-04T18:49:18Z |

实际完成事件：IMP-DOSE-01 20000/20000、IMP-FLU-01 20000/20000、
IMP-LET-01 2×2000/2000、IMP-DDD-01 20000/20000（来自 run_summary/run_metadata，
非退出码推断）。原始输出、backend.log、record.json 在 `runs/<case>/`。

## 4. 独立比较器结果

比较器 `comparator.py` 不复刻 scorer 公式：剂量用 hits + event_edep 两条独立链与
解析质量（200 mm³ × 2.33 g/cm³）；注量/DDD 用几何长度与体积；LET 用公开矩列重算
`let_t`/`let_d` 与 delta 误差。12 位有效数字区间 + 1e-6 算术门；delta 方差的三项
~5e-4 相消到 ~4e-10，故 R 的区间把方差区间传过 sqrt 并加机器项（见 §6 修正记录）。

| 病例 | 状态 | 检查数 | 失败 | 实际事件 |
| --- | --- | --- | --- | --- |
| IMP-DOSE-01 | pass | 47 | 0 | 20000 |
| IMP-FLU-01 | pass | 38 | 0 | 20000 |
| IMP-LET-01-10MeV | pass | 37 | 0 | 2000 |
| IMP-LET-01-100MeV | pass | 37 | 0 | 2000 |
| IMP-DDD-01 | pass | 42 | 0 | 20000 |

关键重算值：Dose = Σedep×1.602176634e-13 J / 4.66e-4 kg = **6.87420705284e-05 Gy**（与
报告 12 位一致）；Fluence = 2000 mm / 10 mm³ = **200 mm⁻²**；LET 10 MeV `let_t` =
**8.10102792672**、`let_d` = **8.10114300199**，100 MeV = **1.3603544191** / **1.36048023323**；
DDD = 2000×0.003×100/10 = **60 MeV/g**。逐检查 reported/recomputed/区间见
`results.json`（5 例，201 checks，overall pass）。

**运行证据校验（修复 R1 新增，强制）**：每个病例在算术结论旁强制校验实际运行证据——
`run_summary.txt` 存在且可解析，`status=completed`、`summary_write_status=completed`、
`output_failure_status=none`、`macro_execution_status=completed`、`simulation_executed=true`、
`program_exit_code=0`；`run_count=1` 且 `run_0_planned/completed_events`、
`planned_event_count`、`actual_completed_event_count` 均等于冻结 N；
`run_metadata.json` 的 `runs` 恰一条且 planned=completed=N；被比较每个 CSV 都在
`generated_files` 声明、`integrity_status=hashed`、`size_bytes`/`sha256` 与磁盘一致；
`scorer_statistics` 每行 `n_events` 等于冻结 N。失败以 `EVID-*` 明确列出；比较器自身
异常记为 `EVID-COMPARATOR-EXCEPTION` 并仍写出结果。独立复验反例（仅删 FLU 的
run_summary/run_metadata）复现见 `review-counterexample/`：exit 1、19 项 fail。

## 5. 篡改反例（27/27 检出）

对产物**拷贝**施加单点篡改（不改原件）。算术族 15 个：质量×2、剂量单位×1000、
删剂量列、事件截断、缺 hits、体积减半、注量单位×10、删 n_events、LET 交叉矩×1.01、
LET 值×1.01、删 LET 矩列、DDD 体积因子、DDD 值×10、改合成 NIEL 表、删越界列；
副本中刷新对应 `generated_files` 的 sha256/size，使 SHA 校验通过而仅算术失败。
证据族 12 个：删/损坏摘要与 metadata、两者都删、失败摘要、零/少完成事件、
资产未声明、资产字节不符、陈旧串包产物、错误退出码。

| 篡改 | 期望检查 | 结果 |
| --- | --- | --- |
| dose-mass-double | DOSE-MASS | detected |
| dose-unit-x1000 | DOSE-VALUE-HITS | detected |
| dose-missing-column | DOSE-SUMMARY-COLUMNS | detected |
| dose-missing-events | DOSE-EDEP-EVENTS | detected |
| dose-missing-hits | EVID-ASSET-FILE-hits_t0.csv | detected |
| fluence-volume-factor | FLU-VOLUME | detected |
| fluence-unit-x10 | FLU-FLUENCE | detected |
| fluence-missing-column | FLU-SUMMARY-COLUMNS | detected |
| let-cross-moment | IMP-LET-01-10MeV-LET_T-REL | detected |
| let-value | IMP-LET-01-10MeV-LET-T | detected |
| let-missing-column | IMP-LET-01-10MeV-SUMMARY-COLUMNS | detected |
| ddd-volume-factor | DDD-VOLUME | detected |
| ddd-value-unit | DDD-VALUE | detected |
| ddd-table-modified | DDD-TABLE-SHA | detected |
| ddd-missing-column | DDD-SUMMARY-COLUMNS | detected |
| evidence-missing-summary | EVID-SUMMARY-FILE | detected |
| evidence-missing-metadata | EVID-METADATA-FILE | detected |
| evidence-failed-summary | EVID-SUMMARY-STATUS | detected |
| evidence-zero-events | EVID-METADATA-RUNS | detected |
| evidence-fewer-events | EVID-COMPLETED-TOTAL | detected |
| evidence-corrupt-summary | EVID-SUMMARY-PARSE | detected |
| evidence-corrupt-metadata | EVID-METADATA-PARSE | detected |
| evidence-asset-not-declared | EVID-ASSET-DECLARED-event_edep_t0.csv | detected |
| evidence-asset-sha-mismatch | EVID-ASSET-SHA-hits_t0.csv | detected |
| evidence-stale-product | FLU-SUMMARY-COLUMNS | detected |
| evidence-missing-both | EVID-SUMMARY-FILE | detected |
| evidence-wrong-exit | EVID-PROGRAM-EXIT | detected |

比较器对每个拷贝均返回 fail 且命中预期检查 id；明细 `tamper-results.json`。

## 6. 作者侧自身错误与修正（保留记录）

1. IMP-DOSE-01 首跑 1 µm cut：hits 9.1 GB、预计约 17 分钟，磁盘/时间不可接受；停止
   （未进入证据），改 10 mm cut 重跑并通过。属输入取舍，不是物理结果问题。
2. 比较器初版将 `sqrt(方差)` 的区间丢失，let_t/let_d delta 误差被误判失败（相对差约 1e-7）；
   修正为方差区间过 sqrt + 机器项后通过。属比较器自身错误，物理输入/容差未改。

## 7. 限制（与结论一起阅读）

- 仅实现算术：单位/质量/体积因子、矩与表身份；不验证物理正确性、截面、NIEL 模型、
  统计覆盖率，不替代 Q2-3/4/5。
- IMP-DOSE-01 的 10 mm cut 无 δ 电子；总沉积能/质量归一不变，但不能外推其它 cut。
- IMP-LET-01 只验比值与 delta 误差的输出/算法；绝对阻止本领归 Q2-3。
- IMP-DDD-01 的合成常数表只验单位/体积因子，不验证真实 NIEL 数据。
- 全部 1 线程、Windows、作者自测；跨平台/MT/GUI 入口不在本任务。
- 运行证据校验依赖当前 run_summary/run_metadata 协议；旧格式产物会以 EVID-* 失败，
  这是有意门禁；证据校验只证明“本次运行完成并产生被比较字节”，不补足物理验证。

## 8. 复跑命令

```bash
python out/collab/q2-implementation-v1/setup_inputs.py
python out/collab/q2-implementation-v1/run_cases.py
python out/collab/q2-implementation-v1/comparator.py     # overall pass (201 checks)
python out/collab/q2-implementation-v1/tamper.py         # 27/27 detected
```

需要 `PATH` 前置 `D:/ProgramFiles/Geant4/bin` 且
`GEANT4_DATA_DIR=D:/ProgramFiles/Geant4/share/Geant4/data`。

## 9. 文件与哈希

| 文件 | sha256 | 字节 |
| --- | --- | --- |
| `setup_inputs.py` | 4d650b2424e0ed1e1e20167650b82bee45363ae58bbd9cf7d14c9bf3c75da6ea | 6532 |
| `run_cases.py` | bd4b6d604698e40a60ce7606cdd4b05c426432eee614cb9a92739a3469dbe4b7 | 6642 |
| `comparator.py` | a9e37392df623507b1647184aab54492344cfc7ea89c0a333437945a5b2601e5 | 35886 |
| `tamper.py` | 580a2453bdd2f82a6975a85541fda67d92d7f20f8a01aa75c5afb387a633fde5 | 15765 |
| `identity.json` | 5a33199367059d85fd5e4808b80bdb079dc7a633fadf376cae8a96a83597615d | 30441 |
| `backend_capabilities.json` | 52c107db8ffebbab145c9a8ec2e3eef4c9adec8b3ace44170fc9618820e0c557 | 16610 |
| `backend_geant4_data.json` | ce037de51bd689f9353b177422ac6dc4ee477887012793987b119e378668672c | 2219 |
| `raw_runs.json` | 767e4f9a64f8018f287a96f965d2e1c06a97e1e1cb4d9f9fe4f85d523fe415e3 | 42255 |
| `results.json` | 90bb07a7d197eb3e0c3fb601982a92a69b4e31eb4626d34898c3e22f044379bd | 63276 |
| `tamper-results.json` | b79c480663702ef86c7e3e5a1985509d873bf76f6fadc95cc4157b7698c4e31f | 11459 |
| `inputs/inputs.json` | 59237dfa384116bd70f35bc8777fb4a77797f164a502cb33be05ddef3b299a59 | 445 |
| `review-counterexample/result.json` | 58fca78bab38dfd0d8455978831ad61f2c110de041a48e11f0bc634eb6915c30 | 41829 |
| `review-counterexample/stdout.log` | 34d0630b8fe4e5351819c028d0d80bf4b4edefcf2eb0bff994a847dcc8067e3e | 29833 |
| `review-counterexample/README.txt` | a5f755d51ab98d0c9a435f43d2ad4b18d1874c51875d38025e3b3af8b6b11487 | 193 |
| `inputs/geometry_dose.ini` | 7040ed8c9cb2d13f290758e00522067dfe403eae2638cc8eb937d397a5f3aba4 | 216 |
| `inputs/geometry_fluence.ini` | 17b11d2d387c5bb339781c0d22a0833a81ceea35423a4cb9675351e937e67125 | 220 |
| `inputs/geometry_let.ini` | 3802c956bccab42f19d4cfd0c098a0cb7820d0be857491a4a72bdcbbf564ce0a | 220 |
| `inputs/main_imp_ddd.ini` | 0041a94cfa5198d0a914c5d2a91f43c5a94ceae18ad0541cefa273af1f70860b | 962 |
| `inputs/main_imp_dose.ini` | 18abcc8766ebd8cb32d38c207b26cd4debd4e8c264d774fd44500f46a9b8c5dc | 811 |
| `inputs/main_imp_fluence.ini` | 80d36b8b334ab4cb636e99b2adc3c6caed985e9c644687fa10e11ca059ed1aea | 825 |
| `inputs/main_imp_let_10.ini` | 8ebd84d1d7e63677d28a4bcd54f708cf657454d0f0d200e59fde48762402109c | 849 |
| `inputs/main_imp_let_100.ini` | 6dee036fcb39a45cfafba52ac0a85b0e2c08ba9eac1e86f59f302cf78e8e4925 | 852 |
| `inputs/materials.ini` | fb05cfd6f448f12805a15c3b423cb16889fc34e64bbbc1a1a7bce45a6d0ef858 | 67 |
| `inputs/niel_constant_0p003.csv` | bbf159bc16506fcff8d40e2d6f56f176e1ab62b3f792402a2bdbdf7c990ea89a | 134 |
| `README.md` | 1d5a5a4ceb6de9ca5b67d96544b8432299435dea240dc6c8fb8ba8f4f3428ae1 | 11390 |

（`runs/**` 为真实运行产物：每例 output/、backend.log、record.json、run.mac；`tampered/**`
为可删除的篡改拷贝。全部未提交 Git。）

## 10. 停止声明

四例和反例已完成，作者停写等待独立复验；未运行其它未冻结的外部参考/统计/偏置，未扩工具，
未提交 Git。需要先冻结的输入/容差变更按监督流程提案后再执行。
