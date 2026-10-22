"""Real Geant4 regression for the detector response pack (roadmap B4).

Generates detectors with scenarios/detector_response/make_detector.py, runs them and
checks analyze_detector.py:
  1. absolute efficiency normalisation: 100 keV photons on a bare BGO cylinder (mean
     free path ~0.3 mm, a black detector) give an absolute detection efficiency equal
     to the solid-angle fraction (1 - d / sqrt(d^2 + R^2)) / 2 of the front face,
     although the source only samples the cone around the detector;
  2. no deposit exceeds the photon energy, the full-energy peak sits at E, and with a
     resolution model the smeared photopeak has the model FWHM at E;
  3. escape-peak fields only above the pair threshold;
  4. silicon: every primary deposits, and the most probable deposit in 100 um Si is
     within 7 % of the PDG Landau-Vavilov-Bichsel value (Geant4 option4 is ~5 % high
     at this thickness; the 300 um cases are in the detector_response benchmark);
  5. invalid options fail.
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
PACK = ROOT / "scenarios" / "detector_response"
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def scenario(out: Path, *options: str, analyze: tuple[str, ...] = ()) -> dict:
    subprocess.run([sys.executable, str(PACK / "make_detector.py"), "--out", str(out), "--threads", "2", *options],
                   check=True, capture_output=True, text=True)
    result = subprocess.run([str(EXE), "--config", "main.ini"], cwd=out, capture_output=True, text=True,
                            errors="replace", timeout=1800)
    log = result.stdout + result.stderr
    assert result.returncode == 0, log[-3000:]
    assert "G4Exception-START" not in log, log[log.index("G4Exception-START") - 200:][:2000]
    subprocess.run([sys.executable, str(PACK / "analyze_detector.py"), str(out / "output"), *analyze],
                   check=True, capture_output=True, text=True)
    return json.loads((out / "output" / "detector_report.json").read_text(encoding="utf-8"))


def check(label, got, expected, tolerance):
    print(f"  {label}: {got:.6g} (expected {expected:.6g} +- {tolerance:.3g})")
    assert abs(got - expected) <= tolerance, (label, got, expected)


def main() -> int:
    if not EXE.is_file():
        print(f"backend executable missing: {EXE}")
        return 1
    work = Path(tempfile.mkdtemp(prefix="g4usim_detector_"))
    try:
        print("absolute efficiency of a black detector")
        events = 40000
        report = scenario(work / "bgo", "--crystal", "BGO", "--radius", "20mm", "--length", "30mm", "--housing", "0",
                          "--distance", "50mm", "--energy", "0.1", "--events", str(events))
        solid = (1 - 50 / math.hypot(50, 20)) / 2
        eff = report["detection_efficiency_absolute"]
        fraction = report["scenario"]["cone_fraction_of_4pi"]
        # binomial error of the intrinsic fraction, plus 1.5 % for photons that leave without a deposit
        check("absolute detection efficiency", eff, solid,
              4 * fraction * math.sqrt(solid / fraction * (1 - solid / fraction) / events) + 0.015 * solid)

        print("NaI pulse height with resolution")
        report = scenario(work / "nai", "--crystal", "NaI", "--energy", "0.662", "--events", "20000",
                          analyze=("--fwhm", "0.002,0.035,0"))
        spectrum = (work / "nai" / "output" / "pulse_height.csv").read_text(encoding="utf-8").splitlines()[1:]
        top = max(float(line.split(",")[1]) for line in spectrum if float(line.split(",")[2]) > 0)
        assert top <= 0.662 + 0.001, top
        assert report["fep_efficiency_intrinsic"] > 0.1 and 0 < report["peak_to_total"] < 1, report
        check("smeared photopeak position [MeV]", report["photopeak_position_MeV"], 0.662, 0.002)
        check("smeared photopeak FWHM [MeV]", report["photopeak_fwhm_MeV"], report["photopeak_fwhm_model_MeV"],
              0.05 * report["photopeak_fwhm_model_MeV"])
        assert "single_escape_MeV" not in report
        check("Compton edge [MeV]", report["compton_edge_MeV"], report["compton_edge_klein_nishina_MeV"], 0.01)

        print("silicon pad")
        sys.path.insert(0, str(PACK))
        import response_physics as rp
        report = scenario(work / "si", "--kind", "silicon", "--thickness", "100um", "--particle", "mu-",
                          "--energy", "4000", "--events", "40000")
        assert report["detected_fraction"] == 1.0, report["detected_fraction"]
        mpv = rp.landau_mpv("mu-", 4000.0, 0.1)[0]
        # G4EmStandardPhysics_option4 puts the mode ~5 % above the LVB value in 100 um (2026-10-22)
        check("100 um Si MPV [MeV]", report["mpv_MeV"], mpv, 0.07 * mpv + 3 * report["mpv_error_MeV"])
        assert abs(report["pdg_mpv_MeV"] - mpv) < 1e-12

        print("failures")
        for options in (["--crystal", "Unobtainium", "--energy", "1"], ["--radius", "-1mm", "--energy", "1"],
                        ["--kind", "silicon"]):
            result = subprocess.run([sys.executable, str(PACK / "make_detector.py"), "--out", str(work / "bad"),
                                     *options], capture_output=True, text=True)
            assert result.returncode != 0, options
        print("  3 invalid option sets rejected")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_detector_response: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
