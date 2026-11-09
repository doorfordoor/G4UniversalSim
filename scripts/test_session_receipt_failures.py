"""Real session terminal receipts after output finalization and integrity faults."""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import test_session_protocol as protocol
from run_m0_tests import workspace_source_fingerprint
from test_config_precedence import read_summary

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.session_model import receipt_check_for_event, summarize_round


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _try_evidence(errors, stage, operation):
    try:
        return operation()
    except BaseException as error:
        errors.append((stage, error))
        return None


def _finish_case_evidence(session, case, result, primary_error):
    """Attempt each cleanup/write; never replace an already active failure."""
    errors = []
    if _try_evidence(errors, "poll_before_cleanup", session.process.poll) is None:
        result["cleanup_exit"] = _try_evidence(errors, "cleanup", lambda: session.close(timeout=30))
    _try_evidence(errors, "reader_join", lambda: session.thread.join(timeout=10))
    result["final_exit"] = _try_evidence(errors, "poll_after_cleanup", session.process.poll)
    if result["final_exit"] is None:
        errors.append(("process_exit", RuntimeError("process exit remains unknown after cleanup")))
    alive = _try_evidence(errors, "reader_state", session.thread.is_alive)
    if alive:
        errors.append(("reader_state", RuntimeError("log reader is still active after join")))
    _try_evidence(errors, "backend_log", lambda: (case / "backend.log").write_text(
        "\n".join(session.raw_lines) + "\n", encoding="utf-8"))
    _try_evidence(errors, "frames", lambda: save(case / "frames.json", session.frames))
    if primary_error is not None or errors:
        result["status"] = "failed"
        result.setdefault("error", repr(primary_error if primary_error is not None else errors[0][1]))
    result["cleanup_evidence_errors"] = [{"stage": stage, "error": repr(error)} for stage, error in errors]
    _try_evidence(errors, "execution", lambda: save(case / "execution.json", result))
    if primary_error is None and errors:
        raise errors[0][1]


def _finish_global_evidence(work, executable, binary, source, primary_error):
    errors = []
    identity = dict(binary_before=binary, source_before=source)
    identity["binary_after"] = _try_evidence(errors, "binary_identity", lambda: sha(executable))
    identity["source_after"] = _try_evidence(errors, "source_identity", workspace_source_fingerprint)
    for key, expected in (("binary_after", binary), ("source_after", source)):
        if identity[key] is not None and identity[key] != expected:
            errors.append((key, AssertionError("final identity drift: " + key)))
    identity["status"] = "failed" if primary_error is not None or errors else "verified"
    identity["primary_error"] = repr(primary_error) if primary_error is not None else None
    identity["errors"] = [{"stage": stage, "error": repr(error)} for stage, error in errors]
    _try_evidence(errors, "final_identity_write", lambda: save(work / "final-identity.json", identity))
    # Preserve the established flat files.json format. A failed file digest is
    # explicit null, never a fabricated hash; evidence-status marks incompleteness.
    files = {}
    paths = _try_evidence(errors, "enumerate_evidence", lambda: sorted(work.rglob("*"))) or []
    for path in paths:
        if path == work / "files.json":
            continue
        is_file = _try_evidence(errors, "file_type:" + str(path.relative_to(work)), path.is_file)
        if is_file:
            files[str(path.relative_to(work))] = _try_evidence(
                errors, "hash:" + str(path.relative_to(work)), lambda path=path: sha(path))
    evidence_status = dict(stage="before_manifest_write",
                           status="failed" if primary_error is not None or errors else "pending_manifest",
                           primary_error=repr(primary_error) if primary_error is not None else None,
                           errors=[{"stage": stage, "error": repr(error)} for stage, error in errors])
    status_path = work / "evidence-status.json"
    _try_evidence(errors, "evidence_status_write", lambda: save(status_path, evidence_status))
    files[status_path.name] = _try_evidence(errors, "evidence_status_hash", lambda: sha(status_path))
    _try_evidence(errors, "files_manifest_write", lambda: save(work / "files.json", files))
    if primary_error is None and errors:
        raise errors[0][1]


