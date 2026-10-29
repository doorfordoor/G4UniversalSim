"""File-only acceptance resources: never create Qt windows or start a process."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
EXPECTED = "a779634483d1f077357433c532ccb0d9e3dc5517"
EXE = ROOT / "out/build-e6/Release/G4UniversalSim.exe"
sys.path.insert(0, str(ROOT / "gui"))

def no_process(event, args):
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "os.startfile"}:
        raise RuntimeError("Preparation forbids process/desktop launch: " + event)
sys.addaudithook(no_process)

from g4usim_gui.core.project import G4USimProject, project_to_dict, load_project_snapshot
from g4usim_gui.core.project_migration import plan_project_migration
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import MaterialRow, material_document_from_summary
from g4usim_gui.editors.source_physics_scoring_model import PhysicsEditableModel, ScoringEditableModel, SourceEditableModel
from g4usim_gui.history.run_package_actions import read_generated_run_settings
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.writers.package_writer import create_run_package

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def fixture_function(file, name):
    source = (ROOT / "gui/smoke_tests" / file).read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    snippet = ast.get_source_segment(source, node).replace("sys.executable", "str(EXE)")
    # Visible acceptance candidate uses two events, not the test's 23-event setting.
    if name == "make_package":
        snippet = snippet.replace("beam_on=23", "beam_on=2")
    exec(compile(snippet, str(file) + ":file-only-fixture", "exec"), globals())
    return globals()[name]

if (BASE / "resources").exists():
    raise SystemExit("Resources already exist; inspect manifest before any retry.")
resources = BASE / "resources"
resources.mkdir()
migration = resources / "migration"
migration.mkdir()
project = G4USimProject(projectName="a779 acceptance", executable=str(EXE), workspaceRoot=str(ROOT),
                        runsRoot=str(resources / "ui-created-runs"))
old = project_to_dict(project)
old["version"] = 5
source = migration / "legacy-v5.json"
write_json(source, old)
write_json(migration / "occupied-target.json", {"sentinel": "must not be overwritten"})
os.link(source, migration / "source-hardlink.json")
write_json(migration / "future-version.json", {**old, "version": 999})
(migration / "malformed.json").write_text('{"version":5,', encoding="utf-8")
write_json(migration / "projection-overflow.json", {**old, "threads": 10**100})
plan = plan_project_migration(source)
write_json(migration / "preview-reference.json", {"input_version": plan.input_version,
           "output_version": plan.output_version, "changes": plan.changes, "validation": plan.validation,
           "source_sha256": plan.source_sha256, "payload_sha256": hashlib.sha256(plan.payload).hexdigest()})

snapshot_root = resources / "snapshot"
snapshot_root.mkdir()
package, original_materials, original_geometry = fixture_function("smoke_project_snapshot_restore.py", "make_package")(snapshot_root)
restored = load_project_snapshot(package.project_snapshot_path)
snapshot_record = {"package": package.package_dir, "snapshot": package.project_snapshot_path,
                   "notes": restored.notes, "source_files": [str(original_materials), str(original_geometry)],
                   "file_only_loader_check": "passed", "event_count_candidate": 2}
# Change external originals after writer output; copied package resources stay authoritative.
original_materials.write_text("[material.ChangedExternal]\ndensity=1 g/cm3\n", encoding="utf-8")
original_geometry.write_text("[global]\nversion=2\n", encoding="utf-8")

duplicate_root = resources / "duplicate"
duplicate_root.mkdir()
make_duplicate = fixture_function("smoke_duplicate_history_cli.py", "package_fixture")
cases = []
for label, seed in (("seed43",43), ("seed_omitted",None), ("seed_zero",0),
                    ("stale_snapshot",43), ("unicode_name",43), ("ascii_name",43), ("projection1025",43)):
    home = duplicate_root / label
    home.mkdir()
    candidate = make_duplicate(home, seed)
    main = Path(candidate.main_ini_path)
    text = main.read_text(encoding="utf-8")
    if label == "stale_snapshot":
        text = text.replace("threads = 2\n", "threads = 3\n").replace("seed = 43\n", "seed = 83\n").replace("name = writer_run\n", "name = actual_main_run\n")
    elif label == "unicode_name":
        text = text.replace("name = writer_run\n", "name = Alpha 名称\u3000Tail\u00a0\n")
    elif label == "ascii_name":
        text = text.replace("name = writer_run\n", "name = \t ordinary name \t \n")
    elif label == "projection1025":
        text = text.replace("threads = 2\n", "threads = 1025\n")
    main.write_text(text, encoding="utf-8")
    startup = read_generated_run_settings(candidate.package_dir)
    cases.append({"case": label, "package": candidate.package_dir, "main": candidate.main_ini_path,
                  "threads": startup.threads, "seed": startup.seed, "run_name": startup.run_name,
                  "expected_gui": "copy created; no load/run; preserve current state" if label == "projection1025" else "publish candidate; final CLI follows main"})

current = project_to_dict(project)
current.update(threads=7, seed="999", runName="unrelated_current_run")
current["runSettings"].update(threads=7, seed=999, run_name="unrelated_current_run")
write_json(resources / "current-project-7-999.json", current)
write_json(BASE / "resource-index.json", {"frozen_commit": EXPECTED, "snapshot": snapshot_record,
           "duplicate_cases": cases, "ui_or_backend_launched": False,
           "fixture_origin": "Frozen formal smoke helper bodies; only executable replaced with candidate Geant4 path and snapshot beam_on 23 changed to 2. No GUI/test main invoked."})
files = [{"path": str(p.relative_to(BASE)), "bytes": p.stat().st_size,
          "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(resources.rglob("*")) if p.is_file()]
write_json(BASE / "resource-hashes.json", files)
print(json.dumps({"resources": len(files), "duplicate_cases": len(cases), "snapshot_loader": "passed", "ui_or_backend_launched": False}))
