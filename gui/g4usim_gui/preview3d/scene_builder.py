from __future__ import annotations

from pathlib import Path

from g4usim_gui.editors.geometry_editor_model import GeometryDocument
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.preview3d.geometry_primitives import combine_bounds
from g4usim_gui.preview3d.scene_model import PreviewScene, PreviewVolume
from g4usim_gui.preview3d.sketch_geometry import Placement, SketchError, angle_vec3, length_vec3, solid_mesh
from g4usim_gui.preview3d.source_builder import build_preview_source
from g4usim_gui.preview3d.units import parse_angle_list_deg, parse_length_list_to_mm, parse_vec3_deg, parse_vec3_to_mm, parse_length_to_mm


def build_preview_scene(geometry: GeometryDocument, source: SourceEditableModel) -> PreviewScene:
    scene = PreviewScene(template=geometry.mode)
    scene.errors.extend(f"Geometry source: {message}" for message in geometry.source_errors)
    scene.warnings.extend(f"Geometry source: {message}" for message in geometry.source_warnings)
    scene.warnings.extend(f"Round-trip blocker: {message}" for message in geometry.round_trip_blockers)
    if geometry.source_copy_mode:
        scene.warnings.append("Original geometry source copy mode is active; editor validation is bypassed.")
    if geometry.mode == "simple_box":
        _build_simple_box(scene, geometry)
    elif geometry.mode == "layered_device":
        _build_layered_device(scene, geometry)
    elif geometry.mode in {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}:
        _build_hierarchical(scene, geometry)
    else:
        _build_preview_only(scene, geometry)
    for volume in scene.volumes:
        if volume.not_drawn and volume.role != "boolean_tool":
            scene.warnings.append(f"{volume.name}: not drawn in the sketch ({volume.not_drawn}).")
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
    world, target = scene.volumes[-2], scene.volumes[-1]
    _place(world, "box", model.world_size, "", {}, None, Placement.identity())
    _place(target, "box", model.target_size, "", {}, None,
           _placement(model.target_position or "0 mm, 0 mm, 0 mm", model.target_rotation or "0 deg, 0 deg, 0 deg",
                      target))


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
    _place(scene.volumes[-1], "box", model.world_size, "", {}, None, Placement.identity())
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
        if model.auto_stack:     # as LayeredDeviceTemplate: stacked, or at each layer's own position
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
        layer_volume = scene.volumes[-1]
        stacked = f"0 mm, 0 mm, {position[2]} mm"
        _place(layer_volume, "box", f"{xy[0]} mm, {xy[1]} mm, {thickness} mm", "", {}, None,
               _placement(stacked if model.auto_stack else layer.position, layer.rotation or "0 deg, 0 deg, 0 deg",
                          layer_volume))


