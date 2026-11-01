from __future__ import annotations

import re
import math
from contextvars import ContextVar
from pathlib import Path
from dataclasses import asdict, dataclass, field
from types import SimpleNamespace

from g4usim_gui.core.diagnostics import (
    EditorLocation, collect_diagnostics, emit_diagnostic, extend_diagnostics, reset_diagnostics,
)

from g4usim_gui.editors.editable_models import EditableDocument
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.project_migration import normalize_geometry_data, validate_dataclass_fields
from g4usim_gui.parsers.materials_parser import NIST_QUICK_LIST, material_reference_status
from g4usim_gui.parsers.geometry_parser import GeometrySummary
from g4usim_gui.parsers.geometry_parser import PRODUCTION_CUT_KEYS, TRD_PROPERTY_KEYS, VISUAL_KEYS
from g4usim_gui.preview3d.units import parse_length_to_mm, parse_angle_deg, parse_vec3_to_mm
from g4usim_gui.core.solid_registry_data import SOLIDS, ALIASES, canonical_solid, solid_spec, property_keys
from g4usim_gui.parsers.geometry_parser import PLACEMENT_PROPERTY_KEYS


EDITABLE_GEOMETRY_MODES = {"simple_box", "layered_device", "hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}
HIERARCHICAL_GEOMETRY_MODES = {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}
SUPPORTED_HIERARCHICAL_SHAPES = set(ALIASES)
SUPPORTED_BOOLEAN_TOOL_SHAPES = {alias for alias, name in ALIASES.items() if SOLIDS[name]["boolean_tool"]}
BACKEND_SHAPES = set(ALIASES)
SUPPORTED_VISUAL_COLORS = {
    "white", "black", "red", "green", "blue", "yellow", "cyan", "aqua",
    "magenta", "gray", "grey", "darkgray", "lime", "brown",
}
STABLE_GUI_SHAPES = {"box", "tubs"}
BOOLEAN_OPERATIONS = {"subtraction", "union", "intersection"}
_ACTIVE_DOCUMENT: ContextVar[GeometryDocument | None] = ContextVar("geometry_diagnostic_document", default=None)


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
    preview_properties: dict[str, str] = field(default_factory=dict)   # known placement and legacy sketch projection
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
    shape_properties: dict[str, str] = field(default_factory=dict)
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
    document._f4_source_diagnostics = collect_diagnostics(summary)
    document._f4_source_snapshot = getattr(summary, "_f4_source_snapshot", None)
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
                shape_properties=dict(op.shape_properties),
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
        if data is None:
            return document
        raise ValueError("Expected JSON object: project.geometryEditor")
    data = normalize_geometry_data(data)
    document.mode = str(data.get("mode", "preview_only"))
    raw_version = data.get("schema_version", data.get("schemaVersion"))
    if raw_version is not None:
        if str(raw_version) not in {"1", "2"}:
            raise ValueError(f"Unsupported geometry schema version in project snapshot: {raw_version}")
        document.schema_version = int(raw_version)
    validate_dataclass_fields(data, GeometryDocument, "project.geometryEditor")
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
        if "layers" in layered:
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
    token = _ACTIVE_DOCUMENT.set(document)
    try:
        _validate_geometry_document(document, material_names=material_names,
                                    scoring_hits_enabled=scoring_hits_enabled,
                                    physics_biasing_enabled=physics_biasing_enabled)
    finally:
        _ACTIVE_DOCUMENT.reset(token)


def _validate_geometry_document(document: GeometryDocument, *, material_names: set[str] | None,
                                scoring_hits_enabled: bool, physics_biasing_enabled: bool) -> None:
    _prepare_diagnostics(document)
    document.errors = []
    document.warnings = []
    if document.schema_version not in {None, 1, 2}:
        _issue(document, 'geometry.schema_version', 'error', "Geometry schema version must be 1, 2, or absent.", 'schema_version', reason='unsupported_editor')
    known_materials = set(material_names or set()) | NIST_QUICK_LIST
    if document.mode == "simple_box":
        _validate_simple(document, known_materials)
    elif document.mode == "layered_device":
        _validate_layered(document, known_materials)
    elif document.mode in HIERARCHICAL_GEOMETRY_MODES:
        _validate_hierarchical(document, known_materials)
    else:
        _issue(document, 'geometry.preview_only', 'warning', "This geometry template is preview-only in the GUI MVP. Source geometry.ini will be copied unchanged.", 'mode', reason='preview_only')

    if geometry_sensitive_count(document) and not scoring_hits_enabled:
        _issue(document, 'geometry.scoring_hits_disabled', 'warning', "Geometry marks sensitive volumes, but scoring hits output is disabled.", 'hits', location=EditorLocation('scoring', 'hits'))
    if geometry_bias_count(document) and not physics_biasing_enabled:
        _issue(document, 'geometry.bias_hook_disabled', 'warning', "Geometry marks bias volumes, but physics biasing hook is disabled.", 'enable_biasing_physics', location=EditorLocation('physics', 'enable_biasing_physics'))
    if document.round_trip_blockers and not document.source_copy_mode:
        _issue(document, 'geometry.round_trip.blocked', 'error', "Source geometry contains fields that the current editor cannot preserve; use original source copy mode.", 'source_copy_mode', location=EditorLocation('geometry', 'source_copy_mode'))
        document.errors.extend(f"Round-trip blocker: {item}" for item in document.round_trip_blockers)
    if document.source_copy_mode and document.round_trip_blockers:
        _issue(document, 'geometry.round_trip.source_copy', 'warning', "Original geometry source will be copied unchanged; Geometry Editor validation does not certify blocked fields.", 'source_copy_mode', location=EditorLocation('geometry', 'source_copy_mode'))

    document.validation_errors = _deduplicate(document.errors)
    document.validation_warnings = _deduplicate(document.warnings)
    document.errors = _deduplicate([*document.source_errors, *document.validation_errors])
    document.warnings = _deduplicate([*document.source_warnings, *document.validation_warnings])
    _finish_diagnostics(document)


def _prepare_diagnostics(document: GeometryDocument) -> None:
    reset_diagnostics(document)
    extend_diagnostics(document, (item for item in getattr(document, "_f4_source_diagnostics", ())
                                  if item.severity != "blocker"), append=False)
    if document.mode == "layered_device":
        document._f4_context = ("layers", "layered_device", None)
    else:
        document._f4_context = ("geometry", "simple_box" if document.mode == "simple_box" else "", None)
    document._f4_target_context = {id(document): document._f4_context}
    document._f4_row_diagnostics = {}
    for model, editor, collection in ((document.simple_box, "geometry", "simple_box"),
                                      (document.layered_device, "layers", "layered_device")):
        document._f4_target_context[id(model)] = (editor, collection, None)
    for editor, collection, rows in (("geometry", "volumes", document.volumes),
                                     ("layers", "layers", document.layered_device.layers),
                                     ("booleans", "boolean_ops", document.boolean_ops)):
        for index, row in enumerate(rows):
            # Layers and simple models have legacy __dict__ snapshot/clone paths.
            # Keep every row's runtime metadata on the document, never on the row.
            document._f4_row_diagnostics[id(row)] = SimpleNamespace()
            document._f4_target_context[id(row)] = (editor, collection, index)


def _finish_diagnostics(document: GeometryDocument) -> None:
    if document.round_trip_blockers and not document.source_copy_mode:
        extend_diagnostics(document, (item for item in getattr(document, "_f4_source_diagnostics", ())
                                      if item.severity == "blocker"), prefix="Round-trip blocker: ", append=False)
    if document.mode == "layered_device":
        for row in document.layered_device.layers:
            if row.enabled:
                extend_diagnostics(document, collect_diagnostics(document._f4_row_diagnostics[id(row)]), prefix=f"[layer.{row.name}]: ", append=False)
    elif document.mode in HIERARCHICAL_GEOMETRY_MODES:
        for row in document.volumes:
            if row.enabled:
                for item in collect_diagnostics(document._f4_row_diagnostics[id(row)]):
                    tag = "ERROR" if item.severity == "error" else "WARN"
                    extend_diagnostics(document, (item,), prefix=f"[GEOMETRY][{tag}] {row.name or '<unnamed>'}: ", append=False)
        for row in document.boolean_ops:
            if row.enabled:
                for item in collect_diagnostics(document._f4_row_diagnostics[id(row)]):
                    tag = "ERROR" if item.severity == "error" else "WARN"
                    extend_diagnostics(document, (item,), prefix=f"[BOOLEAN][{tag}] {row.target_volume or '<missing>'}[{row.index}]: ", append=False)


def _issue(owner, code: str, severity: str, message: str, field: str, *, target=None,
           location: EditorLocation | None = None, reason: str = "", facts: dict | None = None) -> None:
    # Transient context lives only on the document: row __dict__ is a legacy API.
    getattr(owner, "errors" if severity == "error" else "warnings").append(message)
    target = owner if target is None else target
    document = _ACTIVE_DOCUMENT.get()
    editor, collection, index = document._f4_target_context.get(id(target), ("geometry", "", None))
    entity = (f"{target.target_volume}[{target.index}]" if isinstance(target, BooleanOperationRow)
              else getattr(target, "name", ""))
    if location is None and not reason:
        location = EditorLocation(editor, field, collection, index, entity)
    value = getattr(target, field, None)
    for attribute in ("visual", "production_cuts", "shape_properties", "preview_properties"):
        if field in getattr(target, attribute, {}):
            value = getattr(target, attribute)[field]
    if not isinstance(value, (str, int, float, bool, type(None))):
        value = None
    # Only the original successful parser read can provide historical text.
    # Legacy restored documents without this runtime evidence remain unlocated.
    source = getattr(document, "_f4_source_snapshot", None) if reason else None
    identity = {"value": value, **(facts or {})}
    if location is None:
        identity.update(field=field, collection=collection, row=index, entity=entity)
    destination = document if owner is document else document._f4_row_diagnostics[id(owner)]
    emit_diagnostic(destination, code, severity, message, origin="geometry.editor", location=location,
                    source=source, identity_parameters=identity,
                    unavailable_reason=reason, append=False)


def _validate_simple(document: GeometryDocument, known_materials: set[str]) -> None:
    simple = document.simple_box
    _require_vec3(simple.world_size, "simple_box [world]/size", document, target=simple, field='world_size')
    _require_material(simple.world_material, "simple_box [world]/material", known_materials, document, target=simple, field='world_material')
    if not simple.target_name.strip():
        _issue(document, 'geometry.simple.name_required', 'error', "simple_box target name is required.", 'target_name', target=simple)
    if simple.target_shape.strip().lower() != "box":
        _issue(document, 'geometry.simple.shape', 'error', "simple_box target only supports shape=box.", 'target_shape', target=simple)
    _require_vec3(simple.target_size, "simple_box [target]/size", document, target=simple, field='target_size')
    _require_vec3(simple.target_position, "simple_box [target]/position", document, target=simple, field='target_position')
    _require_vec3(simple.target_rotation, "simple_box [target]/rotation", document, target=simple, field='target_rotation')
    _require_material(simple.target_material, "simple_box [target]/material", known_materials, document, target=simple, field='target_material')


def _validate_layered(document: GeometryDocument, known_materials: set[str]) -> None:
    layered = document.layered_device
    _require_vec3(layered.world_size, "layered_device [world]/size", document, target=layered, field='world_size')
    _require_material(layered.world_material, "layered_device [world]/material", known_materials, document, target=layered, field='world_material')
    if layered.axis.strip().lower() != "z":
        _issue(document, 'geometry.layered.axis', 'error', "layered_device currently supports axis=z only.", 'axis', target=layered)
    if not _looks_like_value_with_unit(layered.gap):
        _issue(document, 'geometry.layered.gap', 'warning', "layered_device gap should include a length unit, e.g. 0 um.", 'gap', target=layered)

    enabled_layers = [layer for layer in layered.layers if layer.enabled]
    if not enabled_layers:
        _issue(document, 'geometry.layered.empty', 'error', "layered_device requires at least one enabled layer.", 'layers', reason='empty_collection')
    seen: set[str] = set()
    for index, layer in enumerate(enabled_layers, start=1):
        layer.errors.clear()
        if not layer.name.strip():
            _issue(document, 'geometry.layer.name_required', 'error', f"layered_device layer #{index} name is required.", 'name', target=layer)
            continue
        key = layer.name.strip().lower()
        if key in seen:
            _issue(document, 'geometry.layer.duplicate_name', 'error', f"layered_device duplicate layer name: {layer.name}", 'name', target=layer)
        seen.add(key)
        _require_material(layer.material, f"layered_device [layer.{layer.name}]/material", known_materials, document, target=layer, field='material')
        if not _looks_like_value_with_unit(layer.thickness):
            _issue(document, 'geometry.layer.thickness', 'error', f"layered_device layer '{layer.name}' thickness must include a positive length with unit.", 'thickness', target=layer)
        if not _looks_like_xy(layer.xy):
            _issue(document, 'geometry.layer.xy', 'error', f"layered_device layer '{layer.name}' xy must have two lengths, e.g. 10 mm, 10 mm.", 'xy', target=layer)
        if layer.copy_no.strip() and not _is_int32(layer.copy_no):
            _issue(document, 'geometry.layer.copy_no', 'error', f"layered_device layer '{layer.name}' copyNo must be a signed 32-bit integer.", 'copy_no', target=layer)
        if not layered.auto_stack and not layer.position.strip():
            _issue(document, 'geometry.layer.position_required', 'error', f"layered_device layer '{layer.name}' requires position when auto_stack=false.", 'position', target=layer)
        if layer.position.strip():
            _require_vec3(layer.position, f"[layer.{layer.name}]/position", document, target=layer, field='position')
        if layer.rotation.strip():
            _require_vec3(layer.rotation, f"[layer.{layer.name}]/rotation", document, target=layer, field='rotation')
        for field, value in layer.production_cuts.items():
            if field not in PRODUCTION_CUT_KEYS:
                _issue(layer, 'geometry.layer.cut_unknown', 'error', f"Unsupported production cut field '{field}'.", field, reason='unsupported_editor')
            elif not layer.region.strip():
                _issue(layer, 'geometry.layer.cut_region', 'error', f"{field} requires a non-empty region in the same layer.", 'region', facts={'cut_field': field})
            elif (parsed := parse_length_to_mm(value)) is None or parsed <= 0:
                _issue(layer, 'geometry.layer.cut_positive', 'error', f"{field} must be a positive length.", field)
        for field, value in layer.visual.items():
            if field not in VISUAL_KEYS:
                _issue(layer, 'geometry.layer.visual_unknown', 'error', f"Unsupported visual field '{field}'.", field, reason='unsupported_editor')
            elif field == "vis.alpha":
                try:
                    alpha = float(value.strip())
                    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
                        _issue(layer, 'geometry.layer.alpha_range', 'error', "vis.alpha must be between 0 and 1.", 'vis.alpha')
                except ValueError:
                    _issue(layer, 'geometry.layer.alpha_numeric', 'error', "vis.alpha must be numeric.", 'vis.alpha')
            elif field in {"vis.visible", "vis.wireframe"} and value.strip().lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                _issue(layer, 'geometry.layer.visual_bool', 'error', f"{field} must be a boolean value.", field)
            elif field == "vis.color" and value.strip().lower() not in SUPPORTED_VISUAL_COLORS:
                _issue(layer, 'geometry.layer.color', 'error', "vis.color must be a color supported by the backend.", 'vis.color')
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
        _issue(document, 'geometry.hierarchical.empty', 'error', "hierarchical geometry requires at least one enabled volume.", 'volumes', reason='empty_collection')
        return

    by_key: dict[str, HierarchicalVolumeRow] = {}
    for row in enabled:
        name = row.name.strip()
        if not name:
            _issue(row, 'geometry.volume.name_required', 'error', "Volume name is required.", 'name')
            continue
        key = name.lower()
        if key in by_key:
            _issue(row, 'geometry.volume.duplicate_name', 'error', f"Duplicate volume name: {name}", 'name')
            _issue(by_key[key], 'geometry.volume.duplicate_name', 'error', f"Duplicate volume name: {name}", 'name')
            _issue(document, 'geometry.duplicate_name_summary', 'error', f"[GEOMETRY] duplicate volume name: {name}", 'name', target=row)
        else:
            by_key[key] = row

    if "world" not in by_key:
        _issue(document, 'geometry.world_missing', 'error', "[GEOMETRY] hierarchical geometry requires a world volume named 'world'.", 'volumes', reason='missing_entity')

    for row in enabled:
        name = row.name.strip()
        key = name.lower()
        parent = row.parent.strip()
        shape = row.shape.strip().lower()
        if key != "world":
            if not parent:
                _issue(row, 'geometry.parent.required', 'error', "Non-world volume requires parent.", 'parent')
            elif parent.lower() == key:
                _issue(row, 'geometry.parent.self', 'error', "Volume parent cannot point to itself.", 'parent')
            elif parent.lower() not in by_key:
                _issue(row, 'geometry.parent.missing', 'error', f"Parent volume does not exist: {parent}", 'parent')
        _validate_solid(row, document)
        _validate_placement(row, document, by_key)
        _require_material(row.material, f"[volume.{name}]/material", known_materials, document, target=row, field='material')
        if row.position.strip():
            _require_vec3(row.position, f"[volume.{name}]/position", document, target=row, field='position')
        if row.rotation.strip():
            _require_vec3(row.rotation, f"[volume.{name}]/rotation", document, target=row, field='rotation')
        if row.copy_no.strip() and not _is_int32(row.copy_no):
            _issue(row, 'geometry.copy_no', 'error', "copyNo must be a signed 32-bit integer.", 'copy_no')
        for field, value in row.production_cuts.items():
            if field not in PRODUCTION_CUT_KEYS:
                _issue(row, 'geometry.cut.unknown', 'error', ui_format("Unsupported production cut field '{field}'.", field=field), field, reason='unsupported_editor')
            elif not row.region.strip():
                _issue(row, 'geometry.cut.region', 'error', ui_format("{field} requires a non-empty region in the same volume.", field=field), 'region', facts={'cut_field': field})
            elif (parsed := parse_length_to_mm(value)) is None or parsed <= 0:
                _issue(row, 'geometry.cut.positive', 'error', ui_format("{field} must be a positive length.", field=field), field)
        for field, value in row.visual.items():
            if field not in VISUAL_KEYS:
                _issue(row, 'geometry.visual.unknown', 'error', ui_format("Unsupported visual field '{field}'.", field=field), field, reason='unsupported_editor')
            elif field == "vis.alpha":
                try:
                    alpha = float(value.strip())
                    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
                        _issue(row, 'geometry.visual.alpha_range', 'error', ui_text("vis.alpha must be between 0 and 1."), 'vis.alpha')
                except ValueError:
                    _issue(row, 'geometry.visual.alpha_numeric', 'error', ui_text("vis.alpha must be numeric."), 'vis.alpha')
            elif field in {"vis.visible", "vis.wireframe"} and value.strip().lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
                _issue(row, 'geometry.visual.boolean', 'error', ui_format("{field} must be a boolean value.", field=field), field)
            elif field == "vis.color" and value.strip().lower() not in SUPPORTED_VISUAL_COLORS:
                _issue(row, 'geometry.visual.color', 'error', ui_text("vis.color must be a color supported by the backend."), 'vis.color')
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


def _solid_tokens(text: str) -> list[str]:
    if not text.strip():
        return []
    if ',' in text:
        return [part.strip() for part in text.split(',')]
    # Same numeric/unit grouping accepted by the backend parameter-list parser.
    pattern = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:\s*\*?\s*[A-Za-zµ]+)?'
    matches = list(re.finditer(pattern, text))
    tail = re.sub(pattern, '', text)
    if tail.strip():
        return [text]
    return [match.group().strip() for match in matches]


