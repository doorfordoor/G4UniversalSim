from __future__ import annotations


_MESSAGES = {
    "geometry.gdml.unsupported": (
        "Geometry: GDML is not supported by the backend; use a supported "
        "geometry template and regular volume definitions."
    ),
    "geometry.placement.unsupported": (
        "Geometry: placement={placement} is not supported by the backend; "
        "use placement=normal with explicit child volumes."
    ),
    "materials.field.unsupported": (
        "Materials: {field} is not supported by the backend; remove it and "
        "use density, state, and composition only."
    ),
    "scoring.let.unsupported": (
        "LET is not supported by the backend because no reliable runtime "
        "LET calculation chain exists"
    ),
    "scoring.dose.unsupported": (
        "Dose is not supported by the backend; use Edep scoring instead"
    ),
    "scoring.fluence.unsupported": (
        "Fluence is not supported by the backend; use hits or Edep scoring instead"
    ),
}


def capability_message(key: str, **values: str) -> str:
    """Return the default text for a stable capability message key."""
    return _MESSAGES[key].format(**values)
