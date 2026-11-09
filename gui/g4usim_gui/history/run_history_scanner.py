from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from g4usim_gui.history.run_history_model import RunHistoryEntry
from g4usim_gui.core.copy_execution_link import read_copy_execution
from g4usim_gui.core.persisted_run_evidence import read_persisted_run_evidence
from g4usim_gui.output.provenance import output_evidence
from g4usim_gui.output.file_classifier import OutputFileType, classify_files


def scan_runs_root(runs_root: str) -> list[RunHistoryEntry]:
    root = Path(runs_root)
    if not root.is_dir():
        return []
    entries: list[RunHistoryEntry] = []
    for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        if not child.is_dir() or not _looks_like_package(child):
            continue
        entries.append(scan_package(child))
    return entries


def scan_package(package_dir: str | Path) -> RunHistoryEntry:
    package = Path(package_dir)
    entry = RunHistoryEntry(package_dir=str(package))
    try:
        entry.timestamp, entry.run_name = _parse_package_name(package.name)
        entry.last_modified = datetime.fromtimestamp(package.stat().st_mtime).isoformat(timespec="seconds")
        snapshot_path = package / "project_snapshot.json"
        entry.has_project_snapshot = snapshot_path.is_file()
        entry.has_validation_report = (package / "validation_report.txt").is_file()
        entry.config_path = str(package / "config" / "main.ini")
        entry.macro_path = str(package / "macros" / "run.mac")
        _apply_snapshot(entry, _read_json(snapshot_path))

        try:
            linked = read_copy_execution(package)
        except (OSError, TypeError, ValueError) as error:
            entry.copy_linked = True
            _unproven_link(entry, error)
            return entry
        if linked is not None:
            entry.copy_linked = True
            _apply_copy_execution(entry, *linked)
            return entry

        entry.result_dir = str(package)
        entry.output_dir = str(package / "output")
        _set_logs(entry, package / "logs")
        status = _read_json(package / "logs/run_status.json")
        _apply_status(entry, status if isinstance(status, dict) else {})
        _apply_output_counts(entry, Path(entry.output_dir))
        _infer_status(entry, Path(entry.output_dir), Path(entry.logs_dir))
        _apply_identity(entry, package)
    except Exception as exc:  # noqa: BLE001
        entry.status = "unknown"
        entry.errors.append(f"Failed to scan package: {exc}")
    return entry


def _looks_like_package(path: Path) -> bool:
    return (
        (path / "project_snapshot.json").exists()
        or ((path / "config" / "main.ini").exists() and (path / "macros" / "run.mac").exists())
        or ((path / "output").exists() and (path / "logs").exists())
    )


def _parse_package_name(name: str) -> tuple[str, str]:
    parts = name.split("_", 2)
    if len(parts) >= 3 and len(parts[0]) == 8 and len(parts[1]) == 6:
        return f"{parts[0]}_{parts[1]}", parts[2]
    return "", name


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _apply_snapshot(entry: RunHistoryEntry, snapshot: dict[str, Any]) -> None:
    if not snapshot:
        return
    entry.executable = snapshot.get("executable", entry.executable)
    run = snapshot.get("runSettings", {})
    paths = snapshot.get("pathSettings", {})
    geom = snapshot.get("geometrySettings", {})
    entry.run_name = run.get("run_name") or snapshot.get("runName") or entry.run_name
    entry.threads = _int_or_none(run.get("threads") or snapshot.get("threads"))
    entry.seed = _int_or_none(run.get("seed") or snapshot.get("seed"))
    entry.beam_on = _int_or_none(run.get("beam_on"))
    entry.geometry_template = geom.get("template", entry.geometry_template)
    entry.materials_config = paths.get("materials_config", entry.materials_config)
    entry.geometry_config = geom.get("config_path") or paths.get("geometry_config", entry.geometry_config)
    package = snapshot.get("runPackage", {})
    entry.recorded_config_path = package.get("main_ini_path", "")
    entry.recorded_macro_path = package.get("run_macro_path", "")
    entry.recorded_output_dir = package.get("output_dir", "")


def _apply_status(entry: RunHistoryEntry, status: dict[str, Any]) -> None:
    if not status:
        return
    entry.status = str(status.get("state", entry.status))
    entry.exit_code = _int_or_none(status.get("exitCode"))
    entry.executable = status.get("program", entry.executable)


def _set_logs(entry: RunHistoryEntry, logs: Path) -> None:
    entry.logs_dir = str(logs)
    entry.has_stdout_log = (logs / "stdout.log").is_file()
    entry.has_stderr_log = (logs / "stderr.log").is_file()


