"""Local, single-attempt locator for History's explicit Duplicate and Rerun."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat

from g4usim_gui.core.config_migration import MigrationPlan, digest, load_json_strict, publish_migration

_LOCATOR = "copy_execution_link.json"
_SCHEMA = "g4usim_copy_execution_link_v1"
_RECORDS = "experiment-records"


def _checked(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Copy execution requires an anchored path.")
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Copy execution refuses a linked path: {part}")
    if path.resolve() != path:
        raise ValueError(f"Copy execution refuses an ambiguous path: {path}")
    return path


def _read(path: Path, limit: int) -> bytes:
    path = _checked(path)
    if not path.is_file():
        raise ValueError(f"Copy execution file is missing: {path}")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"Copy execution file is too large: {path}")
    return raw


def _origin(package: Path) -> dict:
    raw = _read(package / "project_snapshot.json", 8 * 1024 * 1024)
    return {"package": package.name, "snapshot_sha256": digest(raw)}


def capture_copy_origin(copy_package, records_root: Path, project) -> dict:
    package = _checked(Path(copy_package))
    if (_checked(records_root) != package.parent / _RECORDS
            or project.runInputMode != "external"
            or _checked(Path(project.workspaceRoot)) != package
            or _checked(Path(project.configPath)) != package / "config/main.ini"
            or _checked(Path(project.macroPath)) != package / "macros/run.mac"):
        raise ValueError("Copy execution does not match the accepted copy inputs and runs root.")
    if os.path.lexists(package / _LOCATOR):
        raise ValueError("This copy already has an execution locator.")
    return _origin(package)


def _execution_record(package: Path, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise ValueError("Invalid copy execution record ID.")
    root = _checked(package.parent / _RECORDS / identifier)
    record = load_json_strict(_read(root / "record.json", 16 * 1024 * 1024))
    if (not isinstance(record, dict) or record.get("schema") != "g4usim_experiment_record_v1"
            or record.get("record_id") != identifier or record.get("run_id") != identifier
            or record.get("action") != "run" or record.get("level") != "execution"
            or record.get("status") not in ("passed", "failed", "cancelled", "stale", "unobserved")
            or not isinstance(record.get("finished_at"), str) or not record["finished_at"]
            or record.get("copy_origin") != _origin(package)
            or Path(record.get("record_dir") or "") != root
            or ("output_dir" in record and Path(record.get("output_dir") or "") != root / "output")):
        raise ValueError("Copy execution record does not bind this copy and execution root.")
    for relative in ("config", "output", "logs", "output/run_summary.txt", "output/run_metadata.json",
                     "logs/run_status.json", "logs/stdout.log", "logs/stderr.log"):
        _checked(root / relative)
    return root, record


def read_copy_execution(package: Path):
    package = package.absolute()
    locator = package / _LOCATOR
    try:
        locator.lstat()
    except FileNotFoundError:
        return None
    data = load_json_strict(_read(locator, 1024))
    if (not isinstance(data, dict) or set(data) != {"schema", "record_id"}
            or data["schema"] != _SCHEMA):
        raise ValueError("Invalid copy execution locator.")
    return _execution_record(package, data["record_id"])


def publish_copy_execution(copy_package: Path, record: dict) -> str | None:
    package = _checked(copy_package)
    identifier = record["record_id"]
    _, saved = _execution_record(package, identifier)
    if saved != record:
        raise ValueError("Saved execution record differs from the final receipt.")
    existing = read_copy_execution(package)
    if existing is not None:
        if existing[1]["record_id"] == identifier:
            return None
        raise ValueError("Copy already links a different execution.")
    payload = (json.dumps({"schema": _SCHEMA, "record_id": identifier}, sort_keys=True) + "\n").encode()
    # The existing exclusive publisher rechecks the copy's snapshot bytes on
    # both sides of staging, then commits by hard link without replacement.
    plan = MigrationPlan("copy_execution_locator", str(package / "project_snapshot.json"),
                         saved["copy_origin"]["snapshot_sha256"], None, 1, (), (), payload, str(package))
    return publish_migration(plan, package / _LOCATOR).cleanup_warning
