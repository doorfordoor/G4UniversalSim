"""Real Geant4 regression for the displacement damage scorer (roadmap B2).

[scoring] displacement = true folds the track-length fluence of each tabulated
particle in a daughter-free sensitive volume with its NIEL(E) table:
DDD = sum w l NIEL(E_mean) / V (MeV/g). Checks:
  1. 1 GeV mu- through 1 mm Si with a log-log table NIEL = 2e-6 E/MeV: the scorer's
     muon track length equals the sum of the muon hits exactly, and its DDD equals
     the independent recomputation from the hits (energy loss << 1 %);
  2. an e- table outside the electrons' energies scores no DDD and puts their track
     length into out_of_range_track_length_mm;
  3. 1 MeV neutrons through 100 um Si (steps without energy deposit, scored through
     the zero-deposit path) with a constant table: DDD = NIEL * N / A;
  4. per-worker CSV sums, ddd_total and the merged scorer_statistics.csv agree, and a
     ROOT-only run still writes the statistics;
  5. invalid tables and settings fail before events.
"""

from __future__ import annotations

import csv
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

MAIN = """
[run]
threads = 2
seed = 11
[output]
format = {format}
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = hierarchical
config = {geometry}
[physics]
reference = FTFP_BERT
[scoring]
enabled = true
hits = {hits}
event_edep = false
edep = false
displacement = true
auto_create_default_scorers = {auto}
[source]
particle = {particle}
energy = {energy} MeV
position_type = point
position = 0,0,-10 mm
direction = +z
{extra}
"""

GEOMETRY = """
[world]
shape = box
size = 1 m, 1 m, 1 m
material = G4_Galactic
[volume.Die]
parent = world
shape = box
size = 100 mm, 100 mm, {thickness} mm
material = G4_Si
position = 0 mm, 0 mm, {z} mm
sensitive = true
"""


class Runner:
    def __init__(self, work: Path):
        self.work = work
        self.count = 0

    def run(self, particle, energy, events, tables, *, thickness=1.0, hits=True, fmt="csv", auto="true",
            extra=None, expect_ok=True):
        self.count += 1
        name = f"case{self.count:02d}"
        geo = self.work / f"{name}_geometry.ini"
        geo.write_text(GEOMETRY.format(thickness=thickness, z=thickness / 2), encoding="utf-8")
        if extra is None:
            extra = "[scoring.displacement]\n" + "".join(f"{p} = {f}\n" for p, f in tables.items())
        ini = self.work / f"{name}.ini"
        ini.write_text(MAIN.format(root=ROOT.as_posix(), geometry=geo.as_posix(), particle=particle, energy=energy,
                                   hits="true" if hits else "false", format=fmt, auto=auto, extra=extra),
                       encoding="utf-8")
        mac = self.work / f"{name}.mac"
        mac.write_text(f"/run/initialize\n/run/beamOn {events}\n", encoding="utf-8")
        output = self.work / name
        result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(mac), "--output", str(output)],
                                cwd=self.work, capture_output=True, text=True, errors="replace", timeout=900)
        log = result.stdout + result.stderr
        if expect_ok:
            assert result.returncode == 0, f"{name} failed:\n{log[-3000:]}"
        else:
            assert result.returncode != 0, f"{name} unexpectedly succeeded"
        return output, log


def rows(output: Path, stem: str):
    for path in sorted(output.glob(f"{stem}_t*.csv")):
        if re.fullmatch(rf"{stem}_t\d+\.csv", path.name):
            with path.open(newline="", encoding="utf-8") as handle:
                yield from csv.DictReader(handle)


