"""Builds reference.csv of the detector_response benchmark (analytic references).

  compton_edge   Klein-Nishina kinematics, E_c = E 2a / (1 + 2a), a = E / m_e c^2, in a small
                 plastic scintillator (single scattering dominates; in large high-Z
                 crystals multiple Compton events fill in above the edge)
  escape_peak    pair production, single and double escape lines E - m_e c^2, E - 2 m_e c^2
  landau_mpv     most probable energy loss in a thin silicon detector, PDG
                 Landau-Vavilov-Bichsel formula with the Sternheimer density effect
All formulas are in scenarios/detector_response/response_physics.py.

    python scenarios/benchmarks/detector_response/make_reference.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "detector_response"))
import response_physics as rp  # noqa: E402

#   kind, detector settings for make_detector.py, particle, energy MeV
CASES = [
    ("compton_edge", "plastic 12.7mm 25.4mm", "gamma", 0.662),
    ("compton_edge", "plastic 12.7mm 25.4mm", "gamma", 1.332),
    ("single_escape", "HPGe 30mm 50mm", "gamma", 4.44),
    ("double_escape", "HPGe 30mm 50mm", "gamma", 4.44),
    ("landau_mpv", "Si 300um", "mu-", 4000.0),
    ("landau_mpv", "Si 300um", "proton", 300.0),
    ("landau_mpv", "Si 300um", "proton", 1000.0),
]


def main() -> None:
    lines = ["# detector_response references from response_physics.py (Klein-Nishina kinematics,",
             "# pair-production escape lines, PDG Landau-Vavilov-Bichsel MPV with Sternheimer delta).",
             "kind,detector,particle,energy_MeV,reference_MeV,source"]
    for kind, detector, particle, energy in CASES:
        if kind == "compton_edge":
            value, source = rp.compton_edge(energy), "Klein-Nishina kinematics"
        elif kind == "single_escape":
            value, source = energy - rp.ME, "E - m_e c^2"
        elif kind == "double_escape":
            value, source = energy - 2 * rp.ME, "E - 2 m_e c^2"
        else:
            value, source = rp.landau_mpv(particle, energy, 0.3)[0], "PDG Landau-Vavilov-Bichsel (Eq. 34.12)"
        lines.append(f"{kind},{detector},{particle},{energy:g},{value:.6g},{source}")
    (HERE / "reference.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