def _solid_scalar(text: str, dimension: str) -> float:
    if dimension == 'integer':
        number = float(text.strip())
        if not math.isfinite(number) or number != math.floor(number):
            raise ValueError('integer required')
        return number
    if dimension == 'angle':
        # Bare backend angles use rad, whereas the sketch helper defaults to deg.
        number = (float(text.strip()) if re.fullmatch(r'[+\-\d.eE]+', text.strip())
                  else math.radians(parse_angle_deg(text)))
    else:
        number = parse_length_to_mm(text)
    if number is None or not math.isfinite(number):
        raise ValueError('finite ' + dimension + ' required')
    return number


def _geometry_resource_path(document: GeometryDocument, text: str) -> Path:
    path = Path(text.strip()).expanduser()
    if not path.is_absolute():
        if not document.source_path:
            raise ValueError('In-memory geometry requires absolute resource paths.')
        path = Path(document.source_path).expanduser().resolve().parent / path
    return path.resolve()


def _check_geometry_resource(row, document: GeometryDocument, key: str, value: str) -> None:
    try:
        path = _geometry_resource_path(document, value)
        if not path.is_file():
            raise ValueError('file is missing')
        if key == 'copies_file':
            import csv
            with path.open(encoding='utf-8-sig', newline='') as stream:
                records = list(csv.reader(line for line in stream if line.strip() and not line.lstrip().startswith(('#',';'))))
            header = [c.strip().lower() for c in records[0]] if records else []
            base = ['x_mm','y_mm','z_mm']
            variants = [base, base+['material'], base+['rot_x_deg','rot_y_deg','rot_z_deg'],
                        base+['rot_x_deg','rot_y_deg','rot_z_deg','material']]
            if header not in variants or len(records) < 2:
                raise ValueError('copies_file header or copy rows are invalid')
            for cells in records[1:]:
                if len(cells) != len(header): raise ValueError('copies_file column count differs')
                count = len(header)-1 if header[-1]=='material' else len(header)
                if not all(math.isfinite(float(cell.strip())) for cell in cells[:count]):
                    raise ValueError('copies_file numeric values must be finite')
    except (OSError, ValueError, OverflowError) as exc:
        _issue(row, 'geometry.resource.' + key, 'error', ui_format(
            'Invalid geometry resource {field}: {detail}', field=key, detail=str(exc)), key)


