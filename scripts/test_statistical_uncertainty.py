"""Real Geant4 regression for per-event statistical uncertainties (roadmap A3).

10 MeV protons cross a 200 um water slab (sensitive) in vacuum, 2 threads.
Checks:
  1. scorer_statistics.csv (master-merged) has edep / edep_volume / edep_particle /
     dose / fluence / LET rows with n_events = events of the run;
  2. independent recomputation from the raw hits CSV (per-event sums per thread)
     reproduces sum, sum_sq and rel_error of the edep and dose rows, and the event_edep
     CSV reproduces the edep total row;
  3. per-thread CSV sum_sq / n_events columns add up to the merged row, ROOT rows
     merged by scripts/g4usim_io.py reproduce every merged value and error, FOM = 1/(R^2 T);
  4. the reported errors are honest: over 20 independent runs of 100 events the
     observed run-to-run spread of dose, fluence, LET_t and LET_d agrees with the
     mean reported error within a factor 1.5, and the error of the pooled 20 x 100
     events is sqrt(20) times smaller (R ~ 1/sqrt(N));
  5. format = root still writes scorer_statistics.csv (no per-thread CSVs).
Requires uproot and numpy.
"""

from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
try:
    import numpy as np
    import uproot  # noqa: F401  (needed by g4usim_io)
except ImportError:
    print("SKIP: uproot/numpy is not installed")
    sys.exit(2)
sys.path.insert(0, str(ROOT / "scripts"))
import g4usim_io  # noqa: E402

MEV_IN_JOULES = 1.602176634e-13
GEOMETRY = """
[world]
size = 20 cm, 20 cm, 20 cm
material = G4_Galactic
[target]
name = WaterSlab
shape = box
size = 5 cm, 5 cm, 200 um
material = G4_WATER
position = 0 mm, 0 mm, 0 mm
sensitive = true
"""


def config(geometry: Path, fmt: str, hits: bool) -> str:
    return f"""
[run]
threads = 2
seed = 20261022
[output]
format = {fmt}
[materials]
file = {ROOT.as_posix()}/config/materials/material.ini
[geometry]
template = simple_box
config = {geometry.as_posix()}
[physics]
reference = FTFP_BERT_EMZ
default_cut = 10 um
[source]
particle = proton
energy = 10 MeV
position_type = point
position = 0,0,-5 cm
direction = 0,0,1
[scoring]
enabled = true
hits = {'true' if hits else 'false'}
event_edep = true
edep = true
let = true
dose = true
fluence = true
auto_create_default_scorers = true
[scoring.let]
particles = proton
"""


def run(work: Path, name: str, text: str, macro: str) -> Path:
    (work / f"{name}.ini").write_text(text, encoding="utf-8")
    (work / f"{name}.mac").write_text(macro, encoding="utf-8")
    output = work / name
    result = subprocess.run([str(EXE), "--config", str(work / f"{name}.ini"), "--macro", str(work / f"{name}.mac"),
                             "--output", str(output)], cwd=work, capture_output=True, text=True,
                            errors="replace", timeout=1200)
    assert result.returncode == 0, f"{name}:\n{(result.stdout + result.stderr)[-2500:]}"
    return output


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stats_table(path: Path) -> dict[tuple[str, str, str], dict[str, str]]:
    return {(r["scorer"], r["quantity"], r["key"]): r for r in read_csv(path)}


def close(a: float, b: float, label: str, rel: float = 1e-9) -> None:
    assert math.isclose(a, b, rel_tol=rel, abs_tol=1e-300), f"{label}: {a!r} != {b!r}"


def rel_error(total: float, sum_sq: float, n: int) -> float:
    return math.sqrt(max(sum_sq / total**2 - 1.0 / n, 0.0))


def thread_files(directory: Path, stem: str) -> list[tuple[int, Path]]:
    pattern = re.compile(rf"{stem}_t(\d+)\.csv$")
    return sorted((int(m.group(1)), p) for p in directory.glob(f"{stem}_t*.csv") if (m := pattern.fullmatch(p.name)))


