"""M0-3B2B2 structured geometry diagnostics and legacy metadata tests."""

from __future__ import annotations

import os
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
sys.path.insert(0, str(ROOT / "gui"))


def main_ini(template: str, geometry: Path, output: Path, extra: str = "") -> str:
    return f"""[run]
threads = 1
dry_run = true
interactive = false
verbose = 0

[output]
dir = {output}

[materials]
file = {ROOT / 'config' / 'materials' / 'material.ini'}

[geometry]
template = {template}
config = {geometry}

[physics]
reference = FTFP_BERT_EMZ
default_cut = 1 mm

[source]
preset = proton_beam
particle = proton
energy = 10 MeV
position_type = point
position = 0,0,-1 mm
direction = 0,0,1

[scoring]
enabled = false
{extra}
"""


def run_case(exe: Path, template: str, text: str, temp: Path, label: str, extra: str = "") -> tuple[str, str]:
    geometry = temp / f"{label}.geometry.ini"
    config = temp / f"{label}.main.ini"
    output = temp / f"{label}.output"
    geometry.write_text(text, encoding="utf-8")
    config.write_text(main_ini(template, geometry, output, extra), encoding="utf-8")
    completed = subprocess.run([str(exe), "--config", str(config)], cwd=ROOT, text=True, capture_output=True, timeout=90)
    combined = completed.stdout + completed.stderr
    summary_path = output / "run_summary.txt"
    summary = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    return combined, summary


SIMPLE = """[world]
size = 10 cm, 10 cm, 10 cm
material = G4_AIR
[target]
shape = box
size = 1 mm, 1 mm, 1 mm
material = G4_Si
region = R
"""

LAYERED = """[world]
size = 10 cm, 10 cm, 10 cm
material = G4_AIR
[layers]
count = 1
names = L
[layer.L]
thickness = 1 mm
xy = 2 mm, 2 mm
material = G4_Si
region = R
"""

ARRAY = """[world]
size = 10 cm, 10 cm, 10 cm
material = G4_AIR
[array]
shape = box
material = G4_Si
element_size = 1 mm, 1 mm, 1 mm
counts = 1, 1, 1
pitch = 1 mm, 1 mm, 1 mm
"""

SHIELDING = """[world]
size = 1 m, 1 m, 1 m
material = G4_AIR
[shielding]
area = 10 cm, 10 cm
start = -10 cm
layers = Lead
[shield.Lead]
thickness = 1 cm
material = G4_Pb
"""

HIERARCHICAL = """[world]
shape = box
size = 10 cm, 10 cm, 10 cm
material = G4_AIR
[volume.Target]
parent = world
shape = box
size = 1 cm, 1 cm, 1 cm
material = G4_Si
region = R
"""


def assert_clean(output: str, summary: str, label: str) -> None:
    assert "[GeometryConfigWarning]" not in output, (label, output)
    assert "geometry_config_warning_count = 0" in summary, (label, summary)