def _validate_solid(row, document: GeometryDocument, *, boolean: bool = False) -> None:
    shape = canonical_solid(row.tool_shape if boolean else row.shape)
    spec = solid_spec(shape)
    shape_field = 'tool_shape' if boolean else 'shape'
    size_field = 'tool_size' if boolean else 'size'
    parameter_field = 'tool_parameters' if boolean else 'parameters'
    def error(field, message):
        _issue(row, 'geometry.solid.' + field, 'error', message, field)
    if spec is None or (boolean and not spec['boolean_tool']):
        error(shape_field, ui_format("Unsupported boolean tool shape '{shape}'." if boolean else
                                    "Unsupported shape '{shape}'.", shape=shape))
        return
    size = row.tool_size if boolean else row.size
    parameters = row.tool_parameters if boolean else row.parameters
    tokens = _solid_tokens(parameters)
    if spec['uses_size']:
        vector = parse_vec3_to_mm(size)
        if vector is None or not all(math.isfinite(v) and v > 0 for v in vector):
            error(size_field, ui_text('Box size must contain three positive finite lengths.'))
    elif size.strip():
        error(size_field, ui_format('{shape} does not accept size shorthand.', shape=shape))
    if spec['parameter_counts']:
        if len(tokens) not in spec['parameter_counts']:
            error(parameter_field, ui_format('{shape} parameter count must be one of {counts}.',
                                            shape=shape, counts=str(spec['parameter_counts'])))
    elif parameters.strip():
        error(parameter_field, ui_format('{shape} does not accept parameters.', shape=shape))
    numbers = []
    if len(tokens) in spec['parameter_counts']:
        for token, field in zip(tokens, spec['parameters']):
            try:
                numbers.append(_solid_scalar(token, field['dimension']))
            except (ValueError, TypeError, OverflowError):
                error(parameter_field, ui_format('Invalid {dimension} value for {field}: {value}',
                                                dimension=field['dimension'], field=field['name'], value=token))
                break
    properties = row.shape_properties
    allowed = set(property_keys(shape))
    for field in properties:
        if field not in allowed:
            error(field, ui_format("Unsupported shape field '{field}'.", field=field))
    for field in spec['properties']:
        value = properties.get(field['name'], '')
        if not value.strip():
            if field['required']:
                error(field['name'], ui_format('Required geometry field: {field}', field=field['name']))
            continue
        try:
            if field['dimension'] in {'length', 'angle'}:
                n = _solid_scalar(value, field['dimension'])
                if field['dimension'] == 'length' and n <= 0:
                    raise ValueError('positive length required')
            elif field['dimension'] == 'path':
                _check_geometry_resource(row, document, field['name'], value)
            elif field['dimension'] == 'length_unit':
                if _solid_scalar('1 ' + value, 'length') <= 0:
                    raise ValueError('positive length unit required')
            elif field['dimension'] == 'length_list':
                if not _solid_tokens(value):
                    raise ValueError('list required')
                for token in _solid_tokens(value):
                    _solid_scalar(token, 'length')
        except (TypeError, ValueError, OverflowError):
            error(field['name'], ui_format('Invalid {dimension} value for {field}: {value}',
                                         dimension=field['dimension'], field=field['name'], value=value))
    if len(numbers) == len(tokens) and numbers:
        p = numbers
        valid = True
        if shape == 'tubs': valid = 0 <= p[0] < p[1] and p[2] > 0 and p[4] > 0
        elif shape == 'sphere': valid = 0 <= p[0] < p[1] and p[3] > 0 and p[5] > 0
        elif shape == 'orb': valid = p[0] > 0
        elif shape == 'cone': valid = 0 <= p[0] < p[1] and 0 <= p[2] < p[3] and p[4] > 0 and p[6] > 0
        elif shape == 'ellipsoid': valid = all(n > 0 for n in p[:3]) and (len(p) == 3 or p[3] < p[4])
        elif shape in {'eltube', 'para'}: valid = all(n > 0 for n in p[:3])
        elif shape == 'torus': valid = 0 <= p[0] < p[1] <= p[2] and p[4] > 0
        elif shape == 'hype': valid = 0 <= p[0] < p[1] and p[4] > 0
        elif shape in {'polycone', 'polyhedra'}:
            valid = p[1] > 0 and (shape != 'polyhedra' or p[2] >= 3)
            try:
                z, ri, ro = [[_solid_scalar(t, 'length') for t in _solid_tokens(properties.get(k, ''))]
                             for k in ('z_planes', 'r_inner', 'r_outer')]
                valid = valid and len(z) >= 2 and len(ri) == len(ro) == len(z)
                valid = valid and all(a <= b for a, b in zip(z, z[1:])) and all(0 <= a <= b for a, b in zip(ri, ro))
            except (TypeError, ValueError, OverflowError):
                valid = False
        if not valid:
            error(parameter_field, ui_format('Invalid dimensions or parameter relationships for {shape}.', shape=shape))
    if spec['experimental']:
        _issue(row, 'geometry.solid.experimental', 'warning', ui_format(
            '{shape} is experimental; sketch preview does not validate backend geometry.', shape=shape), shape_field)


