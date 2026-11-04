# Q2-4 统计不确定度预注册 v1（草案，R1 精度边界修订）

- 日期：2026-11-05
- 任务：`q2-uncertainty-preregister-v1-20261105`
- 状态：**draft**，`execution_authorized=false`；未编译、未运行 Geant4，未提交 Git。等待独立复验与冻结。
- R1：按 `docs/collab/reviews/20261105-q2-uncertainty-preregister-r1.md` 仅修订本方案的 12 位有效数字半单位定义、N=1 与覆盖批次 `hits=false` 措辞，复算纯数学核验；未动生产、既有冻结参考、其它候选与阶段状态。
- R1 同轮结构化续审：合并同文件末节四项——LET_d 两平方矩分母、完整 `event_edep` 行数恰为 N、稀疏 MT 三二阶矩与“错误平均可能数值退化”、`weighted_edep_MeV` 可直接对账；仅改验证器/生成器/文案/SHA，病例、种子、N、范围不变，未运行 Geant4。

## 1. 交付物

目录 `out/collab/q2-uncertainty-proposal-v1/`：

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `proposal.json`（机器合同，7 案例） | 70625 | `bfe5e0b2378686741074ed1b6022605e03c569f5debd05003334dc3b31853905` |
| `cases.md`（本说明的人类文档） | 21164 | `833c075b95fa72a00989730b6932fb0d254681e25edfd38bdf7040bb8c2c790b` |
| `inputs_manifest.json`（17 个草案输入 SHA） | 1725 | `048bec9bd7582c2ced7ace5654056b4c20ca9c6d6db1b0d1122bcaf53f0009e4` |
| `make_inputs.py`（确定性输入生成器） | 6918 | `9b4390578560ccb9559529cff5e568b04e91a44d3b6692d8a7506758f01ad1bd` |
| `build_proposal.py`（确定性 proposal 生成器） | 42376 | `8aec4b98db7e5073cd1d9fb4a2d88ea3d0ac3206887cc18205140b1ac0085fdc` |
| `verify_coverage.py` | 13120 | `7fc7db48b7b8889ef16744130640d7d7616ad3345b1cc84cd0e0aa2bc57cfb5a` |
| `verify_coverage_results.json` | 5437 | `fc09a56999d5ea812cb089af76db0dc8585e7e0f46fe95c38bdddd097a3a141e` |
| `verify_moments.py` | 13547 | `270e253de7f941c8add805707a30de8b657f022ddbb6b62a873c7c4fd69b55ab` |
| `verify_moments_results.json` | 5276 | `b3f2131766f826ead9fa32241b0f1e398bce77ef6bfa09195f51e7d74835d0a3` |

`inputs/` 17 个草案文件 SHA 见 `inputs_manifest.json`（materials/4 个 geometry/6 个 main/6 个 macro；重跑 `make_inputs.py` 可复现，R1 未改动）。文本替换脚本保留在 `patches/`：`r1_apply.py`（`cd3241eb4ed354c3…`）、`r1_cases_md.py`（`76239b8b500cc4f6…`）、`r1b_verify_moments.py`（`fc73f1897a87e5c2…`）、`r1b_build_proposal.py`（`db35cacea11b1621…`）、`r1b_cases_md.py`（`1e1a955f74fe9b39…`），仅用于可复现记录，不参与执行。

## 2. R1：12 位有效数字半单位的更正

**缺陷**：`verify_moments.py` 原先用 `Decimal(printed).as_tuple().exponent`（打印串的小数位数）取半单位。生产者是 `std::setprecision(12)` 的 general 输出（`src/Output/OutputManager.cc:837—841`），会省略尾零，因此对 `1`、`1000` 这类打印值会把半宽从 5e-12、5e-9 放宽到 0.5，接受区间被放宽 10¹¹ 倍。

