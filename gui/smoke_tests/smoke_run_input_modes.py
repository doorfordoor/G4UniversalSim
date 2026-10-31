from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QProcess, QTimer
from smoke_k1_workflow import wait_workflow, close_window
from g4usim_gui.core.run_result import RunResult

import g4usim_gui.window.run as main_window_module   # _generate_current_package lives here (E5)
from g4usim_gui.core.project import G4USimProject, project_from_dict
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.editors.geometry_editor_model import GeometryDocument
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from gui_test_window import MainWindow
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.output.run_summary_parser import parse_run_summary
from g4usim_gui.widgets.project_page import ProjectPage


ROOT = Path(__file__).resolve().parents[2]


def _configure_generated(window: MainWindow, temp_root: Path) -> None:
    executable = temp_root / "G4UniversalSim.exe"
    executable.write_text("test executable", encoding="utf-8")
    page = window.project_page
    page.executable.setText(str(executable))
    page.workspace_root.setText(str(ROOT))
    page.runs_root.setText(str(temp_root / "runs"))
    page.output_dir.setText(str(temp_root / "requested-output"))
    page.run_name.setText("generated_smoke")
    page.threads.setValue(2)
    page.seed.setText("42")
    page.run_input_mode.setCurrentIndex(page.run_input_mode.findData("generated"))

    builder = window.config_builder_page
    builder.materials_config.setText(str(ROOT / "config" / "materials" / "material.ini"))
    builder._set_geometry_template_token("simple_box")
    assert builder.geometry_settings().template == "simple_box"
    builder.geometry_config.setText(str(ROOT / "config" / "geometry" / "simple_box.ini"))
    builder.reload_materials()
    builder.reload_geometry()
    # The repository fixture contains fields outside the editable model; this is
    # the user's explicit source-copy choice, never an automatic runner action.
    builder.geometry_source_copy.setChecked(True)


def test_model_migration_and_command() -> None:
    project = G4USimProject()
    assert project.runInputMode == "generated"
    assert not project.configPath
    assert not project.macroPath

    old_external = project_from_dict({
        "schema": "G4UniversalSimProject",
        "version": 5,
        "configPath": "old/main.ini",
    })
    assert old_external.runInputMode == "external"
    old_generated = project_from_dict({"schema": "G4UniversalSimProject", "version": 5})
    assert old_generated.runInputMode == "generated"

    command_project = G4USimProject(
        runInputMode="external",
        executable="G4UniversalSim.exe",
        configPath="config.ini",
        macroPath="",
    )
    command = G4USimRunner.build_command(command_project)
    assert command[:3] == ["G4UniversalSim.exe", "--config", "config.ini"]
    assert "--macro" not in command


def test_project_page_preserves_nested_models(app: QApplication) -> None:
    project = G4USimProject()
    project.sourceEditor = SourceEditableModel(particle="neutron")
    project.pathSettings = PathSettings(materials_config="materials.ini", geometry_config="geometry.ini")
    project.geometrySettings = GeometrySettings(template="hierarchical", config_path="geometry.ini")
    project.geometryEditor = GeometryDocument(mode="hierarchical", is_dirty=True)
    source_editor = project.sourceEditor
    geometry_editor = project.geometryEditor
    path_settings = project.pathSettings
    geometry_settings = project.geometrySettings

    page = ProjectPage()
    page.set_project(project)
    page.workspace_root.setText("changed-workspace")
    page.apply_to_project(project)
    assert project.sourceEditor is source_editor
    assert project.geometryEditor is geometry_editor
    assert project.pathSettings is path_settings
    assert project.geometrySettings is geometry_settings
    assert project.sourceEditor.particle == "neutron"
    page.deleteLater()
    app.processEvents()


