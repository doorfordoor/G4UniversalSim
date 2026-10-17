from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.editors.geometry_editor_model import (
    GeometryDocument,
    geometry_document_from_dict,
    geometry_document_to_snapshot,
)
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
)


SCHEMA_NAME = "G4UniversalSimProject"
SCHEMA_VERSION = 6
RUN_INPUT_MODES = {"generated", "external"}


@dataclass
class G4USimProject:
    """Serializable GUI state for the external G4UniversalSim runner."""

    schema: str = SCHEMA_NAME
    version: int = SCHEMA_VERSION
    projectName: str = "demo"
    runInputMode: str = "generated"
    executable: str = ""
    workspaceRoot: str = ""
    configPath: str = ""
    macroPath: str = ""
    outputDir: str = ""
    runsRoot: str = ""
    threads: int = 1
    seed: str = ""
    runName: str = ""
    runSettings: RunSettings = field(default_factory=RunSettings)
    pathSettings: PathSettings = field(default_factory=PathSettings)
    geometrySettings: GeometrySettings = field(default_factory=GeometrySettings)
    sourceSettings: SourceSettings = field(default_factory=SourceSettings)
    physicsSettings: PhysicsSettings = field(default_factory=PhysicsSettings)
    scoringSettings: ScoringSettings = field(default_factory=ScoringSettings)
    sourceEditor: SourceEditableModel = field(default_factory=SourceEditableModel)
    physicsEditor: PhysicsEditableModel = field(default_factory=PhysicsEditableModel)
    scoringEditor: ScoringEditableModel = field(default_factory=ScoringEditableModel)
    geometryEditor: GeometryDocument = field(default_factory=GeometryDocument)


def project_to_dict(project: G4USimProject) -> dict[str, Any]:
    data = asdict(project)
    data["schema"] = SCHEMA_NAME
    data["version"] = SCHEMA_VERSION
    data["geometryEditor"] = geometry_document_to_snapshot(project.geometryEditor)
    return data


def project_from_dict(data: dict[str, Any]) -> G4USimProject:
    if data.get("schema", SCHEMA_NAME) != SCHEMA_NAME:
        raise ValueError("Unsupported project schema")

    allowed = set(G4USimProject.__dataclass_fields__.keys())
    filtered = {key: value for key, value in data.items() if key in allowed}
    if "runInputMode" not in data:
        filtered["runInputMode"] = "external" if data.get("configPath") or data.get("macroPath") else "generated"
    for key, cls in [
        ("runSettings", RunSettings),
        ("pathSettings", PathSettings),
        ("geometrySettings", GeometrySettings),
        ("sourceSettings", SourceSettings),
        ("physicsSettings", PhysicsSettings),
        ("scoringSettings", ScoringSettings),
        ("sourceEditor", SourceEditableModel),
        ("physicsEditor", PhysicsEditableModel),
        ("scoringEditor", ScoringEditableModel),
    ]:
        if isinstance(filtered.get(key), dict):
            cls_fields = set(cls.__dataclass_fields__.keys())
            filtered[key] = cls(**{field: value for field, value in filtered[key].items() if field in cls_fields})
    if isinstance(filtered.get("geometryEditor"), dict):
        filtered["geometryEditor"] = geometry_document_from_dict(filtered["geometryEditor"])
    has_source_editor = "sourceEditor" in data
    has_physics_editor = "physicsEditor" in data
    has_scoring_editor = "scoringEditor" in data
    project = G4USimProject(**filtered)
    if project.runInputMode not in RUN_INPUT_MODES:
        raise ValueError(f"Unsupported runInputMode: {project.runInputMode}")
    if not isinstance(project.threads, int):
        project.threads = int(project.threads)
    if project.threads <= 0:
        project.threads = 1
    if project.seed is None:
        project.seed = ""

    # Backward compatibility with Round 7B flat project JSON.
    if not project.pathSettings.executable:
        project.pathSettings.executable = project.executable
    if not project.pathSettings.workspace_root:
        project.pathSettings.workspace_root = project.workspaceRoot
    if not project.pathSettings.runs_root:
        project.pathSettings.runs_root = project.runsRoot
    if not project.runSettings.run_name.strip():
        project.runSettings.run_name = project.runName or project.projectName
    if project.runSettings.threads == 1 and project.threads != 1:
        project.runSettings.threads = project.threads
    if project.runSettings.seed is None and project.seed:
        project.runSettings.seed = int(project.seed)
    if not has_source_editor or not project.sourceEditor.particle:
        project.sourceEditor = SourceEditableModel.from_settings(project.sourceSettings)
    if not has_physics_editor or not project.physicsEditor.reference_list:
        project.physicsEditor = PhysicsEditableModel.from_settings(project.physicsSettings)
    if not has_scoring_editor or project.scoringEditor.hist_bins <= 0:
        project.scoringEditor = ScoringEditableModel.from_settings(project.scoringSettings)
    return project


def load_project(path: str | Path) -> G4USimProject:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Project JSON root must be an object")
    return project_from_dict(data)


def save_project(project: G4USimProject, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(project_to_dict(project), handle, indent=2, ensure_ascii=False)
        handle.write("\n")
