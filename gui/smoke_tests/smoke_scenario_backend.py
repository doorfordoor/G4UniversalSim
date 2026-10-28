"""End-to-end regression for the shielding scenario page with the real backend (2B).

Twelve steps, all through the GUI page: defaults -> edit -> validate -> generate ->
run through QProcess -> read run_summary.txt -> analyse -> fill the table -> check the
evidence column and the backend log. 200 events and 2 threads keep it around a minute
on a laptop; nothing here replaces the physics benchmarks in scenarios/benchmarks.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "gui") not in sys.path:
    sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core import scenario_shielding as shielding  # noqa: E402
from g4usim_gui.core.install_layout import default_backend_executable  # noqa: E402
from g4usim_gui.widgets.scenario_page import ScenarioPage  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    executable = os.environ.get("G4USIM_EXE", "") or default_backend_executable()
    assert executable and Path(executable).is_file(), (
        "the backend executable was not found; build it or set G4USIM_BACKEND_EXECUTABLE")
    workdir = Path(tempfile.mkdtemp(prefix="g4usim-scenario-e2e-"))
    page = ScenarioPage()
    try:
        # 1-3: the default form is valid, and a 200-event transmission case is accepted.
        page.set_executable(executable)
        page.set_directory(workdir / "case")
        assert page.validate_form() == []
        page.set_values({"events": "200", "threads": "2", "energy": "100", "particle": "proton",
                         "mode": "transmission", "seed": "12345"})
        assert page.validate_form() == [], page._parse_problems

        # 4: generated files exist and carry the run parameters.
        generated = page.generate_scenario()
        assert generated is not None
        main_ini = (generated.directory / "main.ini").read_text(encoding="utf-8")
        assert "threads = 2" in main_ini and "seed = 12345" in main_ini, main_ini
        assert (generated.directory / "geometry.ini").is_file()

        # 5-6: the page starts the QProcess and stays busy until it exits.
        assert page.start_run() is True
        assert page.is_running
        assert not page.run_button.isEnabled()
        deadline = time.monotonic() + 900
        while page.is_running and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        assert not page.is_running, "the backend did not finish within 15 minutes"

        # 7-9: the outcome agrees with run_summary.txt and the analysis report.
        outcome = page.outcome
        assert outcome is not None, ("outcome is None; status=" + page.status_text() + "; problems=" + repr(page._parse_problems) + "; log=" + repr(page.log_text()[-2000:]))
        assert outcome.exit_code == 0, outcome.exit_code
        assert outcome.ok
        assert outcome.summary.get("status") == "completed", outcome.summary.get("status")
        assert outcome.summary.get("run_count") == "1"
        assert outcome.summary.get("run_0_completed_events") == "200", outcome.summary.get("run_0_completed_events")
        report = outcome.report
        assert report is not None
        assert report["tid"]["total"] > 0.0
        assert report["tid"]["per_primary"] > 0.0
        assert report["evidence"]["run_status"] == "completed"
        assert report["evidence"]["completed_events"] == 200

        # 10-11: the table shows every number with its evidence label.
        rows = page.result_rows()
        assert rows, "the result table is empty"
        tid_rows = [row for row in rows if row["group"] == "TID"]
        assert {row["label"] for row in tid_rows} >= {"Total", "Per primary"}
        assert all(row["evidence"] == "scorer_statistics.csv" for row in tid_rows)
        transmission = [row for row in rows if row["group"] == "Transmission"]
        assert transmission and transmission[0]["evidence"] == "phase_space"
        assert float(transmission[0]["value"]) > 0.9, transmission[0]

        # 12: the log and the evidence panel keep the run facts.
        log = page.log_text()
        assert "--config main.ini" in log
        assert "status" in " ".join(page.evidence_lines())
        evidence_text = "\n".join(page.evidence_lines())
        assert "Completed events: 200" in evidence_text, evidence_text
        assert "Statistics evidence: scorer_statistics.csv" in evidence_text, evidence_text
        assert "Scenario run finished: 200 events, completed." in page.status_text(), page.status_text()
        assert outcome.log_path.is_file() and outcome.log_path.stat().st_size > 0

        print("PASS: scenario page end to end (200 events, TID/transmission with evidence)")
        return 0
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
