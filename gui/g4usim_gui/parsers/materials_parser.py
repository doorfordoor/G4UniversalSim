from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.parsers.ini_light_parser import parse_ini_light


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
