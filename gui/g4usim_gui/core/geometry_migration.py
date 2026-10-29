"""Conservative, source-preserving geometry v2 copy plans.

This is a format/schema check, not a second geometry builder. The real backend
must still inspect/build the resulting configuration before it is run.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from g4usim_gui.core.config_migration import MigrationPlan, digest
from g4usim_gui.core.config_schema import section_spec, spec

TEMPLATE_ALIASES = {"simple": "simple_box", "layered": "layered_device",
                    "hierarchical_boolean": "hierarchical", "boolean_hierarchical": "hierarchical",
                    "boolean": "hierarchical"}


@dataclass(frozen=True)
class _Field:
    line: int
    section: str
    key: str
    value: str
    key_start: int
    key_end: int
    value_start: int
    value_end: int


def _scan(text: str, source: str) -> tuple[list[str], list[tuple[str, int]], list[_Field]]:
    if "\r" in text.replace("\r\n", "") or any(char in text for char in "\x85\u2028\u2029\x1c\x1d\x1e"):
        raise ValueError(f"{source}: unsupported line separator; use LF or CRLF without changing field values")
    # Match std::getline: only LF separates source statements, preserving CRLF.
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    sections = []
    fields = []
    seen_sections = set()
    seen_fields = set()
    section = "global"
    for index, raw in enumerate(lines):
        clean = re.split(r"[#;]", raw, maxsplit=1)[0].strip(" \t\r\n\v\f")
        if not clean:
            continue
        if clean.startswith("[") and clean.endswith("]"):
            section = clean[1:-1].strip(" \t\r\n\v\f")
            normalized = section.lower()
            if not section or normalized in seen_sections:
                raise ValueError(f"{source}:{index + 1} [{section}]: empty or duplicate geometry section")
            seen_sections.add(normalized)
            sections.append((section, index))
            continue
        if "=" not in clean:
            raise ValueError(f"{source}:{index + 1}: invalid geometry INI line")
        equal = raw.index("=")
        key = raw[:equal].strip(" \t\r\n\v\f")
        if any(char.isspace() and ord(char) > 127 for char in section + key):
            raise ValueError(f"{source}:{index + 1}: non-ASCII whitespace in geometry section/key")
        value_part = raw[equal + 1:]
        comment = re.search(r"[#;\r\n]", value_part)
        end = equal + 1 + (comment.start() if comment else len(value_part))
        start = equal + 1
        while start < end and raw[start] in " \t\r\n\v\f":
            start += 1
        while end > start and raw[end - 1] in " \t\r\n\v\f":
            end -= 1
        identity = (section.lower(), key.lower())
        if not key or identity in seen_fields:
            raise ValueError(f"{source}:{index + 1} [{section}]/{key}: empty or duplicate geometry key")
        seen_fields.add(identity)
        key_start = len(raw[:equal]) - len(raw[:equal].lstrip())
        fields.append(_Field(index, section, key, raw[start:end], key_start, key_start + len(key), start, end))
    return lines, sections, fields


def plan_geometry_migration(source: str | Path, template_name: str, *,
                            metadata_mapping: dict[str, str] | None = None) -> MigrationPlan:
    path = Path(source).resolve(strict=True)
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines, sections, fields = _scan(text, str(path))
    mode = template_name.strip().lower()
    mode = TEMPLATE_ALIASES.get(mode, mode)
    if mode not in {"simple_box", "layered_device", "hierarchical", "array", "shielding", "gdml"}:
        raise ValueError(f"Unsupported geometry template: {template_name}")
    schema_file = f"geometry_{mode}_ini"
    mappings = dict(metadata_mapping or {})
    used = set()
    changes = []
    version = None
    versions = [f for f in fields if f.section.lower() == "global" and f.key.lower() == "version"]
    if versions:
        if versions[0].value not in {"1", "2"}:
            raise ValueError(f"{path}:{versions[0].line + 1}: supported geometry versions are 1 and 2")
        version = int(versions[0].value)
    names = {}
    for field in fields:
        names[(field.section.lower(), field.key.lower())] = field.value
    layer_names = {x.strip().lower() for x in names.get(("layers", "names"), "").split(",")}
    shield_names = {x.strip().lower() for x in names.get(("shielding", "layers"), "").split(",")}

    def supported_section(section):
        lower = section.lower()
        if not section_spec(lower, schema_file):
            return False
        if mode == "layered_device" and lower.startswith("layer."):
            return lower[6:] in layer_names
        if mode == "shielding" and lower.startswith("shield."):
            return lower[7:] in shield_names
        if mode == "hierarchical" and ".boolean." in lower:
            return bool(re.fullmatch(r"volume\..+\.boolean\.[0-9]+", lower))
        return True

    for section, index in sections:
        if not supported_section(section):
            raise ValueError(f"{path}:{index + 1} [{section}]: unknown geometry section for {mode}")
    existing = {(f.section.lower(), f.key.lower()) for f in fields}
    for field in fields:
        section, key = field.section.lower(), field.key.lower()
        where = f"{path}:{field.line + 1} [{field.section}]/{field.key}"
        if section == "global" and key == "version":
            lines[field.line] = lines[field.line][:field.value_start] + "2" + lines[field.line][field.value_end:]
            continue
        descriptor = spec(section, key, schema_file)
        replacement_key = field.key
        replacement_value = field.value
        if descriptor is None:
            mapping_key = f"[{field.section}]/{field.key}"
            replacement_key = mappings.get(mapping_key, "")
            # Mapping is explicit, and only applies to the legacy metadata
            # namespace accepted by these existing backend templates.
            ordinary = (mode == "hierarchical" and (section == "world" or section.startswith("volume."))
                        and ".boolean." not in section) or (mode == "layered_device" and section.startswith("layer."))
            if (not ordinary or key.startswith(("vis.", "cut.", "metadata."))
                    or not re.fullmatch(r"metadata\.[A-Za-z0-9_.-]+", replacement_key, re.IGNORECASE)):
                raise ValueError(f"{where}: unknown field; explicit legacy metadata mapping required where supported")
            if (section, replacement_key.lower()) in existing:
                raise ValueError(f"{where}: metadata destination collision: {replacement_key}")
            descriptor = spec(section, replacement_key, schema_file)
            if descriptor is None:
                raise ValueError(f"{where}: unsupported metadata destination {replacement_key}")
            existing.add((section, replacement_key.lower()))
            used.add(mapping_key)
            changes.append(f"[{field.section}]/{field.key} -> {replacement_key}")
        if descriptor.data.get("recognition") == "parser_only":
            raise ValueError(f"{where}: field is not accepted by strict geometry v2 diagnostics")
        if descriptor.data.get("support") == "unsupported" or (key == "placement" and field.value.lower() == "assembly"):
            raise ValueError(f"{where}: unsupported geometry capability")
        if key in {"file", "copies_file"}:
            resource = Path(field.value)
            if not field.value or any(c in field.value for c in "\r\n#;"):
                raise ValueError(f"{where}: invalid geometry resource path")
            if not resource.is_absolute():
                resource = path.parent / resource
                replacement_value = str(resource.resolve(strict=True))
                if any(c in replacement_value for c in "\r\n#;"):
                    raise ValueError(f"{where}: resolved resource path cannot be represented by geometry INI")
                if not resource.is_file():
                    raise ValueError(f"{where}: geometry resource is not a file")
                changes.append(f"[{field.section}]/{field.key}: retain original resource {replacement_value}")
            elif not resource.is_file():
                raise ValueError(f"{where}: geometry resource does not exist")
        raw_line = lines[field.line]
        lines[field.line] = (raw_line[:field.key_start] + replacement_key + raw_line[field.key_end:field.value_start]
                             + replacement_value + raw_line[field.value_end:])
    if set(mappings) != used:
        raise ValueError("Unused or conflicting metadata mappings: " + ", ".join(sorted(set(mappings) - used)))
    newline = "\r\n" if "\r\n" in text else "\n"
    global_sections = [index for section, index in sections if section.lower() == "global"]
    if not versions:
        if global_sections:
            index = global_sections[0]
            if not lines[index].endswith(("\n", "\r")):
                lines[index] += newline
            lines.insert(index + 1, "version = 2" + newline)
        else:
            lines.insert(0, f"[global]{newline}version = 2{newline}")
    elif not any(index < versions[0].line for index in global_sections):
        if global_sections:
            raise ValueError("Implicit and explicit [global] cannot be migrated without restructuring the source")
        lines.insert(0, "[global]" + newline)
    changes.insert(0, f"Geometry version {version if version is not None else 'absent (legacy 1)'} -> 2")
    payload = "".join(lines).encode("utf-8")
    _scan(payload.decode("utf-8"), str(path))
    return MigrationPlan("geometry", str(path), digest(raw), version, 2, tuple(changes),
                         ("Strict v2 field recognition, duplicate declarations, and explicit metadata mappings checked",
                          "Relative resource targets retained using absolute paths",
                          "Backend Inspect inputs is still required for complete geometry/material/capability validation",
                          "No simulation or physics validation; existing GUI editing limits remain"), payload)
