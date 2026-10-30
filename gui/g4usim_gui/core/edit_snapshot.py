"""Isolated editor snapshots, without Qt, processes or implicit file reads."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from g4usim_gui.core.config_migration import load_json_strict
from g4usim_gui.core.edit_state import copy_editing_state, validate_editing_state
from g4usim_gui.core.project import G4USimProject, SCHEMA_VERSION, project_from_dict, project_to_dict
from g4usim_gui.core.project_migration import normalize_project_data, require_complete_dataclass, validate_dataclass_fields

SNAPSHOT_SCHEMA = "g4usim_edit_snapshot_v1"
SNAPSHOT_VERSION = 1
MAX_SNAPSHOT_BYTES = 24 * 1024 * 1024


@dataclass
class WorkspaceSnapshot:
    """Data captured by the UI; histories clone on every ownership boundary.

    transient may contain already-read parser summaries/typed source records.
    It never enters the persistent codec, fingerprints or recovered trust.
    """

    project: G4USimProject
    state: dict[str, Any] | None = None
    transient: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.project) is not G4USimProject:
            raise ValueError("Workspace snapshot requires a G4USimProject")
        self.project = copy.deepcopy(self.project)
        self.state = copy_editing_state(self.project.editingState if self.state is None else self.state)
        self.project.editingState = copy.deepcopy(self.state)
        from g4usim_gui.core.edit_sources import restore_source_evidence
        restore_source_evidence(self.project, self.state)
        if type(self.transient) is not dict:
            raise ValueError("Workspace snapshot transient context must be a dictionary")
        self.transient = copy.deepcopy(self.transient)

    @property
    def materials(self):
        return self.project.materialEditor


EditSnapshot = WorkspaceSnapshot


def clone_snapshot(snapshot: WorkspaceSnapshot) -> WorkspaceSnapshot:
    if type(snapshot) is not WorkspaceSnapshot:
        raise ValueError("Expected WorkspaceSnapshot")
    return WorkspaceSnapshot(snapshot.project, snapshot.state, snapshot.transient)


def snapshot_to_dict(snapshot: WorkspaceSnapshot) -> dict[str, Any]:
    if type(snapshot) is not WorkspaceSnapshot:
        raise ValueError("Expected WorkspaceSnapshot")
    validate_editing_state(snapshot.state)
    project = project_to_dict(snapshot.project)
    # Store the editing state once in the snapshot envelope. Ordinary project
    # saves use the same state under project.editingState.
    project["editingState"] = None
    validate_dataclass_fields(normalize_project_data(project), G4USimProject, "snapshot.project")
    result = {"schema": SNAPSHOT_SCHEMA, "version": SNAPSHOT_VERSION,
              "project": project, "state": copy.deepcopy(snapshot.state)}
    _encoded(result)
    return result


def _encoded(data: dict[str, Any]) -> bytes:
    try:
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"Invalid workspace snapshot data: {exc}") from exc
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Workspace snapshot exceeds size limit")
    return raw


def snapshot_to_json(snapshot: WorkspaceSnapshot) -> bytes:
    return _encoded(snapshot_to_dict(snapshot)) + b"\n"


def snapshot_from_json(raw: bytes | str) -> WorkspaceSnapshot:
    if type(raw) not in (bytes, str):
        raise ValueError("Workspace snapshot JSON must be bytes or text")
    if len(raw if isinstance(raw, bytes) else raw.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Workspace snapshot exceeds size limit")
    return snapshot_from_dict(load_json_strict(raw))


def snapshot_from_dict(data: Any) -> WorkspaceSnapshot:
    if type(data) is not dict or set(data) != {"schema", "version", "project", "state"}:
        raise ValueError("Invalid workspace snapshot fields")
    if data["schema"] != SNAPSHOT_SCHEMA or type(data["version"]) is not int or data["version"] != SNAPSHOT_VERSION:
        raise ValueError("Unsupported workspace snapshot version/schema")
    _encoded(data)
    validate_editing_state(data["state"], "snapshot.state")
    if type(data["project"]) is not dict or data["project"].get("editingState") is not None:
        raise ValueError("Snapshot project contains duplicate editing state")
    if set(data["project"]) != set(G4USimProject.__dataclass_fields__):
        raise ValueError("Incomplete or unknown workspace project fields")
    if type(data["project"]["version"]) is not int or data["project"]["version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported workspace project version")
    require_complete_dataclass(normalize_project_data(data["project"]), G4USimProject, "snapshot.project")
    # The source context belongs to the same envelope; supply it while rebuilding
    # source constraints so the ordinary-project fallback cannot guess a template.
    project_data = dict(data["project"], editingState=data["state"])
    project = project_from_dict(project_data)
    return WorkspaceSnapshot(project, data["state"])


def _semantic(value: Any) -> Any:
    if isinstance(value, dict):
        # Validation text and generated path labels are derived views. Source
        # errors, source-copy and document is_dirty remain writer semantics.
        ignored = {"errors", "warnings", "validation_errors", "validation_warnings", "generated_path"}
        return {key: _semantic(item) for key, item in value.items() if key not in ignored}
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


def snapshot_fingerprint(snapshot: WorkspaceSnapshot) -> str:
    data = snapshot_to_dict(snapshot)
    data["state"]["selections"] = {}
    return hashlib.sha256(_encoded(_semantic(data))).hexdigest()


def snapshot_size(snapshot: WorkspaceSnapshot) -> int:
    return len(_encoded(snapshot_to_dict(snapshot)))


def project_for_snapshot(snapshot: WorkspaceSnapshot) -> G4USimProject:
    """Exact ordinary-save payload; no legacy loader, normalization or IO."""
    result = copy.deepcopy(snapshot.project)
    result.editingState = copy_editing_state(snapshot.state)
    return result
