"""The GUI and the backend must agree on which geometry/material inputs are valid (roadmap E1).

The GUI checks the geometry and materials files with its own Python validators before it
generates a run package; the backend checks them again while building the Geant4
world. When the two disagree, the GUI either blocks inputs that run fine (the default
demo project could not show "Show Backend Geometry") or lets through inputs that fail
later. Every case below goes through both:

  GUI      parse_materials + parse_geometry, then validate_geometry_document and
           validate_material_document exactly as the Configuration page calls them;
           verdict "accept", "reject" (errors), or "limited" (only round-trip blockers,
           or a preview-only template: the GUI copies the file and does not judge it)
  backend  a minimal main INI with the same [materials] file and [geometry]
           template/config, a macro "/run/initialize + /AIHL/geometry/exportMesh"
           (what Show Backend Geometry runs); verdict "accept" when the process exits 0
           and the mesh file is written

Cases: every main INI in the repository that names a geometry file (with its own
materials file), every geometry file under config/geometry and test/geometry paired
with config/materials/material.ini and test/materials/test_materials.ini, the
volume-fraction material fixtures (one valid, three that must be rejected), and the
five new-simulation wizard scenarios through the GUI's package writer.

Round trip: when the GUI accepts the materials file, the materials the GUI's writer
generates from it (and, when the geometry is editable, the generated geometry) must
also be accepted by the backend, so loading a file into the editors and generating a
package never breaks a valid input.

A case fails when one side accepts and the other rejects, or a round trip is rejected,
unless the case is listed in EXPECTED with the reason. "limited" cases (the editor
cannot write the geometry and points to source copy mode) are reported, not judged.

    gui\\.venv\\Scripts\\python.exe scripts\\test_gui_backend_agreement.py [-v]
"""

from __future__ import annotations

import configparser
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
EXE = Path(os.environ.get("G4USIM_EXE", ROOT / "build_vs2026/Release/G4UniversalSim.exe"))

from g4usim_gui.core import wizard as wz   # noqa: E402
from g4usim_gui.core.project import G4USimProject   # noqa: E402
from g4usim_gui.editors.geometry_editor_model import (   # noqa: E402
    HIERARCHICAL_GEOMETRY_MODES,
    geometry_document_from_summary,
    validate_geometry_document,
)
from g4usim_gui.editors.material_editor_model import (   # noqa: E402
    generate_materials_ini_text,
    material_document_from_summary,
    validate_material_document,
)
from g4usim_gui.models.package_model import PathSettings   # noqa: E402
from g4usim_gui.parsers.geometry_parser import parse_geometry   # noqa: E402
from g4usim_gui.parsers.materials_parser import parse_materials   # noqa: E402
from g4usim_gui.preview3d.backend_mesh import export_arguments, write_export_macro   # noqa: E402
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text   # noqa: E402
from g4usim_gui.writers.package_writer import create_run_package   # noqa: E402

MATERIAL_FILES = ("config/materials/material.ini", "test/materials/test_materials.ini")
VOLUME_FRACTION = ("config/materials/volume_fraction_test.ini", "test/materials/volume_fraction_bad_sum.ini",
                   "test/materials/volume_fraction_cycle.ini", "test/materials/volume_fraction_element_component.ini")
# (geometry file, materials file) -> why GUI and backend are allowed to disagree
EXPECTED: dict[tuple[str, str], str] = {}


@dataclass
class Case:
    name: str
    template: str
    geometry: str = ""
    materials: str = ""
    main_ini: str = ""          # wizard cases: the generated package's main INI
    gui: str = ""
    gui_reason: str = ""
    backend: str = ""
    backend_reason: str = ""
    generated_materials: str = ""   # the GUI writer's output, when the GUI accepts the materials
    generated_geometry: str = ""    # ... and the geometry, when the editor can write it
    roundtrip: str = ""
    roundtrip_reason: str = ""


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(inline_comment_prefixes=("#", ";"), strict=False, interpolation=None)
    parser.read(path, encoding="utf-8")
    return parser


def template_of(text: str) -> str:
    if "[gdml]" in text:
        return "gdml"
    if "[volume." in text:
        return "hierarchical"
    if "[layers]" in text or "[layer." in text:
        return "layered_device"
    if "[target]" in text:
        return "simple_box"
    if "[array]" in text:
        return "array"
    if "[shielding]" in text:
        return "shielding"
    return "hierarchical"


