"""Real Geant4 regression for roadmap A5 geometry: new solids, STL tessellated
solids, replica and parameterised placement, and the backend mesh export.

Checks:
  1. every new solid (ellipsoid, cut ellipsoid, eltube, torus, para, hype, polycone,
     polyhedra, binary-STL octahedron, inside-out ASCII-STL cube) has the analytic
     volume (Geant4 GetCubicVolume via the fluence CSV) and mass = density * volume
     (dose CSV);
  2. STL navigation: each isotropic geantino leaves an STL cube exactly on its surface
     along its own direction (phase-space exit points), and the chords add up to the
     scored fluence track length (1e-9); a G4Box cube passes the same check;
  3. replica: a z-replicated water stack gives the same per-slice dose as ten
     explicitly placed slabs (5 sigma, scorer_statistics); a beam inside phi slice 1
     scores only copy 1; exported phi slices lie in their own phi sectors;
  4. parameterised: copies_file positions, rotations and per-copy materials give the
     right per-copy masses and exported positions/extents; copies + copy_step places
     a linear row;
  5. /AIHL/geometry/exportMesh writes every copy with world-frame vertices that match
     the configured positions;
  6. GDML: a geometry with polycone, STL, boolean, replica, parameterised and rotated
     volumes exported with /AIHL/geometry/exportGDML and re-imported with
     template = gdml has identical copies, solids, materials, mesh and masses and the
     same per-slice dose (5 sigma); <auxiliary auxtype="SensDet"> marks sensitive
     volumes; missing files, unknown sensitive volumes and overwrites are rejected;
  7. invalid definitions (open/non-manifold STL, replica mismatches, mixed
     parameterised inputs, assembly, A5 shapes as boolean tools) fail before any
     Geant4 geometry object is created.
"""

from __future__ import annotations

