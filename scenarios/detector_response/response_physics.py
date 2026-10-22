"""Analytic references for detector response (roadmap Phase B4).

- Compton kinematics: edge of the single-scatter electron spectrum
  E_c = E 2a / (1 + 2a) with a = E / m_e c^2, and the backscatter energy E / (1 + 2a).
- Pair production: single / double escape peaks at E - m_e c^2 and E - 2 m_e c^2.
- Most probable energy loss of a charged particle in a thin absorber
  (Landau-Vavilov-Bichsel, Review of Particle Physics, "Passage of particles through
  matter", Eq. 34.12):
      Delta_p = xi [ ln(2 m c^2 b^2 g^2 / I) + ln(xi / I) + j - b^2 - delta(bg) ],
      xi = (K / 2) <Z/A> z^2 x / b^2,  K = 0.307075 MeV cm2/mol,  j = 0.200,
  with the Sternheimer density correction delta. The silicon parameters are those of
  Geant4's G4DensityEffectData for G4_Si (Sternheimer, Berger and Seltzer 1984):
  I = 173 eV, C = 4.4351, x0 = 0.2014, x1 = 2.8715, a = 0.14921, k = 3.2546, d0 = 0.14.
"""

from __future__ import annotations

import math

ME = 0.51099895         # MeV
K = 0.307075            # MeV cm2 / mol
J = 0.200
MASS = {"proton": 938.272088, "mu-": 105.6583755, "mu+": 105.6583755, "pi-": 139.57039, "pi+": 139.57039,
        "e-": ME, "e+": ME, "alpha": 3727.3794066, "deuteron": 1875.61294257}
CHARGE = {"alpha": 2}
SILICON = {"Z_over_A": 14 / 28.0855, "density": 2.33, "I_MeV": 173e-6, "C": 4.4351, "x0": 0.2014,
           "x1": 2.8715, "a": 0.14921, "k": 3.2546, "delta0": 0.14}


def compton_edge(energy: float) -> float:
    a = energy / ME
    return energy * 2 * a / (1 + 2 * a)


def backscatter_peak(energy: float) -> float:
    return energy / (1 + 2 * energy / ME)


def density_effect(bg: float, m: dict = SILICON) -> float:
    x = math.log10(bg)
    if x >= m["x1"]:
        return 2 * math.log(10) * x - m["C"]
    if x >= m["x0"]:
        return 2 * math.log(10) * x - m["C"] + m["a"] * (m["x1"] - x) ** m["k"]
    return m["delta0"] * 10 ** (2 * (x - m["x0"]))   # conductors / semiconductors below x0


def landau_mpv(particle: str, kinetic: float, thickness_mm: float, m: dict = SILICON) -> tuple[float, float]:
    """(most probable energy loss, xi) in MeV for a particle of kinetic energy [MeV]."""
    mass = MASS[particle]
    gamma = 1 + kinetic / mass
    beta2 = 1 - 1 / gamma ** 2
    bg2 = beta2 * gamma ** 2
    z = CHARGE.get(particle, 1)
    xi = K / 2 * m["Z_over_A"] * z ** 2 * m["density"] * thickness_mm / 10.0 / beta2
    mpv = xi * (math.log(2 * ME * bg2 / m["I_MeV"]) + math.log(xi / m["I_MeV"]) + J - beta2
                - density_effect(math.sqrt(bg2), m))
    return mpv, xi


def half_sample_mode(values: list[float]) -> float:
    """Robust mode estimator (Bickel and Fruehwirth 2006): repeatedly keep the shortest half."""
    data = sorted(values)
    while len(data) > 3:
        half = (len(data) + 1) // 2
        widths = [data[i + half - 1] - data[i] for i in range(len(data) - half + 1)]
        start = widths.index(min(widths))
        data = data[start:start + half]
    if len(data) == 3:
        left, right = data[1] - data[0], data[2] - data[1]
        return (data[0] + data[1]) / 2 if left < right else (data[1] + data[2]) / 2 if right < left else data[1]
    return sum(data) / len(data)


def mode_with_error(values: list[float], batches: int = 20) -> tuple[float, float]:
    """Half-sample mode of all values and its standard error from independent batches."""
    size = len(values) // batches
    modes = [half_sample_mode(values[i * size:(i + 1) * size]) for i in range(batches)]
    mean = sum(modes) / batches
    error = math.sqrt(sum((x - mean) ** 2 for x in modes) / (batches - 1) / batches)
    return half_sample_mode(values), error
