"""Exercise complete random-state replay against the real backend.

The replay contract is strict: a completed session captures the CLHEP engine
state, the build/data/input identity and the accepted operations; a replay in a
fresh process with a new output root must restore that exact state (verified by
reading the engine state back) and reproduce every per-event row.  Corrupt,
incomplete, cancelled and identity-mismatched sessions are refused before any
run starts.  These assertions only use the public session protocol, the produced
CSV files and the replay snapshot/manifest documents.
"""

from __future__ import annotations

import atexit
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

OPEN_SESSIONS: list = []


def _cleanup_sessions() -> None:
    for session in OPEN_SESSIONS:
        try:
            if session.process.poll() is None:
                session.process.kill()
                session.process.wait(timeout=30)
        except (OSError, ValueError):
            pass


atexit.register(_cleanup_sessions)
sys.path.insert(0, str(ROOT / "scripts"))

from test_session_protocol import (  # noqa: E402
    PROTOCOL,
    Session,
    finish_session,
    open_session,
    run_round,
)

DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def set_energy(session: Session, text: str) -> None:
    state = session.state()
    response = session.request("set_source", {"field": "energy", "value": text},
                               state["state_revision"])
    assert response["status"] == "accepted", response


def run_source_session(executable: Path, temp: Path, name: str, *, threads: int,
                       rounds: list[tuple[str, int]], events: int,
                       cancel: bool = False) -> dict[str, object]:
    """Run a real session, finish it cleanly and return its evidence."""
    output = temp / f"{name}-out"
    records = temp / f"{name}-records"
    session = Session(executable, output, records, threads=threads)
    OPEN_SESSIONS.append(session)
    started_at = time.monotonic()
    welcome = open_session(session)
    print(f"[timing] {name}: session open (identity capture) {time.monotonic() - started_at:.1f}s",
          flush=True)
    session_dir = Path(welcome["state"]["session_root"])
    for energy_text, _ in rounds:
        set_energy(session, energy_text)
        if cancel:
            # Start a long round and cancel it while it is running; the round
            # stays in the record but the session is not replayable.
            revision = session.state()["state_revision"]
            session.request("run", {"events": 200000}, revision, wait=False)
            started = session.wait_event("run_started", timeout=300)
            assert started["run_id"] is not None
            accepted = session.request("cancel", {}, revision)
            assert accepted["status"] == "accepted", accepted
            finished = session.wait_event("run_finished", timeout=300)
            assert finished["status"] in {"cancelled", "aborted"}, finished
            break
        record = run_round(session, events)
        assert record["status"] == "completed", record
        assert record["completed_events"] == events, record
    finish_session(session)
    snapshot = json.loads((session_dir / "replay-snapshot.json").read_text(encoding="utf-8"))
    manifest = json.loads((session_dir / "replay-manifest.json").read_text(encoding="utf-8"))
    return {
        "output": output,
        "records": records,
        "session_dir": session_dir,
        "snapshot": snapshot,
        "manifest": manifest,
    }


def start_replay(executable: Path, temp: Path, name: str, source_dir: Path, *,
                 threads: int, output: Path | None = None,
                 extra_args: list[str] | None = None) -> Session:
    """Spawn a replay process and send hello; the caller waits for its frames."""
    out = output if output is not None else temp / f"{name}-out"
    records = temp / f"{name}-records"
    replay = Session(executable, out, records, threads=threads,
                     extra_args=extra_args if extra_args is not None
                     else ["--session-replay", str(source_dir)])
    OPEN_SESSIONS.append(replay)
    replay.send({"kind": "hello", "protocol": PROTOCOL})
    return replay


