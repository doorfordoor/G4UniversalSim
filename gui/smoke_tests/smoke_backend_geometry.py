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
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QProcess  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.main_window import MainWindow  # noqa: E402
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
    window.close()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix="g4usim_backend_geometry_") as directory:
        temp = Path(directory)
        check_loader(temp)
        executable = os.environ.get("G4USIM_EXE", str(ROOT / "build_vs2026/Release/G4UniversalSim.exe"))
        if Path(executable).is_file():
            check_window(app, temp, executable)
        else:
            print(f"SKIP backend part: executable not found ({executable})")
    print("smoke_backend_geometry: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
