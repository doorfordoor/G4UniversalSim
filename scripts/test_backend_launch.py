"""Component contracts for backend launch planning; no Geant4 pass is fabricated."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
if (ROOT / "baseline.json").is_file():
    sys.path.append(str(Path(json.loads((ROOT / "baseline.json").read_bytes())["workspace"]) / "gui"))
from g4usim_gui.core import backend_launch as launch


def expect(code, call):
    caught = None
    try:
        call()
    except launch.BackendLaunchError as error:
        caught = error
    assert caught is not None, code
    assert caught.code == code, (code, caught.code)


def deep_directory(root):
    path = root
    while launch.utf16_units(str(path.resolve())) <= 262:
        path /= "中文😀-" + "x" * 22
    path.mkdir(parents=True)
    return path.resolve()


def exercise(root):
    root.mkdir(parents=True, exist_ok=True)
    program = str(Path(sys.executable).resolve())
    short = root / "short"
    short.mkdir()
    args = [program, "--config", "relative.ini", "--run-name", "\u3000同名\u00a0"]
    original = list(args)
    with patch.object(launch, "WINDOWS", False):
        plan = launch.prepare_backend_launch(args, short)
        assert plan.command == args
        assert plan.route == "direct"
        assert plan.logical_cwd == plan.launch_cwd == str(short.resolve())
    with patch.object(launch, "WINDOWS", True):
        direct = launch.prepare_backend_launch(args, short)
        assert direct.command == args and direct.route == "direct"
    assert args == original
    assert launch.utf16_units("中😀") == 3
    assert launch.utf16_units("x" * 258) == launch.MAX_LAUNCH_CWD_UNITS
    deep = deep_directory(root)
    assert launch.utf16_units(str(deep)) > launch.MAX_LAUNCH_CWD_UNITS
    with patch.object(launch, "WINDOWS", True):
        plan = launch.prepare_backend_launch(args, deep)
        assert plan.route == "restore_working_directory"
        assert plan.requires_working_directory
        assert plan.logical_cwd == str(deep)
        assert launch.utf16_units(plan.launch_cwd) <= launch.MAX_LAUNCH_CWD_UNITS
        assert Path(plan.launch_cwd) in deep.parents
        assert Path(plan.launch_cwd).is_dir()
        assert plan.arguments[:2] == ("--working-directory", str(deep))
        assert plan.arguments[2:] == tuple(args[1:])
        assert plan.program == program and Path(plan.program).is_absolute()
        assert launch.prepare_backend_launch(plan.command, deep) == plan
        assert args == original
        assert plan.to_dict()["working_directory"] == str(deep)
        assert plan.to_dict()["launch_working_directory"] == plan.launch_cwd
        expect("backend_launch.duplicate_working_directory", lambda: launch.prepare_backend_launch(
            [program, "--working-directory", str(deep), "--working-directory", str(deep)], deep))
        expect("backend_launch.conflicting_working_directory", lambda: launch.prepare_backend_launch(
            [program, "--working-directory", str(short)], deep))
        expect("backend_launch.relative_working_directory", lambda: launch.prepare_backend_launch(
            [program, "--working-directory", "relative"], deep))
        expect("backend_launch.missing_working_directory", lambda: launch.prepare_backend_launch(
            [program, "--working-directory"], deep))
        expect("backend_launch.invalid_working_directory_option", lambda: launch.prepare_backend_launch(
            [program, "--working-directory=" + str(deep)], deep))
    with patch.object(launch, "WINDOWS", True), patch.object(launch, "MAX_LAUNCH_CWD_UNITS", 0):
        expect("backend_launch.unsupported_cwd", lambda: launch.prepare_backend_launch(args, deep))
    with patch.object(launch, "WINDOWS", False):
        unchanged = launch.prepare_backend_launch(args, deep)
        assert unchanged.command == args and unchanged.launch_cwd == str(deep)
    # Values are consumed by the backend CLI, including option-shaped labels.
    # Test real cwd flags on either side so a value cannot hide a duplicate.
    with patch.object(launch, "WINDOWS", True):
        for cwd in (short.resolve(), deep):
            for label in ("--working-directory", "--working-directory=label", "\u3000--working-directory\u00a0"):
                labelled = [program, "--run-name", label, "--seed", "17"]
                labelled_plan = launch.prepare_backend_launch(labelled, cwd)
                prefix = ["--working-directory", str(cwd)] if cwd == deep else []
                assert labelled_plan.command == [program, *prefix, *labelled[1:]]
                assert labelled_plan.arguments[-4:] == tuple(labelled[1:])
                assert launch.prepare_backend_launch(labelled_plan.command, cwd) == labelled_plan
                for declared in (["--working-directory", str(cwd), *labelled[1:]],
                                 [*labelled[1:], "--working-directory", str(cwd)]):
                    explicit = launch.prepare_backend_launch([program, *declared], cwd)
                    assert explicit.arguments == tuple(declared)
                    assert launch.prepare_backend_launch(explicit.command, cwd) == explicit
                expect("backend_launch.duplicate_working_directory", lambda: launch.prepare_backend_launch(
                    [program, "--working-directory", str(cwd), *labelled[1:], "--working-directory", str(cwd)], cwd))
                expect("backend_launch.conflicting_working_directory", lambda: launch.prepare_backend_launch(
                    [*labelled, "--working-directory", str(root)], cwd))
                expect("backend_launch.invalid_working_directory_option", lambda: launch.prepare_backend_launch(
                    [*labelled, "--working-directory=actual"], cwd))
        # Other known value-bearing options obey the same consumption rule;
        # validity of their values is still checked by the backend, not here.
        for option in ("--dump-effective-config", "--config", "-c", "--macro", "-m", "--output", "-o",
                       "--ui-session", "--threads", "-t", "--seed", "--check-overlaps"):
            for value in ("--working-directory", "--working-directory=value"):
                command = [program, option, value]
                assert launch.prepare_backend_launch(command, short).command == command
    expect("backend_launch.cwd_unavailable", lambda: launch.prepare_backend_launch(args, root / "missing"))
    file = root / "not-directory"
    file.write_text("fixture", encoding="utf-8")
    expect("backend_launch.cwd_not_directory", lambda: launch.prepare_backend_launch(args, file))
    expect("backend_launch.program_not_file", lambda: launch.prepare_backend_launch([str(root)], short))
    expect("backend_launch.invalid_command", lambda: launch.prepare_backend_launch([], short))
    expect("backend_launch.invalid_command", lambda: launch.prepare_backend_launch([program, "bad\x00arg"], short))
    with patch.object(launch.shutil, "which", return_value=program):
        found = launch.prepare_backend_launch(["backend-fixture-not-in-cwd", "--capabilities"], short)
        assert found.program == program
    assert launch.unsupported_working_directory("Unknown command-line option: --working-directory\n")
    assert launch.unsupported_working_directory("unrecognized arguments: --working-directory")
    assert not launch.unsupported_working_directory("Cannot read config; --working-directory was accepted")
    assert not launch.unsupported_working_directory("Unknown source particle")
    return {"status": "passed", "kind": "component_launch_planning", "deep_utf16_units": launch.utf16_units(str(deep)),
            "simulation": "not_executed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default="")
    args = parser.parse_args()
    if args.evidence_dir:
        result = exercise(Path(args.evidence_dir).resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="backend-launch-") as directory:
            result = exercise(Path(directory))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
