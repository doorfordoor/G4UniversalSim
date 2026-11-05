"""H2-3 GUI entry smoke: volume filters and kinetic-energy spectra.

The editor model, the main.ini writer and the project serializer are exercised
without starting Qt. The C++ consumer is validated separately by the backend
regression in ``scripts/test_h2_volume_scoring.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.core.project import G4USimProject, load_project, project_to_dict, save_project
from g4usim_gui.core.run_editor_import import parse_run_editor_ini
from g4usim_gui.editors.source_physics_scoring_model import (
    SPECTRUM_SCORERS,
    ScoringEditableModel,
    validate_scoring_model,
)
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


def _ini(model: ScoringEditableModel) -> str:
    return build_main_ini_text(
        package=_package(),
        run=RunSettings(run_name="h2_volume", threads=1),
        geometry=GeometrySettings(template="simple_box", config_path="<package>/config/geometry/geometry.ini"),
        source=SourceSettings(),
        physics=PhysicsSettings(),
        scoring=ScoringSettings(),
        scoring_model=model,
    )


def _config(**kwargs) -> ScoringEditableModel:
    model = ScoringEditableModel(**kwargs)
    validate_scoring_model(model)
    assert not model.errors, model.errors
    return model


def test_default_writes_no_volume_sections() -> None:
    text = _ini(_config())
    assert "[scoring.filter." not in text
    assert "[scoring.spectrum." not in text


def test_filter_sections_written() -> None:
    model = _config(dose=True, auto_create_default_scorers=True)
    model.volume_filters["dose"] = {
        "enabled": True,
        "particles": "e-,gamma",
        "energy_min": "1 MeV",
        "energy_max": "10 MeV",
    }
    validate_scoring_model(model)
    assert not model.errors, model.errors
    text = _ini(model)
    assert "[scoring.filter.dose]" in text
    assert "particles = e-,gamma" in text
    assert "energy_min = 1 MeV" in text
    assert "energy_max = 10 MeV" in text
    dump = model.volume_filters["dose"]
    assert dump == {"enabled": True, "particles": "e-,gamma",
                    "energy_min": "1 MeV", "energy_max": "10 MeV"}


def test_spectrum_sections_written() -> None:
    model = _config(fluence=True, auto_create_default_scorers=True)
    model.volume_spectra["fluence"] = {
        "enabled": True,
        "bins": 10,
        "min": "0.5 MeV",
        "max": "1.5 MeV",
    }
    validate_scoring_model(model)
    assert not model.errors, model.errors
    text = _ini(model)
    assert "[scoring.spectrum.fluence]" in text
    assert "bins = 10" in text
    assert "min = 0.5 MeV" in text
    assert "max = 1.5 MeV" in text


def test_filter_requires_enabled_scorer() -> None:
    model = ScoringEditableModel(dose=False)
    model.volume_filters["dose"] = {
        "enabled": True, "particles": "all", "energy_min": "", "energy_max": "",
    }
    validate_scoring_model(model)
    assert any(error.startswith("volume_filters.dose.enabled: dose filter requires")
               for error in model.errors) or any(
        "dose filter requires [scoring] dose = true" in error for error in model.errors), model.errors


def test_particles_all_must_be_alone() -> None:
    model = _config(fluence=True, auto_create_default_scorers=True)
    model.volume_filters["fluence"] = {
        "enabled": True, "particles": "all,gamma", "energy_min": "", "energy_max": "",
    }
    validate_scoring_model(model)
    assert any("all cannot be combined" in error for error in model.errors), model.errors


def test_energy_window_must_be_ordered() -> None:
    model = _config(dose=True, auto_create_default_scorers=True)
    model.volume_filters["dose"] = {
        "enabled": True, "particles": "all", "energy_min": "10 MeV", "energy_max": "1 MeV",
    }
    validate_scoring_model(model)
    assert any("energy_max must be greater" in error for error in model.errors), model.errors


def test_spectrum_bins_and_window_validated() -> None:
    model = _config(fluence=True, auto_create_default_scorers=True)
    model.volume_spectra["fluence"] = {
        "enabled": True, "bins": 0, "min": "2 MeV", "max": "1 MeV",
    }
    validate_scoring_model(model)
    assert any("spectrum bins must be an integer in 1..1000000" in error for error in model.errors), model.errors
    assert any("spectrum max must be greater" in error for error in model.errors), model.errors


def test_spectrum_bins_integer_and_limits() -> None:
    for bins in (1, 1_000_000, "1000"):
        model = _config(fluence=True, auto_create_default_scorers=True)
        model.volume_spectra["fluence"] = {
            "enabled": True, "bins": bins, "min": "0 MeV", "max": "1 MeV",
        }
        validate_scoring_model(model)
        assert not model.errors, (bins, model.errors)
        text = _ini(model)
        assert f"bins = {int(bins)}" in text, (bins, text)
    for bins in (0, 1_000_001, 2.5, True, "2.5"):
        model = _config(fluence=True, auto_create_default_scorers=True)
        model.volume_spectra["fluence"] = {
            "enabled": True, "bins": bins, "min": "0 MeV", "max": "1 MeV",
        }
        validate_scoring_model(model)
        assert any("spectrum bins must be an integer in 1..1000000" in error
                   for error in model.errors), (bins, model.errors)
        try:
            _ini(model)
        except ValueError:
            pass
        else:
            raise AssertionError(f"writer accepted invalid spectrum bins {bins!r}")


def test_writer_refuses_invalid_model() -> None:
    model = ScoringEditableModel(dose=True)
    model.volume_filters["dose"] = {"enabled": True, "particles": "", "energy_min": "", "energy_max": ""}
    try:
        _ini(model)
    except ValueError as exc:
        assert "filter particles must be" in str(exc), exc
    else:
        raise AssertionError("writer accepted a model with filter validation errors")


def test_project_round_trip_keeps_volume_config() -> None:
    project = G4USimProject(projectName="h2_roundtrip")
    project.scoringEditor = _config(dose=True, fluence=True, auto_create_default_scorers=True)
    project.scoringEditor.volume_filters["dose"] = {
        "enabled": True, "particles": "proton", "energy_min": "2 MeV", "energy_max": "20 MeV",
    }
    project.scoringEditor.volume_spectra["fluence"] = {
        "enabled": True, "bins": 12, "min": "0.1 MeV", "max": "5 MeV",
    }
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "project.json"
        save_project(project, path)
        loaded = load_project(path)
    assert loaded.scoringEditor.volume_filters["dose"]["particles"] == "proton"
    assert loaded.scoringEditor.volume_spectra["fluence"]["bins"] == 12
    assert loaded.scoringEditor.volume_spectra["fluence"]["max"] == "5 MeV"
    data = project_to_dict(loaded)["scoringEditor"]
    assert SPECTRUM_SCORERS == ("dose", "fluence")
    assert "volume_filters" in data and "volume_spectra" in data


def test_import_accepts_written_ini() -> None:
    model = _config(dose=True, fluence=True, auto_create_default_scorers=True)
    model.volume_filters["dose"] = {
        "enabled": True, "particles": "all", "energy_min": "1 MeV", "energy_max": "",
    }
    model.volume_spectra["fluence"] = {
        "enabled": True, "bins": 10, "min": "0.5 MeV", "max": "1.5 MeV",
    }
    validate_scoring_model(model)
    assert not model.errors, model.errors
    text = _ini(model)
    imported = parse_run_editor_ini(text, source_path="<written>/main.ini")
    assert imported.source is not None and imported.physics is not None
    # This importer only accepts the new sections and returns source/physics.
    # It does not rebuild a ScoringEditableModel: INI scoring import is out of
    # scope here (project JSON save/load is the tested restoration path).
    assert not hasattr(imported, "scoring")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok: {test.__name__}")
    print(f"PASS: H2-3 volume filter/spectrum GUI entry ({len(tests)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
