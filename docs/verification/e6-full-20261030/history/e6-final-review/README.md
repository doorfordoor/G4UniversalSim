# E6 冻结范围与证据覆盖最终只读复核

审查对象：`cb837e680e08a66dd47e62a9ee7e25fa125026c3`（`roadmap/E6-config-compat`）。本轮开始及取证时 tracked 工作树干净。只读取冻结产品/正式测试/既有证据；新报告、取证脚本和门禁输出全部写在本目录。没有修改产品、正式测试或 tracked 文档，没有重跑整阶段测试，也没有重新操作 Windows UI。

**结论：E6 约定的实现范围已落入冻结代码，抽查未发现新增范围缺口；阶段验收仍未完成。** 下列“实现”判断与“现有证据”分开；不能用专项通过、文档存在或已推送宣称 E6 已完成。当前 ROADMAP 保持进行中，与此判断一致。

## 契约逐项核对

| 开工契约 | 冻结实现核对 | 已有证据与覆盖 | 仍需验收 |
| --- | --- | --- | --- |
| 五类 field/biasing schema | schema 及生成 C++/Python/覆盖表/支持矩阵同步；ConfigManager 静态/动态键表来自生成表；FieldConfig 只替换允许键集合。原 global 禁 volumes、局部场后缀/祖先规则、dormant、hIoni 大小写、默认精度、模块三态与 worker 证据保持。external_only 未变成新编辑器。 | `e6-backend-second` 的 field_biasing_schema；61例候选/2C差分记录；独立三类四例见下文。schema组件包含生成器 `--check`。 | 在冻结提交的 Windows127全量、Linux双版本及M0双平台中重新覆盖并过严格证据门禁。 |
| 主 INI 版本 | `[general]/schema_version` 精确1或缺省legacy1；候选reader验证后发布；重复声明后值生效并告警；EffectiveConfig `/configuration/main_ini_schema_version` 保留真实输入来源、未冒充内核应用。`LoadGeometryConfigBytes`独立边界已消除误入几何的缺陷。 | `main_config_version_component`、`main_config_version`，含非法词法/未来/重复/拒绝不污染/独立几何反例；`main_ini_migration`含ASCII空白、LF/CRLF与同目录复制保护。 | 冻结运行身份、全量及同代2C基线逐项/总数门禁，跨平台复验。 |
| 几何 v2 迁移 | 缺省/1继续兼容；显式迁移生成新副本。未知/重复/忽略/未来/歧义拒绝；legacy metadata只按明确映射改名，冲突与未用映射拒绝。STL/GDML/copies_file转换为原资源绝对目标。预览明确仅字段/结构/路径检查，不发完整语义或物理认证。 | `config_migration`覆盖拒绝、源哈希、资源重定位及编辑blocker；`config_migration_backend`10类源/副本网格一致及真实2事件，4类项目/writer链通过。 | 冻结全量/双版本执行；可见窗口显示与用户操作验证。GDML只在后端声明可用时实际运行，未编译GDML时只能证明格式计划而不能声称GDML运行通过。 |
| 项目格式 v6 与正常保存 | 缺省/1–6经明确已知转换进入v6内存模型；旧preview/别名转换，未知/冲突/未来/重复JSON key/非有限拒绝。构造前类型检查阻止字符串truthiness、浮点截断、null路径和字符串拆字符；preview比较类型敏感。普通保存仍同目录临时文件+fsync+原子replace；旧项目正常可编辑，不被强制只读。 | `config_migration`保留独立审查原始5例；不同写者的 `e6-independent/types-fix-review.json`确认5例均拒绝、14组合法旧格式兼容；`project_io`及几何editor相关专项。 | 冻结全量与实际Windows打开/另存/失败保留/显式打开副本操作。 |
| 副本发布安全 | 计划不改当前对象；目标必须不存在，拒绝源/已有链接别名；同目录临时写、flush/fsync，发布前重查源SHA，以os.link独占提交。竞争者先建目标不覆盖。发布后清理失败返回cleanup_warning，不误报失败或删目标。主INI强制同目录，不假设已经实现K1资源打包。 | `config_migration`含写入/链接故障、并发目标、源改变、清理失败；`main_ini_migration`含同目录/硬链接/失败路径；迁移UI smoke显示警告。 | 冻结全量及跨平台文件系统运行。不承诺断电恢复、跨文件事务、资源永久不变或设备持久化实测。 |
| 诊断与前端 | C++排序/相等用同一完整身份；GUI源诊断使用code/severity/规范路径/行/section/key/value，不以显示文案为唯一身份；重复validate/项目重载保持源问题。文件菜单迁移预览显示版本/改动/范围，副本写完不自动切换。Save As成功后才切路径。DeepSeek咨询及取舍已记录。 | `geometry_diagnostic_identity`组件，`config_migration`多次重载/不同文案身份断言；`gui_config_migration` offscreen74入口；设计记录有真实调用信息和采纳纠偏。 | 实际Windows可见窗口验收；offscreen、咨询成功与历史2C截图均不能替代。 |

