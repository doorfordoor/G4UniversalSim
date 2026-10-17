from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.history.run_history_scanner import scan_runs_root
from g4usim_gui.core.run_result import summary_fingerprint
from g4usim_gui.history.run_package_actions import duplicate_package


def _make_package(root: Path, name: str, status: dict | None = None, summary: bool = False) -> Path:
    package = root / name
    (package / "config").mkdir(parents=True)
    (package / "macros").mkdir()
    (package / "logs").mkdir()
    (package / "output").mkdir()
    (package / "config" / "main.ini").write_text("[run]\n", encoding="utf-8")
    (package / "macros" / "run.mac").write_text("/run/initialize\n", encoding="utf-8")
    if status:
        (package / "logs" / "run_status.json").write_text(json.dumps(status), encoding="utf-8")
    if summary:
        summary_path = package / "output" / "run_summary.txt"
        summary_path.write_text(
            "status = completed\nprogram_exit_code = 0\nsummary_write_status = completed\n"
            "macro_execution_status = completed\nrun_count = 1\nplanned_event_count = 3\n"
            "actual_completed_event_count = 3\nsimulation_executed = true\n"
            "[Runs]\nrun_0_id = 0\nrun_0_planned_events = 3\nrun_0_completed_events = 3\n",
            encoding="utf-8",
        )
        if status:
            status.update({"resultVersion": 1, "summaryFresh": True,
                           "summaryFingerprint": list(summary_fingerprint(summary_path))})
            (package / "logs" / "run_status.json").write_text(json.dumps(status), encoding="utf-8")
    (package / "project_snapshot.json").write_text(json.dumps({"schema": "G4UniversalSimProject", "version": 1}), encoding="utf-8")
    return package


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        success = _make_package(root, "20260621_010101_success", {"state": "success", "exitCode": 0}, True)
        _make_package(root, "20260621_010102_failed", {"state": "finished", "exitCode": 1}, False)
        old = _make_package(root, "20260621_010104_old", {"state": "finished", "exitCode": 0}, True)
        (old / "logs/run_status.json").write_text(
            json.dumps({"state": "finished", "exitCode": 0}), encoding="utf-8"
        )
        incomplete = root / "20260621_010103_incomplete"
        (incomplete / "config").mkdir(parents=True)
        (incomplete / "macros").mkdir()
        (incomplete / "config" / "main.ini").write_text("[run]\n", encoding="utf-8")
        (incomplete / "macros" / "run.mac").write_text("/run/initialize\n", encoding="utf-8")

        entries = scan_runs_root(str(root))
        statuses = {entry.run_name: entry.status for entry in entries}
        assert statuses["success"] == "success"
        assert statuses["failed"] == "failed"
        assert statuses["incomplete"] == "incomplete"
        assert statuses["old"] == "incomplete"

        copy = Path(duplicate_package(str(success), str(root)))
        assert (copy / "config").exists()
        assert (copy / "macros").exists()
        assert not list((copy / "output").glob("*.csv"))

    print("smoke_history: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
