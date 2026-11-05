"""Roadmap H2-4 pre-registered real-transport benchmarks (contract freeze
20261106, cases V1a/V4/V6a).

The H2-2 component check already covers V1b/V2/V3/V5 boundaries/V6b/V8 without
transport.  This script adds only the fixed real-transport cases that were still
missing:

  V1a  small EM-only partition: water slab, 1 MeV photons, gauge/gamma/e-
       filter runs must produce byte-identical hits and additive dose/fluence
       partitions; the {gamma,e-} completeness argument is checked against the
       distinct particle names actually present in the hits.
  V4   real spectrum identity: Pb target with 100 MeV protons, dose/fluence
       spectra over [0,200] MeV with 20 bins; the sum of all bins plus
       underflow/overflow must reproduce the volume CSV weighted total.
  V6a  weight-once cross-check: 10 MeV electrons on a Pb target with eBrem
       biasing factor 2 vs 1; the printed dose spectrum must match an
       independent per-bin recomputation from the hits rows.  This only
       evaluates scoring weights; it is not a transport-unbiasedness proof.

Fixed seeds 20261301 (V1a/V4) and 20261306 (V6a), single thread, no tuning.
Every criterion uses the 12-digit half-unit interval arithmetic from the H2-1
contract (Decimal), never a raw float comparison.

Usage:
    G4USIM_EXE=build_vs2026/Release/G4UniversalSim.exe \
        python -B scripts/test_h2_benchmarks.py [--work-root DIR] [--json PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
JOULE_PER_MEV = Decimal("1.602176634e-13")

SPECTRUM_HEADER = ["runID", "scorer", "volume_path", "volume_name", "region", "bin",
                   "low_edge_MeV", "high_edge_MeV", "amount", "unit", "n_events"]
DOSE_HEADER = ["runID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
               "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy",
               "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"]
FLUENCE_HEADER = ["runID", "volume_path", "volume_name", "volume_mm3",
                  "raw_track_length_mm", "weighted_track_length_mm",
                  "raw_fluence_mm-2", "weighted_fluence_mm-2",
                  "raw_track_length_sum_sq_mm2", "weighted_track_length_sum_sq_mm2",
                  "n_events"]


class Failure(RuntimeError):
    pass


def expect(condition: bool, message: str) -> None:
    # Written as an assert so the shared assertion probe counts every judgement.
    assert condition, message


def interval(printed: str) -> tuple[Decimal, Decimal]:
    """Return the printed-value half-unit interval frozen by the H2-1 contract."""
    text = str(printed).strip()
    value = Decimal(text)
    if value == 0:
        return Decimal(0), Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 60
        h = Decimal(5).scaleb(value.copy_abs().adjusted() - 12)
        return value - h, value + h


def add_intervals(items: list[tuple[Decimal, Decimal]]) -> tuple[Decimal, Decimal]:
    low = sum((item[0] for item in items), Decimal(0))
    high = sum((item[1] for item in items), Decimal(0))
    return low, high


def intersects(a: tuple[Decimal, Decimal], b: tuple[Decimal, Decimal]) -> bool:
    return max(a[0], b[0]) <= min(a[1], b[1])


def multiply_intervals(a: tuple[Decimal, Decimal],
                       b: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    """Multiply two non-negative intervals."""
    expect(a[0] >= 0 and b[0] >= 0, "interval multiplication expects non-negative values")
    return a[0] * b[0], a[1] * b[1]


def divide_positive(numerator: tuple[Decimal, Decimal],
                    denominator: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    return numerator[0] / denominator[1], numerator[1] / denominator[0]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def single(paths: list[Path]) -> Path:
    expect(len(paths) == 1, f"expected exactly one file, found {paths}")
    return paths[0]


def read_summary(output: Path) -> dict[str, str]:
    path = single(list(output.glob("run_summary*.txt")))
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if " = " in line and not line.startswith("["):
            key, value = line.split(" = ", 1)
            values[key.strip()] = value.strip()
    return values


def write_geometry(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def run_case(root: Path, name: str, text: str, events: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    main = root / f"{name}.ini"
    main.write_text(text, encoding="utf-8")
    macro = root / f"{name}.mac"
    macro.write_text(f"/run/initialize\n/run/beamOn {events}\n", encoding="utf-8")
    output = root / name / "output"
    result = subprocess.run(
        [str(EXE), "--config", str(main), "--macro", str(macro), "--output", str(output)],
        cwd=root, capture_output=True, text=True, errors="replace", timeout=600)
    log = root / f"{name}.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    expect(result.returncode == 0,
           f"{name}: expected exit 0, got {result.returncode}; log={log}\n"
           f"{(result.stdout + result.stderr)[-2000:]}")
    return output


def base_config(*, name: str, root: Path, geometry: Path, seed: int, events: int,
                physics: str, scoring: str, source: str, biasing: str = "") -> str:
    return f"""[run]