**更正**：对非零有限值 `d` 用 `h = 0.5 × 10^(floor(log10(|d|)) − 11)`（`Decimal.adjusted()`），量级边界取较宽一侧（保守）；打印的精确零按精确 0 处理，不凭空给半宽。`proposal.json` 的 `formulas.half_unit_interval` 已改为该定义，并明确传播到所有原始量、比值与矩的比较；`verify_moments.py` 新增/保留 fixture：

| 打印值 | 旧字符串法半宽 | 量级基保守半宽 | 接受区间 |
|---|---|---|---|
| `1` | 0.5 | 5e-12 | `[0.999999999995, 1.000000000005]` |
| `1000` | 0.5 | 5e-9 | `[999.999999995, 1000.000000005]` |
| `1e-9` | 5e-10 | 5e-21 | `[9.99999999995e-10, 1.000000000005e-9]` |
| `-1000` | 0.5 | 5e-9 | `[-1000.000000005, -999.999999995]` |
| `1.36016812632` | 5e-12 | 5e-12 | `[1.360168126315, 1.360168126325]` |
| `0` | 0.5 | 精确 0（不给容差） | `[0, 0]` |

旧字符串法对 `1` 得到 0.5，比量级基宽 `1.0e11` 倍（`PRECISION-OLD-STRING-RULE-REJECTED`）；`999.9999999995` 按 `%.12g` 打印为 `1000`，落在保守区间内（`PRECISION-MAGNITUDE-BOUNDARY`）。该半单位随后传播到 REF-LET-01-EM 100 MeV 的 `let_d−let_t`：单值相对半宽 `3.676e-12`，差值相对半宽 `4.228e-4`（`PRECISION-DIFFERENCE-NOT-1E12`），不改为统一 1e-12 相对门槛。

## 3. R1：两处定稿措辞

1. **UNC-N1**：`insufficient_events` 是唯一接受的状态；delta 公式在浮点下仍可能打印极小非零 `rel_error`，因此不强制字面 0，也绝不把它作为可用置信误差。合同 `N1-STATUS` 已改为该表述。
2. **UNC-COVERAGE（`hits=false`）**：覆盖批次没有逐事件路径观测；只以冻结直线路径模型的**打印矩一致性**（`K=round(track_length/0.1)`、`sum_sq=K×0.1²`、`sum=K×0.1`）做有限解析检查，不声称读到每个事件的完整路径。合同 `COV-PATH` 与 K 的 `source/semantics`、边界、`cases.md` 与回执均已同步。

## 3b. R1 结构化续审：四处更正

1. **LET_d 两平方矩分母**：`let_t=B/A`（A=Σwl、B=ΣwSl）、`let_d=C/B`（C=ΣwS2l）。正确式 `R_d² = sum_sq_wS2l/C² + sum_sq_wSl/B² − 2·AC/(B·C)`（顶层通式本身无误，错误在逐病例/生成器/文案把两个平方矩的分母写反）。`verify_moments.py` 增加不对称 fixture B=[1,2,4]（Σ=7）、C=[5,1,2]（Σ=8）：交换分母得 `R_d²=0.404655612245`，正确值 `0.361607142857`（相差 11.905%），因此该反例可检出分母写反；对称示例不会掩盖。
2. **`event_edep` 行数 = N**：完整合法文件的每事件一行就是 N，不能用“行数”本身证明检出。N 必须来自 summary/metadata；拒绝的是“用非零贡献 entries 或普通 hits 行数替代完整 N”，以及缺行/重复行的不完整文件（`TOT-NOT-HITS-ROWS`、`TOT-EVENT-ROWS`）。同值合法文件的情形不声称可检出，反例改用缺行/重复行副本或组件 fixture。
3. **稀疏 MT 合并**：必须合并三个二阶矩 `sum_sq_wl`、`sum_sq_wSl`、`sum_sq_wS2l` 后再算两条 delta 误差，不能平均各 worker 误差；但实际分配下“错误平均”可能与合并值数值退化相同（N=2 可能落同一 worker），`MT-NO-WORKER-AVERAGE` 只记录两者，不强制本次分配暴露差异；可区分性由预先指定的“两个非空 worker、误差不同”的组件/副本 fixture 证明。
4. **加权对账**：`event_edep` 的 `weighted_edep_MeV` 可直接与 weighted dose 对账，不需要逐步 weight 列，也不要求先证明全部权重为 1；`TOT-EDEP-EQ-DOSE` / `MT-EDEP-MERGE` 已按此改写。另：`ratio_delta` 的措辞由“unweighted per-event moments”改为“每事件加权 tally 的矩”。

