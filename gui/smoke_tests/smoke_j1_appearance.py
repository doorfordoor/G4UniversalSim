"""J1 theme and display preference boundaries; no physics execution implied."""
from __future__ import annotations
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if "--renderer" in sys.argv and sys.platform == "win32" else "offscreen")

from PySide6.QtWidgets import QApplication
from g4usim_gui.core.theme import apply_theme, current_colors, B, K, C
from g4usim_gui.preview3d.view_model import ViewState, ViewItem
from g4usim_gui.preview3d.appearance_controls import AppearanceControls
from g4usim_gui.preview3d.fallback_preview_widget import FallbackPreviewWidget


def main():
    app = QApplication.instance() or QApplication([])
    apply_theme(app, "light", "K")
    assert current_colors() == K
    apply_theme(app, "dark", "C")
    assert current_colors() == C and app.property("lightThemePalette") == "K"
    apply_theme(app, "system")
    assert current_colors() in (K, C) and app.property("lightThemePalette") == "K"
    apply_theme(app, "light")
    assert current_colors() == K
    apply_theme(app, "light", "B")
    assert current_colors() == B
    for mode, palette in (("bad", "B"), ("light", "unknown")):
        try:
            apply_theme(app, mode, palette)
        except ValueError:
            pass
        else:
            assert False, "Invalid theme accepted"
    a = ViewItem("/world/detector:0", "detector", "G4_Si")
    b = ViewItem("/world/detector:1", "detector", "G4_Si")
    world = ViewItem("/world", "world", "G4_AIR", world=True)
    state = ViewState(items=[world, a, b])
    state.set_appearance("material", "G4_Si", colour="#abcdef", opacity=0.4)
    state.set_appearance("volume", a.key, opacity=0.72)
    assert state.style(a)["colour"] == "#abcdef" and state.style(a)["opacity"] == 0.72
    assert state.style(b)["opacity"] == 0.4
    assert state.legend()[0][1] == "#abcdef"
    for selected in (None, "detector", "world"):
        state.select(selected)
        state.tracks_shown = True
        state.isolated = "detector"
        apply_theme(app, "dark")
        assert state.style(a)["opacity"] == 0.72 and state.style(b)["opacity"] == 0.4
    state.set_appearance("volume", world.key, colour="#123456", opacity=0)
    assert state.style(world)["opacity"] == 0 and state.style(world)["colour"] == "#123456"
    before = dict(state.volume_appearance[a.key])
    for invalid in (-0.01, 1.01, float("nan"), float("inf"), True):
        try:
            state.set_appearance("volume", a.key, colour="#112233", opacity=invalid)
        except ValueError:
            pass
        else:
            assert False, "Invalid opacity accepted"
        assert state.volume_appearance[a.key] == before
    for scope, target, colour in (("bad", a.key, "#112233"), ("volume", "absent", "#112233"),
                                  ("volume", a.key, "red")):
        try:
            state.set_appearance(scope, target, colour=colour)
        except ValueError:
            pass
        else:
            assert False, "Invalid appearance accepted"
    controls = AppearanceControls(state)
    changed = []
    controls.changed.connect(lambda: changed.append(True))
    controls.target.setCurrentIndex(controls.target.findData(a.key))
    controls.opacity.setValue(81)
    assert state.style(a)["opacity"] == 0.81 and changed
    assert state.style(b)["opacity"] == 0.4
    controls.reset.click()
    assert a.key not in state.volume_appearance and state.style(a)["opacity"] == 0.4
    controls.scope.setCurrentIndex(1)
    controls.target.setCurrentIndex(controls.target.findData("G4_Si"))
    controls.opacity.setValue(35)
    assert state.style(a)["opacity"] == state.style(b)["opacity"] == 0.35
    state.set_appearance("volume", a.key, colour="#999999")
    state.set_items([world, a, b])
    assert state.volume_appearance[a.key]["colour"] == "#999999"
    state.set_items([world, b])
    assert not state.volume_appearance and not state.material_appearance
    state.set_appearance("volume", b.key, opacity=0.2)
    changed_copy = ViewItem(b.key, b.name, "G4_Pb")
    state.set_items([world, changed_copy])
    assert not state.volume_appearance  # same key/name in a changed geometry is a different object
    state.set_items([world])
    assert not state.material_appearance
    controls.refresh_targets()
    controls.reset_all.click()
    assert not state.volume_appearance and not state.material_appearance
    state.set_items([])
    controls.refresh_targets()
    assert not controls.opacity.isEnabled() and not controls.colour.isEnabled()
    fallback = FallbackPreviewWidget(reason="test missing renderer")
    assert "text only" in fallback.appearance_unavailable.text()
    assert not hasattr(fallback, "appearance")
    fallback.close()
    controls.close()
    if "--renderer" in sys.argv:
        check_renderer(app)
    app.processEvents()
    print("smoke_j1_appearance: OK (theme, exact-copy precedence, atomic validation, Qt controls, fallback)")
    return 0


