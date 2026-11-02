"""Pure stdlib journal smoke: real files/processes, no Qt or simulation."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.agent import session as sj


IDENTITY = dict(snapshot_fingerprint="a" * 64, revision=7, session_id="editor-session")
AUTH = dict(allowed_actions=["plan", "apply", "validate", "initialize", "generate", "run",
                             "evaluate", "export"], max_calls=8, max_events=100, timeout_seconds=60)
_CREATED = []


def create(root, **kwargs):
    journal = sj.TaskJournal.create(root, "bounded task", kwargs.pop("authorization", deepcopy(AUTH)),
                                    deepcopy(IDENTITY), **kwargs)
    _CREATED.append(journal)
    return journal


def refused(call, error=sj.JournalError, code=None):
    try:
        call()
    except error as exc:
        assert code is None or str(exc) == code, (str(exc), code)
    else:
        assert False, "Invalid journal action was accepted"


def test_lifecycle(root):
    auth = deepcopy(AUTH)
    j = create(root, authorization=auth)
    auth["allowed_actions"].clear()
    assert j.state == "planned" and j.path.is_file()
    assert j.to_dict()["authorization"]["allowed_actions"]
    detached = j.to_dict()
    detached["prompt"] = "different"
    assert j.to_dict()["prompt"] == "bounded task"
    j.set_plan(dict(schema="g4usim_config_agent_plan_v1", changes=[]))
    j.transition("awaiting_approval")
    oid = j.record_intent("apply", dict(revision=7, snapshot_fingerprint="a" * 64))
    disk = sj.TaskJournal.load(j.path).to_dict()
    assert disk["operations"][0]["operation_id"] == oid  # Durable before caller can execute.
    assert disk["state"] == "applying" and disk["operations"][0]["result"] is None
    j.record_binding(oid, dict(record_id="record-1", run_id="run-1"))
    original = j.path.read_bytes()
    j.bind_operation(oid, dict(record_id="record-1", run_id="run-1"))
    assert j.path.read_bytes() == original
    refused(lambda: j.record_binding(oid, dict(record_id="different")), code="agent.journal.binding_conflict")
    refused(lambda: j.record_binding(oid, dict(action="run")), code="agent.journal.binding_action")
    assert j.path.read_bytes() == original
    result = dict(status="completed", record_id="record-1", run_id="run-1", revision=8, stale=False)
    j.record_result(oid, result)
    assert j.to_dict()["operations"][0]["binding"]["revision"] == 7
    assert j.to_dict()["operations"][0]["result"]["revision"] == 8
    raw = j.path.read_bytes()
    with patch.object(sj.os, "replace", side_effect=AssertionError("idempotence wrote again")):
        j.record_result(oid, result)
    assert j.path.read_bytes() == raw
    refused(lambda: j.record_result(oid, dict(status="failed")), code="agent.journal.result_conflict")
    refused(lambda: j.record_binding(oid, dict(events=1)), code="agent.journal.unreserved_events")
    j.transition("completed")
    refused(lambda: j.transition("running"), code="agent.journal.terminal")
    refused(lambda: j.record_intent("run", dict(events=1)), code="agent.journal.terminal")
    j.cancel()
    assert j.state == "completed"
    assert sj.TaskJournal.load(j.path).state == "completed"


def test_cancel_and_binding(root):
    j = create(root)
    oid = j.record_intent("run", dict(events=3))
    refused(lambda: j.record_intent("validate", {}), code="agent.journal.in_flight")
    refused(lambda: j.transition("completed"), code="agent.journal.in_flight")
    j.cancel()
    raw = j.path.read_bytes()
    j.cancel()
    assert raw == j.path.read_bytes()
    j.record_binding(oid, dict(run_id="late-run", record_id="late-record"))
    j.record_result(oid, dict(status="failed", reason="raw-first-backend-error", events=3,
                              run_id="late-run", record_id="late-record"))
    assert j.state == "cancelled"
    assert j.to_dict()["first_failure"]["reason"] == "agent.task.cancelled"
    refused(lambda: j.transition("completed"), code="agent.journal.terminal")
    failed = create(root)
    op = failed.record_intent("validate", {})
    failed.record_result(op, dict(status="failed", reason="original diagnosis"))
    failed.transition("failed", reason="later generic error")
    assert failed.to_dict()["first_failure"]["reason"] == "original diagnosis"
    assert failed.to_dict()["reason"] == "later generic error"
    refused(lambda: failed.record_result("0" * 32, dict(status="completed")),
            code="agent.journal.unknown_operation")
    partial = create(root)
    op = partial.record_intent("run", dict(events=100, revision=7))
    partial.record_result(op, dict(status="failed", events=22, revision=8))
    assert partial.to_dict()["usage"]["events"] == 100
    assert partial.to_dict()["operations"][0]["result"]["events"] == 22
    assert sj.TaskJournal.load(partial.path).to_dict() == partial.to_dict()
    over = create(root)
    op = over.record_intent("run", dict(events=1))
    refused(lambda: over.record_result(op, dict(status="completed", events=2)),
            code="agent.journal.unreserved_events")
    assert over.to_dict()["operations"][0]["result"] is None


def test_budgets(root):
    j = create(root, authorization=dict(AUTH, max_calls=1))
    oid = j.record_intent("validate", {})
    j.record_result(oid, dict(status="passed"))
    refused(lambda: j.record_intent("validate", {}), sj.JournalLimitError, "agent.limit.calls")
    assert j.state == "failed" and j.to_dict()["usage"]["calls"] == 1
    j = create(root, authorization=dict(AUTH, max_events=2))
    refused(lambda: j.record_intent("run", dict(events=3)), sj.JournalLimitError, "agent.limit.events")
    assert j.state == "failed" and j.to_dict()["usage"] == dict(calls=0, events=0)
    assert not j.to_dict()["operations"]
    j = create(root)
    refused(lambda: j.record_intent("run", {}), code="agent.journal.integer")
    refused(lambda: j.record_intent("run", dict(events=True)), code="agent.journal.integer")
    oid = j.record_intent("generate", {})
    refused(lambda: j.record_binding(oid, dict(events=1)), code="agent.journal.unreserved_events")
    j = create(root, limits=dict(max_records=8, max_bytes=sj.MAX_BYTES))
    for index in range(6):
        j.set_plan(dict(iteration=index))
    refused(lambda: j.set_plan(dict(iteration=7)), sj.JournalLimitError, "agent.limit.records")
    assert j.state == "failed" and len(j.to_dict()["records"]) == 8
    assert sj.TaskJournal.load(j.path).state == "failed"
    j = create(root, limits=dict(max_records=8, max_bytes=4096))
    refused(lambda: j.set_plan(dict(notes="x" * 3500)), sj.JournalLimitError, "agent.limit.bytes")
    assert j.state == "failed" and j.to_dict()["plan"] is None
    assert j.path.stat().st_size <= 4096
    j = create(root, authorization=dict(AUTH, timeout_seconds=.01))
    time.sleep(.02)
    refused(lambda: j.record_intent("validate", {}), sj.JournalLimitError, "agent.limit.time")
    assert j.state == "failed" and not j.to_dict()["operations"]
    j = create(root, authorization=dict(AUTH, timeout_seconds=1))
    with patch.object(sj.time, "time", return_value=j.to_dict()["created_at"] - 1000), \
            patch.object(sj.time, "monotonic", return_value=j._start + 2):
        refused(lambda: j.record_intent("validate", {}), sj.JournalLimitError, "agent.limit.time")
    assert j.state == "failed"
    j = create(root, authorization=dict(AUTH, timeout_seconds=1))
    oid = j.record_intent("validate", {})
    with patch.object(sj.time, "monotonic", return_value=j._start + 2):
        j.record_result(oid, dict(status="passed"))  # Preserve late observations.
        refused(lambda: j.transition("completed"), sj.JournalLimitError, "agent.limit.time")
    assert j.state == "failed" and j.to_dict()["operations"][0]["result"]["status"] == "passed"
    for auth in (dict(AUTH, max_calls=33), dict(AUTH, max_calls=True), dict(AUTH, max_events=100001),
                 dict(AUTH, timeout_seconds=float("inf")), dict(AUTH, timeout_seconds=3601),
                 dict(AUTH, timeout_seconds=10**1000),
                 dict(AUTH, allowed_actions=["shell"]), dict(AUTH, extra=1)):
        refused(lambda auth=auth: create(root, authorization=auth))


def test_inputs_and_corruption(root):
    j = create(root, authorization=dict(AUTH, allowed_actions=["validate"]))
    original = j.path.read_bytes()
    refused(lambda: j.record_intent("export", {}), code="agent.journal.unauthorized")
    for value in (dict(api_key="synthetic"), dict(nested=dict(secret_key="synthetic")),
                  dict(provider={}), dict(key="synthetic"), dict(x=float("nan")), dict(x=object())):
        refused(lambda value=value: j.set_plan(value))
    refused(lambda: j.set_plan([]), code="agent.journal.plan")
    assert j.path.read_bytes() == original
    payload = j.to_dict()
    examples = []
    def malformed(label, change):
        data = deepcopy(payload)
        change(data)
        examples.append((label, sj._encode(data)))
    malformed("unknown payload", lambda d: d.update(unknown=True))
    malformed("unknown authorization", lambda d: d["authorization"].update(api_key="synthetic"))
    malformed("secret plan", lambda d: d.update(plan=dict(secret_key="synthetic")))
    malformed("bad state", lambda d: d.update(state="trusted"))
    malformed("bad sequence", lambda d: d["records"][0].update(sequence=True))
    malformed("bad counter", lambda d: d["usage"].update(calls=1))
    malformed("unknown identity", lambda d: d["project_identity"].update(approved=True))
    env = json.loads(original)
    examples.extend([
        ("unknown envelope", json.dumps(dict(env, extra=True)).encode()),
        ("future version", json.dumps(dict(env, version=2)).encode()),
        ("bool version", json.dumps(dict(env, version=True)).encode()),
        ("checksum", json.dumps(dict(env, checksum="0" * 64)).encode()),
        ("duplicate key", original.replace(b'"state":"planned"', b'"state":"planned","state":"planned"')),
        ("nonfinite", original.replace(b'"revision":7', b'"revision":NaN')),
        ("truncated", original[:-4]), ("invalid UTF8", b"\xff"),
        ("oversize", b"x" * (sj.MAX_BYTES + 1)),
    ])
    for index, (label, raw) in enumerate(examples):
        target = root / ("corrupt-" + str(index) + ".json")
        target.write_bytes(raw)
        refused(lambda target=target: sj.TaskJournal.load(target))
        assert target.read_bytes() == raw, label
    # Recomputed checksum is NOT a signature: even internally valid edited auth
    # cannot turn load() into a live execution grant.
    data = deepcopy(payload)
    data["authorization"]["allowed_actions"] = ["run"]
    forged = root / "recomputed-checksum.json"
    forged.write_bytes(sj._encode(data))
    restored = sj.TaskJournal.load(forged)
    refused(lambda: restored.record_intent("run", dict(events=1)), code="agent.journal.recovered_query_only")
    assert not restored.to_dict()["operations"]


def test_file_faults(root):
    for fault in ("fdopen", "write", "flush", "fsync", "replace"):
        j = create(root)
        before, state = j.path.read_bytes(), j.to_dict()
        real_fdopen = sj.os.fdopen
        def faulty_open(fd, mode):
            stream = real_fdopen(fd, mode)
            class FaultStream:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return stream.__exit__(*args)
                def write(self, value):
                    if fault == "write":
                        raise OSError("synthetic atomic IO refusal")
                    return stream.write(value)
                def flush(self):
                    if fault == "flush":
                        raise OSError("synthetic atomic IO refusal")
                    return stream.flush()
                def fileno(self):
                    return stream.fileno()
            return FaultStream()
        manager = (patch.object(sj.os, "fdopen", faulty_open) if fault in ("write", "flush") else
                   patch.object(sj.os, fault, side_effect=OSError("synthetic atomic IO refusal")))
        executed = []
        with manager:
            try:
                oid = j.record_intent("validate", {})
                executed.append(oid)  # unreachable unless durable intent returned
            except sj.JournalIOError:
                pass
        assert executed == [], fault
        assert j.path.read_bytes() == before and j.to_dict() == state, fault
        assert not list(j.path.parent.glob(".journal-*.tmp")), fault
        assert sj.TaskJournal.load(j.path).to_dict() == state
    # Real destination-type failure; preserve the original file as an explicit
    # untouched fixture instead of treating a directory as a journal.
    j = create(root)
    before = j.path.read_bytes()
    backup = j.path.with_name("original-preserved.json")
    j.path.rename(backup)
    j.path.mkdir()
    refused(lambda: j.record_intent("validate", {}), code="agent.journal.regular_file")
    assert backup.read_bytes() == before and j.path.is_dir()
    j = create(root)
    real_sync = sj.os.fsync
    changed = j.to_dict()
    changed["prompt"] = "externally edited"
    changed_raw = sj._encode(changed)
    def edit_during_sync(fd):
        real_sync(fd)
        j.path.write_bytes(changed_raw)
    with patch.object(sj.os, "fsync", edit_during_sync):
        refused(lambda: j.record_intent("validate", {}), sj.JournalConflict, "agent.journal.changed")
    assert j.path.read_bytes() == changed_raw
    assert not j.to_dict()["operations"]


def test_recovery_and_concurrency(root):
    j = create(root)
    stale = sj.TaskJournal.load(j.path)
    oid = j.record_intent("validate", dict(record_id="known"))
    refused(stale.cancel, sj.JournalIOError, "agent.journal.storage_failed")
    j.record_result(oid, dict(status="passed", record_id="known"))
    refused(lambda: j.record_intent("validate", dict(record_id="known")), code="agent.journal.duplicate_binding")
    j.transition("failed", reason="owner finished")
    refused(stale.cancel, sj.JournalConflict, "agent.journal.changed")
    j = create(root)
    barrier = threading.Barrier(2)
    results = []
    def contender(index):
        barrier.wait()
        try:
            results.append(j.record_intent("validate", dict(revision=index)))
        except sj.JournalError:
            results.append(None)
    threads = [threading.Thread(target=contender, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
        assert not t.is_alive()
    assert sum(x is not None for x in results) == 1
    assert len(j.to_dict()["operations"]) == 1
    # The actual OS lease also excludes a distinct Python process.
    child = subprocess.run([sys.executable, "-B", __file__, "--lease-contender", str(j.path)],
                           capture_output=True, text=True, timeout=15)
    assert child.returncode == 0 and child.stdout.strip() == "lease_busy", child.stderr
    # Exit without finally/normal caller completion after intent+binding persisted.
    child = subprocess.run([sys.executable, "-B", __file__, "--crash-intent", str(root)],
                           capture_output=True, text=True, timeout=15)
    assert child.returncode == 0, child.stderr
    info = json.loads(child.stdout)
    recovered = sj.TaskJournal.load(info["path"])
    original = recovered.path.read_bytes()
    policy = recovered.resume_policy()
    assert policy["mode"] == "query_only" and policy["can_replay"] is False
    assert policy["requires_new_user_request"] and policy["requires_live_identity_check"]
    assert policy["suggested_state"] == "interrupted" and policy["persisted_state"] == "running"
    assert policy["in_flight"][0]["binding"]["record_id"] == "crash-record"
    assert policy["in_flight"][0]["binding"]["run_id"] == "crash-run"
    assert recovered.path.read_bytes() == original  # load does not rewrite history
    refused(lambda: recovered.record_intent("run", dict(events=4)), code="agent.journal.recovered_query_only")
    refused(lambda: recovered.transition("running", "retry"))
    refused(lambda: recovered.set_plan({}), code="agent.journal.recovered_query_only")
    recovered.record_result(info["operation_id"], dict(status="unknown", record_id="crash-record", run_id="crash-run"))
    recovered.transition("interrupted", reason="agent.recovery.query_only")
    assert recovered.state == "interrupted"
    assert len(recovered.to_dict()["operations"]) == 1
    fresh = create(root)
    assert fresh.task_id != recovered.task_id
    assert fresh.resume_policy()["mode"] == "new_task_required"
    raw = fresh.path.read_bytes()
    fresh.close()
    with patch.object(sj.os, "close", side_effect=AssertionError("close was not idempotent")):
        fresh.close()
    assert fresh.path.read_bytes() == raw
    refused(lambda: fresh.record_intent("validate", {}), code="agent.journal.closed")


def test_link_paths(root):
    j = create(root)
    original = j.path.read_bytes()
    alias = root / "alias"
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(j.path.parent), str(alias))
    else:
        alias.symlink_to(j.path.parent, target_is_directory=True)
    refused(lambda: sj.TaskJournal.load(alias / "journal.json"), code="agent.journal.link_path")
    refused(lambda: create(alias), code="agent.journal.link_path")
    refused(lambda: sj.TaskJournal.load(alias / ".." / "journal.json"), code="agent.journal.path")
    refused(lambda: sj.TaskJournal.load("bad\0path"), code="agent.journal.path")
    assert j.path.read_bytes() == original
    hard = root / "hard-journal.json"
    os.link(j.path, hard)
    refused(lambda: sj.TaskJournal.load(hard), code="agent.journal.regular_file")
    refused(lambda: j.record_intent("validate", {}), code="agent.journal.regular_file")
    assert hard.read_bytes() == original and j.path.read_bytes() == original


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--lease-contender":
        try:
            sj.TaskJournal.load(sys.argv[2]).cancel()
        except sj.JournalIOError:
            print("lease_busy", flush=True)
            return 0
        return 3
    if len(sys.argv) == 3 and sys.argv[1] == "--crash-intent":
        j = create(Path(sys.argv[2]))
        oid = j.record_intent("run", dict(events=4))
        j.record_binding(oid, dict(record_id="crash-record", run_id="crash-run"))
        print(json.dumps(dict(path=str(j.path), operation_id=oid)), flush=True)
        os._exit(0)
    groups = [test_lifecycle, test_cancel_and_binding, test_budgets, test_inputs_and_corruption,
              test_file_faults, test_recovery_and_concurrency, test_link_paths]
    for test in groups:
        with tempfile.TemporaryDirectory(prefix="g4usim-agent-session-") as directory:
            try:
                test(Path(directory))
            finally:
                for journal in _CREATED:
                    journal.close()
                _CREATED.clear()
        print("PASS " + test.__name__, flush=True)
    assert not any(name.startswith(("PySide6", "PyQt")) for name in sys.modules)
    print("agent_session: 7 pure-file groups passed; no Qt/backend execution", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
