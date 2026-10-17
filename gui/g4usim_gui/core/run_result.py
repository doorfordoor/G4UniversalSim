from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from g4usim_gui.output.run_summary_parser import parse_run_summary


@dataclass(frozen=True)
class RunResult:
    state: str
    reason: str
    summary_status: str = ""
    run_count: int | None = None
    planned_events: int | None = None
    completed_events: int | None = None


def summary_fingerprint(path: str | Path) -> tuple[int, int] | None:
    try:
        stat = Path(path).stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


def _runs_match_summary(facts: dict[str, str], run_count: int, planned: int, completed: int) -> bool:
    planned_sum = 0
    completed_sum = 0
    try:
        for index in range(run_count):
            int(facts[f"run_{index}_id"])
            run_planned = int(facts[f"run_{index}_planned_events"])
            run_completed = int(facts[f"run_{index}_completed_events"])
            if run_planned < 0 or run_completed != run_planned:
                return False
            planned_sum += run_planned
            completed_sum += run_completed
    except (KeyError, ValueError):
        return False
    return planned_sum == planned and completed_sum == completed


def evaluate_run_result(
    summary_path: str | Path,
    *,
    exit_code: int | None,
    crashed: bool = False,
    requested_state: str = "",
    summary_fresh: bool = False,
) -> RunResult:
    if requested_state in {"stopped", "killed"}:
        return RunResult(requested_state, "User requested process termination.")
    if crashed:
        return RunResult("failed", "Process crashed or failed to start.")
    if exit_code is None:
        return RunResult("incomplete", "Process exit status is unavailable.")
    if exit_code != 0:
        return RunResult("failed", "Process exited with nonzero code.")
    if not summary_fresh:
        return RunResult("incomplete", "No fresh run summary was produced by this process.")

    summary = parse_run_summary(summary_path)
    if not summary.exists or summary.warnings:
        return RunResult("incomplete", "Run summary is missing or unreadable.")
    facts = summary.key_values
    status = facts.get("status", "")
    try:
        summary_exit = int(facts["program_exit_code"])
        runs = int(facts["run_count"])
        planned = int(facts["planned_event_count"])
        completed = int(facts["actual_completed_event_count"])
    except (KeyError, ValueError):
        return RunResult("incomplete", "Run summary lacks valid lifecycle counts or exit status.", status)
    result = lambda state, reason: RunResult(state, reason, status, runs, planned, completed)
    if summary_exit != exit_code or min(runs, planned, completed) < 0:
        return result("incomplete", "Run summary conflicts with process exit or contains invalid counts.")
    if facts.get("summary_write_status") != "completed":
        return result("incomplete", "Run summary write completion is not confirmed.")
    macro = facts.get("macro_execution_status", "")
    if status in {"failed", "aborted"} or macro in {"failed", "preflight_failed"}:
        return result("failed", "Backend or macro reported failure.")
    if status == "dry_run" and macro == "skipped_dry_run" and (runs, planned, completed) == (0, 0, 0):
        return result("dry_run", "Configuration checked; no simulation run was requested.")
    if status == "interactive_no_run" and runs == 0 and planned == completed == 0:
        return result("interactive_no_run", "Interactive session ended without a run.")
    if status != "completed" or macro not in {"completed", "not_run"}:
        return result("incomplete", "Backend or macro status is not a completed state.")
    if runs == 0:
        return result("no_run", "Process completed but no Geant4 run occurred.")
    if planned == 0 or completed != planned or facts.get("simulation_executed") != "true":
        return result("incomplete", "Run events were not confirmed complete.")
    if not _runs_match_summary(facts, runs, planned, completed):
        return result("incomplete", "Individual run event counts are missing or inconsistent.")
    return result("success", "Events completed as planned.")
