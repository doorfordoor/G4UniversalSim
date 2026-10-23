from __future__ import annotations

import re
import math
from dataclasses import asdict, dataclass, field

from g4usim_gui.editors.editable_models import EditableDocument
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.parsers.materials_parser import NIST_QUICK_LIST, material_reference_status
from g4usim_gui.parsers.geometry_parser import GeometrySummary
from g4usim_gui.parsers.geometry_parser import PRODUCTION_CUT_KEYS, TRD_PROPERTY_KEYS, VISUAL_KEYS
from g4usim_gui.preview3d.units import parse_length_to_mm


EDITABLE_GEOMETRY_MODES = {"simple_box", "layered_device", "hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}
HIERARCHICAL_GEOMETRY_MODES = {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}
SUPPORTED_HIERARCHICAL_SHAPES = {"box", "tubs", "sphere", "orb", "cone", "trd"}
SUPPORTED_BOOLEAN_TOOL_SHAPES = {"box", "tubs", "sphere", "orb", "cone"}
# every name the backend's ParseShape accepts (GeometryUtils.cc), aliases included
BACKEND_SHAPES = {"box", "cube", "tubs", "tube", "cylinder", "sphere", "orb", "cone", "cons", "trd", "trapezoid",
                  "trap", "ellipsoid", "eltube", "elliptical_tube", "torus", "para", "parallelepiped", "hype",
                  "polycone", "polyhedra", "tessellated", "stl"}
SUPPORTED_VISUAL_COLORS = {
    "white", "black", "red", "green", "blue", "yellow", "cyan", "aqua",
    "magenta", "gray", "grey", "darkgray", "lime", "brown",
}
STABLE_GUI_SHAPES = {"box", "tubs"}
BOOLEAN_OPERATIONS = {"subtraction", "union", "intersection"}


@dataclass
class HierarchicalVolumeRow:
    enabled: bool = True
    name: str = ""
    parent: str = ""
    shape: str = ""
    size: str = ""
    parameters: str = ""
    material: str = ""
    position: str = ""
    rotation: str = ""
    sensitive: bool = False
    bias: bool = False
    region: str = ""
    copy_no: str = ""
    metadata: str = ""
    shape_properties: dict[str, str] = field(default_factory=dict)
    preview_properties: dict[str, str] = field(default_factory=dict)   # read-only, for the 3D sketch
    visual: dict[str, str] = field(default_factory=dict)
    production_cuts: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class BooleanOperationRow:
    enabled: bool = True
    target_volume: str = ""
    index: int = 0
    operation: str = ""
    tool_shape: str = ""
    tool_size: str = ""
    tool_parameters: str = ""
    position: str = ""
    rotation: str = ""
    name: str = ""
    notes: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


VolumeRow = HierarchicalVolumeRow
BooleanOpRow = BooleanOperationRow


@dataclass
class SimpleBoxGeometryModel:
    world_size: str = "10 cm, 10 cm, 10 cm"
    world_material: str = "G4_AIR"
    target_name: str = "Target"
    target_shape: str = "box"
    target_size: str = "1 cm, 1 cm, 1 mm"
    target_material: str = "G4_Si"
    target_position: str = "0 mm, 0 mm, 0 mm"
    target_rotation: str = "0 deg, 0 deg, 0 deg"
    target_sensitive: bool = True
    target_bias: bool = False
    target_region: str = "SV"


@dataclass
class LayerRow:
    enabled: bool = True
    name: str = "Layer"
    material: str = "G4_Si"
    thickness: str = "1 um"
    xy: str = "10 mm, 10 mm"
    sensitive: bool = False
    bias: bool = False
    region: str = ""
    copy_no: str = ""
    position: str = ""
    rotation: str = ""
    visual: dict[str, str] = field(default_factory=dict)
    production_cuts: dict[str, str] = field(default_factory=dict)
    metadata: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class LayeredDeviceGeometryModel:
    world_size: str = "20 cm, 20 cm, 20 cm"
    world_material: str = "G4_AIR"
    axis: str = "z"
    auto_stack: bool = True
    gap: str = "0 um"
    z_start: str = ""
    layers: list[LayerRow] = field(default_factory=lambda: [
        LayerRow(name="Substrate", material="G4_Si", thickness="500 um", xy="10 mm, 10 mm"),
        LayerRow(name="Sensitive", material="G4_Si", thickness="10 um", xy="10 mm, 10 mm", sensitive=True, region="SV"),
    ])


@dataclass
class GeometryDocument(EditableDocument):
    mode: str = "preview_only"
    schema_version: int | None = None
    simple_box: SimpleBoxGeometryModel = field(default_factory=SimpleBoxGeometryModel)
    layered_device: LayeredDeviceGeometryModel = field(default_factory=LayeredDeviceGeometryModel)
    volumes: list[HierarchicalVolumeRow] = field(default_factory=list)
    boolean_ops: list[BooleanOperationRow] = field(default_factory=list)
    raw_source_text: str = ""
    source_errors: list[str] = field(default_factory=list)
    source_warnings: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    round_trip_blockers: list[str] = field(default_factory=list)
    legacy_metadata: list[str] = field(default_factory=list)
    source_copy_mode: bool = False


def geometry_document_from_summary(summary: GeometrySummary | None, template_name: str = "") -> GeometryDocument:
    document = GeometryDocument()
    if summary is None:
        document.mode = _mode_from_template(template_name)
        return document

    document.source_path = summary.path
    document.source_errors = _deduplicate(list(summary.errors))
    document.source_warnings = _deduplicate(list(summary.warnings))
    document.round_trip_blockers = _deduplicate(list(summary.round_trip_blockers))
    document.legacy_metadata = _deduplicate(list(summary.legacy_metadata))
    document.errors = list(document.source_errors)
    document.warnings = list(document.source_warnings)
    document.mode = _mode_from_template(template_name or summary.template_hint)
    document.schema_version = summary.schema_version
    document.raw_source_text = summary.raw_text
    for volume in summary.volumes:
        document.volumes.append(
            VolumeRow(
                name=volume.name,
                parent=volume.parent,
                shape=volume.shape,
                size=volume.size,
                parameters=volume.parameters,
                material=volume.material,
                position=volume.position,
                rotation=volume.rotation,
                sensitive=volume.sensitive,
                bias=volume.bias,
                region=volume.region,
                copy_no=volume.copy_no,
                metadata=volume.metadata,
                shape_properties=dict(volume.shape_properties),
                preview_properties=dict(volume.preview_properties),
                visual=dict(volume.visual),
                production_cuts=dict(volume.production_cuts),
            )
        )
    for op in summary.boolean_ops:
        document.boolean_ops.append(
            BooleanOperationRow(
                target_volume=op.target_volume,
                index=op.index,
                operation=op.operation,
                tool_shape=op.tool_shape,
                tool_size=op.tool_size,
                tool_parameters=op.tool_parameters,
                position=op.position,
                rotation=op.rotation,
                name=op.name,
            )
        )

    sections = _parse_ini_sections(summary.raw_text)
    if document.mode == "simple_box":
        document.simple_box = _simple_from_sections(sections)
    elif document.mode == "layered_device":
        document.layered_device = _layered_from_sections(sections, summary.raw_text)
    if document.boolean_ops and document.mode in HIERARCHICAL_GEOMETRY_MODES:
        document.mode = "hierarchical_boolean"
    return document


def geometry_document_from_dict(data: dict | None) -> GeometryDocument:
    document = GeometryDocument()
    if not isinstance(data, dict):
        return document
    document.mode = str(data.get("mode", "preview_only"))
    raw_version = data.get("schema_version", data.get("schemaVersion"))
    if raw_version is not None:
        if str(raw_version) not in {"1", "2"}:
            raise ValueError(f"Unsupported geometry schema version in project snapshot: {raw_version}")
        document.schema_version = int(raw_version)
    document.source_path = str(data.get("source_path", data.get("sourcePath", "")))
    document.is_dirty = bool(data.get("is_dirty", data.get("dirty", False)))
    document.source_copy_mode = bool(data.get("source_copy_mode", data.get("sourceCopyMode", False)))
    document.source_errors = list(data.get("source_errors", data.get("sourceErrors", [])))
    document.source_warnings = list(data.get("source_warnings", data.get("sourceWarnings", [])))
    document.validation_errors = list(data.get("validation_errors", data.get("validationErrors", [])))
    document.validation_warnings = list(data.get("validation_warnings", data.get("validationWarnings", [])))
    document.round_trip_blockers = list(data.get("round_trip_blockers", data.get("roundTripBlockers", [])))
    document.legacy_metadata = list(data.get("legacy_metadata", data.get("legacyMetadata", [])))
    simple = data.get("simple_box", data.get("simpleBox", {}))
    if isinstance(simple, dict):
        document.simple_box = SimpleBoxGeometryModel(**{k: v for k, v in simple.items() if k in SimpleBoxGeometryModel.__dataclass_fields__})
    layered = data.get("layered_device", data.get("layeredDevice", {}))
    if isinstance(layered, dict):
        values = {k: v for k, v in layered.items() if k in LayeredDeviceGeometryModel.__dataclass_fields__ and k != "layers"}
        layers = []
        for item in layered.get("layers", []) if isinstance(layered.get("layers", []), list) else []:
            if isinstance(item, dict):
                layers.append(LayerRow(**{k: v for k, v in item.items() if k in LayerRow.__dataclass_fields__}))
        document.layered_device = LayeredDeviceGeometryModel(**values)
        if layers:
            document.layered_device.layers = layers
    preview = data.get("preview", {})
    volume_rows = data.get("volumes", preview.get("volumes", []))
    if isinstance(volume_rows, list):
        for item in volume_rows:
            if isinstance(item, dict):
                document.volumes.append(_volume_from_dict(item))
    op_rows = data.get("boolean_ops", preview.get("boolean_ops", []))
    if isinstance(op_rows, list):
        for item in op_rows:
            if isinstance(item, dict):
                document.boolean_ops.append(_boolean_from_dict(item))
    return document


def geometry_document_to_snapshot(document: GeometryDocument | None) -> dict:
    if document is None:
        return {}
    return {
        "mode": document.mode,
        "schema_version": document.schema_version,
        "source_path": document.source_path,
        "is_dirty": document.is_dirty,
        "source_copy_mode": document.source_copy_mode,
        "source_errors": list(document.source_errors),
        "source_warnings": list(document.source_warnings),
        "validation_errors": list(document.validation_errors),
        "validation_warnings": list(document.validation_warnings),
        "round_trip_blockers": list(document.round_trip_blockers),
        "legacy_metadata": list(document.legacy_metadata),
        "simple_box": document.simple_box.__dict__.copy(),
        "layered_device": {
            "world_size": document.layered_device.world_size,
            "world_material": document.layered_device.world_material,
            "axis": document.layered_device.axis,
            "auto_stack": document.layered_device.auto_stack,
            "gap": document.layered_device.gap,
            "z_start": document.layered_device.z_start,
            "layers": [layer.__dict__.copy() for layer in document.layered_device.layers],
        },
        "volumes": [_clean_dataclass(row) for row in document.volumes],
        "boolean_ops": [_clean_dataclass(row) for row in document.boolean_ops],
        "preview": {
            "volumes": [_clean_dataclass(row) for row in document.volumes],
            "boolean_ops": [_clean_dataclass(row) for row in document.boolean_ops],
        },
    }


def set_geometry_mode(document: GeometryDocument, template_name: str) -> None:
    document.mode = _mode_from_template(template_name)
    document.is_dirty = document.mode in EDITABLE_GEOMETRY_MODES


def geometry_material_refs(document: GeometryDocument) -> set[str]:
    if document.mode == "simple_box":
        return {document.simple_box.world_material, document.simple_box.target_material} - {""}
    if document.mode == "layered_device":
        refs = {document.layered_device.world_material}
        refs.update(layer.material for layer in document.layered_device.layers if layer.enabled and layer.material)
        return refs - {""}
    return {volume.material for volume in document.volumes if volume.enabled and volume.material}


def geometry_sensitive_count(document: GeometryDocument) -> int:
    if document.mode == "simple_box":
        return 1 if document.simple_box.target_sensitive else 0
    if document.mode == "layered_device":
        return sum(1 for layer in document.layered_device.layers if layer.enabled and layer.sensitive)
    return sum(1 for volume in document.volumes if volume.enabled and volume.sensitive)


def geometry_bias_count(document: GeometryDocument) -> int:
    if document.mode == "simple_box":
        return 1 if document.simple_box.target_bias else 0
    if document.mode == "layered_device":
        return sum(1 for layer in document.layered_device.layers if layer.enabled and layer.bias)
    return sum(1 for volume in document.volumes if volume.enabled and volume.bias)


def validate_geometry_document(
    document: GeometryDocument,
    *,
    material_names: set[str] | None = None,
    scoring_hits_enabled: bool = True,
    physics_biasing_enabled: bool = False,
) -> None:
    document.errors = []
    document.warnings = []
    if document.schema_version not in {None, 1, 2}:
        document.errors.append("Geometry schema version must be 1, 2, or absent.")
    known_materials = set(material_names or set()) | NIST_QUICK_LIST
    if document.mode == "simple_box":
        _validate_simple(document, known_materials)
    elif document.mode == "layered_device":
        _validate_layered(document, known_materials)
    elif document.mode in HIERARCHICAL_GEOMETRY_MODES:
        _validate_hierarchical(document, known_materials)
    else:
        document.warnings.append("This geometry template is preview-only in the GUI MVP. Source geometry.ini will be copied unchanged.")

    if geometry_sensitive_count(document) and not scoring_hits_enabled:
        document.warnings.append("Geometry marks sensitive volumes, but scoring hits output is disabled.")
    if geometry_bias_count(document) and not physics_biasing_enabled:
        document.warnings.append("Geometry marks bias volumes, but physics biasing hook is disabled.")
    if document.round_trip_blockers and not document.source_copy_mode:
        document.errors.append(
            "Source geometry contains fields that the current editor cannot preserve; use original source copy mode."
        )
        document.errors.extend(f"Round-trip blocker: {item}" for item in document.round_trip_blockers)
    if document.source_copy_mode and document.round_trip_blockers:
        document.warnings.append(
            "Original geometry source will be copied unchanged; Geometry Editor validation does not certify blocked fields."
        )

    document.validation_errors = _deduplicate(document.errors)
    document.validation_warnings = _deduplicate(document.warnings)
    document.errors = _deduplicate([*document.source_errors, *document.validation_errors])
    document.warnings = _deduplicate([*document.source_warnings, *document.validation_warnings])


def _validate_simple(document: GeometryDocument, known_materials: set[str]) -> None:
    simple = document.simple_box
    _require_vec3(simple.world_size, "simple_box [world]/size", document)
    _require_material(simple.world_material, "simple_box [world]/material", known_materials, document)
    if not simple.target_name.strip():
        document.errors.append("simple_box target name is required.")
    if simple.target_shape.strip().lower() != "box":
        document.errors.append("simple_box target only supports shape=box.")
    _require_vec3(simple.target_size, "simple_box [target]/size", document)
    _require_vec3(simple.target_position, "simple_box [target]/position", document)
    _require_vec3(simple.target_rotation, "simple_box [target]/rotation", document)
    _require_material(simple.target_material, "simple_box [target]/material", known_materials, document)


def _validate_layered(document: GeometryDocument, known_materials: set[str]) -> None:
    layered = document.layered_device
    _require_vec3(layered.world_size, "layered_device [world]/size", document)
    _require_material(layered.world_material, "layered_device [world]/material", known_materials, document)
    if layered.axis.strip().lower() != "z":
        document.errors.append("layered_device currently supports axis=z only.")
    if not _looks_like_value_with_unit(layered.gap):
        document.warnings.append("layered_device gap should include a length unit, e.g. 0 um.")

    enabled_layers = [layer for layer in layered.layers if layer.enabled]
    if not enabled_layers:
        document.errors.append("layered_device requires at least one enabled layer.")
    seen: set[str] = set()
    for index, layer in enumerate(enabled_layers, start=1):
        layer.errors.clear()
        if not layer.name.strip():
            document.errors.append(f"layered_device layer #{index} name is required.")
            continue
        key = layer.name.strip().lower()
        if key in seen:
            document.errors.append(f"layered_device duplicate layer name: {layer.name}")
        seen.add(key)
        _require_material(layer.material, f"layered_device [layer.{layer.name}]/material", known_materials, document)
        if not _looks_like_value_with_unit(layer.thickness):
            document.errors.append(f"layered_device layer '{layer.name}' thickness must include a positive length with unit.")
        if not _looks_like_xy(layer.xy):
            document.errors.append(f"layered_device layer '{layer.name}' xy must have two lengths, e.g. 10 mm, 10 mm.")
        if layer.copy_no.strip() and not _is_int32(layer.copy_no):
            document.errors.append(f"layered_device layer '{layer.name}' copyNo must be a signed 32-bit integer.")
        if not layered.auto_stack and not layer.position.strip():
            document.errors.append(f"layered_device layer '{layer.name}' requires position when auto_stack=false.")
        if layer.position.strip():
            _require_vec3(layer.position, f"[layer.{layer.name}]/position", document)
        if layer.rotation.strip():
            _require_vec3(layer.rotation, f"[layer.{layer.name}]/rotation", document)
        for field, value in layer.production_cuts.items():
            if field not in PRODUCTION_CUT_KEYS:
                layer.errors.append(f"Unsupported production cut field '{field}'.")
            elif not layer.region.strip():
                layer.errors.append(f"{field} requires a non-empty region in the same layer.")
            elif (parsed := parse_length_to_mm(value)) is None or parsed <= 0:
                layer.errors.append(f"{field} must be a positive length.")
        for field, value in layer.visual.items():
            if field not in VISUAL_KEYS:
                layer.errors.append(f"Unsupported visual field '{field}'.")
            elif field == "vis.alpha":
                try:
                    alpha = float(value.strip())
                    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
                        layer.errors.append("vis.alpha must be between 0 and 1.")
                except ValueError:
                    layer.errors.append("vis.alpha must be numeric.")
            elif field in {"vis.visible", "vis.wireframe"} and value.strip().lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                layer.errors.append(f"{field} must be a boolean value.")
            elif field == "vis.color" and value.strip().lower() not in SUPPORTED_VISUAL_COLORS:
                layer.errors.append("vis.color must be a color supported by the backend.")
        _validate_metadata_text(layer.metadata, layer)
        document.errors.extend(f"[layer.{layer.name}]: {message}" for message in layer.errors)


def _validate_hierarchical(document: GeometryDocument, known_materials: set[str]) -> None:
    for row in document.volumes:
        row.errors.clear()
        row.warnings.clear()
    for row in document.boolean_ops:
        row.errors.clear()
        row.warnings.clear()

    enabled = [row for row in document.volumes if row.enabled]
    if not enabled:
        document.errors.append("hierarchical geometry requires at least one enabled volume.")
        return

    by_key: dict[str, HierarchicalVolumeRow] = {}
    for row in enabled:
        name = row.name.strip()
        if not name:
            row.errors.append("Volume name is required.")
            continue
        key = name.lower()
        if key in by_key:
            row.errors.append(f"Duplicate volume name: {name}")
            by_key[key].errors.append(f"Duplicate volume name: {name}")
            document.errors.append(f"[GEOMETRY] duplicate volume name: {name}")
        else:
            by_key[key] = row

    if "world" not in by_key:
        document.errors.append("[GEOMETRY] hierarchical geometry requires a world volume named 'world'.")

    for row in enabled:
        name = row.name.strip()
        key = name.lower()
        parent = row.parent.strip()
        shape = row.shape.strip().lower()
        if key != "world":
            if not parent:
                row.errors.append("Non-world volume requires parent.")
            elif parent.lower() == key:
                row.errors.append("Volume parent cannot point to itself.")
            elif parent.lower() not in by_key:
                row.errors.append(f"Parent volume does not exist: {parent}")
        if shape in BACKEND_SHAPES and shape not in SUPPORTED_HIERARCHICAL_SHAPES:
            # valid for Geant4, but the editor cannot check or write it: an editor limit, not an input error
            message = ui_format("Shape '{shape}' is supported by the backend but not by the Geometry Editor; "
                                "use original source copy mode.", shape=row.shape)
            (row.warnings if document.source_copy_mode else row.errors).append(message)
        elif shape not in SUPPORTED_HIERARCHICAL_SHAPES:
            row.errors.append(ui_format("Unsupported shape '{shape}'. Supported in the editor: box, tubs, sphere, orb, cone, trd.", shape=row.shape))
        elif shape not in STABLE_GUI_SHAPES:
            row.warnings.append(f"Shape '{row.shape}' is backend-supported but preview/editor validation is approximate.")
        if shape == "box":
            _require_vec3(row.size, f"[volume.{name}]/size", document)
            if row.parameters.strip():
                row.errors.append("box does not accept parameters.")
        elif shape in {"tubs", "sphere", "orb", "cone"}:
            expected = {"tubs": 5, "sphere": 6, "orb": 1, "cone": 7}[shape]
            actual = _parameter_count(row.parameters)
            if actual != expected:
                row.errors.append(f"{shape} requires exactly {expected} parameters; got {actual}.")
            if row.size.strip():
                row.errors.append(f"{shape} does not accept size shorthand.")
        elif shape == "trd":
            if row.size.strip() or row.parameters.strip():
                row.errors.append(ui_text("trd uses dx1, dx2, dy1, dy2, dz instead of size/parameters."))
            for field in TRD_PROPERTY_KEYS:
                value = row.shape_properties.get(field, "")
                parsed = parse_length_to_mm(value)
                if parsed is None or not math.isfinite(parsed) or parsed <= 0:
                    row.errors.append(ui_format("trd {field} must be a positive length.", field=field))
            for field in row.shape_properties:
                if field not in TRD_PROPERTY_KEYS:
                    row.errors.append(ui_format("Unsupported trd shape field '{field}'.", field=field))
        backend_only = shape in BACKEND_SHAPES and shape not in SUPPORTED_HIERARCHICAL_SHAPES
        if shape != "trd" and row.shape_properties and not backend_only:   # backend-only: the limit above says it
            row.errors.append(ui_text("Shape-specific fields are present but the selected shape is not trd."))
        _require_material(row.material, f"[volume.{name}]/material", known_materials, document)
        if row.position.strip():
            _require_vec3(row.position, f"[volume.{name}]/position", document)
        if row.rotation.strip():
            _require_vec3(row.rotation, f"[volume.{name}]/rotation", document)
        if row.copy_no.strip() and not _is_int32(row.copy_no):
            row.errors.append("copyNo must be a signed 32-bit integer.")
        for field, value in row.production_cuts.items():
            if field not in PRODUCTION_CUT_KEYS:
                row.errors.append(ui_format("Unsupported production cut field '{field}'.", field=field))
            elif not row.region.strip():
                row.errors.append(ui_format("{field} requires a non-empty region in the same volume.", field=field))
            elif (parsed := parse_length_to_mm(value)) is None or parsed <= 0:
                row.errors.append(ui_format("{field} must be a positive length.", field=field))
        for field, value in row.visual.items():
            if field not in VISUAL_KEYS:
                row.errors.append(ui_format("Unsupported visual field '{field}'.", field=field))
            elif field == "vis.alpha":
                try:
                    alpha = float(value.strip())
                    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
                        row.errors.append(ui_text("vis.alpha must be between 0 and 1."))
                except ValueError:
                    row.errors.append(ui_text("vis.alpha must be numeric."))
            elif field in {"vis.visible", "vis.wireframe"} and value.strip().lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                row.errors.append(ui_format("{field} must be a boolean value.", field=field))
            elif field == "vis.color" and value.strip().lower() not in SUPPORTED_VISUAL_COLORS:
                row.errors.append(ui_text("vis.color must be a color supported by the backend."))
        _validate_metadata_text(row.metadata, row)

    _validate_tree_cycles(enabled, document)
    _validate_boolean_operations(document, by_key)

    for row in enabled:
        for message in row.errors:
            document.errors.append(f"[GEOMETRY][ERROR] {row.name or '<unnamed>'}: {message}")
        for message in row.warnings:
            document.warnings.append(f"[GEOMETRY][WARN] {row.name or '<unnamed>'}: {message}")
    for row in document.boolean_ops:
        if not row.enabled:
            continue
        for message in row.errors:
            document.errors.append(f"[BOOLEAN][ERROR] {row.target_volume or '<missing>'}[{row.index}]: {message}")
        for message in row.warnings:
            document.warnings.append(f"[BOOLEAN][WARN] {row.target_volume or '<missing>'}[{row.index}]: {message}")


def _validate_tree_cycles(enabled: list[HierarchicalVolumeRow], document: GeometryDocument) -> None:
    parents: dict[str, str] = {}
    rows: dict[str, HierarchicalVolumeRow] = {}
    for row in enabled:
        key = row.name.strip().lower()
        if key and key not in parents:
            parents[key] = row.parent.strip().lower()
            rows[key] = row
    for name in list(parents):
        visiting: set[str] = set()
        current = name
        while current:
            if current in visiting:
                rows[name].errors.append("Parent cycle detected.")
                document.errors.append(f"[GEOMETRY] parent cycle detected at volume '{rows[name].name}'.")
                break
            visiting.add(current)
            current = parents.get(current, "")


def _validate_boolean_operations(document: GeometryDocument, volumes_by_key: dict[str, HierarchicalVolumeRow]) -> None:
    enabled_targets = {row.name.strip().lower() for row in volumes_by_key.values() if row.enabled}
    indices_by_target: dict[str, list[int]] = {}
    for row in document.boolean_ops:
        if not row.enabled:
            row.warnings.append("Disabled boolean operation is ignored by writer.")
            continue
        target = row.target_volume.strip()
        if not target:
            row.errors.append("Target volume is required.")
        elif target.lower() not in enabled_targets:
            row.errors.append(f"Target volume does not exist or is disabled: {target}")
        operation = row.operation.strip().lower()
        if operation not in BOOLEAN_OPERATIONS:
            row.errors.append("Operation must be subtraction, union, or intersection.")
        shape = row.tool_shape.strip().lower()
        if shape not in SUPPORTED_BOOLEAN_TOOL_SHAPES:
            row.errors.append(f"Unsupported boolean tool shape '{row.tool_shape}'.")
        elif shape not in STABLE_GUI_SHAPES:
            row.warnings.append(f"Tool shape '{row.tool_shape}' is backend-supported but preview is approximate.")
        if shape == "box":
            if len(_split_csv_or_space(row.tool_size)) < 3:
                row.errors.append("box boolean tool requires size with three length components.")
            if row.tool_parameters.strip():
                row.errors.append("box boolean tool does not accept parameters.")
        elif shape in {"tubs", "sphere", "orb", "cone"}:
            expected = {"tubs": 5, "sphere": 6, "orb": 1, "cone": 7}[shape]
            actual = _parameter_count(row.tool_parameters)
            if actual != expected:
                row.errors.append(f"{shape} boolean tool requires exactly {expected} parameters; got {actual}.")
            if row.tool_size.strip():
                row.errors.append(f"{shape} boolean tool does not accept size shorthand.")
        if row.position.strip() and len(_split_csv_or_space(row.position)) < 3:
            row.errors.append("Tool position must have three components.")
        if row.rotation.strip() and len(_split_csv_or_space(row.rotation)) < 3:
            row.errors.append("Tool rotation must have three components.")
        if target:
            indices_by_target.setdefault(target.lower(), []).append(row.index)
        if operation in {"union", "intersection"}:
            row.warnings.append("Union/intersection results are shown approximately; Geant4 backend is authoritative.")

    for target, indices in indices_by_target.items():
        ordered = sorted(indices)
        expected = list(range(len(ordered)))
        if ordered != expected:
            document.warnings.append(
                f"[BOOLEAN][WARN] target '{target}' indices are not contiguous; writer will renumber enabled ops from 0."
            )


def _require_material(value: str, label: str, known_materials: set[str], document: GeometryDocument) -> None:
    material = value.strip()
    if not material:
        document.errors.append(f"{label} is required.")
        return
    status = material_reference_status(material, known_materials)
    if status in {"custom", "nist"}:
        return
    if status == "g4":
        document.warnings.append(f"{label} references possible NIST material '{material}', not in GUI quick list.")
    else:
        document.errors.append(f"{label} references undefined custom material '{material}'.")


def _require_vec3(value: str, label: str, document: GeometryDocument) -> None:
    if len([token for token in re.split(r"[,\s]+", value.strip()) if token]) < 3:
        document.errors.append(f"{label} expects three components.")


def _split_csv_or_space(value: str) -> list[str]:
    return [token for token in re.split(r"[,\s]+", value.strip()) if token]


def _parameter_count(value: str) -> int:
    text = value.strip()
    if not text:
        return 0
    if "," in text:
        return len([part for part in text.split(",") if part.strip()])
    tokens = text.split()
    if len(tokens) % 2 == 0 and all(re.search(r"[A-Za-z]", tokens[index]) for index in range(1, len(tokens), 2)):
        return len(tokens) // 2
    return len(tokens)


def _looks_like_xy(value: str) -> bool:
    tokens = [token for token in re.split(r"[,\s]+", value.strip()) if token]
    return len(tokens) >= 2 and bool(re.search(r"\d", value)) and bool(re.search(r"[A-Za-z]", value))


def _looks_like_value_with_unit(value: str) -> bool:
    return bool(re.search(r"\d", value.strip())) and bool(re.search(r"[A-Za-z]", value.strip()))


def _is_int(value: str) -> bool:
    try:
        int(value.strip())
        return True
    except ValueError:
        return False


def _is_int32(value: str) -> bool:
    if not _is_int(value):
        return False
    number = int(value.strip())
    return -(2**31) <= number <= 2**31 - 1


def _mode_from_template(template_name: str) -> str:
    name = (template_name or "").strip().lower()
    if name in {"boolean_hierarchical", "hierarchical_boolean", "boolean"}:
        return "hierarchical_boolean"
    if name == "hierarchical":
        return "hierarchical"
    if name in EDITABLE_GEOMETRY_MODES:
        return name
    return "preview_only"


def _parse_ini_sections(raw_text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for line in raw_text.splitlines():
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        if text.startswith("[") and text.endswith("]"):
            current = text[1:-1].strip()
            sections.setdefault(current.lower(), {})
            continue
        if "=" in text and current:
            key, value = text.split("=", 1)
            sections.setdefault(current.lower(), {})[key.strip().lower()] = value.strip()
    return sections


def _simple_from_sections(sections: dict[str, dict[str, str]]) -> SimpleBoxGeometryModel:
    world = sections.get("world", {})
    target = sections.get("target", {})
    return SimpleBoxGeometryModel(
        world_size=world.get("size", "10 cm, 10 cm, 10 cm"),
        world_material=world.get("material", "G4_AIR"),
        target_name=target.get("name", "Target"),
        target_shape=target.get("shape", "box"),
        target_size=target.get("size", "1 cm, 1 cm, 1 mm"),
        target_material=target.get("material", "G4_Si"),
        target_position=target.get("position", "0 mm, 0 mm, 0 mm"),
        target_rotation=target.get("rotation", "0 deg, 0 deg, 0 deg"),
        target_sensitive=_as_bool(target.get("sensitive", "true")),
        target_bias=_as_bool(target.get("bias", "false")),
        target_region=target.get("region", "SV"),
    )


def _layered_from_sections(sections: dict[str, dict[str, str]], raw_text: str) -> LayeredDeviceGeometryModel:
    world = sections.get("world", {})
    layers_section = sections.get("layers", {})
    names = _split_csv(layers_section.get("names", ""))
    rows: list[LayerRow] = []
    for name in names:
        layer = sections.get(f"layer.{name}".lower(), {})
        rows.append(
            LayerRow(
                enabled=True,
                name=name,
                material=layer.get("material", "G4_Si"),
                thickness=layer.get("thickness", "1 um"),
                xy=layer.get("xy", "10 mm, 10 mm"),
                sensitive=_as_bool(layer.get("sensitive", "false")),
                bias=_as_bool(layer.get("bias", "false")),
                region=layer.get("region", ""),
                copy_no=layer.get("copyno", ""),
                position=layer.get("position", ""),
                rotation=layer.get("rotation", ""),
                visual={key: value for key, value in layer.items() if key in VISUAL_KEYS},
                production_cuts={key: value for key, value in layer.items() if key in PRODUCTION_CUT_KEYS},
                metadata="\n".join(_original_metadata_lines(raw_text, f"layer.{name}")),
            )
        )
    return LayeredDeviceGeometryModel(
        world_size=world.get("size", "20 cm, 20 cm, 20 cm"),
        world_material=world.get("material", "G4_AIR"),
        axis=layers_section.get("axis", "z"),
        auto_stack=_as_bool(layers_section.get("auto_stack", "true")),
        gap=layers_section.get("gap", "0 um"),
        z_start=layers_section.get("z_start", ""),
        layers=rows or LayeredDeviceGeometryModel().layers,
    )


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _original_metadata_lines(raw_text: str, section_name: str) -> list[str]:
    current = ""
    lines: list[str] = []
    for raw in raw_text.splitlines():
        text = raw.split("#", 1)[0].strip()
        if text.startswith("[") and text.endswith("]"):
            current = text[1:-1].strip().lower()
        elif current == section_name.lower() and "=" in text:
            key, value = text.split("=", 1)
            if key.strip().lower().startswith("metadata."):
                lines.append(f"{key.strip()} = {value.strip()}")
    return lines


def _validate_metadata_text(metadata: str, row: HierarchicalVolumeRow | LayerRow) -> None:
    for line_no, raw in enumerate(metadata.splitlines(), start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            row.errors.append(f"metadata line {line_no} must use metadata.<name> = value.")
            continue
        key, _value = text.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"metadata\.[A-Za-z0-9_.-]+", key, flags=re.IGNORECASE):
            row.errors.append(
                f"metadata line {line_no} key '{key}' is not allowed; only metadata.<non-empty-name> is permitted."
            )


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _volume_from_dict(data: dict) -> HierarchicalVolumeRow:
    mapped = dict(data)
    if "copyNo" in mapped and "copy_no" not in mapped:
        mapped["copy_no"] = mapped["copyNo"]
    return HierarchicalVolumeRow(**{k: v for k, v in mapped.items() if k in HierarchicalVolumeRow.__dataclass_fields__})


def _boolean_from_dict(data: dict) -> BooleanOperationRow:
    mapped = dict(data)
    if "target" in mapped and "target_volume" not in mapped:
        mapped["target_volume"] = mapped["target"]
    if "toolShape" in mapped and "tool_shape" not in mapped:
        mapped["tool_shape"] = mapped["toolShape"]
    if "toolSize" in mapped and "tool_size" not in mapped:
        mapped["tool_size"] = mapped["toolSize"]
    if "toolParameters" in mapped and "tool_parameters" not in mapped:
        mapped["tool_parameters"] = mapped["toolParameters"]
    return BooleanOperationRow(**{k: v for k, v in mapped.items() if k in BooleanOperationRow.__dataclass_fields__})


def _clean_dataclass(row) -> dict:
    data = asdict(row)
    data.pop("errors", None)
    data.pop("warnings", None)
    return data
