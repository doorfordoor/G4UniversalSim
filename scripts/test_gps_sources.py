"""Real Geant4 regression for the roadmap A4 GPS sources.

Protons start inside a large sensitive water box, so the first hit of track 1
in every event carries the exact primary vertex, direction and kinetic energy
(pre-step point). 2 worker threads. Checks, against analytic expectations:
  energy  gauss, uniform, power, exp, histogram file and point-wise file spectra;
  position volume sphere / cylinder / box, beam spot (circle, ellipse),
           rotated plane (rot1/rot2), plane annulus, volume confinement;
  angular cosine law, cone (isotropic with max_theta around a tilted axis),
          full isotropic, beam1d, beam2d, focused;
  multiple weighted [source.<name>] sources (fractions, per-source energy);
  ions: Na-24 at rest with radioactive decay (decay to the 4122.9 keV Mg-24 level
        and the mean beta energy 554 keV, NNDC) and a 12C ion beam. Co-60 is not used:
        Geant4 >= 11.2 skips decays of nuclides whose lifetime exceeds its 1-year
        default time threshold;
  phase space: [phase_space] records particles crossing into a volume; replaying
        the worker files with [source] phase_space_file reproduces every recorded
        entry state exactly (event k = history k) and the same mean energy deposit;
        kill = true stops recorded particles before they deposit; hand-written
        multi-particle histories and weights replay as one event each;
  failures: missing confinement volume, mixed [source]/[source.<name>],
        unknown keys, bad spectra and conflicting fields fail before events;
        /AIHL/source/energy is rejected with several sources.
Tolerances are 5 standard errors of the sample statistic (seeds fixed).
"""

from __future__ import annotations

import csv
import math
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

GEOMETRY = """
[world]
size = 1 m, 1 m, 1 m
material = G4_Galactic
[target]
name = Water
shape = box
size = {size}, {size}, {size}
material = G4_WATER
position = 0 mm, 0 mm, 0 mm
sensitive = true
"""

MAIN = """
[run]
threads = 2
seed = {seed}
[output]
format = csv
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = simple_box
config = {geometry}
[physics]
reference = FTFP_BERT
default_cut = 1 mm
{physics}
[scoring]
enabled = true
hits = true
event_edep = false
edep = false
auto_create_default_scorers = true
{source}
"""


class Case:
    def __init__(self, work: Path):
        self.work = work
        self.count = 0

    def run(self, source: str, events: int = 3000, size: str = "40 cm", physics: str = "",
            macro_extra: str = "", expect_ok: bool = True, files: dict[str, str] | None = None):
        self.count += 1
        name = f"case{self.count:02d}"
        geometry = self.work / f"{name}_geometry.ini"
        geometry.write_text(GEOMETRY.format(size=size), encoding="utf-8")
        for filename, text in (files or {}).items():
            (self.work / filename).write_text(text, encoding="utf-8")
        ini = self.work / f"{name}.ini"
        ini.write_text(MAIN.format(seed=1000 + self.count, root=ROOT.as_posix(), geometry=geometry.as_posix(),
                                   physics=physics, source=source), encoding="utf-8")
        macro = self.work / f"{name}.mac"
        macro.write_text(f"/run/initialize\n{macro_extra}/run/beamOn {events}\n", encoding="utf-8")
        output = self.work / name
        result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(macro), "--output", str(output)],
                                cwd=self.work, capture_output=True, text=True, errors="replace", timeout=1200)
        log = result.stdout + result.stderr
        if expect_ok:
            assert result.returncode == 0, f"{name} failed:\n{source}\n{log[-3000:]}"
        else:
            assert result.returncode != 0, f"{name} unexpectedly succeeded:\n{source}"
        return output, log


def hits(output: Path):
    pattern = re.compile(r"hits_t(\d+)\.csv$")
    for path in sorted(output.glob("hits_t*.csv")):
        match = pattern.fullmatch(path.name)
        if not match:
            continue
        thread = int(match.group(1))
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                yield thread, row


def first_steps(output: Path, select=lambda row: row["trackID"] == "1"):
    """First recorded step of each selected track: (thread, event, track) -> row."""
    first = {}
    for thread, row in hits(output):
        if select(row):
            key = (thread, int(row["eventID"]), int(row["trackID"]))
            first.setdefault(key, row)
    return list(first.values())