def _check_terminal_transport(session, welcome, terminal, receipt):
    limit = welcome["limits"]["max_frame_bytes"]
    assert limit == 65536
    # Use the actual line, not the pretty-printed terminal.json in evidence.
    frames = [line for line in session.raw_lines
              if line.startswith("{") and '"event":"run_finished"' in line]
    assert len(frames) == 1 and json.loads(frames[0]) == terminal
    wire_size = len(frames[0].encode("utf-8"))
    assert 0 < wire_size <= limit

    record = Path(welcome["state"]["session_root"]) / f"run-{terminal['run_id']:04d}.json"
    record_bytes = record.read_bytes()
    assert record_bytes.endswith(b"\n") and json.loads(record_bytes) == receipt

    reference = "receipt_ref" in terminal
    assert reference != ("receipt" in terminal), "exactly one receipt form is required"
    if not reference:
        assert terminal["receipt_integrity"] == "written"
        assert Path(terminal["receipt_path"]) == record
        assert terminal["artifacts"] == receipt["artifacts"]
        assert "artifacts_truncated" not in terminal and "artifact_count" not in terminal
        return dict(reference=False, wire_bytes=wire_size, inline_bytes=wire_size, frame_limit=limit)

    ref = terminal["receipt_ref"]
    assert terminal["artifacts_truncated"] is True and "artifacts" not in terminal
    assert terminal["artifact_count"] == len(receipt["artifacts"])
    assert Path(ref["path"]) == record and ref["schema"] == receipt["schema"]
    # Reconstruct the omitted inline payload. Its receipt is the exact on-disk
    # JSON (without the final LF); the envelope and artifact fields contain
    # only strings, integers, booleans and nulls. Worker count is irrelevant.
    expanded = {key: value for key, value in terminal.items()
                if key not in {"artifacts_truncated", "artifact_count", "receipt_ref"}}
    expanded.update(artifacts=receipt["artifacts"], receipt_path=ref["path"],
                    receipt_integrity="written")
    envelope = json.dumps(expanded, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    inline_size = len(envelope) + len(b',"receipt":') + len(record_bytes) - 1
    assert inline_size > limit, "compact receipt emitted for a frame that fits inline"

    for change, reason in (
        ({"size_bytes": ref["size_bytes"] + 1}, "size_mismatch"),
        ({"sha256": ("1" if ref["sha256"][0] == "0" else "0") + ref["sha256"][1:]}, "sha_mismatch"),
    ):
        bad = receipt_check_for_event(dict(terminal, receipt_ref=dict(ref, **change)))
        assert not bad.ok and bad.reason == reason, bad
    return dict(reference=True, wire_bytes=wire_size, inline_bytes=inline_size, frame_limit=limit)


def main():
    executable = Path(os.environ["G4USIM_EXE"]).resolve()
    root = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="receipt-", dir=root))
    binary, source = sha(executable), workspace_source_fingerprint()
    cases = [("normal", None, 16, 32), ("close", "summary_close_t0", 16, 32),
             ("hash", "artifact_hash_master", 16, 32),
             ("inline_hash", "artifact_hash_master", 1, 2)]
    save(work / "plan.json", dict(binary_sha=binary, source=source, cases=cases,
                                 processes=4, events=98, script_sha=sha(Path(__file__))))
    try:
        for name, fault, threads, events in cases:
            case = work / name
            case.mkdir()
            spawn = protocol.subprocess.Popen

            def launch(*args, **kwargs):
                environment = dict(kwargs["env"])
                if fault:
                    environment["G4USIM_TEST_OUTPUT_FAULT"] = fault
                kwargs["env"] = environment
                return spawn(*args, **kwargs)

            with patch.object(protocol.subprocess, "Popen", launch):
                session = protocol.Session(executable, case / "output", case / "records", threads=threads)
            result = dict(pid=session.process.pid, argv=session.process.args, cwd=str(ROOT), fault=fault)
            try:
                welcome = protocol.open_session(session)
                terminal = protocol.run_round(session, events, timeout=240)
                save(case / "terminal.json", terminal)
                session.request("shutdown", revision=session.state()["state_revision"], wait=False)
                code = session.close(timeout=60)
                result["exit"] = code
                check = receipt_check_for_event(terminal)
                assert check.ok, check
                receipt = check.receipt
                assert receipt["status"] == terminal["status"]
                assert receipt["run_request_id"] == terminal["run_request_id"]
                assert receipt["run_id"] == terminal["run_id"] == 0
                assert receipt["planned_events"] == events
                assert terminal["planned_events"] == receipt["planned_events"]
                assert terminal["completed_events"] == receipt["completed_events"]
                assert terminal["aborted_events"] == receipt["aborted_events"]
                assert 0 <= receipt["aborted_events"] <= receipt["completed_events"] <= events
                transport = _check_terminal_transport(session, welcome, terminal, receipt)
                result.update(transport)
                if name == "normal":
                    assert transport["reference"], "oversized normal fixture must exercise a real receipt reference"
                if name == "inline_hash":
                    assert not transport["reference"], "small fault fixture must exercise an inline receipt"
                summary = read_summary(case / "output")
                assert summary["actual_threads"] == str(threads)
                assert summary["run_count"] == "1" and summary["run_0_id"] == "0"
                assert summary["run_0_planned_events"] == str(events)
                assert summary["run_0_completed_events"] == str(receipt["completed_events"])
                assert summary["actual_completed_event_count"] == summary["run_0_completed_events"]
                if fault != "summary_close_t0":
                    assert receipt["completed_events"] == events and receipt["aborted_events"] == 0
                rows = []
                for path in (case / "output").glob("event_edep_t*.csv"):
                    with path.open(encoding="utf-8", newline="") as stream:
                        rows.extend((int(row["runID"]), int(row["eventID"])) for row in csv.DictReader(stream))
                assert len(rows) == len(set(rows))
                assert set(rows) <= {(0, index) for index in range(events)}
                if fault != "summary_close_t0":
                    assert set(rows) == {(0, index) for index in range(events)}
                if fault is None:
                    assert code == 0 and terminal["status"] == "completed"
                    assert receipt["completed_events"] == events and receipt["output_failed"] is False
                    assert summary["status"] == "completed"
                else:
                    assert code != 0 and receipt["output_failed"] is True
                    expected = "aborted" if receipt["aborted_events"] > 0 else "failed"
                    assert terminal["status"] == expected, terminal
                    assert summary["status"] == "failed"
                    assert summary["output_failure_run_id"] == "0"
                    assert summarize_round(terminal, "proton", 10)["status"] == expected
                    if fault == "summary_close_t0":
                        assert summary["output_failure_stage"] == "scoring_write_all"
                        assert "edep_volume_summary_t0.csv" in summary["output_failure_message"]
                        assert "Failed to finalize CSV file" in summary["output_failure_message"]
                artifacts = receipt["artifacts"]
                assert isinstance(artifacts, list) and artifacts
                if fault == "artifact_hash_master":
                    assert any(a["integrity_status"] == "unavailable" for a in artifacts)
                    assert summary["output_failure_stage"] == "artifact_integrity"
                else:
                    for artifact in artifacts:
                        if artifact["integrity_status"] == "hashed":
                            path = Path(artifact["path"])
                            assert path.stat().st_size == artifact["size_bytes"]
                            assert sha(path) == artifact["sha256"]
                session_dirs = list((case / "records").glob("session-*"))
                assert len(session_dirs) == 1
                replay = json.loads((session_dirs[0] / "replay-manifest.json").read_text(encoding="utf-8"))
                steps = [s for s in replay["steps"] if s["op"] == "run"]
                assert len(steps) == 1 and steps[0]["status"] == terminal["status"]
                assert steps[0]["run_id"] == receipt["run_id"]
                assert steps[0]["run_request_id"] == receipt["run_request_id"]
                assert steps[0]["params"]["events"] == receipt["planned_events"]
                assert steps[0]["completed_events"] == receipt["completed_events"]
                if fault:
                    assert replay["replayable"] is False
                result.update(status="passed", terminal_status=terminal["status"],
                              artifact_count=len(artifacts))
            except BaseException as error:
                result.update(status="failed", error=repr(error))
                raise
            finally:
                _finish_case_evidence(session, case, result, sys.exc_info()[1])
    finally:
        _finish_global_evidence(work, executable, binary, source, sys.exc_info()[1])
    print("session receipt failures: four real processes passed; controlled faults, no science claim")


if __name__ == "__main__":
    main()
