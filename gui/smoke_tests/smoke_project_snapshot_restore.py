"""Restore a real writer package through the GUI, save/reload and regenerate."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import G4USimProject, load_project
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import MaterialRow, material_document_from_summary
from g4usim_gui.editors.source_physics_scoring_model import PhysicsEditableModel, ScoringEditableModel, SourceEditableModel
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.window import project as project_window
from smoke_project_import_projection import snapshot


def make_package(work: Path):
    source = work / "original_inputs"
    source.mkdir()
    materials = source / "material.ini"
    materials.write_text("[material.Mix]\nmode=mass_fraction\ndensity=2 g/cm3\ncomponents=Si:0.5,O:0.5\n", encoding="utf-8")
    geometry = source / "geometry.ini"
    geometry.write_text("[global]\nversion=2\n[world]\nshape=box\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n"
                        "[volume.Target]\nparent=world\nshape=box\nsize=1 cm,1 cm,1 cm\nmaterial=Mix\n"
                        "position=0 mm,0 mm,0 mm\nrotation=0 deg,0 deg,0 deg\nsensitive=true\n", encoding="utf-8")
    material = material_document_from_summary(parse_materials(materials))
    material.rows[0].density = "2.8 g/cm3"
    material.rows[0].components_text = "Si:0.25\nO:0.75"
    material.rows[0].is_dirty = True
    material.rows.append(MaterialRow(name="UnwrittenDraft", enabled=False, mode="mass_fraction",
                                     density="3 g/cm3", components_text="Si:1"))
    material.is_dirty = True
    document = geometry_document_from_summary(parse_geometry(geometry, "hierarchical"), "hierarchical")
    document.volumes[1].size = "3 mm,4 mm,5 mm"
    draft = copy.deepcopy(document.volumes[1])
    draft.name = "UnwrittenGeometryDraft"
    draft.enabled = False
    document.volumes.append(draft)
    document.is_dirty = True
    runs = work / "runs"
    runs.mkdir()
    project = G4USimProject(projectName="snapshot_restore", executable=sys.executable,
                            workspaceRoot=str(work), runsRoot=str(runs), threads=1)
    paths = PathSettings(executable=sys.executable, workspace_root=str(work), runs_root=str(runs),
                         materials_config=str(materials), geometry_config=str(geometry))
    settings = GeometrySettings(template="hierarchical", config_path=str(geometry))
    run = RunSettings(run_name="snapshot_restore", threads=2, seed=246, beam_on=23)
    src = SourceEditableModel(energy="7 MeV")
    physics = PhysicsEditableModel(reference_list="FTFP_BERT", default_cut="0.7 mm")
    scoring = ScoringEditableModel(hist_bins=42)
    package, _ = create_run_package(project=project, paths=paths, run=run, geometry=settings,
                                    source=src.to_settings(), physics=physics.to_settings(), scoring=scoring.to_settings(),
                                    material_document=material, geometry_document=document,
                                    source_model=src, physics_model=physics, scoring_model=scoring)
    return package, materials, geometry


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4USimSmoke")
    app.setApplicationName("ProjectSnapshotRestore")
    app.setQuitOnLastWindowClosed(False)
    set_application_language(app, "zh_CN")
    with tempfile.TemporaryDirectory(prefix="e6-snapshot-ui-") as temporary:
        work = Path(temporary)
        run_history_store.STATE_PATH = work / "state.json"
        package, materials, geometry = make_package(work)
        source = Path(package.project_snapshot_path)
        envelope = json.loads(source.read_text(encoding="utf-8"))
        try:
            load_project(source)
        except ValueError as error:
            assert "Unsupported project field" in str(error)
        else:
            assert False, "Ordinary project loading must remain strict"
        # Old external sources and hand-edited main/macro must not become the restored inputs.
        materials.write_text("[material.Mix]\nmode=mass_fraction\ndensity=999 g/cm3\ncomponents=Si:1\n", encoding="utf-8")
        geometry.write_text(geometry.read_text(encoding="utf-8").replace("1 cm,1 cm,1 cm", "9 cm,9 cm,9 cm"), encoding="utf-8")
        main_ini = Path(package.main_ini_path)
        main_text = main_ini.read_text(encoding="utf-8")
        assert "7 MeV" in main_text
        main_ini.write_text(main_text.replace("7 MeV", "99 MeV"), encoding="utf-8")
        macro = Path(package.run_macro_path)
        macro.write_text(macro.read_text(encoding="utf-8").replace("beamOn 23", "beamOn 999"), encoding="utf-8")
        originals = {p: p.read_bytes() for p in (source, materials, geometry, main_ini, macro,
                                                Path(package.materials_ini_path), Path(package.geometry_ini_path))}
        window = MainWindow()
        for timer in window.findChildren(QTimer):
            timer.stop()
        window.project_file = work / "previous.json"
        widgets = window.findChildren(QWidget)
        old = snapshot(window, widgets)
        boxes = []
        def record(kind):
            return lambda _p, title, message, *_a, **_k: boxes.append((kind, str(title), str(message)))
        with patch.object(project_window.QMessageBox, "critical", side_effect=record("critical")), \
             patch.object(project_window.QMessageBox, "warning", side_effect=record("warning")), \
             patch.object(project_window.QMessageBox, "information", side_effect=record("information")):
            assert not window._load_project_path(str(source))
            assert len(boxes) == 1 and boxes[0][:2] == ("critical", "打开项目失败"), boxes
            assert snapshot(window, widgets) == old
            # Fail before publication for malformed metadata, missing live inputs, and projection overflow.
            variants = [
                ({**envelope, "unknown_snapshot_field": 1}, "unknown_snapshot_field"),
                ({**envelope, "runPackage": {**envelope["runPackage"], "future_snapshot_meta": 1}}, "future_snapshot_meta"),
                ({**envelope, "runSettings": {**envelope["runSettings"], "beam_on": 10**100}}, "runSettings.beam_on"),
            ]
            for invalid, fragment in variants:
                source.write_text(json.dumps(invalid), encoding="utf-8")
                boxes.clear()
                assert not window._load_project_path(str(source), snapshot=True)
                assert len(boxes) == 1 and boxes[0][:2] == ("warning", "加载快照失败"), boxes
                assert fragment in boxes[0][2], boxes
                assert snapshot(window, widgets) == old
            source.write_bytes(originals[source])
            package_materials = Path(package.materials_ini_path)
            package_materials.unlink()
            boxes.clear()
            assert not window._load_project_path(str(source), snapshot=True)
            assert len(boxes) == 1 and boxes[0][:2] == ("warning", "加载快照失败"), boxes
            assert snapshot(window, widgets) == old
            package_materials.write_bytes(originals[package_materials])
            boxes.clear()
            # Exercise the real history signal connection, with no information/exec modal.
            window.run_history_page.loadSnapshotRequested.emit(str(source))
            assert not boxes, boxes
            page = window.config_builder_page
            assert window.page_stack.currentWidget() is page
            assert page.workspace_tabs.currentWidget().isAncestorOf(page.details_tabs)
            assert page.details_tabs.currentIndex() == 0
            details = page.validation_text.toPlainText()
            assert "当前的材料、几何" in details and "重新校验" in details and "历史运行成功" in details
            assert "未输出" in details and "主配置/宏文件" in details
            assert "资源内容哈希" in details and "历史运行使用的字节" in details
            assert str(Path(package.package_dir)) in details
            assert details in window.run_page.merged_view.toPlainText().replace("[gui] ", "")
            assert Path(page.materials_config.text()) == Path(package.materials_ini_path)
            assert Path(page.geometry_config.text()) == Path(package.geometry_ini_path)
            assert len(page.material_document.rows) == 1
            row = page.material_document.rows[0]
            assert row.name == "Mix" and row.density == "2.8 g/cm3"
            assert [(c.name, c.value) for c in row.components] == [("Si", "0.25"), ("O", "0.75")]
            assert [v.name for v in page.geometry_document.volumes] == ["world", "Target"]
            assert page.geometry_document.volumes[1].size.replace(" ", "") == "3mm,4mm,5mm"
            assert page.source_editor.energy == "7 MeV"
            assert page.physics_editor.reference_list == "FTFP_BERT"
            assert page.scoring_editor.hist_bins == 42
            assert window.project.threads == window.project.runSettings.threads == 2
            assert window.project.runSettings.beam_on == 23
            assert window.project.runSettings.seed == 246
            assert window.project.configPath == window.project.macroPath == window.project.outputDir == ""
            assert window._generated_package_stale and not window._generated_package_dir
            assert window.output_page._output_dir == ""
            assert not window.runner.last_result
            saved = work / "saved-restored-project.json"
            assert window._save_project_to(saved)
            saved_json = json.loads(saved.read_text(encoding="utf-8"))
            assert "runPackage" not in saved_json and "materialDocument" not in saved_json
            second = MainWindow()
            for timer in second.findChildren(QTimer):
                timer.stop()
            assert second._load_project_path(str(saved))
            assert second.config_builder_page.source_editor.energy == "7 MeV"
            assert second.config_builder_page.material_document.rows[0].density == "2.8 g/cm3"
            second.generate_package(run_after_generate=False)
            assert second._generated_package_dir
            new_root = Path(second._generated_package_dir)
            assert (new_root / "config/materials/material.ini").read_bytes() == originals[Path(package.materials_ini_path)]
            assert (new_root / "config/geometry/geometry.ini").read_bytes() == originals[Path(package.geometry_ini_path)]
            regenerated_main = (new_root / "config/main.ini").read_text(encoding="utf-8")
            assert "7 MeV" in regenerated_main and "99 MeV" not in regenerated_main
            assert "beamOn 23" in (new_root / "macros/run.mac").read_text(encoding="utf-8")
            assert all(p.read_bytes() == raw for p, raw in originals.items())
            boxes.clear()
            assert second._load_project_path(str(saved), snapshot=True)
            assert not boxes
            legacy_notes = second.config_builder_page.validation_text.toPlainText()
            assert "旧式项目快照" in legacy_notes and "尚未核验" in legacy_notes
            assert "运行包内当前的材料" not in legacy_notes
            second.close()
            second.deleteLater()
        window.close()
        window.deleteLater()
        app.processEvents()
    print("smoke_project_snapshot_restore: ok")


if __name__ == "__main__":
    main()
