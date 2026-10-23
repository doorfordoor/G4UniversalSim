"""Source glyphs in the 3D view match what Geant4's GPS samples (roadmap G5).

Without Geant4: the glyphs of each source setting (point, plane circle, annulus,
rectangle, square; fixed, isotropic, cone, cosine, focused), the XY plane whatever
the editor's normal (with a warning), preview-only settings marked as not generated,
and the translated description.

With the backend: four sources the GUI can generate are written by the GUI's own
main.ini writer and run with 200 geantinos and trajectories on (roadmap H1). Every
primary must start where its glyph is drawn (on the point; inside the disc or the
rectangle, in the XY plane at the center's z) and leave along the arrow (fixed) or in
all directions (isotropic); the sampled starts must also fill the drawn shape.

With a display (VTK needs a real window on Windows): the glyphs are drawn over the
sketch and over a Geant4 mesh, the status line describes the source, and "Show
Source" removes and restores them.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))
if sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    os.environ["QT_QPA_PLATFORM"] = "windows"      # VTK needs a real OpenGL context
ROOT = GUI.parent
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

from g4usim_gui.editors.source_physics_scoring_model import (   # noqa: E402
    ScoringEditableModel, SourceEditableModel)
from g4usim_gui.preview3d.source_builder import build_preview_source   # noqa: E402

GEOMETRY = """[world]
shape = box
size = 1 m, 1 m, 1 m
material = G4_Galactic

