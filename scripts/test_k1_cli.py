"""K1 CLI transport tests. Static profile requires gui/requirements.txt (QtCore).

Optional --backend EXE exercises the actual installed service and Geant4 binary;
absence of that option is explicitly not evidence of backend coverage.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import types
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui import experiment_cli as cli
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_to_json
from g4usim_gui.core.project import G4USimProject


def transport_tests():
    for argv in ([], ["--project", "a", "--bundle", "b", "run"],
                 ["--project", "a", "--timeout", "nan", "run"],
                 ["--project", "a", "--timeout", "inf", "run"],
                 ["--project", "a", "--timeout", "0", "run"],
                 ["--project", "a", "validate", "--level", "physics"],
                 ["--project", "a", "apply", "--set", "__dict__.seed=2"],
                 ["--project", "a", "run", "--unknown"]):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.main(argv)
        payload = json.loads(output.getvalue())
        assert code != 0
        assert payload["schema"] == cli.SCHEMA and payload["ok"] is False
        assert payload["error"]["code"] == "arguments"
        assert len(output.getvalue().splitlines()) == 1
    args = cli.parser().parse_args(["--bundle", "中文目录", "--executable", "backend", "run"])
    assert args.bundle == Path("中文目录") and args.command == "run"
    with tempfile.TemporaryDirectory(prefix="k1-cli-") as directory:
        path = Path(directory) / "快照.json"
        path.write_bytes(snapshot_to_json(WorkspaceSnapshot(G4USimProject())))
        candidate = cli.read_candidate(path)
        assert candidate.project.version == 7
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'{}'):
            path.write_bytes(raw)
            rejected = False
            try:
                cli.read_candidate(path)
            except ValueError:
                rejected = True
            assert rejected
        path.write_bytes(b"123456")
        rejected = False
        try:
            cli.read_json(path, limit=5)
        except cli.CliError as exc:
            rejected = exc.code == "input_too_large"
        assert rejected


def event_loop_tests():
    from PySide6.QtCore import QCoreApplication, QObject, QProcess, QTimer, Signal
    app = QCoreApplication.instance() or QCoreApplication([])

    class Service(QObject):
        completed = Signal(dict)

        def __init__(self, deliver_cancel=True):
            super().__init__()
            self.cancels = []
            self.deliver_cancel = deliver_cancel

        def cancel(self, force=False):
            self.cancels.append(force)
            if self.deliver_cancel:
                QTimer.singleShot(0, lambda: self.completed.emit({"test": "cancelled"}))

    class Runner(QObject):
        finished = Signal(int)

        def is_running(self):
            return False

        def kill(self):
            assert False, "idle test runner must not be killed"

    runner, process = Runner(), QProcess()
    service = Service()
    record, reason = cli.await_action(service, runner, process,
        lambda: QTimer.singleShot(0, lambda: service.completed.emit({"test": "finished"})),
        timeout=1, stop_timeout=.05)
    assert record == {"test": "finished"} and reason is None
    service = Service()
    record, reason = cli.await_action(service, runner, process, lambda: None,
                                    timeout=.03, stop_timeout=.05)
    assert reason == "timeout" and service.cancels == [False]
    assert record == {"test": "cancelled"}
    service = Service(deliver_cancel=False)
    record, reason = cli.await_action(service, runner, process, lambda: None,
                                    timeout=.03, stop_timeout=.03)
    assert reason == "timeout" and record is None
    assert service.cancels == [False, True]
    service = Service()
    record, reason = cli.await_action(service, runner, process,
        lambda: QTimer.singleShot(0, lambda: signal.raise_signal(signal.SIGINT)),
        timeout=1, stop_timeout=.05)
    assert reason == "cancelled" and service.cancels == [False]
    service = Service()
    record, reason = cli.await_action(service, runner, process,
        lambda: {"status": "passed", "test": "synchronous"}, timeout=1, stop_timeout=.05)
    assert record == {"status": "passed", "test": "synchronous"} and reason is None
    service = Service()
    began = time.monotonic()
    record, reason = cli.await_action(service, runner, process,
        lambda: QTimer.singleShot(8, lambda: service.completed.emit({'status': 'passed'})),
        timeout=.001, stop_timeout=.05)
    assert record == {'status': 'passed'} and reason == 'timeout', (record, reason, service.cancels, time.monotonic() - began)
    assert service.cancels == [False]
    service = Service()
    def signal_before_terminal():
        QTimer.singleShot(0, lambda: signal.raise_signal(signal.SIGINT))
        QTimer.singleShot(8, lambda: service.completed.emit({'status': 'passed'}))
    record, reason = cli.await_action(service, runner, process, signal_before_terminal,
                                    timeout=1, stop_timeout=.05)
    assert record == {'status': 'passed'} and reason == 'cancelled'
    assert service.cancels == [False]
    service = Service()
    def late_synchronous_terminal():
        time.sleep(.008)
        return {'status': 'passed'}
    record, reason = cli.await_action(service, runner, process, late_synchronous_terminal,
                                    timeout=.001, stop_timeout=.05)
    assert record == {'status': 'passed'} and reason == 'timeout'
    service = Service()
    def interrupted_synchronous_terminal():
        signal.raise_signal(signal.SIGINT)
        return {'status': 'passed'}
    record, reason = cli.await_action(service, runner, process, interrupted_synchronous_terminal,
                                    timeout=1, stop_timeout=.05)
    assert record == {'status': 'passed'} and reason == 'cancelled'
    class Closer(QObject):
        closed = Signal()
        def close(self):
            QTimer.singleShot(8, self.closed.emit)
            return False
    closer = Closer()
    observed = []
    closer.closed.connect(lambda: observed.append(True))
    cli.await_closed(closer, 1)
    assert observed == [True]
    class StuckCloser(QObject):
        closed = Signal()
        def close(self):
            return False
    rejected = False
    try:
        cli.await_closed(StuckCloser(), .001)
    except cli.CliError as error:
        rejected = error.code == 'close_timeout'
    assert rejected
    assert app is QCoreApplication.instance()


def adapter_tests():
    """An explicit service double tests routing, not experiment correctness."""
    from PySide6.QtCore import QObject, Signal, QTimer
    from g4usim_gui.core.project import save_project, load_project
    from g4usim_gui.validators.config_validator import ValidationReport
    calls = []

    class Service(QObject):
        completed = Signal(dict)
        status = "passed"
        closed = Signal()
        busy = False
        completion_delay = 0
        signal_on_start = False

        def __init__(self, session, runner, **kwargs):
            super().__init__()
            self.session = session

        def close(self):
            self.closed.emit()
            return True

        def cancel(self, force=False):
            self.busy = False

        def result(self, action, **extra):
            print("synthetic service diagnostic")
            record = {"action": action, "record_id": "synthetic-record", "status": self.status,
                      "level": "fields", "reason": "synthetic", "run_id": None,
                      "revision": self.session.revision, **extra}
            calls.append(action)
            if self.signal_on_start:
                QTimer.singleShot(0, lambda: signal.raise_signal(signal.SIGINT))
            QTimer.singleShot(self.completion_delay, lambda: self.completed.emit(record))
            return dict(record, status="pending")

        def inspect(self):
            return self.result("inspect")

        def validate(self, level):
            return self.result("validate", report=ValidationReport(), level=level)

        def apply(self, candidate, *, expected_revision, label):
            # The adapter must send a full snapshot to the core entry, not write
            # the model directly. This double models only its acceptance reply.
            assert isinstance(candidate, WorkspaceSnapshot)
            self.session.replace(label, candidate, expected_revision=expected_revision)
            return self.result("apply")

        def generate(self):
            return self.result("generate", package={"package_dir": "/synthetic"})

        def run(self):
            return self.result("run", run_id="explicit-run")

        def evaluate(self, run_id, comparisons):
            assert run_id == "explicit-run" and comparisons == []
            return self.result("evaluate")

        def export(self, destination, resource_policy):
            assert destination.name == "bundle" and resource_policy is None
            return self.result("export")

    module = types.ModuleType("g4usim_gui.core.experiment_workflow")
    module.ExperimentWorkflow = Service
    with tempfile.TemporaryDirectory(prefix="k1-adapter-") as directory:
        root = Path(directory)
        project = root / "project.json"
        save_project(G4USimProject(), project)
        candidate = root / "snapshot.json"
        state = WorkspaceSnapshot(G4USimProject(projectName="accepted"))
        candidate.write_bytes(snapshot_to_json(state))
        comparisons = root / "comparisons.json"
        comparisons.write_text("[]", encoding="utf-8")
        commands = [["inspect"], ["validate", "--level", "initialization"],
            ["apply", "--snapshot", str(candidate), "--save-project", str(root / "saved.json")],
            ["generate"], ["run"],
            ["evaluate", "--run-id", "explicit-run", "--comparisons", str(comparisons)],
            ["export", "--destination", str(root / "bundle")],
            ["evaluate", "--run-first", "--comparisons", str(comparisons)]]
        with patch.dict(sys.modules, {module.__name__: module}):
            for command in commands:
                output, diagnostics = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(diagnostics):
                    code = cli.main(["--project", str(project), *command])
                payload = json.loads(output.getvalue())
                assert code == 0 and payload["ok"] is True, payload
                assert payload["record"]["action"] == command[0]
                assert "synthetic service diagnostic" in diagnostics.getvalue()
                assert len(output.getvalue().splitlines()) == 1
            assert load_project(root / "saved.json").projectName == "accepted"
            for status in ("failed", "stale", "unobserved", "cancelled"):
                Service.status = status
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    code = cli.main(["--project", str(project), "run"])
                assert code != 0 and json.loads(output.getvalue())["ok"] is False
            Service.status = 'passed'
            Service.completion_delay = 8
            for timeout, interrupted, expected in (('.001', False, 124), ('1', True, 130)):
                Service.signal_on_start = interrupted
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                    code = cli.main(['--project', str(project), '--timeout', timeout, 'run'])
                payload = json.loads(output.getvalue())
                assert code == expected and payload['ok'] is False, payload
                assert payload['error']['code'] == ('cancelled' if interrupted else 'timeout')
    assert calls[:7] == ["inspect", "validate", "apply", "generate", "run", "evaluate", "export"]
    assert calls[7:9] == ['run', 'evaluate']


def process_lifecycle_tests():
    """Use the real runner with a Python fixture process, not a fake Geant4."""
    from PySide6.QtCore import QCoreApplication, QObject, QProcess, Signal
    from g4usim_gui.core.runner import G4USimRunner
    app = QCoreApplication.instance() or QCoreApplication([])
    with tempfile.TemporaryDirectory(prefix="k1-cli-process-") as directory:
        root = Path(directory)
        config = root / "fixture.ini"
        config.write_text("[run]\n", encoding="utf-8")
        project = G4USimProject(runInputMode="external", executable=sys.executable,
            workspaceRoot=str(root), configPath=str(config), outputDir=str(root / "output"))
        runner = G4USimRunner()

        class Service(QObject):
            completed = Signal(dict)

            def cancel(self, force=False):
                if force:
                    runner.kill()
                else:
                    runner.terminate()

        service = Service()
        runner.finished.connect(lambda code: service.completed.emit({"status": runner.last_result.state}))
        record, reason = cli.await_action(service, runner, QProcess(),
            lambda: runner.start(project, [sys.executable, "-c", "pass"]),
            timeout=5, stop_timeout=.1)
        assert reason is None and record["status"] != "success"
        assert runner.last_result is not None and runner.last_result.state != "success"
        assert not runner.is_running()
        began = time.monotonic()
        record, reason = cli.await_action(service, runner, QProcess(),
            lambda: runner.start(project, [sys.executable, "-c", "import time; time.sleep(30)"]),
            timeout=.1, stop_timeout=.1)
        assert reason == "timeout"
        assert not runner.is_running()
        assert runner.last_result is not None and runner.last_result.state != "success"
        assert time.monotonic() - began < 5
    assert app is QCoreApplication.instance()


def bundle_adapter_tests():
    from g4usim_gui.core.experiment_bundle import export_bundle
    from test_live_progress import fixture
    with tempfile.TemporaryDirectory(prefix="k1-cli-bundle-") as directory:
        root = Path(directory)
        config, macro = fixture(root / "inputs", (3,), threads=1)
        snapshot = WorkspaceSnapshot(G4USimProject(runInputMode="external",
            workspaceRoot=str(root), configPath=str(config), macroPath=str(macro)))
        bundle = root / "export"
        export_bundle(snapshot, bundle, validation_records=[{"status": "passed", "run_id": "old"}])
        moved = root / "搬移后"
        bundle.rename(moved)
        (root / "inputs").rename(root / "old-inputs")
        args = cli.parser().parse_args(["--bundle", str(moved), "--executable", sys.executable,
                                       "--runs-root", str(root / "new-runs"), "run"])
        replay = cli.load_input(args)
        assert replay.project.runInputMode == "external"
        assert Path(replay.project.workspaceRoot) == moved
        assert Path(replay.project.configPath).is_relative_to(moved)
        assert Path(replay.project.configPath).is_file()
        assert Path(replay.project.macroPath).is_file()
        assert replay.project.executable == str(Path(sys.executable).resolve())
        history = replay.transient["bundle"]["validation_records"]
        assert history[0]["stale"] is True
        assert history[0]["record"]["run_id"] == "old"
        (moved / "workspace.json").write_bytes(b"{}")
        rejected = False
        try:
            cli.load_input(args)
        except ValueError:
            rejected = True
        assert rejected
    from test_f5_transactions_backend import initial_state
    with tempfile.TemporaryDirectory(prefix='k1-cli-generated-bundle-') as directory:
        root = Path(directory)
        inputs = root / 'inputs'
        inputs.mkdir()
        snapshot, _ = initial_state(inputs, Path(sys.executable))
        snapshot.state['drafts'].update({'project.run_input_mode': 'generated',
            'project.config_path': '', 'project.macro_path': ''})
        bundle = root / 'bundle'
        export_bundle(snapshot, bundle)
        run = cli.load_input(cli.parser().parse_args(['--bundle', str(bundle), '--executable', sys.executable, 'run']))
        assert run.project.runInputMode == run.state['drafts']['project.run_input_mode'] == 'external'
        assert run.project.configPath == run.state['drafts']['project.config_path']
        assert run.project.macroPath == run.state['drafts']['project.macro_path']
        apply = cli.load_input(cli.parser().parse_args(['--bundle', str(bundle), 'apply',
            '--snapshot', str(root / 'candidate.json'), '--save-project', str(root / 'saved.json')]))
        assert apply.project.runInputMode == apply.state['drafts']['project.run_input_mode'] == 'generated'
        assert apply.project.sourceEditor.energy == snapshot.project.sourceEditor.energy


def backend_tests(executable: Path, evidence_root: Path | None = None):
    """Keep all real-backend evidence even when the first assertion fails."""
    base = evidence_root or Path(os.environ.get('G4USIM_TEST_EVIDENCE_DIR') or ROOT / 'out/verification/k1-cli')
    root = base.absolute() / ('k1-cli-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid4().hex[:10])
    root.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='g4usim_k1_cli_test_receipt_v1', status='running', executable=str(executable.absolute()),
                   evidence_root=str(root), started_at=datetime.now(timezone.utc).isoformat())
    try:
        _backend_tests(executable, root)
    except BaseException as error:
        receipt.update(status='failed', error_type=type(error).__name__, error=str(error))
        raise
    else:
        receipt['status'] = 'passed'
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        (root / 'test-receipt.json').write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print('K1 CLI retained evidence: ' + str(root))


def _backend_tests(executable: Path, evidence_directory: Path):
    """Subprocess CLI calls, real backend, relocated bundle and damaged inputs."""
    from g4usim_gui.core.project import save_project
    from test_live_progress import fixture
    assert executable.is_file(), executable
    with contextlib.nullcontext(evidence_directory) as directory:
        root = Path(directory)
        config, macro = fixture(root / "inputs", (3,), threads=1)
        project = G4USimProject(runInputMode="external", executable=str(executable.resolve()),
            workspaceRoot=str(root), configPath=str(config), macroPath=str(macro),
            runsRoot=str(root / "runs"), outputDir=str(root / "requested-output"), seed="4242")
        project_path = root / "project.json"
        save_project(project, project_path)
        env = dict(os.environ, PYTHONPATH=str(ROOT / "gui"))
        invocation_count = 0

        def invoke(command, *, bundle=None, good=True):
            nonlocal invocation_count
            invocation_count += 1
            case = root / 'invocations' / f'{invocation_count:02d}-{command[0]}'
            case.mkdir(parents=True)
            shutil.copytree(root / 'inputs', case / 'inputs')
            for name in ('project.json', 'reference.json', 'comparisons.json'):
                if (root / name).is_file():
                    shutil.copyfile(root / name, case / name)
            source = ["--bundle", str(bundle), "--executable", str(executable.resolve())] if bundle else ["--project", str(project_path)]
            argv = [sys.executable, "-m", "g4usim_gui.experiment_cli", *source,
                "--runs-root", str(root / "runs"), "--records", str(root / "records"),
                "--timeout", "120", *command]
            receipt = dict(command=argv, cwd=str(root), expected_success=good,
                           started_at=datetime.now(timezone.utc).isoformat())
            stdout, stderr = b'', b''
            try:
                result = subprocess.run(argv, cwd=root, env=env, capture_output=True, timeout=150)
                stdout, stderr = result.stdout, result.stderr
                receipt.update(exit_code=result.returncode, timed_out=False)
            except subprocess.TimeoutExpired as error:
                stdout, stderr = error.stdout or b'', error.stderr or b''
                receipt.update(exit_code=None, timed_out=True)
                raise
            except OSError as error:
                receipt.update(exit_code=None, timed_out=False, launch_error=str(error))
                raise
            finally:
                (case / 'stdout.log').write_bytes(stdout)
                (case / 'stderr.log').write_bytes(stderr)
                receipt.update(finished_at=datetime.now(timezone.utc).isoformat(),
                    stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest())
                (case / 'exit-receipt.json').write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
            payload = json.loads(result.stdout)
            (case / 'result.json').write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
            assert (result.returncode == 0) == good, (payload, result.stderr[-3000:].decode('utf-8', 'replace'))
            assert payload["ok"] is good, payload
            if good:
                assert payload["record"]["status"] == "passed", payload
            return payload

        invoke(["inspect"])
        invoke(["validate", "--level", "fields"])
        invoke(["validate", "--level", "initialization"])
        first = invoke(["run"])
        assert first["record"]["run_id"], first
        output = Path(first['record']['output_dir'])
        artifact = next(output.glob('event_edep_t0.csv'))
        with artifact.open(encoding='utf-8', newline='') as stream:
            values = [float(row['raw_edep_MeV']) for row in csv.DictReader(stream)]
        assert len(values) == 3
        definition = dict(quantity='energy_deposition', unit='MeV', weighted=False,
            normalization='per_event', run=0, object='sensitive_total',
            source='CLI same-seed arithmetic regression; not an independent physical reference')
        reference = root / 'reference.json'
        reference.write_text(json.dumps(dict(schema='g4usim_physical_reference_v1',
            value=statistics.mean(values), conditions='Three-event CLI transport fixture, fixed seed 4242',
            source_kind='user_supplied', **definition)), encoding='utf-8')
        comparison = dict(artifact=artifact.name, column='raw_edep_MeV',
            reference=statistics.mean(values), reference_unit='MeV',
            absolute_tolerance=1e-9, relative_tolerance=0., statistical_method='mean_standard_error',
            sigma_multiplier=0., reference_file=str(reference), **definition)
        comparisons = root / 'comparisons.json'
        comparisons.write_text(json.dumps([comparison]), encoding='utf-8')
        evaluated = invoke(['evaluate', '--run-first', '--comparisons', str(comparisons)])
        assert evaluated['record']['action'] == 'evaluate'
        historical = invoke(['evaluate', '--run-id', first['record']['run_id'], '--comparisons', str(comparisons)])
        assert historical['record']['evaluated_run_id'] == first['record']['run_id']
        comparisons.write_text(json.dumps([dict(comparison, passed=True)]), encoding='utf-8')
        invoke(['evaluate', '--run-first', '--comparisons', str(comparisons)], good=False)
        bundle = root / "bundle"
        invoke(["export", "--destination", str(bundle)])
        shutil.copytree(bundle, root / 'exported-bundle-original')
        moved = root / "搬移包"
        bundle.rename(moved)
        second = invoke(["run"], bundle=moved)
        assert second["record"]["run_id"] != first["record"]["run_id"]
        (moved / "workspace.json").write_bytes(b"{}")
        invoke(["run"], bundle=moved, good=False)
        macro.write_text("/run/initialize\n", encoding="utf-8", newline="\n")
        invoke(["run"], good=False)  # Exit zero and no events must fail.
        print("PASS K1 CLI real backend inspect/fields/initialization/events/bundle replay/rejections")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", nargs="?", const=os.environ.get("G4USIM_EXE", ""))
    parser.add_argument('--evidence-root', type=Path)
    args = parser.parse_args()
    transport_tests()
    event_loop_tests()
    adapter_tests()
    process_lifecycle_tests()
    bundle_adapter_tests()
    if args.backend is not None:
        backend_tests(Path(args.backend), args.evidence_root)
    else:
        print("Backend not requested; no backend coverage claimed")
    print("PASS K1 CLI static transport/adapter (synthetic service)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
