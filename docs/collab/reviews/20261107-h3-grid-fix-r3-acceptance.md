# H3-4 导航计分最小修复 r3 主审验收（2026-11-07）

结论：本次计分阻断的最小修复通过；H3-4正式统计基准与H3-5尚未完成，不关闭H3阶段。

候选程序3700e27240a06b865949b0a8a48ba2d47f2af689acc515a428c14f05096c90c3，组件34066c138f518e8533f10543759f860cd8f47a01c833bc359217a1fe2ca5c4cd，源码指纹c7de5a3c819079cd14765d89e22c4570aba54523b17ce6fa51d513f1207e4be7。20源/测试/文档文件与两程序冻结out/collab/h3-grid-fix-independent-r3；18运行时文件复验前后SHA稳定。相对H3-3仅ParallelWorld六源/头与Core内实际构造校验等7产品文件变化；未改Dose/Fluence/ScoringManager算法、原物理输入或判据。

主审实际独立执行：
- 原A2/A2f20事件、原seed20261465：raw/weighted沉积及长度四量按原12位半单位加数区间求和相交；每cell谱12桶和、N=20、质量侧proton hits独立乘权复算均通过。
- 原光子直穿2mm盒20事件总长度40mm，域外gap无ghost量；原合法2e-7mm/4x4x1微网格1-event反例获得2.00000001169e-7mm正长度，全为新真实层级路径。
- 冻结程序内置tracking独立观察到z=-20→-1e-7→+1e-7→50的真实步骤，其中目标内一步约2e-7mm；不再是旧f656的70mm单步。证据tracking-thin-grid/stdout.log，未剪切/分摊整步Edep。
- 现有parallel_world与parallel_scoring_component独立2 pass/0 fail/0 skip、2425断言；报告verification/20261107-050502-9037a74f/report.json，SHA256 0bb0b52f309d19c4dbd02584f9f960bb84cecbd1e9841d514bb09525a24c72a7。它是本次受影响专项，不替代H3-5全矩阵、严格源门禁、双平台或云CI。

代码与语义：内部导航包络只包住原grid的相同全局边界，不计scoring volume_count/参考质量，也不产生独立scorer行。cell实际全局尺寸/中心、母体/变换/copy/材质与worker SD绑定有构造校验；恢复分支使用真实PV身份与变换，正常leaf仍走旧专用路由与TLS manager，量仍来自真实ghost step，未污染质量hits/event_edep。完整路径现在包含真实包络层，每层#copy，原未发布flat路径保留其原SHA；源码与中文指南已说明。不对逐单元空间剂量分布作新增物理验证外推。

旧证据：最初20事件漏计、r1/f656与r2微网格零注量、临时trace打印精度限制、原参数变体均按原身份保留。旧9daf/8e程序的主审冻结副本仍在h3-3-independent-r1/bin，本轮已核SHA；不能因作者本轮覆盖工作目录程序就声称原副本不存在。作者turn106已completed并交付，当前原任务下一turn只处理后续事项；禁止重复trace/重复修复已签本候选。

后续立即回到H3-4原冻结基准，先补局部脚本数值停止门禁、组件真实路径、C质量端点、正有限分母及M冻结规则，再核具体manifest后运行原定批次。不得改变原输入/种子/批次数/阈值追通过。