def _validate_placement(row, document: GeometryDocument, volumes: dict) -> None:
    p = row.preview_properties
    mode = p.get('placement', 'normal').strip().lower()
    def error(field, message):
        _issue(row, 'geometry.placement.' + field, 'error', message, field)
    if mode not in {'normal', 'replica', 'parameterised', 'parameterized'}:
        error('placement', ui_text('Only normal, replica and parameterised placements are supported.'))
        return
    for key in p:
        if key not in PLACEMENT_PROPERTY_KEYS and key not in property_keys(row.shape):
            error(key, ui_format("Unsupported geometry property '{field}'.", field=key))
        if (key.startswith('replica_') and mode != 'replica') or (key in {'copies_file', 'copies', 'copy_step'} and mode not in {'parameterised', 'parameterized'}):
            error(key, ui_format('Field {field} conflicts with placement {mode}.', field=key, mode=mode))
    if mode == 'normal':
        return
    if row.name.strip().lower() == 'world':
        error('placement', ui_text('The world must use normal placement.'))
    siblings = [v for v in volumes.values() if v.parent.strip().lower() == row.parent.strip().lower() and v.name.strip().lower() != 'world']
    if len(siblings) != 1:
        error('placement', ui_text('Replica or parameterised placement must be the only daughter of its mother.'))
    if mode == 'replica':
        if row.position.strip() or row.rotation.strip() or row.copy_no.strip():
            error('placement', ui_text('Replica placement forbids position, rotation and copyNo.'))
        axis = p.get('replica_axis', '').strip().lower()
        if axis not in {'x', 'y', 'z', 'phi'}:
            error('replica_axis', ui_text('Replica axis must be x, y, z or phi.'))
        parent = volumes.get(row.parent.strip().lower())
        expected_shape = 'tubs' if axis == 'phi' else 'box'
        if not parent or canonical_solid(parent.shape) != expected_shape or canonical_solid(row.shape) != expected_shape:
            error('replica_axis', ui_text('Replica shape and mother must match the selected axis.'))
        count = p.get('replica_count', '')
        if not _is_int32(count) or int(count) <= 0:
            error('replica_count', ui_text('Replica count must be a positive 32-bit integer.'))
        try:
            width = _solid_scalar(p.get('replica_width', ''), 'angle' if axis == 'phi' else 'length')
            if width <= 0:
                raise ValueError('positive width required')
            offset = None
            if p.get('replica_offset', '').strip():
                offset = _solid_scalar(p['replica_offset'], 'angle' if axis == 'phi' else 'length')
                if axis != 'phi' and offset != 0:
                    raise ValueError('cartesian offset must be zero')
            if parent and _is_int32(count) and int(count) > 0:
                close = lambda a,b: abs(a-b) <= 1e-9 * max(1.0, abs(a), abs(b))
                if axis == 'phi' and canonical_solid(parent.shape) == canonical_solid(row.shape) == 'tubs':
                    def tubs(v):
                        return [_solid_scalar(t,f['dimension']) for t,f in zip(_solid_tokens(v.parameters), SOLIDS['tubs']['parameters'])]
                    mother, child = tubs(parent), tubs(row)
                    if len(mother)==len(child)==5:
                        if not (close(int(count)*width,mother[4]) and close(child[4],width)
                                and close(child[3],-width/2) and all(close(a,b) for a,b in zip(mother[:3],child[:3]))
                                and (offset is None or close(offset,mother[3]))):
                            error('replica_width', ui_text('Replica dimensions, total width or phi centering do not match the mother.'))
                elif axis in {'x','y','z'}:
                    mother, child = parse_vec3_to_mm(parent.size), parse_vec3_to_mm(row.size)
                    if mother and child:
                        index = {'x':0,'y':1,'z':2}[axis]
                        if not (close(int(count)*width,mother[index]) and all(
                                close(child[i],width if i==index else mother[i]) for i in range(3))):
                            error('replica_width', ui_text('Replica dimensions, total width or phi centering do not match the mother.'))
        except (TypeError, ValueError, OverflowError):
            error('replica_width', ui_text('Replica width/offset has invalid units or range.'))
    else:
        table = bool(p.get('copies_file', '').strip())
        linear = bool(p.get('copies', '').strip() or p.get('copy_step', '').strip())
        if table == linear:
            error('placement', ui_text('Parameterised placement requires either copies_file or copies + copy_step.'))
        if table:
            _check_geometry_resource(row, document, 'copies_file', p['copies_file'])
        if linear:
            count = p.get('copies', '')
            if not _is_int32(count) or int(count) <= 0:
                error('copies', ui_text('Copy count must be a positive 32-bit integer.'))
            vector = parse_vec3_to_mm(p.get('copy_step', ''))
            if vector is None or not all(math.isfinite(n) for n in vector):
                error('copy_step', ui_text('copy_step must contain three finite lengths.'))

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
                _issue(rows[name], 'geometry.parent.cycle', 'error', "Parent cycle detected.", 'parent')
                _issue(document, 'geometry.parent.cycle_summary', 'error', f"[GEOMETRY] parent cycle detected at volume '{rows[name].name}'.", 'parent', target=rows[name])
                break
            visiting.add(current)
            current = parents.get(current, "")