def _build_preview_only(scene: PreviewScene, geometry: GeometryDocument) -> None:
    scene.warnings.append(f"The sketch does not draw the {geometry.mode} template; the Geant4 geometry shows it.")
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
    rows = [row for row in geometry.volumes if row.enabled]
    by_name = {row.name.strip().lower(): row for row in rows}
    base_dir = Path(geometry.source_path).parent if geometry.source_path else None
    targets = {op.target_volume.strip().lower() for op in geometry.boolean_ops if op.enabled}
    placements: dict[str, Placement | SketchError] = {}

    def world_placement(row, chain: tuple[str, ...] = ()) -> Placement:
        """World <- volume, composed through the parents as Geant4 does (the world stays at the origin)."""
        key = row.name.strip().lower()
        if key in placements:
            known = placements[key]
            if isinstance(known, SketchError):
                raise known
            return known
        try:
            if key in chain:
                raise SketchError("its parent chain is circular")
            if key == "world":
                placement = Placement.identity()
            else:
                mode = row.preview_properties.get("placement", "").strip().lower()
                if mode in {"replica", "parameterised", "parametrised"}:
                    raise SketchError(f"placement={mode} copies are drawn only by the Geant4 geometry")
                parent = by_name.get((row.parent or "world").strip().lower())
                if parent is None:
                    raise SketchError(f"its parent {row.parent!r} is not a volume")
                try:
                    mother = world_placement(parent, chain + (key,))
                except SketchError as error:
                    raise SketchError(f"its parent {parent.name} is not drawn") from error
                local = Placement.from_g4(length_vec3(row.position) if row.position.strip() else (0.0, 0.0, 0.0),
                                          angle_vec3(row.rotation) if row.rotation.strip() else (0.0, 0.0, 0.0))
                placement = mother.then(local)
        except SketchError as error:
            placements[key] = error
            raise
        placements[key] = placement
        return placement

    ignored = PreviewScene()       # the old size/parameter readers' messages: the mesh reports problems itself
    for row in rows:
        shape = row.shape.strip().lower() or "box"
        size, params_mm, params_deg = _volume_parameters_for_preview(
            row.size, row.parameters, shape, ignored, row.name, shape_properties=row.shape_properties)
        volume = PreviewVolume(
            name=row.name,
            shape=shape,
            size_mm=size,
            parameters_mm=params_mm,
            parameters_deg=params_deg,
            position_mm=parse_vec3_to_mm(row.position) if row.position else (0.0, 0.0, 0.0),
            rotation_deg=parse_vec3_deg(row.rotation) if row.rotation else (0.0, 0.0, 0.0),
            material=row.material,
            sensitive=row.sensitive,
            bias=row.bias,
            role="world" if row.name.strip().lower() == "world" else "ordinary",
        )
        scene.volumes.append(volume)
        try:
            placement = world_placement(row)
        except SketchError as error:
            volume.not_drawn = str(error)
            continue
        _place(volume, shape, row.size, row.parameters, {**row.shape_properties, **row.preview_properties},
               base_dir, placement)
        if row.name.strip().lower() in targets:
            volume.note = "boolean operations not applied: the solid is drawn before them"
    if targets:
        scene.warnings.append("Boolean results are not drawn: boolean targets show their solid before the "
                              "operations; the Geant4 geometry shows the result.")
    for op in geometry.boolean_ops:
        if not op.enabled:
            continue
        shape = op.tool_shape.strip().lower() or "box"
        size, params_mm, params_deg = _volume_parameters_for_preview(
            op.tool_size, op.tool_parameters, shape, ignored, f"boolean:{op.name or op.target_volume}")
        scene.volumes.append(
            PreviewVolume(
                name=f"{op.target_volume}.{op.index}.{op.operation}",
                shape=shape,
                size_mm=size,
                parameters_mm=params_mm,
                parameters_deg=params_deg,
                position_mm=parse_vec3_to_mm(op.position) if op.position else (0.0, 0.0, 0.0),
                rotation_deg=parse_vec3_deg(op.rotation) if op.rotation else (0.0, 0.0, 0.0),
                material="boolean tool",
                sensitive=False,
                bias=False,
                role="boolean_tool",
                not_drawn="boolean tool",
            )
        )


def _placement(position: str, rotation: str, volume: PreviewVolume) -> Placement | None:
    try:
        return Placement.from_g4(length_vec3(position), angle_vec3(rotation))
    except SketchError as error:
        volume.not_drawn = str(error)
        return None


def _place(volume: PreviewVolume, shape: str, size: str, parameters: str, properties: dict[str, str],
           base_dir: Path | None, placement: Placement | None) -> None:
    """The volume's solid in world coordinates, or the reason it cannot be drawn."""
    if placement is None:
        return
    try:
        vertices, faces = solid_mesh(shape, size=size, parameters=parameters, properties=properties,
                                     base_dir=base_dir)
    except (SketchError, ValueError, ZeroDivisionError) as error:
        volume.not_drawn = str(error)
        return
    volume.vertices, volume.faces = placement.apply(vertices), faces


