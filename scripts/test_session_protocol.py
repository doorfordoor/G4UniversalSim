"""Exercise the versioned JSON-lines session protocol against the real backend.

The controlled session is a transport-level contract: frames arrive on stdin,
every response carries the request identity, and terminal errors must fail the
process without pretending a run happened.  These assertions only use the
public protocol surface plus the produced record files; they do not inspect
Geant4 internals behind the backend's own receipts.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
PROTOCOL = "g4usim-session-v1"


def hexadecimal(counter: list[int], width: int = 12) -> str:
    counter[0] += 1
    return f"{counter[0]:0{width}x}"


class Session:
    """Line-oriented client: every JSON frame is matched by predicate."""

    def __init__(self, executable: Path, output_dir: Path, record_dir: Path,
                 threads: int = 1, extra_args: list[str] | None = None,
                 config: Path | None = None) -> None:
        self.executable = executable
        self.output_dir = output_dir
        self.record_dir = record_dir
        environment = os.environ.copy()
        environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
        record_dir.parent.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            [
                str(executable),
                "--config", str(config if config is not None else ROOT / "config" / "main.ini"),
                "--session-server",
                "--output", str(output_dir),
                "--session-record-dir", str(record_dir),
                "--threads", str(threads),
                *(extra_args or []),
            ],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=environment,
        )
        assert self.process.stdin is not None and self.process.stdout is not None
        self.frames: list[dict[str, object]] = []
        self.raw_lines: list[str] = []
        self.condition = threading.Condition()
        self.closed = False
        self.counter = [0]
        self.seq = 0
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            text = line.rstrip("\n")
            with self.condition:
                self.raw_lines.append(text)
                try:
                    frame = json.loads(text)
                except (ValueError, TypeError):
                    frame = None
                if isinstance(frame, dict):
                    self.frames.append(frame)
                self.condition.notify_all()
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def send(self, frame: dict[str, object]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(frame, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def request(self, op: str, params: dict[str, object] | None = None,
                revision: int | None = None, *, wait: bool = True) -> dict[str, object]:
        self.seq += 1
        frame: dict[str, object] = {
            "kind": "request",
            "seq": self.seq,
            "id": hexadecimal(self.counter),
            "request_id": hexadecimal(self.counter),
            "op": op,
        }
        if params is not None:
            frame["params"] = params
        if revision is not None:
            frame["state_revision"] = revision
        self.send(frame)
        if not wait:
            return frame
        response = self.wait(lambda item: item.get("kind") == "response" and
                             item.get("id") == frame["id"])
        return response

    def wait(self, predicate, timeout: float = 300.0) -> dict[str, object]:
        deadline = time.time() + timeout
        with self.condition:
            while True:
                for frame in self.frames:
                    if predicate(frame):
                        return frame
                remaining = deadline - time.time()
                assert remaining > 0, f"timed out; tail={self.raw_lines[-12:]}"
                self.condition.wait(min(remaining, 1.0))

    def wait_event(self, event: str, timeout: float = 300.0) -> dict[str, object]:
        return self.wait(lambda item: item.get("kind") == "event" and
                         item.get("event") == event, timeout)

    def state(self) -> dict[str, object]:
        response = self.request("get_state")
        assert response["status"] == "ok", response
        state = response["state"]
        assert isinstance(state, dict)
        return state

    def close(self, expect_exit: int | None = None, timeout: float = 180.0) -> int:
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        try:
            code = self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=30)
            raise AssertionError(f"session did not exit; tail={self.raw_lines[-20:]}")
        if expect_exit is not None:
            assert code == expect_exit, (code, self.raw_lines[-20:])
        return code


def eof_case(executable: Path, temp: Path) -> None:
    output = temp / "eof-out"
    records = temp / "eof-records"
    environment = os.environ.copy()
    environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    process = subprocess.Popen(
        [str(executable), "--config", str(ROOT / "config" / "main.ini"),
         "--session-server", "--output", str(output),
         "--session-record-dir", str(records)],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        errors="replace", bufsize=1, env=environment)
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps({"kind": "hello", "protocol": PROTOCOL}) + "\n")
    process.stdin.flush()
    frames = []

    def read_until(predicate, timeout=180.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            try:
                frame = json.loads(line)
            except ValueError:
                continue
            frames.append(frame)
            if predicate(frame):
                return frame
        raise AssertionError(f"frame not observed; tail={frames[-8:]}")

    welcome = read_until(lambda item: item.get("kind") == "welcome")
    session_dir = Path(welcome["state"]["session_root"])
    assert Path(welcome["state"]["record_root"]) == records
    assert session_dir.parent == records and session_dir.name.startswith("session-")
    process.stdin.close()
    code = process.wait(timeout=180)
    assert code == 0, (code, frames[-8:])
    rest = process.stdout.read()
    for line in rest.splitlines():
        try:
            frame = json.loads(line)
        except ValueError:
            continue
        if isinstance(frame, dict):
            frames.append(frame)
    log = (session_dir / "session.jsonl").read_text(encoding="utf-8").splitlines()
    meta = [json.loads(line) for line in log if '"direction":"meta"' in line]
    assert any(entry.get("event") == "eof_close" for entry in meta), meta[-3:]
    assert any(entry.get("exit_code") == 0 for entry in meta), meta[-3:]


def _record_entries(session_dir: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for line in (session_dir / "session.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def fatal_during_run_cases(executable: Path, temp: Path) -> None:
    """Corrupt/overlong frames during a run must fail the session, not exit 0 via EOF."""

    def expect_failed_round(session: "Session", label: str, code: int,
                            session_dir: Path) -> None:
        assert code == 3, (label, code, session.frames[-12:])
        errors = [item for item in session.frames if item.get("kind") == "error"]
        assert any(item.get("code") == "protocol_error" for item in errors), (label, errors[-4:])
        started = [item for item in session.frames
                   if item.get("kind") == "event" and item.get("event") == "run_started"]
        finished = [item for item in session.frames
                    if item.get("kind") == "event" and item.get("event") == "run_finished"]
        assert len(started) == 1, (label, len(started))
        assert len(finished) == 1, (label, len(finished))
        record = finished[0]
        assert record["status"] in {"cancelled", "aborted", "failed"}, (label, record)
        completed = record["completed_events"]
        planned = record["planned_events"]
        assert isinstance(completed, int) and isinstance(planned, int), (label, record)
        assert 0 <= completed < planned, (label, completed, planned)
        meta = [entry for entry in _record_entries(session_dir)
                if entry.get("direction") == "meta"
                and entry.get("event") in {"session_end", "eof_close"}]
        assert meta and meta[-1]["exit_code"] == 3, (label, meta[-3:])
        inputs = [entry.get("text") for entry in _record_entries(session_dir)
                  if entry.get("direction") == "c2s" and isinstance(entry.get("text"), str)]
        assert inputs, (label, "no raw client input recorded")

    # -- corrupt frame followed by EOF while a two-worker run is active
    output = temp / "fatal-corrupt-out"
    records = temp / "fatal-corrupt-records"
    session = Session(executable, output, records, threads=2)
    open_session(session)
    session_dir = Path(session.state()["session_root"])
    session.request("run", {"events": 200000}, session.state()["state_revision"], wait=False)
    session.wait_event("run_started", timeout=300)
    assert session.process.stdin is not None
    session.process.stdin.write('{"kind":' + chr(10))
    session.process.stdin.flush()
    session.process.stdin.close()
    try:
        code = session.process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        session.process.kill()
        session.process.wait(timeout=30)
        raise AssertionError("backend did not exit after a corrupt frame and EOF")
    expect_failed_round(session, "corrupt_frame_eof", code, session_dir)
    raw = [entry.get("text", "") for entry in _record_entries(session_dir)
           if entry.get("direction") == "c2s"]
    assert any('{"kind":' in text for text in raw), raw[:6]

    # -- overlong frame with a newline while the run is active and stdin stays open
    output = temp / "fatal-overlong-out"
    records = temp / "fatal-overlong-records"
    session = Session(executable, output, records, threads=2)
    open_session(session)
    session_dir = Path(session.state()["session_root"])
    session.request("run", {"events": 200000}, session.state()["state_revision"], wait=False)
    session.wait_event("run_started", timeout=300)
    assert session.process.stdin is not None
    session.process.stdin.write("x" * 70000 + chr(10))
    session.process.stdin.flush()
    try:
        code = session.process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        session.process.kill()
        session.process.wait(timeout=30)
        raise AssertionError("backend did not exit after an overlong frame")
    expect_failed_round(session, "overlong_frame", code, session_dir)
    errors = [item for item in session.frames if item.get("kind") == "error"]
    assert any("frame_too_large" in str(item.get("message", "")) for item in errors), errors[-4:]

    # -- short fragment without a newline followed by EOF (no run active)
    output = temp / "fatal-fragment-out"
    records = temp / "fatal-fragment-records"
    session = Session(executable, output, records)
    session.send({"kind": "hello", "protocol": PROTOCOL})
    welcome = session.wait(lambda item: item.get("kind") == "welcome", timeout=180.0)
    fragment_dir = Path(welcome["state"]["session_root"])
    assert session.process.stdin is not None
    session.process.stdin.write('{"kind":')
    session.process.stdin.flush()
    session.process.stdin.close()
    code = session.close(expect_exit=None)
    assert code == 3, (code, session.frames[-8:])
    fragment_errors = [item for item in session.frames if item.get("kind") == "error"]
    assert any(item.get("code") == "protocol_error" for item in fragment_errors), session.frames[-8:]
    assert not [item for item in session.frames
                if item.get("kind") == "event" and item.get("event") == "run_started"], session.frames[-8:]
    fragment_meta = [entry for entry in _record_entries(fragment_dir)
                     if entry.get("direction") == "meta"
                     and entry.get("event") in {"session_end", "eof_close"}]
    assert fragment_meta and fragment_meta[-1]["exit_code"] == 3, fragment_meta[-3:]


def write_refusal_case(executable: Path, temp: Path, name: str,
                       lines: list[str], expected_code: str) -> None:
    output = temp / f"refusal-{name}-out"
    records = temp / f"refusal-{name}-records"
    environment = os.environ.copy()
    environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    completed = subprocess.run(
        [
            str(executable),
            "--config", str(ROOT / "config" / "main.ini"),
            "--session-server",
            "--output", str(output),
            "--session-record-dir", str(records),
        ],
        cwd=ROOT,
        input="".join(line + "\n" for line in lines),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        env=environment,
        check=False,
    )
    assert completed.returncode != 0, (name, completed.returncode, completed.stdout[-2000:])
    frames = []
    for line in completed.stdout.splitlines():
        try:
            frame = json.loads(line)
        except ValueError:
            continue
        if isinstance(frame, dict):
            frames.append(frame)
    errors = [item for item in frames if item.get("kind") == "error"]
    assert errors, (name, completed.stdout[-2000:])
    assert errors[0]["code"] == expected_code, (name, errors[0])
    assert "terminate" not in completed.stdout.lower(), completed.stdout[-2000:]


def write_cli_refusal(executable: Path, temp: Path, name: str, extra: list[str],
                      expected: str) -> None:
    output = temp / f"cli-{name}-out"
    records = temp / f"cli-{name}-records"
    base = [str(executable), "--config", str(ROOT / "config" / "main.ini"),
            "--session-server", "--output", str(output)]
    if name == "missing_records":
        pass
    elif name == "records_inside_output":
        base.extend(["--session-record-dir", str(output)])
    else:
        base.extend(["--session-record-dir", str(records)])
    completed = subprocess.run(base + extra, cwd=ROOT, input="", capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=120, check=False)
    assert completed.returncode != 0, (name, completed.returncode)
    log = completed.stdout + completed.stderr
    assert expected in log, (name, log[-2000:])


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-session-",
                                          ignore_cleanup_errors=True) as directory:
        temp = Path(directory)
        output = temp / "out"
        records = temp / "records"
        session = Session(executable, output, records)

        # ---------------------------------------------------------- handshake
        handshake = {"kind": "hello", "protocol": PROTOCOL,
                     "client": {"name": "test_session_protocol", "version": "1"},
                     "labels": {"描述": "会话测试", "说明": "JSON 帧含中文与 emoji 😀",
                                "矩阵": [[1.5, 2.0], [3, {"嵌套": "值"}]]}}
        session.send(handshake)
        welcome = session.wait(lambda item: item.get("kind") == "welcome")
        assert welcome["protocol"] == PROTOCOL, welcome
        backend = welcome["backend"]
        assert isinstance(backend, dict)
        assert isinstance(backend["source_fingerprint"], str) and backend["source_fingerprint"]
        assert isinstance(backend["build_git_commit"], str) and backend["build_git_commit"]
        limits = welcome["limits"]
        assert limits["max_frame_bytes"] > 0 and limits["max_events_per_run"] > 0, limits
        assert welcome["session_id"], welcome
        revision = welcome["state"]["state_revision"]
        assert revision == 0, welcome["state"]

        # Request before hello is only rejected in a separate process; here the
        # handshake is already complete.
        state = session.state()
        assert state["phase"] == "idle" and state["kernel_state"] == "pre_init", state
        assert Path(state["output_root"]) == output, state["output_root"]
        assert Path(state["record_root"]) == records, state["record_root"]
        session_dir = Path(state["session_root"])
        assert session_dir.parent == records, state["session_root"]
        assert session_dir.name.startswith("session-"), state["session_root"]
        assert (session_dir / "session.jsonl").is_file(), session_dir
        assert state["source"]["particle"] == "proton", state["source"]
        assert state["state_revision"] == 0, state

        # ------------------------------------------------------ source drafts
        response = session.request("set_source", {"field": "energy", "value": "50 MeV"},
                                   state["state_revision"])
        assert response["op"] == "set_source" and response["status"] == "accepted", response
        assert response["application_status"] == "configured", response
        assert response["evidence_level"] == "unknown", response
        assert response["kernel_evidence"] == "not_observed", response
        assert response["duplicate"] is False, response
        assert abs(response["resolved"]["mono_energy_MeV"] - 50.0) < 1e-9, response
        assert response["requested"] == {"field": "energy", "value": "50 MeV"}, response
        revision = response["state_revision"]
        assert revision > state["state_revision"], response

        state = session.state()
        assert abs(state["source"]["mono_energy_MeV"] - 50.0) < 1e-9, state["source"]
        response = session.request("set_source", {"field": "particle", "value": "e-"},
                                   state["state_revision"])
        assert response["status"] == "accepted", response
        assert response["resolved"]["particle"] == "e-", response

        # Running before the kernel is initialized must be refused, not faked.
        state = session.state()
        response = session.request("run", {"events": 4}, state["state_revision"])
        assert response["status"] == "rejected", response
        assert response["reason"] == "kernel_not_initialized", response
        stale = session.request("set_source", {"field": "energy", "value": "60 MeV"},
                                max(0, state["state_revision"] - 1))
        assert stale["status"] == "rejected" and stale["reason"] == "stale_revision", stale
        first = session.request("get_state")
        session.seq += 1
        conflict_frame = {
            "kind": "request",
            "seq": session.seq,
            "id": hexadecimal(session.counter),
            "request_id": first["request_id"],
            "op": "get_state",
            "params": {"reuse": True},
        }
        session.send(conflict_frame)
        conflict_response = session.wait(
            lambda item: item.get("kind") == "response" and
            item.get("id") == conflict_frame["id"])
        assert conflict_response["reason"] == "idempotency_conflict", conflict_response
        unknown = session.request("unknown_op", revision=session.state()["state_revision"])
        assert unknown["status"] == "rejected" and unknown["reason"] == "unknown_op", unknown
        # The idempotency key covers the op as well as params: reusing a
        # request_id with a different op is a conflict, not a duplicate.
        third = session.request("get_state")
        session.seq += 1
        op_conflict_frame = {
            "kind": "request",
            "seq": session.seq,
            "id": hexadecimal(session.counter),
            "request_id": third["request_id"],
            "op": "ping",
            "params": {"reuse": True},
        }
        session.send(op_conflict_frame)
        op_conflict_response = session.wait(
            lambda item: item.get("kind") == "response" and
            item.get("id") == op_conflict_frame["id"])
        assert op_conflict_response["reason"] == "idempotency_conflict", op_conflict_response

        # -------------------------------------------------------- initialize
        state = session.state()
        response = session.request("initialize", revision=state["state_revision"])
        assert response["status"] == "applied", response
        assert response["kernel_state"] == "idle", response
        state = session.state()
        assert state["kernel_state"] == "idle", state
        again = session.request("initialize", revision=state["state_revision"])
        assert again["status"] == "rejected" and again["reason"] == "already_initialized", again

        # --------------------------------------------------------------- run
        state = session.state()
        run_frame = session.request("run", {"events": 6}, state["state_revision"], wait=False)
        response = session.wait(lambda item: item.get("kind") == "response" and
                                item.get("id") == run_frame["id"])
        assert response["status"] == "accepted" and response["planned_events"] == 6, response
        started = session.wait_event("run_started")
        assert started["planned_events"] == 6, started
        assert started["run_request_id"] == run_frame["request_id"], started
        run_id = started["run_id"]
        assert isinstance(run_id, int) and run_id >= 0, started
        finished = session.wait_event("run_finished")
        assert finished["run_id"] == run_id, finished
        assert finished["status"] == "completed", finished
        assert finished["planned_events"] == 6 and finished["completed_events"] == 6, finished
        assert finished["cancel_requested"] is False, finished
        assert finished["receipt"]["schema"] == "g4usim_session_run_receipt_v1", finished
        assert finished["receipt"]["completed_events"] == 6, finished
        receipt_path = Path(finished["receipt_path"])
        assert receipt_path.is_file(), finished
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["run_id"] == run_id and receipt["status"] == "completed", receipt
        artifacts = finished["artifacts"]
        assert isinstance(artifacts, list) and artifacts, finished
        for artifact in artifacts:
            assert Path(artifact["path"]).is_file(), artifact
            assert isinstance(artifact["sha256"], str) and len(artifact["sha256"]) == 64, artifact
            assert artifact["integrity_status"] in ("hashed", "self_reference_excluded"), artifact

        # Duplicate run request must be answered from the idempotency cache.
        session.send({"kind": "request", "seq": run_frame["seq"], "id": run_frame["id"],
                      "request_id": run_frame["request_id"], "op": "run",
                      "params": {"events": 6}, "state_revision": state["state_revision"]})
        duplicate = session.wait(lambda item: item.get("kind") == "response" and
                                 item.get("request_id") == run_frame["request_id"] and
                                 item.get("duplicate") is True)
        assert duplicate["status"] == "accepted", duplicate
        time.sleep(0.5)
        assert not [item for item in session.frames
                    if item.get("event") == "run_started" and item.get("run_id") == run_id + 1], \
            "duplicate run request started a second run"

        # ---------------------------------------------------- state and exit
        state = session.state()
        assert state["phase"] == "idle" and state["kernel_state"] == "idle", state
        response = session.request("shutdown", revision=state["state_revision"])
        assert response["status"] == "accepted", response
        assert response["session_id"] == welcome["session_id"], response
        closing = session.wait_event("closing")
        assert closing["reason"] == "shutdown_requested", closing
        assert closing["exit_code"] == 0, closing
        code = session.close(expect_exit=0)
        assert code == 0, code
        record_file = session_dir / "session.jsonl"
        assert record_file.is_file(), list(records.iterdir())
        recorded_texts = []
        for line in record_file.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            assert entry["schema"] == "g4usim-session-log-v1", entry
            recorded_texts.append(entry.get("text", ""))
        assert any('"event":"run_finished"' in text for text in recorded_texts), recorded_texts[:3]
        assert (output / "run_summary.txt").is_file(), list(output.iterdir())
        assert list(output.glob("event_edep_t0.csv")), list(output.iterdir())

        # ------------------------------------------------ terminal refusals
        write_refusal_case(executable, temp, "handshake_required",
                           ['{"kind":"request","seq":1,"id":"a1","request_id":"b1","op":"get_state"}'],
                           "handshake_required")
        write_refusal_case(executable, temp, "unsupported_protocol",
                           ['{"kind":"hello","protocol":"g4usim-session-v0"}'],
                           "unsupported_protocol")
        write_refusal_case(executable, temp, "invalid_json",
                           ['{"kind":"hello","protocol":"%s"' % PROTOCOL, '{"kind":'],
                           "protocol_error")
        write_refusal_case(executable, temp, "non_object_root",
                           ['{"kind":"hello","protocol":"%s"}' % PROTOCOL, "[1,2,3]"],
                           "protocol_error")
        write_refusal_case(executable, temp, "duplicate_key",
                           ['{"kind":"hello","protocol":"%s","protocol":"x"}' % PROTOCOL],
                           "protocol_error")
        write_refusal_case(executable, temp, "non_finite",
                           ['{"kind":"hello","protocol":"%s","value":1e999}' % PROTOCOL],
                           "protocol_error")
        write_cli_refusal(executable, temp, "missing_records", [],
                          "requires --session-record-dir")
        write_cli_refusal(executable, temp, "ui_combination", ["--ui", "--ui-session", "csh"],
                          "cannot be combined")
        write_cli_refusal(executable, temp, "records_inside_output", [],
                          "must be outside --output")
        eof_case(executable, temp)
        fatal_during_run_cases(executable, temp)
        ini_macro_refusal(executable, temp)
        record_boundary_cases(executable, temp)
        two_sessions_keep_history(executable, temp)
        mt16_terminal_case(executable, temp)
        v7_unknown_particle_session_case(executable, temp)

    return 0
# ---------------------------------------------------------------- repair scenarios


def absolute_config(temp: Path, *, macro: Path | None = None) -> Path:
    """A copy of the reference config with every input path made absolute."""
    text = (ROOT / "config" / "main.ini").read_text(encoding="utf-8")
    text = text.replace("file = config/materials/material.ini",
                        f"file = {(ROOT / 'config' / 'materials' / 'material.ini')}")
    text = text.replace("config = config/geometry/simple_box.ini",
                        f"config = {(ROOT / 'config' / 'geometry' / 'simple_box.ini')}")
    if macro is not None:
        assert "\n[run]\n" in text
        text = text.replace("\n[run]\n", f"\n[run]\nmacro = {macro}\n", 1)
    target = temp / ("config-macro.ini" if macro is not None else "config-absolute.ini")
    target.write_text(text, encoding="utf-8")
    return target


def open_session(session: "Session") -> dict[str, object]:
    session.send({"kind": "hello", "protocol": PROTOCOL})
    welcome = session.wait(lambda item: item.get("kind") == "welcome")
    state = session.state()
    response = session.request("initialize", revision=state["state_revision"])
    assert response["status"] == "applied", response
    return welcome


def run_round(session: "Session", events: int, timeout: float = 600.0) -> dict[str, object]:
    state = session.state()
    session.request("run", {"events": events}, state["state_revision"], wait=False)
    session.wait_event("run_started", timeout=timeout)
    return session.wait_event("run_finished", timeout=timeout)


def finish_session(session: "Session") -> None:
    state = session.state()
    response = session.request("shutdown", revision=state["state_revision"])
    assert response["status"] == "accepted", response
    session.wait_event("closing")
    assert session.close(expect_exit=0) == 0


def ini_macro_refusal(executable: Path, temp: Path) -> None:
    """A preconfigured INI macro must be refused instead of silently ignored."""
    macro = temp / "selected.mac"
    macro.write_text("/run/beamOn 1\n", encoding="utf-8")
    config = absolute_config(temp, macro=macro)
    output = temp / "macro-out"
    records = temp / "macro-records"
    completed = subprocess.run(
        [str(executable), "--config", str(config), "--session-server",
         "--output", str(output), "--session-record-dir", str(records)],
        cwd=ROOT, input="", capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300, check=False)
    log = completed.stdout + completed.stderr
    assert completed.returncode != 0, (completed.returncode, log[-2000:])
    assert "does not support a preconfigured macro" in log, log[-2000:]
    assert "run_started" not in log, log[-2000:]


def record_boundary_cases(executable: Path, temp: Path) -> None:
    """Record roots resolve like the output root and must stay outside it."""
    root = temp / "boundary"
    root.mkdir(parents=True, exist_ok=True)
    config = absolute_config(temp)
    rejected = subprocess.run(
        [str(executable), "--config", str(config), "--session-server",
         "--output", "out", "--session-record-dir", "out/records"],
        cwd=root, input="", capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=300, check=False)
    log = rejected.stdout + rejected.stderr
    assert rejected.returncode != 0, (rejected.returncode, log[-2000:])
    assert "must be outside --output" in log, log[-2000:]

    accepted = subprocess.run(
        [str(executable), "--config", str(config), "--session-server",
         "--output", "out2", "--session-record-dir", "records2"],
        cwd=root,
        input=json.dumps({"kind": "hello", "protocol": PROTOCOL}) + "\n",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300, check=False)
    assert accepted.returncode == 0, (accepted.returncode, (accepted.stdout + accepted.stderr)[-2000:])
    created = root / "records2"
    assert created.is_dir(), list(root.iterdir())
    assert list(created.glob("session-*/session.jsonl")), list(created.rglob("*"))

    if os.name == "nt":
        alias = temp / "alias"
        alias.mkdir(parents=True, exist_ok=True)
        rejected_alias = subprocess.run(
            [str(executable), "--config", str(config), "--session-server",
             "--output", str(alias / "CaseOut"),
             "--session-record-dir", str(alias / "caseout" / "records")],
            cwd=ROOT, input="", capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300, check=False)
        alias_log = rejected_alias.stdout + rejected_alias.stderr
        assert rejected_alias.returncode != 0, (rejected_alias.returncode, alias_log[-2000:])
        assert "must be outside --output" in alias_log, alias_log[-2000:]


def two_sessions_keep_history(executable: Path, temp: Path) -> None:
    """A second session on the same record root must never truncate the first."""
    base = temp / "shared-records"
    first = Session(executable, temp / "shared-out-1", base)
    open_session(first)
    first_finished = run_round(first, 4)
    assert first_finished["status"] == "completed", first_finished
    state = first.state()
    first_dir = Path(state["session_root"])
    first_log = first_dir / "session.jsonl"
    finish_session(first)
    # The session_end meta line is written during shutdown; only that close is
    # allowed to add bytes. A later session must leave the file untouched.
    before = first_log.read_bytes()

    second = Session(executable, temp / "shared-out-2", base)
    open_session(second)
    second_finished = run_round(second, 3)
    assert second_finished["status"] == "completed", second_finished
    second_dir = Path(second.state()["session_root"])
    assert second_dir != first_dir, (second_dir, first_dir)
    finish_session(second)
    assert first_log.read_bytes() == before, "the first session log changed after the second session"
    assert list(second_dir.glob("run-*.json")), list(second_dir.iterdir())


def mt16_terminal_case(executable: Path, temp: Path) -> None:
    """A supported 16-worker run must end with exactly one attributable terminal frame."""
    session = Session(executable, temp / "mt16-out", temp / "mt16-records", threads=16)
    open_session(session)
    finished = run_round(session, 32, timeout=900)
    assert finished["run_id"] == 0, finished
    assert finished["status"] == "completed", finished
    assert finished["completed_events"] == 32, finished
    assert "run_request_id" in finished and "state_revision" in finished, finished
    if finished.get("artifacts_truncated"):
        reference = finished.get("receipt_ref")
        assert isinstance(reference, dict) and reference.get("path"), finished
        assert Path(reference["path"]).is_file(), reference
    else:
        assert isinstance(finished.get("artifacts"), list), finished
    finish_session(session)

def v7_unknown_particle_session_case(executable: Path, temp: Path) -> None:
    """A run refused by kernel-level scoring validation must leave no run at all.

    The controlled session applies its source and initializes the kernel before
    BeamOn, so the scoring-filter particle check must happen in the run request
    before accepted/started/replay registration.  A refused run must not create a
    run receipt, must not emit run_started/run_finished, must exit non-zero and
    must write a failed summary with zero planned and zero completed events.
    """
    case = temp / "v7-session"
    case.mkdir(parents=True, exist_ok=True)
    geometry = case / "geometry.ini"
    geometry.write_text(
        """[world]
