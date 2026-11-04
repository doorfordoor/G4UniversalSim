# XS 偏置与 analog 病例（D 组，Q2-5 预注册草案）

本文件只作预注册设计；不运行模拟、不改产品/测试/CI。预注册口径：同一几何、源、物理列表与
截面、固定种子批次，analog（偏置关闭）与偏置批次分进程独立运行；比较加权均值、统计误差、
耗时与效率（FOM），保留异常种子与适用条件。过程级偏置的既有实现见
`scripts/test_biasing_worker_runtime.py`、`scripts/test_biasing_step_weight.py` 与
`docs/功能支持矩阵.md` 的“过程级偏置（部分支持）”。**本组不验证 importance sampling /
weight window / splitting / Russian roulette（仓库不支持）**。

## 预注册公共条件

- 几何：单层平板屏蔽 + 后置敏感体（例如 10×10×（front + shield + back）mm 的 Si/Al 层块，
  敏感体为后置 10×10×0.1 mm 薄层）；源：单能质子（100 MeV）或中子（14 MeV），
  `position_type=plane`、`shape=square`、`halfx=5 mm`、`center=0,0,-5 mm`、`direction=0,0,1`、
  `events` 按病例；物理：中子用 `QGSP_BIC_HP`，质子用 `option4`；`[scoring] dose=true`（或
  fluence=true，按病例），`[scoring.displacement]` 不参与（见下“DDD 未验证”）。
- 偏置配置：用 `[biasing]` 与既有 process-level 规则写法（以 `test/macros` 与
  `scripts/test_biasing_worker_runtime.py` 的实际配置为准，冻结时把逐字 INI 抄进 registry），
  `enabled = true`；analog 批次同文件仅 `enabled = false`（或等价关闭）。
- 种子（**16 个独立批次/组、各 200000 事件**；两组种子表不重叠）：
  analog `20261201..20261216`，biased `20261217..20261232`（一一配对，第 i 对
  analog=20261200+i、biased=20261216+i）。不得复用种子、不得按结果换种子。
- 执行顺序与计时：按配对交替执行，偶数对先 analog 后 biased、奇数对先 biased 后 analog；
  全部 32 批次在同一机器、同一构建、同一登录会话内完成，记录每批 `started_at`/`finished_at`
  （UTC）与 `run_metadata.json` 的 wall time；不在批次间改 CPU 频率策略（若无法固定，记录
  实际频率策略/负载并作为限制）。MT 批次（threads=4）单独列出，不混入 16 对统计比较。
- 采集：全部 32 批原始输出、`run_metadata.json`、`scorer_statistics*.csv`、worker 绑定/权重
  收据（偏置批次）保留；失败批次保留原件，不用新批次替换。
- 通过判据（先定，不因结果调整）：
  1. **无偏性**：`|μ_bias − μ_analog| ≤ 3·sqrt(σ_bias² + σ_analog²) + 0.005·|μ_analog|`
     （3σ + 0.5% 容差；0.5% 只为覆盖未验证的残余系统差，若复核认为过宽需在 Q2-5 前改，
     改必须发生在运行前）。
  2. **方差收益**：FOM = 1/(R²·T)（`src/Scoring/HistoryStatistics.cc` 的 `FigureOfMerit`），
     每批次记录 T（wall time）。预注册判据：2 个种子上 `FOM_bias/FOM_analog` 的几何均值的
     95% bootstrap 置信下界 > 1.0 才算“有方差收益”；否则如实报“无显著收益/更差”。
  3. **权重收据**：偏置批次必须能证明每个事件贡献使用其权重（worker 绑定、权重非 1 的
     事件比例、加权与未加权总量关系），否则该批次判 `incomplete`，不得进入均值比较。
  4. **收敛与异常**：保留每个种子的 R、N、entries；N<2、零事件、NaN/Inf、状态非
     `approximate` 的批次判失败并保留原件；不得丢弃异常种子后再报通过。
- 停止条件：批次中途失败则记录失败阶段与退出码，不再补跑同一种子（新种子须登记为新批次，
  不替换失败）。

## BIAS-01 中子在 5 cm 铝后的剂量：analog vs 偏置（无偏性，16 对批次）

- 配置：14 MeV 中子、5 cm Al 屏蔽、后置 0.1 mm Si 敏感层；`dose=true`；每批次 `events=200000`。
  偏置规则：对中子输运过程（例如 `hadElastic` 或非弹性实现所用的目标过程）提高重要性/截断；
  具体规则逐字写进 registry（以现有 `test_biasing_worker_runtime.py` 的配置为准）。