def primaries(output: Path, events: int):
    rows = first_steps(output)
    assert len(rows) == events, f"expected one primary per event, got {len(rows)} for {events}"
    return [{"x": float(r["x0_mm"]), "y": float(r["y0_mm"]), "z": float(r["z0_mm"]),
             "u": float(r["px"]), "v": float(r["py"]), "w": float(r["pz"]),
             "E": float(r["kineticEnergy_MeV"]), "particle": r["particle"]} for r in rows]


def mean(values):
    values = list(values)
    return sum(values) / len(values)


def std(values):
    values = list(values)
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def check_mean(label, values, expected, sigma=None):
    values = list(values)
    m = mean(values)
    se = (sigma if sigma is not None else std(values)) / math.sqrt(len(values))
    print(f"  {label}: mean {m:.5g} expected {expected:.5g} (+-{se:.2g})")
    assert abs(m - expected) < 5 * se + 1e-9, (label, m, expected, se)


def check_std(label, values, expected):
    values = list(values)
    s = std(values)
    se = expected / math.sqrt(2 * (len(values) - 1))
    print(f"  {label}: std {s:.5g} expected {expected:.5g} (+-{se:.2g})")
    assert abs(s - expected) < 5 * se, (label, s, expected)


def check_fraction(label, count, total, p):
    se = math.sqrt(p * (1 - p) / total)
    print(f"  {label}: {count / total:.4f} expected {p:.4f} (+-{se:.2g})")
    assert abs(count / total - p) < 5 * se + 1e-12, (label, count, total, p)


PROTON = "particle = proton\n"
POINT = "position_type = point\nposition = 0,0,0 mm\n"


def energy_cases(case: Case) -> None:
    print("energy spectra")
    n = 3000
    p = primaries(case.run(f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = gauss\nenergy = 10 MeV\n"
                           "energy_sigma = 1 MeV\n", n)[0], n)
    check_mean("gauss mean", (q["E"] for q in p), 10.0, 1.0)
    check_std("gauss sigma", (q["E"] for q in p), 1.0)

    p = primaries(case.run(f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = uniform\n"
                           "energy_min = 5 MeV\nenergy_max = 15 MeV\n", n)[0], n)
    assert all(5.0 <= q["E"] <= 15.0 for q in p)
    check_mean("uniform mean", (q["E"] for q in p), 10.0, 10 / math.sqrt(12))
    check_std("uniform std", (q["E"] for q in p), 10 / math.sqrt(12))

    lo, hi = 2.0, 20.0
    p = primaries(case.run(f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = power\n"
                           f"energy_min = {lo} MeV\nenergy_max = {hi} MeV\nalpha = -2\n", n)[0], n)
    assert all(lo <= q["E"] <= hi for q in p)
    check_mean("power(-2) mean", (q["E"] for q in p), math.log(hi / lo) / (1 / lo - 1 / hi))

    e0, lo, hi = 3.0, 1.0, 20.0
    p = primaries(case.run(f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = exp\n"
                           f"energy_min = {lo} MeV\nenergy_max = {hi} MeV\nezero = {e0} MeV\n", n)[0], n)
    norm = math.exp(-lo / e0) - math.exp(-hi / e0)
    expected = ((lo + e0) * math.exp(-lo / e0) - (hi + e0) * math.exp(-hi / e0)) / norm
    check_mean("exp mean", (q["E"] for q in p), expected)

    histogram = "# test spectrum\ne_low_MeV,e_high_MeV,weight\n2,4,1\n4,6,3\n6,10,0\n10,12,2\n"
    p = primaries(case.run(f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = histogram\n"
                           "spectrum_file = spectrum_hist.csv\n", n, files={"spectrum_hist.csv": histogram})[0], n)
    assert all(2.0 <= q["E"] <= 12.0 and not (6.0 < q["E"] < 10.0) for q in p)
    for (a, b, w) in ((2, 4, 1), (4, 6, 3), (10, 12, 2)):
        check_fraction(f"histogram bin {a}-{b}", sum(a <= q["E"] < b for q in p), n, w / 6)

    points = "energy_keV,density\n2000,0\n10000,1\n"
    p = primaries(case.run(f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = points\n"
                           "spectrum_file = spectrum_points.csv\n", n, files={"spectrum_points.csv": points})[0], n)
    assert all(2.0 <= q["E"] <= 10.0 for q in p)
    check_mean("points (triangle) mean", (q["E"] for q in p), 2 + 2 / 3 * 8, 8 / math.sqrt(18))


