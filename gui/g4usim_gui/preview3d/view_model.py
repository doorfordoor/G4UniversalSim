"""What the 3D view shows and how (roadmap G2/G3), without Qt or VTK.

Both the Geant4 world (backend mesh) and the editor sketch become a list of ViewItems:
one per volume copy, keyed by its touchable path. ViewState decides, per item,
whether it is drawn (world, hidden, isolated, per-material legend toggles), its colour
(one per material, with fixed colours for common materials) and its look (selected,
sensitive, world), and where the section plane cuts. The widget only applies these.
Volume names: the backend calls physical volumes "<name>_PV" and logical ones
"<name>_LV"; the editor's name is what remains.
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field

Bounds = tuple[float, float, float, float, float, float]

# common materials keep their colour from scene to scene (keys: lower case, aliases included)
KNOWN_COLOURS = {
    "g4_water": "#4f9bd9", "water": "#4f9bd9",
    "g4_pb": "#7d858f", "lead": "#7d858f",
    "g4_al": "#b9c3cc", "aluminum": "#b9c3cc", "aluminium": "#b9c3cc",
    "g4_si": "#8c7bc9", "silicon": "#8c7bc9",
    "g4_cu": "#d0864a", "copper": "#d0864a",
    "g4_fe": "#a0705c", "iron": "#a0705c",
    "g4_w": "#5d6670", "tungsten": "#5d6670",
    "g4_sodium_iodide": "#e2b64a", "g4_cesium_iodide": "#d9a441", "g4_bgo": "#c9a227",
    "g4_ge": "#6f9f8f", "g4_polyethylene": "#d9d4c7", "g4_plastic_sc_vinyltoluene": "#9fd0c4",
    "g4_silicon_dioxide": "#c7b9e6", "g4_kapton": "#e09a3e", "g4_ti": "#9aa6b2",
}
# for the others, in order of first appearance (sorted by name for a stable legend)
PALETTE = ("#e15759", "#59a14f", "#f28e2b", "#4e79a7", "#b07aa1", "#76b7b2", "#edc948",
           "#ff9da7", "#9c755f", "#86bcb6", "#d37295", "#a0cbe8")
EMPTY_MATERIALS = {"g4_air", "air", "g4_galactic", "galactic", "vacuum"}

# camera presets: (direction from the focal point to the camera, view-up)
CAMERA_PRESETS = {
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),   # looking along +y, beam (+z) upwards
    "side": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "iso": ((1.0, -1.0, 0.8), (0.0, 0.0, 1.0)),
}
AXES = {"x": 0, "y": 1, "z": 2}


def volume_name(name: str) -> str:
    """The editor's volume name of a Geant4 physical/logical volume name."""
    return re.sub(r"_(PV|LV)$", "", name.strip())


@dataclass
class ViewItem:
    key: str                     # touchable path (backend) or editor name (sketch)
    name: str                    # editor volume name
    material: str = ""
    solid: str = ""
    sensitive: bool = False
    world: bool = False
    container: bool = False      # has daughters: drawn as faint glass so they stay visible
    copy: int = 0
    cubic_volume_mm3: float | None = None
    bounds: Bounds | None = None

    def describe(self) -> str:
        parts = [self.name + (f" #{self.copy}" if self.copy else ""), self.material or "?", self.solid]
        if self.cubic_volume_mm3 is not None:
            parts.append(f"{self.cubic_volume_mm3 / 1000.0:.4g} cm3")
        if self.sensitive:
            parts.append("sensitive")
        return "  |  ".join(p for p in parts if p)


