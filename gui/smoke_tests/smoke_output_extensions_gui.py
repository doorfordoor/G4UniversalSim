"""Exercise the real M5 CLI via the asynchronous Results-page QProcess."""

from __future__ import annotations

import json
import math
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QProcess

from g4usim_gui.core.i18n import apply_language
import g4usim_gui.output.extension_runner as extension_module
from g4usim_gui.widgets.output_page import OutputPage
from smoke_dose_results import dose_row, write_csv
from smoke_fluence_results import row as fluence_row, write as write_fluence_csv


def wait_for_completion(app: QApplication, page: OutputPage, expected: int, completed: list) -> tuple:
    deadline = time.monotonic() + 15
    while len(completed) < expected and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert len(completed) == expected, "Results-page QProcess did not finish"
    assert not page._extension_runner.is_running()
    return completed[-1]


def wait_for_running(app: QApplication, page: OutputPage) -> None:
    deadline = time.monotonic() + 8
    while page._extension_runner._process.state() != QProcess.Running and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert page._extension_runner._process.state() == QProcess.Running


def main() -> None:
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="g4usim-gui-extension-") as folder:
        root = Path(folder)
        out = root / "output"
        out.mkdir()
        write_csv(out, "dose_volume_summary_t0.csv", [dose_row(0, 2, 3)])
        write_csv(out, "dose_volume_summary_t1.csv", [dose_row(0, 4, 5)])
        write_fluence_csv(out, "fluence_volume_summary_t0.csv", [fluence_row(0, 2, 2)])
        write_fluence_csv(out, "fluence_volume_summary_t1.csv", [fluence_row(0, 3, 3)])
        page = OutputPage()
        completed: list[tuple] = []
        page._extension_runner.finished.connect(lambda *args: completed.append(args))
        assert not page.export_dose_button.isEnabled()
        assert not page.run_output_extension("dose_json", str(root / "empty.json"))
        page.set_output_dir(str(out))
        assert page.export_dose_button.isEnabled()
        assert page.export_fluence_button.isEnabled()
        assert not page.cancel_extension_button.isEnabled()

        dose_json = out / "dose.json"
        assert page.run_output_extension("dose_json", str(dose_json))
        assert not page.export_dose_button.isEnabled()
        assert not page.run_output_extension("fluence_json", str(out / "concurrent.json"))
        assert wait_for_completion(app, page, 1, completed)[2] is True, completed
        dose = json.loads(dose_json.read_text(encoding="utf-8"))
        assert dose["extension_id"] == "dose_json"
        assert dose["data"]["physical_validation"] == "not_established"
        assert len(dose["data"]["volumes"]) == 1
        assert dose["data"]["volumes"][0]["thread_ids"] == [0, 1]
        assert any(Path(info.path) == dose_json for info in page._files)

        fluence_json = out / "fluence.json"
        assert page.run_output_extension("fluence_json", str(fluence_json))
        assert wait_for_completion(app, page, 2, completed)[2] is True, completed
        fluence = json.loads(fluence_json.read_text(encoding="utf-8"))
        assert fluence["extension_id"] == "fluence_json"
        assert len(fluence["data"]["volumes"]) == 1
        volume = fluence["data"]["volumes"][0]
        assert volume["thread_ids"] == [0, 1] and volume["volume_mm3"] == 100
        assert math.isclose(volume["raw_fluence_mm-2"], 0.05)
        log_text = page.extension_log.toPlainText()
        # CI may resolve the temporary directory to a different (8.3 or long) spelling
        # than the one used to request the export, so accept either spelling.
        assert str(fluence_json) in log_text or str(fluence_json.resolve()) in log_text, log_text
        assert page.export_dose_button.isEnabled()

        # No silent overwrite or deletion of an already published JSON file.
        previous = dose_json.read_bytes()
        assert not page.run_output_extension("dose_json", str(dose_json))
        assert dose_json.read_bytes() == previous and len(completed) == 2

        empty = root / "empty"
        empty.mkdir()
        page.set_output_dir(str(empty))
        target = empty / "missing_data.json"
        assert page.run_output_extension("fluence_json", str(target))
        assert wait_for_completion(app, page, 3, completed)[2] is False
        assert not target.exists()
        assert "No valid fluence" in page.extension_log.toPlainText()
        assert "Failed" in page.extension_status.text()

        # Early validation never starts a child or overwrites an existing output.
        assert not page.run_output_extension("unknown_plugin", str(empty / "invalid.json"))
        assert not page.run_output_extension("dose_json", str(root / "missing" / "invalid.json"))
        assert not page.run_output_extension("dose_json", str(empty / "wrong.txt"))
        page.set_output_dir(str(root / "no_such_output"))
        assert not page.run_output_extension("dose_json", str(root / "invalid.json"))
        page.set_output_dir(str(out))

        # Actual QProcess cancellation of a long-running child.
        sleepy = root / "slow_extension.py"
        sleepy.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        runner = page._extension_runner
        real_script = runner._cli_script
        runner._cli_script = lambda: sleepy
        cancelled = out / "cancelled.json"
        assert page.run_output_extension("dose_json", str(cancelled))
        wait_for_running(app, page)
        page.cancel_extension_button.click()
        result = wait_for_completion(app, page, 4, completed)
        assert result[2] is False and "cancelled" in result[3].lower()
        assert not cancelled.exists()

        # Process-start error must clear the busy state, with no reported success.
        runner._cli_script = real_script
        with patch.object(extension_module.install_layout, "script_python", lambda: str(root / "no_python.exe")):
            assert page.run_output_extension("dose_json", str(out / "not_started.json"))
            result = wait_for_completion(app, page, 5, completed)
        assert result[2] is False and "Cannot start" in result[3]
        assert page.export_dose_button.isEnabled()

        # A child exiting zero with malformed JSON cannot report success.
        invalid = root / "invalid_extension.py"
        invalid.write_text(
            "from pathlib import Path\nimport sys\n"
            "Path(sys.argv[sys.argv.index('--output') + 1]).write_text("
            "'{\"schema\":\"G4UniversalSimOutputExtensionResult\",\"version\":1,'"
            "'\"extension_id\":\"dose_json\",\"extension_version\":\"0.1.0\",'"
            "'\"data\":{\"warnings\":[],\"value\":NaN}}', encoding='utf-8')\n",
            encoding="utf-8",
        )
        runner._cli_script = lambda: invalid
        malformed = out / "malformed.json"
        assert page.run_output_extension("dose_json", str(malformed))
        result = wait_for_completion(app, page, 6, completed)
        assert result[2] is False and "Non-finite JSON" in result[3]
        runner._cli_script = real_script

        apply_language(page, "zh_CN")
        assert page.export_dose_button.text() == "导出 Dose JSON..."
        assert page.tool_tabs.tabText(0) == "JSON 导出（M5 原型）"
        assert "仅汇总已发现的 CSV" in page.extension_caution.text()

        # Closing Results while the child runs must terminate it before deletion.
        runner._cli_script = lambda: sleepy
        assert page.run_output_extension("dose_json", str(out / "closed.json"))
        wait_for_running(app, page)
        page.close()
        assert runner._process.state() == QProcess.NotRunning
        assert not (out / "closed.json").exists()
    print("smoke_output_extensions_gui: ok")


if __name__ == "__main__":
    main()