def position_cases(case: Case) -> None:
    print("positions")
    n = 3000
    base = f"[source]\n{PROTON}energy = 5 MeV\nisotropic = true\n"
    p = primaries(case.run(base + "position_type = volume\nshape = sphere\ncenter = 10,0,0 mm\nradius = 50 mm\n", n)[0], n)
    r = [math.dist((q["x"], q["y"], q["z"]), (10, 0, 0)) for q in p]
    assert max(r) <= 50.0 + 1e-6
    check_mean("sphere (r/R)^3", ((x / 50) ** 3 for x in r), 0.5, math.sqrt(1 / 12))

    p = primaries(case.run(base + "position_type = volume\nshape = cylinder\ncenter = 0,0,0 mm\nradius = 30 mm\n"
                           "halfz = 40 mm\n", n)[0], n)
    assert all(abs(q["z"]) <= 40 + 1e-6 and math.hypot(q["x"], q["y"]) <= 30 + 1e-6 for q in p)
    check_mean("cylinder rho^2", (q["x"] ** 2 + q["y"] ** 2 for q in p), 450.0, 900 / math.sqrt(12))
    check_std("cylinder z", (q["z"] for q in p), 80 / math.sqrt(12))

    p = primaries(case.run(base + "position_type = volume\nshape = box\ncenter = 0,0,0 mm\nhalfx = 10 mm\n"
                           "halfy = 20 mm\nhalfz = 30 mm\n", n)[0], n)
    for axis, half in (("x", 10), ("y", 20), ("z", 30)):
        assert all(abs(q[axis]) <= half + 1e-6 for q in p)
        check_std(f"box {axis}", (q[axis] for q in p), 2 * half / math.sqrt(12))

    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\nposition_type = beam\nshape = circle\n"
                           "center = 0,0,-100 mm\nbeam_sigma = 2 mm\ndirection = +z\n", n)[0], n)
    assert all(abs(q["z"] + 100) < 1e-6 for q in p)
    check_std("beam circle x", (q["x"] for q in p), 2.0)
    check_std("beam circle y", (q["y"] for q in p), 2.0)
    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\nposition_type = beam\nshape = ellipse\n"
                           "center = 0,0,-100 mm\nbeam_sigma_x = 1 mm\nbeam_sigma_y = 3 mm\ndirection = +z\n", n)[0], n)
    check_std("beam ellipse x", (q["x"] for q in p), 1.0)
    check_std("beam ellipse y", (q["y"] for q in p), 3.0)

    # Rectangle spanned by rot1 = x and rot2 = z: an XZ plane at y = 5 mm.
    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\nposition_type = plane\nshape = rectangle\n"
                           "center = 0,5,0 mm\nhalfx = 10 mm\nhalfy = 20 mm\nrot1 = 1,0,0\nrot2 = 0,0,1\n"
                           "direction = 0,1,0\n", n)[0], n)
    assert all(abs(q["y"] - 5) < 1e-6 and abs(q["x"]) <= 10 + 1e-6 and abs(q["z"]) <= 20 + 1e-6 for q in p)
    check_std("rotated plane z", (q["z"] for q in p), 40 / math.sqrt(12))
    print("  rotated rectangle lies in the XZ plane")

    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\nposition_type = plane\nshape = annulus\n"
                           "center = 0,0,-50 mm\nradius = 20 mm\ninner_radius = 10 mm\ndirection = +z\n", n)[0], n)
    rho = [math.hypot(q["x"], q["y"]) for q in p]
    assert all(10 - 1e-6 <= x <= 20 + 1e-6 for x in rho)
    check_mean("annulus rho^2", (x * x for x in rho), 250.0, 300 / math.sqrt(12))

    # Confinement: a sphere larger than the 40 mm water cube, confined to it.
    p = primaries(case.run(base + "position_type = volume\nshape = sphere\ncenter = 0,0,0 mm\nradius = 40 mm\n"
                           "confine = Water_PV\n", 1000, size="40 mm")[0], 1000)
    assert all(max(abs(q["x"]), abs(q["y"]), abs(q["z"])) <= 20 + 1e-6 for q in p)
    corner = sum(math.dist((q["x"], q["y"], q["z"]), (0, 0, 0)) > 21 for q in p)
    assert corner > 0, "confined sampling never reached the cube corners"
    check_std("confined box x", (q["x"] for q in p), 40 / math.sqrt(12))