shape = box
size = 40 mm, 40 mm, 40 mm
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 10 mm, 10 mm, 0.1 mm
material = G4_Galactic
position = 0 mm, 0 mm, 0 mm
sensitive = true
""",
        encoding="utf-8",
    )
    config = case / "main.ini"
    config.write_text(
        f"""[run]
name = v7_session
threads = 1
seed = 20261307
interactive = false
verbose = 0
check_overlaps = false
dry_run = false

[output]
dir = out
format = csv

[geometry]
template = hierarchical
config = {geometry}
default_world_material = G4_Galactic

[physics]
em = option4
default_cut = 0.7 mm

[scoring]
enabled = true
hits = true
event_edep = false
edep = false
dose = true
fluence = false
auto_create_default_scorers = true

[scoring.filter.dose]
particles = muon

[source]
particle = gamma
energy = 1 MeV
position_type = plane
shape = square
halfx = 4 mm
center = 0, 0, -2 mm
direction = 0, 0, 1
""",
        encoding="utf-8",
    )
    output = case / "output"
    records = case / "records"
    session = Session(executable, output, records, config=config)
    welcome = open_session(session)
    session_dir = Path(welcome["state"]["session_root"])
    state = session.state()
    request = session.request("run", {"events": 10}, state["state_revision"], wait=False)
    response = session.wait(lambda item: item.get("kind") == "response" and
                            item.get("id") == request["id"])
    assert response["status"] == "rejected", response
    assert response["reason"] == "scoring_config_invalid", response
    assert isinstance(response.get("message"), str) and response["message"], response
    assert "run_id" not in response, response
    run_events = [item for item in session.frames
                  if item.get("kind") == "event" and
                  item.get("event") in {"run_started", "run_finished"}]
    assert run_events == [], run_events
    accepted = [item for item in session.frames
                if item.get("kind") == "response" and item.get("op") == "run" and
                item.get("status") != "rejected"]
    assert accepted == [], accepted
    code = session.close(expect_exit=None)
    assert code != 0, (code, session.raw_lines[-20:])
    assert not list(session_dir.glob("run-*.json")), list(session_dir.iterdir())

    summary_paths = list(output.glob("run_summary*.txt"))
    assert len(summary_paths) == 1, summary_paths
    summary: dict[str, str] = {}
    for line in summary_paths[0].read_text(encoding="utf-8").splitlines():
        if " = " in line and not line.startswith("["):
            key, value = line.split(" = ", 1)
            summary[key.strip()] = value.strip()
    assert summary.get("status") == "failed", summary.get("status")
    assert summary.get("output_failure_stage") == "scoring_filter_particle", summary
    assert summary.get("run_count") == "0", summary.get("run_count")
    assert summary.get("actual_completed_event_count") == "0", summary
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata.get("runs") == [], metadata.get("runs")
    planned = summary.get("run_0_planned_events")
    assert planned in (None, "", "0"), planned
    for pattern in ("hits_t*.csv", "event_edep_t*.csv", "dose_volume_summary_t*.csv",
                    "fluence_volume_summary_t*.csv", "spectrum_*.csv",
                    "scorer_statistics*.csv", "edep_*summary_t*.csv"):
        assert not list(output.glob(pattern)), (pattern, list(output.iterdir()))


if __name__ == "__main__":
    raise SystemExit(main())
