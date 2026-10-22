from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QLocale, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QTabWidget,
    QWidget,
)


LanguageCode = Literal["en", "zh_CN"]


ZH_CN: dict[str, str] = {
    "Export Dose JSON...": "导出 Dose JSON...",
    "Export Fluence JSON...": "导出 Fluence JSON...",
    "Cancel export": "取消导出",
    "Select an output directory to export results.": "选择模拟输出目录后可导出结果。",
    "JSON export process output and warnings": "JSON 导出进程输出与警告",
    "JSON Exports (M5 prototype)": "JSON 导出（M5 原型）",
    "JSON export reads discovered CSV files only; verify run_summary.txt status, event counts, worker files and warnings. Dose/Fluence are experimental.": "JSON 仅汇总已发现的 CSV；请核对 run_summary.txt 状态、事件数、worker 文件及警告。Dose/Fluence 仍为实验性。",
    "Choose a new JSON result file": "选择新的 JSON 结果文件",
    "Select an existing output directory first.": "请先选择已有的模拟输出目录。",
    "An output extension is already running.": "已有输出扩展正在运行。",
    "JSON export rejected: {error}": "JSON 导出已拒绝：{error}",
    "Exporting {extension}...": "正在导出 {extension}...",
    "{extension}: {state}": "{extension}：{state}",
    "Enable sensitive-volume Dose (Gy, prototype)": "启用敏感体吸收剂量 Dose (Gy，原型)",
    "Enable track-length Fluence (mm^-2, prototype)": "启用径迹长度 Fluence (mm^-2，原型)",
    "Dose and Fluence are experimental sensitive-volume scorers; LET remains unavailable.": "Dose 与 Fluence 均为实验性敏感体计分；LET 仍不可用。",
    "Dose sums energy deposition in sensitive volumes; results are per run and thread. LET/Fluence remain unavailable.": "Dose 仅累计敏感体中的能量沉积；原始 CSV 按 run 和线程分别保存。Fluence 现有实验性原型，LET 仍不可用。",
    "Unsupported run input mode.": "运行来源模式无效。",
    "Generate a run package before starting generated input.": "请先生成运行包，再启动配置页生成模式。",
    "A run is already active.": "已有仿真正在运行。",
    "Macro path is not a file: {path}": "macro 路径不是文件：{path}",
    "Config path is not a file: {path}": "主配置路径不是文件：{path}",
    "Materials source changed since the editor was loaded; reload materials before generating a package.": "材料源文件在加载到编辑器后已变化；生成运行包前请重新加载材料。",
    "Geometry source changed since the editor was loaded; reload geometry before generating a package.": "几何源文件在加载到编辑器后已变化；生成运行包前请重新加载几何。",
    # Application shell and menus.
    "File": "文件",
    "View": "视图",
    "Theme": "主题",
    "Language": "语言",
    "Light": "浅色",
    "Dark": "深色",
    "System": "跟随系统",
    "Chinese": "中文",
    "English": "English",
    "Open Project...": "打开项目...",
    "Save Project": "保存项目",
    "Save Project As...": "项目另存为...",
    "Recent Projects": "最近项目",
    "Clear Recent Projects": "清除最近项目",
    "Exit": "退出",
    "<none>": "<无>",
    "SIMULATION WORKSPACE": "仿真工作区",
    "WORKFLOW": "工作流程",
    "Desktop GUI\nGeant4 workflow": "桌面 GUI\nGeant4 工作流程",
    "Project": "项目",
    "Configuration": "配置",
    "Run Console": "运行控制台",
    "Results": "结果",
    "Run History": "运行历史",
    "Connect the executable, workspace and run defaults.": "连接可执行程序、工作区和运行默认值。",
    "Compose supported simulation inputs and inspect the geometry preview.": "编排已支持的仿真输入并检查几何预览。",
    "Validate the launch command and monitor backend execution.": "校验启动命令并监控后端执行。",
    "Review summaries, logs and generated output files.": "查看运行摘要、日志和生成的输出文件。",
    "Browse previous packages and restore reproducible snapshots.": "浏览历史运行包并恢复可复现快照。",
    "Project: demo": "项目：demo",
    "Project: {name}": "项目：{name}",
    "untitled": "未命名",
    "Idle": "空闲",
    "Starting": "正在启动",
    "Running": "运行中",
    "Not running": "未运行",
    "Stopped": "已停止",
    "Killed": "已强制结束",
    "Error": "错误",
    "ERROR": "错误",
    "WARN": "警告",
    "OK": "正常",
    "Ready": "就绪",
    "Completed": "已完成",
    "Failed": "失败",
    "success": "模拟成功",
    "dry_run": "仅检查（dry-run）",
    "interactive_no_run": "交互结束但未运行",
    "no_run": "未执行模拟",
    "failed": "运行失败",
    "incomplete": "结果未证实",
    "stopped": "用户停止",
    "killed": "强制结束",
    "Run result: {state}. {reason}": "运行结果：{state}。{reason}",
    "Result: {state}": "结果：{state}",
    "User requested process termination.": "用户请求结束进程。",
    "Process crashed or failed to start.": "进程崩溃或未能启动。",
    "Process exit status is unavailable.": "无法取得进程退出状态。",
    "Process exited with nonzero code.": "进程以非零退出码结束。",
    "No fresh run summary was produced by this process.": "本次进程未生成新的运行摘要。",
    "Run summary is missing or unreadable.": "运行摘要缺失或无法读取。",
    "Run summary lacks valid lifecycle counts or exit status.": "运行摘要缺少有效的生命周期计数或退出状态。",
    "Run summary conflicts with process exit or contains invalid counts.": "运行摘要与进程退出状态冲突，或计数无效。",
    "Run summary write completion is not confirmed.": "运行摘要写入未被确认为完成。",
    "Backend or macro reported failure.": "后端或 macro 报告失败。",
    "Configuration checked; no simulation run was requested.": "配置检查完成；未请求模拟运行。",
    "Interactive session ended without a run.": "交互会话结束，但未执行模拟。",
    "Backend or macro status is not a completed state.": "后端或 macro 状态未完成。",
    "Process completed but no Geant4 run occurred.": "进程结束，但没有发生 Geant4 run。",
    "Run events were not confirmed complete.": "无法确认运行事件全部完成。",
    "Events completed as planned.": "事件已按计划完成。",
    "Run result is unavailable.": "运行结果不可用。",
    "Biasing hook (external input only)": "偏置物理钩子（仅外部输入）",
    "Generated packages cannot configure biasing rules. Use external config/macro for process-level biasing.":
        "生成包尚不能配置偏置规则；process-level biasing 请使用外部配置或 macro。",
    "Biasing rules cannot be edited or generated here. Disable the hook for generated packages, or use external config/macro with explicit process-level rules.":
        "此处无法编辑或生成偏置规则。生成包请关闭物理钩子，或使用含显式 process-level 规则的外部配置或 macro。",
    "Choose light, dark or system appearance": "选择浅色、深色或跟随系统外观",
    "Choose the interface language": "选择界面语言",
    "Unsupported production cut field '{field}'.": "不支持的 production cut 字段 '{field}'。",
    "{field} requires a non-empty region in the same volume.": "{field} 要求同一体积中设置非空 region。",
    "{field} must be a positive length.": "{field} 必须是正长度。",
    "Unsupported visual field '{field}'.": "不支持的可视化字段 '{field}'。",
    "vis.alpha must be between 0 and 1.": "vis.alpha 必须在 0 到 1 之间。",
    "vis.alpha must be numeric.": "vis.alpha 必须是数值。",
    "{field} must be a boolean value.": "{field} 必须是布尔值。",
    "vis.color must be a color supported by the backend.": "vis.color 必须是后端支持的颜色。",
    "trd uses dx1, dx2, dy1, dy2, dz instead of size/parameters.": "trd 使用 dx1、dx2、dy1、dy2、dz，不使用 size/parameters。",
    "trd {field} must be a positive length.": "trd {field} 必须是正长度。",
    "Unsupported trd shape field '{field}'.": "不支持的 trd 形状字段 '{field}'。",
    "Shape-specific fields are present but the selected shape is not trd.": "存在形状专用字段，但所选形状不是 trd。",
    "Unsupported shape '{shape}'. Supported in the editor: box, tubs, sphere, orb, cone, trd.": "不支持的形状 '{shape}'。编辑器当前支持 box、tubs、sphere、orb、cone、trd。",

    # Common controls.
    "Browse": "浏览",
    "Refresh": "刷新",
    "Validate": "校验",
    "Duplicate": "复制",
    "Delete": "删除",
    "Enabled": "启用",
    "Status": "状态",
    "Search": "搜索",
    "Open": "打开",
    "Preview": "预览",
    "Messages": "消息",
    "Source": "源",
    "Physics": "物理",
    "Scoring": "计分",
    "Geometry": "几何",
    "Materials": "材料",
    "Preset": "预设",
    "Particle": "粒子",
    "Energy": "能量",
    "Position": "位置",
    "Direction": "方向",
    "Clean": "未修改",
    "Dirty": "已修改",
    "editable": "可编辑",
    "preview": "预览",
    "missing": "缺失",
    "not set": "未设置",
    "ok": "正常",
    "creatable": "可创建",
    "missing parent": "父目录缺失",
    "not set/missing": "未设置或缺失",

    # Project page.
    "Save project": "保存项目",
    "Load project": "加载项目",
    "Project Setup": "项目设置",
    "Current Run Defaults": "当前运行默认值",
    "Run input mode": "运行来源",
    "Generated from Configuration": "由配置页生成",
    "Use external files": "使用外部文件",
    "Generated automatically at run time": "运行时自动生成",
    "Project name": "项目名称",
    "G4UniversalSim executable": "G4UniversalSim 可执行程序",
    "Workspace root": "工作区根目录",
    "Runs root": "运行包根目录",
    "Config file": "配置文件",
    "Macro file": "Macro 文件",
    "Output directory": "输出目录",
    "Threads": "线程数",
    "Seed": "随机种子",
    "Run name": "运行名称",
    "Step 1: choose executable. Step 2: choose config/macro here or generate a run package in Config Builder. Project JSON stores GUI state only; simulation inputs remain config and macro files.":
        "第 1 步：选择可执行程序。第 2 步：在此选择配置和 macro，或在配置页生成运行包。项目 JSON 只保存 GUI 状态；仿真输入仍由配置文件和 macro 提供。",
    "Choose the executable, then use Configuration-generated input (default) or external config/macro files. Generated input is validated and rebuilt when Run is clicked.":
        "选择可执行程序，然后使用配置页生成的输入（默认）或外部 config/macro 文件。点击 Run 时会校验并重新生成已失效的运行包。",

    # Configuration workspace.
    "Setup generates a reproducible run package. Material and geometry previews are read-only in this round.":
        "此处生成可复现的运行包。材料和几何源文件不会被直接覆盖。",
    "Run": "运行",
    "Input files": "输入文件",
    "Actions": "操作",
    "Materials config": "材料配置",
    "Geometry config": "几何配置",
    "Geometry template": "几何模板",
    "Layered Model": "快速分层模型",
    "Hierarchical Model": "通用层级模型",
    "External Geometry Import (Planned)": "外部几何导入（规划中）",
    "Single Target Preset (Legacy)": "单靶体预设（兼容）",
    "Regular Array Preset (Legacy)": "规则阵列预设（兼容）",
    "Shielding Preset (Legacy)": "屏蔽体预设（兼容）",
    "Hierarchical Boolean Alias (Legacy)": "层级布尔别名（兼容）",
    "Compatibility mode: {token}": "兼容模式：{token}",
    "Reload materials": "重新加载材料",
    "Reload geometry": "重新加载几何",
    "Check overlaps": "检查重叠",
    "Dry run": "仅检查",
    "BeamOn": "事件数",
    "Generate Package": "生成运行包",
    "Generate and Run": "生成并运行",
    "Generated package: <none>": "已生成运行包：<无>",
    "Materials Editor": "材料编辑器",
    "Load from selected materials.ini": "从所选 materials.ini 加载",
    "Add NIST": "添加 NIST 材料",
    "Add mass_fraction": "添加质量分数材料",
    "Add volume_fraction": "添加体积分数材料",
    "Add atom_count": "添加原子计数材料",
    "Validate Materials": "校验材料",
    "Revert to source": "恢复源文件状态",
    "Selected material": "所选材料",
    "Name": "名称",
    "Mode": "模式",
    "Density": "密度",
    "Components": "组分",
    "Boolean Ops": "布尔运算",
    "3D Preview": "3D 预览",
    "Run Config": "运行配置",
    "Raw Files": "原始文件",
    "NIST Quick List": "NIST 快速列表",
    "Refresh Preview": "刷新预览",
    "Reset Camera": "重置相机",
    "Show Backend Geometry": "显示后端几何",
    "Run the backend with /run/initialize only and show the geometry Geant4 actually built "
    "(every replica and parameterised copy, all solids).": "仅以 /run/initialize 运行后端，显示 Geant4 实际构建的几何（包括每个 replica 与 parameterised 副本及全部 solid）。",
    "Backend geometry: exporting...": "后端几何：正在导出……",
    "Backend geometry: ERROR": "后端几何：错误",
    "Backend geometry: {count} volume copies from Geant4.": "后端几何：Geant4 构建的 {count} 个体积副本。",
    "Backend geometry render failed: {reason}": "后端几何渲染失败：{reason}",
    "Backend geometry export failed: {reason}": "后端几何导出失败：{reason}",
    "Backend geometry needs a main INI: choose one in external mode or generate the run package first.": "显示后端几何需要主 INI：请在 external 模式下选择，或先生成运行包。",
    "Backend executable not found.": "未找到后端可执行文件。",
    "This is the geometry built by the Geant4 backend, not the editor approximation.": "这是 Geant4 后端实际构建的几何，而不是编辑器的近似预览。",
    "Source: {path}": "来源：{path}",
    "Solids: {solids}": "Solid：{solids}",
    "Show Source": "显示粒子源",
    "Show Labels": "显示标签",
    "3D preview messages": "3D 预览消息",
    "Simple Box": "简单盒体",
    "Layered Device": "分层器件",
    "Hierarchical Volumes": "层级体积",
    "Boolean Operations": "布尔运算",
    "Preview / Unsupported Template": "预览 / 不支持的模板",
    "Add Volume": "添加体积",
    "Duplicate Volume": "复制体积",
    "Delete Volume": "删除体积",
    "Move Up": "上移",
    "Move Down": "下移",
    "Validate Geometry": "校验几何",
    "Revert Geometry": "恢复几何",
    "Add Boolean Operation": "添加布尔运算",
    "Duplicate Operation": "复制运算",
    "Delete Operation": "删除运算",
    "Validate Boolean Ops": "校验布尔运算",
    "Add Layer": "添加层",
    "Selected layer": "所选层",
    "Layer validation": "层校验",
    "Validation messages": "校验消息",
    "Validation result": "校验结果",
    "Materials messages": "材料消息",
    "Geometry messages": "几何消息",
    "3D Preview messages": "3D 预览消息",
    "3D Preview: OK": "3D 预览：正常",
    "3D Preview: {status} | volumes={volumes}": "3D 预览：{status} | 体积数={volumes}",
    "Rendered with {errors} error(s) and {warnings} warning(s).": "已渲染，包含 {errors} 个错误和 {warnings} 个警告。",
    "Rendered with {warnings} warning(s).": "已渲染，包含 {warnings} 个警告。",
    "Source materials raw": "材料源文件",
    "Generated materials preview": "生成材料预览",
    "Generated geometry preview": "生成几何预览",
    "Generated main.ini preview": "生成 main.ini 预览",
    "Geometry raw": "几何源文件",

    # Run console.
    "Build the command first when paths change. Validation errors usually point back to the Project page.":
        "路径改变后请先构建命令。校验错误通常需要返回项目页处理。",
    "Command preview": "命令预览",
    "Build command": "构建命令",
    "Inspect macro": "检查 macro",
    "Inspect inputs": "检查运行输入",
    "Inspecting inputs with backend preflight...": "正在使用后端预检器检查运行输入...",
    "Input inspection failed: {reason}": "运行输入检查失败：{reason}",
    "Run plan is stale; inputs changed.": "运行前清单已失效：输入发生变化。",
    "Run plan": "运行前清单",
    "Input inspection is available in external mode.": "外部运行来源模式可检查运行输入。",
    "Configuration before macro execution; runtime results remain unknown.": "以下为 macro 执行前的配置；实际运行结果尚未确定。",
    "Initial configuration and sources:": "初始配置及来源：",
    "Macro commands may change configuration after initialization.": "以下 macro 命令可能在初始化后更改配置。",
    "Backend diagnostics:": "后端诊断：",
    "No beamOn command was found; no macro events are planned.": "未发现 beamOn 命令；macro 没有计划执行事件。",
    "Macro plan": "macro 运行前计划",
    "Macro inspection is available for external input with an explicit macro file.": "仅外部运行来源且显式指定 macro 文件时可检查运行前计划。",
    "Inspecting macro with backend preflight...": "正在使用后端预检器检查 macro...",
    "Macro inspection failed: {reason}": "macro 检查失败：{reason}",
    "Macro plan is stale; inputs changed during inspection.": "macro 计划已失效：检查过程中输入发生变化。",
    "Static macro plan only; main config and runtime command success are not evaluated.": "仅为 macro 静态计划；尚未评估主配置和命令运行结果。",
    "Macro file: {path}": "macro 文件：{path}",
    "Expanded commands: {count}": "展开命令数：{count}",
    "Stop": "停止",
    "Kill": "强制结束",
    "Clear log": "清空日志",
    "Save logs": "保存日志",
    "State: Not running": "状态：未运行",
    "Exit code: -": "退出码：-",
    "Elapsed: 00:00:00": "耗时：00:00:00",
    "State: {state}": "状态：{state}",
    "Exit code: {code}": "退出码：{code}",
    "Elapsed: {elapsed}": "耗时：{elapsed}",
    "merged log": "合并日志",
    "Configuration changed; the run package will be regenerated at run time.":
        "配置已修改，运行时将重新生成 package。",

    # Results page.
    "Output directory: <none>": "输出目录：<无>",
    "Open package folder": "打开运行包目录",
    "Open output folder": "打开输出目录",
    "Overview": "概览",
    "Run Summary": "运行摘要",
    "CSV Preview": "CSV 预览",
    "Merge": "合并",
    "Logs": "日志",
    "Rows": "行数",
    "Refresh merge plan": "刷新合并计划",
    "Run selected merge": "执行所选合并",
    "Run all available merges": "执行全部可用合并",
    "Cancel merge": "取消合并",
    "Merge stdout/stderr": "合并标准输出/错误输出",

    # History page.
    "All": "全部",
    "Open runs root": "打开运行包根目录",
    "Load Snapshot into Project": "将快照加载到项目",
    "Open Package": "打开运行包",
    "Open Output": "打开输出",
    "Open Logs": "打开日志",
    "Open Config": "打开配置",
    "Open Macro": "打开 Macro",
    "Duplicate Package": "复制运行包",
    "Duplicate and Rerun": "复制并重新运行",
    "Select a run to view details, logs, output and rerun options.": "选择一次运行以查看详情、日志、输出和重新运行选项。",

    # Dynamic summaries. Technical values remain unchanged.
    "Executable: {status}": "可执行程序：{status}",
    "Config: {status}": "配置：{status}",
    "Macro: {status}": "Macro：{status}",
    "Output: {status}": "输出：{status}",
    "Workspace: {status}": "工作区：{status}",
    "Materials: {count} rows, {enabled} enabled | {errors} errors, {warnings} warnings | {state}":
        "材料：{count} 行，启用 {enabled} 行 | {errors} 个错误，{warnings} 个警告 | {state}",
    "Volumes: {count} rows, {enabled} enabled | {errors} errors, {warnings} warnings | {mode}":
        "体积：{count} 行，启用 {enabled} 行 | {errors} 个错误，{warnings} 个警告 | {mode}",
    "Boolean ops: {count} rows, {enabled} enabled | {errors} errors, {warnings} warnings | {mode}":
        "布尔运算：{count} 行，启用 {enabled} 行 | {errors} 个错误，{warnings} 个警告 | {mode}",
    "Materials: {materials} entries | Geometry: {volumes} volumes, {booleans} boolean ops | Messages: {errors} errors, {warnings} warnings | Materials: {material_state} | Geometry: {geometry_mode} {geometry_state} | Source: {source_status} | Physics: {physics} | Scoring: {scoring}":
        "材料：{materials} 项 | 几何：{volumes} 个体积，{booleans} 个布尔运算 | 消息：{errors} 个错误，{warnings} 个警告 | 材料：{material_state} | 几何：{geometry_mode} {geometry_state} | 源：{source_status} | 物理：{physics} | 计分：{scoring}",
}


