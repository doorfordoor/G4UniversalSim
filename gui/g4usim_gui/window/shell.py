"""The window's frame: sidebar, header, menus, theme, language and the run status chip."""

from __future__ import annotations

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui import __version__
from g4usim_gui.core import icons
from g4usim_gui.core.i18n import LanguageCode, apply_language, current_language, ui_format, ui_text
from g4usim_gui.core.theme import ThemeMode, apply_theme, current_colors
from g4usim_gui.window.workspace_layout import WorkspacePageStack


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
        page_header.setMinimumHeight(66)
        header_layout = QHBoxLayout(page_header)
        header_layout.setContentsMargins(24, 10, 16, 10)
        header_layout.setSpacing(8)

        heading_layout = QVBoxLayout()
        heading_layout.setSpacing(1)
        self.page_title = QLabel(page_specs[0][1])
        self.page_title.setObjectName("pageTitle")
        self.page_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.page_subtitle = QLabel(page_specs[0][2])
        self.page_subtitle.setObjectName("pageSubtitle")
        self.page_subtitle.setWordWrap(True)
        self.page_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        heading_layout.addWidget(self.page_title)
        heading_layout.addWidget(self.page_subtitle)
        header_layout.addLayout(heading_layout, 1)

        self.project_context = QLabel(self.tr("Project: demo"))
        self.project_context.setProperty("uiRole", "contextChip")
        self.project_context.setMaximumWidth(210)
        self.project_context.setWordWrap(True)
        self.project_context.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
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

        self.page_stack = WorkspacePageStack()
        self.page_stack.setObjectName("pageViewport")
        for page, _title, _subtitle, _icon in page_specs:
            self.page_stack.addWidget(page)

        content_layout.addWidget(page_header)
        workspace_viewport = QWidget(content)
        viewport_layout = QVBoxLayout(workspace_viewport)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.addWidget(self.page_stack)
        self.content_scroll = QScrollArea(content)
        self.content_scroll.setObjectName('workspaceContentScroll')
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setWidget(workspace_viewport)
        content_layout.addWidget(self.content_scroll, 1)
        shell_layout.addWidget(sidebar)
        shell_layout.addWidget(content, 1)
        # Retain the same shell/docks/pages. A viewport provides a last-resort
        # scroll path when their real minimum sizes exceed a small desktop.
        self.shell_scroll = QScrollArea(self)
        self.shell_scroll.setObjectName('workspaceShellScroll')
        self.shell_scroll.setFrameShape(QFrame.NoFrame)
        self.shell_scroll.setWidgetResizable(True)
        self.shell_scroll.setWidget(shell)
        self.setCentralWidget(self.shell_scroll)
        self.sidebar = sidebar
        self.page_header = page_header

        # Keep the historical attribute available to internal navigation helpers.
        self.tabs = self.page_stack
        self._nav_group.idClicked.connect(self.page_stack.setCurrentIndex)
        self.page_stack.currentChanged.connect(self._on_page_changed)
        from g4usim_gui.window.workspace_layout import WorkspaceLayout
        self.workspace_layout = WorkspaceLayout(self)
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
        blank_action = file_menu.addAction("New blank simulation")
        blank_action.setShortcut("Ctrl+Shift+N")
        blank_action.triggered.connect(self.new_blank_project)
        wizard_action = file_menu.addAction("New Simulation...")
        wizard_action.setShortcut("Ctrl+N")
        wizard_action.triggered.connect(self.open_new_simulation_wizard)
        file_menu.addSeparator()
        open_action = file_menu.addAction("Open Project...")
        save_action = file_menu.addAction("Save Project")
        save_as_action = file_menu.addAction("Save Project As...")
        open_action.setShortcut('Ctrl+O')
        save_action.setShortcut('Ctrl+S')
        save_as_action.setShortcut('Ctrl+Shift+S')
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
        self._create_history_actions()

        view_menu = self.menuBar().addMenu(self.tr("View"))
        self.workspace_layout.add_menu(view_menu)
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

        theme_menu.addSeparator()
        palette_menu = theme_menu.addMenu(self.tr("Light palette"))
        self._palette_action_group = QActionGroup(self)
        self._palette_action_group.setExclusive(True)
        self._palette_actions = {}
        selected_palette = str(QSettings().value("appearance/light_palette", "B"))
        if selected_palette not in ("B", "K"):
            selected_palette = "B"
        for palette, label in (("B", "B · Lattice"), ("K", "K · Software")):
            action = palette_menu.addAction(self.tr(label))
            action.setCheckable(True)
            action.setChecked(palette == selected_palette)
            action.triggered.connect(lambda _checked=False, selected=palette: self._set_palette(selected))
            self._palette_action_group.addAction(action)
            self._palette_actions[palette] = action
        dark_palette = theme_menu.addAction(self.tr("Dark palette: C · Night reading"))
        dark_palette.setEnabled(False)
        self._set_theme(current_mode, palette=selected_palette)

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
        self._create_accessibility_actions()

    def _create_accessibility_actions(self) -> None:
        menu = self.menuBar().addMenu(ui_text("Navigate"))
        menu.setProperty('i18nSource_menuTitle', 'Navigate')
        self.navigation_menu = menu
        self.page_navigation_actions = []
        for index, (_page, title, _subtitle, _icon) in enumerate(self._page_specs):
            action = QAction(ui_text(title), self)
            action.setShortcut(f'Ctrl+Alt+{index + 1}')
            action.triggered.connect(lambda _checked=False, i=index: self.focus_page(i))
            menu.addAction(action)
            self.page_navigation_actions.append(action)
        menu.addSeparator()
        self.focus_next_action = menu.addAction(ui_text("Focus next workspace region"))
        self.focus_next_action.setProperty('i18nSource_actionText', 'Focus next workspace region')
        self.focus_next_action.setShortcut('F6')
        self.focus_next_action.triggered.connect(lambda: self.focus_workspace_region())
        self.focus_previous_action = menu.addAction(ui_text("Focus previous workspace region"))
        self.focus_previous_action.setProperty('i18nSource_actionText', 'Focus previous workspace region')
        self.focus_previous_action.setShortcut('Shift+F6')
        self.focus_previous_action.triggered.connect(lambda: self.focus_workspace_region(backward=True))
        self.environment_action = menu.addAction(ui_text("Environment setup..."))
        self.environment_action.setProperty('i18nSource_actionText', 'Environment setup...')
        self.environment_action.setShortcut('Ctrl+Alt+E')
        self.environment_action.triggered.connect(self.show_environment_settings)
        self.installation_action = menu.addAction(ui_text("Open environment installer..."))
        self.installation_action.setProperty('i18nSource_actionText', 'Open environment installer...')
        self.installation_action.setShortcut('Ctrl+Alt+I')
        self.installation_action.triggered.connect(self.show_environment_installer)
        self.import_bundle_action = menu.addAction(ui_text("Import configuration bundle..."))
        self.import_bundle_action.setProperty('i18nSource_actionText', 'Import configuration bundle...')
        self.import_bundle_action.setShortcut('Ctrl+Alt+O')
        self.import_bundle_action.triggered.connect(lambda: self._experiment_action('import'))

    def _setup_accessibility(self) -> None:
        from g4usim_gui.core.accessibility import AccessibilityController, name_control
        self.accessibility_controller = AccessibilityController(self)
        page = self.config_builder_page
        for widget, source in ((page.materials_table, 'Materials table'), (page.geometry_table, 'Geometry volumes table'),
                               (page.layer_table, 'Geometry layers table'), (page.boolean_table, 'Boolean operations table')):
            name_control(widget, source)
        self._refresh_accessibility()

    def _refresh_accessibility(self) -> None:
        controller = getattr(self, 'accessibility_controller', None)
        if controller is not None:
            controller.refresh()
        for index, button in enumerate(self._nav_buttons):
            title = self._page_specs[index][1]
            button.setAccessibleName(ui_text(title))
            button.setAccessibleDescription(ui_format('Open {page}. Shortcut: Ctrl+Alt+{number}.', page=ui_text(title), number=index + 1))
        for action, (_page, title, _subtitle, _icon) in zip(getattr(self, 'page_navigation_actions', ()), self._page_specs):
            action.setText(ui_text(title))
        self.theme_button.setAccessibleName(ui_text('Theme'))
        self.language_button.setAccessibleName(ui_text('Language'))

    def focus_page(self, index: int) -> None:
        from g4usim_gui.core.accessibility import focus_first
        if 0 <= index < len(self._page_specs):
            self.page_stack.setCurrentIndex(index)
            focus_first(self._page_specs[index][0])

    def focus_workspace_region(self, *, backward=False) -> None:
        from g4usim_gui.core.accessibility import focus_first, ensure_focus_visible
        regions = [self.sidebar, self.page_stack.currentWidget()]
        for dock in self.workspace_layout.docks.values():
            if dock.isVisible() and dock.widget() not in regions:
                regions.append(dock.widget())
        regions.append(self.page_header)
        focused = QApplication.focusWidget()
        current = next((i for i, root in enumerate(regions) if root is focused or root.isAncestorOf(focused)), -1) if focused else -1
        direction = -1 if backward else 1
        for offset in range(1, len(regions) + 1):
            index = (current + direction * offset) % len(regions)
            if index == 0:
                button = self._nav_buttons[self.page_stack.currentIndex()]
                button.setFocus(Qt.ShortcutFocusReason)
                ensure_focus_visible(button)
                return
            if focus_first(regions[index]) is not None:
                return

    def show_environment_settings(self) -> None:
        existing = getattr(self, '_environment_dialog', None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        self._experiment_action('environment')

    def show_environment_installer(self) -> None:
        # I1's own button creates/reuses I2 and connects publication to reprobe.
        self.show_environment_settings()
        dialog = getattr(self, '_environment_dialog', None)
        if dialog is not None and dialog.isVisible() and dialog.install_button.isEnabled():
            dialog.install_button.click()

    def _set_palette(self, palette: str) -> None:
        if palette not in ("B", "K"):
            raise ValueError("unknown light palette")
        app = QApplication.instance()
        self._set_theme(str(app.property("themeMode") or "light"), palette=palette)
        QSettings().setValue("appearance/light_palette", palette)
        self._palette_actions[palette].setChecked(True)

    def _set_theme(self, mode: ThemeMode, *, palette=None) -> None:
        self._clear_diagnostic_highlights()
        app = QApplication.instance()
        if app is None:
            return
        apply_theme(app, mode, palette)
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
        self._clear_diagnostic_highlights()
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
        self.workspace_layout.refresh_language()
        agent_panel = getattr(self, 'config_agent_panel', None)
        if agent_panel is not None:
            agent_panel.retranslate_ui()
        self._set_run_chip(*self._run_chip)
        self.statusBar().clearMessage()   # a message shown before the switch is in the old language
        self.project_context.setText(
            ui_format("Project: {name}", name=self.project.projectName or ui_text("untitled"))
        )
        self.history_changed()
        environment_dialog = getattr(self, "_environment_dialog", None)
        if environment_dialog is not None:
            environment_dialog.retranslate_ui()
        self._refresh_accessibility()

    def _set_run_chip(self, state: str, role: str) -> None:
        """Header status chip: a dot and the state in words; colour only repeats what the text says."""
        self._run_chip = (state, role)
        self._render_run_chip()

    def _render_run_chip(self):
        from g4usim_gui.widgets.run_page import scoped_run_text
        state, role = self._run_chip
        page = getattr(self, 'run_page', None)
        scope = getattr(page, '_run_display_scope', '')
        retained = getattr(page, '_retained_run_view', None)
        if retained and scope not in ('', 'running'):
            state = retained['result'] or state
        if scope in ('changed', 'historical', 'unverified', 'checking'):
            role = ''  # Historical facts and pending checks are neutral.
        self.run_context.setText(f"\u25CF {scoped_run_text(ui_text(state), scope)}")
        self.run_context.setToolTip(page.run_display_identity_text() if page is not None else '')
        self.run_context.setProperty("statusRole", role)
        self.run_context.style().unpolish(self.run_context)
        self.run_context.style().polish(self.run_context)