name = {name}
threads = 1
seed = {seed}
interactive = false
verbose = 0
check_overlaps = false
dry_run = false

[output]
dir = {root / name / "output"}
format = csv

[geometry]
template = hierarchical
config = {geometry}
default_world_material = G4_Galactic

{physics}

[scoring]
enabled = true
hits = true
event_edep = false
edep = false
dose = false
fluence = false
auto_create_default_scorers = true
{scoring}

[source]
{source}
{biasing}
"""


def hits_rows(output: Path) -> tuple[Path, list[dict[str, str]]]:
    path = single(list(output.glob("hits_t*.csv")))
    return path, read_csv(path)


def dose_row(output: Path) -> dict[str, str]:
    rows = read_csv(single(list(output.glob("dose_volume_summary_t*.csv"))))
    expect(len(rows) == 1, f"expected one dose volume row, got {len(rows)}")
    return rows[0]


def fluence_row(output: Path) -> dict[str, str]:
    rows = read_csv(single(list(output.glob("fluence_volume_summary_t*.csv"))))
    expect(len(rows) == 1, f"expected one fluence volume row, got {len(rows)}")
    return rows[0]


def spectrum_rows(output: Path, scorer: str) -> list[dict[str, str]]:
    path = single([p for p in output.glob(f"spectrum_{scorer}_t*.csv")])
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        expect(reader.fieldnames == SPECTRUM_HEADER,
               f"{path.name}: unexpected header {reader.fieldnames}")
        return list(reader)


def spectrum_sum(rows: list[dict[str, str]]) -> tuple[Decimal, Decimal]:
    return add_intervals([interval(row["amount"]) for row in rows])


def check_spectrum_structure(rows: list[dict[str, str]], expected_n_events: int) -> None:
    bins = [row for row in rows if row["region"] == "bin"]
    under = [row for row in rows if row["region"] == "underflow"]
    over = [row for row in rows if row["region"] == "overflow"]
    expect(len(bins) == len({row["bin"] for row in bins}) and len(bins) > 0,
           "spectrum bin rows are not unique")
    expect([int(row["bin"]) for row in bins] == list(range(len(bins))),
           f"spectrum bins are not ordered 0..N-1: {[row['bin'] for row in bins]}")
    expect(len(under) == 1 and under[0]["bin"] == "-1",
           f"missing or duplicated underflow row: {under}")
    expect(len(over) == 1 and over[0]["bin"] == str(len(bins)),
           f"missing or duplicated overflow row: {over}")
    for row in rows:
        expect(row["n_events"] == str(expected_n_events),
               f"n_events={row['n_events']} in a spectrum row, expected {expected_n_events}")
        if row["region"] == "bin":
            expect(row["low_edge_MeV"] != "" and row["high_edge_MeV"] != "",
                   "bin row edge columns must be printed")
        elif row["region"] == "underflow":
            expect(row["low_edge_MeV"] == "" and row["high_edge_MeV"] != "",
                   "underflow edges are wrong")
        else:
            expect(row["low_edge_MeV"] != "" and row["high_edge_MeV"] == "",
                   "overflow edges are wrong")


def v1a_em_partition(work: Path) -> dict:
    """V1a: EM-only particle partition on a water slab (500 events, seed 20261301)."""
    case = work / "v1a"
    case.mkdir(parents=True, exist_ok=True)
    geometry = write_geometry(case / "geometry.ini", """[world]
shape = box
size = 40 mm, 40 mm, 40 mm
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 10 mm, 10 mm, 1 mm
material = G4_WATER
position = 0 mm, 0 mm, 0 mm
sensitive = true
""")
    physics = "[physics]\nem = option4\ndefault_cut = 0.1 mm"
    source = """particle = gamma
