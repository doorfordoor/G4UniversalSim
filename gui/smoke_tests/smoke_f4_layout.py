"""F4 compact layouts: diagnostics and fields remain reachable at 768px/narrow sizes."""
from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtTest import QSignalSpy  # noqa: E402
from g4usim_gui.core.diagnostics import collect_diagnostics, extend_diagnostics  # noqa: E402
from g4usim_gui.editors.geometry_editor_model import (  # noqa: E402
    BooleanOperationRow, GeometryDocument, HierarchicalVolumeRow, validate_geometry_document,
)
from g4usim_gui.editors.material_editor_model import (  # noqa: E402
    MaterialDocument, MaterialRow, validate_material_document,
)
from g4usim_gui.validators.config_validator import ValidationReport  # noqa: E402
from g4usim_gui.core.i18n import apply_language, set_application_language  # noqa: E402
from g4usim_gui.core.theme import apply_theme  # noqa: E402
from g4usim_gui.main_window import MainWindow  # noqa: E402
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard  # noqa: E402
from g4usim_gui.widgets.scenario_page import ScenarioPage  # noqa: E402
from g4usim_gui.widgets.project_page import ProjectPage  # noqa: E402
from g4usim_gui.widgets.run_page import RunPage  # noqa: E402


def visible_in_scroll(scroll, widget):
    point = widget.mapTo(scroll.viewport(), widget.rect().center())
    assert scroll.viewport().rect().contains(point), (widget.objectName(), point, scroll.viewport().rect())


