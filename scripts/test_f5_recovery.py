"""Recovery atomicity and genuine process-death/lease experiments (no Qt)."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.project import G4USimProject, project_to_dict
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, project_for_snapshot
from g4usim_gui.editors.material_editor_model import MaterialDocument
from g4usim_gui.core import workspace_recovery as recovery


def payload(name="未命名草稿"):
    project = G4USimProject(projectName=name)
    project.seed = "invalid draft"
    # The flat seed can be an invalid raw draft if the typed run seed exists.
    project.runSettings.seed = 1
    project.materialEditor = MaterialDocument()
    return project_to_dict(project_for_snapshot(WorkspaceSnapshot(project)))


def rejected(action, contains=""):
    try:
        action()
    except (ValueError, OSError, RuntimeError) as exc:
        assert contains in str(exc), str(exc)
    else:
        assert False, "Invalid or competing recovery action was accepted"


def child(mode, root):
    store = recovery.RecoveryStore(root)
    session = store.open_session()
    receipt = session.publish(payload(), 1)
    if mode == "normal":
        session.retire("saved")
        session.close()
        print(json.dumps({"normal": True}), flush=True)
        return
    if mode == "retained":
        session.retain()
        session.close()
        print(json.dumps({"retained": True}), flush=True)
        return
    if mode.startswith("atomic_"):
        original_replace = recovery.os.replace

        def stopped_replace(source, target):
            if mode == "atomic_after":
                original_replace(source, target)
            print(json.dumps({"id": session.session_id, "point": mode,
                              "temporary": str(source), "previous": receipt.raw_sha256,
                              "pid": os.getpid()}), flush=True)
            sys.stdin.readline()  # Parent kills this process at the actual write boundary.
            if mode == "atomic_before":
                original_replace(source, target)
        recovery.os.replace = stopped_replace
        session.publish(payload("second actual generation"), 2)
        return
    print(json.dumps({"id": session.session_id, "pid": os.getpid(),
                      "sha256": receipt.raw_sha256, "revision": receipt.revision}), flush=True)
    for command in sys.stdin:
        if command.strip() == "edit":
            session.publish(payload("live second generation"), 2)
            print(json.dumps({"revision": 2}), flush=True)
        elif command.strip() == "close":
            session.retire("saved")
            session.close()
            return


def start_child(root, mode="active"):
    # The Windows venv python.exe can be a redirector that owns a second real
    # interpreter process. Kill the directly spawned base interpreter instead,
    # and assert the child's own PID agrees before interpreting a crash result.
    executable = getattr(sys, "_base_executable", sys.executable) if os.name == "nt" else sys.executable
    process = subprocess.Popen([executable, str(Path(__file__).resolve()), "--child", mode, str(root)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", cwd=ROOT)
    ready = read_line(process)
    if "pid" in ready:
        assert process.pid == ready["pid"], "The process handle does not own the actual recovery writer"
    return process, ready


def read_line(process):
    responses = queue.Queue()
    thread = threading.Thread(target=lambda: responses.put(process.stdout.readline()), daemon=True)
    thread.start()
    try:
        line = responses.get(timeout=15)
    except queue.Empty:
        process.kill()
        process.wait(timeout=10)
        assert False, "Recovery child did not reach its observable boundary"
    assert line, f"Recovery child exited early: {process.poll()}: {process.stderr.read()}"
    return json.loads(line)


def kill_owned(process):
    process.kill()
    code = process.wait(timeout=10)
    assert code != 0, "The crash experiment unexpectedly closed normally"
    process.stdin.close()
    process.stdout.close()
    process.stderr.close()
    return code


def model_tests(root):
    store = recovery.RecoveryStore(root)
    origin = root / "original-project.json"
    origin.write_bytes(b"original project bytes\r\n")
    original = origin.read_bytes()
    original_sha = hashlib.sha256(original).hexdigest()
    first, second = store.open_session(), store.open_session()
    try:
        receipt = first.publish(payload(), 1, origin_path=str(origin), origin_sha256=original_sha)
        second.publish(payload("other live window"), 0)
        assert not store.discover(), "Another window in this same process can see a live copy"
        rejected(lambda: store._lease(first.session_id), "active")
        initial = first.path.read_bytes()
        retry = first.publish(payload(), 1, origin_path=str(origin), origin_sha256=original_sha)
        assert retry.raw_sha256 == receipt.raw_sha256 and first.path.read_bytes() == initial
        rejected(lambda: first.publish(payload("conflicting same revision"), 1), "different payloads")
        assert first.path.read_bytes() == initial
        with patch.object(recovery.os, "replace", side_effect=OSError("injected replace failure")):
            rejected(lambda: first.publish(payload("failed new"), 2), "injected")
        assert first.path.read_bytes() == initial
        assert not list(root.glob("*.tmp")) and not list(root.glob(".*.tmp"))
        rejected(lambda: first.publish(payload(), 0), "backwards")
        rejected(lambda: first.publish(payload(), True), "backwards")
        assert origin.read_bytes() == original
        first.close()
        candidates = store.discover()
        assert len(candidates) == 1 and candidates[0].raw_sha256 == receipt.raw_sha256
        candidate = candidates[0]
        with store.claim(candidate) as claim:
            assert claim.read().payload == payload()
            assert claim.read().origin_sha256 == original_sha
            assert not store.discover(), "A claimed copy was offered concurrently"
            rejected(lambda: store._lease(candidate.session_id), "active")
            claim.retain()
        changed = store.discover()[0]
        assert changed.disposition == "retained"
        assert changed.raw_sha256 != candidate.raw_sha256
        with store.claim(changed) as claim:
            claim.discard()
        rejected(claim.read, "closed")
        assert not store.discover()
        assert origin.read_bytes() == original

        # An original changed or deleted externally is context, never a target
        # required for loading drafts or a file the recovery service rewrites.
        third = store.open_session()
        third.publish(payload(), 0, origin_path=str(origin), origin_sha256=original_sha)
        origin.write_bytes(b"external change")
        third.close()
        candidate = store.discover()[0]
        with store.claim(candidate) as claim:
            assert claim.read().origin_sha256 == original_sha
            assert origin.read_bytes() == b"external change"
            assert recovery.origin_status(claim.read()) == "changed"
        origin.unlink()
        with store.claim(candidate) as claim:
            assert claim.read().payload == payload()
            assert recovery.origin_status(claim.read()) == "missing"
            claim.discard()
        assert not origin.exists()

        # False/0/empty remain JSON types; envelope or project schema violations
        # fail closed while preserving other valid candidates.
        session = store.open_session()
        session.publish(payload(), 0)
        raw = session.path.read_bytes()
        data = json.loads(raw)
        session.close()
        invalid = []
        for key, value in (("schema", "future"), ("revision", True), ("payload_sha256", "0" * 64),
                           ("origin_path", False), ("saved_digest", "bad")):
            value_data = copy.deepcopy(data)
            value_data[key] = value
            invalid.append(json.dumps(value_data).encode())
        unknown = copy.deepcopy(data); unknown["unknown"] = 1
        invalid.append(json.dumps(unknown).encode())
        missing = copy.deepcopy(data); missing.pop("payload")
        invalid.append(json.dumps(missing).encode())
        future_project = copy.deepcopy(data); future_project["payload"]["version"] = 999
        invalid.append(json.dumps(future_project).encode())
        incomplete_project = copy.deepcopy(data); incomplete_project["payload"].pop("sourceEditor")
        invalid.append(json.dumps(incomplete_project).encode())
        missing_state = copy.deepcopy(data); missing_state["payload"]["editingState"] = None
        invalid.append(json.dumps(missing_state).encode())
        invalid.extend((b"", b"{", raw.replace(b'"revision":0', b'"revision":0,"revision":1'),
                        raw.replace(b'"revision":0', b'"revision":NaN')))
        for raw_bad in invalid:
            session.path.write_bytes(raw_bad)
            candidate = store.discover()[0]
            assert candidate.error, raw_bad[:80]
            with store.claim(candidate) as claim:
                rejected(claim.read)
                claim.retain()
            assert session.path.read_bytes() == raw_bad
        session.path.write_bytes(raw)
        stale = store.discover()[0]
        session.path.write_bytes(raw + b" ")
        rejected(lambda: enter_claim(store, stale), "changed")
        with store.claim(store.discover()[0]) as claim:
            claim.discard()

        # Cleanup failure after retirement is a warning, not an active crash copy.
        session = store.open_session()
        session.publish(payload(), 0)
        real_unlink = Path.unlink
        def fail_target(path, *args, **kwargs):
            if path == session.path:
                raise OSError("retirement cleanup blocked")
            return real_unlink(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_target):
            assert session.retire("saved").cleanup_warning
        session.close()
        assert not store.discover()
        assert json.loads(session.path.read_bytes())["disposition"] == "saved"
        # Retired revisions cannot be resurrected, while genuinely new edits
        # in the same still-owned session continue to work normally.
        fresh = store.open_session()
        fresh.publish(payload(), 4)
        fresh.retire("saved")
        rejected(lambda: fresh.publish(payload(), 4), "Retired")
        rejected(lambda: fresh.publish(payload("late old bytes"), 4), "Retired")
        assert not fresh.path.exists()
        fresh.publish(payload("new revision after save"), 5)
        assert json.loads(fresh.path.read_bytes())["revision"] == 5
        fresh.retire("discarded")
        fresh.close()
    finally:
        first.close()
        second.retire("discarded")
        second.close()


def enter_claim(store, candidate):
    with store.claim(candidate):
        pass


def process_tests(root):
    facts = []
    for mode in ("active", "atomic_before", "atomic_after"):
        store = recovery.RecoveryStore(root / mode)
        process, ready = start_child(store.root, mode)
        assert not store.discover(), "Live child lease was ignored"
        code = kill_owned(process)
        candidates = store.discover()
        assert len(candidates) == 1 and not candidates[0].error, (mode, candidates, list(store.root.iterdir()))
        with store.claim(candidates[0]) as claim:
            record = claim.read()
            expected = 2 if mode == "atomic_after" else 1
            assert record.revision == expected
            assert record.payload["projectName"] == (
                "second actual generation" if expected == 2 else "未命名草稿")
            if mode == "atomic_before":
                assert candidates[0].raw_sha256 == ready["previous"]
                assert Path(ready["temporary"]).exists()
            facts.append({"mode": mode, "exit_code": code, "recovered_revision": expected,
                          "raw_sha256": candidates[0].raw_sha256})
            claim.discard()
    store = recovery.RecoveryStore(root / "multiple")
    left, left_info = start_child(store.root)
    right, right_info = start_child(store.root)
    try:
        assert left_info["id"] != right_info["id"] and not store.discover()
        kill_owned(left)
        candidates = store.discover()
        assert len(candidates) == 1 and candidates[0].session_id == left_info["id"]
        right.stdin.write("edit\n"); right.stdin.flush()
        assert read_line(right)["revision"] == 2
        assert len(store.discover()) == 1
        right.stdin.write("close\n"); right.stdin.flush()
        assert right.wait(timeout=10) == 0
        assert len(store.discover()) == 1
    finally:
        for process in (left, right):
            if process.poll() is None:
                kill_owned(process)
            else:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if not stream.closed:
                        stream.close()
    for mode in ("normal", "retained"):
        store = recovery.RecoveryStore(root / mode)
        process, ready = start_child(store.root, mode)
        assert ready[mode] and process.wait(timeout=10) == 0
        assert len(store.discover()) == (1 if mode == "retained" else 0)
        if mode == "retained":
            assert store.discover()[0].disposition == "retained"
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
    return facts


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2], Path(sys.argv[3])); return
    with tempfile.TemporaryDirectory(prefix="f5-recovery-") as temporary:
        work = Path(temporary)
        model_tests(work / "model")
        facts = process_tests(work / "process")
        print(json.dumps({"real_process_death_experiments": facts}, ensure_ascii=False))
    print("F5 recovery persistence and real process isolation: passed")


if __name__ == "__main__":
    main()
