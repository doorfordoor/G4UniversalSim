"""Visible Windows Q1 lifecycle check; requires G4USIM_EXE and windows Qt platform."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QProcess
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject, load_project
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow


def wait(predicate, seconds=90):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(50)
    assert predicate(), "Timed out waiting for GUI lifecycle"


def main():
    assert sys.platform == "win32"
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "windows", app.platformName()
    app.setOrganizationName("G4USimQ1Visible")
    app.setApplicationName("Q1Lifecycle")
    app.setQuitOnLastWindowClosed(False)
    work = ROOT / "out/q1-gui-review" / time.strftime("%Y%m%d-%H%M%S")
    work.mkdir(parents=True)
    run_history_store.STATE_PATH = work / "state.json"
    exe = Path(os.environ["G4USIM_EXE"]).resolve()
    facts = {"platform": app.platformName(), "executable": str(exe),
             "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest()}
    messages = []
    def dialog(*args, **kwargs):
        messages.append(str(args[2]) if len(args) > 2 else str(args))
        return QMessageBox.Ok
    with patch.object(QMessageBox, "warning", side_effect=dialog), \
         patch.object(QMessageBox, "information", side_effect=dialog), \
         patch.object(QMessageBox, "critical", side_effect=dialog):
        window = MainWindow()
        window.show()
        assert QTest.qWaitForWindowExposed(window)
        spec = wizard.default_spec("single_target")
        spec.events = 20
        project = G4USimProject()
        project.pathSettings = PathSettings(executable=str(exe), workspace_root=str(ROOT),
            runs_root=str(work / "runs"), materials_config=str(ROOT / "config/materials/material.ini"),
            geometry_config=str(ROOT / "config/geometry/simple_box.ini"))
        project.executable = str(exe)
        project.workspaceRoot = str(ROOT)
        project.runsRoot = str(work / "runs")
        wizard.apply_to_project(project, wizard.build(spec))
        window._set_project(project)
        window.project_file = work / "saved-project.json"
        window.save_project()
        assert load_project(window.project_file).projectName == window.project.projectName
        window.generate_package(False)
        assert window._generated_package_dir, messages
        output = Path(window.project.outputDir)
        assert not (output / "run_summary.txt").exists()
        facts["output"] = str(output)
        window.page_stack.setCurrentWidget(window.run_page)
        window._start_current_project()
        wait(lambda: window.runner.last_result is not None)
        assert window.runner.last_result.state == "success", window.runner.last_result
        facts["run_result"] = window.runner.last_result.state
        facts["completed_events"] = window.runner.last_result.completed_events
        facts["summary_sha256"] = hashlib.sha256((output / "run_summary.txt").read_bytes()).hexdigest()
        window.page_stack.setCurrentWidget(window.output_page)
        QTest.qWait(400)
        assert window.grab().save(str(work / "results.png"))
        # A separate output identity and long macro make cancellation observable.
        macro = work / "long.mac"
        macro.write_text("/run/initialize\n/run/beamOn 10000000\n", encoding="utf-8")
        window.project.macroPath = str(macro)
        window.project.outputDir = str(work / "cancel-output")
        window.page_stack.setCurrentWidget(window.run_page)
        window._start_current_project()
        assert window.runner._process.waitForStarted(5000)
        QTest.qWait(300)
        window.stop_run()
        QTest.qWait(3100)
        if window.runner.is_running():
            window.runner.kill()  # the Run page exposes Kill when graceful stop does not exit
        wait(lambda: not window.runner.is_running())
        assert window.runner.last_result.state in {"stopped", "killed"}
        facts["cancel_result"] = window.runner.last_result.state
        assert window.grab().save(str(work / "cancelled.png"))
        window.project.outputDir = str(work / "close-output")
        window._start_current_project()
        assert window.runner._process.waitForStarted(5000)
        QTest.qWait(200)
        assert window.grab().save(str(work / "before-close.png"))
        window.close()
        assert not window.isVisible()
        assert all(p.state() == QProcess.NotRunning for p in window.findChildren(QProcess))
        facts["close_result"] = window.runner.last_result.state
        facts["owned_processes_stopped"] = True
        facts["dialogs"] = messages
    (work / "report.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(work / "report.json")
    print("PASS visible Windows Q1 lifecycle")


if __name__ == "__main__":
    main()