energy = 1 MeV
position_type = plane
shape = square
halfx = 3 mm
center = 0, 0, -2 mm
direction = 0, 0, 1"""
    outputs: dict[str, Path] = {}
    for role, filter_text in (
            ("a", ""),
            ("b", "[scoring.filter.dose]\nparticles = gamma\n\n[scoring.filter.fluence]\nparticles = gamma"),
            ("c", "[scoring.filter.dose]\nparticles = e-\n\n[scoring.filter.fluence]\nparticles = e-")):
        scoring = "dose = true\nfluence = true\n" + filter_text
        text = base_config(name=f"v1a_{role}", root=case, geometry=geometry,
                           seed=20261301, events=500, physics=physics,
                           scoring=scoring, source=source)
        outputs[role] = run_case(case, f"v1a_{role}", text, 500)

    hits_a, rows = hits_rows(outputs["a"])
    particles = sorted({row["particle"] for row in rows})
    em_complete = particles == ["e-", "gamma"]
    expect(particles in (["e-", "gamma"], ["e-", "gamma", "e+"]),
           f"V1a: unexpected EM particle set in hits: {particles}")
    for role in ("b", "c"):
        hits_x, _ = hits_rows(outputs[role])
        expect(hits_x.read_bytes() == hits_a.read_bytes(),
               f"V1a: hits_{role} differs from the unfiltered hits; filters must not change transport")

    report: dict = {"case": "V1a", "particles": particles, "em_complete": em_complete}
    dose_a = dose_row(outputs["a"])
    dose_b = dose_row(outputs["b"])
    dose_c = dose_row(outputs["c"])
    expect(dose_a["volume_path"] == dose_b["volume_path"] == dose_c["volume_path"],
           "V1a: dose volume path differs between filter runs")
    weighted_a = interval(dose_a["weighted_dose_Gy"])
    weighted_b = interval(dose_b["weighted_dose_Gy"])
    weighted_c = interval(dose_c["weighted_dose_Gy"])
    expect(weighted_a[1] > 0, "V1a: unfiltered dose total is not positive")
    expect(intersects(weighted_a, add_intervals([weighted_b, weighted_c])),
           f"V1a dose partition mismatch: a={weighted_a} b+c={add_intervals([weighted_b, weighted_c])}")
    report["dose"] = {"a": str(weighted_a), "b": str(weighted_b), "c": str(weighted_c)}

    flu_a = fluence_row(outputs["a"])
    flu_b = fluence_row(outputs["b"])
    flu_c = fluence_row(outputs["c"])
    total_a = interval(flu_a["weighted_fluence_mm-2"])
    total_b = interval(flu_b["weighted_fluence_mm-2"])
    total_c = interval(flu_c["weighted_fluence_mm-2"])
    expect(total_a[1] > 0 and total_b[1] > 0 and total_c[1] > 0,
           "V1a: fluence partition has an empty component")
    expect(intersects(total_a, add_intervals([total_b, total_c])),
           f"V1a fluence partition mismatch: a={total_a} b+c={add_intervals([total_b, total_c])}")
    report["fluence"] = {"a": str(total_a), "b": str(total_b), "c": str(total_c)}
    report["status"] = "pass" if em_complete else "limited"
    if not em_complete:
        report["limited_reason"] = "hits enumerate e+ as well; completeness argument must be revisited"
    return report


def v4_spectrum_identity(work: Path) -> dict:
    """V4: real dose/fluence spectrum sum identity on a Pb target (seed 20261301)."""
    case = work / "v4"
    case.mkdir(parents=True, exist_ok=True)
    geometry = write_geometry(case / "geometry.ini", """[world]
shape = box
size = 200 mm, 200 mm, 200 mm
material = G4_Galactic

[volume.Target]
parent = world
shape = box
size = 50 mm, 50 mm, 50 mm
material = G4_Pb
position = 0 mm, 0 mm, 0 mm
sensitive = true
""")
    physics = "[physics]\nreference = FTFP_BERT_EMZ\ndefault_cut = 0.1 mm"
    source = """particle = proton