def default_language() -> LanguageCode:
    return "zh_CN" if QLocale.system().language() == QLocale.Chinese else "en"


def normalize_language(value: object) -> LanguageCode:
    return "zh_CN" if str(value) == "zh_CN" else "en"


def set_application_language(app: QApplication, language: LanguageCode) -> None:
    app.setProperty("languageCode", language)


def current_language() -> LanguageCode:
    app = QApplication.instance()
    return normalize_language(app.property("languageCode") if app is not None else "en")


def ui_text(source: str, language: LanguageCode | None = None) -> str:
    active = language or current_language()
    return ZH_CN.get(source, source) if active == "zh_CN" else source


def ui_format(source: str, *, language: LanguageCode | None = None, **values: object) -> str:
    return ui_text(source, language).format(**values)


def apply_language(root: QWidget, language: LanguageCode) -> None:
    set_application_language(QApplication.instance(), language)
    objects: list[QObject] = [root, *root.findChildren(QObject)]
    for obj in objects:
        if isinstance(obj, QLabel):
            _translate_getter_setter(obj, "labelText", obj.text, obj.setText, language)
        elif isinstance(obj, QAbstractButton):
            _translate_getter_setter(obj, "buttonText", obj.text, obj.setText, language)
        if isinstance(obj, QGroupBox):
            _translate_getter_setter(obj, "groupTitle", obj.title, obj.setTitle, language)
        if isinstance(obj, QMenu):
            _translate_getter_setter(obj, "menuTitle", obj.title, obj.setTitle, language)
        if isinstance(obj, QAction):
            _translate_getter_setter(obj, "actionText", obj.text, obj.setText, language)
            _translate_getter_setter(obj, "actionTip", obj.toolTip, obj.setToolTip, language)
        if isinstance(obj, QWidget):
            _translate_getter_setter(obj, "toolTip", obj.toolTip, obj.setToolTip, language)
        if isinstance(obj, QLineEdit):
            _translate_getter_setter(
                obj,
                "placeholder",
                obj.placeholderText,
                obj.setPlaceholderText,
                language,
            )
        if isinstance(obj, QTabWidget):
            _translate_tabs(obj, language)


def _translate_getter_setter(obj: QObject, key: str, getter, setter, language: LanguageCode) -> None:
    source_key = f"i18nSource_{key}"
    source = obj.property(source_key)
    current = getter()
    if source is None:
        if current not in ZH_CN:
            return
        source = current
        obj.setProperty(source_key, source)
    setter(ui_text(str(source), language))


def _translate_tabs(tabs: QTabWidget, language: LanguageCode) -> None:
    sources = getattr(tabs, "_i18n_tab_sources", None)
    if sources is None or len(sources) != tabs.count():
        sources = [tabs.tabText(index) for index in range(tabs.count())]
        tabs._i18n_tab_sources = sources
    for index, source in enumerate(sources):
        tabs.setTabText(index, ui_text(source, language))
