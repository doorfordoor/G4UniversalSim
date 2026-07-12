"""Black-box regression tests for M0-1 configuration precedence."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run(
    executable: Path,
    args: list[str],
    expected: int = 0,
    cwd: Path = ROOT,
) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=cwd,
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


def read_summary(output_dir: Path) -> dict[str, str]:
    summary = output_dir / "run_summary.txt"
    if not summary.is_file():
        raise AssertionError(f"run_summary.txt was not created: {summary}")
    values: dict[str, str] = {}
    in_values = False
    for line in summary.read_text(encoding="utf-8").splitlines():
        if line.strip() == "[Values]":
            in_values = True
            continue
        if in_values and " = " in line:
            key, value = line.split(" = ", 1)
            values[key] = value
    return values


def require(text: str, expected: str) -> None:
    if expected not in text:
        raise AssertionError(f"Expected marker not found: {expected}\n{text}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-m01-") as temporary:
        temp = Path(temporary)
        config_output = temp / "config-output"
        cli_output = temp / "cli-output"
        macro_output = temp / "macro-output"
        direct_macro_output = temp / "direct-macro-output"
        invalid_output = temp / "invalid-output"
        interactive_output = temp / "interactive-output"
        no_task_output = temp / "no-task-output"
        duplicate_first_output = temp / "duplicate-first-output"
        duplicate_second_output = temp / "duplicate-second-output"
        space_output = temp / "path with spaces" / "output dir"
        nested_space_macro = temp / "path with spaces" / "nested macro.mac"
        nested_space_parent = temp / "path with spaces" / "parent macro.mac"
        relative_root = temp / "relative macros"
        relative_parent = relative_root / "level1" / "parent.mac"
        relative_child = relative_root / "level1" / "level2" / "child.mac"
        relative_leaf = relative_root / "level1" / "leaf.mac"
        cwd_child = temp / "child.mac"
        hash_child = relative_root / "hash#child.mac"
        direct_cycle = temp / "direct-cycle.mac"
        indirect_cycle_a = temp / "indirect-a.mac"
        indirect_cycle_b = temp / "indirect-b.mac"
        failing_macro = temp / "failing-command.mac"
        real_output = temp / "real-output"
        macro_threads_output = temp / "macro-threads-output"
        macro_seed_output_a = temp / "macro-seed-output-a"
        macro_seed_output_b = temp / "macro-seed-output-b"
        config_macro = temp / "config.mac"
        runtime_macro = temp / "runtime.mac"
        cli_only_macro = temp / "cli-only.mac"
        cli_macro_path = temp / "cli-macro-path.mac"
        conflict_output_macro = temp / "conflict-output.mac"
        conflict_threads_macro = temp / "conflict-threads.mac"
        conflict_seed_macro = temp / "conflict-seed.mac"
        conflict_check_macro = temp / "conflict-check.mac"
        alias_macro = temp / "alias.mac"
        loop_macro = temp / "loop.mac"
        macro_threads = temp / "macro-threads.mac"
        macro_seed = temp / "macro-seed.mac"
        space_macro = temp / "path with spaces" / "macro file.mac"
        duplicate_first_macro = temp / "duplicate-first.mac"
        duplicate_second_macro = temp / "duplicate-second.mac"
        config_file = temp / "main.ini"
        interactive_config = temp / "interactive.ini"
        no_task_config = temp / "no-task.ini"

        config_macro.write_text(
            "/control/echo CONFIG_MACRO_MARKER\n", encoding="utf-8"
        )
        runtime_macro.write_text(
            "\n".join(
                [
                    f"/AIHL/app/setOutputDir {macro_output.as_posix()}",
                    f"/AIHL/output/setDir {direct_macro_output.as_posix()}",
                    "/AIHL/app/setNumThreads 3",
                    "/AIHL/app/setSeed 303",
                    "/AIHL/app/setCheckOverlaps true",
                    "/AIHL/geometry/checkOverlaps true",
                    "/AIHL/app/printSummary",
                    "/AIHL/output/print",
                    "/AIHL/geometry/print",
                    "/control/echo CLI_MACRO_MARKER",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        cli_only_macro.write_text(
            "/AIHL/app/printSummary\n/AIHL/output/print\n/control/echo CLI_ONLY_MARKER\n",
            encoding="utf-8",
        )
        cli_macro_path.write_text(
            "/control/echo CLI_MACRO_PATH_MARKER\n", encoding="utf-8"
        )
        conflict_threads_macro.write_text(
            "/control/echo SHOULD_NOT_RUN\n"
            "/AIHL/app/setNumThreads 3\n"
            "/run/initialize\n"
            "/run/beamOn 1\n",
            encoding="utf-8",
        )
        conflict_output_macro.write_text(
            "/control/echo SHOULD_NOT_RUN\n"
            "/AIHL/output/setDir should-not-run\n"
            "/run/initialize\n"
            "/run/beamOn 1\n",
            encoding="utf-8",
        )
        conflict_seed_macro.write_text(
            "/control/echo SHOULD_NOT_RUN\n"
            "/random/setSeeds 11 22\n"
            "/run/initialize\n"
            "/run/beamOn 1\n",
            encoding="utf-8",
        )
        conflict_check_macro.write_text(
            "/control/echo SHOULD_NOT_RUN\n"
            "/AIHL/geometry/checkOverlaps false\n"
            "/run/initialize\n"
            "/run/beamOn 1\n",
            encoding="utf-8",
        )
        alias_macro.write_text(
            "/control/alias seedValue 123\n/control/echo SHOULD_NOT_RUN\n",
            encoding="utf-8",
        )
        loop_macro.write_text(
            "/control/loop macros/run_hit_smoke.mac i 0 0 1\n",
            encoding="utf-8",
        )
        macro_threads.write_text(
            "/AIHL/app/setNumThreads 2\n"
            "/control/execute macros/run_hit_smoke.mac\n",
            encoding="utf-8",
        )
        macro_seed.write_text(
            "/AIHL/app/setSeed 444\n"
            "/control/execute macros/run_hit_smoke.mac\n",
            encoding="utf-8",
        )
        space_macro.parent.mkdir(parents=True, exist_ok=True)
        space_macro.write_text(
            "/control/echo SPACE_PATH_MARKER\n", encoding="utf-8"
        )
        nested_space_macro.write_text(
            "/control/echo NESTED_SPACE_PATH_MARKER\n", encoding="utf-8"
        )
        nested_space_parent.write_text(
            f"/control/execute {nested_space_macro.as_posix()}\n", encoding="utf-8"
        )
        relative_parent.parent.mkdir(parents=True, exist_ok=True)
        relative_child.parent.mkdir(parents=True, exist_ok=True)
        relative_parent.write_text(
            "/control/execute level2/child.mac # relative child\n"
            "/control/execute level2/child.mac # execute again\n",
            encoding="utf-8",
        )
        relative_child.write_text(
            "/control/execute ../leaf.mac # parent-relative leaf\n", encoding="utf-8"
        )
        relative_leaf.write_text(
            "/control/echo RELATIVE_PARENT_MARKER\n", encoding="utf-8"
        )
        cwd_child.write_text(
            "/control/echo WRONG_CWD_CHILD_MARKER\n", encoding="utf-8"
        )
        hash_child.parent.mkdir(parents=True, exist_ok=True)
        hash_child.write_text(
            "/control/echo HASH_IN_QUOTED_PATH_MARKER\n", encoding="utf-8"
        )
        (relative_root / "hash-parent.mac").write_text(
            '/control/execute "hash#child.mac" # quoted path comment\n',
            encoding="utf-8",
        )
        direct_cycle.write_text(
            "/control/execute direct-cycle.mac\n", encoding="utf-8"
        )
        indirect_cycle_a.write_text(
            "/control/execute indirect-b.mac\n", encoding="utf-8"
        )
        indirect_cycle_b.write_text(
            "/control/execute indirect-a.mac\n", encoding="utf-8"
        )
        failing_macro.write_text(
            "/control/echo BEFORE_FAILURE_MARKER\n"
            "/does/not/exist\n"
            "/control/echo AFTER_FAILURE_MARKER\n",
            encoding="utf-8",
        )
        duplicate_first_macro.write_text(
            "/control/echo DUPLICATE_FIRST_MARKER\n", encoding="utf-8"
        )
        duplicate_second_macro.write_text(
            "/control/echo DUPLICATE_SECOND_MARKER\n", encoding="utf-8"
        )
        config_file.write_text(
            "\n".join(
                [
                    "[run]",
                    "name = config_run",
                    "threads = 2",
                    "seed = 111",
                    "interactive = false",
                    "verbose = 0",
                    "check_overlaps = false",
                    "dry_run = false",
                    f"macro = {config_macro.as_posix()}",
                    "",
                    "[output]",
                    f"dir = {config_output.as_posix()}",
                    "",
                    "[materials]",
                    "file = config/materials/material.ini",
                    "",
                    "[geometry]",
                    "template = simple_box",
                    "config = config/geometry/simple_box.ini",
                    "check_overlaps = false",
                    "default_world_material = G4_AIR",
                    "",
                    "[physics]",
                    "reference = FTFP_BERT_EMZ",
                    "default_cut = 1 mm",
                    "biasing = false",
                    "",
                    "[source]",
                    "preset = proton_beam",
                    "",
                    "[scoring]",
                    "enabled = false",
                    "",
                    "[biasing]",
                    "enabled = false",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        config_text = config_file.read_text(encoding="utf-8")
        interactive_config.write_text(
            config_text
            .replace(f"dir = {config_output.as_posix()}", f"dir = {interactive_output.as_posix()}")
            .replace("interactive = false", "interactive = true")
            .replace("dry_run = false", "dry_run = true"),
            encoding="utf-8",
        )
        no_task_config.write_text(
            "\n".join(
                line for line in config_text.splitlines()
                if not line.startswith("macro = ")
            )
            + "\n",
            encoding="utf-8",
        )

        # A CLI dry-run overrides the config and must not execute its macro.
        dry_run_text = run(executable, ["--config", str(config_file), "--dry-run"])
        if "CONFIG_MACRO_MARKER" in dry_run_text:
            raise AssertionError("dry-run executed the config macro")
        config_values = read_summary(config_output)
        assert config_values["output_dir"] == config_output.as_posix()
        assert config_values["num_threads"] == "2"
        assert config_values["seed"] == "111"
        assert config_values["check_overlaps"] == "false"
        assert config_values["run_name"] == "config_run"
        assert config_values["dry_run"] == "true"

        # A macro specified only by the main config must execute.
        config_macro_text = run(executable, ["--config", str(config_file)])
        require(config_macro_text, "CONFIG_MACRO_MARKER")

        # interactive=true and dry_run=true supplied only by the main config must pass
        # the startup gate; dry-run prevents a UI session from being started.
        interactive_text = run(executable, ["--config", str(interactive_config)])
        if "CONFIG_MACRO_MARKER" in interactive_text:
            raise AssertionError("config dry_run=true executed its macro")
        interactive_values = read_summary(interactive_output)
        assert interactive_values["interactive"] == "true"
        assert interactive_values["dry_run"] == "true"

        # Only a fully configured no-task run should print usage after configuration.
        no_task_text = run(executable, ["--config", str(no_task_config)])
        require(no_task_text, "Usage:")

        # CLI-only: no main config is loaded.
        run(
            executable,
            [
                "--macro",
                str(cli_only_macro),
                "--output",
                cli_output.as_posix(),
                "--threads",
                "4",
                "--seed",
                "202",
                "--check-overlaps",
                "true",
                "--run-name",
                "cli_only",
            ],
        )
        cli_values = read_summary(cli_output)
        assert cli_values["output_dir"] == cli_output.as_posix()
        assert cli_values["num_threads"] == "4"
        assert cli_values["seed"] == "202"
        assert cli_values["check_overlaps"] == "true"
        assert cli_values["run_name"] == "cli_only"

        # Macro runtime values override the config when no corresponding CLI value exists.
        macro_output_text = run(
            executable,
            ["--config", str(config_file), "--macro", str(runtime_macro)],
        )
        require(macro_output_text, "CLI_MACRO_MARKER")
        macro_values = read_summary(config_output)
        # M0-2 will make run_summary reflect post-macro values; stdout is authoritative here.
        require(macro_output_text, f"output_dir        : {direct_macro_output.as_posix()}")
        require(macro_output_text, "num_threads       : 3")
        require(macro_output_text, "seed              : 303")
        require(macro_output_text, "check_overlaps    : true")
        require(macro_output_text, f"outputDir={direct_macro_output.as_posix()}")
        require(macro_output_text, "checkOverlaps=true")
        assert macro_values["output_dir"] == config_output.as_posix()

        # Explicit CLI macro path wins over [run]/macro in the main config.
        cli_macro_path_text = run(
            executable,
            ["--config", str(config_file), "--macro", str(cli_macro_path)],
        )
        require(cli_macro_path_text, "CLI_MACRO_PATH_MARKER")
        if "CONFIG_MACRO_MARKER" in cli_macro_path_text:
            raise AssertionError("Config macro executed despite explicit --macro")

        # Explicit CLI values remain final after a non-conflicting macro executes.
        cli_after_macro_text = run(
            executable,
            [
                "--config",
                str(config_file),
                "--macro",
                str(cli_only_macro),
                "--output",
                cli_output.as_posix(),
                "--threads",
                "4",
                "--seed",
                "202",
                "--check-overlaps",
                "true",
                "--run-name",
                "cli_wins",
            ],
        )
        require(cli_after_macro_text, "CLI_ONLY_MARKER")
        require(cli_after_macro_text, "output_dir        : " + cli_output.as_posix())
        require(cli_after_macro_text, "num_threads       : 4")
        require(cli_after_macro_text, "seed              : 202")
        require(cli_after_macro_text, "run_name          : cli_wins")
        require(cli_after_macro_text, "check_overlaps    : true")
        # Known project/native conflict commands fail before any macro command runs.
        conflict_threads_text = run(
            executable,
            [
                "--config",
                str(config_file),
                "--macro",
                str(conflict_threads_macro),
                "--threads",
                "4",
            ],
            expected=1,
        )
        require(conflict_threads_text, "conflict-threads.mac:2")
        require(conflict_threads_text, "thread count")
        if "SHOULD_NOT_RUN" in conflict_threads_text:
            raise AssertionError("thread conflict macro executed before preflight failed")

        conflict_output_text = run(
            executable,
            [
                "--config",
                str(config_file),
                "--macro",
                str(conflict_output_macro),
                "--output",
                cli_output.as_posix(),
            ],
            expected=1,
        )
        require(conflict_output_text, "conflict-output.mac:2")
        require(conflict_output_text, "output directory")
        if "SHOULD_NOT_RUN" in conflict_output_text:
            raise AssertionError("output conflict macro executed before preflight failed")

        conflict_seed_text = run(
            executable,
            [
                "--config",
                str(config_file),
                "--macro",
                str(conflict_seed_macro),
                "--seed",
                "202",
            ],
            expected=1,
        )
        require(conflict_seed_text, "conflict-seed.mac:2")
        require(conflict_seed_text, "random seed/state")
        if "SHOULD_NOT_RUN" in conflict_seed_text:
            raise AssertionError("seed conflict macro executed before preflight failed")

        conflict_check_text = run(
            executable,
            [
                "--config",
                str(config_file),
                "--macro",
                str(conflict_check_macro),
                "--check-overlaps",
                "true",
            ],
            expected=1,
        )
        require(conflict_check_text, "conflict-check.mac:2")
        require(conflict_check_text, "geometry overlap checking")
        if "SHOULD_NOT_RUN" in conflict_check_text:
            raise AssertionError("overlap conflict macro executed before preflight failed")

        alias_text = run(executable, ["--macro", str(alias_macro)], expected=1)
        require(alias_text, "alias.mac:1")
        require(alias_text, "dynamic macro command")
        loop_text = run(executable, ["--macro", str(loop_macro)], expected=1)
        require(loop_text, "loop.mac:1")
        require(loop_text, "dynamic macro command")

        # Empty values, missing paths, and parser errors must fail clearly.
        run(executable, ["--threads", "0"], expected=1)
        run(executable, ["--seed", "-1"], expected=1)
        run(executable, ["--output"], expected=1)
        run(executable, ["--output", ""], expected=1)
        run(executable, ["--run-name", ""], expected=1)
        run(executable, ["--macro", ""], expected=1)
        run(executable, ["--config", ""], expected=1)
        run(executable, ["--config", str(temp / "missing.ini"), "--dry-run"], expected=1)
        run(
            executable,
            [
                "--macro",
                str(temp / "missing.mac"),
                "--output",
                invalid_output.as_posix(),
            ],
            expected=1,
        )

        # Repeated CLI options use the last value, including string and numeric options.
        duplicate_text = run(
            executable,
            [
                "--macro",
                str(duplicate_first_macro),
                "--macro",
                str(duplicate_second_macro),
                "--output",
                duplicate_first_output.as_posix(),
                "--output",
                duplicate_second_output.as_posix(),
                "--run-name",
                "first_name",
                "--run-name",
                "second_name",
                "--threads",
                "1",
                "--threads",
                "2",
                "--seed",
                "11",
                "--seed",
                "22",
            ],
        )
        require(duplicate_text, "DUPLICATE_SECOND_MARKER")
        if "DUPLICATE_FIRST_MARKER" in duplicate_text:
            raise AssertionError("first repeated macro option was executed")
        duplicate_values = read_summary(duplicate_second_output)
        assert duplicate_values["macro_file"] == str(duplicate_second_macro)
        assert duplicate_values["run_name"] == "second_name"
        assert duplicate_values["num_threads"] == "2"
        assert duplicate_values["seed"] == "22"

        # ExecuteMacroFile must support Windows paths containing spaces.
        space_text = run(
            executable,
            ["--macro", space_macro.as_posix(), "--output", space_output.as_posix()],
        )
        require(space_text, "SPACE_PATH_MARKER")
        assert (space_output / "run_summary.txt").is_file()
        nested_space_text = run(
            executable,
            ["--macro", nested_space_parent.as_posix(), "--output", space_output.as_posix()],
        )
        require(nested_space_text, "NESTED_SPACE_PATH_MARKER")

        # Nested relative paths are resolved from the including macro directory,
        # including ../ paths, comments, and a same-name file in the CWD.
        relative_text = run(
            executable,
            ["--macro", relative_parent.as_posix(), "--output", space_output.as_posix()],
            cwd=temp,
        )
        require(relative_text, "RELATIVE_PARENT_MARKER")
        if relative_text.count("RELATIVE_PARENT_MARKER") != 2:
            raise AssertionError("repeated nested macro execution was deduplicated")
        if "WRONG_CWD_CHILD_MARKER" in relative_text:
            raise AssertionError("nested macro resolved from the process CWD")
        hash_text = run(
            executable,
            ["--macro", str(relative_root / "hash-parent.mac"), "--output", space_output.as_posix()],
            cwd=temp,
        )
        require(hash_text, "HASH_IN_QUOTED_PATH_MARKER")

        direct_cycle_text = run(executable, ["--macro", str(direct_cycle)], expected=1)
        require(direct_cycle_text, "recursive /control/execute cycle detected")
        indirect_cycle_text = run(executable, ["--macro", str(indirect_cycle_a)], expected=1)
        require(indirect_cycle_text, "recursive /control/execute cycle detected")

        # A failed command must stop execution and produce a non-zero process exit.
        failure_text = run(executable, ["--macro", str(failing_macro)], expected=1)
        require(failure_text, "BEFORE_FAILURE_MARKER")
        if "AFTER_FAILURE_MARKER" in failure_text:
            raise AssertionError("macro continued after a failed command")
        require(failure_text, "failing-command.mac:2")
        require(failure_text, "/does/not/exist")

        # Real beamOn regression: CLI threads/seed survive a non-conflicting macro.
        run(
            executable,
            [
                "--macro",
                "macros/run_hit_smoke.mac",
                "--output",
                real_output.as_posix(),
                "--threads",
                "1",
                "--seed",
                "777",
            ],
        )
        assert (real_output / "event_edep_t0.csv").is_file()
        assert read_summary(real_output)["num_threads"] == "1"
        assert read_summary(real_output)["seed"] == "777"

        # A non-CLI macro thread setting is applied before /run/initialize.
        run(
            executable,
            ["--macro", str(macro_threads), "--output", macro_threads_output.as_posix(), "--seed", "888"],
        )
        assert (macro_threads_output / "event_edep_t1.csv").is_file()

        # A macro seed is applied before beamOn and is reproducible in MT-disabled-by-test mode.
        for output in (macro_seed_output_a, macro_seed_output_b):
            run(
                executable,
                ["--macro", str(macro_seed), "--output", output.as_posix(), "--threads", "1"],
            )
        assert sha256(macro_seed_output_a / "hits_t0.csv") == sha256(macro_seed_output_b / "hits_t0.csv")

    print("M0-1/M0-1b configuration precedence regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