def reach(app, scroll, widget):
    scroll.ensureWidgetVisible(widget, 8, 8)
    app.processEvents()
    # QTextEdit asks Qt to reveal its cursor, which need not center the large
    # control. Exercise the user's scrollbars as well as automatic field reveal.
    center = widget.mapTo(scroll.widget(), widget.rect().center())
    scroll.verticalScrollBar().setValue(center.y() - scroll.viewport().height() // 2)
    scroll.horizontalScrollBar().setValue(center.x() - scroll.viewport().width() // 2)
    app.processEvents()
    visible_in_scroll(scroll, widget)


def target_visible_through_ancestors(widget, local_rect, *, full_cell=True):
    """Selection/isVisible alone do not prove a cell survived outer clipping."""
    target = local_rect.translated(widget.mapToGlobal(local_rect.topLeft()) - local_rect.topLeft())
    clipped = target
    parent = widget
    while parent is not None:
        area = parent.rect().translated(parent.mapToGlobal(parent.rect().topLeft()))
        clipped = clipped.intersected(area)
        parent = parent.parentWidget()
    assert not clipped.isEmpty(), (target, clipped)
    assert clipped.contains(target.center()), (target, clipped)
    if full_cell:
        assert clipped == target, (target, clipped)


def check_config_targets(app, window):
    page = window.config_builder_page
    page.preview3d_auto_backend.setChecked(False)
    window.page_stack.setCurrentWidget(page)
    page.geometry_document = GeometryDocument(mode="hierarchical", is_dirty=True, volumes=[
        HierarchicalVolumeRow(name="World", shape="box", size="10 cm,10 cm,10 cm", material="G4_AIR"),
        HierarchicalVolumeRow(name="Sensor", parent="World", shape="box", size="1 mm,1 mm,1 mm", material="G4_Si"),
        HierarchicalVolumeRow(name="Sensor", parent="World", shape="box", size="bad", material="G4_Si"),
    ], boolean_ops=[BooleanOperationRow(target_volume="Sensor", index=2, operation="invalid-operation",
                                       tool_shape="box", tool_size="0.1 mm,0.1 mm,0.1 mm")])
    # A distant row also exercises the table's internal scrollbar.
    page.geometry_document.volumes.extend(HierarchicalVolumeRow(
        name=f"Far{i}", parent="World", shape="box", size="bad", material="G4_Si") for i in range(60))
    page._populate_geometry_editor()
    validate_geometry_document(page.geometry_document)
    report = ValidationReport()
    extend_diagnostics(report, collect_diagnostics(page.geometry_document))
    page.set_validation_report(report)
    for editor, row, field, table, column in (
        ("geometry", 2, "size", page.geometry_table, 6),
        ("geometry", 62, "size", page.geometry_table, 6),
        ("booleans", 0, "operation", page.boolean_table, 3),
    ):
        record = next(d for d in page.diagnostic_panel.records if d.location and
                      (d.location.editor, d.location.row, d.location.field) == (editor, row, field))
        before = asdict(page.geometry_document)
        snapshot = page._current_diagnostic_snapshot()
        changed = QSignalSpy(page.settingsChanged)
        page.workspace_tabs.setCurrentIndex(5)
        app.processEvents()
        assert page.navigate_diagnostic(record).ok
        app.processEvents()
        assert (table.currentRow(), table.currentColumn()) == (row, column)
        target_visible_through_ancestors(table.viewport(), table.visualItemRect(table.currentItem()))
        assert asdict(page.geometry_document) == before
        assert page._current_diagnostic_snapshot() == snapshot
        assert changed.count() == 0

    page.material_document = MaterialDocument(is_dirty=True, rows=[
        MaterialRow(name="Same", density="1 g/cm3", components_text="Si:1"),
        MaterialRow(name="Same", density="bad", components_text="Si:1")])
    page._populate_material_editor()
    validate_material_document(page.material_document)
    report = ValidationReport()
    extend_diagnostics(report, collect_diagnostics(page.material_document))
    page.set_validation_report(report)
    record = next(d for d in page.diagnostic_panel.records if d.location and
                  d.location.row == 1 and d.location.field == "density")
    before = asdict(page.material_document)
    snapshot = page._current_diagnostic_snapshot()
    changed = QSignalSpy(page.settingsChanged)
    page.workspace_tabs.setCurrentIndex(5)
    app.processEvents()
    assert page.navigate_diagnostic(record).ok
    app.processEvents()
    target_visible_through_ancestors(page.material_density, page.material_density.rect(), full_cell=False)
    assert page.materials_table.currentRow() == 1
    assert page.material_density.text() == "bad"
    assert asdict(page.material_document) == before
    assert page._current_diagnostic_snapshot() == snapshot
    assert changed.count() == 0


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("F4Layout")
    QSettings().clear()
    set_application_language(app, "en")
    window = MainWindow()
    window.show()
    app.processEvents()
    project = window.project_page
    run = window.run_page
    project.executable.setText("")
    window._validate_project_diagnostics()
    for language, theme in (("en", "light"), ("zh_CN", "dark")):
        window._set_language(language, persist=False)
        window._set_theme(theme)
        # MainWindow's established minimum is 1200x760; test that supported
        # boundary, then test the isolated page containers at narrower sizes.
        for width, height in ((1280, 768), (1200, 768)):
            window.resize(width, height)
            app.processEvents()
            assert window.width() == width and window.height() == height
            before = project.diagnostic_values()
            window.page_stack.setCurrentWidget(project)
            app.processEvents()
            assert project.content_scroll.widgetResizable()
            for widget in (project.executable, project.run_name, project.status_summary,
                           project.diagnostics_panel.table, project.diagnostics_panel.locate_button):
                reach(app, project.content_scroll, widget)
            assert project.diagnostic_values() == before
            window.page_stack.setCurrentWidget(run)
            app.processEvents()
            for widget in (run.command_preview, run.build_button, run.save_logs_button,
                           run.diagnostics_panel.table, run.diagnostics_panel.locate_button, run.stdout_view):
                reach(app, run.content_scroll, widget)
            assert project.diagnostic_values() == before
            record = next(d for d in run.diagnostics_panel.records if d.location.field == "executable")
            assert window._run_diagnostics.navigate(record)
            app.processEvents()
            assert window.page_stack.currentWidget() is project
            visible_in_scroll(project.content_scroll, project.executable)
            assert project.diagnostic_values() == before
            check_config_targets(app, window)

    narrow_project, narrow_run = ProjectPage(), RunPage()
    for page in (narrow_project, narrow_run):
        page.diagnostics_panel.set_records(project.diagnostics_panel.records)
        page.diagnostics_panel.show()
        page.resize(680, 640)
        page.show()
        app.processEvents()
        assert page.width() == 680 and page.height() == 640
        reach(app, page.content_scroll, page.diagnostics_panel.table)
        reach(app, page.content_scroll, page.diagnostics_panel.revalidate_button)
    for widget in (narrow_project.executable, narrow_project.seed, narrow_project.status_summary):
        reach(app, narrow_project.content_scroll, widget)
    for widget in (narrow_run.run_button, narrow_run.save_logs_button, narrow_run.stdout_view):
        reach(app, narrow_run.content_scroll, widget)

    scenario = ScenarioPage()
    scenario.show()
    app.processEvents()
    for width, height in ((1000, 768), (680, 640)):
        scenario.resize(width, height)
        scenario.advanced_check.setChecked(False)
        scenario.set_values({"threads": "2", "pore_fraction": "2"})
        scenario.validate_form()
        app.processEvents()
        assert scenario.width() == width and scenario.height() == height
        before = scenario.values()
        record = next(d for d in scenario.diagnostics_panel.records if d.location.field == "pore_fraction")
        reach(app, scenario.input_scroll, scenario.diagnostics_panel.locate_button)
        assert scenario.diagnostic_controller.navigate(record)
        app.processEvents()
        assert scenario.advanced_check.isChecked()
        visible_in_scroll(scenario.input_scroll, scenario._fields["pore_fraction"])
        for widget in (scenario._fields["threads"], scenario.validate_button, scenario.diagnostics_panel.table,
                       scenario.diagnostics_panel.revalidate_button):
            reach(app, scenario.input_scroll, widget)
        assert scenario.values() == before

    wizard = NewSimulationWizard()
    wizard.show()
    app.processEvents()
    for _ in range(3):
        wizard.next()
        app.processEvents()
    assert wizard.currentId() == 3
    wizard.run_page.seed.setText("invalid")
    app.processEvents()
    for width, height in ((720, 768), (600, 640)):
        wizard.resize(width, height)
        app.processEvents()
        assert wizard.width() == width and wizard.height() == height
        before = (asdict(wizard.spec), wizard._diagnostic_values())
        page = wizard.run_page
        for widget in (page.physics, page.seed, page.summary, page.diagnostics_panel.table,
                       page.diagnostics_panel.locate_button, page.run_after):
            reach(app, page.content_scroll, widget)
        record = next(d for d in page.diagnostics_panel.records if d.location.field == "seed")
        assert wizard.diagnostic_controller.navigate(record)
        app.processEvents()
        visible_in_scroll(page.content_scroll, page.seed)
        assert (asdict(wizard.spec), wizard._diagnostic_values()) == before

    for widget in (wizard, scenario, narrow_project, narrow_run, window):
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    print("smoke_f4_layout: 768px/narrow, scroll reachability, themes/languages and unchanged values passed")


if __name__ == "__main__":
    main()