def angular_cases(case: Case) -> None:
    print("angular distributions")
    n = 3000
    plane = f"[source]\n{PROTON}energy = 5 MeV\nposition_type = plane\nshape = circle\ncenter = 0,0,0 mm\nradius = 10 mm\n"
    p = primaries(case.run(plane + "direction = +z\nangular = cos\n", n)[0], n)
    assert all(q["w"] >= -1e-9 for q in p)
    check_mean("cosine law <cos theta>", (q["w"] for q in p), 2 / 3, math.sqrt(1 / 18))

    axis = (1 / math.sqrt(2), 0.0, 1 / math.sqrt(2))
    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\n{POINT}direction = 1,0,1\nangular = isotropic\n"
                           "max_theta = 30 deg\n", n)[0], n)
    mu = [q["u"] * axis[0] + q["v"] * axis[1] + q["w"] * axis[2] for q in p]
    c30 = math.cos(math.radians(30))
    assert min(mu) >= c30 - 1e-6, min(mu)
    check_mean("cone <cos theta>", mu, (1 + c30) / 2, (1 - c30) / math.sqrt(12))

    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\n{POINT}angular = isotropic\n", n)[0], n)
    check_mean("isotropic <w>", (q["w"] for q in p), 0.0, 1 / math.sqrt(3))
    check_mean("isotropic <w^2>", (q["w"] ** 2 for q in p), 1 / 3, math.sqrt(4 / 45))

    sigma = math.radians(2.0)
    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\n{POINT}direction = +z\nangular = beam1d\n"
                           "angular_sigma = 2 deg\n", n)[0], n)
    assert all(q["w"] > 0.95 for q in p), "beam1d must point along +z"
    theta2 = [math.acos(min(1.0, q["w"])) ** 2 for q in p]
    # GPS beam1d draws the polar angle itself from Gauss(0, sigma): <theta^2> = sigma^2.
    check_mean("beam1d <theta^2>/sigma^2", (t / sigma**2 for t in theta2), 1.0, math.sqrt(2.0))

    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\n{POINT}direction = +z\nangular = beam2d\n"
                           "angular_sigma_x = 1 deg\nangular_sigma_y = 4 deg\n", n)[0], n)
    assert all(q["w"] > 0.95 for q in p)
    check_std("beam2d x angle", (math.atan2(q["u"], q["w"]) for q in p), math.radians(1))
    check_std("beam2d y angle", (math.atan2(q["v"], q["w"]) for q in p), math.radians(4))

    p = primaries(case.run(f"[source]\n{PROTON}energy = 5 MeV\nposition_type = plane\nshape = circle\n"
                           "center = 0,0,-50 mm\nradius = 20 mm\nangular = focused\nfocus = 0,0,50 mm\n", n)[0], n)
    worst = 0.0
    for q in p:
        to_focus = (-q["x"], -q["y"], 50 - q["z"])
        length = math.hypot(*to_focus)
        worst = max(worst, 1 - (q["u"] * to_focus[0] + q["v"] * to_focus[1] + q["w"] * to_focus[2]) / length)
    assert worst < 1e-9, worst
    print("  focused: every primary points at the focus")


