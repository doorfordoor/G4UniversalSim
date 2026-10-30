from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.core.diagnostics import emit_diagnostic, source_location, SourceLocation


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
        result = IniLightDocument(str(source), [], warnings, [], "")
        result._f4_read_success = False
        emit_diagnostic(result, "ini.read_failed", "error", f"Failed to read {source}: {exc}",
                        origin="ini.source", source=SourceLocation(str(source)),
                        unavailable_reason="source_unavailable")
        return result

    result = IniLightDocument(str(source), [], warnings, errors, raw_text)
    result._f4_read_success = True

    def problem(code: str, message: str, line_no: int, *, section: str = "", key: str = "", value: str = "") -> None:
        # The digest describes this already-read logical text, not raw file bytes.
        emit_diagnostic(result, code, "error", message, origin="ini.source",
                        source=source_location(str(source), raw_text, line=line_no,
                                               section=section, key=key, value=value),
                        unavailable_reason="source_only")

    sections: list[IniSection] = []
    current: IniSection | None = None
    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and "]" in line:
            name = line[1 : line.index("]")].strip()
            if not name:
                problem("ini.empty_section", f"Line {line_no}: empty section name", line_no)
                continue
            current = IniSection(name=name, line_no=line_no)
            sections.append(current)
            continue
        if "=" in line and current is not None:
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                problem("ini.empty_key", f"Line {line_no}: empty key", line_no, section=current.name, value=value.strip())
                continue
            current.values[key] = _strip_inline_comment(value.strip())
            current.key_lines[key] = line_no
            continue
        if "=" in line and current is None:
            key, value = line.split("=", 1)
            problem("ini.global_field", f"Line {line_no}: key/value outside any section", line_no,
                    section="global", key=key.strip(), value=_strip_inline_comment(value.strip()))
            continue
        problem("ini.invalid_line", f"Line {line_no}: invalid INI line: {line}", line_no,
                section=current.name if current else "", value=line)

    result.sections = sections
    return result


def _strip_inline_comment(value: str) -> str:
    for marker in (" #", " ;"):
        index = value.find(marker)
        if index >= 0:
            value = value[:index].rstrip()
    return value
