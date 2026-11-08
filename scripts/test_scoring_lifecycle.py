"""Frozen AR2 native Action/factory matrix; the probe is not the production CLI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from run_m0_tests import workspace_source_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    assert condition, message


def cases():
    result = []
    def add(name, workers=1, sequential=False, mode="normal", startup="explicit",
            exception="std", modulo=1, output_format="csv", cleanup_fault=None):
        result.append(dict(name=name, workers=workers, sequential=sequential, mode=mode,
                           startup=startup, exception=exception, modulo=modulo,
                           output_format=output_format, cleanup_fault=cleanup_fault))
    add("normal-sequential", sequential=True)
    for workers in (1, 2, 4):
        for modulo in (1, 3):
            add(f"normal-mt{workers}-mod{modulo}", workers=workers, modulo=modulo)
    for sequential, workers in ((True, 1), (False, 1), (False, 2), (False, 4)):
        role = "sequential" if sequential else f"mt{workers}"
        for exception in ("std", "nonstd"):
            for startup in ("explicit", "direct-beamon"):
                add(f"throw-{role}-{exception}-{startup}", workers, sequential,
                    "worker-throw", startup, exception)
    for workers, exception in ((2, "std"), (4, "nonstd")):
        for startup in ("explicit", "direct-beamon"):
            add(f"delayed-mt{workers}-{startup}", workers=workers, mode="worker-delayed-throw",
                startup=startup, exception=exception, modulo=3)
    for sequential, workers in ((True, 1), (False, 2)):
        add(f"legacy-{'sequential' if sequential else 'mt2'}", workers, sequential, "legacy-clone")
    for mode in ("empty", "null", "unknown", "wrong-name", "duplicate", "throw-std", "throw-nonstd"):
        add("register-" + mode, mode="register-" + mode)
    for fault in ("final_flush_master", "final_close_master"):
        add("startup-plus-" + fault, workers=2, mode="worker-delayed-throw",
            startup="direct-beamon", cleanup_fault=fault)
    add("normal-root-mt2", workers=2, output_format="root")
    add("delayed-root-mt2", workers=2, mode="worker-delayed-throw",
        startup="direct-beamon", output_format="root")
    return result


def inputs(folder, case):
    geometry = folder / "geometry.ini"
    geometry.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
                        "[volume.Probe]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\n"
                        "material=G4_Si\nsensitive=true\n", encoding="utf-8")
    config = folder / "main.ini"
    config.write_text(f"[run]\nthreads={case['workers']}\nseed=20261108\ninteractive=false\nverbose=0\n"
                      f"[output]\nformat={case['output_format']}\n"
                      f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\ncheck_overlaps=true\n"
                      "[physics]\nreference=FTFP_BERT\ndefault_cut=0.1 mm\n"
                      "[scoring]\nenabled=true\nhits=false\nevent_edep=true\nedep=true\n"
                      "let=false\ndose=false\nfluence=false\ndisplacement=false\n"
                      "[source]\nparticle=geantino\nenergy=10 MeV\nposition_type=point\n"
                      "position=-20 mm,0,0\ndirection=1,0,0\n", encoding="utf-8")
    return config


def check_trace(case, trace):
    require([t["seq"] for t in trace] == list(range(1, len(trace) + 1)), "trace sequence incomplete")
    times = [t["monotonic_ns"] for t in trace]
    require(times == sorted(times), "trace ordering")
    constructed = [t for t in trace if t["kind"] == "instance_construct"]
    require(len({t["instance"] for t in constructed}) == len(constructed), "duplicate instance identity")
    instances = {t["instance"]: t for t in constructed}
    workers = {i: t for i, t in instances.items() if t["factory_thread_id"] >= 0}
    for t in workers.values():
        require(t["role"] == ("sequential" if case["sequential"] else "worker"), "instance role")
        require(0 <= t["factory_thread_id"] < case["workers"], "instance thread range")
        if not case["sequential"]:
            require(t["native_thread_id"] == t["factory_thread_id"], "native/factory thread mismatch")
    begun = {}
    ended = {}
    for t in trace:
        if t["kind"] == "scorer_begin_run":
            key = (t["instance"], t["run"])
            require(t["instance"] in workers and key not in begun, "invalid/duplicate BeginRun")
            require(t["reset"] is True, "run not reset")
            require(t["seq"] > instances[t["instance"]]["seq"], "Begin before construction")
            begun[key] = t
        elif t["kind"] == "scorer_end_run":
            key = (t["instance"], t["run"])
            require(key in begun and key not in ended, "End without Begin or duplicate End")
            require(t["seq"] > begun[key]["seq"], "End before Begin")
            require(t["factory_thread_id"] == instances[t["instance"]]["factory_thread_id"], "End instance/thread mismatch")
            ended[key] = t
    require(set(begun) == set(ended), "entered instance not cleaned up")
    destroyed = [t for t in trace if t["kind"] == "instance_destroy" and t["instance"] in workers]
    require(sorted(t["instance"] for t in destroyed) == sorted(workers), "worker instance destruction incomplete")
    for t in destroyed:
        require(t["seq"] > max([instances[t["instance"]]["seq"]] +
                [e["seq"] for (i, _), e in ended.items() if i == t["instance"]]), "destroy before cleanup")
    if case["mode"] == "normal":
        require({t["factory_thread_id"] for t in workers.values()} == set(range(case["workers"])), "worker instance set")
        require(len(workers) == case["workers"], "worker instance multiplicity")
        require(set(begun) == {(i, r) for i in workers for r in (0, 1)}, "per-instance two-run coverage")
    for key, end in ended.items():
        events = end["events"]
        require(end["n_events"] == len(events) and len(set(events)) == len(events), "local event count")
        require(end["sum_test_units"] == sum(e % 2 for e in events), "local deterministic sum")
        require(end["sum_sq_test_units2"] == sum((e % 2) ** 2 for e in events), "local deterministic square sum")
        starts = [t for t in trace if t["kind"] == "scorer_begin_event" and (t["instance"], t["run"]) == key]
        finishes = [t for t in trace if t["kind"] == "scorer_end_event" and (t["instance"], t["run"]) == key]
        require([t["event"] for t in starts] == events == [t["event"] for t in finishes], "local event pairing")
        for start, finish in zip(starts, finishes):
            require(begun[key]["seq"] < start["seq"] < finish["seq"] < end["seq"], "event outside run")
    for t in trace:
        if t["kind"] in ("scorer_begin_event", "scorer_end_event"):
            require((t["instance"], t["run"]) in begun, "event outside entered instance/run")


def check_output(case, folder, report, summary):
    output = (folder / "output").resolve()
    require(Path(report["finalization"]["summary_path"]).resolve() == output / "run_summary.txt", "summary path escaped case")
    require(Path(summary["actual_output_dir"]).resolve() == output, "summary output path")
    require(summary["configured_seed"] == "20261108" and summary["planned_num_threads"] == str(case["workers"]), "summary configuration")
    require(summary["output_format"] == case["output_format"] and summary["output_format_requested"] == case["output_format"], "output format not applied")
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    registered = set()
    for artifact in metadata["generated_files"]:
        path = Path(artifact["path"]).resolve()
        require(path.is_relative_to(output) and path not in registered, "artifact path/duplicate")
        registered.add(path)
        require(path.is_file(), "registered artifact missing")
        if path.name == "run_metadata.json":
            require(artifact["integrity_status"] == "self_reference_excluded", "metadata self exclusion")
        else:
            require(artifact["integrity_status"] == "hashed" and artifact["sha256"] == sha(path), "artifact SHA")
            require(artifact["size_bytes"] == path.stat().st_size, "artifact size")
    actual = {p.resolve() for p in output.rglob("*") if p.is_file()}
    require(actual == registered | {output / "scoring-lifecycle-receipt.json"}, "unregistered/missing output")
    for name in ("main.ini", "geometry.ini"):
        path = (folder / name).resolve()
        require(any(Path(i["path"]).resolve() == path and i["sha256"] == sha(path) and i["status"] == "recorded"
                    for i in metadata["provenance"]["inputs"]), "missing accepted input identity: " + name)
    if case["mode"] == "normal":
        require(summary["actual_threads"] == str(case["workers"]), "actual thread count")
        require(summary["run_count"] == "2" and summary["planned_event_count"] == "20" and
                summary["actual_completed_event_count"] == "20", "persisted totals")
        for r, n in ((0, 12), (1, 8)):
            require(summary[f"run_{r}_id"] == str(r) and summary[f"run_{r}_planned_events"] == str(n) and
                    summary[f"run_{r}_completed_events"] == str(n), "persisted per-run totals")
        if case["output_format"] == "root":
            import uproot
            require({p.name for p in output.glob("*.root")} == {"g4usim.root", "g4usim_r1.root"}, "ROOT file set")
            for r, n, name in ((0, 12, "g4usim.root"), (1, 8, "g4usim_r1.root")):
                with uproot.open(output / name) as root:
                    tree = root["events"]
                    require(int(tree.num_entries) == n, "ROOT event entry count")
                    require(sorted(tree["eventID"].array(library="np").tolist()) == list(range(n)), "ROOT event IDs")
                    require(set(tree["runID"].array(library="np").tolist()) == {r}, "ROOT run IDs")
    else:
        require(summary["actual_completed_event_count"] == "0", "persisted negative event count")
        expected_runs = 1 if case["startup"] == "direct-beamon" and not case["mode"].startswith("register-") else 0
        require(summary["run_count"] == str(expected_runs), "negative actual run count")
        if expected_runs:
            require(summary["run_0_planned_events"] == "12" and summary["run_0_completed_events"] == "0", "negative per-run count")
        # ROOT startup refusal does not assert that any ROOT writer was opened.


def judge(case, report, run, log, binary_sha, source_sha, probe_sha, folder, probe):
    identity = report["identity"]
    require(report["schema"] == "scoring_lifecycle_probe_v1", "probe schema")
    require(report["entrypoint"] == ("probe_realSequential" if case["sequential"] else "probe_MT"), "probe entrypoint")
    require(report["mode"] == case["mode"] and report["startup"] == case["startup"], "probe case mismatch")
    require(report["not_production_CLI_coverage"] is True, "probe boundary missing")
    parameters = report["parameters"]
    expected_fault = case["workers"] - 1 if case["mode"] == "worker-delayed-throw" else 0
    expected_parameters = dict(workers=case["workers"], event_modulo_requested=case["modulo"], events=[12, 8],
                               exception=case["exception"], seed=20261108, fault_thread=expected_fault, delay_ms=50, gate_timeout_ms=10000)
    for key, value in expected_parameters.items():
        require(parameters[key] == value and type(parameters[key]) is type(value), "parameter mismatch: " + key)
    require(Path(identity["binary_path"]).resolve() == probe.resolve(), "binary path mismatch")
    require(Path(identity["config_path"]).resolve() == (folder / "main.ini").resolve(), "config path mismatch")
    require(Path(identity["probe_source_path"]).resolve() == ROOT / "tools/scoringLifecycleCheck.cc", "probe source path mismatch")
    require(identity["source_fingerprint"] == source_sha, "candidate source drift")
    require(identity["compiled_probe_sha256"] == probe_sha, "probe build/source mismatch")
    for key in ("binary_sha256_before", "binary_sha256_after"):
        require(identity[key] == binary_sha, key)
    for key in ("probe_source_sha256", "probe_source_sha256_after"):
        require(identity[key] == probe_sha, key)
    require(report["observations_complete"] and not report["delay_gate_timed_out"], "incomplete native observer")
    require(report["exit_code"] == run.returncode, "exit receipt mismatch")
    require(report["finalization"]["calls"] == 1, "summary finalized other than once")
    summary_path = Path(report["finalization"]["summary_path"])
    require(summary_path.is_file() and sha(summary_path) == report["finalization"]["summary_sha256"], "summary identity")
    summary = dict(line.split(" = ", 1) for line in summary_path.read_text(encoding="utf-8").splitlines() if " = " in line)
    require(summary["source_fingerprint"] == source_sha, "summary source mismatch")
    observations = report["event_observations"]
    trace = report["trace"]
    check_trace(case, trace)
    check_output(case, folder, report, summary)
    commands = report["commands"]
    names = ["Initialize_with_MT_fake_if_MT" if case["startup"] == "explicit" else "base_kernel_Initialize_without_MT_fake",
             "BeamOn_run_0", "probe_marker_after_run_0", "BeamOn_run_1", "probe_marker_after_run_1"]
    require([c["command"] for c in commands] == names, "command list mismatch")
    if case["mode"] == "normal":
        expected_statuses = ["completed"] * 5
    elif case["mode"].startswith("register-"):
        expected_statuses = ["not_started"] * 5
    elif case["startup"] == "explicit":
        expected_statuses = ["failed"] + ["not_started"] * 4
    else:
        expected_statuses = ["completed", "failed"] + ["not_started"] * 3
    require([c["status"] for c in commands] == expected_statuses, "command boundary mismatch")
    if not case["mode"].startswith("register-"):
        require(identity["runmanager_kind"] == (0 if case["sequential"] else 1), "actual runmanager kind")
        require(parameters["event_modulo_public_getter"] == (None if case["sequential"] else case["modulo"]), "event modulo readback")
    if "controlled_direct_admission" in report:
        admission = report["controlled_direct_admission"]
        require(case["startup"] == "direct-beamon" and admission["enabled"] is True and
                admission["not_production_CLI_behavior"] is True and admission["failure_latch_cleared"] is False and
                admission["first_failure"] == report["first_failure_after_finalize"], "controlled direct admission boundary")
    require(report["first_failure_before_finalize"] == report["first_failure_after_finalize"], "cleanup overwrote first failure")
    if case["cleanup_fault"]:
        require(f"[TestOutputFault] {case['cleanup_fault']} triggered" in log,
                "secondary finalization fault was not observed")
    if case["mode"] == "normal":
        require(run.returncode == 0 and summary["status"] == "completed", "normal run failed")
        require(report["first_failure_after_finalize"] is None, "normal run has a failure")
        require([r["planned"] for r in report["runs_from_production_summary"]] == [12, 8], "normal planned runs")
        require([r["processed"] for r in report["runs_from_production_summary"]] == [12, 8], "normal completed runs")
        for key in ("primary_generator_calls", "primary_vertices", "event_begin_callbacks", "event_end_callbacks",
                    "processed_from_production_run_summary"):
            require(observations[key] == 20, key)
        require(observations["aborted_at_event_end"] == 0, "normal aborted event")
        require(all(c["status"] == "completed" for c in report["commands"]), "normal command missing")
        instances = [t for t in trace if t["kind"] == "instance_construct" and t["factory_thread_id"] >= 0]
        require(len(instances) == case["workers"], "per-thread instance count")
        require(len({t["instance"] for t in instances}) == case["workers"], "shared instance")
        ends = [t for t in trace if t["kind"] == "scorer_end_run"]
        require(len(ends) == case["workers"] * 2, "per-thread two-run cleanup")
        for run_id, total in ((0, 12), (1, 8)):
            rows = [t for t in ends if t["run"] == run_id]
            events = [e for t in rows for e in t["events"]]
            require(sorted(events) == list(range(total)), "missing, duplicate or cross-run events")
            require(sum(t["sum_test_units"] for t in rows) == total // 2, "deterministic sum or reset")
            require(sum(t["sum_sq_test_units2"] for t in rows) == total // 2, "deterministic second moment")
        return
    require(run.returncode == 1 and summary["status"] == "failed", "negative failed for an unrelated reason")
    require(int(summary["program_exit_code"]) != 0, "negative summary exit")
    for key in ("primary_generator_calls", "primary_vertices", "event_begin_callbacks", "event_end_callbacks",
                "processed_from_production_run_summary"):
        require(observations[key] == 0, "negative processed events: " + key)
    require(all(c["status"] == "not_started" for c in report["commands"][2:]), "continued after startup failure")
    failure = report["first_failure_after_finalize"]
    require(failure is not None and failure["run_id"] == -1, "startup run identity")
    if case["mode"].startswith("register-"):
        require(failure["stage"] == "probe_exception" and failure["thread_id"] == 0, "wrong registration failure provenance")
        require(not any(t["kind"].startswith("action_build") or t["kind"] == "run_begin_observed" for t in trace), "registration failure reached actions")
        entries = [t for t in trace if t["kind"] == "factory_enter"]
        require(all(t["factory_thread_id"] == -1 and t["factory_phase"] == "registration" for t in entries), "registration failure reached clone")
        require(len(entries) == (0 if case["mode"] in ("register-empty", "register-unknown") else 1), "registration factory count")
        expected = {"register-empty": "nonnull", "register-null": "null instance", "register-unknown": "unknown type",
                    "register-wrong-name": "name mismatch", "register-duplicate": "Duplicate",
                    "register-throw-std": "deliberate factory throw", "register-throw-nonstd": "non-standard"}
        require(expected[case["mode"]] in failure["message"], "wrong registration rejection")
        return
    require(failure["stage"] == "scoring_factory_build", "wrong failure stage")
    if case["mode"] == "legacy-clone":
        require("legacy" in failure["message"] and "rebuild description" in failure["message"] and
                "lifecycle_probe" in failure["message"], "wrong legacy rejection")
        require(not any(t["kind"] == "factory_enter" and t["factory_thread_id"] >= 0 for t in trace), "legacy rejection invoked clone factory")
    else:
        require("non-standard" in failure["message"] if case["exception"] == "nonstd"
                else "deliberate factory throw" in failure["message"], "wrong factory rejection")
        fault = case["workers"] - 1 if case["mode"] == "worker-delayed-throw" else 0
        require(failure["thread_id"] == fault, "wrong fault thread")
    if case["mode"] == "worker-delayed-throw":
        releases = [t for t in trace if t["kind"] == "delay_gate_release"]
        require(len(releases) == 1 and releases[0]["all_other_factories_arrived"], "delay was not synchronized")
        arrivals = [t for t in trace if t["kind"] == "factory_arrived"]
        require({t["factory_thread_id"] for t in arrivals} == set(range(case["workers"])), "delay factory set")
        require(all(t["seq"] < releases[0]["seq"] for t in arrivals), "gate released before peers arrived")
    # Sequential explicit Initialize is rejected before entering any event loop.
    if not (case["sequential"] and case["startup"] == "explicit"):
        rows = re.findall(r"\[RunAdmissionRejected\] role=(\w+) thread=(-?\d+) planned=(\d+) loop_dispatched=0 stage=(\S+)", log)
        require(len(rows) == case["workers"], "missing actual loop admission observations")
        require(all(r[0] == ("sequential" if case["sequential"] else "worker") and r[3] == "scoring_factory_build" for r in rows), "wrong admission scope")
        if not case["sequential"]:
            require({int(r[1]) for r in rows} == set(range(case["workers"])), "worker admission set")
        require(all(int(r[2]) == (0 if case["startup"] == "explicit" else 12) for r in rows), "fake/real loop identity")


def main():
    backend = Path(os.environ["G4USIM_EXE"])
    probe = Path(os.environ.get("G4USIM_SCORING_LIFECYCLE_EXE", str(backend.with_name("scoringLifecycleCheck" + backend.suffix)))).resolve()
    evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"])
    evidence.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix="scoring-lifecycle-", dir=evidence))
    binary_sha, source_sha = sha(probe), workspace_source_fingerprint()
    probe_source = ROOT / "tools/scoringLifecycleCheck.cc"
    probe_sha = sha(probe_source)
    plan = cases()
    save(trial / "plan.json", plan)
    records = []
    for case in plan:
        folder = trial / case["name"]
        folder.mkdir()
        config = inputs(folder, case)
        command = [str(probe), "--config", str(config.resolve()), "--output", str((folder / "output").resolve()),
                   "--probe-source", str(probe_source), "--workers", str(case["workers"]), "--mode", case["mode"],
                   "--startup", case["startup"], "--exception", case["exception"], "--event-modulo", str(case["modulo"]),
                   "--events", "12,8", "--seed", "20261108", "--delay-ms", "50", "--gate-timeout-ms", "10000",
                   "--fault-thread", "last" if case["mode"] == "worker-delayed-throw" else "0"]
        if case["sequential"]:
            command.append("--sequential")
        env = os.environ.copy()
        env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
        if case["cleanup_fault"]:
            env["G4USIM_TEST_OUTPUT_FAULT"] = case["cleanup_fault"]
        record = dict(case=case, argv=command, cwd=str(folder.resolve()), status="not_run",
                      environment={k: env.get(k) for k in ("TEMP", "TMP", "TMPDIR", "G4USIM_TEST_OUTPUT_FAULT")},
                      inputs={p.name: sha(p) for p in (config, folder / "geometry.ini")})
        try:
            require(sha(probe) == binary_sha, "probe changed before execution")
            with (folder / "stdout.log").open("wb") as stdout, (folder / "stderr.log").open("wb") as stderr:
                run = subprocess.run(command, cwd=folder, env=env, stdout=stdout, stderr=stderr, timeout=120)
            record["exit_code"] = run.returncode
            report = json.loads((folder / "output/scoring-lifecycle-receipt.json").read_text(encoding="utf-8"))
            require(report["identity"]["config_sha256"] == record["inputs"]["main.ini"], "config identity")
            require(all(sha(folder / name) == digest for name, digest in record["inputs"].items()), "input changed during execution")
            log = (folder / "stdout.log").read_bytes() + (folder / "stderr.log").read_bytes()
            judge(case, report, run, log.decode("utf-8", errors="replace"), binary_sha, source_sha, probe_sha, folder, probe)
            record["status"] = "pass"
        except Exception as error:
            record.update(status="fail", error=repr(error))
        record["artifacts"] = {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob("*")) if p.is_file()}
        save(folder / "receipt.json", record)
        records.append(record)
        save(trial / "matrix.json", records)
    require(sha(probe) == binary_sha and sha(probe_source) == probe_sha, "final identity drift")
    require(workspace_source_fingerprint() == source_sha, "final source drift")
    failures = [r["case"]["name"] for r in records if r["status"] != "pass"]
    require(not failures, f"native lifecycle failures {failures}; evidence {trial}")
    print(f"Native scoring lifecycle: {len(records)} cases passed; evidence={trial}")


if __name__ == "__main__":
    main()
