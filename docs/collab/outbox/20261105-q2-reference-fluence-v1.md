# 回执：Q2-3 REF-FLU-01 单例冻结参考注量病例

- 日期：2026-11-05
- 执行：DeepSeek（Lead 执行负责人）
- 依据：`docs/collab/inbox/20261105-q2-reference-fluence-v1.md`、
  `docs/collab/decisions/20261105-q2-fluence-reference-freeze-v1.md` 与同名 JSON
- 状态：**比较通过；真实运行完成 20000 事件；有限反例 7/7 检出；原件未变**
- 写入范围：仅 `out/collab/q2-reference-fluence-v1/**` 与本文档；未修改产品、正式测试/基准、
  冻结合同、其它候选、`ROADMAP.md`/`STATUS.md`；未提交 Git。

## 1. 冻结身份（未变更）

| 项目 | 值 |
| --- | --- |
| 冻结 JSON SHA-256 | `d9ceb71f9cb6a3bcf4029010eb2bf2212c6b014dca9967b40277e01379b077b3` |
| schema / case | `q2_reference_fluence_freeze_v1` / `REF-FLU-01` |
| 后端 exe SHA-256 | `f8a8119da5d68814a14920056d85a7f30e4f8380d393ea1d439cc8ca2726820f` |
| 后端 build | `864bc036d6d7752475e52db4efd2b950cabfcc3d` |
| 后端 source fingerprint | `e7de615d4e342114104f970688a7ea5f9789f7b70240b2562a388a50a45704e7` |
| Geant4 | 11.3.2（`G4VERSION_NUMBER = 1132`），`--check-geant4-data` exit 0 / `required_complete = true` |
| 生成输入 | `inputs/geometry.ini` `cc7d1819f14627a6…`、`inputs/main.ini` `5571b5ee62461a0b…`（全文 SHA 见 `identity.json`） |

运行前先核对身份（`setup_inputs.py`），后比物理；比较器中 ID 层逐项复验。

## 2. 几何、源与独立解析参考

- 世界 3000×3000×3000 mm `G4_Galactic`；灵敏片世界子体 10×10×0.1 mm `G4_Galactic`、
  `position = 0,0,0`、`sensitive = true`、无 daughter；片体积 10 mm³、面积 100 mm²。
- 源 `plane/square/halfx = 6 mm`（方形源只写 `halfx`）、`center = 0,0,-2 mm`、
  `direction = 0,0,1`、100 MeV 质子；束面积 144 mm²。
- 解析参考（`reference.py` 从冻结几何/源直接计算，不读产品输出）：
  - `p = 100/144 = 0.6944444444444444`
  - `E[K] = 20000·p = 13888.888888888889`
  - `E[ΣL] = 20000·p·0.1 mm = 1388.888888888889 mm`
  - `E[Φ] = E[ΣL]/10 mm³ = 138.88888888888889 mm⁻²`
  - 单位权重观测标准差 `0.6514466333088097 mm⁻²`；`1 cm⁻² = 0.01 mm⁻²`
- `reference.py --check`：6 项参考量**逐项双精度相等**（绝对差 0），输出
  `reference-recompute.json`。

## 3. 真实运行事实

同一冻结后端、仅电磁 `G4EmStandardPhysics_option4` 且配置无 `reference`、0.7 mm cut、
1 线程、20000 事件、种子 20261110：

- 后端 **exit 0**，`actual_completed_event_count = 20000`，`status = completed`，
  `output_failure_status = none`，耗时 1.636 s；
- 产物：`run_summary.txt`、`run_metadata.json`、`hits_t0.csv`（13851 行）、
  `fluence_volume_summary_t0.csv`、`scorer_statistics.csv`，外加 6 个
  `effective_config_*.json`；全部 SHA 记录在 `results.json`；
- 记录状态：**复用已验证记录**（冻结 SHA、后端 SHA、输入 SHA、产物 SHA/大小、完成事件数全部
  一致，未重复模拟）；`--force` 才会重跑；
- 命令与完整路径见 `results.json.command` 与 README 第 4 节。

## 4. 比较结果（六层证据门禁之后）

