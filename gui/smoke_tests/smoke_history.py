from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.history.run_history_scanner import scan_runs_root
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
        (package / "output" / "run_summary.txt").write_text("threads = 1\n", encoding="utf-8")
    (package / "project_snapshot.json").write_text(json.dumps({"schema": "G4UniversalSimProject", "version": 1}), encoding="utf-8")
    return package


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        success = _make_package(root, "20260621_010101_success", {"state": "finished", "exitCode": 0}, True)
        _make_package(root, "20260621_010102_failed", {"state": "finished", "exitCode": 1}, False)
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

        copy = Path(duplicate_package(str(success), str(root)))
        assert (copy / "config").exists()
        assert (copy / "macros").exists()
        assert not list((copy / "output").glob("*.csv"))

    print("smoke_history: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
