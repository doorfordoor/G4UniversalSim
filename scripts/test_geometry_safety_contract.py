"""M0-3B2B1 geometry safety-contract regression tests."""

from __future__ import annotations

import hashlib
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
sys.path.insert(0, str(ROOT / "gui"))


def main_config(template: str, geometry: Path, output: Path) -> str:
    return f"""[run]
name = geometry-safety
threads = 1
seed = 12345
interactive = false
dry_run = true
verbose = 0

[output]
dir = {output}

[materials]
file = {ROOT / 'config' / 'materials' / 'material.ini'}

[geometry]
template = {template}
config = {geometry}
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
"""


def run_case(exe: Path, temp: Path, label: str, template: str, geometry_text: str, success: bool) -> str:
    geometry = temp / f"{label}-geometry.ini"
    config = temp / f"{label}-main.ini"
    geometry.write_text(geometry_text, encoding="utf-8")
    config.write_text(main_config(template, geometry, temp / f"{label}-output"), encoding="utf-8")
    completed = subprocess.run(
        [str(exe), "--config", str(config)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    output = completed.stdout + completed.stderr
    expected = 0 if success else 1
    if completed.returncode != expected:
        raise AssertionError(f"{label}: expected exit {expected}, got {completed.returncode}\n{output}")
    if not success and "created_geometry_object_count=0" not in output:
        raise AssertionError(f"{label}: failure was not proven pre-object\n{output}")
    return output


def fail(exe: Path, temp: Path, label: str, template: str, text: str, *markers: str) -> None:
    output = run_case(exe, temp, label, template, text, False)
    for marker in markers:
        if marker not in output:
            raise AssertionError(f"{label}: missing marker {marker!r}\n{output}")


def hierarchical(child: str, boolean: str = "") -> str:
    return f"""[world]
shape = box
size = 10 cm, 10 cm, 10 cm
material = G4_AIR

[volume.Target]
parent = world
{child}
material = G4_Si
region = TargetRegion
{boolean}
"""


SHAPES = {
    "box": ("shape = box\nsize = 2 mm, 3 mm, 4 mm", "shape = box", "shape = box\nsize = 2 mm, 3 mm, 4 mm\nparameters = 1 mm", "shape = box\nsize = -1 mm, 3 mm, 4 mm"),
    "tubs": ("shape = tubs\nparameters = 0 mm, 2 mm, 2 mm, 0 deg, 360 deg", "shape = tubs\nparameters = 0 mm, 2 mm, 2 mm, 0 deg", "shape = tubs\nparameters = 0 mm, 2 mm, 2 mm, 0 deg, 360 deg, 1 mm", "shape = tubs\nparameters = 2 mm, 1 mm, 2 mm, 0 deg, 360 deg"),
    "sphere": ("shape = sphere\nparameters = 0 mm, 2 mm, 0 deg, 360 deg, 0 deg, 180 deg", "shape = sphere\nparameters = 0 mm, 2 mm, 0 deg, 360 deg, 0 deg", "shape = sphere\nparameters = 0 mm, 2 mm, 0 deg, 360 deg, 0 deg, 180 deg, 1 mm", "shape = sphere\nparameters = 2 mm, 1 mm, 0 deg, 360 deg, 0 deg, 180 deg"),
    "orb": ("shape = orb\nparameters = 2 mm", "shape = orb", "shape = orb\nparameters = 2 mm, 3 mm", "shape = orb\nparameters = -2 mm"),
    "cone": ("shape = cone\nparameters = 0 mm, 2 mm, 0 mm, 1 mm, 2 mm, 0 deg, 360 deg", "shape = cone\nparameters = 0 mm, 2 mm, 0 mm, 1 mm, 2 mm, 0 deg", "shape = cone\nparameters = 0 mm, 2 mm, 0 mm, 1 mm, 2 mm, 0 deg, 360 deg, 1 mm", "shape = cone\nparameters = 0 mm, 2 mm, 0 mm, 1 mm, -2 mm, 0 deg, 360 deg"),
    "trd": ("shape = trd\ndx1 = 1 mm\ndx2 = 2 mm\ndy1 = 1 mm\ndy2 = 2 mm\ndz = 1 mm", "shape = trd\ndx1 = 1 mm\ndx2 = 2 mm\ndy1 = 1 mm\ndy2 = 2 mm", "shape = trd\ndx1 = 1 mm\ndx2 = 2 mm\ndy1 = 1 mm\ndy2 = 2 mm\ndz = 1 mm\nparameters = 1 mm", "shape = trd\ndx1 = -1 mm\ndx2 = 2 mm\ndy1 = 1 mm\ndy2 = 2 mm\ndz = 1 mm"),
    "trap": ("shape = trap\ndz = 1 mm\ntheta = 0 deg\nphi = 0 deg\ndy1 = 1 mm\ndx1 = 1 mm\ndx2 = 1 mm\nalpha1 = 0 deg\ndy2 = 1 mm\ndx3 = 1 mm\ndx4 = 1 mm\nalpha2 = 0 deg", "shape = trap\ndz = 1 mm\ntheta = 0 deg\nphi = 0 deg\ndy1 = 1 mm\ndx1 = 1 mm\ndx2 = 1 mm\nalpha1 = 0 deg\ndy2 = 1 mm\ndx3 = 1 mm\ndx4 = 1 mm", "shape = trap\ndz = 1 mm\ntheta = 0 deg\nphi = 0 deg\ndy1 = 1 mm\ndx1 = 1 mm\ndx2 = 1 mm\nalpha1 = 0 deg\ndy2 = 1 mm\ndx3 = 1 mm\ndx4 = 1 mm\nalpha2 = 0 deg\nparameters = 1 mm", "shape = trap\ndz = -1 mm\ntheta = 0 deg\nphi = 0 deg\ndy1 = 1 mm\ndx1 = 1 mm\ndx2 = 1 mm\nalpha1 = 0 deg\ndy2 = 1 mm\ndx3 = 1 mm\ndx4 = 1 mm\nalpha2 = 0 deg"),
}


def backend_contract(exe: Path, temp: Path) -> None:
    simple = """[world]\nsize = 10 cm,10 cm,10 cm\nmaterial = G4_AIR\n[target]\nshape = box\nsize = 1 mm,1 mm,1 mm\nmaterial = G4_Si\nregion = R\n"""
    layered = """[world]\nsize = 10 cm,10 cm,10 cm\nmaterial = G4_AIR\n[layers]\ncount = 1\nnames = L\n[layer.L]\nthickness = 1 mm\nxy = 2 mm,2 mm\nmaterial = G4_Si\nregion = R\n"""
    for template, base, section in (("simple_box", simple, "target"), ("layered_device", layered, "layer.L"), ("hierarchical", hierarchical("shape = box\nsize = 1 mm,1 mm,1 mm"), "volume.Target")):
        fail(exe, temp, f"{template}-cut-typo", template, base + f"\n[{section}]\ncut.electron = 1 mm\n", "cut.electron", "cut.e-", "line", "value '1 mm'")
        no_region = base.replace("region = R\n", "").replace("region = TargetRegion\n", "") + f"\n[{section}]\ncut.e- = 1 mm\n"
        fail(exe, temp, f"{template}-cut-no-region", template, no_region, "requires a non-empty region", "cut.e-")

    fail(exe, temp, "simple-nonbox", "simple_box", simple.replace("shape = box", "shape = orb"), "only supports shape=box")
    array = """[world]\nsize = 10 cm,10 cm,10 cm\nmaterial = G4_AIR\n[array]\nshape = orb\nmaterial = G4_Si\nelement_size = 1 mm,1 mm,1 mm\ncounts = 1,1,1\npitch = 1 mm,1 mm,1 mm\n"""
    fail(exe, temp, "array-nonbox", "array", array, "only supports shape=box")

    for shape, variants in SHAPES.items():
        valid, missing, extra, invalid = variants
        run_case(exe, temp, f"volume-{shape}-valid", "hierarchical", hierarchical(valid), True)
        fail(exe, temp, f"volume-{shape}-missing", "hierarchical", hierarchical(missing), "created_geometry_object_count=0")
        fail(exe, temp, f"volume-{shape}-extra", "hierarchical", hierarchical(extra), "created_geometry_object_count=0")
        fail(exe, temp, f"volume-{shape}-invalid", "hierarchical", hierarchical(invalid), "created_geometry_object_count=0")

        boolean_header = "\n[volume.Target.boolean.0]\noperation = subtraction\n" + valid
        run_case(exe, temp, f"boolean-{shape}-valid", "hierarchical", hierarchical("shape = box\nsize = 5 mm,5 mm,5 mm", boolean_header), True)
        for kind, body in (("missing", missing), ("extra", extra), ("invalid", invalid)):
            boolean = "\n[volume.Target.boolean.0]\noperation = subtraction\n" + body
            fail(exe, temp, f"boolean-{shape}-{kind}", "hierarchical", hierarchical("shape = box\nsize = 5 mm,5 mm,5 mm", boolean), "created_geometry_object_count=0")

    fail(exe, temp, "orb-size-shorthand", "hierarchical", hierarchical("shape = orb\nsize = 2 mm,2 mm,2 mm"), "does not accept size shorthand")
    fail(exe, temp, "copy-no-text", "hierarchical", hierarchical("shape = box\nsize = 1 mm,1 mm,1 mm\ncopyNo = 1x"), "signed 32-bit integer")
    fail(exe, temp, "copy-no-range", "hierarchical", hierarchical("shape = box\nsize = 1 mm,1 mm,1 mm\ncopyNo = 2147483648"), "signed 32-bit integer")
    fail(exe, temp, "placement", "hierarchical", hierarchical("shape = box\nsize = 1 mm,1 mm,1 mm\nplacement = assembly"), "placement=assembly", "placement=normal")


def gui_contract(temp: Path) -> None:
    from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow, geometry_document_from_summary, validate_geometry_document
    from g4usim_gui.models.package_model import GeometrySettings, PathSettings
    from g4usim_gui.parsers.geometry_parser import parse_geometry
    from g4usim_gui.preview3d.scene_builder import build_preview_scene
    from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
    from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
    from g4usim_gui.writers.package_writer import _copy_or_generate_inputs

    malformed = temp / "malformed.ini"
    malformed.write_text("[world\nshape = box\n", encoding="utf-8")
    document = geometry_document_from_summary(parse_geometry(malformed), "hierarchical")
    original_errors = list(document.source_errors)
    validate_geometry_document(document)
    validate_geometry_document(document)
    assert original_errors and all(item in document.errors for item in original_errors)

    blocked = temp / "blocked.ini"
    blocked.write_text(hierarchical("shape = box\nsize = 1 mm,1 mm,1 mm\ncut.e- = 1 mm\nvis.color = red\nlegacy_label = old"), encoding="utf-8")
    blocked_document = geometry_document_from_summary(parse_geometry(blocked), "hierarchical")
    assert blocked_document.round_trip_blockers and blocked_document.legacy_metadata
    scene = build_preview_scene(blocked_document, SourceEditableModel())
    assert scene.volumes
    assert any("Round-trip blocker:" in item for item in scene.warnings)
    blocked_document.is_dirty = True
    try:
        generate_geometry_ini_text(blocked_document)
    except ValueError as error:
        assert "round-trip" in str(error).lower()
    else:
        raise AssertionError("round-trip blocker did not stop editable writer")

    metadata_document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / "hierarchical_volume.ini"), "hierarchical")
    metadata_document.volumes[0].metadata = "placement = replica\nmetadata.role = world"
    metadata_document.is_dirty = True
    validate_geometry_document(metadata_document, material_names={"G4_AIR", "G4_WATER", "G4_Si"})
    assert any("only metadata" in item for item in metadata_document.errors)

    dotted = temp / "dotted.ini"
    dotted.write_text(hierarchical("shape = box\nsize = 2 mm,2 mm,2 mm") + "\n[volume.A.B]\nparent = world\nshape = box\nsize = 1 mm,1 mm,1 mm\nmaterial = G4_Si\n\n[volume.A.B.boolean.0]\noperation = subtraction\nshape = box\nsize = 0.5 mm,0.5 mm,0.5 mm\n", encoding="utf-8")
    dotted_summary = parse_geometry(dotted)
    assert any(op.target_volume == "A.B" for op in dotted_summary.boolean_ops)

    source_hash = hashlib.sha256(blocked.read_bytes()).hexdigest()
    blocked_document.source_copy_mode = True
    package = SimpleNamespace(
        materials_ini_path=str(temp / "copied-material.ini"),
        geometry_ini_path=str(temp / "copied-geometry.ini"),
    )
    paths = PathSettings(materials_config=str(ROOT / "config" / "materials" / "material.ini"), geometry_config=str(blocked))
    modes = _copy_or_generate_inputs(package, paths, GeometrySettings(template="hierarchical", config_path=str(blocked)), None, blocked_document)
    assert "validation bypassed" in modes[1]
    assert hashlib.sha256(blocked.read_bytes()).hexdigest() == source_hash
    assert Path(package.geometry_ini_path).read_bytes() == blocked.read_bytes()

    safe = HierarchicalVolumeRow(name="world", shape="box", size="1 mm,1 mm,1 mm", material="G4_AIR", metadata="metadata.role = world")
    metadata_document.volumes = [safe]
    metadata_document.round_trip_blockers = []
    metadata_document.source_errors = []
    metadata_document.source_copy_mode = False
    assert "metadata.role = world" in generate_geometry_ini_text(metadata_document)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", choices=("all", "backend", "gui"), default="all")
    layer = parser.parse_args().layer
    exe = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if layer != "gui" and not exe.is_file():
        raise FileNotFoundError(f"G4UniversalSim executable not found: {exe}")
    with tempfile.TemporaryDirectory(prefix="g4usim_geometry_safety_") as raw:
        temp = Path(raw)
        if layer != "gui":
            backend_contract(exe, temp)
        if layer != "backend":
            gui_contract(temp)
    print("test_geometry_safety_contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
