# G4UniversalSim GUI Agent 开发约束

2026-10-27 GUI 源字段保留：Setup 栏的 summary widgets 只能镜像它真正暴露的标量源字段（preset/particle/energy/position/direction）与 physics/scoring 字段；源几何与角分布（`position_mode`/`position_type`/`source_shape`/`center`/`halfx`/`halfy`/`radius`/`isotropic`/`angular_mode`）属于 Source editor，任何槽都不得无条件重置为 `point`/`fixed`——`widgets/config/run_config.py` 曾这么做，导致 plane/rectangle/isotropic 源在用户改一个数字后静默退回点源+固定束流、生成的 main.ini 丢字段而运行仍“成功”。回归 `gui/smoke_tests/smoke_source_field_preservation.py`（端到端写 main.ini 后断言字段仍在，含 point 反向 sanity）；同类重置只允许带明确条件（空值补默认、旧别名归一化）。进度终态文案走既有 `Result: {state}`；stdout/stderr/merged 三个日志视图必须有行数上限，merged 前缀只在行首插入，runner 的日志 tag 解析必须跨 chunk 缓冲完整行。

2026-10-27 F6：`core/run_progress.py` 有界增量解析版本化 stdout 进度；runner 每次启动重置，分别增量解码 stdout/stderr，退出先排空尾流再判最终结果。RunPage 未知进度不造百分比，计数全到但未 end 显示收尾中；停止/强杀/失败时进度条保留最后观察值，状态文字改用终态文案（结果：模拟成功／用户停止／强制结束／结果未证实），不再输出“进度已冻结”。end 不代表成功，最终状态仍由 run_result.py 决定。新消息版本、噪声前缀、坏 JSON、非有限数、超长行、倒序、跨 run、无换行 EOF 必须保留测试；smoke_live_progress.py 和 smoke_live_progress_backend.py 分别验证协议/Qt 与真实 Geant4，契约见 docs/实时运行进度.md。

2026-10-26 E2：`core/config_schema.py` 只做字段描述/标量必要条件；`structured` 会要求上下文校验，不能吞掉这个结果并当作可运行。动态源/区域/网格及独立几何模板可查询描述，但不扩大 editor/writer 白名单。源长度/能量、physics.default_cut 和 Edep 直方图复用 schema；跨字段 max>min 等仍由 editor 验证。材料已知键从生成数据读取，元素/同位素仍原文保留。writer 不再生成未消费的 physics.mode，参考模式仍由 reference 决定。四份生成产物一律由 scripts/generate_config_schema.py 更新。

2026-10-22 D 安装包：源码与安装包路径只经 `core/install_layout.py` 判断（冻结时 `sys.executable` 是 GUI 本身）：应用根、默认后端（包内 `bin/` 或 `build_vs2026/Release`）、运行包目录（冻结时为“文档\G4UniversalSim\gui_runs”）、脚本目录与运行辅助脚本的 Python（冻结时找 `G4USIM_PYTHON` 或 PATH 中的 python，找不到则禁用并说明）。不要再用 `Path(__file__).parents[...]` 或 `sys.executable` 定位仓库与 Python。`app.py --self-test <报告.json>` 供打包验证，冻结窗口程序没有控制台，必须写文件。

2026-10-22 C3 参数扫描：`core/scan.py`（无 Qt）只扫描配置页编辑器能生成的设置，逐点 `apply_value` 深拷贝基准，先 `validate_scan` 全部通过再写任何文件，再用 `create_run_package` 生成普通运行包并写 `scan.json`（G4UniversalSimScan v1）；`core/scan_runner.py` 逐点复用 `G4USimRunner`（日志、`run_status.json`、`evaluate_run_result` 判定一致），以 attempt 令牌保证每点只结束一次（启动失败只有 errorOccurred、崩溃两者都有），并传入该点自己的 seed，不能用基准 seed 覆盖 `run.seed` 扫描。结果只读该点合并的 `scorer_statistics.csv`。QWidget 子类属性不得与 Qt 虚方法同名（`metric` 曾覆盖 `QPaintDevice.metric()` 导致绘制时访问违例）。冒烟测试中的计时器要可停止，退出前在 QApplication 仍存在时删除带 QProcess 的页面。专项 `smoke_scans.py`、`smoke_scans_backend.py`。

