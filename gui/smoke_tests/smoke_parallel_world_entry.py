"""H3-3 regression: parallel-world configuration entry, diagnostics and K1 closure.

Qt-only for the Project page parts, plus non-Qt checks of the read-only scope,
the editable-import refusal, the resource closure and a 20-event real backend run
on the tracked box example. No new acceptance framework: plain asserts.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "gui") not in sys.path:
    sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core import parallel_world_scope  # noqa: E402
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot  # noqa: E402
from g4usim_gui.core.experiment_bundle import collect_bundle_resources, export_bundle, load_bundle  # noqa: E402
from g4usim_gui.core.experiment_identity import capture_identity  # noqa: E402
from g4usim_gui.core.project import G4USimProject, load_project, save_project  # noqa: E402
from g4usim_gui.core.project_diagnostics import validate_project_report  # noqa: E402
from g4usim_gui.core.run_editor_import import RunEditorImportError, parse_run_editor_ini  # noqa: E402
from g4usim_gui.widgets.project_page import ProjectPage  # noqa: E402

EXE = Path(
    __import__("os").environ.get("G4USIM_EXE", "")
    or ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe"
)

MAIN = """[run]
name = h3_entry
threads = 1
seed = 20261400
interactive = false
verbose = 0
check_overlaps = true
dry_run = false

[output]
dir = output
format = csv

[materials]
file = materials.ini

[geometry]
template = hierarchical
config = geometry.ini
default_world_material = galactic

[physics]
reference = FTFP_BERT

[scoring]
enabled = true
hits = false
event_edep = false
edep = false
dose = true
fluence = true
auto_create_default_scorers = true

[source]
particle = proton
energy = 10 MeV
position_type = point
position = 0, 0, -20 mm
direction = 0, 0, 1

[parallel_world]
enabled = true
name = ScoringWorld
geometry_config = parallel.ini
"""

MATERIALS = """[galactic]
material = G4_Galactic

[water]
material = G4_WATER
"""

GEOMETRY = """[world]
shape = box
size = 100 mm, 100 mm, 100 mm
material = galactic

[volume.Slab]
parent = world
shape = box
size = 20 mm, 20 mm, 2 mm
position = 0 mm, 0 mm, 0 mm
material = water
sensitive = false
"""

PARALLEL = """[world]
material = G4_Galactic