def collect_cases(work: Path) -> list[Case]:
    cases: list[Case] = []
    seen: set[tuple[str, str, str]] = set()

    def add(name: str, template: str, geometry: str, materials: str) -> None:
        key = (geometry, materials, template)
        if key not in seen:
            seen.add(key)
            cases.append(Case(name, template, geometry, materials))

    for main in sorted(p for d in ("config", "test", "scenarios", "examples") for p in (ROOT / d).rglob("*.ini")):
        ini = read_ini(main)
        if not ini.has_option("geometry", "config") or not ini.has_option("materials", "file"):
            continue
        geometry, materials = ini.get("geometry", "config"), ini.get("materials", "file")
        if (ROOT / geometry).is_file() and (ROOT / materials).is_file():
            add(f"main:{rel(main)}", ini.get("geometry", "template", fallback="hierarchical"), geometry, materials)
    for geometry in sorted(list((ROOT / "config/geometry").glob("*.ini")) + list((ROOT / "test/geometry").glob("*.ini"))):
        template = template_of(geometry.read_text(encoding="utf-8", errors="replace"))
        for materials in MATERIAL_FILES:
            add(f"{rel(geometry)} + {Path(materials).name}", template, rel(geometry), materials)
    # each volume-fraction fixture with a box made of its last material, so the verdicts
    # are about that material and not about a name the geometry lacks
    for materials in VOLUME_FRACTION:
        names = [s[len("material."):] for s in read_ini(ROOT / materials).sections() if s.lower().startswith("material.")]
        geometry = work / "geometry" / f"{Path(materials).stem}.ini"
        geometry.parent.mkdir(parents=True, exist_ok=True)
        geometry.write_text("\n".join([
            "[world]", "size = 6 cm, 6 cm, 6 cm", "material = G4_AIR", "",
            "[target]", "name = Target", "shape = box", "size = 10 mm, 10 mm, 10 mm",
            f"material = {names[-1]}", "position = 0 mm, 0 mm, 0 mm", ""]), encoding="utf-8")
        add(f"box of {names[-1]} + {Path(materials).name}", "simple_box", str(geometry), materials)
    return cases


def gui_verdict(case: Case) -> None:
    materials = parse_materials(ROOT / case.materials)
    material_document = material_document_from_summary(materials)
    geometry = parse_geometry(ROOT / case.geometry, case.template)
    document = geometry_document_from_summary(geometry, case.template)
    names = {row.name for row in material_document.rows if row.enabled and row.name}   # as the Configuration page
    validate_geometry_document(document, material_names=names, scoring_hits_enabled=True, physics_biasing_enabled=True)
    validate_material_document(material_document, geometry_material_refs=geometry.material_refs)
    # editor limits (the file is fine, the editor cannot write it): they all point to source copy mode
    limits = [e for e in document.errors if e.startswith("Round-trip blocker:") or "use original source copy mode" in e]
    errors = [e for e in document.errors if e not in limits] + material_document.errors
    if not material_document.errors:
        case.generated_materials = generate_materials_ini_text(material_document)
    if errors:
        case.gui, case.gui_reason = "reject", errors[0]
    elif limits:
        case.gui, case.gui_reason = "limited", limits[-1]
    elif document.mode not in HIERARCHICAL_GEOMETRY_MODES | {"simple_box", "layered_device"}:
        case.gui, case.gui_reason = "limited", f"preview-only template {case.template}"
    elif document.round_trip_blockers:
        case.gui, case.gui_reason = "limited", f"round-trip blocker: {document.round_trip_blockers[0]}"
    else:
        case.gui = "accept"
        document.is_dirty = True
        case.generated_geometry = generate_geometry_ini_text(document)


def wizard_cases(work: Path) -> list[Case]:
    """The wizard scenarios through the GUI package writer (which raises when the GUI rejects)."""
    cases = []
    for scenario in wz.SCENARIOS:
        result = wz.build(wz.default_spec(scenario))
        project = G4USimProject()
        project.pathSettings = PathSettings(executable=str(EXE), workspace_root=str(ROOT), runs_root=str(work),
                                            materials_config=str(ROOT / MATERIAL_FILES[0]),
                                            geometry_config=str(ROOT / "test/geometry/hierarchical_test.ini"))
        wz.apply_to_project(project, result)
        case = Case(f"wizard:{scenario}", "hierarchical")
        try:
            package, _ = create_run_package(
                project=project, paths=project.pathSettings, run=result.run, geometry=project.geometrySettings,
                source=project.sourceSettings, physics=project.physicsSettings, scoring=project.scoringSettings,
                geometry_document=result.geometry, source_model=result.source, physics_model=result.physics,
                scoring_model=result.scoring)
            case.gui, case.main_ini = "accept", package.main_ini_path
        except ValueError as error:
            case.gui, case.gui_reason = "reject", str(error).splitlines()[0]
        cases.append(case)
    return cases


