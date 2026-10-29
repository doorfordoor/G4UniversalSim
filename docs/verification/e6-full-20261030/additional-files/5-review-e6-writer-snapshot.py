"""Read-only product check: use the real snapshot writer, then normal loader."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/verification/e6-frontend-guard-independent"
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.project import G4USimProject, load_project
from g4usim_gui.models.package_model import RunPackage
from g4usim_gui.parsers.materials_parser import MaterialsSummary
from g4usim_gui.parsers.geometry_parser import GeometrySummary
from g4usim_gui.writers.package_writer import _write_snapshot

project = G4USimProject()
path = OUT / "real-writer-project_snapshot.json"
package = RunPackage(**{name: str(OUT / name) for name in RunPackage.__dataclass_fields__})
_write_snapshot(str(path), project, project.pathSettings, project.runSettings,
                project.geometrySettings, project.sourceSettings, project.physicsSettings,
                project.scoringSettings, package, MaterialsSummary("materials.ini"),
                GeometrySummary("geometry.ini"), None, "copied", None, "copied", None, None, None)
before = hashlib.sha256(path.read_bytes()).hexdigest()
try:
    load_project(path)
except ValueError as error:
    result = {"real_writer_snapshot_loads": False, "error": str(error)}
else:
    result = {"real_writer_snapshot_loads": True}
assert hashlib.sha256(path.read_bytes()).hexdigest() == before
result.update({"scope": "actual _write_snapshot output, not a handwritten minimal fixture; no product edits",
               "snapshot": str(path), "snapshot_sha256": before})
(OUT / "writer-snapshot-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
