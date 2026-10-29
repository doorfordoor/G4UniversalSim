from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.parsers.ini_light_parser import IniSection, parse_ini_light


FORBIDDEN_BOOLEAN_KEYS = {"material", "sensitive", "bias", "region", "parent", "placement", "copyno"}
SHAPE_PROPERTY_KEYS = {
    "dx1", "dx2", "dx3", "dx4", "dy1", "dy2", "dz",
    "theta", "phi", "alpha1", "alpha2",
}
TRD_PROPERTY_KEYS = ("dx1", "dx2", "dy1", "dy2", "dz")
# backend keys the editor cannot write (A5 solids, replica/parameterised placement): kept read-only so
# the 3D sketch can draw the solid or say why it does not (roadmap G4)
PREVIEW_PROPERTY_KEYS = {
    "z_planes", "r_inner", "r_outer", "file", "file_unit", "placement",
    "replica_axis", "replica_count", "replica_width", "replica_offset", "copies_file", "copies", "copy_step",
}
VISUAL_KEYS = {"vis.color", "vis.alpha", "vis.visible", "vis.wireframe"}
PRODUCTION_CUT_KEYS = {"cut.gamma", "cut.e-", "cut.e+", "cut.proton"}


@dataclass
class BooleanOperationEntry:
    target_volume: str
    index: int
    operation: str = ""
    tool_shape: str = ""
    tool_size: str = ""
    tool_parameters: str = ""
    position: str = ""
    rotation: str = ""
    name: str = ""
    section: str = ""
    line_no: int = 0
    forbidden_keys: list[str] = field(default_factory=list)


@dataclass
class VolumeEntry:
    name: str
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
    preview_properties: dict[str, str] = field(default_factory=dict)
    visual: dict[str, str] = field(default_factory=dict)
    production_cuts: dict[str, str] = field(default_factory=dict)
    section: str = ""
    line_no: int = 0
    boolean_ops: list[BooleanOperationEntry] = field(default_factory=list)


