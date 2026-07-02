from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogTag:
    level: str
    keyword: str
    message: str
    advice: str = ""


KEYWORDS: tuple[tuple[str, str, str, str], ...] = (
    ("error", "G4Exception", "Geant4 exception detected", "Open stderr and the macro line around the failure."),
    ("error", "Unknown command", "Macro command was not recognized", "Check that the macro uses commands supported by this executable."),
    ("error", "Material not found", "Material lookup failed", "Check materials.ini and geometry material references."),
    ("error", "root node", "Geometry root node may be missing", "Check geometry template/config and load order before /run/initialize."),
    ("warning", "Geometry", "Geometry message", "Review geometry config and overlap messages."),
    ("warning", "Biasing", "Biasing message", "Check biasing volumes, process names, and physics biasing hook."),
    ("error", "process not found", "Biasing process may be invalid", "Use the exact Geant4 process name for the selected particle."),
    ("error", "AIHLSDMT001", "Sensitive-detector or multithread warning", "Check worker SD/scoring registration and per-thread output."),
    ("warning", "OGL", "OpenGL visualization message", "Current Geant4 may not provide this visualization driver; try a no-vis macro."),
    ("warning", "visualization", "Visualization message", "Verify local Geant4 UI/Vis support."),
    ("warning", "overlap", "Geometry overlap message", "Check geometry dimensions and placements."),
    ("error", "Geant4Config.cmake", "Geant4 CMake package was not found", "Check Geant4_DIR and matching compiler/toolchain."),
    ("error", "output directory", "Output directory message", "Check that the output directory exists and is writable."),
)


def parse_log_line(line: str) -> list[LogTag]:
    """Return lightweight tags for a single stdout/stderr line."""
    tags: list[LogTag] = []
    lower = line.lower()
    for level, keyword, message, advice in KEYWORDS:
        if keyword.lower() in lower:
            tags.append(LogTag(level=level, keyword=keyword, message=message, advice=advice))
    return tags
