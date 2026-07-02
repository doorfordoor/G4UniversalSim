from __future__ import annotations

from g4usim_gui.editors.geometry_editor_model import GeometryDocument
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.preview3d.geometry_primitives import combine_bounds
from g4usim_gui.preview3d.scene_model import PreviewScene, PreviewVolume
from g4usim_gui.preview3d.source_builder import build_preview_source
from g4usim_gui.preview3d.units import parse_vec3_deg, parse_vec3_to_mm, parse_length_to_mm


def build_preview_scene(geometry: GeometryDocument, source: SourceEditableModel) -> PreviewScene:
    scene = PreviewScene(template=geometry.mode)
    if geometry.mode == "simple_box":
        _build_simple_box(scene, geometry)
    elif geometry.mode == "layered_device":
        _build_layered_device(scene, geometry)
    elif geometry.mode in {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}:
        _build_hierarchical(scene, geometry)
    else:
        _build_preview_only(scene, geometry)
    scene.bounds_mm = combine_bounds(scene.volumes)
    scene.source = build_preview_source(source, scene.warnings, scene.errors)
    return scene


def _build_simple_box(scene: PreviewScene, geometry: GeometryDocument) -> None:
    model = geometry.simple_box
    world_size = _vec3(model.world_size, "simple_box world size", scene)
    target_size = _vec3(model.target_size, "simple_box target size", scene)
    target_position = _vec3(model.target_position, "simple_box target position", scene)
    target_rotation = parse_vec3_deg(model.target_rotation)
    if target_rotation is None:
        scene.warnings.append(f"simple_box target rotation could not be parsed: {model.target_rotation!r}")
    scene.volumes.append(
        PreviewVolume(
            name="world",
            shape="box",
            size_mm=world_size,
            position_mm=(0.0, 0.0, 0.0),
            rotation_deg=(0.0, 0.0, 0.0),
            material=model.world_material,
            role="world",
        )
    )
    if model.target_shape.strip().lower() != "box":
        scene.warnings.append("Simple Box preview only draws target shape=box.")
    scene.volumes.append(
        PreviewVolume(
            name=model.target_name or "Target",
            shape="box",
            size_mm=target_size,
            position_mm=target_position,
            rotation_deg=target_rotation,
            material=model.target_material,
            sensitive=model.target_sensitive,
            bias=model.target_bias,
            role="target",
        )
    )


def _build_layered_device(scene: PreviewScene, geometry: GeometryDocument) -> None:
    model = geometry.layered_device
    world_size = _vec3(model.world_size, "layered_device world size", scene)
    scene.volumes.append(
        PreviewVolume(
            name="world",
            shape="box",
            size_mm=world_size,
            position_mm=(0.0, 0.0, 0.0),
            rotation_deg=(0.0, 0.0, 0.0),
            material=model.world_material,
            role="world",
        )
    )
    if model.axis.strip().lower() != "z":
        scene.warnings.append("Layered Device preview currently supports axis=z only.")
    enabled_layers = [layer for layer in model.layers if layer.enabled]
    thicknesses: list[float] = []
    gap = parse_length_to_mm(model.gap) or 0.0
    if model.gap.strip() and parse_length_to_mm(model.gap) is None:
        scene.warnings.append(f"Layer gap could not be parsed, using 0 mm: {model.gap!r}")
    for layer in enabled_layers:
        thickness = parse_length_to_mm(layer.thickness)
        if thickness is None or thickness <= 0.0:
            scene.warnings.append(f"Layer '{layer.name}' thickness could not be parsed, using 1 mm.")
            thickness = 1.0
        thicknesses.append(thickness)
    total = sum(thicknesses) + max(0, len(thicknesses) - 1) * gap
    if model.z_start.strip():
        edge = parse_length_to_mm(model.z_start)
        if edge is None:
            scene.warnings.append(f"z_start could not be parsed, centering stack: {model.z_start!r}")
            edge = -0.5 * total
    else:
        edge = -0.5 * total
    for layer, thickness in zip(enabled_layers, thicknesses):
        xy = _xy(layer.xy, f"layer '{layer.name}' xy", scene)
        position = (0.0, 0.0, edge + 0.5 * thickness)
        edge += thickness + gap
        scene.volumes.append(
            PreviewVolume(
                name=layer.name,
                shape="box",
                size_mm=(xy[0], xy[1], thickness),
                position_mm=position,
                rotation_deg=(0.0, 0.0, 0.0),
                material=layer.material,
                sensitive=layer.sensitive,
                bias=layer.bias,
                role="layer",
            )
        )