[volume.Marker]
parent = world
shape = box
size = 1 mm, 1 mm, 1 mm
position = 0 mm, 0 mm, 300 mm
material = G4_WATER
"""


def glyphs(**fields):
    warnings: list[str] = []
    source = build_preview_source(SourceEditableModel(**fields), warnings, [])
    return source, [g.kind for g in source.glyphs], warnings


def check_model() -> None:
    source, kinds, _ = glyphs(position="1, 2, 3 mm", direction="0,0,1")
    assert kinds == ["point", "arrow"] and source.generated and source.glyphs[0].center == (1.0, 2.0, 3.0)
    source, kinds, _ = glyphs(position_mode="plane", source_shape="circle", radius="5 mm", angular_mode="isotropic")
    assert kinds == ["disc", "isotropic"] and source.glyphs[0].radius_mm == 5.0 and source.generated
    source, kinds, _ = glyphs(position_mode="plane", source_shape="rectangle", halfx="6 mm", halfy="2 mm")
    assert kinds == ["rectangle"] + ["arrow"] * 5 and (source.glyphs[0].halfx_mm, source.glyphs[0].halfy_mm) == (6, 2)
    assert sum(g.secondary for g in source.glyphs) == 4, "a parallel beam shows arrows from the plane's corners"
    source, kinds, _ = glyphs(position_mode="plane", source_shape="annulus", radius="5 mm", inner_radius="2 mm")
    assert kinds[0] == "disc" and source.glyphs[0].inner_radius_mm == 2.0 and not source.generated
    source, kinds, _ = glyphs(position_mode="plane", source_shape="square", halfx="3 mm")
    assert (source.glyphs[0].halfx_mm, source.glyphs[0].halfy_mm) == (3, 3) and not source.generated
    source, kinds, _ = glyphs(angular_mode="cone", cone_half_angle="10 deg")
    assert kinds == ["point", "cone"] and source.glyphs[1].half_angle_deg == 10.0 and not source.generated
    source, kinds, _ = glyphs(angular_mode="cosine")
    assert kinds == ["point", "isotropic"] and source.glyphs[1].direction is not None   # a hemisphere
    source, kinds, _ = glyphs(position="0,0,0 mm", angular_mode="focused", focus_point="0,0,40 mm")
    assert kinds == ["point", "arrow"] and source.glyphs[1].length_mm == 40.0
    # GPS puts the plane in the XY plane: the editor's normal is not used
    source, kinds, warnings = glyphs(position_mode="plane", source_shape="circle", radius="5 mm", normal="1,0,0")
    assert source.generated and any("XY plane" in w for w in warnings)
    from g4usim_gui.preview3d.pyvista_preview_widget import describe_source   # noqa: PLC0415
    source, _, _ = glyphs(particle="proton", energy="150 MeV", position="0, 0, -10 mm", direction="0,0,1")
    text = describe_source(source, "en")
    assert text == "proton 150 MeV, point at (0, 0, -10) mm, fixed direction (0, 0, 1)", text
    assert "固定方向" in describe_source(source, "zh_CN"), describe_source(source, "zh_CN")
    print("model: glyphs per position shape and angular mode, XY plane, preview-only marked, description")


def run_case(temp: Path, name: str, model: SourceEditableModel, events: int = 200):
    from g4usim_gui.models.package_model import GeometrySettings, RunPackage   # noqa: PLC0415
    from g4usim_gui.models.physics_model import PhysicsSettings   # noqa: PLC0415
    from g4usim_gui.models.run_model import RunSettings   # noqa: PLC0415
    from g4usim_gui.models.source_model import SourceSettings   # noqa: PLC0415
    from g4usim_gui.preview3d.trajectories import load_trajectories   # noqa: PLC0415
    from g4usim_gui.writers.main_ini_writer import build_main_ini_text   # noqa: PLC0415

    folder = temp / name
    folder.mkdir()
    (folder / "geometry.ini").write_text(GEOMETRY, encoding="utf-8")
    package = RunPackage(package_dir=str(folder), config_dir=str(folder), macro_dir=str(folder),
                         logs_dir=str(folder), output_dir=str(folder / "output"),
                         main_ini_path=str(folder / "main.ini"), run_macro_path=str(folder / "run.mac"),
                         validation_report_path="v", project_snapshot_path="s",
                         materials_ini_path=str(ROOT / "test/materials/test_materials.ini"),
                         geometry_ini_path=str(folder / "geometry.ini"))
    scoring = ScoringEditableModel(trajectory_events=events)
    text = build_main_ini_text(package=package, run=RunSettings(), geometry=GeometrySettings(template="hierarchical"),
                               source=SourceSettings(), physics=PhysicsSettings(), scoring=scoring.to_settings(),
                               source_model=model, scoring_model=scoring)
    (folder / "main.ini").write_text(text, encoding="utf-8")
    (folder / "run.mac").write_text(f"/run/initialize\n/run/beamOn {events}\n", encoding="utf-8")
    process = subprocess.run([str(EXE), "--config", str(folder / "main.ini"), "--macro", str(folder / "run.mac"),
                              "--output", str(folder / "output")], cwd=str(folder), capture_output=True, text=True,
                             errors="replace", timeout=600)
    assert process.returncode == 0, process.stdout[-2000:] + process.stderr[-2000:]
    starts, directions = [], []
    for event in load_trajectories(folder / "output").events:
        for track in event.tracks:
            if track.primary:
                (x0, y0, z0), (x1, y1, z1) = track.points[0], track.points[1]
                norm = math.dist(track.points[0], track.points[1])
                starts.append((x0, y0, z0))
                directions.append(((x1 - x0) / norm, (y1 - y0) / norm, (z1 - z0) / norm))
    assert len(starts) == events, (name, len(starts))
    warnings: list[str] = []
    return build_preview_source(model, warnings, []), starts, directions, warnings


def check_backend(temp: Path) -> None:
    if not EXE.is_file():
        print(f"SKIP backend part: {EXE} missing")
        return
    common = dict(particle="geantino", energy="1 MeV", preset="proton_beam")
    tol = 1e-6

    # point + fixed oblique direction
    d = (1 / math.sqrt(14), 2 / math.sqrt(14), 3 / math.sqrt(14))
    source, starts, directions, _ = run_case(temp, "point_fixed", SourceEditableModel(
        **common, position="10, -20, 30 mm", direction="1,2,3"))
    point, arrow = source.glyphs
    assert all(math.dist(s, point.center) < tol for s in starts)
    assert all(math.dist(v, arrow.direction) < 1e-6 for v in directions) and math.dist(arrow.direction, d) < 1e-12

    # plane circle + isotropic
    source, starts, directions, _ = run_case(temp, "circle_iso", SourceEditableModel(
        **common, position_mode="plane", source_shape="circle", radius="5 mm", position="4, -3, -20 mm",
        angular_mode="isotropic"))
    disc = source.glyphs[0]
    cx, cy, cz = disc.center
    radii = [math.hypot(x - cx, y - cy) for x, y, _ in starts]
    assert all(abs(z - cz) < tol for _, _, z in starts) and max(radii) <= disc.radius_mm + tol
    assert max(radii) > 0.9 * disc.radius_mm, "the starts fill the drawn disc"
    assert source.glyphs[1].kind == "isotropic"
    for axis in range(3):
        assert min(v[axis] for v in directions) < -0.8 and max(v[axis] for v in directions) > 0.8

    # plane rectangle + fixed, off-axis center
    source, starts, directions, _ = run_case(temp, "rectangle_fixed", SourceEditableModel(
        **common, position_mode="plane", source_shape="rectangle", halfx="6 mm", halfy="2 mm",
        position="0, 5, 10 mm", direction="0,0,-1"))
    rect = source.glyphs[0]
    cx, cy, cz = rect.center
    assert all(abs(x - cx) <= rect.halfx_mm + tol and abs(y - cy) <= rect.halfy_mm + tol and abs(z - cz) < tol
               for x, y, z in starts)
    assert max(abs(x - cx) for x, _, _ in starts) > 0.9 * rect.halfx_mm
    assert max(abs(y - cy) for _, y, _ in starts) > 0.9 * rect.halfy_mm
    assert all(math.dist(v, source.glyphs[1].direction) < 1e-6 for v in directions)

    # the editor's normal is not used by GPS: the disc is drawn, and sampled, in the XY plane
    source, starts, _, warnings = run_case(temp, "circle_normal_x", SourceEditableModel(
        **common, position_mode="plane", source_shape="circle", radius="5 mm", position="0, 0, 0 mm",
        normal="1,0,0", direction="1,0,0"))
    assert any("XY plane" in w for w in warnings)
    assert all(abs(z) < tol for _, _, z in starts) and max(abs(x) for x, _, _ in starts) > 4.0
    print("backend: 4 x 200 primaries start inside their glyphs and leave along the arrow / in all directions")


def check_widget() -> None:
    from PySide6.QtWidgets import QApplication   # noqa: PLC0415
    from g4usim_gui.editors.geometry_editor_model import GeometryDocument   # noqa: PLC0415
    from g4usim_gui.preview3d.backend_mesh import BackendMesh, BackendVolume   # noqa: PLC0415
    from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget, pyvista_available   # noqa: PLC0415
    from g4usim_gui.preview3d.scene_builder import build_preview_scene   # noqa: PLC0415
    available, reason = pyvista_available()
    app = QApplication.instance() or QApplication([])
    if not available or app.platformName() == "offscreen":
        print(f"SKIP widget part: {reason or 'no display for VTK'}")
        return
    widget = PyVistaPreviewWidget()
    widget.resize(900, 650)
    widget.show()
    app.processEvents()
    model = SourceEditableModel(position_mode="plane", source_shape="rectangle", halfx="2 mm", halfy="1 mm",
                                position="0, 0, -8 mm", direction="0,0,1")
    scene = build_preview_scene(GeometryDocument(mode="simple_box"), model)

    def actors() -> int:
        return len(widget._plotter.renderer.actors)

    widget.render_scene(scene)
    with_source = actors()
    assert "Source:" in widget.status.text() and "plane rectangle" in widget.status.text()
    widget.set_show_source(False)
    assert actors() == with_source - 7, (actors(), with_source)   # face, outline, 1 + 4 arrows
    assert "Source:" not in widget.status.text()
    widget.set_show_source(True)
    assert actors() == with_source
    mesh = BackendMesh(source_file="x")
    box = [(x, y, z) for x in (-5, 5) for y in (-5, 5) for z in (-5, 5)]
    mesh.volumes = [BackendVolume(path="/world_PV#0/T_PV#0", name="T_PV", copy=0, depth=1, solid="G4Box",
                                  material="G4_Si", sensitive=False, cubic_volume_mm3=1.0, vertices=box,
                                  faces=[(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4),
                                         (1, 5, 7, 3)])]
    widget.render_backend_mesh(mesh, scene.source)
    assert "Source:" in widget.status.text() and actors() >= 8
    widget.render_backend_mesh(mesh)                      # external mode: no source
    assert "Source:" not in widget.status.text()
    print("widget: glyphs over the sketch and the Geant4 mesh, Show Source, description in the status line")
    widget._plotter.close()
    widget.close()


def main() -> int:
    check_model()
    with tempfile.TemporaryDirectory(prefix="g4usim-glyphs-") as directory:
        check_backend(Path(directory))
    check_widget()
    print("smoke_source_glyphs: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
