from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Vec3 = tuple[float, float, float]
Bounds = tuple[float, float, float, float, float, float]


@dataclass
class PreviewVolume:
    name: str = ""
    shape: str = "box"
    size_mm: Vec3 | None = None
    parameters_mm: tuple[float, ...] = field(default_factory=tuple)
    parameters_deg: tuple[float, ...] = field(default_factory=tuple)
    position_mm: Vec3 | None = None
    rotation_deg: Vec3 | None = None
    material: str = ""
    sensitive: bool = False
    bias: bool = False
    role: str = "ordinary"
    # the solid in world coordinates (roadmap G4: placements composed as in Geant4);
    # None when it cannot be drawn, with the reason in not_drawn
    vertices: Any = None
    faces: list[tuple[int, ...]] = field(default_factory=list)
    not_drawn: str = ""
    note: str = ""            # drawn, but not exactly (a boolean target shows its solid before the operations)


@dataclass
class SourceGlyph:
    """One mark of the source drawing (roadmap G5); lengths that depend on the scene size are the widget's.

    kind: "point" (a dot), "disc" (plane circle/annulus), "rectangle" (plane rectangle/square),
    "arrow" (a fixed direction), "isotropic" (rays in all directions, or a hemisphere about
    ``direction``), "cone" (directions inside ``half_angle_deg`` of ``direction``).
    """
    kind: str
    center: Vec3
    direction: Vec3 | None = None
    radius_mm: float = 0.0
    inner_radius_mm: float = 0.0
    halfx_mm: float = 0.0
    halfy_mm: float = 0.0
    half_angle_deg: float = 0.0
    length_mm: float | None = None      # fixed length (focused: to the focus point); None: scaled to the scene
    secondary: bool = False             # extra beam lines from the plane's edge, drawn fainter


@dataclass
class PreviewSource:
    particle: str = ""
    energy: str = ""
    position_mm: Vec3 | None = None
    direction: Vec3 | None = None
    mode: str = "fixed"
    position_mode: str = "point"
    source_shape: str = "point"
    radius_mm: float | None = None
    inner_radius_mm: float | None = None
    halfx_mm: float | None = None
    halfy_mm: float | None = None
    normal: Vec3 | None = None
    cone_half_angle_deg: float | None = None
    preview_rays: list[tuple[Vec3, Vec3]] = field(default_factory=list)
    glyphs: list[SourceGlyph] = field(default_factory=list)
    generated: bool = True              # False: a preview-only setting the GUI does not write to a run package
    description: tuple[str, dict] = ("", {})    # (template, values) for ui_format


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
            drawn = f", not drawn: {volume.not_drawn}" if volume.not_drawn else ""
            lines.append(
                f"- {volume.name or '<unnamed>'}: role={volume.role}, shape={volume.shape}, "
                f"material={volume.material or '<none>'}, size_mm={volume.size_mm}, params_mm={volume.parameters_mm}, "
                f"pos_mm={volume.position_mm}{flag_text}{drawn}"
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
                f"- position_mode: {self.source.position_mode}",
                f"- source_shape: {self.source.source_shape}",
                f"- preview_rays: {len(self.source.preview_rays)}",
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
