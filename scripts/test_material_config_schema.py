"""M0-3B2A regression tests for the closed material-file schema."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
LEGACY_GUI_FIXTURE = ROOT / "scripts" / "fixtures" / "materials" / "legacy_gui_type.ini"


def run(executable: Path, config: Path, expected: int) -> str:
    environment = os.environ.copy()
    environment["G4USIM_TEST_MATERIAL_LIFECYCLE"] = "1"
    result = subprocess.run(
        [str(executable), "--config", str(config)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        env=environment,
    )
    output = result.stdout + result.stderr
    if result.returncode != expected:
        raise AssertionError(f"Expected {expected}, got {result.returncode}\n{output}")
    return output


def main_config(materials: Path, output: Path) -> str:
    geometry = ROOT / "config" / "geometry" / "simple_box.ini"
    return f"""[run]
name = material-schema
threads = 1
seed = 12345
interactive = false
dry_run = true
verbose = 0

[output]
dir = {output}

[materials]
file = {materials}

[geometry]
template = simple_box
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


def write_case(temp: Path, name: str, material_text: str | Path) -> Path:
    materials = temp / f"{name}-materials.ini"
    if isinstance(material_text, Path):
        materials = material_text
    else:
        materials.write_text(material_text, encoding="utf-8")
    config = temp / f"{name}.ini"
    config.write_text(main_config(materials, temp / f"{name}-output"), encoding="utf-8")
    return config


def expect_failure(executable: Path, temp: Path, name: str, material_text: str, *markers: str) -> None:
    output = run(executable, write_case(temp, name, material_text), 1)
    for marker in markers:
        if marker not in output:
            raise AssertionError(f"Missing marker {marker!r}\n{output}")
    if "[MaterialLifecycle] build_started" in output:
        raise AssertionError(f"Schema failure reached material object construction:\n{output}")


def expect_success(executable: Path, temp: Path, name: str, material_text: str | Path) -> str:
    output = run(executable, write_case(temp, name, material_text), 0)
    if "[MaterialLifecycle] build_started" not in output:
        raise AssertionError(f"Successful material load did not reach object construction:\n{output}")
    return output


def legal_material_schema() -> str:
    return """[NIST]
materials = G4_AIR,G4_WATER

[isotope.H1]
symbol = H
z = 1
n = 1
a = 1.007825 g/mole

[element.CustomH]
symbol = H
isotopes = H1:1.0

[element.CustomO]
symbol = O
z = 8
a = 15.999 g/mole

[material.MassWater]
mode = mass_fraction
density = 1 g/cm3
components = CustomH:0.1119,CustomO:0.8881
state = liquid

[material.AtomWater]
mode = atom_count
density = 1 g/cm3
components = CustomH:2,CustomO:1
state = liquid

[material.VolumeMix]
mode = volume_fraction
density = auto
components = G4_WATER:0.75,G4_AIR:0.25
state = gas
"""


def test_gui_writer(temp: Path, executable: Path) -> None:
    sys.path.insert(0, str(ROOT / "gui"))
    from g4usim_gui.editors.material_editor_model import (
        MaterialDocument,
        MaterialRow,
        generate_materials_ini_text,
    )
    from g4usim_gui.parsers.materials_parser import parse_materials

    legacy_summary = parse_materials(LEGACY_GUI_FIXTURE)
    if legacy_summary.errors:
        raise AssertionError(f"GUI parser rejected legacy type fixture: {legacy_summary.errors}")

    document = MaterialDocument(rows=[
        MaterialRow(name="G4_AIR", mode="nist", nist_name="G4_AIR"),
        MaterialRow(name="GuiWater", mode="mass_fraction", density="1.0 g/cm3", components_text="G4_H:0.1119\nG4_O:0.8881"),
    ])
    generated = temp / "gui-generated-materials.ini"
    generated.write_text(generate_materials_ini_text(document), encoding="utf-8")
    if "type =" in generated.read_text(encoding="utf-8").lower():
        raise AssertionError("Current GUI writer must not emit deprecated material type fields")
    output = run(executable, write_case(temp, "gui-generated", generated), 0)
    if "[ConfigWarning]" in output:
        raise AssertionError(f"GUI-generated material file produced main-config warnings:\n{output}")


