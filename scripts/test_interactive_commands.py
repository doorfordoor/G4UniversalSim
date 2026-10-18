"""Exercise Geant4's command-line UI and its post-session failure contract."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def facts(output_dir: Path) -> dict[str, str]:
    summary = output_dir / "run_summary.txt"
    assert summary.is_file(), summary
    result: dict[str, str] = {}
    for line in summary.read_text(encoding="utf-8").splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            result[key] = value
    return result


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-interactive-") as directory:
        temp = Path(directory)

        def session(name: str, commands: str, fault: str | None = None,
                    config: bool = False, threads: int | None = None) -> tuple[int, str, dict[str, str]]:
            output_dir = temp / name
            environment = os.environ.copy()
            if fault is None:
                environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
            else:
                environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
            args = [str(executable), "--ui", "--ui-session", "csh", "--output", str(output_dir)]
            if config:
                args.extend(["--config", str(ROOT / "config/main.ini")])
            if threads is not None:
                args.extend(["--threads", str(threads)])
            completed = subprocess.run(
                args,
                cwd=ROOT, input=commands + "\nexit\n", capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=60,
                env=environment, check=False,
            )
            return completed.returncode, completed.stdout + completed.stderr, facts(output_dir)

        code, log, result = session("clean", "/AIHL/material/list")
        assert code == 0, log[-4000:]
        assert result["status"] == "interactive_no_run", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "none", result

        code, log, result = session("unknown_command", "/definitely/not/a/geant4/command")
        assert code != 0 and "command </definitely/not/a/geant4/command> not found" in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "geant4_command_not_found", result
        assert "/definitely/not/a/geant4/command" in result["interactive_command_failure_message"], result

        code, log, result = session("invalid_parameter", "/run/beamOn wrong\n/AIHL/material/list")
        assert code != 0 and "integer expected" in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "geant4_invalid_parameter", result
        assert "Parameter is wrong type" in result["interactive_command_failure_message"], result

        code, log, result = session("real_run", "/run/initialize\n/run/beamOn 2", config=True, threads=1)
        assert code == 0, log[-4000:]
        assert result["status"] == "completed" and result["run_count"] == "1", result
        assert result["run_0_planned_events"] == "2" and result["run_0_completed_events"] == "2", result
        assert result["interactive_command_failure_kind"] == "none", result

        code, log, result = session("worker_write_failure", "/run/initialize\n/run/beamOn 5",
                                    "event_row_t0", config=True, threads=2)
        assert code != 0 and "Interactive output failure" in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["run_count"] == "1" and result["output_failure_stage"] == "event_edep_write", result
        assert result["macro_execution_status"] == "not_run", result

        code, log, result = session("material_failure", "/AIHL/material/addNist missing_required_nist=G4_Si")
        assert code != 0 and "Interactive command failure" in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "material", result
        assert "Missing required key" in result["interactive_command_failure_message"], result

        target = temp / "unused_target"
        code, log, result = session(
            "output_failure", f"/AIHL/output/setDir {target.as_posix()}", "messenger_set_dir"
        )
        assert code != 0 and "Interactive command failure" in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "output", result
        assert "Injected /AIHL/output/setDir handler failure" in result["interactive_command_failure_message"], result
        assert Path(result["actual_output_dir"]) == temp / "output_failure", result

        invalid = subprocess.run(
            [str(executable), "--ui-session", "csh"], cwd=ROOT,
            capture_output=True, text=True, timeout=30, check=False,
        )
        assert invalid.returncode != 0 and "--ui-session requires --ui" in invalid.stderr, invalid.stderr

    print("interactive command failures: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
