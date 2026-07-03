from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel, validate_source_model
from g4usim_gui.models.package_model import GeometrySettings, RunPackage
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.writers.main_ini_writer import build_main_ini_text


def _package() -> RunPackage:
    return RunPackage(
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


def _ini(source: SourceEditableModel) -> str:
    return build_main_ini_text(
        package=_package(),
        run=RunSettings(run_name="source_v2", threads=1),
        geometry=GeometrySettings(template="simple_box", config_path="<package>/config/geometry/geometry.ini"),
        source=SourceSettings(),
        physics=PhysicsSettings(),
        scoring=ScoringSettings(),
        source_model=source,
    )


def test_point_fixed() -> None:
    source = SourceEditableModel(position_mode="point", source_shape="point", angular_mode="fixed")
    validate_source_model(source)
    assert not source.errors, source.errors
    text = _ini(source)
    assert "position_type = point" in text
    assert "isotropic = true" not in text


def test_plane_circle_fixed() -> None:
    source = SourceEditableModel(position_mode="plane", source_shape="circle", radius="2 mm", angular_mode="fixed")
    validate_source_model(source)
    assert not source.errors, source.errors
    assert any("plane circle source" in item for item in source.warnings)
    text = _ini(source)
    assert "position_type = plane" in text
    assert "radius = 2 mm" in text


def test_point_isotropic() -> None:
    source = SourceEditableModel(position_mode="point", source_shape="point", angular_mode="isotropic")
    validate_source_model(source)
    assert not source.errors, source.errors
    assert "isotropic = true" in _ini(source)


def test_preview_only_modes_are_blocked() -> None:
    rectangle = SourceEditableModel(
        position_mode="plane",
        source_shape="rectangle",
        halfx="1 mm",
        halfy="2 mm",
        angular_mode="fixed",
    )
    validate_source_model(rectangle)
    assert any("preview-only" in item for item in rectangle.errors)

    cone = SourceEditableModel(position_mode="point", source_shape="point", angular_mode="cone", cone_half_angle="5 deg")
    validate_source_model(cone)
    assert any("cone angular mode is preview-only" in item for item in cone.errors)


def test_validation_errors() -> None:
    source = SourceEditableModel(direction="0,0,0")
    validate_source_model(source)
    assert any("direction cannot be all zero" in item for item in source.errors)

    circle = SourceEditableModel(position_mode="plane", source_shape="circle", radius="")
    validate_source_model(circle)
    assert any("requires radius" in item for item in circle.errors)

    rectangle = SourceEditableModel(position_mode="plane", source_shape="rectangle", halfx="", halfy="")
    validate_source_model(rectangle)
    assert any("requires halfx" in item for item in rectangle.errors)
    assert any("requires halfy" in item for item in rectangle.errors)

    bad_angle = SourceEditableModel(theta_min="not_an_angle")
    validate_source_model(bad_angle)
    assert any("theta_min" in item for item in bad_angle.errors)


def test_project_save_load(tmp_path: Path | None = None) -> None:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="g4usim_source_v2_")) if tmp_path is None else tmp_path
    project_path = tmp / "project.json"
    source = SourceEditableModel(position_mode="plane", source_shape="circle", radius="3 mm", angular_mode="isotropic")
    project = G4USimProject(projectName="source_v2", sourceEditor=source)
    save_project(project, project_path)
    loaded = load_project(project_path)
    assert loaded.sourceEditor.position_mode == "plane"
    assert loaded.sourceEditor.source_shape == "circle"
    assert loaded.sourceEditor.radius == "3 mm"
    assert loaded.sourceEditor.angular_mode == "isotropic"


if __name__ == "__main__":
    test_point_fixed()
    test_plane_circle_fixed()
    test_point_isotropic()
    test_preview_only_modes_are_blocked()
    test_validation_errors()
    test_project_save_load()
    print("smoke_source_editor_v2: OK")
