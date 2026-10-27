from __future__ import annotations
import json
import os
import sys
import tempfile
import time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.run_progress import PREFIX, ProgressParser
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.runner import G4USimRunner
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.widgets.run_page import RunPage


def message(run=0, phase="begin", completed=0, **values):
    data = dict(schema="g4usim_progress_v1", run_id=run, phase=phase,
                planned_events=10, completed_events=completed, elapsed_s=float(completed),
                rate_eps=1.0 if completed else None, eta_s=10.0-completed if completed else None)
    data.update(values)
    return PREFIX + json.dumps(data) + "\n"


def main():
    parser = ProgressParser()
    wire = "noise\n" + message() + message(phase="running", completed=5)
    seen = []
    for character in wire:
        seen.extend(parser.feed(character))
    assert [d["completed_events"] for d in seen] == [0, 5]
    assert not parser.feed(message(phase="running", completed=4))
    assert not parser.feed(message(phase="running", completed=6, elapsed_s=float("nan")))
    assert not parser.feed(message(phase="running", completed=6, schema="future"))
    assert not parser.feed(message(phase="running", completed=True))
    assert not parser.feed(message(phase="running", completed=11))
    assert not parser.feed(PREFIX + "{" + "x" * 100000)
    assert len(parser._buffer) <= parser.MAX_LINE
    assert parser.feed("\n" + message(phase="end", completed=10))
    assert not parser.feed(message(phase="running", completed=10))
    assert parser.feed(message(run=1))
    assert not parser.feed(message(run=0))
    assert parser.feed(message(run=1, phase="aborted", completed=1).rstrip(), final=True)
    parser = ProgressParser()
    assert not parser.feed(PREFIX + "[" * 2000 + "0" + "]" * 2000 + "\n")
    assert parser.feed(message(planned_events=None, completed_events=None, elapsed_s=None))
    parser = ProgressParser()
    assert parser.feed(message(planned_events=0, completed_events=0))
    parser = ProgressParser()
    wire = "noise without newline" + message()
    inline = []
    for character in wire:
        inline.extend(parser.feed(character))
    assert len(inline) == 1 and inline[0]["phase"] == "begin"
    assert not parser.feed("noise" + message(phase="running", completed=1).rstrip() + " trailing noise\n")
    app = QApplication.instance() or QApplication([])
    page = RunPage()
    page.set_progress_state("starting")
    assert page.progress_bar.maximum() == 0
    page.set_progress(json.loads(message(phase="running", completed=5)[len(PREFIX):]))
    assert page.progress_bar.value() == 500
    assert page.progress_bar.text() == "50%"
    set_application_language(app, "zh_CN")
    page.refresh_language()
    assert "运行" in page.progress_label.text()
    page.set_progress(json.loads(message(phase="running", completed=10)[len(PREFIX):]))
    assert page.progress_bar.value() == 1000 and "收尾中" in page.progress_label.text()
    page.set_progress(json.loads(message(phase="running", completed=5)[len(PREFIX):]))
    page.set_progress_state("stopped")
    page.set_progress(json.loads(message(phase="end", completed=10)[len(PREFIX):]))
    assert page.progress_bar.value() == 500 and "冻结" in page.progress_label.text()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = root / "dummy.ini"
        config.write_text("unused")
        project = G4USimProject(executable=sys.executable, runInputMode="external",
            workspaceRoot=str(root), configPath=str(config), outputDir=str(root / "output"))
        runner = G4USimRunner()
        runner.progressReceived.connect(page.set_progress)
        runner.progressStateChanged.connect(page.set_progress_state)
        received = []
        runner.progressReceived.connect(received.append)
        stderr_seen = []
        runner.stderrReceived.connect(stderr_seen.append)
        done = []
        runner.finished.connect(done.append)
        def execute(code):
            done.clear()
            runner.start(project, [sys.executable, "-u", "-c", code])
            deadline = time.monotonic() + 8
            while not done and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.005)
            assert done, "process timed out"
        wire = message() + message(phase="running", completed=5) + message(phase="end", completed=10).rstrip()
        execute("import sys; sys.stdout.write(" + repr(wire) + "); sys.stdout.flush()")
        assert len(received) == 3 and received[-1]["phase"] == "end"
        assert runner.last_result.state != "success"  # Full progress cannot replace a fresh summary.
        assert "冻结" in page.progress_label.text()
        assert (root / "output/logs/stdout.log").read_text() == wire
        stderr_seen.clear()
        # Separate byte writes plus sleeps force UTF-8 codepoints across readyRead chunks.
        execute("import os,time; b='中文'.encode(); "
                "[(os.write(2, bytes([v])),time.sleep(.02)) for v in b]; os.write(2,b'\\xe4')")
        assert "".join(stderr_seen) == "中文\ufffd"
        assert (root / "output/logs/stderr.log").read_text(encoding="utf-8") == "中文\ufffd"
        execute("print('legacy backend')")
        assert page._progress_data is None and page.progress_bar.maximum() != 0
        execute("import sys; print(" + repr(message(phase="running", completed=2).rstrip()) + "); sys.exit(3)")
        assert runner.last_result.state != "success" and page.progress_bar.value() == 200
        # Cancellation freezes immediately; later queued data must not advance it.
        done.clear()
        runner.start(project, [sys.executable, "-u", "-c", "import time; print(" + repr(message(phase="running", completed=3).rstrip()) + "); time.sleep(20)"])
        deadline = time.monotonic() + 5
        while page._progress_data is None and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.005)
        assert page.progress_bar.value() == 300
        runner.kill()
        while not done and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.005)
        assert done and runner.last_result.state == "killed"
        assert page.progress_bar.value() == 300
        done.clear()
        runner.start(project, [sys.executable, "-u", "-c", "import time; print(" + repr(message(phase="running", completed=4).rstrip()) + "); time.sleep(20)"])
        deadline = time.monotonic() + 5
        while page._progress_data is None and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.005)
        runner.terminate()
        assert page._progress_state == "stopped" and page.progress_bar.value() == 400
        # Windows console children may ignore terminate; the user can escalate to Kill.
        runner.kill()
        while not done and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.005)
        assert done and runner.last_result.state in {"stopped", "killed"}
        assert page.progress_bar.value() == 400
        received.clear()
        wire = message() + message(phase="end", completed=10) + message(run=1) + message(run=1, phase="aborted", completed=2)
        execute("import sys; sys.stdout.write(" + repr(wire) + ")")
        assert [(d["run_id"], d["phase"]) for d in received] == [(0,"begin"),(0,"end"),(1,"begin"),(1,"aborted")]
        assert page.progress_bar.value() == 200
        errors = []
        runner.errorOccurred.connect(errors.append)
        runner.start(project, [str(root / "missing.exe")])
        deadline = time.monotonic() + 5
        while not errors and time.monotonic() < deadline:
            app.processEvents(); time.sleep(.005)
        assert errors and page._progress_state == "failed"
        assert runner._stdout_file is None and runner._stderr_file is None
        runner.deleteLater()
        app.processEvents()
    page._timer.stop()
    page.close()
    page.deleteLater()
    app.processEvents()
    print("PASS: bounded parser, Qt state/language, QProcess tail, legacy, failure and kill")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
