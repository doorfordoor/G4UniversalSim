# G4UniversalSim Agent 开发约束

## 网页模型临时暂停（当前有效）

2026-11-07用户明确要求：暂时暂停使用网页模型。G4UniversalSim暂停调用所有chatgpt-web/*模型（包括GPT6-sol(web)、GPT6 Pro(web)），不新建网页助手对话、不向已有网页助手发送后续指令，也不通过子代理或其它协作入口调用网页模型。恢复必须有用户新的明确指示，定时任务、阶段切换或先前授权不能自动恢复。已产生的报告与失败记录保留，按原身份复用；主审与DeepSeek原开发、自测和验收流程继续。

详见 docs/collab/decisions/20261107-web-model-pause.md。

> **状态与历史的边界（2026-11-04 E4 收尾）**：本文件只记录实现约束与工作规则。阶段完成度以 `docs/ROADMAP.md` 为准，任务级状态以 `docs/collab/CURRENT-SUPERVISION.md` 为准；下方条目中的“作者交付/未验收/未关闭”等文字是历史记录，不构成当前状态。历史全文见 `docs/agent-history.md`，归档快照见 `docs/archive/`。


Linux原生通道补充（主审已签收）：main已实际操作独立真实X11/xcb桌面，一次固定HTTP计划passed，操作观察时曾停在awaiting_approval、0事件；随后在观察期间触及300秒预算，整任务保留failed／agent.task_timeout，不称整任务成功。原host exit0、slot_released=true、host与显示服务两组remaining_owned均空、HTTP已关闭；显示辅助子进程退出码[0,1,0]（twm非零保留），不能写全部子进程exit0；代表性原生签收结果为 **独立X11/xcb代表性原生已通过，正常退出及清理完成；WSLg RAIL失败限制保留**。WSLg RAIL任务栏无法展开，第三次host退出且0请求，原失败保留，绝不称该通道成功。Ubuntu实际系统安装x11-xkb-utils，其它本次依赖保持隔离OUT前缀；具体包版本／SHA及安装收据见最终证据，不把早期准备收据system_installs=0外推到之后。

本文件是仓库级约束，适用于根目录及其子目录。更具体的目录约束可以由更深层的 AGENTS.md 补充；gui/AGENTS.md 适用于 GUI 目录。

## 0. 条目索引与历史全文
> 条目按日期保留；状态一律以 ROADMAP/CURRENT-SUPERVISION 为准，本索引不重复判定完成度。

> 索引只给主题、历史全文位置与相关文档；各阶段完成度仍以 ROADMAP 为准，
> 实现约束见下文第 1–10 节。条目全文（含行号/反例/回归）已迁入 agent-history。

- 2026-11-04 F2已验收：冻结864bc036，协议B保留csh/批处理；重放结构预检与内核初始化后/BeamOn前只读语义预检分开，禁止预检修改SourceManager。closing的steps_total计全部操作、s…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-04 J3：本轮约定范围已验收并关闭，冻结92134da0；Windows125/150与独立X11代表性、云12报告696/247580及严格门禁完成。历史图身份/非逐页八态、WSLg与约一秒切换限制保留，不外推物理…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-03 J3 独立审查响应：独立复验不同意关闭（`docs/collab/reviews/20261103-j3-closure-review.md`）；外观断言必须用 `theme.current_skin()`（无参…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-02 J3 第七阶段（作者交付，未验收）：Help 菜单的快捷键表由 `ShellMixin.shortcut_rows()` 提供、对话框由 `build_shortcut_dialog()` 构建（测试/截图用非阻…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-02 J3 第四阶段（作者交付，未验收）：`WorkspaceLayout.preset_for_page()` 按页面映射 configuration/running/analysis（0–4 / 5 / 6–8），…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-02 J3 第三阶段（作者交付，未验收）：3D 视图视点/投影控件用两行 `QGridLayout`（窄 dock 不再横向裁剪），图例 190→168、剖切滑块最小宽 80；3D 预览选项分行；配置 setup 面板…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-02 J3 第二阶段（作者交付，未验收）：侧栏 `WORKFLOW`/`RUN & ANALYZE` 分组与选中轨道、页头面包屑、Ctrl+K 命令面板（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[README.md](docs/verification/j3-theme-v1-20261102/README.md)
- 2026-11-02 L1 本轮验收与交付：阶段签收 **本轮约定范围验收完成**；冻结246e4f6，Windows六profile308/183347、CI十二原报告662/228978，Windows安装显式attempt2且原…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-l1本轮验收与交付](docs/agent-history.md#2026-11-02-l1本轮验收与交付)、[README.md](docs/verification/l1-final-20261102/README.md)
- 2026-11-02 L1 EE验收快照与原生布局后续候选：EE四本机／十二CI报告、真实云与受控恢复的限定证据分开；native150原失败保留、布局候选限定独审PASS，下一候选仍待，阶段未关闭，见[同名历史条目](docs/ag…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选](docs/agent-history.md#2026-11-02-l1-ee验收快照与原生布局后续候选)
- 2026-11-02 L1 路径显示 raw 修复候选：K1 生成包显示只回绑三条路径，不能重排非路径草稿或改变 F5/K1 资格；正常业务载入与 legacy 全量投影保持原行为。首候选失败与后续身份分开，见[同名历史条目](doc…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-l1-路径显示-raw-修复候选](docs/agent-history.md#2026-11-02-l1-路径显示-raw-修复候选)
- 2026-11-02 L1 配置 Agent 实施候选：固定白名单、同计划新授权新任务、只读恢复及待正式验收边界，见[同名历史条目](docs/agent-history.md#2026-11-02-l1-配置-agent-实施候选)…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-l1-配置-agent-实施候选](docs/agent-history.md#2026-11-02-l1-配置-agent-实施候选)、[L1配置Agent.md](docs/L1配置Agent.md)
- 2026-11-02 J2/F8与E7本轮验收：测试／构建冻结2ec5b14；15/7注册元数据、真实平台接口、限定原生及docs-only身份合同见[同名历史条目](docs/agent-history.md#2026-11-02-…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-j2f8与e7本轮验收完成测试冻结2ec5b14](docs/agent-history.md#2026-11-02-j2f8与e7本轮验收完成测试冻结2ec5b14)、[README.md](docs/verification/j2-f8-final-20261102/README.md)
- 2026-11-02 J2/F8第四修复候选：test-only接口、字节映射及未关闭边界见[同名历史条目](docs/agent-history.md#2026-11-02-j2f8-第四修复候选18c5858平台测试接口与证据映射)。（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[agent-history.md#2026-11-02-j2f8-第四修复候选18c5858平台测试接口与证据映射](docs/agent-history.md#2026-11-02-j2f8-第四修复候选18c5858平台测试接口与证据映射)
- 2026-11-02 J2/F8第三修复候选：相关专项独审已完成，完整新候选验收待进行；2901f42本机已过范围不代表CI/原生整体通过；History三显式buddy/动态语言、QLayout类型递归、K1 policy规范身份与…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-02 J2/F8候选：E7实体元数据、命名源/显式构造器替换与v8快照已接线；完整验收未关闭。修改前读 docs/agent-history.md 同日条目及 docs/J2编辑覆盖与F8验收.md，保持原source…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-02 J2/F8首轮验收修复：external与generated来源核验按实际输入模式分开，完整编辑包闭包保持；F8延迟显露只能服务仍当前的owned焦点。诊断code兼容/迁移、完整PyVista环境及首尾构建/报…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-11-01 I2/J1 已完成：6310969仅补测试，380产品文件与5fe0a10相同；Windows/Linux runtime/SDK、冻结工具、正式矩阵与26图/4次正常退出的原生范围已验。布局/3D覆盖不进F5/…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[README.md](docs/verification/i2-j1-final-20261101/README.md)
- 2026-11-01 I2/J1 实施候选：安装、环境就绪和模拟成功分别核验；发布包版本与 Geant4 版本独立。冻结程序必须隔离宿主 DLL 搜索路径、核对源码及产物身份，不能凭自检可启动复用旧 GUI。布局沿用单实例与原业务所有…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-31 K1 验收关闭：资源路径 P1 与永久回归 P2 经独审和 Windows/Linux 正式单例关闭；5644e1e 仅追加回归，350 产品字节保持2914b39，原矩阵与原生证据按原身份沿用。晚变化链接仍须在…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[README.md](docs/verification/k1-final-20261031/README.md)
- 2026-10-31 K1 显示契约：成功且非陈旧的生成/运行命令投影覆盖 external 无 package；有效 launch 的实际 argv 优先，兼容计划命令不冒实际事实，目录未知不回填编辑 cwd。pending 按服务…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-31 K1 配置包搬移：匹配资源的四个路径草稿随规范路径搬移，非法草稿保留；staging 与 writer 收据先检查链接再比较规范路径。真实 GUI 下一动作、Windows 别名及旧异步 smoke 反例见 `d…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-31 K1 实施中：统一动作服务复用 F4/F5/runner，四层验证独立；输入变化及 Undo 后历史不得恢复当前资格。资源包重写路径后的哈希与原始读取证据分别保存；I1 只给环境事实。范围与验收见 `docs/c…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-31 F5：已完成；冻结5c1eec5、原生5d身份映射及失败历史见[最终证据](docs/verification/f5-final-20261031/README.md)。完整契约仍在docs/agent-hist…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[README.md](docs/verification/f5-final-20261031/README.md)、[MODEL-POLICY.md](docs/collab/MODEL-POLICY.md)
- 2026-10-30 F5候选：主编辑快照/事务统一Undo/Redo，v7保留材料/几何及raw drafts，源阻断从捕获原文重建；旧包恢复仍遵守E6当前包语义。每会话恢复OS锁、单调revision和已退役屏障；发布后清理不能反…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 F4阶段关闭记录（已完成）：产品7d718d038a00d89995ea773b4772764116b620c3，正式矩阵/原生退出/独立审查见[最终证据](docs/verification/f4-final-…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[README.md](docs/verification/f4-final-20261030/README.md)
- 2026-10-30 F4候选：诊断身份、字段和来源须由规则生产，不能解析翻译文本猜位置；旧文本报告与blocking保持，重复源行保留独立记录。定位不修改模型，编辑/重载/切项目后旧快照失效；源内容只读且区分逻辑文本SHA与F1原始…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 F1阶段关闭：产品f176d0e自动矩阵及14次Windows原生观察/正常退出、独立复核通过；GUI ede037f仅文档差异，不能伪改构建commit相等。合成历史行仍为结果未证实，07图像与滞后UIA分开解…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 F1 GDML 收尾：原生句柄取得后的缓冲分配必须在关闭保护范围内；测试线程异常须转回调用线程，仅 `std::bad_alloc`/Xerces `OutOfMemoryException` 作为预期分配拒绝，…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 F1首轮回归：后台加载时预设图表必须绑定当前目录/请求序号，完成后再选择；未知key必须清空旧图并明确报错，不能仅加等待掩盖默认图。Qt回传显式排队，旧请求完成不得覆盖新请求。Windows全量显式传实际 `G4…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 F1候选：来源扩展严格区分读取/接受/运行/字节一致；不得重读源文件伪造历史hash。产物显式scope，metadata唯一自排除，新协议缺损不得降级；auto仅显式选择、默认CSV不变。GUI每次新动作后台重…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 E6阶段关闭：实现a779634的自动矩阵与12状态实窗补验通过；合成Inspect命令检查、真实运行与原生截图观察分开计证，旧自动归档pending不得追改。完整范围与首个GUI host退出码unknown边…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-30 E6候选：主INI版本标记与独立几何版本严格分开，版本拒绝须保持旧reader；迁移副本源SHA复核/exclusive发布，发布后清理失败仅warning；旧项目已知兼容、未知/类型冲突拒绝；schema394…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 完整 2C 回归衔接：有效配置文件按 `g4usim_effective_config_v1` 登记；dry-run 配置证据不是模拟执行。故障注入的 `_t0` 仅用于单 worker 确定性覆盖，多 work…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 Q1 运行边界：Dose 用扣 daughter 的本体质量；GDML SD 保留真实对象，无法表达的 bias 名碰撞和持久 touchable 路径歧义须拒绝；材料解析/实际构造都检查数值及版本壳层范围；局部…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 Q1 数值与统计口径：非有限值/事件矩/worker 合并溢出须锁存失败，不限幅伪造结果；仅 ROOT 也检查 master mesh。scorer/mesh CSV v2 追加估计方法与可用状态，N<2/零分母…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 R-01/R-02 失败证据：csh 中配置后 `setMainConfig` 拒绝必须登记 app 失败、停止后续输入并非零退出；不实现热重载。（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 历史2C配置快照子集：`Config/EffectiveConfig` 区分缺失值与显式 null，事务拒绝不得改变 revision；（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-19 → 2026-10-27 的 29 条实施契约全文（含文件路径、行号、反例与回归入口）在 [docs/agent-history.md](docs/agent-history.md)。下表只列**仍然有效的操作规…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-28 Geant4 11.4 支持与版本矩阵：`src/Core/Geant4DataLocator.cc` 的数据集表按 `G4VERSION_NUMBER` 分段，新增（历史全文见 [docs/agent-history.md](docs/agent-history.md)）；相关：[Linux构建与验证.md](docs/Linux构建与验证.md)、[实时运行进度.md](docs/实时运行进度.md)
- 2026-10-28 命令失败传播：`/AIHL/biasing/*` 修改类命令在交互会话里被拒绝时必须计入交互失败（`interactive_command_failure_kind = biasing`）、停止会话、写 `sta…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 Q1 R25–R30：偏置须worker TLS私有算符、真实绑定与逐run/thread完整EndRun收据，master挂接不证明运行；派生XS溢出/下溢锁存失败。RNG命令须语义守卫，setSeeds 2–…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）
- 2026-10-29 Q1 R32：交互执行必须显式 `--ui --ui-session csh`；裸 `--ui` 或 INI interactive 未选 csh 在 macro 执行前拒绝（dry-run 例外），不能恢复未经…（历史全文见 [docs/agent-history.md](docs/agent-history.md)）

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
- 配置优先级必须以代码实际行为为准。M0-1/M0-1b 已对当前启动字段统一为“默认值 < 主配置文件 < macro 运行时命令 < 显式 CLI 参数”：`SimulationCommandLineOverrides` 在 `Configure()` 后重应用显式 CLI，并由 `SimulationManager`、`OutputManager`、`GeometryManager` 阻止低优先级入口改写 `output`、`threads`、`seed`、`check_overlaps` 等字段。该启动优先级过渡层本身不承担完整来源追踪；当前完整2C来源与独立应用证据见 `docs/EffectiveConfig.md`，不得以优先级守卫代替运行收据。
- M0 几何生命周期守卫：`/AIHL/geometry/` 的几何/配置修改命令（含 `markModified`）以及 `/AIHL/app/setCheckOverlaps` 只允许在 Geant4 `PreInit` 状态执行；`print`、`printTree`、`listUserVolumes` 为只读命令，不受此限制。初始化后禁止只改 Manager 缓存却继续以旧 Geant4 world 执行。batch 的 `ApplyCommand` 非零返回须保存失败位置、失败摘要和非零退出；`csh` 的失败返回须停止后续输入。切换几何请在初始化前配置或启动新进程，不能把 `/run/reinitializeGeometry`（尤其含 biasing operator）视为已完成安全验收。实际后端回归见 `scripts/test_run_summary.py`、`scripts/test_interactive_commands.py`。
- M0-2 的 `run_summary.txt` 只在最终生命周期阶段写入（dry-run、正常结束、交互会话结束或失败收尾），并区分计划配置与实际运行事实：状态、每次 run、计划/完成事件数、实际线程数、配置 seed、引擎初始 seed（无法可靠取得时为 `unknown`）、macro seed 修改、最终输出目录、生成文件和失败命令位置。seed 修改只可由当前代码明确识别且成功执行的命令确认；失败摘要必须区分执行失败和 preflight 失败。preflight 没有 `ApplyCommand()` 返回码，必须用 `macro_failure_code_available=false` 表达 `macro_failure_code=0` 的语义。无法取得的运行事实必须写为 `unknown` 或 `not_executed`。
- M0-3C4 的 GUI 结果判定不能仅凭进程退出码：`success` 必须有正常退出、本次新摘要、后端和 macro 完成、至少一个 run 与正数计划事件；每个 run 的计划/完成事件数须一致，逐 run 合计也须与摘要总数一致，不能仅用相等总数掩盖单轮未完成。dry-run、交互无 run、普通无 run、终止、kill、失败和未证实分别保留状态；旧摘要和无摘要不得冒充成功。当前仅是未提交工作区候选，见 `gui/g4usim_gui/core/run_result.py` 和专项 smoke。
- M0-3D 默认复杂示例的无界面验收入口是 `test/macros/run_hierarchical_batch.mac`；`test/macros/vis.mac` 仅用于显式 UI 可视化。复杂源文件的冷却管和颜色修复须由真实后端 overlap、运行摘要和旧坐标反例回归证明，不得因 3D Preview 正常或进程退出码 0 宣称场景可信。`test/main_hierarchical.ini` 已改为逐 process 规则和真实体积；它与批处理 macro 完成 3/3、与完整 macro 完成 100/100 事件且两个目标匹配，但实际偏置效果仍为 `unknown`，不能当作 M2 验证。
- M0-3E 的工作区候选要求以物理初始化后的实际 wrapped process 校验每个启用的 bias 目标；普通 process 名存在但未包裹不算匹配。macro 配置的物理/biasing 修改须在初始化前重绑物理列表，初始化后修改应拒绝；失败在事件前报告粒子、目标、候选和替代建议。摘要分别记录规则、挂接、匹配，未观察实际偏置时必须写 `unknown`，不得把目标匹配当成 M2 物理验证。GUI generated 模式无规则编辑器，启用空 hook 时不得生成运行包。
- biasing operator 已挂接后的 `/run/reinitializeGeometry` 在本机真实后端曾访问违例；当前 batch macro 必须提前拒绝并建议新进程重建。`--ui` 与已启用的 biasing 配置或会修改 biasing 的 macro 不能组合，交互会话内的 biasing 修改命令必须明确拒绝，避免绕过 batch 保护。`/run/physicsModified` 后 `/run/initialize` 的专项通过不等于完整几何重建安全；实际交互 UI 操作尚未自动化验收。
- macro 执行前必须运行静态递归 preflight：检查 `/control/execute` 引入的文件，顶层相对路径按进程工作目录解析，嵌套相对路径只能按发出命令的 macro 文件目录解析。预检生成的规范化命令序列必须直接用于实际执行；拒绝已知 CLI 冲突的项目命令、`/run/numberOfThreads`、`/random/...`，以及无法可靠分析的 `/control/alias`、`/control/loop`、`/control/foreach`。不得声称能够保护任意动态 Geant4 命令；未覆盖命令必须记录为风险或明确不支持。
- `/AIHL/app/setMainConfig` 只能用于 `Configure()` 以前的入口，批处理 macro 已在配置后，必须在 preflight 阶段拒绝切换主 INI；直接调用 `SimulationManager::SetMainConfig()` 在已配置/初始化状态也必须拒绝，避免破坏来源快照与 Manager 一致性。更换主配置须新进程指定 `--config`。
- 配置字段、Geant4 命令、输出列名和项目 JSON 字段属于接口。删除、改名或改变默认值时，必须给出迁移策略和兼容性说明。
- M0-3A 对尚未支持的能力采用统一 fail-fast：`placement=replica|parameterised|assembly`、GDML、材料 `temperature`/`pressure`、`[physics.region.*]`、LET 开启均必须在 Geant4 对象创建或运行前拒绝；替代方案必须出现在错误消息中。Dose 和 Fluence 例外仅为已实现的实验性敏感体计分（需默认 scorer），Fluence 限无 daughter 的 solid 与 track-length 定义，不能推断其他剂量或注量能力已支持。
- M0-3B1 对主配置文件建立字段消费追踪：`IniReader` 保留文件、section、key、原始值和行号；成功 getter 标记字段已消费，`ConfigManager` 在各 Manager 完成配置后稳定输出 `[ConfigWarning]` 未消费字段和未知 section，并写入 `run_summary.txt`。该机制只警告、不改变运行结果；材料文件和几何文件仍由各自解析器独立处理。
- M0-3B2A 对材料独立配置文件使用闭合 schema：隐式 `global`、未知 section、空的动态 section 后缀和未知 key 必须在 Geant4 对象创建前失败，并报告 file、line、section、key、value；`temperature`/`pressure` 继续使用专用的 M0-3A 错误和替代建议。旧 GUI run package 在 `[material.<name>]` 中生成的 `type = material` 是已弃用兼容字段，只可取该值且不得影响 `MaterialDefinition`；新 writer 不再生成。该 schema 不适用于几何独立配置文件，也不实现新的材料能力。
- 输出必须说明文件生成条件、线程后缀、单位/量纲、合并方式和未生成文件的正常原因。没有物理定义或数据契约的 scorer 不得输出看似有效的结果。
- M0-4 工作区 CSV 契约候选采用 `output_csv_schema_version=3`：hits/event 保留 `runID`，首轮仍使用 `_tN`，后续 run 使用 `_tN_rR`；当前已验证的能量/长度列在表头标记 `_MeV`/`_mm`，hits 不再输出未计算的 `LETcalc`/`LETstep` 零值占位。Edep 直方图和分类汇总按 run 独立，摘要根据实际表头区分 v2/v3 或 `unknown`；`run_summary_schema_version=1` 只描述摘要结构，单位标记和目标匹配都不代表物理结果已验证。旧 CSV v1 无可靠的多 run 恢复路径，v2→v3 的字段迁移见 `docs/输出数据契约.md`。
- M0-4 工作区输出文件登记已改为 master/worker 共享的互斥保护登记表，仅在 CSV 显式关闭成功或直方图写出成功后登记；`GetGeneratedFiles()` 不再扫描目录或依赖 mtime，因此外部程序同期创建的文件不会因时间戳被误列。真实双线程运行期间外部文件注入回归见 `scripts/test_run_summary.py`。登记只证明写出组件报告完成且文件仍存在，不证明设备持久化、未被外部修改或物理正确。
- M0-4 工作区候选还在共享登记表中锁存首个 worker 输出失败（`run_id/thread_id/stage/message`）；event/hits 写出错误请求停止 run，worker 收尾阶段捕获并记录异常，batch `beamOn` 返回后以及交互会话结束时检查失败，最终摘要写 `output_failure_*`、`status=failed` 和非零退出码。`G4USIM_TEST_OUTPUT_FAULT=event_row_t0|summary_close_t0` 仅供测试，在真实 Geant4 双线程 worker 路径中验证了事件行和汇总关闭故障；不要在正常生产环境设置此变量。未验证磁盘满/断连、异常进程终止及交互 UI 的全部失败路径，M0-4 仍为部分实现。
- M0-4 主线程最终化补充：`FinalizeRunSummary()` 必须分别尝试最终 `Flush`/`Close`，将首个异常锁存在共享输出失败登记表，尽力写出 `failed` 摘要并返回失败结果；正常结束路径收到失败结果时必须返回非零退出码，不能把已写出的失败摘要误报为摘要写入失败。测试专用 `final_flush_master` / `final_close_master` 在真实最终化分支完成操作后模拟异常，验证失败状态和摘要写出；这不是磁盘错误实测。摘要本身无法写入时仍使用专用 summary failure 错误路径。
- M0-4 运行启动阶段补充：`BeginOfRunAction()` 的 `SetRunId`、run 开始摘要、输出初始化及 `ScoringManager::BeginRun` 共用分阶段异常捕获，锁存首因并请求中止，不允许 worker 启动异常穿出回调。`SetRunId` 切换旧文件失败时使用尝试启动的 run ID 登记错误，避免误归属上一轮；`OutputManager::Flush()` 逐 writer 尝试并重新抛出首个异常。测试专用 `begin_set_run_id_t0` / `begin_scoring_t0` 仅模拟第二轮启动故障，不代表物理介质故障。必须检查首轮 run 与输出保留、失败摘要、非零退出；MT 下 master/worker 的线程编号可能重叠，不能仅以编号判定故障源。
- M0-4 交互式目录冲突补充：`RunAction::BeginOfRunAction()` 在 master/sequential 运行启动时，按实际线程数对所有已知 worker CSV 目标目录先执行 `ValidateOutputTargetDirectories`，失败记入 `run_begin_validate_targets` 并中止 run；batch 仍保留宏命令前的早期检查和精确来源行号。此检查预防已存在目录占用目标文件名，不覆盖后续并发创建、权限变化、实际磁盘或设备故障。真实 `--ui --ui-session csh` 单/双线程首轮与第二轮回归见 `scripts/test_interactive_commands.py`，失败时 `run_count` 可能包含已开始但零完成事件的 run。
- batch macro 中材料 Messenger 的命令执行异常不能只降级成 `JustWarning` 并假装成功；须同时锁存命令失败计数与错误，`ApplyCommand()` 即使返回 0 也应在本条 macro 后拒绝继续、写入来源行号和失败摘要并非零退出。交互 UI 材料命令仍是聚合级失败判定（`MaterialManager` 失败计数汇总为 `interactive_command_failure_kind=material`，不是逐条）；`PreInit` 之外的交互材料修改已由 `AvailableForStates(G4State_PreInit)` 关闭，初始化后调用会被 Geant4 拒绝并以 `geant4_illegal_application_state` 失败（见 2026-10-28 命令失败传播条目）。
- batch macro 的 `/AIHL/output/*` 命令也必须检查 `OutputManager` 记录的 Messenger 命令失败计数；即使 `ApplyCommand()` 返回 0，内部异常仍须中止后续命令、保留失败文件/行号、输出 `macro_failure_code_available=false` 并返回非零。`SimulationManager::SetOutputDir()` 应先让 `OutputManager` 接受目录，再更新 context 和 EffectiveConfig 来源；失败不得冒充成功来源。测试专用 `G4USIM_TEST_OUTPUT_FAULT=messenger_set_dir|manager_set_dir` 分别注入命令处理器和 Manager setter 失败，正常运行不得设置。交互 UI 尚未完成逐命令相同保证。
- 交互会话可用 `--ui --ui-session csh` 选择可脚本输入的 Geant4 命令行 UI。`AuditedCshSession` 复用终端命令路径并在覆写的 `ExecuteCommand()` 中直接取得 `G4UImanager::ApplyCommand()` 数值结果，保留原有诊断文本；本机 Geant4 11.3.2 的 `GetLastReturnCode()` 对错误命令仍返回 0，不能作为证据。未知命令、错误类型、越界和非法状态维持原分类，其他非零数值状态使用 `geant4_command_status`，记录命令与状态码；与材料、输出和物理 Messenger 错误计数合并，失败在会话结束时非零退出、写 `status=failed` 和单行 `interactive_command_failure_kind/message`。真实测试增加 `/gps/pos/type InvalidCandidate` 状态码 500 和常见拒绝路径。受控 `G4UIcsh` shell 在已识别的直接命令失败或 Messenger/输出错误后停止读取下一条命令；仅覆盖脚本化 `csh`，内部 Messenger 返回 0 的路径依靠独立错误计数，不能保证所有嵌套/动态命令、Qt UI、未明确报告的内核失败及完整生命周期均已验证。
- 交互会话物理命令补充：Geant4 physics list 已注册后，`/AIHL/physics/*` 中会修改 PhysicsManager 的命令必须在 `PhysicsMessenger` 拒绝并累计交互错误，不得产生仅修改 Manager、没有重绑内核的假状态；`print`、`listAvailableReferences`、`listAvailableEMReferences` 查询可用。会话收尾记录 `interactive_command_failure_kind=physics`（有其他类别时为 `multiple`）、失败摘要与非零退出；修改物理配置应在新进程的初始化前 batch macro 中完成。该守卫不保证其他原生 Geant4 UI 命令已受审计；真实 `csh` 专项覆盖改前、改后及查询命令。
- batch macro 修改物理配置后若直接进入 `--ui` 而尚未执行 `/run/initialize`，必须在交互 SessionStart 前消费 `physicsListDirty`，重新注册 `sim.CreatePhysicsList()` 并重新准备 Source；否则用户在 csh 内的 `/run/initialize` 会使用旧列表。batch 的 `/AIHL/physics/listAvailableReferences` 和 `listAvailableEMReferences` 是只读命令，允许在内核初始化后查询，不应把它们误分类为物理突变。真实 `csh` 宏转交专项验证了重绑日志、两个事件及只读命令，仍不等同辐射物理结果基准。
- Geant4 对象创建、敏感体、region、biasing、线程本地输出和 reinitialize 生命周期必须有可重复的运行验证。只在内存中保存配置不能算运行时生效。

## 4. GUI、国际化和人类文档

- GUI 只是后端能力的编辑和运行入口，不是功能定义者。后端未支持的能力不得被 GUI 默认生成或静默降级。
- 面向人类的说明文档只使用中文。代码标识符、Geant4 命令、文件名、配置 section/key、输出列名和外部 API 名称保持原样，不翻译成另一个接口。
- 每项开发完成后同步人类文档和 Agent 文档；至少检查 docs/功能支持矩阵.md、docs/开发路线图.md、相关模块说明和相关目录的 AGENTS.md 是否仍然准确。
- GUI 的 PySide6、国际化、主题、配置编辑器和生成包约束见 gui/AGENTS.md，不得在根目录规则之外另行发明一套支持口径。
- 状态入口唯一：当前快照、阶段进度、验收证据与已知缺口以仓库根 `STATUS.md` 为入口；阶段状态只登记在 `docs/ROADMAP.md`，长期目标在 `docs/开发路线图.md`。不得再新建“交接/检查点/执行规划”类状态文档；带日期的历史快照放 `docs/archive/` 并登记到 `docs/archive/README.md`。
- 本文件只保留规则与条目索引：新增实施契约全文追加到 `docs/agent-history.md` 末尾，同时在 §0 索引加一行摘要；不得再在 AGENTS.md 内堆长篇日期条目。

## 5. 工作区和改动范围

- 不修改无关代码，不覆盖工作区已有改动。开始工作前检查 git status；对未跟踪文件、暂存内容和用户已改文件保持原样。
- 优先做小范围、可审查的修改。不要借整理文档之机重排代码、清理旧输出、修改 .gitignore 或删除示例。
- 不使用破坏性 Git 操作覆盖用户内容，例如未经明确要求不得执行 git reset --hard 或 git checkout --。

## 6. 测试和交付

- 每个任务必须运行相应测试，并在最终报告中区分“已验证”和“未验证”。文档任务至少运行链接/路径检查和受影响的 GUI 或配置 smoke；涉及后端行为时还要运行可用的构建、--help、dry-run 或后端 smoke。
- 配置优先级回归测试入口为 `python scripts/test_config_precedence.py`；M0-2 摘要回归测试入口为 `python scripts/test_run_summary.py`。涉及 M0-1/M0-1b 的改动至少覆盖配置-only、配置 macro、配置 dry-run/interactive、CLI-only、配置/CLI 冲突、macro preflight、真实 `beamOn`、无效参数、重复参数和缺失路径；涉及摘要时还必须覆盖多次 `beamOn`、失败收尾、无 run、输出目录切换和摘要写入失败。
- 测试失败时先区分代码失败、环境缺失和未覆盖场景，不得把“命令成功退出”当作物理正确性证明。
- M0-5 工作区统一测试入口为 `scripts/run_m0_tests.py`，按 static/GUI/backend/integration 分层，报告 pass/fail/skip 和日志；后端用例必须核对 `--capabilities.source_fingerprint` 与当前 C++ 工作区。CTest skipped 不等于完整通过，不能只看总退出码；详情见 `docs/测试平台说明.md`。
- 若真实 Geant4 可执行文件、Qt/PySide6、3D 依赖或特定工具链不可用，必须明确记录未验证部分和复现命令。
- 统一测试入口的报告是 `version: 2` 证据：每用例经 `tools/test_assert_probe.py` 记录 `assertions_executed`，报告带 `tests_content_fingerprint` 与逐用例 `log_sha256`；`scripts/check_report_evidence.py` 必须对最新报告通过。验证 helper 写成 `assert`，`raise AssertionError` 不会被计数。CI 的 profile 步骤必须带 `--fail-on-skip`，缺失 Qt/uproot/后端的 skip 不得以退出码 2 变绿。
- 归档证据必须自洽可复核：提交到 `docs/verification/<阶段>-<日期>/` 的证据副本要连同 `logs/` 一起入库（`.gitignore` 对 `docs/verification/**/logs/*.log` 有例外），使 `python -B scripts/check_report_evidence.py --report-root <归档目录>` 能在干净克隆上通过；归档目录的 `report.json` 直接位于目录根，运行目录是 `<report-root>/<run-id>/report.json`，两种布局都必须支持。被指纹按原始字节哈希的输入（`src/`、`include/`、`main.cc`、`CMakeLists.txt`）与测试内容指纹覆盖的目录，任何改动都不得让 `git checkout`/`merge` 改变磁盘字节：`.gitattributes` 已对 `*.cc`/`*.hh`/`*.h`/`*.in`/`*.py`/`*.json`/`*.ini`/`*.mac`/`*.csv` 与 `CMakeLists.txt` 固定 `text eol=lf`；新增被哈希的文件类型必须同时加 eol 规则或先归一化。
- 完成前复核 git diff、 新增文件编码、文档中的支持等级和工作区状态，确保没有把用户已有改动混入本任务。

## 7. M0-3B2B1 几何安全闭环

- M0-3B2B1 只闭合会造成静默失效或晚失败的几何字段：production cut 只允许 `cut.gamma`、`cut.e-`、`cut.e+`、`cut.proton`，且所在普通 volume 必须有非空 `region`；shape 参数、`copyNo` 和 M0-3A placement 拒绝必须在首个 Geant4 geometry object 创建前完成。
- `simple_box` target 和 `array` element 只允许 `shape=box`；`layered_device`、`shielding` 继续固定为 box。hierarchical 普通 volume 和 boolean tool 使用严格的逐 shape 参数数量及 shape-specific 字段契约。
- `VolumeBuilder` 的 `created_geometry_object_count` 是 B2B1 前置失败测试的可观察事实，不能用日志先后顺序替代。
- B2B1 本身没有建立完整几何闭合 schema；普通未知字段、legacy metadata warning、`run_summary.txt` 诊断已由 B2B2 补齐，自动迁移及 `version=2` 留给 M0-3B3。

## 8. M0-3B2B2 几何来源诊断与兼容 warning

- 几何配置诊断使用 `GeometryConfigDiagnostic`，必须保留文件、行号、原始 section/key/value、code/category、message 和 suggestion；输出统一为 `[GeometryConfigWarning] file:line [section]/key = value: message; suggestion`。
- `unknown_section`、`unconsumed_key`、`legacy_metadata`、`ignored_boolean_key` 按文件、行号、section、key 稳定排序去重，并通过 `GeometryManager`、`SimulationManager` 和 `run_summary.txt` 统一输出；`config_warning_count` 仍只统计主 INI，几何 warning 使用独立 `geometry_config_warning_count`。
- canonical `metadata.<非空名称>` 仅作为保存属性，不参与 Geant4 运行；hierarchical/layered 的无前缀未知属性继续保留并建议迁移到 `metadata.<原key>`，不得自动改写。B3 工作区候选允许在几何文件 `[global]` 显式写 `version = 2`，此时现有四类来源诊断在创建几何对象前变为错误；无版本或 `version = 1` 保持兼容 warning。GUI 已可在受支持编辑子集里保留版本标记并写回，项目快照不得丢失它；其他 round-trip blocker 仍须阻止 editable 生成。自动迁移和完整无损 round-trip 仍未完成。
- B3 严格几何源中的重复 section/key 也须在首个几何对象前拒绝，避免 `IniReader` 的后值覆盖前值；GUI 对空未知 section、未列于 `[layers]/names` 的层以及重复声明设置 round-trip blocker。无版本或版本 1 的重复声明暂保留原兼容行为，升级到版本 2 前须人工消歧。

## 9. M0-3C0B 运行前清单（工作区）

- `--inspect-run` 必须复用真实 `SimulationManager::Configure()` 和 `PreflightMacro`，不初始化/执行 Geant4 run，不写摘要或创建输出目录；JSON `G4UniversalSimRunPlan` v1 使用 `configuration_phase=before_macro` 明确区分配置计划与运行事实。
- 初始配置清单记录当前启动字段、材料/几何输入、默认/主配置/CLI 来源以及主 INI 原文和行号。该 `--inspect-run` 清单不是全消费者JSON快照，macro后续修改仍作为待执行命令报告；完整2C使用独立协议与真实阶段收据，不能据清单声称已生效。
- GUI 外部 Run 先异步查询同一组实际启动参数，成功且输入未变化才启动；config-only、macro-only、中文路径、CLI 冲突和失败阻断由 `scripts/test_macro_plan.py` 与 GUI `smoke_run_input_modes.py` 验证。实际运行成功由 C4 结合摘要判断。
- 回归脚本的默认输出和随机引擎文件必须留在临时工作区，不能改写仓库示例输出。当前 M0-1/M0-2 脚本复制所需配置/macro fixture 后在临时目录运行。

## 10. M0 有效启动字段来源快照（工作区候选）

- `scripts/test_run_summary.py` 的单线程双 run 源采样回归，通过真实 hits 的主粒子首步记录验证 `/AIHL/source/particle`、`/AIHL/source/energy` 在受控点源、单能配置中实际作用于 Geant4 事件；不得推广为原生 `/gps/*`、多线程或全模块 EffectiveConfig 的应用验证。
- `effective_config_source_coverage=startup_geometry_source_and_physics_reference` 代表六个启动字段 `output_dir`、`run_name`、`threads`、`seed`、`macro_file`、`check_overlaps`、三个几何字段 `geometry_template`、`geometry_config`、`geometry_default_world_material` 及 `source_particle`、`source_energy` 及 `physics_reference` 的来源记录；历史 `startup_geometry_and_source_particle`、`startup_geometry_and_source_particle_energy` 仍须兼容。该旧摘要覆盖枚举不能代表完整2C JSON，也不能证明Geant4内核实际应用。
- `effective_<field>_origin_kind/file/line/section/key` 的 `kind` 只能使用 `default`、`main_ini`、`cli`、`macro` 或 `runtime_unattributed`。主 INI 保留原始字段和行号；宏命令须在真实执行成功并通过 Messenger 错误检查后记载来源；CLI 锁定字段不受宏重新归属。无法确定的运行时修改必须明确标为 `runtime_unattributed`。
- `physics_reference` 在主 INI 中通常由 `[physics]/reference` 决定；reference 模式下非空 `[physics]/em` 改变最终 reference 后由 `em` 归属。成功 batch `/AIHL/physics/setReferenceList`、`setBaseReferenceList`、`clearReferenceList` 更新来源；`setEM` 仅在 PhysicsManager 当前处于 reference 模式时更新 reference 来源。`effective_physics_reference` 是 Manager 名称，不能据此推断 Geant4 内核或 biasing 已实际验证。
- 相关回归由 `scripts/test_run_summary.py` 覆盖，几何来源在成功执行已识别 batch macro 后登记；`/AIHL/geometry/clear` 只重新归属 `geometry_config`，不改变模板或默认世界材料。`effective_geometry_default_world_material` 为 Manager 当前值，`effective_config_geant4_applied=unknown` 仍保留。`startup_fields_only`、`startup_and_geometry_fields`、`startup_geometry_and_source_particle`、`startup_geometry_and_source_particle_energy` 是历史摘要枚举值，消费者须兼容。`source_particle` 主 INI 优先记录非空 `[source]/particle`，否则记录 `[source]/preset`；成功 batch macro 的 `/AIHL/source/preset`、`/AIHL/source/particle`、`/AIHL/source/reset` 更新来源，包含重置为空状态。`source_energy` 优先记录非空 `[source]/energy`，否则记录 `[source]/preset`；成功批处理 `/AIHL/source/energy`、`/AIHL/source/preset`、`/AIHL/source/reset` 更新来源。`effective_source_energy_MeV` 是 SourceManager 当前单能值，0 表示未设置或已重置。来源仅针对 SourceManager，原生 `/gps/*` 命令对 Geant4 的直接效果未覆盖；后续扩展旧摘要字段仍须逐模块校验实际消费与运行生命周期；当前完整2C JSON另有消费者协议，不能直接把配置表中的初始值当作最终有效值。


- 2026-10-29 完整2C已验收：产品f4770b0，11消费者、三阶段、模块策略和GUI集合/差异，Windows118、双版本Linux各118、同口径Q1控制及实窗均通过；最终证据 `docs/verification/2c-full-20261029/README.md`。同日configured子集限制仅是历史验收范围；更改这些路径前读 `docs/EffectiveConfig.md` 和 `docs/agent-history.md` 末尾完整 2C 补充。配置 revision、消费者 configuration_generation 与应用证据分别处理，未知原生命令不能伪造 applied，不以构建或旧测试宣称完整验收。

- 2026-10-29 完整 2C 偏置命令新反例：build03 非法 factor 曾 FatalException abort 且无受控摘要，旧 Q1 冻结范围未覆盖此例。非法 biasing macro/csh 应受控 failed、停止后续输入并保留真实失败位置，不发布配置值/来源/代次/revision；ParseDouble 拒绝非有限值，ApplyCommand 返回 0 仍须检查 BiasingManager 内部失败计数。修前证据、修复契约及反例见 `docs/agent-history.md` 末尾“偏置 macro 非法数值的受控失败链”；修后6类负例、正例与完整平台通过以完整2C最终报告为准，不把修前build03当作验收版本。
