from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow,
    HierarchicalVolumeRow,
    geometry_document_from_summary,
    validate_geometry_document,
)
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.preview3d.scene_builder import build_preview_scene
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage


ROOT = Path(__file__).resolve().parents[2]


def _materials() -> set[str]:
    return {"G4_AIR", "G4_WATER", "G4_Si", "G4_Al"}


def _dummy_exe(tmp: Path) -> Path:
    exe = tmp / "G4UniversalSim.exe"
    exe.write_text("", encoding="utf-8")
    return exe


def _source() -> SourceSettings:
    return SourceSettings(
        preset="proton_beam",
        particle="proton",
        energy="10 MeV",
        position="0 mm, 0 mm, -20 mm",
        direction="0,0,1",
    )


def test_hierarchical_roundtrip() -> None:
    summary = parse_geometry(ROOT / "config" / "geometry" / "hierarchical_volume.ini")
    document = geometry_document_from_summary(summary, "hierarchical")
    assert document.mode == "hierarchical"
    assert any(row.name == "world" for row in document.volumes)
    assert any(row.name == "Detector" and row.sensitive for row in document.volumes)

    document.volumes.append(
        HierarchicalVolumeRow(
            name="Guard",
            parent="Container",
            shape="box",
            size="2 mm,2 mm,2 mm",
            material="G4_Al",
            position="1 mm,0 mm,0 mm",
            rotation="0 deg,0 deg,0 deg",
        )
    )
    duplicate = HierarchicalVolumeRow(**document.volumes[-1].__dict__.copy())
    duplicate.name = "GuardCopy"
    document.volumes.append(duplicate)
    document.volumes = [row for row in document.volumes if row.name != "GuardCopy"]
    document.is_dirty = True

    validate_geometry_document(document, material_names=_materials())
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "[volume.Guard]" in text
    reparsed = parse_geometry(_write_tmp_ini(text))
    assert "Guard" in reparsed.volume_names


def test_hierarchical_validation_errors() -> None:
    document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / "hierarchical_volume.ini"), "hierarchical")
    document.volumes.append(HierarchicalVolumeRow(name="Detector", parent="world", shape="box", size="1 mm,1 mm,1 mm", material="G4_Si"))
    document.volumes[1].parent = "Detector"
    document.volumes[2].parent = "Container"
    document.volumes[1].material = "MissingCustom"
    validate_geometry_document(document, material_names=_materials())
    joined = "\n".join(document.errors)
    assert "duplicate volume name" in joined.lower()
    assert "undefined custom material" in joined.lower()
    assert "parent cycle" in joined.lower()


