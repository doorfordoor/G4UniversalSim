"""The configuration schema for the GUI (roadmap E2): field specs, value checks, hints.

The data is generated from schema/config_schema.json (``config_schema_data``); the checks
mirror how the backend reads a value (``ConfigValue::AsInt``/``AsBool``,
``UnitParser``, the enum parsers). These are necessary scalar checks, not a replacement
for contextual or runtime validation. Structured values deliberately have no scalar
acceptance result. ``scripts/test_config_schema.py`` checks startup values and full
context fixtures. Only migrated sections are described.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from g4usim_gui.core.config_schema_data import SCHEMA

INT32 = (-2147483648, 2147483647)
INTEGER = re.compile(r"[+-]?[0-9]+")
# std::strtod: decimal, hexadecimal, inf and nan (the last two are refused as not finite)
NUMBER = re.compile(r"[+-]?(?:0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?[0-9]+)?"
                    r"|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|inf(?:inity)?|nan(?:\([^)]*\))?)", re.IGNORECASE)
ENERGY_UNITS = {"eV": 1e-6, "keV": 1e-3, "MeV": 1.0, "GeV": 1e3}
UNITS = {
    "energy": ENERGY_UNITS,
    "length": {"nm": 1e-6, "um": 1e-3, "mm": 1.0, "cm": 10.0, "m": 1000.0},
    "angle": {"deg": math.pi / 180.0, "rad": 1.0},
    "time": {"ps": .001, "ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9,
             "min": 60e9, "h": 3600e9, "d": 86400e9, "day": 86400e9,
             "y": 365 * 86400e9, "year": 365 * 86400e9},
    "number": {},
}
TRUE, FALSE = {"true", "yes", "on", "1"}, {"false", "no", "off", "0"}


@dataclass(frozen=True)
class FieldSpec:
    file: str
    section: str
    key: str               # canonical name
    data: dict

    @property
    def type(self) -> str:
        return self.data["type"]

    @property
    def default(self) -> str | None:
        return self.data["default"]

    def hint(self, language: str = "en") -> str:
        """A tooltip: the INI field, its description and the accepted values."""
        zh = language == "zh_CN"
        parts = [self.data["description_zh" if zh else "description"]]
        low, high = self.data.get("min"), self.data.get("max")
        if self.type == "enum":
            parts.append(("取值：" if zh else "values: ") + ", ".join(self.data["allowed"]))
        elif low is not None and self.type in {"int", "energy"} and (low, high) != INT32:
            parts.append(f"{'取值' if zh else 'value'} >= {low}" + (" MeV" if self.type == "energy" else ""))
        if self.default not in (None, ""):
            parts.append(f"{'默认' if zh else 'default'} {self.default}")
        return f"[{self.section}] {self.key}{'：' if zh else ': '}" + ("；" if zh else "; ").join(parts)


def sections(file: str = "main_ini") -> list[str]:
    return list(SCHEMA.get(file, {}))


def spec(section: str, key: str, file: str = "main_ini") -> FieldSpec | None:
    """The field a key (or one of its aliases, any case) names, in a migrated section."""
    keys = section_spec(section, file).get("keys", {})
    wanted = key.strip().lower()
    for name, data in keys.items():
        if _matches(name.lower(), wanted, file) or wanted in (alias.lower() for alias in data.get("aliases", [])):
            inherited = {k: v for k, v in section_spec(section, file).items()
                         if k in {"parser", "validation", "tests", "gui"}}
            return FieldSpec(file, section.strip().lower(), name, {**inherited, **data})
    return None


def _matches(pattern: str, value: str, file: str) -> bool:
    if pattern == value:
        return True
    token = r"[^.]+" if file == "main_ini" else r".+"
    expression = token.join(re.escape(p) for p in re.split(r"<[^>]+>", pattern))
    return bool(re.fullmatch(expression, value))


def section_spec(section: str, file: str = "main_ini") -> dict:
    """Look up descriptors, not acceptance: parsers still enforce section grammar.

    Exact sections win over templates, and a specific template wins over <alias>.
    Material aliases are a legacy syntax requiring a material key in the actual file.
    """
    value = section.strip().lower()
    items = SCHEMA.get(file, {})
    if value in items:
        return items[value]
    for pattern in sorted(items, key=lambda p: len(re.sub(r"<[^>]+>", "", p)), reverse=True):
        if "<" in pattern and _matches(pattern, value, file):
            return items[pattern]
    return {}


def check_value(section: str, key: str, text: str, *, base_dir: str | Path | None = None,
                file: str = "main_ini") -> str | None:
    """Check a scalar, not a complete configuration. None means scalar checks pass.

    Structured values need their contextual parser; raise rather than silently
    accepting them. Cross-field, compiled-capability and runtime checks remain
    mandatory even when a scalar is valid.
    """
    field = spec(section, key, file)
    if field is None:
        return f"[{section}]/{key} is not a known field"
    data, where = field.data, f"[{field.section}]/{key}"
    if data.get("support") == "unsupported":
        return f"{where} is unsupported: {data['description']}"
    if field.type == "structured":
        raise ValueError(f"{where} requires contextual validation by {data.get('parser', 'the backend')}")
    value = text.strip()
    if not value and data.get("empty") == "default":
        return None          # the backend reads an empty value as absent
    if field.type == "int":
        if not INTEGER.fullmatch(value):
            return f"{where} must be an integer, got {text!r}"
        number = int(value)
        if not INT32[0] <= number <= INT32[1]:
            return f"{where} = {value} is out of range for a 32-bit integer"
        return _bounds(where, number, data)
    if field.type == "bool":
        return None if value.lower() in TRUE | FALSE else f"{where} must be true or false, got {text!r}"
    if field.type == "enum":
        normalize = (lambda v: v) if data.get("case_sensitive") else str.lower
        allowed = [normalize(v) for v in data["allowed"]] + [normalize(v) for v in data.get("value_aliases", {})]
        return None if normalize(value) in allowed else f"{where} must be one of {', '.join(data['allowed'])}, got {text!r}"
    if field.type in UNITS:
        number = quantity(value, field.type)
        if number is None:
            return f"{where} must be a finite {field.type} (units {', '.join(UNITS[field.type])}), got {text!r}"
        return _bounds(where, number, data)
    if field.type == "existing_file":
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute() and base_dir is not None:
            path = Path(base_dir) / path
        return None if path.is_file() else f"{where}: the file {value} does not exist"
    if "\n" in text or "\r" in text:
        return f"{where} must be a single line"
    if len(value) < data.get("min_length", 0):
        return f"{where} must not be empty"
    return None


def energy_mev(text: str) -> float | None:
    """``UnitParser::ParseEnergy``: a number, then an optional '*' and a unit without spaces."""
    return quantity(text, "energy")


def quantity(text: str, kind: str) -> float | None:
    """UnitParser scalar grammar, in Geant4 base units; includes conversion overflow."""
    match = NUMBER.match(text.strip())
    if not match:
        return None
    try:
        number = float.fromhex(match.group(0)) if "x" in match.group(0).lower() else float(match.group(0))
    except (ValueError, OverflowError):
        return None
    unit = text.strip()[match.end():].strip()
    if unit.startswith("*") and kind != "number":
        unit = unit[1:].strip()
    if not math.isfinite(number) or any(c.isspace() for c in unit):
        return None
    if not unit:
        return number
    if unit not in UNITS[kind]:
        return None
    result = number * UNITS[kind][unit]
    return result if math.isfinite(result) else None


def _bounds(where: str, number: float, data: dict) -> str | None:
    low, high = data.get("min"), data.get("max")
    if data.get("exclusive_min") is not None and number <= data["exclusive_min"]:
        return f"{where} must be > {data['exclusive_min']}"
    if low is not None and number < low:
        return f"{where} must be >= {low}"
    if high is not None and number > high:
        return f"{where} must be <= {high}"
    return None