def statistics(output: Path) -> dict[str, dict[str, str]]:
    with (output / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
        return {r["quantity"]: r for r in csv.DictReader(handle) if r["scorer"] == "displacement"}


def close(label, got, expected, rel):
    print(f"  {label}: {got:.9g} (expected {expected:.9g}, rel. tolerance {rel:g})")
    assert abs(got - expected) <= rel * abs(expected), (label, got, expected)


def table(path: Path, points) -> str:
    path.write_text("# test table\nenergy_MeV,niel_MeV_cm2_g\n" + "".join(f"{e},{v}\n" for e, v in points),
                    encoding="utf-8")
    return path.as_posix()


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    work = Path(tempfile.mkdtemp(prefix="g4usim_ddd_"))
    try:
        r = Runner(work)
        mu = table(work / "mu.csv", [(500, 1e-3), (2000, 4e-3)])          # NIEL = 2e-6 * E (log-log exact)
        far = table(work / "far.csv", [(1e5, 1.0), (1e6, 1.0)])           # outside every electron energy
        flat = table(work / "flat.csv", [(0.01, 2e-3), (20, 2e-3)])

        print("muons: log-log table, hits recomputation")
        output, _ = r.run("mu-", 1000, 200, {"mu-": mu, "e-": far})
        volume_mm3 = 100 * 100 * 1.0
        length = defaultdict(float)
        expected_ddd = 0.0
        for hit in rows(output, "hits"):
            l = float(hit["stepLength_mm"])
            length[hit["particle"]] += l
            if hit["particle"] == "mu-":
                expected_ddd += l * 2e-6 * float(hit["kineticEnergy_MeV"]) * 100.0 / volume_mm3
        summary = list(rows(output, "displacement_volume_summary"))
        by_particle = defaultdict(lambda: defaultdict(float))
        for row in summary:
            for key in ("track_length_mm", "out_of_range_track_length_mm", "ddd_MeV_g", "ddd_sum_sq_MeV2_g2"):
                by_particle[row["particle"]][key] += float(row[key])
            assert row["volume_name"] == "Die_PV" and abs(float(row["volume_mm3"]) - volume_mm3) < 1e-6, row
        close("mu- track length [mm]", by_particle["mu-"]["track_length_mm"], length["mu-"], 1e-9)
        # hits carry the pre-step energy; the scorer uses the step mean (dE << E)
        close("mu- DDD [MeV/g]", by_particle["mu-"]["ddd_MeV_g"], expected_ddd, 1e-3)
        assert by_particle["e-"]["ddd_MeV_g"] == 0.0, by_particle["e-"]
        assert by_particle["e-"]["track_length_mm"] == 0.0, by_particle["e-"]
        out_of_range = by_particle["e-"]["out_of_range_track_length_mm"]
        print(f"  e- out-of-range track length {out_of_range:.6g} mm (hits {length['e-']:.6g} mm)")
        assert out_of_range >= length["e-"] * (1 - 1e-9) and out_of_range > 0, (out_of_range, length["e-"])
        stats = statistics(output)
        close("statistics ddd_mu-", float(stats["ddd_mu-"]["value"]), by_particle["mu-"]["ddd_MeV_g"], 1e-9)
        close("statistics ddd_total", float(stats["ddd_total"]["value"]), by_particle["mu-"]["ddd_MeV_g"], 1e-9)
        close("statistics sum_sq", float(stats["ddd_mu-"]["sum_sq"]), by_particle["mu-"]["ddd_sum_sq_MeV2_g2"], 1e-9)
        assert stats["ddd_total"]["unit"] == "MeV/g" and int(stats["ddd_total"]["n_events"]) == 200, stats
        rel = float(stats["ddd_total"]["rel_error"])
        print(f"  relative error {rel:.4g}")
        assert 0 < rel < 0.05, rel

        print("neutrons: zero-deposit steps, constant table")
        events = 2000
        output, _ = r.run("neutron", 1.0, events, {"neutron": flat}, thickness=0.1, hits=False)
        ddd = sum(float(row["ddd_MeV_g"]) for row in rows(output, "displacement_volume_summary")
                  if row["particle"] == "neutron")
        close("neutron DDD [MeV/g]", ddd, 2e-3 * 100.0 * events / (100 * 100), 0.005)

        print("ROOT-only output")
        output, _ = r.run("mu-", 1000, 20, {"mu-": mu}, hits=False, fmt="root")
        assert not list(output.glob("displacement_volume_summary*.csv"))
        assert float(statistics(output)["ddd_total"]["value"]) > 0

        print("failures")
        bad = [
            (dict(extra=""), "needs [scoring.displacement]"),
            (dict(extra="[scoring.displacement]\nproton = missing.csv\n"), "cannot open NIEL table"),
            (dict(extra=f"[scoring.displacement]\nproton = {table(work / 'hdr.csv', [])}\n".replace(
                "energy_MeV,niel_MeV_cm2_g", "E,niel")), "header must be"),
            (dict(extra=f"[scoring.displacement]\nproton = {table(work / 'dec.csv', [(2, 1), (1, 1)])}\n"),
             "strictly increasing"),
            (dict(extra=f"[scoring.displacement]\nproton = {table(work / 'neg.csv', [(1, -1), (2, 1)])}\n"),
             "NIEL must be finite and >= 0"),
            (dict(extra=f"[scoring.displacement]\nproton = {table(work / 'one.csv', [(1, 1)])}\n"),
             "at least 2 rows"),
            (dict(auto="false"), "requires [scoring]/auto_create_default_scorers = true"),
        ]
        (work / "hdr.csv").write_text("E,niel\n1,1\n2,1\n", encoding="utf-8")
        for options, message in bad:
            _, log = r.run("proton", 10, 1, {"proton": flat}, expect_ok=False, **options)
            assert message in log, (message, log[-2000:])
        print(f"  {len(bad)} invalid settings rejected")

        print("particle names: case-insensitive resolution and unknown names")
        # IniReader lower-cases every key, so "he3" is the only way to spell the Geant4
        # particle "He3" in the INI. The table must be stored under the canonical name,
        # otherwise no hit ever matches and the DDD stays at zero without any warning.
        # 10 MeV He3 range in Si is ~65 um, so the slab must stay thinner than that.
        output, _ = r.run("He3", 10.0, 200, {"he3": flat}, thickness=0.01, hits=False)
        he3 = [row for row in rows(output, "displacement_volume_summary") if row["particle"] == "He3"]
        assert he3, "no 'He3' row: the lower-case table key was not resolved to the Geant4 name"
        he3_length = sum(float(row["track_length_mm"]) for row in he3)
        close("He3 track length [mm]", he3_length, 0.01 * 200, 0.02)

        # An unknown name must fail before any event instead of leaving the DDD at zero,
        # and it must name the configuration line and suggest the intended particle.
        output, log = r.run("proton", 10, 1, {"protom": flat}, expect_ok=False)
        for message in ("is not a Geant4 particle name", "line ", "did you mean 'proton'"):
            assert message in log, (message, log[-2000:])
        assert not [row for row in rows(output, "displacement_volume_summary")], "DDD rows for a rejected name"
        print("  unknown name rejected before events, He3 resolved")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_displacement_damage: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
