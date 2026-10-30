from __future__ import annotations

import json
from pathlib import Path

from g4usim_gui.validators.config_validator import ValidationReport


def write_validation_report(path: str | Path, report: ValidationReport, extra_text: str = "") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "G4UniversalSim GUI Validation Report",
        f"can_run = {str(report.can_run).lower()}",
        "",
        "[errors]",
    ]
    lines.extend(report.errors or ["<none>"])
    lines.extend(["", "[warnings]"])
    lines.extend(report.warnings or ["<none>"])
    lines.extend(["", "[info]"])
    lines.extend(report.info or ["<none>"])
    if extra_text:
        lines.extend(["", extra_text])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_diagnostic_report(path: str | Path, report: ValidationReport) -> None:
    """Publish the versioned field/source records alongside the unchanged text report."""
    data = report.to_dict()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8", newline="\n")
