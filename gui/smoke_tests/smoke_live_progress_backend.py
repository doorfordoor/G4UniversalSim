"""Real Qt runner + Geant4 progress, repeated runs, failure and cancellation."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "scripts")]
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.widgets.run_page import RunPage
from test_live_progress import fixture


def main():
    app = QApplication.instance() or QApplication([])
    exe = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
    with tempfile.TemporaryDirectory(prefix="f6-qt-real-") as directory:
        work = Path(directory)
        for scenario in ("success", "failure", "kill"):
            events = (200, 137) if scenario != "kill" else (10000000,)
            ini, macro = fixture(work / scenario, events)
            project = G4USimProject()
            project.runInputMode = "external"
            project.executable = str(exe)
            project.configPath = str(ini)
            project.macroPath = str(macro)
            project.outputDir = str(work / scenario / "output")
            project.workspaceRoot = str(ROOT)
            project.threads = 2
            runner = G4USimRunner()
            page = RunPage()
            runner.progressReceived.connect(page.set_progress)
            runner.progressStateChanged.connect(page.set_progress_state)
            loop = QEventLoop()
            messages = []
            exits = []
            def receive(message):
                messages.append(message)
                if scenario == "kill" and message["phase"] == "running":
                    runner.kill()
            runner.progressReceived.connect(receive)
            runner.finished.connect(lambda code: (exits.append(code), loop.quit()))
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            previous = os.environ.pop("G4USIM_TEST_OUTPUT_FAULT", None)
            try:
                if scenario == "failure":
                    os.environ["G4USIM_TEST_OUTPUT_FAULT"] = "final_close_master"
                runner.start(project)
                timer.start(90000)
                loop.exec()
                timer.stop()
                assert exits, f"runner timeout ({scenario})"
                assert runner.last_result is not None
                if scenario == "success":
                    assert runner.last_result.state == "success", runner.last_result
                    assert [(x["run_id"], x["completed_events"]) for x in messages if x["phase"] == "end"] == [(0, 200), (1, 137)]
                    assert page.progress_bar.value() == 1000
                elif scenario == "failure":
                    assert runner.last_result.state == "failed", runner.last_result
                    assert any(x["phase"] == "end" for x in messages)
                    assert page._progress_state == "failed"
                else:
                    assert runner.last_result.state == "killed", runner.last_result
                    assert any(x["phase"] == "running" for x in messages)
                    assert not any(x["phase"] == "end" for x in messages)
                    assert page._progress_state == "killed"
                print(f"PASS real GUI {scenario}: {len(messages)} messages, result={runner.last_result.state}")
            finally:
                timer.stop()
                if runner.is_running():
                    runner.kill()
                    runner._process.waitForFinished(10000)
                os.environ.pop("G4USIM_TEST_OUTPUT_FAULT", None)
                if previous is not None:
                    os.environ["G4USIM_TEST_OUTPUT_FAULT"] = previous
                page.close()
                runner.deleteLater()
                page.deleteLater()
                app.processEvents()
    print("smoke_live_progress_backend: OK")


if __name__ == "__main__":
    main()