def multi_source_case(case: Case) -> None:
    print("multiple weighted sources")
    n = 4000
    text = ("[source.low]\nparticle = proton\nenergy = 5 MeV\nposition_type = point\nposition = -50,0,0 mm\n"
            "direction = +z\nintensity = 1\n"
            "[source.high]\nparticle = proton\nenergy_type = gauss\nenergy = 15 MeV\nenergy_sigma = 0.5 MeV\n"
            "position_type = point\nposition = 50,0,0 mm\nangular = isotropic\nintensity = 3\n")
    output, _ = case.run(text, n)
    p = primaries(output, n)
    low = [q for q in p if abs(q["x"] + 50) < 1e-6]
    high = [q for q in p if abs(q["x"] - 50) < 1e-6]
    assert len(low) + len(high) == n
    check_fraction("intensity fraction of [source.high]", len(high), n, 0.75)
    assert all(abs(q["E"] - 5) < 1e-9 and q["w"] > 0.999999 for q in low)
    check_mean("[source.high] energy", (q["E"] for q in high), 15.0, 0.5)
    summary = (output / "run_summary.txt").read_text(encoding="utf-8")
    assert "source_count = 2" in summary and "name=high intensity=3" in summary, summary[-3000:]

    _, log = case.run(text, 1, macro_extra="/AIHL/source/energy 2 MeV\n", expect_ok=False)
    assert "several [source.<name>] sources" in log, log[-2000:]
    print("  /AIHL/source/energy rejected with several sources")


def level_name(particle: str, nucleus: str, energy_keV: float) -> bool:
    """Return True when ``particle`` is ``nucleus`` in the excited level at ``energy_keV``.

    Geant4 prints the level energy with a version-dependent number of decimals
    (``Ni60[2505.753]`` under 11.3, ``Ni60[2505.75300]`` under 11.4), so compare the
    value instead of the formatted string.
    """
    prefix = f"{nucleus}["
    if not particle.startswith(prefix) or not particle.endswith("]"):
        return False
    try:
        value = float(particle[len(prefix):-1])
    except ValueError:
        return False
    return abs(value - energy_keV) <= 0.01


def ion_cases(case: Case) -> None:
    print("ions")
    n = 2000
    output, _ = case.run("[source]\nparticle = ion\nion = 11 24\nenergy = 0 keV\nposition_type = point\n"
                         "position = 0,0,0 mm\nangular = isotropic\n", n,
                         physics="extra_modules = radioactive_decay")
    # Gammas deposit no energy on their own steps and so leave no hits; the
    # decay branch is checked through the recoiling daughter instead. NNDC:
    # 99.86 % of Na-24 decays feed the 4122.9 keV level of Mg-24, which
    # de-excites by the 2754.0 + 1368.6 keV cascade.
    daughters = [r["particle"] for r in first_steps(output, lambda r: r["parentID"] == "1" and r["particle"].startswith("Mg24"))]
    level = sum(level_name(name, "Mg24", 4122.853) for name in daughters)
    print(f"  Na-24: {len(daughters)} Mg-24 recoils, {level} in the 4122.9 keV level")
    assert len(daughters) > 0.98 * n and level > 0.99 * len(daughters), (len(daughters), level)
    betas = [float(r["kineticEnergy_MeV"])
             for r in first_steps(output, lambda r: r["particle"] == "e-" and r["parentID"] == "1")]
    assert len(betas) > 0.9 * n, len(betas)
    beta_mean = mean(betas)
    print(f"  Na-24 beta: {len(betas)} electrons, mean {beta_mean * 1000:.1f} keV (NNDC 554 keV)")
    assert abs(beta_mean - 0.554) < 0.05 * 0.554, beta_mean

    output, _ = case.run("[source]\nparticle = ion\nion = 6 12 6\nenergy = 1200 MeV\nposition_type = point\n"
                         "position = 0,0,0 mm\ndirection = +z\n", 50)
    p = primaries(output, 50)
    assert {q["particle"] for q in p} == {"C12"}, {q["particle"] for q in p}
    assert all(abs(q["E"] - 1200) < 1e-6 for q in p)
    print("  12C ion beam: primaries are C12 at 1200 MeV")


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def edep_per_event(output: Path) -> dict[int, float]:
    totals: dict[int, float] = defaultdict(float)
    for _, row in hits(output):
        totals[int(row["eventID"])] += float(row["edep_MeV"])
    return totals


