"""The window's frame: sidebar, header, menus, theme, language and the run status chip."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui import __version__
from g4usim_gui.core import icons
from g4usim_gui.core.i18n import LanguageCode, apply_language, current_language, ui_format, ui_text
from g4usim_gui.core.theme import ThemeMode, apply_theme, current_colors


class ShellMixin:
    """The window's frame: sidebar, header, menus, theme, language and the run status chip. Mixed into MainWindow."""

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
                self.scenario_page,
                self.tr("Scenario"),
                self.tr("Run the shielding and coating scenario end to end with evidence for every number."),
                "scenario",
            ),
            (
                self.effective_config_page,
                self.tr("Effective Configuration"),
                self.tr("Inspect backend configuration snapshots and their evidence without editing them."),
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

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        wizard_action = file_menu.addAction("New Simulation...")
        wizard_action.setShortcut("Ctrl+N")
        wizard_action.triggered.connect(self.open_new_simulation_wizard)
        file_menu.addSeparator()
        open_action = file_menu.addAction("Open Project...")
        save_action = file_menu.addAction("Save Project")
        save_as_action = file_menu.addAction("Save Project As...")
        migration_action = file_menu.addAction("Configuration migration copy...")
        self.recent_menu = file_menu.addMenu("Recent Projects")
        clear_recent_action = file_menu.addAction("Clear Recent Projects")
        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")

        open_action.triggered.connect(self.open_project)
        save_action.triggered.connect(self.save_project)
        save_as_action.triggered.connect(self.save_project_as)
        migration_action.triggered.connect(self.open_migration_preview)
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
        for page in (self.start_page, self.config_builder_page, self.output_page, self.scenario_page, self.effective_config_page, self.scan_page):
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
                     self.scenario_page, self.effective_config_page, self.scan_page):
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

    def _set_run_chip(self, state: str, role: str) -> None:
        """Header status chip: a dot and the state in words; colour only repeats what the text says."""
        self._run_chip = (state, role)
        self.run_context.setText(f"\u25CF {ui_text(state)}")
        self.run_context.setProperty("statusRole", role)
        self.run_context.style().unpolish(self.run_context)
        self.run_context.style().polish(self.run_context)
