from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui import __version__
from g4usim_gui.core import examples as gallery
from g4usim_gui.core import icons
from g4usim_gui.core import install_layout
from g4usim_gui.core import scan as parameter_scan
from g4usim_gui.core import wizard as simulation_wizard
from g4usim_gui.core.i18n import LanguageCode, apply_language, current_language, ui_format, ui_text
from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.core.theme import ThemeMode, apply_theme, current_colors
from g4usim_gui.history.run_history_store import add_recent_project, clear_recent_projects, get_recent_projects, load_state, save_state
from g4usim_gui.history.run_package_actions import duplicate_package
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.preview3d.backend_mesh import export_arguments, load_backend_mesh, write_export_macro
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.widgets.project_page import ProjectPage
from g4usim_gui.widgets.run_page import RunPage
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from g4usim_gui.widgets.scan_page import ScanPage
from g4usim_gui.widgets.start_page import StartPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("G4UniversalSim Runner")
        self.resize(1500, 950)
        self.setMinimumSize(1200, 760)

        self.project = self._default_project()
        self.project_file: Path | None = None
        self._generated_package_stale = True
        self._generated_package_dir = ""
        self.runner = G4USimRunner(self)
        self._macro_inspection = QProcess(self)
        self._geometry_export = QProcess(self)
        self._geometry_export.finished.connect(self._on_geometry_export_finished)
        self._geometry_export_dir: tempfile.TemporaryDirectory | None = None
        self._macro_inspection_snapshot: tuple[object, ...] | None = None
        self._pending_inspection_run = False
        self._macro_inspection.finished.connect(self._on_macro_inspection_finished)
        self._macro_inspection.errorOccurred.connect(self._on_macro_inspection_error)

        self.start_page = StartPage()
        self.project_page = ProjectPage()
        self.config_builder_page = ConfigBuilderPage()
        self.run_page = RunPage()
        self.output_page = OutputPage()
        self.run_history_page = RunHistoryPage()
        self.scan_page = ScanPage()
        self.scan_page.set_base_provider(self.scan_base)

        self._build_workspace_shell()
        self._apply_visual_roles()
        self._run_chip = ("Idle", "")

        self._connect_signals()
        self._create_menu()
        self._restore_app_state()
        self._set_project(self.project)
        self._set_language(current_language(), persist=False)
        self.statusBar().showMessage(ui_text("Ready"), 5000)

    def _build_workspace_shell(self) -> None:
        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 18, 14, 14)
        sidebar_layout.setSpacing(4)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        self.brand_logo = QLabel()
        self.brand_logo.setObjectName("brandLogo")
        self.brand_logo.setFixedSize(30, 30)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("G4UniversalSim")
        brand.setObjectName("brandMark")
        brand_caption = QLabel(self.tr("Simulation workspace"))
        brand_caption.setObjectName("brandCaption")
        brand_text.addWidget(brand)
        brand_text.addWidget(brand_caption)
        brand_row.addWidget(self.brand_logo)
        brand_row.addLayout(brand_text, 1)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(22)

        section_label = QLabel(self.tr("WORKFLOW"))
        section_label.setObjectName("sidebarSection")
        sidebar_layout.addWidget(section_label)

        page_specs = [
            (
                self.start_page,
                self.tr("Start"),
                self.tr("Start a new simulation, reopen a project or explore an example."),
                "start",
            ),
            (
                self.project_page,
                self.tr("Project"),
                self.tr("Connect the executable, workspace and run defaults."),
                "project",
            ),
            (
                self.config_builder_page,
                self.tr("Configuration"),
                self.tr("Compose supported simulation inputs and inspect the geometry preview."),
                "configuration",
            ),
            (
                self.run_page,
                self.tr("Run Console"),
                self.tr("Validate the launch command and monitor backend execution."),
                "run",
            ),
            (
                self.output_page,
                self.tr("Results"),
                self.tr("Review summaries, logs and generated output files."),
                "results",
            ),
            (
                self.run_history_page,
                self.tr("Run History"),
                self.tr("Browse previous packages and restore reproducible snapshots."),
                "history",
            ),
            (
                self.scan_page,
                self.tr("Parameter Scans"),
                self.tr("Vary one setting over several values, run every point and compare the results."),
                "scans",
            ),
        ]
        self._page_specs = page_specs
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: list[QToolButton] = []
        for index, (_page, title, _subtitle, _icon) in enumerate(page_specs):
            button = QToolButton()
            button.setText(title)
            button.setIconSize(QSize(18, 18))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setProperty("navButton", True)
            button.setMinimumHeight(38)
            button.setAccessibleName(title)
            sidebar_layout.addWidget(button)
            self._nav_group.addButton(button, index)
            self._nav_buttons.append(button)
        self._nav_buttons[0].setChecked(True)
        sidebar_layout.addStretch(1)

        footer = QLabel(f"G4UniversalSim {__version__}")
        footer.setObjectName("sidebarFooter")
        footer.setToolTip(ui_format("GUI version {version}", version=__version__))
        sidebar_layout.addWidget(footer)

        content = QWidget()
        content.setObjectName("contentHost")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        page_header = QFrame()
        page_header.setObjectName("pageHeader")
        page_header.setFixedHeight(66)
        header_layout = QHBoxLayout(page_header)
        header_layout.setContentsMargins(24, 10, 16, 10)
        header_layout.setSpacing(8)

        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(1)
        self.page_title = QLabel(page_specs[0][1])
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel(page_specs[0][2])
        self.page_subtitle.setObjectName("pageSubtitle")
        heading_layout.addWidget(self.page_title)
        heading_layout.addWidget(self.page_subtitle)
        header_layout.addLayout(heading_layout, 1)

        self.project_context = QLabel(self.tr("Project: demo"))
        self.project_context.setProperty("uiRole", "contextChip")
        self.run_context = QLabel(self.tr("Idle"))
        self.run_context.setProperty("uiRole", "statusChip")
        header_layout.addWidget(self.project_context, 0, Qt.AlignVCenter)
        header_layout.addWidget(self.run_context, 0, Qt.AlignVCenter)
        header_layout.addSpacing(6)

        # icon-only: the tooltip and accessible name carry the text
        self.theme_button = QToolButton()
        self.theme_button.setText(self.tr("Theme"))
        self.theme_button.setIconSize(QSize(20, 20))
        self.theme_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.theme_button.setPopupMode(QToolButton.InstantPopup)
        self.theme_button.setProperty("iconButton", True)
        self.theme_button.setToolTip(self.tr("Choose light, dark or system appearance"))
        self.theme_button.setAccessibleName(self.tr("Theme"))
        header_layout.addWidget(self.theme_button)

        self.language_button = QToolButton()
        self.language_button.setText(self.tr("Language"))
        self.language_button.setIconSize(QSize(20, 20))
        self.language_button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.language_button.setPopupMode(QToolButton.InstantPopup)
        self.language_button.setProperty("iconButton", True)
        self.language_button.setToolTip(self.tr("Choose the interface language"))
        self.language_button.setAccessibleName(self.tr("Language"))
        header_layout.addWidget(self.language_button)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageViewport")
        for page, _title, _subtitle, _icon in page_specs:
            self.page_stack.addWidget(page)

        content_layout.addWidget(page_header)
        content_layout.addWidget(self.page_stack, 1)
        shell_layout.addWidget(sidebar)
        shell_layout.addWidget(content, 1)
        self.setCentralWidget(shell)

        # Keep the historical attribute available to internal navigation helpers.
        self.tabs = self.page_stack
        self._nav_group.idClicked.connect(self.page_stack.setCurrentIndex)
        self.page_stack.currentChanged.connect(self._on_page_changed)
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        """Line icons in the current theme's colours (re-rendered on theme change)."""
        colors = current_colors()
        self.brand_logo.setPixmap(icons.pixmap("logo", colors.accent, 30))
        for button, (_page, _title, _subtitle, name) in zip(self._nav_buttons, self._page_specs):
            button.setIcon(icons.icon(name, colors.sidebar_muted, 18, active=colors.sidebar_text,
                                      background=colors.sidebar))
        self.theme_button.setIcon(icons.icon("theme", colors.text_muted, 20, active=colors.text))
        self.language_button.setIcon(icons.icon("language", colors.text_muted, 20, active=colors.text))

    def _apply_visual_roles(self) -> None:
        self.config_builder_page.generate_run_button.setProperty("buttonRole", "primary")
        self.run_page.run_button.setProperty("buttonRole", "primary")
        self.run_page.stop_button.setProperty("buttonRole", "danger")
        self.run_page.kill_button.setProperty("buttonRole", "danger")
        self.project_page.save_button.setProperty("buttonRole", "primary")
        self.project_page.status_summary.setProperty("uiRole", "contextChip")

    def _on_page_changed(self, index: int) -> None:
        if not 0 <= index < len(self._page_specs):
            return
        _page, title, subtitle, _icon = self._page_specs[index]
        self.page_title.setText(ui_text(title))
        self.page_subtitle.setText(ui_text(subtitle))
        self._nav_buttons[index].setChecked(True)

    def _default_project(self) -> G4USimProject:
        root = install_layout.application_root()
        runs_root = install_layout.default_runs_root()
        output = runs_root / "demo" / "output"
        project = G4USimProject(
            projectName="demo",
            runInputMode="generated",
            workspaceRoot=str(root),
            configPath="",
            macroPath="",
            outputDir=str(output),
            runsRoot=str(runs_root),
            threads=1,
            runName="demo_run",
        )
        executable = install_layout.default_backend_executable()
        project.executable = executable
        project.pathSettings = PathSettings(
            executable=executable,
            workspace_root=str(root),
            runs_root=str(runs_root),
            # the materials the demo geometry uses (silicon, iron, water, ...), as test/main_hierarchical.ini
            materials_config=str(root / "test" / "materials" / "test_materials.ini"),
            geometry_config=str(root / "test" / "geometry" / "hierarchical_test.ini"),
        )
        project.geometrySettings.config_path = project.pathSettings.geometry_config
        project.geometrySettings.template = "hierarchical"
        return project

    def _connect_signals(self) -> None:
        self.start_page.newSimulationRequested.connect(self.open_new_simulation_wizard)
        self.start_page.openProjectRequested.connect(self.open_project)
        self.start_page.recentProjectRequested.connect(self._open_recent_project)
        self.start_page.exampleRequested.connect(self.open_example)
        self.project_page.projectChanged.connect(self._update_project_from_page)
        self.project_page.saveProjectRequested.connect(self.save_project_as)
        self.project_page.loadProjectRequested.connect(self.open_project)
        self.config_builder_page.settingsChanged.connect(self._update_project_from_config_builder)
        self.config_builder_page.validateRequested.connect(self.validate_generated_config)
        self.config_builder_page.generatePackageRequested.connect(self.generate_package)
        self.config_builder_page.backendGeometryRequested.connect(self.export_backend_geometry)

        self.run_page.buildCommandRequested.connect(self.build_command_preview)
        self.run_page.inspectMacroRequested.connect(self.inspect_external_macro)
        self.run_page.runRequested.connect(self.start_run)
        self.run_page.stopRequested.connect(self.stop_run)
        self.run_page.killRequested.connect(self.runner.kill)
        self.run_page.saveLogsRequested.connect(self.runner.save_logs)

        self.runner.stdoutReceived.connect(self.run_page.append_stdout)
        self.runner.stderrReceived.connect(self.run_page.append_stderr)
        self.runner.stateChanged.connect(self._on_state_changed)
        self.runner.finished.connect(self._on_finished)
        self.runner.errorOccurred.connect(self._on_runner_error)
        self.runner.logTagDetected.connect(self._on_log_tag)
        self.run_history_page.loadSnapshotRequested.connect(self.load_snapshot_into_project)
        self.run_history_page.openOutputRequested.connect(self.open_history_output)
        self.run_history_page.duplicateRequested.connect(lambda package: self.duplicate_history_package(package, run_after=False))
        self.run_history_page.duplicateAndRunRequested.connect(lambda package: self.duplicate_history_package(package, run_after=True))

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        wizard_action = file_menu.addAction("New Simulation...")
        wizard_action.setShortcut("Ctrl+N")
        wizard_action.triggered.connect(self.open_new_simulation_wizard)
        file_menu.addSeparator()
        open_action = file_menu.addAction("Open Project...")
        save_action = file_menu.addAction("Save Project")
        save_as_action = file_menu.addAction("Save Project As...")
        self.recent_menu = file_menu.addMenu("Recent Projects")
        clear_recent_action = file_menu.addAction("Clear Recent Projects")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")

        open_action.triggered.connect(self.open_project)
        save_action.triggered.connect(self.save_project)
        save_as_action.triggered.connect(self.save_project_as)
        clear_recent_action.triggered.connect(self.clear_recent_projects)
        exit_action.triggered.connect(self.close)
        self._refresh_recent_menu()

        view_menu = self.menuBar().addMenu(self.tr("View"))
        theme_menu = view_menu.addMenu(self.tr("Theme"))
        self._theme_action_group = QActionGroup(self)
        self._theme_action_group.setExclusive(True)
        self._theme_actions = {}
        current_mode = str(QApplication.instance().property("themeMode") or "light")
        for mode, label in [
            ("light", self.tr("Light")),
            ("dark", self.tr("Dark")),
            ("system", self.tr("System")),
        ]:
            action = theme_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(mode == current_mode)
            action.triggered.connect(lambda _checked=False, selected=mode: self._set_theme(selected))
            self._theme_action_group.addAction(action)
            self._theme_actions[mode] = action
        self.theme_button.setMenu(theme_menu)

        language_menu = view_menu.addMenu(self.tr("Language"))
        self._language_action_group = QActionGroup(self)
        self._language_action_group.setExclusive(True)
        self._language_actions = {}
        active_language = current_language()
        for code, label in [("zh_CN", self.tr("Chinese")), ("en", self.tr("English"))]:
            action = language_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(code == active_language)
            action.triggered.connect(lambda _checked=False, selected=code: self._set_language(selected))
            self._language_action_group.addAction(action)
            self._language_actions[code] = action
        self.language_button.setMenu(language_menu)

    def _set_theme(self, mode: ThemeMode) -> None:
        app = QApplication.instance()
        if app is None:
            return
        apply_theme(app, mode)
        self._refresh_icons()
        # matplotlib figures, icons and other custom-painted views keep their colours until redrawn
        for page in (self.start_page, self.config_builder_page, self.output_page, self.scan_page):
            refresh_theme = getattr(page, "refresh_theme", None)
            if refresh_theme is not None:
                refresh_theme()
        QSettings().setValue("appearance/theme", mode)
        action = self._theme_actions.get(mode)
        if action is not None:
            action.setChecked(True)

    def _set_language(self, language: LanguageCode, *, persist: bool = True) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.setProperty("languageCode", language)
        apply_language(self, language)
        for page in (self.start_page, self.project_page, self.config_builder_page, self.run_page, self.output_page,
                     self.scan_page):
            refresh_language = getattr(page, "refresh_language", None)
            if refresh_language is not None:
                refresh_language()
        if persist:
            QSettings().setValue("appearance/language", language)
        action = self._language_actions.get(language)
        if action is not None:
            action.setChecked(True)
        self._on_page_changed(self.page_stack.currentIndex())
        self._set_run_chip(*self._run_chip)
        self.statusBar().clearMessage()   # a message shown before the switch is in the old language
        self.project_context.setText(
            ui_format("Project: {name}", name=self.project.projectName or ui_text("untitled"))
        )

    def _set_project(self, project: G4USimProject) -> None:
        self.project = project
        self.run_page.set_macro_plan("")
        self._generated_package_stale = project.runInputMode == "generated"
        self._generated_package_dir = ""
        self.project_page.set_project(project)
        self.config_builder_page.set_from_project(project)
        self.output_page.set_workspace_root(project.workspaceRoot)
        self.output_page.set_output_dir(project.outputDir)
        self.run_history_page.set_runs_root(project.runsRoot)
        self.project_context.setText(
            ui_format("Project: {name}", name=project.projectName or ui_text("untitled"))
        )
        self.build_command_preview(show_errors=False)

    def _update_project_from_page(self) -> None:
        before = self._project_page_stale_signature(self.project)
        macro_before = self._macro_inspection_inputs()
        self.project_page.apply_to_project(self.project)
        after = self._project_page_stale_signature(self.project)
        if macro_before != self._macro_inspection_inputs():
            self.run_page.set_macro_plan(ui_text("Run plan is stale; inputs changed."))
        self.project_context.setText(
            ui_format("Project: {name}", name=self.project.projectName or ui_text("untitled"))
        )
        self._sync_flat_project_to_nested_paths()
        self.config_builder_page.set_run_defaults(self.project)
        self.output_page.set_workspace_root(self.project.workspaceRoot)
        self.output_page.set_output_dir(self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        if before != after and self.project.runInputMode == "generated":
            self._mark_generated_package_stale()
        else:
            self.build_command_preview(show_errors=False)

    def _update_project_from_config_builder(self) -> None:
        self.config_builder_page.update_project(self.project)
        run = self.project.runSettings
        self.project.runName = run.run_name
        self.project.threads = run.threads
        self.project.seed = "" if run.seed is None else str(run.seed)
        self.project_page.set_project(self.project)
        self._mark_generated_package_stale()

    def scan_base(self) -> tuple[parameter_scan.ScanBase, str, str, str]:
        """Snapshot of the Configuration page for a parameter scan (same inputs as Generate & Run)."""
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        if self.project.runInputMode != "generated":
            raise ValueError(ui_text("Parameter scans use the Configuration page as run input (generated mode)."))
        page = self.config_builder_page
        paths = page.path_settings(self.project)
        base = parameter_scan.ScanBase(
            project=copy.deepcopy(self.project), paths=paths, run=page.run_settings(),
            geometry_settings=page.geometry_settings(), geometry=copy.deepcopy(page.geometry_document),
            source=copy.deepcopy(page.source_editor), physics=copy.deepcopy(page.physics_editor),
            scoring=copy.deepcopy(page.scoring_editor),
            materials=copy.deepcopy(page.material_document) if page.material_document.is_dirty else None)
        return base, paths.runs_root, self.project.executable or paths.executable, self.project.workspaceRoot

    def open_new_simulation_wizard(self) -> None:
        wizard = NewSimulationWizard(self)
        if wizard.exec() != NewSimulationWizard.Accepted:
            return
        self.apply_simulation_wizard(wizard.spec, run_after=wizard.run_after_finish())

    def apply_simulation_wizard(self, spec: simulation_wizard.WizardSpec, *, run_after: bool) -> bool:
        """Put a wizard result into the current project (in place) and show the Configuration page."""
        try:
            result = simulation_wizard.build(spec)
        except ValueError as error:
            QMessageBox.warning(self, ui_text("New simulation"), str(error))
            return False
        self._update_project_from_page_without_preview()
        simulation_wizard.apply_to_project(self.project, result)
        self._set_project(self.project)
        index = self.page_stack.indexOf(self.config_builder_page)
        self.page_stack.setCurrentIndex(index)
        self._nav_buttons[index].setChecked(True)
        self.statusBar().showMessage(
            ui_format("New simulation {name}: review the editors or press Generate & Run.", name=spec.project_name),
            8000)
        if run_after:
            self.generate_package(run_after_generate=True)
        return True

    def open_example(self, example_id: str) -> bool:
        """Load a gallery example: its wizard spec into the project, its bundled results into the views."""
        example = gallery.find(example_id)
        if example is None:
            return False
        if not self.apply_simulation_wizard(example.spec(), run_after=False):
            return False
        if example.is_scan:
            if example.has_results():
                self.scan_page.refresh_base()
                self.scan_page.select_parameter(example.scan_parameter)
                self.scan_page.values.setText(example.scan_values)
                self.scan_page.name.setText(example.id)
                self.scan_page.load_scan(example.scan_dir())
                self.scan_page.select_quantity(*example.scan_quantity)
            self.page_stack.setCurrentWidget(self.scan_page)
        elif example.has_results():
            self.output_page.set_output_dir(str(example.output_dir()))
            self.output_page.refresh()
            self.output_page.show_plot(example.plot)
            self.page_stack.setCurrentWidget(self.output_page)
        message = ("Example {name} loaded with its bundled scan results; Create scan makes new run packages."
                   if example.is_scan else
                   "Example {name} loaded with its bundled results; Generate & Run computes it again.")
        self.statusBar().showMessage(ui_format(message, name=ui_text(example.title)), 10000)
        return True

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            project = load_project(path)
        except Exception as exc:  # noqa: BLE001 - user-facing project load errors.
            QMessageBox.critical(self, "Open project failed", str(exc))
            return
        self.project_file = Path(path)
        add_recent_project(path)
        self._refresh_recent_menu()
        self._set_project(project)
        self.statusBar().showMessage(f"Loaded project: {path}", 5000)

    def save_project(self) -> None:
        if self.project_file is None:
            self.save_project_as()
            return
        self._update_project_from_page()
        self.config_builder_page.update_project(self.project)
        try:
            save_project(self.project, self.project_file)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save project failed", str(exc))
            return
        self.statusBar().showMessage(f"Saved project: {self.project_file}", 5000)
        add_recent_project(str(self.project_file))
        self._refresh_recent_menu()

    def save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save G4UniversalSim project", filter="JSON files (*.json);;All files (*)"
        )
        if not path:
            return
        self.project_file = Path(path)
        self.save_project()

    def build_command_preview(self, *, show_errors: bool = True) -> None:
        self._update_project_from_page_without_preview()
        if self.project.runInputMode == "generated" and self._generated_package_stale:
            self.run_page.set_command([ui_text("Configuration changed; the run package will be regenerated at run time.")])
            return
        errors = self.runner.validate_project(self.project)
        if errors:
            self.run_page.set_command(["Validation errors:", *errors])
            if show_errors:
                QMessageBox.warning(self, "Validation failed", "\n".join(errors))
            return
        command = self.runner.build_command(self.project)
        self.run_page.set_command(self._format_command_preview(command))

    def _macro_inspection_inputs(self) -> tuple[object, ...]:
        return (self.project.runInputMode, self.project.executable,
                self.project.workspaceRoot, self.project.configPath, self.project.macroPath,
                self.project.outputDir, self.project.threads, self.project.seed, self.project.runName)

    def export_backend_geometry(self) -> None:
        """Roadmap A5: show the geometry the backend builds (asynchronous QProcess)."""
        if self._geometry_export.state() != QProcess.NotRunning:
            return
        self._update_project_from_page_without_preview()
        config = self.project.configPath
        if not config or not Path(config).is_file():
            self.config_builder_page.show_backend_geometry_message(ui_text(
                "Backend geometry needs a main INI: choose one in external mode or generate the run package first."))
            return
        if not self.project.executable or not Path(self.project.executable).is_file():
            self.config_builder_page.show_backend_geometry_message(ui_text("Backend executable not found."))
            return
        self._geometry_export_dir = tempfile.TemporaryDirectory(prefix="g4usim_geometry_")
        work = Path(self._geometry_export_dir.name)
        json_path = work / "geometry_mesh.json"
        macro = write_export_macro(work, json_path)
        self._geometry_export.setProgram(self.project.executable)
        self._geometry_export.setArguments(export_arguments(config, macro, work / "output"))
        self._geometry_export.setWorkingDirectory(self.project.workspaceRoot or str(Path(config).parent))
        self.config_builder_page.set_backend_geometry_busy(True)
        self._geometry_export.start()

    def _on_geometry_export_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.config_builder_page.set_backend_geometry_busy(False)
        work = Path(self._geometry_export_dir.name) if self._geometry_export_dir else None
        stderr = bytes(self._geometry_export.readAllStandardError()).decode("utf-8", errors="replace").strip()
        try:
            if exit_status != QProcess.NormalExit or exit_code != 0 or work is None:
                raise ValueError(ui_format("Backend geometry export failed: {reason}", reason=stderr[-2000:] or exit_code))
            mesh = load_backend_mesh(work / "geometry_mesh.json")
            self.config_builder_page.show_backend_geometry(mesh)
        except ValueError as exc:
            self.config_builder_page.show_backend_geometry_message(str(exc))
        finally:
            if self._geometry_export_dir:
                self._geometry_export_dir.cleanup()
                self._geometry_export_dir = None

    def inspect_external_macro(self, *, run_after: bool = False) -> None:
        if self._macro_inspection.state() != QProcess.NotRunning:
            return
        self._update_project_from_page_without_preview()
        if self.project.runInputMode != "external":
            self.run_page.set_macro_plan(ui_text(
                "Input inspection is available in external mode."
            ))
            return
        errors = self.runner.validate_project(self.project, ready_to_run=True)
        if errors:
            self.run_page.set_macro_plan("\n".join(errors))
            return
        args = ["--inspect-run", *self.runner.build_command(self.project)[1:]]
        self._pending_inspection_run = run_after
        self._macro_inspection_snapshot = self._macro_inspection_inputs()
        self._macro_inspection.setProgram(self.project.executable)
        self._macro_inspection.setArguments(args)
        self._macro_inspection.setWorkingDirectory(self.project.workspaceRoot or str(Path.cwd()))
        self.run_page.set_macro_plan(ui_text("Inspecting inputs with backend preflight..."))
        self._macro_inspection.start()

    def _on_macro_inspection_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        run_after = self._pending_inspection_run
        self._pending_inspection_run = False
        self.project_page.apply_to_project(self.project)
        if self._macro_inspection_snapshot != self._macro_inspection_inputs():
            self.run_page.set_macro_plan(ui_text("Run plan is stale; inputs changed."))
            return
        stderr = bytes(self._macro_inspection.readAllStandardError()).decode("utf-8", errors="replace").strip()
        stdout = bytes(self._macro_inspection.readAllStandardOutput()).decode("utf-8", errors="replace")
        if exit_status != QProcess.NormalExit or exit_code != 0:
            self.run_page.set_macro_plan(ui_format("Input inspection failed: {reason}", reason=stderr or exit_code))
            return
        try:
            plan = json.loads(stdout)
            if plan.get("schema") != "G4UniversalSimRunPlan" or plan.get("version") != 1:
                raise ValueError("unsupported run plan schema")
            commands = plan["macro_plan"]["commands"]
            if not isinstance(commands, list):
                raise ValueError("macro plan commands are not a list")
            lines = [
                ui_text("Configuration before macro execution; runtime results remain unknown."),
                ui_text("Initial configuration and sources:"),
            ]
            for item in plan["initial_configuration"]:
                location = f" {item.get('file', '')}:{item.get('line', '')}" if item["source"] == "main_ini" else ""
                lines.append(f"{item['name']} = {item['value']} [{item['source']}]{location}")
            lines.extend(["", ui_format("Expanded commands: {count}", count=len(commands)),
                          ui_text("Macro commands may change configuration after initialization.")])
            for item in commands:
                lines.append(f"{item['file']}:{item['line']} [{item['category']}] {item['text']}")
            if plan["macro_execution_planned"] and not any(item["category"] == "beam_on" for item in commands):
                lines.extend(["", ui_text("No beamOn command was found; no macro events are planned.")])
            if stderr:
                lines.extend(["", ui_text("Backend diagnostics:"), stderr])
            self.run_page.set_macro_plan("\n".join(lines))
            if run_after:
                self._start_current_project()
        except (KeyError, TypeError, ValueError) as error:
            self.run_page.set_macro_plan(ui_format("Input inspection failed: {reason}", reason=str(error)))

    def _on_macro_inspection_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.FailedToStart:
            self._pending_inspection_run = False
            self.run_page.set_macro_plan(ui_format("Input inspection failed: {reason}", reason=self._macro_inspection.errorString()))

    def start_run(self) -> None:
        if self.runner.is_running() or self._macro_inspection.state() != QProcess.NotRunning:
            self.run_page.append_status_message(ui_text("A run is already active."))
            return
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        if self.project.runInputMode == "generated":
            if not self._generate_current_package():
                return
            self._start_current_project()
            return
        self.inspect_external_macro(run_after=True)

    def _start_current_project(self) -> None:
        errors = self.runner.validate_project(self.project, ready_to_run=True)
        if errors:
            message = "\n".join(errors)
            self.run_page.append_status_message(message)
            QMessageBox.warning(self, "Validation failed", message)
            return
        self.run_page.clear_logs()
        self.run_page.set_result("")
        command = self.runner.build_command(self.project)
        self.run_page.set_command(self._format_command_preview(command))
        self.run_page.append_status_message("Starting run")
        self.statusBar().showMessage("Running", 5000)
        self.runner.start(self.project, command)

    def validate_generated_config(self) -> None:
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        try:
            report = self.config_builder_page.validate_current(self.project)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Validation failed", str(exc))
            self.config_builder_page.set_validation_text(str(exc))
            return
        self.config_builder_page.set_validation_text(report.to_text())
        if report.can_run:
            self.statusBar().showMessage("Config Builder validation passed", 5000)
        else:
            QMessageBox.warning(self, "Validation failed", "\n".join(report.errors))

    def generate_package(self, run_after_generate: bool) -> None:
        self._update_project_from_page_without_preview()
        self.config_builder_page.update_project(self.project)
        if not self._generate_current_package():
            return
        if run_after_generate:
            self._start_current_project()

    def _generate_current_package(self) -> bool:
        try:
            pre_report = self.config_builder_page.validate_current(self.project)
            if not pre_report.can_run:
                self.config_builder_page.set_validation_text(pre_report.to_text())
                QMessageBox.warning(self, "Validation failed", "\n".join(pre_report.errors))
                return False
            if pre_report.warnings:
                QMessageBox.information(
                    self,
                    "Validation warnings",
                    "Package generation will continue with warnings:\n\n"
                    + "\n".join(pre_report.warnings[:10]),
                )
            package, report_text = create_run_package(
                project=self.project,
                paths=self.config_builder_page.path_settings(self.project),
                run=self.config_builder_page.run_settings(),
                geometry=self.config_builder_page.geometry_settings(),
                source=self.config_builder_page.source_settings(),
                physics=self.config_builder_page.physics_settings(),
                scoring=self.config_builder_page.scoring_settings(),
                material_document=self.config_builder_page.material_document if self.config_builder_page.material_document.is_dirty else None,
                geometry_document=self.config_builder_page.geometry_document,
                source_model=self.config_builder_page.source_editor,
                physics_model=self.config_builder_page.physics_editor,
                scoring_model=self.config_builder_page.scoring_editor,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self.config_builder_page.set_validation_text(message)
            QMessageBox.warning(self, "Generate package failed", message)
            return False

        self.project.configPath = package.main_ini_path
        self.project.macroPath = package.run_macro_path
        self.project.outputDir = package.output_dir
        self.project.runName = self.config_builder_page.run_settings().run_name
        self.project.threads = self.config_builder_page.run_settings().threads
        seed = self.config_builder_page.run_settings().seed
        self.project.seed = "" if seed is None else str(seed)
        self.project.runInputMode = "generated"
        self.project_page.set_project(self.project)
        self._generated_package_dir = package.package_dir
        self._generated_package_stale = False
        self.config_builder_page.set_package_path(package.package_dir)
        self.config_builder_page.set_validation_text(report_text)
        self.output_page.set_package_dir(package.package_dir, package.output_dir)
        self.run_history_page.set_runs_root(self.project.runsRoot)
        self.run_history_page.refresh()
        self.build_command_preview(show_errors=False)
        self.statusBar().showMessage(f"Generated package: {package.package_dir}", 8000)

        return True

    def stop_run(self) -> None:
        self.runner.terminate()
        self.run_page.append_status_message("Terminate requested. Use Kill if the process does not exit.")
        QTimer.singleShot(3000, self._offer_kill_if_running)

    def _offer_kill_if_running(self) -> None:
        if not self.runner.is_running():
            return
        self.run_page.append_status_message("Process is still running; Kill is available.")

    def _on_state_changed(self, state: str) -> None:
        self.run_page.set_state(state)
        running = state in {"Starting", "Running"}
        self._set_run_chip(state, "running" if running else "")
        self.project_page.set_inputs_enabled(not running)

    def _on_finished(self, exit_code: int) -> None:
        self.run_page.set_exit_code(exit_code)
        result = self.runner.last_result
        state = result.state if result else "incomplete"
        reason = result.reason if result else "Run result is unavailable."
        self.run_page.set_result(state)
        self.run_page.append_status_message(ui_format("Run result: {state}. {reason}", state=ui_text(state), reason=ui_text(reason)))
        self.project_page.set_inputs_enabled(True)
        self.output_page.set_output_dir(self.project.outputDir)
        self.output_page.refresh()
        self.run_history_page.refresh()
        self._set_run_chip(state, {"success": "success", "failed": "failed"}.get(state, ""))
        self.statusBar().showMessage(ui_format("Run result: {state}. {reason}", state=ui_text(state), reason=ui_text(reason)), 8000)

    def _set_run_chip(self, state: str, role: str) -> None:
        """Header status chip: a dot and the state in words; colour only repeats what the text says."""
        self._run_chip = (state, role)
        self.run_context.setText(f"\u25CF {ui_text(state)}")
        self.run_context.setProperty("statusRole", role)
        self.run_context.style().unpolish(self.run_context)
        self.run_context.style().polish(self.run_context)

    def _on_runner_error(self, message: str) -> None:
        self.run_page.append_status_message(message)
        QMessageBox.warning(self, "Runner error", message)

    def _on_log_tag(self, level: str, message: str, advice: str) -> None:
        self.statusBar().showMessage(f"{level.upper()}: {message}", 8000)
        detail = f"{level.upper()}: {message}"
        if advice:
            detail += f" | Advice: {advice}"
        self.run_page.append_status_message(detail)

    def _update_project_from_page_without_preview(self) -> None:
        self.project_page.apply_to_project(self.project)
        self._sync_flat_project_to_nested_paths()
        self.config_builder_page.set_run_defaults(self.project)
        self.output_page.set_workspace_root(self.project.workspaceRoot)
        self.output_page.set_output_dir(self.project.outputDir)
        self.run_history_page.set_runs_root(self.project.runsRoot)

    def _sync_flat_project_to_nested_paths(self) -> None:
        self.project.pathSettings.executable = self.project.executable
        self.project.pathSettings.workspace_root = self.project.workspaceRoot
        self.project.pathSettings.runs_root = self.project.runsRoot

    def _project_page_stale_signature(self, project: G4USimProject) -> tuple[object, ...]:
        return (
            project.runInputMode,
            project.projectName,
            project.executable,
            project.workspaceRoot,
            project.outputDir,
            project.runsRoot,
            project.threads,
            project.seed,
            project.runName,
        )

    def _mark_generated_package_stale(self) -> None:
        if self.project.runInputMode != "generated":
            self.build_command_preview(show_errors=False)
            return
        self._generated_package_stale = True
        self.config_builder_page.set_package_path("<stale>")
        self.run_page.set_command([ui_text("Configuration changed; the run package will be regenerated at run time.")])

    def _format_command_preview(self, command: list[str]) -> list[str]:
        if not command:
            return []
        working_directory = self.project.workspaceRoot or "<not set>"
        lines = [
            "program:",
            f"  {command[0]}",
            "arguments:",
        ]
        lines.extend(f"  {arg}" for arg in command[1:])
        lines.extend(["working directory:", f"  {working_directory}", "", "human-readable:", "  " + " ".join(command)])
        return lines

    def load_snapshot_into_project(self, snapshot_path: str) -> None:
        try:
            project = load_project(snapshot_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Load snapshot failed", str(exc))
            return
        # Keep historical package paths visible, but users can generate a new package before running.
        self._set_project(project)
        self.statusBar().showMessage("Snapshot loaded. You can generate a new package or rerun with the existing package.", 8000)

    def open_history_output(self, package_dir: str, output_dir: str) -> None:
        self.output_page.set_package_dir(package_dir, output_dir)
        self.tabs.setCurrentWidget(self.output_page)

    def duplicate_history_package(self, package_dir: str, *, run_after: bool) -> None:
        try:
            new_package = duplicate_package(package_dir, self.project.runsRoot)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Duplicate failed", str(exc))
            return
        package = Path(new_package)
        self.project.configPath = str(package / "config" / "main.ini")
        self.project.macroPath = str(package / "macros" / "run.mac")
        self.project.outputDir = str(package / "output")
        self.project.runInputMode = "external"
        self.project_page.set_project(self.project)
        self.output_page.set_package_dir(str(package), self.project.outputDir)
        self.run_history_page.refresh()
        self.build_command_preview(show_errors=False)
        self.tabs.setCurrentWidget(self.run_page)
        if run_after:
            self.start_run()

    def _restore_app_state(self) -> None:
        state = load_state()
        if state.get("lastWorkspaceRoot") and not self.project.workspaceRoot:
            self.project.workspaceRoot = state["lastWorkspaceRoot"]
        if state.get("lastRunsRoot") and not self.project.runsRoot:
            self.project.runsRoot = state["lastRunsRoot"]

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override.
        if self._macro_inspection.state() != QProcess.NotRunning:
            self._macro_inspection.kill()
            self._macro_inspection.waitForFinished(1000)
        if self.scan_page.runner.is_running():   # do not leave a scan point running after exit
            self.scan_page.runner.stop()
        state = load_state()
        state["lastWorkspaceRoot"] = self.project.workspaceRoot
        state["lastRunsRoot"] = self.project.runsRoot
        save_state(state)
        super().closeEvent(event)

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        projects = get_recent_projects()
        self.start_page.set_recent_projects(projects)
        if not projects:
            action = self.recent_menu.addAction("<none>")
            action.setEnabled(False)
            return
        for path in projects:
            action = self.recent_menu.addAction(path)
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_project(p))

    def _open_recent_project(self, path: str) -> None:
        try:
            project = load_project(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Open recent project failed", str(exc))
            return
        self.project_file = Path(path)
        self._set_project(project)

    def clear_recent_projects(self) -> None:
        clear_recent_projects()
        self._refresh_recent_menu()
