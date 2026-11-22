"""Check the opt-in hierarchical touchable path in actual CSV and ROOT hits."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.output.provenance import output_evidence

LEGACY_COLUMNS = (
    "runID", "eventID", "trackID", "parentID", "particle", "edep_MeV", "ndep_MeV",
    "stepLength_mm", "x0_mm", "y0_mm", "z0_mm", "x1_mm", "y1_mm", "z1_mm",
    "px", "py", "pz", "kineticEnergy_MeV", "process", "volume", "weight",
)
GEOMETRY = """[world]
shape = box
size = 100 mm, 100 mm, 100 mm
material = G4_Galactic

[volume.Stack]
parent = world
shape = box
size = 20 mm, 20 mm, 4 mm
material = G4_Galactic

[volume.Carrier]
parent = Stack
shape = box
size = 20 mm, 20 mm, 2 mm
material = G4_Galactic
placement = replica
replica_axis = z
replica_count = 2
replica_width = 2 mm

[volume.Leaf]
parent = Carrier
shape = box
size = 10 mm, 10 mm, 0.1 mm
material = G4_Si
sensitive = true
"""
COUNTS = (7, 3)
PATHS = tuple(
    f"/world_PV#0/Stack_PV#0/Carrier_PV#{copy}/Leaf_PV#0" for copy in (0, 1)
)


def run(exe, work, name, *, setting="", hits=True, x=0):
    config = work / f"{name}.ini"
    config.write_text(f"""[run]
