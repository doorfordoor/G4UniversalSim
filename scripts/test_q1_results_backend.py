"""Real Q1 histories/ROOT evidence. Set G4USIM_EXE; --baseline labels old binaries."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
from collections import defaultdict
import numpy as np
import uproot
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "gui")]
import g4usim_io
from g4usim_gui.output import plot_data

HEADER = "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n"

def rows(path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run(exe, work, counts, *, threads=1, event_edep=True, particle="proton", weights=None, sparse=False):
    work.mkdir(parents=True, exist_ok=False)
    phase = HEADER
    for event, count in enumerate(counts):
        for track in range(count):
            x = 20 if sparse == "all" or sparse and event != 0 else 0
            weight = weights[event] if weights else 1
            phase += f"0,{event},{track+1},0,{particle},{2212 if particle == 'proton' else 0},{x},0,-2,0,0,1,100,0,{weight}\n"
    (work / "source.csv").write_text(phase, encoding="utf-8")
    (work / "geometry.ini").write_text("""[world]
size = 10 cm,10 cm,10 cm
material = G4_Galactic
[target]
name = Target
shape = box
size = 10 mm,10 mm,2 mm
material = G4_Si
position = 0,0,0 mm
sensitive = true
""", encoding="utf-8")
    (work / "main.ini").write_text(f"""[run]
