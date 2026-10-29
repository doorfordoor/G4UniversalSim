# 配置 schema（E2 / E6）

`schema/config_schema.json` 统一描述本次迁移范围内的配置字段。它生成 C++ 已知键登记表、GUI 字段描述、支持矩阵第 5 节以及逐字段覆盖清单 `schema/config_schema_coverage.json`。生成文件不得手改。

## 范围

- 主 INI：run/general/output、source 与命名源、phase_space、physics（含 MicroElec、cuts、区域和放射性衰变）、scoring（含 Edep、LET、DDD、网格及 quantity）、geometry/materials 文件引用。
- 独立材料 INI：global、nist、isotope、element、material 和旧材料别名。
- 独立几何 INI：hierarchical（含布尔工具）、simple_box、layered_device、array、shielding、GDML。各模板单独登记，不能用所有字段的并集接受任意模板。
- E6 补齐 field、field.<name>、biasing、legacy biasing.xs、biasing.xs.<particle>.<process>，并登记 `[general]/schema_version`；合计 394 个字段。静态/动态已知键和 FieldConfig 闭合键表由 schema 生成，专用上下文校验保留。macro、CLI、GDML 内容、STL 内容、NIEL/能谱文件格式不因此成为通用 schema 解释器的一部分。

## 描述与执行的边界

`migrated` 表示字段登记与描述已进入统一来源，不表示后端解析器被替换。默认值、对象构建和输运继续由后端实现决定；E2 不重新定义物理模型、计分量或配置优先级。

`independent=true` 的启动字段可以在独立 section 中检查。其他字段记录 `parser`、`validation`、`rules`、`tests` 和 `gui`；这些属性按 section 继承，字段可以覆盖。`default=null` 表示没有单一固定默认值（可能依赖预设、其他字段、必需条件或引擎），不是“随便填空值”。显式空值与字段缺失仍有区别。

标量类型有 int/bool/enum/string/energy/length/time/angle/number/existing_file。长度默认 mm、能量默认 MeV、角度默认 rad、时间默认 ns。枚举默认不区分大小写，`case_sensitive=true` 用于 STL 单位等区分大小写的字段。单位大小写、非有限数和换算溢出按 UnitParser 处理。路径字段记录 `path_base`；主 INI 的 geometry/materials 引用相对进程工作目录，高级源和 NIEL 引用相对主 INI，STL/GDML/copies 引用相对几何 INI。

`structured` 用于向量、组分、分布、实体参数及其他依赖上下文的语法。GUI 的 `check_value()` 对它明确要求上下文校验，不会把未知语法当成合法字符串。跨字段规则仍由已有专用校验器执行，并在 schema 中记录约束与入口；例如：

- 源位置/形状与字段匹配，能谱参数互斥，isotropic/direction 冲突，rot1/rot2 成对且非平行，多源与旧源配置互斥。
- 直方图 max>min、DDD 必需 NIEL 表、Dose/Fluence/DDD 依赖默认计分器。
- 区域名称、材料依赖、几何母子结构、实体参数数量、replica 填充尺寸、parameterised 副本文件与版本 2 的重复声明。

`--inspect-run` 只能验证配置与宏预检。离子/confine/相空间粒子准备、参考物理列表实际初始化、网格 scorer 命令、GDML 世界构建以及真实输运/输出须运行对应专项。覆盖清单是“字段→解析入口/阶段/GUI状态/回归”的导航，不是逐字段物理验证证明。

## 兼容行为

- E6 的主 INI / 几何 / 项目版本和迁移副本规则见 [配置兼容与迁移](配置兼容与迁移.md)。主 INI 缺失版本保持旧行为；未来版本拒绝，独立几何不使用主版本规则。场/偏置描述不开放新 GUI 编辑器；默认精度、局部场绑定、dormant 偏置和 process 大小写保持专用解析器语义。

- `source.z` 是历史已知但未消费字段，会警告；它不是 center 的别名。命名源保留原先解析器接受、诊断键表不登记的差异。
- hierarchical 的 dx/dy/dz/theta/phi/alpha 字段保留原解析与诊断登记差异。`recognition=parser_only` 明确记录，不借 E2 改变 version 1/2 的警告或拒绝行为。
- 材料温度/压力继续专用报错，旧 `type=material` 兼容但不重新生成。几何元数据仍保存在原 userProperties，不能被已知键迁移丢弃。
- GUI 继续只生成已开放子集。高级源、离子、区域物理、LET 等字段被描述不等于新编辑器已开放。元素/同位素保持原文保留策略，外部文件复制与不可无损回写阻断不变。
- GUI 不再生成后端从未消费的 `[physics]/mode=reference`；参考模式仍由 `reference` 字段选择。旧文件仍按原行为解析/警告，没有新增后端兼容拒绝。
- GUI 对已经生成的源长度/能量、物理 cut、直方图边界复用标量 schema；不合法单位、换算溢出及 max<=min 在生成前提示。这些是提前暴露后端已存在的约束。

## 更新与验收

1. 先核对后端实现。字段、别名、默认、范围、组合关系或校验阶段改变时，修改 schema 及对应回归。
2. 运行 `gui/.venv/Scripts/python.exe -B scripts/generate_config_schema.py`；`--check` 检查四个生成产物是否同步。
3. `scripts/test_config_schema.py` 验证独立启动标量、默认/别名优先级、GUI 接入和完整上下文用例。`scripts/test_config_schema_context.py` 可用 `--baseline <迁移前后端> --probe-scalars` 对照同一批配置的接受结果、诊断和 inspected configuration。
4. 运行 E1 GUI/后端一致性、GPS/A5/A6/计分专项和整套 `scripts/run_m0_tests.py --profile all --require-tracked-sources`。必须分别确认源码指纹、tracked_source_gate、pass/fail/skip；不能只凭退出码或 GUI 预览判定。

本阶段的实际执行记录见 [E2接续检查点.md](E2接续检查点.md)。安装包需另行重建验收，本阶段源码测试不会自动更新既有安装包。