threads = 1
seed = 20261122
[output]
format = both
[geometry]
template = hierarchical
config = {work.joinpath('geometry.ini').as_posix()}
[physics]
reference = FTFP_BERT_EMZ
[source]
particle = proton
energy = 100 MeV
position_type = point
position = {x},0,-8 mm
direction = +z
[scoring]
enabled = true
hits = {str(hits).lower()}
{setting}
event_edep = true
dose = false
fluence = false
""", encoding="utf-8")
    dest = work / name
    macro = work / "run.mac"
    argv = [str(exe), "--config", str(config), "--macro", str(macro), "--output", str(dest)]
    proc = subprocess.run(argv, cwd=work, capture_output=True, timeout=240)
    (work / f"{name}.stdout.log").write_bytes(proc.stdout)
    (work / f"{name}.stderr.log").write_bytes(proc.stderr)
    (work / f"{name}.process.json").write_text(
        json.dumps({"argv": argv, "exit": proc.returncode}, indent=2) + "\n", encoding="utf-8")
    assert proc.returncode == 0, (name, proc.returncode, proc.stderr[-3000:])
    evidence = output_evidence(dest, fresh=True)
    assert evidence.status == "verified", dest
    assert evidence.document["values"]["status"] == "completed", dest
    assert [row["completed_events"] for row in evidence.document["runs"]] == list(COUNTS), dest
    return evidence


def hit_tables(evidence, run_id, uproot):
    suffix = f"_r{run_id}" if run_id else ""
    name = f"hits_t0{suffix}.csv"
    csv_path = evidence.root / name
    rows, columns, file_sha, schema = [], (), None, None
    if csv_path.exists():
        record = evidence.artifact(evidence.require(name))
        schema = record["schema"]
        with csv_path.open(newline="", encoding="utf-8") as handle:
            table = csv.DictReader(handle)
            rows = list(table)
            columns = tuple(table.fieldnames or ())
        file_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    root_path = evidence.require(f"g4usim{suffix}.root")
    with uproot.open(root_path) as root:
        if "hits" in root:
            hits = root["hits"]
            root_columns = tuple(hits.keys())
            select = [key for key in ("runID", "eventID", "trackID", "parentID", "particle", "volume", "z0_mm", "volume_path")
                      if key in root_columns]
            arrays = hits.arrays(select, library="np")
            assert "runID" in arrays, root_columns
            root_rows = [{key: str(arrays[key][i]) for key in select} for i in range(len(arrays["runID"]))]
        else:
            root_columns, root_rows = (), []
    return rows, columns, root_rows, root_columns, file_sha, schema


def row_counter(rows, with_path):
    keys = ("runID", "eventID", "trackID", "parentID", "particle", "volume")
    if with_path:
        keys += ("volume_path",)
    return Counter(tuple(row[key] for key in keys) for row in rows)


def check_hit_rows(rows, run_id, with_path):
    expected_events = set(range(COUNTS[run_id]))
    assert {int(row["runID"]) for row in rows} == {run_id}
    assert {int(row["eventID"]) for row in rows} == expected_events
    assert {row["volume"] for row in rows} == {"Leaf_PV"}
    if with_path:
        assert {row["volume_path"] for row in rows} == set(PATHS)
        for event in expected_events:
            primary = [row for row in rows if int(row["eventID"]) == event and row["trackID"] == "1"]
            assert {row["volume_path"] for row in primary} == set(PATHS), (run_id, event, primary)
        # Verify each ancestor copy with the independently known placement bounds.
        for row in rows:
            path = PATHS[0 if float(row["z0_mm"]) < 0 else 1]
            assert row["volume_path"] == path, row


def run_suite(exe, work, uproot, baseline):
    (work / "geometry.ini").write_text(GEOMETRY, encoding="utf-8")
    (work / "run.mac").write_text(
        "/run/initialize\n" + "".join(f"/run/beamOn {n}\n" for n in COUNTS), encoding="utf-8")
    cases = {
        "default": {},
        "disabled": {"setting": "hit_volume_path = false"},
        "enabled": {"setting": "hit_volume_path = true"},
        "hits-off": {"setting": "hit_volume_path = true", "hits": False},
        "beam-miss": {"setting": "hit_volume_path = true", "x": 15},
    }
    outcomes = {name: run(exe, work, name, **settings) for name, settings in cases.items()}
    check_outputs(work, outcomes, uproot, baseline)


def check_outputs(work, outcomes, uproot, baseline):
    proof = {"baseline_expected_missing": baseline, "expected_paths": PATHS, "runs": list(COUNTS), "cases": {}}
    for name, evidence in outcomes.items():
        proof["cases"][name] = {"execution_id": evidence.document["provenance"]["execution_id"],
                                 "metadata_sha256": evidence.manifest_digest, "runs": []}
        for run_id in range(len(COUNTS)):
            rows, columns, rrows, rcolumns, digest, schema = hit_tables(evidence, run_id, uproot)
            with_path = name == "enabled" and not baseline
            if name not in {"hits-off", "beam-miss"}:
                assert columns == LEGACY_COLUMNS + (("volume_path",) if with_path else ()), (name, columns)
                assert schema == ("hits_csv_v4" if with_path else "hits_csv_v3"), (name, schema)
                assert rcolumns == LEGACY_COLUMNS + ("threadID",) + (("volume_path",) if with_path else ()), rcolumns
                assert row_counter(rows, with_path) == row_counter(rrows, with_path), (name, run_id)
                check_hit_rows(rows, run_id, with_path)
                check_hit_rows(rrows, run_id, with_path)
                base = outcomes["default"]
                base_rows, _, _, _, base_sha, _ = hit_tables(base, run_id, uproot)
                if not with_path:
                    assert digest == base_sha, (name, run_id, digest, base_sha)
                else:
                    assert [tuple(row[key] for key in LEGACY_COLUMNS) for row in rows] == [
                        tuple(row[key] for key in LEGACY_COLUMNS) for row in base_rows
                    ], (name, run_id, "existing columns changed")
            else:
                assert not rows and not rrows, (name, rows, rrows)
                if columns:
                    assert columns == LEGACY_COLUMNS + (() if baseline else ("volume_path",)), (name, columns)
                    assert schema == ("hits_csv_v3" if baseline else "hits_csv_v4"), (name, schema)
                if rcolumns:
                    assert rcolumns == LEGACY_COLUMNS + ("threadID",) + (() if baseline else ("volume_path",)), rcolumns
            proof["cases"][name]["runs"].append({
                "run_id": run_id, "csv_schema": schema, "csv_columns": columns,
                "root_columns": rcolumns, "rows": len(rows), "csv_sha256": digest,
                "paths": dict(Counter(row["volume_path"] for row in rows if "volume_path" in row)),
            })
    (work / "READBACK.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(f"hit volume paths {'legacy baseline' if baseline else 'candidate'} verified: {work}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=os.environ.get("G4USIM_EXE"))
    parser.add_argument("--output", type=Path, default=os.environ.get("G4USIM_TEST_EVIDENCE_DIR"))
    parser.add_argument("--legacy-baseline", action="store_true", help="record a backend with no opt-in path support")
    args = parser.parse_args()
    if not args.exe or not args.exe.is_file():
        parser.error("supply --exe with an existing Geant4 backend")
    if not __debug__:
        parser.error("this regression requires Python assertions")
    import uproot

    if args.output:
        output = args.output.resolve()
        output.mkdir(parents=True)
        run_suite(args.exe.resolve(), output, uproot, args.legacy_baseline)
    else:
        with tempfile.TemporaryDirectory(prefix="g4usim-hit-path-") as folder:
            run_suite(args.exe.resolve(), Path(folder).resolve(), uproot, args.legacy_baseline)


if __name__ == "__main__":
    main()
