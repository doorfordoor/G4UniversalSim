"""Read backend facts without treating them as GUI writer or physics support."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


CAPABILITY_GROUPS = ("templates", "solids", "placements", "materials", "physics", "sources", "scorers")


@dataclass(frozen=True)
class BackendCapabilities:
    data: dict

    @classmethod
    def from_json(cls, text: str) -> BackendCapabilities:
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("schema") != "G4UniversalSimCapabilities" or data.get("version") != 1:
            raise ValueError("Unsupported backend capabilities schema/version")
        for group in CAPABILITY_GROUPS:
            entries = data.get(group)
            if not isinstance(entries, list):
                raise ValueError(f"Missing backend capability group: {group}")
            seen: set[str] = set()
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry["id"]:
                    raise ValueError(f"Invalid backend capability entry: {group}")
                if type(entry.get("runtime")) is not bool or entry["id"] in seen:
                    raise ValueError(f"Invalid or duplicate backend capability: {group}/{entry['id']}")
                seen.add(entry["id"])
        return cls(data)

    def runtime_ids(self, group: str) -> frozenset[str]:
        if group not in CAPABILITY_GROUPS:
            raise ValueError(f"Unknown backend capability group: {group}")
        return frozenset(entry["id"] for entry in self.data[group] if entry["runtime"])

    def editable_shapes(self, writer_shapes: set[str]) -> frozenset[str]:
        # A backend addition never opens an editor that cannot preserve its data.
        return self.runtime_ids("solids").intersection(writer_shapes)


def query_backend_capabilities(executable: str | Path, *, timeout: float = 10) -> BackendCapabilities:
    """Call from a worker or CLI, never synchronously from the Qt event thread."""
    path = Path(executable).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Backend executable is not a file: {path}")
    result = subprocess.run(
        [str(path), "--capabilities"], cwd=path.parent, capture_output=True,
        text=True, encoding="utf-8", errors="strict", timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise ValueError(f"Backend capabilities query failed: {result.stderr.strip()}")
    return BackendCapabilities.from_json(result.stdout)
