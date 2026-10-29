"""Bounded, atomic reader for backend EffectiveConfig snapshots (no Qt)."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
SCHEMA = "g4usim_effective_config_v1"
MISSING = object()


class SnapshotError(ValueError):
    pass


def _reject(message: str) -> None:
    raise SnapshotError(message)


def _integer(value: object, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= 2**63 - 1


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _reject(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_snapshot(text: str) -> dict:
    if len(text.encode("utf-8")) > MAX_BYTES:
        _reject("Snapshot exceeds 4 MiB limit")
    try:
        data = json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=lambda v: _reject(f"Non-finite JSON number: {v}"))
    except (ValueError, RecursionError) as exc:
        raise SnapshotError(str(exc)) from exc
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            _reject("Non-finite JSON number")
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)
    try:
        finite(data)
    except RecursionError as exc:
        raise SnapshotError("Snapshot nesting exceeds reader limit") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        _reject("Unsupported EffectiveConfig schema")
    if not isinstance(data.get("stage"), str) or data["stage"] not in {"configure", "run_begin", "finalization"}:
        _reject("Invalid snapshot stage")
    if not _integer(data.get("revision")):
        _reject("Invalid snapshot revision")
    if "run_id" not in data or (data["run_id"] is not None and not _integer(data["run_id"])):
        _reject("Invalid run_id")
    if data["stage"] == "run_begin" and data["run_id"] is None:
        _reject("run_begin requires run_id")
    if not isinstance(data.get("fields"), list):
        _reject("Missing fields array")
    seen = set()
    for field in data["fields"]:
        if not isinstance(field, dict):
            _reject("Invalid field object")
        path = field.get("path")
        if not isinstance(path, str) or not path.startswith("/") or re.search(r"[\x00-\x1f]|~(?![01])", path):
            _reject("Invalid canonical path")
        tokens = path.split("/")[1:]
        if not all(tokens) or not (len(tokens) == 2 or (len(tokens) == 4 and tokens[1] == "objects")):
            _reject("Invalid canonical path shape")
        if path in seen:
            _reject(f"Duplicate canonical path: {path}")
        seen.add(path)
        for key in ("unit", "reason", "evidence_source"):
            if key in field and not isinstance(field[key], str):
                _reject(f"Invalid {key}: {path}")
        status = field.get("application_status", "unknown")
        evidence = field.get("evidence_level", "none")
        if not isinstance(status, str) or status not in {"not_applied", "applied", "unknown", "failed"}:
            _reject(f"Invalid application_status: {path}")
        if not isinstance(evidence, str) or evidence not in {"none", "manager_accepted", "kernel_constructed", "thread_applied", "run_validated"}:
            _reject(f"Invalid evidence_level: {path}")
        if not _integer(field.get("revision"), 1) or field["revision"] > data["revision"]:
            _reject(f"Invalid field revision: {path}")
        if "configuration_generation" in field and not _integer(field["configuration_generation"]):
            _reject(f"Invalid configuration_generation: {path}")
        applied = field.get("applied_revision")
        if applied is not None and (not _integer(applied, 1) or applied > field["revision"]):
            _reject(f"Invalid applied_revision: {path}")
        if status == "applied":
            if applied is None or evidence in {"none", "manager_accepted"} or not field.get("evidence_source"):
                _reject(f"Applied field lacks runtime evidence: {path}")
        elif applied is not None:
            _reject(f"Non-applied field claims applied_revision: {path}")
        origins = field.get("origins", [])
        if not isinstance(origins, list):
            _reject(f"Invalid origins: {path}")
        for origin in origins:
            if not isinstance(origin, dict):
                _reject(f"Invalid origin: {path}")
            for key in ("kind", "file", "section", "key", "raw", "alias", "input_sha256", "disposition"):
                if key in origin and not isinstance(origin[key], str):
                    _reject(f"Invalid origin {key}: {path}")
            if "line" in origin and not _integer(origin["line"]):
                _reject(f"Invalid origin line: {path}")
    return data


def load_snapshot_document(path: str | Path) -> tuple[dict, str, bytes]:
    """Read once: validation and document identity refer to these exact bytes."""
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        _reject("Snapshot exceeds 4 MiB limit")
    text = content.decode("utf-8-sig")
    return parse_snapshot(text), text, content


def load_snapshot(path: str | Path) -> tuple[dict, str]:
    data, text, _ = load_snapshot_document(path)
    return data, text


def value_text(value: object = MISSING) -> str:
    return "Unknown (not provided)" if value is MISSING else json.dumps(value, ensure_ascii=False, allow_nan=False)


def decoded_path(path: str) -> list[str]:
    return [token.replace("~1", "/").replace("~0", "~") for token in path.split("/")[1:]]


def object_summaries(snapshot: dict) -> list[dict]:
    """Summarize recorded fields only; counts never establish coverage/success."""
    groups = {}
    for field in snapshot["fields"]:
        parts = field["path"].split("/")
        key = "/".join(parts[:4] if len(parts) == 5 else parts[:2])
        group = groups.setdefault(key, {"path": key, "fields": 0, "statuses": {}, "evidence": {}})
        group["fields"] += 1
        for target, source in (("statuses", "application_status"), ("evidence", "evidence_level")):
            value = field.get(source, "unknown")
            group[target][value] = group[target].get(value, 0) + 1
    return [groups[key] for key in sorted(groups)]


def snapshot_diff(before: dict, after: dict) -> list[dict]:
    """Canonical-path, type-sensitive diff. Missing, null, bool and number differ."""
    left = {field["path"]: field for field in before["fields"]}
    right = {field["path"]: field for field in after["fields"]}
    changes = []
    for path in sorted(left.keys() | right.keys()):
        a, b = left.get(path), right.get(path)
        if a is None or b is None:
            changes.append({"path": path, "kind": "added" if a is None else "removed", "before": a, "after": b})
            continue
        keys = sorted(key for key in a.keys() | b.keys() if key not in a or key not in b or
                      json.dumps(a[key], sort_keys=True, ensure_ascii=False) != json.dumps(b[key], sort_keys=True, ensure_ascii=False))
        if keys:
            changes.append({"path": path, "kind": "changed", "keys": keys, "before": a, "after": b})
    return changes