def _validate_boolean_operations(document: GeometryDocument, volumes_by_key: dict[str, HierarchicalVolumeRow]) -> None:
    enabled_targets = {row.name.strip().lower() for row in volumes_by_key.values() if row.enabled}
    indices_by_target: dict[str, list[int]] = {}
    for row in document.boolean_ops:
        if not row.enabled:
            _issue(row, 'geometry.boolean.disabled', 'warning', "Disabled boolean operation is ignored by writer.", 'enabled')
            continue
        target = row.target_volume.strip()
        if not target:
            _issue(row, 'geometry.boolean.target_required', 'error', "Target volume is required.", 'target_volume')
        elif target.lower() not in enabled_targets:
            _issue(row, 'geometry.boolean.target_missing', 'error', f"Target volume does not exist or is disabled: {target}", 'target_volume')
        operation = row.operation.strip().lower()
        if operation not in BOOLEAN_OPERATIONS:
            _issue(row, 'geometry.boolean.operation', 'error', "Operation must be subtraction, union, or intersection.", 'operation')
        _validate_solid(row, document, boolean=True)
        if row.position.strip() and len(_split_csv_or_space(row.position)) < 3:
            _issue(row, 'geometry.boolean.position', 'error', "Tool position must have three components.", 'position')
        if row.rotation.strip() and len(_split_csv_or_space(row.rotation)) < 3:
            _issue(row, 'geometry.boolean.rotation', 'error', "Tool rotation must have three components.", 'rotation')
        if target:
            indices_by_target.setdefault(target.lower(), []).append(row.index)
        if operation in {"union", "intersection"}:
            _issue(row, 'geometry.boolean.approximate_operation', 'warning', "Union/intersection results are shown approximately; Geant4 backend is authoritative.", 'operation')

    for target, indices in indices_by_target.items():
        ordered = sorted(indices)
        expected = list(range(len(ordered)))
        if ordered != expected:
            _issue(document, 'geometry.boolean.renumber', 'warning', f"[BOOLEAN][WARN] target '{target}' indices are not contiguous; writer will renumber enabled ops from 0.", 'index', reason='writer_assigned_index', facts={'target': target, 'indices': indices})


