"""Roadmap H2-2 black-box regression: volume particle/energy filters and
kinetic-energy spectra on real Geant4 output.

The fixture is deliberately simple (1 MeV photons crossing a 10x10x0.1 mm
G4_Galactic slab).  A photon step carries zero local energy deposition, so the
fluence path only exists through the zero-deposition branch: the spectrum sum
therefore proves that the scorer is fed by that branch and not by hits.

Fixed pre-registered cases (H2-1 contract freeze 20261106):
  V5  mono-energetic spectrum: 100 events x 0.1 mm / 10 mm^3 = 1.0 mm^-2,
      E = 1.0 MeV falls into bin 5 of [0.5, 1.5) MeV with 10 bins.
  boundaries: E == min accepted, E == max rejected by a filter, E == max
      written into the closed last bin instead of overflow.
  V7  invalid configurations fail during configuration / run begin.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
SPECTRUM_NAME = re.compile(r"spectrum_fluence_t\d+\.csv$")
SPECTRUM_HEADER = ["runID", "scorer", "volume_path", "volume_name", "region", "bin",
                   "low_edge_MeV", "high_edge_MeV", "amount", "unit", "n_events"]
FLUENCE_HEADER = ["runID", "volume_path", "volume_name", "volume_mm3",
                  "raw_track_length_mm", "weighted_track_length_mm",
                  "raw_fluence_mm-2", "weighted_fluence_mm-2",
                  "raw_track_length_sum_sq_mm2", "weighted_track_length_sum_sq_mm2",
                  "n_events"]
GEOMETRY = """[world]
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
"""


def config(root: Path, *, name: str, photon_energy: str = "1 MeV", events: int = 100,
           extra_scoring: str = "", extra: str = "", format: str = "csv") -> str:
    geometry = root / "geometry.ini"
    geometry.write_text(GEOMETRY, encoding="utf-8")
    main = f"""[run]
name = {name}
threads = 1
seed = 20261305
interactive = false
verbose = 0
check_overlaps = false
dry_run = false

[output]
dir = {root / name / "output"}
format = {format}

[geometry]
template = hierarchical
config = {geometry}
default_world_material = G4_Galactic

[physics]
em = option4
default_cut = 0.1 mm

[scoring]
enabled = true
hits = true
event_edep = false
edep = false
dose = false
fluence = true
auto_create_default_scorers = true
{extra_scoring}

[source]
particle = gamma
energy = {photon_energy}
position_type = plane
shape = square
halfx = 4 mm
center = 0, 0, -2 mm
direction = 0, 0, 1
{extra}
"""
    return main


def run(root: Path, name: str, text: str, events: int = 100, *, expect_ok: bool = True) -> tuple[Path, str]:
    main = root / f"{name}.ini"
    main.write_text(text, encoding="utf-8")
    macro = root / f"{name}.mac"
    macro.write_text(f"/run/initialize\n/run/beamOn {events}\n", encoding="utf-8")
    output = root / name / "output"
    result = subprocess.run(
        [str(EXE), "--config", str(main), "--macro", str(macro), "--output", str(output)],
        cwd=root, capture_output=True, text=True, errors="replace", timeout=300)
    log = root / f"{name}.log"
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    combined = result.stdout + result.stderr
    if expect_ok:
        assert result.returncode == 0, f"{name}: exit={result.returncode}, log={log}\n{combined[-2500:]}"
    else:
        assert result.returncode != 0, f"{name}: expected a nonzero exit, log={log}\n{combined[-1500:]}"
    return output, combined


def single(path_glob: list[Path]) -> Path:
    assert len(path_glob) == 1, path_glob
    return path_glob[0]


def read_summary(output: Path) -> dict[str, str]:
    path = single(list(output.glob("run_summary*.txt")))
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if " = " in line and not line.startswith("["):
            key, value = line.split(" = ", 1)
            values[key.strip()] = value.strip()
    return values


def spectrum_rows(output: Path) -> list[dict[str, str]]:
    path = single([p for p in output.glob("spectrum_fluence_t*.csv") if SPECTRUM_NAME.fullmatch(p.name)])
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == SPECTRUM_HEADER, reader.fieldnames
        return list(reader)


def fluence_rows(output: Path) -> list[dict[str, str]]:
    path = single(list(output.glob("fluence_volume_summary_t*.csv")))
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == FLUENCE_HEADER, reader.fieldnames
        return list(reader)


def assert_rejected(root: Path, name: str, text: str, needle: str) -> None:
    _, combined = run(root, name, text, expect_ok=False)
    assert needle in combined, f"{name}: expected '{needle}' in output\n{combined[-2500:]}"


def case_spectrum_mono_photon(root: Path) -> None:
    text = config(root, name="spectrum_mono", extra_scoring="""[scoring.spectrum.fluence]
