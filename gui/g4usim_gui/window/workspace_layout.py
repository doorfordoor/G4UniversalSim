"""Native dock arrangements; all saved state belongs to this computer's UI.

The page widgets remain the business owners. One shared workspace host allows
configuration, 3D, results and logs to be observed together across navigation.
"""
from __future__ import annotations

import base64
import hashlib
import json
import weakref

from PySide6.QtCore import QByteArray, QObject, QSettings, Signal, QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QFrame, QLabel, QMainWindow, QPushButton, QScrollArea, QStackedWidget,
    QTabWidget, QVBoxLayout, QWidget,
)

from g4usim_gui.core.i18n import ui_text

STATE_KEY = "workspace/v1/layout"
STATE_VERSION = 1
MAX_STATE_BYTES = 1024 * 1024
PRESETS = {
    "configuration": "Configuration editing",
    "running": "Run observation",
    "analysis": "Result analysis",
}


def _encoded(value: QByteArray) -> str:
    return base64.b64encode(bytes(value)).decode("ascii")


def _decoded(value: object) -> QByteArray:
    if not isinstance(value, str) or not value or len(value) > MAX_STATE_BYTES:
        raise ValueError("invalid Qt layout data")
    return QByteArray(base64.b64decode(value, validate=True))


class WorkspacePageStack(QStackedWidget):
    """Nine logical page identities, including the pages shown in native docks.

    Anchors take their places in the central viewport; callers still navigate
    with the original single-instance page objects.
    """

    previewActivationRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dock_pages = {}
        self._navigation_docks = {}
        self._first_navigation_docks = {}
        self._preview_activation_index = None

    def _current_size_hint(self, *, minimum: bool) -> QSize:
        # QStackedLayout otherwise takes the maximum of *all* pages. Inside the
        # scrollable workspace that gives an inactive history/scans page control
        # over the host's size, pushing a visible bottom log dock out of view.
        # Use the actual central anchor here, not widget()'s logical dock page.
        page = super().currentWidget()
        if page is None:
            return QSize(0, 0)
        hint = page.minimumSizeHint() if minimum else page.sizeHint()
        hint = hint.expandedTo(page.minimumSize()).expandedTo(QSize(0, 0))
        # A page's scroll-frame minimum (often 66px) is not a readable editor
        # width when peer docks remain open. Preserve the active page's preferred
        # horizontal extent only; its tall contents must still scroll vertically
        # rather than taking space away from the simultaneously visible logs.
        if minimum:
            hint.setWidth(max(hint.width(), page.sizeHint().width()))
        margins = self.contentsMargins()
        return hint + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self._current_size_hint(minimum=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self._current_size_hint(minimum=False)

    def attach_dock_page(self, page, dock):
        index = super().indexOf(page)
        self._dock_pages[index] = (page, dock)
        current = self.currentIndex()
        super().removeWidget(page)
        super().insertWidget(index, QWidget(self))
        self.setCurrentIndex(current)

    def widget(self, index):
        return self._dock_pages[index][0] if index in self._dock_pages else super().widget(index)

    def currentWidget(self):
        return self.widget(self.currentIndex())

    def indexOf(self, page):
        for index, (candidate, _dock) in self._dock_pages.items():
            if candidate is page:
                return index
        return super().indexOf(page)

    def setCurrentWidget(self, page):
        index = self.indexOf(page)
        if index >= 0:
            self.setCurrentIndex(index)

    def setCurrentIndex(self, index):
        super().setCurrentIndex(index)
        self.updateGeometry()
        if self._dock_pages:
            self.reveal_current()

    def reveal_current(self):
        selected = self._dock_pages.get(self.currentIndex())
        self._central_extent(selected is not None)
        if selected is not None and selected[1] is not None:
            selected[1].show()
            selected[1].raise_()
        for dock in self._navigation_docks.get(self.currentIndex(), ()):
            dock.show()
            dock.raise_()
        for dock in self._first_navigation_docks.pop(self.currentIndex(), ()):
            dock.show()
            dock.raise_()
        if self.currentIndex() == self._preview_activation_index:
            self.previewActivationRequested.emit()

    def restore_current_index(self, index):
        # A saved hidden active dock must remain hidden. Restoring navigation
        # updates its header/anchor without overriding Qt's saved visibility.
        super().setCurrentIndex(index)
        self.updateGeometry()
        self._central_extent(index in self._dock_pages)

    def _central_extent(self, dock_page):
        # Keep the stack itself visible so normal hidden stack-page diagnostics
        # remain revealable. An active dock page only needs a zero-size anchor.
        self.setMaximumSize(0, 0) if dock_page else self.setMaximumSize(16777215, 16777215)
        self.show()


class WorkspaceDock(QDockWidget):
    """A floating page's Qt window reflects its sole main-window lifecycle."""

    def __init__(self, title, host, owner):
        super().__init__(title, host)
        self._workspace_owner = weakref.ref(owner)

    @property
    def _closing(self):
        # OutputPage's late merge-error adapter uses self.window()._closing.
        # Floating changes that Qt window to this dock, not its process owner.
        owner = self._workspace_owner()
        return owner is None or getattr(owner, "_closing", False)


class WorkspaceLayout(QObject):
    """Only geometry and widget placement; never collects or changes a project."""

    def __init__(self, window, *, settings: QSettings | None = None):
        super().__init__(window)
        self.window = window
        self.settings = settings if settings is not None else QSettings()
        self.hosts: dict[str, QMainWindow] = {}
        self.docks: dict[str, QDockWidget] = {}
        self.preset = "configuration"
        self.last_restore = "default"
        self._build()
        self.apply_preset("configuration")
        if window.page_stack.currentIndex() == 0:
            self.docks["configuration"].hide()
            self.docks["preview"].hide()
            window.page_stack._first_navigation_docks[window.page_stack.indexOf(window.config_builder_page)] = (
                self.docks["preview"],)

    def _host(self, name: str, parent: QWidget) -> QMainWindow:
        host = QMainWindow(parent)
        host.setWindowFlags(Qt.Widget)
        host.setObjectName("workspaceHost_" + name)
        host.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks)
        host.setDockNestingEnabled(True)
        self.hosts[name] = host
        return host

    def _dock(self, name: str, title: str, host: QMainWindow, widget: QWidget,
              area=Qt.LeftDockWidgetArea) -> QDockWidget:
        dock = WorkspaceDock(ui_text(title), host, self.window)
        dock.setProperty("workspaceDock", True)
        dock.setObjectName("workspaceDock_" + name)
        dock.setProperty("workspaceTitle", title)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable |
                         QDockWidget.DockWidgetClosable)
        dock.setWidget(widget)
        host.addDockWidget(area, dock)
        self.docks[name] = dock
        return dock

    def _build(self):
        window = self.window
        config = window.config_builder_page
        config._preview_activation_ready = False
        stack = window.page_stack
        content_layout = stack.parentWidget().layout()
        host = self._host("workspace", stack.parentWidget())
        content_layout.replaceWidget(stack, host)
        host.setCentralWidget(stack)
        stack.attach_dock_page(config, None)
        dock = self._dock("configuration", "Configuration editors", host, config)
        dock.setMinimumHeight(380)
        dock.setMinimumWidth(620)
        stack._dock_pages[stack.indexOf(config)] = (config, dock)
        # Setup already scrolls. Permit a narrow dock without clipping wide
        # path rows; users can resize the native separator or its scrollbar.
        config.setup_panel.setMinimumWidth(260)
        config.setup_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        config.layout().itemAt(0).widget().setSizes([300, 680])
        config.workspace_tabs.setMinimumHeight(220)
        # With logs simultaneously docked below the editor, outer scroll areas
        # may become short. Keep at least one complete editable table row; the
        # existing outer scroll then reveals its real cell without clipping it.
        for table in (config.materials_table, config.geometry_table, config.boolean_table, config.layer_table):
            table.setMinimumHeight(max(table.minimumHeight(),
                                       table.horizontalHeader().sizeHint().height() +
                                       table.verticalHeader().defaultSectionSize() + 24))

        # Keep the historical tab index as an explicit activation entry. The
        # actual scene/control instance is now a peer of the configuration dock.
        tabs = config.workspace_tabs
        index = config.preview3d_tab_index()
        original_tab = tabs.widget(index)
        title = tabs.tabText(index)
        current = tabs.currentIndex()
        tabs.removeTab(index)
        anchor = QWidget(tabs)
        anchor_layout = QVBoxLayout(anchor)
        show_preview = QPushButton(ui_text("Show 3D view"))
        show_preview.setProperty("workspaceText", "Show 3D view")
        anchor_layout.addWidget(show_preview)
        anchor_layout.addStretch(1)
        tabs.insertTab(index, anchor, title)
        tabs.setCurrentIndex(current)
        preview_dock = self._dock("preview", "3D view", host, original_tab, Qt.RightDockWidgetArea)
        config._workspace_preview_index = index
        config._workspace_preview_dock = preview_dock
        stack._preview_activation_index = stack.indexOf(config)
        stack.previewActivationRequested.connect(config.preview3d_user_activated)
        preview_dock.visibilityChanged.connect(
            lambda visible: None if visible else self._forget_first_dock(preview_dock))
        preview_dock.visibilityChanged.connect(config.preview3d_visibility_changed)
        show_preview.clicked.connect(lambda: (preview_dock.show(), preview_dock.raise_(),
                                               config.preview3d_user_activated()))
        preview_dock.toggleViewAction().triggered.connect(
            lambda checked: config.preview3d_user_activated() if checked else None)

        output = window.output_page
        stack.attach_dock_page(output, None)
        results_scroll = QScrollArea(host)
        results_scroll.setObjectName("workspaceResultsScroll")
        results_scroll.setWidgetResizable(True)
        results_scroll.setFrameShape(QFrame.NoFrame)
        results_scroll.setWidget(output)
        result_dock = self._dock("results", "Results view", host, results_scroll, Qt.RightDockWidgetArea)
        stack._dock_pages[stack.indexOf(output)] = (output, result_dock)

        run = window.run_page
        log_tabs = run.stdout_view.parentWidget()
        while not isinstance(log_tabs, QTabWidget):
            log_tabs = log_tabs.parentWidget()
        logs = QWidget(host)
        logs_layout = QVBoxLayout(logs)
        logs_layout.setContentsMargins(6, 6, 6, 6)
        logs_layout.addWidget(run.progress_bar)
        logs_layout.addWidget(run.progress_label)
        logs_layout.addWidget(log_tabs, 1)
        log_dock = self._dock("logs", "Execution logs", host, logs, Qt.BottomDockWidgetArea)
        stack._navigation_docks[stack.indexOf(run)] = (log_dock,)

        # An explicitly unavailable area, with no provider, controls or fake chat.
        ai = QWidget(config)
        ai_layout = QVBoxLayout(ai)
        message = QLabel(ui_text("AI assistance is not connected. This reserved area does not run actions."))
        message.setProperty("workspaceText", "AI assistance is not connected. This reserved area does not run actions.")
        message.setWordWrap(True)
        ai_layout.addWidget(message)
        ai_layout.addStretch(1)
        self._dock("ai", "AI assistance (not connected)", host, ai, Qt.RightDockWidgetArea)

    def _forget_first_dock(self, dock):
        pending = self.window.page_stack._first_navigation_docks
        for index in tuple(pending):
            pending[index] = tuple(candidate for candidate in pending[index] if candidate is not dock)

    def add_menu(self, view_menu):
        self.menu = view_menu.addMenu(ui_text("Workspace layout"))
        self.menu.setProperty("workspaceTitle", "Workspace layout")
        self.preset_actions = {}
        for key, label in PRESETS.items():
            action = self.menu.addAction(ui_text(label))
            action.setProperty("workspaceTitle", label)
            action.setObjectName("workspacePreset_" + key)
            action.triggered.connect(lambda _checked=False, selected=key: self.apply_preset(selected))
            self.preset_actions[key] = action
        self.menu.addSeparator()
        for label, callback in (("Save current layout", self.save),
                                ("Restore saved layout", self.restore),
                                ("Reset workspace layout", self.reset)):
            action = self.menu.addAction(ui_text(label))
            action.setProperty("workspaceTitle", label)
            action.triggered.connect(callback)
        self.menu.addSeparator()
        for dock in self.docks.values():
            self.menu.addAction(dock.toggleViewAction())

    def refresh_language(self):
        for dock in self.docks.values():
            dock.setWindowTitle(ui_text(dock.property("workspaceTitle")))
        if hasattr(self, "menu"):
            self.menu.setTitle(ui_text("Workspace layout"))
            for action in self.menu.actions():
                title = action.property("workspaceTitle")
                if title:
                    action.setText(ui_text(title))
        for label in self.window.findChildren(QWidget):
            text = label.property("workspaceText")
            if text:
                label.setText(ui_text(text))

    def apply_preset(self, preset: str):
        if preset not in PRESETS:
            raise ValueError("unknown workspace preset")
        self.preset = preset
        host = self.hosts["workspace"]
        areas = {
            "configuration": Qt.LeftDockWidgetArea,
            "ai": Qt.RightDockWidgetArea,
            "preview": Qt.RightDockWidgetArea,
            "results": Qt.RightDockWidgetArea,
            "logs": Qt.BottomDockWidgetArea if preset != "analysis" else Qt.RightDockWidgetArea,
        }
        visible = {"configuration": {"configuration", "preview"},
                   "running": {"configuration", "preview", "logs"},
                   "analysis": {"configuration", "results"}}[preset]
        for index in self.window.page_stack._first_navigation_docks:
            self.window.page_stack._first_navigation_docks[index] = (
                (self.docks["preview"],) if "preview" in visible else ())
        for name, dock in self.docks.items():
            dock.setFloating(False)
            host.addDockWidget(areas[name], dock)
            dock.setVisible(name in visible)
        host.resizeDocks([self.docks["configuration"], self.docks["preview"], self.docks["results"]],
                         [700 if preset == "configuration" else 560, 440, 760], Qt.Horizontal)
        host.resizeDocks([self.docks["logs"]], [260], Qt.Vertical)

    @staticmethod
    def _screens():
        return [{"name": screen.name(), "geometry": [screen.availableGeometry().x(),
                 screen.availableGeometry().y(), screen.availableGeometry().width(),
                 screen.availableGeometry().height()]} for screen in QApplication.screens()]

    def save(self):
        payload = {"version": STATE_VERSION, "preset": self.preset,
                   "page": self.window.page_stack.currentIndex(),
                   "initial_configuration_preview": self.docks["preview"] in
                       self.window.page_stack._first_navigation_docks.get(
                           self.window.page_stack.indexOf(self.window.config_builder_page), ()),
                   "geometry": _encoded(self.window.saveGeometry()),
                   "hosts": {name: _encoded(host.saveState(STATE_VERSION)) for name, host in self.hosts.items()},
                   "screens": self._screens()}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        envelope = {"payload": payload, "sha256": hashlib.sha256(body.encode()).hexdigest()}
        self.settings.setValue(STATE_KEY, json.dumps(envelope, ensure_ascii=False))
        self.settings.sync()
        saved = self.settings.status() == QSettings.NoError
        self.window.statusBar().showMessage(ui_text("Workspace layout saved on this computer." if saved
                                                   else "Workspace layout could not be saved."), 8000)
        return saved

    def _fit_window(self):
        screens = QApplication.screens()
        if not screens:
            return
        target = QApplication.primaryScreen().availableGeometry()
        rect = self.window.frameGeometry()
        if any(screen.availableGeometry().contains(rect) for screen in screens):
            return
        self.window.setMinimumSize(min(self.window.minimumWidth(), target.width()),
                                   min(self.window.minimumHeight(), target.height()))
        self.window.resize(min(self.window.width(), target.width()), min(self.window.height(), target.height()))
        self.window.move(target.topLeft())

    def restore(self):
        raw = self.settings.value(STATE_KEY)
        if raw is None:
            self.last_restore = "default"
            self._fit_window()
            return False
        try:
            if not isinstance(raw, str) or len(raw) > MAX_STATE_BYTES:
                raise ValueError("oversize or non-text layout")
            envelope = json.loads(raw)
            payload = envelope["payload"]
            body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if envelope["sha256"] != hashlib.sha256(body.encode()).hexdigest():
                raise ValueError("layout checksum mismatch")
            if type(payload["version"]) is not int or payload["version"] != STATE_VERSION:
                raise ValueError("unsupported layout version")
            if set(payload["hosts"]) != set(self.hosts) or payload["preset"] not in PRESETS:
                raise ValueError("incomplete layout")
            if type(payload["page"]) is not int or not 0 <= payload["page"] < self.window.page_stack.count():
                raise ValueError("invalid navigation page")
            if type(payload.get("initial_configuration_preview", False)) is not bool:
                raise ValueError("invalid initial configuration layout")
            states = {name: _decoded(value) for name, value in payload["hosts"].items()}
            geometry = _decoded(payload["geometry"])
            if not isinstance(payload["screens"], list):
                raise ValueError("missing screen facts")
            if not self.window.restoreGeometry(geometry):
                raise ValueError("invalid Qt geometry")
            for name, host in self.hosts.items():
                if not host.restoreState(states[name], STATE_VERSION):
                    raise ValueError("invalid Qt dock state")
            self.preset = payload["preset"]
            self.window.page_stack._first_navigation_docks.clear()
            if payload.get("initial_configuration_preview", False):
                self.window.page_stack._first_navigation_docks[
                    self.window.page_stack.indexOf(self.window.config_builder_page)] = (self.docks["preview"],)
            self.window.page_stack.restore_current_index(payload["page"])
            if payload["screens"] != self._screens():
                # Qt can restore floats onto an unplugged display. Redock when
                # screen names or available rectangles change, retaining content.
                self.apply_preset(self.preset)
                self.last_restore = "screen_fallback"
                self.window.statusBar().showMessage(ui_text(
                    "Display configuration changed; floating panels were docked on the current screen."), 10000)
            else:
                self.last_restore = "restored"
                self.window.statusBar().showMessage(ui_text("Workspace layout restored."), 8000)
            self._fit_window()
            return True
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            self.apply_preset("configuration")
            self._fit_window()
            self.last_restore = "invalid_fallback"
            self.window.statusBar().showMessage(ui_text(
                "Workspace layout could not be restored; the default layout was used."), 10000)
            return False

    def reset(self):
        self.settings.remove(STATE_KEY)
        self.settings.sync()
        self.apply_preset("configuration")
        self._fit_window()
        self.last_restore = "reset"
        self.window.statusBar().showMessage(ui_text("Workspace layout reset."), 8000)