def test_launch_validation(temp_root: Path) -> None:
    executable = temp_root / "validation.exe"
    executable.write_text("test executable", encoding="utf-8")
    project = G4USimProject(executable=str(executable), outputDir=str(temp_root / "output"))
    assert not G4USimRunner.validate_project(project)
    assert G4USimRunner.validate_project(project, ready_to_run=True)
    runner = G4USimRunner()
    errors: list[str] = []
    runner.errorOccurred.connect(errors.append)
    runner.start(project)
    assert errors and not runner.is_running()
    assert not (temp_root / "output").exists()
    project.runInputMode = "external"
    assert G4USimRunner.validate_project(project)
    config = temp_root / "main.ini"
    config.write_text("[run]\ndry_run = true\n", encoding="utf-8")
    project.configPath = str(config)
    assert not G4USimRunner.validate_project(project, ready_to_run=True)
    assert "--macro" not in runner.build_command(project)
    project.configPath = ""
    project.macroPath = str(config)
    assert not G4USimRunner.validate_project(project, ready_to_run=True)
    assert "--config" not in runner.build_command(project)
    project.macroPath = str(temp_root)
    assert G4USimRunner.validate_project(project)
    project.macroPath = ""
    project.configPath = str(temp_root)
    assert G4USimRunner.validate_project(project)
    project.runInputMode = "invalid"
    project.configPath = str(config)
    assert G4USimRunner.validate_project(project)


