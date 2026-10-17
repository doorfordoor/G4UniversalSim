from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from g4usim_gui.history.run_history_model import RunHistoryEntry
from g4usim_gui.core.run_result import evaluate_run_result, summary_fingerprint
from g4usim_gui.output.file_classifier import OutputFileType, classify_files
from g4usim_gui.output.run_summary_parser import parse_run_summary


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
        status_path = package / "logs" / "run_status.json"
        validation_path = package / "validation_report.txt"
        output_dir = package / "output"
        logs_dir = package / "logs"

        snapshot = _read_json(snapshot_path)
        status = _read_json(status_path)
        entry.has_project_snapshot = snapshot_path.is_file()
        entry.has_validation_report = validation_path.is_file()
        entry.has_stdout_log = (logs_dir / "stdout.log").is_file()
        entry.has_stderr_log = (logs_dir / "stderr.log").is_file()
        entry.config_path = str(package / "config" / "main.ini")
        entry.macro_path = str(package / "macros" / "run.mac")
        entry.output_dir = str(output_dir)

        _apply_snapshot(entry, snapshot)
        _apply_status(entry, status)
        _apply_output_counts(entry, package)
        _infer_status(entry, package, status)
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
    entry.config_path = package.get("main_ini_path", entry.config_path)
    entry.macro_path = package.get("run_macro_path", entry.macro_path)
    entry.output_dir = package.get("output_dir", entry.output_dir)


def _apply_status(entry: RunHistoryEntry, status: dict[str, Any]) -> None:
    if not status:
        return
    entry.status = str(status.get("state", entry.status))
    entry.exit_code = _int_or_none(status.get("exitCode"))
    entry.executable = status.get("program", entry.executable)


def _apply_output_counts(entry: RunHistoryEntry, package: Path) -> None:
    output = package / "output"
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


def _infer_status(entry: RunHistoryEntry, package: Path, status: dict[str, Any]) -> None:
    summary_path = package / "output" / "run_summary.txt"
    stored_fingerprint = status.get("summaryFingerprint")
    fresh = (
        status.get("resultVersion") == 1
        and status.get("summaryFresh") is True
        and isinstance(stored_fingerprint, list)
        and tuple(stored_fingerprint) == summary_fingerprint(summary_path)
    )
    result = evaluate_run_result(
        summary_path,
        exit_code=entry.exit_code,
        crashed=status.get("exitStatus") == "crashed" or status.get("state") == "error",
        requested_state=status.get("state") if status.get("state") in {"stopped", "killed"} else "",
        summary_fresh=fresh,
    )
    entry.status = result.state
    entry.result_reason = result.reason
    if entry.has_run_summary:
        entry.warnings.extend(parse_run_summary(summary_path).warnings)


def _int_or_none(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None