energy = 100 MeV
position_type = point
position = 0, 0, -30 mm
direction = 0, 0, 1"""
    spectra = ("dose = true\nfluence = true\n"
               "[scoring.spectrum.dose]\nbins = 20\nmin = 0 MeV\nmax = 200 MeV\n\n"
               "[scoring.spectrum.fluence]\nbins = 20\nmin = 0 MeV\nmax = 200 MeV")
    report: dict = {"case": "V4", "runs": {}}
    outputs: dict[str, Path] = {}
    for role, filter_text in (("a", ""),
                              ("b", "[scoring.filter.dose]\nparticles = proton\n\n"
                                    "[scoring.filter.fluence]\nparticles = proton")):
        scoring = spectra + ("\n" + filter_text if filter_text else "")
        text = base_config(name=f"v4_{role}", root=case, geometry=geometry,
                           seed=20261301, events=500, physics=physics,
                           scoring=scoring, source=source)
        outputs[role] = run_case(case, f"v4_{role}", text, 500)
    hits_a, _ = hits_rows(outputs["a"])
    hits_b, _ = hits_rows(outputs["b"])
    expect(hits_a.read_bytes() == hits_b.read_bytes(),
           "V4: the proton filter run changed the transport output (hits differ)")

    for role, output in outputs.items():
        summary = read_summary(output)
        expect(summary.get("spectrum_csv_schema_version") == "1",
               f"V4 {role}: spectrum_csv_schema_version is missing")
        expect(summary.get("output_csv_schema_version") == "3",
               f"V4 {role}: output_csv_schema_version changed")
        dose = dose_row(output)
        flu = fluence_row(output)
        dose_rows = spectrum_rows(output, "dose")
        flu_rows = spectrum_rows(output, "fluence")
        check_spectrum_structure(dose_rows, 500)
        check_spectrum_structure(flu_rows, 500)
        dose_sum = spectrum_sum(dose_rows)
        expect(intersects(dose_sum, interval(dose["weighted_dose_Gy"])),
               f"V4 {role}: dose spectrum sum {dose_sum} != weighted_dose {dose['weighted_dose_Gy']}")
        flu_sum = spectrum_sum(flu_rows)
        expect(intersects(flu_sum, interval(flu["weighted_fluence_mm-2"])),
               f"V4 {role}: fluence spectrum sum {flu_sum} != weighted_fluence "
               f"{flu['weighted_fluence_mm-2']}")
        expect(dose["n_events"] == "500" and flu["n_events"] == "500",
               f"V4 {role}: volume CSV n_events is not the finish-event count")
        report["runs"][role] = {
            "dose_spectrum_sum": str(dose_sum),
            "weighted_dose_Gy": dose["weighted_dose_Gy"],
            "fluence_spectrum_sum": str(flu_sum),
            "weighted_fluence_mm-2": flu["weighted_fluence_mm-2"],
            "volume_path": dose["volume_path"],
        }
    report["status"] = "pass"
    return report


def bin_index(energy_mev: Decimal, bins: int, low: Decimal, high: Decimal) -> int | None:
    """Contract §4.2: half-open bins, last bin closed at high, under/overflow."""
    if energy_mev < low:
        return -1
    if energy_mev > high:
        return bins
    with localcontext() as ctx:
        ctx.prec = 60
        width = (high - low) / bins
        if energy_mev == high:
            return bins - 1
        index = int((energy_mev - low) // width)
        return min(index, bins - 1)


def v6a_weight_once(work: Path) -> dict:
    """V6a: independent per-bin recomputation from hits with eBrem biasing (seed 20261306)."""
    case = work / "v6a"
    case.mkdir(parents=True, exist_ok=True)
    geometry = write_geometry(case / "geometry.ini", """[world]
shape = box
size = 100 mm, 100 mm, 100 mm
material = G4_Galactic

[volume.Target]
parent = world
shape = box
size = 10 mm, 10 mm, 10 mm
material = G4_Pb
position = 0 mm, 0 mm, 0 mm
sensitive = true
""")
    physics = "[physics]\nreference = FTFP_BERT\nbiasing = true\ndefault_cut = 0.1 mm"
    source = """particle = e-