2026-10-22 C2 新建仿真向导：业务逻辑在 `core/wizard.py`（无 Qt），只产生编辑器已能生成的子集（NIST 材料、box/tubs、点源 fixed/isotropic 与矩形面源、参考物理列表、hits/event_edep/Edep/Dose/Fluence），不得借向导写出编辑器之外的后端字段；结果通过 `apply_to_project` 原位写入现有 `G4USimProject` 并由 `_set_project` 刷新页面，生成包必须走 `create_run_package`。校验消息与摘要以 (模板, 参数) 返回再 `ui_format`。向导页面在 `initializePage` 填控件时须屏蔽信号回读（`_loading`），否则半填的控件会覆盖 spec。新增 ZH_CN 键前检查重复：字典字面量中重复键会静默覆盖。专项 `smoke_new_simulation_wizard.py`（模型、对话框、主窗口与生成包；须替换模态 QMessageBox）与 `smoke_new_simulation_backend.py`（五个场景真实运行与物理合理性）。

2026-10-22 C1 内置图表：数据读取只放在 `output/plot_data.py`（无 Qt，numpy），页面 `widgets/plot_panel.py` 只选数据集/视图、用 matplotlib 绘制并导出；图中数值必须与后端文件一致（scorer_statistics 的 value/std_error，网格 CSV 或 ROOT 的 sum 与 rel_error，box 网格坐标取 `run_metadata.json` 的 bins/size_mm（半宽）/center_mm）。每初级粒子归一化只能用 `run_summary.txt` 的 `run_<R>_completed_events`。说明文字以 (模板, 参数) 返回再经 `ui_format` 翻译。视图 combobox 的 data 用字符串（`profile:<轴>`、`map:<x>:<y>`），PySide6 的 `findData` 不能匹配 Python tuple。matplotlib 缺失时输出页仍须可用。专项 `smoke_plots.py`（合成逐值）与 `smoke_plots_backend.py`（真实后端，CSV/ROOT 网格一致）。

2026-10-21 M3/M5 Results JSON 导出原型：`widgets/output_page.py` 通过 `output/extension_runner.py` 的 `QProcess` 运行正式 Python CLI `dose_json`/`fluence_json`；只在存在模拟输出目录且目标为尚不存在的 JSON 文件时允许启动，重复启动拒绝，支持取消、启动/退出失败报告与页面关闭时子进程清理。GUI 对 schema、version、extension ID/version、data、warnings 和无效 JSON 常量执行读取校验，刷新文件列表；`smoke_output_extensions_gui.py` 覆盖真实 Qt 子进程和错误路径。导出成功只说明发现的 CSV 被后处理，必须提示检查上游 run_summary、worker 文件完整性及独立物理 benchmark，不能提升实验性 Dose/Fluence 的支持等级。

2026-10-21 Rectangle Source GUI 原型：`source_shape=rectangle` 在 generated 模式仅开放 XY 平面、`center`、有限正 `halfx/halfy`，按 `shape=rectangle` 写出且不混入 `radius`；fixed/isotropic 两种角分布遵循方向字段互斥；square、annulus、其他高级分布继续阻止运行包。`gui/smoke_tests/smoke_source_editor_v2.py` 检查生成及非法输入；C++ 真实采样专项见 `scripts/test_run_summary.py`。普通预览不代表源平面任意旋转受支持。

2026-10-21 Dose GUI 原型已开放：`ScoringSettings` 与 `ScoringEditableModel` 双向保留 `dose`（默认 false），writer 只在选择时写 `dose=true`，且必须依赖默认 scorer 自动创建；Results / Dose (Gy) 使用 `read_dose_summaries()` 合并已发现的 worker 数据，质量不能跨线程累加，缺失/损坏文件需提示。GUI smoke 入口 `gui/smoke_tests/smoke_dose_results.py`；尚未独立物理标定，文案必须标明实验性。

