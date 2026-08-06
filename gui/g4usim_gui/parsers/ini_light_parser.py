from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IniSection:
    name: str
    line_no: int
    values: dict[str, str] = field(default_factory=dict)
    key_lines: dict[str, int] = field(default_factory=dict)


@dataclass
class IniLightDocument:
    path: str
    sections: list[IniSection]
    warnings: list[str]
    errors: list[str]
    raw_text: str

    def section_map(self) -> dict[str, IniSection]:
        return {section.name: section for section in self.sections}


def parse_ini_light(path: str | Path) -> IniLightDocument:
    """Parse enough INI syntax for GUI summaries without enforcing strict schema."""
    source = Path(path)
    warnings: list[str] = []
    errors: list[str] = []
    try:
        raw_text = source.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - preview parser should not crash GUI.
        return IniLightDocument(str(source), [], warnings, [f"Failed to read {source}: {exc}"], "")

    sections: list[IniSection] = []
    current: IniSection | None = None
    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and "]" in line:
            name = line[1 : line.index("]")].strip()
            if not name:
                errors.append(f"Line {line_no}: empty section name")
                continue
            current = IniSection(name=name, line_no=line_no)
            sections.append(current)
            continue
        if "=" in line and current is not None:
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                errors.append(f"Line {line_no}: empty key")
                continue
            current.values[key] = _strip_inline_comment(value.strip())
            current.key_lines[key] = line_no
            continue
        if "=" in line and current is None:
            errors.append(f"Line {line_no}: key/value outside any section")
            continue
        errors.append(f"Line {line_no}: invalid INI line: {line}")

    return IniLightDocument(str(source), sections, warnings, errors, raw_text)


def _strip_inline_comment(value: str) -> str:
    for marker in (" #", " ;"):
        index = value.find(marker)
        if index >= 0:
            value = value[:index].rstrip()
    return value
