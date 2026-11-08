"""AUD10 native charge checks; --help/--plan never launch a backend.

Frozen finite transport comparison: C12, 120 MeV, initial q=2, 2 T +z,
A x=100 mm, B x=200 mm, G4_Galactic, four events, MT1, seed20261109.
Do not infer constant effective ion charge from vacuum or nominal source q.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261109
HEADER_V1 = "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight".split(",")
HEADER_V2 = HEADER_V1 + ["charge_eplus"]
HEADER = HEADER_V2 + ["dynamic_mass_MeV", "electron_occupancy", "magnetic_moment_MeV_per_T", "polarization_x", "polarization_y", "polarization_z"]
TOLERANCES = {"position_mm": 0.01, "direction": 2e-5, "energy_MeV": 1e-6,
              "time_ns": 0.002, "charge_eplus": 1e-8, "primary": 1e-11}
GEOMETRY = """[world]
shape = box
size = 2 m, 2 m, 2 m
material = G4_Galactic
[volume.A]
parent = world
shape = box
size = 1 mm, 800 mm, 800 mm
position = 100.5 mm, 0 mm, 0 mm
material = G4_Galactic
[volume.B]
parent = world
shape = box
size = 1 mm, 800 mm, 800 mm
position = 200.5 mm, 0 mm, 0 mm
material = G4_Galactic
"""
ION_SOURCE = """[source]
particle = ion
ion = 6 12 2
energy = 120 MeV
position_type = point
position = 0,0,0 mm
direction = +x
"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    assert condition, message  # Real runner counts successful checks; -O still rejects.


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def table(rows, header=HEADER) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue()


def particle(pdg=1000060120, name="C12", charge=2, event=0, track=1):
    return [0, event, track, 0, name, pdg, 0, 0, 0, 1, 0, 0, 120, 0, 1, charge, 11176.90738362439, "[" + ";".join(["4"] + ["0"] * 19) + "]", 0, 0, 0, 0]


def fixed_cases():
    """Input fixtures, not a second implementation of the production parser."""
    yield "same_pdg_charges", {"input.csv": table([particle(charge=q, track=i+1) for i, q in enumerate((2, 0, 5))])}, 1, None, None
    # G4IonTable classifies proton as ion: v1 lacks its actual charge.
    yield "legacy_proton", {"input.csv": table([particle(2212, "proton")[:15]], HEADER_V1)}, 1, "legacy", 2
    yield "legacy_electron", {"input.csv": table([particle(11, "e-")[:15]], HEADER_V1)}, 1, None, None
    for name, rows in (
        ("legacy_ion", [particle()[:15]]),
        ("legacy_anti_ion", [particle(-1000020040, "anti_alpha")[:15]]),
        ("legacy_electron_then_ion", [particle(11, "e-")[:15], particle(track=2)[:15]]),
        ("legacy_ion_then_electron", [particle()[:15], particle(11, "e-", track=2)[:15]]),
    ):
        yield name, {"input.csv": table(rows, HEADER_V1)}, 1, "legacy", 3 if name == "legacy_electron_then_ion" else 2
    yield "legacy_v2_electron", {"input.csv": table([particle(11, "e-", charge=-1)[:16]], HEADER_V2)}, 1, None, None
    yield "v2_ion_missing_state", {"input.csv": table([particle()[:16]], HEADER_V2)}, 1, "state", 2
    for label, index, value in (("mass_nan",16,"NaN"),("mass_negative",16,-1),
                                ("occupancy_empty",17,"[]"),("occupancy_negative",17,"[-1]"),
                                ("occupancy_fraction",17,"[1.5]"),("moment_inf",18,"Inf"),
                                ("polarization_large",19,2)):
        row=particle();row[index]=value
        yield label,{"input.csv":table([row])},1,"parse",2
    for label, charge in (("charge_huge",1e100),("charge_negative_huge",-1e100),("charge_int_overflow",2147483648),("charge_difference_overflow",-2147483648)):
        yield label,{"input.csv":table([particle(11,"e-",charge=charge)[:16]],HEADER_V2)},1,"state",2
    for label,index in (("finite_huge_mass",16),("finite_huge_energy",12)):
        row=particle();row[index]=1e308
        yield label,{"input.csv":table([row])},1,"state",2
    row=particle();row[17]="none"
    yield "v3_recorded_sentinel", {"input.csv":table([particle(charge=sys.float_info.max)])},1,"state",2
    for reverse in (False, True):
        files = {"valid-v3.csv": table([particle()]), "legacy-v1.csv": table([particle()[:15]], HEADER_V1)}
        if reverse:
            files = dict(reversed(list(files.items())))
        yield "cache_order_" + ("v1_first" if reverse else "v3_first"), files, 2, "legacy", 2
    for label, value in (("nan", "NaN"), ("inf", "Inf"), ("minus_inf", "-Inf"), ("blank", ""), ("whitespace", "   ")):
        yield "charge_" + label, {"input.csv": table([particle(charge=value)])}, 1, "parse", 2
    yield "missing_column", {"input.csv": table([particle()[:15]])}, 1, "parse", 2
    yield "extra_column", {"input.csv": table([particle() + [2]])}, 1, "parse", 2
    reordered = HEADER.copy()
    reordered[-1], reordered[-2] = reordered[-2], reordered[-1]
    yield "wrong_column_order", {"input.csv": table([particle()], reordered)}, 1, "parse", 1