2026-10-21 Fluence GUI 实验性原型：`fluence` 默认 false，配置模型、生成包 writer 与 Results / Fluence (mm^-2) 已接通。GUI 按 `(runID, physical touchable path)` 聚合已发现的 worker CSV，只累加 raw/weighted track length、每体积只取一次并重新计算 mm^-2；拒绝 schema、非有限值、坏文件及 worker 体积冲突，缺失 worker 只能提示风险。专项 `gui/smoke_tests/smoke_fluence_results.py`；零 Edep Geantino 和 ST/MT 双 run 真实验证见 `scripts/test_fluence_scoring.py`。仅适用于 daughter-free sensitive solid，不能宣称 surface fluence 或独立物理基准已通过。

2026-10-21 Source isotropic 输出约束：`angular_mode=isotropic` 时，generated main.ini 只输出 `isotropic=true`，不输出模型中保留供 fixed 模式使用的 `direction` 字段；后端明确拒绝 `isotropic=true` 与显式 `direction` 冲突。点源写 `position`，圆形平面源写 `center`/`radius`；禁止混写两种位置字段。`smoke_source_editor_v2.py` 同时验证点源和平面源的 isotropic writer。

2026-10-19 Source Editor 数值门禁：运行包中的 `energy`、`position`、`direction`、`radius` 不允许 `NaN`、`Inf` 和超出有限浮点范围的表示；validator 在生成前拒绝，后端 `UnitParser` 保留最终约束。由 `gui/smoke_tests/smoke_source_editor_v2.py` 覆盖。该门禁不表示全部单位和参数组合已完成 GUI 验证。

2026-10-19 平面源位置映射：Source Editor 的 `Position` 在 `position_mode=plane` 时必须生成 `[source]/center`（三轴及单位），在 `point` 时生成 `[source]/position`；GUI 预览中心、writer 和 Geant4 GPS 实际采样必须一致。`gui/smoke_tests/smoke_source_editor_v2.py` 检查偏移 4 mm 的生成配置，`scripts/test_run_summary.py` 核对真实后端 hits。旧 `planeBeam` 命令保留零 x/y 的兼容语义，不能扩大为任意空间分布已验证。

2026-10-22 界面刷新：主题色只在 `core/theme.py`（样式表 + `build_palette` 的 Qt palette；“系统”主题读 `styleHints().colorScheme()`，因为应用 palette 已是自定义的）；图标只用 `core/icons.py` 的 SVG 线条图标，主题切换时由 `MainWindow._refresh_icons` 和各页 `refresh_theme` 重绘，样式表中的箭头图片由 `_svg_url` 写到临时目录。matplotlib 图用 `plot_panel.style_axes`/`draw_empty`，字体族列表带 CJK 回退（`font.family` 而非 `font.sans-serif`，否则不逐字回退）。开始页 `widgets/start_page.py` 的示例在 `core/examples.py`（无 Qt）登记：示例 = 向导 spec + `examples/gallery/<id>/` 附带结果，载入走 `apply_simulation_wizard`，附带文件只读、输出仍写运行目录；附带结果只能由 `examples/gallery/build_gallery.py` 用真实后端生成，卡片描述须与数据一致（`smoke_start_page.py` 核对）。`core/scan.load_manifest` 支持相对路径与目录移动后的改基；运行包缺失的扫描只读（`ScanPage.is_read_only`）。页序：开始、项目、配置、运行、结果、历史、扫描；结果页分组为 `tabs`（概览、图表、表格、文件、工具）及 `data_tabs`/`file_tabs`/`tool_tabs`，配置页消息/原始文件/NIST 在 `details_tabs`。Tab 文字不能含 `&`（会被当作助记符）。

