"""The configuration schema for the GUI (roadmap E2): field specs, value checks, hints.

The data is generated from schema/config_schema.json (``config_schema_data``); the checks
mirror how the backend reads a value (``ConfigValue::AsInt``/``AsBool``,
``UnitParser::ParseEnergy``, the enum parsers), so the GUI rejects what the backend
rejects. ``scripts/test_config_schema.py`` runs both on the same values to keep them in
step. Only migrated sections are described; ``spec`` returns None for the others.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from g4usim_gui.core.config_schema_data import SCHEMA

INT32 = (-2147483648, 2147483647)
INTEGER = re.compile(r"[+-]?\d+")
# std::strtod: decimal, hexadecimal, inf and nan (the last two are refused as not finite)
NUMBER = re.compile(r"[+-]?(?:0[xX](?:[0-9a-fA-F]+\.?[0-9a-fA-F]*|\.[0-9a-fA-F]+)(?:[pP][+-]?\d+)?"
                    r"|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|inf(?:inity)?|nan(?:\([^)]*\))?)", re.IGNORECASE)
ENERGY_UNITS = {"eV": 1e-6, "keV": 1e-3, "MeV": 1.0, "GeV": 1e3}
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
    keys = SCHEMA.get(file, {}).get(section.strip().lower(), {}).get("keys", {})
    wanted = key.strip().lower()
    for name, data in keys.items():
        if wanted == name.lower() or wanted in (alias.lower() for alias in data.get("aliases", [])):
            return FieldSpec(file, section.strip().lower(), name, data)
    return None


def check_value(section: str, key: str, text: str, *, base_dir: str | Path | None = None,
                file: str = "main_ini") -> str | None:
    """None when the backend accepts ``text`` for this field, else the reason (English)."""
    field = spec(section, key, file)
    if field is None:
        return f"[{section}]/{key} is not a known field"
    data, where = field.data, f"[{field.section}]/{key}"
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
        allowed = [v.lower() for v in data["allowed"]] + [v.lower() for v in data.get("value_aliases", {})]
        return None if value.lower() in allowed else f"{where} must be one of {', '.join(data['allowed'])}, got {text!r}"
    if field.type == "energy":
        number = energy_mev(value)
        if number is None:
            return f"{where} must be an energy such as '5 MeV' (units eV, keV, MeV, GeV), got {text!r}"
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
    return None


def energy_mev(text: str) -> float | None:
    """``UnitParser::ParseEnergy``: a number, then an optional '*' and a unit without spaces."""
    match = NUMBER.match(text.strip())
    if not match:
        return None
    try:
        number = float.fromhex(match.group(0)) if "x" in match.group(0).lower() else float(match.group(0))
    except ValueError:
        return None
    unit = text.strip()[match.end():].strip()
    if unit.startswith("*"):
        unit = unit[1:].strip()
    if not math.isfinite(number) or any(c.isspace() for c in unit):
        return None
    if not unit:
        return number
    return number * ENERGY_UNITS[unit] if unit in ENERGY_UNITS else None


def _bounds(where: str, number: float, data: dict) -> str | None:
    low, high = data.get("min"), data.get("max")
    if low is not None and number < low:
        return f"{where} must be >= {low}"
    if high is not None and number > high:
        return f"{where} must be <= {high}"
    return None
