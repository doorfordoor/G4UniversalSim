"""Explicit compatibility normalization and project-copy migration."""
from __future__ import annotations

import copy
from dataclasses import is_dataclass
import json
from pathlib import Path
import re
import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from g4usim_gui.core.config_migration import MigrationPlan, digest, load_json_strict

GEOMETRY_ALIASES = {
    "schemaVersion": "schema_version", "sourcePath": "source_path", "dirty": "is_dirty",
    "sourceCopyMode": "source_copy_mode", "sourceErrors": "source_errors",
    "sourceWarnings": "source_warnings", "validationErrors": "validation_errors",
    "validationWarnings": "validation_warnings", "roundTripBlockers": "round_trip_blockers",
    "legacyMetadata": "legacy_metadata", "simpleBox": "simple_box", "layeredDevice": "layered_device",
}


def same_json_value(left: Any, right: Any) -> bool:
    """Python bool/int equality is not JSON type equality."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_json_value(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_json_value(a, b) for a, b in zip(left, right))
    return left == right


def validate_dataclass_fields(data: Any, model: type, path: str) -> None:
    """Check JSON types before constructors can stringify or apply truthiness."""
    if type(data) is not dict:
        raise ValueError(f"Expected JSON object: {path}")
    hints = get_type_hints(model)
    for key, value in data.items():
        if key not in hints:
            raise ValueError(f"Unsupported project field: {path}.{key}")
        _check_json_type(value, hints[key], f"{path}.{key}")


def require_complete_dataclass(data: Any, model: type, path: str) -> None:
    """Closed complete snapshots may not replace missing data with defaults.

    Ordinary legacy project imports deliberately do not use this stronger rule.
    """
    validate_dataclass_fields(data, model, path)
    hints = get_type_hints(model)
    if set(data) != set(hints):
        raise ValueError(f"Incomplete snapshot fields: {path}")
    for key, expected in hints.items():
        _require_complete_value(data[key], expected, f"{path}.{key}")


def _require_complete_value(value: Any, expected: Any, path: str) -> None:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (types.UnionType, Union):
        for choice in args:
            try:
                _check_json_type(value, choice, path)
            except ValueError:
                continue
            _require_complete_value(value, choice, path)
            return
    elif is_dataclass(expected):
        require_complete_dataclass(value, expected, path)
    elif origin is list:
        for index, item in enumerate(value):
            _require_complete_value(item, args[0], f"{path}[{index}]")
    elif origin is dict:
        for key, item in value.items():
            _require_complete_value(item, args[1], f"{path}.{key}")


def _check_json_type(value: Any, expected: Any, path: str) -> None:
    origin, args = get_origin(expected), get_args(expected)
    if origin in (types.UnionType, Union):
        # Optional typed editor documents should retain the exact nested error
        # path; trying None after a bad component must not hide that evidence.
        if len(args) == 2 and type(None) in args:
            if value is None:
                return
            _check_json_type(value, next(choice for choice in args if choice is not type(None)), path)
            return
        for choice in args:
            try:
                _check_json_type(value, choice, path)
                return
            except ValueError:
                pass
        raise ValueError(f"Invalid JSON type at {path}; expected {expected}")
    if is_dataclass(expected):
        validate_dataclass_fields(value, expected, path)
        return
    if origin is list:
        if type(value) is not list:
            raise ValueError(f"Expected JSON array: {path}")
        for index, item in enumerate(value):
            _check_json_type(item, args[0], f"{path}[{index}]")
        return
    if origin is dict:
        if type(value) is not dict:
            raise ValueError(f"Expected JSON object: {path}")
        for key, item in value.items():
            _check_json_type(key, args[0], f"{path}.<key>")
            _check_json_type(item, args[1], f"{path}.{key}")
        return
    if expected is Any:
        return
    if type(value) is not expected:
        raise ValueError(f"Invalid JSON type at {path}; expected {getattr(expected, '__name__', str(expected))}")


def normalize_geometry_data(data: dict[str, Any]) -> dict[str, Any]:
    geometry = copy.deepcopy(data)
    if isinstance(geometry, dict):
        for old, new in GEOMETRY_ALIASES.items():
            if old in geometry:
                if new in geometry:
                    raise ValueError(f"Conflicting project fields: project.geometryEditor.{old} / {new}")
                geometry[new] = geometry.pop(old)
        if "preview" in geometry:
            preview = geometry.pop("preview")
            if not isinstance(preview, dict):
                raise ValueError("Unsupported project object: project.geometryEditor.preview")
            for key, value in preview.items():
                if key not in {"volumes", "boolean_ops"}:
                    raise ValueError(f"Unsupported project field: project.geometryEditor.preview.{key}")
                if key in geometry:
                    # v6 snapshots deliberately retain a redundant preview for
                    # old readers. Only identical representations are safe.
                    if not same_json_value(geometry[key], value):
                        raise ValueError(f"Conflicting project fields: project.geometryEditor.preview.{key} / {key}")
                else:
                    geometry[key] = value
        version = geometry.get("schema_version")
        if type(version) is str and version in {"1", "2"}:
            geometry["schema_version"] = int(version)
    return geometry


def normalize_project_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize only enumerated legacy shapes, never discard unknown data."""
    result = copy.deepcopy(data)
    if isinstance(result.get("geometryEditor"), dict):
        result["geometryEditor"] = normalize_geometry_data(result["geometryEditor"])
    source = result.get("sourceEditor")
    if isinstance(source, dict):
        has_mode, has_type = "position_mode" in source, "position_type" in source
        if has_mode and has_type:
            if not same_json_value(source["position_mode"], source["position_type"]):
                raise ValueError("Conflicting project fields: project.sourceEditor.position_mode / position_type")
        elif has_mode:
            source["position_type"] = source["position_mode"]
        elif has_type:
            source["position_mode"] = source["position_type"]
    # These two flat Round-7B compatibility conversions predate E6. Do not
    # extend them to nested fields, fractional numbers, booleans or null paths.
    if type(result.get("threads")) is str:
        value = result["threads"].strip()
        if not re.fullmatch(r"[+-]?[0-9]+", value):
            raise ValueError("Invalid integer string: project.threads")
        result["threads"] = int(value)
    if "seed" in result and result["seed"] is None:
        result["seed"] = ""
    return result


def plan_project_migration(source: str | Path) -> MigrationPlan:
    from g4usim_gui.core.project import SCHEMA_VERSION, project_from_dict, project_to_dict
    path = Path(source).resolve(strict=True)
    raw = path.read_bytes()
    original = load_json_strict(raw)
    project = project_from_dict(original)
    result = project_to_dict(project)
    changes = [f"Project version {original.get('version', 1)} -> {SCHEMA_VERSION}"]
    normalized = normalize_project_data(original)
    if not same_json_value(original.get("geometryEditor"), normalized.get("geometryEditor")):
        changes.append("Normalize enumerated geometry aliases and legacy preview rows")
    if not same_json_value(original.get("sourceEditor"), normalized.get("sourceEditor")):
        changes.append("Derive the missing source position alias from the explicitly supplied position field")
    if "runInputMode" not in original:
        changes.append("Record the existing generated/external compatibility decision")
    changes.append("Serialize the supported project model; retain existing path strings and loading semantics")
    return MigrationPlan("project", str(path), digest(raw), original.get("version"), SCHEMA_VERSION,
                         tuple(changes), ("Supported JSON structure and known compatibility rules checked",
                                          "No backend configuration, simulation, or physics validation performed"),
                         (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
