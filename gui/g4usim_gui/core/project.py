from __future__ import annotations

import json
import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from g4usim_gui.core.config_migration import check_finite_json, load_json_strict
from g4usim_gui.core.project_migration import normalize_project_data, validate_dataclass_fields
from g4usim_gui.core.edit_state import validate_editing_state
from g4usim_gui.editors.material_editor_model import MaterialComponent, MaterialDocument, MaterialRow

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
SCHEMA_VERSION = 7
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
    # None means an older project has no captured editor state. An explicit
    # empty document is intentional and must never trigger a source reload.
    materialEditor: MaterialDocument | None = None
    editingState: dict[str, Any] | None = None


def project_to_dict(project: G4USimProject) -> dict[str, Any]:
    if project.editingState is not None:
        validate_editing_state(project.editingState)
    data = asdict(project)
    data["schema"] = SCHEMA_NAME
    data["version"] = SCHEMA_VERSION
    # v7 retains the complete editor document, including the source text and
    # source-error evidence needed for exact undo and crash recovery. Keep the
    # redundant legacy preview shape for known older snapshot consumers.
    geometry = asdict(project.geometryEditor)
    geometry["preview"] = {"volumes": geometry["volumes"], "boolean_ops": geometry["boolean_ops"]}
    data["geometryEditor"] = geometry
    # In-memory SourceEditableModel historically accepts position_mode alone;
    # its runtime validator treats that field as authoritative. Export the same
    # established alias meaning without mutating the caller or running validation.
    # Raw JSON declaring two different aliases is rejected before construction.
    source = data["sourceEditor"]
    if source["position_mode"].strip():
        source["position_type"] = source["position_mode"]
    elif source["position_type"].strip():
        source["position_mode"] = source["position_type"]
    validate_dataclass_fields(normalize_project_data(data), G4USimProject, "project")
    return data


def project_from_dict(data: dict[str, Any]) -> G4USimProject:
    if not isinstance(data, dict):
        raise ValueError("Project JSON root must be an object")
    if data.get("schema", SCHEMA_NAME) != SCHEMA_NAME:
        raise ValueError("Unsupported project schema")
    version = data.get("version", 1)
    if type(version) is not int or not 1 <= version <= SCHEMA_VERSION:
        raise ValueError(f"Unsupported project version: {version}")
    check_finite_json(data)
    data = normalize_project_data(data)
    validate_dataclass_fields(data, G4USimProject, "project")
    if data.get("editingState") is not None:
        validate_editing_state(data["editingState"])
    if data.get("threads", 1) <= 0:
        raise ValueError("project.threads must be positive")

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
        geometry_data = filtered["geometryEditor"]
        geometry_document = geometry_document_from_dict(geometry_data)
        for name in ("raw_source_text", "generated_path", "errors", "warnings"):
            if name in geometry_data:
                setattr(geometry_document, name, geometry_data[name])
        filtered["geometryEditor"] = geometry_document
    if isinstance(filtered.get("materialEditor"), dict):
        material_data = dict(filtered["materialEditor"])
        rows = []
        for item in material_data.pop("rows", []):
            row_data = dict(item)
            row_data["components"] = [MaterialComponent(**component) for component in row_data.get("components", [])]
            rows.append(MaterialRow(**row_data))
        filtered["materialEditor"] = MaterialDocument(rows=rows, **material_data)
    has_source_editor = "sourceEditor" in data
    has_physics_editor = "physicsEditor" in data
    has_scoring_editor = "scoringEditor" in data
    project = G4USimProject(**filtered)
    if project.runInputMode not in RUN_INPUT_MODES:
        raise ValueError(f"Unsupported runInputMode: {project.runInputMode}")

    # Backward compatibility with Round 7B flat project JSON.
    legacy_paths = version < 7 or "pathSettings" not in data
    legacy_run = version < 7 or "runSettings" not in data
    if legacy_paths and not project.pathSettings.executable:
        project.pathSettings.executable = project.executable
    if legacy_paths and not project.pathSettings.workspace_root:
        project.pathSettings.workspace_root = project.workspaceRoot
    if legacy_paths and not project.pathSettings.runs_root:
        project.pathSettings.runs_root = project.runsRoot
    if legacy_run and not project.runSettings.run_name.strip():
        project.runSettings.run_name = project.runName or project.projectName
    if legacy_run and project.runSettings.threads == 1 and project.threads != 1:
        project.runSettings.threads = project.threads
    # v7 has a complete editing state, including invalid/unfinished raw seed
    # drafts. Only legacy projects use the old flat-to-nested fallback.
    if legacy_run and project.runSettings.seed is None and project.seed:
        project.runSettings.seed = int(project.seed)
    if not has_source_editor:
        project.sourceEditor = SourceEditableModel.from_settings(project.sourceSettings)
    if not has_physics_editor:
        project.physicsEditor = PhysicsEditableModel.from_settings(project.physicsSettings)
    if not has_scoring_editor:
        project.scoringEditor = ScoringEditableModel.from_settings(project.scoringSettings)
    _check_supported_fields(data, project_to_dict(project))
    # Captured source facts cannot be waived by relabeling a modern payload as
    # an older project. Genuine legacy documents without captured text remain
    # unchanged by this helper and retain their existing source-loading path.
    from g4usim_gui.core.edit_sources import restore_source_evidence
    restore_source_evidence(project, project.editingState)
    project.version = SCHEMA_VERSION
    return project