import csv
import json
import math
import re
import os
import shutil
import struct
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
seed = {seed}
[output]
format = csv
[materials]
file = {root}/config/materials/material.ini
[geometry]
template = hierarchical
config = {geometry}
check_overlaps = true
[physics]
reference = FTFP_BERT
default_cut = 1 mm
[scoring]
enabled = true
hits = false
event_edep = false
edep = true
dose = true
fluence = true
auto_create_default_scorers = true
{source}
"""

WORLD = "[world]\nshape = box\nsize = 2 m, 2 m, 2 m\nmaterial = G4_Galactic\n"


def volume(name: str, body: str, parent: str = "world", material: str = "G4_WATER", sensitive: bool = True) -> str:
    return (f"\n[volume.{name}]\nparent = {parent}\nmaterial = {material}\n"
            f"sensitive = {'true' if sensitive else 'false'}\n{body}\n")


class Runner:
    def __init__(self, work: Path):
        self.work = work
        self.count = 0
        self.threads = 2

    def run(self, geometry: str, source: str, events: int, *, seed: int = 4242, macro_extra: str = "",
            expect_ok: bool = True):
        self.count += 1
        name = f"case{self.count:02d}"
        geo = self.work / f"{name}_geometry.ini"
        geo.write_text(geometry, encoding="utf-8")
        ini = self.work / f"{name}.ini"
        ini.write_text(MAIN.replace("threads = 2", f"threads = {self.threads}").format(seed=seed, root=ROOT.as_posix(), geometry=geo.as_posix(), source=source),
                       encoding="utf-8")
        mac = self.work / f"{name}.mac"
        mac.write_text(f"/run/initialize\n{macro_extra}/run/beamOn {events}\n", encoding="utf-8")
        output = self.work / name
        result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(mac), "--output", str(output)],
                                cwd=self.work, capture_output=True, text=True, errors="replace", timeout=1200)
        log = result.stdout + result.stderr
        if expect_ok:
            assert result.returncode == 0, f"{name} failed:\n{log[-3000:]}"
        else:
            assert result.returncode != 0, f"{name} unexpectedly succeeded"
        return output, log


def rows(output: Path, stem: str):
    out = []
    for path in sorted(output.glob(f"{stem}_t*.csv")):
        with path.open(newline="", encoding="utf-8") as handle:
            out.extend(csv.DictReader(handle))
    return out


def by_volume(output: Path, stem: str, value: str):
    merged: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows(output, stem):
        key = row["volume_path"]
        merged[key]["value"] += float(row[value])
        for column in ("volume_mm3", "mass_kg"):
            if column in row:
                merged[key][column] = float(row[column])
    return merged


def write_binary_stl(path: Path, triangles) -> None:
    data = bytearray(b"g4usim test octahedron".ljust(80, b" "))
    data += struct.pack("<I", len(triangles))
    for tri in triangles:
        data += struct.pack("<3f", 0.0, 0.0, 0.0)
        for vertex in tri:
            data += struct.pack("<3f", *vertex)
        data += b"\0\0"
    path.write_bytes(bytes(data))


def write_ascii_stl(path: Path, triangles) -> None:
    lines = ["solid cube"]
    for tri in triangles:
        lines += ["facet normal 0 0 0", " outer loop"] + [f"  vertex {x} {y} {z}" for x, y, z in tri]
        lines += [" endloop", "endfacet"]
    path.write_text("\n".join(lines + ["endsolid cube"]) + "\n", encoding="utf-8")


def octahedron(a: float):
    v = [(a, 0, 0), (-a, 0, 0), (0, a, 0), (0, -a, 0), (0, 0, a), (0, 0, -a)]
    faces = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return [tuple(v[i] for i in face) for face in faces]


def cube(half: float, inside_out: bool):
    h = half
    corners = [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h), (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (0, 4, 7, 3)]  # outward
    tris = []
    for a, b, c, d in quads:
        for tri in ((a, b, c), (a, c, d)):
            tri = (tri[0], tri[2], tri[1]) if inside_out else tri
            tris.append(tuple(corners[i] for i in tri))
    return tris


def solids_case(r: Runner) -> None:
    print("solids: analytic volumes and masses")
    write_binary_stl(r.work / "octa.stl", octahedron(15.0))
    write_ascii_stl(r.work / "cube.stl", cube(10.0, inside_out=True))
    t = math.tan
    shapes = {
        # name: (geometry body, analytic volume mm3, interior source point)
        "Ell": ("shape = ellipsoid\nparameters = 30 mm, 20 mm, 10 mm", 4 / 3 * math.pi * 30 * 20 * 10, (0, 0, 0)),
        "ElCut": ("shape = ellipsoid\nparameters = 30 mm, 20 mm, 10 mm, -5 mm, 8 mm",
                  math.pi * 30 * 20 * ((8 - 8**3 / 300) - (-5 + 125 / 300)), (0, 0, 0)),
        "ElTube": ("shape = eltube\nparameters = 20 mm, 10 mm, 15 mm", math.pi * 20 * 10 * 30, (0, 0, 0)),
        "Torus": ("shape = torus\nparameters = 5 mm, 10 mm, 30 mm, 0 deg, 360 deg",
                  math.pi * (100 - 25) * 2 * math.pi * 30, (30, 0, 0)),
        "Para": ("shape = para\nparameters = 10 mm, 20 mm, 30 mm, 20 deg, 10 deg, 30 deg", 8 * 10 * 20 * 30, (0, 0, 0)),
        "Hype": ("shape = hype\nparameters = 5 mm, 15 mm, 0.2 rad, 0.3 rad, 20 mm",
                 math.pi * (40 * (225 - 25) + (t(0.3) ** 2 - t(0.2) ** 2) * 2 * 20**3 / 3), (10, 0, 0)),
        "Pcone": ("shape = polycone\nparameters = 0 deg, 360 deg\nz_planes = -20 mm, 0 mm, 20 mm\n"
                  "r_inner = 0 mm, 5 mm, 0 mm\nr_outer = 10 mm, 20 mm, 10 mm",
                  2 * (math.pi * 20 / 3 * (100 + 200 + 400) - math.pi * 20 / 3 * 25), (12, 0, 0)),
        "Phedra": ("shape = polyhedra\nparameters = 0 deg, 360 deg, 6\nz_planes = -10 mm, 10 mm\n"
                   "r_inner = 0 mm, 0 mm\nr_outer = 10 mm, 10 mm", 2 * math.sqrt(3) * 100 * 20, (0, 0, 0)),
        "Octa": ("shape = tessellated\nfile = octa.stl\nfile_unit = mm", 4 / 3 * 15**3, (0, 0, 0)),
        "StlCube": ("shape = tessellated\nfile = cube.stl", 20**3, (0, 0, 0)),
    }
    geometry = WORLD
    sources = ""
    for index, (name, (body, _, point)) in enumerate(shapes.items()):
        x = -450 + 100 * index
        geometry += volume(name, f"{body}\nposition = {x} mm, 0 mm, 0 mm")
        px, py, pz = point
        sources += (f"[source.s{name}]\nparticle = proton\nenergy = 10 MeV\nposition_type = point\n"
                    f"position = {x + px},{py},{pz} mm\nangular = isotropic\n")
    output, _ = r.run(geometry, sources, 400)
    fluence = by_volume(output, "fluence_volume_summary", "raw_track_length_mm")
    dose = by_volume(output, "dose_volume_summary", "raw_edep_MeV")
    for name, (_, expected, _) in shapes.items():
        key = next(k for k in fluence if f"/{name}_PV#0" in k)
        got = fluence[key]["volume_mm3"]
        mass = dose[key]["mass_kg"]
        print(f"  {name:8s} volume {got:12.2f} mm3 (analytic {expected:12.2f}, {got / expected - 1:+.2e}); "
              f"mass {mass * 1000:.4f} g")
        assert abs(got / expected - 1) < 2e-3, (name, got, expected)
        assert abs(mass / (expected * 1e-6) - 1) < 2e-3, (name, mass)   # water: 1 g/cm3 = 1e-6 kg/mm3


def stl_navigation_case(r: Runner) -> None:
    print("STL navigation: every geantino leaves the cube on its surface along its direction")
    # The phase-space recorder on world_PV captures each geantino where it
    # leaves the cube (state at the boundary). For a straight track from s
    # along d the exit e must satisfy max|e_i| = 10 mm, (e - s) x d = 0 and
    # (e - s).d > 0, and sum |e - s| must equal the scored fluence track length.
    start = (3.0, 1.0, 2.0)
    source = ("[source]\nparticle = geantino\nenergy = 1 MeV\nposition_type = point\nposition = 3,1,2 mm\n"
              "angular = isotropic\n[phase_space]\nvolume = world_PV\nparticles = geantino\n")
    for label, body in (("STL", "shape = tessellated\nfile = cube.stl\nposition = 0 mm, 0 mm, 0 mm"),
                        ("G4Box", "shape = box\nsize = 20 mm, 20 mm, 20 mm\nposition = 0 mm, 0 mm, 0 mm")):
        n = 2000
        output, _ = r.run(WORLD + volume("Cube", body), source, n, seed=777)
        exits = rows(output, "phase_space")
        assert len(exits) == n, (label, len(exits))
        total = 0.0
        worst_surface = worst_direction = 0.0
        for e in exits:
            p = (float(e["x_mm"]), float(e["y_mm"]), float(e["z_mm"]))
            d = (float(e["u"]), float(e["v"]), float(e["w"]))
            v = tuple(p[k] - start[k] for k in range(3))
            length = math.sqrt(sum(c * c for c in v))
            cross = (v[1] * d[2] - v[2] * d[1], v[2] * d[0] - v[0] * d[2], v[0] * d[1] - v[1] * d[0])
            worst_surface = max(worst_surface, abs(max(abs(c) for c in p) - 10.0))
            worst_direction = max(worst_direction, math.sqrt(sum(c * c for c in cross)) / length)
            assert sum(v[k] * d[k] for k in range(3)) > 0
            total += length
        fluence = by_volume(output, "fluence_volume_summary", "raw_track_length_mm")
        scored = next(iter(fluence.values()))["value"]
        print(f"  {label:5s}: {n} exits, max |surface offset| {worst_surface:.1e} mm, max direction "
              f"deviation {worst_direction:.1e}, sum of chords {total:.6f} mm = scored {scored:.6f} mm")
        assert worst_surface < 1e-6 and worst_direction < 1e-9, (label, worst_surface, worst_direction)
        assert abs(total / scored - 1) < 1e-9, (label, total, scored)


def scorer_rows(output: Path, scorer: str, quantity: str):
    result = {}
    with (output / "scorer_statistics.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["scorer"] == scorer and row["quantity"] == quantity:
                result[row["key"]] = (float(row["value"]), float(row["std_error"]))
    return result


def replica_cases(r: Runner) -> None:
    print("replica placement")
    beam = ("[source]\nparticle = proton\nenergy = 100 MeV\nposition_type = point\nposition = 0,0,-200 mm\n"
            "direction = +z\n")
    replicated = WORLD + volume("Stack", "shape = box\nsize = 50 mm, 50 mm, 100 mm\nposition = 0 mm, 0 mm, 0 mm",
                                sensitive=False) + \
        volume("Slice", "shape = box\nsize = 50 mm, 50 mm, 10 mm\nplacement = replica\nreplica_axis = z\n"
                        "replica_count = 10\nreplica_width = 10 mm", parent="Stack")
    explicit = WORLD + "".join(
        volume(f"Slab{i}", f"shape = box\nsize = 50 mm, 50 mm, 10 mm\nposition = 0 mm, 0 mm, {-45 + 10 * i} mm")
        for i in range(10))
    n = 1500
    a, _ = r.run(replicated, beam, n, seed=11)
    b, _ = r.run(explicit, beam, n, seed=12)
    rep = scorer_rows(a, "dose", "raw_dose")
    ref = scorer_rows(b, "dose", "raw_dose")
    assert len(rep) == 10 and len(ref) == 10, (len(rep), len(ref))
    masses = {k: v["mass_kg"] for k, v in by_volume(a, "dose_volume_summary", "raw_edep_MeV").items()}
    for copy in range(10):
        key = next(k for k in rep if k.endswith(f"/Slice_PV#{copy}"))
        value, error = rep[key]
        ref_value, ref_error = ref[next(k for k in ref if f"/Slab{copy}_PV#0" in k)]
        pull = (value - ref_value) / math.hypot(error, ref_error) if value or ref_value else 0.0
        assert abs(masses[key] / 0.025 - 1) < 1e-6, masses[key]
        assert abs(pull) < 5, (copy, value, ref_value, pull)
    print(f"  10 slices: masses 25 g each; per-slice dose matches explicit slabs (|pull| < 5)")

    phi = WORLD + volume("Wheel", "shape = tubs\nparameters = 0 mm, 50 mm, 10 mm, 0 deg, 360 deg\n"
                                  "position = 0 mm, 0 mm, 0 mm", sensitive=False) + \
        volume("Sector", "shape = tubs\nparameters = 0 mm, 50 mm, 10 mm, -22.5 deg, 45 deg\nplacement = replica\n"
                         "replica_axis = phi\nreplica_count = 8\nreplica_width = 45 deg", parent="Wheel")
    angle = math.radians(67.5)
    source = (f"[source]\nparticle = geantino\nenergy = 1 MeV\nposition_type = point\n"
              f"position = {25 * math.cos(angle)},{25 * math.sin(angle)},-5 mm\ndirection = +z\n")
    mesh = r.work / "phi_mesh.json"
    output, _ = r.run(phi, source, 20, macro_extra=f"/AIHL/geometry/exportMesh {mesh.as_posix()}\n")
    fluence = by_volume(output, "fluence_volume_summary", "raw_track_length_mm")
    assert list(fluence) and all(k.endswith("/Sector_PV#1") for k in fluence), list(fluence)
    assert abs(next(iter(fluence.values()))["value"] - 20 * 15) < 1e-6
    data = json.loads(mesh.read_text(encoding="utf-8"))
    sectors = [v for v in data["volumes"] if v["name"] == "Sector_PV"]
    assert sorted(v["copy"] for v in sectors) == list(range(8))
    for v in sectors:
        lo, hi = 45 * v["copy"] - 1e-6, 45 * (v["copy"] + 1) + 1e-6
        for x, y, _ in v["vertices"]:
            if math.hypot(x, y) > 1e-6:
                p = math.degrees(math.atan2(y, x)) % 360
                if v["copy"] == 7 and p < 1e-6:
                    p = 360.0          # phi = 0 boundary belongs to the last sector here
                if v["copy"] == 0 and p > 360.0 - 1e-6:
                    p = 0.0            # -0 rounding of the first sector's lower edge
                assert lo <= p <= hi, (v["copy"], p)
    print("  phi replica: a beam in sector 1 scores only copy 1; exported sectors lie in their phi ranges")


def parameterised_cases(r: Runner) -> None:
    print("parameterised placement")
    table = ("# copies\nx_mm,y_mm,z_mm,rot_x_deg,rot_y_deg,rot_z_deg,material\n"
             "-100,0,0,0,0,0,G4_WATER\n0,0,0,0,0,45,G4_Si\n100,0,0,0,0,0,G4_Pb\n")
    (r.work / "copies.csv").write_text(table, encoding="utf-8")
    # Geant4: a parameterised volume must be the only daughter of its mother.
    geometry = WORLD + \
        volume("CellBox", "shape = box\nsize = 400 mm, 100 mm, 100 mm\nposition = 0 mm, 0 mm, 0 mm",
               material="G4_Galactic", sensitive=False) + \
        volume("Cell", "shape = box\nsize = 10 mm, 10 mm, 10 mm\nplacement = parameterised\n"
                       "copies_file = copies.csv", parent="CellBox") + \
        volume("RowBox", "shape = box\nsize = 20 mm, 20 mm, 200 mm\nposition = 0 mm, 300 mm, 0 mm",
               material="G4_Galactic", sensitive=False) + \
        volume("Row", "shape = box\nsize = 4 mm, 4 mm, 4 mm\nposition = 0 mm, 0 mm, 0 mm\n"
                      "placement = parameterised\ncopies = 4\ncopy_step = 0 mm, 0 mm, 20 mm", parent="RowBox",
               sensitive=False)
    sources = "".join(f"[source.c{i}]\nparticle = proton\nenergy = 20 MeV\nposition_type = point\n"
                      f"position = {x},0,0 mm\nisotropic = true\n" for i, x in enumerate((-100, 0, 100)))
    mesh = r.work / "param_mesh.json"
    output, _ = r.run(geometry, sources, 300, macro_extra=f"/AIHL/geometry/exportMesh {mesh.as_posix()}\n")
    dose = by_volume(output, "dose_volume_summary", "raw_edep_MeV")
    densities = {0: 1.0, 1: 2.33, 2: 11.35}   # g/cm3: water, Si, Pb (NIST)
    for copy, density in densities.items():
        key = next(k for k in dose if k.endswith(f"/Cell_PV#{copy}"))
        mass = dose[key]["mass_kg"]
        assert abs(mass / (density * 1e-3) - 1) < 2e-3, (copy, mass)
    print("  per-copy materials: masses 1.00 / 2.33 / 11.35 g (water, Si, Pb)")
    data = json.loads(mesh.read_text(encoding="utf-8"))
    cells = {v["copy"]: v for v in data["volumes"] if v["name"] == "Cell_PV"}
    assert [cells[i]["material"] for i in range(3)] == ["G4_WATER", "G4_Si", "G4_Pb"]
    for copy, x0 in ((0, -100), (1, 0), (2, 100)):
        xs = [v[0] for v in cells[copy]["vertices"]]
        assert abs((max(xs) + min(xs)) / 2 - x0) < 1e-6
        half = (max(xs) - min(xs)) / 2
        expected = 5 * math.sqrt(2) if copy == 1 else 5.0
        assert abs(half - expected) < 1e-6, (copy, half)
    row = sorted((v for v in data["volumes"] if v["name"] == "Row_PV"), key=lambda v: v["copy"])
    centres = [round((max(p[2] for p in v["vertices"]) + min(p[2] for p in v["vertices"])) / 2, 6) for v in row]
    assert centres == [0.0, 20.0, 40.0, 60.0], centres
    assert all(abs(sum(p[1] for p in v["vertices"]) / len(v["vertices"]) - 300) < 1e-6 for v in row)
    print("  exported copies: positions, 45 deg rotation and linear row (z = 0, 20, 40, 60 mm) as configured")


def export_case(r: Runner) -> None:
    print("mesh export of a nested, rotated geometry")
    geometry = WORLD + volume("Outer", "shape = box\nsize = 100 mm, 100 mm, 100 mm\nposition = 10 mm, 20 mm, 30 mm\n"
                                       "rotation = 0 deg, 0 deg, 90 deg", sensitive=False) + \
        volume("Inner", "shape = orb\nparameters = 5 mm\nposition = 20 mm, 0 mm, 0 mm", parent="Outer")
    mesh = r.work / "nested.json"
    r.run(geometry, "[source]\nparticle = geantino\nenergy = 1 MeV\nposition = 0,0,-500 mm\ndirection = +z\n", 1,
          macro_extra=f"/AIHL/geometry/exportMesh {mesh.as_posix()}\n")
    data = json.loads(mesh.read_text(encoding="utf-8"))
    assert data["schema"] == "g4usim_geometry_mesh_v1" and data["volume_count"] == 3
    inner = next(v for v in data["volumes"] if v["name"] == "Inner_PV")
    centre = [sum(p[k] for p in inner["vertices"]) / len(inner["vertices"]) for k in range(3)]
    # Geant4 rotation = rotation of the frame: a +90 deg frame rotation about z maps the
    # daughter offset (20,0,0) to (0,-20,0) in the mother, then the mother offset applies.
    expected = (10.0, 0.0, 30.0)
    assert all(abs(c - e) < 0.05 for c, e in zip(centre, expected)), (centre, expected)
    assert inner["sensitive"] is True and inner["material"] == "G4_WATER"
    print(f"  daughter centre in world frame {tuple(round(c, 3) for c in centre)} = expected {expected}")


GDML_SENSDET = """<?xml version="1.0" encoding="UTF-8"?>
<gdml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:noNamespaceSchemaLocation="http://service-spi.web.cern.ch/service-spi/app/releases/GDML/schema/gdml.xsd">
  <materials>
    <material name="Water" Z="1">
      <D value="1.0" unit="g/cm3"/>
      <atom value="1.008"/>
    </material>
    <material name="Vacuum" Z="1">
      <D value="1e-25" unit="g/cm3"/>
      <atom value="1.008"/>
    </material>
  </materials>
  <solids>
    <box name="WorldBox" x="1000" y="1000" z="1000" lunit="mm"/>
    <box name="DetBox" x="20" y="20" z="20" lunit="mm"/>
  </solids>
  <structure>
    <volume name="Det_LV">
      <materialref ref="Water"/>
      <solidref ref="DetBox"/>
      <auxiliary auxtype="SensDet" auxvalue="Detector"/>
    </volume>
    <volume name="World_LV">
      <materialref ref="Vacuum"/>
      <solidref ref="WorldBox"/>
      <physvol name="Det_PV">
        <volumeref ref="Det_LV"/>
        <position name="DetPos" x="0" y="0" z="100" unit="mm"/>
      </physvol>
    </volume>
  </structure>
  <setup name="Default" version="1.0">
    <world ref="World_LV"/>
  </setup>
