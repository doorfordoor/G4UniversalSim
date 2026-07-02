from __future__ import annotations

from dataclasses import dataclass, field


Vec3 = tuple[float, float, float]
Bounds = tuple[float, float, float, float, float, float]


@dataclass
class PreviewVolume:
    name: str = ""
    shape: str = "box"
    size_mm: Vec3 | None = None
    position_mm: Vec3 | None = None
    rotation_deg: Vec3 | None = None
    material: str = ""
    sensitive: bool = False
    bias: bool = False
    role: str = "ordinary"


@dataclass
class PreviewSource:
    particle: str = ""
    energy: str = ""
    position_mm: Vec3 | None = None
    direction: Vec3 | None = None
    mode: str = "unknown"


@dataclass
class PreviewScene:
    template: str = ""
    volumes: list[PreviewVolume] = field(default_factory=list)
    source: PreviewSource = field(default_factory=PreviewSource)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    bounds_mm: Bounds | None = None

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def summary_lines(self) -> list[str]:
        lines = [
            f"template: {self.template or '<unknown>'}",
            f"volumes: {len(self.volumes)}",
        ]
        for volume in self.volumes:
            flags = []
            if volume.sensitive:
                flags.append("sensitive")
            if volume.bias:
                flags.append("bias")
            flag_text = f" [{' '.join(flags)}]" if flags else ""
            lines.append(
                f"- {volume.name or '<unnamed>'}: role={volume.role}, shape={volume.shape}, "
                f"material={volume.material or '<none>'}, size_mm={volume.size_mm}, pos_mm={volume.position_mm}{flag_text}"
            )
        lines.extend(
            [
                "",
                "source:",
                f"- particle: {self.source.particle or '<none>'}",
                f"- energy: {self.source.energy or '<none>'}",
                f"- position_mm: {self.source.position_mm}",
                f"- direction: {self.source.direction}",
                f"- mode: {self.source.mode}",
            ]
        )
        if self.bounds_mm:
            lines.extend(["", f"bounds_mm: {self.bounds_mm}"])
        if self.errors:
            lines.extend(["", "errors:"])
            lines.extend(f"- {item}" for item in self.errors)
        if self.warnings:
            lines.extend(["", "warnings:"])
            lines.extend(f"- {item}" for item in self.warnings)
        return lines