2026-10-23 E1 GUI/后端规则一致：材料名一律经 `parsers/materials_parser.material_reference_status`（自定义名去空白后不区分大小写，NIST 名区分大小写，其他 `G4_` 名只警告），与后端 `MaterialManager::GetMaterial` 一致；`[material.X]` 定义 X，`[NIST]`/`[element.*]`/`[isotope.*]` 不是材料行，原文保存在 `preserved_sections` 并由 writer 写在材料之前；组分保留 `名称:数值`；体积分数材料无 density 即 auto；材料循环引用报错。后端支持而编辑器不支持的形状（`geometry_editor_model.BACKEND_SHAPES`，与 `GeometryUtils.cc` 的 `ParseShape` 同步）是编辑器限制：提示原始文件复制模式，勾选后降为警告。默认演示项目用 `test/materials/test_materials.ini`。新规则差异由 `scripts/test_gui_backend_agreement.py`（统一平台 `gui_backend_agreement`）发现：新增几何/材料夹具会自动加入，判定不一致必须修正 GUI 或在 `EXPECTED` 中写明原因。

2026-10-23 G1 后端几何默认显示：配置页 3D 标签可见且勾选“自动显示 Geant4 几何”时，`schedule_backend_geometry` 在修改后 1.2 秒、切换到该页后 0.1 秒发出 `autoBackendGeometryRequested`；导出期间显示编辑器草图并注明近似。writer 不得在调用方文档上做校验（`generate_geometry_ini_text` 校验副本），否则会抹掉页面的材料错误。专项 `smoke_backend_geometry_auto.py`（真实后端：无运行包导出、缓存、去抖、忙时合并、编辑器错误、后端错误、关闭自动）。

2026-10-23 G2/G3 3D 视图：后端几何与编辑器草图都转为 `preview3d/view_model.ViewItem` 列表，由 `ViewState` 决定可见性（世界、隐藏、单独显示、按材料）、颜色（常见材料固定色，其余按名称顺序取调色板）、样式（容器半透明、敏感体实心、选中描边且其余变淡）和剖切平面；`pyvista_preview_widget.py` 只把它们映射到 VTK 属性，不在控件里写判定逻辑。体积名：后端物理/逻辑体名去掉 `_PV`/`_LV` 即编辑器名；`volumeSelected` 与体积表双向联动（`select_geometry_row` 屏蔽信号避免回环）。点击与拖动以 4 像素区分。VTK 在 Windows 上不能用 Qt offscreen 平台渲染，`smoke_3d_view.py` 的控件部分切换到 windows 平台、无显示时跳过；独立 QtInteractor 关闭前先 `_plotter.close()`，否则测试退出时 wglMakeCurrent 报错。

2026-10-23 E2 配置 schema：GUI 对已迁移字段（`[run]`、`[general]`、`[output]`）的检查用 `core/config_schema.check_value`（与后端解析一致：32 位整数、布尔词、能量单位、空值取默认等），不要再手写同类规则；GUI 自己更严的上限写在 schema 字段的 `gui` 中（如 trajectories 的 1000）。编辑某字段的控件用 `i18n.set_schema_tooltip(widget, section, key)` 设置提示，语言切换时由 `apply_language` 按 schema 重写。`core/config_schema_data.py` 是生成文件。

2026-10-23 G4/G5 草图与源：草图几何只在 `preview3d/sketch_geometry.py`（无 Qt/VTK）：数值按后端解析（`ParseDoubleWithUnit` 无单位为 mm/rad，旋转 `ParseAngle` 逐分量，`SplitVectorText` 分割），放置为 `G4PVPlacement(R, t)`、R = Rz·Ry·Rx 是坐标系旋转，实体按 R⁻¹ 转动，沿父链组合；各实体参数顺序照 `VolumeBuilder::Create*Solid`，改后端实体时须同步并跑 `scripts/test_sketch_accuracy.py`（统一平台 `gui_sketch_accuracy`；把旋转约定改错会失败）。`PreviewVolume.vertices/faces` 是世界坐标网格，画不出的写 `not_drawn` 原因并进消息，不得静默跳过；A5/placement 键存于只读 `preview_properties`（不写回，不算 legacy metadata）。源图元由 `source_builder._build_glyphs` 生成：平面源固定在 XY 平面（GPS 不用 normal），只有 point/circle/rectangle × fixed/isotropic 为 `generated`，其余淡色并标注仅预览；描述是 (模板, 值) 嵌套元组，由 `describe_source` 逐层 `ui_format`。Geant4 几何上只在 generated 模式叠加源（`show_backend_geometry(with_source=...)`）。专项 `smoke_source_glyphs.py` 用 H1 径迹核对真实初级粒子的起点与方向。