def _unproven_link(entry: RunHistoryEntry, error) -> None:
    entry.status = "incomplete"
    entry.result_reason = str(error)
    publish_identity(entry, error=error)


def _apply_copy_execution(entry: RunHistoryEntry, root: Path, record: dict) -> None:
    entry.copy_record_id = record["record_id"]
    entry.result_dir = str(root)
    _set_logs(entry, root / "logs")
    entry.exit_code = record.get("exit_code") if type(record.get("exit_code")) is int else None
    entry.result_reason = str(record.get("reason", ""))
    result = record.get("result")
    if record["status"] != "passed" or record.get("stale") is not False:
        state = result.get("state") if isinstance(result, dict) else None
        entry.status = (state if record["status"] == "cancelled" and state in {"stopped", "killed"}
                        else "failed" if record["status"] == "failed" else "incomplete")
        return
    output = root / "output"
    try:
        process = read_persisted_run_evidence(output / "run_summary.txt", root / "logs/run_status.json")
        if (process.result.state != "success" or process.exit_code != 0 or entry.exit_code != 0
                or result != asdict(process.result)):
            raise ValueError(f"Copy execution process evidence is not confirmed: {process.result.reason}")
        evidence = output_evidence(output)
        if (evidence.status != "verified" or not record.get("execution_id")
                or record["execution_id"] != evidence.document["provenance"]["execution_id"]
                or record.get("metadata_sha256") != evidence.manifest_digest):
            raise ValueError("Copy execution output identity does not match the final record.")
        _apply_output_counts(entry, output)
    except (OSError, ValueError) as error:
        _unproven_link(entry, error)
        return
    entry.output_dir = str(output)
    entry.status = process.result.state
    entry.result_reason = process.result.reason
    entry.result_trust_level = process.trust_level
    entry.warnings.extend(process.summary_warnings)
    publish_identity(entry, evidence)


def _apply_output_counts(entry: RunHistoryEntry, output: Path) -> None:
    entry.has_run_summary = (output / "run_summary.txt").is_file()
    for info in classify_files(output) if output.exists() else []:
        if info.file_type == OutputFileType.HITS_THREAD_CSV:
            entry.hits_files_count += 1
        elif info.file_type == OutputFileType.EVENT_EDEP_THREAD_CSV:
            entry.event_edep_files_count += 1
        elif info.file_type == OutputFileType.HIST_EDEP_RAW_THREAD_CSV:
            entry.hist_raw_files_count += 1
        elif info.file_type == OutputFileType.HIST_EDEP_WEIGHTED_THREAD_CSV:
            entry.hist_weighted_files_count += 1
        elif info.file_type == OutputFileType.HITS_MERGED_CSV:
            entry.merged_hits = True
        elif info.file_type == OutputFileType.EVENT_EDEP_MERGED_CSV:
            entry.merged_event_edep = True
        elif info.file_type == OutputFileType.HIST_EDEP_RAW_MERGED_CSV:
            entry.merged_hist_raw = True
        elif info.file_type == OutputFileType.HIST_EDEP_WEIGHTED_MERGED_CSV:
            entry.merged_hist_weighted = True


def _infer_status(entry: RunHistoryEntry, output: Path, logs: Path) -> None:
    evidence = read_persisted_run_evidence(output / "run_summary.txt", logs / "run_status.json")
    result = evidence.result
    entry.status = result.state
    entry.result_reason = result.reason
    entry.exit_code = evidence.exit_code
    entry.result_trust_level = evidence.trust_level
    entry.warnings.extend(evidence.summary_warnings)


def _int_or_none(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def publish_identity(entry, evidence=None, error=None):
    entry.warnings = [item for item in entry.warnings if item not in entry.identity_warnings]
    entry.identity_warnings = []
    if error is None:
        entry.identity_status = evidence.verification_status
        entry.identity_warnings = list(evidence.warnings)
        entry.identity_details = json.dumps(evidence.document.get("provenance", {}) if evidence.document else {}, ensure_ascii=False, indent=2)
    else:
        entry.identity_status = "tampered" if "bytes mismatch" in str(error) else "unavailable"
        entry.identity_details = str(error)
        entry.identity_warnings = [str(error)]
    entry.warnings.extend(entry.identity_warnings)


def _apply_identity(entry, package):
    try:
        publish_identity(entry, output_evidence(package / "output"))
    except (ValueError, OSError) as error:
        publish_identity(entry, error=error)