`results.json.evaluation`：**status = pass，122 项检查，0 失败**。分层计数：
ID 13 / IN 20 / EVID 46 / MOM 19 / STAT 23 / REF 1。

| 量 | 数值 |
| --- | --- |
| 产品 Φ（weighted = raw） | **138.51 mm⁻²** |
| hits 独立复算 ΣL/体积 | 1385.0999999998357/10 = 138.50999999998356 mm⁻² |
| 解析期望 N/面积 | 138.88888888888889 mm⁻² |
| 绝对偏差 / 相对偏差 | 0.3788888888888948 / 0.002728 |
| σ_obs（本轮有效误差） | 0.6525710650958741（rel_error 0.00471136427042） |
| 允许误差 | 1.9578520841765115（= 1e-6·期望 + 3·σ_obs） |
| 判定 | **通过**（0.3789 ≤ 1.9579） |

- `Φ = Σ(stepLength·weight)/体积`，本病例权重恒 1；统计量为真实 N（20000，含零贡献事件），
  `rel_error = sqrt(1/K−1/N)`（K = 13851 为有命中事件数），`entries = 13851`，
  `uncertainty_estimator = uncorrected_event_moments_v1`、`uncertainty_status = approximate`；
- K 的期望（13888.8889）与 z（−0.5816）仅作诊断，**不设 K=Np 门槛**；
- 单位口径：`1 cm⁻² = 0.01 mm⁻²`；产品 `unit = mm-2`，未混用 cm⁻²；
- 实现自洽：产品 Fluence 与由 hits 按事件合并的独立重算一致（差约 1e-14），
  远小于 1e-9 相对约束与印刷精度；hits 每事件一行、步长 0.1 mm，行数不当事件总数。

## 5. 有限反例（7/7 检出，原件未变）

反例只在 `tampered/**` 副本上进行；原运行、`results.json`、冻结输入全程未改，
结束后逐个复核原件 SHA 一致（`tamper-results.json.originals_unchanged = true`）。

| 反例 | 缺陷 | 检出证据 |
| --- | --- | --- |
| `missing_metadata` | 删除 run_metadata.json | `EVID-METADATA-FILE` |
| `cm2_factor` | Φ 按 cm⁻²×100 误写 | `REF-DPHI-ABS`、`MOM-FLUENCE-RAW-DIVISION` |
| `volume_factor` | 体积因子重复（10→20 mm³） | `MOM-FLUENCE-VOLUME` |
| `reference_number` | 冻结参考 Φ 改 148.8889 | `REF-DPHI-ABS` |
| `artifact_sha` | 改 hits 产物、记录 SHA 未变 | `EVID-ASSET-SHA-hits_t0.csv` |
| `path_per_event` | 步长 0.1→0.2 并同步记录 | `MOM-PATH-PER-EVENT` |
| `completed_events` | run_summary 完成数 20000→15000 | `EVID-COMPLETED` |

## 6. 复现与文件

```bash
cd out/collab/q2-reference-fluence-v1
python -B setup_inputs.py            # 冻结/后端/数据身份 + 生成 inputs/
python -B reference.py --check       # 独立解析参考
python -B run_cases.py               # 真实运行（输入未变时复用记录）
python -B compare.py --update        # 122 项六层检查
python -B tamper.py                  # 7 个副本反例 + 原件 SHA 复核
```

候选文件清单与 SHA-256 前 16 位见 `README.md` 第 9 节（脚本、身份、参考、结果、反例、
输入、日志与全部原始输出）。`backend-data-check.txt` 保存 Geant4 数据自检输出。

## 7. 边界与非声明

- 仅电磁质子、仅均匀孔径、近似空介质（世界与片均为 `G4_Galactic`）；不验证散射材料中的
  注量、非均匀/倾斜束、剂量、NIEL 或完整强子输运。
- Fluence 是面积注量（mm⁻²），不是通量率或剂量；统计误差按本模型 Bernoulli 口径给出，
  `uncertainty_status = approximate` 如实保留。
- 本交付是单例冻结参考的**通过**结论，不是产品整体物理验收；未修改产品、正式测试/基准、
  冻结合同、其它候选、`ROADMAP.md`/`STATUS.md`，未提交 Git；等待监督端独立复验。