- 预注册：`threads=1`；16 对批次（analog 20261201..20261216、biased 20261217..20261232），
  配对与交替顺序见“预注册公共条件”。
- 判据（运行前固定，不因结果调整）：
  1. 逐对无偏性：`|μ_b − μ_a| ≤ 3·sqrt(σ_b²+σ_a²) + 0.005·|μ_a|`；
  2. 汇总无偏性：16 对差值 `d_i=μ_b,i−μ_a,i` 的均值 95% CI（按批次对做 t 区间，
     不按事件 bootstrap）应包含 0；若偏离超出 3σ+0.5% 则 `unbiased=false` 并如实报告；
  3. 权重收据：偏置批次每个事件贡献必须使用其权重（worker 绑定、非单位权重比例、加权与
     未加权关系）；任一批次不满足 → 该批次 `incomplete`，不进入均值比较；
  4. 失败/异常批次保留原件并报告 N/R/entries，不得丢弃异常种子后宣称通过。
- 能发现：权重丢失、偏置只对部分过程生效、事件选择偏差；不能发现：截面数据本身与实验不符。

## BIAS-02 FOM 收益与耗时（16 对批次；无收益即实际结论）

- 数据复用 BIAS-01 的 32 个批次（16 对）的 T、R、N；每批次 `FOM=1/(R²·T)`。
- 统计方法（先定，不因 CI 结果换方法/换种子）：
  1. 主判据：16 个配对 `FOM_b,i/FOM_a,i` 的几何均值的 95% 置信区间（对 16 个批次对做
     对数比值的 t 区间；`bootstrap` **不替代独立批次数**）；
  2. 辅助描述：对 16 对做 10000 次配对 bootstrap（固定 seed=20261140），仅作区间与分布的
     描述性复核，不作为主判决；
  3. 判定：区间下界 >1.0 → `has_variance_benefit=true`；下界 ≤1.0 或区间跨 1 →
     `has_variance_benefit=false`（或 `inconclusive`，二者如实报告）。
- **FOM 无收益或更差是允许的实际结论**：不得为让下界 >1 而继续挑种子、调参、换事件数或延长
  计时；若需改进，只能登记为新阶段/新批次，并在运行前另行预注册。
- 计时范围：同一机器/构建/会话；批次交替执行（见公共条件），报告中包含频率策略与
  同时段负载限制；wall time 取自后端 `run_metadata.json`，不采用外部秒表。

## BIAS-03 权重因子线性传递（实现层，算术）

- 目的：验证权重从 GPS/相空间到 Dose/Fluence 的线性传递，发现 `w` 被重复乘/遗漏。
- 输入：REF-FLU-01 的真空注量配置，1000 事件、threads=1；用相空间重放或现有权重机制构造
  `w=2` 的事件（具体机制以 `[source] phase_space_file` 实际支持为准；若权重量不可注入，则本
  例降级为 `not_executable` 并记数据需求，不得伪造）。
- 检查：`weighted_fluence = 2 × raw_fluence`（每体积、相对 1e-12）；`let_t/let_d` 因 w 在分子
  分母同时出现而对共同因子不变（允许 1e-12）；`ddd` 若启用则按 `w·l` 线性翻倍（但对 DDD 的
  偏置未验证，见下）。
- 判据：算术关系全过；任何体积出现比例偏离 1e-9 判失败。

## 明确未覆盖（缺口单列）

1. **DDD 的权重/偏置未验证**：现有 `test_biasing_step_weight.py` 未启用 displacement
   （见 `raw/scorer-facts.md` 的 double-application 表），且 DDD 的注量在薄靶极限下由几何长度
   决定，偏置不会显著改变统计误差但会影响 `NIEL(E_step)` 的抽样分布；本组不把它当作已覆盖，
   列为 Q2-5 缺口，如需覆盖须新增配置并在 Q2-5 单独预注册。
2. **importance sampling / weight window / splitting / RR**：产品不支持，见矩阵；不作为病例。
3. **analog 与偏置的“同一截面数据”条件**：只能通过同一物理列表/相同构建身份证明，
   不能证明 Geant4 内部数据文件完全一致；身份以 `--capabilities`、构建指纹与数据清单为准，
   在报告中如实说明。
4. **MT 批次**：Q2-5 首轮只做单线程；MT 偏置的 worker 绑定/权重另列为独立批次，不混入
   BIAS-01/02 的统计比较。