threads = {threads}
seed = 4242
check_overlaps = false
[output]
format = both
[materials]
file = {(ROOT / 'config/materials/material.ini').as_posix()}
[geometry]
template = simple_box
config = {(work / 'geometry.ini').as_posix()}
[physics]
em = option4
[source]
phase_space_file = {(work / 'source.csv').as_posix()}
[scoring]
enabled = true
hits = true
event_edep = {'true' if event_edep else 'false'}
edep = true
dose = true
fluence = true
let = true
[scoring.let]
particles = proton
[scoring.mesh.m]
shape = box
size = 5 mm,5 mm,1 mm
bins = 1,1,2
center = 0,0,0 mm
[scoring.mesh.m.flux]
type = cellFlux
""", encoding="utf-8")
    (work / "run.mac").write_text(f"/run/initialize\n/run/beamOn {len(counts)}\n", encoding="utf-8")
    output = work / "output"
    result = subprocess.run([str(exe), "--config", str(work / "main.ini"), "--macro", str(work / "run.mac"),
                             "--output", str(output)], cwd=ROOT, capture_output=True, timeout=120)
    (work / "stdout.log").write_bytes(result.stdout)
    (work / "stderr.log").write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode(errors="replace")[-3000:]
    meta = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert meta["runs"][0]["completed_events"] == len(counts)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    executable = os.environ.get("G4USIM_EXE")
    assert executable, "Set G4USIM_EXE to the backend under test"
    exe = Path(executable).resolve()
    # Keep prior evidence intact and permit repeated full-suite runs.
    import uuid
    work = (args.work_dir or ROOT / "out/verification/q1-results-backend" / uuid.uuid4().hex).resolve()
    work.mkdir(parents=True, exist_ok=False)
    report = {"backend": str(exe), "binary_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "backend_scope": "baseline binary; Python candidate only" if args.baseline else "candidate binary",
              "checks": []}
    for label, counts in (("single", [1,1,1,1]), ("double", [2,2,2,2]), ("variable", [1,2,3,1])):
        output = run(exe, work / label, counts)
        primary = set()
        for path in output.glob("hits_t*.csv"):
            for row in rows(path):
                if int(row["parentID"]) == 0:
                    primary.add((int(row["eventID"]), int(row["trackID"])))
        assert [sum(event == i for event, _ in primary) for i in range(len(counts))] == counts
        checked = []
        for dataset in plot_data.discover(output):
            if dataset.kind != "scorer" or dataset.detail[0] not in {"edep_volume", "dose", "fluence"}:
                continue
            raw = plot_data.build_plot(output, dataset)
            per = plot_data.build_plot(output, dataset, normalization="per_event")
            assert np.allclose(per.series[0].y, raw.series[0].y / len(counts))
            assert per.ylabel.endswith(" / event")
            checked.append(dataset.detail[0])
        assert {"edep_volume", "dose", "fluence"} <= set(checked), checked
        report["checks"].append({"history_case": label, "events": len(counts), "primary_particles": len(primary)})
        # R10 evidence: ratio estimator is already independent of history count.
        lets = [d for d in plot_data.discover(output) if d.kind == "scorer" and d.detail[0] == "let"]
        assert lets
        raw = plot_data.build_plot(output, lets[0])
        try:
            plot_data.build_plot(output, lets[0], normalization="per_event")
        except ValueError as error:
            assert "ratio estimator" in str(error)
        else:
            assert False, "LET ratio was divided by N"
        report.setdefault("R10_ratio_rejected", []).append({"case":label,"backend_ratio":float(raw.series[0].y[0])})
    for enabled in (True, False):
        output = run(exe, work / f"sparse-{enabled}", [1]*32, threads=2, event_edep=enabled, sparse=True)
        with uproot.open(output / "g4usim.root") as root:
            data = root["edep_volume"].arrays(library="np")
            assert "events" in root
            event_rows=root["events"].num_entries
            assert event_rows==(32 if enabled else 0),event_rows
        workers = {int(t): int(n) for t,n in zip(data["threadID"],data["n_events"])}
        # Only event 0 crosses the target, so exactly one worker contributes.
        # Geant4 does not promise that the other worker receives any histories;
        # the contributing worker may legitimately own all 32 events (R31).
        worker_events=sum(workers.values())
        assert len(workers) == 1 and 1 <= worker_events <= 32, workers
        # Preserve a real, unmodified ROOT copy as explicit offline input. Even
        # an event ntuple and rows whose counter happens to equal 32 do not
        # establish a trustworthy completed-event denominator without metadata.
        offline=work/f"offline-root-{enabled}"
        offline.mkdir()
        offline_root=offline/"g4usim.root"
        shutil.copy2(output/"g4usim.root",offline_root)
        assert hashlib.sha256(offline_root.read_bytes()).digest()==hashlib.sha256((output/"g4usim.root").read_bytes()).digest()
        assert not (offline/"run_metadata.json").exists()
        try:
            g4usim_io.load_scorer_statistics(offline_root)
        except ValueError as error:
            assert "no reliable completed event count" in str(error),error
        else:
            assert False,"ROOT rows/event ntuples bypassed the metadata denominator requirement"
        values = g4usim_io.load_scorer_statistics(output / "g4usim.root")
        assert values and all(v.n_events == 32 for v in values)
        csv_stats = {(r["scorer"],r["quantity"],r["key"]):r for r in rows(output / "scorer_statistics.csv")}
        for value in values:
            ref = csv_stats[(value.scorer,value.quantity,value.key)]
            assert np.isclose(value.value,float(ref["value"]),rtol=1e-5)
            assert np.isclose(value.rel_error,float(ref["rel_error"]),rtol=1e-5)
        report["checks"].append({"sparse_worker": workers, "events":32, "event_edep":enabled,
            "contributing_worker_events":worker_events, "observed_sparse_denominator_gap":worker_events<32,
            "offline_root_without_metadata_rejected":True, "event_ntuple_rows":event_rows,
            "sparse_gap_numeric_counterexample":"deterministic test_q1_postprocessing fixture; no worker scheduling guarantee"})
    for enabled in (True, False):
        zero = run(exe, work / f"zero-{enabled}", [1]*8, threads=2, event_edep=enabled, sparse="all")
        assert g4usim_io.load_scorer_statistics(zero / "g4usim.root") == []
        report["checks"].append({"all_workers_zero":True,"event_edep":enabled,"events":8})
    output = run(exe, work / "covariance", [1]*4, particle="proton", weights=[1,2,3,4])
    meshset = next(d for d in plot_data.discover(output) if d.kind == "mesh")
    mesh = plot_data.load_mesh(output, meshset)
    profile = plot_data.mesh_profile(mesh, 0)
    # Each proton history crosses both equal cells; contribution is w/area.
    tracks = defaultdict(float)
    for path in output.glob("hits_t*.csv"):
        for row in rows(path):
            tracks[int(row["eventID"])] += float(row["stepLength_mm"]) * float(row["weight"])
    assert len(tracks) == 4, tracks
    # Cell volume=100 mm^3, default flux unit=cm^-2: length_mm * 100 / 100.
    event_totals = np.array([tracks[i] for i in range(4)])
    assert np.isclose(event_totals.sum(),mesh.value.sum(),rtol=1e-6)
    exact = np.sqrt(np.sum(event_totals**2) - event_totals.sum()**2/4)
    shown = float(np.sqrt((mesh.error**2).sum()))
    assert not np.isclose(shown,exact,rtol=.01), (shown,exact)
    assert profile.series[0].yerr is None
    report["R11_covariance_evidence"] = {"raw_event_weighted_lengths":dict(tracks),
        "mesh_sum":float(mesh.value.sum()), "displayed_error_independent_cells":shown,
        "event_recomputed_projection_error":float(exact)}
    (work / "report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print("test_q1_results_backend: OK (R10 rejected; R11 missing covariance marked unavailable)")


if __name__ == "__main__":
    main()
