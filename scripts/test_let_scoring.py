"""Real Geant4 regression for track- and dose-averaged LET ([scoring] let = true).

Mono-energetic protons cross a 20 um water slab (sensitive) in vacuum, 2 threads.
Checks:
  1. proton-only LET_t equals the Bethe electronic stopping power of liquid water
     (I = 75 eV, as in ICRU 49 / NIST PSTAR) at the mean slab energy within 2 %,
     at 100 MeV (PSTAR 7.289 MeV cm2/g -> 0.729 keV/um) and 10 MeV;
  2. LET_d >= LET_t, and LET_d ~ LET_t for a thin slab with protons only;
  3. ROOT per-worker sums (scripts/g4usim_io-style merge) reproduce the CSV;
  4. particles = all includes secondary electrons (more steps), and output is finite;
  5. a neutral beam (gamma) gives no proton LET rows; macro enabling is still rejected.
Requires uproot.
"""

from __future__ import annotations

import csv
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
try:
    import uproot
except ImportError:
    print("SKIP: uproot is not installed")
    sys.exit(2)

SLAB_UM = 20.0

GEOMETRY = f"""
[world]
size = 20 cm, 20 cm, 20 cm
material = G4_Galactic
[target]
name = WaterSlab
shape = box
size = 5 cm, 5 cm, {SLAB_UM} um
material = G4_WATER
position = 0 mm, 0 mm, 0 mm
sensitive = true
"""


def config(geometry: Path, particle: str, energy_mev: float, let_particles: str) -> str:
    return f"""
[run]
threads = 2
seed = 31415
[output]
format = both
[materials]
file = {ROOT.as_posix()}/config/materials/material.ini
[geometry]
template = simple_box
config = {geometry.as_posix()}
[physics]
reference = FTFP_BERT_EMZ
default_cut = 10 um
[source]
particle = {particle}
energy = {energy_mev} MeV
position_type = point
position = 0,0,-5 cm
direction = 0,0,1
[scoring]
enabled = true
hits = false
event_edep = true
edep = true
let = true
dose = true
fluence = true
auto_create_default_scorers = true
[scoring.let]
particles = {let_particles}
"""


def bethe_water_mev_cm2_per_g(kinetic_mev: float) -> float:
    """Bethe electronic mass stopping power of liquid water for protons (no shell/density corrections)."""
    mp, me, k, z_over_a, i_mev = 938.272088, 0.51099895, 0.307075, 0.555087, 75.0e-6
    gamma = 1.0 + kinetic_mev / mp
    beta2 = 1.0 - 1.0 / gamma**2
    bg2 = beta2 * gamma**2
    tmax = 2.0 * me * bg2 / (1.0 + 2.0 * gamma * me / mp + (me / mp) ** 2)
    return k * z_over_a / beta2 * (0.5 * math.log(2.0 * me * bg2 * tmax / i_mev**2) - beta2)


def run(work: Path, name: str, text: str, macro: str = "/run/initialize\n/run/beamOn 300\n",
        expect_ok: bool = True) -> tuple[Path, str]:
    (work / f"{name}.ini").write_text(text, encoding="utf-8")
    (work / f"{name}.mac").write_text(macro, encoding="utf-8")
    output = work / name
    result = subprocess.run([str(EXE), "--config", str(work / f"{name}.ini"), "--macro", str(work / f"{name}.mac"),
                             "--output", str(output)], cwd=ROOT, capture_output=True, text=True,
                            errors="replace", timeout=600)
    log = result.stdout + result.stderr
    if expect_ok:
        assert result.returncode == 0, f"{name}:\n{log[-2500:]}"
    else:
        assert result.returncode != 0, f"{name}: expected failure"
    return output, log


def merged(output: Path) -> dict[str, float]:
    with uproot.open(output / "g4usim.root") as root:
        data = root["let"].arrays(library="np")
    sums = {key: float(data[key].sum()) for key in ("steps", "sum_wl_mm", "sum_wSl_MeV", "sum_wS2l_MeV2_per_mm")}
    csv_rows = list(csv.DictReader(open(f, encoding="utf-8")) for f in sorted(output.glob("let_volume_summary_t*.csv")))
    csv_sums = {key: 0.0 for key in sums}
    rows = 0
    for reader in csv_rows:
        for row in reader:
            rows += 1
            for key in csv_sums:
                csv_sums[key] += float(row[key])
    assert rows == len(data["runID"]), (rows, len(data["runID"]))
    for key in sums:
        assert math.isclose(sums[key], csv_sums[key], rel_tol=1e-9, abs_tol=1e-300), (key, sums[key], csv_sums[key])
    if sums["sum_wl_mm"] <= 0:
        return {"steps": 0.0}
    let_t = sums["sum_wSl_MeV"] / sums["sum_wl_mm"]
    let_d = sums["sum_wS2l_MeV2_per_mm"] / sums["sum_wSl_MeV"]
    return {"steps": sums["steps"], "let_t": let_t, "let_d": let_d}


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_let_"))
    try:
        geometry = work / "slab.ini"
        geometry.write_text(GEOMETRY, encoding="utf-8")
        results = {}
        for energy in (100.0, 10.0):
            output, _ = run(work, f"p{int(energy)}", config(geometry, "proton", energy, "proton"))
            r = merged(output)
            # Mean energy in the slab: subtract half the (Bethe) energy loss across it.
            loss = bethe_water_mev_cm2_per_g(energy) * 1.0 * SLAB_UM * 1e-4
            expected = bethe_water_mev_cm2_per_g(energy - 0.5 * loss) / 10.0   # MeV cm2/g * 1 g/cm3 -> keV/um
            ratio = r["let_t"] / expected
            print(f"{energy:5.0f} MeV p: LET_t={r['let_t']:.4f} keV/um, LET_d={r['let_d']:.4f}, "
                  f"Bethe={expected:.4f}, ratio={ratio:.4f}, steps={r['steps']:.0f}")
            assert abs(ratio - 1.0) < 0.02, ratio
            assert r["let_d"] >= r["let_t"] * (1 - 1e-12)
            assert r["let_d"] < 1.05 * r["let_t"], (r["let_d"], r["let_t"])
            results[energy] = r

        output, _ = run(work, "p10_all", config(geometry, "proton", 10.0, "all"))
        everything = merged(output)
        assert everything["steps"] > results[10.0]["steps"], (everything["steps"], results[10.0]["steps"])
        assert math.isfinite(everything["let_t"]) and everything["let_d"] >= everything["let_t"] * (1 - 1e-12)
        print(f"10 MeV, all charged: LET_t={everything['let_t']:.4f}, LET_d={everything['let_d']:.4f} keV/um, "
              f"steps={everything['steps']:.0f} (protons only: {results[10.0]['steps']:.0f})")

        output, _ = run(work, "gamma", config(geometry, "gamma", 1.0, "proton"))
        assert merged(output)["steps"] == 0
        print("neutral beam: no proton LET contributions")

        _, log = run(work, "macro_let", config(geometry, "proton", 10.0, "proton").replace("let = true", "let = false"),
                     macro="/AIHL/scoring/let true\n/run/initialize\n/run/beamOn 1\n", expect_ok=False)
        assert "main INI [scoring]" in log, log[-1200:]
        print("macro LET enabling rejected with INI guidance")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_let_scoring: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
