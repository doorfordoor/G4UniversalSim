# G4UniversalSim GUI Agent 开发约束

本文件适用于 gui/。GUI 是 PySide6 外部运行器和配置编辑器，后端 C++/Geant4 的实际实现仍是功能支持的唯一依据。

## 1. 分层和数据流

- g4usim_gui/widgets/ 负责页面、信号和用户交互；不要把后端配置语义、文件解析或大量业务校验继续堆进单个页面。
- models/、editors/ 保存可序列化的编辑状态；parsers/ 读取现有配置；validators/ 做 GUI 侧早期提示；writers/ 生成运行包；core/runner.py 只负责进程生命周期、日志和状态。
- 推荐的数据流是“源文件解析 → 编辑模型 → GUI 校验 → writer 生成运行包 → 后端再次校验/运行”。GUI 校验永远不能替代 C++ 后端校验。
- 源 materials.ini、geometry.ini 不得被编辑器直接覆盖。编辑结果写入独立 run package，并在报告中记录 copied 或 generated 来源。
- 项目 JSON schema 当前为 G4UniversalSimProject version 5。修改字段必须增加读取兼容或迁移测试，不能静默丢弃旧项目状态。

## 2. 后端能力边界

- 每个 GUI 控件必须有明确的后端映射：配置 section/key 或 macro 命令、单位、默认值、校验、writer 输出和至少一个 smoke 断言。
- 后端未实现的功能不得出现在“可运行/已支持”列表中。若需要保留设计入口，必须同时显示“预览”“实验”或“不可用”，在 validator 中阻止生成可运行配置，并在 validation report 中说明原因。
- 解析到但后端会忽略、空实现、占位模板或只用于预览的字段，不得被 writer 静默写出并宣称生效。未知字段要么原样保留并标记未编辑，要么明确提示会被丢弃后再由用户确认。
- 当前 GUI 可生成的后端子集以 writers/main_ini_writer.py、writers/geometry_ini_writer.py 和 editors/source_physics_scoring_model.py 的真实逻辑为准；不要只根据 combobox 的选项扩展支持矩阵。
- trd、trap、GDML、STL、高级 GPS 分布、手动物理模块、biasing 规则、LET/Dose/Fluence 等能力必须等后端和测试闭环后再开放生成。
- 3D 预览永远不是 Geant4 几何真值。预览不能修改后端配置语义；缺少 PyVista 或遇到不支持 shape 时应显示降级原因。

## 3. PySide6 约束

- 使用 PySide6 的信号、槽、模型和 Qt 生命周期；长时间运行的后端或合并任务不得阻塞 Qt 主线程。
- QProcess 的 stdout、stderr、退出码、终止/强制结束和日志文件必须保持可观察；不能吞掉用户需要诊断的错误。
- 页面之间通过项目模型和明确的 signal 同步，不要依赖控件当前文本作为唯一状态来源。编辑后必须更新 dirty 状态，生成包前再次从模型读取。
- 文件路径使用 pathlib.Path，生成文件统一 UTF-8 和 LF 换行；Windows 路径不得手工拼接成只适用于单一平台的字符串。
- 运行包生成失败必须保留清晰的字段/文件上下文；不要用 except Exception 把后端契约错误改写成“生成成功”。

## 4. 国际化约束

- 所有面向用户的标题、按钮、提示、校验错误、状态、日志解释和菜单文本必须使用可翻译的消息键；不得在新代码中继续散落硬编码英文或中文显示文本。
- 使用 Qt 的翻译机制（例如 QTranslator 与 QCoreApplication.translate）或项目统一封装；翻译资源、默认语言、运行时切换、持久化和缺失翻译行为必须一并设计。
- 代码标识符、Geant4 命令、INI section/key、输出列名、文件名和外部错误中的原始 token 保持原样；可以在旁边提供中文解释，但不能翻译接口本身。
- 带数值、路径、文件名和后端错误的消息必须支持参数化，不能通过字符串拼接制造不可翻译的句子。
- 当前 GUI 尚未建立完整翻译资源和 QTranslator 闭环；在此之前，新增页面应至少把用户可见文本集中管理，并在文档中标明国际化未完成。

## 5. 主题和可访问性约束

- 主题由集中式 palette/style token 管理，至少规划浅色、深色和跟随系统三种模式；业务控件不得各自硬编码背景色、文字色或状态色。
- 绿色、橙色、红色只能表达成功、警告、错误等语义，并且必须同时有文字/图标信息，不能只依赖颜色。
- 主题切换后要覆盖表格、日志、原始配置、预览、禁用控件、选中状态和错误状态；检查对比度、字体缩放和高 DPI 布局。
- 主题和语言偏好应通过统一配置持久化（例如 QSettings 封装），不能写入项目 JSON，除非它们确实属于项目复现所需状态。
- 当前工程只有零散 setStyleSheet 辅助样式，没有完整主题系统；不要把新增的局部颜色当作主题实现。

