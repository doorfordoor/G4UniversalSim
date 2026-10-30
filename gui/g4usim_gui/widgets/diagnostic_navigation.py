"""Resolve diagnostic targets before changing selection; never edit configuration."""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import hashlib
from pathlib import Path
import weakref
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QComboBox, QLineEdit, QPlainTextEdit, QScrollArea, QStackedWidget, QStyledItemDelegate, QTabWidget, QTableWidget, QWidget
from shiboken6 import isValid

from g4usim_gui.core.diagnostics import Diagnostic, EditorLocation, SourceLocation, semantic_snapshot
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.editors.geometry_editor_model import HIERARCHICAL_GEOMETRY_MODES
from g4usim_gui.widgets.qt_data import combo_data
from g4usim_gui.widgets.ui_helpers import CollapsibleSection

MAX_SOURCE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class NavigationResult:
    status: str
    message: str
    widget: QWidget | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"focused", "source_shown", "historical_source"}


def _ancestors(widget: QWidget) -> list[QWidget]:
    result = []
    current = widget
    while current is not None:
        result.append(current)
        current = current.parentWidget()
    return result


def can_reveal_widget(widget: QWidget, *, allow_read_only: bool = False,
                      revealable_ancestors: tuple[QWidget, ...] = ()) -> NavigationResult:
    if not isValid(widget) or not widget.isEnabled() or widget.isHidden():
        return NavigationResult("not_editable", ui_text("This field is not currently editable."))
    if not allow_read_only and isinstance(widget, (QLineEdit, QPlainTextEdit, QAbstractSpinBox)) and widget.isReadOnly():
        return NavigationResult("not_editable", ui_text("This field is not currently editable."))
    for parent in _ancestors(widget):
        owner = parent.parentWidget()
        # Hidden tab/stack pages and collapsed sections have an explicit reveal
        # path; a separately hidden field/group must not be reported as located.
        if parent is not widget and parent.isHidden() and not parent.isWindow():
            revealable = (parent in revealable_ancestors or isinstance(owner, QStackedWidget) or
                          isinstance(owner, CollapsibleSection) and owner.group is parent)
            if not revealable:
                return NavigationResult("not_editable", ui_text("This field is not currently visible."))
        if isinstance(parent, QTabWidget):
            index = next((i for i in range(parent.count()) if parent.widget(i) is widget or
                          parent.widget(i).isAncestorOf(widget)), -1)
            if index >= 0 and not parent.isTabEnabled(index):
                return NavigationResult("not_editable", ui_text("This editor is unavailable in the current mode."))
    return NavigationResult("focused", "", widget)


