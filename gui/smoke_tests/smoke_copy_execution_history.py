"""Qt component coverage for the explicit copy-to-execution History link.

No backend, helper or desktop window is launched. The real workflow prepares
and verifies a synthetic backend receipt, and the real History/Results views
consume the resulting durable record.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtCore import QCoreApplication, QEvent, QProcess
from PySide6.QtWidgets import QApplication, QMessageBox
from g4usim_gui.core import experiment_workflow as workflow
from g4usim_gui.core.config_migration import digest
from g4usim_gui.core.run_result import evaluate_run_result, summary_fingerprint
from g4usim_gui.history import run_history_store
from g4usim_gui.history.run_history_scanner import scan_package, scan_runs_root
from g4usim_gui.output.identity import hash_file
from g4usim_gui.widgets.run_history_page import RunHistoryPage
from gui_test_window import MainWindow
from smoke_duplicate_history_cli import current_project, package_fixture
from smoke_f1_output_identity import publish, upgrade
from smoke_history import _make_package
from smoke_k1_workflow import close_window, wait_workflow


def backend_fixture(project, record):
    output = Path(project.outputDir)
    root = output.parent
    logs = root / "logs"
    logs.mkdir()
    doc = upgrade(output)
    name = record["requested_run_name"]
    doc["values"] = {"run_name": name, "effective_run_name": name}
    summary = output / "run_summary.txt"
    summary.write_text(
        "status = completed\nprogram_exit_code = 0\nsummary_write_status = completed\n"
        "macro_execution_status = completed\nrun_count = 1\nplanned_event_count = 1\n"
        "actual_completed_event_count = 1\nsimulation_executed = true\n"
        f"actual_output_dir = {output}\nmain_config = {project.configPath}\n"
        f"actual_macro_file = {project.macroPath}\nrun_name = {name}\neffective_run_name = {name}\n"
        "[Runs]\nrun_0_id = 0\nrun_0_planned_events = 1\nrun_0_completed_events = 1\n",
        encoding="utf-8",
    )
    hits = output / "hits_t0.csv"
    hits.write_text("runID,eventID,edep_MeV\n0,0,1\n", encoding="utf-8")
    doc["generated_files"].append({"path": hits.as_posix(), "schema": "hits_csv_v1",
                                  "scope": "thread", "run_id": 0, "thread_id": 0,
                                  "integrity_status": "hashed"})
    execution_id = uuid4().hex
    doc["provenance"]["execution_id"] = execution_id
    doc["provenance"]["inputs"] = [
        {"sequence": index, "path": path, "kind": "ini", "role": facts["role"],
         "capture_method": "binary_buffer", "status": "recorded", "reason": "",
         "sha256": facts["sha256"], "size_bytes": facts["size_bytes"]}
        for index, (path, facts) in enumerate(record["expected_inputs"].items(), 1)
    ]
    for row in doc["generated_files"]:
        row["execution_id"] = execution_id
        file = output / Path(row["path"]).name
        if file.name != "run_metadata.json":
            row["sha256"], row["size_bytes"] = hash_file(file)
    publish(output, doc)
    (logs / "stdout.log").write_text("synthetic run stdout\n", encoding="utf-8")
    (logs / "run_status.json").write_text(json.dumps({
        "state": "success", "exitCode": 0, "exitStatus": "normal", "resultVersion": 1,
        "summaryFresh": True, "summaryFingerprint": list(summary_fingerprint(summary)),
    }), encoding="utf-8")
    return evaluate_run_result(summary, exit_code=0, summary_fresh=True)


def attempt(app, window, original, *, mode):
    service = window.experiment
    completed = []
    window.experiment.completed.connect(completed.append)
    inspection, starts = [], []
    try:
        with patch.object(window._macro_inspection, "start", side_effect=lambda: inspection.append(True)), \
             patch.object(window.runner, "start", side_effect=lambda p, cmd: starts.append((p, cmd))):
            if mode == "ordinary":
                window.start_run()
            else:
                window.duplicate_history_package(str(original), run_after=True)
            package = Path(window.project.workspaceRoot)
            locator = package / "copy_execution_link.json"
            previous = locator.read_bytes() if locator.is_file() else None
            wait_workflow(app, window, lambda: bool(inspection) or not service.busy)
            assert inspection and service.busy, service.state()
            record = service._active["record"]
            root = Path(record["record_dir"])
            if mode == "ordinary":
                assert "copy_origin" not in record
            else:
                assert record["copy_origin"] == {
                    "package": package.name,
                    "snapshot_sha256": digest((package / "project_snapshot.json").read_bytes()),
                }
                assert not locator.exists()
            raw = b'{"schema":"G4UniversalSimRunPlan","version":1,"configuration_phase":"before_macro"}'
            with patch.object(window._macro_inspection, "readAllStandardOutput", return_value=raw), \
                 patch.object(window._macro_inspection, "readAllStandardError", return_value=b"first preflight error"):
                service._inspect_finished(2 if mode in {"preflight", "persist_error", "link_error"} else 0,
                                          QProcess.NormalExit)
            if mode in {"preflight", "persist_error", "link_error"}:
                original_persist = workflow._persist

                def terminal_persist(record):
                    if mode == "persist_error" and record.get("finished_at"):
                        raise OSError("controlled terminal write error")
                    return original_persist(record)
                with patch.object(workflow, "_persist", side_effect=terminal_persist):
                    if mode == "link_error":
                        with patch.object(os, "link", side_effect=OSError("controlled locator error")):
                            wait_workflow(app, window)
                    else:
                        wait_workflow(app, window)
                assert not starts
            else:
                wait_workflow(app, window, lambda: bool(starts) or not service.busy)
                assert len(starts) == 1, service.state()
                project, command = starts[0]
                assert Path(command[command.index("--output") + 1]) == root / "output"
                assert Path(project.workspaceRoot) == root / "execution-inputs"
                window.runner.last_result = backend_fixture(project, record)
                window.runner._output_dir = Path(project.outputDir)
                reached, release = threading.Event(), threading.Event()
                original_persist = workflow._persist

                def hold_first_terminal(record):
                    original_persist(record)
                    if record.get("status") == "passed" and not reached.is_set():
                        reached.set()
                        assert release.wait(12), "terminal test did not release the publication gate"

                with patch.object(workflow, "_persist", side_effect=hold_first_terminal):
                    try:
                        window.runner.finished.emit(0)
                        wait_workflow(app, window, lambda: reached.is_set() or not service.busy)
                        assert reached.is_set(), service.state()
                        assert not completed
                        assert (locator.read_bytes() if locator.is_file() else None) == previous
                        if mode == "late_cancel":
                            service.cancel()
                            with patch.object(QMessageBox, "warning"):
                                window.runner.errorOccurred.emit("duplicate late process signal")
                        elif mode == "late_edit":
                            service.invalidate("fixture_edit_during_terminal_write")
                    finally:
                        release.set()
                    wait_workflow(app, window)
            assert len(completed) == 1
            receipt = completed[0]
            if mode == "ordinary":
                assert receipt["status"] == "passed" and locator.read_bytes() == previous
            elif mode == "persist_error":
                assert receipt["status"] == "failed" and not locator.exists()
                assert "controlled terminal write error" in receipt["reason"]
                assert "first preflight error" in receipt["_copy_attempt_reason"]
            elif mode == "link_error":
                assert receipt["status"] == "failed" and not locator.exists()
                assert "first preflight error" in receipt["reason"]
                assert "controlled locator error" in receipt["_copy_link_diagnostic"]
                assert not list(package.glob(".copy_execution_link.json.*.tmp"))
                assert json.loads((root / "record.json").read_bytes())["reason"] == receipt["reason"]
            else:
                saved = json.loads((root / "record.json").read_bytes())
                assert json.loads(locator.read_bytes()) == {
                    "schema": "g4usim_copy_execution_link_v1", "record_id": root.name,
                }
                expected = {"preflight": "failed", "late_cancel": "cancelled", "late_edit": "stale"}.get(mode, "passed")
                assert saved["status"] == receipt["status"] == expected
                assert saved["reason"] == receipt["reason"]
                if mode == "preflight":
                    assert "first preflight error" in saved["reason"]
                if mode == "late_cancel":
                    assert "duplicate late" not in saved["reason"]
            assert not list((package / "output").iterdir())
            assert not list((package / "logs").iterdir())
            print("component:", mode, receipt["status"], root.name)
            return package, root
    finally:
        window.experiment.completed.disconnect(completed.append)


def select(app, window, page, package):
    wait_workflow(app, window, lambda: not page._scan_job.pending)
    row = next(index for index, entry in enumerate(page._filtered) if Path(entry.package_dir) == package)
    page.table.selectRow(row)
    wait_workflow(app, window, lambda: not page._selection_job.pending)
    return page._selected()


def click_routes(app, window, page, action):
    output_calls = []

    def opened_output(root, output):
        output_calls.append((root, output))

    page.openOutputRequested.connect(opened_output)
    try:
        with patch.object(page, "_open_dir") as open_logs:
            getattr(page, f"open_{action}_button").click()
            wait_workflow(app, window, lambda: not page._selection_job.pending)
            return output_calls, [call.args[0] for call in open_logs.call_args_list]
    finally:
        page.openOutputRequested.disconnect(opened_output)


def check_click_after_locator_arrives(app, window, runs, package, execution, legacy):
    page = RunHistoryPage()
    page.set_runs_root(str(runs))
    locator = package / "copy_execution_link.json"
    original = locator.read_bytes()
    record = json.loads((execution / "record.json").read_bytes())
    try:
        for action in ("output", "logs"):
            for valid in (True, False):
                # Build a separate stale selection for each button. The other
                # button must not refresh the row before the tested click.
                locator.unlink(missing_ok=True)
                page.refresh()
                initial = select(app, window, page, package)
                assert initial.status == "success" and not initial.copy_linked
                assert getattr(page, f"open_{action}_button").isEnabled()
                if valid:
                    workflow.publish_copy_execution(package, record)
                else:
                    locator.write_bytes(b"{")
                assert not initial.copy_linked
                expected = (([(str(execution), str(execution / "output"))], []) if action == "output"
                            else ([], [str(execution / "logs")])) if valid else ([], [])
                observed = click_routes(app, window, page, action)
                assert observed == expected, (action, valid, observed, expected)
                assert page._selected().status == ("success" if valid else "incomplete")
                print("component: locator_arrives_after_selection", action, "valid" if valid else "malformed")

        locator.write_bytes(original)
        page.refresh()
        assert select(app, window, page, package).copy_record_id == execution.name
        locator.write_bytes(b"{")
        assert click_routes(app, window, page, "output") == ([], [])
        assert page._selected().copy_record_id == execution.name
        locator.write_bytes(original)

        page.refresh()
        assert select(app, window, page, package).copy_linked
        legacy_row = next(i for i, item in enumerate(page._filtered) if Path(item.package_dir) == legacy)
        emitted = []
        page.openOutputRequested.connect(lambda *args: emitted.append(args))
        page.open_output_button.click()
        assert page._selection_job.pending
        # Qt delivers worker receipts through a queued signal, so the new
        # selection retires the open request before any completion can dispatch.
        page.table.selectRow(legacy_row)
        wait_workflow(app, window, lambda: not page._selection_job.pending)
        assert Path(page._selected().package_dir) == legacy and not emitted
        print("component: selected_execution_id_retained_and_stale_action_retired")

        for scan_root, path in ((runs, legacy), (runs / "experiment-records", execution)):
            page.set_runs_root(str(scan_root))
            page.refresh()
            assert not select(app, window, page, path).copy_linked
            assert click_routes(app, window, page, "output") == ([(str(path), str(path / "output"))], [])
            assert click_routes(app, window, page, "logs") == ([], [str(path / "logs")])
        print("component: ordinary_and_direct_execution_actions")
    finally:
        locator.write_bytes(original)
        page.close()


def consumer_checks(app, window, runs, package, execution, second, failed):
    page = window.run_history_page
    page.set_runs_root(str(runs))
    page.refresh()
    entry = select(app, window, page, package)
    assert (entry.status, entry.result_dir, entry.output_dir, entry.logs_dir) == (
        "success", str(execution), str(execution / "output"), str(execution / "logs"))
    assert entry.identity_status == "verified" and entry.hits_files_count == 1
    assert Path(entry.config_path).is_relative_to(package)
    assert page.identity_panel._evidence is not None
    with patch.object(page, "_open_dir") as open_dir:
        page.open_logs_button.click()
        wait_workflow(app, window, lambda: not page._selection_job.pending)
        open_dir.assert_called_once_with(str(execution / "logs"))
    page.open_output_button.click()
    wait_workflow(app, window, lambda: not page._selection_job.pending and not window.output_page._identity_job.pending)
    results = window.output_page
    assert (results._package_dir, results._output_dir) == (str(execution), str(execution / "output"))
    assert "synthetic run stdout" in results.logs_text.toPlainText()
    for kind in ("hits", "event_edep"):
        task = next(t for t in results._merge_plan.tasks if t.kind == kind)
        assert task.available and task.provenance_status == "verified"
        assert Path(task.command_args[0]) == ROOT / "scripts/merge_outputs.py"
        assert all(Path(n).parent == execution / "output" for n in task.matched_files)
        with patch.object(results._merge_runner, "run_tasks") as start:
            results._run_merge_tasks([task])
            start.assert_called_once_with([task], execution / "logs")
    failed_entry = select(app, window, page, second)
    assert failed_entry.result_dir == str(failed) and failed_entry.status == "failed"
    assert "first preflight error" in failed_entry.result_reason and not page.open_output_button.isEnabled()
    assert any(Path(e.package_dir) == execution and e.status == "success"
               for e in scan_runs_root(str(runs / "experiment-records")))

    # A fresh view resolves the persisted link with no in-memory workflow binding.
    reopened = RunHistoryPage()
    reopened.set_runs_root(str(runs))
    reopened.refresh()
    assert select(app, window, reopened, package).copy_record_id == execution.name
    reopened.close()

    locator = package / "copy_execution_link.json"
    original_locator = locator.read_bytes()
    # A corrupted/deleted link after selecting a good row must not open old output.
    select(app, window, page, package)
    event = execution / "output/event_edep_t0.csv"
    original_event = event.read_bytes()
    event.write_bytes(original_event + b"\n")
    with patch.object(window.output_page, "set_package_dir") as open_results:
        page.open_output_button.click()
        wait_workflow(app, window, lambda: not page._selection_job.pending)
        assert not open_results.called and page._selected().status == "incomplete"
    event.write_bytes(original_event)
    status_path = execution / "logs/run_status.json"
    original_status = status_path.read_bytes()
    status = json.loads(original_status)
    status["summaryFresh"] = False
    status_path.write_text(json.dumps(status), encoding="utf-8")
    assert scan_package(package).status == "incomplete"
    status_path.write_bytes(original_status)

    # Plant otherwise valid same-root legacy evidence to make fallback observable.
    legacy = _make_package(runs, "20260621_010101_legacy", {"state": "success", "exitCode": 0}, True)
    assert scan_package(legacy).status == "success"
    import shutil
    for relative in ("output/run_summary.txt", "logs/run_status.json"):
        shutil.copy2(legacy / relative, package / relative)
    for bad in (b"{", b'{"schema":"g4usim_copy_execution_link_v1","record_id":"../escape"}',
                (second / "copy_execution_link.json").read_bytes()):
        locator.write_bytes(bad)
        observed = scan_package(package)
        assert observed.copy_linked and observed.status == "incomplete" and not observed.output_dir
    locator.write_bytes(original_locator)
    assert scan_package(package).status == "success"

    page.refresh()
    assert select(app, window, page, package).status == "success"
    locator.unlink()
    with patch.object(window.output_page, "set_package_dir") as open_results:
        page.open_output_button.click()
        wait_workflow(app, window, lambda: not page._selection_job.pending)
        assert not open_results.called and page._selected().status == "incomplete"
    locator.write_bytes(original_locator)

    # No write can replace the selected attempt; a repeat uses a new C and E.
    receipt = json.loads((execution / "record.json").read_bytes())
    assert workflow.publish_copy_execution(package, receipt) is None
    assert locator.read_bytes() == original_locator
    check_click_after_locator_arrives(app, window, runs, package, execution, legacy)
    print("component: linked_history_results_refresh_and_restart_equivalent")
    print("component: fail_closed_tamper_stale_cross_copy_and_traversal")
    print("component: legacy_and_direct_execution_routes")


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4USimSmoke")
    app.setApplicationName("CopyExecutionHistory")
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="copy-link-") as temp:
        work = Path(temp).resolve()
        runs = work / "异根 Copy Runs"
        runs.mkdir()
        run_history_store.STATE_PATH = work / "state.json"
        with patch.object(QProcess, "start", side_effect=AssertionError("Unexpected QProcess start")), \
             patch.object(subprocess, "Popen", side_effect=AssertionError("Unexpected process start")):
            window = MainWindow()
            try:
                window.experiment._probe = lambda _: {"status": "ready"}
                source = package_fixture(work / "generated")
                original = Path(source.package_dir)
                original_tree = {p: p.read_bytes() for p in original.rglob("*") if p.is_file()}
                current_project(window, runs)
                package, execution = attempt(app, window, original, mode="success")
                assert attempt(app, window, original, mode="ordinary")[0] == package
                second, failed = attempt(app, window, package, mode="preflight")
                assert second != package and failed != execution
                for mode in ("late_cancel", "late_edit", "persist_error", "link_error"):
                    other, _ = attempt(app, window, original, mode=mode)
                    assert scan_package(other).status != "success"
                consumer_checks(app, window, runs, package, execution, second, failed)
                assert {p: p.read_bytes() for p in original.rglob("*") if p.is_file()} == original_tree
            finally:
                close_window(app, window)
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    print("smoke_copy_execution_history: ok")


if __name__ == "__main__":
    main()
