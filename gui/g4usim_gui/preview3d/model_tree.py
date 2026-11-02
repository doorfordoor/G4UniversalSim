"""Model tree of the geometry editor (roadmap J3, usability).

The 3D preview draws the scene; this module turns the editor's geometry document into
a parent/child tree so the user can see which volume sits in which mother volume and
pick a volume by name instead of clicking it in the viewport.

Kept pure (no Qt) so it can be unit-tested without a widget.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# only an empty parent means "this row sits directly in the world": the world
# volume itself is an ordinary row whose name may also be "world"
WORLD_NAMES = ("",)

#: how many rows a mode that cannot express a hierarchy still shows as one level
FLAT_MODES = ("preview_only", "template_flat", "flat", "")


@dataclass(frozen=True)
class ModelNode:
    """One row of the model tree; ``key`` is the editor volume name used by the 3D view."""

    key: str
    label: str
    material: str = ""
    sensitive: bool = False
    role: str = ""
    children: tuple["ModelNode", ...] = field(default_factory=tuple)


def build_model_tree(geometry) -> ModelNode:
    """Build the tree of *geometry* (a ``GeometryDocument``); always returns a World root."""
    mode = str(getattr(geometry, "mode", ""))
    world_material = ""
    if getattr(geometry, "simple_box", None) is not None:
        world_material = geometry.simple_box.world_material
    if getattr(geometry, "layered_device", None) is not None and not world_material:
        world_material = geometry.layered_device.world_material
    world_key = "world"
    if mode in ("simple_box", "simplebox"):
        simple = geometry.simple_box
        target = ModelNode(
            key=simple.target_name or "target",
            label=simple.target_name or "Target",
            material=simple.target_material,
            sensitive=bool(getattr(simple, "target_sensitive", True)),
            role="target",
        )
        return ModelNode(world_key, "World", world_material, role="world",
                         children=(target,))
    if mode in ("layered_device", "layereddevice", "layered"):
        layers = []
        for index, layer in enumerate(getattr(geometry.layered_device, "layers", ()) or (), start=1):
            if not layer.enabled:
                continue
            layers.append(ModelNode(
                key=layer.name,
                label=layer.name or f"Layer {index}",
                material=layer.material,
                sensitive=layer.sensitive,
                role="layer",
            ))
        return ModelNode(world_key, "World", world_material, role="world",
                         children=tuple(layers))

    rows = [row for row in getattr(geometry, "volumes", ()) if getattr(row, "enabled", True)]
    if not rows:
        return ModelNode(world_key, "World", world_material, role="world")

    by_name = {row.name: row for row in rows if row.name}
    children: dict[str, list] = {}
    roots = []
    for row in rows:
        parent = row.parent if row.parent not in WORLD_NAMES else ""
        if parent and parent in by_name and parent != row.name:
            children.setdefault(parent, []).append(row)
        else:
            roots.append(row)

    if not roots:
        # a document whose rows all point at each other still shows one entry
        roots = [rows[0]]

    def node_for(row, chain: tuple[str, ...]) -> ModelNode:
        if row.name in chain:
            # a parent cycle in an editor document must not hang the GUI
            return ModelNode("", row.name, row.material, row.sensitive,
                             role="cycle")
        kids = tuple(node_for(child, chain + (row.name,))
                     for child in children.get(row.name, ()))
        return ModelNode(
            key=row.name,
            label=row.name or "(unnamed)",
            material=row.material,
            sensitive=row.sensitive,
            role="volume",
            children=kids,
        )

    world_row = next(
        (row for row in rows if str(row.name).strip().lower() in ("world",)), None)
    if world_row is not None and world_row.parent in WORLD_NAMES:
        # the model may carry the world as an ordinary row: it becomes the tree root
        built = node_for(world_row, ())
        return ModelNode(
            key=world_row.name or world_key,
            label="World",
            material=built.material or world_material,
            role="world",
            children=built.children,
        )

    world = ModelNode(world_key, "World", world_material, role="world",
                      children=tuple(node_for(row, ()) for row in roots))
    return world


def flatten(node: ModelNode) -> list[ModelNode]:
    """Depth-first list of *node* and all descendants (helper for tests and searches)."""
    out = [node]
    for child in node.children:
        out.extend(flatten(child))
    return out
