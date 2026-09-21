from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.parsers.ini_light_parser import IniSection, parse_ini_light


FORBIDDEN_BOOLEAN_KEYS = {"material", "sensitive", "bias", "region", "parent", "placement", "copyno"}


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
    section: str = ""
    line_no: int = 0
    boolean_ops: list[BooleanOperationEntry] = field(default_factory=list)


@dataclass
class GeometrySummary:
    path: str
    template_hint: str = ""
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

    @property
    def volume_names(self) -> set[str]:
        return {volume.name for volume in self.volumes if volume.name}

    @property
    def round_trip_blocker(self) -> bool:
        return bool(self.round_trip_blockers)


def parse_geometry(path: str | Path, template_name: str | None = None) -> GeometrySummary:
    document = parse_ini_light(path)
    summary = GeometrySummary(path=document.path, warnings=list(document.warnings), errors=list(document.errors), raw_text=document.raw_text)
    lower_text = document.raw_text.lower()
    summary.template_hint = (template_name or "").strip().lower() or _template_hint(lower_text)

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
            summary.warnings.append(
                f"Boolean section [{operation.section}] contains unsupported keys: {', '.join(operation.forbidden_keys)}"
            )

    if not summary.volumes and not summary.errors:
        summary.warnings.append("No ordinary volume sections were found.")
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
    simple_keys = {
        "world": {"size", "material"},
        "target": {"name", "shape", "size", "material", "position", "rotation", "sensitive", "bias", "region"},
    }
    layered_control = {"count", "names", "axis", "gap", "z_start"}
    layered_volume = {"thickness", "xy", "material", "sensitive", "bias", "region", "copyno"}
    hierarchical_volume = {
        "name", "parent", "shape", "size", "parameters", "material", "position", "rotation",
        "sensitive", "bias", "region", "copyno",
    }
    boolean_keys = {"name", "operation", "shape", "size", "parameters", "position", "rotation"}

    for section in sections:
        section_lower = section.name.lower()
        for original_key, value in section.values.items():
            key = original_key.lower()
            line = section.key_lines.get(original_key, section.line_no)
            representable = False
            legacy = False
            if mode == "simple_box":
                representable = section_lower in simple_keys and key in simple_keys[section_lower]
            elif mode == "layered_device":
                if section_lower == "world":
                    representable = key in {"size", "material"}
                elif section_lower == "layers":
                    representable = key in layered_control
                elif section_lower.startswith("layer."):
                    representable = key in layered_volume
            elif mode == "hierarchical":
                if _is_boolean_section(section.name):
                    representable = key in boolean_keys
                elif section_lower == "world" or section_lower.startswith("volume."):
                    representable = key in hierarchical_volume or key.startswith("metadata.")

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
            }:
                legacy = True

            message = (
                f"{summary.path}:{line} [{section.name}]/{original_key} = {value}: "
                "the current Geometry Editor cannot preserve this field without changing the source"
            )
            summary.round_trip_blockers.append(message)
            if legacy:
                summary.legacy_metadata.append(message)
                summary.warnings.append(
                    f"{summary.path}:{line} [{section.name}]/{original_key} = {value}: legacy metadata is preserved; "
                    f"use metadata.{original_key} in a future migration"
                )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes", "on"}


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
