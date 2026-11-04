"""Cancel a multi-threaded run through the controlled session and keep serving.

The contract requires the reader thread to answer control traffic while the
main thread is inside BeamOn: pings respond, mutation requests are refused as
busy, and cancel is acknowledged before the run ends.  The cancelled run must
still produce a per-run receipt, and a following run must not inherit the
cancel request from an earlier run id.
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


class Client:
    def __init__(self, executable: Path, output: Path, records: Path) -> None:
        environment = os.environ.copy()
        environment.pop("G4USIM_TEST_OUTPUT_FAULT", None)
        records.parent.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            [str(executable), "--config", str(ROOT / "config" / "main.ini"),
             "--session-server", "--output", str(output),
             "--session-record-dir", str(records), "--threads", "2"],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, env=environment)
        assert self.process.stdin is not None and self.process.stdout is not None
        self.frames: list[dict[str, object]] = []
        self.raw: list[str] = []
        self.condition = threading.Condition()
        self.counter = [0]
        self.sequence = 0
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            text = line.rstrip("\n")
            with self.condition:
                self.raw.append(text)
                try:
                    frame = json.loads(text)
                except ValueError:
                    frame = None
                if isinstance(frame, dict):
                    self.frames.append(frame)
                self.condition.notify_all()

    def send(self, frame: dict[str, object]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(frame) + "\n")
        self.process.stdin.flush()

    def new_id(self) -> str:
        self.counter[0] += 1
        return f"{self.counter[0]:012x}"

    def frame(self, op: str, params: dict[str, object] | None = None,
              revision: int | None = None) -> dict[str, object]:
        sequence = self.sequence
        self.sequence += 1
        value: dict[str, object] = {"kind": "request", "seq": sequence,
                                    "id": self.new_id(), "request_id": self.new_id(),
                                    "op": op}
        if params is not None:
            value["params"] = params
        if revision is not None:
            value["state_revision"] = revision
        return value

    def request(self, op: str, params: dict[str, object] | None = None,
                revision: int | None = None) -> dict[str, object]:
        value = self.frame(op, params, revision)
        self.send(value)
        return self.wait(lambda item: item.get("kind") == "response" and
                         item.get("id") == value["id"], timeout=180.0)

    def wait(self, predicate, timeout: float = 300.0) -> dict[str, object]:
        deadline = time.time() + timeout
        with self.condition:
            while True:
                for frame in self.frames:
                    if predicate(frame):
                        return frame
                remaining = deadline - time.time()
                assert remaining > 0, f"timed out; tail={self.raw[-16:]}"
                self.condition.wait(min(remaining, 0.5))

    def wait_event(self, event: str, timeout: float = 300.0) -> dict[str, object]:
        return self.wait(lambda item: item.get("kind") == "event" and
                         item.get("event") == event, timeout)

    def close(self, timeout: float = 300.0) -> int:
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=30)
            raise AssertionError(f"session did not exit; tail={self.raw[-20:]}")


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    assert executable.is_file(), executable
    with tempfile.TemporaryDirectory(prefix="g4usim-session-cancel-",
                                     ignore_cleanup_errors=True) as directory:
        temp = Path(directory)
        output = temp / "out"
        records = temp / "records"
        client = Client(executable, output, records)

        client.send({"kind": "hello", "protocol": PROTOCOL})
        welcome = client.wait(lambda item: item.get("kind") == "welcome")
        assert welcome["protocol"] == PROTOCOL, welcome
        client.sequence = 1
        state = client.request("get_state")
        assert state["status"] == "ok", state
        assert state["state"]["phase"] == "idle", state
        assert Path(state["state"]["record_root"]) == records
        session_dir = Path(state["state"]["session_root"])
        assert session_dir.parent == records and session_dir.name.startswith("session-")
        initialized = client.request("initialize", revision=welcome["state"]["state_revision"])
        assert initialized["status"] == "applied", initialized
        revision = initialized["state_revision"]

        planned = 200000
        run_frame = client.frame("run", {"events": planned}, revision)
        client.send(run_frame)
        accepted = client.wait(lambda item: item.get("kind") == "response" and
                               item.get("id") == run_frame["id"], timeout=180.0)
        assert accepted["status"] == "accepted", accepted
        assert accepted["planned_events"] == planned, accepted
        revision = accepted["state_revision"]
        run_request_id = run_frame["request_id"]
        started = client.wait_event("run_started", timeout=180.0)
        assert started["planned_events"] == planned, started
        assert started["run_request_id"] == run_request_id, started
        run_id = started["run_id"]
        assert isinstance(run_id, int) and run_id >= 0, started

        # The reader thread must answer while the main thread runs BeamOn.
        time.sleep(0.8)
        ping = client.request("ping")
        assert ping["status"] == "ok", ping
        assert ping["phase"] == "running", ping
        busy = client.request("set_source", {"field": "energy", "value": "11 MeV"},
                              revision)
        assert busy["status"] == "rejected" and busy["reason"] == "busy", busy

        # Reader control frames share the revision identity rule with the
        # main path: a cancel from a stale revision, a missing/wrong-typed
        # revision, a wrong target type or a wrong run target must all be
        # rejected without touching the cancel intent while the run continues.
        stale = client.request("cancel", {"run_request_id": run_request_id},
                               max(0, revision - 1))
        assert stale["status"] == "rejected", stale
        assert stale["reason"] == "stale_revision", stale
        missing_revision = client.frame("cancel", {"run_request_id": run_request_id})
        client.send(missing_revision)
        missing_response = client.wait(
            lambda item: item.get("kind") == "response" and
            item.get("id") == missing_revision["id"], timeout=30.0)
        assert missing_response["status"] == "rejected", missing_response
        assert missing_response["reason"] == "invalid_request", missing_response
        wrong_type = client.request("cancel", {"run_request_id": 123}, revision)
        assert wrong_type["status"] == "rejected", wrong_type
        assert wrong_type["reason"] == "invalid_request", wrong_type
        wrong_target = client.request("cancel", {"run_request_id": "not-this-run"}, revision)
        assert wrong_target["status"] == "rejected", wrong_target
        assert wrong_target["reason"] == "unknown_run", wrong_target
        wrong_id_type = client.request("cancel", {"run_id": "zero"}, revision)
        assert wrong_id_type["status"] == "rejected", wrong_id_type
        assert wrong_id_type["reason"] == "invalid_request", wrong_id_type
        still_running = client.request("ping")
        assert still_running["status"] == "ok", still_running
        assert still_running["phase"] == "running", still_running

        cancel = client.request("cancel", {"run_request_id": run_request_id}, revision)
        assert cancel["status"] == "accepted", cancel
        assert cancel["run_request_id"] == run_request_id, cancel
        assert cancel["cancel_mode"] == "soft_abort_at_event_boundary", cancel
        assert cancel["run_id"] == run_id, cancel

        finished = client.wait_event("run_finished", timeout=300.0)
        assert finished["run_id"] == run_id, finished
        assert finished["status"] == "cancelled", finished
        assert finished["cancel_requested"] is True, finished
        assert finished["planned_events"] == planned, finished
        completed = finished["completed_events"]
        assert isinstance(completed, int) and 0 <= completed < planned, finished
        assert finished["receipt"]["status"] == "cancelled", finished
        receipt_path = Path(finished["receipt_path"])
        assert receipt_path.is_file(), finished
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["status"] == "cancelled" and receipt["cancel_requested"] is True, receipt
        assert receipt["completed_events"] == completed, receipt

        # A completed run after a cancelled one must not inherit the cancel flag.
        state = client.request("get_state")
        assert state["status"] == "ok" and state["state"]["phase"] == "idle", state
        revision = state["state"]["state_revision"]
        second_frame = client.frame("run", {"events": 10}, revision)
        client.send(second_frame)
        second_accepted = client.wait(lambda item: item.get("kind") == "response" and
                                      item.get("id") == second_frame["id"], timeout=180.0)
        assert second_accepted["status"] == "accepted", second_accepted
        second_started = client.wait(
            lambda item: item.get("kind") == "event" and item.get("event") == "run_started"
            and item.get("run_request_id") == second_frame["request_id"], timeout=180.0)
        assert second_started["run_request_id"] == second_frame["request_id"], second_started
        assert second_started["run_id"] == run_id + 1, second_started
        assert second_started["cancel_requested"] is False, second_started
        second_finished = client.wait(
            lambda item: item.get("kind") == "event" and item.get("event") == "run_finished"
            and item.get("run_request_id") == second_frame["request_id"], timeout=300.0)
        assert second_finished["run_id"] == run_id + 1, second_finished
        assert second_finished["status"] == "completed", second_finished
        assert second_finished["completed_events"] == 10, second_finished
        assert second_finished["cancel_requested"] is False, second_finished

        state = client.request("get_state")
        shutdown = client.request("shutdown", revision=state["state"]["state_revision"])
        assert shutdown["status"] == "accepted", shutdown
        closing = client.wait_event("closing")
        assert closing["exit_code"] == 0, closing
        code = client.close()
        assert code == 0, (code, client.raw[-20:])
        assert (session_dir / "run-0000.json").is_file(), list(session_dir.iterdir())
        assert (session_dir / "run-0001.json").is_file(), list(session_dir.iterdir())
        assert (session_dir / "session.jsonl").is_file(), list(session_dir.iterdir())
        summary = (output / "run_summary.txt").read_text(encoding="utf-8")
        assert "status = completed" in summary, summary[-2000:]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
