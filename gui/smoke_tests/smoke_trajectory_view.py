"""Particle tracks in the 3D view (roadmap G6).

Without Geant4:
  - the loader merges the worker files of a run in event order (default: the last
    run), counts particles, keeps fixed colours for common particles, and the filter
    selects one event or all, hides particles, hides secondaries below an energy or
    all secondaries while primaries stay; a wrong schema, an event in two files and a
    bad volume index are refused;
  - the Run Config setting writes [output] trajectories = N only when N > 0, is
    validated (0..1000) and survives a project save/load.
With a display (VTK needs a real window on Windows):
  - the overlay draws one line set per shown particle; unticking a particle, the
    event arrows, "All events" and Clear change what is drawn; tracks stay when the
    geometry is drawn again.
With the backend:
  - the default demo project with "Particle tracks of the first events" = 3 runs
    through Generate and Run; when the run finishes its tracks (3 events, primaries
    starting at the source energy) are loaded into the 3D view.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))
if sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    os.environ["QT_QPA_PLATFORM"] = "windows"      # VTK needs a real OpenGL context
ROOT = GUI.parent
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

from g4usim_gui.preview3d.trajectories import (   # noqa: E402
    PARTICLE_COLOURS, TrackFilter, available_runs, load_trajectories)


def track(number, parent, particle, energy, points):
    return {"track": number, "parent": parent, "particle": particle, "pdg": 0,
            "creator": "primary" if parent == 0 else "eIoni", "initial_energy": energy, "end_process": "x",
            "length": 1.0, "points": [[*p, energy, 0] for p in points]}


def write_file(folder: Path, name: str, run: int, events: list) -> None:
    data = {"schema": "g4usim_trajectories_v1", "length_unit": "mm", "energy_unit": "MeV", "run": run,
            "thread": 0, "events": events, "truncated": False}
    (folder / name).write_text(json.dumps(data), encoding="utf-8")


def event(number, tracks):
    return {"event": number, "truncated": False, "volumes": ["Target_PV"], "tracks": tracks}


def synthetic(folder: Path) -> None:
    line = [(0, 0, 0), (0, 0, 10), (0, 1, 20)]
    write_file(folder, "trajectories_t0.json", 0, [
        event(2, [track(1, 0, "proton", 100.0, line), track(2, 1, "e-", 0.05, line)]),
        event(0, [track(1, 0, "proton", 100.0, line), track(3, 1, "gamma", 2.0, line)])])
    write_file(folder, "trajectories_t1.json", 0, [
        event(1, [track(1, 0, "proton", 100.0, line), track(2, 1, "e-", 3.0, line), track(4, 1, "kaon0L", 1.0, line)])])
    write_file(folder, "trajectories_t0_r1.json", 1, [event(0, [track(1, 0, "proton", 50.0, line)])])


def check_model(temp: Path) -> None:
    folder = temp / "synthetic"
    folder.mkdir()
    synthetic(folder)
    assert available_runs(folder) == [0, 1]
    assert len(load_trajectories(folder).events) == 1, "default: the last run"
    tracks = load_trajectories(folder, run=0)
    assert [e.event for e in tracks.events] == [0, 1, 2]
    assert tracks.particles() == {"e-": 2, "gamma": 1, "kaon0L": 1, "proton": 3}
    colours = tracks.colours()
    assert colours["proton"] == PARTICLE_COLOURS["proton"] and colours["kaon0L"] not in PARTICLE_COLOURS.values()
    names = lambda f: sorted((t.particle, t.initial_energy) for t in f.tracks(tracks))   # noqa: E731
    assert names(TrackFilter(event_index=1)) == [("e-", 3.0), ("kaon0L", 1.0), ("proton", 100.0)]
    assert len(TrackFilter(event_index=None).tracks(tracks)) == 7
    assert names(TrackFilter(event_index=1, hidden_particles={"kaon0L"})) == [("e-", 3.0), ("proton", 100.0)]
    assert names(TrackFilter(event_index=None, min_energy=1.5)) == [("e-", 3.0), ("gamma", 2.0), ("proton", 100.0),
                                                                   ("proton", 100.0), ("proton", 100.0)]
    assert names(TrackFilter(event_index=None, primaries_only=True)) == [("proton", 100.0)] * 3
    assert tracks.events[1].tracks[0].volumes == ["Target_PV"] * 3

    for name, change in (("schema", lambda d: d.update(schema="other")),
                         ("index", lambda d: d["events"][0]["tracks"][0]["points"][0].__setitem__(4, 7))):
        bad = temp / f"bad_{name}"
        bad.mkdir()
        write_file(bad, "trajectories_t0.json", 0, [event(0, [track(1, 0, "proton", 1.0, [(0, 0, 0), (1, 1, 1)])])])
        data = json.loads((bad / "trajectories_t0.json").read_text(encoding="utf-8"))
        change(data)
        (bad / "trajectories_t0.json").write_text(json.dumps(data), encoding="utf-8")
        try:
            load_trajectories(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"a bad file ({name}) must be refused")
    duplicate = temp / "duplicate"
    duplicate.mkdir()
    for name in ("trajectories_t0.json", "trajectories_t1.json"):
        write_file(duplicate, name, 0, [event(0, [])])
    try:
        load_trajectories(duplicate)
    except ValueError as error:
        assert "more than one file" in str(error)
    else:
        raise AssertionError("an event in two files must be refused")

    # volumes turn to glass while tracks are shown, fainter when many are stacked (40 water slabs)
    from g4usim_gui.preview3d.view_model import ViewItem, ViewState   # noqa: PLC0415
    one = ViewState(items=[ViewItem("a", "a", "G4_WATER")])
    stack = ViewState(items=[ViewItem(f"s{i}", f"s{i}", "G4_WATER") for i in range(40)])
    assert one.style(one.items[0])["opacity"] == 0.6
    for state in (one, stack):
        state.tracks_shown = True
    assert one.style(one.items[0])["opacity"] == 0.15
    glass = stack.style(stack.items[0])["opacity"]
    assert 0.01 <= glass < 0.02 and 1 - (1 - glass) ** 80 <= 0.6, glass
    stack.selected = "s0"
    assert stack.style(stack.items[0])["opacity"] >= 0.85    # the selected volume stays solid
    print("loader and filters: events merged in order, particles, colours, filters, bad files refused, glass")


def check_setting() -> None:
    from g4usim_gui.core.project import G4USimProject, project_from_dict, project_to_dict   # noqa: PLC0415
    from g4usim_gui.editors.source_physics_scoring_model import (   # noqa: PLC0415
        ScoringEditableModel, validate_scoring_model)
    from g4usim_gui.models.package_model import RunPackage   # noqa: PLC0415
    from g4usim_gui.models.run_model import RunSettings   # noqa: PLC0415
    from g4usim_gui.models.package_model import GeometrySettings   # noqa: PLC0415
    from g4usim_gui.models.physics_model import PhysicsSettings   # noqa: PLC0415
    from g4usim_gui.models.source_model import SourceSettings   # noqa: PLC0415
    from g4usim_gui.writers.main_ini_writer import build_main_ini_text   # noqa: PLC0415

    def ini(model):
        package = RunPackage(package_dir="p", config_dir="c", macro_dir="m", logs_dir="l", output_dir="o",
                             main_ini_path="c/main.ini", run_macro_path="m/run.mac", validation_report_path="v",
                             project_snapshot_path="s", materials_ini_path="c/materials.ini",
                             geometry_ini_path="c/geometry.ini")
        return build_main_ini_text(package=package, run=RunSettings(), geometry=GeometrySettings(template="hierarchical"),
                                   source=SourceSettings(), physics=PhysicsSettings(), scoring=model.to_settings(),
                                   scoring_model=model)

    model = ScoringEditableModel()
    assert "trajectories" not in ini(model)
    model.trajectory_events = 3
    text = ini(model)
    assert "[output]\ndir = o\ntrajectories = 3\n\n[materials]" in text, text[:400]
    model.trajectory_events = 1001
    assert validate_scoring_model(model).errors
    project = G4USimProject()
    project.scoringEditor = ScoringEditableModel(trajectory_events=5)
    project.scoringSettings = project.scoringEditor.to_settings()
    restored = project_from_dict(json.loads(json.dumps(project_to_dict(project))))
    assert restored.scoringEditor.trajectory_events == 5 and restored.scoringSettings.trajectory_events == 5
    old = project_to_dict(G4USimProject())
    old["scoringEditor"].pop("trajectory_events")
    assert project_from_dict(old).scoringEditor.trajectory_events == 0, "older projects default to off"
    print("setting: written only when on, validated, kept in projects (older projects: off)")


def check_widget(temp: Path) -> None:
    from PySide6.QtCore import Qt   # noqa: PLC0415
    from PySide6.QtWidgets import QApplication   # noqa: PLC0415
    from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget, pyvista_available   # noqa: PLC0415
    available, reason = pyvista_available()
    app = QApplication.instance() or QApplication([])
    if not available or app.platformName() == "offscreen":
        print(f"SKIP widget part: {reason or 'no display for VTK'}")
        return
    widget = PyVistaPreviewWidget()
    widget.resize(900, 650)
    widget.show()
    app.processEvents()
    assert widget.track_row.isHidden(), "track controls appear only with tracks"
    widget.show_trajectories(load_trajectories(temp / "synthetic", run=0))
    app.processEvents()
    assert not widget.track_row.isHidden() and widget.particle_legend.count() == 4
    assert widget.track_event.count() == 4 and len(widget._track_actors) == 2     # event 0: proton, gamma
    widget.step_event(1)
    assert len(widget._track_actors) == 3                                          # event 1: proton, e-, kaon0L
    row = next(i for i in range(widget.particle_legend.count())
               if widget.particle_legend.item(i).data(Qt.UserRole) == "kaon0L")
    widget.particle_legend.item(row).setCheckState(Qt.Unchecked)
    assert len(widget._track_actors) == 2
    widget.track_event.setCurrentIndex(widget.track_event.count() - 1)            # all events
    assert len(widget.shown_tracks()) == 6 and len(widget._track_actors) == 3
    widget.track_primaries.setChecked(True)
    assert len(widget._track_actors) == 1 and len(widget.shown_tracks()) == 3
    from g4usim_gui.preview3d.backend_mesh import BackendMesh, BackendVolume   # noqa: PLC0415
    mesh = BackendMesh(source_file="x")
    box = [(x, y, z) for x in (-5, 5) for y in (-5, 5) for z in (-5, 25)]
    mesh.volumes = [BackendVolume(path="/world_PV#0", name="world_PV", copy=0, depth=0, solid="G4Box",
                                  material="G4_AIR", sensitive=False, cubic_volume_mm3=1.0, vertices=box,
                                  faces=[(0, 1, 3, 2), (4, 6, 7, 5)])]
    widget.render_backend_mesh(mesh)
    assert len(widget._track_actors) == 1, "tracks stay when the geometry is drawn again"
    widget.clear_trajectories()
    assert not widget._track_actors and widget.track_row.isHidden()
    print("widget: line sets per particle, legend, events, all events, primaries only, clear")
    widget._plotter.close()
    widget.close()
    widget.deleteLater()
    app.processEvents()


def check_backend(temp: Path) -> None:
    if not EXE.is_file():
        print(f"SKIP backend part: {EXE} missing")
        return
    from PySide6.QtCore import QProcess, QSettings   # noqa: PLC0415
    from PySide6.QtWidgets import QApplication, QMessageBox   # noqa: PLC0415
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("TrajectoryView")
    QSettings().clear()
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    from g4usim_gui.main_window import MainWindow   # noqa: PLC0415
    window = MainWindow()
    window.show()
    window.project_page.executable.setText(str(EXE))
    window.project_page.runs_root.setText(str(temp / "runs"))
    page = window.config_builder_page
    page.preview3d_auto_backend.setChecked(False)
    page.beam_on.setValue(5)
    page.threads.setValue(2)
    page.scoring_editor_trajectories.setValue(3)
    app.processEvents()
    assert page.scoring_editor.trajectory_events == 3
    exits: list[int] = []
    window.runner.finished.connect(exits.append)
    window.generate_package(run_after_generate=True)
    end = time.monotonic() + 600
    while not exits and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.05)
    assert exits == [0], exits
    app.processEvents()
    view = page.preview3d_widget
    if hasattr(view, "trajectories"):            # the PyVista view (the text fallback has no overlay)
        assert view.trajectories is not None, "the finished run's tracks were not loaded"
        events = view.trajectories.events
        assert [e.event for e in events] == [0, 1, 2], [e.event for e in events]
        energy = float(page.source_editor.energy.split()[0])
        primaries = [t for e in events for t in e.tracks if t.primary]
        assert len(primaries) == 3 and all(abs(t.initial_energy - energy) < 1e-6 for t in primaries), primaries
        print(f"backend: Generate and Run wrote and showed tracks of 3 events "
              f"({sum(len(e.tracks) for e in events)} tracks)")
    else:
        print("backend: run finished; the 3D view is the text fallback (no PyVista)")
    window.close()
    window.deleteLater()
    app.processEvents()
    QSettings().clear()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim-tracks-") as directory:
        temp = Path(directory)
        check_model(temp)
        check_setting()
        check_widget(temp)
        check_backend(temp)
    print("smoke_trajectory_view: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