def replay_session(executable: Path, temp: Path, name: str, source_dir: Path, *,
                   threads: int, output: Path | None = None,
                   extra_args: list[str] | None = None) -> dict[str, object]:
    """Spawn a replay process and collect all frames until the process exits."""
    started_at = time.monotonic()
    replay = start_replay(executable, temp, name, source_dir, threads=threads,
                          output=output, extra_args=extra_args)
    welcome = replay.wait(lambda item: item.get("kind") == "welcome", timeout=600)
    print(f"[timing] {name}: replay welcome (identity validation) "
          f"{time.monotonic() - started_at:.1f}s", flush=True)
    out = output if output is not None else temp / f"{name}-out"
    records = temp / f"{name}-records"
    closing = None
    deadline = time.time() + 600.0
    while time.time() < deadline:
        for frame in replay.frames:
            if frame.get("kind") == "event" and frame.get("event") == "closing":
                closing = frame
        if closing is not None:
            break
        if replay.closed:
            break
        time.sleep(0.05)
    code = replay.close(timeout=300)
    return {"session": replay, "welcome": welcome, "closing": closing,
            "exit_code": code, "output": out, "records": records}


def collect_table(output: Path, pattern: str,
                  keys: tuple[str, ...] = ("runID", "eventID")) -> dict[tuple[str, ...], list[str]]:
    """Multiset of CSV rows keyed by the physical identity columns."""
    table: dict[tuple[str, ...], list[str]] = {}
    for path in sorted(output.rglob(pattern)):
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            assert header is not None, path
            columns = list(header)
            for index in keys:
                assert index in columns, (path, columns)
            for row in reader:
                if not row:
                    continue
                values = dict(zip(columns, row))
                key = tuple(values.get(index, "") for index in keys)
                table.setdefault(key, []).append("|".join(row))
    return table


def compare_tables(original: dict, replayed: dict, label: str) -> None:
    assert set(original) == set(replayed), (
        f"{label}: keys differ; original={len(original)} replayed={len(replayed)}")
    for key in original:
        assert original[key] == replayed[key], f"{label}: row differs at {key}"
    rows = sum(len(value) for value in original.values())
    assert rows > 0, f"{label}: no rows compared"


def refusal_case(executable: Path, temp: Path, name: str, *,
                 source: dict[str, object] | None = None,
                 source_dir: Path | None = None,
                 threads: int = 1, output: Path | None = None,
                 extra_args: list[str] | None = None,
                 expected_text: str = "",
                 pre_existing_output: bool = False) -> None:
    directory = source_dir if source_dir is not None else Path(str(source["session_dir"]))
    replay = start_replay(executable, temp, name, directory, threads=threads,
                          output=output, extra_args=extra_args)
    code = replay.close(timeout=600)
    text = "\n".join(replay.raw_lines)
    assert code != 0, (code, replay.raw_lines[-16:])
    assert "session replay refused" in text, text[-2000:]
    if expected_text:
        assert expected_text in text, text[-2000:]
    run_frames = [item for item in replay.frames
                  if item.get("kind") == "event" and item.get("event") == "run_started"]
    assert not run_frames, run_frames
    if pre_existing_output:
        return
    output_dir = Path(str(output if output is not None else temp / f"{name}-out"))
    produced = sorted(path for path in output_dir.rglob("*") if path.is_file()) if output_dir.exists() else []
    physical = [path for path in produced if path.suffix in {".csv", ".root", ".h5"}]
    assert not physical, ("a refused replay must not produce physics output files", physical)
    summary = output_dir / "run_summary.txt"
    if summary.exists():
        summary_text = summary.read_text(encoding="utf-8", errors="replace")
        assert "status = failed" in summary_text or "status=failed" in summary_text, summary_text[-1200:]


def closing_failure_case(executable: Path, temp: Path, name: str,
                         source_dir: Path, expected_text: str = "") -> None:
    """Identity checks that need the initialized kernel fail the replay without runs."""
    replay = replay_session(executable, temp, name, source_dir, threads=1)
    closing = replay["closing"]
    assert replay["exit_code"] != 0, replay["session"].raw_lines[-16:]
    assert closing is not None and closing.get("reason") == "replay_failed", closing
    if expected_text:
        assert expected_text in str(closing.get("message", "")), closing
    run_frames = [item for item in replay["session"].frames
                  if item.get("kind") == "event" and item.get("event") == "run_started"]
    assert not run_frames, run_frames
    output_dir = Path(str(replay["output"]))
    produced = (sorted(path for path in output_dir.rglob("*") if path.is_file())
                if output_dir.exists() else [])
    physical = [path for path in produced if path.suffix in {".csv", ".root", ".h5"}]
    assert not physical, ("a refused replay must not produce physics output files", physical)