def _build_preview_only(scene: PreviewScene, geometry: GeometryDocument) -> None:
    scene.warnings.append("This template is preview-only. 3D preview is approximate and may show only parsed bounding boxes.")
    for row in geometry.volumes:
        scene.volumes.append(
            PreviewVolume(
                name=row.name,
                shape=row.shape or "box",
                size_mm=None,
                position_mm=parse_vec3_to_mm(row.position) if row.position else None,
                rotation_deg=parse_vec3_deg(row.rotation) if row.rotation else None,
                material=row.material,
                sensitive=row.sensitive,
                bias=row.bias,
                role="ordinary",
            )
        )


def _build_hierarchical(scene: PreviewScene, geometry: GeometryDocument) -> None:
    scene.warnings.append("Hierarchical preview uses approximate absolute transforms.")
    if geometry.boolean_ops:
        scene.warnings.append("Boolean preview is approximate; Geant4 backend is authoritative.")
    for row in geometry.volumes:
        if not row.enabled:
            continue
        shape = row.shape.strip().lower() or "box"
        size = _volume_size_for_preview(row.size, row.parameters, shape, scene, row.name)
        scene.volumes.append(
            PreviewVolume(
                name=row.name,
                shape="box",
                size_mm=size,
                position_mm=parse_vec3_to_mm(row.position) if row.position else (0.0, 0.0, 0.0),
                rotation_deg=parse_vec3_deg(row.rotation) if row.rotation else (0.0, 0.0, 0.0),
                material=row.material,
                sensitive=row.sensitive,
                bias=row.bias,
                role="world" if row.name.strip().lower() == "world" else "ordinary",
            )
        )
    for op in geometry.boolean_ops:
        if not op.enabled:
            continue
        shape = op.tool_shape.strip().lower() or "box"
        size = _volume_size_for_preview(op.tool_size, op.tool_parameters, shape, scene, f"boolean:{op.name or op.target_volume}")
        scene.volumes.append(
            PreviewVolume(
                name=f"{op.target_volume}.{op.index}.{op.operation}",
                shape="box",
                size_mm=size,
                position_mm=parse_vec3_to_mm(op.position) if op.position else (0.0, 0.0, 0.0),
                rotation_deg=parse_vec3_deg(op.rotation) if op.rotation else (0.0, 0.0, 0.0),
                material="boolean tool",
                sensitive=False,
                bias=False,
                role="boolean_tool",
            )
        )


def _volume_size_for_preview(size_text: str, parameters_text: str, shape: str, scene: PreviewScene, label: str) -> tuple[float, float, float] | None:
    if shape == "box":
        size = parse_vec3_to_mm(size_text)
        if size is None:
            scene.warnings.append(f"{label} box size could not be parsed for preview: {size_text!r}")
        return size
    if shape == "tubs":
        parts = [part.strip() for part in parameters_text.split(",") if part.strip()]
        if len(parts) >= 3:
            radius = parse_length_to_mm(parts[1])
            half_z = parse_length_to_mm(parts[2])
            if radius is not None and half_z is not None:
                return (2.0 * radius, 2.0 * radius, 2.0 * half_z)
        scene.warnings.append(f"{label} tubs parameters could not be parsed for preview: {parameters_text!r}")
        return None
    scene.warnings.append(f"{label} shape={shape!r} is shown only as approximate/unsupported in 3D preview.")
    return parse_vec3_to_mm(size_text) if size_text else None


def _vec3(value: str, label: str, scene: PreviewScene) -> tuple[float, float, float] | None:
    parsed = parse_vec3_to_mm(value)
    if parsed is None:
        scene.warnings.append(f"{label} could not be parsed for preview: {value!r}")
    return parsed


def _xy(value: str, label: str, scene: PreviewScene) -> tuple[float, float]:
    parsed = parse_vec3_to_mm(value)
    if parsed is not None:
        return (parsed[0], parsed[1])
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) == 2:
        x = parse_length_to_mm(parts[0])
        y = parse_length_to_mm(parts[1])
        if x is not None and y is not None:
            return (x, y)
    scene.warnings.append(f"{label} could not be parsed, using 10 mm x 10 mm: {value!r}")
    return (10.0, 10.0)
