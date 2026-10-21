"""Cross-check a G4UniversalSim ROOT file against the CSV files of the same run.

Requires `uproot` (pip install uproot). Run with output format `both`.

    python scripts/compare_root_csv.py --dir test/output/root_mt [--run 0]

Checks: event and hit row counts, total raw/weighted edep, edep histogram
entries and bin contents (summed over worker CSVs), per-volume and
per-particle edep summaries, and optional dose/fluence summaries.
Exits non-zero on the first mismatch.
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import os
import sys
from collections import defaultdict

try:
    import uproot
except ImportError:  # pragma: no cover - environment guard
    print("SKIP: uproot is not installed (pip install uproot)")
    sys.exit(2)

REL_TOL = 1e-9


def run_suffix(run: int) -> str:
    return "" if run == 0 else f"_r{run}"


def csv_files(directory: str, stem: str, run: int) -> list[str]:
    files = sorted(glob.glob(os.path.join(directory, f"{stem}_t*.csv")))
    suffix = run_suffix(run)
    selected = []
    for path in files:
        name = os.path.basename(path)[len(stem) + 2:-4]  # strip "<stem>_t" and ".csv"
        thread, _, rest = name.partition("_")
        if thread.isdigit() and ("_" + rest if rest else "") == suffix:
            selected.append(path)
    return selected


def read_rows(paths: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with open(path, newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def close(a: float, b: float, label: str) -> None:
    if not math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-12):
        raise AssertionError(f"{label}: ROOT={a!r} CSV={b!r}")


def check(directory: str, run: int) -> list[str]:
    root_path = os.path.join(directory, f"g4usim{run_suffix(run)}.root")
    report = []
    with uproot.open(root_path) as root:
        keys = {key.split(";")[0] for key in root.keys()}
        for required in ("hits", "events", "edep_volume", "edep_particle", "dose", "fluence",
                         "edep_raw", "edep_weighted"):
            if required not in keys:
                raise AssertionError(f"{root_path}: missing object '{required}' (have {sorted(keys)})")

        # Events ----------------------------------------------------------
        events = root["events"].arrays(library="np")
        csv_events = read_rows(csv_files(directory, "event_edep", run))
        if len(events["eventID"]) != len(csv_events):
            raise AssertionError(f"events rows: ROOT={len(events['eventID'])} CSV={len(csv_events)}")
        close(float(events["raw_edep_MeV"].sum()),
              sum(float(r["raw_edep_MeV"]) for r in csv_events), "total raw edep")
        close(float(events["weighted_edep_MeV"].sum()),
              sum(float(r["weighted_edep_MeV"]) for r in csv_events), "total weighted edep")
        if set(events["runID"].tolist()) != {run}:
            raise AssertionError(f"events runID values {set(events['runID'].tolist())} != {{{run}}}")
        report.append(f"events={len(csv_events)} edep_sum={events['raw_edep_MeV'].sum():.6g} MeV")

        # Hits ------------------------------------------------------------
        hits = root["hits"].arrays(["edep_MeV", "particle", "volume"], library="np")
        csv_hits = read_rows(csv_files(directory, "hits", run))
        if len(hits["edep_MeV"]) != len(csv_hits):
            raise AssertionError(f"hits rows: ROOT={len(hits['edep_MeV'])} CSV={len(csv_hits)}")
        close(float(hits["edep_MeV"].sum()), sum(float(r["edep_MeV"]) for r in csv_hits), "hits edep")
        if sorted(map(str, hits["particle"])) != sorted(r["particle"] for r in csv_hits):
            raise AssertionError("hits particle column differs")
        report.append(f"hits={len(csv_hits)}")

        # Histograms (merged in ROOT; summed over worker CSVs) -------------
        for name in ("edep_raw", "edep_weighted"):
            values = root[name].values(flow=False)
            bins: dict[int, float] = defaultdict(float)
            for row in read_rows(csv_files(directory, f"hist_{name}", run)):
                bins[int(row["bin"])] += float(row["count"])
            if len(values) != len(bins):
                raise AssertionError(f"{name}: ROOT bins={len(values)} CSV bins={len(bins)}")
            for index, value in enumerate(values):
                close(float(value), bins[index], f"{name} bin {index}")
            report.append(f"{name}: {len(values)} bins, {values.sum():.0f} in range")

        # Per-volume / per-particle summaries ------------------------------
        for stem, tree in (("edep_volume_summary", "edep_volume"), ("edep_particle_summary", "edep_particle")):
            data = root[tree].arrays(library="np")
            root_sum: dict[str, float] = defaultdict(float)
            for name, value in zip(data["name"], data["raw_edep_MeV"]):
                root_sum[str(name)] += float(value)
            csv_sum: dict[str, float] = defaultdict(float)
            for row in read_rows(csv_files(directory, stem, run)):
                csv_sum[row["name"]] += float(row["raw_edep_MeV"])
            if set(root_sum) != set(csv_sum):
                raise AssertionError(f"{tree} names: ROOT={sorted(root_sum)} CSV={sorted(csv_sum)}")
            for key in csv_sum:
                close(root_sum[key], csv_sum[key], f"{tree}[{key}]")
            report.append(f"{tree}: {len(csv_sum)} entries")

        # Dose / fluence (only present when those scorers are enabled) -----
        for stem, tree, column in (("dose_volume_summary", "dose", "raw_edep_MeV"),
                                   ("fluence_volume_summary", "fluence", "raw_track_length_mm")):
            data = root[tree].arrays(library="np")
            csv_rows = read_rows(csv_files(directory, stem, run))
            if len(data["runID"]) != len(csv_rows):
                raise AssertionError(f"{tree} rows: ROOT={len(data['runID'])} CSV={len(csv_rows)}")
            if csv_rows:
                close(float(data[column].sum()), sum(float(r[column]) for r in csv_rows), f"{tree} {column}")
                report.append(f"{tree}: {len(csv_rows)} rows")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", required=True, help="output directory of a run with format=both")
    parser.add_argument("--run", type=int, action="append", help="run ID(s) to check (default: all found)")
    args = parser.parse_args()

    runs = args.run
    if not runs:
        runs = []
        for path in glob.glob(os.path.join(args.dir, "g4usim*.root")):
            stem = os.path.basename(path)[:-5]
            runs.append(0 if stem == "g4usim" else int(stem.split("_r")[-1]))
        runs.sort()
    if not runs:
        print(f"FAIL: no g4usim*.root in {args.dir}")
        return 1
    for run in runs:
        try:
            report = check(args.dir, run)
        except AssertionError as error:
            print(f"FAIL run {run}: {error}")
            return 1
        print(f"OK run {run}: " + "; ".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
