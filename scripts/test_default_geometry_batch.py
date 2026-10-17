"""Real-backend regression for the headless hierarchical demonstration."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
MACRO = ROOT / "test" / "macros" / "run_hierarchical_batch.mac"
GEOMETRY = ROOT / "test" / "geometry" / "hierarchical_test.ini"
MAIN_CONFIG = ROOT / "test" / "main_hierarchical.ini"
FULL_MACRO = ROOT / "test" / "macros" / "test_hierarchical_full.mac"


def run(executable: Path, macro: Path, output: Path,
        config: Path | None = None) -> tuple[str, dict[str, str]]:
    command = [str(executable)]
    if config is not None:
        command.extend(["--config", str(config)])
    command.extend(["--macro", str(macro), "--output", str(output), "--threads", "1"])
    result = subprocess.run(
        command,
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=90, check=False,
    )
    log = result.stdout + "\n" + result.stderr
    if result.returncode:
        raise AssertionError(f"Backend exited {result.returncode}:\n{log[-6000:]}")
    summary_path = output / "run_summary.txt"
    if not summary_path.is_file():
        raise AssertionError("Backend did not produce run_summary.txt")
    facts = {}
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            facts[key] = value
    return log, facts


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")
    macro_text = MACRO.read_text(encoding="utf-8")
    if "/vis/open" in macro_text or "/run/beamOn 3" not in macro_text:
        raise AssertionError("Batch macro must avoid visualization and request three events")
    for name in ("run_hierarchical.mac", "run_biasing.mac"):
        batch_text = (ROOT / "macros" / name).read_text(encoding="utf-8")
        assert "/control/execute macros\\vis.mac" not in batch_text, name
    with tempfile.TemporaryDirectory(prefix="g4usim-m03d-") as directory:
        temp = Path(directory)
        log, facts = run(executable, MACRO, temp / "good")
        assert facts["status"] == "completed", facts
        assert facts["macro_execution_status"] == "completed", facts
        assert (facts["run_count"], facts["planned_event_count"], facts["actual_completed_event_count"]) == ("1", "3", "3"), facts
        assert re.search(r"Checking overlaps for volume cooling_pipe_PV.*?\.\.\. OK!", log, re.S), log[-6000:]
        for forbidden in ("GeomVol1002", "Overlap is detected", "protruding out", "Unknown visual color", "OGLSQt"):
            assert forbidden not in log, f"Unexpected {forbidden}:\n{log[-6000:]}"

        configured_log, configured = run(executable, MACRO, temp / "configured", MAIN_CONFIG)
        assert (configured["status"], configured["macro_execution_status"]) == ("completed", "completed"), configured
        assert (configured["run_count"], configured["planned_event_count"],
                configured["actual_completed_event_count"]) == ("1", "3", "3"), configured
        assert configured["biasing_matched_process_rule_count"] == "2", configured
        assert configured["biasing_process_match_status"] == "validated", configured
        assert configured["biasing_effect_observed"] == "unknown", configured
        assert "[biasing.xs]" not in configured_log and "sensor_1" not in configured_log, configured_log[-6000:]

        full_log, full = run(executable, FULL_MACRO, temp / "full", MAIN_CONFIG)
        assert (full["status"], full["macro_execution_status"]) == ("completed", "completed"), full
        assert (full["run_count"], full["planned_event_count"],
                full["actual_completed_event_count"]) == ("1", "100", "100"), full
        assert full["biasing_matched_process_rule_count"] == "2", full
        assert full["biasing_effect_observed"] == "unknown", full
        assert "Overlap is detected" not in full_log and "OGLSQt" not in full_log, full_log[-6000:]

        # Prove the overlap check is sensitive to the original out-of-bounds pipe.
        old_geometry = temp / "old_geometry.ini"
        updated = GEOMETRY.read_text(encoding="utf-8")
        original = updated.replace("position = 9 cm, 15 cm, 0 cm", "position = 15 cm, 15 cm, 0 cm")
        assert original != updated
        old_geometry.write_text(original, encoding="utf-8")
        old_macro = temp / "old_geometry.mac"
        old_macro.write_text(
            macro_text.replace("test/geometry/hierarchical_test.ini", old_geometry.as_posix()),
            encoding="utf-8",
        )
        old_log, _ = run(executable, old_macro, temp / "old")
        assert "cooling_pipe_PV" in old_log and ("GeomVol1002" in old_log or "Overlap is detected" in old_log), old_log[-6000:]

    print("M0-3D default geometry batch regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
