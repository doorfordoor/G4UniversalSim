from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunHistoryEntry:
    package_dir: str
    run_name: str = ""
    timestamp: str = ""
    status: str = "unknown"
    result_reason: str = ""
    identity_status: str = "unavailable"
    identity_details: str = ""
    exit_code: int | None = None
    executable: str = ""
    config_path: str = ""
    macro_path: str = ""
    output_dir: str = ""
    threads: int | None = None
    seed: int | None = None
    beam_on: int | None = None
    geometry_template: str = ""
    materials_config: str = ""
    geometry_config: str = ""
    has_run_summary: bool = False
    has_stdout_log: bool = False
    has_stderr_log: bool = False
    has_validation_report: bool = False
    has_project_snapshot: bool = False
    hits_files_count: int = 0
    event_edep_files_count: int = 0
    hist_raw_files_count: int = 0
    hist_weighted_files_count: int = 0
    merged_hits: bool = False
    merged_event_edep: bool = False
    merged_hist_raw: bool = False
    merged_hist_weighted: bool = False
    last_modified: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RunHistoryIndex:
    runs_root: str
    entries: list[RunHistoryEntry] = field(default_factory=list)
