"""The editor sketch must match the geometry Geant4 builds (roadmap G4).

For every geometry fixture the 3D view can sketch (hierarchical, simple_box and
layered_device files in config/, test/, scenarios/ and examples/, the same set as
test_gui_backend_agreement.py) plus three fixtures written here, the GUI builds its
sketch (parse_geometry -> GeometryDocument -> build_preview_scene) and the backend
exports the world it built (/run/initialize + /AIHL/geometry/exportMesh, as "Show
Backend Geometry"). The bounding box of each volume must agree:

  |sketch - backend| <= 1.5 % of the volume's largest extent + 1e-4 mm per face

(Geant4 draws a full circle with 24 segments, the sketch with 64: curved bounds differ
by up to r (1 - cos 7.5 deg) = 0.86 % of r.) Boolean targets are drawn before their
operations, so their sketch box must contain the backend box for subtraction and
intersection, and lie inside it for union. A volume the sketch does not draw must
have a reason, and only replica/parameterised copies (and what they contain) may be
missing; every other backend volume must be in the sketch.

The written fixtures are built to catch what matching symmetric shapes would hide:
offset daughters inside rotated mothers three levels deep (rotation order and sign),
unitless angles (radians, as in the backend), phi/theta segments of tubs, cons and
sphere, every A5 solid (ellipsoid, eltube, torus, para, hype, polycone, polyhedra, an
STL file next to the geometry), trap, trd, a replica, a rotated simple_box target and
layers placed with auto_stack = false.

    gui\\.venv\\Scripts\\python.exe scripts\\test_sketch_accuracy.py [-v]
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
sys.path.insert(0, str(ROOT / "scripts"))
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary   # noqa: E402
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel   # noqa: E402
from g4usim_gui.parsers.geometry_parser import parse_geometry   # noqa: E402
from g4usim_gui.preview3d.backend_mesh import export_arguments, load_backend_mesh, write_export_macro   # noqa: E402
from g4usim_gui.preview3d.geometry_primitives import volume_bounds   # noqa: E402
from g4usim_gui.preview3d.scene_builder import build_preview_scene   # noqa: E402
from test_gui_backend_agreement import collect_cases   # noqa: E402

SKETCHED = {"hierarchical", "simple_box", "layered_device"}
RELATIVE, ABSOLUTE = 0.015, 1e-4
MATERIALS = "test/materials/test_materials.ini"

ROTATED = """[world]
shape = box
size = 80 cm, 80 cm, 80 cm
material = G4_AIR

# three levels of offset daughters in rotated mothers: rotation order, sign, composition
[volume.Frame]
parent = world
shape = box
size = 20 cm, 10 cm, 6 cm
position = 15 cm, -8 cm, 5 cm
rotation = 10 deg, 25 deg, 30 deg
material = G4_AIR

[volume.Arm]
parent = Frame
shape = box
size = 6 cm, 2 cm, 2 cm
position = 5 cm, 2 cm, 1 cm
# unitless angles are radians in the backend
rotation = 20 deg, 0, 0.3
material = G4_Si

[volume.Pin]
parent = Arm
shape = tubs
parameters = 2 mm, 4 mm, 6 mm, 30 deg, 200 deg
position = 2 cm, 0 mm, 0 mm
rotation = 0 deg, 40 deg, -15 deg
material = G4_Si

[volume.Shell]
parent = world
shape = sphere
parameters = 1 cm, 3 cm, 20 deg, 120 deg, 30 deg, 60 deg
position = -20 cm, 15 cm, 0 cm
rotation = 10 deg, 20 deg, 30 deg
material = G4_WATER

[volume.Funnel]
parent = world
shape = cone
parameters = 0 mm, 2 cm, 1 cm, 3 cm, 2 cm, 0 deg, 270 deg
position = -20 cm, -15 cm, 10 cm
rotation = 0 deg, 90 deg, 15 deg
material = G4_WATER

[volume.Ball]
parent = world
shape = orb
parameters = 1.5 cm
position = 0 cm, 25 cm, -20 cm
material = G4_WATER

