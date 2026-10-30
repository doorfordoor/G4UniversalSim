"""Read-only production-path probes; emits confirmed Q1 defects, not an acceptance gate."""
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
        assert not facts["save_failure_preserves_original"]
        future = projects.project_to_dict(projects.G4USimProject())
        future["version"] = 999
        future["future_setting"] = {"required": True}
        loaded = projects.project_from_dict(future)
        saved = projects.project_to_dict(loaded)
        facts["future_version_roundtrip"] = {"loaded_version": loaded.version, "saved_version":saved["version"],
                                             "unknown_field_preserved": "future_setting" in saved}
        assert saved["version"] != 999 and "future_setting" not in saved
        stale_dir = work / "old-results"
        stale_dir.mkdir()
        (stale_dir / "run_summary.txt").write_text("status = completed\nrun_name = OLD_RUN\n",encoding="utf-8")
        page = OutputPage()
        page.set_output_dir(str(stale_dir))
        assert "OLD_RUN" in page.summary_text.toPlainText()
        page.set_output_dir(str(work / "missing-results"))
        facts["old_summary_after_missing_results_switch"] = "OLD_RUN" in page.summary_text.toPlainText()
        assert facts["old_summary_after_missing_results_switch"]
        page.close();page.deleteLater()
        zero_dir = work / "zero-results"
        zero_dir.mkdir()
        (zero_dir / "run_summary.txt").write_text("status = completed\nplanned_event_count = 0\nactual_completed_event_count = 0\nsimulation_executed = true\n",encoding="utf-8")
        manifest = scan.ScanManifest("test","p","p",["1"],str(work),"now",points=[scan.ScanPoint(0,"1",str(work),str(zero_dir))])
        facts["scan_zero_events_state"] = scan.collect(manifest)[0].state
        assert facts["scan_zero_events_state"] == "success"
        controller = BackendGeometryController()
        delivered = []
        controller.meshReady.connect(lambda mesh, cached: delivered.append(mesh.name))
        controller.is_running = lambda: True
        controller._cache["A"] = SimpleNamespace(name="A")
        controller._running = GeometryInputs("B")
        controller.request(GeometryInputs("A"), "unused", "unused")
        controller._finish(SimpleNamespace(name="B"), "")
        facts["cached_geometry_then_old_completion"] = delivered
        assert delivered == ["A", "B"]
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
            window.close()
            app.processEvents()
            facts["main_run_alive_after_window_close"] = window.runner.is_running()
            assert facts["main_run_alive_after_window_close"]
            window.runner.kill()
            window.runner._process.waitForFinished(5000)
            window.deleteLater()
            app.processEvents()
    destination = ROOT / "out/verification/q1-public-paths.json"
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(facts,ensure_ascii=False,indent=2))
    print("AUDIT REPRODUCED DEFECTS; NOT acceptance PASS")


if __name__ == "__main__":
    main()
