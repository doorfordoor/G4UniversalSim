from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunSummary:
    path: str
    exists: bool = False
    sections: dict[str, list[str]] = field(default_factory=dict)
    key_values: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    raw_text: str = ""


def parse_run_summary(path: str | Path) -> RunSummary:
    source = Path(path)
    summary = RunSummary(path=str(source), exists=source.exists())
    if not source.exists():
        summary.warnings.append("run_summary.txt does not exist.")
        return summary
    try:
        summary.raw_text = source.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        summary.warnings.append(f"Failed to read run summary: {exc}")
        return summary

    current = "default"
    summary.sections[current] = []
    for raw_line in summary.raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line.strip("[]").strip() or "default"
            summary.sections.setdefault(current, [])
            continue
        summary.sections.setdefault(current, []).append(raw_line)
        if "=" in line:
            key, value = line.split("=", 1)
            summary.key_values[key.strip()] = value.strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            summary.key_values[key.strip()] = value.strip()
    return summary
