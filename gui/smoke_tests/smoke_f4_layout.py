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
