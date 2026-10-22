from __future__ import annotations


_MESSAGES = {
    "geometry.gdml.unsupported": (
        "Geometry: the GUI cannot generate GDML run packages; run a hand-written main INI with "
        "[geometry] template = gdml in external mode (backend built with Geant4 GDML), or use a "
        "supported geometry template and regular volume definitions."
    ),
    "geometry.gdml.external": (
        "Geometry: [gdml] is imported by the backend (template = gdml, Geant4 with GDML); "
        "the GUI geometry editors cannot edit GDML."
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
