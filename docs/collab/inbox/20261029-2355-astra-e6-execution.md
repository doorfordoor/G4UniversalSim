# E6 开工契约：字段补齐与配置兼容

基线：`c6bf8ad`，`roadmap/E6-config-compat`，复用 effective-config 隔离工作区。用户已启动下一完整阶段；按 ROADMAP 对应 E6，阶段内部实施、修复、复核和提交连续推进。原 DSH 工作区保持独立。

## 范围与决定

1. **field/biasing schema**：五类静态/动态 section 从真实解析器登记到统一 schema，生成 C++/Python/覆盖表/支持矩阵。保留全局场禁 volumes、局部场规则、偏置 dormant 短路、process 大小写、模块三态和运行期绑定校验。schema 不是物理验证，也不新增编辑器。
2. **主 INI 版本**：唯一标记 `[general] schema_version = 1`；缺失按兼容版本 1 解释。显式值只接受字符串 `1`，空、非法词法和未来版本在候选 reader 发布前拒绝并给 file:line。主 INI 重复声明仍后值生效并告警；不借版本策略改成全文件闭合 schema。版本规则和 EffectiveConfig 格式字段区分于 JSON 协议版本、几何版本及 GUI 项目版本。
3. **几何迁移**：当前格式保持 v2，旧文件继续兼容运行。显式迁移生成新副本；源顺序/注释/数值/单位与资源指向保持。legacy metadata 仅接受明确映射，未知字段、重复声明、目标碰撞及无法证明等价的内容拒绝，不猜测物理含义。迁移不得授予原本没有的 GUI 编辑能力。需要改变资源路径时按真实原路径重定位，不能复制到另一目录后让相对引用悄悄改变。
4. **项目迁移**：当前规范版本保持 6；明确 1–6 与缺省版本的迁移规则，兼容历史 preview/别名，分开输入版本与内存规范版本。未知或未来数据、冲突别名、重复 JSON key、非有限 JSON 数值必须拒绝。正常保存仍原子替换；“迁移副本”必须独占新文件，拒绝已有目标、同文件/链接别名；失败保持源与当前 GUI 状态。
5. **诊断及前端**：修复已发现的诊断身份去重缺口和另存失败污染路径；显示版本、改动、阻断原因及验证范围。DeepSeek 实际咨询及采纳纠偏记入 outbox。迁移成功只表示格式/已执行校验通过，不声称模拟或物理正确。

## 单写者文件清单

- Sol schema：`schema/config_schema.json`、生成器与四份生成输出、`src/Config/ConfigManager.cc`、`src/Field/FieldConfig.cc`、新增 field/biasing 专项。
- Sol migration：`core/config_migration.py`、`project_migration.py`、`geometry_migration.py`、`core/project.py`、几何 parser/editor 模型所需改动、`GeometryConfigDiagnostic.cc/.hh`、迁移底层专项。
- Sol frontend + DeepSeek：`window/project.py`、`widgets/migration_dialog.py`、`core/i18n.py`、前端专项；涉及其他窗口文件先协调。
- 主负责人：主 INI 版本 helper、`src/Core/EffectiveSimulation.cc`、版本测试、runner、文档、构建集成、独立复核与验收归档。ConfigManager 的版本候选发布由 schema 写者接入 helper，避免并发改文件。

## 验收与提交节点

内部按契约/实现、专项修复、冻结验收、证据交付提交；这些不是用户需逐项批准的子阶段。

- 旧/新/未来版本、别名、重复声明、拒绝后状态不变；迁移原件 SHA 不变，已有目标/硬链接/写入失败/源变更拒绝。
- 字段迁移对照保留的 2C 后端接受/拒绝/默认/来源和真实运行；新版本策略的预期差异独立列明。
- 当前编辑子集读取→迁移→项目保存/重载→writer→后端运行，语义相符；超出编辑能力仍阻断；重复诊断不得随刷新增长。
- 干净 Release、Windows 全量及同 v3 的 2C 基线逐项/总数门禁，实际 Linux 11.3.2/11.4.3 CI 与 M0 双平台；失败证据原样留存。
- 前端 offscreen smoke + 实际 Windows 窗口检查，记录程序化操作与截图观察的边界。
- 代码冻结后验证源码/测试/exe 身份，归档日志及严格证据门禁；正常集成与推送前复核工作区状态。

## 检查点

2026-10-29 23:55：完成基线/范围审查；三个协作审查结束，DeepSeek 一次真实设计咨询已保存。已确认主版本策略缺失、旧 preview 项目拒绝、诊断排序身份不完整、另存失败提前改路径。尚未实施、构建或验收；下一步按上述文件归属实现并交叉审查。状态登记在 STATUS/ROADMAP，详细证据后续独立归档。

2026-10-30 冻结前检查点：三块实现完成，394字段生成同步；真实后端专项4/4、其余专项6/6通过。field/biasing与保留2C二进制61项差分及独立4例相符；几何10类源/迁移副本网格与2事件、4类editor/project/writer链通过。独立审查补修了主版本误入几何、Unicode空白/分行、发布后临时清理、项目类型静默降级/preview类型比较；后两项原始5例及14组合法旧版本已由不同写者复核关闭。首轮构建中源码仍变化导致runner2项skip，报告保留，不算通过。当前源码/测试准备冻结127项，下一步干净构建、Windows全量/2C基线、真实CI。桌面锁屏已按技能停止UI操作并询问解锁；不阻塞其余验收，不冒称实窗已通过。无其他未终态本地会话。
