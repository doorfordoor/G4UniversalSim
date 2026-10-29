"""File-import GUI projection preflight and original error presentation contracts."""
from __future__ import annotations

import copy
import gc
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtCore import QTimer, Qt, QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QComboBox, QLabel, QLineEdit, QPlainTextEdit,
    QSpinBox, QTableWidget, QTabWidget, QTextEdit, QWidget,
)
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import load_project, project_to_dict
from g4usim_gui.core.wizard import WizardSpec
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.widgets.migration_dialog import MigrationDialog
from g4usim_gui.window import project as project_window


def combo_role_data(combo, row):
    model = combo.model()
    index = model.index(row, combo.modelColumn(), combo.rootModelIndex())
    return model.itemData(index).get(int(Qt.ItemDataRole.UserRole))


def widget_state(widgets):
    result = []
    for widget in widgets:
        value = [id(widget), widget.isEnabled()]
        if isinstance(widget, (QLabel, QLineEdit, QAbstractButton)):
            value.append(widget.text())
        if isinstance(widget, QAbstractButton):
            value.append(widget.isChecked())
        if isinstance(widget, QSpinBox):
            value.extend((widget.value(), widget.minimum(), widget.maximum()))
        if isinstance(widget, QComboBox):
            value.extend((widget.currentIndex(), combo_role_data(widget, widget.currentIndex()),
                          tuple((widget.itemText(i), combo_role_data(widget, i)) for i in range(widget.count()))))
        if isinstance(widget, (QPlainTextEdit, QTextEdit)):
            value.append(widget.toPlainText())
        if isinstance(widget, QTableWidget):
            value.append(tuple(tuple(widget.item(row, col).text() if widget.item(row, col) else None
                                     for col in range(widget.columnCount())) for row in range(widget.rowCount())))
        if isinstance(widget, QTabWidget):
            value.append(widget.currentIndex())
        result.append(value)
    return result


def snapshot(window, widgets):
    page = window.config_builder_page
    return copy.deepcopy({
        "project_identity": id(window.project), "project": project_to_dict(window.project),
        "file": window.project_file, "stale": window._generated_package_stale,
        "package": window._generated_package_dir, "widgets": widget_state(widgets),
        "building": (window.project_page._building, page._building),
        "editor_ids": tuple(id(obj) for obj in (page.geometry_document, page.source_editor, page.physics_editor, page.scoring_editor)),
        "geometry": asdict(page.geometry_document), "source": asdict(page.source_editor),
        "physics": asdict(page.physics_editor), "scoring": asdict(page.scoring_editor),
        "output_dir": window.output_page._output_dir,
        "inspection": (window._macro_inspection_snapshot, window._pending_inspection_run),
        "recent": run_history_store.get_recent_projects(),
    })