def _require_material(value: str, label: str, known_materials: set[str], document: GeometryDocument,
                      *, target=None, field: str) -> None:
    material = value.strip()
    if not material:
        _issue(document, 'geometry.material.required', 'error', f"{label} is required.", field, target=target)
        return
    status = material_reference_status(material, known_materials)
    if status in {"custom", "nist"}:
        return
    if status == "g4":
        _issue(document, 'geometry.material.unlisted', 'warning', f"{label} references possible NIST material '{material}', not in GUI quick list.", field, target=target)
    else:
        _issue(document, 'geometry.material.undefined', 'error', f"{label} references undefined custom material '{material}'.", field, target=target)


def _require_vec3(value: str, label: str, document: GeometryDocument, *, target=None, field: str) -> None:
    if len([token for token in re.split(r"[,\s]+", value.strip()) if token]) < 3:
        _issue(document, 'geometry.vector.components', 'error', f"{label} expects three components.", field, target=target)


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
            _issue(row, 'geometry.metadata.syntax', 'error', f"metadata line {line_no} must use metadata.<name> = value.", 'metadata', facts={'line': line_no})
            continue
        key, _value = text.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"metadata\.[A-Za-z0-9_.-]+", key, flags=re.IGNORECASE):
            _issue(row, 'geometry.metadata.key', 'error', f"metadata line {line_no} key '{key}' is not allowed; only metadata.<non-empty-name> is permitted.", 'metadata', facts={'line': line_no, 'key': key})


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _volume_from_dict(data: dict) -> HierarchicalVolumeRow:
    mapped = dict(data)
    if "copyNo" in mapped and "copy_no" not in mapped:
        mapped["copy_no"] = mapped["copyNo"]
    row = HierarchicalVolumeRow(**{k: v for k, v in mapped.items() if k in HierarchicalVolumeRow.__dataclass_fields__})
    for key in property_keys(row.shape):
        if key in row.preview_properties:
            if key in row.shape_properties and row.shape_properties[key] != row.preview_properties[key]:
                raise ValueError("Conflicting geometry property projections: " + key)
            row.shape_properties[key] = row.preview_properties.pop(key)
    return row


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