bins = 10
min = 0.5 MeV
max = 1.5 MeV""")
    output, _ = run(root, "spectrum_mono", text)
    rows = spectrum_rows(output)
    assert len(rows) == 12, len(rows)
    bins = [row for row in rows if row["region"] == "bin"]
    assert [int(row["bin"]) for row in bins] == list(range(10)), bins
    under = single([row for row in rows if row["region"] == "underflow"])
    over = single([row for row in rows if row["region"] == "overflow"])
    assert float(under["amount"]) == 0.0 and under["bin"] == "-1"
    assert float(over["amount"]) == 0.0 and over["bin"] == "10"
    assert bins[0]["low_edge_MeV"] == "0.5" and bins[0]["high_edge_MeV"] == "0.6", bins[0]
    assert bins[5]["low_edge_MeV"] == "1" and bins[5]["high_edge_MeV"] == "1.1", bins[5]
    total = sum(float(row["amount"]) for row in rows)
    assert abs(total - 1.0) < 1e-9, total
    assert float(bins[5]["amount"]) > 0.0, bins[5]
    assert float(bins[4]["amount"]) == 0.0 and float(bins[6]["amount"]) == 0.0, (bins[4], bins[6])
    assert all(row["unit"] == "mm^-2" for row in rows), rows[0]
    assert all(row["n_events"] == "100" for row in rows), rows[0]
    assert rows[0]["volume_name"] == "Slab_PV", rows[0]

    fluence = single(fluence_rows(output))
    assert abs(float(fluence["weighted_fluence_mm-2"]) - 1.0) < 1e-9, fluence
    assert fluence["n_events"] == "100"

    summary = read_summary(output)
    assert summary["status"] == "completed", summary.get("status")
    assert summary["spectrum_csv_schema_version"] == "1", summary.get("spectrum_csv_schema_version")
    assert summary["output_csv_schema_version"] == "3", summary.get("output_csv_schema_version")
    schemas = [value for key, value in summary.items() if key.endswith("_schema")]
    assert "spectrum_kinetic_energy_csv_v1" in schemas, schemas


def case_boundaries(root: Path) -> None:
    # E == max closes the last bin; E == min is accepted by a filter; E == max is
    # rejected by the half-open filter window.
    text = config(root, name="spectrum_max", photon_energy="1.5 MeV", extra_scoring="""[scoring.spectrum.fluence]
bins = 10
min = 0.5 MeV
max = 1.5 MeV""")
    output, _ = run(root, "spectrum_max", text)
    rows = spectrum_rows(output)
    over = single([row for row in rows if row["region"] == "overflow"])
    last = single([row for row in rows if row["region"] == "bin" and row["bin"] == "9"])
    assert float(over["amount"]) == 0.0, over
    assert abs(float(last["amount"]) - 1.0) < 1e-9, last

    min_filtered = config(root, name="filter_min_inclusive", photon_energy="1.5 MeV", extra_scoring="""[scoring.filter.fluence]
energy_min = 1.5 MeV""")
    output, _ = run(root, "filter_min_inclusive", min_filtered)
    rows = fluence_rows(output)
    assert len(rows) == 1 and abs(float(rows[0]["weighted_fluence_mm-2"]) - 1.0) < 1e-9, rows

    max_filtered = config(root, name="filter_max_exclusive", photon_energy="1.5 MeV", extra_scoring="""[scoring.filter.fluence]
energy_max = 1.5 MeV""")
    output, _ = run(root, "filter_max_exclusive", max_filtered)
    assert fluence_rows(output) == [], fluence_rows(output)


def case_filters(root: Path) -> None:
    particles_gamma = config(root, name="filter_particles_gamma", extra_scoring="""[scoring.filter.fluence]
particles = gamma""")
    output, _ = run(root, "filter_particles_gamma", particles_gamma)
    assert abs(float(single(fluence_rows(output))["weighted_fluence_mm-2"]) - 1.0) < 1e-9

    particles_electron = config(root, name="filter_particles_electron", extra_scoring="""[scoring.filter.fluence]
particles = e-""")
    output, _ = run(root, "filter_particles_electron", particles_electron)
    assert fluence_rows(output) == [], fluence_rows(output)
    assert not list(output.glob("spectrum_*.csv"))

    window = config(root, name="filter_window", extra_scoring="""[scoring.filter.fluence]