def phase_space_cases(case: Case) -> None:
    print("phase space")
    n = 600
    # Stage A: 50 MeV protons (Gaussian energy, beam spot and divergence) cross a
    # vacuum gap into a 10 cm water cube; record what enters the cube.
    source = ("[source]\nparticle = proton\nenergy_type = gauss\nenergy = 50 MeV\nenergy_sigma = 2 MeV\n"
              "position_type = beam\nshape = circle\ncenter = 0,0,-150 mm\nbeam_sigma = 3 mm\n"
              "direction = +z\nangular = beam1d\nangular_sigma = 1 deg\n"
              "[phase_space]\nvolume = Water_PV\nparticles = proton\n")
    stage_a, _ = case.run(source, n, size="10 cm")
    files = sorted(stage_a.glob("phase_space_t*.csv"))
    assert len(files) == 2, files
    recorded = [row for path in files for row in read_csv(path)]
    assert len(recorded) == n and all(r["trackID"] == "1" for r in recorded), len(recorded)
    assert all(abs(float(r["z_mm"]) + 50) < 1e-6 for r in recorded), "entries must lie on the cube face"
    check_mean("recorded entry energy", (float(r["kineticEnergy_MeV"]) for r in recorded), 50.0, 2.0)

    file_list = ", ".join(path.as_posix() for path in files)
    stage_b, _ = case.run(f"[source]\nphase_space_file = {file_list}\n", n, size="10 cm")
    replay = {}
    for row in first_steps(stage_b):
        replay[int(row["eventID"])] = row
    assert len(replay) == n, len(replay)
    worst = 0.0
    for k, entry in enumerate(recorded):
        row = replay[k]
        for a, b in (("x_mm", "x0_mm"), ("y_mm", "y0_mm"), ("z_mm", "z0_mm"), ("u", "px"), ("v", "py"),
                     ("w", "pz"), ("kineticEnergy_MeV", "kineticEnergy_MeV")):
            worst = max(worst, abs(float(entry[a]) - float(row[b])) / max(1.0, abs(float(entry[a]))))
    print(f"  replay reproduces all {n} recorded entry states (max deviation {worst:.1e})")
    assert worst < 1e-9, worst
    a_edep, b_edep = list(edep_per_event(stage_a).values()), list(edep_per_event(stage_b).values())
    se = math.sqrt(std(a_edep) ** 2 / len(a_edep) + std(b_edep) ** 2 / len(b_edep))
    print(f"  mean edep per event: recorded run {mean(a_edep):.4f} MeV, replay {mean(b_edep):.4f} MeV (+-{se:.2g})")
    assert abs(mean(a_edep) - mean(b_edep)) < 5 * se
    summary = (stage_b / "run_summary.txt").read_text(encoding="utf-8")
    assert f"source_phase_space_histories = {n}" in summary, summary[-2000:]

    killed, _ = case.run(source + "kill = true\n", 100, size="10 cm")
    assert len([row for path in killed.glob("phase_space_t*.csv") for row in read_csv(path)]) == 100
    assert not any(row["particle"] == "proton" for _, row in hits(killed)), "killed protons must not deposit"
    print("  kill = true: recorded protons deposit nothing in the volume")

    header = "runID,eventID,trackID,parentID,particle,pdg,x_mm,y_mm,z_mm,u,v,w,kineticEnergy_MeV,time_ns,weight\n"
    rows = "".join(f"0,{e},1,0,proton,2212,0,0,0,0,0,1,{10 + e},0,0.5\n0,{e},2,0,proton,2212,5,0,0,1,0,0,7,0,0.5\n"
                   for e in range(3))
    output, _ = case.run("[source]\nphase_space_file = hand.csv\nphase_space_recycle = true\n", 6,
                         files={"hand.csv": header + rows})
    starts = first_steps(output, lambda r: r["parentID"] == "0")
    per_event = defaultdict(list)
    for row in starts:
        per_event[int(row["eventID"])].append(row)
    assert sorted(per_event) == list(range(6)) and all(len(v) == 2 for v in per_event.values()), sorted(per_event)
    for event, event_rows in per_event.items():
        energies = sorted(float(r["kineticEnergy_MeV"]) for r in event_rows)
        assert energies == [7.0, 10.0 + event % 3], (event, energies)
        assert all(abs(float(r["weight"]) - 0.5) < 1e-12 for r in event_rows)
    print("  two-particle histories with weight 0.5 replay as one event each (6 events recycled from 3)")

    _, log = case.run("[source]\nphase_space_file = hand.csv\n", 4, expect_ok=False, files={"hand.csv": header + rows})
    assert "has 3 histories but the run requests 4" in log, log[-2000:]
    _, log = case.run("[source]\nphase_space_file = hand.csv\nparticle = proton\n", 1, expect_ok=False,
                      files={"hand.csv": header + rows})
    assert "cannot be combined with phase_space_file" in log
    _, log = case.run("[source]\nphase_space_file = bad_ps.csv\n", 1, expect_ok=False,
                      files={"bad_ps.csv": header + "0,0,1,0,proton,2212,0,0,0,0,0,2,10,0,1\n"})
    assert "unit vector" in log
    _, log = case.run(f"[source]\n{PROTON}energy = 5 MeV\n{POINT}direction = +z\n[phase_space]\nvolume = Nope_PV\n",
                      1, expect_ok=False)
    assert "Nope_PV" in log
    print("  short file without recycle, mixed keys, bad rows and unknown volumes are rejected")


