from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.editors.material_editor_model import MaterialDocument, MaterialRow
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
    validate_physics_model,
    validate_scoring_model,
    validate_source_model,
)
from g4usim_gui.models.package_model import GeometrySettings, PathSettings, RunPackage
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.writers.main_ini_writer import build_main_ini_text
from g4usim_gui.writers.package_writer import create_run_package


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    source = SourceEditableModel()
    physics = PhysicsEditableModel()
    scoring = ScoringEditableModel()
    validate_source_model(source)
    validate_physics_model(physics)
    validate_scoring_model(scoring)
    assert not source.errors
    assert not physics.errors
    assert not scoring.errors

    bad_source = SourceEditableModel(direction="0,0,0")
    validate_source_model(bad_source)
    assert any("direction cannot be all zero" in item for item in bad_source.errors)

    bad_physics = PhysicsEditableModel(reference_list="")
    validate_physics_model(bad_physics)
    assert any("reference list is required" in item for item in bad_physics.errors)

    bad_scoring = ScoringEditableModel(enabled=True, hits=False, event_edep=False, edep=False, hist_bins=0)
    validate_scoring_model(bad_scoring)
    assert any("at least one" in item for item in bad_scoring.errors)
    assert any("bins" in item for item in bad_scoring.errors)

    package = RunPackage(
        package_dir="<package>",
        config_dir="<package>/config",
        macro_dir="<package>/macros",
        logs_dir="<package>/logs",
        output_dir="<package>/output",
        main_ini_path="<package>/config/main.ini",
        run_macro_path="<package>/macros/run.mac",
        validation_report_path="<package>/validation_report.txt",
        project_snapshot_path="<package>/project_snapshot.json",
        materials_ini_path="<package>/config/materials/material.ini",
        geometry_ini_path="<package>/config/geometry/geometry.ini",
    )
    text = build_main_ini_text(
        package=package,
        run=RunSettings(run_name="smoke", threads=1),
        geometry=GeometrySettings(template="simple_box", config_path="<package>/config/geometry/geometry.ini"),
        source=source.to_settings(),
        physics=physics.to_settings(),
        scoring=scoring.to_settings(),
        source_model=source,
        physics_model=physics,
        scoring_model=scoring,
    )
    assert "[source]" in text
    assert "position_type = point" in text
    assert "[physics]" in text
    assert "mode = reference" not in text  # not consumed by the backend
    assert "[physics]" in text and "reference = " in text
    assert "[scoring.edep]" in text
    assert "let = false" in text
    assert "dose = false" in text
    assert "fluence = false" in text
    scoring.dose = True
    validate_scoring_model(scoring)
    assert not scoring.errors, scoring.errors
    dose_text = build_main_ini_text(
        package=package, run=RunSettings(run_name="dose", threads=2),
        geometry=GeometrySettings(template="simple_box", config_path=package.geometry_ini_path),
        source=source.to_settings(), physics=physics.to_settings(), scoring=scoring.to_settings(),
        source_model=source, physics_model=physics, scoring_model=scoring,
    )
    assert "dose = true" in dose_text
    assert scoring.to_settings().dose
    scoring.auto_create_default_scorers = False
    validate_scoring_model(scoring)
    assert any("auto-create" in message for message in scoring.errors)
    scoring.auto_create_default_scorers = True
    validate_scoring_model(scoring)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        exe = tmp_path / "G4UniversalSim.exe"
        exe.write_text("fake", encoding="utf-8")
        material_doc = MaterialDocument(rows=[
            MaterialRow(name="CustomA", mode="mass_fraction", density="1.0 g/cm3", components_text="G4_Si:1.0")
        ])
        material_doc.is_dirty = True
        source.particle = "neutron"
        source.energy = "14 MeV"
        source.is_dirty = True
        physics.reference_list = "Shielding"
        physics.is_dirty = True
        scoring.hist_bins = 321
        scoring.is_dirty = True
        package_out, report = create_run_package(
            project=G4USimProject(projectName="smoke"),
            paths=PathSettings(
                executable=str(exe),
                workspace_root=str(root),
                runs_root=str(tmp_path / "runs"),
                materials_config=str(root / "config" / "materials" / "material.ini"),
                geometry_config=str(root / "config" / "geometry" / "simple_box.ini"),
            ),
            run=RunSettings(run_name="smoke", threads=1, beam_on=0),
            geometry=GeometrySettings(template="simple_box", config_path=str(root / "config" / "geometry" / "simple_box.ini")),
            source=source.to_settings(),
            physics=physics.to_settings(),
            scoring=scoring.to_settings(),
            material_document=material_doc,
            source_model=source,
            physics_model=physics,
            scoring_model=scoring,
        )
        generated_main = Path(package_out.main_ini_path).read_text(encoding="utf-8")
        assert "particle = neutron" in generated_main
        assert "reference = Shielding" in generated_main
        assert "bins = 321" in generated_main
        assert "Source summary:" in report
        snapshot = json.loads(Path(package_out.project_snapshot_path).read_text(encoding="utf-8"))
        assert snapshot["sourceEditor"]["particle"] == "neutron"
        assert snapshot["physicsEditor"]["reference_list"] == "Shielding"
        assert snapshot["scoringEditor"]["hist_bins"] == 321

        project_path = tmp_path / "project.json"
        project = G4USimProject(projectName="p", sourceEditor=source, physicsEditor=physics, scoringEditor=scoring)
        save_project(project, project_path)
        loaded = load_project(project_path)
        assert loaded.sourceEditor.particle == "neutron"
        assert loaded.physicsEditor.reference_list == "Shielding"
        assert loaded.scoringEditor.hist_bins == 321
        assert loaded.scoringEditor.dose
        assert loaded.scoringSettings.dose is False  # separate legacy settings remain compatible

        old_path = tmp_path / "old_project.json"
        old_path.write_text(
            json.dumps({
                "schema": "G4UniversalSimProject",
                "version": 1,
                "sourceSettings": {"particle": "gamma", "energy": "1 MeV", "position": "0,0,0 mm", "direction": "0,0,1", "preset": "gamma_beam"},
            }),
            encoding="utf-8",
        )
        old_loaded = load_project(old_path)
        assert old_loaded.sourceEditor.particle == "gamma"
        assert old_loaded.scoringEditor.dose is False

    print("smoke_run_config_editors: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
