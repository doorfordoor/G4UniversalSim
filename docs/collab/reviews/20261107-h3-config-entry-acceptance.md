# H3-3 配置入口主审验收（2026-11-07）

结论：H3-3 固定范围通过。H3 整阶段未关闭，继续 H3-4 基准与 H3-5 最终验收。

## 候选与最小修复

HEAD 83c0b1399584031f82d7d1fe38443ed2d1713e4f，未提交候选。后端复用
9daf3d22a3701ddeb3fd691351f92e2b1c31038a9fe2f16367f66f329e4e4dc0，
组件 8e01532770423a2498231c5a029bce1854ce0329f628d9f3ab41e988b8a99e95，
构建源码指纹 9523b9874ebb813cca321184a10269db4c76f4a7b9cbbdcd96e262a85bab6379。
本轮 GUI 修复未重建后端，不能称新后端构建。

首交付后只改两文件：parallel_world_scope.py 删除把空 DDD 节当启用的分支，且只在
平行世界实际启用时执行组合冲突检查；既有 smoke_parallel_world_entry.py 补对应回归。
最终 SHA 分别为 fe3c9935aa5d9248e2f6e3a92f6c071ebde663b6fda538dd4b887e09a0407a4e、
49734b39e832e73385696a00ecb179678e772cbd32781c2a588cef1400b058ef。
45 项源码/示例/文档冻结于 out/collab/h3-3-independent-r3/source，清单
source-sha256.json。主审比较首交付，43 项未变、仅上述两项改变，复验后再次核对45项稳定。

## 独立复验与复用

- 主审实际执行 compileall -q gui 成功；现有四专项独立 **4 pass / 0 fail / 0 skip，523断言**。
  原报告 out/collab/h3-3-independent-r3/verification/20261107-033302-4d24dadf/report.json，
  SHA256 048d254218b17d9a7a6d0de7cc8b6285eaf5a78eb29c3beb3242a5bfa7d6f145。
- 主审六个独立配置探针：空 DDD 节、显式 DDD=false、禁用平行世界+LET 均无 errors 且
  ready_to_run/can_run=true；启用世界+LET/DDD 均拒绝；禁用世界却带 name/geometry_config
  仍拒绝。每个探针保存/重载均不改变主 INI 字节。原结果 probe-results.json 与 probe.log。
- 首交付八专项独立3281断言、schema、双示例与 K1 闭包/身份证据按原SHA复用，见
  20261107-h3-config-entry-independent-web.md 与 out/collab/h3-3-independent-r1。
  本轮只补受影响四专项，不把两个报告断言数直接相加冒充全新矩阵。
- 原合法空 DDD 节后端200/200实际运行、禁用世界+LET后端dry-run exit0证据保留。
  后者只证明配置可创建，不称新增物理验证。作者 turn103/104已completed、任务idle，
  实际配置 deepseek-account-vision/deepseek-flash/max；两次修复作者回执与原报告各自保留。

## 原失败与范围边界

首交付误拒绝证据 h3-3-independent-r1/disabled-displacement-probe；r1修复后新增禁用世界
误拒绝证据 h3-3-independent-r2/disabled-world-probe，均不覆盖。交付前两次中间自测JSON缺项
仍在CURRENT限制表登记，不补造、不用作验收依据。

本项签收 GUI/schema/external配置入口、保存与K1资源闭包及文档/示例；Generated模式保留
外部H3配置时明确提示其不参与本次输入，editable导入拒绝，不新增编辑框架；3D仅质量几何。
H3-2原运行时验收独立保留。统计物理、Linux/Windows正式矩阵、云CI及必要原生观察仍归
H3-4/H3-5，本签收不替代它们，不重开Q2/H2或扩科学适用域。
