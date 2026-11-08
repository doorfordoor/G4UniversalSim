"""AUD08: 16 real backend processes, legacy LET/phase-space selectors, MT1/MT2.

Requires G4USIM_EXE and G4USIM_TEST_EVIDENCE_DIR. No skips or synthetic backend
data. --help does not inspect the executable, create inputs or run processes.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

EVENTS = 10
SEED = 20261108
ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    assert condition, message  # Successful checks counted by test_assert_probe; -O retains rejection above.


def csv_rows(paths: list[Path], required: set[str]) -> list[dict[str, str]]:
    result = []
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            require(required <= set(reader.fieldnames or []), f"Wrong CSV header: {path}")
            result.extend(reader)
    return result


def worker_files(output: Path, stem: str, workers: int) -> list[Path]:
    expected = {f"{stem}_t{i}.csv" for i in range(workers)}
    found = sorted(output.glob(stem + "_t*.csv"))
    require({p.name for p in found} == expected, f"Missing/unexpected worker CSVs: {stem}: {found}")
    return found


def lazy_worker_files(output: Path, stem: str, workers: int) -> list[Path]:
    # Only these writers open on the first row. Phase space/LET summaries do not.
    require(stem in ("event_edep", "hits"), "Not a supported lazy writer")
    expected = {f"{stem}_t{i}.csv" for i in range(workers)}
    found = sorted(output.glob(stem + "_t*.csv"))
    require(bool(found) and {p.name for p in found} <= expected,
            f"Missing all or unexpected lazy worker CSVs: {stem}: {found}")
    return found


def write_inputs(work: Path, topic: str, selector: str, workers: int) -> tuple[Path, Path]:
    # LET: real proton deposition, gamma is a known neutral particle and gives no LET.
    # Phase space: noninteracting geantino crosses a vacuum target exactly once.
    # The matching all case demonstrates recording; proton selection legitimately records zero.
    material = "G4_Si" if topic == "let" else "G4_Galactic"
    geometry = work / "geometry.ini"
    geometry.write_text(
        "[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_Galactic\n"
        "[volume.Probe]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\n"
        f"position=0,0,0\nmaterial={material}\nsensitive=true\n", encoding="utf-8")
    source = "proton" if topic == "let" else "geantino"
    config = work / "main.ini"
    text = (
        f"[run]\nthreads={workers}\nseed={SEED}\ninteractive=false\nverbose=0\n"
        "[output]\nformat=csv\n"
        f"[geometry]\ntemplate=hierarchical\nconfig={geometry.as_posix()}\ncheck_overlaps=true\n"
        "[physics]\nreference=FTFP_BERT\ndefault_cut=0.1 mm\n"
        "[scoring]\nenabled=true\nhits=true\nevent_edep=true\nedep=true\n"
        f"let={'true' if topic == 'let' else 'false'}\n"
        "dose=false\nfluence=false\ndisplacement=false\nauto_create_default_scorers=true\n"
        f"[source]\nparticle={source}\nenergy=10 MeV\nposition_type=point\n"
        "position=-20 mm,0,0\ndirection=1,0,0\n")
    text += (f"[scoring.let]\nparticles={selector}\n" if topic == "let" else
             f"[phase_space]\nvolume=Probe_PV\nparticles={selector}\nkill=false\n")
    config.write_text(text, encoding="utf-8")
    macro = work / "run.mac"
    # This is a real post-BeamOn command, not an echoed input string.
    macro.write_text(f"/run/initialize\n/run/beamOn {EVENTS}\n"
                     "/AIHL/physics/dumpProcesses after-selector.json\n", encoding="utf-8")
    return config, macro


def inspect(work: Path, record: dict, expected_source: str) -> dict:
    output = work / "output"
    summary_path = output / "run_summary.txt"
    require(summary_path.is_file(), "Missing fresh run_summary.txt")
    summary = dict(line.split(" = ", 1) for line in summary_path.read_text(encoding="utf-8").splitlines()
                   if " = " in line)
    record["summary"] = summary
    topic, kind, workers = record["topic"], record["kind"], record["workers"]
    expected_particle = "proton" if topic == "let" else "geantino"
    for key, expected in {"source_fingerprint": expected_source, "planned_num_threads": str(workers),
                          "configured_seed": str(SEED), "source_particle": expected_particle,
                          "source_energy": "10", "macro_seed_modified": "false"}.items():
        require(summary.get(key) == expected, f"{key}: {summary.get(key)!r} != {expected!r}")
    require(bool(summary.get("geant4_version")), "Missing Geant4 runtime identity")
    log = (work / "stdout.log").read_text(encoding="utf-8", errors="replace")
    diagnostic = log + (work / "stderr.log").read_text(encoding="utf-8", errors="replace")
    progress = []
    for line in log.splitlines():
        if line.startswith("[G4USimProgress] "):
            progress.append(json.loads(line.split(" ", 1)[1]))
    if kind in ("mixed_unknown", "all_unknown"):
        require(summary.get("actual_threads") in (str(workers), "unknown", "not_executed"),
                "Invalid actual_threads for a pre-run failure")
        require(record["exit_code"] != 0, "Unknown selector was accepted")
        require(summary.get("status") == "failed", "Missing failed summary")
        require(int(summary.get("program_exit_code", "0")) != 0, "Summary exit code is not failure")
        section = "scoring.let" if topic == "let" else "phase_space"
        # Require diagnostic in the persisted summary too, not just a stray stdout message.
        failure_text = "\n".join(v for k, v in summary.items() if "failure" in k)
        for token in (f"[{section}]/particles", "protno", "unknown Geant4 particle"):
            require(token in diagnostic and token in failure_text, f"Missing persisted selector diagnostic: {token}")
        require(summary.get("macro_execution_status") == "failed", "Macro failure not propagated")
        require(summary.get("macro_failure_command") in ("/run/initialize", f"/run/beamOn {EVENTS}"),
                "Wrong failed macro command")
        require(summary.get("macro_failure_line") in ("1", "2"), "Wrong macro failure line")
        # Strict pre-run rejection, not merely zero completed events after an aborted event.
        require(summary.get("run_count") == "0", "Run started: cannot claim pre-event rejection")
        require(not any(p.get("phase") in ("begin", "running", "end") for p in progress),
                "Run progress observed for invalid selector")
        require(not (work / "after-selector.json").exists(), "Later macro command executed after failure")
        require("to after-selector.json" not in diagnostic, "Later dump command logged after failure")
        for stem, columns in (("event_edep", {"eventID"}), ("hits", {"eventID"}), ("phase_space", {"eventID"})):
            require(not csv_rows(sorted(output.glob(stem + "_t*.csv")), columns),
                    f"Event/transport rows exist after selector failure: {stem}")
        return {"pre_run_rejection": True, "later_macro_blocked": True}
    require(record["exit_code"] == 0, "Valid selector backend failed")
    require(summary.get("actual_threads") == str(workers), "Successful run has wrong actual worker count")
    for key, expected in {"status": "completed", "macro_execution_status": "completed", "run_count": "1",
                          "run_0_planned_events": str(EVENTS), "run_0_completed_events": str(EVENTS),
                          "simulation_executed": "true", "output_failure_status": "none"}.items():
        require(summary.get(key) == expected, f"{key}: {summary.get(key)!r}")
    require((work / "after-selector.json").is_file() and "to after-selector.json" in diagnostic,
            "Positive control did not execute post-run macro sentinel")
    events = []
    worker_events = {}
    for path in lazy_worker_files(output, "event_edep", workers):
        rows = csv_rows([path], {"runID", "eventID", "raw_edep_MeV", "weighted_edep_MeV"})
        require(bool(rows), "Lazy event file has no actual event rows")
        worker = int(path.stem.rsplit("_t", 1)[1])
        worker_events[worker] = {int(r["eventID"]) for r in rows}
        events.extend(rows)
    require(len(events) == EVENTS and {int(r["eventID"]) for r in events} == set(range(EVENTS)),
            "Wrong event set or duplicate event rows")
    require(all(r["runID"] == "0" for r in events), "Unexpected additional run")
    values = [Decimal(r["raw_edep_MeV"]) for r in events]
    require(all(v.is_finite() and v >= 0 for v in values), "Invalid energy values")
    result = {"events": len(events), "raw_edep_sum_MeV": str(sum(values)),
              "event_ids_by_worker": {str(w): sorted(ids) for w, ids in worker_events.items()}}
    if topic == "let":
        hits = []
        for path in lazy_worker_files(output, "hits", workers):
            worker = int(path.stem.rsplit("_t", 1)[1])
            rows = csv_rows([path], {"runID", "particle", "parentID", "eventID", "edep_MeV"})
            require(bool(rows), "Lazy hit file has no actual hit rows")
            require(all(r["runID"] == "0" and int(r["eventID"]) in worker_events.get(worker, set()) for r in rows),
                    "Hit row does not belong to this worker's actual event set")
            hits.extend(rows)
        primary_events = {int(r["eventID"]) for r in hits if r["particle"] == "proton" and r["parentID"] == "0"}
        require(primary_events == set(range(EVENTS)) and sum(values) > 0, "No real proton deposition control")
        tallies = csv_rows(worker_files(output, "let_volume_summary", workers),
                           {"runID", "particles", "steps", "sum_wl_mm", "sum_wSl_MeV"})
        steps = sum(int(r["steps"]) for r in tallies)
        if kind == "all":
            require(steps > 0 and all(r["particles"] == "all_charged" for r in tallies), "all LET control is empty")
            require(sum(Decimal(r["sum_wSl_MeV"]) for r in tallies) > 0, "No LET contribution")
        else:
            require(not tallies, "Neutral gamma selector unexpectedly has LET rows")
        result.update(primary_proton_events=len(primary_events), let_rows=len(tallies), let_steps=steps)
    else:
        recorded = []
        for path in worker_files(output, "phase_space", workers):
            worker = int(path.stem.rsplit("_t", 1)[1])
            rows = csv_rows([path], {"runID", "eventID", "trackID", "parentID", "particle", "x_mm", "u", "v", "w"})
            require(all(r["runID"] == "0" and int(r["eventID"]) in worker_events.get(worker, set()) for r in rows),
                    "Phase-space row does not belong to this worker's actual event set")
            recorded.extend(rows)
        require(sum(values) == 0, "Noninteracting vacuum control deposited energy")
        if kind == "all":
            require(len(recorded) == EVENTS and {int(r["eventID"]) for r in recorded} == set(range(EVENTS)),
                    "Missing/duplicate geantino boundary records")
            for row in recorded:
                require(row["particle"] == "geantino" and row["trackID"] == "1" and row["parentID"] == "0" and row["runID"] == "0",
                        "Wrong recorded primary identity")
                require(abs(Decimal(row["x_mm"]) + 5) < Decimal("1e-8") and
                        Decimal(row["u"]) == 1 and Decimal(row["v"]) == Decimal(row["w"]) == 0,
                        "Recorded primary did not enter the expected face along +x")
        else:
            require(not recorded, "Proton selector recorded geantino")
        result["phase_space_rows"] = len(recorded)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source-fingerprint", default=os.environ.get("G4USIM_EXPECTED_SOURCE_FINGERPRINT"),
                        help="Frozen candidate SHA; defaults to current workspace_source_fingerprint()")
    parser.add_argument("--timeout", type=int, default=180, help="Seconds per backend process (no retry)")
    args = parser.parse_args()
    require(args.timeout > 0, "timeout must be positive")
    executable = Path(os.environ["G4USIM_EXE"]).resolve()
    evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]).resolve()
    require(executable.is_file(), f"Backend missing: {executable}")
    if args.expected_source_fingerprint is None:
        from run_m0_tests import workspace_source_fingerprint
        args.expected_source_fingerprint = workspace_source_fingerprint()
    require(re.fullmatch(r"[0-9a-f]{64}", args.expected_source_fingerprint) is not None, "Invalid source fingerprint")
    evidence.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix="legacy-selectors-", dir=evidence))
    digest = sha(executable)
    receipt = {"script_sha256": sha(Path(__file__)), "binary": str(executable), "binary_sha256": digest,
               "expected_source_fingerprint": args.expected_source_fingerprint, "trial": str(trial),
               "events": EVENTS, "seed": SEED, "planned_cases": 16, "status": "running", "cases": [],
               "scope": "Real MT1/MT2 backend; no claim from C++ component thread tests"}
    save(trial / "receipt.json", receipt)
    for workers in (1, 2):
        for topic in ("let", "phase_space"):
            selectors = {"all": "all", "valid_zero": "gamma" if topic == "let" else "proton",
                         "mixed_unknown": "proton,protno", "all_unknown": "protno"}
            for kind, selector in selectors.items():
                name = f"{topic}-{kind}-mt{workers}"
                work = trial / name
                work.mkdir(exist_ok=False)
                config, macro = write_inputs(work, topic, selector, workers)
                argv = [str(executable), "--config", str(config), "--macro", str(macro),
                        "--output", str(work / "output"), "--threads", str(workers), "--seed", str(SEED)]
                record = {"name": name, "topic": topic, "kind": kind, "selector": selector, "workers": workers,
                          "argv": argv, "cwd": str(work), "binary_sha256": digest, "exit_code": None,
                          "input_sha256": {p.name: sha(p) for p in (config, macro, work / "geometry.ini")}}
                started = time.monotonic()
                try:
                    require(sha(executable) == digest, "Executable changed during matrix")
                    with (work / "stdout.log").open("wb") as out, (work / "stderr.log").open("wb") as err:
                        run = subprocess.run(argv, cwd=work, stdout=out, stderr=err, timeout=args.timeout)
                    record["exit_code"] = run.returncode
                    require(sha(executable) == digest, "Executable changed during process")
                    record["observed"] = inspect(work, record, args.expected_source_fingerprint)
                    record["status"] = "pass"
                except Exception as error:
                    record.update(status="fail", error=repr(error))
                record["elapsed_seconds"] = time.monotonic() - started
                record["artifacts"] = {p.relative_to(work).as_posix(): sha(p) for p in sorted(work.rglob("*")) if p.is_file()}
                save(work / "receipt.json", record)  # sole self-exclusion
                receipt["cases"].append(record)
                save(trial / "receipt.json", receipt)
    failures = [r["name"] for r in receipt["cases"] if r["status"] != "pass"]
    # all positive controls are mandatory, so valid_zero cannot pass on absent recording capability.
    receipt.update(status="failed" if failures else "passed", failures=failures,
                   completed_cases=len(receipt["cases"]))
    save(trial / "receipt.json", receipt)
    print(f"Legacy particle selectors: {len(receipt['cases']) - len(failures)}/16 cases passed; receipt={trial / 'receipt.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