2026-10-23 G6 径迹叠加：`preview3d/trajectories.py` 无 Qt，读取一次 run 的全部 worker 文件（默认最后一轮）并按事件排序，schema/单位、跨文件重复事件、体积索引越界都报 ValueError；`TrackFilter` 按事件（None 为全部）、隐藏粒子、仅初级和次级最低初始能量筛选，初级径迹不受能量阈值影响；粒子颜色固定。`pyvista_preview_widget.py` 每种粒子一个线集 actor（不可拾取、不重置相机），`_render` 清场后重画；有径迹时 `ViewState.tracks_shown` 使未选中体积不透明度不超过 0.15。`load_tracks` 依次尝试项目输出目录、Output 页目录，最后才弹目录对话框；`_on_finished` 以 quiet 方式自动加载。配置页各编辑器标签页包在 `_scrolled` 的 QScrollArea（`editorScroll`）中，测试取标签页内容须解包；3D 页索引用 `preview3d_tab_index()`。截图脚本必须替换 `QMessageBox` 的 warning/information，否则会在用户桌面留下模态框。专项 `smoke_trajectory_view.py`（含真实后端 Generate and Run）。

2026-10-23 E5 拆分：配置页在 `widgets/config/`，每个编辑器一个模块，内含其控件与布局的 QWidget（`SetupPanel`、`MaterialsEditor`、`GeometryEditor`、`Preview3DPanel`、`RunConfigEditor`、`DetailsPanel`，可单独构建）和其逻辑 mixin（另有 `layers.py`、`booleans.py`）；`ConfigBuilderPage` 只保存共享状态（文档与模型）、组合这些控件并做跨编辑器协调，通过 `_adopt` 把各控件挂到页面属性上（重名即报错）。标签页的构建顺序决定共用控件的最终位置（布尔表在“Boolean Ops”、3D 消息框在“Messages and files”），改顺序即改界面。`_connect_signals` 按原顺序调用各模块的连接函数，同一信号的槽按此顺序执行。主窗口行为在 `window/`（shell、project、run、content 四个 mixin），`main_window.py` 只剩构造、信号连接和关闭；测试替换模块函数时要替换其所在模块（例如 `window.run.create_run_package`）。新控件属性名在整页内必须唯一（`add_volume_button` 曾被材料和几何两处共用）。专项 `smoke_config_editors.py`。

本文件适用于 gui/。GUI 是 PySide6 外部运行器和配置编辑器，后端 C++/Geant4 的实际实现仍是功能支持的唯一依据。

## 1. 分层和数据流

- g4usim_gui/widgets/ 负责页面、信号和用户交互；不要把后端配置语义、文件解析或大量业务校验继续堆进单个页面。
- models/、editors/ 保存可序列化的编辑状态；parsers/ 读取现有配置；validators/ 做 GUI 侧早期提示；writers/ 生成运行包；core/runner.py 只负责进程生命周期、日志和状态。
- 推荐的数据流是“源文件解析 → 编辑模型 → GUI 校验 → writer 生成运行包 → 后端再次校验/运行”。GUI 校验永远不能替代 C++ 后端校验。
- 源 materials.ini、geometry.ini 不得被编辑器直接覆盖。编辑结果写入独立 run package，并在报告中记录 copied 或 generated 来源。
- 项目 JSON schema 当前为 G4UniversalSimProject version 6。`runInputMode` 只保存 `generated`/`external` 机器值；旧项目缺少该字段时，有 config/macro 路径迁移为 `external`，否则迁移为 `generated`。修改字段必须增加读取兼容或迁移测试，不能静默丢弃旧项目状态。