@dataclass
class GeometrySummary:
    path: str
    template_hint: str = ""
    schema_version: int | None = None
    volumes: list[VolumeEntry] = field(default_factory=list)
    material_refs: set[str] = field(default_factory=set)
    sensitive_volumes: set[str] = field(default_factory=set)
    bias_volumes: set[str] = field(default_factory=set)
    boolean_ops: list[BooleanOperationEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    round_trip_blockers: list[str] = field(default_factory=list)
    legacy_metadata: list[str] = field(default_factory=list)
    raw_text: str = ""
    diagnostics: list[GeometrySourceDiagnostic] = field(default_factory=list)

    def record(self, code: str, severity: str, message: str, *, line: int = 0,
               section: str = "", key: str = "", value: str = "") -> None:
        diagnostic = GeometrySourceDiagnostic(code, severity, self.path, line, section, key, value, message)
        if any(item.identity == diagnostic.identity for item in self.diagnostics):
            return
        self.diagnostics.append(diagnostic)
        channel = {"error": self.errors, "warning": self.warnings, "blocker": self.round_trip_blockers}[severity]
        channel.append(message)

    @property
    def volume_names(self) -> set[str]:
        return {volume.name for volume in self.volumes if volume.name}

    @property
    def round_trip_blocker(self) -> bool:
        return bool(self.round_trip_blockers)


@dataclass(frozen=True)
class GeometrySourceDiagnostic:
    code: str
    severity: str
    filename: str
    line: int
    section: str
    key: str
    value: str
    message: str

    @property
    def identity(self) -> tuple:
        # Display wording is deliberately excluded from source-fact identity.
        return (self.code, self.severity, str(Path(self.filename).resolve()), self.line,
                self.section.lower(), self.key.lower(), self.value)


def parse_geometry(path: str | Path, template_name: str | None = None) -> GeometrySummary:
    document = parse_ini_light(path)
    summary = GeometrySummary(path=document.path, raw_text=document.raw_text)
    for severity, messages in (("warning", document.warnings), ("error", document.errors)):
        for message in messages:
            summary.record("ini_syntax", severity, message, value=message)
    lower_text = document.raw_text.lower()
    summary.template_hint = (template_name or "").strip().lower() or _template_hint(lower_text)

    version_fields = _schema_version_fields(document.raw_text)
    if len(version_fields) > 1:
        summary.record("duplicate_version", "error", f"{summary.path}: duplicate [global]/version declaration",
                       line=version_fields[1][0], section="global", key="version")
    elif version_fields:
        line, section, key, value = version_fields[0]
        if value.strip() in {"1", "2"}:
            summary.schema_version = int(value.strip())
        else:
            summary.record("unsupported_version", "error",
                f"{summary.path}:{line} [{section}]/{key} = {value}: "
                "supported geometry versions are 1 and 2", line=line, section=section, key=key, value=value,
            )

    volume_by_name: dict[str, VolumeEntry] = {}
    boolean_sections: list[IniSection] = []

    for section in document.sections:
        lower_name = section.name.lower()
        if _is_boolean_section(section.name):
            boolean_sections.append(section)
            continue
        if lower_name == "world" or lower_name == "target" or lower_name.startswith("volume."):
            volume = _parse_volume(section)
            summary.volumes.append(volume)
            volume_by_name[volume.name] = volume
            if volume.material:
                summary.material_refs.add(volume.material)
            if volume.sensitive:
                summary.sensitive_volumes.add(volume.name)
            if volume.bias:
                summary.bias_volumes.add(volume.name)

    for section in boolean_sections:
        operation = _parse_boolean(section)
        summary.boolean_ops.append(operation)
        if operation.target_volume in volume_by_name:
            volume_by_name[operation.target_volume].boolean_ops.append(operation)
        if operation.forbidden_keys:
            summary.record("ignored_boolean_key", "warning",
                f"Boolean section [{operation.section}] contains unsupported keys: {', '.join(operation.forbidden_keys)}",
                line=operation.line_no, section=operation.section, value=",".join(operation.forbidden_keys),
            )

    if not summary.volumes and not summary.errors:
        summary.record("no_ordinary_volumes", "warning", "No ordinary volume sections were found.")
    _detect_round_trip_blockers(document.sections, summary)
    return summary


def _parse_volume(section: IniSection) -> VolumeEntry:
    values = {key.lower(): value for key, value in section.values.items()}
    name = values.get("name", "")
    lower_section = section.name.lower()
    if lower_section == "world":
        name = name or "world"
    elif lower_section == "target":
        name = name or "Target"
    elif lower_section.startswith("volume."):
        name = name or section.name.split(".", 1)[1]

    metadata_lines = [f"{key} = {value}" for key, value in section.values.items() if key.lower().startswith("metadata.")]
    shape_properties = {key: value for key, value in values.items() if key in SHAPE_PROPERTY_KEYS}
    preview_properties = {key: value for key, value in values.items() if key in PREVIEW_PROPERTY_KEYS}
    visual = {key: value for key, value in values.items() if key in VISUAL_KEYS}
    production_cuts = {key: value for key, value in values.items() if key in PRODUCTION_CUT_KEYS}
    return VolumeEntry(
        name=name,
        parent=values.get("parent", "world" if name != "world" else ""),
        shape=values.get("shape", ""),
        size=values.get("size", ""),
        parameters=values.get("parameters", ""),
        material=values.get("material", ""),
        position=values.get("position", ""),
        rotation=values.get("rotation", ""),
        sensitive=_parse_bool(values.get("sensitive", "false")),
        bias=_parse_bool(values.get("bias", "false")),
        region=values.get("region", values.get("regionname", "")),
        copy_no=values.get("copyno", values.get("copy_no", "")),
        metadata="\n".join(metadata_lines),
        shape_properties=shape_properties,
        preview_properties=preview_properties,
        visual=visual,
        production_cuts=production_cuts,
        section=section.name,
        line_no=section.line_no,
    )


def _parse_boolean(section: IniSection) -> BooleanOperationEntry:
    values = {key.lower(): value for key, value in section.values.items()}
    lower_name = section.name.lower()
    marker = ".boolean."
    marker_index = lower_name.find(marker)
    target = section.name[len("volume.") : marker_index] if marker_index >= len("volume.") else ""
    index_text = section.name[marker_index + len(marker) :] if marker_index >= 0 else ""
    try:
        index = int(index_text)
    except ValueError:
        index = -1
    forbidden = sorted(key for key in values if _is_forbidden_boolean_key(key))
    return BooleanOperationEntry(
        target_volume=target,
        index=index,
        operation=values.get("operation", ""),
        tool_shape=values.get("shape", values.get("tool_shape", "")),
        tool_size=values.get("size", ""),
        tool_parameters=values.get("parameters", ""),
        position=values.get("position", ""),
        rotation=values.get("rotation", ""),
        name=values.get("name", ""),
        section=section.name,
        line_no=section.line_no,
        forbidden_keys=forbidden,
    )


def _is_boolean_section(name: str) -> bool:
    lower = name.strip().lower()
    return lower.startswith("volume.") and ".boolean." in lower


def _is_forbidden_boolean_key(key: str) -> bool:
    lower = key.strip().lower()
    return lower in FORBIDDEN_BOOLEAN_KEYS or lower.startswith("cut.") or lower.startswith("vis.")


def _detect_round_trip_blockers(sections: list[IniSection], summary: GeometrySummary) -> None:
    mode = summary.template_hint
    layer_names: set[str] = set()
    if mode == "layered_device":
        for section in sections:
            if section.name.lower() == "layers":
                for key, value in section.values.items():
                    if key.lower() == "names":
                        layer_names.update(name.strip().lower() for name in value.split(",") if name.strip())
    simple_keys = {
        "world": {"size", "material"},
        "target": {"name", "shape", "size", "material", "position", "rotation", "sensitive", "bias", "region"},
    }
    layered_control = {"count", "names", "auto_stack", "axis", "gap", "z_start"}
    layered_volume = {"thickness", "xy", "material", "sensitive", "bias", "region", "copyno", "position", "rotation"}
    hierarchical_volume = {
        "name", "parent", "shape", "size", "parameters", "material", "position", "rotation",
        "sensitive", "bias", "region", "copyno",
    }
    boolean_keys = {"name", "operation", "shape", "size", "parameters", "position", "rotation"}

    seen_sections: set[str] = set()
    raw_lines = summary.raw_text.splitlines()

    for index, section in enumerate(sections):
        section_lower = section.name.lower()
        if section_lower in seen_sections:
            summary.record("duplicate_section", "blocker",
                f"{summary.path}:{section.line_no} [{section.name}]: duplicate section cannot be preserved by the Geometry Editor",
                line=section.line_no, section=section.name,
            )
        seen_sections.add(section_lower)
        if mode == "simple_box":
            recognized_section = section_lower in {"global", "world", "target", "visual.world", "visual.target"}
        elif mode == "layered_device":
            recognized_section = section_lower in {"global", "world", "layers"} or (
                section_lower.startswith("layer.") and section_lower[6:] in layer_names
            )
        elif mode in {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}:
            recognized_section = section_lower in {"global", "world"} or (
                section_lower.startswith("volume.") and len(section_lower) > 7
            )
        else:
            recognized_section = False
        if not recognized_section:
            summary.record("unknown_editor_section", "blocker",
                f"{summary.path}:{section.line_no} [{section.name}]: section is not represented by the Geometry Editor",
                line=section.line_no, section=section.name,
            )
            continue

        end_line = sections[index + 1].line_no if index + 1 < len(sections) else len(raw_lines) + 1
        seen_keys: set[str] = set()
        for line_no in range(section.line_no + 1, end_line):
            raw = raw_lines[line_no - 1].strip()
            if not raw or raw.startswith(("#", ";")) or "=" not in raw:
                continue
            key = raw.split("=", 1)[0].strip().lower()
            if key in seen_keys:
                summary.record("duplicate_key", "blocker",
                    f"{summary.path}:{line_no} [{section.name}]/{key}: duplicate key cannot be preserved by the Geometry Editor",
                    line=line_no, section=section.name, key=key,
                )
            seen_keys.add(key)
        for original_key, value in section.values.items():
            key = original_key.lower()
            line = section.key_lines.get(original_key, section.line_no)
            if section_lower == "global" and key == "version":
                continue
            representable = False
            legacy = False
            if mode == "simple_box":
                representable = section_lower in simple_keys and key in simple_keys[section_lower]
            elif mode == "layered_device":
                if section_lower == "world":
                    representable = key in {"size", "material"}
                elif section_lower == "layers":
                    representable = key in layered_control
                elif section_lower.startswith("layer.") and section_lower[6:] in layer_names:
                    representable = (key in layered_volume or key in VISUAL_KEYS
                                     or key in PRODUCTION_CUT_KEYS or key.startswith("metadata."))
            elif mode in {"hierarchical", "hierarchical_boolean", "boolean_hierarchical", "boolean"}:
                if _is_boolean_section(section.name):
                    representable = key in boolean_keys
                elif section_lower == "world" or section_lower.startswith("volume."):
                    representable = (key in hierarchical_volume or key.startswith("metadata.")
                                     or key in VISUAL_KEYS or key in PRODUCTION_CUT_KEYS
                                     or (key in TRD_PROPERTY_KEYS and
                                         next((value for name, value in section.values.items()
                                               if name.lower() == "shape"), "").strip().lower() == "trd"))

            if representable:
                if key.startswith("metadata.") and not key[len("metadata.") :].strip():
                    representable = False
                else:
                    continue

            if not key.startswith(("cut.", "vis.", "metadata.")) and key not in {
                "auto_stack", "position", "rotation", "placement", "dx1", "dx2", "dx3", "dx4",
                "dy1", "dy2", "dz", "theta", "phi", "alpha1", "alpha2", "shape", "copyno",
                "name", "material", "size", "parameters", "sensitive", "bias", "region", "parent",
                "operation", "count", "names", "axis", "gap", "z_start", "thickness", "xy",
            } and key not in PREVIEW_PROPERTY_KEYS:
                legacy = True

            message = (
                f"{summary.path}:{line} [{section.name}]/{original_key} = {value}: "
                "the current Geometry Editor cannot preserve this field without changing the source"
            )
            summary.record("unrepresentable_editor_field", "blocker", message,
                           line=line, section=section.name, key=original_key, value=value)
            if legacy:
                summary.legacy_metadata.append(message)
                summary.record("legacy_metadata", "warning",
                    f"{summary.path}:{line} [{section.name}]/{original_key} = {value}: legacy metadata is preserved; "
                    f"use metadata.{original_key} in a future migration",
                    line=line, section=section.name, key=original_key, value=value,
                )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "on"}


def _schema_version_fields(raw_text: str) -> list[tuple[int, str, str, str]]:
    fields: list[tuple[int, str, str, str]] = []
    section = ""
    for line_number, raw in enumerate(raw_text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and "]" in line:
            section = line[1 : line.index("]")].strip()
            continue
        if section.lower() != "global" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().lower() == "version":
            value = value.split(" #", 1)[0].split(" ;", 1)[0].strip()
            fields.append((line_number, section, key.strip(), value))
    return fields


def _template_hint(text: str) -> str:
    if "[volume." in text:
        return "hierarchical"
    if "layer" in text:
        return "layered_device"
    if "[target]" in text:
        return "simple_box"
    if "array" in text:
        return "array"
    if "shield" in text:
        return "shielding"
    return ""
