from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.parsers.ini_light_parser import parse_ini_light
from g4usim_gui.core.capability_messages import capability_message


NIST_QUICK_LIST: set[str] = {
    "G4_AIR",
    "G4_WATER",
    "G4_Si",
    "G4_SILICON_DIOXIDE",
    "G4_Al",
    "G4_Cu",
    "G4_Fe",
    "G4_Pb",
    "G4_POLYETHYLENE",
    "G4_Galactic",
}


@dataclass
class MaterialEntry:
    name: str
    kind: str = "unknown"
    density: str = ""
    components: list[str] = field(default_factory=list)
    section: str = ""
    line_no: int = 0


@dataclass
class MaterialsSummary:
    path: str
    materials: list[MaterialEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def names(self) -> set[str]:
        names = {entry.name for entry in self.materials if entry.name}
        for entry in self.materials:
            if entry.kind == "nist" and entry.components:
                names.update(entry.components)
        return names


def parse_materials(path: str | Path) -> MaterialsSummary:
    document = parse_ini_light(path)
    summary = MaterialsSummary(path=document.path, warnings=list(document.warnings), errors=list(document.errors), raw_text=document.raw_text)
    _validate_material_schema(summary)
    for section in document.sections:
        values = {key.lower(): value for key, value in section.values.items()}
        name = values.get("name", section.name)
        material_alias = values.get("material", "")
        mode = values.get("mode", values.get("type", "")).lower()
        density = values.get("density", "")
        components_text = values.get("components", values.get("component", ""))
        components = _split_components(components_text)

        if material_alias.startswith("G4_"):
            kind = "nist"
            components = [material_alias]
        elif mode in {"volume_fraction", "volume-fraction"}:
            kind = "volume_fraction"
        elif mode in {"mass_fraction", "mass-fraction", "mixture"}:
            kind = "mass_fraction"
        elif mode in {"atom_count", "atom-count", "material"}:
            kind = "atom_count" if components else "custom"
        elif components:
            kind = "custom"
        else:
            kind = "unknown"

        if material_alias and not name:
            name = material_alias

        summary.materials.append(
            MaterialEntry(
                name=name,
                kind=kind,
                density=density,
                components=components,
                section=section.name,
                line_no=section.line_no,
            )
        )

    if not summary.materials and not summary.errors:
        summary.warnings.append("No material sections were found.")
    return summary


def _validate_material_schema(summary: MaterialsSummary) -> None:
    """Reject material fields that the C++ MaterialIniReader cannot consume."""
    allowed = {
        "nist": {"materials"},
        "isotope": {"symbol", "z", "n", "a"},
        "element": {"symbol", "isotopes", "z", "a"},
        "material": {"type", "mode", "density", "components", "state", "temperature", "pressure"},
    }
    section_seen = False
    current_section = "global"
    section_lines: dict[str, int] = {}
    section_keys: dict[str, set[str]] = {}
    for line_no, raw_line in enumerate(summary.raw_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and "]" in line:
            section_seen = True
            current_section = line[1 : line.index("]")].strip()
            section_lower = current_section.lower()
            section_lines[section_lower] = line_no
            section_keys.setdefault(section_lower, set())
            if section_lower == "global":
                summary.errors.append(_schema_error(summary.path, line_no, current_section, "<section>", "", "global section must not contain fields"))
            elif section_lower in allowed:
                pass
            elif any(section_lower.startswith(prefix + ".") for prefix in ("isotope", "element", "material")):
                prefix, suffix = section_lower.split(".", 1)
                if not suffix:
                    summary.errors.append(_schema_error(summary.path, line_no, current_section, "<section>", "", "section suffix must not be empty"))
            else:
                # A non-reserved section is the legacy alias form only when it
                # contains exactly material=...; the key check below decides it.
                current_section = current_section
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        key_lower = key.lower()
        section_lower = current_section.lower()
        section_keys.setdefault(section_lower, set()).add(key_lower)
        if not section_seen:
            summary.errors.append(_schema_error(summary.path, line_no, "global", key, value, "global section must not contain fields"))
            continue
        if section_lower == "global":
            summary.errors.append(_schema_error(summary.path, line_no, current_section, key, value, "global section must not contain fields"))
            continue
        if section_lower.startswith("material.") and key_lower in {"temperature", "pressure"}:
            summary.errors.append(capability_message("materials.field.unsupported", field=key_lower))
            continue
        if section_lower.startswith("material.") and key_lower == "type":
            if value.strip().lower() != "material":
                summary.errors.append(_schema_error(
                    summary.path,
                    line_no,
                    current_section,
                    key,
                    value,
                    "deprecated compatibility field 'type' only accepts 'material'",
                ))
            continue
        is_legacy = section_lower not in allowed and not any(section_lower.startswith(prefix + ".") for prefix in ("isotope", "element", "material"))
        if is_legacy:
            if key_lower != "material":
                summary.errors.append(_schema_error(summary.path, line_no, current_section, key, value, "unknown legacy alias field; only material is allowed"))
            continue
        prefix = section_lower if section_lower in allowed else section_lower.split(".", 1)[0]
        if key_lower not in allowed[prefix]:
            suggestion = _suggestion(key_lower, allowed[prefix])
            detail = "unknown material configuration key"
            if suggestion:
                detail += f"; did you mean '{suggestion}'?"
            summary.errors.append(_schema_error(summary.path, line_no, current_section, key, value, detail))

    for section_lower, keys in section_keys.items():
        if section_lower in allowed or section_lower == "global":
            continue
        if any(section_lower.startswith(prefix + ".") for prefix in ("isotope", "element", "material")):
            continue
        if "material" not in keys:
            summary.errors.append(_schema_error(summary.path, section_lines[section_lower], section_lower, "<section>", "", "unknown material configuration section"))


def _schema_error(path: str, line_no: int, section: str, key: str, value: str, detail: str) -> str:
    return f"Material schema error: file '{path}', line {line_no}, section '{section}', key '{key}', value '{value}': {detail}"


def _suggestion(value: str, candidates: set[str]) -> str:
    def distance(left: str, right: str) -> int:
        previous = list(range(len(right) + 1))
        for i, left_char in enumerate(left, 1):
            current = [i]
            for j, right_char in enumerate(right, 1):
                current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (left_char != right_char)))
            previous = current
        return previous[-1]

    matches = sorted((distance(value, candidate), candidate) for candidate in candidates)
    return matches[0][1] if matches and matches[0][0] <= 3 else ""


def _strip_inline_comment(value: str) -> str:
    for marker in (" #", " ;"):
        index = value.find(marker)
        if index >= 0:
            value = value[:index].rstrip()
    return value


def _split_components(text: str) -> list[str]:
    if not text:
        return []
    items = []
    for part in text.replace(";", ",").split(","):
        item = part.strip()
        if not item:
            continue
        if ":" in item:
            item = item.split(":", 1)[0].strip()
        items.append(item)
    return items
