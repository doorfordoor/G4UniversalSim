"""Headless command transport for ExperimentWorkflow; no simulation semantics here."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
import json
import math
from pathlib import Path
import signal
import sys
import time

SCHEMA = "g4usim_experiment_cli_v1"


class CliError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise CliError("arguments", message)


def positive_seconds(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected positive finite seconds") from exc
    if not math.isfinite(result) or result <= 0 or result > 86400:
        raise argparse.ArgumentTypeError("seconds must be in (0, 86400]")
    return result


def parser() -> argparse.ArgumentParser:
    result = JsonArgumentParser(prog="python -m g4usim_gui.experiment_cli", allow_abbrev=False)
    source = result.add_mutually_exclusive_group(required=True)
    source.add_argument("--project", type=Path)
    source.add_argument("--bundle", type=Path)
    result.add_argument("--executable", type=Path)
    result.add_argument("--runs-root", type=Path)
    result.add_argument("--records", type=Path, help="action-record directory")
    result.add_argument("--timeout", type=positive_seconds, default=300.0)
    result.add_argument("--stop-timeout", type=positive_seconds, default=5.0)
    commands = result.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)
    commands.add_parser("inspect", allow_abbrev=False)
    validate = commands.add_parser("validate", allow_abbrev=False)
    validate.add_argument("--level", choices=("fields", "initialization"), default="fields")
    apply = commands.add_parser("apply", allow_abbrev=False)
    apply.add_argument("--snapshot", type=Path, required=True)
    apply.add_argument("--save-project", type=Path, required=True)
    commands.add_parser("generate", allow_abbrev=False)
    commands.add_parser("run", allow_abbrev=False)
    evaluate = commands.add_parser("evaluate", allow_abbrev=False)
    selected_run = evaluate.add_mutually_exclusive_group(required=True)
    selected_run.add_argument("--run-id")
    selected_run.add_argument("--run-first", action="store_true",
                              help="explicitly execute fresh inputs before comparing in this process")
    evaluate.add_argument("--comparisons", type=Path, required=True)
    export = commands.add_parser("export", allow_abbrev=False)
    export.add_argument("--destination", type=Path, required=True)
    export.add_argument("--resource-policy", type=Path)
    return result


def read_json(path: Path, limit: int = 24 * 1024 * 1024):
    from g4usim_gui.core.config_migration import load_json_strict
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise CliError("input_too_large", str(path))
    return load_json_strict(raw)


def read_candidate(path: Path):
    from g4usim_gui.core.edit_snapshot import snapshot_from_dict
    # No dotted setters, arbitrary attribute traversal, or JSON patch execution.
    return snapshot_from_dict(read_json(path))


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def await_action(workflow, runner, inspect_process, start, *, timeout, stop_timeout):
    """Wait on the service, keeping Qt delivery and cancellation on its owner thread.

    A local timeout remains a failure even if a late completed signal says pass.
    No process status is ever converted into an experiment success here.
    """
    from PySide6.QtCore import QEventLoop, QTimer
    loop = QEventLoop()
    terminal = []
    interruption = None
    stop_at = None
    forced_at = None
    # CPython 3.11 on Windows uses a coarse clock for monotonic(); perf_counter
    # is monotonic too and preserves sub-tick timeout precision.
    deadline = time.perf_counter() + timeout
    requested = []

    def completed(record):
        nonlocal interruption, stop_at
        if not terminal:
            # A terminal signal can beat the 25 ms polling timer. Observe the
            # deadline and already delivered OS signals at this boundary too.
            if interruption is None:
                if requested:
                    interruption = requested[0]
                elif time.perf_counter() >= deadline:
                    interruption = 'timeout'
            terminal.append(record)
            loop.quit()
            if interruption is not None and stop_at is None:
                stop_at = time.perf_counter()
                request_cancel()

    def interrupt(signum, frame):
        requested.append("cancelled")

    def request_cancel(force=False):
        try:
            workflow.cancel(force=force)
        except Exception as exc:
            # A failed service cancellation must not prevent process cleanup.
            sys.stderr.write(f"cancel: {type(exc).__name__}: {exc}\n")

    def tick():
        nonlocal interruption, stop_at, forced_at
        now = time.perf_counter()
        if interruption is None and (requested or now >= deadline):
            interruption = requested[0] if requested else "timeout"
            stop_at = now
            request_cancel()
        if stop_at is not None and forced_at is None and now - stop_at >= stop_timeout:
            forced_at = now
            request_cancel(force=True)
            if runner.is_running():
                runner.kill()
            if inspect_process.state() != inspect_process.ProcessState.NotRunning:
                inspect_process.kill()
        if forced_at is not None and now - forced_at >= stop_timeout:
            loop.quit()

    previous = {}
    timer = QTimer()
    timer.setInterval(25)
    timer.timeout.connect(tick)
    workflow.completed.connect(completed)
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, interrupt)
        timer.start()
        initial = start()
        # Some actions (notably fields validation) complete synchronously.
        if not terminal and isinstance(initial, dict) and initial.get("status") != "pending":
            completed(initial)
        if not terminal:
            loop.exec()
    finally:
        timer.stop()
        workflow.completed.disconnect(completed)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        # Also cover synchronous dispatch exceptions after a process was started.
        if runner.is_running():
            interruption = interruption or "process_still_running"
            request_cancel(force=True)
            runner.kill()
            cleanup = QEventLoop()
            runner.finished.connect(cleanup.quit)
            QTimer.singleShot(int(stop_timeout * 1000), cleanup.quit)
            if runner.is_running():
                cleanup.exec()
            runner.finished.disconnect(cleanup.quit)
        if inspect_process.state() != inspect_process.ProcessState.NotRunning:
            interruption = interruption or "process_still_running"
            inspect_process.kill()
            inspect_process.waitForFinished(int(stop_timeout * 1000))
    return (terminal[0] if terminal else None), interruption


def json_value(value):
    """Serialize the declared report boundary; reject unknown runtime objects."""
    from g4usim_gui.validators.config_validator import ValidationReport
    if isinstance(value, ValidationReport):
        return json_value(value.to_dict())
    if value is None or type(value) in (str, bool, int, float):
        return value
    if isinstance(value, Path):
        return str(value)
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise CliError("record_schema", "Record keys must be strings")
        return {key: json_value(item) for key, item in value.items()}
    if type(value) in (list, tuple):
        return [json_value(item) for item in value]
    raise CliError("record_schema", f"Unsupported record value: {type(value).__name__}")


def await_closed(workflow, timeout):
    """Keep the owner event loop delivering worker results until close drains."""
    from PySide6.QtCore import QEventLoop, QTimer
    loop, timer = QEventLoop(), QTimer()
    done = []
    deadline = time.perf_counter() + timeout
    def closed():
        done.append(True)
        loop.quit()
    def tick():
        if time.perf_counter() >= deadline:
            loop.quit()
    workflow.closed.connect(closed)
    timer.setInterval(25)
    timer.timeout.connect(tick)
    try:
        timer.start()
        immediate = workflow.close()
        if not immediate and not done:
            loop.exec()
        if not immediate and not done:
            raise CliError('close_timeout', 'Experiment workers did not drain before the close deadline')
    finally:
        timer.stop()
        workflow.closed.disconnect(closed)


@contextmanager
def workflow_lifetime(workflow, stop_timeout):
    try:
        yield
    finally:
        if workflow.busy:
            workflow.cancel(force=True)
        await_closed(workflow, stop_timeout)


def load_input(args):
    from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
    from g4usim_gui.core.project import load_project
    def rebind(snapshot, binding, before, after):
        drafts = snapshot.state['drafts']
        if binding in drafts and drafts[binding] == before:
            drafts[binding] = after
    if args.bundle:
        from g4usim_gui.core.experiment_bundle import load_bundle
        snapshot = load_bundle(args.bundle, executable=str(args.executable.resolve()) if args.executable else "")
        if (args.command in {"run", "inspect"}
                or (args.command == "validate" and args.level == "initialization")
                or (args.command == "evaluate" and args.run_first)):
            if not args.executable:
                raise CliError("executable_required", "Bundle replay requires --executable")
            # Replay the verified closure's inputs. Re-generating the editor model
            # could strand relative resources copied by the legacy package writer.
            bundle = snapshot.transient["bundle"]
            root = Path(bundle["path"])
            replay = bundle["replay_inputs"]
            project = snapshot.project
            before_mode, before_config, before_macro = project.runInputMode, project.configPath, project.macroPath
            project.runInputMode = "external"
            project.workspaceRoot = str(root)
            project.pathSettings.workspace_root = str(root)
            project.configPath = str(root / replay["config"]) if replay["config"] else ""
            project.macroPath = str(root / replay["macro"]) if replay["macro"] else ""
            # Transport-owned mirrors follow the explicit replay selection.
            # An already inconsistent draft remains inconsistent and is rejected.
            rebind(snapshot, 'project.run_input_mode', before_mode, project.runInputMode)
            rebind(snapshot, 'project.config_path', before_config, project.configPath)
            rebind(snapshot, 'project.macro_path', before_macro, project.macroPath)
    else:
        snapshot = WorkspaceSnapshot(load_project(args.project))
    project = snapshot.project
    if args.executable:
        before = project.executable
        project.executable = project.pathSettings.executable = str(args.executable.resolve())
        rebind(snapshot, 'project.executable', before, project.executable)
    if args.runs_root:
        before = project.runsRoot
        project.runsRoot = project.pathSettings.runs_root = str(args.runs_root.resolve())
        rebind(snapshot, 'project.runs_root', before, project.runsRoot)
        rebind(snapshot, 'config.runs_root', before, project.runsRoot)
    elif not project.runsRoot:
        project.runsRoot = project.pathSettings.runs_root = str((Path.cwd() / "runs").absolute())
    return snapshot


def execute(args):
    from PySide6.QtCore import QCoreApplication, QProcess
    from g4usim_gui.core.edit_snapshot import project_for_snapshot
    from g4usim_gui.core.edit_transactions import EditSession
    from g4usim_gui.core.experiment_workflow import ExperimentWorkflow
    from g4usim_gui.core.project import save_project
    from g4usim_gui.core.runner import G4USimRunner

    app = QCoreApplication.instance() or QCoreApplication(["g4usim-experiment"])
    snapshot = load_input(args)
    session = EditSession(snapshot)
    runner = G4USimRunner()
    inspect_process = QProcess()
    records = args.records or Path(snapshot.project.runsRoot) / "experiment-records"
    workflow = ExperimentWorkflow(session, runner, records_root=records.resolve(),
                                  inspect_process=inspect_process)
    with workflow_lifetime(workflow, args.stop_timeout):
        return _dispatch_workflow(args, workflow, runner, inspect_process, session, snapshot, app)


def _dispatch_workflow(args, workflow, runner, inspect_process, session, snapshot, app):
    from PySide6.QtCore import QCoreApplication
    from g4usim_gui.core.edit_snapshot import project_for_snapshot
    from g4usim_gui.core.project import save_project
    candidate = read_candidate(args.snapshot) if args.command == "apply" else None
    comparisons = read_json(args.comparisons) if args.command == "evaluate" else None
    if comparisons is not None and type(comparisons) is not list:
        raise CliError("comparisons", "Comparisons must be a JSON array")
    policy = read_json(args.resource_policy) if args.command == "export" and args.resource_policy else None

    def wait(start):
        return await_action(workflow, runner, inspect_process, start,
                            timeout=args.timeout, stop_timeout=args.stop_timeout)

    bundle_history = snapshot.transient.get('bundle', {}).get('validation_records', [])
    if bundle_history:
        imported, interrupted = wait(lambda: workflow.import_history(bundle_history))
        if interrupted or imported is None or imported.get('status') != 'passed':
            return json_value(imported), 124 if interrupted == 'timeout' else 130 if interrupted == 'cancelled' else 1, interrupted or 'history_import_failed'

    if args.command == 'evaluate' and args.run_first:
        fresh, interrupted = wait(workflow.run)
        if interrupted or fresh is None or fresh.get('status') != 'passed' or fresh.get('stale'):
            return json_value(fresh), 124 if interrupted == 'timeout' else 130 if interrupted == 'cancelled' else 1, interrupted or 'run_before_evaluation_failed'
        args.run_id = fresh['run_id']

    def start():
        if args.command == "validate":
            return workflow.validate(args.level)
        if args.command == "apply":
            return workflow.apply(candidate, expected_revision=session.revision,
                                  label="experiment.cli.apply")
        if args.command == "evaluate":
            return workflow.evaluate(args.run_id, comparisons)
        if args.command == "export":
            return workflow.export(args.destination.resolve(), resource_policy=policy)
        if args.command == "inspect":
            return workflow.inspect()
        if args.command == "generate":
            return workflow.generate()
        return workflow.run()

    record, interruption = wait(start)
    record = json_value(record)
    if interruption:
        code = {"cancelled": 130, "timeout": 124}.get(interruption, 1)
        return record, code, interruption
    if not isinstance(record, dict) or record.get("status") not in {
            "passed", "failed", "stale", "unobserved", "cancelled"}:
        raise CliError("record_schema", "Workflow did not produce a terminal record")
    if record["status"] != "passed" or record.get('stale'):
        return record, 130 if record["status"] == "cancelled" else 1, "workflow_failed"
    if args.command == "apply":
        save_project(project_for_snapshot(session.current()), args.save_project)
        record["saved_project"] = str(args.save_project.absolute())
    # Keep the application alive through signal cleanup and final serialization.
    assert app is QCoreApplication.instance()
    return record, 0, None


def main(argv=None) -> int:
    command = None
    try:
        args = parser().parse_args(argv)
        command = args.command
        # Dependency and backend diagnostics never share the JSON transport.
        with redirect_stdout(sys.stderr):
            record, code, reason = execute(args)
        emit({"schema": SCHEMA, "command": command, "ok": code == 0,
              "record": record, "error": None if reason is None else {"code": reason,
              "message": record.get("reason", reason) if isinstance(record, dict) else reason}})
        return code
    except CliError as exc:
        code, kind, message = 2, exc.code, str(exc)
    except (OSError, ValueError, ImportError) as exc:
        code, kind, message = 2, type(exc).__name__, str(exc)
    except KeyboardInterrupt:
        code, kind, message = 130, "cancelled", "Interrupted"
    except Exception as exc:
        code, kind, message = 3, type(exc).__name__, str(exc)
    emit({"schema": SCHEMA, "command": command, "ok": False, "record": None,
          "error": {"code": kind, "message": message}})
    return code


if __name__ == "__main__":
    raise SystemExit(main())