## 2. 后端能力边界

- 每个 GUI 控件必须有明确的后端映射：配置 section/key 或 macro 命令、单位、默认值、校验、writer 输出和至少一个 smoke 断言。
- 后端未实现的功能不得出现在“可运行/已支持”列表中。若需要保留设计入口，必须同时显示“预览”“实验”或“不可用”，在 validator 中阻止生成可运行配置，并在 validation report 中说明原因。
- 解析到但后端会忽略、空实现、占位模板或只用于预览的字段，不得被 writer 静默写出并宣称生效。未知字段要么原样保留并标记未编辑，要么明确提示会被丢弃后再由用户确认。
- 当前 GUI 可生成的后端子集以 writers/main_ini_writer.py、writers/geometry_ini_writer.py 和 editors/source_physics_scoring_model.py 的真实逻辑为准；不要只根据 combobox 的选项扩展支持矩阵。
- `trd` 普通 hierarchical 体积已在 B3 工作区候选中通过五参数表格编辑、writer 往返、GUI package 和真实后端测试；boolean tool 的 `trd` 及 `trap`、GDML、STL、高级 GPS 分布、手动物理模块、biasing 规则、LET 等能力仍须等待各自后端和测试闭环后再开放生成。Dose 与 Fluence 仅开放实验性敏感体计分子集。
- 3D 预览永远不是 Geant4 几何真值；唯一例外是路线图 A5 的“显示后端几何”，它显示后端 `/AIHL/geometry/exportMesh` 写出的 Geant4 实际网格（`preview3d/backend_mesh.py`；G1 起由 `preview3d/backend_geometry_controller.py` 运行，一次一个导出、忙时只保留最新请求、按 `backend_inputs.GeometryInputs.key` 缓存；generated 模式不需运行包，输入规则见 `preview3d/backend_inputs.py`：未编辑文件原地使用以保持 STL/GDML 相对路径，编辑过的须通过编辑器校验），状态栏与消息须注明来源，不得把编辑器近似预览称为后端几何。replica/parameterised 放置在 validator 中只警告（后端支持、GUI 不可编辑），`assembly` 仍阻断。预览不能修改后端配置语义；缺少 PyVista 或遇到不支持 shape 时应显示降级原因。
- 预览读取 `tubs` 时必须保留内半径；除已验证的 hierarchical 普通体积 `trd` 五字段外，读取后端已支持但 GUI writer 尚未开放的 shape-specific 字段时，只能作为只读预览数据使用，不得借此扩大可生成白名单。

## 3. PySide6 约束

