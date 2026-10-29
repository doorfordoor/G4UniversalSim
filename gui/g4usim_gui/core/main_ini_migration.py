"""Explicit main INI version tagging without rewriting simulation settings."""
from __future__ import annotations

from pathlib import Path

from g4usim_gui.core.config_migration import MigrationPlan, digest

_ASCII_SPACE = " \t\r\n\v\f"


def plan_main_ini_migration(source: str | Path) -> MigrationPlan:
    path = Path(source).resolve(strict=True)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    # Match the backend's first '#' or ';' comment rule, including comments
    # without preceding whitespace. Do not use ConfigParser's interpolation or
    # duplicate rejection: main INI duplicates intentionally keep last-wins.
    parts = text.split("\n")
    lines = [line + "\n" for line in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    section = "global"
    general_line = None
    version = None
    for number, line in enumerate(lines, 1):
        clean = line.split("#", 1)[0].split(";", 1)[0].strip(_ASCII_SPACE)
        if not clean:
            continue
        if clean.startswith("["):
            if not clean.endswith("]") or not clean[1:-1].strip(_ASCII_SPACE):
                raise ValueError(f"{path}:{number}: invalid INI section")
            section = clean[1:-1].strip(_ASCII_SPACE).lower()
            if section == "general" and general_line is None:
                general_line = number
            continue
        if "=" not in clean or not clean.split("=", 1)[0].strip(_ASCII_SPACE):
            raise ValueError(f"{path}:{number}: expected key = value")
        key, value = (part.strip(_ASCII_SPACE) for part in clean.split("=", 1))
        if section == "general" and key.lower() == "schema_version":
            version = (value, number)
    if version is not None and version[0] != "1":
        raise ValueError(f"{path}:{version[1]} [general]/schema_version = {version[0]!r}: "
                         "supported value is 1; do not downgrade an unknown format")
    changes: tuple[str, ...] = ()
    if version is None:
        newline = "\r\n" if "\r\n" in text else "\n"
        if general_line is None:
            separator = "" if not text or text.endswith("\n") else newline
            text += separator + f"[general]{newline}schema_version = 1{newline}"
        else:
            index = general_line - 1
            if not lines[index].endswith("\n"):
                lines[index] += newline
            lines.insert(general_line, f"schema_version = 1{newline}")
            text = "".join(lines)
        changes = ("[general]/schema_version: absent legacy version -> explicit 1; settings unchanged",)
    return MigrationPlan(
        "main_ini", str(path), digest(raw), 1 if version else None, 1,
        changes,
        ("Main INI syntax and winning format version checked; duplicate declarations retain last-wins",
         "Same-directory copy required to preserve existing relative resource paths and working-directory rules",
         "Unknown fields are preserved; full configuration acceptance requires backend Inspect inputs",
         "No simulation or physics validation performed"),
        text.encode("utf-8"), destination_parent=str(path.parent),
    )