def backend_contract(exe: Path, temp: Path) -> None:
    for template, text, label in (("simple_box", SIMPLE, "simple"), ("layered_device", LAYERED, "layered"),
                                  ("array", ARRAY, "array"), ("shielding", SHIELDING, "shielding"),
                                  ("hierarchical", HIERARCHICAL, "hierarchical")):
        assert_clean(*run_case(exe, template, text, temp, f"valid-{label}"), label)
        strict = "[global]\nversion = 2\n" + text
        strict_output, strict_summary = run_case(exe, template, strict, temp, f"strict-valid-{label}")
        assert "created_geometry_object_count=0" not in strict_output, (label, strict_output)
        assert "geometry_config_warning_count = 0" in strict_summary, (label, strict_output, strict_summary)

    strict_unknown = "[global]\nversion = 2\n" + SIMPLE + "\n[mystery]\nvalue = 1\n"
    output, _ = run_case(exe, "simple_box", strict_unknown, temp, "strict-unknown-section")
    assert "version=2 schema rejected unknown_section" in output and "created_geometry_object_count=0" in output
    strict_empty_section = "[global]\nversion = 2\n" + SIMPLE + "\n[mystery]\n"
    output, _ = run_case(exe, "simple_box", strict_empty_section, temp, "strict-empty-unknown-section")
    assert "version=2 schema rejected unknown_section" in output and "created_geometry_object_count=0" in output
    strict_key = "[global]\nversion = 2\n" + SIMPLE.replace("region = R", "region = R\nextra = 1")
    output, _ = run_case(exe, "simple_box", strict_key, temp, "strict-unknown-key")
    assert "version=2 schema rejected unconsumed_key" in output and "created_geometry_object_count=0" in output
    strict_legacy = "[global]\nversion = 2\n" + HIERARCHICAL.replace("region = R", "region = R\nLegacyTag = retained")
    output, _ = run_case(exe, "hierarchical", strict_legacy, temp, "strict-legacy")
    assert "version=2 schema rejected legacy_metadata" in output and "created_geometry_object_count=0" in output
    strict_canonical = "[global]\nversion = 2\n" + HIERARCHICAL.replace("region = R", "region = R\nmetadata.owner = QA")
    assert_clean(*run_case(exe, "hierarchical", strict_canonical, temp, "strict-canonical"), "strict-canonical")
    strict_vis = "[global]\nversion = 2\n" + HIERARCHICAL.replace("region = R", "region = R\nvis.palette = rainbow")
    output, _ = run_case(exe, "hierarchical", strict_vis, temp, "strict-unknown-vis")
    assert "version=2 schema rejected unconsumed_key" in output and "created_geometry_object_count=0" in output
    strict_boolean = "[global]\nversion = 2\n" + HIERARCHICAL + "\n[volume.Target.boolean.0]\noperation = subtraction\nshape = box\nsize = 1 mm,1 mm,1 mm\nmaterial = G4_Si\n"
    output, _ = run_case(exe, "hierarchical", strict_boolean, temp, "strict-boolean")
    assert "version=2 schema rejected ignored_boolean_key" in output and "created_geometry_object_count=0" in output
    invalid_version = "[global]\nversion = 3\n" + SIMPLE
    output, _ = run_case(exe, "simple_box", invalid_version, temp, "unsupported-version")
    assert "supported geometry versions are 1 (legacy) and 2 (strict)" in output
    legacy_explicit = "[global]\nversion = 1\n" + HIERARCHICAL.replace("region = R", "region = R\nLegacyTag = retained")
    output, summary = run_case(exe, "hierarchical", legacy_explicit, temp, "explicit-legacy-version")
    assert "legacy unprefixed metadata" in output and "geometry_config_warning_count = 1" in summary
    duplicated_version = "[global]\nversion = 2\nversion = 2\n" + SIMPLE
    output, _ = run_case(exe, "simple_box", duplicated_version, temp, "duplicate-version")
    assert "duplicate geometry version declaration" in output and "created_geometry_object_count=0" in output, output
    repeated_section = "[global]\nversion = 2\n" + SIMPLE + "\n[WORLD]\nmaterial = G4_AIR\n"
    output, _ = run_case(exe, "simple_box", repeated_section, temp, "strict-duplicate-section")
    assert "version=2 schema rejected duplicate_section" in output and "created_geometry_object_count=0" in output, output
    repeated_key = "[global]\nversion = 2\n" + SIMPLE.replace("material = G4_AIR", "material = G4_AIR\nMaterial = G4_AIR", 1)
    output, _ = run_case(exe, "simple_box", repeated_key, temp, "strict-duplicate-key")
    assert "version=2 schema rejected duplicate_key" in output and "created_geometry_object_count=0" in output, output
    legacy_repeated_key = "[global]\nversion = 1\n" + SIMPLE.replace("material = G4_AIR", "material = G4_AIR\nMaterial = G4_AIR", 1)
    _, legacy_summary = run_case(exe, "simple_box", legacy_repeated_key, temp, "legacy-duplicate-key")
    assert "status = completed" in legacy_summary, legacy_summary

    layered_copy_no = LAYERED.replace("region = R", "region = R\ncopyNo = 7")
    assert_clean(*run_case(exe, "layered_device", layered_copy_no, temp, "layered-copy-no"), "layered-copy-no")

    output, summary = run_case(exe, "simple_box", SIMPLE + "\n[WORLD]\nImPlicit = 1\n", temp, "implicit")
    assert "not consumed" in output and "[WORLD]/ImPlicit" in output and "geometry_config_warning_count = 1" in summary
    output, summary = run_case(exe, "simple_box", SIMPLE + "\n[mystery]\nvalue = 1\n", temp, "unknown-section")
    assert "[mystery]" in output and "not recognized" in output and "geometry_config_warning_count = 1" in summary
    output, _ = run_case(exe, "layered_device", LAYERED + "\n[layer.NotListed]\nthickness = 1 mm\n", temp, "layer-not-listed")
    assert "[layer.NotListed]" in output and "not recognized" in output
    output, _ = run_case(exe, "shielding", SHIELDING + "\n[shield.NotListed]\nthickness = 1 mm\n", temp, "shield-not-listed")
    assert "[shield.NotListed]" in output and "not recognized" in output
    output, _ = run_case(exe, "hierarchical", HIERARCHICAL + "\n[mystery]\nfoo = bar\n", temp, "hier-unknown")
    assert "[mystery]" in output and "not recognized" in output

    canonical = HIERARCHICAL.replace("region = R", "region = R\nmetadata.owner = QA")
    assert_clean(*run_case(exe, "hierarchical", canonical, temp, "canonical-metadata"), "canonical")
    legacy = HIERARCHICAL.replace("region = R", "region = R\nLegacyTag = retained")
    output, summary = run_case(exe, "hierarchical", legacy, temp, "legacy-metadata")
    assert "legacy unprefixed metadata" in output and "metadata.LegacyTag" in output and "geometry_config_warning_count = 1" in summary

    boolean = HIERARCHICAL + """
[volume.Target.boolean.0]
operation = subtraction
shape = box
size = 1 mm, 1 mm, 1 mm
Material = G4_Si
"""
    output, summary = run_case(exe, "hierarchical", boolean, temp, "boolean-forbidden")
    assert "boolean tool ignores volume-only field" in output and "[volume.Target.boolean.0]/Material = G4_Si" in output
    assert "geometry_config_warning_count = 1" in summary

    _, summary = run_case(exe, "simple_box", SIMPLE, temp, "main-typo", "[run]\nthreds = 3\n")
    assert "config_warning_count = 1" in summary and "geometry_config_warning_count = 0" in summary
    malformed = HIERARCHICAL + "\n[volume.Target.boolean.bad]\noperation = subtraction\nshape = box\nsize = 1 mm,1 mm,1 mm\n"
    output, summary = run_case(exe, "hierarchical", malformed, temp, "malformed-boolean")
    assert "[volume.Target.boolean.bad]" in output and "not recognized" in output and "geometry_config_warning_count = 1" in summary
    empty = HIERARCHICAL.replace("region = R", "region = R\nmetadata. = bad")
    output, _ = run_case(exe, "hierarchical", empty, temp, "empty-metadata")
    assert "metadata namespace requires a non-empty name" in output
    fail_fast = SIMPLE.replace("region = R", "region = R\ncut.typo = 1 mm")
    output, _ = run_case(exe, "simple_box", fail_fast, temp, "b2b1-fail-fast")
    assert "unknown production cut key" in output and "created_geometry_object_count=0" in output