@dataclass
class ViewState:
    items: list[ViewItem] = field(default_factory=list)
    show_world: bool = False
    hidden: set[str] = field(default_factory=set)            # volume names
    hidden_materials: set[str] = field(default_factory=set)
    isolated: str | None = None                               # volume name
    selected: str | None = None                               # volume name
    section_axis: str = ""                                    # "", "x", "y", "z"
    section_fraction: float = 0.5                             # 0..1 across the visible bounds
    tracks_shown: bool = False                                # particle tracks drawn: volumes become glass (G6)
    # Transient view preferences only. Never part of GeometryDocument / F5 inputs.
    volume_appearance: dict[str, dict] = field(default_factory=dict)  # exact touchable key
    material_appearance: dict[str, dict] = field(default_factory=dict)
    geometry_identity: str | None = None

    def set_items(self, items: list[ViewItem], *, geometry_identity: str | None = None) -> None:
        """New geometry: keep choices that still apply (same volumes/materials), drop the rest."""
        identity = geometry_identity or repr(items)
        previous = self.geometry_identity or (repr(self.items) if self.items else None)
        if previous is not None and previous != identity:
            # A same-named/path object in another geometry must not inherit overrides.
            self.reset_appearance()
        self.geometry_identity = identity
        self.items = items
        names = {item.name for item in items}
        materials = {item.material for item in items}
        self.volume_appearance = {k: v for k, v in self.volume_appearance.items() if k in {i.key for i in items}}
        self.material_appearance = {k: v for k, v in self.material_appearance.items() if k in materials}
        self.hidden &= names
        self.hidden_materials &= materials
        if self.isolated not in names:
            self.isolated = None
        if self.selected not in names:
            self.selected = None

    # --- what is drawn ------------------------------------------------------------
    def visible(self, item: ViewItem) -> bool:
        if item.world:
            return self.show_world and self.isolated is None
        if self.isolated is not None:
            return item.name == self.isolated
        return item.name not in self.hidden and item.material not in self.hidden_materials

    def track_glass_opacity(self) -> float:
        """Opacity of volumes while tracks are shown: a line of sight crosses about two surfaces
        per visible volume, so with many volumes (a stack of 40 slabs) each must be fainter for
        the stack to stay at most half opaque."""
        surfaces = 2 * max(1, sum(1 for item in self.items if not item.world and self.visible(item)))
        return min(0.15, max(0.01, 1.0 - 0.5 ** (1.0 / surfaces)))

    def colours(self) -> dict[str, str]:
        """Material -> colour; known materials fixed, others from the palette in name order."""
        result: dict[str, str] = {}
        others = []
        for material in sorted({item.material for item in self.items if not item.world}, key=str.lower):
            known = KNOWN_COLOURS.get(material.lower())
            if known:
                result[material] = known
            else:
                others.append(material)
        free = [c for c in PALETTE if c not in result.values()] or list(PALETTE)
        for index, material in enumerate(others):
            result[material] = free[index % len(free)]
        for material, preference in self.material_appearance.items():
            if material in result and "colour" in preference:
                result[material] = preference["colour"]
        return result

    def set_appearance(self, scope: str, target: str, *, colour: str | None = None,
                       opacity: float | None = None) -> None:
        """Set explicit properties atomically; volume properties override material properties."""
        if scope not in ("volume", "material"):
            raise ValueError("Unknown appearance scope")
        valid = {i.key if scope == "volume" else i.material for i in self.items}
        if target not in valid:
            raise ValueError("Unknown appearance target")
        value = {}
        if colour is not None:
            if not isinstance(colour, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", colour) is None:
                raise ValueError("Expected #RRGGBB colour")
            value["colour"] = colour.lower()
        if opacity is not None:
            if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not math.isfinite(opacity) or not 0 <= opacity <= 1:
                raise ValueError("Opacity must be finite and between 0 and 1")
            value["opacity"] = float(opacity)
        store = self.volume_appearance if scope == "volume" else self.material_appearance
        store[target] = {**store.get(target, {}), **value}

    def reset_appearance(self, scope: str | None = None, target: str | None = None) -> None:
        if scope is None:
            self.volume_appearance.clear()
            self.material_appearance.clear()
        elif scope in ("volume", "material"):
            (self.volume_appearance if scope == "volume" else self.material_appearance).pop(target, None)
        else:
            raise ValueError("Unknown appearance scope")

    def explicit_appearance(self, item: ViewItem) -> dict:
        return {**self.material_appearance.get(item.material, {}), **self.volume_appearance.get(item.key, {})}

    def style(self, item: ViewItem) -> dict:
        """Colour, opacity and outline of an item (the widget maps them to VTK properties)."""
        if item.world:
            return {"colour": None, "opacity": 0.25, "wireframe": True, "selected": False,
                    **self.explicit_appearance(item)}
        selected = item.name == self.selected
        empty = item.material.lower() in EMPTY_MATERIALS
        opacity = 0.12 if empty or item.container else 0.9 if item.sensitive else 0.6
        if self.isolated is not None or selected:
            opacity = max(opacity, 0.85)
        elif self.selected is not None:
            opacity *= 0.45      # the others fade while a volume is selected
        if self.tracks_shown and not selected:
            opacity = min(opacity, self.track_glass_opacity())   # tracks inside volumes stay visible
        return {"colour": self.colours().get(item.material, "#9aa6b2"), "opacity": opacity,
                "wireframe": False, "selected": selected, **self.explicit_appearance(item)}

    def legend(self) -> list[tuple[str, str, int, bool]]:
        """(material, colour, volume copies, shown) for the legend."""
        counts: dict[str, int] = {}
        for item in self.items:
            if not item.world:
                counts[item.material] = counts.get(item.material, 0) + 1
        colours = self.colours()
        return [(material, colours[material], counts[material], material not in self.hidden_materials)
                for material in sorted(counts, key=str.lower)]

    # --- selection and visibility commands ---------------------------------------------
    def select(self, name: str | None) -> None:
        self.selected = name if name and any(item.name == name for item in self.items) else None

    def hide_selected(self) -> None:
        if self.selected:
            self.hidden.add(self.selected)
            if self.isolated == self.selected:
                self.isolated = None
            self.selected = None

    def isolate_selected(self) -> None:
        if self.selected:
            self.isolated = self.selected

    def show_all(self) -> None:
        self.hidden.clear()
        self.hidden_materials.clear()
        self.isolated = None

    def toggle_material(self, material: str, shown: bool) -> None:
        (self.hidden_materials.discard if shown else self.hidden_materials.add)(material)

    # --- section plane -----------------------------------------------------------------
    def visible_bounds(self) -> Bounds | None:
        boxes = [item.bounds for item in self.items if item.bounds and self.visible(item)]
        if not boxes:
            boxes = [item.bounds for item in self.items if item.bounds]
        if not boxes:
            return None
        return (min(b[0] for b in boxes), max(b[1] for b in boxes), min(b[2] for b in boxes),
                max(b[3] for b in boxes), min(b[4] for b in boxes), max(b[5] for b in boxes))

    def section_plane(self) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        """(origin, normal) of the cut, keeping the side below the plane; None when off."""
        if self.section_axis not in AXES:
            return None
        bounds = self.visible_bounds()
        if bounds is None:
            return None
        axis = AXES[self.section_axis]
        low, high = bounds[2 * axis], bounds[2 * axis + 1]
        origin = [(bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, (bounds[4] + bounds[5]) / 2]
        origin[axis] = low + (high - low) * min(max(self.section_fraction, 0.0), 1.0)
        normal = [0.0, 0.0, 0.0]
        normal[axis] = -1.0       # vtkPlane keeps the half the normal points into
        return tuple(origin), tuple(normal)


def bounds_of(vertices) -> Bounds | None:
    if not len(vertices):
        return None
    xs, ys, zs = zip(*vertices)
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def mark_containers(items: list[ViewItem]) -> None:
    """Sketch items: a volume whose box holds another volume's box is a container."""
    boxes = [(item, item.bounds) for item in items if item.bounds and not item.world]
    for item, outer in boxes:
        item.container = any(
            other is not item and all(outer[2 * a] <= inner[2 * a] and inner[2 * a + 1] <= outer[2 * a + 1]
                                      for a in range(3)) and inner != outer
            for other, inner in boxes)


def backend_items(mesh) -> list[ViewItem]:
    """ViewItems of a BackendMesh (every volume copy Geant4 built); daughters from the touchable paths."""
    parents = {v.path.rsplit("/", 1)[0] for v in mesh.volumes}
    return [ViewItem(key=v.path, name=volume_name(v.logical or v.name), material=v.material, solid=v.solid,
                     sensitive=v.sensitive, world=v.depth == 0, container=v.path in parents, copy=v.copy,
                     cubic_volume_mm3=v.cubic_volume_mm3, bounds=bounds_of(v.vertices))
            for v in mesh.volumes if v.vertices and v.faces]