## 4. 预审意见的落实（续）

`docs/collab/reviews/20261105-q2-uncertainty-preregister-review.md` 七点仍全部成立：确定性几何/点源（非概率全零）、`insufficient_events` 优先、geantino+proton 过滤、真实 `HistoryStatistics.cc` 组件证据、N=2<threads=4 全局事件 ID 合并、半单位区间（不统一 1e-12）、64 批固定种子与停止条件。R1 仅修正第 4 项中半单位的具体定义和第 5/6 项的措辞。

## 5. 纯数学核验结果（R1 复算）

- `python -B verify_coverage.py`：**19/19 pass**（约 1.4 s），结果 JSON 与 R1 前一致（未改动）。复现 p=25/36、单批覆盖 K `[1347,1429]`、覆盖概率 `0.9559137115315595`、覆盖数下限 57 及 `P(C<57)=0.006980515324`、总 K 中央 99% `[88464,89313]`、联合误拒上界 `0.01698…`；含精确有理归一化与整数-浮点判据等价性。
- `python -B verify_moments.py`：**22/22 pass**。含 R1 新增的量级基 fixture、精确零、量级边界、旧字符串法拒绝，以及结构化续审新增的 LET_d 分母顺序（不对称 fixture）与原有符号稳健、Bernoulli 矩恒等式。

两程序均为纯数学/恒等式，不调用后端、不读取运行输出、不据结果调整阈值；结果 JSON 已冻结。

## 6. 七个案例（合同摘要）

| 案例 | 目的 | 关键输入/数据 | 关键判据 |
|---|---|---|---|
| UNC-TOT | 事件内合并与零贡献 | REF-Dose 10 MeV 单敏感体、N=20、seed 20261120、dose+event_edep | 20 行 event_edep 与 eventID 对应；Σraw/Σweighted↔dose 两条恒等（`weighted_edep_MeV` 直接可用）；S/S²/R 与公开矩一致；entries=非零事件数；N 来自 summary（完整文件行数即 N，不作独立检出依据） |
| UNC-N1 | N<2 | 10×10×2 mm Si 内点源、N=1、seed 20261121、dose+LET | dose/LET 行存在非零、n_events=1、状态 `insufficient_events`；不把微小/零 rel_error 当有效误差 |
| UNC-ZERO | 无沉积/无选中粒子 | 同几何 geantino、N=100、seed 20261122 | dose/let 仅表头；`scorer_statistics.csv` 缺失；禁止伪造 zero_total/undefined_ratio |
| UNC-LET-COV | 比值相关矩 | REF-LET 20 μm Si、100 MeV、2000 事件、seed 20261123 | let_t=B/A、let_d=C/B；`R_d²=sumSq_wS2l/C²+sumSq_wSl/B²−2AC/(B·C)`，R_t 用 BA、R_d 用 AC；无 5% 物理门槛 |
| UNC-MT-SPARSE | 稀疏多线程 | N=2、threads=4、seed 20261124 | 2 个全局事件不重复；合并三个二阶矩而非平均误差；允许空 worker 文件；记录实际分配，错误平均数值退化时不判检出，可区分性用预指定组件 fixture |
| UNC-COMPONENT | 共享实现边界 | 一次性 C++ probe 链接真实 `HistoryStatistics.cc` | 7 个状态 fixture 与冻结协方差 fixture；编译命令+源码 SHA |
| UNC-COVERAGE | 独立有限批次 | 64 批、N=2000、seeds 220001…220064、geantino 注量 | 打印矩与直线路径模型一致（`hits=false`，无逐事件路径观测）；C≥57；ΣK∈[88464,89313]；不重采样 |

