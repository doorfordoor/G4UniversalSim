"""Exercise Geant4's command-line UI and its post-session failure contract."""

from __future__ import annotations

import os
import csv
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
                    config: bool = False, threads: int | None = None,
                    macro: Path | None = None) -> tuple[int, str, dict[str, str]]:
            output_dir = temp / name
            environment = os.environ.copy()
            if fault is None:
                environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
            else:
                environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
            args = [str(executable), "--ui", "--ui-session", "csh", "--output", str(output_dir)]
            if config:
                args.extend(["--config", str(ROOT / "config/main.ini")])
            if macro is not None:
                args.extend(["--macro", str(macro)])
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

        code, log, result = session("physics_read_only", "/AIHL/physics/print")
        assert code == 0 and result["status"] == "interactive_no_run", log[-4000:]

        # A physics list is already registered when the terminal starts.
        # Interactive manager changes must not pretend to rebuild that list.
        code, log, result = session(
            "physics_before_init", "/AIHL/physics/setReferenceList QGSP_BIC\n/AIHL/physics/print",
            config=True,
        )
        assert code != 0 and "Interactive physics mutation is unsupported" in log, log[-4000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["interactive_command_failure_kind"] == "physics", result

        # A batch macro may stop before initialization; its physics edits must
        # be registered before csh later runs /run/initialize.
        physics_macro = temp / "physics_before_ui.mac"
        physics_macro.write_text("/AIHL/physics/setReferenceList QGSP_BIC\n", encoding="utf-8")
        code, log, result = session(
            "physics_macro_before_ui", "/run/initialize\n/run/beamOn 2",
            config=True, threads=1, macro=physics_macro,
        )
        assert code == 0 and result["status"] == "completed", log[-4000:]
        assert "[PhysicsLifecycle] Rebound physics list from batch macro before interactive UI." in log, log[-4000:]
        assert result["effective_physics_reference"] == "QGSP_BIC", result
        assert result["macro_execution_status"] == "completed", result
        assert result["run_0_completed_events"] == "2", result

        # List commands only inspect physics; they remain legal after init.
        query_macro = temp / "physics_query_after_init.mac"
        query_macro.write_text(
            "/run/initialize\n/AIHL/physics/listAvailableReferences\n"
            "/AIHL/physics/listAvailableEMReferences\n/run/beamOn 2\n", encoding="utf-8",
        )
        code, log, result = session("physics_macro_queries", "", config=True,
                                    threads=1, macro=query_macro)
        assert code == 0 and result["status"] == "completed", log[-4000:]
        assert result["macro_execution_status"] == "completed", result
        assert result["run_0_completed_events"] == "2", result
        assert result["effective_physics_reference"] != "QGSP_BIC", result

        code, log, result = session(
            "physics_after_run", "/run/initialize\n/run/beamOn 2\n/AIHL/physics/setEM option3",
            config=True, threads=1,
        )
        assert code != 0 and "Interactive physics mutation is unsupported" in log, log[-4000:]
        assert result["status"] == "failed" and result["run_count"] == "1", result
        assert result["run_0_completed_events"] == "2", result
        assert result["interactive_command_failure_kind"] == "physics", result

        # csh bypasses the batch macro loop. A collision must be caught by the
        # Geant4 run-start callback before a worker writes its first event.
        first_target = temp / "collision_first"
        blocked = first_target / "event_edep_t1.csv"
        blocked.mkdir(parents=True)
        marker = blocked / "keep.txt"
        marker.write_text("untouched\n", encoding="utf-8")
        code, log, result = session(
            "collision_first", "/run/initialize\n/run/beamOn 2", config=True, threads=2
        )
        assert code != 0 and "run_begin_validate_targets" in log, log[-4000:]
        assert result["status"] == "failed" and result["run_count"] == "1", result
        assert result["actual_completed_event_count"] == "0", result
        assert result["output_failure_stage"] == "run_begin_validate_targets", result
        assert result["output_failure_run_id"] == "0", result
        assert marker.read_text(encoding="utf-8") == "untouched\n"
        assert not list(first_target.glob("event_edep_t0.csv"))

        # A collision on the second run must leave first-run data intact.
        second_target = temp / "collision_second"
        (second_target / "event_edep_t0_r1.csv").mkdir(parents=True)
        code, log, result = session(
            "collision_second", "/run/initialize\n/run/beamOn 2\n/run/beamOn 3",
            config=True, threads=1,
        )
        assert code != 0 and "run_begin_validate_targets" in log, log[-4000:]
        assert result["status"] == "failed" and result["output_failure_run_id"] == "1", result
        assert result["output_failure_stage"] == "run_begin_validate_targets", result
        assert result["actual_completed_event_count"] == "2", result
        assert result["run_0_completed_events"] == "2", result
        with (second_target / "event_edep_t0.csv").open(newline="", encoding="utf-8") as stream:
            assert len(list(csv.DictReader(stream))) == 2
        assert not (second_target / "hits_t0_r1.csv").exists()

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

        code, log, result = session("parameter_out_of_range", "/run/verbose -1\n/AIHL/material/list")
        assert code != 0 and "parameter out of range: level >=0 && level <=4" in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["interactive_command_failure_kind"] == "geant4_parameter_out_of_range", result
        assert "parameter out of range" in result["interactive_command_failure_message"], result

        code, log, result = session("negative_beamon", "/run/beamOn -1")
        assert code != 0 and "parameter out of range: numberOfEvent >= 0" in log, log[-4000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["interactive_command_failure_kind"] == "geant4_parameter_out_of_range", result

        # This Geant4 state-machine rejection previously returned exit code 0
        # and was incorrectly summarized as a clean interactive_no_run.
        code, log, result = session("illegal_state", "/run/abort\n/AIHL/material/list")
        assert code != 0 and "illegal application state -- command refused" in log, log[-4000:]
        assert result["status"] == "failed" and result["run_count"] == "0", result
        assert result["interactive_command_failure_kind"] == "geant4_illegal_application_state", result
        assert "command refused" in result["interactive_command_failure_message"], result

        code, log, result = session(
            "mixed_physics_and_state", "/AIHL/physics/setReferenceList QGSP_BIC\n/run/abort",
            config=True,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert result["interactive_command_failure_kind"] == "multiple", result
        assert "Interactive physics mutation is unsupported" in result["interactive_command_failure_message"], result
        assert "illegal application state -- command refused" in result["interactive_command_failure_message"], result
        assert "; ; " not in result["interactive_command_failure_message"], result

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
