"""Known package snapshots restore current inputs without relaxing normal JSON IO."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.project import G4USimProject, load_project, load_project_snapshot, save_project
from g4usim_gui.core.project_migration import plan_project_migration
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import MaterialRow, material_document_from_summary
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel, PhysicsEditableModel, ScoringEditableModel
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.history.run_package_actions import duplicate_package


def rejected(action, fragment=""):
    try:
        action()
    except (ValueError, OSError) as error:
        assert fragment in str(error), str(error)
    else:
        assert False, "Unsupported or ambiguous snapshot accepted"


def build_package_fixture(work: Path, executable: Path | None = None):
    if executable is None:
        executable = work / "G4UniversalSim-not-executed"
        executable.write_text("static writer fixture only; this file is never run", encoding="utf-8")
    material_file = work / "source-materials.ini"
    material_file.write_text("[NIST]\nmaterials = G4_AIR, G4_Si, G4_O\n", encoding="utf-8")
    materials = material_document_from_summary(parse_materials(material_file))
    materials.rows.extend((
        MaterialRow(name="ActiveMix", mode="mass_fraction", density="2 g/cm3", components_text="G4_Si:0.7\nG4_O:0.3", is_dirty=True),
        MaterialRow(enabled=False, name="UnwrittenDraft", mode="mass_fraction", density="3 g/cm3", components_text="G4_Si:1", is_dirty=True),
    ))
    materials.is_dirty = True
    geometry_file = work / "source-geometry.ini"
    geometry_file.write_text("[world]\nshape=box\nsize=100 mm,100 mm,100 mm\nmaterial=G4_AIR\n"
                             "[volume.Target]\nparent=world\nshape=box\nsize=10 mm,10 mm,10 mm\nmaterial=ActiveMix\nsensitive=true\n", encoding="utf-8")
    geometry = geometry_document_from_summary(parse_geometry(geometry_file, "hierarchical"), "hierarchical")
    next(row for row in geometry.volumes if row.name == "Target").size = "12 mm,14 mm,16 mm"
    geometry.is_dirty = True
    source = SourceEditableModel(particle="proton", energy="5 MeV", position="0,0,-20 mm", direction="0,0,1")
    physics = PhysicsEditableModel(reference_list="FTFP_BERT", default_cut="1 mm")
    scoring = ScoringEditableModel(hits=False, event_edep=True, edep=True, dose=True,
                                   raw_histogram=True, weighted_histogram=False)
    run = RunSettings(run_name="snapshot_fixture", threads=1, seed=12345, beam_on=2)
    paths = PathSettings(executable=str(executable), workspace_root=str(ROOT), runs_root=str(work / "runs"),
                         materials_config=str(material_file), geometry_config=str(geometry_file))
    settings = GeometrySettings(template="hierarchical", config_path=str(geometry_file))
    project = G4USimProject(projectName="snapshot fixture", executable=str(executable), workspaceRoot=str(ROOT),
                            runsRoot=paths.runs_root, threads=64, seed="999", runName="stale-mirror")
    package, _ = create_run_package(project=project, paths=paths, run=run, geometry=settings,
                                    source=source.to_settings(), physics=physics.to_settings(), scoring=scoring.to_settings(),
                                    material_document=materials, geometry_document=geometry,
                                    source_model=source, physics_model=physics, scoring_model=scoring)
    return package, (material_file, geometry_file)


def regenerate_project(project):
    return create_run_package(project=project, paths=project.pathSettings, run=project.runSettings,
                              geometry=project.geometrySettings, source=project.sourceSettings,
                              physics=project.physicsSettings, scoring=project.scoringSettings,
                              geometry_document=project.geometryEditor, source_model=project.sourceEditor,
                              physics_model=project.physicsEditor, scoring_model=project.scoringEditor)[0]


def main():
    with tempfile.TemporaryDirectory(prefix="e6-snapshot-compat-") as directory:
        work = Path(directory)
        package, originals = build_package_fixture(work)
        snapshot = Path(package.project_snapshot_path)
        original_snapshot = snapshot.read_bytes()
        data = json.loads(original_snapshot)
        # Original source inputs are no longer authoritative after generation.
        for path in originals:
            path.write_text("changed outside the package", encoding="utf-8")
        restored = load_project_snapshot(snapshot)
        project = restored.project
        assert project.threads == project.runSettings.threads == 1
        assert project.seed == "12345" and project.runName == "snapshot_fixture"
        assert project.runInputMode == "generated" and project.configPath == project.macroPath == project.outputDir == ""
        assert project.pathSettings.materials_config == package.materials_ini_path
        assert project.geometrySettings.config_path == package.geometry_ini_path
        assert next(row for row in project.geometryEditor.volumes if row.name == "Target").size == "12 mm,14 mm,16 mm"
        assert project.sourceEditor.energy == "5 MeV" and project.sourceEditor.particle == "proton"
        assert any("drafts" in note for note in restored.notes) and any("no original resource hashes" in note for note in restored.notes)
        assert len(restored.inputs) == 4 and all(len(item.sha256) == 64 for item in restored.inputs)
        ordinary = work / "restored-project.json"
        save_project(project, ordinary)
        reloaded = load_project(ordinary)
        regenerated = regenerate_project(reloaded)
        assert Path(regenerated.materials_ini_path).read_bytes() == Path(package.materials_ini_path).read_bytes()
        assert Path(regenerated.geometry_ini_path).read_bytes() == Path(package.geometry_ini_path).read_bytes()
        assert snapshot.read_bytes() == original_snapshot
        rejected(lambda: load_project(snapshot), "runPackage")
        rejected(lambda: plan_project_migration(snapshot), "runPackage")
        duplicate = Path(duplicate_package(package.package_dir, str(work / "duplicates")))
        real_read = Path.read_bytes
        source_package_root = Path(package.package_dir)
        def only_duplicate_reads(path):
            assert not path.is_relative_to(source_package_root), "real duplicate must not fall back to original package"
            return real_read(path)
        with patch.object(Path, "read_bytes", new=only_duplicate_reads):
            copied = load_project_snapshot(duplicate / "project_snapshot.json")
        assert all(Path(item.path).is_relative_to(duplicate) for item in copied.inputs)
        assert copied.project.pathSettings.materials_config == str(duplicate / "config/materials/material.ini")
        assert copied.project.runsRoot == str(duplicate.parent)
        copied_regenerated = regenerate_project(copied.project)
        assert Path(copied_regenerated.materials_ini_path).read_bytes() == Path(package.materials_ini_path).read_bytes()
        # Current package files, rather than lossy original document summaries,
        # are the defined restoration authority. This is not a historical hash.
        geometry_current = Path(package.geometry_ini_path)
        previous_geometry = geometry_current.read_bytes()
        geometry_current.write_bytes(previous_geometry.replace(b"12 mm,14 mm,16 mm", b"13 mm,14 mm,16 mm"))
        now = load_project_snapshot(snapshot)
        assert next(row for row in now.project.geometryEditor.volumes if row.name == "Target").size == "13 mm,14 mm,16 mm"
        geometry_current.write_bytes(previous_geometry)

        def attempt(value, fragment=""):
            snapshot.write_text(json.dumps(value), encoding="utf-8")
            raw = snapshot.read_bytes()
            rejected(lambda: load_project_snapshot(snapshot), fragment)
            assert snapshot.read_bytes() == raw

        for mutate, fragment in (
            (lambda value: value.update(futureMetadata={}), "Unsupported snapshot field"),
            (lambda value: value.update(version=7), "Unsupported project version"),
            (lambda value: value["runPackage"].update(future_path="x"), "future_path"),
            (lambda value: value["materialsSummary"].update(count=999), "count"),
            (lambda value: value["materialDocument"]["rows"][0].update(future_recipe="x"), "future_recipe"),
            (lambda value: value["materialDocument"].update(enabledCount=0), "counts"),
            (lambda value: value["geometryDocument"].update(source_copy_mode="false"), "source_copy_mode"),
            (lambda value: value["geometrySummary"]["volumes"][0].update(sensitive=0), "sensitive"),
            (lambda value: value["runPackage"].update(main_ini_path=str(work / "outside.ini")), "contradicts"),
            (lambda value: value["runPackage"].update(materials_ini_path=str(work / "old/config/materials/material.ini")), "single contradictory"),
            (lambda value: value["runPackage"].update(materials_ini_path=str(work / "old/config/materials/material.ini"),
                                                     geometry_ini_path=str(work / "different/config/geometry/geometry.ini")), "one old"),
        ):
            invalid = copy.deepcopy(data); mutate(invalid); attempt(invalid, fragment)
        for raw in (original_snapshot.replace(b'"version": 6', b'"version": 6, "version": 6', 1),
                    original_snapshot.replace(b'"threads": 64', b'"threads": NaN', 1)):
            snapshot.write_bytes(raw)
            rejected(lambda: load_project_snapshot(snapshot))
        snapshot.write_bytes(original_snapshot)
        material = Path(package.materials_ini_path)
        saved = material.read_bytes()
        material.unlink()
        rejected(lambda: load_project_snapshot(snapshot), "missing")
        material.write_bytes(saved)
        old = work / "deleted-old-package"
        legacy = copy.deepcopy(data)
        legacy["runPackage"]["materials_ini_path"] = str(old / "config/materials/material.ini")
        legacy["runPackage"]["geometry_ini_path"] = str(old / "config/geometry/geometry.ini")
        snapshot.write_text(json.dumps(legacy), encoding="utf-8")
        real_read = Path.read_bytes
        def no_old_reads(path):
            assert not path.is_relative_to(old), "old package must never be read"
            return real_read(path)
        with patch.object(Path, "read_bytes", new=no_old_reads):
            assert any("Legacy duplicate" in note for note in load_project_snapshot(snapshot).notes)
        snapshot.write_bytes(original_snapshot)
        # Exercise the symlink-escape resolver branch without requiring Windows
        # symlink privileges. Linux/Windows filesystem ownership is unchanged.
        real_resolve = Path.resolve
        def escape(path, *args, **kwargs):
            return work / "outside-resource.ini" if path == material else real_resolve(path, *args, **kwargs)
        with patch.object(Path, "resolve", new=escape):
            rejected(lambda: load_project_snapshot(snapshot), "symbolic link")
        legacy_plain = work / "legacy-v1.json"
        legacy_plain.write_text('{"schema":"G4UniversalSimProject","version":1,"macroPath":"old.mac"}', encoding="utf-8")
        plain = load_project_snapshot(legacy_plain)
        assert plain.project.macroPath == "old.mac" and not plain.inputs and not plain.package_root
        assert "not verified" in plain.notes[0]
        legacy_plain.write_text('{"version":1,"materialDocument":{}}', encoding="utf-8")
        rejected(lambda: load_project_snapshot(legacy_plain), "Incomplete")
    print("Project snapshot adapter: actual writer/current-input/save/reload/regenerate and refusal contracts passed")


if __name__ == "__main__":
    main()