def _volume_parameters_for_preview(
    size_text: str,
    parameters_text: str,
    shape: str,
    scene: PreviewScene,
    label: str,
    *,
    shape_properties: dict[str, str] | None = None,
) -> tuple[tuple[float, float, float] | None, tuple[float, ...], tuple[float, ...]]:
    if shape == "box":
        size = parse_vec3_to_mm(size_text)
        if size is None:
            scene.warnings.append(f"{label} box size could not be parsed for preview: {size_text!r}")
        return size, tuple(), tuple()
    if shape in {"tubs", "cylinder"}:
        parts = [part.strip() for part in parameters_text.split(",") if part.strip()]
        if len(parts) >= 3:
            inner_radius = parse_length_to_mm(parts[0])
            outer_radius = parse_length_to_mm(parts[1])
            half_z = parse_length_to_mm(parts[2])
            if inner_radius is not None and outer_radius is not None and half_z is not None:
                angles = parse_angle_list_deg(",".join(parts[3:5])) if len(parts) >= 5 else tuple()
                if angles and (abs(angles[0]) > 1.0e-9 or (len(angles) > 1 and abs(angles[1] - 360.0) > 1.0e-9)):
                    scene.warnings.append(f"{label} partial tubs is drawn as a full cylinder in preview.")
                return (
                    (2.0 * outer_radius, 2.0 * outer_radius, 2.0 * half_z),
                    (inner_radius, outer_radius, half_z),
                    angles,
                )
        scene.warnings.append(f"{label} tubs parameters could not be parsed for preview: {parameters_text!r}")
        return None, tuple(), tuple()
    if shape in {"sphere", "orb"}:
        params = parse_length_list_to_mm(parameters_text)
        if shape == "orb" and params:
            radius = params[0]
            return (2.0 * radius, 2.0 * radius, 2.0 * radius), params, tuple()
        if shape == "sphere" and len(params) >= 2:
            radius = params[1]
            angles = parse_angle_list_deg(",".join([part.strip() for part in parameters_text.split(",") if part.strip()][2:]))
            if angles:
                scene.warnings.append(f"{label} partial sphere is drawn as a full sphere in preview.")
            return (2.0 * radius, 2.0 * radius, 2.0 * radius), params, angles
        size = parse_vec3_to_mm(size_text) if size_text else None
        if size:
            return size, tuple(), tuple()
        scene.warnings.append(f"{label} sphere/orb parameters could not be parsed for preview: {parameters_text!r}")
        return None, tuple(), tuple()
    if shape == "cone":
        parts = [part.strip() for part in parameters_text.split(",") if part.strip()]
        params = parse_length_list_to_mm(",".join(parts[:5]))
        if len(params) >= 5:
            radius = max(params[1], params[3])
            half_z = params[4]
            angles = parse_angle_list_deg(",".join(parts[5:7])) if len(parts) >= 7 else tuple()
            if angles:
                scene.warnings.append(f"{label} partial cone is drawn as a full cone/frustum approximation in preview.")
            return (2.0 * radius, 2.0 * radius, 2.0 * half_z), params, angles
        scene.warnings.append(f"{label} cone parameters could not be parsed for preview: {parameters_text!r}")
        return None, tuple(), tuple()
    if shape == "trd":
        properties = shape_properties or {}
        values = tuple(parse_length_to_mm(properties.get(key, "")) for key in ("dx1", "dx2", "dy1", "dy2", "dz"))
        if all(value is not None and value > 0.0 for value in values):
            dx1, dx2, dy1, dy2, dz = values
            return (
                (2.0 * max(dx1, dx2), 2.0 * max(dy1, dy2), 2.0 * dz),
                (dx1, dx2, dy1, dy2, dz),
                tuple(),
            )
        scene.warnings.append(f"{label} trd properties could not be parsed for preview: {properties!r}")
        return None, tuple(), tuple()
    scene.warnings.append(f"{label} shape={shape!r} is shown only as approximate/unsupported in 3D preview.")
    return (parse_vec3_to_mm(size_text) if size_text else None), tuple(), tuple()


def _volume_size_for_preview(size_text: str, parameters_text: str, shape: str, scene: PreviewScene, label: str) -> tuple[float, float, float] | None:
    size, _, _ = _volume_parameters_for_preview(size_text, parameters_text, shape, scene, label)
    return size


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
