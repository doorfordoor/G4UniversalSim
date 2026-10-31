"""Smoke test for the roadmap A5 backend geometry view.

1. load_backend_mesh accepts a valid g4usim_geometry_mesh_v1 file and rejects
   a wrong schema, a bad face index and a mismatched volume_count;
2. with G4USIM_EXE: MainWindow (external mode) runs the backend through the
   asynchronous QProcess path, loads the exported mesh of a geometry with a
   z-replica and an STL solid, and shows it on the 3D Preview tab;
3. a missing main INI is reported instead of starting the backend.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QEvent, QProcess  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui_test_window import MainWindow  # noqa: E402
from smoke_k1_workflow import wait_workflow  # noqa: E402
from g4usim_gui.preview3d.backend_mesh import load_backend_mesh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

STL = """solid t
facet normal 0 0 0
 outer loop
  vertex 0 0 0
  vertex 0 10 0
  vertex 10 0 0
 endloop
endfacet
facet normal 0 0 0
 outer loop
  vertex 0 0 0
  vertex 10 0 0
  vertex 0 0 10
 endloop
endfacet
facet normal 0 0 0
 outer loop
  vertex 0 0 0
  vertex 0 0 10
  vertex 0 10 0
 endloop
endfacet
facet normal 0 0 0
 outer loop
  vertex 10 0 0
  vertex 0 10 0
  vertex 0 0 10
 endloop