## 6. 配置编辑器约束

- 编辑器必须区分“后端支持”“GUI 可编辑”“仅预览”三种状态。状态要在控件、验证消息、原始文件/生成文件预览和中文文档中一致。
- 读取配置时保留 section/key、原始值、来源文件和未知字段信息；重新生成时不能无提示地改变单位、默认值、布尔语义、字段顺序含义或删掉用户配置。
- 材料 parser 的源 schema 错误必须与编辑语义错误分开保存；重复校验和编辑不得清空源错误，公共 errors 视图要稳定合并并去重。只要源错误仍存在，生成预览和 run package 都必须保持不可用，不能通过丢弃未知字段表现为已经修复。
- 材料独立配置文件采用后端闭合 schema；GUI writer 只能生成 `[NIST]`、`[isotope.<name>]`、`[element.<name>]`、`[material.<name>]` 和 legacy alias 的允许字段。旧包中的 `[material.<name>] type = material` 只作为已弃用兼容输入读取，新 writer 不得继续生成；其他 `type` 值或其他 section 中的 `type` 必须拒绝。未知 section/key、空动态后缀和 implicit global 字段必须阻止生成；`temperature`/`pressure` 显示为后端不可用，不得改写成可运行字段。
- 材料、几何、源、物理和计分之间的依赖必须在生成前校验：材料引用、敏感体与 hits、bias 体与 biasing、histogram 范围、源分布与后端能力等。
- writer 只生成后端实际支持的字段。布尔工具不是普通体积，不得给它写 material、sensitive、bias、region 等无效字段。
- 生成包必须能脱离 GUI 运行，报告必须列出所选输入、复制/生成方式、最终配置路径和警告；源文件永远不因“保存项目”或“生成包”而覆盖。
- project_from_dict() 和生成包快照中的兼容字段要有回归测试；修改编辑模型时同步 snapshot、writer、validator、页面绑定和 smoke。

## 7. 测试和文档

- Python 逻辑修改至少运行 python -m compileall gui 及受影响的 smoke tests；涉及 Qt 页面时优先使用 QT_QPA_PLATFORM=offscreen 的无头测试。
- 配置 writer 修改至少运行项目 IO、解析器、材料/几何/源/运行配置 smoke，并在有可执行文件时运行对应后端 package smoke。
- 只有 GUI 字符串、主题或布局修改也必须测试页面构造、状态切换和关键错误显示；截图或人工视觉检查未做时要明确报告。
- GUI 行为改变时同步 gui/docs/中文快速使用说明.md、根目录 docs/功能支持矩阵.md、docs/开发路线图.md 和本文件；面向人类的说明只使用中文。
- 不把 GUI smoke 的“生成文本正确”当作 Geant4 运行或物理结果验证；后端可执行文件未运行时必须单独标注未验证。

## 8. M0-3B2B1 几何 round-trip 保护

- 几何文档与材料文档一样，必须分开保存 `source_errors/source_warnings` 和编辑语义校验消息；重复 validate、编辑或预览不得清空源问题。
- parser 发现当前模型不能无损保存的 `cut.*`、`vis.*`、`auto_stack`、显式 placement/rotation、shape-specific 属性、userProperties 或 boolean tool properties 时，必须设置 round-trip blocker。editable writer 和 generated package 必须阻断；用户只能显式选择原始 geometry 文件复制模式，并在报告中标明编辑器验证已绕过。
- Run 不得为了通过 generated package 校验而自动打开 `source_copy_mode`。只有用户显式勾选后才可逐字节复制源 geometry；复制模式不等于编辑器验证通过。

## 9. M0-3B2B2 来源诊断对齐

- `parse_geometry(path, template_name)` 在调用方已知模板时必须优先使用显式模板，不得依赖文本启发式；源 warning、legacy metadata blocker 和 source-copy 状态必须跨重复 validate 保留。
- canonical `metadata.<非空名称>` 在可无损保存的编辑模式中不产生 blocker；legacy 无前缀属性只诊断和保留，不自动改名或删除。array/shielding 仍为 preview-only。
- metadata 编辑框只允许 `metadata.<非空名称>`。runtime 字段和旧式无前缀未知字段不得从 metadata 写出；legacy 字段本阶段只保留并阻断，不能自动改名或删除。
