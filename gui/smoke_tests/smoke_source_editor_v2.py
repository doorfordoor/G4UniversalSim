from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel, PhysicsEditableModel, validate_source_model, validate_physics_model
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
    source = SourceEditableModel(position_mode="plane", source_shape="circle", radius="2 mm",
                                 position="4 mm, 0 mm, -9 mm", angular_mode="fixed")
    validate_source_model(source)
    assert not source.errors, source.errors
    assert any("plane circle source" in item for item in source.warnings)
    text = _ini(source)
    assert "position_type = plane" in text
    assert "center = 4 mm, 0 mm, -9 mm" in text
    assert "position = 4 mm, 0 mm, -9 mm" not in text
    assert "radius = 2 mm" in text


def test_point_isotropic() -> None:
    source = SourceEditableModel(position_mode="point", source_shape="point", angular_mode="isotropic")
    validate_source_model(source)
    assert not source.errors, source.errors
    text = _ini(source)
    assert "isotropic = true" in text
    assert "direction = " not in text

    plane = SourceEditableModel(position_mode="plane", source_shape="circle", radius="2 mm",
                                angular_mode="isotropic")
    plane_text = _ini(plane)
    assert "isotropic = true" in plane_text
    assert "direction = " not in plane_text
    assert "center = " in plane_text


def test_source_nonfinite_is_blocked() -> None:
    for field, value in (("direction", "NaN,0,1"), ("energy", "inf MeV"),
                         ("energy", "1e999 MeV"), ("position", "inf,0,-1 mm"),
                         ("radius", "NaN mm")):
        source = SourceEditableModel(position_mode="plane", source_shape="circle")
        setattr(source, field, value)
        validate_source_model(source)
        assert any(f"{field} must contain only finite" in msg for msg in source.errors), (field, source.errors)


def test_rectangle_source_and_preview_only_modes() -> None:
    rectangle = SourceEditableModel(
        position_mode="plane",
        source_shape="rectangle",
        halfx="1 mm",
        halfy="2 mm",
        position="1 mm, -2 mm, 0 mm",
        angular_mode="fixed",
    )
    validate_source_model(rectangle)
    assert not rectangle.errors, rectangle.errors
    text = _ini(rectangle)
    assert "shape = rectangle" in text
    assert "halfx = 1 mm" in text
    assert "halfy = 2 mm" in text
    assert "center = 1 mm, -2 mm, 0 mm" in text
    assert "radius = " not in text

    rectangle.angular_mode = "isotropic"
    validate_source_model(rectangle)
    assert not rectangle.errors, rectangle.errors
    assert "isotropic = true" in _ini(rectangle)
    assert "direction = " not in _ini(rectangle)

    for shape in ("square", "annulus"):
        source = SourceEditableModel(position_mode="plane", source_shape=shape)
        validate_source_model(source)
        assert any("preview-only" in error for error in source.errors), (shape, source.errors)

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
    for field, value in (("halfx", "0 mm"), ("halfy", "-2 mm"),
                         ("halfx", "1 MeV"), ("halfy", "oops"),
                         ("halfx", "NaN mm"), ("halfy", "Inf mm"),
                         ("halfx", "1e999 mm")):
        rectangle = SourceEditableModel(position_mode="plane", source_shape="rectangle",
                                         halfx="1 mm", halfy="2 mm")
        setattr(rectangle, field, value)
        validate_source_model(rectangle)
        assert rectangle.errors, (field, value)
    rectangle = SourceEditableModel(position_mode="plane", source_shape="rectangle",
                                    halfx="1 mm", halfy="2 mm", normal="0,1,0")
    validate_source_model(rectangle)
    assert any("XY plane" in error for error in rectangle.errors)

    bad_angle = SourceEditableModel(theta_min="not_an_angle")
    validate_source_model(bad_angle)
    assert any("theta_min" in item for item in bad_angle.errors)


def test_generated_biasing_hook_is_blocked() -> None:
    physics = PhysicsEditableModel(enable_biasing_physics=True)
    validate_physics_model(physics)
    assert any("Biasing rules cannot be edited" in item for item in physics.errors), physics.errors


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
    test_source_nonfinite_is_blocked()
    test_rectangle_source_and_preview_only_modes()
    test_validation_errors()
    test_generated_biasing_hook_is_blocked()
    test_project_save_load()
    print("smoke_source_editor_v2: OK")