def reveal_widget(widget: QWidget, *, allow_read_only: bool = False) -> NavigationResult:
    """Reveal a resolved field without enabling disabled pages or changing values."""
    result = can_reveal_widget(widget, allow_read_only=allow_read_only)
    if not result.ok:
        return result
    parents = _ancestors(widget)
    for parent in reversed(parents):
        if isinstance(parent, QTabWidget):
            for index in range(parent.count()):
                content = parent.widget(index)
                if content is widget or content.isAncestorOf(widget):
                    parent.setCurrentIndex(index)
                    break
        elif isinstance(parent, CollapsibleSection):
            parent.set_expanded(True)
        if parent.layout() is not None:
            parent.layout().activate()
    for parent in parents:
        if isinstance(parent, QScrollArea):
            parent.ensureWidgetVisible(widget, 24, 24)
            # Qt may reveal only a line edit/text edit cursor. In a narrow pane
            # that can leave the highlighted control mostly outside the view.
            center = widget.mapTo(parent.widget(), widget.rect().center())
            parent.ensureVisible(center.x(), center.y(),
                                 min(widget.width() // 2 + 24, parent.viewport().width() // 2),
                                 min(widget.height() // 2 + 24, parent.viewport().height() // 2))
    widget.setFocus(Qt.OtherFocusReason)
    return result


class WidgetHighlighter(QObject):
    """Temporary theme property and accessible text with bounded, safe cleanup."""

    def __init__(self, parent: QObject | None = None, *, duration_ms: int = 3500) -> None:
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(duration_ms)
        self.timer.timeout.connect(self.clear)
        self._target: weakref.ReferenceType | None = None
        self._previous_property: Any = None
        self._previous_description = ""

    @property
    def target(self) -> QWidget | None:
        widget = self._target() if self._target else None
        return widget if widget is not None and isValid(widget) else None

    def highlight(self, widget: QWidget, severity: str = "error", text: str = "") -> None:
        self.clear()
        if not isValid(widget):
            return
        self._target = weakref.ref(widget)
        self._previous_property = widget.property("diagnosticFocus")
        self._previous_description = widget.accessibleDescription()
        widget.setProperty("diagnosticFocus", True)
        widget.setAccessibleDescription(text or ui_text("Diagnostic target"))
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
        widget.setFocus(Qt.OtherFocusReason)
        self.timer.start()

    def clear(self) -> None:
        self.timer.stop()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        widget = self.target
        self._target = None
        if widget is not None:
            widget.setProperty("diagnosticFocus", self._previous_property)
            widget.setAccessibleDescription(self._previous_description)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.clear()
        return False


class DiagnosticDraftDelegate(QStyledItemDelegate):
    """Keep normal Qt editing, but invalidate as soon as a cell draft is edited."""

    def __init__(self, table: QTableWidget, invalidate) -> None:
        super().__init__(table)
        self.invalidate = invalidate

    def createEditor(self, parent, option, index):  # noqa: N802
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.textEdited.connect(self.invalidate)
        return editor


_TRANSIENT = {"errors", "warnings", "info", "source_errors", "source_warnings",
              "validation_errors", "validation_warnings", "round_trip_blockers", "diagnostics"}


def _semantic(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {key: _semantic(item) for key, item in value.items() if key not in _TRANSIENT and not key.startswith("_f4_")}
    if isinstance(value, (list, tuple)):
        return [_semantic(item) for item in value]
    return value


def _widget_value(widget: QWidget) -> Any:
    if isinstance(widget, QComboBox):
        data = combo_data(widget)
        return data if isinstance(data, (str, int, float, bool)) else widget.currentText()
    if isinstance(widget, QLineEdit):
        return widget.text()
    if hasattr(widget, "isChecked"):
        return widget.isChecked()
    return widget.value()


_STATIC_FIELDS = {
    "run": {name: name for name in ("run_name", "threads", "seed", "beam_on", "check_overlaps", "dry_run")},
    "setup": {name: name for name in ("materials_config", "geometry_config", "geometry_template")},
    "source": {
        "preset": "source_editor_preset", "particle": "source_editor_particle", "energy": "source_editor_energy",
        "position_mode": "source_editor_position_type", "position_type": "source_editor_position_type",
        "source_shape": "source_editor_shape", "shape": "source_editor_shape", "position": "source_editor_position",
        "center": "source_editor_position", "radius": "source_editor_radius", "inner_radius": "source_editor_inner_radius",
        "halfx": "source_editor_halfx", "halfy": "source_editor_halfy", "normal": "source_editor_normal",
        "confine_volume": "source_editor_confine_volume", "direction": "source_editor_direction",
        "angular_mode": "source_editor_angular_mode", "theta_min": "source_editor_theta_min",
        "theta_max": "source_editor_theta_max", "phi_min": "source_editor_phi_min", "phi_max": "source_editor_phi_max",
        "cone_half_angle": "source_editor_cone_half_angle", "focus_point": "source_editor_focus_point",
        "preview_ray_count": "source_editor_preview_rays", "preview_seed": "source_editor_preview_seed",
        "random_seed_preview": "source_editor_preview_seed",
    },
    "physics": {"mode": "physics_editor_mode", "reference": "physics_editor_reference",
                "reference_list": "physics_editor_reference", "default_cut": "physics_editor_default_cut",
                "enable_biasing": "physics_editor_biasing", "enable_biasing_physics": "physics_editor_biasing"},
    "scoring": {
        **{name: f"scoring_editor_{name}" for name in ("enabled", "hits", "event_edep", "edep", "dose", "fluence", "trajectories")},
        "raw_histogram": "scoring_editor_raw_hist", "weighted_histogram": "scoring_editor_weighted_hist",
        "hist_bins": "scoring_editor_bins", "hist_min": "scoring_editor_min", "hist_max": "scoring_editor_max",
        "volume_summary": "scoring_editor_volume_summary", "particle_summary": "scoring_editor_particle_summary",
        "auto_create_default": "scoring_editor_auto_create",
        "auto_create_default_scorers": "scoring_editor_auto_create",
        "trajectory_events": "scoring_editor_trajectories",
    },
}

_VOLUME_COLUMNS = dict(zip(("enabled", "name", "parent", "shape", "material", "position", "size", "rotation", "sensitive", "bias", "region", "dx1", "dx2", "dy1", "dy2", "dz"), range(16)))
_VOLUME_COLUMNS.update(parameters=6, **{f"shape_properties.{name}": col for name, col in zip(("dx1", "dx2", "dy1", "dy2", "dz"), range(11, 16))})
_BOOLEAN_COLUMNS = dict(zip(("enabled", "target_volume", "index", "operation", "tool_shape", "tool_size", "tool_parameters", "position", "rotation"), range(9)))
_MATERIAL_FIELDS = {"enabled": "material_enabled", "name": "material_name", "mode": "material_mode", "density": "material_density", "components_text": "material_components", "components": "material_components"}
_LAYER_FIELDS = {name: f"layer_{name}" for name in ("enabled", "name", "material", "thickness", "xy", "sensitive", "bias", "region", "copy_no", "position", "rotation")}


def configuration_snapshot(page: Any, generation: int) -> str:
    """Semantic editor state plus unparsed scalar/table drafts, never selection or labels."""
    names = {attribute for fields in _STATIC_FIELDS.values() for attribute in fields.values()}
    names.update(name for name, widget in vars(page).items()
                 if (name.startswith(("simple_", "layered_")) and isinstance(widget, (QLineEdit, QComboBox)))
                 or name in {"layered_auto_stack", "geometry_source_copy"})
    models = {name: _semantic(getattr(page, name)) for name in
              ("material_document", "geometry_document", "source_editor", "physics_editor", "scoring_editor")}
    raw = {name: _widget_value(getattr(page, name)) for name in sorted(names)}
    tables = {}
    for name, columns in (("geometry_table", 16), ("boolean_table", 9)):
        table = getattr(page, name)
        tables[name] = [[table.item(row, col).text() if table.item(row, col) else "" for col in range(columns)]
                        for row in range(table.rowCount())]
    files = {}
    for name in ("materials_config", "geometry_config"):
        path = getattr(page, name).text().strip()
        if not path:
            continue
        digest = hashlib.sha256()
        try:
            with Path(path).open("rb") as stream:
                for chunk in iter(lambda: stream.read(64 * 1024), b""):
                    digest.update(chunk)
            files[name] = digest.hexdigest()
        except OSError:
            files[name] = "unavailable"
    return semantic_snapshot(dict(generation=generation, models=models, raw=raw, tables=tables, files=files))


@dataclass
class _Resolved:
    widget: QWidget
    table: QTableWidget | None = None
    row: int | None = None
    column: int = 0
    detail: str = ""


class ConfigDiagnosticNavigator(QObject):
    def __init__(self, page: Any) -> None:
        super().__init__(page)
        self.page = page
        self.highlighter = WidgetHighlighter(page)

    def clear(self) -> None:
        self.highlighter.clear()

    def resolve(self, location: EditorLocation) -> _Resolved | NavigationResult:
        page = self.page
        editor, field, collection = location.editor, location.field, location.collection
        if editor in _STATIC_FIELDS:
            attribute = _STATIC_FIELDS[editor].get(field)
            if attribute is not None and location.row is None:
                return _Resolved(getattr(page, attribute))
        if editor == "geometry" and not collection and location.row is None:
            special = {"template": "geometry_template", "config_path": "geometry_config", "source_copy_mode": "geometry_source_copy"}
            if field in special:
                return _Resolved(getattr(page, special[field]))
        if editor in {"geometry", "layers"} and collection in {"simple_box", "layered_device"} and location.row is None:
            if page.geometry_document.source_copy_mode:
                return NavigationResult("not_editable", ui_text("This editor is unavailable in the current mode."))
            mode = "simple_box" if collection == "simple_box" else "layered_device"
            if page.geometry_document.mode != mode:
                return NavigationResult("not_editable", ui_text("This editor is unavailable in the current mode."))
            fields = ({name: f"simple_{name}" for name in ("world_size", "world_material", "target_name", "target_shape", "target_size", "target_material", "target_position", "target_rotation", "target_sensitive", "target_bias", "target_region")}
                      if mode == "simple_box" else
                      {name: f"layered_{name}" for name in ("world_size", "world_material", "axis", "gap", "z_start", "auto_stack")})
            if field in fields:
                return _Resolved(getattr(page, fields[field]))
        rows = None
        table = None
        attributes = {}
        columns = {}
        detail = ""
        if editor == "materials" and collection == "rows":
            rows, table, attributes, detail = page.material_document.rows, page.materials_table, _MATERIAL_FIELDS, "material"
        elif editor in {"geometry", "layers"} and collection == "layers":
            rows, table, attributes, detail = page.geometry_document.layered_device.layers, page.layer_table, _LAYER_FIELDS, "layer"
            if page.geometry_document.mode != "layered_device":
                return NavigationResult("not_editable", ui_text("This editor is unavailable in the current mode."))
        elif editor == "geometry" and collection == "volumes":
            rows, table, columns = page.geometry_document.volumes, page.geometry_table, _VOLUME_COLUMNS
        elif editor in {"geometry", "booleans"} and collection == "boolean_ops":
            rows, table, columns = page.geometry_document.boolean_ops, page.boolean_table, _BOOLEAN_COLUMNS
        if rows is None or field not in attributes and field not in columns:
            return NavigationResult("not_editable", ui_text("No editable control is registered for this diagnostic."))
        if editor != "materials" and page.geometry_document.source_copy_mode:
            return NavigationResult("not_editable", ui_text("This editor is unavailable in the current mode."))
        if collection in {"volumes", "boolean_ops"} and page.geometry_document.mode not in HIERARCHICAL_GEOMETRY_MODES:
            return NavigationResult("not_editable", ui_text("This editor is unavailable in the current mode."))
        row = location.row
        if row is None:
            return NavigationResult("ambiguous", ui_text("The diagnostic does not identify one current object."))
        if row >= len(rows) or row >= table.rowCount():
            return NavigationResult("target_missing", ui_text("The diagnostic target no longer exists. Validate again."))
        current = rows[row]
        if collection != "boolean_ops" and location.entity and current.name != location.entity:
            return NavigationResult("target_missing", ui_text("The diagnostic target has changed. Validate again."))
        if collection == "boolean_ops" and location.entity:
            identity = f"{current.target_volume}[{current.index}]"
            if location.entity != identity:
                return NavigationResult("target_missing", ui_text("The diagnostic target has changed. Validate again."))
        if attributes:
            return _Resolved(getattr(page, attributes[field]), table, row, 0, detail)
        column = columns[field]
        if table.item(row, column) is None:
            return NavigationResult("target_missing", ui_text("The diagnostic target no longer exists. Validate again."))
        if table.editTriggers() == QTableWidget.NoEditTriggers or not table.item(row, column).flags() & Qt.ItemIsEditable:
            return NavigationResult("not_editable", ui_text("This field is not currently editable."))
        return _Resolved(table, table, row, column)

    def navigate(self, diagnostic: Diagnostic) -> NavigationResult:
        if diagnostic.location is None:
            return NavigationResult("unavailable", ui_text("This diagnostic has no editable location."))
        target = self.resolve(diagnostic.location)
        if isinstance(target, NavigationResult):
            return target
        reachable = can_reveal_widget(target.widget)
        if not reachable.ok:
            return reachable
        self.page.diagnosticPageRequested.emit()
        if target.table is not None and target.row is not None:
            previous = target.table.blockSignals(True)
            was_building = self.page._building
            try:
                target.table.selectRow(target.row)
                target.table.setCurrentCell(target.row, target.column)
                if target.detail == "material":
                    self.page._select_material_row(target.row)
                elif target.detail == "layer":
                    self.page._select_layer_row(target.row)
            finally:
                target.table.blockSignals(previous)
                self.page._building = was_building
            item = target.table.item(target.row, target.column)
            if item is not None:
                target.table.scrollToItem(item, QTableWidget.PositionAtCenter)
        reveal_widget(target.widget)
        self.highlighter.highlight(target.widget, diagnostic.severity, diagnostic.message)
        return NavigationResult("focused", ui_format("Located field: {location}", location=diagnostic.location.field), target.widget)


def source_view_text(source: SourceLocation) -> tuple[NavigationResult, str]:
    """Use a verified logical-text snapshot; never present a new file's old line as fact."""
    if not source.text_sha256:
        return NavigationResult("unavailable", ui_text("No source content identity was recorded for this diagnostic.")), ""
    snapshot = source.text_snapshot
    if snapshot is not None and len(snapshot.encode("utf-8")) > MAX_SOURCE_BYTES:
        return NavigationResult("unavailable", ui_text("The source is too large for this diagnostic preview.")), ""
    current = None
    try:
        with Path(source.filename).open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
        if len(raw) <= MAX_SOURCE_BYTES:
            current = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    except OSError:
        pass
    current_matches = current is not None and hashlib.sha256(current.encode("utf-8")).hexdigest() == source.text_sha256
    if snapshot is None:
        if not current_matches:
            return NavigationResult("stale", ui_text("The source file differs from the diagnostic or is unavailable. Validate again.")), ""
        snapshot = current
    if hashlib.sha256(snapshot.encode("utf-8")).hexdigest() != source.text_sha256:
        return NavigationResult("stale", ui_text("The recorded source snapshot is inconsistent.")), ""
    lines = snapshot.splitlines()
    if source.line is not None and source.line > len(lines):
        return NavigationResult("unavailable", ui_text("The recorded source line is outside the available snapshot.")), ""
    # The producer counts logical lines with splitlines; normalize their display
    # boundaries explicitly instead of relying on QTextDocument's separator rules.
    text = "\n".join(lines)
    if current_matches:
        return NavigationResult("source_shown", ui_text("Source text matches the recorded diagnostic snapshot.")), text
    return NavigationResult("historical_source", ui_text("Recorded source snapshot shown. The current file differs or is unavailable; validate again before editing.")), text


# Shared forms use the same lifecycle and source-content checks as dynamic editors.
DiagnosticHighlighter = WidgetHighlighter


def checked_source_text(source: SourceLocation) -> str:
    """Return current verified text or reject; callers wanting history use source_view_text."""
    result, text = source_view_text(source)
    if result.status != "source_shown":
        raise ValueError(result.message)
    return text
