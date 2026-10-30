"""F4 real Qt controls: exact targets, stale rejection and read-only source evidence."""
from __future__ import annotations

from dataclasses import asdict, replace
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402
from PySide6.QtTest import QSignalSpy, QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from g4usim_gui.core.diagnostics import (  # noqa: E402
    Diagnostic, EditorLocation, SourceLocation, collect_diagnostics, source_location,
)
from g4usim_gui.core.i18n import apply_language  # noqa: E402
from g4usim_gui.core.project import G4USimProject  # noqa: E402
from g4usim_gui.editors.geometry_editor_model import (  # noqa: E402
    BooleanOperationRow, GeometryDocument, HierarchicalVolumeRow, LayerRow,
)
from g4usim_gui.editors.material_editor_model import MaterialDocument, MaterialRow  # noqa: E402
from g4usim_gui.validators.config_validator import ValidationReport  # noqa: E402
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage  # noqa: E402
from g4usim_gui.widgets.diagnostic_navigation import (  # noqa: E402
    WidgetHighlighter, can_reveal_widget, checked_source_text, source_view_text,
)


def report_for(page, *records):
    report = ValidationReport()
    # Public typed producer path, retaining normal text report behavior.
    for record in records:
        report.add(record.code, record.severity, record.message, origin=record.origin,
                   location=record.location, source=record.source,
                   message_key=record.message_key, params=dict(record.params),
                   raw_message=record.raw_message, unavailable_reason=record.unavailable_reason)
    page.set_validation_report(report)
    return report, page.diagnostic_panel.records


def diagnostic(editor, field, collection="", row=None, entity="", *, code="test.target"):
    return Diagnostic(code, "error", "test", "A deliberately invalid field",
                      location=EditorLocation(editor, field, collection, row, entity))


def model_state(page):
    return tuple(asdict(getattr(page, name)) for name in (
        "material_document", "geometry_document", "source_editor", "physics_editor", "scoring_editor"))


def hierarchy(page):
    page.geometry_document = GeometryDocument(mode="hierarchical", is_dirty=True, volumes=[
        HierarchicalVolumeRow(name="World", shape="box", size="10 cm, 10 cm, 10 cm", material="G4_AIR"),
        HierarchicalVolumeRow(name="Sensor", parent="World", shape="box", size="1 mm, 1 mm, 1 mm",
                              material="G4_Si", position="0 mm, 0 mm, 0 mm"),
    ], boolean_ops=[BooleanOperationRow(target_volume="Sensor", index=2, operation="subtraction",
                                       tool_shape="box", tool_size="0.1 mm, 0.1 mm, 0.1 mm")])
    page._populate_geometry_editor()


def assert_navigation(page, record, widget, *, row=None, column=None):
    _, records = report_for(page, record)
    before = model_state(page)
    snapshot = page._current_diagnostic_snapshot()
    changed = QSignalSpy(page.settingsChanged)
    page.workspace_tabs.setCurrentIndex(5)
    result = page.navigate_diagnostic(records[0])
    assert result.ok, (record.location, result)
    assert result.widget is widget
    assert widget.property("diagnosticFocus") is True
    assert widget.isVisible(), record.location
    if row is not None:
        assert widget.currentRow() == row
        assert widget.currentColumn() == column
    assert model_state(page) == before, "navigation wrote a model field or dirty state"
    assert page._current_diagnostic_snapshot() == snapshot, "selection changed business snapshot"
    assert changed.count() == 0
    assert page.is_diagnostic_current(records[0])
    return records[0]