particles = gamma
energy_min = 1.0 MeV
energy_max = 2.0 MeV""")
    output, _ = run(root, "filter_window", window)
    assert abs(float(single(fluence_rows(output))["weighted_fluence_mm-2"]) - 1.0) < 1e-9

    # Unconfigured H2-2 keeps the previous behavior byte-for-byte in content:
    # same fluence total and no spectrum file or summary key.
    plain = config(root, name="plain_no_h2")
    output, _ = run(root, "plain_no_h2", plain)
    assert not list(output.glob("spectrum_*.csv"))
    summary = read_summary(output)
    assert "spectrum_csv_schema_version" not in summary
    assert abs(float(single(fluence_rows(output))["weighted_fluence_mm-2"]) - 1.0) < 1e-9


def case_invalid_configurations(root: Path) -> None:
    base = config(root, name="invalid_base")
    cases = {
        "unknown_filter_topic": (
            base.replace("[source]", "[scoring.filter.edep]\nparticles = gamma\n\n[source]"),
            "Unknown scoring filter topic 'edep'"),
        "spectrum_let": (
            base.replace("[source]", "[scoring.spectrum.let]\nbins = 2\nmin = 0 MeV\nmax = 2 MeV\n\n[source]"),
            "Spectrum for scorer 'let' is not supported"),
        "empty_particles": (
            base.replace("[scoring]", "[scoring.filter.fluence]\nparticles =\n\n[scoring]"),
            "must list at least one Geant4 particle name or 'all'"),
        "all_mixed": (
            base.replace("[scoring]", "[scoring.filter.fluence]\nparticles = all,gamma\n\n[scoring]"),
            "cannot mix 'all' with other particle names"),
        "energy_window": (
            base.replace("[scoring]", "[scoring.filter.fluence]\nenergy_min = 2 MeV\nenergy_max = 1 MeV\n\n[scoring]"),
            "energy_max must be greater than energy_min"),
        "unused_filter": (
            base.replace("[scoring]", "[scoring.filter.fluence]\nparticles = gamma\n\n[scoring]").replace(
                "fluence = true", "fluence = false"),
            "requires [scoring] fluence = true"),
        "missing_scoring": (
            base.replace("[source]", "[scoring.filter.fluence]\nparticles = gamma\n\n[source]").replace(
                "[scoring]\nenabled = true\nhits = true\nevent_edep = false\nedep = false\ndose = false\nfluence = true\n"
                "auto_create_default_scorers = true\n", ""),
            "require a [scoring] section"),
        "spectrum_width": (
            base.replace(
                "[source]",
                "[scoring.spectrum.fluence]\nbins = 2\nmin = 0 MeV\nmax = 4.9e-324 MeV\n\n[source]",
            ),
            "bin width"),
        "spectrum_bins": (
            base.replace("[source]", "[scoring.spectrum.fluence]\nbins = 0\nmin = 0 MeV\nmax = 2 MeV\n\n[source]"),
            "bins"),
        "spectrum_root": (
            config(root, name="invalid_root", format="root",
                   extra_scoring="[scoring.spectrum.fluence]\nbins = 2\nmin = 0 MeV\nmax = 2 MeV"),
            "Kinetic-energy spectra require CSV output"),
    }
    for name, (text, needle) in cases.items():
        assert_rejected(root, f"invalid_{name}", text, needle)

    # Unknown Geant4 particle names are only resolvable once the particle table
    # exists: they must fail at run begin with a dedicated stage, before events.
    unknown = config(root, name="invalid_particle",
                     extra_scoring="[scoring.filter.fluence]\nparticles = muon")
    output, combined = run(root, "invalid_particle", unknown, expect_ok=False)
    assert "unknown Geant4 particle 'muon'" in combined, combined[-2000:]
    summary = read_summary(output)
    assert summary["status"] == "failed", summary.get("status")
    assert summary["output_failure_stage"] == "scoring_filter_particle", summary.get("output_failure_stage")
    assert "unknown Geant4 particle 'muon'" in summary["output_failure_message"]


def case_determinism(root: Path) -> None:
    text = config(root, name="determinism", extra_scoring="""[scoring.spectrum.fluence]
bins = 10
min = 0.5 MeV
max = 1.5 MeV""")
    first, _ = run(root, "determinism", text)
    first_bytes = single([p for p in first.glob("spectrum_fluence_t*.csv")]).read_bytes()
    second, _ = run(root, "determinism_again", text.replace("name = determinism", "name = determinism_again"))
    second_bytes = single([p for p in second.glob("spectrum_fluence_t*.csv")]).read_bytes()
    assert first_bytes == second_bytes, "spectrum output is not deterministic for a fixed seed"


def main() -> None:
    assert EXE.is_file(), f"backend executable not found: {EXE}"
    with tempfile.TemporaryDirectory(prefix="g4usim-h2-") as tmp:
        root = Path(tmp)
        case_spectrum_mono_photon(root)
        case_boundaries(root)
        case_filters(root)
        case_invalid_configurations(root)
        case_determinism(root)
    print("PASS: H2-2 volume filters, kinetic-energy spectra, boundaries, negative configurations")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise
