"""Real Geant4 track-length Fluence prototype regression (isolated fixtures)."""

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
NAME = re.compile(r"fluence_volume_summary_t(\d+)(?:_r(\d+))?\.csv$")
HEADER = ["runID", "volume_path", "volume_name", "volume_mm3", "raw_track_length_mm",
          "weighted_track_length_mm", "raw_fluence_mm-2", "weighted_fluence_mm-2"]


def run(root: Path, name: str, config: str, macro: str, threads: int = 1, expected: int = 0) -> Path:
    main = root / f"{name}.ini"
    main.write_text(config, encoding="utf-8")
    mac = root / f"{name}.mac"
    mac.write_text(macro, encoding="utf-8")
    result = subprocess.run([str(EXE), "--config", str(main), "--macro", str(mac),
                             "--output", str(root / name), "--threads", str(threads)],
                            cwd=root, capture_output=True, text=True, errors="replace", timeout=120)
    (root / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == expected, f"{name}: exit={result.returncode}, log={root / (name + '.log')}\n{(result.stdout + result.stderr)[-1800:]}"
    return root / name


def check(output: Path, threads: int, runs: int) -> dict[tuple[int, int], dict]:
    files = sorted(p for p in output.glob("fluence_volume_summary*.csv") if NAME.fullmatch(p.name))
    assert len(files) == threads * runs, files
    measurements = {}
    for path in files:
        match = NAME.fullmatch(path.name)
        assert match
        thread, run_id = int(match.group(1)), int(match.group(2) or 0)
        assert (run_id, thread) not in measurements
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == HEADER, (path, reader.fieldnames)
            rows = list(reader)
        assert len(rows) == 1, (path, rows)
        row = rows[0]
        assert int(row["runID"]) == run_id
        assert row["volume_path"].endswith("/Target_PV#0")
        volume = float(row["volume_mm3"])
        assert math.isclose(volume, 100.0, rel_tol=1e-9), (path, volume)
        for prefix in ("raw", "weighted"):
            length = float(row[f"{prefix}_track_length_mm"])
            phi = float(row[f"{prefix}_fluence_mm-2"])
            assert math.isfinite(length) and math.isfinite(phi) and (prefix != "raw" or length > 0)
            assert math.isclose(phi, length / volume, rel_tol=2e-9, abs_tol=1e-12), (path, row)
        measurements[(run_id, thread)] = row
    assert {r for r, _ in measurements} == set(range(runs))
    assert {thread for _, thread in measurements} == set(range(threads))
    summary = (output / "run_summary.txt").read_text(encoding="utf-8")
    assert "status = completed" in summary, summary[-800:]
    assert "fluence_volume_csv_v1" in summary, summary[-1200:]
    for path in files:
        assert path.name in summary, (path, summary[-1200:])
    return measurements


def main() -> None:
    assert EXE.is_file(), EXE
    with tempfile.TemporaryDirectory(prefix="g4usim-fluence-") as tmp:
        root = Path(tmp)
        shutil.copytree(ROOT / "config", root / "config")
        base = (root / "config/main.ini").read_text(encoding="utf-8")
        macro = "/run/initialize\n/run/beamOn 12\n"

        off = run(root, "off", base, macro)
        assert not list(off.glob("fluence_volume_summary*.csv"))

        enabled = base.replace("fluence = false", "fluence = true")
        # Geantino transports through the 1 mm silicon target and deposits
        # exactly zero energy: this proves the zero-Edep branch contributes.
        geantino = enabled.replace("particle = proton", "particle = geantino")
        single = run(root, "geantino", geantino, macro)
        result = check(single, 1, 1)[(0, 0)]
        raw = float(result["raw_track_length_mm"])
        assert math.isclose(raw, 12.0, rel_tol=1e-6), raw
        assert math.isclose(float(result["weighted_track_length_mm"]), raw, rel_tol=1e-9)
        # Zero-Edep transport must not produce fabricated deposited-energy hits.
        for path in single.glob("hits*.csv"):
            with path.open(newline="", encoding="utf-8") as stream:
                assert not list(csv.DictReader(stream)), path

        # Multi-thread, multi-run both with and without Dose enabled.
        with_dose = enabled.replace("dose = false", "dose = true")
        double = run(root, "double", with_dose, macro + "/run/beamOn 12\n", threads=2)
        actual = check(double, 2, 2)
        assert len(list(double.glob("dose_volume_summary*.csv"))) == 4

        # M5: use the public CLI on real Geant4 worker CSVs and compare to
        # the individual inputs, retaining run separation and one denominator.
        exported_path = root / "fluence.json"
        exported = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts/run_output_extension.py"),
             "--run", "fluence_json", "--input-dir", str(double),
             "--output", str(exported_path)], cwd=root, capture_output=True,
            text=True, timeout=30)
        assert exported.returncode == 0, exported.stderr
        extension = json.loads(exported_path.read_text(encoding="utf-8"))
        assert extension["extension_id"] == "fluence_json"
        assert extension["data"]["physical_validation"] == "not_established"
        assert len(extension["data"]["volumes"]) == 2
        for volume in extension["data"]["volumes"]:
            run_id = volume["runID"]
            assert volume["thread_ids"] == [0, 1]
            assert math.isclose(volume["volume_mm3"], 100.0)
            for prefix in ("raw", "weighted"):
                total = sum(float(actual[(run_id, thread)][f"{prefix}_track_length_mm"])
                            for thread in (0, 1))
                assert math.isclose(volume[f"{prefix}_track_length_mm"], total, rel_tol=1e-9)
                assert math.isclose(volume[f"{prefix}_fluence_mm-2"], total / 100,
                                    rel_tol=1e-9, abs_tol=1e-12)

        invalid = enabled.replace("auto_create_default_scorers = true", "auto_create_default_scorers = false")
        failed = run(root, "invalid", invalid, macro, expected=1)
        assert not list(failed.glob("fluence_volume_summary*.csv"))
        print("PASS: disabled, geantino zero-Edep 12mm/100mm3, ST/MT, 2 runs, Dose coexistence, CSV, M5 Fluence JSON, invalid config")


if __name__ == "__main__":
    main()
