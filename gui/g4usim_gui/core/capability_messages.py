from __future__ import annotations


_MESSAGES = {
    "geometry.gdml.unsupported": (
        "Geometry: GDML is not supported by the backend; use a supported "
        "geometry template and regular volume definitions."
    ),
    "geometry.placement.unsupported": (
        "Geometry: placement={placement} is not supported by the backend; "
        "use placement=normal with explicit child volumes, or placement=parameterised."
    ),
    "materials.field.unsupported": (
        "Materials: {field} is not supported by the backend; remove it and "
        "use density, state, and composition only."
    ),
    "scoring.let.unsupported": (
        "LET is experimental and not yet editable in this GUI; enable it with "
        "[scoring] let = true in an external main INI"
    ),
    "scoring.dose.unsupported": (
        "Dose is experimental and only supports sensitive physical touchables with default scorers"
    ),
    "scoring.fluence.unsupported": (
        "Fluence is experimental: track length in daughter-free sensitive solids with default scorers only"
    ),
}


def capability_message(key: str, **values: str) -> str:
    """Return the default text for a stable capability message key."""
    return _MESSAGES[key].format(**values)
