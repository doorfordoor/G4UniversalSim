"""Real small-event runs after F5 undo/redo and persistent editing recovery.

This checks configuration selection and actual source/geometry consumption. It
is not an independent radiation-physics or statistical-accuracy benchmark.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint, snapshot_from_json, snapshot_to_json
from g4usim_gui.core.edit_state import empty_editing_state
from g4usim_gui.core.edit_transactions import EditSession
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.editors.source_physics_scoring_model import PhysicsEditableModel, ScoringEditableModel, SourceEditableModel
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.preview3d.backend_mesh import load_backend_mesh
from g4usim_gui.writers.package_writer import create_run_package

EVENTS = 3
MATERIALS = """# F5 source must stay unchanged
[NIST]
materials = G4_Galactic, G4_Si, G4_Al
[material.FirstTarget]
mode = mass_fraction
density = 2.33 g/cm3
components = G4_Si:1
[material.SecondTarget]
mode = mass_fraction
density = 2.7 g/cm3
components = G4_Al:1
"""
GEOMETRY = """# original geometry is never overwritten
[global]
version = 2
[world]
shape = box
size = 100 mm,100 mm,100 mm
material = G4_Galactic
[volume.Target]
parent = world
shape = box
size = 8 mm,8 mm,8 mm
material = FirstTarget
position = 0 mm,0 mm,0 mm
sensitive = true
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initial_state(folder: Path, executable: Path) -> tuple[WorkspaceSnapshot, tuple[Path, Path]]:
    material_path = folder / "original-materials.ini"
    geometry_path = folder / "original-geometry.ini"
    material_path.write_text(MATERIALS, encoding="utf-8", newline="\n")
    geometry_path.write_text(GEOMETRY, encoding="utf-8", newline="\n")
    material_summary = parse_materials(material_path)
    geometry_summary = parse_geometry(geometry_path, "hierarchical")
    project = G4USimProject(projectName="F5 backend transactions", executable=str(executable),
                            workspaceRoot=str(folder), runsRoot=str(folder / "packages"), seed="4242", threads=1)
    project.pathSettings = PathSettings(executable=str(executable), workspace_root=str(folder),
        runs_root=project.runsRoot, materials_config=str(material_path), geometry_config=str(geometry_path))
    project.runSettings = RunSettings(run_name="f5-transaction", threads=1, seed=4242, beam_on=EVENTS)
    project.geometrySettings = GeometrySettings(template="hierarchical", config_path=str(geometry_path))
    project.materialEditor = material_document_from_summary(material_summary)
    project.geometryEditor = geometry_document_from_summary(geometry_summary, "hierarchical")
    # Both cases exercise editor writers, while source originals stay immutable.
    project.materialEditor.is_dirty = True
    project.geometryEditor.is_dirty = True
    project.sourceEditor = SourceEditableModel(particle="e-", energy="1 MeV", position="0,0,-20 mm", direction="0,0,1")
    project.physicsEditor = PhysicsEditableModel(reference_list="FTFP_BERT", default_cut="0.1 mm")
    project.scoringEditor = ScoringEditableModel(hits=True, event_edep=True, edep=True, trajectory_events=EVENTS)
    project.sourceSettings = project.sourceEditor.to_settings()
    project.physicsSettings = project.physicsEditor.to_settings()
    project.scoringSettings = project.scoringEditor.to_settings()
    state = empty_editing_state()
    state["drafts"] = {"config.source_editor_energy": "1 MeV"}
    state["sources"] = {
        "materials": {"path": str(material_path), "text": material_summary.raw_text, "read_success": True, "template": ""},
        "geometry": {"path": str(geometry_path), "text": geometry_summary.raw_text, "read_success": True, "template": "hierarchical"},
    }
    return WorkspaceSnapshot(project, state), (material_path, geometry_path)


