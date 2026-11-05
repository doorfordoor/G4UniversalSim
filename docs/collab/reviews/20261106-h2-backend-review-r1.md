# H2-2 首候选独立审查
2026-11-06。结论：失败，需最小修复；不扩H2清单。

独立运行现有h2VolumeScoringCheck及scripts/test_h2_volume_scoring.py均exit0，日志out/collab/h2-backend/logs/independent_component.log、independent_backend.log。它们证明已覆盖的固定输入和V5接线，不覆盖下列反例。

1. include/Scoring/VolumeFilter.hh Matches：NaN/±inf的比较直接返回false，把合同要求的内部错误变为正常拒绝；DoseScorer在累计前就return，fluence亦未查kineticEnergy。应在启用filter时、粒子条件短路之前验证采样能量有限，不有限抛出并沿既有锁存失败路径传播。给真实scorer注入正沉积NaN能量，及粒子不匹配+NaN，必须失败而非header-only成功。
2. src/Scoring/VolumeSpectrum.cc：bins/underflow/overflow使用裸+=，只验证单次输入有限，不验证累计。两个1e308有限amount会产生inf并被Number写为成功数据。使用既有ScoringNumeric::Add或等价有限累计检查，所有桶同等处理，不限幅。配置min=0,max=double最小正subnormal,bins=2会让width下溢0；在构造/配置处拒绝不可表示的正有限width，避免floor(NaN/inf)转int。组件测试真实谱类验证三类桶累计溢出与零width拒绝；无需扩输运矩阵。
3. src/Scoring/FluenceScorer.cc传入谱单位mm-2，而冻结合同精确值mm^-2。只修新谱单位，不改旧fluence CSV列名；补精确字段断言。

原候选未获独立验收。修复完成复跑上述两项以及受影响定向回归；不重跑Q2/旧GUI矩阵，不补通用工具，不改阈值掩盖失败。