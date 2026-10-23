"""The 3D view shows the Geant4 world by default (roadmap G1).

Without Geant4:
  - generated-mode inputs use the source files as they are and the editor's text only
    for what was edited; edited geometry/materials with errors are refused with the
    editor's messages; the key is stable for unchanged inputs and changes with the
    geometry, the materials, a file the geometry refers to (STL) and the executable;
  - the export main INI holds only materials and geometry; backend errors name the
    editor's files instead of the temporary folder.
With the backend (G4USIM_EXE or the Release build):
  - opening the 3D tab of the default demo project builds the Geant4 world without a
    run package; asking again with unchanged inputs is served from the cache (no
    second Geant4 run);
  - an edit triggers one new export after the debounce, and a burst of requests while
    Geant4 is busy ends in exactly one more export of the latest inputs;
  - an edit the editor rejects is reported without running Geant4; a geometry the
    backend rejects shows the backend's reason; with the automatic option off, edits
    do not start Geant4.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
GUI = Path(__file__).resolve().parents[1]
ROOT = GUI.parent
sys.path.insert(0, str(GUI))

from PySide6.QtCore import QProcess, QSettings   # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox   # noqa: E402

from g4usim_gui.editors.geometry_editor_model import (   # noqa: E402
    GeometryDocument, HierarchicalVolumeRow, validate_geometry_document)
from g4usim_gui.editors.material_editor_model import MaterialDocument, MaterialRow, validate_material_document   # noqa: E402
from g4usim_gui.preview3d.backend_inputs import (   # noqa: E402
    backend_failure, external_inputs, generated_inputs, write_main_ini)

EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))


def check_inputs(temp: Path) -> None:
    stl = temp / "part.stl"
    stl.write_text("solid a\nendsolid a\n", encoding="utf-8")
    geometry_file = temp / "geometry.ini"
    geometry_file.write_text("[world]\nshape = box\nsize = 1 m, 1 m, 1 m\nmaterial = G4_AIR\n"
                             "[volume.Part]\nparent = world\nshape = tessellated\nfile = part.stl\nmaterial = G4_Si\n",
                             encoding="utf-8")
    materials_file = ROOT / "test/materials/test_materials.ini"
    exe = temp / "fake.exe"
    exe.write_bytes(b"x")
    source = GeometryDocument(mode="hierarchical")   # not edited: the source file is used as is
    materials = MaterialDocument()

    def inputs(geometry=source, mats=materials):
        return generated_inputs(template="hierarchical", geometry_config=str(geometry_file), geometry=geometry,
                                materials_config=str(materials_file), materials=mats, executable=str(exe))

    first = inputs()
    assert first.geometry_text is None and first.materials_text is None and not first.edited
    assert inputs().key == first.key, "key must be stable for unchanged inputs"
    stl.write_text("solid b\nendsolid b\n", encoding="utf-8")
    assert inputs().key != first.key, "a changed STL must change the key"
    exe.write_bytes(b"xy")
    assert inputs().key != first.key

    edited = GeometryDocument(mode="hierarchical", volumes=[
        HierarchicalVolumeRow(name="world", shape="box", size="1 m, 1 m, 1 m", material="G4_AIR"),
        HierarchicalVolumeRow(name="Pad", parent="world", shape="box", size="1 cm, 1 cm, 1 cm", material="G4_Si",
                              position="0 mm, 0 mm, 0 mm", rotation="0 deg, 0 deg, 0 deg")])
    edited.is_dirty = True
    validate_geometry_document(edited, material_names=set())
    with_edit = inputs(edited)
    assert with_edit.geometry_text and "[volume.Pad]" in with_edit.geometry_text and with_edit.key != first.key
    edited.volumes[1].material = "unobtainium"
    validate_geometry_document(edited, material_names=set())
    try:
        inputs(edited)
    except ValueError as error:
        assert "unobtainium" in str(error), error
    else:
        raise AssertionError("an edited geometry with errors must not be exported")

    mats = MaterialDocument(rows=[MaterialRow(name="Mix", mode="mass_fraction", density="1 g/cm3",
                                              components_text="G4_H:0.1, G4_O:0.9")])
    mats.is_dirty = True
    validate_material_document(mats)
    with_mats = inputs(source, mats)
    assert with_mats.materials_text and "[material.Mix]" in with_mats.materials_text

    folder = temp / "export"
    main = write_main_ini(with_mats, folder).read_text(encoding="utf-8")
    assert f"config = {geometry_file.as_posix()}" in main and "editor_materials.ini" in main
    assert "[source]" not in main and "[physics]" not in main and "check_overlaps = false" in main
    reason = backend_failure(f"G4UniversalSim fatal error: bad file {(folder / 'editor_geometry.ini').as_posix()}",
                             "", folder)
    assert "<geometry from the editor>" in reason and str(folder.as_posix()) not in reason, reason
    try:
        external_inputs("", str(exe))
    except ValueError as error:
        assert "main INI" in str(error)
    else:
        raise AssertionError("external mode without a main INI must be refused")
    print("inputs: source files used as is, edits generated, key and messages as expected")


def wait_until(app: QApplication, condition, timeout_s: float = 300.0) -> bool:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    return False


def check_window(app: QApplication, temp: Path) -> None:
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    from g4usim_gui.main_window import MainWindow   # noqa: PLC0415
    window = MainWindow()
    window.resize(1300, 850)
    window.show()
    window.project_page.executable.setText(str(EXE))
    window.project_page.runs_root.setText(str(temp / "runs"))
    page = window.config_builder_page
    controller = window.geometry_controller
    window.page_stack.setCurrentWidget(page)
    app.processEvents()
    assert not window.project.configPath, "the demo project must not need a generated package"

    def idle() -> bool:
        return controller.process.state() == QProcess.NotRunning and not controller._pending

    preview_index = page.workspace_tabs.indexOf(page.preview3d_widget.parentWidget())
    page.workspace_tabs.setCurrentIndex(preview_index)   # opening the 3D tab asks for the Geant4 world
    assert wait_until(app, lambda: controller.exports == 1), "opening the 3D tab did not start an export"
    assert wait_until(app, idle), "export did not finish"
    assert wait_until(app, lambda: "volume copies" in page.preview3d_status.text(), 30), page.preview3d_status.text()
    assert "15 volume copies" in page.preview3d_status.text(), page.preview3d_status.text()
    print(f"3D tab: {page.preview3d_status.text()}")

    window.export_backend_geometry()
    app.processEvents()
    assert controller.exports == 1 and "cache" in page.preview3d_status.text(), page.preview3d_status.text()
    print("unchanged inputs: shown from the cache without running Geant4")

    def edit(material: str) -> None:
        volume = next(v for v in page.geometry_document.volumes if v.name == "target_sphere")
        volume.material = material
        page._mark_geometry_dirty()

    edit("lead")
    assert wait_until(app, lambda: controller.exports == 2), "an edit did not start a new export"
    assert wait_until(app, idle)
    assert wait_until(app, lambda: "volume copies" in page.preview3d_status.text(), 30)
    assert "cache" not in page.preview3d_status.text()
    print("edit: one new export after the debounce")

    edit("copper")
    assert wait_until(app, lambda: controller.exports == 3)
    for material in ("aluminum", "water", "silicon"):   # requests while Geant4 is busy
        edit(material)
        window.export_backend_geometry()
    assert wait_until(app, idle), "pending export did not run"
    app.processEvents()
    assert controller.exports == 4, f"a burst must end in exactly one more export, got {controller.exports}"
    sphere = next(v for v in page.geometry_document.volumes if v.name == "target_sphere")
    assert sphere.material == "silicon"
    print(f"burst of edits while busy: {controller.exports - 3} more export (latest inputs)")

    edit("unobtainium")
    window.export_backend_geometry()
    app.processEvents()
    assert controller.exports == 4 and "unobtainium" in page.preview3d_messages.toPlainText(), (
        controller.exports, page.preview3d_messages.toPlainText()[:800])
    print("editor error: reported without running Geant4")
    edit("silicon")
    assert wait_until(app, idle)

    page.preview3d_auto_backend.setChecked(False)
    edit("iron")
    deadline = time.monotonic() + 2.5
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert controller.exports == 4, "with the automatic option off an edit must not run Geant4"
    print("automatic option off: edits do not start Geant4")

    geometry = temp / "bad_geometry.ini"
    geometry.write_text("[world]\nshape = box\nsize = 1 m, 1 m, 1 m\nmaterial = G4_AIR\n"
                        "[volume.X]\nparent = world\nshape = box\nsize = 1 cm, 1 cm, 1 cm\nmaterial = nothing_here\n",
                        encoding="utf-8")
    main = temp / "bad_main.ini"
    main.write_text(f"[materials]\nfile = {(ROOT / 'config/materials/material.ini').as_posix()}\n"
                    f"[geometry]\ntemplate = hierarchical\nconfig = {geometry.as_posix()}\n", encoding="utf-8")
    project_page = window.project_page
    project_page.run_input_mode.setCurrentIndex(project_page.run_input_mode.findData("external"))
    project_page.config_path.setText(str(main))
    window.export_backend_geometry()
    assert wait_until(app, lambda: controller.exports == 5 and idle())
    assert wait_until(app, lambda: "nothing_here" in page.preview3d_messages.toPlainText(), 30), \
        page.preview3d_messages.toPlainText()
    print("backend error: " + page.preview3d_messages.toPlainText().splitlines()[0][:150])
    window.close()
    window.deleteLater()
    app.processEvents()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="g4usim-g1-") as directory:
        temp = Path(directory)
        check_inputs(temp)
        if not EXE.is_file():
            print(f"SKIP window part: backend executable missing ({EXE})")
        else:
            app = QApplication.instance() or QApplication([])
            app.setOrganizationName("G4UniversalSimSmoke")
            app.setApplicationName("BackendGeometryAuto")
            QSettings().clear()
            check_window(app, temp)
            QSettings().clear()
    print("smoke_backend_geometry_auto: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
