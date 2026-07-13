# G4UniversalSim Agent 开发约束

本文件是仓库级约束，适用于根目录及其子目录。更具体的目录约束可以由更深层的 AGENTS.md 补充；gui/AGENTS.md 适用于 GUI 目录。

## 1. 事实来源和支持判定

- 后端实际实现是功能支持情况的唯一依据。优先检查 src/、include/、main.cc、配置解析器和可运行测试；不要根据旧文档、类名、配置字段名、GUI 控件或空接口推断功能已经支持。
- “能解析”不等于“能运行”，“能运行”不等于“物理结果已经验证”。文档必须分别说明解析、校验、运行时行为、输出和验证范围。
- 任何 stub、空函数、只注册不计算的类、占位模板、预览模型或兼容字段，都不能被描述为完整支持。
- GUI 不得展示后端尚未实现的功能；如果为了预览、规划或兼容性必须展示，必须在控件、校验消息、生成包报告和人类文档中明确标记为“预览”“实验”或“不可用”，并阻止生成可运行配置，除非后端已经提供对应实现。
- 支持等级以 docs/功能支持矩阵.md 为基线。修改后端后先更新事实，再更新 GUI 和文档；不要为了让矩阵变绿而放宽判定标准。

## 2. 新功能的完整链路

新增或修改功能时，必须同时检查并在任务说明中列出以下环节：

1. 配置解析：INI、macro、CLI 或其他入口是否真正读取字段，路径和单位如何解析。
2. 配置校验：缺失值、非法值、依赖关系、冲突和未知字段如何报错或警告。
3. 运行时实现：Geant4 对象、生命周期、线程模型、依赖和错误路径是否真正执行。
4. GUI：编辑器是否只生成后端支持的配置，预览和不可用状态是否清楚。
5. 测试：至少有与变更层级相符的解析测试、GUI smoke、后端 smoke 或物理基准；不能只测试字符串生成。
6. 文档：同步人类文档、Agent 文档、支持矩阵和必要的示例配置或 macro。

不得用空实现、占位实现或只增加开关/枚举的方式宣称功能已支持。若暂时只能完成部分链路，应保留“部分支持”或“未支持”状态，并说明缺口。

## 3. 后端维护规则

- SimulationManager、各模块 Manager、配置读取器和 Messenger 的行为必须保持一致；新增配置字段不能只加到 GUI writer 或文档。
- 配置优先级必须以代码实际行为为准。M0-1/M0-1b 已对当前启动字段统一为“默认值 < 主配置文件 < macro 运行时命令 < 显式 CLI 参数”：`SimulationCommandLineOverrides` 在 `Configure()` 后重应用显式 CLI，并由 `SimulationManager`、`OutputManager`、`GeometryManager` 阻止低优先级入口改写 `output`、`threads`、`seed`、`check_overlaps` 等字段。它是向完整 `EffectiveConfig` 迁移的过渡层，不代表已经提供来源追踪。
- M0-2 的 `run_summary.txt` 只在最终生命周期阶段写入（dry-run、正常结束、交互会话结束或失败收尾），并区分计划配置与实际运行事实：状态、每次 run、计划/完成事件数、实际线程数、配置 seed、引擎初始 seed（无法可靠取得时为 `unknown`）、macro seed 修改、最终输出目录、生成文件和失败命令位置。seed 修改只可由当前代码明确识别且成功执行的命令确认；失败摘要必须区分执行失败和 preflight 失败。preflight 没有 `ApplyCommand()` 返回码，必须用 `macro_failure_code_available=false` 表达 `macro_failure_code=0` 的语义。无法取得的运行事实必须写为 `unknown` 或 `not_executed`。
- macro 执行前必须运行静态递归 preflight：检查 `/control/execute` 引入的文件，顶层相对路径按进程工作目录解析，嵌套相对路径只能按发出命令的 macro 文件目录解析。预检生成的规范化命令序列必须直接用于实际执行；拒绝已知 CLI 冲突的项目命令、`/run/numberOfThreads`、`/random/...`，以及无法可靠分析的 `/control/alias`、`/control/loop`、`/control/foreach`。不得声称能够保护任意动态 Geant4 命令；未覆盖命令必须记录为风险或明确不支持。
- 配置字段、Geant4 命令、输出列名和项目 JSON 字段属于接口。删除、改名或改变默认值时，必须给出迁移策略和兼容性说明。
- M0-3A 对尚未完整支持的能力采用统一 fail-fast：`placement=replica|parameterised|assembly`、GDML、材料 `temperature`/`pressure`、`[physics.region.*]`、LET/Dose/Fluence 开启均必须在 Geant4 对象创建或运行前拒绝；替代方案必须出现在错误消息中。对应字段为 false 或缺失时保持兼容。
- 输出必须说明文件生成条件、线程后缀、单位/量纲、合并方式和未生成文件的正常原因。没有物理定义或数据契约的 scorer 不得输出看似有效的结果。
- Geant4 对象创建、敏感体、region、biasing、线程本地输出和 reinitialize 生命周期必须有可重复的运行验证。只在内存中保存配置不能算运行时生效。

## 4. GUI、国际化和人类文档

- GUI 只是后端能力的编辑和运行入口，不是功能定义者。后端未支持的能力不得被 GUI 默认生成或静默降级。
- 面向人类的说明文档只使用中文。代码标识符、Geant4 命令、文件名、配置 section/key、输出列名和外部 API 名称保持原样，不翻译成另一个接口。
- 每项开发完成后同步人类文档和 Agent 文档；至少检查 docs/功能支持矩阵.md、docs/开发路线图.md、相关模块说明和相关目录的 AGENTS.md 是否仍然准确。
- GUI 的 PySide6、国际化、主题、配置编辑器和生成包约束见 gui/AGENTS.md，不得在根目录规则之外另行发明一套支持口径。

## 5. 工作区和改动范围

- 不修改无关代码，不覆盖工作区已有改动。开始工作前检查 git status；对未跟踪文件、暂存内容和用户已改文件保持原样。
- 优先做小范围、可审查的修改。不要借整理文档之机重排代码、清理旧输出、修改 .gitignore 或删除示例。
- 不使用破坏性 Git 操作覆盖用户内容，例如未经明确要求不得执行 git reset --hard 或 git checkout --。

## 6. 测试和交付

- 每个任务必须运行相应测试，并在最终报告中区分“已验证”和“未验证”。文档任务至少运行链接/路径检查和受影响的 GUI 或配置 smoke；涉及后端行为时还要运行可用的构建、--help、dry-run 或后端 smoke。
- 配置优先级回归测试入口为 `python scripts/test_config_precedence.py`；M0-2 摘要回归测试入口为 `python scripts/test_run_summary.py`。涉及 M0-1/M0-1b 的改动至少覆盖配置-only、配置 macro、配置 dry-run/interactive、CLI-only、配置/CLI 冲突、macro preflight、真实 `beamOn`、无效参数、重复参数和缺失路径；涉及摘要时还必须覆盖多次 `beamOn`、失败收尾、无 run、输出目录切换和摘要写入失败。
- 测试失败时先区分代码失败、环境缺失和未覆盖场景，不得把“命令成功退出”当作物理正确性证明。
- 若真实 Geant4 可执行文件、Qt/PySide6、3D 依赖或特定工具链不可用，必须明确记录未验证部分和复现命令。
- 完成前复核 git diff、 新增文件编码、文档中的支持等级和工作区状态，确保没有把用户已有改动混入本任务。