def main() -> int:
    executable = Path(os.environ.get("G4USIM_EXE", str(DEFAULT_EXE)))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")

    with tempfile.TemporaryDirectory(prefix="g4usim-material-schema-") as temporary:
        temp = Path(temporary)
        valid = ROOT / "config" / "materials" / "material.ini"
        expect_success(executable, temp, "repository", valid.read_text(encoding="utf-8"))
        expect_success(executable, temp, "legacy-gui-fixture", LEGACY_GUI_FIXTURE)
        expect_success(executable, temp, "legacy-gui-case", "[material.Case]\nTyPe =  MaTeRiAl  \nmode = atom_count\ndensity = 1 g/cm3\ncomponents = G4_H:2,G4_O:1\n")
        expect_success(executable, temp, "legal-combination", legal_material_schema())

        expect_failure(executable, temp, "nist-typo", "[NIST]\nmaterails = G4_AIR\n", "line", "section", "materails", "materials")
        expect_failure(executable, temp, "material-typo", "[material.X]\ndensitty = 1 g/cm3\ncomponents = G4_Si:1\n", "line", "densitty", "density")
        expect_failure(executable, temp, "unknown-section", "[mystery]\nvalue = 1\n", "unknown material configuration section", "mystery", "value '1'")
        expect_failure(executable, temp, "global-field", "threds = 1\n", "global", "threds", "value '1'")
        for name in ("material", "element", "isotope"):
            expect_failure(executable, temp, f"empty-{name}", f"[{name}.]\n", "section suffix must not be empty")
        expect_failure(executable, temp, "legacy-extra", "[Alias]\nmaterial = G4_AIR\nmatreial = G4_WATER\n", "Alias", "matreial", "material")
        expect_failure(executable, temp, "temperature", "[material.X]\ndensity = 1 g/cm3\ncomponents = G4_Si:1\ntemperature = 300 K\n", "unsupported temperature/pressure", "density, state, and composition")
        expect_failure(executable, temp, "pressure", "[material.X]\ndensity = 1 g/cm3\ncomponents = G4_Si:1\npressure = 1 atm\n", "unsupported temperature/pressure", "pressure")
        expect_failure(
            executable,
            temp,
            "type-invalid",
            "[material.MixedCase]\nTyPe = isotope\nmode = atom_count\ndensity = 1 g/cm3\ncomponents = G4_H:2,G4_O:1\n",
            "line 2, section 'material.MixedCase', key 'TyPe', value 'isotope'",
            "only accepts 'material'",
        )
        expect_failure(
            executable,
            temp,
            "type-empty",
            "[material.EmptyType]\nTYPE =   \nmode = atom_count\ndensity = 1 g/cm3\ncomponents = G4_H:2,G4_O:1\n",
            "line 2, section 'material.EmptyType', key 'TYPE', value ''",
            "only accepts 'material'",
        )
        forbidden_type_sections = {
            "nist": "[NIST]\ntype = material\nmaterials = G4_AIR\n",
            "isotope": "[isotope.H1]\ntype = material\nsymbol = H\nz = 1\nn = 1\na = 1 g/mole\n",
            "element": "[element.H]\ntype = material\nsymbol = H\nz = 1\na = 1 g/mole\n",
            "alias": "[Alias]\nmaterial = G4_AIR\ntype = material\n",
        }
        for label, text in forbidden_type_sections.items():
            expect_failure(executable, temp, f"type-forbidden-{label}", text, "key 'type'", "value 'material'", "unknown material configuration key")

        case_config = write_case(temp, "case-comments", "[nIsT]\nMATERIALS = G4_AIR # compatible comment\n[Alias]\nMATERIAL = G4_WATER ; legacy comment\n")
        output = run(executable, case_config, 0)
        if "[MaterialLifecycle] build_started" not in output:
            raise AssertionError("Case-insensitive legal configuration did not build materials")
        test_gui_writer(temp, executable)

    print("M0-3B2A material schema tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
