# V-01：现有统计误差的口径与兼容决定

判定：当前代码遵循项目已有近似公式，但“与 Geant4/MCNP 相同”的归因和小样本解释不充分；这次明确口径，不偷偷改为另一估计量。Q2 再开展独立覆盖与加权适用范围验证。

独立事件贡献为 x_i、S=Σx_i、S2=Σx_i²、N 为包含零贡献的完成事件数。现有 `R²=S2/S²−1/N` 是未作有限样本校正的事件矩近似；常见独立同分布样本均值标准误的平方比它多 `N/(N−1)`。例如 N=2、贡献 1 与 2，现有总量标准误约 0.7071，样本方差方法为 1；差异是方法口径，不应靠放宽回归容差隐藏。

已核对 [Geant4 11.3.2 G4StatDouble 官方实现](https://raw.githubusercontent.com/Geant4/geant4/v11.3.2/source/global/HEPNumerics/src/G4StatDouble.cc) 的 rms 分支，其有限样本因子和返回量不能直接等同本项目 R；移除没有依据的完全相同声明。这里不声称已检查或验证所有 MCNP 版本。

决定与文件范围：

1. 保留现有有限样本修正前的数值及累计 sum/sum_sq，R-06 只改变溢出检测和数学等价求值顺序。总量方法标识 `uncorrected_event_moments_v1`，比值方法标识 `uncorrected_delta_ratio_v1`。
2. scorer_statistics 和 mesh CSV 追加 `uncertainty_estimator`、`uncertainty_status`，版本标识升至 v2，旧列保持顺序与含义；ROOT 原始矩布局不变，由 Python 消费端从同 run N 推导相同状态。
3. 状态为 `approximate`、`insufficient_events`（N<2）、`zero_total`（零观测总量/分子）或 `undefined_ratio`（比值分母为零）。不可用状态下旧数值零只保留为兼容哨兵，不是零不确定度。消费者必须显示不可用并隐藏误差条；不得输出 NaN/Inf 冒充物理数据。旧 CSV 没有新列时按 N/estimator/value 推导保守状态。
4. 不用本轮改变模拟的事件单位、权重、初级粒子数或物理列表。LET 的 delta 误差在小样本/重尾场景依旧可能不足，不能把 `approximate` 解释为已验证覆盖率。

后端文件：HistoryStatistics.hh/.cc、OutputManager.cc、RunSummary.cc、统计/mesh 回归。GUI/IO 文件由前端代理继续独占：g4usim_io.py、plot_data.py、相关 smoke。文档同步输出契约、支持矩阵、历史约束和 CHANGELOG。

验收：N=0/1/2 与含零历史对照；总量和比值；CSV/ROOT 新旧读取一致；原 sum/sum_sq/已定义 R 数值不变；无可用证据时图形不显示零误差条；新列不会改变归一化或事件分母。完整方法验证仍归 Q2，本决定不能当作其已完成。