def main() -> int:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("F4Navigation")
    page = ConfigBuilderPage()
    page.preview3d_auto_backend.setChecked(False)
    page.resize(1200, 850)
    page.show()
    app.processEvents()

    # Static forms include nested source scrolling and collapsed setup groups.
    for editor, field, widget in (
        ("source", "energy", page.source_editor_energy),
        ("source", "preview_ray_count", page.source_editor_preview_rays),
        ("physics", "reference_list", page.physics_editor_reference),
        ("physics", "enable_biasing_physics", page.physics_editor_biasing),
        ("scoring", "hist_max", page.scoring_editor_max),
        ("scoring", "trajectory_events", page.scoring_editor_trajectories),
        ("run", "seed", page.seed),
    ):
        for section in page.setup_sections:
            section.set_expanded(False)
        assert_navigation(page, diagnostic(editor, field), widget)
    assert page.setup_sections[0].is_expanded()
    assert page.run_config_tabs.currentIndex() == 2

    # Dynamic tables use row + current object identity, never first name match.
    hierarchy(page)
    assert_navigation(page, diagnostic("geometry", "material", "volumes", 1, "Sensor"),
                      page.geometry_table, row=1, column=4)
    assert page.workspace_tabs.currentIndex() == 1 and page.geometry_editor_tabs.currentIndex() == 2
    assert_navigation(page, diagnostic("booleans", "operation", "boolean_ops", 0, "Sensor[2]"),
                      page.boolean_table, row=0, column=3)
    assert page.workspace_tabs.currentIndex() == 2

    # Selecting material/layer detail must not activate setters or mark dirty.
    page.material_document = MaterialDocument(rows=[
        MaterialRow(name="First", density="1 g/cm3", components_text="G4_Si:1"),
        MaterialRow(name="Second", density="2 g/cm3", components_text="G4_Si:1"),
    ], is_dirty=True)
    page._populate_material_editor()
    assert_navigation(page, diagnostic("materials", "density", "rows", 1, "Second"), page.material_density)
    assert page._selected_material_row == 1 and page.material_density.text() == "2 g/cm3"
    assert_navigation(page, diagnostic("materials", "components_text", "rows", 0, "First"), page.material_components)
    assert page._selected_material_row == 0
    page.geometry_document = GeometryDocument(mode="layered_device", is_dirty=True)
    page.geometry_document.layered_device.layers = [LayerRow(name="First"), LayerRow(name="Second", thickness="3 um")]
    page._populate_geometry_editor()
    assert_navigation(page, diagnostic("layers", "thickness", "layers", 1, "Second"), page.layer_thickness)
    assert page._selected_layer_row == 1 and page.layer_thickness.text() == "3 um"
    assert_navigation(page, diagnostic("layers", "gap", "layered_device"), page.layered_gap)
    page.geometry_document = GeometryDocument(mode="simple_box", is_dirty=True)
    page._populate_geometry_editor()
    assert_navigation(page, diagnostic("geometry", "target_size", "simple_box"), page.simple_target_size)

    # Producer-driven invalid volume size maps to its actual editable cell.
    hierarchy(page)
    page.geometry_document.volumes[1].size = "bad"
    page._populate_geometry_editor()
    typed = [item for item in collect_diagnostics(page.geometry_document)
             if item.location and item.location.collection == "volumes" and item.location.field == "size"]
    assert typed
    assert_navigation(page, typed[0], page.geometry_table, row=1, column=6)

    page.geometry_document.volumes[1].name = "World"
    page._populate_geometry_editor()
    assert_navigation(page, diagnostic("geometry", "material", "volumes", 1, "World"),
                      page.geometry_table, row=1, column=4)
    hierarchy(page)

    # Unsupported/ambiguous/missing/identity mismatch never changes tab or selection.
    for record in (
        diagnostic("geometry", "production_cut", "volumes", 1, "Sensor"),
        diagnostic("geometry", "material", "volumes", None, "Sensor"),
        diagnostic("geometry", "material", "volumes", 99, "Sensor"),
        diagnostic("geometry", "material", "volumes", 1, "Other"),
        diagnostic("booleans", "operation", "boolean_ops", 0, "Sensor[99]"),
    ):
        _, records = report_for(page, record)
        page.workspace_tabs.setCurrentIndex(5)
        row = page.geometry_table.currentRow()
        column = page.geometry_table.currentColumn()
        assert not page.navigate_diagnostic(records[0]).ok
        assert page.workspace_tabs.currentIndex() == 5
        assert (page.geometry_table.currentRow(), page.geometry_table.currentColumn()) == (row, column)
    page.geometry_document.source_copy_mode = True
    _, records = report_for(page, diagnostic("geometry", "size", "volumes", 1, "Sensor"))
    assert page.navigate_diagnostic(records[0]).status == "not_editable"
    page.geometry_document.source_copy_mode = False
    page.geometry_editor_tabs.setTabEnabled(2, False)
    _, records = report_for(page, diagnostic("geometry", "size", "volumes", 1, "Sensor"))
    page.workspace_tabs.setCurrentIndex(5)
    assert not page.navigate_diagnostic(records[0]).ok and page.workspace_tabs.currentIndex() == 5
    page.geometry_editor_tabs.setTabEnabled(2, True)
    for method in (page.source_editor_energy.hide, lambda: page.source_editor_energy.setEnabled(False),
                   lambda: page.source_editor_energy.setReadOnly(True)):
        method()
        _, records = report_for(page, diagnostic("source", "energy"))
        page.workspace_tabs.setCurrentIndex(5)
        assert not page.navigate_diagnostic(records[0]).ok
        assert page.workspace_tabs.currentIndex() == 5
        page.source_editor_energy.show()
        page.source_editor_energy.setEnabled(True)
        page.source_editor_energy.setReadOnly(False)
    item = page.geometry_table.item(1, 6)
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    _, records = report_for(page, diagnostic("geometry", "size", "volumes", 1, "Sensor"))
    assert page.navigate_diagnostic(records[0]).status == "not_editable"
    item.setFlags(item.flags() | Qt.ItemIsEditable)
    source_parent = page.source_editor_energy.parentWidget()
    source_parent.hide()
    assert not can_reveal_widget(page.source_editor_energy).ok
    source_parent.show()

    # An edit, even if reverted to its initial text, cannot revive a prior report.
    _, records = report_for(page, diagnostic("run", "seed"))
    saved_seed = page.seed.text()
    page.seed.setText("not a seed")
    page.seed.setText(saved_seed)
    assert page.diagnostic_panel.stale
    assert page.navigate_diagnostic(records[0]).status == "stale"
    assert not page.diagnostic_panel.locate_button.isEnabled()

    # Programmatic mutations with blocked UI signals are also detected at activation.
    for mutate in (
        lambda: page.geometry_document.volumes.reverse(),
        lambda: page.geometry_document.volumes.pop(),
        lambda: setattr(page.geometry_document.volumes[1], "name", "Renamed"),
        lambda: setattr(page.source_editor, "energy", "999 MeV"),
    ):
        hierarchy(page)
        _, records = report_for(page, diagnostic("geometry", "material", "volumes", 1, "Sensor"))
        page.workspace_tabs.setCurrentIndex(5)
        mutate()
        assert page.navigate_diagnostic(records[0]).status == "stale"
        assert page.workspace_tabs.currentIndex() == 5
    hierarchy(page)
    _, records = report_for(page, diagnostic("geometry", "material", "volumes", 1, "Sensor"))
    page.geometry_table.blockSignals(True)
    page.geometry_table.item(1, 4).setText("G4_Al")
    page.geometry_table.blockSignals(False)
    assert page.navigate_diagnostic(records[0]).status == "stale"
    page._populate_hierarchical_tables()

    # Editing a delegate has not committed a table/model value yet. It must
    # invalidate immediately, including Escape/undo restoring the old value.
    _, records = report_for(page, diagnostic("geometry", "material", "volumes", 1, "Sensor"))
    page.workspace_tabs.setCurrentIndex(1)
    page.geometry_editor_tabs.setCurrentIndex(2)
    page.geometry_table.editItem(page.geometry_table.item(1, 4))
    app.processEvents()
    draft = next(widget for widget in page.geometry_table.findChildren(QLineEdit) if widget.isVisible())
    before = model_state(page)
    QTest.keyClicks(draft, "draft")
    assert page.diagnostic_panel.stale and model_state(page) == before
    QTest.keyClick(draft, Qt.Key_Escape)
    assert page.navigate_diagnostic(records[0]).status == "stale"
    assert model_state(page) == before

    # The parent owns project fields; forwarding occurs only after our guard.
    forwarded = QSignalSpy(page.diagnosticNavigationRequested)
    _, records = report_for(page, diagnostic("project", "executable"))
    page.workspace_tabs.setCurrentIndex(5)
    assert page.navigate_diagnostic(records[0]).status == "delegated"
    assert forwarded.count() == 1 and page.workspace_tabs.currentIndex() == 5
    page.seed.setText("41")
    assert page.navigate_diagnostic(records[0]).status == "stale" and forwarded.count() == 1
    _, records = report_for(page, diagnostic("setup", "executable"))
    assert page.navigate_diagnostic(records[0]).status == "delegated" and forwarded.count() == 2

    # Reusing an old report is not a fresh validation; language/theme do not edit.
    old_report, old_records = report_for(page, diagnostic("source", "energy"))
    page.seed.setText("17")
    page.set_validation_report(old_report)
    assert page.diagnostic_panel.stale
    _, records = report_for(page, diagnostic("source", "energy"))
    before = page._current_diagnostic_snapshot()
    apply_language(page, "zh_CN")
    page.refresh_language()
    page.refresh_theme()
    assert before == page._current_diagnostic_snapshot()
    assert not page.diagnostic_panel.stale and page.navigate_diagnostic(records[0]).ok
    assert not page.is_diagnostic_current(old_records[0])
    page.refresh_theme()
    assert page.source_editor_energy.property("diagnosticFocus") is not True
    apply_language(page, "en")
    page.refresh_language()

    # Enter activation resolves the typed record despite label text changes.
    _, records = report_for(page, diagnostic("source", "energy"))
    page.workspace_tabs.setCurrentIndex(5)
    page.diagnostic_panel.table.item(0, 3).setText("Unrelated localized display")
    page.diagnostic_panel.table.setFocus()
    QTest.keyClick(page.diagnostic_panel.table, Qt.Key_Return)
    app.processEvents()
    assert page.diagnostic_navigator.highlighter.target is page.source_editor_energy
    assert page.workspace_tabs.currentIndex() == 4
    page.workspace_tabs.setCurrentIndex(5)
    page.diagnostic_panel.locate_button.click()
    assert page.workspace_tabs.currentIndex() == 4

    # Legacy display replacement, reload, and project replacement invalidate locations.
    page.set_validation_text("Legacy text only")
    assert not page.diagnostic_panel.records and not page.is_diagnostic_current(records[0])
    assert page.validation_text.toPlainText() == "Legacy text only"
    _, records = report_for(page, diagnostic("source", "energy"))
    page.reload_materials()
    assert not page.is_diagnostic_current(records[0])
    _, records = report_for(page, diagnostic("source", "energy"))
    page.reload_geometry()
    assert not page.is_diagnostic_current(records[0])
    _, records = report_for(page, diagnostic("source", "energy"))
    page.set_from_project(G4USimProject())
    assert not page.is_diagnostic_current(records[0])

    with tempfile.TemporaryDirectory(prefix="g4-f4-navigation-") as directory:
        filename = Path(directory) / "input.ini"
        original = "[source]\nenergy = broken\n"
        filename.write_text(original, encoding="utf-8")
        source = source_location(filename, original, line=2, section="source", key="energy", value="broken")
        record = Diagnostic("ini.value", "error", "parser", "Bad input", source=source)
        _, records = report_for(page, record)
        assert page.view_diagnostic_source(records[0]).status == "source_shown"
        assert page.diagnostic_panel.source_view.isReadOnly()
        assert page.diagnostic_panel.source_view.textCursor().selectedText() == "energy = broken"
        filename.write_text("[other]\nnew = valid\n", encoding="utf-8")
        assert page.view_diagnostic_source(records[0]).status == "historical_source"
        assert "energy = broken" in page.diagnostic_panel.source_view.toPlainText()
        assert "new = valid" not in page.diagnostic_panel.source_view.toPlainText()
        assert "differs" in page.diagnostic_panel.status.text()
        result, text = source_view_text(replace(source, text_snapshot=None))
        assert result.status == "stale" and not text
        try:
            checked_source_text(source)
        except ValueError:
            pass
        else:
            assert False, "strict source helper accepted changed current text"
        filename.write_bytes(original.replace("\n", "\r\n").encode("utf-8"))
        assert checked_source_text(source) == original.rstrip("\n")
        assert source_view_text(replace(source, line=99))[0].status == "unavailable"
        assert source_view_text(SourceLocation(str(filename), line=1))[0].status == "unavailable"
        page.materials_config.setText(str(filename))
        _, records = report_for(page, diagnostic("source", "energy"))
        filename.write_text("changed on disk", encoding="utf-8")
        assert page.navigate_diagnostic(records[0]).status == "stale"

    # Highlight is transient, theme-owned and reversible, including deleted widgets.
    a, b = QLineEdit(), QLineEdit()
    a.setAccessibleDescription("original help")
    a.setProperty("diagnosticFocus", "prior")
    highlighter = WidgetHighlighter(page, duration_ms=10)
    highlighter.highlight(a, text="bad energy")
    assert a.property("diagnosticFocus") is True and a.accessibleDescription() == "bad energy"
    highlighter.highlight(b)
    assert a.property("diagnosticFocus") == "prior" and a.accessibleDescription() == "original help"
    for _ in range(100):
        if highlighter.target is None:
            break
        QTest.qWait(10)
    assert highlighter.target is None
    assert b.property("diagnosticFocus") is None
    highlighter.highlight(a)
    QTest.keyClick(a, Qt.Key_Escape)
    assert highlighter.target is None and a.property("diagnosticFocus") == "prior"
    highlighter.highlight(a)
    QTest.keyClick(page.diagnostic_panel.table, Qt.Key_Escape)
    assert highlighter.target is None and a.property("diagnosticFocus") == "prior"
    highlighter.highlight(b)
    b.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    highlighter.clear()
    assert highlighter.target is None
    a.deleteLater()

    # Invalid seed is a structured diagnostic while retaining its old raw text.
    page.seed.setText("invalid")
    report = page.validate_current(G4USimProject())
    seeds = [item for item in report.diagnostics if item.code == "run.seed.invalid"]
    assert len(seeds) == 1 and seeds[0].location == EditorLocation("run", "seed")
    assert "Seed must be an integer" in report.to_text()
    page.set_validation_report(report)
    assert page.navigate_diagnostic(seeds[0]).widget is page.seed
    page.close()
    assert page.diagnostic_navigator.highlighter.target is None
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    print("F4 navigation: exact editable targets, stale guards, keyboard, source snapshots and cleanup passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
