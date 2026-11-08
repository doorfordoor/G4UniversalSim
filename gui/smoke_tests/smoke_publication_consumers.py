"""Real Qt child processes with controlled publication/cleanup IO failures."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.output.merge_plan import MergeTask
from g4usim_gui.output.merge_runner import MergeRunner
from g4usim_gui.output.publication_diagnostics import PublicationDiagnostics
from g4usim_gui.widgets.output_page import OutputPage
from smoke_dose_results import dose_row, write_csv
from async_wait import wait_for_idle

REPO = Path(__file__).resolve().parents[2]


def wait(app, predicate):
    deadline = time.monotonic() + 30
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert predicate(), "Child process did not complete"


def wrapper(root, script, fault):
    path = root / f"{script}-{fault}.py"
    path.write_text(
        "import sys, runpy, os\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(REPO / 'scripts')!r})\n"
        "def deny(*args, **kwargs):\n    raise PermissionError('controlled IO denial')\n"
        + ("Path.unlink = deny\n" if fault == "cleanup" else "os.link = deny\n")
        + f"runpy.run_path({str(REPO / 'scripts' / (script + '.py'))!r}, run_name='__main__')\n",
        encoding="utf-8")
    return path


def main():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-publication-consumers-") as directory:
        root = Path(directory)
        target = root / "parser.json"
        record = dict(schema="g4usim_publication_v1", published=True, output=str(target),
                      residual_temporary=str(root / "残留.tmp"), warnings=["cleanup 残留.tmp"])
        line = "G4USIM_PUBLICATION_RESULT " + json.dumps(record, ensure_ascii=True) + "\n"
        for cut in range(len(line) + 1):
            parser = PublicationDiagnostics(target)
            parser.feed(line[:cut])
            parser.feed(line[cut:])
            assert parser.warnings == tuple(record["warnings"])
        for changes in ({"published": False}, {"output": str(root / "other.json")},
                        {"warnings": [None]}, {"schema": "unknown"}):
            parser = PublicationDiagnostics(target)
            parser.feed("G4USIM_PUBLICATION_RESULT " + json.dumps(record | changes) + "\n")
            assert not parser.warnings

        inputs = root / "input"
        inputs.mkdir()
        source = write_csv(inputs, "dose_volume_summary_t0.csv", [dose_row(0, 2, 3)])
        page = OutputPage()
        page.set_output_dir(str(inputs))
        wait_for_idle(page)
        completed = []
        page._extension_runner.finished.connect(lambda *args: completed.append(args))
        cleanup = wrapper(root, "run_output_extension", "cleanup")
        result = root / "dose.json"
        with patch.object(page._extension_runner, "_cli_script", return_value=cleanup):
            assert page.run_output_extension("dose_json", str(result))
            wait(app, lambda: len(completed) == 1)
        assert completed[-1][2], completed
        assert page._extension_runner.publication_warnings
        assert "Warnings (0): none" not in completed[-1][3]
        assert ui_text("Completed with cleanup warnings") in page.extension_status.text()
        published = result.read_bytes()
        assert json.loads(published)["extension_id"] == "dose_json"
        leftovers = list(root.glob(".g4usim-extension-*.tmp"))
        assert len(leftovers) == 1 and leftovers[0].read_bytes() == published
        assert str(leftovers[0]) in completed[-1][3]
        assert not page.run_output_extension("dose_json", str(result))
        assert result.read_bytes() == published
        failed = root / "failed.json"
        with patch.object(page._extension_runner, "_cli_script",
                          return_value=wrapper(root, "run_output_extension", "link")):
            assert page.run_output_extension("dose_json", str(failed))
            wait(app, lambda: len(completed) == 2)
        assert not completed[-1][2] and not failed.exists()
        assert not page._extension_runner.publication_warnings
        page._extension_runner.shutdown()
        wait_for_idle(page)
        page.close()

        merger = MergeRunner()
        finished, all_done, warnings = [], [], []
        merger.taskFinished.connect(lambda *args: finished.append(args))
        merger.allFinished.connect(lambda: all_done.append(True))
        merger.publicationWarning.connect(lambda *args: warnings.append(args))
        merge_cleanup = wrapper(root, "merge_outputs", "cleanup")

        def task(name, script):
            output = root / (name + ".csv")
            return MergeTask(name, "csv", str(inputs), "", str(output), "python_script",
                             sys.executable, ["-B", str(script), "--output", str(output), str(source)],
                             True, "", [str(source)], name)

        merger.run_tasks([task("one", merge_cleanup), task("two", merge_cleanup)], root / "logs")
        wait(app, lambda: len(all_done) == 1)
        assert finished == [("one", 0), ("two", 0)], finished
        assert [name for name, _ in warnings] == ["one", "two"]
        for name in ("one", "two"):
            output = root / (name + ".csv")
            assert output.read_bytes() == source.read_bytes()
            residual = list(root.glob(f".{name}.csv.*.tmp"))
            assert len(residual) == 1 and residual[0].read_bytes() == output.read_bytes()
            assert str(residual[0]) in dict(warnings)[name]
        finished.clear()
        warnings.clear()
        merger.run_tasks([task("bad", wrapper(root, "merge_outputs", "link")),
                          task("not_started", merge_cleanup)], root / "logs")
        wait(app, lambda: len(all_done) == 2)
        assert len(finished) == 1 and finished[0][0] == "bad" and finished[0][1] != 0
        assert not warnings and not (root / "bad.csv").exists()
        assert not (root / "not_started.csv").exists()
        finished.clear()
        merger.run_tasks([task("one", merge_cleanup), task("also_not_started", merge_cleanup)], root / "logs")
        wait(app, lambda: len(all_done) == 3)
        assert len(finished) == 1 and finished[0][1] != 0
        assert (root / "one.csv").read_bytes() == source.read_bytes()
        assert not (root / "also_not_started.csv").exists()
        assert not merger.is_running()
    print("smoke_publication_consumers: OK (real QProcess; controlled IO faults)")


if __name__ == "__main__":
    main()