def test_generated_external_and_source_copy(app: QApplication, temp_root: Path) -> None:
    window = MainWindow()
    window.show()
    app.processEvents()
    _configure_generated(window, temp_root)

    warnings: list[str] = []
    original_warning = QMessageBox.warning
    original_information = QMessageBox.information
    QMessageBox.warning = staticmethod(lambda _parent, _title, message: warnings.append(str(message)))
    QMessageBox.information = staticmethod(lambda *_args, **_kwargs: None)
    original_create = main_window_module.create_run_package
    create_calls: list[str] = []

    def counted_create(**kwargs):
        package, report = original_create(**kwargs)
        create_calls.append(package.package_dir)
        return package, report

    main_window_module.create_run_package = counted_create
    started_commands: list[list[str]] = []
    # This original writer/dispatch test deliberately uses an inert runner and
    # a synthetic readiness probe. Real backend tests below keep both real.
    window.experiment._probe = lambda _executable: {'status': 'ready'}
    def synthetic_start(_project, command=None):
        started_commands.append(list(command or []))
        window.runner.last_result = RunResult('incomplete', 'Synthetic dispatch only; no backend evidence')
        QTimer.singleShot(0, lambda: window.runner.finished.emit(0))
    window.runner.start = synthetic_start
    try:
        assert window.project.runInputMode == "generated"
        assert window._generated_package_stale
        assert "regenerated" in window.run_page.command_preview.toPlainText().lower()

        window.start_run()
        wait_workflow(app, window)
        assert len(create_calls) == 1, warnings
        assert len(started_commands) == 1
        command = started_commands[-1]
        config_arg = Path(command[command.index("--config") + 1])
        macro_arg = Path(command[command.index("--macro") + 1])
        execution_config, execution_macro = config_arg, macro_arg
        # The writer's canonical package contract remains intact. K1 executes
        # its verified resource closure, which has separate relocated paths.
        config_arg = Path(create_calls[0]) / 'config/main.ini'
        macro_arg = Path(create_calls[0]) / 'macros/run.mac'
        assert config_arg.name == "main.ini" and config_arg.parent.name == "config"
        assert macro_arg.name == "run.mac" and macro_arg.parent.name == "macros"
        assert config_arg.is_file() and macro_arg.is_file()
        prepared = window.experiment.records()[-1]
        assert execution_config.is_file() and execution_macro.is_file()
        assert str(execution_config.resolve()) in prepared['expected_inputs']
        assert str(execution_macro.resolve()) in prepared['expected_inputs']
        assert not window._generated_package_stale
        original_is_running = window.runner.is_running
        window.runner.is_running = lambda: True
        window.start_run()
        wait_workflow(app, window, predicate=lambda: not window.experiment._active)
        assert len(create_calls) == 1 and len(started_commands) == 1
        window.runner.is_running = original_is_running
        macro_text = macro_arg.read_text(encoding="utf-8")
        assert "/run/initialize" in macro_text
        assert "material" not in macro_text.lower()
        assert "geometry" not in macro_text.lower()

        alternate_materials = temp_root / "alternate_materials.ini"
        alternate_materials.write_bytes((ROOT / "config" / "materials" / "material.ini").read_bytes())
        window.config_builder_page.materials_config.setText(str(alternate_materials))
        window.config_builder_page.reload_materials()
        assert window._generated_package_stale
        assert "regenerated" in window.run_page.command_preview.toPlainText().lower()
        window.start_run()
        wait_workflow(app, window)
        assert len(create_calls) == 2, (warnings, window.experiment.records()[-1].get('reason'))
        assert create_calls[0] != create_calls[1]

        alternate_geometry = temp_root / "alternate_geometry.ini"
        alternate_geometry.write_bytes((ROOT / "config" / "geometry" / "simple_box.ini").read_bytes())
        window.config_builder_page.geometry_config.setText(str(alternate_geometry))
        window.config_builder_page.reload_geometry()
        window.config_builder_page.geometry_source_copy.setChecked(True)
        assert window._generated_package_stale
        window.start_run()
        wait_workflow(app, window)
        assert len(create_calls) == 3, (warnings, window.experiment.records()[-1].get('reason'))

        window.project_page.project_name.setText("renamed-project")
        assert window._generated_package_stale
        assert len(create_calls) == 3  # Editing must never write a new package.
        window.start_run()
        wait_workflow(app, window)
        assert len(create_calls) == 4
        assert not window._generated_package_stale
        window.project_page.workspace_root.setText(str(temp_root))
        assert window._generated_package_stale
        window.project_page.workspace_root.setText(str(ROOT))
        assert len(create_calls) == 4

        external_config = Path(window.project.configPath)
        mode_index = window.project_page.run_input_mode.findData("external")
        window.project_page.run_input_mode.setCurrentIndex(mode_index)
        window.project_page.config_path.setText(str(external_config))
        window.project_page.macro_path.clear()
        app.processEvents()
        assert window.project.runInputMode == "external"
        preview = window.run_page.command_preview.toPlainText()
        assert str(external_config) in preview
        assert "--macro" not in preview

        external_macro = temp_root / "external.mac"
        external_macro.write_text("/run/initialize\n", encoding="utf-8")
        alternate_executable = temp_root / "G4UniversalSim-alt.exe"
        alternate_executable.write_text("test executable", encoding="utf-8")
        window.project_page.executable.setText(str(alternate_executable))
        window.project_page.workspace_root.setText(str(temp_root))
        window.project_page.macro_path.setText(str(external_macro))
        window.project_page.output_dir.setText(str(temp_root / "external-output"))
        window.project_page.threads.setValue(7)
        window.project_page.seed.setText("77")
        window.project_page.run_name.setText("external-refresh")
        app.processEvents()
        preview = window.run_page.command_preview.toPlainText()
        for expected in [
            str(alternate_executable), str(external_config), str(external_macro),
            str(temp_root / "external-output"), "7", "77", "external-refresh", str(temp_root),
        ]:
            assert expected in preview

        # The default hierarchical source now round-trips. Add an intentionally
        # unsupported field to exercise the source-copy consent boundary.
        generated_index = window.project_page.run_input_mode.findData("generated")
        window.project_page.run_input_mode.setCurrentIndex(generated_index)
        builder = window.config_builder_page
        builder._set_geometry_template_token("hierarchical")
        assert builder.geometry_settings().template == "hierarchical"
        blocked_geometry = temp_root / "blocked_geometry.ini"
        original_geometry = (ROOT / "test" / "geometry" / "hierarchical_test.ini").read_text(encoding="utf-8")
        assert "vis.color = white" in original_geometry
        blocked_geometry.write_text(
            original_geometry.replace("vis.color = white", "vis.color = white\nvis.palette = sunset", 1),
            encoding="utf-8",
        )
        builder.geometry_config.setText(str(blocked_geometry))
        builder.reload_geometry()
        geometry = builder.geometry_document
        assert geometry.round_trip_blockers
        assert not geometry.source_copy_mode
        before_count = len(create_calls)
        window.start_run()
        wait_workflow(app, window)
        assert len(create_calls) == before_count
        assert any("round-trip" in item.lower() for item in warnings)

        source_bytes = Path(builder.geometry_config.text()).read_bytes()
        builder.geometry_source_copy.setChecked(True)
        window.start_run()
        wait_workflow(app, window)
        assert len(create_calls) == before_count + 1, (warnings, window.experiment.records()[-1].get('reason'),
            getattr(window.experiment.records()[-1].get('report'), 'errors', []))
        generated_geometry = Path(create_calls[-1]) / "config" / "geometry" / "geometry.ini"
        assert generated_geometry.read_bytes() == source_bytes
    finally:
        main_window_module.create_run_package = original_create
        QMessageBox.warning = original_warning
        QMessageBox.information = original_information
        close_window(app, window)
        app.processEvents()


