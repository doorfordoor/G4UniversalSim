# H2-2 r1 独立复验
2026-11-06。H2-2后端实现范围通过，允许推进H2-3；H2-4完整固定基准及H2-5平台/CI仍待，不宣告H2阶段关闭。

候选为D盘未提交工作树（基底e2117037），build source_fingerprint=9ebcd8808db6eb22ea7a5aafd45eb2d43366ec09305fac7cade228e0b7d0ab52；实际复核exe SHA256 fae758c430e08a54650466e627bb3e6e8693dd60accb69a90580b7d7b3c7f477。不是干净提交构建。

源码复核：filter有限性检查置于粒子短路之前；谱三类桶用ScoringNumeric::Add，配置及构造拒绝不可表示width；fluence谱unit恢复mm^-2；worker复制配置后独立构造对象，BeginRun清空数据，原scorer权重累计后交付谱；新schema识别要求精确表头，失败保留既有锁存路径。旧Histogram1D未改。

独立执行：h2VolumeScoringCheck.exe，56项检查及V9非有限采样、V10三桶溢出、V11零width全部通过exit0，日志out/collab/h2-backend/logs/independent_r1_component.log；真实后端scripts/test_h2_volume_scoring.py（单能峰、过滤边界、单位、非法配置）PASS exit0，日志independent_r1_backend.log。原r0审查/失败与日志不覆盖。上述未声称Linux、GUI、正式证据门禁或普遍物理验证。

下一项：既有配置入口、编辑覆盖、生效事实展示与可复演示例；后端本轮停写，只有实际入口阻断才作最小修复。未使用FileSha256/重复格式辅助函数等清理记后续，不设前置。