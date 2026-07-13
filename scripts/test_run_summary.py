"""M0-2 black-box tests for final run summaries."""

from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run(executable: Path, args: list[str], expected: int = 0) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    if result.returncode != expected:
        raise AssertionError(
            f"Unexpected exit code for {' '.join(args)}: "
            f"expected {expected}, got {result.returncode}\n{output}"
        )
    return output


def read_summary(directory: Path) -> tuple[dict[str, str], list[str]]:
    summary = directory / "run_summary.txt"
    if not summary.is_file():
        raise AssertionError(f"run_summary.txt was not created: {summary}")
    values: dict[str, str] = {}
    generated: list[str] = []
    section = ""
    for line in summary.read_text(encoding="utf-8").splitlines():
        if line.startswith("[") and line.endswith("]"):
            section = line
            continue
        if section in {"[Values]", "[Runs]"} and " = " in line:
            key, value = line.split(" = ", 1)
            values[key] = value
        elif section == "[GeneratedFiles]" and line.startswith("- "):
            generated.append(line[2:])
    return values, generated


def normalize(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-m02-") as temporary:
        temp = Path(temporary)
        dry_output = temp / "dry-output"
        single_output = temp / "single-output"
        multi_output = temp / "multi-output"
        failed_output = temp / "failed-output"
        no_run_output = temp / "no-run-output"
        changed_output = temp / "changed-output"
        locked_output = temp / "locked-output"
        write_failure_output = temp / "write-failure-output"
        dry_macro = temp / "dry.mac"
        single_macro = temp / "single.mac"
        multi_macro = temp / "multi.mac"
        failed_macro = temp / "failed.mac"
        preflight_macro = temp / "preflight-failed.mac"
        random_seed_macro = temp / "random-seed.mac"
        random_nonseed_macro = temp / "random-nonseed.mac"
        no_run_macro = temp / "no-run.mac"
        changed_macro = temp / "changed.mac"

        dry_macro.write_text(
            "/control/echo SHOULD_NOT_EXECUTE\n/run/beamOn 2\n", encoding="utf-8"
        )
        single_macro.write_text(
            "/run/initialize\n/run/beamOn 3\n", encoding="utf-8"
        )
        multi_macro.write_text(
            "/run/initialize\n/run/beamOn 2\n/run/beamOn 3\n", encoding="utf-8"
        )
        failed_macro.write_text(
            "/run/initialize\n/run/beamOn 2\n/random/showEngineStatus\n/does/not/exist\n", encoding="utf-8"
        )
        preflight_macro.write_text(
            "/AIHL/app/setSeed 88\n/control/echo SHOULD_NOT_RUN\n", encoding="utf-8"
        )
        random_seed_macro.write_text(
            "/random/setSeeds 123 456\n/run/initialize\n/run/beamOn 1\n", encoding="utf-8"
        )
        random_nonseed_macro.write_text(
            "/random/setSavingFlag true\n/run/initialize\n/run/beamOn 1\n", encoding="utf-8"
        )
        no_run_macro.write_text("/control/echo NO_BEAMON\n", encoding="utf-8")
        changed_macro.write_text(
            f"/AIHL/output/setDir {changed_output.as_posix()}\n"
            "/run/initialize\n/run/beamOn 2\n",
            encoding="utf-8",
        )

        # dry-run produces a summary but never creates simulation output.
        dry_text = run(
            executable,
            ["--macro", str(dry_macro), "--output", str(dry_output), "--dry-run"],
        )
        if "SHOULD_NOT_EXECUTE" in dry_text:
            raise AssertionError("dry-run executed the macro")
        dry_values, dry_files = read_summary(dry_output)
        assert dry_values["status"] == "dry_run"
        assert dry_values["actual_completed_event_count"] == "0"
        assert dry_values["run_count"] == "0"
        assert dry_values["actual_threads"] == "not_executed"
        assert dry_values["macro_execution_status"] == "skipped_dry_run"
        assert any(Path(file).name == "run_summary.txt" for file in dry_files)

        # A single real run reports completed events and generated files.
        run(executable, ["--config", "config/main.ini", "--macro", str(single_macro), "--output", str(single_output), "--seed", "77"])
        single_values, single_files = read_summary(single_output)
        assert single_values["status"] == "completed"
        assert single_values["run_count"] == "1"
        assert single_values["planned_event_count"] == "3"
        assert single_values["actual_completed_event_count"] == "3"
        assert single_values["initial_seed"] == "77"
        assert single_values["macro_seed_modified"] == "false"
        assert single_values["program_exit_code"] == "0"
        assert any(Path(file).name == "event_edep_t0.csv" for file in single_files)
        with (single_output / "event_edep_t0.csv").open(newline="", encoding="utf-8") as stream:
            assert sum(1 for _ in csv.reader(stream)) - 1 == 3
        run(executable, ["--config", "config/main.ini", "--macro", str(single_macro), "--output", str(single_output), "--seed", "77"])
        _, repeated_files = read_summary(single_output)
        assert any(Path(file).name == "event_edep_t0.csv" for file in repeated_files)

        # These command names are present in the installed Geant4 examples.
        run(executable, ["--config", "config/main.ini", "--macro", str(random_seed_macro), "--output", str(temp / "random-seed-output")])
        random_seed_values, _ = read_summary(temp / "random-seed-output")
        assert random_seed_values["macro_execution_status"] == "completed"
        assert random_seed_values["macro_seed_modified"] == "true"
        run(executable, ["--config", "config/main.ini", "--macro", str(random_nonseed_macro), "--output", str(temp / "random-nonseed-output")])
        random_nonseed_values, _ = read_summary(temp / "random-nonseed-output")
        assert random_nonseed_values["macro_seed_modified"] == "false"

        # Multiple beamOn calls retain every run and aggregate all events.
        run(executable, ["--config", "config/main.ini", "--macro", str(multi_macro), "--output", str(multi_output)])
        multi_values, _ = read_summary(multi_output)
        assert multi_values["run_count"] == "2"
        assert multi_values["planned_event_count"] == "5"
        assert multi_values["actual_completed_event_count"] == "5"
        assert multi_values["run_0_completed_events"] == "2"
        assert multi_values["run_1_completed_events"] == "3"

        # A later command failure preserves the completed run and failure location.
        failure_text = run(executable, ["--config", "config/main.ini", "--macro", str(failed_macro), "--output", str(failed_output)], expected=1)
        failed_values, _ = read_summary(failed_output)
        assert failed_values["status"] == "failed"
        assert failed_values["macro_execution_status"] == "failed"
        assert failed_values["actual_completed_event_count"] == "2"
        assert failed_values["macro_failure_line"] == "3"
        assert failed_values["macro_failure_command"] == "/random/showEngineStatus"
        assert failed_values["macro_failure_code"] != "0"
        assert failed_values["macro_seed_modified"] == "false"
        if "summary failure" in failure_text.lower():
            raise AssertionError("failed macro could not write its summary")

        preflight_output = temp / "preflight-output"
        preflight_text = run(
            executable,
            ["--config", "config/main.ini", "--macro", str(preflight_macro), "--output", str(preflight_output), "--seed", "77"],
            expected=1,
        )
        preflight_values, _ = read_summary(preflight_output)
        assert preflight_values["macro_execution_status"] == "preflight_failed"
        assert preflight_values["macro_failure_phase"] == "preflight"
        assert preflight_values["macro_failure_line"] == "1"
        assert preflight_values["macro_failure_command"] == "/AIHL/app/setSeed 88"
        assert preflight_values["macro_failure_code"] == "0"
        assert preflight_values["macro_failure_code_available"] == "false"
        if "SHOULD_NOT_RUN" in preflight_text:
            raise AssertionError("preflight-failed macro executed")

        # A macro without beamOn completes with zero actual events.
        run(executable, ["--macro", str(no_run_macro), "--output", str(no_run_output)])
        no_run_values, _ = read_summary(no_run_output)
        assert no_run_values["status"] == "completed"
        assert no_run_values["run_count"] == "0"
        assert no_run_values["actual_completed_event_count"] == "0"

        # A legal macro output switch changes the final summary location.
        run(executable, ["--config", "config/main.ini", "--macro", str(changed_macro)])
        changed_values, _ = read_summary(changed_output)
        assert normalize(changed_values["actual_output_dir"]) == normalize(str(changed_output))
        if (locked_output / "run_summary.txt").exists():
            raise AssertionError("summary remained in the pre-macro output directory")

        # Explicit CLI output remains locked and the preflight rejects the conflict.
        run(
            executable,
            ["--config", "config/main.ini", "--macro", str(changed_macro), "--output", str(locked_output)],
            expected=1,
        )

        # Summary write failures are reported instead of being swallowed.
        write_failure_output.mkdir(parents=True, exist_ok=True)
        (write_failure_output / "run_summary.txt").mkdir()
        write_failure_text = run(
            executable,
            ["--macro", str(no_run_macro), "--output", str(write_failure_output)],
            expected=1,
        )
        if "summary failure" not in write_failure_text.lower():
            raise AssertionError(f"summary write failure was not reported:\n{write_failure_text}")

    print("M0-2 run summary regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