`event_edep` 字段/单位已从产品代码确认：`runID,eventID,raw_edep_MeV,weighted_edep_MeV`，12 位有效数字，每事件一行（零沉积也写，`ScoringManager.cc:516`、`OutputManager.cc:832`）；`raw_edep_MeV` 为该事件正沉积分步 Σedep，未加权。

## 7. 反例与停止条件

合同预注册 8 个副本反例（删零贡献行、用非零贡献 entries/普通 hits 行数冒充完整 N（副本另含缺行/重复行）、伪造 zero_total、交叉矩置 0、平均 worker rel_error（用预指定两非空 worker 的组件/副本 fixture，不强制冻结稀疏分配暴露差异）、缺 metadata、覆盖批次换种子、kg/g 混用），必须命中 `fail`，并且原件 SHA 前后不变；本预注册没有 `limited` 基线可充数。

冻结输入未变时复用原始运行（比对冻结/后端/输入/产物 SHA 与完成事件），不因报告或比较器更新重跑同一模拟。任何失败保留原始证据、停止调参；缺证据即停；交付后停写等独立复验。

## 8. 边界与已按原授权确定的点

- 不宣称通用置信覆盖：结果只适用于本预注册的模型（12×12 mm 束、10×10×0.1 mm Galactic 靶、p=25/36、N=2000、seeds 220001…220064、Geant4 11.3.2、后端 864bc036）。
- UNC-COMPONENT 只是组件级证据；UNC-N1/UNC-ZERO 是极端统计表示验证，不评价探测器物理；不验证剂量/LET 物理正确性。
- R1 已按原授权确定的点（不改变冻结数值）：
  1. UNC-ZERO 的空 dose/let 汇总文件“仅表头 + 已登记文件”是当前生产者的表示（`DoseScorer.cc:94—114`、`LETScorer.cc:148` 起恒创建并登记）；`scorer_statistics.csv` 无 entry 时不写文件（`OutputManager.cc:290—291`）。生产者若改变该表示，按契约不匹配报告，不改产品。
  2. 候选目录内一次性 C++ probe 直接链接 `src/Scoring/HistoryStatistics.cc` 可用（无产品/测试/构建改动）。
  3. UNC-COVERAGE 保留 `em=option4`（与冻结 fluence 参考设置一致；geantino 无 EM 交互）。
  4. 覆盖批次真实不可用时保留并停止比较，不用替代批次。
- 完整 `event_edep` 文件的合法行数就是 N，因此不以“行数=N”本身作为检出依据；拒绝用 entries/hits 行数替代 N 用缺行/重复行副本或组件 fixture。
- 稀疏 MT 的实际分配可能使“错误平均”数值退化，不强制冻结分配下必然不同；可区分性只由预指定的两非空 worker 组件/副本 fixture 证明。
- `weighted_edep_MeV` 直接提供，加权恒等式不依赖逐步 weight 列或“全部权重=1”的前提。

## 9. 校验与下一步

- `python -B scripts/check_doc_links.py` 结果见下；`git status` 仅监督端既有 `M docs/ROADMAP.md` 与本回执为新增未跟踪，候选目录在 gitignore 的 `out/` 下；未改产品/测试/基准/冻结/表数据，未提交 Git。
- 复演命令（不需要后端）：
  ```
  cd out/collab/q2-uncertainty-proposal-v1
  python -B make_inputs.py
  python -B build_proposal.py
  python -B verify_coverage.py
  python -B verify_moments.py
  ```
- 下一步：独立复验通过后进入 `q2-uncertainty-execution-v1`（复制输入、运行 7 案例含 64 批、组件 probe、比较器/反例/README/回执、证据与链接校验、停写等复验）。