- 使用 PySide6 的信号、槽、模型和 Qt 生命周期；长时间运行的后端或合并任务不得阻塞 Qt 主线程。
- QProcess 的 stdout、stderr、退出码、终止/强制结束和日志文件必须保持可观察；不能吞掉用户需要诊断的错误。
- 页面之间通过项目模型和明确的 signal 同步，不要依赖控件当前文本作为唯一状态来源。编辑后必须更新 dirty 状态，生成包前再次从模型读取。
- Project 页更新必须原位应用到现有 `G4USimProject`，不得新建对象而丢失 geometry/source/physics/scoring editor、pathSettings 或 geometrySettings。新项目默认以 Configuration 页为运行来源；generated 模式的 Run 必须先完整校验和生成新 package，external 模式只传递非空的 config/macro 路径。
- generated package 只在当前配置快照下有效。材料、几何、Source、Physics、Scoring、运行参数、output 或 runs root 变化后必须标记 stale；预览不得继续展示旧包为可运行命令，下一次 Run 必须重新生成。
- C0A 的配置检查与实际启动检查分开：新 generated 项目允许空 config/macro，但 Runner 实际启动要求两者都是现存文件；external 至少提供一个文件。无效模式和目录输入必须拒绝，已有进程运行时不得再次生成 package。专项 `smoke_run_input_modes.py` 设置 `G4USIM_EXE` 后必须覆盖 GUI Run → package → QProcess → 摘要中的实际事件。
- C0B 联合入口现为 Inspect inputs / `--inspect-run`：用实际 Configure 和 macro preflight 得到 macro 执行前配置及来源，外部 Run 自动先查询再启动；失败、输入变化或新版查询接口不可用时均不启动。GUI 不复制 macro parser，不根据计划判定运行成功；新版后端是此入口的前置条件。专项必须覆盖 config-only、macro-only、中文路径和 CLI 冲突阻断，等待 QProcess 时使用 `QProcess.NotRunning`，不得用整数 0 比较 PySide6 枚举。
- C4 工作区候选使用 `core/run_result.py` 一处判定 Runner 与历史状态：成功要求正常退出、本次新摘要、后端 completed、macro 完成、至少一个 run，且逐 run 计划/完成事件一致并与摘要总数相符。退出码 0 的 dry-run、interactive_no_run、no_run、旧/缺失摘要不得显示模拟成功；终止/kill、crash、摘要写入失败分别保留原因。`run_status.json` 的 `resultVersion=1` 和摘要指纹供历史页复核，不得只根据状态字符串或摘要文件存在推断成功。
- E 工作区候选确认 GUI generated 模式没有 process-level biasing 规则编辑器；仅启用 physics hook 会被校验阻断，不得生成一个表面上“启用偏置”而实际无规则的包。external 模式仅在 batch 运行时保留显式配置/macro 的后端校验入口；后端目前拒绝 `--ui` 与启用偏置的配置或偏置修改 macro 组合。运行摘要的 `biasing_process_match_status=validated` 不能当作实际偏置效果或 M2 物理验证。
- 文件路径使用 pathlib.Path，生成文件统一 UTF-8 和 LF 换行；Windows 路径不得手工拼接成只适用于单一平台的字符串。
- 运行包生成失败必须保留清晰的字段/文件上下文；不要用 except Exception 把后端契约错误改写成“生成成功”。

## 4. 国际化约束

- 所有面向用户的标题、按钮、提示、校验错误、状态、日志解释和菜单文本必须使用可翻译的消息键；不得在新代码中继续散落硬编码英文或中文显示文本。
- 使用 Qt 的翻译机制（例如 QTranslator 与 QCoreApplication.translate）或项目统一封装；翻译资源、默认语言、运行时切换、持久化和缺失翻译行为必须一并设计。
- 代码标识符、Geant4 命令、INI section/key、输出列名、文件名和外部错误中的原始 token 保持原样；可以在旁边提供中文解释，但不能翻译接口本身。
- 带数值、路径、文件名和后端错误的消息必须支持参数化，不能通过字符串拼接制造不可翻译的句子。
- 当前 GUI 通过 `core/i18n.py` 提供中文/英文运行时切换和 `QSettings` 持久化，覆盖主框架、核心页面静态控件及关键动态状态。新增用户可见文本必须进入集中词典或参数化翻译封装；原始后端诊断、配置 token 和尚未收录的专业文本保持英文，不得用不完整翻译改变其语义。若后续迁移到 `QTranslator`/`.qm`，必须保留现有语言代码和偏好键的兼容性。
- 几何模式等业务选择器必须使用“本地化显示名 + 稳定机器值”：显示文本进入翻译层，项目和 writer 使用 `currentData()`/`findData()`；不得把 `currentText()` 写入 `geometry.template`。旧模板 token 只能作为显式兼容项加载，不得随语言切换改变。

## 5. 主题和可访问性约束

