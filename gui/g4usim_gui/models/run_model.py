from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunSettings:
    run_name: str = "gui_run"
    threads: int = 1
    seed: int | None = 12345
    beam_on: int = 100
    check_overlaps: bool = True
    dry_run: bool = False
