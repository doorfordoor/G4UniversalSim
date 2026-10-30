"""Standard history copies must not inherit another project's CLI run overrides.

The actual Run entry and inspection callback construct the final command; the
inspection reply is synthetic and QProcess/runner starts are intercepted.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QWidget
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.history import run_history_store
from gui_test_window import MainWindow
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.window import project as project_window
from smoke_project_import_projection import snapshot


def package_fixture(root, seed=43):
    geometry = ROOT / "config/geometry/simple_box.ini"
    paths = PathSettings(executable=sys.executable, workspace_root=str(ROOT), runs_root=str(root),
                         materials_config=str(ROOT / "config/materials/material.ini"), geometry_config=str(geometry))
    # Real API permits old flat mirrors; the recorded run/main remain authoritative here.
    project = G4USimProject(projectName="writer_run", executable="stale-snapshot-backend",
                            workspaceRoot=str(ROOT), runsRoot=str(root), threads=1, seed="")
    package, _ = create_run_package(project=project, paths=paths,
                                    run=RunSettings(run_name="writer_run", threads=2, seed=seed, beam_on=2),
                                    geometry=GeometrySettings(template="simple_box", config_path=str(geometry)),
                                    source=SourceSettings(), physics=PhysicsSettings(), scoring=ScoringSettings())
    return package


def current_project(window, runs):
    candidate = copy.deepcopy(window._default_project())
    candidate.executable = sys.executable
    candidate.runsRoot = str(runs)
    candidate.threads = candidate.runSettings.threads = 7
    candidate.seed = "999"
    candidate.runSettings.seed = 999
    candidate.runName = candidate.runSettings.run_name = "unrelated_current_run"
    window._set_project(candidate)
    for timer in window.findChildren(QTimer):
        timer.stop()


def argument(command, key):
    return command[command.index(key) + 1] if key in command else None


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4USimSmoke")
    app.setApplicationName("DuplicateHistoryCLI")
    app.setQuitOnLastWindowClosed(False)
    set_application_language(app, "en")
    with tempfile.TemporaryDirectory(prefix="e6-duplicate-cli-") as temporary:
        work = Path(temporary)
        runs = work / "runs"
        runs.mkdir()
        run_history_store.STATE_PATH = work / "state.json"
        window = MainWindow()
        boxes = []
        def record(_parent, title, message, *_a, **_k):
            boxes.append((str(title), str(message)))
        with patch.object(project_window.QMessageBox, "warning", side_effect=record):
            for seed, edited in ((43, False), (0, False), (None, False), (43, True), (43, "unicode_name"), (43, "ascii_name")):
                package = package_fixture(runs, seed)
                main = Path(package.main_ini_path)
                if edited is True:
                    main.write_text(main.read_text(encoding="utf-8").replace("threads = 2\n", "threads = 3\n")
                                    .replace("seed = 43\n", "seed = 83\n")
                                    .replace("name = writer_run\n", "name = actual_main_run\n"), encoding="utf-8")
                elif edited == "unicode_name":
                    main.write_text(main.read_text(encoding="utf-8").replace("name = writer_run\n", "name = Alpha 名称\u3000Tail\u00a0\n"), encoding="utf-8")
                elif edited == "ascii_name":
                    main.write_text(main.read_text(encoding="utf-8").replace("name = writer_run\n", "name = \t ordinary name \t \n"), encoding="utf-8")
                captured_source = {p: p.read_bytes() for p in Path(package.package_dir).rglob("*") if p.is_file()}
                old_snapshot = json.loads(Path(package.project_snapshot_path).read_text(encoding="utf-8"))
                assert old_snapshot["threads"] == 1 and old_snapshot["seed"] == ""
                for run_after in (False, True):
                    current_project(window, runs)
                    inspection, starts = [], []
                    boxes.clear()
                    with patch.object(window._macro_inspection, "start", side_effect=lambda: inspection.append(window._macro_inspection.arguments())), \
                         patch.object(window.runner, "start", side_effect=lambda project, command: starts.append((project, command))):
                        window.duplicate_history_package(package.package_dir, run_after=run_after)
                        assert not boxes, boxes
                        assert not starts
                        if not run_after:
                            assert not inspection
                            window.start_run()
                        assert len(inspection) == 1
                        assert inspection[0][0] == "--inspect-run"
                        plan = {"schema": "G4UniversalSimRunPlan", "version": 1,
                                "macro_plan": {"commands": [{"file": window.project.macroPath, "line": 1,
                                                              "category": "beam_on", "text": "/run/beamOn 2"}]},
                                "initial_configuration": [], "macro_execution_planned": True}
                        with patch.object(window._macro_inspection, "readAllStandardOutput", return_value=json.dumps(plan).encode()), \
                             patch.object(window._macro_inspection, "readAllStandardError", return_value=b""):
                            window._on_macro_inspection_finished(0, QProcess.NormalExit)
                        assert len(starts) == 1
                    project, command = starts[0]
                    expected_threads, expected_seed, expected_name = ((3, "83", "actual_main_run") if edited is True else
                        (2, None if seed is None else str(seed),
                         {"unicode_name": "Alpha 名称\u3000Tail\u00a0", "ascii_name": "ordinary name"}.get(edited, "writer_run")))
                    assert command[0] == sys.executable == project.executable
                    assert argument(command, "--threads") == str(expected_threads)
                    assert argument(command, "--seed") == expected_seed
                    assert argument(command, "--run-name") == expected_name
                    assert argument(inspection[0], "--threads") == str(expected_threads)
                    assert argument(inspection[0], "--seed") == expected_seed
                    assert project.threads == project.runSettings.threads == expected_threads
                    assert project.seed == (expected_seed or "")
                    assert project.runSettings.seed == (None if expected_seed is None else int(expected_seed))
                    assert project.runName == project.runSettings.run_name == expected_name
                    assert Path(project.workspaceRoot) == Path(project.configPath).parents[1]
                    assert window._macro_inspection.workingDirectory() == project.workspaceRoot
                    assert not window.runner.is_running() and window._macro_inspection.state() == QProcess.NotRunning
                    assert all(path.read_bytes() == raw for path, raw in captured_source.items())
            for field, replacement in (("threads", "1025"), ("seed", "invalid")):
                package = package_fixture(runs)
                main = Path(package.main_ini_path)
                main.write_text(main.read_text(encoding="utf-8").replace(f"{field} = {2 if field == 'threads' else 43}\n", f"{field} = {replacement}\n"), encoding="utf-8")
                current_project(window, runs)
                widgets = window.findChildren(QWidget)
                old = snapshot(window, widgets)
                boxes.clear()
                with patch.object(window._macro_inspection, "start") as inspect_start, patch.object(window.runner, "start") as run_start:
                    window.duplicate_history_package(package.package_dir, run_after=True)
                    assert len(boxes) == 1 and field in boxes[0][1], boxes
                    assert boxes[0][0] == ("Copy created; not loaded or run" if field == "threads" else "Duplicate failed"), boxes
                    assert not inspect_start.called and not run_start.called
                assert snapshot(window, widgets) == old
            # A real post-copy parse failure keeps the created files but never publishes the candidate.
            package = package_fixture(runs)
            original_main = Path(package.main_ini_path).read_bytes()
            current_project(window, runs)
            widgets = window.findChildren(QWidget)
            old = snapshot(window, widgets)
            created = []
            real_reader = project_window.read_generated_run_settings
            def corrupt_after_copy(package_dir):
                target = Path(package_dir) / "config/main.ini"
                created.append(target)
                target.write_text(target.read_text(encoding="utf-8").replace("seed = 43\n", "seed = invalid\n"), encoding="utf-8")
                return real_reader(package_dir)
            boxes.clear()
            with patch.object(project_window, "read_generated_run_settings", side_effect=corrupt_after_copy), \
                 patch.object(window._macro_inspection, "start") as inspect_start, \
                 patch.object(window.runner, "start") as run_start:
                window.duplicate_history_package(package.package_dir, run_after=True)
                assert len(boxes) == 1 and boxes[0][0] == "Copy created; not loaded or run", boxes
                assert "no run was started" in boxes[0][1] and "seed" in boxes[0][1]
                assert len(created) == 1 and created[0].is_file() and str(created[0].parents[1]) in boxes[0][1]
                assert not inspect_start.called and not run_start.called
            assert snapshot(window, widgets) == old
            assert Path(package.main_ini_path).read_bytes() == original_main
        window.close()
        window.deleteLater()
        app.processEvents()
    print("smoke_duplicate_history_cli: ok")


if __name__ == "__main__":
    main()
