from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MergeTask:
    name: str
    kind: str
    input_dir: str
    pattern: str
    output_file: str
    tool_type: str
    command_program: str
    command_args: list[str]
    available: bool
    reason: str
    matched_files: list[str]
    log_prefix: str


@dataclass
class MergePlan:
    tasks: list[MergeTask]


def build_merge_plan(output_dir: str, workspace_root: str = "", merge_histograms_exe: str = "") -> MergePlan:
    output = Path(output_dir)
    workspace = Path(workspace_root) if workspace_root else Path.cwd()
    script = workspace / "scripts" / "merge_outputs.py"
    hist_tool = Path(merge_histograms_exe) if merge_histograms_exe else find_merge_histograms(workspace)

    specs = [
        ("Merge hits CSV", "hits", "hits_t*.csv", "hits_merged.csv", "python_script", script, "merge_hits"),
        ("Merge event edep CSV", "event_edep", "event_edep_t*.csv", "event_edep_merged.csv", "python_script", script, "merge_event_edep"),
        ("Merge raw histogram", "hist_raw", "hist_edep_raw_t*.csv", "hist_edep_raw_merged.csv", "executable", hist_tool, "merge_hist_raw"),
        ("Merge weighted histogram", "hist_weighted", "hist_edep_weighted_t*.csv", "hist_edep_weighted_merged.csv", "executable", hist_tool, "merge_hist_weighted"),
    ]
    tasks: list[MergeTask] = []
    for name, kind, pattern, output_name, tool_type, tool_path, log_prefix in specs:
        matched = sorted(str(path) for path in output.glob(pattern)) if output.is_dir() else []
        out_file = output / output_name
        available, reason = _availability(output, matched, tool_type, Path(tool_path), out_file)
        if tool_type == "python_script":
            program = sys.executable
            args = [str(tool_path), "--input", str(output), "--pattern", pattern, "--output", str(out_file)]
        else:
            program = str(tool_path)
            args = ["--input", str(output), "--pattern", pattern, "--output", str(out_file)]
        tasks.append(
            MergeTask(
                name=name,
                kind=kind,
                input_dir=str(output),
                pattern=pattern,
                output_file=str(out_file),
                tool_type=tool_type,
                command_program=program,
                command_args=args,
                available=available,
                reason=reason,
                matched_files=matched,
                log_prefix=log_prefix,
            )
        )
    return MergePlan(tasks)


def find_merge_histograms(workspace: Path) -> Path:
    candidates = [
        workspace / "build_vs2026" / "Release" / "mergeHistograms.exe",
        workspace / "build" / "Release" / "mergeHistograms.exe",
        workspace / "build_vs" / "Release" / "mergeHistograms.exe",
        workspace / "build_vs2026" / "Debug" / "mergeHistograms.exe",
        workspace / "build" / "Debug" / "mergeHistograms.exe",
        workspace / "build_vs" / "Debug" / "mergeHistograms.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _availability(output_dir: Path, matched: list[str], tool_type: str, tool_path: Path, output_file: Path) -> tuple[bool, str]:
    if not output_dir.is_dir():
        return False, f"Input directory does not exist: {output_dir}"
    if not matched:
        return False, "No matching input files"
    if tool_type == "python_script" and not tool_path.is_file():
        return False, f"Python merge script not found: {tool_path}"
    if tool_type == "executable" and not tool_path.is_file():
        return False, f"mergeHistograms executable not found: {tool_path}"
    if output_file.exists():
        return False, f"Output file already exists: {output_file}"
    return True, f"{len(matched)} input file(s)"