def corrupt_session(source_dir: Path, temp: Path, name: str, mutate) -> Path:
    target = temp / name
    shutil.copytree(source_dir, target)
    snapshot_path = target / "replay-snapshot.json"
    manifest_path = target / "replay-manifest.json"
    if mutate == "bad_snapshot_json":
        snapshot_path.write_text("{not json", encoding="utf-8")
    elif mutate == "unknown_schema":
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["version"] = 99
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshot_sha256"] = __import__("hashlib").sha256(
            snapshot_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif mutate == "rng_bytes":
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["rng"]["status_text"] = "corrupted engine state\n"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshot_sha256"] = __import__("hashlib").sha256(
            snapshot_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif mutate == "not_replayable":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["replayable"] = False
        manifest["reason"] = "the test marks the session incomplete"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif mutate == "data_digest":
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["data_identity"]["digest"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif mutate == "provenance_digest":
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["provenance"]["digest"] = "f" * 64
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["snapshot_sha256"] = __import__("hashlib").sha256(
            snapshot_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif mutate == "missing_snapshot":
        snapshot_path.unlink()
    else:
        raise AssertionError(f"unknown mutation {mutate}")
    return target


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", "")) if os.environ.get("G4USIM_EXE") else DEFAULT_EXE
    assert executable.is_file(), executable
    environment = os.environ.copy()
    environment.pop("G4USIM_TEST_OUTPUT_FULL", None)

    with tempfile.TemporaryDirectory(prefix="session-replay-") as tmp_text:
        temp = Path(tmp_text)

        # ---- single-threaded A/B/A replay reproduces every event row
        source = run_source_session(executable, temp, "single", threads=1,
                                    rounds=[("100 MeV", 100.0), ("200 MeV", 200.0),
                                            ("100 MeV", 100.0)], events=5)
        snapshot = source["snapshot"]
        manifest = source["manifest"]
        assert snapshot["schema"] == "g4usim_session_replay_v1"
        assert snapshot["version"] == 1
        assert snapshot["threads"] == 1
        assert len(snapshot["rng"]["status_text"]) > 0
        assert len(snapshot["rng"]["sha256"]) == 64
        # The physics data identity is captured lazily right before the first
        # BeamOn, not during the session handshake (multi-GB content hash).
        assert "data" not in snapshot, snapshot.keys()
        assert snapshot["provenance"]["count"] > 0, snapshot["provenance"]
        assert len(snapshot["provenance"]["digest"]) == 64
        assert snapshot["provenance"]["observations"], snapshot["provenance"]
        assert snapshot["inputs"]["main_config"]["sha256"]
        assert manifest["schema"] == "g4usim_session_replay_manifest_v1"
        assert manifest["replayable"] is True, manifest
        assert manifest["snapshot_sha256"]
        data_identity = manifest["data_identity"]
        assert len(data_identity["digest"]) == 64, data_identity
        assert data_identity["datasets"], data_identity
        contents = [entry.get("manifest_sha256") for entry in data_identity["datasets"]
                    if entry.get("available")]
        assert contents and all(len(value) == 64 for value in contents), contents
        steps = manifest["steps"]
        assert [step["op"] for step in steps] == [
            "set_source", "run", "set_source", "run", "set_source", "run"], steps
        assert all(step["status"] == "completed" for step in steps if step["op"] == "run")

        replay = replay_session(executable, temp, "single-replay",
                                Path(str(source["session_dir"])), threads=1)
        assert replay["exit_code"] == 0, replay["session"].raw_lines[-16:]
        payload = replay["welcome"].get("replay")
        assert isinstance(payload, dict) and payload.get("replayable") is True, payload
        assert payload["steps"] == steps
        closing = replay["closing"]
        assert closing is not None and closing["reason"] == "replay_finished", closing
        assert closing["steps_executed"] == 3, closing
        original = collect_table(Path(str(source["output"])), "event_edep_t*.csv")
        replayed = collect_table(Path(str(replay["output"])), "event_edep_t*.csv")
        compare_tables(original, replayed, "single event table")
        original_hits = collect_table(Path(str(source["output"])), "hits_t*.csv", ("runID", "eventID", "trackID"))
        replayed_hits = collect_table(Path(str(replay["output"])), "hits_t*.csv", ("runID", "eventID", "trackID"))
        compare_tables(original_hits, replayed_hits, "single hits table")

        # ---- two-worker replay: the same physical events must reappear even
        # though the worker/file sharding may differ (compared before sharding).
        source_mt = run_source_session(executable, temp, "multi", threads=2,
                                       rounds=[("150 MeV", 150.0), ("80 MeV", 80.0)],
                                       events=6)
        assert source_mt["snapshot"]["threads"] == 2
        assert source_mt["manifest"]["replayable"] is True
        replay_mt = replay_session(executable, temp, "multi-replay",
                                   Path(str(source_mt["session_dir"])), threads=2)
        assert replay_mt["exit_code"] == 0, replay_mt["session"].raw_lines[-16:]
        assert replay_mt["closing"]["reason"] == "replay_finished"
        compare_tables(collect_table(Path(str(source_mt["output"])), "event_edep_t*.csv"),
                       collect_table(Path(str(replay_mt["output"])), "event_edep_t*.csv"),
                       "multi event table")
        compare_tables(collect_table(Path(str(source_mt["output"])), "hits_t*.csv", ("runID", "eventID", "trackID")),
                       collect_table(Path(str(replay_mt["output"])), "hits_t*.csv", ("runID", "eventID", "trackID")),
                       "multi hits table")

        # ---- refusals must happen before any run and leave no output behind
        single_dir = Path(str(source["session_dir"]))
        refusal_case(executable, temp, "bad-json",
                     source_dir=corrupt_session(single_dir, temp, "mut-bad-json",
                                                "bad_snapshot_json"))
        refusal_case(executable, temp, "unknown-schema",
                     source_dir=corrupt_session(single_dir, temp, "mut-schema",
                                                "unknown_schema"),
                     expected_text="unsupported replay snapshot schema")
        refusal_case(executable, temp, "missing-snapshot",
                     source_dir=corrupt_session(single_dir, temp, "mut-missing",
                                                "missing_snapshot"))
        refusal_case(executable, temp, "rng-corrupt",
                     source_dir=corrupt_session(single_dir, temp, "mut-rng", "rng_bytes"),
                     expected_text="random state")
        closing_failure_case(executable, temp, "data-digest",
                             corrupt_session(single_dir, temp, "mut-data",
                                             "data_digest"),
                             expected_text="different Geant4 physics data")
        refusal_case(executable, temp, "provenance-digest",
                     source_dir=corrupt_session(single_dir, temp, "mut-prov",
                                                "provenance_digest"),
                     expected_text="different input bytes")
        refusal_case(executable, temp, "not-replayable",
                     source_dir=corrupt_session(single_dir, temp, "mut-incomplete",
                                                "not_replayable"),
                     expected_text="not replayable")
        refusal_case(executable, temp, "threads-mismatch", source_dir=single_dir,
                     threads=2, expected_text="thread count")
        refusal_case(executable, temp, "same-output", source_dir=single_dir,
                     output=Path(str(source["output"])),
                     expected_text="new output root", pre_existing_output=True)
        cancelled = run_source_session(executable, temp, "cancelled", threads=1,
                                       rounds=[("100 MeV", 100.0)], events=5,
                                       cancel=True)
        assert cancelled["manifest"]["replayable"] is False, cancelled["manifest"]
        refusal_case(executable, temp, "cancelled-replay",
                     source_dir=Path(str(cancelled["session_dir"])))

        # ---- the flag needs the session server entry point (fail fast)
        completed = subprocess.run(
            [str(executable), "--config", str(ROOT / "config" / "main.ini"),
             "--output", str(temp / "flag-out"),
             "--session-record-dir", str(temp / "flag-records"),
             "--session-replay", str(single_dir)],
            cwd=ROOT, input="", capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300, check=False)
        assert completed.returncode != 0, completed.returncode
        log = completed.stdout + completed.stderr
        assert "--session-replay requires --session-server" in log, log[-1500:]

    print("session replay smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