def gui_contract(temp: Path) -> None:
    from g4usim_gui.editors.geometry_editor_model import (
        geometry_document_from_dict, geometry_document_from_summary,
        geometry_document_to_snapshot, validate_geometry_document,
    )
    from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
    from g4usim_gui.models.package_model import GeometrySettings, PathSettings
    from g4usim_gui.parsers.geometry_parser import parse_geometry
    from g4usim_gui.preview3d.scene_builder import build_preview_scene
    from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
    from g4usim_gui.writers.package_writer import _copy_or_generate_inputs

    explicit = temp / "explicit.ini"
    explicit.write_text("[world]\nsize=1 cm,1 cm,1 cm\nmaterial=G4_AIR\n", encoding="utf-8")
    assert parse_geometry(explicit, "array").template_hint == "array"

    strict_source = temp / "strict-source.ini"
    strict_source.write_text("[global]\nversion = 2\n" + HIERARCHICAL, encoding="utf-8")
    strict_summary = parse_geometry(strict_source, "hierarchical")
    assert strict_summary.schema_version == 2 and not strict_summary.round_trip_blockers
    strict_document = geometry_document_from_summary(strict_summary, "hierarchical")
    strict_reloaded = geometry_document_from_dict(geometry_document_to_snapshot(strict_document))
    assert strict_reloaded.schema_version == 2
    try:
        geometry_document_from_dict({"schema_version": 3})
    except ValueError as error:
        assert "Unsupported geometry schema version" in str(error)
    else:
        raise AssertionError("Unsupported project geometry schema version was silently dropped")
    strict_generated = temp / "strict-generated.ini"
    strict_generated.write_text(generate_geometry_ini_text(strict_reloaded), encoding="utf-8")
    strict_reparsed = parse_geometry(strict_generated, "hierarchical")
    assert strict_reparsed.schema_version == 2 and not strict_reparsed.round_trip_blockers
    strict_reloaded.is_dirty = True
    strict_package = type("Package", (), {"materials_ini_path": str(temp / "strict-material.ini"), "geometry_ini_path": str(temp / "strict-package.ini")})()
    strict_paths = PathSettings(materials_config=str(ROOT / "config" / "materials" / "material.ini"), geometry_config=str(strict_source))
    strict_modes = _copy_or_generate_inputs(
        strict_package, strict_paths, GeometrySettings(template="hierarchical", config_path=str(strict_source)),
        None, strict_reloaded,
    )
    assert "generated" in strict_modes[1]
    assert parse_geometry(strict_package.geometry_ini_path, "hierarchical").schema_version == 2

    duplicate_version = temp / "duplicate-version.ini"
    duplicate_version.write_text("[global]\nversion = 2\nversion = 2\n" + HIERARCHICAL, encoding="utf-8")
    assert any("duplicate [global]/version" in item for item in parse_geometry(duplicate_version, "hierarchical").errors)
    unsupported_version = temp / "unsupported-version-gui.ini"
    unsupported_version.write_text("[global]\nversion = 3\n" + HIERARCHICAL, encoding="utf-8")
    assert any("supported geometry versions" in item for item in parse_geometry(unsupported_version, "hierarchical").errors)
    legacy_version = temp / "legacy-version-gui.ini"
    legacy_version.write_text("[global]\nversion = 1\n" + HIERARCHICAL, encoding="utf-8")
    legacy_document = geometry_document_from_summary(parse_geometry(legacy_version, "hierarchical"), "hierarchical")
    assert "[global]\nversion = 1" in generate_geometry_ini_text(legacy_document)

    legacy = temp / "legacy.ini"
    legacy.write_text(HIERARCHICAL.replace("region = R", "region = R\nLegacyTag = retained"), encoding="utf-8")
    document = geometry_document_from_summary(parse_geometry(legacy, "hierarchical"), "hierarchical")
    source_warnings = list(document.source_warnings)
    validate_geometry_document(document)
    validate_geometry_document(document)
    assert source_warnings == document.source_warnings and document.round_trip_blockers
    assert any("LegacyTag" in item for item in document.round_trip_blockers)
    assert any("Round-trip blocker:" in item for item in build_preview_scene(document, SourceEditableModel()).warnings)

    document.source_copy_mode = True
    package = type("Package", (), {"materials_ini_path": str(temp / "material.ini"), "geometry_ini_path": str(temp / "copy.ini")})()
    paths = PathSettings(materials_config=str(ROOT / "config" / "materials" / "material.ini"), geometry_config=str(legacy))
    modes = _copy_or_generate_inputs(package, paths, GeometrySettings(template="hierarchical", config_path=str(legacy)), None, document)
    assert "validation bypassed" in modes[1] and Path(package.geometry_ini_path).read_bytes() == legacy.read_bytes()
    document.source_copy_mode = False
    document.is_dirty = True
    try:
        generate_geometry_ini_text(document)
    except ValueError as error:
        assert "round-trip" in str(error).lower()
    else:
        raise AssertionError("legacy metadata was silently rewritten by the GUI writer")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=("all", "backend", "gui"), default="all")
    layer = parser.parse_args().layer
    exe = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if layer != "gui" and not exe.is_file():
        raise FileNotFoundError(f"G4UniversalSim executable not found: {exe}")
    with tempfile.TemporaryDirectory(prefix="g4usim-geometry-diagnostics-") as raw:
        temp = Path(raw)
        if layer != "gui":
            backend_contract(exe, temp)
        if layer != "backend":
            gui_contract(temp)
    print("test_geometry_config_diagnostics: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
