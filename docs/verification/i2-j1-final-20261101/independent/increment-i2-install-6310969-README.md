# I2 独立小增量 — 6310969

本包收集原始小证据，不复制EXE、SDK或数据集，不修改既有manifest/ZIP。原文件不做换行/编码/路径重写；原件SHA见同名-manifest.json。内部历史绝对路径/旧out路径是当时来源，不保证迁移后存在。归档候选6310969不冒充所有原始证据的运行提交。

- `114/review.md`、`114/identity/`、`114/report/`：03d2c48正式114 integration29/29、6045 v3、严格gate0。报告及29条原始case日志可独立核SHA；产品EXE仍为5fe字节，03d只两项测试改动。native-helper-build-identity.json只存来源/散列元数据，不含SDK/helper二进制。GDML组件scope与官方114应用GDML OFF分开。
- `baseline/`：K1同v3 182项57181→本轮113四profile193项93592，无缺项/逐项下降/总量下降。10项差异与具体文件原因在review.md；4份当前报告及原基线报告保持原字节。它是比较视图，不伪称新跑193项；历史case日志在原K1/本轮正式归档，不为这份小增量重复复制193条。
- `gui-83/original-ci-failure/`：03d远端M0 Windows GUI58/59、I2用例54入口后的原始失败；不追改为通过。
- `gui-83/repro/`：同源完整smoke离屏三组。长TEMP59通过，真实C盘8.3 TEMP54失败，仅fixture根.resolve的相同短TEMP59通过。两个实际候选完整保留，只是长短路径拼写不同。所有原assert谓词/次序保留；out副本只固定ROOT、打印操作数及候选规范化单行，不冒真实tracked验收。
- `gui-83/source/`：03d原始Git blob与631 tracked源字节，分别匹配反例与target收据。
- `gui-83/tracked-target/`：631提交前的真实tracked修订target59/49、严格gate0。它的原始身份是03d HEAD+仅smoke修改的dirty快照；GIT_CONFIG core.longpaths=true，无false D。源码SHA等于631提交文件；不把旧报告改写成clean631。
- `docs/`：安装说明最终候选，仍待Root在全部门禁后应用。四事实、GDML OFF、无公共catalog自动下载承诺与host工具/资源成本边界均保留。

这份增量不宣布I2/J1阶段关闭；最新631远端CI终态与阶段身份整合由Root最终归档。没有覆盖原失败、改旧报告、重跑矩阵或改变门槛。