</gdml>
"""


def run_gdml(r: Runner, gdml_ini_text: str, source: str, events: int, *, seed: int = 4242, macro_extra: str = "",
             expect_ok: bool = True):
    """Like Runner.run, with [geometry] template = gdml and the given [gdml] INI."""
    r.count += 1
    name = f"case{r.count:02d}"
    geo = r.work / f"{name}_gdml.ini"
    geo.write_text(gdml_ini_text, encoding="utf-8")
    ini = r.work / f"{name}.ini"
    ini.write_text(MAIN.replace("threads = 2", f"threads = {r.threads}").replace("template = hierarchical", "template = gdml").format(
        seed=seed, root=ROOT.as_posix(), geometry=geo.as_posix(), source=source), encoding="utf-8")
    mac = r.work / f"{name}.mac"
    mac.write_text(f"/run/initialize\n{macro_extra}/run/beamOn {events}\n", encoding="utf-8")
    output = r.work / name
    result = subprocess.run([str(EXE), "--config", str(ini), "--macro", str(mac), "--output", str(output)],
                            cwd=r.work, capture_output=True, text=True, errors="replace", timeout=1200)
    log = result.stdout + result.stderr
    if expect_ok:
        assert result.returncode == 0, f"{name} failed:\n{log[-3000:]}"
    else:
        assert result.returncode != 0, f"{name} unexpectedly succeeded"
    return output, log


def gdml_path(path: str) -> str:
    """Map re-imported GDML touchable names onto the exported ones.

    GDML does not store the physical-volume name of the world, of replicas or of
    parameterised volumes; G4GDMLParser names them <LV>_PV (world, replica) and
    <LV>_param (parameterised)."""
    return re.sub(r"/(\w+)_LV_(?:PV|param)#", r"/\1_PV#", path)


def gdml_cases(r: Runner) -> None:
    print("GDML export and re-import")
    write_ascii_stl(r.work / "cube.stl", cube(10.0, inside_out=False))
    geometry = WORLD + \
        volume("Lens", "shape = polycone\nparameters = 0 deg, 360 deg\nz_planes = -20 mm, 0 mm, 20 mm\n"
                       "r_inner = 0 mm, 5 mm, 0 mm\nr_outer = 10 mm, 20 mm, 10 mm\nposition = -200 mm, 0 mm, 0 mm") + \
        volume("Mesh", "shape = tessellated\nfile = cube.stl\nposition = 200 mm, 0 mm, 0 mm\n"
                       "rotation = 0 deg, 0 deg, 30 deg", material="G4_Si") + \
        volume("Holed", "shape = box\nsize = 40 mm, 40 mm, 40 mm\nposition = 0 mm, 200 mm, 0 mm") + \
        "\n[volume.Holed.boolean.0]\noperation = subtraction\nshape = tubs\n" \
        "parameters = 0 mm, 8 mm, 30 mm, 0 deg, 360 deg\n" + \
        volume("Stack", "shape = box\nsize = 50 mm, 50 mm, 100 mm\nposition = 0 mm, 0 mm, 0 mm", sensitive=False) + \
        volume("Slice", "shape = box\nsize = 50 mm, 50 mm, 10 mm\nplacement = replica\nreplica_axis = z\n"
                        "replica_count = 10\nreplica_width = 10 mm", parent="Stack") + \
        volume("RowBox", "shape = box\nsize = 20 mm, 20 mm, 200 mm\nposition = 0 mm, -200 mm, 0 mm",
               material="G4_Galactic", sensitive=False) + \
        volume("Cell", "shape = box\nsize = 4 mm, 4 mm, 4 mm\nposition = 0 mm, 0 mm, -60 mm\n"
                       "placement = parameterised\ncopies = 4\ncopy_step = 0 mm, 0 mm, 40 mm", parent="RowBox")
    beam = ("[source]\nparticle = proton\nenergy = 100 MeV\nposition_type = point\nposition = 0,0,-300 mm\n"
            "direction = +z\n")
    gdml = r.work / "model.gdml"
    mesh_a = r.work / "mesh_a.json"
    a, _ = r.run(geometry, beam, 1500, seed=21,
                 macro_extra=f"/AIHL/geometry/exportGDML {gdml.as_posix()}\n/AIHL/geometry/exportMesh {mesh_a.as_posix()}\n")
    assert gdml.is_file() and gdml.stat().st_size > 1000
    sensitive = "Lens_LV, Mesh_LV, Holed_LV, Slice_LV, Cell_LV"
    mesh_b = r.work / "mesh_b.json"
    b, _ = run_gdml(r, f"[gdml]\nfile = {gdml.name}\nsensitive_volumes = {sensitive}\n", beam, 1500, seed=22,
                    macro_extra=f"/AIHL/geometry/exportMesh {mesh_b.as_posix()}\n")
    va = {v["path"]: v for v in json.loads(mesh_a.read_text(encoding="utf-8"))["volumes"]}
    vb = {gdml_path(v["path"]): v for v in json.loads(mesh_b.read_text(encoding="utf-8"))["volumes"]}
    assert set(va) == set(vb), (sorted(set(va) ^ set(vb)))[:10]
    worst = 0.0
    for path, x in va.items():
        y = vb[path]
        assert x["solid"] == y["solid"] and x["material"] == y["material"], (path, x["solid"], y["solid"], x["material"], y["material"])
        assert len(x["vertices"]) == len(y["vertices"]), path
        for p, q in zip(x["vertices"], y["vertices"]):
            worst = max(worst, max(abs(p[k] - q[k]) for k in range(3)))
        if x["solid"] != "G4SubtractionSolid":   # boolean volumes are Monte Carlo estimates
            assert abs(x["cubic_volume_mm3"] / y["cubic_volume_mm3"] - 1) < 1e-9, path
    print(f"  {len(va)} volume copies re-imported with identical solids, materials and mesh "
          f"(max vertex difference {worst:.1e} mm)")
    assert worst < 1e-6, worst

    mass_a = {k: v["mass_kg"] for k, v in by_volume(a, "dose_volume_summary", "raw_edep_MeV").items()}
    mass_b = {gdml_path(k): v["mass_kg"] for k, v in by_volume(b, "dose_volume_summary", "raw_edep_MeV").items()}
    # Off-axis volumes may score in only one run (stray secondaries); compare the common ones.
    common = mass_a.keys() & mass_b.keys()
    assert sum("/Slice_PV#" in k for k in common) == 10, sorted(common)
    for key in common:
        if "/Holed_PV#" not in key:
            assert abs(mass_a[key] / mass_b[key] - 1) < 1e-6, (key, mass_a[key], mass_b[key])
    da = scorer_rows(a, "dose", "raw_dose")
    db = {gdml_path(k): v for k, v in scorer_rows(b, "dose", "raw_dose").items()}
    slices = [k for k in da if "/Slice_PV#" in k]
    assert len(slices) == 10 and all(k in db for k in slices), (len(slices), sorted(db)[:5])
    for key in slices:
        (x, ex), (y, ey) = da[key], db[key]
        assert abs(x - y) < 5 * math.hypot(ex, ey) + 1e-30, (key, x, y)
    print("  masses identical; per-slice dose of original and re-imported geometry agree (5 sigma)")

    (r.work / "sensdet.gdml").write_text(GDML_SENSDET, encoding="utf-8")
    source = ("[source]\nparticle = proton\nenergy = 20 MeV\nposition_type = point\nposition = 0,0,0 mm\n"
              "direction = +z\n")
    output, _ = run_gdml(r, "[gdml]\nfile = sensdet.gdml\n", source, 50)
    dose = by_volume(output, "dose_volume_summary", "raw_edep_MeV")
    assert list(dose) and all("/Det_PV#0" in k for k in dose), list(dose)
    assert abs(next(iter(dose.values()))["mass_kg"] / 8e-3 - 1) < 1e-9
    print("  hand-written GDML: <auxiliary auxtype=\"SensDet\"> makes Det_LV sensitive (8 g of water)")

    _, log = run_gdml(r, "[gdml]\nfile = missing.gdml\n", source, 1, expect_ok=False)
    assert "GDML file does not exist" in log
    _, log = run_gdml(r, "[gdml]\nfile = sensdet.gdml\nsensitive_volumes = Nope_LV\n", source, 1, expect_ok=False)
    assert "Nope_LV" in log and "available logical volumes" in log, log[-1500:]
    _, log = r.run(WORLD + volume("B", "shape = box\nsize = 1 mm, 1 mm, 1 mm"), source, 1, expect_ok=False,
                   macro_extra=f"/AIHL/geometry/exportGDML {gdml.as_posix()}\n")
    assert "refuses to overwrite" in log, log[-1500:]
    print("  missing file, unknown sensitive volume and overwriting an existing GDML file are rejected")


def gdml_case_sensitive_sd(r: Runner) -> None:
    """Case-distinct LV objects, duplicate selections, both SD entry points and runs."""
    import xml.etree.ElementTree as ET
    for auxiliary in (True, False):
        tree = ET.fromstring(GDML_SENSDET)
        structure = tree.find("structure")
        original = structure.find("volume[@name='Det_LV']")
        original.set("name", "Sensor")
        second = ET.fromstring(ET.tostring(original))
        second.set("name", "sensor")
        structure.insert(1, second)
        world = structure.find("volume[@name='World_LV']")
        first_pv = world.find("physvol")
        first_pv.set("name", "Upper_PV")
        first_pv.find("volumeref").set("ref", "Sensor")
        first_pv.find("position").set("x", "-30")
        second_pv = ET.fromstring(ET.tostring(first_pv))
        second_pv.set("name", "Lower_PV")
        second_pv.find("volumeref").set("ref", "sensor")
        second_pv.find("position").set("name", "SecondPos")
        second_pv.find("position").set("x", "30")
        world.append(second_pv)
        if not auxiliary:
            for logical in (original, second):
                logical.remove(logical.find("auxiliary"))
        filename = f"case_distinct_{auxiliary}.gdml"
        (r.work / filename).write_text(ET.tostring(tree, encoding="unicode"), encoding="utf-8")
        for threads in (1, 2):
            r.threads = threads
            for x, expected in ((-30, "Upper_PV"), (30, "Lower_PV")):
                source = (f"[source]\nparticle = proton\nenergy = 20 MeV\nposition_type = point\n"
                          f"position = {x},0,90 mm\ndirection = +z\n")
                selections = "" if auxiliary else "sensitive_volumes = Sensor, sensor, Sensor\n"
                output, _ = run_gdml(r, f"[gdml]\nfile = {filename}\n"
                                    + selections, source, 20,
                                    macro_extra="/run/beamOn 20\n")
                dose = rows(output, "dose_volume_summary")
                assert dose and {int(row["runID"]) for row in dose} == {0, 1}, dose
                assert all(row["volume_path"].endswith(f"/{expected}#0") for row in dose), dose
                for row in dose:
                    assert abs(float(row["mass_kg"]) / .008 - 1) < 1e-9, row
                # No duplicated SD counting: each run deposits at most its injected energy.
                for run in (0, 1):
                    energy = sum(float(row["raw_edep_MeV"]) for row in dose if int(row["runID"]) == run)
                    assert 0 < energy <= 400.0001, energy
    r.threads = 2


def failure_cases(r: Runner) -> None:
    print("failures before Geant4 geometry objects")
    (r.work / "open.stl").write_text("solid o\n" + "".join(
        f"facet normal 0 0 1\n outer loop\n  vertex {a}\n  vertex {b}\n  vertex {c}\n endloop\nendfacet\n"
        for a, b, c in (("0 0 0", "1 0 0", "0 1 0"), ("0 0 0", "0 1 0", "0 0 1"), ("0 0 0", "0 0 1", "1 0 0"),
                        ("1 0 0", "0 0 1", "0.5 0.5 2"))) + "endsolid o\n", encoding="utf-8")
    (r.work / "bad_copies.csv").write_text("x_mm,y_mm\n0,0\n", encoding="utf-8")
    stack = volume("Stack", "shape = box\nsize = 50 mm, 50 mm, 100 mm\nposition = 0 mm, 0 mm, 0 mm", sensitive=False)
    slice_ = "shape = box\nsize = 50 mm, 50 mm, 10 mm\nplacement = replica\nreplica_axis = z\nreplica_width = 10 mm\n"
    cases = [
        (volume("O", "shape = tessellated\nfile = open.stl"), "is not closed"),
        (volume("P", "shape = polycone\nparameters = 0 deg, 360 deg\nz_planes = 0 mm, 1 mm\nr_inner = 0 mm\n"
                     "r_outer = 1 mm, 1 mm"), "same number"),
        (volume("T", "shape = torus\nparameters = 5 mm, 10 mm, 8 mm, 0 deg, 360 deg"), "rMax <= rTor"),
        (stack + volume("S", slice_ + "replica_count = 9", parent="Stack"), "replica_count * replica_width"),
        (stack + volume("S", slice_.replace("50 mm, 50 mm, 10 mm", "40 mm, 50 mm, 10 mm") + "replica_count = 10",
                        parent="Stack"), "mother's size"),
        (stack + volume("S", slice_ + "replica_count = 10", parent="Stack") +
         volume("X", "shape = box\nsize = 1 mm, 1 mm, 1 mm", parent="Stack"), "only the replica"),
        (volume("W", "shape = tubs\nparameters = 0 mm, 5 mm, 5 mm, 0 deg, 360 deg", sensitive=False) +
         volume("Q", "shape = tubs\nparameters = 0 mm, 5 mm, 5 mm, 0 deg, 90 deg\nplacement = replica\n"
                     "replica_axis = phi\nreplica_count = 4\nreplica_width = 90 deg", parent="W"), "-replica_width/2"),
        (volume("C", "shape = box\nsize = 1 mm, 1 mm, 1 mm\nplacement = parameterised\ncopies = 2\n"
                     "copy_step = 1 mm, 0 mm, 0 mm\ncopies_file = copies.csv"), "either copies_file"),
        (volume("C", "shape = box\nsize = 1 mm, 1 mm, 1 mm\nplacement = parameterised\ncopies_file = bad_copies.csv"),
         "header must be"),
        (volume("C", "shape = box\nsize = 1 mm, 1 mm, 1 mm\nreplica_count = 3"), "only valid with placement=replica"),
        (volume("A", "shape = box\nsize = 1 mm, 1 mm, 1 mm\nplacement = assembly"), "placement=assembly"),
        (volume("C", "shape = box\nsize = 1 mm, 1 mm, 1 mm\nplacement = parameterised\ncopies = 2\n"
                     "copy_step = 2 mm, 0 mm, 0 mm") +
         volume("D", "shape = box\nsize = 1 mm, 1 mm, 1 mm\nposition = 0 mm, 50 mm, 0 mm"),
         "only the parameterised volume"),
        (volume("B", "shape = box\nsize = 10 mm, 10 mm, 10 mm") +
         "\n[volume.B.boolean.0]\noperation = subtraction\nshape = torus\nparameters = 0 mm, 1 mm, 2 mm, 0 deg, 360 deg\n",
         "not supported as a boolean tool"),
    ]
    for body, message in cases:
        _, log = r.run(WORLD + body, "[source]\nparticle = geantino\nenergy = 1 MeV\nposition = 0,0,0 mm\n"
                                     "direction = +z\n", 1, expect_ok=False)
        assert message in log, (message, log[-2500:])
        assert "created_geometry_object_count=0" in log or "Geometry config error" in log or \
            "Geometry volume" in log, (message, log[-1500:])
    print(f"  {len(cases)} invalid geometries rejected")


def main() -> int:
    assert EXE.is_file(), f"backend executable missing: {EXE}"
    work = Path(tempfile.mkdtemp(prefix="g4usim_a5_"))
    try:
        r = Runner(work)
        solids_case(r)
        stl_navigation_case(r)
        replica_cases(r)
        parameterised_cases(r)
        export_case(r)
        gdml_cases(r)
        gdml_case_sensitive_sd(r)
        failure_cases(r)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("test_geometry_a5: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