## 正常 writer 与范围抽查

- 主INI writer仍输出既有可编辑子集，没有自动加入field/biasing编辑器；正常生成未写schema_version时按已契约化的legacy1读取，属于兼容行为。schema不是全文件闭合校验，未知主INI字段仍保留既有诊断规则。
- geometry writer仍只生成simple_box、layered_device、hierarchical/既有布尔子集；缺版本或显式1/2标记按模型保留。A5专有字段/placement、array/shielding等继续预览或round-trip blocker，原文复制仍需显式布尔选择。迁移成功不清除已有blocker，不解锁J2。
- package writer在blocker存在且未显式source_copy_mode时拒绝；未因E6自动打开原文件复制。正常项目save/load保持已有编辑字段及项目路径，不以保存项目覆盖输入几何/材料。
- 未发现E6开放assembly、材料temperature/pressure、新实体编辑或新偏置规则编辑；E7/J2/K1/Q2的独立范围继续保留。几何资源绝对重定位只保持引用目标，不等于可移植资源包。

## 独立 schema 新增反例抽查

`scripts/test_field_biasing_schema_review.py`已在runner登记backend/exe，四例分成三类，构成原suite之外的交叉边界：

1. 缺gate时畸形`[biasing.xs.proton.h.Ioni]`加NaN仍休眠接受；同内容加显式auto后必须进入语法解析并拒绝。
2. 全局gate打开而单条rule `enabled=false`时，NaN仍在数值读取阶段拒绝；不能把rule禁用误解成全局休眠短路。
3. 混合大小写section/key保持Coil和hIoni身份；YES/ON布尔词、`.001 cm -> .01 mm`、三项缺省精度、only_primary与apply_to_secondaries优先级均保持。

`e6-independent-schema-candidate/review.json`记录候选SHA256 `dcd96ad49c1c3756a4be4175c7182681de93979c7c5cbc354b1941d4eee2c785`及2C SHA256 `fbb7c56e820d3d36e5f87a3ef2995d55c554d4c5cb38dbaa75191422d4bc37f0`，四例通过；接受病例完整field/biasing快照差分相同。这是Configure证据，不外推transport/物理正确性。冻结前specialized报告也已执行该新case且18入口。

## 本轮证据抽核结果

机器可读摘要见 `evidence-summary.json`；本轮重新对既有报告执行官方严格门禁，没有重新生成或改写原报告：

- foundation：2pass、41入口，门禁0；属于早期身份，不是冻结全量。
- backend-second：4pass、820入口，门禁0；sourcefp与冻结相同，testsfp早于最终冻结，报告git_dirty=true，不能冒充冻结提交完整验收。
- specialized：6pass、390入口，门禁0；sourcefp/testsfp均与冻结清单相同，但仍是c6bf8ad工作区dirty时的专项，不是cb837e6 clean全量。
- backend-first：2skip、0入口，门禁按预期返回1。保留源码/可执行文件指纹不同步导致的拒绝证据，未算通过，也不作为确定产品缺陷。
- 上述存在的逐例日志原始字节SHA全部匹配。独立项目类型复核确认5个原失败载荷全部拒绝、14组合法旧格式继续兼容。

冻结清单：static19/gui33/backend55/integration20，共127；sourcefp=`ab79c6c2227518bd7f38d5109998ed0998d8fd53ad500cfbe714d544eb19a474`，testsfp=`bfdb9630eef8ee95146d95769bf83bb247afbd54e1d81f3f4fa409a3a1f57430`。

## 尚待关闭的验收事项

1. 干净Release与cb837e6运行时身份、Windows127全量、同v3保留2C基线逐例/总数门禁、零fail/skip/零断言、严格日志与指纹核验。不能仅由专项内容指纹相同替代clean全量。
2. 本次真实CI Linux11.3.2/11.4.3与M0 Windows/Ubuntu终态、4归档SHA及12报告门禁。读取时checkpoint仍in_progress：Linux run `40911355023`，M0 run `40911355092`，均对应cb837e6；后续状态以主负责人的实时收据为准。`e6-ci-script-selfcheck*`是旧证据隔离自检副本，不计本次E6平台通过。
3. **UI锁屏缺口单列：** 当前桌面锁屏，按既定技能已停止操作并请求用户解锁。它是外部验收条件，当前没有证据将其归为产品缺陷。等待解锁后完成E6可见窗口迁移预览、取消/拒绝、另存失败、显式打开副本、语言及运行链检查，并实际查看截图；不得用offscreen或2C历史实窗代替。
4. 完成上述后再汇总归档、校准状态文档与作最终阶段关闭裁决。冻结README/STATUS部分实施时态较早，但阶段仍标进行中；本轮按授权不改tracked文档。

本报告是范围/证据覆盖复核，不是完整独立产品审查，也不以本迁移实现者对自身代码的阅读代替已记录的跨写者P1/P2复核。冻结产品和正式测试未改。