def close(a, b, tolerance, label):
    a, b = float(a), float(b)
    require(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= tolerance,
            f"{label}: {a} versus {b}, fixed tolerance {tolerance}")


class Trial:
    def __init__(self, root, exe, source, timeout):
        self.root, self.exe, self.source, self.timeout = root, exe, source, timeout
        self.digest = sha(exe)
        self.receipt = {"status": "running", "binary": str(exe), "binary_sha256": self.digest,
                        "source_fingerprint": source, "script_sha256": sha(Path(__file__)),
                        "seed": SEED, "tolerances": TOLERANCES, "cases": [],
                        "planned_cases": len(list(fixed_cases())) + 3,
                        "transport_scope": "fixed vacuum boundary continuation; not general charge-exchange validation"}
        self.flush()

    def flush(self):
        save(self.root / "receipt.json", self.receipt)

    def run(self, name, *, files=None, events=1, negative=None, line=None,
            record_at="B", field=False, replay=None):
        work = self.root / name
        work.mkdir()
        files = files or {}
        for filename, content in files.items():
            (work / filename).write_text(content, encoding="utf-8")
        (work / "geometry.ini").write_text(GEOMETRY, encoding="utf-8")
        inputs = [work / "geometry.ini"] + [work / key for key in files]
        if replay is not None:
            # Replay unmodified real boundary bytes; provenance binds the copy.
            (work / "recorded-A.csv").write_bytes(replay.read_bytes())
            inputs.append(work / "recorded-A.csv")
            source_text = "[source]\nphase_space_file = recorded-A.csv\n"
        elif files:
            source_text = "[source]\nphase_space_file = " + ", ".join(files) + "\n"
        else:
            source_text = ION_SOURCE
        ini = f"""[run]
threads = 1
seed = {SEED}
[output]
format = csv
[geometry]
template = hierarchical
config = {(work / 'geometry.ini').as_posix()}
[physics]
reference = FTFP_BERT
default_cut = 0.1 mm
[scoring]
enabled = true
hits = false
event_edep = false
edep = false
{source_text}
[phase_space]
volume = {record_at}_PV
particles = all
kill = true
"""
        if field:
            ini += "[field]\nmagnetic = 0,0,2 T\ndelta_chord = 0.001 mm\ndelta_one_step = 0.0001 mm\ndelta_intersection = 0.0001 mm\n"
        (work / "main.ini").write_text(ini, encoding="utf-8")
        # Sentinel uses an existing real read-only command, not a fake marker.
        (work / "run.mac").write_text(f"/run/initialize\n/run/beamOn {events}\n/AIHL/physics/dumpProcesses after.json\n", encoding="utf-8")
        inputs += [work / "main.ini", work / "run.mac"]
        argv = [str(self.exe), "--config", str(work / "main.ini"), "--macro", str(work / "run.mac"),
                "--output", str(work / "output"), "--threads", "1", "--seed", str(SEED)]
        env = os.environ.copy()
        env.pop("G4USIM_TEST_OUTPUT_FAULT", None)
        env["G4USIM_TEST_PRIMARY_VERTICES"] = str(work / "primaries.jsonl")
        record = {"name": name, "argv": argv, "cwd": str(work), "events": events,
                  "expected_failure": negative, "binary_sha256": self.digest,
                  "environment_overrides": {"G4USIM_TEST_PRIMARY_VERTICES": env["G4USIM_TEST_PRIMARY_VERTICES"], "G4USIM_TEST_OUTPUT_FAULT": None},
                  "inputs": {p.name: sha(p) for p in inputs}, "exit_code": None}
        save(work / "command.json", record)
        try:
            require(sha(self.exe) == self.digest, "binary changed before execution")
            with (work / "stdout.log").open("wb") as stdout, (work / "stderr.log").open("wb") as stderr:
                result = subprocess.run(argv, cwd=work, env=env, stdout=stdout, stderr=stderr, timeout=self.timeout)
            record["exit_code"] = result.returncode
            require(sha(self.exe) == self.digest, "binary changed during execution")
            require(all(sha(work / p) == digest for p, digest in record["inputs"].items()), "input bytes changed")
            log = (work / "stdout.log").read_text(encoding="utf-8", errors="replace") + (work / "stderr.log").read_text(encoding="utf-8", errors="replace")
            summary_path = work / "output/run_summary.txt"
            summary = dict(part.split(" = ", 1) for part in summary_path.read_text(encoding="utf-8").splitlines() if " = " in part) if summary_path.exists() else None
            record["summary"] = summary
            primary = [json.loads(s) for s in (work / "primaries.jsonl").read_text(encoding="utf-8").splitlines()] if (work / "primaries.jsonl").exists() else []
            record["primaries"] = primary
            trace_path=work/"primaries.jsonl.phase-state.jsonl"
            trace=[json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
            record["phase_state_trace"]=trace
            if negative:
                require(result.returncode != 0, f"{name}: invalid input accepted")
                require(not primary and not (work / "after.json").exists(), "failure generated primaries or executed later macro")
                require(f"line {line}" in log, "missing precise input line diagnostic")
                require("legacy-v1.csv" in log if name.startswith("cache_order") else "input.csv" in log, "missing failing input filename")
                if negative == "legacy":
                    require("legacy v1 ion has no actual charge" in log and "charge_eplus" in log, "wrong legacy ion refusal")
                    require(summary is not None, "runtime legacy rejection lacks summary")
                elif negative == "state":
                    require("PhaseSpace" in log and ("dynamic state" in log or "electron_occupancy" in log or "PrimaryTransformer" in log or "kinematics" in log or "construction sentinel" in log), "wrong dynamic state refusal")
                    require(summary is not None, "runtime state rejection lacks summary")
                else:
                    require("PhaseSpace" in log and any(t in log for t in ("invalid number", "columns", "header must", "dynamic mass", "electron_occupancy", "polarization")), "not a phase-space parse rejection")
                if summary is not None:
                    require(summary.get("status") == "failed" and int(summary.get("actual_completed_event_count", "-1")) == 0, "failure summary does not prove zero events")
                    require(int(summary.get("program_exit_code", "0")) != 0, "failed summary exit")
                # Configure-time parser exceptions may occur before any summary is initialized.
                record["summary_absence_reason"] = "configure-time rejection" if summary is None else None
                crossings = []
            else:
                require(result.returncode == 0 and summary is not None, f"{name}: expected native success: {log[-1500:]}")
                require(summary["status"] == "completed" and int(summary["actual_completed_event_count"]) == events and int(summary["planned_event_count"]) == events, "incomplete run")
                require(summary["run_count"] == "1" and summary["actual_threads"] == "1", "run/thread mismatch")
                require((work / "after.json").is_file(), "successful macro sentinel missing")
                require(primary and {int(p["event"]) for p in primary} == set(range(events)), "primary evidence incomplete")
                paths = list((work / "output").glob("phase_space_t*.csv"))
                require({p.name for p in paths} == {"phase_space_t0.csv"}, "wrong MT1 phase-space output set")
                with paths[0].open(encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    require(reader.fieldnames == HEADER, "writer did not append exact v3 dynamic state header")
                    crossings = list(reader)
                require(crossings, "no actual boundary records")
                for row in crossings:
                    require(set(row) == set(HEADER) and all(row[k] is not None for k in HEADER), "bad v3 row width")
                    require(math.isfinite(float(row["charge_eplus"])), "boundary charge is nonfinite")
                    close(row["x_mm"], 100 if record_at == "A" else 200, 0.001, "boundary plane")
                if name in ("legacy_electron", "legacy_v2_electron"):
                    require(("legacy v1 non-ion replay assumes particle-definition charge" if name == "legacy_electron" else "legacy v2 non-ion replay restores charge only") in log, "legacy assumption warning missing")
                    require(len(primary) == 1 and primary[0]["pdg"] == 11, "legacy primary identity")
                    close(primary[0]["charge_eplus"], -1, 1e-12, "legacy electron assumed charge")
                if name == "same_pdg_charges" or replay is not None:
                    require(all(p["charge_eplus"]==sys.float_info.max for p in primary), "v3 raw primary must honestly contain construction sentinel")
                    restored=[x for x in trace if x["stage"]=="dynamic_restored"]
                    first=[x for x in trace if x["stage"]=="first_step_pre"]
                    require(len(restored)==len(first)==len(primary), "actual restore/first-step trace incomplete")
                    index={(x["event"],x["input_line"]):x for x in restored}
                    require(len(index)==len(restored), "duplicate restored trace")
                    for x in first:
                        y=index[(x["event"],x["input_line"])]
                        require(x["primary_charge_eplus"]==sys.float_info.max and y["primary_charge_eplus"]==sys.float_info.max, "trace construction sentinel")
                        require(math.isfinite(x["actual_charge_eplus"]) and x["actual_charge_eplus"]==y["actual_charge_eplus"]==x["recorded_charge_eplus"]==y["recorded_charge_eplus"], "recorded/restored/true first-step charge differs")
                        require(x["mass_MeV"]==y["mass_MeV"] and math.isfinite(x["beta"]) and math.isfinite(y["beta"]), "first-step mass/beta")
                if name == "same_pdg_charges":
                    require(len(primary) == 3 and all(p["pdg"] == 1000060120 for p in primary), "same-PDG history incomplete")
                    ordered = sorted(primary, key=lambda p: p["vertex"])
                    require([x["actual_charge_eplus"] for x in sorted(restored,key=lambda x:x["input_line"])] == [2, 0, 5], "actual restored same-PDG / zero / isolation")
            if summary is not None:
                require(summary["source_fingerprint"] == self.source, "summary candidate identity mismatch")
                self.metadata(work, summary, not negative, record["inputs"])
            record["status"] = "pass"
            return work, crossings, primary
        except Exception as error:
            record.update(status="fail", error=repr(error))
            raise
        finally:
            record["artifacts"] = {p.relative_to(work).as_posix(): sha(p) for p in sorted(work.rglob("*")) if p.is_file() and p.name != "receipt.json"}
            save(work / "receipt.json", record)
            self.receipt["cases"].append(record)
            self.flush()

    def metadata(self, work, summary, positive, inputs):
        output = work / "output"
        metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
        require(metadata["provenance"]["build"]["source_fingerprint"] == self.source, "metadata source identity")
        for key in ("status", "actual_completed_event_count", "run_count"):
            require(metadata["values"][key] == summary[key], "summary/metadata disagreement")
        require(Path(summary["actual_output_dir"]).resolve() == output.resolve(), "wrong output root")
        found = set()
        for item in metadata["generated_files"]:
            path = Path(item["path"])
            require(path.resolve().is_relative_to(output.resolve()) and path not in found, "invalid artifact path/duplicate")
            found.add(path)
            require(path.is_file(), "registered output missing")
            if path.name != "run_metadata.json":
                require(sha(path) == item["sha256"] and path.stat().st_size == item["size_bytes"], "artifact drift")
            if path.name.startswith("phase_space"):
                require(item["schema"] == "phase_space_csv_v3", "metadata actual phase schema wrong")
        require(found == {p for p in output.rglob("*") if p.is_file()}, "output set not exactly registered")
        captured = {}
        for item in metadata["provenance"]["inputs"]:
            if item["status"] == "recorded":
                require(sha(Path(item["path"])) == item["sha256"], "input provenance hash drift")
                captured[Path(item["path"]).resolve()] = item["sha256"]
        if positive:
            require(all(captured.get((work / name).resolve()) == digest for name, digest in inputs.items()),
                    "successful inputs missing from actual read provenance")


def transport(trial):
    continuous, b, initial_b = trial.run("field_continuous_B", events=4, field=True)
    stage_a, a, initial_a = trial.run("field_record_A", events=4, field=True, record_at="A")
    stage_b, replay_b, primaries = trial.run("field_replay_A_to_B", events=4, field=True,
                                           replay=stage_a / "output/phase_space_t0.csv")
    for rows in (initial_a, initial_b):
        require(len(rows) == 4 and all(p["pdg"] == 1000060120 and p["charge_eplus"] == 2 for p in rows),
                "fixed source did not create C12 charge2 primaries")
    for label, rows in (("A", a), ("continuous B", b), ("replay B", replay_b)):
        require(len(rows) == 4 and {int(p["eventID"]) for p in rows} == set(range(4)), label + " incomplete/extra crossings")
        require(all(p["pdg"] == "1000060120" and p["parentID"] == "0" and p["trackID"] == "1" for p in rows), label + " changed particle/secondary")
        for p in rows:
            close(p["kineticEnergy_MeV"], 120, TOLERANCES["energy_MeV"], label + " vacuum energy")
    require(len(primaries) == 4, "replay primary count")
    # ReadHistories preserves physical CSV order, not sorted event IDs.
    for event, boundary in enumerate(a):
        primary = next(p for p in primaries if p["event"] == event)
        for old, new in (("x_mm", "x_mm"), ("y_mm", "y_mm"), ("z_mm", "z_mm"),
                         ("u", "u"), ("v", "v"), ("w", "w"), ("kineticEnergy_MeV", "energy_MeV")):
            close(boundary[old], primary[new], TOLERANCES["primary"], "actual A to primary " + old)
    actual_first=[json.loads(line) for line in (stage_b/"primaries.jsonl.phase-state.jsonl").read_text().splitlines() if json.loads(line)["stage"]=="first_step_pre"]
    for event,boundary in enumerate(a):
        first=next(x for x in actual_first if x["event"]==event)
        close(boundary["charge_eplus"],first["actual_charge_eplus"],TOLERANCES["primary"],"A to true first-step charge")
        close(boundary["dynamic_mass_MeV"],first["mass_MeV"],TOLERANCES["primary"],"A to true first-step mass")
    by_event = {int(p["eventID"]): p for p in b}
    maxima = {}
    for event, after in enumerate(sorted(replay_b, key=lambda p: int(p["eventID"]))):
        before = by_event[int(a[event]["eventID"])]
        for keys, tolerance in ((["x_mm", "y_mm", "z_mm"], TOLERANCES["position_mm"]),
                                (["u", "v", "w"], TOLERANCES["direction"]),
                                (["kineticEnergy_MeV"], TOLERANCES["energy_MeV"]),
                                (["time_ns"], TOLERANCES["time_ns"]),
                                (["charge_eplus"], TOLERANCES["charge_eplus"])):
            for key in keys:
                close(before[key], after[key], tolerance, "continuous/replay B " + key)
                maxima[key] = max(maxima.get(key, 0), abs(float(before[key])-float(after[key])))
        for key in ("dynamic_mass_MeV", "electron_occupancy", "magnetic_moment_MeV_per_T", "polarization_x", "polarization_y", "polarization_z"):
            require(before[key] == after[key], "continuous/replay dynamic state differs: " + key)
    require(all(abs(float(p["y_mm"])) > 0.1 and abs(float(p["v"])) > 0.001 for p in b), "magnetic deflection not observed")
    trial.receipt["transport_comparison"] = {"status": "pass", "max_absolute_differences": maxima,
        "A_charges": [p["charge_eplus"] for p in a], "B_charges": [p["charge_eplus"] for p in b],
        "scope": "fixed finite vacuum comparison, no constant ion charge assumption; no general material/charge exchange claim"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source-fingerprint")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--plan", action="store_true", help="Print fixed matrix/tolerances; no native process")
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({"cases": [x[0] for x in fixed_cases()] + ["field_continuous_B", "field_record_A", "field_replay_A_to_B"], "seed": SEED, "tolerances": TOLERANCES}, indent=2))
        return 0
    require(args.timeout > 0, "timeout must be positive")
    exe = Path(os.environ["G4USIM_EXE"]).resolve()
    evidence = Path(os.environ["G4USIM_TEST_EVIDENCE_DIR"]).resolve()
    require(exe.is_file(), "candidate backend missing")
    if not args.expected_source_fingerprint:
        from run_m0_tests import workspace_source_fingerprint
        args.expected_source_fingerprint = workspace_source_fingerprint()
    evidence.mkdir(parents=True, exist_ok=True)
    trial = Trial(Path(tempfile.mkdtemp(prefix="phase-charge-", dir=evidence)), exe, args.expected_source_fingerprint, args.timeout)
    try:
        for name, files, events, negative, line in fixed_cases():
            trial.run(name, files=files, events=events, negative=negative, line=line)
        transport(trial)
        require(len(trial.receipt["cases"]) == trial.receipt["planned_cases"], "matrix incomplete")
        require(sha(exe) == trial.digest, "final binary drift")
        require(sha(Path(__file__)) == trial.receipt["script_sha256"], "test script drift")
        for record in trial.receipt["cases"]:
            folder = Path(record["cwd"])
            require(json.loads((folder / "receipt.json").read_text(encoding="utf-8")) == record,
                    "case sidecar differs from aggregate")
            actual = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob("*")
                      if p.is_file() and p != folder / "receipt.json"}
            require(actual == record["artifacts"], "case artifact set or bytes changed during matrix")
        trial.receipt["status"] = "passed"
    except Exception as error:
        trial.receipt.update(status="failed", error=repr(error))
    trial.flush()
    print(f"Phase-space charge {trial.receipt['status']}; receipt={trial.root / 'receipt.json'}")
    return 0 if trial.receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