def test_boolean_roundtrip_and_indices() -> None:
    summary = parse_geometry(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini")
    document = geometry_document_from_summary(summary, "hierarchical")
    assert document.mode == "hierarchical_boolean"
    assert len(document.boolean_ops) == 3
    assert document.boolean_ops[0].tool_parameters

    document.boolean_ops.append(
        BooleanOperationRow(
            target_volume="Target",
            index=99,
            operation="subtraction",
            tool_shape="box",
            tool_size="1 mm,1 mm,1 mm",
            position="0 mm,0 mm,0 mm",
            rotation="0 deg,0 deg,0 deg",
            name="extra_cut",
        )
    )
    document.boolean_ops.insert(0, document.boolean_ops.pop())
    del document.boolean_ops[1]
    document.is_dirty = True

    validate_geometry_document(document, material_names=_materials())
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "[volume.Target.boolean.0]" in text
    assert "[volume.Target.boolean.1]" in text
    assert "[volume.Target.boolean.2]" in text
    assert "[volume.Target.boolean.3]" not in text
    reparsed = parse_geometry(_write_tmp_ini(text))
    assert [op.index for op in reparsed.boolean_ops] == [0, 1, 2]


def test_boolean_validation_errors() -> None:
    document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini"), "hierarchical")
    document.boolean_ops[0].target_volume = "MissingTarget"
    document.boolean_ops[1].tool_shape = "invalid_shape"
    validate_geometry_document(document, material_names=_materials())
    joined = "\n".join(document.errors)
    assert "target volume does not exist" in joined.lower()
    assert "unsupported boolean tool shape" in joined.lower()


def test_package_writer_and_preview() -> None:
    with tempfile.TemporaryDirectory(prefix="g4usim_hier_bool_pkg_") as tmp_raw:
        tmp = Path(tmp_raw)
        exe = _dummy_exe(tmp)
        document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini"), "hierarchical")
        document.is_dirty = True
        package, report = create_run_package(
            project=G4USimProject(projectName="hier_bool_smoke"),
            paths=PathSettings(
                executable=str(exe),
                workspace_root=str(ROOT),
                runs_root=str(tmp / "runs"),
                materials_config=str(ROOT / "config" / "materials" / "material.ini"),
                geometry_config=str(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini"),
            ),
            run=RunSettings(run_name="hier_bool_smoke", threads=1, beam_on=10, check_overlaps=True),
            geometry=GeometrySettings(template="hierarchical", config_path=str(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini")),
            source=_source(),
            physics=PhysicsSettings(reference="FTFP_BERT_EMZ", default_cut="1 mm", enable_biasing=False),
            scoring=ScoringSettings(enabled=True, hits=True, event_edep=True, edep=True, hist_bins=50, hist_min="0 eV", hist_max="10 MeV"),
            geometry_document=document,
        )
        package_dir = Path(package.package_dir)
        geometry_text = (package_dir / "config" / "geometry" / "geometry.ini").read_text(encoding="utf-8")
        assert "geometry_source_mode = generated by Geometry Editor" in report
        assert "[volume.Target.boolean.0]" in geometry_text
        assert "material =" not in _boolean_section_text(geometry_text)
        scene = build_preview_scene(document, SourceEditableModel())
        assert any(volume.role == "boolean_tool" for volume in scene.volumes)

        exe_env = os.environ.get("G4USIM_EXE", "").strip()
        if exe_env:
            _run_backend(package_dir, Path(exe_env))
        else:
            print("backend run skipped: set G4USIM_EXE to run C++ hierarchical/boolean package")


def test_config_builder_hier_bool_ui() -> None:
    app = QApplication.instance() or QApplication([])
    page = ConfigBuilderPage()
    page.geometry_config.setText(str(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini"))
    page.geometry_template.setCurrentText("hierarchical")
    page.reload_geometry()
    tab_names = [page.geometry_editor_tabs.tabText(index) for index in range(page.geometry_editor_tabs.count())]
    assert "Hierarchical Volumes" in tab_names
    assert "Boolean Operations" in tab_names
    page.add_volume_button.click()
    assert any(row.name.startswith("Volume") for row in page.geometry_document.volumes)
    page.add_boolean_button.click()
    assert page.geometry_document.boolean_ops
    page.refresh_3d_preview()
    assert "3D Preview:" in page.preview3d_status.text()
    page.deleteLater()


def _write_tmp_ini(text: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="g4usim_hier_bool_ini_"))
    path = tmp / "geometry.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _boolean_section_text(text: str) -> str:
    chunks = []
    capture = False
    for line in text.splitlines():
        if line.startswith("[volume.") and ".boolean." in line:
            capture = True
        elif line.startswith("[") and capture:
            capture = False
        if capture:
            chunks.append(line)
    return "\n".join(chunks)


def _run_backend(package_dir: Path, exe: Path) -> None:
    if not exe.is_file():
        raise FileNotFoundError(f"G4USIM_EXE does not exist: {exe}")
    output_dir = package_dir / "output"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    command = [
        str(exe),
        "--config",
        str(package_dir / "config" / "main.ini"),
        "--macro",
        str(package_dir / "macros" / "run.mac"),
        "--output",
        str(output_dir),
        "--threads",
        "1",
    ]
    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=240, check=False)
    assert completed.returncode == 0, completed.stderr
    assert (output_dir / "run_summary.txt").is_file()


def main() -> int:
    test_hierarchical_roundtrip()
    test_hierarchical_validation_errors()
    test_boolean_roundtrip_and_indices()
    test_boolean_validation_errors()
    test_package_writer_and_preview()
    test_config_builder_hier_bool_ui()
    print("smoke_hier_boolean_geometry_editor: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
