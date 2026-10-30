"""Regression for Q1 project, results, asynchronous preview and owned process shutdown."""
from async_wait import wait_for_idle
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import os
import sys
import tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QProcess
from g4usim_gui.core import project as projects
from g4usim_gui.core import scan
from g4usim_gui.widgets.output_page import OutputPage
from g4usim_gui.history import run_history_store
from g4usim_gui.preview3d.backend_geometry_controller import BackendGeometryController
from g4usim_gui.preview3d.backend_inputs import GeometryInputs
from gui_test_window import MainWindow


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4USimQ1Audit")
    app.setApplicationName("Q1PublicPaths")
    app.setQuitOnLastWindowClosed(False)
    facts = {}
    with tempfile.TemporaryDirectory(prefix="q1-gui-paths-") as directory:
        work = Path(directory)
        run_history_store.STATE_PATH = work / "state.json"
        p = work / "project.json"
        original = b'{"previous":"good project"}'
        p.write_bytes(original)
        with patch.object(projects.json, "dump", side_effect=OSError("injected disk write failure")):
            try:
                projects.save_project(projects.G4USimProject(), p)
            except OSError:
                pass
        facts["save_failure_preserves_original"] = p.read_bytes() == original
        assert facts["save_failure_preserves_original"]
        assert not list(work.glob(".project.json.*.tmp"))
        with patch.object(projects.os, "replace", side_effect=OSError("injected replace failure")):
            try:
                projects.save_project(projects.G4USimProject(), p)
            except OSError:
                pass
        assert p.read_bytes() == original
        assert not list(work.glob(".project.json.*.tmp"))
        future = projects.project_to_dict(projects.G4USimProject())
        future["version"] = 999
        future["future_setting"] = {"required": True}
        for invalid in (future, {**projects.project_to_dict(projects.G4USimProject()), "unknown": 1}):
            try:
                projects.project_from_dict(invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("Unsupported content accepted")
        nested = projects.project_to_dict(projects.G4USimProject())
        nested["sourceEditor"]["unknown"] = 1
        try:
            projects.project_from_dict(nested)
        except ValueError as error:
            assert "sourceEditor.unknown" in str(error)
        else:
            raise AssertionError("Nested unsupported content accepted")
        projects.save_project(projects.G4USimProject(projectName="保留项目"), p)
        assert projects.load_project(p).projectName == "保留项目"
        facts["unsupported_content_rejected"] = True
        stale_dir = work / "old-results"
        stale_dir.mkdir()
        (stale_dir / "run_summary.txt").write_text("status = completed\nrun_name = OLD_RUN\n",encoding="utf-8")
        page = OutputPage()
        backend = work / "G4UniversalSim.exe"
        backend.touch()
        merge = work / "mergeHistograms.exe"
        merge.touch()
        (stale_dir / "hist_edep_raw_t0.csv").write_text("bin_low,bin_high,count\n0,1,1\n", encoding="utf-8")
        page.set_workspace_root(str(ROOT), str(backend))
        page.set_output_dir(str(stale_dir))
        wait_for_idle(page)
        task = next(t for t in page._merge_plan.tasks if t.kind == "hist_raw")
        assert task.available and task.command_program == str(merge)
        assert "OLD_RUN" in page.summary_text.toPlainText()
        page.set_output_dir(str(work / "missing-results"))
        wait_for_idle(page)
        facts["old_summary_after_missing_results_switch"] = "OLD_RUN" in page.summary_text.toPlainText()
        assert not facts["old_summary_after_missing_results_switch"]
        page.close();page.deleteLater()
        zero_dir = work / "zero-results"
        zero_dir.mkdir()
        (zero_dir / "run_summary.txt").write_text("status = completed\nplanned_event_count = 0\nactual_completed_event_count = 0\nsimulation_executed = true\n",encoding="utf-8")
        manifest = scan.ScanManifest("test","p","p",["1"],str(work),"now",points=[scan.ScanPoint(0,"1",str(work),str(zero_dir))])
        facts["scan_zero_events_state"] = scan.collect(manifest)[0].state
        assert facts["scan_zero_events_state"] != "success"
        (work / "logs").mkdir()
        (work / "logs/run_status.json").write_text('{"state":"success"}', encoding="utf-8")
        assert scan.collect(manifest)[0].state != "success"
        (work / "logs/run_status.json").unlink()
        (zero_dir / "run_summary.txt").write_text(
            "status = completed\nplanned_event_count = 4\nactual_completed_event_count = 4\n"
            "simulation_executed = true\nprogram_exit_code = 0\nsummary_write_status = completed\n"
            "macro_execution_status = completed\nrun_count = 2\nrun_0_id = 0\nrun_1_id = 1\n"
            "run_0_planned_events = 2\nrun_0_completed_events = 1\n"
            "run_1_planned_events = 2\nrun_1_completed_events = 3\n", encoding="utf-8")
        assert scan.collect(manifest)[0].state != "success"
        controller = BackendGeometryController()
        delivered = []
        controller.meshReady.connect(lambda mesh, cached: delivered.append(mesh.name))
        controller.is_running = lambda: True
        controller._cache["A"] = SimpleNamespace(name="A")
        controller._running = GeometryInputs("B")
        controller.request(GeometryInputs("A"), "unused", "unused")
        controller._finish(SimpleNamespace(name="B"), "")
        facts["cached_geometry_then_old_completion"] = delivered
        assert delivered == ["A"]
        controller._running = GeometryInputs("C")
        controller.request(GeometryInputs("D"), "unused", "unused")
        assert controller._pending[0].key == "D"
        controller.request(GeometryInputs("C"), "unused", "unused")
        assert controller._pending is None
        controller._finish(SimpleNamespace(name="C"), "")
        assert delivered == ["A", "C"]
        controller.is_running = lambda: False
        controller._running = GeometryInputs("E")
        controller.stop()
        controller._finish(SimpleNamespace(name="E"), "")
        assert delivered == ["A", "C"]
        controller.deleteLater()
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
            window = MainWindow()
            (work / "input.ini").write_text("[run]\n",encoding="utf-8")
            project = projects.G4USimProject(runInputMode="external", executable=sys.executable,
                configPath=str(work / "input.ini"), workspaceRoot=str(ROOT), outputDir=str(work / "output"))
            window.project = project
            window.show()
            window.runner.start(project,[sys.executable,"-c","import time; time.sleep(30)"])
            assert window.runner._process.waitForStarted(5000)
            # Each controller owns a distinct real child. No unrelated process is touched.
            children = [window.geometry_controller.process, window._macro_inspection,
                        window.output_page._merge_runner._process,
                        window.output_page._extension_runner._process]
            window.scenario_page._process = QProcess(window.scenario_page)
            children.append(window.scenario_page._process)
            for child in children:
                child.start(sys.executable, ["-c", "import time; time.sleep(30)"])
                assert child.waitForStarted(5000)
            window.scan_page.runner._queue = [123]
            window.output_page._merge_runner._queue = [object()]
            window.scan_page.runner._runner.start(project, [sys.executable, "-c", "import time; time.sleep(30)"])
            assert window.scan_page.runner._runner._process.waitForStarted(5000)
            outsider = QProcess()
            outsider.start(sys.executable, ["-c", "import time; time.sleep(30)"])
            assert outsider.waitForStarted(5000)
            window.close()
            app.processEvents()
            facts["main_run_alive_after_window_close"] = window.runner.is_running()
            assert not facts["main_run_alive_after_window_close"]
            assert window.runner.last_result.state in {"stopped", "killed"}
            assert all(child.state() == QProcess.NotRunning for child in children)
            assert not window.scan_page.runner._runner.is_running()
            assert not window.scan_page.runner._queue and not window.output_page._merge_runner._queue
            assert outsider.state() == QProcess.Running
            outsider.kill()
            assert outsider.waitForFinished(5000)
            window.runner.kill()
            window.runner._process.waitForFinished(5000)
            window.deleteLater()
            app.processEvents()
    destination = ROOT / "out/verification/q1-public-paths-regression.json"
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(facts,ensure_ascii=False,indent=2))
    print("PASS Q1 public path regressions")


if __name__ == "__main__":
    main()
