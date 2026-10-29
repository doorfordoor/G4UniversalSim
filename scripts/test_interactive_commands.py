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

        # Native non-csh sessions bypass the audited random/run callbacks.
        # Reject before initialization or even the first supplied macro command.
        native_ini = temp / "native-ui.ini"
        native_ini.write_text("[run]\ninteractive=true\nthreads=1\n", encoding="utf-8")
        native_macro = temp / "native-ui.mac"
        sentinel = "R32_NATIVE_UI_MACRO_EXECUTED"
        native_macro.write_text(f"/control/echo {sentinel}\n/run/beamOn 1\n", encoding="utf-8")
        native_cases = (
            ("native_cli", ["--ui"]),
            ("native_ini", ["--config", str(native_ini)]),
            ("native_macro", ["--ui", "--macro", str(native_macro)]),
            ("native_dry", ["--ui", "--macro", str(native_macro), "--dry-run"]),
        )
        environment = os.environ.copy()
        environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
        for name, extra in native_cases:
            output_dir = temp / name
            completed = subprocess.run(
                [str(executable), "--output", str(output_dir), *extra],
                cwd=ROOT, input="exit\n", capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=60,
                env=environment, check=False,
            )
            log = completed.stdout + completed.stderr
            result = facts(output_dir)
            assert result["run_count"] == "0", result
            assert sentinel not in log, log[-4000:]
            assert not list(output_dir.glob("event_edep*.csv")), result
            if name == "native_dry":
                assert completed.returncode == 0, log[-4000:]
                assert result["status"] == "dry_run", result
                assert result["macro_execution_status"] == "skipped_dry_run", result
            else:
                assert completed.returncode != 0, log[-4000:]
                assert "requires --ui-session csh" in log, log[-4000:]
                assert result["status"] == "failed", result
                assert result["program_exit_code"] != "0", result

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

        # setMainConfig cannot reload a configured process, even while Geant4
        # remains PreInit. Its JustWarning must fail csh and stop later input.
        replacement = temp / "replacement.ini"
        replacement.write_text("[source]\nparticle=proton\nenergy=9 MeV\n", encoding="utf-8")
        code, log, baseline = session("app_config_baseline", "/AIHL/app/printSummary",
                                      config=True, threads=1)
        assert code == 0 and baseline["status"] == "interactive_no_run", log[-4000:]
        preserved_keys = ["main_config", "source_particle", "source_energy"]
        preserved_keys.extend(key for key in baseline if
                              key.startswith("effective_source_particle") or
                              key.startswith("effective_source_energy"))
        assert any("origin" in key for key in preserved_keys), baseline
        for threads in (1, 2):
            for initialized in (False, True):
                name = f"app_config_reject_t{threads}_init{int(initialized)}"
                commands = ("/run/initialize\n" if initialized else "")
                commands += (f"/AIHL/app/setMainConfig {replacement.as_posix()}\n"
                             "/control/echo APP_CONFIG_REJECT_CONTINUED\n"
                             "/run/initialize\n/run/beamOn 1")
                code, log, result = session(name, commands, config=True, threads=threads)
                assert code != 0 and result["status"] == "failed", log[-4000:]
                assert result["program_exit_code"] != "0", result
                assert result["interactive_command_failure_kind"] == "app", result
                assert "/AIHL/app/setMainConfig" in result["interactive_command_failure_message"], result
                assert "start a new process" in result["interactive_command_failure_message"], result
                assert "APP_CONFIG_REJECT_CONTINUED" not in log, log[-4000:]
                assert result["run_count"] == "0", result
                assert result["macro_execution_status"] == "not_run", result
                for key in preserved_keys:
                    assert result[key] == baseline[key], (key, result[key], baseline[key])
                assert not list((temp / name).glob("event_edep*.csv")), result

        # Before /run/initialize geometry edits remain usable; afterwards
        # Geant4 refuses them and the audited terminal skips subsequent input.
        code, log, result = session(
            "geometry_before_init", "/AIHL/geometry/setTemplate hierarchical\n/AIHL/geometry/print",
            config=True,
        )
        assert code == 0 and result["status"] == "interactive_no_run", log[-4000:]
        assert result["effective_geometry_template"] == "hierarchical", result

        code, log, result = session(
            "geometry_after_init", "/run/initialize\n/AIHL/geometry/setTemplate hierarchical\n"
            "/control/echo GEOMETRY_MUTATION_CONTINUED\n/run/beamOn 2",
            config=True, threads=1,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert "GEOMETRY_MUTATION_CONTINUED" not in log, log[-4000:]
        assert result["run_count"] == "0", result
        assert result["interactive_command_failure_kind"] == "geant4_illegal_application_state", result
        assert result["effective_geometry_template"] != "hierarchical", result

        code, log, result = session(
            "app_geometry_after_init", "/run/initialize\n/AIHL/app/setCheckOverlaps true\n"
            "/control/echo APP_GEOMETRY_CONTINUED", config=True, threads=1,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert "APP_GEOMETRY_CONTINUED" not in log, log[-4000:]
        assert result["interactive_command_failure_kind"] == "geant4_illegal_application_state", result
        # The interactive shell must reject a thread-count mutation after
        # initialization and stop input before any subsequent beamOn.
        code, log, result = session(
            "threads_before_init", "/AIHL/app/setNumThreads 2\n/run/initialize\n/run/beamOn 2",
            config=True,
        )
        assert code == 0 and result["status"] == "completed", log[-4000:]
        assert result["actual_threads"] == "2", result
        assert result["effective_threads_origin_kind"] == "runtime_unattributed", result

        code, log, result = session(
            "threads_after_init", "/run/initialize\n/AIHL/app/setNumThreads 3\n"
            "/control/echo THREAD_MUTATION_CONTINUED\n/run/beamOn 2", config=True,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert result["interactive_command_failure_kind"] == "geant4_illegal_application_state", result
        assert "THREAD_MUTATION_CONTINUED" not in log, log[-4000:]
        assert result["run_count"] == "0", result
        assert result["effective_threads_origin_kind"] == "main_ini", result

        # The output suffix preference used to accept false while workers
        # silently kept _tN. csh must stop after the Messenger reports failure.
        code, log, result = session(
            "suffix_disabled", "/AIHL/output/setThreadSuffix false\n"
            "/control/echo SUFFIX_CSH_CONTINUED\n/run/initialize\n/run/beamOn 2",
            config=True, threads=2,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert "disabling worker _tN suffix is unsupported" in log, log[-4000:]
        assert "SUFFIX_CSH_CONTINUED" not in log, log[-4000:]
        assert result["interactive_command_failure_kind"] == "output", result
        assert result["run_count"] == "0", result

        # Scoring configuration must reach workers before initialization.
        code, log, result = session(
            "scoring_before_init", "/AIHL/scoring/eventEdep false\n"
            "/run/initialize\n/run/beamOn 2", config=True, threads=2,
        )
        assert code == 0 and result["status"] == "completed", log[-4000:]
        assert result["run_0_completed_events"] == "2", result
        assert not list((temp / "scoring_before_init").glob("event_edep*.csv"))

        code, log, result = session(
            "scoring_after_init", "/run/initialize\n/AIHL/scoring/eventEdep false\n"
            "/control/echo SCORING_CSH_CONTINUED\n/run/beamOn 2",
            config=True, threads=2,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert result["interactive_command_failure_kind"] == "geant4_illegal_application_state", result
        assert "SCORING_CSH_CONTINUED" not in log, log[-4000:]
        assert result["run_count"] == "0", result

        code, log, result = session(
            "scoring_read_only_after_init", "/run/initialize\n/AIHL/scoring/print\n"
            "/run/beamOn 2", config=True, threads=2,
        )
        assert code == 0 and result["status"] == "completed", log[-4000:]
        assert result["run_0_completed_events"] == "2", result

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

        code, log, result = session(
            "unknown_command", "/definitely/not/a/geant4/command\n/control/echo POST_ERROR_SENTINEL"
        )
        assert code != 0 and "command </definitely/not/a/geant4/command> not found" in log, log[-4000:]
        assert "POST_ERROR_SENTINEL" not in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "geant4_command_not_found", result
        assert "/definitely/not/a/geant4/command" in result["interactive_command_failure_message"], result
        assert "Geant4 UI status=100" in result["interactive_command_failure_message"], result

        code, log, result = session("invalid_parameter", "/run/beamOn wrong\n/control/echo POST_ERROR_SENTINEL")
        assert code != 0 and "integer expected" in log, log[-4000:]
        assert "POST_ERROR_SENTINEL" not in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["macro_execution_status"] == "not_run", result
        assert result["interactive_command_failure_kind"] == "geant4_invalid_parameter", result
        assert "Parameter is wrong type" in result["interactive_command_failure_message"], result
        assert "Geant4 UI status=400" in result["interactive_command_failure_message"], result

        # This native Geant4 failure was not covered by text-only audit:
        # the command's candidate rejection is carried by numeric status 500.
        code, log, result = session(
            "invalid_candidate", "/gps/pos/type InvalidCandidate\n/run/initialize\n/run/beamOn 2", config=True
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert result["run_count"] == "0", result
        assert result["interactive_command_failure_kind"] == "geant4_command_status", result
        assert "Geant4 UI status=500 for command: /gps/pos/type InvalidCandidate" in (
            result["interactive_command_failure_message"]
        ), result

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
        assert "Geant4 UI status=200 for command: /run/abort" in result["interactive_command_failure_message"], result

        code, log, result = session(
            "physics_stops_before_state", "/AIHL/physics/setReferenceList QGSP_BIC\n/run/abort",
            config=True,
        )
        assert code != 0 and result["status"] == "failed", log[-4000:]
        assert result["interactive_command_failure_kind"] == "physics", result
        assert "Interactive physics mutation is unsupported" in result["interactive_command_failure_message"], result
        assert "illegal application state -- command refused" not in log, log[-4000:]

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

        code, log, result = session(
            "material_failure", "/AIHL/material/addNist missing_required_nist=G4_Si\n/control/echo POST_ERROR_SENTINEL"
        )
        assert code != 0 and "Interactive command failure" in log, log[-4000:]
        assert "POST_ERROR_SENTINEL" not in log, log[-4000:]
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

        # A rejected interactive biasing mutation used to be a JustWarning: the
        # command was ignored, the session continued and the process exited 0
        # although nothing was biased. It must now fail the session.
        code, log, result = session(
            "biasing_interactive_reject",
            "/AIHL/biasing/enable true\n/control/echo BIASING_CONTINUED\n/run/initialize\n/run/beamOn 1",
            config=True, threads=1,
        )
        assert code != 0 and "Interactive command failure" in log, log[-4000:]
        assert "BIASING_CONTINUED" not in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["interactive_command_failure_kind"] == "biasing", result
        assert "Interactive XS biasing" in result["interactive_command_failure_message"], result
        assert result["run_count"] == "0", result

        # Materials mutated after /run/initialize never reach a built volume:
        # the command must be refused by the lifecycle gate instead of applying
        # an effectless mutation and reporting success.
        code, log, result = session(
            "material_after_initialize",
            "/run/initialize\n/AIHL/material/addNist nist=G4_WATER name=late_water\n/control/echo MATERIAL_CONTINUED",
            config=True, threads=1,
        )
        assert code != 0 and "Interactive command failure" in log, log[-4000:]
        assert "MATERIAL_CONTINUED" not in log, log[-4000:]
        assert result["status"] == "failed" and result["program_exit_code"] != "0", result
        assert result["interactive_command_failure_kind"] == "geant4_illegal_application_state", result
        assert result["run_count"] == "0", result

        invalid = subprocess.run(
            [str(executable), "--ui-session", "csh"], cwd=ROOT,
            capture_output=True, text=True, timeout=30, check=False,
        )
        assert invalid.returncode != 0 and "--ui-session requires --ui" in invalid.stderr, invalid.stderr

    print("interactive command failures: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
