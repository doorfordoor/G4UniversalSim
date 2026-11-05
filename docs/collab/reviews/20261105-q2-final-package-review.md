# Q2-6 入口独立复验（2026-11-05）

DeepSeek turn81 completed，deepseek-flash/max；round98修正已落盘，执行者停写。

- 53个manifest条目/路径独立核查，存在性、给定SHA-256及尺寸全部一致；包含原产品exe、3个入口和10组病例引用。
- Dose按源码DoseScorer.cc的MeV→J、本体质量kg换算核对；run累计与每事件均值分开，LET不再除N。原定义缺质量换算已修正。
- F2四个云run及E4三个云run与原ci-runs-final/ci-accepted-runs逐项一致，均保留原SHA，不能称当前文档提交的新构建。
- git diff 864bc036..e5c3164a在src/include/gui/scripts/tools/config/schema/macros/CMakeLists中仅gui/AGENTS.md和中文快速说明为文档；无产品实现变化。因此不重跑已冻结的69次统计与32批偏置物理实验、不扩平台物理声明。
- 原factor10失败、DDD/NIEL限制与强子LET限制保留。Q2-1定义/参考/预注册范围可通过；Q2-6仍待交付候选链接门禁、提交/实际云状态和集成。
- 原始大件仍在D盘out/collab，对外仓库不包含这些原始大件；入口是本机交付索引。C盘独立原件保持。

只提交本轮入口、manifest、相关已引用偏置冻结/原失败小证据及审查记录。H8的ROADMAP未提交内容不纳入。现有push工作流可能自动运行；不另行dispatch重复批次。最终阶段关闭前核查实际CI终态并更新最终报告/阶段状态。
