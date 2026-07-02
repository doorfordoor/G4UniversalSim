from __future__ import annotations

from g4usim_gui.preview3d.scene_model import Bounds, PreviewVolume, Vec3


def volume_bounds(volume: PreviewVolume) -> Bounds | None:
    if not volume.size_mm or not volume.position_mm:
        return None
    sx, sy, sz = volume.size_mm
    px, py, pz = volume.position_mm
    return (px - sx / 2.0, px + sx / 2.0, py - sy / 2.0, py + sy / 2.0, pz - sz / 2.0, pz + sz / 2.0)


def combine_bounds(volumes: list[PreviewVolume]) -> Bounds | None:
    bounds = [item for item in (volume_bounds(volume) for volume in volumes) if item is not None]
    if not bounds:
        return None
    return (
        min(item[0] for item in bounds),
        max(item[1] for item in bounds),
        min(item[2] for item in bounds),
        max(item[3] for item in bounds),
        min(item[4] for item in bounds),
        max(item[5] for item in bounds),
    )


def scene_extent(bounds: Bounds | None) -> float:
    if bounds is None:
        return 10.0
    return max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4], 1.0)


def add_vec3(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale_vec3(a: Vec3, scale: float) -> Vec3:
    return (a[0] * scale, a[1] * scale, a[2] * scale)