def check_base(output: Path, events: int) -> None:
    table = stats_table(output / "scorer_statistics.csv")
    expected = {("edep", "raw_edep"), ("edep", "weighted_edep"), ("edep_volume", "raw_edep"),
                ("edep_particle", "raw_edep"), ("dose", "raw_dose"), ("dose", "weighted_dose"),
                ("fluence", "raw_fluence"), ("fluence", "weighted_fluence"), ("let", "let_t"), ("let", "let_d")}
    present = {(s, q) for s, q, _ in table}
    assert expected <= present, sorted(expected - present)
    assert all(int(r["n_events"]) == events for r in table.values())

    # 2. Independent recomputation from the raw hits.
    per_event: dict[tuple[int, int], float] = defaultdict(float)
    for thread, path in thread_files(output, "hits"):
        for row in read_csv(path):
            if row["volume"] == "WaterSlab_PV":
                per_event[(thread, int(row["eventID"]))] += float(row["edep_MeV"])
    total = sum(per_event.values())
    sum_sq = sum(x * x for x in per_event.values())
    volume_row = table[("edep_volume", "raw_edep", "WaterSlab_PV")]
    close(float(volume_row["sum"]), total, "edep_volume sum vs hits")
    close(float(volume_row["sum_sq"]), sum_sq, "edep_volume sum_sq vs hits")
    close(float(volume_row["rel_error"]), rel_error(total, sum_sq, events), "edep_volume rel_error vs hits", 1e-7)
    assert int(volume_row["entries"]) == sum(1 for x in per_event.values() if x != 0)

    event_values = [float(r["raw_edep_MeV"]) for _, p in thread_files(output, "event_edep") for r in read_csv(p)]
    assert len(event_values) == events
    total_row = table[("edep", "raw_edep", "total")]
    close(float(total_row["sum"]), sum(event_values), "edep total sum vs event_edep")
    close(float(total_row["sum_sq"]), sum(x * x for x in event_values), "edep total sum_sq vs event_edep")
    close(float(total_row["mean_per_event"]), sum(event_values) / events, "edep mean per event")

    dose_rows = [r for k, r in table.items() if k[0] == "dose" and k[1] == "raw_dose"]
    assert len(dose_rows) == 1
    dose = dose_rows[0]
    mass = float(read_csv(thread_files(output, "dose_volume_summary")[0][1])[0]["mass_kg"])
    close(float(dose["value"]), total * MEV_IN_JOULES / mass, "dose value vs hits")
    close(float(dose["rel_error"]), float(volume_row["rel_error"]), "dose rel_error = edep rel_error", 1e-7)
    close(float(dose["std_error"]), float(dose["value"]) * float(dose["rel_error"]), "dose std_error")
    print(f"hits recomputation: {len(per_event)} events with edep, edep={total:.4f} MeV, "
          f"R={float(volume_row['rel_error']):.5f}, dose={float(dose['value']):.4e} Gy")

    # 3. Per-thread CSV columns are additive and match the merged rows.
    for stem, key, sq, quantity in (("dose_volume_summary", "raw_edep_MeV", "raw_edep_sum_sq_MeV2", "raw_dose"),
                                    ("fluence_volume_summary", "raw_track_length_mm",
                                     "raw_track_length_sum_sq_mm2", "raw_fluence")):
        rows = [r for _, p in thread_files(output, stem) for r in read_csv(p)]
        assert sum(int(r["n_events"]) for r in rows) == events, stem
        merged = next(r for k, r in table.items() if k[0] == stem.split("_")[0] and k[1] == quantity)
        close(float(merged["rel_error"]),
              rel_error(sum(float(r[key]) for r in rows), sum(float(r[sq]) for r in rows), events), stem, 1e-7)
    for item in g4usim_io.load_scorer_statistics(output / "g4usim.root"):
        row = table[(item.scorer, item.quantity, item.key)]
        close(item.value, float(row["value"]), f"ROOT {item.scorer}/{item.quantity} value", 1e-8)
        close(item.rel_error, float(row["rel_error"]), f"ROOT {item.scorer}/{item.quantity} rel_error", 1e-6)
        assert item.n_events == events
    wall = float(dose["run_wall_time_s"])
    assert wall > 0
    close(float(dose["fom_per_s"]), 1.0 / (float(dose["rel_error"]) ** 2 * wall), "FOM", 1e-6)
    print("per-thread CSV, ROOT (g4usim_io) and merged statistics agree; FOM = 1/(R^2 T)")


def check_batches(output: Path, runs: int, events: int) -> None:
    quantities = [("dose", "raw_dose"), ("fluence", "raw_fluence"), ("let", "let_t"), ("let", "let_d")]
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    errors: dict[tuple[str, str], list[float]] = defaultdict(list)
    pooled: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for run_id in range(runs):
        name = "scorer_statistics.csv" if run_id == 0 else f"scorer_statistics_r{run_id}.csv"
        for (scorer, quantity, _), row in stats_table(output / name).items():
            if (scorer, quantity) in quantities:
                assert int(row["n_events"]) == events
                values[(scorer, quantity)].append(float(row["value"]))
                errors[(scorer, quantity)].append(float(row["rel_error"]))
                if row["estimator"] == "total":
                    pooled[(scorer, quantity)][0] += float(row["sum"])
                    pooled[(scorer, quantity)][1] += float(row["sum_sq"])
    for q in quantities:
        v = np.array(values[q])
        assert len(v) == runs, (q, len(v))
        observed = float(v.std(ddof=1) / v.mean())
        predicted = float(np.sqrt(np.mean(np.square(errors[q]))))
        ratio = observed / predicted
        print(f"{q[0]}/{q[1]}: observed run spread {observed:.5f}, reported R {predicted:.5f}, ratio {ratio:.3f}")
        assert 1 / 1.5 < ratio < 1.5, (q, observed, predicted)
        if q in pooled:
            total, sum_sq = pooled[q]
            scaling = predicted / rel_error(total, sum_sq, runs * events)
            print(f"  R(100 events) / R(pooled {runs * events}) = {scaling:.3f} (sqrt({runs}) = {math.sqrt(runs):.3f})")
            assert 0.75 * math.sqrt(runs) < scaling < 1.33 * math.sqrt(runs), (q, scaling)


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_stat_"))
    try:
        geometry = work / "slab.ini"
        geometry.write_text(GEOMETRY, encoding="utf-8")

        base_events = 400
        output = run(work, "base", config(geometry, "both", True), f"/run/initialize\n/run/beamOn {base_events}\n")
        check_base(output, base_events)

        runs, events = 20, 100
        output = run(work, "batches", config(geometry, "csv", False),
                     "/run/initialize\n" + f"/run/beamOn {events}\n" * runs)
        check_batches(output, runs, events)

        output = run(work, "root_only", config(geometry, "root", False), "/run/initialize\n/run/beamOn 50\n")
        assert (output / "scorer_statistics.csv").is_file()
        assert not list(output.glob("dose_volume_summary_t*.csv"))
        names = {(s, q) for s, q, _ in stats_table(output / "scorer_statistics.csv")}
        assert ("let", "let_t") in names and ("dose", "raw_dose") in names
        print("format = root: scorer_statistics.csv written, no per-thread CSVs")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_statistical_uncertainty: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