def test_real_generated_run(app: QApplication, temp_root: Path, executable: Path) -> None:
    """Exercise Run -> package -> QProcess -> actual run summary, without source-copy."""
    assert executable.is_file(), executable
    window = MainWindow()
    warnings: list[str] = []
    errors: list[str] = []
    exits: list[int] = []
    original_warning = QMessageBox.warning
    original_information = QMessageBox.information
    QMessageBox.warning = staticmethod(lambda _parent, _title, message: warnings.append(str(message)))
    QMessageBox.information = staticmethod(lambda *_args, **_kwargs: None)
    window.runner.errorOccurred.connect(errors.append)
    window.runner.finished.connect(exits.append)
    try:
        _configure_generated(window, temp_root)
        window.project_page.executable.setText(str(executable))
        window.project_page.threads.setValue(1)
        builder = window.config_builder_page
        geometry_path = temp_root / "editable.ini"
        geometry_path.write_text(
            "[world]\nshape = box\nsize = 10 cm, 10 cm, 10 cm\nmaterial = G4_AIR\n"
            "[volume.target]\nparent = world\nshape = box\n"
            "size = 1 cm, 1 cm, 1 mm\nmaterial = G4_Si\n"
            "position = 0 mm, 0 mm, 0 mm\nrotation = 0 deg, 0 deg, 0 deg\n"
            "sensitive = true\nbias = false\n", encoding="utf-8",
        )
        builder._set_geometry_template_token("hierarchical")
        builder.geometry_config.setText(str(geometry_path))
        builder.reload_geometry()
        assert not builder.geometry_document.round_trip_blockers
        assert not builder.geometry_document.source_copy_mode
        # Make an actual editor change so this covers generated geometry as well.
        target = next(volume for volume in builder.geometry_document.volumes if volume.name == "target")
        target_row = builder.geometry_document.volumes.index(target)
        builder.geometry_table.item(target_row, 6).setText("2 cm, 1 cm, 1 mm")
        assert builder.geometry_document.volumes[target_row].size == "2 cm, 1 cm, 1 mm"
        builder.geometry_document.is_dirty = True
        builder.beam_on.setValue(3)
        window.start_run()
        assert not warnings, warnings
        deadline = time.monotonic() + 60
        while not exits and not errors and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        wait_workflow(app, window)
        assert not warnings, warnings
        assert not errors, errors
        assert exits == [0], exits
        assert window.runner.last_result is not None
        assert window.runner.last_result.state == "success", window.runner.last_result
        summary = parse_run_summary(Path(window.project.outputDir) / "run_summary.txt")
        facts = summary.key_values
        assert summary.exists and facts["status"] == "completed", summary.raw_text
        assert facts["run_count"] == "1"
        assert facts["planned_event_count"] == "3"
        assert facts["actual_completed_event_count"] == "3"
        assert facts["macro_execution_status"] == "completed"
        package = Path(window._generated_package_dir)
        report = (package / "validation_report.txt").read_text(encoding="utf-8")
        assert "generated by Geometry Editor" in report
        assert "2 cm, 1 cm, 1 mm" in (package / "config/geometry/geometry.ini").read_text(encoding="utf-8")
        run_status = json.loads((package / "logs/run_status.json").read_text(encoding="utf-8"))
        assert run_status["exitCode"] == 0
        assert run_status["state"] == "success" and run_status["summaryFresh"] is True
        print("smoke_run_input_modes: real generated QProcess run completed 3/3 events")
    finally:
        if window.runner.is_running():
            window.runner.kill()
            window.runner._process.waitForFinished(5000)
        QMessageBox.warning = original_warning
        QMessageBox.information = original_information
        close_window(app, window)
        app.processEvents()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    test_model_migration_and_command()
    test_project_page_preserves_nested_models(app)
    with tempfile.TemporaryDirectory() as tmp:
        test_launch_validation(Path(tmp))
        test_generated_external_and_source_copy(app, Path(tmp))
    backend = os.environ.get("G4USIM_EXE", "").strip()
    if backend:
        with tempfile.TemporaryDirectory() as tmp:
            test_real_generated_run(app, Path(tmp), Path(backend).resolve())
        with tempfile.TemporaryDirectory() as tmp:
            test_real_no_run_and_stale_summary(app, Path(tmp), Path(backend).resolve())
        with tempfile.TemporaryDirectory() as tmp:
            test_external_macro_inspection(app, Path(tmp), Path(backend).resolve())
    else:
        print("smoke_run_input_modes: real backend skipped; set G4USIM_EXE")
    print("smoke_run_input_modes: ok")
    return 0


