from __future__ import annotations

import math
import re


_LENGTH_FACTORS_MM = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "um": 1.0e-3,
    "µm": 1.0e-3,
    "micrometer": 1.0e-3,
    "micrometers": 1.0e-3,
    "nm": 1.0e-6,
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
}


def parse_length_to_mm(text: str) -> float | None:
    value, unit = _parse_value_unit(text)
    if value is None:
        return None
    if not unit:
        return value
    factor = _LENGTH_FACTORS_MM.get(unit.lower())
    if factor is None:
        return None
    return value * factor


def parse_angle_deg(text: str) -> float | None:
    value, unit = _parse_value_unit(text)
    if value is None:
        return None
    if not unit:
        return value
    unit = unit.lower()
    if unit in {"deg", "degree", "degrees"}:
        return value
    if unit in {"rad", "radian", "radians"}:
        return math.degrees(value)
    return None


def parse_vec3_to_mm(text: str) -> tuple[float, float, float] | None:
    return _parse_vec3(text, parse_length_to_mm, default_unit="mm")


def parse_vec3_deg(text: str) -> tuple[float, float, float] | None:
    return _parse_vec3(text, parse_angle_deg, default_unit="deg")


def parse_direction(text: str) -> tuple[float, float, float] | None:
    parts = _split_vec(text)
    if len(parts) != 3:
        return None
    try:
        values = tuple(float(part.strip()) for part in parts)
    except ValueError:
        return None
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0.0:
        return None
    return tuple(value / norm for value in values)  # type: ignore[return-value]


def _parse_vec3(text: str, scalar_parser, *, default_unit: str) -> tuple[float, float, float] | None:
    parts = _split_vec(text)
    if len(parts) != 3:
        return None
    last_unit = _extract_unit(parts[-1])
    parsed = []
    for part in parts:
        token = part.strip()
        if last_unit and not _extract_unit(token):
            token = f"{token} {last_unit}"
        elif not last_unit and not _extract_unit(token) and default_unit:
            token = f"{token} {default_unit}"
        value = scalar_parser(token)
        if value is None:
            return None
        parsed.append(value)
    return (parsed[0], parsed[1], parsed[2])


def _split_vec(text: str) -> list[str]:
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    tokens = [token for token in text.split() if token]
    if len(tokens) == 3:
        return tokens
    if len(tokens) == 6:
        return [f"{tokens[0]} {tokens[1]}", f"{tokens[2]} {tokens[3]}", f"{tokens[4]} {tokens[5]}"]
    return tokens


def _parse_value_unit(text: str) -> tuple[float | None, str]:
    token = text.strip().replace("*", " ")
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-zµ]*)", token)
    if not match:
        return None, ""
    try:
        return float(match.group(1)), match.group(2)
    except ValueError:
        return None, ""


def _extract_unit(text: str) -> str:
    match = re.search(r"([A-Za-zµ]+)\s*$", text.strip())
    return match.group(1) if match else ""
