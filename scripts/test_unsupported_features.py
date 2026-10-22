"""M0-3A regression tests for unsupported capabilities failing before execution."""

from __future__ import annotations

import os
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"


def run(executable: Path, args: list[str], expected: int) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    if result.returncode != expected:
        raise AssertionError(
            f"Unexpected exit code for {' '.join(args)}: expected {expected}, "
            f"got {result.returncode}\n{output}"
        )
    return output


def run_nonzero(executable: Path, args: list[str]) -> str:
    result = subprocess.run(
        [str(executable), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise AssertionError(f"Expected non-zero exit code for {' '.join(args)}\n{output}")
    return output


def main_config(
    *,
    output: Path,
    geometry_template: str,
    geometry_config: Path,
    materials_config: Path,
    extra: str = "",
    macro: Path | None = None,
    dry_run: bool = True,
) -> str:
    macro_line = f"macro = {macro}\n" if macro else ""
    return f"""[run]
name = m03a
threads = 1
seed = 12345
interactive = false
verbose = 0
check_overlaps = false
dry_run = {str(dry_run).lower()}
{macro_line}
[output]
dir = {output}

[materials]
file = {materials_config}

[geometry]
template = {geometry_template}
config = {geometry_config}
check_overlaps = false
default_world_material = G4_AIR

[physics]
reference = FTFP_BERT_EMZ
default_cut = 1 mm
biasing = false
verbose = 0

[source]
preset = proton_beam
particle = proton
energy = 10 MeV
position_type = point
position = 0,0,-1 mm
direction = 0,0,1

[scoring]
enabled = true
hits = false
event_edep = false
edep = true
let = false
dose = false
fluence = false
auto_create_default_scorers = true
verbose = 0
{extra}
"""


def assert_failure(text: str, *markers: str) -> None:
    for marker in markers:
        if marker not in text:
            raise AssertionError(f"Missing failure marker {marker!r}\n{text}")


def test_gui_validation(temp: Path) -> None:
    sys.path.insert(0, str(ROOT / "gui"))
    from g4usim_gui.editors.source_physics_scoring_model import (  # type: ignore
        ScoringEditableModel,
        validate_scoring_model,
    )
    from g4usim_gui.parsers.geometry_parser import GeometrySummary  # type: ignore
    from g4usim_gui.validators.config_validator import (  # type: ignore
        ValidationReport,
        _validate_geometry_text,
        _validate_material_text,
        _validate_template_consistency,
    )

    geometry = temp / "gui-unsupported-geometry.ini"
    geometry.write_text("[volume.target]\nplacement = assembly\n", encoding="utf-8")
    report = ValidationReport()
    _validate_geometry_text(geometry, report)
    if report.can_run or not any("placement=assembly" in item for item in report.errors):
        raise AssertionError(f"GUI geometry validation did not block unsupported placement: {report.errors}")

    report = ValidationReport()
    _validate_template_consistency("gdml", GeometrySummary(path="valid.ini"), report)
    if report.can_run or not any("GDML" in item for item in report.errors):
        raise AssertionError(f"GUI template validation did not block GDML: {report.errors}")

    comment_only = temp / "gui-gdml-comment-only.ini"
    comment_only.write_text(
        "[world]\nshape = box\n# GDML is intentionally not used\n",
        encoding="utf-8",
    )
    report = ValidationReport()
    _validate_geometry_text(comment_only, report)
    if any("GDML" in item for item in report.errors):
        raise AssertionError(f"GUI treated a GDML comment as an enabled capability: {report.errors}")

    materials = temp / "gui-unsupported-materials.ini"
    materials.write_text("[material.test]\ntemperature = 300 K\n", encoding="utf-8")
    report = ValidationReport()
    _validate_material_text(materials, report)
    if report.can_run or not any("temperature" in item for item in report.errors):
        raise AssertionError(f"GUI material validation did not block temperature: {report.errors}")

    scoring = ScoringEditableModel(dose=True, auto_create_default_scorers=False)
    validate_scoring_model(scoring)
    if not scoring.errors or not any("Dose" in item for item in scoring.errors):
        raise AssertionError("GUI scoring validation did not enforce Dose scorer prerequisites")

    scoring.auto_create_default_scorers = True
    validate_scoring_model(scoring)
    if scoring.errors:
        raise AssertionError(f"GUI scoring validation rejected supported Dose MVP: {scoring.errors}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=("all", "backend", "gui"), default="all")
    layer = parser.parse_args().layer
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if layer != "gui" and not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-m03a-") as temporary:
        temp = Path(temporary)
        if layer != "backend":
            test_gui_validation(temp)
        if layer == "gui":
            print("M0-3A GUI unsupported capability validation passed")
            return 0
        materials = ROOT / "config" / "materials" / "material.ini"
        simple_geometry = ROOT / "config" / "geometry" / "simple_box.ini"
        hierarchical_geometry = ROOT / "test" / "geometry" / "hierarchical_test.ini"

        def write_and_run(name: str, config: str) -> str:
            config_path = temp / f"main-{name}.ini"
            config_path.write_text(config, encoding="utf-8")
            return run(executable, ["--config", str(config_path)], expected=1)

        # replica / parameterised became supported in roadmap A5 (scripts/test_geometry_a5.py).
        for placement in ("assembly",):
            geometry = temp / f"{placement}.ini"
            geometry.write_text(
                hierarchical_geometry.read_text(encoding="utf-8").replace(
                    "parent = world", f"parent = world\nplacement = {placement}", 1
                ),
                encoding="utf-8",
            )
            text = write_and_run(
                placement,
                main_config(
                    output=temp / f"{placement}-output",
                    geometry_template="hierarchical",
                    geometry_config=geometry,
                    materials_config=materials,
                ),
            )
            assert_failure(text, f"placement={placement}", "placement=normal")

        gdml_geometry = temp / "gdml.ini"
        gdml_geometry.write_text("[gdml]\nfile = model.gdml\n", encoding="utf-8")
        text = write_and_run(
            "gdml",
            main_config(
                output=temp / "gdml-output",
                geometry_template="gdml",
                geometry_config=gdml_geometry,
                materials_config=materials,
            ),
        )
        assert_failure(text, "GDML", "supported geometry template")

        temperature_materials = temp / "temperature-materials.ini"
        temperature_materials.write_text(
            "[material.test]\nmode = mass_fraction\ndensity = 1 g/cm3\n"
            "components = H:1\ntemperature = 300 K\n",
            encoding="utf-8",
        )
        text = write_and_run(
            "temperature",
            main_config(
                output=temp / "temperature-output",
                geometry_template="simple_box",
                geometry_config=simple_geometry,
                materials_config=temperature_materials,
            ),
        )
        assert_failure(text, "temperature/pressure", "density, state, and composition")

        region_text = write_and_run(
            "region",
            main_config(
                output=temp / "region-output",
                geometry_template="simple_box",
                geometry_config=simple_geometry,
                materials_config=materials,
                extra="\n[physics.region.SV]\ne- = 1 mm\n",
            ),
        )
        assert_failure(region_text, "Physics region cuts", "geometry volume cut.*")

        # LET became a supported (experimental) scorer in roadmap A2; see scripts/test_let_scoring.py.

        for name, command, markers in (
            (
                "macro-placement",
                '/AIHL/geometry/addBox name=Replica parent=world material=G4_AIR size="1 mm,1 mm,1 mm" placement=replica\n',
                ("placement=replica", "placement=normal"),
            ),
            ("macro-region", "/AIHL/physics/setRegionCut SV e- 1 mm\n", ("region cuts", "geometry volume cut.*")),
            (
                "macro-material-temperature",
                '/AIHL/material/add name=MacroMaterial density="1 g/cm3" components="H:1" temperature="300 K"\n',
                ("temperature/pressure", "density, state, and composition"),
            ),
            ("macro-gdml", "/AIHL/geometry/setTemplate gdml\n", ("GDML", "supported geometry template")),
        ):
            macro = temp / f"{name}.mac"
            macro.write_text(command, encoding="utf-8")
            macro_config = temp / f"main-{name}.ini"
            macro_config.write_text(
                main_config(
                    output=temp / f"{name}-output",
                    geometry_template="simple_box",
                    geometry_config=simple_geometry,
                    materials_config=materials,
                    macro=macro,
                    dry_run=False,
                ),
                encoding="utf-8",
            )
            text = run_nonzero(executable, ["--config", str(macro_config)])
            assert_failure(text, *markers)

    print("M0-3A unsupported capability fail-fast tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