def test_real_no_run_and_stale_summary(app: QApplication, temp_root: Path, executable: Path) -> None:
    macro = temp_root / "no_run.mac"
    macro.write_text("/control/echo NO_BEAMON\n", encoding="utf-8")
    project = G4USimProject(
        runInputMode="external", executable=str(executable), workspaceRoot=str(temp_root),
        macroPath=str(macro), outputDir=str(temp_root / "output"), threads=1,
    )
    runner = G4USimRunner()

    def finish() -> int:
        exits: list[int] = []
        runner.finished.connect(exits.append)
        deadline = time.monotonic() + 40
        while not exits and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        runner.finished.disconnect(exits.append)
        assert exits, "Runner did not finish"
        return exits[0]

    runner.start(project)
    assert finish() == 0
    assert runner.last_result is not None and runner.last_result.state == "no_run", runner.last_result
    summary = Path(project.outputDir) / "run_summary.txt"
    assert summary.is_file()
    # A later zero-exit process that does not write a summary must not inherit it.
    runner.start(project, [sys.executable, "-c", "pass"])
    assert finish() == 0
    assert runner.last_result is not None and runner.last_result.state == "incomplete", runner.last_result


def test_external_macro_inspection(app: QApplication, temp_root: Path, executable: Path) -> None:
    nested = temp_root / "子文件.mac"
    nested.write_text("/run/beamOn 3\n", encoding="utf-8")
    macro = temp_root / "main.mac"
    macro.write_text('/control/execute "子文件.mac"\n', encoding="utf-8")
    window = MainWindow()
    try:
        page = window.project_page
        page.executable.setText(str(executable))
        page.workspace_root.setText(str(ROOT))
        page.output_dir.setText(str(temp_root / "output"))
        page.run_input_mode.setCurrentIndex(page.run_input_mode.findData("external"))
        page.macro_path.setText(str(macro))
        window.inspect_external_macro()
        wait_workflow(app, window)
        deadline = time.monotonic() + 30
        while window._macro_inspection.state() != QProcess.NotRunning and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        plan = window.run_page.macro_plan_view.toPlainText()
        assert "Expanded commands: 1" in plan or "展开命令数：1" in plan, plan
        assert "[beam_on] /run/beamOn 3" in plan, plan
        assert "子文件.mac:1" in plan, plan

        config = temp_root / "external.ini"
        config.write_text(f"[run]\nmacro = {macro.as_posix()}\nseed = 19\n", encoding="utf-8")
        page.config_path.setText(str(config))
        page.macro_path.clear()
        launched: list[list[str]] = []
        def synthetic_start(_project, command=None):
            launched.append(list(command or []))
            window.runner.last_result = RunResult('incomplete', 'Synthetic dispatch after real Inspect')
            QTimer.singleShot(0, lambda: window.runner.finished.emit(0))
        window.runner.start = synthetic_start
        window.start_run()
        wait_workflow(app, window)
        deadline = time.monotonic() + 30
        while window._macro_inspection.state() != QProcess.NotRunning and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        assert len(launched) == 1, window.run_page.macro_plan_view.toPlainText()
        assert "--macro" not in launched[0]
        assert "macro_file" in window.run_page.macro_plan_view.toPlainText()

        conflicting = temp_root / "conflicting.mac"
        conflicting.write_text("/AIHL/output/setDir old-output\n", encoding="utf-8")
        page.macro_path.setText(str(conflicting))
        # Independent Inspect preserves the backend's original-path diagnostic;
        # the requested run below separately proves that refusal cannot launch.
        window.inspect_external_macro()
        wait_workflow(app, window)
        failure = window.run_page.macro_plan_view.toPlainText()
        assert "conflicts with an explicit CLI lock" in failure, failure
        window.start_run()
        wait_workflow(app, window)
        deadline = time.monotonic() + 30
        while window._macro_inspection.state() != QProcess.NotRunning and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        assert window.experiment.records()[-1]['status'] == 'failed'
        assert len(launched) == 1  # Failed preflight must not launch the simulation.
    finally:
        if window._macro_inspection.state() != QProcess.NotRunning:
            window._macro_inspection.kill()
            window._macro_inspection.waitForFinished(5000)
        close_window(app, window)
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