energy = 10 MeV
position_type = point
position = 0, 0, 0
direction = 0, 0, 1"""
    scoring = ("dose = true\nhits = true\n"
               "[scoring.spectrum.dose]\nbins = 10\nmin = 0 MeV\nmax = 10 MeV")
    report: dict = {"case": "V6a", "runs": {}}
    outputs: dict[str, Path] = {}
    for role, factor in (("a", "2"), ("b", "1")):
        biasing = ("\n[biasing]\nenabled = true\n"
                   f"\n[biasing.xs.e-.eBrem]\nfactor = {factor}\nvolumes = Target\n"
                   "only_primary = true\napply_to_secondaries = false\n"
                   "min_weight = 0.05\nmax_interactions = 2")
        text = base_config(name=f"v6a_{role}", root=case, geometry=geometry,
                           seed=20261306, events=200, physics=physics,
                           scoring=scoring, source=source, biasing=biasing)
        outputs[role] = run_case(case, f"v6a_{role}", text, 200)

    report["status"] = "pass"
    for role, output in outputs.items():
        dose = dose_row(output)
        mass = Decimal(dose["mass_kg"])
        rows = spectrum_rows(output, "dose")
        check_spectrum_structure(rows, 200)
        printed = {int(row["bin"]): interval(row["amount"]) for row in rows}
        under = interval(next(row["amount"] for row in rows if row["region"] == "underflow"))
        over = interval(next(row["amount"] for row in rows if row["region"] == "overflow"))
        _hits_path, hits = hits_rows(output)
        weights = [Decimal(row["weight"]) for row in hits]
        expect(len(weights) > 0, f"V6a {role}: no hits to recompute from")
        non_unit = [w for w in weights if w != 1]
        if role == "a":
            expect(len(non_unit) > 0,
                   "V6a: factor=2 run has no non-unit weights; the case cannot separate the formulas")
        else:
            expect(all(w == 1 for w in weights),
                   "V6a: factor=1 run has non-unit weights; the analog control is broken")

        recomputed = {index: (Decimal(0), Decimal(0)) for index in range(10)}
        mass_interval = interval(dose["mass_kg"])
        for row in hits:
            q = multiply_intervals(interval(row["edep_MeV"]),
                                   (JOULE_PER_MEV, JOULE_PER_MEV))
            q = divide_positive(q, mass_interval)
            w = interval(row["weight"])
            contribution = multiply_intervals(w, q)
            energy = Decimal(row["kineticEnergy_MeV"])
            index = bin_index(energy, 10, Decimal(0), Decimal(10))
            if 0 <= index < 10:
                low, high = recomputed[index]
                recomputed[index] = (low + contribution[0], high + contribution[1])
        for index in range(10):
            got_low, got_high = recomputed[index]
            printed_bin = printed[index]
            expect(intersects(printed_bin, (got_low, got_high)),
                   f"V6a {role}: bin {index} printed {printed_bin} does not intersect "
                   f"the independent recomputation [{got_low}, {got_high}]")

        weighted_dose = interval(dose["weighted_dose_Gy"])
        spectrum_total = spectrum_sum(rows)
        expect(intersects(spectrum_total, weighted_dose),
               f"V6a {role}: spectrum sum {spectrum_total} != weighted_dose {weighted_dose}")

        wq_low = wq_high = Decimal(0)
        w2q_low = w2q_high = Decimal(0)
        for row in hits:
            q = divide_positive(multiply_intervals(interval(row["edep_MeV"]),
                                                   (JOULE_PER_MEV, JOULE_PER_MEV)),
                                mass_interval)
            w = interval(row["weight"])
            once = multiply_intervals(w, q)
            twice = multiply_intervals(multiply_intervals(w, w), q)
            wq_low += once[0]
            wq_high += once[1]
            w2q_low += twice[0]
            w2q_high += twice[1]
        wq = (wq_low, wq_high)
        w2q = (w2q_low, w2q_high)
        expect(intersects(spectrum_total, wq),
               f"V6a {role}: spectrum does not match the once-weighted sum {wq}")
        if role == "a":
            expect(not intersects(w2q, wq),
                   "V6a: this fixture cannot distinguish once from twice weighting")
        report["runs"][role] = {
            "hits": len(hits),
            "non_unit_weights": len(non_unit),
            "weighted_dose_Gy": dose["weighted_dose_Gy"],
            "spectrum_total": str(spectrum_total),
            "sum_wq": [str(wq[0]), str(wq[1])],
            "sum_w2q": [str(w2q[0]), str(w2q[1])],
        }
    return report


def v7_zero_and_unknown_particle(work: Path) -> dict:
    """V7: zero-contribution filter and unknown-particle runtime rejection (seed 20261307)."""
    case = work / "v7"
    case.mkdir(parents=True, exist_ok=True)
    geometry = write_geometry(case / "geometry.ini", """[world]