def assign(data, path, value):
    target = data
    components = path.removeprefix("project.").split(".")
    for component in components[:-1]:
        target = target.setdefault(component, {})
    target[components[-1]] = value


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4USimSmoke")
    app.setApplicationName("ProjectImportProjection")
    app.setQuitOnLastWindowClosed(False)
    set_application_language(app, "en")
    with tempfile.TemporaryDirectory(prefix="e6-import-projection-") as temporary:
        work = Path(temporary)
        run_history_store.STATE_PATH = work / "state.json"
        window = MainWindow()
        for timer in window.findChildren(QTimer):
            timer.stop()
        window.project_file = work / "previous.json"
        window._generated_package_stale = False
        window._generated_package_dir = "previous-package"
        window.config_builder_page.set_package_path("previous-package")
        window.run_page.set_macro_plan("previous macro inspection")
        widgets = window.findChildren(QWidget)
        before = snapshot(window, widgets)
        page = window.config_builder_page
        bindings = (
            ("project.threads", (window.project_page.threads, page.threads)),
            ("project.runSettings.threads", (page.threads,)),
            ("project.runSettings.beam_on", (page.beam_on,)),
            ("project.scoringSettings.hist_bins", (page.hist_bins,)),
            ("project.scoringEditor.hist_bins", (page.scoring_editor_bins, page.hist_bins)),
            ("project.scoringEditor.trajectory_events", (page.scoring_editor_trajectories,)),
            ("project.sourceEditor.preview_ray_count", (page.source_editor_preview_rays,)),
            ("project.sourceEditor.random_seed_preview", (page.source_editor_preview_seed,)),
        )
        boxes = []
        def record(kind):
            return lambda _parent, title, message, *_a, **_kw: boxes.append((kind, title, str(message)))
        with patch.object(project_window.QMessageBox, "critical", side_effect=record("critical")), \
             patch.object(project_window.QMessageBox, "warning", side_effect=record("warning")):
            # Both modes still populate the editors; disabled scoring is no exemption.
            for mode in ("generated", "external"):
                for path, controls in bindings:
                    minimum = max(widget.minimum() for widget in controls)
                    maximum = min(widget.maximum() for widget in controls)
                    for value in (minimum - 1, maximum + 1, 10**100, -(10**100)):
                        data = {"projectName": "rejected import", "runInputMode": mode,
                                "scoringSettings": {"enabled": False}}
                        assign(data, path, value)
                        if path.startswith("project.scoringEditor."):
                            data["scoringEditor"]["enabled"] = False
                        source = work / "rejected.json"
                        source.write_text(json.dumps(data), encoding="utf-8")
                        raw = source.read_bytes()
                        boxes.clear()
                        assert not window._load_project_path(str(source)), (mode, path, value)
                        assert len(boxes) == 1 and boxes[0][:2] == ("critical", "Open project failed"), boxes
                        assert path in boxes[0][2], boxes
                        assert snapshot(window, widgets) == before, (mode, path, value)
                        assert source.read_bytes() == raw

            missing = work / "missing-recent-project.json"
            for entry, expected, fragment in (
                (lambda: window._open_recent_project(str(missing)), ("warning", "Open recent project failed"), missing.name),
                (lambda: window.load_snapshot_into_project(str(missing)), ("warning", "Load snapshot failed"), missing.name),
                (lambda: window._load_project_path(str(missing)), ("critical", "Open project failed"), missing.name),
            ):
                boxes.clear()
                entry()
                assert len(boxes) == 1 and boxes[0][:2] == expected and fragment in boxes[0][2], boxes
                assert snapshot(window, widgets) == before

            huge = work / "huge.json"
            huge.write_text(json.dumps({"runSettings": {"beam_on": 10**100}}), encoding="utf-8")
            boxes.clear()
            with patch.object(project_window.QFileDialog, "getOpenFileName", return_value=(str(huge), "")):
                window.open_project()
            assert len(boxes) == 1 and boxes[0][:2] == ("critical", "Open project failed"), boxes
            assert "runSettings.beam_on" in boxes[0][2]
            assert snapshot(window, widgets) == before
            try:
                window._set_project(load_project(huge))
            except ValueError as error:
                assert "runSettings.beam_on" in str(error)
            else:
                assert False, "Direct publication must preflight before changing the current project"
            assert snapshot(window, widgets) == before
            # Legacy plain-project snapshots remain explicit/unverified; the
            # actual writer envelope is exercised by smoke_project_snapshot_restore.
            for entry, expected, fragment in (
                (lambda: window._open_recent_project(str(huge)), ("warning", "Open recent project failed"), "runSettings.beam_on"),
                (lambda: window.load_snapshot_into_project(str(huge)), ("warning", "Load snapshot failed"), "runSettings.beam_on"),
            ):
                boxes.clear()
                entry()
                assert len(boxes) == 1 and boxes[0][:2] == expected and fragment in boxes[0][2], boxes
                assert snapshot(window, widgets) == before

            # A format-valid copy can still be unrepresentable in this GUI.
            dialog = MigrationDialog(window, open_project=window._load_project_path)
            dialog.source_path.setText(str(huge))
            assert dialog.preview()
            migrated = work / "huge-copy.json"
            assert dialog.write_copy(migrated)
            boxes.clear()
            dialog._open_copy()
            assert len(boxes) == 1 and boxes[0][:2] == ("critical", "Open project failed"), boxes
            assert snapshot(window, widgets) == before
            assert migrated.exists()
            dialog.deleteLater()

            # The new guard must not introduce in-place partial wizard writes.
            for spec in (WizardSpec(threads=2048), WizardSpec(events=2_000_000_001)):
                boxes.clear()
                assert not window.apply_simulation_wizard(spec, run_after=False)
                assert len(boxes) == 1 and boxes[0][:2] == ("warning", "New simulation"), boxes
                assert snapshot(window, widgets) == before

        # Each real control's intersected endpoints are accepted exactly.
        for path, controls in bindings:
            for value in (max(widget.minimum() for widget in controls), min(widget.maximum() for widget in controls)):
                data = {"runInputMode": "external", "scoringSettings": {"enabled": False}}
                assign(data, path, value)
                if path == "project.runSettings.threads":
                    # The Project page owns the flat run default too; use a coherent
                    # project rather than testing conflicting historical mirrors.
                    data["threads"] = value
                source = work / "boundary.json"
                source.write_text(json.dumps(data), encoding="utf-8")
                assert window._load_project_path(str(source)), (path, value)
                assert all(widget.value() == value for widget in controls), (path, value)

        # Do not apply Qt integer limits to values rendered as strings/unused legacy data.
        safe = copy.deepcopy(window._default_project())
        safe.runSettings.seed = 10**100
        safe.scoringSettings.trajectory_events = 10**100
        safe.scoringEditor.trajectory_events = 0
        window._check_project_projection(safe)

        for preset, angular in (("FuturePreset", "FutureAngular"), ("", "")):
            source = work / "enum.json"
            source.write_text(json.dumps({"sourceEditor": {"preset": preset, "angular_mode": angular}}), encoding="utf-8")
            assert window._load_project_path(str(source))
            assert page.source_editor_preset.currentText() == preset
            assert page.source_preset.currentText() == preset
            assert page.source_editor_angular_mode.currentText() == angular
            assert window.project.sourceEditor.preset == preset
            assert window.project.sourceEditor.angular_mode == angular
        window._set_language("zh_CN", persist=False)
        with patch.object(project_window.QMessageBox, "critical", side_effect=record("critical")):
            boxes.clear()
            assert not window._load_project_path(str(huge))
            assert boxes[0][1] == "打开项目失败"
            assert "GUI" in boxes[0][2] and "project.runSettings.beam_on" in boxes[0][2]
        window.close()
        dialog.close()
        dialog.deleteLater()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
        del bindings, controls, widgets, page, dialog, timer, entry, window
        gc.collect()
        app.processEvents()
    print("smoke_project_import_projection: ok")


if __name__ == "__main__":
    main()