def _check_supported_fields(source: Any, saved: Any, path: str = "project") -> None:
    """Reject data that the supported serializer would silently discard."""
    aliases = {"schemaVersion": "schema_version", "sourcePath": "source_path",
               "dirty": "is_dirty", "sourceCopyMode": "source_copy_mode",
               "sourceErrors": "source_errors", "sourceWarnings": "source_warnings",
               "validationErrors": "validation_errors", "validationWarnings": "validation_warnings",
               "roundTripBlockers": "round_trip_blockers", "legacyMetadata": "legacy_metadata",
               "simpleBox": "simple_box", "layeredDevice": "layered_device"}
    if isinstance(source, dict):
        if not isinstance(saved, dict):
            raise ValueError(f"Unsupported project object: {path}")
        for key, value in source.items():
            target = aliases.get(key, key) if path.startswith("project.geometryEditor") else key
            if target not in saved:
                raise ValueError(f"Unsupported project field: {path}.{key}")
            if target != key and target in source:
                raise ValueError(f"Conflicting project fields: {path}.{key} / {target}")
            _check_supported_fields(value, saved[target], f"{path}.{key}")
    elif isinstance(source, list):
        if not isinstance(saved, list) or len(source) != len(saved):
            raise ValueError(f"Unsupported project list: {path}")
        for index, (value, result) in enumerate(zip(source, saved)):
            _check_supported_fields(value, result, f"{path}[{index}]")


@dataclass(frozen=True)
class ProjectFileReceipt:
    """Bytes observed by this IO operation, not a claim about a later file."""

    path: str
    sha256: str


def load_project_with_receipt(path: str | Path) -> tuple[G4USimProject, ProjectFileReceipt]:
    source = Path(path).absolute()
    raw = source.read_bytes()
    data = load_json_strict(raw)
    if not isinstance(data, dict):
        raise ValueError("Project JSON root must be an object")
    return project_from_dict(data), ProjectFileReceipt(str(source), hashlib.sha256(raw).hexdigest())


def load_project(path: str | Path) -> G4USimProject:
    return load_project_with_receipt(path)[0]


def load_project_snapshot(path: str | Path):
    """Restore the explicit known run-package envelope; normal load stays strict."""
    from g4usim_gui.core.project_snapshot import load_snapshot
    return load_snapshot(path)


def save_project(project: G4USimProject, path: str | Path) -> ProjectFileReceipt:
    target = Path(path).absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=target.parent, prefix=f".{target.name}.",
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(project_to_dict(project), handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # The receipt belongs to the file being published. Reading target after
        # replace would incorrectly attribute a concurrent external edit to us.
        published_sha256 = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, target)
        # Publication is the commit point. The temporary name no longer belongs
        # to this save; cleanup cannot turn a completed save into a failure.
        temporary = None
        return ProjectFileReceipt(str(target), published_sha256)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
