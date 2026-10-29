# Q1 整阶段启动与文件分工

用户已明确启动 Q1，授权完整审查、修复、验收并持续推进。启动基线 `ff18cce`，分支 `roadmap/2c-effective-config`，工作区 `C:\Users\123\.codex\worktrees\effective-config\G4UniversalSim`；原 DSH 目录只接收新的信箱通知，源码保持独立。

范围与关闭门槛仍以 [ROADMAP](../../ROADMAP.md) 的 Q1 九域和冻结平台矩阵为准。当前没有把已有 89 项通过当作本次验收。阶段内无需逐小项等待用户；新科研定义或兼容默认值改变仍须给出明确方法决策，不以修复名义静默更改。

文件责任：
- q1_geometry：R-03/R-04，DoseContext、Geometry Registry/Manager/GDML/DetectorConstruction 及几何/剂量专项；补材料/几何/SD 审查。
- q1_field：R-08/V-02，FieldSetup/必要 FieldConfig 与 field 专项；补 Source/Physics/Field/Biasing 审查。
- f6_design（复用代理，已切换任务）：R-05/R-07，plot_data/plot_panel/scan_page/i18n、g4usim_io 及相关 GUI smoke；补 GUI/后处理审查。F6 本身不重开。
- 主代理：R-06，HistoryStatistics、Edep/LET/DDD 数值累计、ScoringManager 回调失败捕获、OutputManager 统计发布；数值/统计专项、运行与输出生命周期审查；统一构建、文档、跨代理复核与集成。

R-06 细化：同一根因还存在于 LET 事件矩/协方差和 DDD 长度累计；统一先校验候选有限性再提交，线程合并整体候选失败不能半写入。保留现有统计估计量，仅避免中间乘积溢出；V-01 方法决策另记录。新增异常必须在 Geant4 回调边界锁存首因并请求停止，最终摘要非零/failed；不能任意限制合法权重、置零或输出 inf/nan。

构建由主代理统一调度；不在同一构建目录并发构建。完整回归时冻结源码与测试。各审查记录分别写入 reviews 下 q1-geometry、q1-field、q1-gui-results 与 q1-core；同一实现由另一审查者复核后才关闭。