- 主题由集中式 palette/style token 管理，至少规划浅色、深色和跟随系统三种模式；业务控件不得各自硬编码背景色、文字色或状态色。
- 绿色、橙色、红色只能表达成功、警告、错误等语义，并且必须同时有文字/图标信息，不能只依赖颜色。
- 主题切换后要覆盖表格、日志、原始配置、预览、禁用控件、选中状态和错误状态；检查对比度、字体缩放和高 DPI 布局。
- 主题和语言偏好应通过统一配置持久化（例如 QSettings 封装），不能写入项目 JSON，除非它们确实属于项目复现所需状态。
- 当前工作区 `core/theme.py` 已集中提供浅色/深色/系统主题与偏好持久化；该 GUI 展示改动尚未提交，人工视觉、高 DPI 和可访问性检查尚未完成，不能据此宣称 M3 完成。

## 6. 配置编辑器约束

- 编辑器必须区分“后端支持”“GUI 可编辑”“仅预览”三种状态。状态要在控件、验证消息、原始文件/生成文件预览和中文文档中一致。
- 读取配置时保留 section/key、原始值、来源文件和未知字段信息；重新生成时不能无提示地改变单位、默认值、布尔语义、字段顺序含义或删掉用户配置。
- 材料 parser 的源 schema 错误必须与编辑语义错误分开保存；重复校验和编辑不得清空源错误，公共 errors 视图要稳定合并并去重。只要源错误仍存在，生成预览和 run package 都必须保持不可用，不能通过丢弃未知字段表现为已经修复。
- GUI 工作区诊断计数不可把几何 parser 消息与已合入 GeometryDocument 的源消息再次相加；材料源 warning 仍需由 parser 单独计入，因为 MaterialDocument 的语义校验会重建 warnings。生成前验证若编辑模型对应源文件在磁盘上的内容或路径已经变化，应要求重新加载，不可用旧模型继续生成包。
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
- parser 发现当前模型不能无损保存的字段时必须设置 round-trip blocker。B3 工作区子链路已对 hierarchical 普通体积的 `vis.color/alpha/visible/wireframe`、`cut.gamma/e-/e+/proton` 和 `trd` 五个长度字段，以及 layered 的 `auto_stack`、position/rotation、已知 vis/cut 和 canonical metadata 做值保留、校验和 writer 往返；layered 的 vis/cut/metadata 暂无独立 GUI 编辑控件。未知 `vis.*`/`cut.*`、显式 placement、其他 shape-specific 属性、userProperties 或 boolean tool properties 仍须阻断。editable writer 和 generated package 对剩余 blocker 必须拒绝；用户只能显式选择原始 geometry 文件复制模式，并在报告中标明编辑器验证已绕过。
- Run 不得为了通过 generated package 校验而自动打开 `source_copy_mode`。只有用户显式勾选后才可逐字节复制源 geometry；复制模式不等于编辑器验证通过。

## 9. M0-3B2B2 来源诊断对齐

- `parse_geometry(path, template_name)` 在调用方已知模板时必须优先使用显式模板，不得依赖文本启发式；源 warning、legacy metadata blocker 和 source-copy 状态必须跨重复 validate 保留。
- canonical `metadata.<非空名称>` 在可无损保存的编辑模式中不产生 blocker；legacy 无前缀属性只诊断和保留，不自动改名或删除。array/shielding 仍为 preview-only。
- metadata 编辑框只允许 `metadata.<非空名称>`。runtime 字段和旧式无前缀未知字段不得从 metadata 写出；legacy 字段本阶段只保留并阻断，不能自动改名或删除。
- B3 工作区的后端 `version = 2` 严格几何标记须由 parser、`GeometryDocument`、项目快照和 writer 保留，不得误报为 legacy metadata 或静默删去。已验证的 hierarchical 编辑子集可写回严格标记；其他未知字段与不支持的模式仍保持 round-trip blocker 或 preview-only，source-copy 必须由用户显式选择。
- 即使 section 为空，未知 section 也不能在 editable writer 中静默消失；`[layer.*]` 必须出现在 `[layers]/names`。重复 section 或大小写归一后重复的 key 也须设置 round-trip blocker，用户应先消歧并重新加载源文件。
