"""Real production ROOT TLS and early-bias callback component evidence.

Three separate processes; no BeamOn/application finalization claim. --help
does not launch a probe. Native execution awaits the primary's frozen build.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODES = ("root-two-runs", "bias-no-rules", "bias-unattached")
MESSAGES = {
    "bias-no-rules": "XS biasing is enabled but no process-level rule is active. Add a rule or disable biasing.",
    "bias-unattached": "XS biasing has active rules but no operator is attached to a geometry volume. Configure a valid rule volume or disable biasing.",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    assert condition, message  # successful checks counted by formal runner, -O still rejects


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def judge(mode, folder, raw, identity, stdout):
    require(raw["mode"] == mode and Path(raw["output"]).resolve() == folder.resolve(), "mode/path mismatch")
    require(raw["identity"] == identity and raw["status"] == "pass", "wrong raw identity/status")
    require(raw["beam_on_called"] is False and raw["application_finalize_called"] is False, "scope changed")
    require(type(raw["checks"]) is int and raw["checks"] > 0, "no component checks")
    markers = re.findall(r"^Root lifecycle component checks passed: (\d+)\s*$", stdout, re.M)
    require(markers == [str(raw["checks"])], "check count marker differs from raw result")
    if mode == "root-two-runs":
        import uproot
        require(len(raw["runs"]) == 2 and [x["run"] for x in raw["runs"]] == [0, 1], "two runs missing")
        require({p.name for p in folder.glob("*.root")} == {"run0.root", "run1.root"}, "ROOT file set")
        observations = []
        for run, ids, raw_values, weighted_values in ((0, [11, 12], [1., 2.], [4., 5.]), (1, [21], [3.], [6.])):
            entry = raw["runs"][run]
            require(Path(entry["file"]).resolve() == (folder / f"run{run}.root").resolve(), "ROOT path binding")
            require(entry["fills"] == len(ids) and entry["sentinel_event_id"] == 999, "fill plan mismatch")
            for key in ("tls_open_after_begin", "native_open_after_begin", "end_return", "tls_closed_after_end", "native_closed_after_end"):
                require(entry[key] is True, "actual open/close state: " + key)
            require(entry["repeat_end_return"] is False, "repeat End result")
            with uproot.open(folder / f"run{run}.root") as root:
                events = root["events"].arrays(library="np")
                require(events["eventID"].tolist() == ids, "event IDs / closed sentinel leaked / prior run reset failed")
                require(events["runID"].tolist() == [run] * len(ids), "wrong ROOT run IDs")
                require(events["threadID"].tolist() == [0] * len(ids), "wrong output thread slots")
                require(events["raw_edep_MeV"].tolist() == raw_values, "raw event values")
                require(events["weighted_edep_MeV"].tolist() == weighted_values, "weighted event values")
                histograms = {}
                for name, expected in (("edep_raw", raw_values), ("edep_weighted", weighted_values)):
                    histogram = root[name]
                    values = histogram.values(flow=True).tolist()
                    expected_bins = [0.] * 12
                    for value in expected:
                        expected_bins[int(value) + 1] += 1
                    require(values == expected_bins, name + " bin counts/reset/closed sentinel")
                    require(histogram.axis().edges().tolist() == list(range(11)), "binning changed")
                    require(float(histogram.member("fEntries")) == len(expected), "hist entries mismatch")
                    histograms[name] = values
                observations.append({"run": run, "event_ids": ids, "histogram_bins_with_flow": histograms})
        return {"root_observations": observations}
    require(raw["kernel_initialized"] is True and raw["handler_restored"] is True, "kernel/handler lifecycle")
    require(len(raw["notifications"]) == 1, "wrong exception count")
    note = raw["notifications"][0]
    require(note["origin"] == "RunAction::BeginOfRunAction" and note["code"] == "AIHLBiasingTarget001", "wrong failure entry")
    # G4ExceptionSeverity enumerator is persisted; exact severity is also checked
    # against RunMustBeAborted by the compiled SDK probe, not guessed here.
    require(type(note["severity"]) is int and note["description"] == MESSAGES[mode], "wrong native description/severity")
    require(note["latch_precedes_exception"] is True and note["effective_begin_at_notify"] == 0, "latch ordering")
    first = note["latch_at_notify"]
    require(first["run"] == 42 and first["stage"] == "biasing_validate_active" and first["message"] == MESSAGES[mode], "first failure at Notify")
    require(first == raw["first_failure_after_begin"] == raw["first_failure_after_end_and_cleanup"], "cleanup changed first failure")
    require(raw["effective_begin"] == 0 and raw["effective_end"] == 1, "effective begin/end")
    require(raw["scorer_begin"] == raw["scorer_end"] == raw["bias_worker_receipts"] == 0, "unentered cleanup")
    require(raw["callback_run"] == {"run": 42, "planned": 1, "completed": 0}, "callback run facts")
    summary = json.loads((folder / "callback-summary.json").read_text(encoding="utf-8"))
    require(summary["runs"] == [{"run_id": 42, "planned_events": 1, "completed_events": 0}], "production callback summary mismatch")
    require(not list(folder.rglob("scorer_statistics*")), "statistics generated before timer start")
    require(not list(folder.rglob("*.root")), "early bias entered ROOT Begin")
    require(not list(folder.rglob("run_summary.txt")), "probe should not claim application finalization")
    return {"first_failure": first, "callback_runs": summary["runs"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, help="Default G4USIM_ROOT_LIFECYCLE_CHECK, else sibling of G4USIM_EXE")
    parser.add_argument("--expected-source-fingerprint")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    require(args.timeout > 0, "timeout must be positive")
    if args.probe is None:
        override = os.environ.get("G4USIM_ROOT_LIFECYCLE_CHECK")
        args.probe = Path(override) if override else Path(os.environ["G4USIM_EXE"]).with_name("rootLifecycleCheck.exe" if os.name == "nt" else "rootLifecycleCheck")
    probe = args.probe.resolve()
    require(probe.is_file(), "probe missing")
    if not args.expected_source_fingerprint:
        from run_m0_tests import workspace_source_fingerprint
        args.expected_source_fingerprint = workspace_source_fingerprint()
    evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix="root-lifecycle-", dir=evidence))
    digest = sha(probe)
    probe_source = ROOT / "tools/rootLifecycleCheck.cc"
    receipt = {"status": "running", "binary": str(probe), "binary_sha256": digest,
               "probe_source_sha256": sha(probe_source), "wrapper_sha256": sha(__file__),
               "expected_source_fingerprint": args.expected_source_fingerprint, "cases": [],
               "scope": "production TLS and real initialized SDK callbacks; no BeamOn or application finalize"}
    save(trial / "receipt.json", receipt)
    env = os.environ.copy()
    env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
    try:
        # Import before launching any mode; missing reader is not a native pass.
        import uproot  # noqa: F401
        identity_argv = [str(probe), "--identity"]
        result = subprocess.run(identity_argv, cwd=trial, env=env, capture_output=True, timeout=args.timeout)
        (trial / "identity.stdout.log").write_bytes(result.stdout)
        (trial / "identity.stderr.log").write_bytes(result.stderr)
        receipt["identity_process"] = {"argv": identity_argv, "cwd": str(trial), "exit_code": result.returncode}
        require(result.returncode == 0 and sha(probe) == digest, "identity process/binary drift")
        identity = json.loads(result.stdout.decode("utf-8-sig"))
        require(identity["source_fingerprint"] == args.expected_source_fingerprint, "source fingerprint mismatch")
        require(identity["probe_sha256"] == receipt["probe_source_sha256"], "compiled probe source mismatch")
        receipt["identity"] = identity
        for mode in MODES:
            work = trial / mode
            work.mkdir()
            output = work / "native"  # must not preexist; native probe owns creation
            argv = [str(probe), mode, str(output)]
            record = {"mode": mode, "argv": argv, "cwd": str(work), "exit_code": None,
                      "binary_sha256": digest, "output_fault_env_removed": True}
            save(work / "command.json", record)
            try:
                require(sha(probe) == digest, "probe changed before mode")
                with (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
                    run = subprocess.run(argv, cwd=work, env=env, stdout=stdout, stderr=stderr, timeout=args.timeout)
                record["exit_code"] = run.returncode
                require(run.returncode == 0 and sha(probe) == digest, "native mode failed/binary drift")
                raw = json.loads((output / "result.json").read_text(encoding="utf-8"))
                log = (work / "stdout.log").read_text(encoding="utf-8", errors="replace")
                errors = (work / "stderr.log").read_text(encoding="utf-8", errors="replace")
                require("GetRealElapsed" not in log + errors and "Timer not started" not in log + errors, "unstarted timer diagnostic")
                record["observed"] = judge(mode, output, raw, identity, log)
                record["status"] = "pass"
            except Exception as error:
                record.update(status="fail", error=repr(error))
                raise
            finally:
                record["artifacts"] = {p.relative_to(work).as_posix(): sha(p) for p in sorted(work.rglob("*")) if p.is_file() and p != work / "receipt.json"}
                save(work / "receipt.json", record)
                receipt["cases"].append(record)
                save(trial / "receipt.json", receipt)
        require([c["mode"] for c in receipt["cases"]] == list(MODES), "incomplete mode set")
        require(sha(probe) == digest and sha(probe_source) == receipt["probe_source_sha256"] and sha(__file__) == receipt["wrapper_sha256"], "final identity drift")
        for record in receipt["cases"]:
            work = Path(record["cwd"])
            require(json.loads((work / "receipt.json").read_text(encoding="utf-8")) == record, "sidecar mismatch")
            require({p.relative_to(work).as_posix(): sha(p) for p in work.rglob("*") if p.is_file() and p != work / "receipt.json"} == record["artifacts"], "artifact set/bytes drift")
        receipt["status"] = "passed"
    except Exception as error:
        receipt.update(status="failed", error=repr(error))
    receipt["identity_artifacts"] = {p.name: sha(p) for p in trial.glob("identity.*.log")}
    save(trial / "receipt.json", receipt)
    print(f"ROOT lifecycle {receipt['status']}; receipt={trial / 'receipt.json'}")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
