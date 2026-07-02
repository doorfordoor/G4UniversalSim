from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.parsers.ini_light_parser import IniSection, parse_ini_light


FORBIDDEN_BOOLEAN_KEYS = {"material", "sensitive", "bias", "region", "cuts", "visual", "cut.gamma", "cut.e-", "cut.e+", "cut.proton"}


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
    raw_text: str = ""

    @property
    def volume_names(self) -> set[str]:
        return {volume.name for volume in self.volumes if volume.name}


def parse_geometry(path: str | Path) -> GeometrySummary:
    document = parse_ini_light(path)
    summary = GeometrySummary(path=document.path, warnings=list(document.warnings), errors=list(document.errors), raw_text=document.raw_text)
    lower_text = document.raw_text.lower()
    summary.template_hint = _template_hint(lower_text)

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
        section=section.name,
        line_no=section.line_no,
    )


def _parse_boolean(section: IniSection) -> BooleanOperationEntry:
    values = {key.lower(): value for key, value in section.values.items()}
    parts = section.name.split(".")
    target = parts[1] if len(parts) >= 4 else ""
    index_text = parts[-1] if parts else "0"
    try:
        index = int(index_text)
    except ValueError:
        index = -1
    forbidden = sorted(key for key in values if key in FORBIDDEN_BOOLEAN_KEYS)
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
    parts = name.lower().split(".")
    return len(parts) >= 4 and parts[0] == "volume" and "boolean" in parts


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
