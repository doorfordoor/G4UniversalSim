"""Read bounded cleanup diagnostics without deciding process success."""
from __future__ import annotations

import json
from pathlib import Path


class PublicationDiagnostics:
    def __init__(self, target: str | Path) -> None:
        self.target = Path(target).resolve()
        self._pending = ""
        self._warnings: list[str] = []

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self._warnings)

    def feed(self, text: str) -> None:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            prefix = "G4USIM_PUBLICATION_RESULT "
            if not line.startswith(prefix) or len(line) > 131072:
                continue
            try:
                record = json.loads(line[len(prefix):])
                if (not isinstance(record, dict)
                        or record.get("schema") != "g4usim_publication_v1"
                        or record.get("published") is not True
                        or not isinstance(record.get("output"), str)
                        or Path(record["output"]).resolve() != self.target
                        or not isinstance(record.get("residual_temporary"), str)
                        or not record["residual_temporary"]):
                    continue
                warnings = record.get("warnings")
                if not isinstance(warnings, list) or not warnings or any(type(w) is not str for w in warnings):
                    continue
                for warning in warnings:
                    if warning not in self._warnings:
                        self._warnings.append(warning)
            except (ValueError, OSError, RuntimeError):
                continue  # Raw stderr is still shown; never infer publication.
        if len(self._pending) > 131072:
            self._pending = ""
