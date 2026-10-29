"""Black-box Geant4 Dose MVP acceptance, with temporary isolated inputs."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
MEV_J = 1.602176634e-13
DOSE_NAME = re.compile(r"dose_volume_summary_t\d+(?:_r\d+)?\.csv$")
HEADER = ["runID", "volume_path", "volume_name", "mass_kg", "raw_edep_MeV",
          "weighted_edep_MeV", "raw_dose_Gy", "weighted_dose_Gy",
          "raw_edep_sum_sq_MeV2", "weighted_edep_sum_sq_MeV2", "n_events"]


def execute(root: Path, name: str, main_text: str, macro: str, threads: int = 1,
            expected: int = 0) -> Path:
    config = root / f"{name}.ini"
    config.write_text(main_text, encoding="utf-8")
    script = root / f"{name}.mac"
    script.write_text(macro, encoding="utf-8")
    output = root / name
    result = subprocess.run([str(EXE), "--config", str(config), "--macro", str(script),
                             "--output", str(output), "--threads", str(threads)],
                            cwd=root, capture_output=True, text=True, errors="replace", timeout=120)
    (root / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == expected, f"{name}: exit={result.returncode}; log={root / (name + '.log')}\n" + (result.stdout + result.stderr)[-1500:]
    return output


def check_output(output: Path, threads: int, runs: int) -> None:
    # Each original invariant is checked for every record; counts are independent of worker partition.
    record_errors = {
        'csv_header': [],
        'nonempty_worker_csv': [],
        'row_run_identity': [],
        'target_path': [],
        'analytic_mass': [],
        'finite_energy_and_dose': [],
        'dose_conversion': [],
        'manifest_registration': [],
    }
    coverage = {"rows": 0, "cells": 0, "arrays": 0}
    paths = sorted(path for path in output.glob("dose_volume_summary*.csv") if DOSE_NAME.fullmatch(path.name))
    assert len(paths) == threads * runs, f"Dose output count: {paths}"
    total_raw = 0.0
    run_names = set()
    # 10mm * 10mm * 1mm = 0.1 cm3; Si mass = 0.2329 g = 2.329e-4 kg.
    expected_mass = 2.329e-4
    for path in paths:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not (reader.fieldnames == HEADER):
                record_errors['csv_header'].append((path, reader.fieldnames))
            rows = list(reader)
        if not (rows):
            record_errors['nonempty_worker_csv'].append(f"Expected positive target deposit and nonempty Dose CSV: {path}")
        run_match = re.search(r"_r(\d+)\.csv$", path.name)
        run_id = int(run_match.group(1)) if run_match else 0
        run_names.add(run_id)
        for row in rows:
            coverage['rows'] += 1
            coverage['cells'] += len(row)

            if not (int(row["runID"]) == run_id):
                record_errors['row_run_identity'].append((path, row))
            if not (row["volume_path"].endswith("/Target_PV#0")):
                record_errors['target_path'].append(row)
            mass = float(row["mass_kg"])
            if not (math.isfinite(mass) and math.isclose(mass, expected_mass, rel_tol=0.015)):
                record_errors['analytic_mass'].append((path, mass))
            for prefix in ("raw", "weighted"):
                energy = float(row[f"{prefix}_edep_MeV"])
                dose = float(row[f"{prefix}_dose_Gy"])
                if not (math.isfinite(energy) and math.isfinite(dose)):
                    record_errors['finite_energy_and_dose'].append((path, row, prefix, energy, dose))
                if not (math.isclose(dose, energy * MEV_J / mass, rel_tol=2e-9, abs_tol=1e-15)):
                    record_errors['dose_conversion'].append((path, row))
            total_raw += float(row["raw_edep_MeV"])
    assert total_raw > 0, f"No energy deposited: {output}"
    assert run_names == set(range(runs)), run_names
    summary = (output / "run_summary.txt").read_text(encoding="utf-8")
    assert "status = completed" in summary, summary[-1000:]
    assert "dose_volume_summary" in summary and "dose_volume_csv_v2" in summary, summary[-1500:]
    for path in paths:
        if not (path.name in summary):
            record_errors['manifest_registration'].append(f"Missing output registration: {path}")

    print('check_output: coverage=', coverage)
    assert not record_errors['csv_header'], ('check_output: invariant csv_header', record_errors['csv_header'])
    assert not record_errors['nonempty_worker_csv'], ('check_output: invariant nonempty_worker_csv', record_errors['nonempty_worker_csv'])
    assert not record_errors['row_run_identity'], ('check_output: invariant row_run_identity', record_errors['row_run_identity'])
    assert not record_errors['target_path'], ('check_output: invariant target_path', record_errors['target_path'])
    assert not record_errors['analytic_mass'], ('check_output: invariant analytic_mass', record_errors['analytic_mass'])
    assert not record_errors['finite_energy_and_dose'], ('check_output: invariant finite_energy_and_dose', record_errors['finite_energy_and_dose'])
    assert not record_errors['dose_conversion'], ('check_output: invariant dose_conversion', record_errors['dose_conversion'])
    assert not record_errors['manifest_registration'], ('check_output: invariant manifest_registration', record_errors['manifest_registration'])


def check_output_extension(output: Path, root: Path) -> None:
    """Exercise the M5 JSON extension against actual ST/MT Geant4 Dose files."""
    # Each original invariant is checked for every record; counts are independent of worker partition.
    record_errors = {
        'worker_filename': [],
        'extension_run_identity': [],
        'consistent_volume_mass': [],
        'extension_worker_identity': [],
        'extension_mass': [],
        'extension_energy_sum': [],
        'extension_dose_conversion': [],
    }
    coverage = {"rows": 0, "cells": 0, "arrays": 0}
    destination = root / "dose-real-output.json"
    command = [sys.executable, "-B", str(ROOT / "scripts/run_output_extension.py"),
               "--run", "dose_json", "--input-dir", str(output),
               "--output", str(destination)]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema"] == "G4UniversalSimOutputExtensionResult"
    assert payload["version"] == 1 and payload["extension_id"] == "dose_json"
    data = payload["data"]
    assert data["kind"] == "dose_volume_aggregate"
    assert data["units"] == {"mass": "kg", "edep": "MeV", "dose": "Gy"}
    assert data["physical_validation"] == "not_established"
    assert data["warnings"] == [], data["warnings"]

    # Compute reference totals independently from the raw Geant4 worker CSVs.
    reference: dict[tuple[int, str], dict] = {}
    for path in sorted(output.glob("dose_volume_summary*.csv")):
        match = re.fullmatch(r"dose_volume_summary_t(\d+)(?:_r(\d+))?\.csv", path.name)
        if not (match is not None):
            record_errors['worker_filename'].append(path)
        thread_id, run_id = int(match.group(1)), int(match.group(2) or 0)
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                coverage['rows'] += 1
                coverage['cells'] += len(row)

                if not (int(row["runID"]) == run_id):
                    record_errors['extension_run_identity'].append((path, row, run_id))
                key = (run_id, row["volume_path"])
                record = reference.setdefault(key, {
                    "threads": set(), "mass": float(row["mass_kg"]),
                    "raw": 0.0, "weighted": 0.0,
                })
                if not (math.isclose(record["mass"], float(row["mass_kg"]), rel_tol=1e-9)):
                    record_errors['consistent_volume_mass'].append((path, row, record["mass"]))
                record["threads"].add(thread_id)
                record["raw"] += float(row["raw_edep_MeV"])
                record["weighted"] += float(row["weighted_edep_MeV"])

    assert reference and {key[0] for key in reference} == {0, 1}
    assert len(data["volumes"]) == len(reference)
    for item in data["volumes"]:
        expected = reference.pop((item["runID"], item["volume_path"]))
        if not (item["thread_ids"] == sorted(expected["threads"]) == [0, 1]):
            record_errors['extension_worker_identity'].append((item, sorted(expected["threads"])))
        if not (math.isclose(item["mass_kg"], expected["mass"], rel_tol=1e-9)):
            record_errors['extension_mass'].append((item, expected))
        for prefix in ("raw", "weighted"):
            energy = item[f"{prefix}_edep_MeV"]
            if not (math.isclose(energy, expected[prefix], rel_tol=1e-9, abs_tol=1e-12)):
                record_errors['extension_energy_sum'].append((item, prefix, energy, expected[prefix]))
            if not (math.isclose(item[f"{prefix}_dose_Gy"],
                                energy * MEV_J / expected["mass"], rel_tol=1e-9)):
                record_errors['extension_dose_conversion'].append((item, prefix, energy, expected["mass"]))
    assert not reference

    print('check_output_extension: coverage=', coverage)
    assert not record_errors['worker_filename'], ('check_output_extension: invariant worker_filename', record_errors['worker_filename'])
    assert not record_errors['extension_run_identity'], ('check_output_extension: invariant extension_run_identity', record_errors['extension_run_identity'])
    assert not record_errors['consistent_volume_mass'], ('check_output_extension: invariant consistent_volume_mass', record_errors['consistent_volume_mass'])
    assert not record_errors['extension_worker_identity'], ('check_output_extension: invariant extension_worker_identity', record_errors['extension_worker_identity'])
    assert not record_errors['extension_mass'], ('check_output_extension: invariant extension_mass', record_errors['extension_mass'])
    assert not record_errors['extension_energy_sum'], ('check_output_extension: invariant extension_energy_sum', record_errors['extension_energy_sum'])
    assert not record_errors['extension_dose_conversion'], ('check_output_extension: invariant extension_dose_conversion', record_errors['extension_dose_conversion'])


def check_mother_mass(root: Path) -> None:
    """Independent analytic masses and raw-hit sums for sensitive mother/child."""
    # Each original invariant is checked for every record; counts are independent of worker partition.
    record_errors = {
        'mother_child_identity': [],
        'mother_child_mass': [],
        'mother_child_dose_conversion': [],
        'complete_run_volume_keys': [],
        'positive_volume_energies': [],
        'dose_matches_raw_hits': [],
    }
    coverage = {"rows": 0, "cells": 0, "arrays": 0}
    for material, child_mass in (("G4_WATER", .001), ("G4_Pb", .01135)):
        geo = root / f"mother_{material}.ini"
        geo.write_text("[world]\nshape = box\nsize = 1 m,1 m,1 m\nmaterial = G4_Galactic\n"
                       "[volume.Mother]\nparent = world\nshape = box\nsize = 20 mm,20 mm,20 mm\n"
                       "material = G4_WATER\nsensitive = true\n"
                       "[volume.Child]\nparent = Mother\nshape = box\nsize = 10 mm,10 mm,10 mm\n"
                       f"material = {material}\nsensitive = true\n", encoding="utf-8")
        config = (f"[geometry]\ntemplate = hierarchical\nconfig = {geo.as_posix()}\n"
                  f"[materials]\nfile = {(ROOT / 'config/materials/material.ini').as_posix()}\n"
                  "[physics]\nreference = FTFP_BERT\n[output]\nformat = csv\n"
                  "[scoring]\nenabled = true\nhits = true\ndose = true\n"
                  "auto_create_default_scorers = true\n[source]\nparticle = proton\nenergy = 100 MeV\n"
                  "position_type = point\nposition = 0,0,-9 mm\ndirection = +z\n")
        for threads in (1, 2):
            output = execute(root, f"mother_{material}_{threads}", config,
                             "/run/initialize\n/run/beamOn 40\n/run/beamOn 40\n", threads)
            hits = {}
            for path in output.glob("hits_t*.csv"):
                with path.open(newline="", encoding="utf-8") as stream:
                    for row in csv.DictReader(stream):
                        coverage['rows'] += 1
                        coverage['cells'] += len(row)

                        key = (int(row["runID"]), row["volume"])
                        raw, weighted = hits.get(key, (0.0, 0.0))
                        energy = float(row["edep_MeV"])
                        hits[key] = (raw + energy, weighted + energy * float(row["weight"]))
            dose = {}
            for path in output.glob("dose_volume_summary_t*.csv"):
                with path.open(newline="", encoding="utf-8") as stream:
                    for row in csv.DictReader(stream):
                        coverage['rows'] += 1
                        coverage['cells'] += len(row)

                        name = row["volume_path"].rsplit("/", 1)[1].split("#")[0]
                        key = (int(row["runID"]), name)
                        expected_mass = .007 if name == "Mother_PV" else child_mass
                        if not (name in ("Mother_PV", "Child_PV")):
                            record_errors['mother_child_identity'].append(row)
                        mass = float(row["mass_kg"])
                        # Mother water: 8 cm3 minus child's displaced 1 cm3 = 7 g.
                        if not (math.isclose(mass, expected_mass, rel_tol=1e-9)):
                            record_errors['mother_child_mass'].append(row)
                        raw, weighted = dose.get(key, (0.0, 0.0))
                        dose[key] = (raw + float(row["raw_edep_MeV"]),
                                     weighted + float(row["weighted_edep_MeV"]))
                        for prefix in ("raw", "weighted"):
                            if not (math.isclose(float(row[f"{prefix}_dose_Gy"]),
                                                float(row[f"{prefix}_edep_MeV"]) * MEV_J / expected_mass,
                                                rel_tol=2e-9, abs_tol=1e-18)):
                                record_errors['mother_child_dose_conversion'].append(row)
            if not (set(dose) == {(run, name) for run in (0, 1) for name in ("Mother_PV", "Child_PV")}):
                record_errors['complete_run_volume_keys'].append(dose)
            for key, energies in dose.items():
                if not (all(value > 0 for value in energies)):
                    record_errors['positive_volume_energies'].append((key, energies))
                for observed, expected in zip(energies, hits[key]):
                    if not (math.isclose(observed, expected, rel_tol=2e-9, abs_tol=1e-9)):
                        record_errors['dose_matches_raw_hits'].append((key, observed, expected))

    print('check_mother_mass: coverage=', coverage)
    assert not record_errors['mother_child_identity'], ('check_mother_mass: invariant mother_child_identity', record_errors['mother_child_identity'])
    assert not record_errors['mother_child_mass'], ('check_mother_mass: invariant mother_child_mass', record_errors['mother_child_mass'])
    assert not record_errors['mother_child_dose_conversion'], ('check_mother_mass: invariant mother_child_dose_conversion', record_errors['mother_child_dose_conversion'])
    assert not record_errors['complete_run_volume_keys'], ('check_mother_mass: invariant complete_run_volume_keys', record_errors['complete_run_volume_keys'])
    assert not record_errors['positive_volume_energies'], ('check_mother_mass: invariant positive_volume_energies', record_errors['positive_volume_energies'])
    assert not record_errors['dose_matches_raw_hits'], ('check_mother_mass: invariant dose_matches_raw_hits', record_errors['dose_matches_raw_hits'])


def check_nested_and_invalid_mass(root: Path) -> None:
    # Each original invariant is checked for every record; counts are independent of worker partition.
    record_errors = {
        'nested_nonempty_run_coverage': [],
        'nested_analytic_mass': [],
        'invalid_mass_failed_status': [],
        'invalid_mass_diagnostic': [],
        'invalid_mass_failure_stage': [],
    }
    coverage = {"rows": 0, "cells": 0, "arrays": 0}
    import test_geometry_a5 as a5
    original = a5.MAIN
    a5.MAIN = a5.MAIN.replace("fluence = true", "fluence = false")
    try:
        work = root / "nested"
        work.mkdir()
        (work / "copies.csv").write_text("x_mm,y_mm,z_mm,material\n-50,0,0,G4_WATER\n50,0,0,G4_Si\n", encoding="utf-8")
        nested = a5.WORLD + a5.volume("Container", "shape = box\nsize = 200 mm,100 mm,100 mm", sensitive=False) + \
            a5.volume("Mother", "shape = box\nsize = 20 mm,20 mm,20 mm\nplacement = parameterised\ncopies_file = copies.csv", parent="Container") + \
            a5.volume("Child", "shape = box\nsize = 10 mm,10 mm,10 mm", parent="Mother", material="G4_Pb")
        r = a5.Runner(work)
        for threads in (1, 2):
            r.threads = threads
            for x, expected_mass in ((-50, .007), (50, .01631)):
                source = f"[source]\nparticle = proton\nenergy = 100 MeV\nposition_type = point\nposition = {x},0,-9 mm\ndirection = +z\n"
                output, _ = r.run(nested, source, 20, macro_extra="/run/beamOn 20\n")
                observed = a5.rows(output, "dose_volume_summary")
                if not (observed and {int(row["runID"]) for row in observed} == {0, 1}):
                    record_errors['nested_nonempty_run_coverage'].append(observed)
                for row in observed:
                    coverage['rows'] += 1
                    coverage['cells'] += len(row)

                    expected = .01135 if "/Child_PV#" in row["volume_path"] else expected_mass
                    if not (math.isclose(float(row["mass_kg"]), expected, rel_tol=1e-9)):
                        record_errors['nested_analytic_mass'].append(row)
        # Deliberately overlapping daughters exhaust/exceed mother volume while
        # leaving the starting point in exposed mother material. Overlap checks
        # are disabled solely to exercise zero/negative-mass transport failure.
        a5.MAIN = a5.MAIN.replace("check_overlaps = true", "check_overlaps = false")
        for depth in (10, 12):
            invalid = a5.WORLD + a5.volume("Mother", "shape = box\nsize = 20 mm,20 mm,20 mm")
            for child in ("A", "B"):
                invalid += a5.volume(child, f"shape = box\nsize = 20 mm,20 mm,{depth} mm", parent="Mother", sensitive=False)
            source = "[source]\nparticle = proton\nenergy = 20 MeV\nposition_type = point\nposition = 0,0,-9 mm\ndirection = +z\n"
            for threads in (1, 2):
                r.threads = threads
                output, log = r.run(invalid, source, 10, expect_ok=False)
                (root / f"invalid_mass_{depth}_{threads}.log").write_text(log, encoding="utf-8")
                summary = (output / "run_summary.txt").read_text(encoding="utf-8")
                if not ("status = failed" in summary):
                    record_errors['invalid_mass_failed_status'].append(summary)
                if not ("DoseScorer requires a positive Geant4 physical-volume mass" in summary):
                    record_errors['invalid_mass_diagnostic'].append(summary)
                if not ("output_failure_stage = scoring_dose" in summary):
                    record_errors['invalid_mass_failure_stage'].append(summary)
    finally:
        a5.MAIN = original

    print('check_nested_and_invalid_mass: coverage=', coverage)
    assert not record_errors['nested_nonempty_run_coverage'], ('check_nested_and_invalid_mass: invariant nested_nonempty_run_coverage', record_errors['nested_nonempty_run_coverage'])
    assert not record_errors['nested_analytic_mass'], ('check_nested_and_invalid_mass: invariant nested_analytic_mass', record_errors['nested_analytic_mass'])
    assert not record_errors['invalid_mass_failed_status'], ('check_nested_and_invalid_mass: invariant invalid_mass_failed_status', record_errors['invalid_mass_failed_status'])
    assert not record_errors['invalid_mass_diagnostic'], ('check_nested_and_invalid_mass: invariant invalid_mass_diagnostic', record_errors['invalid_mass_diagnostic'])
    assert not record_errors['invalid_mass_failure_stage'], ('check_nested_and_invalid_mass: invariant invalid_mass_failure_stage', record_errors['invalid_mass_failure_stage'])


def main() -> None:
    assert EXE.is_file(), EXE
    with tempfile.TemporaryDirectory(prefix="g4usim-dose-") as temp:
        root = Path(temp)
        shutil.copytree(ROOT / "config", root / "config")
        base = (root / "config/main.ini").read_text(encoding="utf-8")
        assert base.count("dose = false") == 1
        macro = "/run/initialize\n/run/beamOn 40\n"
        disabled = execute(root, "disabled", base, macro)
        assert not list(disabled.glob("dose_volume_summary*.csv"))
        enabled = base.replace("dose = false", "dose = true")
        check_output(execute(root, "single", enabled, macro), 1, 1)
        double = execute(root, "double", enabled, macro + "/run/beamOn 40\n", 2)
        check_output(double, 2, 2)
        check_output_extension(double, root)
        # LET is supported since roadmap A2 (scripts/test_let_scoring.py); dose + LET must coexist.
        both = execute(root, "dose_let", enabled.replace("let = false", "let = true"), macro)
        check_output(both, 1, 1)
        assert list(both.glob("let_volume_summary_t*.csv")), "LET summary missing next to dose"
        check_mother_mass(root)
        check_nested_and_invalid_mass(root)
        print("PASS: disabled, single/MT, multi-run, mass, Gy, manifest, M5 real Dose JSON, dose+LET coexistence")


if __name__ == "__main__":
    main()
