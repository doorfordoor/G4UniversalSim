from __future__ import annotations

from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.preview3d.scene_model import PreviewSource
from g4usim_gui.preview3d.units import parse_direction, parse_vec3_to_mm


def build_preview_source(source: SourceEditableModel, warnings: list[str], errors: list[str]) -> PreviewSource:
    position = parse_vec3_to_mm(source.position)
    if position is None:
        warnings.append(f"Source position could not be parsed for preview: {source.position!r}")
    direction = parse_direction(source.direction)
    if direction is None:
        warnings.append(f"Source direction is invalid or zero for preview: {source.direction!r}")
    mode = source.angular_mode if source.angular_mode in {"beam", "fixed"} else "unknown"
    return PreviewSource(
        particle=source.particle,
        energy=source.energy,
        position_mm=position,
        direction=direction,
        mode=mode,
    )