def change_configuration(candidate: WorkspaceSnapshot) -> None:
    project = candidate.project
    project.sourceEditor.energy = "3 MeV"
    project.sourceSettings = project.sourceEditor.to_settings()
    target = next(row for row in project.geometryEditor.volumes if row.name == "Target")
    target.material = "SecondTarget"
    target.size = "12 mm,12 mm,12 mm"
    material = next(row for row in project.materialEditor.rows if row.name == "SecondTarget")
    material.density = "3 g/cm3"
    material.is_dirty = True
    project.materialEditor.is_dirty = project.geometryEditor.is_dirty = True
    candidate.state["drafts"]["config.source_editor_energy"] = "3 MeV"


def summary_values(path: Path) -> dict[str, str]:
    return {key.strip(): value.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line for key, value in [line.split("=", 1)]}


def execute_case(executable: Path, folder: Path, snapshot: WorkspaceSnapshot, label: str,
                 energy: float, material: str, side: float, density: str) -> dict:
    project = snapshot.project
    package, _ = create_run_package(project=project, paths=project.pathSettings, run=project.runSettings,
        geometry=project.geometrySettings, source=project.sourceSettings, physics=project.physicsSettings,
        scoring=project.scoringSettings, material_document=project.materialEditor,
        geometry_document=project.geometryEditor, source_model=project.sourceEditor,
        physics_model=project.physicsEditor, scoring_model=project.scoringEditor)
    root = Path(package.package_dir)
    assert not (Path(package.output_dir) / "run_summary.txt").exists(), "A new package inherited old run evidence"
    # Append only the existing read-only actual-geometry inspection command.
    # The normal writer-generated initialization and beamOn remain unchanged.
    mesh_path = root / "actual-geometry.json"
    macro = Path(package.run_macro_path)
    normal_macro = macro.read_text(encoding="utf-8")
    assert f"/run/beamOn {EVENTS}" in normal_macro
    macro.write_text(normal_macro + f"/AIHL/geometry/exportMesh {mesh_path.as_posix()}\n", encoding="utf-8", newline="\n")
    result = subprocess.run([str(executable), "--config", package.main_ini_path, "--macro", package.run_macro_path],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    log_path = folder / f"{label}.log"
    log_path.write_text(result.stdout + result.stderr, encoding="utf-8", newline="\n")
    assert result.returncode == 0, (label, result.returncode, str(log_path), result.stdout[-3500:], result.stderr[-1500:])
    summary = summary_values(Path(package.output_dir) / "run_summary.txt")
    assert summary["status"] == summary["macro_execution_status"] == "completed", summary
    assert summary["summary_write_status"] == "completed" and summary["output_failure_status"] == "none", summary
    assert summary["run_count"] == "1", summary
    assert summary["planned_event_count"] == summary["actual_completed_event_count"] == str(EVENTS), summary
    assert summary["effective_source_particle"] == "e-", summary
    assert math.isclose(float(summary["effective_source_energy_MeV"]), energy, rel_tol=0, abs_tol=1e-12)
    assert Path(summary["effective_materials_file"]).resolve() == Path(package.materials_ini_path).resolve()
    assert Path(summary["effective_geometry_config"]).resolve() == Path(package.geometry_ini_path).resolve()
    generated_materials = parse_materials(package.materials_ini_path)
    assert next(row for row in generated_materials.materials if row.name == material).density == density
    mesh = load_backend_mesh(mesh_path)
    targets = [volume for volume in mesh.volumes if volume.name == "Target_PV"]
    assert len(targets) == 1, [volume.name for volume in mesh.volumes]
    target = targets[0]
    assert target.material == material and target.sensitive, target
    assert math.isclose(target.cubic_volume_mm3, side ** 3, rel_tol=1e-12, abs_tol=1e-9), target
    extents = [max(point[axis] for point in target.vertices) - min(point[axis] for point in target.vertices) for axis in range(3)]
    assert all(math.isclose(extent, side, rel_tol=0, abs_tol=1e-9) for extent in extents), extents
    trajectories = sorted(Path(package.output_dir).glob("trajectories_t*.json"))
    assert trajectories, "No actual primary trajectory evidence"
    events = []
    for path in trajectories:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["schema"] == "g4usim_trajectories_v1" and document["run"] == 0, document.keys()
        events.extend(document["events"])
    assert sorted(event["event"] for event in events) == list(range(EVENTS)), events
    initial_energies = []
    for event in events:
        primaries = [track for track in event["tracks"] if track["parent"] == 0]
        assert len(primaries) == 1 and primaries[0]["particle"] == "e-" and primaries[0]["creator"] == "primary"
        assert math.isclose(primaries[0]["initial_energy"], energy, rel_tol=0, abs_tol=1e-9), primaries[0]
        initial_energies.append(primaries[0]["initial_energy"])
    return {"case": label, "package": str(root), "completed_events": int(summary["actual_completed_event_count"]),
            "source_energy_MeV": energy, "observed_primary_energies_MeV": initial_energies,
            "actual_target_material": target.material, "actual_target_volume_mm3": target.cubic_volume_mm3,
            "actual_target_extents_mm": extents, "generated_material_density": density,
            "main_sha256": digest(Path(package.main_ini_path)), "macro_sha256": digest(macro),
            "materials_sha256": digest(Path(package.materials_ini_path)),
            "geometry_sha256": digest(Path(package.geometry_ini_path)), "log": str(log_path),
            "scope": "configuration and actual consumer selection; not a physics-accuracy benchmark"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE"))
    args = parser.parse_args()
    assert args.executable, "Set G4USIM_EXE or --executable to a built backend"
    executable = Path(args.executable).resolve()
    assert executable.is_file(), executable
    with ExitStack() as stack:
        requested = os.environ.get("G4USIM_TEST_WORK")
        folder = Path(requested).resolve() if requested else Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="f5-transaction-backend-")))
        folder.mkdir(parents=True, exist_ok=True)
        initial, originals = initial_state(folder, executable)
        original_hashes = {str(path): digest(path) for path in originals}
        session = EditSession(initial)
        session.transact("Change energy, material and target size", change_configuration, expected_revision=0)
        assert session.revision == 1 and session.current().project.sourceEditor.energy == "3 MeV"
        edited_digest = snapshot_fingerprint(session.current())
        session.undo()
        assert session.revision == 2 and not session.is_modified and session.can_redo
        # A real persisted file, then a fresh snapshot/session: not merely a
        # deepcopy or reuse of the original project object.
        saved = folder / "after-undo.edit-snapshot.json"
        saved.write_bytes(snapshot_to_json(session.current()))
        recovered = snapshot_from_json(saved.read_bytes())
        recovered_session = EditSession(recovered, saved=False)
        assert recovered_session.is_modified and not recovered_session.can_undo
        assert snapshot_fingerprint(recovered) == snapshot_fingerprint(initial)
        first = execute_case(executable, folder, recovered_session.current(), "undo-restored", 1.0, "FirstTarget", 8.0, "2.33 g/cm3")
        assert {str(path): digest(path) for path in originals} == original_hashes
        session.redo()
        assert session.revision == 3 and snapshot_fingerprint(session.current()) == edited_digest
        second = execute_case(executable, folder, session.current(), "redo-edited", 3.0, "SecondTarget", 12.0, "3 g/cm3")
        assert first["package"] != second["package"]
        assert first["geometry_sha256"] != second["geometry_sha256"]
        assert first["materials_sha256"] != second["materials_sha256"]
        assert {str(path): digest(path) for path in originals} == original_hashes
        report = {"schema": "g4usim_f5_transactions_backend_evidence_v1", "executable": str(executable),
                  "executable_sha256": digest(executable), "original_source_sha256": original_hashes,
                  "persisted_snapshot_sha256": digest(saved), "cases": [first, second]}
        evidence = folder / "f5-backend-evidence.json"
        evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        assert json.loads(evidence.read_text(encoding="utf-8"))["cases"][1]["completed_events"] == EVENTS
        print(f"F5 real backend passed: undo + persisted recovery and redo, {EVENTS} + {EVENTS} completed events; {evidence}")


if __name__ == "__main__":
    main()