def check_renderer(app):
    from smoke_3d_view import sample_mesh
    from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget
    widget = PyVistaPreviewWidget()
    widget.resize(1100, 850)
    widget.show()
    mesh = sample_mesh()
    widget.render_backend_mesh(mesh)
    tank = next(i for i in widget.state.items if i.name == "Tank")
    controls = widget.appearance
    controls.target.setCurrentIndex(controls.target.findData(tank.key))
    tank_actor = widget._actors[tank.key]
    def panel_matches_actor():
        assert abs(controls.opacity.value() - tank_actor.GetProperty().GetOpacity() * 100) < 0.051
        assert not widget.state.volume_appearance and not widget.state.material_appearance
    panel_matches_actor()
    assert controls.opacity.value() == 12
    widget.select_volume("Tank")
    panel_matches_actor()
    assert controls.opacity.value() == 85
    widget.select_volume("")
    panel_matches_actor()
    assert controls.opacity.value() == 12
    widget.state.tracks_shown = True
    widget._apply_styles()
    panel_matches_actor()
    assert controls.opacity.value() < 12
    widget.state.tracks_shown = False
    widget.select_volume("Tank")
    widget.isolate_selected()
    panel_matches_actor()
    widget.show_all()
    panel_matches_actor()
    controls.opacity.stepUp()
    assert abs(tank_actor.GetProperty().GetOpacity() - controls.opacity.value() / 100) < 1e-9
    assert controls.opacity.value() == 86
    widget.state.reset_appearance()
    widget._appearance_changed()
    widget.select_volume("")
    item = next(i for i in widget.state.items if i.name == "Det")
    widget.state.set_appearance("material", item.material, colour="#2468ac", opacity=0.33)
    widget.state.set_appearance("volume", item.key, opacity=0.71)
    widget._appearance_changed()
    actor = widget._actors[item.key]
    assert abs(actor.GetProperty().GetOpacity() - 0.71) < 1e-9
    assert all(abs(a - b / 255) < 1e-6 for a, b in zip(actor.GetProperty().GetColor(), (36, 104, 172)))
    widget.select_volume(item.name)
    widget.state.tracks_shown = True
    widget.set_theme()
    assert abs(actor.GetProperty().GetOpacity() - 0.71) < 1e-9
    widget.render_backend_mesh(mesh)
    assert widget.state.volume_appearance[item.key]["opacity"] == 0.71
    mesh.volumes[2].vertices[0] = (1, 2, 3)  # same names/material/bounds, changed actual mesh
    widget.render_backend_mesh(mesh)
    assert not widget.state.volume_appearance and not widget.state.material_appearance
    app.processEvents()
    evidence_dir = Path(os.environ.get("J1_APPEARANCE_EVIDENCE_DIR", str(Path(__file__).resolve().parents[2] / "out/collab/j1-appearance-20261101")))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    widget._plotter.screenshot(str(evidence_dir / "renderer.png"))
    widget.grab().save(str(evidence_dir / "widget.png"))
    widget._plotter.close()
    widget.close()
    widget.deleteLater()
    app.processEvents()
    print("real PyVista/VTK actor properties and geometry identity: OK")


if __name__ == "__main__":
    sys.exit(main())
