# Q2-3 DDD折积与NIEL表审计：运行前冻结

2026-11-05。REF-DDD-01合同为同名JSON；表级REF-DDD-02合同为20261105-q2-niel-table-audit-freeze-v1.json。两个项目分别记录结果，不把表折积通过称为数据物理评价通过。

DDD病例复用Dose冻结的几何和12×12mm束：10MeV/前层0.05mm/片0.02mm、100MeV/前层0.6mm/片0.1mm，仅电磁option4、10um cut、单线程各20000事件，种子20261113/20261114。由Dose冻结的PSTAR中点能量独立插值质子NIEL表，参考DDD/Phi分别0.009666310206360261和0.0029929239738930983MeV cm²/g。原1%容差加3倍合法标准误差不变，Phi=N/1.44cm²。实际积分按ΣwL×NIEL/V，mm^-2换成cm^-2的因子是100；不得把1cm^-2换算方向写反。

表SHA及插值节点、源几何、后端身份在JSON固定。两例应无超表能域路径；独立核对hits质子加权长度、几何体积与displacement_volume_summary的track_length_mm。公开hits只有一个动能列，没有内部使用的步前后平均动能（include/Output/OutputRecord.hh:33、include/Scoring/DoseContext.hh:33，实际使用见src/Scoring/DisplacementScorer.cc:73），因此本例不宣称逐步NIEL可完全独立恢复；常数表完整实现折积已有Q2-2证据，不新增CSV字段作前置。

REF-DDD-02只审表结构/原始SHA、95MeV·mb假设输入的单位算术、1MeV邻域两种插值。按冻结常数计算95假设输入得0.0020370061861021047MeV cm²/g；该95输入未由ASTM全文核实。中子表1MeV的log-log值0.0021583350121061676、线性值0.0021933714285714283；两算法相对差1.6233%，不能与相对假设参考值的百分点差混用。

表注释仅是来源声明。缺权威数值/模型对齐证据时，物理评价记限制，不推断差异成因，不补点、不改表、不设新的物理门槛。算术与结构项按JSON判断；所有失败保留，不调N、种子、cut、参考或容差。
