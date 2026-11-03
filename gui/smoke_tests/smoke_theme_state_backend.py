"""A real backend run must survive appearance changes while it is running."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "scripts")]

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core import theme  # noqa: E402
from g4usim_gui.core.project import G4USimProject  # noqa: E402
from g4usim_gui.core.runner import G4USimRunner  # noqa: E402
from g4usim_gui.widgets.run_page import RunPage  # noqa: E402
from test_live_progress import fixture  # noqa: E402

APPEARANCES = (
    ("light", "paper", "midnight"),
    ("dark", "paper", "midnight"),
    ("light", "contrast_light", "circuit"),
    ("dark", "sandstone", "aurora"),
    ("light", "B", "C"),
)


def main() -> int:
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setStyle("Fusion")
    executable = Path(os.environ["G4USIM_EXE"]) if os.environ.get("G4USIM_EXE") else (
        ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe")
    assert executable.exists(), f"backend executable not found: {executable}"

    events = 40000
    with tempfile.TemporaryDirectory(prefix="g4usim-theme-running-") as directory:
        work = Path(directory)
        ini, macro = fixture(work, (events,), threads=1)
        project = G4USimProject()
        project.runInputMode = "external"
        project.executable = str(executable)
        project.configPath = str(ini)
        project.macroPath = str(macro)
        project.outputDir = str(work / "output")
        project.workspaceRoot = str(ROOT)
        project.threads = 1

        runner = G4USimRunner()
        page = RunPage()
        runner.progressReceived.connect(page.set_progress)
        runner.progressStateChanged.connect(page.set_progress_state)
        messages = []
        exits = []
        loop = QEventLoop()
        runner.progressReceived.connect(lambda message: messages.append(message))
        runner.finished.connect(lambda code: (exits.append(code), loop.quit()))

        switched = []
        failures = []

        def rotate() -> None:
            index = len(switched) % len(APPEARANCES)
            mode, light, dark = APPEARANCES[index]
            before = len(messages)
            theme.apply_theme(app, mode, light_skin=light, dark_skin=dark)
            after = theme.current_skin()
            expected = dark if theme.resolve_theme(app, mode) == "dark" else light
            if before != len(messages) or after.id != expected:
                failures.append((index, before, len(messages), after.id, expected))
            switched.append((mode, light, dark))
            assert runner.is_running() or exits, "the run stopped while switching appearance"

        timer = QTimer()
        timer.setInterval(100)
        timer.timeout.connect(rotate)
        guard = QTimer()
        guard.setSingleShot(True)
        guard.timeout.connect(loop.quit)
        runner.start(project)
        timer.start()
        guard.start(120000)
        loop.exec()
        timer.stop()
        guard.stop()

        assert not failures, failures
        assert exits, "the run did not finish"
        assert runner.last_result is not None
        assert runner.last_result.state == "success", runner.last_result
        assert len(switched) >= 3, switched
        assert len(messages) >= 2, messages
        phases = [message["phase"] for message in messages]
        assert "end" in phases, phases
        assert messages[-1]["completed_events"] == events, messages[-1]
        assert page._progress_state == "success", page._progress_state

    print(
        f"smoke_theme_state_backend: OK ({len(switched)} appearance changes, "
        f"{len(messages)} progress messages)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
