"""Qt/subprocess launch components; an old interpreter never counts as a run."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
sys.path.insert(0, str(ROOT / "scripts"))
if (ROOT / "baseline.json").is_file():
    sys.path.append(str(Path(json.loads((ROOT / "baseline.json").read_bytes())["workspace"]) / "gui"))

from PySide6.QtCore import QCoreApplication, QProcess
from g4usim_gui.core import backend_launch as launch
from g4usim_gui.core.environment_discovery import _backend_command, _command
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.experiment_workflow import ExperimentWorkflow
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.runner import G4USimRunner
from test_backend_launch import deep_directory


def wait_for(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(.002)
    assert predicate(), "component deadline"


def project_at(directory):
    config = directory / "main.ini"
    config.write_text("[run]\nseed = 17\n", encoding="utf-8")
    return G4USimProject(runInputMode="external", executable=sys.executable,
        workspaceRoot=str(directory), configPath=str(config), outputDir=str(directory / "output"),
        runsRoot=str(directory / "runs"), threads=1, runName="\u3000用户 label\u00a0")


def exercise(root, executable=""):
    root.mkdir(parents=True, exist_ok=True)
    short = root / "short"
    short.mkdir()
    deep = deep_directory(root)
    runners, services = [], []
    try:
        runner = G4USimRunner()
        runners.append(runner)
        project = project_at(short)
        errors, completions = [], []
        runner.errorOccurred.connect(errors.append)
        runner.finished.connect(completions.append)
        bad_output = short / "should-not-create-logs"
        project.outputDir = str(bad_output)
        runner.start(project, [str(root)])
        assert errors and "backend_launch.program_not_file" in errors[-1]
        assert runner.last_result.state == "failed"
        assert not runner.is_running() and runner._stdout_file is runner._stderr_file is None
        assert not bad_output.exists()
        # The same runner is usable after the rejected preparation.
        project.outputDir = str(short / "output")
        code = "import os,json; print(json.dumps({'cwd':os.getcwd()}))"
        command = [sys.executable, "-c", code]
        runner.start(project, command)
        wait_for(lambda: bool(completions))
        assert completions[-1] == 0
        assert runner.last_launch.route == "direct"
        assert runner.last_launch.command == [str(Path(command[0]).resolve()), *command[1:]]
        assert runner.last_result.state == "incomplete", "No summary must remain unverified"
        assert runner._stdout_file is runner._stderr_file is None
        status = json.loads((short / "output/logs/run_status.json").read_bytes())
        assert status["workingDirectory"] == str(short)
        assert status["launchWorkingDirectory"] == str(short.resolve())
        assert status["requestedCommand"] == command
        assert status["command"] == runner.last_launch.command
        for number, label in enumerate(("--working-directory", "--working-directory=label", "\u3000--working-directory\u00a0")):
            project.outputDir = str(short / ("label-" + str(number)))
            echo = [sys.executable, "-c", "import sys,json; print(json.dumps(sys.argv[1:]))", "--run-name", label]
            previous = len(completions)
            runner.start(project, echo)
            wait_for(lambda: len(completions) > previous)
            assert completions[-1] == 0
            assert runner.last_launch.command == [str(Path(echo[0]).resolve()), *echo[1:]]
            assert json.loads((Path(project.outputDir) / "logs/stdout.log").read_text(encoding="utf-8")) == ["--run-name", label]
            assert runner.last_result.state == "incomplete"
        if executable:
            # Real backend protocol queries only; absence of a run summary
            # must remain incomplete rather than claim simulation success.
            for cwd in (short, deep):
                for number, label in enumerate(("--working-directory", "--working-directory=label")):
                    query = G4USimRunner()
                    runners.append(query)
                    query_project = project_at(cwd)
                    query_project.outputDir = str(cwd / ("backend-label-" + str(number)))
                    query_done = []
                    query.finished.connect(query_done.append)
                    command = [str(Path(executable).resolve()), "--capabilities", "--run-name", label]
                    query.start(query_project, command)
                    wait_for(lambda: bool(query_done))
                    assert query_done == [0]
                    assert query.last_launch.arguments[-2:] == ("--run-name", label)
                    assert query.last_launch.logical_cwd == str(cwd)
                    assert query.last_launch.requires_working_directory == (cwd == deep)
                    assert launch.prepare_backend_launch(query.last_launch.command, cwd) == query.last_launch
                    capability = json.loads((Path(query_project.outputDir) / "logs/stdout.log").read_text(encoding="utf-8"))
                    assert capability["launch"]["working_directory"] is True
                    assert query.last_result.state == "incomplete"
        # Python is deliberately an old unsupported backend for this component.
        # It must fail explicitly rather than execute in the ancestor as ready.
        with patch.object(launch, "WINDOWS", True):
            deep_project = project_at(deep)
            unsupported = G4USimRunner()
            runners.append(unsupported)
            done = []
            unsupported.finished.connect(done.append)
            unsupported.start(deep_project)
            wait_for(lambda: bool(done))
            assert done[0] != 0
            assert unsupported.last_result.state == "failed"
            assert unsupported.last_result.reason == "backend_launch.unsupported_working_directory"
            assert unsupported.last_launch.logical_cwd == str(deep)
            assert unsupported.last_launch.launch_cwd != str(deep)
            assert launch.utf16_units(unsupported._process.workingDirectory()) <= launch.MAX_LAUNCH_CWD_UNITS
            assert unsupported._stdout_file is unsupported._stderr_file is None
            old_status = json.loads((deep / "output/logs/run_status.json").read_bytes())
            assert old_status["workingDirectory"] == str(deep)
            assert old_status["launchStatus"] == "unsupported_working_directory"
            record, _ = _backend_command([sys.executable, "--capabilities"], timeout=5, env=dict(os.environ), cwd=deep)
            assert record["status"] == "unsupported_working_directory", record
            assert record["working_directory"] == str(deep)
            assert record["launch_working_directory"] != str(deep)
            assert record["argv"][1:3] == ["--working-directory", str(deep)]
            # Generic SDK/tool commands bypass the backend transport entirely.
            tool, text = _command([sys.executable, "-c", "print('generic-tool')"], timeout=5, env=dict(os.environ), cwd=short)
            assert tool["exit_code"] == 0 and text.strip() == "generic-tool"
            assert "--working-directory" not in tool["argv"]
            for action in ("inspect", "initialization", "run"):
                own_runner = G4USimRunner()
                runners.append(own_runner)
                instance = ExperimentWorkflow(EditSession(WorkspaceSnapshot(deep_project)), own_runner,
                    records_root=deep / ("records-" + action), environment_probe=lambda executable: {"status": "ready"})
                services.append(instance)
                records = []
                instance.completed.connect(records.append)
                if action == "initialization":
                    instance.validate("initialization")
                else:
                    getattr(instance, action)()
                wait_for(lambda: bool(records))
                assert records[0]["status"] == "failed", records[0]
                assert records[0]["reason"] == "experiment.unsupported_working_directory", records[0]["reason"]
                assert not instance.busy and not own_runner.is_running()
                assert own_runner.last_result is None, "Inspect must reject before simulation runner starts"
                transport = records[0]["inspection_launch"]
                assert transport["launch_route"] == "restore_working_directory"
                assert transport["working_directory"] == str(instance.run_project.workspaceRoot)
                assert transport["launch_working_directory"] != transport["working_directory"]
                assert Path(transport["program"]).is_absolute()
        return {"kind": "qt_subprocess_launch_component", "status": "passed", "simulation": "not_executed"}
    finally:
        for runner in runners:
            if runner.is_running():
                runner.kill()
                runner._process.waitForFinished(5000)
        for instance in services:
            instance.close()
        wait_for(lambda: all(instance._closed for instance in services))
        assert all(not runner.is_running() and runner._stdout_file is runner._stderr_file is None for runner in runners)
        QCoreApplication.processEvents()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default="")
    parser.add_argument("--executable", default="", help="Optional real backend capability queries; no simulation")
    args = parser.parse_args()
    app = QCoreApplication.instance() or QCoreApplication([])
    if args.evidence_dir:
        result = exercise(Path(args.evidence_dir).resolve(), args.executable)
    else:
        with tempfile.TemporaryDirectory(prefix="backend-launch-qt-") as directory:
            result = exercise(Path(directory), args.executable)
    app.processEvents()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