endfacet
endsolid t
"""


def check_loader(temp: Path) -> None:
    good = {"schema": "g4usim_geometry_mesh_v1", "length_unit": "mm", "volume_count": 1, "volumes": [
        {"path": "/world_PV#0", "name": "world_PV", "copy": 0, "depth": 0, "logical": "world_LV", "solid": "G4Box",
         "material": "G4_AIR", "sensitive": False, "cubic_volume_mm3": 8.0,
         "vertices": [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1]], "faces": [[0, 1, 2, 3]]}]}
    path = temp / "good.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    mesh = load_backend_mesh(path)
    assert len(mesh.volumes) == 1 and mesh.volumes[0].faces == [(0, 1, 2, 3)]
    for label, change in (("schema", {"schema": "other"}), ("count", {"volume_count": 2})):
        bad = dict(good, **change)
        bad_path = temp / f"bad_{label}.json"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        try:
            load_backend_mesh(bad_path)
        except ValueError:
            pass
        else:
            raise AssertionError(f"loader accepted bad {label}")
    bad = json.loads(json.dumps(good))
    bad["volumes"][0]["faces"] = [[0, 1, 9]]
    bad_path = temp / "bad_face.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        load_backend_mesh(bad_path)
    except ValueError:
        pass
    else:
        raise AssertionError("loader accepted a bad face index")
    print("loader: valid file read; wrong schema, count and face index rejected")


def close_window(app: QApplication, window: MainWindow, timeout: float = 45) -> None:
    """Wait for MainWindow to accept close; it owns service/recovery shutdown."""
    deadline = time.monotonic() + timeout
    accepted = window.close()
    while not accepted and time.monotonic() < deadline:
        app.processEvents()
        # Let pending completion/closed callbacks run before requesting close again.
        if (not window.experiment.busy
                and not getattr(window, "_experiment_loading", False)
                and not window._experiment_service_waiting):
            accepted = window.close()
        if not accepted:
            time.sleep(.005)
    assert accepted, "MainWindow close did not finish within bound"
    assert window._experiment_recovery_closed, "MainWindow did not finish recovery close"
    assert not window.experiment.busy, "experiment still busy after accepted close"
    assert not window._experiment_service_waiting, "experiment close still waiting"
    assert not window.isVisible(), "MainWindow remained visible after accepted close"
    app.processEvents()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def check_window(app: QApplication, temp: Path, executable: str) -> None:
    (temp / "tet.stl").write_text(STL, encoding="utf-8")
    geometry = temp / "geometry.ini"
    geometry.write_text(
        "[world]\nshape = box\nsize = 1 m, 1 m, 1 m\nmaterial = G4_Galactic\n"
        "[volume.Stack]\nparent = world\nshape = box\nsize = 50 mm, 50 mm, 100 mm\nmaterial = G4_WATER\n"
        "[volume.Slice]\nparent = Stack\nshape = box\nsize = 50 mm, 50 mm, 10 mm\nmaterial = G4_WATER\n"
        "placement = replica\nreplica_axis = z\nreplica_count = 10\nreplica_width = 10 mm\nsensitive = true\n"
        "[volume.Tet]\nparent = world\nshape = tessellated\nfile = tet.stl\nmaterial = G4_Si\n"
        "position = 200 mm, 0 mm, 0 mm\n", encoding="utf-8")
    config = temp / "main.ini"
    config.write_text(
        "[run]\nthreads = 1\n[materials]\nfile = " + (ROOT / "config/materials/material.ini").as_posix() + "\n"
        "[geometry]\ntemplate = hierarchical\nconfig = " + geometry.as_posix() + "\n"
        "[physics]\nreference = FTFP_BERT\n[source]\nparticle = geantino\nenergy = 1 MeV\n"
        "position = 0,0,-400 mm\ndirection = +z\n", encoding="utf-8")

    window = MainWindow()
    try:
        page = window.project_page
        page.executable.setText(executable)
        page.workspace_root.setText(str(temp))
        page.output_dir.setText(str(temp / "output"))
        page.run_input_mode.setCurrentIndex(page.run_input_mode.findData("external"))
        page.config_path.setText("")
        window.export_backend_geometry()
        builder = window.config_builder_page
        assert "main INI" in builder.preview3d_messages.toPlainText(), builder.preview3d_messages.toPlainText()
        print("missing main INI: reported without starting the backend")

        page.config_path.setText(str(config))
        window.export_backend_geometry()
        assert window._geometry_export.state() != QProcess.NotRunning, "export did not start"
        assert not builder.preview3d_backend_button.isEnabled()
        assert window._geometry_export.waitForFinished(300000), "backend export timed out"
        app.processEvents()
        status = builder.preview3d_status.text()
        messages = builder.preview3d_messages.toPlainText()
        assert "13 volume copies" in status, (status, messages[-2000:])
        assert "G4TessellatedSolid" in messages and "/Slice_PV#9" in messages, messages[-2000:]
        assert builder.preview3d_backend_button.isEnabled()
        print(f"MainWindow: {status}")
    finally:
        close_window(app, window)


def check_demo_project(app: QApplication, temp: Path, executable: str) -> None:
    """Roadmap E1: the default demo project validates, generates a package and shows backend geometry.

    The demo geometry names its materials in lower case (silicon, iron, water); the GUI used
    to compare names case-sensitively and to pair it with a materials file without iron, so
    no package could be generated and Show Backend Geometry failed although Geant4 builds it.
    """
    from PySide6.QtWidgets import QMessageBox   # noqa: PLC0415
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.Ok)
    window = MainWindow()
    try:
        page = window.project_page
        page.executable.setText(executable)
        page.runs_root.setText(str(temp / "runs"))
        page.output_dir.setText(str(temp / "runs" / "demo" / "output"))
        builder = window.config_builder_page
        assert builder.materials_config.text().replace("\\", "/").endswith("test/materials/test_materials.ini")
        assert not builder.geometry_document.errors, builder.geometry_document.errors
        assert not builder.material_document.errors, builder.material_document.errors
        window.generate_package(run_after_generate=False)
        wait_workflow(app, window)
        assert window.project.configPath and Path(window.project.configPath).is_file(), "demo package not generated"
        window.export_backend_geometry()
        assert window._geometry_export.waitForFinished(300000), "backend export timed out"
        app.processEvents()
        status = builder.preview3d_status.text()
        assert "volume copies" in status, (status, builder.preview3d_messages.toPlainText()[-2000:])
        print(f"demo project: package generated, {status}")
    finally:
        close_window(app, window)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix="g4usim_backend_geometry_") as directory:
        temp = Path(directory)
        check_loader(temp)
        executable = os.environ.get("G4USIM_EXE", str(ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
        if Path(executable).is_file():
            check_window(app, temp, executable)
            check_demo_project(app, temp, executable)
        else:
            print(f"SKIP backend part: executable not found ({executable})")
    print("smoke_backend_geometry: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
