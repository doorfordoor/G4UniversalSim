# H3 grid 修复 r1 独立复验（2026-11-07）

候选f65608f6c170359d84e1c909cc39d7e5206c18af5eceacbcc8f99a7ad7230488，组件3f6b3653323de0df5f49a6c2d80df17e308eaf979d605e01b77ca4edc51d6192，源码指纹15e9fa505d14e6e01d1c3448d53e8b8d923857dd71097fb1b618550881bebf0d。

主审已冻结18运行时文件与两程序到out/collab/h3-grid-fix-independent-r1；相对已验H3-3仅ParallelScoringDetector源/头、ScoringParallelWorld源改变。原A2/A2f20事件同seed20261465独立实际复演通过：四量12位半单位加数区间、每cell谱和与事件N、过滤后mass proton hits独立复算通过。常规光子20事件直穿2mm得总长度40mm，域外gap无ghost剂量/注量，均通过。

P1：ResolveOwnerStep用固定advance=1e-6mm探测方向，且每个world-pre候选都要求探测点仍在box内。对更薄的合法计分网格，探测点会越过整个box，把真实命中误判Skip。已实际反例：沿用光子真空场景，仅parallel几何改为20mm×20mm×0.0000002mm、4×4×1网格，原轴向1MeV gamma、同seed、1事件。后端接受并completed1/1、16单元已构造、exit0/stderr空，却无任何ghost fluence行（应有穿过目标的正长度）。

完整输入/stdout/stderr/摘要/CSV：out/collab/h3-grid-fix-independent-r1/domain/thin-grid；全域检查domain-results.json。不是正式B/C统计病例，不用它调整正式输入或阈值。

最小修复仅预步方向归属判断：严格内部点按pre所有权直接保留；表面点用局部坐标、面法线/方向符号及Geant4几何容差分类进入/出射/共享边界，不使用可能跨过整个单元的固定物理位移。不得通过拒绝原合法输入/增加最小厚度或修改反例厚度规避错误。保留真实PV路径、外部/gap排除及既有两项修复。

本候选不签收，H3-4继续未完成。修好以新身份复验原A2/A2f与已有负控及该反例，之后回到原冻结基准。首个2ca9中间候选在作者定稿时变化，主审身份守卫在运行前拦截，未执行物理；f656的独立结果保持其原身份，不覆盖。