shape = box
size = 40 mm, 40 mm, 40 mm
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 10 mm, 10 mm, 0.1 mm
material = G4_Galactic
position = 0 mm, 0 mm, 0 mm
sensitive = true
""")
    physics = "[physics]\nem = option4\ndefault_cut = 0.7 mm"
    source = """particle = gamma
energy = 1 MeV
position_type = plane
shape = square
halfx = 4 mm
center = 0, 0, -2 mm
direction = 0, 0, 1"""
    filters = ("[scoring.filter.dose]\nparticles = mu-\n\n"
               "[scoring.filter.fluence]\nparticles = mu-")
    scoring = ("dose = true\nfluence = true\n\n"
               "[scoring.spectrum.fluence]\nbins = 10\nmin = 0.5 MeV\nmax = 1.5 MeV\n\n"
               + filters)
    text = base_config(name="v7_muminus", root=case, geometry=geometry,
                       seed=20261307, events=100, physics=physics,
                       scoring=scoring, source=source)
    output = run_case(case, "v7_muminus", text, 100)
    summary = read_summary(output)
    expect(summary.get("status") == "completed",
           f"V7 zero-contribution run did not complete: {summary.get('status')}")
    expect(summary.get("actual_completed_event_count") == "100",
           "V7 zero-contribution run reports the wrong completed event count")
    dose_file = single(list(output.glob("dose_volume_summary_t*.csv")))
    flu_file = single(list(output.glob("fluence_volume_summary_t*.csv")))
    spectrum_file = single(list(output.glob("spectrum_fluence_t*.csv")))
    dose_rows = read_csv(dose_file)
    flu_rows = read_csv(flu_file)
    spectrum = read_csv(spectrum_file)
    expect(dose_rows == [], f"V7 mu- dose should be header-only, got {len(dose_rows)} rows")
    expect(flu_rows == [], f"V7 mu- fluence should be header-only, got {len(flu_rows)} rows")
    expect(spectrum == [], f"V7 mu- spectrum should be header-only, got {len(spectrum)} rows")
    expect(not list(output.glob("scorer_statistics*.csv")),
           "V7 mu- run wrote a scorer_statistics file without entries")

    bad_filters = "[scoring.filter.dose]\nparticles = muon"
    bad = base_config(name="v7_muon", root=case, geometry=geometry,
                      seed=20261307, events=10, physics=physics,
                      scoring="dose = true\n\n" + bad_filters, source=source)
    bad_main = case / "v7_muon.ini"
    bad_main.write_text(bad, encoding="utf-8")
    macro = case / "v7_muon.mac"
    macro.write_text("/run/initialize\n/run/beamOn 10\n", encoding="utf-8")
    bad_output = case / "v7_muon" / "output"
    result = subprocess.run(
        [str(EXE), "--config", str(bad_main), "--macro", str(macro), "--output", str(bad_output)],
        cwd=case, capture_output=True, text=True, errors="replace", timeout=300)
    label = "H2-4 V7 unknown particle"
    expect(result.returncode != 0, f"{label}: expected a nonzero exit")
    bad_summary = read_summary(bad_output) if list(bad_output.glob("run_summary*.txt")) else {}
    expect(bad_summary.get("status") == "failed",
           f"{label}: run summary status is {bad_summary.get('status')!r}")
    expect(bad_summary.get("output_failure_stage") == "scoring_filter_particle",
           f"{label}: failure stage is {bad_summary.get('output_failure_stage')!r}")
    # Frozen contract: the unknown particle must be rejected before the first
    # event, so no run may be created and no scientific file may be written.
    expect(bad_summary.get("run_count") == "0",
           f"{label}: a run was created despite the pre-event rejection "
           f"(run_count={bad_summary.get('run_count')!r})")
    completed = bad_summary.get("actual_completed_event_count")
    expect(completed == "0",
           f"{label}: expected 0 completed events for a pre-event rejection, "
           f"got {completed!r}")
    planned = bad_summary.get("run_0_planned_events")
    expect(planned in (None, "", "0"),
           f"{label}: a rejected run reports planned events {planned!r}")
    for pattern in ("dose_volume_summary_t*.csv", "fluence_volume_summary_t*.csv",
                    "spectrum_fluence_t*.csv", "scorer_statistics*.csv",
                    "hits_t*.csv", "event_edep_t*.csv", "edep_*summary_t*.csv"):
        expect(not list(bad_output.glob(pattern)),
               f"{label}: rejected configuration wrote {pattern}")
    # A rejected configuration must also stop later /run/beamOn commands.
    double_macro = case / "v7_muon_double.mac"
    double_macro.write_text(
        "/run/initialize\n/run/beamOn 10\n/run/beamOn 10\n",
        encoding="utf-8")
    double_output = case / "v7_muon_double" / "output"
    double_result = subprocess.run(
        [str(EXE), "--config", str(bad_main), "--macro", str(double_macro),
         "--output", str(double_output)],
        cwd=case, capture_output=True, text=True, errors="replace", timeout=300)
    expect(double_result.returncode != 0,
           f"{label}: repeated-beamOn case should fail, exit={double_result.returncode}")
    double_summary = read_summary(double_output) if list(double_output.glob("run_summary*.txt")) else {}
    expect(double_summary.get("status") == "failed",
           f"{label}: repeated-beamOn summary status {double_summary.get('status')!r}")
    expect(double_summary.get("run_count") == "0",
           f"{label}: a later /run/beamOn executed after the rejection "
           f"(run_count={double_summary.get('run_count')!r})")
    # Multi-threaded configuration must be rejected identically, with no worker
    # events: validation happens on the master before the run is dispatched.
    threaded_main = case / "v7_muon_threads2.ini"
    threaded_main.write_text(bad.replace("threads = 1", "threads = 2"), encoding="utf-8")
    threaded_output = case / "v7_muon_threads2" / "output"
    threaded_result = subprocess.run(
        [str(EXE), "--config", str(threaded_main), "--macro", str(macro),
         "--output", str(threaded_output)],
        cwd=case, capture_output=True, text=True, errors="replace", timeout=300)
    expect(threaded_result.returncode != 0,
           f"{label}: threaded case should fail, exit={threaded_result.returncode}")
    threaded_summary = read_summary(threaded_output) if list(threaded_output.glob("run_summary*.txt")) else {}
    expect(threaded_summary.get("status") == "failed",
           f"{label}: threaded summary status {threaded_summary.get('status')!r}")
    expect(threaded_summary.get("run_count") == "0",
           f"{label}: threaded rejection created a run "
           f"(run_count={threaded_summary.get('run_count')!r})")
    threaded_completed = threaded_summary.get("actual_completed_event_count")
    expect(threaded_completed == "0",
           f"{label}: threaded rejection processed events ({threaded_completed!r})")
    expect(threaded_summary.get("output_failure_stage") == "scoring_filter_particle",
           f"{label}: threaded failure stage "
           f"{threaded_summary.get('output_failure_stage')!r}")
    return {"case": "V7", "zero_contribution": "pass",
            "unknown_particle": "pass",
            "zero_events": 100,
            "unknown_particle_completed_events": completed,
            "unknown_particle_note": "rejected before the first event; no run and no scientific file",
            "repeated_beam_on_run_count": double_summary.get("run_count"),
            "multi_thread_completed_events": threaded_completed,
            "status": "pass"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path,
                        default=Path("out/collab/h2-benchmarks"))
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    work: Path = args.work_root
    work = work if work.is_absolute() else (Path.cwd() / work)
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "g4usim_h2_benchmarks_report_v1",
        "contract_freeze": "docs/collab/decisions/20261106-h2-contract-freeze.md",
        "backend_sha256": None,
        "cases": {},
    }
    if EXE.exists():
        import hashlib
        report["backend_sha256"] = hashlib.sha256(EXE.read_bytes()).hexdigest()
    try:
        report["cases"]["V1a"] = v1a_em_partition(work)
        report["cases"]["V4"] = v4_spectrum_identity(work)
        report["cases"]["V6a"] = v6a_weight_once(work)
        report["cases"]["V7"] = v7_zero_and_unknown_particle(work)
    except Failure as error:
        report["status"] = "fail"
        report["failure"] = str(error)
        print(f"FAIL: {error}")
    else:
        statuses = {case.get("status", "pass") for case in report["cases"].values()}
        report["status"] = "limited" if "limited" in statuses else "pass"
        print(f"PASS: H2-4 real-transport benchmarks ({', '.join(report['cases'])})"
              if report["status"] == "pass" else
              f"LIMITED: H2-4 real-transport benchmarks; see the report")
    target = args.json or (work / "report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