[volume.Wedge]
parent = world
shape = trd
dx1 = 1 cm
dx2 = 2 cm
dy1 = 1.5 cm
dy2 = 0.5 cm
dz = 2 cm
position = 25 cm, 20 cm, -15 cm
rotation = 35 deg, 0 deg, 50 deg
material = G4_Si

[volume.Skew]
parent = world
shape = trap
dz = 2 cm
theta = 10 deg
phi = 20 deg
dy1 = 1 cm
dx1 = 1 cm
dx2 = 1.5 cm
alpha1 = 5 deg
dy2 = 1.2 cm
dx3 = 1.2 cm
dx4 = 1.8 cm
alpha2 = 5 deg
position = -25 cm, 25 cm, 20 cm
rotation = 0 deg, 0 deg, 70 deg
material = G4_Si
"""

A5 = """[world]
shape = box
size = 80 cm, 80 cm, 80 cm
material = G4_AIR

[volume.Egg]
parent = world
shape = ellipsoid
parameters = 2 cm, 1 cm, 3 cm, -1 cm, 2 cm
position = 20 cm, 0 cm, 0 cm
rotation = 30 deg, 0 deg, 20 deg
material = G4_WATER

[volume.Oval]
parent = world
shape = eltube
parameters = 2 cm, 1 cm, 1.5 cm
position = -20 cm, 0 cm, 0 cm
rotation = 0 deg, 45 deg, 0 deg
material = G4_WATER

[volume.Ring]
parent = world
shape = torus
parameters = 0.5 cm, 1 cm, 3 cm, 0 deg, 180 deg
position = 0 cm, 20 cm, 0 cm
rotation = 0 deg, 0 deg, 60 deg
material = G4_WATER

[volume.Lean]
parent = world
shape = para
parameters = 1 cm, 2 cm, 1.5 cm, 20 deg, 15 deg, 30 deg
position = 0 cm, -20 cm, 0 cm
material = G4_Si

[volume.Waist]
parent = world
shape = hype
parameters = 1 cm, 2 cm, 20 deg, 30 deg, 2 cm
position = 0 cm, 0 cm, 20 cm
rotation = 90 deg, 0 deg, 0 deg
material = G4_Si

[volume.Bottle]
parent = world
shape = polycone
parameters = 0 deg, 300 deg
z_planes = -2 cm, 0 cm, 2 cm
r_inner = 0 cm, 0.5 cm, 0 cm
r_outer = 1 cm, 2 cm, 1.5 cm
position = 20 cm, 20 cm, 0 cm
material = G4_Si

[volume.Nut]
parent = world
shape = polyhedra
parameters = 10 deg, 360 deg, 6
z_planes = -1 cm, 1 cm
r_inner = 0.5 cm, 0.5 cm
r_outer = 2 cm, 2 cm
position = -20 cm, 20 cm, 0 cm
rotation = 0 deg, 30 deg, 0 deg
material = G4_Si

[volume.Mesh]
parent = world
shape = tessellated
file = tetra.stl
file_unit = cm
position = -20 cm, -20 cm, 0 cm
rotation = 0 deg, 0 deg, 25 deg
material = G4_Si

[volume.Stack]
parent = world
shape = box
size = 5 cm, 5 cm, 10 cm
position = 20 cm, -20 cm, 0 cm
material = G4_WATER

[volume.Slice]
parent = Stack
shape = box
size = 5 cm, 5 cm, 1 cm
placement = replica
replica_axis = z
replica_count = 10
replica_width = 1 cm
material = G4_WATER
"""

SIMPLE = """[world]
size = 40 cm, 40 cm, 40 cm
material = G4_AIR

[target]
name = Target
shape = box
size = 4 cm, 2 cm, 1 cm
material = G4_Si
position = 3 cm, -2 cm, 5 cm
rotation = 15 deg, 30 deg, 45 deg
"""

LAYERED = """[world]
size = 40 cm, 40 cm, 40 cm
material = G4_AIR

[layers]
count = 2
names = Base, Tilted
auto_stack = false

[layer.Base]
material = G4_Si
thickness = 2 mm
xy = 30 mm, 20 mm
position = 0 mm, 0 mm, -10 mm