[volume.Slab]
parent = world
shape = box
size = 20 mm, 20 mm, 2 mm
position = 0 mm, 0 mm, 0 mm
material = water
sensitive = true
"""

MACRO = "/run/initialize\n/run/beamOn 200\n"


def _project(root: Path, *, run_input_mode: str = "external") -> G4USimProject:
    project = G4USimProject()
    project.projectName = "h3_entry"
    project.workspaceRoot = str(root)
    project.runInputMode = run_input_mode
    project.configPath = str(root / "main.ini")
    project.macroPath = str(root / "run.mac")
    project.outputDir = str(root / "output")
    project.seed = "20261400"
    return project


def _write(root: Path, *, main: str = MAIN) -> None:
    (root / "main.ini").write_text(main, encoding="utf-8")
    (root / "materials.ini").write_text(MATERIALS, encoding="utf-8")
    (root / "geometry.ini").write_text(GEOMETRY, encoding="utf-8")
    (root / "parallel.ini").write_text(PARALLEL, encoding="utf-8")
    (root / "run.mac").write_text(MACRO, encoding="utf-8")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    workdir = Path(tempfile.mkdtemp(prefix="g4usim-h3-entry-"))
    root = workdir / "project"
    root.mkdir()
    _write(root)
    project = _project(root)

    # 1. Read-only scope: enabled, file resolution relative to the main INI.
    scope = parallel_world_scope.read_inputs_scope("external", str(root / "main.ini"))
    assert scope.status == "enabled", scope.status
    assert scope.name == "ScoringWorld", scope.name
    assert not scope.issues, scope.issues
    line = parallel_world_scope.status_line(scope)
    assert "Parallel world: enabled, name ScoringWorld" in line, line
    assert "ghost geometry" in line and "parallel.ini" in line, line

    # 1b. Generated inputs must diagnose the section instead of dropping it silently.
    generated_project = _project(root, run_input_mode="generated")
    generated_scope = parallel_world_scope.read_scope(generated_project)
    assert generated_scope.status == "incompatible", generated_scope.status
    generated_codes = {issue.code for issue in generated_scope.issues}
    assert "parallel_world_generated_mode" in generated_codes, generated_codes
    generated_line = parallel_world_scope.status_line(generated_scope)
    assert "switch Inputs to External" in generated_line, generated_line
    generated_report = validate_project_report(generated_project)
    assert any("would not be used" in text for text in generated_report.warnings),         generated_report.warnings
    assert not any("would not be used" in text for text in generated_report.errors),         generated_report.errors

    # 2. Project page shows the scope and the honest GUI range note.
    page = ProjectPage()
    page.set_project(project)
    page.resize(1200, 900)
    app.processEvents()
    summary = page.status_summary.text()
    assert "Parallel world: enabled, name ScoringWorld" in summary, summary
    assert not page.parallel_note.isHidden()
    assert "3D preview draws only the mass geometry" in page.parallel_note.text()
    assert page.status_summary.minimumHeight() >= 150

    # 3. Diagnostics: missing geometry file and an unsupported combination.
    broken = workdir / "broken"
    broken.mkdir()
    _write(broken, main=MAIN.replace("geometry_config = parallel.ini", "geometry_config = missing.ini")
           + "\n[scoring.mesh.legacy]\n")
    broken_scope = parallel_world_scope.read_inputs_scope("external", str(broken / "main.ini"))
    codes = {issue.code for issue in broken_scope.issues}
    assert "parallel_world_geometry_missing" in codes, codes
    assert "parallel_world_native_mesh" in codes, codes
    report = validate_project_report(_project(broken))
    text = "\n".join(report.errors)
    assert "geometry file does not exist" in text, text
    assert "native scoring meshes are not supported" in text

    # 3b. An empty [scoring.displacement] is not an enabled DDD mode; only the
    # [scoring] flags are, matching the backend contract.
    ddd_disabled = workdir / "ddd_disabled"
    ddd_disabled.mkdir()
    disabled_main = MAIN + chr(10).join(["", "[scoring.displacement]", ""])
    _write(ddd_disabled, main=disabled_main)
    disabled_scope = parallel_world_scope.read_inputs_scope(
        "external", str(ddd_disabled / "main.ini"))
    assert not disabled_scope.issues, disabled_scope.issues
    disabled_report = validate_project_report(_project(ddd_disabled))
    assert not any("LET" in text or "displacement" in text
                   for text in disabled_report.errors), disabled_report.errors
    disabled_bytes = (ddd_disabled / "main.ini").read_bytes()
    save_project(_project(ddd_disabled), workdir / "ddd_disabled.json")
    assert (ddd_disabled / "main.ini").read_bytes() == disabled_bytes, "empty section rewritten"

    for flag in ("let", "displacement"):
        enabled_dir = workdir / ("enabled_" + flag)
        enabled_dir.mkdir()
        enabled_main = MAIN.replace(
            "auto_create_default_scorers = true",
            "auto_create_default_scorers = true" + chr(10) + flag + " = true")
        _write(enabled_dir, main=enabled_main)
        enabled_scope = parallel_world_scope.read_inputs_scope(
            "external", str(enabled_dir / "main.ini"))
        assert any(issue.code == "parallel_world_let_displacement"
                   for issue in enabled_scope.issues), enabled_scope.issues
        enabled_report = validate_project_report(_project(enabled_dir))
        assert any("LET and displacement" in text for text in enabled_report.errors),             enabled_report.errors

    # 3c. A disabled parallel world returns early in the backend compatibility
    # checks (ParallelWorldConfig::CompatibilityProblems), so LET/DDD, ROOT output
    # and native meshes must not be reported as parallel-world conflicts.
    base_without_parallel = MAIN.split("[parallel_world]")[0].rstrip() + chr(10)

    def _write_disabled(name: str, *, flags=(), section_extra="", body_extra=""):
        folder = workdir / name
        folder.mkdir()
        text = base_without_parallel
        for flag in flags:
            text = text.replace(
                "auto_create_default_scorers = true",
                "auto_create_default_scorers = true" + chr(10) + flag + " = true")
        text += chr(10) + "[parallel_world]" + chr(10) + "enabled = false" + chr(10)
        text += section_extra + body_extra
        _write(folder, main=text)
        return folder

    for flag in ("let", "displacement"):
        disabled_dir = _write_disabled("disabled_world_" + flag, flags=(flag,))
        disabled_scope = parallel_world_scope.read_inputs_scope(
            "external", str(disabled_dir / "main.ini"))
        assert disabled_scope.status == "disabled", disabled_scope.status
        assert not disabled_scope.issues, disabled_scope.issues
        disabled_report = validate_project_report(_project(disabled_dir))
        assert not any("LET and displacement" in text for text in disabled_report.errors),             disabled_report.errors
        before_bytes = (disabled_dir / "main.ini").read_bytes()
        save_project(_project(disabled_dir), workdir / ("disabled_world_" + flag + ".json"))
        assert (disabled_dir / "main.ini").read_bytes() == before_bytes, "disabled world rewritten"

    # A disabled world still diagnoses its own illegal name/geometry_config keys.
    keys_dir = _write_disabled(
        "disabled_world_keys", flags=("let",),
        section_extra="name = Stale" + chr(10) + "geometry_config = parallel.ini" + chr(10))
    keys_scope = parallel_world_scope.read_inputs_scope(
        "external", str(keys_dir / "main.ini"))
    assert keys_scope.status == "disabled", keys_scope.status
    assert {issue.code for issue in keys_scope.issues} == {"parallel_world_disabled_with_keys"},         keys_scope.issues

    # An invalid boolean is still diagnosed and treated as disabled.
    bad_bool_dir = _write_disabled(
        "disabled_world_bad_bool", flags=("let",),
        section_extra="")
    (bad_bool_dir / "main.ini").write_text(
        (bad_bool_dir / "main.ini").read_text(encoding="utf-8").replace(
            "enabled = false", "enabled = maybe"), encoding="utf-8")
    bad_bool_scope = parallel_world_scope.read_inputs_scope(
        "external", str(bad_bool_dir / "main.ini"))
    codes = {issue.code for issue in bad_bool_scope.issues}
    assert "parallel_world_boolean" in codes, codes
    assert "parallel_world_let_displacement" not in codes, codes

    # ROOT output / native meshes are only parallel-world conflicts when enabled.
    combo_dir = _write_disabled(
        "disabled_world_root_mesh", flags=("let", "displacement"),
        section_extra="",
        body_extra="[output]" + chr(10) + "format = root" + chr(10) + chr(10)
        + "[scoring.mesh.legacy]" + chr(10))
    combo_scope = parallel_world_scope.read_inputs_scope(
        "external", str(combo_dir / "main.ini"))
    combo_codes = {issue.code for issue in combo_scope.issues}
    assert combo_scope.status == "disabled", combo_scope.status
    assert not combo_codes, combo_codes

    # 4. Editable import refuses the external-only section instead of dropping it.
    try:
        parallel_section = chr(10).join([
            "[parallel_world]", "enabled = true", "name = ScoringWorld", ""])
        parse_run_editor_ini(parallel_section, source_path=root / "main.ini")
    except RunEditorImportError as error:
        reasons = {issue.reason for issue in error.issues}
        assert any("external-only" in reason for reason in reasons), reasons
    else:
        raise AssertionError("editable import must reject [parallel_world]")

    # 5. Project save/load keeps the external path and never rewrites file bytes.
    main_before = (root / "main.ini").read_bytes()
    parallel_before = (root / "parallel.ini").read_bytes()
    project_file = workdir / "project.json"
    save_project(project, project_file)
    loaded = load_project(project_file)
    assert loaded.runInputMode == "external"
    assert Path(loaded.configPath) == root / "main.ini"
    assert (root / "main.ini").read_bytes() == main_before
    assert (root / "parallel.ini").read_bytes() == parallel_before

    # 6. K1 closure includes the parallel geometry and identity follows its bytes.
    snapshot = WorkspaceSnapshot(project)
    collected = collect_bundle_resources(snapshot)
    roles = {record["role"] for record in collected["resources"]}
    assert "parallel_geometry" in roles, roles
    bundle = workdir / "bundle"
    export_bundle(snapshot, bundle)
    bundle_main = next(path for path in bundle.rglob("*.ini") if "[parallel_world]" in path.read_text(encoding="utf-8"))
    rewritten = [
        line.split("=", 1)[1].strip()
        for line in bundle_main.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("geometry_config")
    ]
    assert rewritten, bundle_main
    assert (bundle_main.parent / rewritten[0]).is_file(), rewritten
    assert load_bundle(bundle).project.runInputMode == "external"
    before = capture_identity(snapshot, 1)["fingerprint"]
    (root / "parallel.ini").write_text(PARALLEL.replace("20 mm, 20 mm, 2 mm", "20 mm, 20 mm, 3 mm"), encoding="utf-8")
    after = capture_identity(WorkspaceSnapshot(project), 1)["fingerprint"]
    assert before != after
    (root / "parallel.ini").write_text(PARALLEL, encoding="utf-8")

    # 7. Real backend: the tracked box example runs 20 events with parallel rows.
    assert EXE.is_file(), f"backend executable not found: {EXE}"
    case = workdir / "case"
    shutil.copytree(ROOT / "examples" / "07_parallel_world_box", case)
    (case / "run.mac").write_text("/run/initialize\n/run/beamOn 20\n", encoding="utf-8")
    result = subprocess.run(
        [str(EXE), "--config", "main.ini", "--macro", "run.mac", "--output", "output"],
        cwd=case, capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary_text = (case / "output" / "run_summary.txt").read_text(encoding="utf-8")
    assert "status = completed" in summary_text
    assert "run_0_completed_events = 20" in summary_text, summary_text
    assert "parallel_world_enabled = true" in summary_text
    assert "parallel_world_volume_count = 1" in summary_text
    dose_rows = (case / "output" / "dose_volume_summary_t0.csv").read_text(encoding="utf-8").splitlines()
    assert dose_rows[0].startswith("runID,volume_path,volume_name,mass_kg"), dose_rows[0]
    cells = [line.split(",") for line in dose_rows[1:] if line]
    assert len(cells) == 1, cells
    assert cells[0][1] == "/ScoringWorld#0/Slab#0", cells[0][1]
    assert abs(float(cells[0][3]) - 0.0008) < 1e-12
    assert int(cells[0][-1]) == 20, cells[0][-1]
    assert float(cells[0][7]) > 0.0, cells[0]
    fluence_rows = (case / "output" / "fluence_volume_summary_t0.csv").read_text(encoding="utf-8").splitlines()
    assert fluence_rows[1].startswith("0,/ScoringWorld#0/Slab#0"), fluence_rows[1]

    print("smoke_parallel_world_entry: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
