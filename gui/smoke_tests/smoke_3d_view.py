"""3D view design and interaction (roadmap G2/G3).

View model (no Qt, no VTK):
  - one colour per material: common materials keep fixed colours, the others get
    distinct palette colours in name order; the legend counts volume copies;
  - visibility: world hidden by default, hide / isolate / show all, per-material
    legend toggles; choices that still apply survive a new geometry;
  - styles: containers (volumes with daughters) faint, sensitive volumes solid,
    selection outlined and the others faded; section plane at the requested fraction
    of the visible bounds; Geant4 names (_PV/_LV) map to the editor's names.
Widget (real PyVista window; VTK cannot render on Qt's offscreen platform on Windows,
so this part uses the native platform there and is skipped elsewhere without a
display):
  - a backend mesh becomes styled actors with the model's colours and opacities and a
    legend; Hide / Isolate / Show all and an unticked legend row switch actor
    visibility; a section plane clips every volume's mapper;
  - a click (press and release at one spot) on a volume selects it and emits its
    editor name, a drag does not, a click on empty space clears the selection;
  - in the Configuration page the selection follows both ways between the 3D view and
    the volume table.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))
if sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    os.environ["QT_QPA_PLATFORM"] = "windows"      # VTK needs a real OpenGL context

from g4usim_gui.preview3d.backend_mesh import BackendMesh, BackendVolume   # noqa: E402
from g4usim_gui.preview3d.view_model import (   # noqa: E402
    KNOWN_COLOURS, PALETTE, ViewItem, ViewState, backend_items, mark_containers, volume_name)


def box(path, name, depth, material, centre, half, sensitive=False, logical=""):
    cx, cy, cz = centre
    hx, hy, hz = half
    vertices = [(cx + sx * hx, cy + sy * hy, cz + sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return BackendVolume(path=path, name=name, copy=0, depth=depth, solid="G4Box", material=material,
                         sensitive=sensitive, cubic_volume_mm3=8 * hx * hy * hz, vertices=vertices, faces=faces,
                         logical=logical)


def sample_mesh() -> BackendMesh:
    mesh = BackendMesh(source_file="sample")
    mesh.volumes = [
        box("/world_PV#0", "world_PV", 0, "G4_AIR", (0, 0, 0), (500, 500, 500), logical="world_LV"),
        box("/world_PV#0/Tank_PV#0", "Tank_PV", 1, "G4_WATER", (0, 0, 0), (100, 100, 100), logical="Tank_LV"),
        box("/world_PV#0/Tank_PV#0/Det_PV#0", "Det_PV", 2, "Scint", (0, 0, 0), (20, 20, 20), True, "Det_LV"),
        box("/world_PV#0/Shield_PV#0", "Shield_PV", 1, "G4_Pb", (300, 0, 0), (20, 100, 100), logical="Shield_LV"),
    ]
    return mesh


def check_model() -> None:
    assert volume_name("Tank_PV") == "Tank" and volume_name("Det_LV") == "Det" and volume_name("Plain") == "Plain"
    items = backend_items(sample_mesh())
    by_name = {item.name: item for item in items}
    assert set(by_name) == {"world", "Tank", "Det", "Shield"}
    assert by_name["world"].world and by_name["Tank"].container and not by_name["Det"].container
    state = ViewState()
    state.set_items(items)
    colours = state.colours()
    assert colours["G4_WATER"] == KNOWN_COLOURS["g4_water"] and colours["G4_Pb"] == KNOWN_COLOURS["g4_pb"]
    assert colours["Scint"] in PALETTE and len(set(colours.values())) == len(colours)
    assert state.legend() == [("G4_Pb", colours["G4_Pb"], 1, True), ("G4_WATER", colours["G4_WATER"], 1, True),
                              ("Scint", colours["Scint"], 1, True)]
    visible = lambda: sorted(i.name for i in items if state.visible(i))   # noqa: E731
    assert visible() == ["Det", "Shield", "Tank"], "world hidden by default"
    assert state.style(by_name["Tank"])["opacity"] < 0.2 and state.style(by_name["Det"])["opacity"] > 0.8

    state.select("Det")
    assert state.style(by_name["Det"])["selected"] and state.style(by_name["Shield"])["opacity"] < 0.6 * 0.6
    state.isolate_selected()
    assert visible() == ["Det"]
    state.show_all()
    state.select("Shield")
    state.hide_selected()
    assert visible() == ["Det", "Tank"] and state.selected is None
    state.toggle_material("G4_WATER", False)
    assert visible() == ["Det"] and state.legend()[1][3] is False
    state.show_all()
    state.show_world = True
    assert visible() == ["Det", "Shield", "Tank", "world"]
    state.select("nonexistent")
    assert state.selected is None

    state.show_world = False
    state.section_axis, state.section_fraction = "x", 0.25
    origin, normal = state.section_plane()
    assert abs(origin[0] - (-100 + 0.25 * 420)) < 1e-9 and normal == (-1.0, 0.0, 0.0), (origin, normal)
    state.section_axis = ""
    assert state.section_plane() is None

    state.hidden.add("Shield")
    state.set_items([i for i in items if i.name != "Shield"])    # new geometry without Shield
    assert "Shield" not in state.hidden

    sketch = [ViewItem("a", "a", "G4_AIR", bounds=(-10, 10, -10, 10, -10, 10)),
              ViewItem("b", "b", "G4_Si", bounds=(-1, 1, -1, 1, -1, 1))]
    mark_containers(sketch)
    assert sketch[0].container and not sketch[1].container
    print("view model: colours, legend, visibility, styles, section and names as expected")


def check_widget() -> None:
    from PySide6.QtWidgets import QApplication   # noqa: PLC0415
    from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget, pyvista_available   # noqa: PLC0415
    available, reason = pyvista_available()
    if not available:
        print(f"SKIP widget part: {reason}")
        return
    app = QApplication.instance() or QApplication([])
    if app.platformName() == "offscreen":
        print("SKIP widget part: no display for VTK")
        return
    widget = PyVistaPreviewWidget()
    widget.resize(900, 650)
    widget.show()
    app.processEvents()
    widget.render_backend_mesh(sample_mesh())
    app.processEvents()
    assert len(widget._actors) == 4 and widget.legend.count() == 3
    actor = {widget._items[k].name: a for k, a in widget._actors.items()}
    assert not actor["world"].GetVisibility() and actor["Det"].GetVisibility()
    assert abs(actor["Det"].GetProperty().GetOpacity() - 0.9) < 1e-6
    assert actor["Tank"].GetProperty().GetOpacity() < 0.2

    selections: list[str] = []
    widget.volumeSelected.connect(selections.append)
    renderer = widget._plotter.renderer
    widget.set_camera("front")
    app.processEvents()

    def display_point(world):
        renderer.SetWorldPoint(*world, 1.0)
        renderer.WorldToDisplay()
        x, y, _ = renderer.GetDisplayPoint()
        return int(round(x)), int(round(y))

    def click(position, release=None):
        widget._plotter.iren.interactor.SetEventPosition(*position)
        widget._on_press()
        widget._plotter.iren.interactor.SetEventPosition(*(release or position))
        widget._on_release()

    click(display_point((300, -21, 0)))           # the lead shield, front face
    assert selections[-1] == "Shield" and widget.state.selected == "Shield", selections
    click(display_point((0, -101, 0)), (display_point((0, -101, 0))[0] + 40, display_point((0, -101, 0))[1]))
    assert len(selections) == 1, "a drag must not select"
    click((2, 2))                                 # empty corner
    assert selections[-1] == "" and widget.state.selected is None
    print("widget: click selects and emits the editor name, drag does not, empty space clears")

    widget.select_volume("Shield")
    widget.hide_selected()
    assert not actor["Shield"].GetVisibility()
    widget.select_volume("Det")
    widget.isolate_selected()
    assert actor["Det"].GetVisibility() and not actor["Tank"].GetVisibility()
    widget.show_all()
    assert actor["Shield"].GetVisibility() and actor["Tank"].GetVisibility()
    row = next(i for i in range(widget.legend.count()) if widget.legend.item(i).text().startswith("G4_Pb"))
    from PySide6.QtCore import Qt   # noqa: PLC0415
    widget.legend.item(row).setCheckState(Qt.Unchecked)
    assert not actor["Shield"].GetVisibility()
    widget.show_all()
    widget.section_axis.setCurrentIndex(widget.section_axis.findData("z"))
    widget.section_slider.setValue(300)
    assert all(a.GetMapper().GetNumberOfClippingPlanes() == (0 if widget._items[k].world else 1)
               for k, a in widget._actors.items())
    widget.section_axis.setCurrentIndex(0)
    assert all(a.GetMapper().GetNumberOfClippingPlanes() == 0 for a in widget._actors.values())
    for preset in ("front", "side", "top", "iso"):
        widget.set_camera(preset)
    widget.ortho.setChecked(True)
    assert widget._plotter.camera.parallel_projection
    print("widget: hide, isolate, show all, legend toggle, section plane and cameras")
    widget._plotter.close()      # release the OpenGL context before the widget goes
    widget.close()
    widget.deleteLater()
    app.processEvents()

    from PySide6.QtCore import QSettings   # noqa: PLC0415
    from g4usim_gui.main_window import MainWindow   # noqa: PLC0415
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("View3D")
    QSettings().clear()
    window = MainWindow()                          # the demo project fills the volume table
    window.resize(1300, 850)
    window.show()
    page = window.config_builder_page
    page.preview3d_auto_backend.setChecked(False)  # this test does not need Geant4
    view = page.preview3d_widget
    if not isinstance(view, PyVistaPreviewWidget):
        print("SKIP page part: the page uses the text fallback")
        return
    names = [page.geometry_table.item(r, 1).text() for r in range(page.geometry_table.rowCount())]
    assert "target_sphere" in names, names
    view.volumeSelected.emit("target_sphere")      # as a click in the view does
    rows = {index.row() for index in page.geometry_table.selectedIndexes()}
    assert rows == {names.index("target_sphere")}, rows
    page.refresh_3d_preview()                      # the editor sketch has the same volume names
    page.geometry_table.selectRow(names.index("water_moderator"))
    app.processEvents()
    assert view.state.selected == "water_moderator", view.state.selected
    print("page: 3D selection selects the table row; a table row selects the volume in the view")
    window.close()
    QSettings().clear()


def main() -> int:
    check_model()
    check_widget()
    print("smoke_3d_view: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
