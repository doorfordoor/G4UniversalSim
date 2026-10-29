# R-05 / R-06 / R-07 最小修复范围

基线：`d286577` 加 R-01/R-02 候选；代码/测试在全量回归期间冻结。以下为下一轮提案，不是已修复声明。原审查在 `5465dbd` 已给出真实反例；本分支静态确认触发路径仍在，R-05–R-07 尚未独立重跑。

## R-05：确定为缺陷（原审查复现，当前静态确认）

`gui/g4usim_gui/output/plot_data.py:328-344` 除以完成事件数却标 `/ primary`。按现有数值含义改成 per_event（相空间中的 history），不改变事件统计单位。拟新增 `normalization="total"|"per_event"` 参数；旧 Python `per_primary=True` 作为明确弃用别名保留数值行为，附诊断并输出正确的每事件标签，新旧参数冲突拒绝。未来真正 per-primary 需后端可靠粒子计数，不能猜一事件一粒子。

文件：plot_data.py、widgets/plot_panel.py、widgets/scan_page.py、core/i18n.py、plots/scans smoke 与输出/用户文档。静态检查未发现项目模型持久化该开关，实施前仍核对保存/导出路径；不机械替换场景/benchmark 内有独立契约的同名词。

验收：单/双初级粒子、不同事件粒子数不同的真实输出；Edep/Dose/Fluence 数值及绘图/导出标签；scan 相同口径；旧 API 弃用别名与冲突；缺计数明确拒绝。原始累计计分不因改标签而改变。

## R-07：确定为缺陷（原审查复现，当前静态确认）

`scripts/g4usim_io.py:125-157` 从非空 scorer 行推断全部 worker 的历史数，会遗漏零贡献 worker。保留合法显式 n_events 与同 run 元数据路径；没有可靠来源时明确 ValueError，提示提供 n_events，不输出虚假零误差。不把任意 histogram entries 当总历史数。

文件：scripts/g4usim_io.py、ROOT/statistics 专项测试、调用方必要的错误显示与输出契约。显式计数校验整数（非 bool）、非负及与可用 metadata 的冲突，不能把 4.5 截为 4；零事件语义另按空结果契约检查。

验收：一个 worker 全零、所有 worker 全零、event_edep 开/关、metadata 有/无/损坏、显式计数和两 run 隔离；同时检查总量、分母和误差。合法 metadata 的旧结果保持，不混入 V-01 公式变更。

## R-06：确定为缺陷（原审查复现，当前静态确认）

`src/Scoring/ScoringManager.cc:518-525`、`src/Scoring/EdepScorer.cc:45-78`、`src/Scoring/HistoryStatistics.cc:8,21,97` 的乘积/累加/平方和/合并可能溢出。必须先计算有限 candidate，再接受累计；不得限制成一个没有物理依据的任意最大权重、截断、置零或放宽测试。

文件：上述实现及必要头文件、OutputManager 事件/统计发布边界、必要时 AnalysisOutput、EventAction 的边界接线；Edep/统计/ROOT 测试及失败契约。`ScoringManager::ScoreHit` 的局部累加位于现有 catch 外，`EndEvent` 经 `EventAction.cc:49` 直接调用，新增 throw 前须补齐 callback 捕获、首因登记和 AbortRun，避免把无效成功变成未收尾崩溃。worker 合并也须候选整体校验后提交。

验收：普通权重 ST/MT；直接乘积溢出、有限乘积的事件/运行累加溢出、平方和溢出、worker 合并溢出；CSV/ROOT/both；非零退出、failed 摘要、首因和产物登记。失败前有限结果可保留，不能因此把整轮报告成功。真实设备故障不在注入测试结论内。

## V-01：需方法决策

当前实现符合现有误差公式契约；N/(N-1)、N<2 和比值 delta 适用范围是方法/兼容决策，不随程序修复偷偷改变。Astra 另行确定估计量与迁移方案后再给实现范围。不得通过修改误差、种子或容差让这批回归“变绿”。
