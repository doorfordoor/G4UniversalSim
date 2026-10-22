"""Real Geant4 regression for the semiconductor device pack (roadmap B3).

Generates devices with scenarios/semiconductor/make_device.py, runs them and checks:
  1. the shipped SR-NIEL tables load in the backend and convert_srniel.py rebuilds a
     table from a result page (ascending order, comments, zero row below threshold);
  2. 50 MeV protons behind 1 mm Al: DDD per unit fluence in the active layer and in
     every substrate slice equals the SR-NIEL proton NIEL at the energy after the lid
     (PSTAR Al/Si CSDA inversion), and Phi_eq = DDD / 2.037e-3 MeV cm2/g;
  3. the dose of 100 MeV protons in the middle of a 2 mm substrate does not depend on
     the production cut (1 um vs 1 mm): delta-electron equilibrium;
  4. 14 MeV neutrons: DDD per unit fluence in the substrate equals the ASTM E722
     NIEL from the table (zero-deposit neutron steps);
  5. a mixed spectrum device runs and analyze_device.py writes rates and the profile;
  6. invalid options fail.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "scenarios" / "semiconductor"
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
sys.path.insert(0, str(ROOT / "scenarios" / "benchmarks" / "shielding_range"))
import make_reference as nist  # noqa: E402


def generate(out: Path, *options: str, ok: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run([sys.executable, str(PACK / "make_device.py"), "--out", str(out), "--threads", "2",
                             *options], capture_output=True, text=True)
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    return result


def run(out: Path) -> dict:
    result = subprocess.run([str(EXE), "--config", "main.ini"], cwd=out, capture_output=True, text=True,
                            errors="replace", timeout=1800)
    log = result.stdout + result.stderr
    assert result.returncode == 0, log[-3000:]
    assert "G4Exception-START" not in log, log[log.index("G4Exception-START") - 200:][:2000]
    analysis = subprocess.run([sys.executable, str(PACK / "analyze_device.py"), str(out / "output")],
                              capture_output=True, text=True)
    assert analysis.returncode == 0, analysis.stdout + analysis.stderr
    return json.loads((out / "output" / "device_report.json").read_text(encoding="utf-8"))


def table(name: str) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for line in (PACK / "niel" / name).read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and not line.startswith("energy"):
            e, v = line.split(",")
            xs.append(float(e))
            ys.append(float(v))
    return xs, ys


def interpolate(x: float, xs: list[float], ys: list[float]) -> float:
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            if ys[i] > 0 and ys[i + 1] > 0:
                t = math.log(x / xs[i]) / math.log(xs[i + 1] / xs[i])
                return math.exp(math.log(ys[i]) + t * (math.log(ys[i + 1]) - math.log(ys[i])))
            return ys[i] + (x - xs[i]) / (xs[i + 1] - xs[i]) * (ys[i + 1] - ys[i])
    raise ValueError(x)


def residual(material: str, energy: float, thickness_mm: float) -> float:
    rows = nist.pstar(material)
    energies, csda = [r[0] for r in rows], [r[4] for r in rows]
    return nist.loglog(nist.loglog(energy, energies, csda) - nist.DENSITY[material] * thickness_mm / 10.0,
                       csda, energies)


def check(label, got, expected, rel):
    print(f"  {label}: {got:.6g} (expected {expected:.6g}, rel. tolerance {rel:g})")
    assert abs(got - expected) <= rel * abs(expected), (label, got, expected)


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    work = Path(tempfile.mkdtemp(prefix="g4usim_device_"))
    try:
        print("NIEL table conversion")
        page = work / "page.html"
        page.write_text("<p>Input Parameters</p><p>Neutrons in Si</p><p>Energy (MeV)</p>"
                        "<td>2.0000e+00</td><td>3.0000e-03</td><td>3.0000e-03</td><td>4.8064e-13</td>\n"
                        "<td>1.0000e+00</td><td>0.0000e+00</td><td>0.0000e+00</td><td>0.0000e+00</td>\n",
                        encoding="utf-8")
        subprocess.run([sys.executable, str(PACK / "niel" / "convert_srniel.py"), str(page), str(work / "t.csv"),
                        "test"], check=True, capture_output=True)
        converted = (work / "t.csv").read_text(encoding="utf-8").splitlines()
        assert converted[0] == "# test" and any("Neutrons in Si" in line for line in converted), converted
        assert converted[-3:] == ["1e-06,0", "1,0", "2,0.003"], converted

        print("50 MeV protons behind 1 mm Al")
        out = work / "protons"
        generate(out, "--energy", "50", "--events", "3000", "--beol", "none", "--physics", "FTFP_BERT")
        report = run(out)
        energy = residual("G4_Al", 50.0, 1.0)
        niel_p = table("si_proton.csv")
        for name, region in report["regions"].items():
            depth_si = region["depth_mm"] + region["thickness_mm"] / 2 - report["regions"]["GateOxide"]["depth_mm"]
            expected = interpolate(residual("G4_Si", energy, depth_si), *niel_p)
            # nuclear reactions remove ~1 % of the protons per cm of Al/Si
            check(f"{name} DDD per fluence", region["ddd_MeV_g_cm2"], expected, 0.02)
            check(f"{name} Phi_eq", region["phi_eq_per_unit_fluence"], region["ddd_MeV_g_cm2"] / 2.0370e-3, 1e-3)

        print("production-cut independence of the substrate dose")
        doses = {}
        for cut in ("1 um", "1 mm"):
            out = work / f"cut_{cut.replace(' ', '')}"
            # middle 400 um slice of a 2 mm substrate: deeper than the 229 keV delta-electron range
            generate(out, "--energy", "100", "--events", "10000", "--lid", "none", "--beol", "none",
                     "--substrate", "2mm", "--slices", "5", "--em", "option4", "--physics", "FTFP_BERT",
                     "--device-cut", cut)
            region = run(out)["regions"]["Slice2"]
            doses[cut] = (region["tid_Gy_cm2"], region["tid_rel_error"])
        (d1, e1), (d2, e2) = doses["1 um"], doses["1 mm"]
        print(f"  middle slice TID: cut 1 um {d1:.5g} +- {d1 * e1:.2g}, cut 1 mm {d2:.5g} +- {d2 * e2:.2g}")
        assert abs(d1 - d2) <= 0.01 * d2 + 3 * math.hypot(d1 * e1, d2 * e2), doses

        print("14 MeV neutrons")
        out = work / "neutrons"
        generate(out, "--particle", "neutron", "--energy", "14", "--events", "20000", "--lid", "none",
                 "--beol", "none", "--slices", "1")
        region = run(out)["regions"]["Slice0"]
        check("substrate DDD per fluence", region["ddd_MeV_g_cm2"], interpolate(14.0, *table("si_neutron.csv")),
              0.01 + 3 * region["ddd_rel_error"])

        print("mixed spectrum device")
        out = work / "mixed"
        generate(out, "--particle", "mixed", "--events", "300")
        report = run(out)
        assert len(report["regions"]) == 12 and "tid_Gy_per_year" in report["regions"]["Active"]
        assert (out / "output" / "depth_profile.csv").read_text(encoding="utf-8").count("\n") == 13

        print("failures")
        generate(work / "bad1", "--particle", "neutron", ok=False)
        generate(work / "bad2", "--lid", "Unobtainium:1mm", ok=False)
        generate(work / "bad3", "--slices", "0", ok=False)
        print("  3 invalid option sets rejected")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_semiconductor_device: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
