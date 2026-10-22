from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class OutputFileType(str, Enum):
    RUN_SUMMARY = "run_summary"
    STDOUT_LOG = "stdout_log"
    STDERR_LOG = "stderr_log"
    VALIDATION_REPORT = "validation_report"
    PROJECT_SNAPSHOT = "project_snapshot"
    MAIN_INI = "main_ini"
    GEOMETRY_INI = "geometry_ini"
    MATERIALS_INI = "materials_ini"
    MACRO = "macro"
    HITS_THREAD_CSV = "hits_thread_csv"
    EVENT_EDEP_THREAD_CSV = "event_edep_thread_csv"
    DOSE_VOLUME_THREAD_CSV = "dose_volume_thread_csv"
    FLUENCE_VOLUME_THREAD_CSV = "fluence_volume_thread_csv"
    HIST_EDEP_RAW_THREAD_CSV = "hist_edep_raw_thread_csv"
    HIST_EDEP_WEIGHTED_THREAD_CSV = "hist_edep_weighted_thread_csv"
    HITS_MERGED_CSV = "hits_merged_csv"
    EVENT_EDEP_MERGED_CSV = "event_edep_merged_csv"
    HIST_EDEP_RAW_MERGED_CSV = "hist_edep_raw_merged_csv"
    HIST_EDEP_WEIGHTED_MERGED_CSV = "hist_edep_weighted_merged_csv"
    OTHER_CSV = "other_csv"
    OTHER_TEXT = "other_text"
    ROOT_FILE = "root_file"
    LARGE_FILE = "large_file"
    UNKNOWN = "unknown"


@dataclass
class OutputFileInfo:
    path: str
    relative_path: str
    file_type: OutputFileType
    size: int
    modified_time: float


def classify_file(path: str | Path, root: str | Path | None = None, large_threshold: int = 50 * 1024 * 1024) -> OutputFileInfo:
    file_path = Path(path)
    rel = str(file_path)
    if root:
        try:
            rel = str(file_path.relative_to(Path(root)))
        except ValueError:
            rel = str(file_path)
    stat = file_path.stat()
    file_type = _classify_name(file_path)
    if stat.st_size > large_threshold and file_type in {OutputFileType.OTHER_CSV, OutputFileType.OTHER_TEXT, OutputFileType.UNKNOWN}:
        file_type = OutputFileType.LARGE_FILE
    return OutputFileInfo(str(file_path), rel, file_type, stat.st_size, stat.st_mtime)


def classify_files(root: str | Path) -> list[OutputFileInfo]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    return [classify_file(path, root_path) for path in sorted(root_path.rglob("*")) if path.is_file()]


def _classify_name(path: Path) -> OutputFileType:
    name = path.name.lower()
    rel = str(path).replace("\\", "/").lower()
    if name == "run_summary.txt":
        return OutputFileType.RUN_SUMMARY
    if name == "stdout.log":
        return OutputFileType.STDOUT_LOG
    if name == "stderr.log":
        return OutputFileType.STDERR_LOG
    if name == "validation_report.txt":
        return OutputFileType.VALIDATION_REPORT
    if name == "project_snapshot.json":
        return OutputFileType.PROJECT_SNAPSHOT
    if name == "main.ini":
        return OutputFileType.MAIN_INI
    if name == "geometry.ini" or rel.endswith("/config/geometry/geometry.ini"):
        return OutputFileType.GEOMETRY_INI
    if name == "material.ini" or rel.endswith("/config/materials/material.ini"):
        return OutputFileType.MATERIALS_INI
    if path.suffix.lower() == ".mac":
        return OutputFileType.MACRO
    if name.startswith("hits_t") and name.endswith(".csv"):
        return OutputFileType.HITS_THREAD_CSV
    if name.startswith("event_edep_t") and name.endswith(".csv"):
        return OutputFileType.EVENT_EDEP_THREAD_CSV
    if name.startswith("dose_volume_summary_t") and name.endswith(".csv"):
        return OutputFileType.DOSE_VOLUME_THREAD_CSV
    if name.startswith("fluence_volume_summary_t") and name.endswith(".csv"):
        return OutputFileType.FLUENCE_VOLUME_THREAD_CSV
    if name.startswith("hist_edep_raw_t") and name.endswith(".csv"):
        return OutputFileType.HIST_EDEP_RAW_THREAD_CSV
    if name.startswith("hist_edep_weighted_t") and name.endswith(".csv"):
        return OutputFileType.HIST_EDEP_WEIGHTED_THREAD_CSV
    if name == "hits_merged.csv":
        return OutputFileType.HITS_MERGED_CSV
    if name == "event_edep_merged.csv":
        return OutputFileType.EVENT_EDEP_MERGED_CSV
    if name == "hist_edep_raw_merged.csv":
        return OutputFileType.HIST_EDEP_RAW_MERGED_CSV
    if name == "hist_edep_weighted_merged.csv":
        return OutputFileType.HIST_EDEP_WEIGHTED_MERGED_CSV
    if path.suffix.lower() == ".csv":
        return OutputFileType.OTHER_CSV
    if path.suffix.lower() in {".txt", ".log", ".ini", ".mac", ".json"}:
        return OutputFileType.OTHER_TEXT
    if path.suffix.lower() == ".root":
        return OutputFileType.ROOT_FILE
    return OutputFileType.UNKNOWN
