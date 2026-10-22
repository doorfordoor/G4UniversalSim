"""Real Geant4 regression for roadmap A7 electromagnetic fields.

Protons start at the origin along +x in vacuum; a thin vacuum plane at x = 500 mm
records them with the phase-space recorder (position, direction, kinetic energy at
the boundary). Every check is an exact analytic property of the motion:
  1. uniform B = 2 T along z: circle of radius r = p / (0.299792458 B); crossing point
     y = -(r - sqrt(r^2 - x^2)), direction v = -x / r, kinetic energy unchanged;
  2. uniform E along the motion (1 MV/m): kinetic energy gain q E d = 0.5 MeV;
     transverse E: the energy gain equals the work q E y at the crossing point;
  3. crossed E and B (Wien filter, E = v B): the proton goes straight, while B alone
     deflects it by 89 mm;
  4. a constant magnetic field map reproduces the uniform field;
  5. a gradient map Bz = B0 + g x: the canonical momentum p_y + q A_y is conserved,
     so v = -0.299792458 (B0 x + g x^2 / 2) / p at the plane;
  6. a local field in a box ([field.<name>] volumes): arc inside, straight outside;
  7. invalid definitions fail before events.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
M_PROTON = 938.272088          # MeV
C_FACTOR = 0.299792458         # GeV/c per (T m)

MAIN = """
[run]
threads = 2
seed = 7
[output]
format = csv
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = hierarchical
config = {geometry}
[physics]
reference = FTFP_BERT
[scoring]
enabled = true
hits = false
event_edep = false
edep = false
[source]
particle = proton
energy = {energy} MeV
position_type = point
position = 0,0,0 mm
direction = +x
[phase_space]
volume = Plane_PV
particles = proton
kill = true
{fields}
"""

PRECISION = "delta_chord = 0.001 mm\ndelta_one_step = 0.0001 mm\ndelta_intersection = 0.0001 mm\n"
GEOMETRY = """
[world]
shape = box
size = 4 m, 4 m, 4 m
material = G4_Galactic
[volume.Plane]
parent = world
shape = box
size = 1 mm, 3 m, 3 m
material = G4_Galactic
position = 500.5 mm, 0 mm, 0 mm
"""
BOX = """
[volume.FieldBox]
parent = world
shape = box
size = 200 mm, 2 m, 2 m
material = G4_Galactic
position = 200 mm, 0 mm, 0 mm
"""


def momentum(kinetic: float) -> float:
    return math.sqrt(kinetic * (kinetic + 2 * M_PROTON))


class Runner:
    def __init__(self, work: Path):
        self.work = work
        self.count = 0

    def run(self, fields: str, energy: float, events: int = 4, geometry: str = GEOMETRY, files=None,
            expect_ok: bool = True):
        self.count += 1
        name = f"case{self.count:02d}"
        for filename, text in (files or {}).items():
            (self.work / filename).write_text(text, encoding="utf-8")
        geo = self.work / f"{name}_geometry.ini"
        geo.write_text(geometry, encoding="utf-8")
        ini = self.work / f"{name}.ini"
        ini.write_text(MAIN.format(root=ROOT.as_posix(), geometry=geo.as_posix(), energy=energy, fields=fields),
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
            assert result.returncode != 0, f"{name} unexpectedly succeeded:\n{fields}"
        return output, log

    def crossings(self, *args, **kwargs):
        output, _ = self.run(*args, **kwargs)
        rows = []
        for path in sorted(output.glob("phase_space_t*.csv")):
            if re.fullmatch(r"phase_space_t\d+\.csv", path.name):
                with path.open(newline="", encoding="utf-8") as handle:
                    rows.extend(r for r in csv.DictReader(handle) if r["trackID"] == "1")
        assert rows, "no proton reached the plane"
        return [{k: float(r[k]) for k in ("x_mm", "y_mm", "z_mm", "u", "v", "w", "kineticEnergy_MeV")} for r in rows]


def close(label, got, expected, tol):
    print(f"  {label}: {got:.6f} (expected {expected:.6f}, tolerance {tol:g})")
    assert abs(got - expected) <= tol, (label, got, expected)


def grid_map(path: Path, function, xs, ys, zs) -> None:
    lines = ["x_m,y_m,z_m,Bx_T,By_T,Bz_T"]
    for x in xs:
        for y in ys:
            for z in zs:
                bx, by, bz = function(x, y, z)
                lines.append(f"{x},{y},{z},{bx},{by},{bz}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_a7_"))
    try:
        r = Runner(work)
        x = 0.5   # m, plane position
        print("uniform magnetic field")
        T = 100.0
        p = momentum(T) / 1000.0
        radius = p / (C_FACTOR * 2.0)
        rows = r.crossings(f"[field]\nmagnetic = 0, 0, 2 T\n{PRECISION}", T)
        y_expected = -(radius - math.sqrt(radius**2 - x**2)) * 1000.0
        for row in rows:
            assert abs(row["x_mm"] - 500.0) < 1e-6
        close("crossing y [mm]", rows[0]["y_mm"], y_expected, 0.01)
        close("direction v", rows[0]["v"], -x / radius, 1e-5)
        close("kinetic energy [MeV]", rows[0]["kineticEnergy_MeV"], T, 1e-6)
        assert all(abs(row["y_mm"] - rows[0]["y_mm"]) < 1e-9 for row in rows)
        uniform_y = rows[0]["y_mm"]

        print("uniform electric fields")
        rows = r.crossings(f"[field]\nelectric = 1, 0, 0 MV/m\n{PRECISION}", 1.0)
        close("energy after 0.5 m along E [MeV]", rows[0]["kineticEnergy_MeV"], 1.5, 1e-6)
        close("transverse direction", abs(rows[0]["v"]) + abs(rows[0]["w"]), 0.0, 1e-9)
        rows = r.crossings(f"[field]\nelectric = 0, 1, 0 MV/m\n{PRECISION}", 10.0)
        work_done = rows[0]["y_mm"] / 1000.0 * 1.0     # q E y in MeV (E = 1 MV/m, y in m)
        close("energy gain = work q E y [MeV]", rows[0]["kineticEnergy_MeV"] - 10.0, work_done, 1e-6)
        assert rows[0]["y_mm"] > 1.0

        print("crossed fields (Wien filter)")
        T = 1.0
        beta = momentum(T) / (T + M_PROTON)
        e_field = beta * 299792458.0 * 0.1 / 1e6        # MV/m for B = 0.1 T
        rows = r.crossings(f"[field]\nmagnetic = 0, 0, 0.1 T\nelectric = 0, {e_field:.9f}, 0 MV/m\n{PRECISION}", T)
        close("Wien filter crossing y [mm]", rows[0]["y_mm"], 0.0, 0.05)
        rows_b = r.crossings(f"[field]\nmagnetic = 0, 0, 0.1 T\n{PRECISION}", T)
        radius_b = momentum(T) / 1000.0 / (C_FACTOR * 0.1)
        close("B alone crossing y [mm]", rows_b[0]["y_mm"], -(radius_b - math.sqrt(radius_b**2 - x**2)) * 1000.0, 0.05)

        print("field maps")
        xs = [-1.0, -0.5, 0.0, 0.5, 1.0]
        ys = [-1.0, 0.0, 1.0]
        zs = [-0.1, 0.1]
        grid_map(work / "constant.csv", lambda *_: (0, 0, 2.0), xs, ys, zs)
        rows = r.crossings(f"[field]\nmagnetic_map = constant.csv\n{PRECISION}", 100.0)
        close("constant map crossing y vs uniform [mm]", rows[0]["y_mm"], uniform_y, 1e-6)
        b0, g = 1.0, 2.0
        grid_map(work / "gradient.csv", lambda xx, yy, zz: (0, 0, b0 + g * xx), xs, ys, zs)
        rows = r.crossings(f"[field]\nmagnetic_map = gradient.csv\n{PRECISION}", 100.0)
        p = momentum(100.0) / 1000.0
        close("gradient map direction v (canonical momentum)", rows[0]["v"],
              -C_FACTOR * (b0 * x + g * x**2 / 2) / p, 1e-5)

        print("local field")
        rows = r.crossings(f"[field.Magnet]\nvolumes = FieldBox\nmagnetic = 0, 0, 2 T\n{PRECISION}", 100.0,
                           geometry=GEOMETRY + BOX)
        length = 0.2
        sin_exit = length / radius
        y_exit = -(radius - math.sqrt(radius**2 - length**2))
        y_plane = (y_exit - (x - 0.3) * sin_exit / math.sqrt(1 - sin_exit**2)) * 1000.0
        close("direction after the field box", rows[0]["v"], -sin_exit, 1e-5)
        close("crossing y [mm]", rows[0]["y_mm"], y_plane, 0.01)

        print("failures")
        bad = [
            ("[field]\nmagnetic = 0, 0, 1 T\nmagnetic_map = constant.csv\n", "not both"),
            ("[field]\nmagnetic = 0, 0, 1 Tesla\n", "unknown magnetic field unit"),
            ("[field]\nmagnetic = 0, 1 T\n", "expected 3 field components"),
            ("[field]\nmagnetic_map = holes.csv\n", "not a complete regular grid"),
            ("[field]\nmagnetic = 0, 0, 1 T\nvolumes = FieldBox\n", "only valid in [field.<name>]"),
            ("[field.Magnet]\nmagnetic = 0, 0, 1 T\n", "local fields need volumes"),
            ("[field.Magnet]\nvolumes = Nope\nmagnetic = 0, 0, 1 T\n", "not a volume of the geometry"),
            ("[field]\nmagnetic = 0, 0, 1 T\nstrength = 2\n", "unknown key [field]/strength"),
            ("[field]\ndelta_chord = 1 mm\n", "needs magnetic, electric"),
        ]
        # A 2 x 2 x 2 grid with one node missing.
        nodes = [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)][:-1]
        files = {"holes.csv": "x_m,y_m,z_m,Bx_T,By_T,Bz_T\n" +
                 "".join(f"{a},{b},{c},0,0,1\n" for a, b, c in nodes)}
        for fields, message in bad:
            _, log = r.run(fields, 10.0, events=1, files=files, expect_ok=False)
            assert message in log, (message, log[-2000:])
        print(f"  {len(bad)} invalid field definitions rejected")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_fields_a7: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