ERROR_LINE = re.compile(r"(error|exception|not found|invalid|failed|unsupported|unknown)", re.IGNORECASE)


def run_backend(folder: Path, main: Path | None, materials: Path, template: str, geometry: Path) -> tuple[str, str]:
    """Initialize Geant4 and export the world, as Show Backend Geometry does."""
    folder.mkdir(parents=True)
    if main is None:
        main = folder / "main.ini"
        main.write_text(f"[materials]\nfile = {materials.as_posix()}\n\n[geometry]\n"
                        f"template = {template}\nconfig = {geometry.as_posix()}\n", encoding="utf-8")
    mesh = folder / "mesh.json"
    macro = write_export_macro(folder, mesh)
    process = subprocess.run([str(EXE), *export_arguments(str(main), macro, folder / "output")], cwd=str(ROOT),
                             capture_output=True, text=True, errors="replace", timeout=600)
    if process.returncode == 0 and mesh.is_file():
        return "accept", ""
    lines = [line.strip() for line in (process.stderr + "\n" + process.stdout).splitlines() if ERROR_LINE.search(line)]
    return "reject", (lines[0] if lines else f"exit code {process.returncode}")[:300]


def backend_verdict(case: Case, work: Path, index: int) -> None:
    folder = work / f"case{index:03d}"
    if case.main_ini:
        case.backend, case.backend_reason = run_backend(folder, Path(case.main_ini), Path(), "", Path())
        return
    case.backend, case.backend_reason = run_backend(folder / "source", None, ROOT / case.materials, case.template,
                                                    ROOT / case.geometry)
    if case.generated_materials and case.backend == "accept":
        generated = folder / "generated"
        generated.mkdir(parents=True)
        materials = generated / "materials.ini"
        materials.write_text(case.generated_materials, encoding="utf-8")
        geometry = ROOT / case.geometry
        if case.generated_geometry:
            geometry = generated / "geometry.ini"
            geometry.write_text(case.generated_geometry, encoding="utf-8")
        case.roundtrip, case.roundtrip_reason = run_backend(generated / "run", None, materials, case.template, geometry)


def main() -> int:
    if not EXE.is_file():
        print(f"SKIP: backend executable missing: {EXE}")
        return 0
    verbose = "-v" in sys.argv
    with tempfile.TemporaryDirectory(prefix="g4usim-agreement-") as temp:
        work = Path(temp)
        cases = collect_cases(work)
        for case in cases:
            gui_verdict(case)
        cases += wizard_cases(work / "runs")
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item: backend_verdict(item[1], work, item[0]), enumerate(cases)))

    mismatches, expected, limited = [], [], []
    for case in cases:
        line = f"{case.name} [{case.template}]: GUI {case.gui}, backend {case.backend}"
        if case.gui == "limited":
            limited.append(f"{line} ({case.gui_reason})")
        elif case.gui != case.backend:
            detail = f"{line}\n    GUI: {case.gui_reason or '-'}\n    backend: {case.backend_reason or '-'}"
            reason = EXPECTED.get((case.geometry, case.materials))
            (expected if reason else mismatches).append(detail + (f"\n    expected: {reason}" if reason else ""))
        if case.roundtrip == "reject":
            mismatches.append(f"{case.name}: the GUI writer's materials/geometry are rejected by the backend\n"
                              f"    backend: {case.roundtrip_reason}")
        if verbose:
            print(line + (f" | GUI: {case.gui_reason}" if case.gui_reason else "")
                  + (f" | backend: {case.backend_reason}" if case.backend_reason else ""))
    agree = sum(1 for c in cases if c.gui == c.backend)
    trips = sum(1 for c in cases if c.roundtrip == "accept")
    print(f"{len(cases)} cases: {agree} agree, {len(limited)} GUI-limited, {len(expected)} expected differences, "
          f"{trips} writer round trips accepted, {len(mismatches)} mismatches")
    for title, items in (("GUI-limited (not judged)", limited), ("Expected differences", expected),
                         ("MISMATCHES", mismatches)):
        if items:
            print(f"\n{title}:")
            for item in items:
                print("  " + item)
    if mismatches:
        return 1
    print("\ntest_gui_backend_agreement: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