[layer.Tilted]
material = G4_Si
thickness = 1 mm
xy = 40 mm, 10 mm
position = 20 mm, 10 mm, 30 mm
rotation = 0 deg, 30 deg, 20 deg
"""


@dataclass
class Fixture:
    name: str
    template: str
    geometry: Path
    materials: Path
    problems: list[str] = field(default_factory=list)
    compared: int = 0
    boolean: int = 0
    not_drawn: list[str] = field(default_factory=list)


def write_tetra(path: Path) -> None:
    corners = [(0, 0, 0), (2, 0, 0), (0, 3, 0), (0, 0, 1.5)]
    triangles = [(0, 2, 1), (0, 1, 3), (1, 2, 3), (0, 3, 2)]
    data = bytearray(b"tetra".ljust(80, b" ") + struct.pack("<I", len(triangles)))
    for triangle in triangles:
        data += struct.pack("<3f", 0, 0, 0)
        for index in triangle:
            data += struct.pack("<3f", *corners[index])
        data += b"\0\0"
    path.write_bytes(bytes(data))


def fixtures(work: Path) -> list[Fixture]:
    found = []
    for case in collect_cases(work / "agreement"):
        if case.template in SKETCHED and case.geometry and Path(case.geometry).suffix == ".ini" \
                and not Path(case.geometry).is_absolute():
            found.append(Fixture(case.name, case.template, ROOT / case.geometry, ROOT / case.materials))
    written = work / "written"
    written.mkdir(parents=True)
    write_tetra(written / "tetra.stl")
    for name, template, text in (("rotated", "hierarchical", ROTATED), ("a5_solids", "hierarchical", A5),
                                 ("simple_box", "simple_box", SIMPLE), ("layered", "layered_device", LAYERED)):
        path = written / f"{name}.ini"
        path.write_text(text, encoding="utf-8")
        found.append(Fixture(f"written:{name}", template, path, ROOT / MATERIALS))
    return found


def backend_mesh(fixture: Fixture, folder: Path):
    folder.mkdir(parents=True)
    main = folder / "main.ini"
    main.write_text(f"[materials]\nfile = {fixture.materials.as_posix()}\n\n[geometry]\n"
                    f"template = {fixture.template}\nconfig = {fixture.geometry.as_posix()}\n", encoding="utf-8")
    mesh = folder / "mesh.json"
    process = subprocess.run([str(EXE), *export_arguments(str(main), write_export_macro(folder, mesh),
                                                          folder / "output")],
                             cwd=str(ROOT), capture_output=True, text=True, errors="replace", timeout=600)
    if process.returncode != 0 or not mesh.is_file():
        return None
    return load_backend_mesh(mesh)


def box(points) -> tuple[list[float], list[float]]:
    return [min(p[k] for p in points) for k in range(3)], [max(p[k] for p in points) for k in range(3)]


def check(fixture: Fixture, work: Path, index: int) -> None:
    mesh = backend_mesh(fixture, work / f"case{index:03d}")
    if mesh is None:
        fixture.problems.append("SKIP: the backend rejects this geometry (judged by test_gui_backend_agreement)")
        return
    document = geometry_document_from_summary(parse_geometry(fixture.geometry, fixture.template), fixture.template)
    scene = build_preview_scene(document, SourceEditableModel())
    operations: dict[str, set[str]] = {}
    for op in document.boolean_ops:
        if op.enabled:
            operations.setdefault(op.target_volume.strip().lower(), set()).add(op.operation.strip().lower())
    backend: dict[str, list] = {}
    for volume in mesh.volumes:
        name = volume.name[:-3] if volume.name.endswith("_PV") else volume.name
        backend.setdefault(name.lower(), []).append(volume)
    sketched = set()
    for volume in scene.volumes:
        if volume.role == "boolean_tool":
            continue
        key = volume.name.strip().lower()
        sketched.add(key)
        copies = backend.get(key, [])
        if volume.not_drawn:
            fixture.not_drawn.append(f"{volume.name}: {volume.not_drawn}")
            if "placement=" not in volume.not_drawn and "parent" not in volume.not_drawn:
                fixture.problems.append(f"{volume.name} is not drawn: {volume.not_drawn}")
            continue
        if len(copies) != 1:
            fixture.problems.append(f"{volume.name}: the backend has {len(copies)} copies")
            continue
        bounds = volume_bounds(volume)
        low, high = [bounds[0], bounds[2], bounds[4]], [bounds[1], bounds[3], bounds[5]]
        glow, ghigh = box(copies[0].vertices)
        tolerance = RELATIVE * max(h - l for l, h in zip(low, high)) + ABSOLUTE
        ops = operations.get(key)
        if ops:
            fixture.boolean += 1
            if ops <= {"subtraction", "intersection"}:
                inside = all(l <= gl + tolerance and h >= gh - tolerance for l, h, gl, gh in zip(low, high, glow, ghigh))
                if not inside:
                    fixture.problems.append(f"{volume.name} ({'/'.join(sorted(ops))}): the backend box "
                                            f"{fmt(glow, ghigh)} is not inside the sketch box {fmt(low, high)}")
            elif ops == {"union"}:
                inside = all(gl <= l + tolerance and gh >= h - tolerance for l, h, gl, gh in zip(low, high, glow, ghigh))
                if not inside:
                    fixture.problems.append(f"{volume.name} (union): the sketch box {fmt(low, high)} is not inside "
                                            f"the backend box {fmt(glow, ghigh)}")
            continue
        error = max(abs(a - b) for a, b in zip(low + high, glow + ghigh))
        fixture.compared += 1
        if error > tolerance:
            fixture.problems.append(f"{volume.name} ({volume.shape}): sketch {fmt(low, high)} vs backend "
                                    f"{fmt(glow, ghigh)}, off by {error:.4g} mm (tolerance {tolerance:.3g})")
    replicated = {key for key, copies in backend.items() if len(copies) > 1}
    for key in backend:
        if key not in sketched and key not in replicated:
            fixture.problems.append(f"the backend volume {key} is missing from the sketch")


def fmt(low, high) -> str:
    return "[" + ", ".join(f"{a:.3f}..{b:.3f}" for a, b in zip(low, high)) + "]"


def main() -> int:
    if not EXE.is_file():
        print(f"SKIP: backend executable missing: {EXE}")
        return 0
    verbose = "-v" in sys.argv
    with tempfile.TemporaryDirectory(prefix="g4usim-sketch-") as temp:
        work = Path(temp)
        cases = fixtures(work)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item: check(item[1], work, item[0]), enumerate(cases)))
    failures = 0
    for case in cases:
        skipped = case.problems and case.problems[0].startswith("SKIP")
        bad = [p for p in case.problems if not p.startswith("SKIP")]
        failures += bool(bad)
        if verbose or bad:
            state = "SKIP" if skipped else "FAIL" if bad else "ok"
            print(f"{state} {case.name}: {case.compared} volumes match, {case.boolean} boolean targets, "
                  f"{len(case.not_drawn)} not drawn")
            for line in bad + (case.not_drawn if verbose else []):
                print("    " + line)
    compared = sum(c.compared for c in cases)
    written = [c for c in cases if c.name.startswith("written:")]
    print(f"{len(cases)} fixtures, {compared} volume boxes compared, "
          f"{sum(c.boolean for c in cases)} boolean targets checked, {failures} failing")
    # the written fixtures must really have been compared (a backend rejection would hide a regression)
    for case in written:
        if case.problems and case.problems[0].startswith("SKIP") or case.compared == 0:
            print(f"FAIL {case.name}: not compared")
            failures += 1
    rotated = next(c for c in written if c.name == "written:rotated")
    a5 = next(c for c in written if c.name == "written:a5_solids")
    if rotated.compared != 9 or a5.compared != 10 or not any("Slice" in n for n in a5.not_drawn):
        print(f"FAIL: expected 9 + 10 compared volumes and the replica listed as not drawn, got "
              f"{rotated.compared} + {a5.compared}, not drawn {a5.not_drawn}")
        failures += 1
    if failures:
        return 1
    print("test_sketch_accuracy: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
