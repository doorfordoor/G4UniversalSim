"""Read-only migration plans and exclusive publication of reviewed copies."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any


@dataclass(frozen=True)
class MigrationPlan:
    kind: str
    source_path: str
    source_sha256: str
    input_version: int | None
    output_version: int
    changes: tuple[str, ...]
    validation: tuple[str, ...]
    payload: bytes
    destination_parent: str | None = None


@dataclass(frozen=True)
class MigrationResult:
    destination: str
    sha256: str
    plan: MigrationPlan
    cleanup_warning: str | None = None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_finite_json(value: Any, path: str = "project") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Non-finite JSON number: {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            check_finite_json(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            check_finite_json(item, f"{path}[{index}]")


def load_json_strict(raw: bytes | str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    check_finite_json(result)
    return result


def publish_migration(plan: MigrationPlan, destination: str | Path) -> MigrationResult:
    """Publish a new file atomically; a competing writer always wins safely.

    Hard-link publication is deliberately required: unlike os.replace, link
    cannot replace an existing destination. Unsupported filesystems fail closed.
    """
    source = Path(plan.source_path)
    target = Path(destination).absolute()
    if plan.destination_parent is not None and target.parent.resolve() != Path(plan.destination_parent).resolve():
        raise ValueError(f"Migration destination must remain in the source directory: {plan.destination_parent}")
    if os.path.lexists(target):
        raise FileExistsError(f"Migration destination already exists: {target}")
    if source.resolve() == target.resolve():
        raise ValueError("Migration source and destination must be different files")
    if digest(source.read_bytes()) != plan.source_sha256:
        raise ValueError(f"Migration source changed; reload and review: {source}")
    temporary = None
    committed = False
    cleanup_warning = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent,
                                         prefix=f".{target.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(plan.payload)
            handle.flush()
            os.fsync(handle.fileno())
        if digest(source.read_bytes()) != plan.source_sha256:
            raise ValueError(f"Migration source changed; reload and review: {source}")
        os.link(temporary, target)
        committed = True
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                # link is the commit point. Never report a completed publication
                # as failure, and never delete a destination to undo cleanup.
                # Before commit, preserve the original error if cleanup also fails.
                if committed:
                    cleanup_warning = f"Published copy; temporary link cleanup failed: {temporary}: {error}"
    return MigrationResult(str(target), digest(plan.payload), plan, cleanup_warning)