def failure_cases(case: Case) -> None:
    print("failures before events")
    bad = [
        ("[source]\nparticle = proton\nenergy = 5 MeV\nposition_type = volume\nshape = sphere\nradius = 1 cm\n"
         "isotropic = true\nconfine = NoSuchVolume_PV\n", "NoSuchVolume_PV"),
        ("[source]\nverbose = 0\nparticle = proton\n[source.a]\nparticle = proton\nenergy = 1 MeV\n"
         "position = 0,0,0 mm\ndirection = +z\n", "cannot be combined with [source.<name>]"),
        ("[source.a]\nparticle = proton\nenergy = 1 MeV\nposition = 0,0,0 mm\ndirection = +z\nenergie = 2\n",
         "unknown key [source.a]/energie"),
        ("[source.a]\nenergy = 1 MeV\nposition = 0,0,0 mm\ndirection = +z\n", "requires particle"),
        (f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = histogram\nspectrum_file = bad.csv\n",
         "contiguous"),
        (f"[source]\n{PROTON}{POINT}direction = +z\nenergy_type = uniform\nenergy = 5 MeV\n"
         "energy_min = 1 MeV\nenergy_max = 2 MeV\n", "is not used by energy_type = uniform"),
        (f"[source]\n{PROTON}energy = 5 MeV\n{POINT}angular = cos\n", "requires direction"),
        (f"[source]\n{PROTON}energy = 5 MeV\n{POINT}direction = +z\nangular = beam1d\n", "angular_sigma"),
        (f"[source]\n{PROTON}energy = 5 MeV\n{POINT}isotropic = true\nangular = isotropic\n", "conflicts with isotropic"),
        (f"[source]\n{PROTON}energy = 5 MeV\n{POINT}direction = +z\nenergy_sigma = 1 MeV\n", "requires energy_type"),
        (f"[source]\nparticle = ion\nenergy = 0 keV\n{POINT}isotropic = true\n", "must be given together"),
        (f"[source]\nparticle = ion\nion = 7 3\nenergy = 0 keV\n{POINT}isotropic = true\n", "1 <= Z <= A"),
    ]
    files = {"bad.csv": "e_low_MeV,e_high_MeV,weight\n1,2,1\n3,4,1\n"}
    for text, message in bad:
        output, log = case.run(text, 5, expect_ok=False, files=files)
        assert message in log, (message, log[-2500:])
        assert not list(output.glob("hits_t*.csv")) or all(
            path.stat().st_size < 400 for path in output.glob("hits_t*.csv")), "events ran despite the error"
    print(f"  {len(bad)} invalid source definitions rejected")


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_gps_"))
    try:
        case = Case(work)
        energy_cases(case)
        position_cases(case)
        angular_cases(case)
        multi_source_case(case)
        ion_cases(case)
        phase_space_cases(case)
        failure_cases(case)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_gps_sources: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
