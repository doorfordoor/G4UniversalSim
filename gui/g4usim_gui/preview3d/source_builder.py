from __future__ import annotations

import math
import random

from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.preview3d.geometry_primitives import add_vec3, scale_vec3
from g4usim_gui.preview3d.scene_model import PreviewSource, Vec3
from g4usim_gui.preview3d.units import (
    parse_angle_deg,
    parse_direction,
    parse_length_to_mm,
    parse_vec3_to_mm,
    rotate_from_axis,
)


def build_preview_source(source: SourceEditableModel, warnings: list[str], errors: list[str]) -> PreviewSource:
    position = parse_vec3_to_mm(source.position)
    if position is None:
        warnings.append(f"Source position could not be parsed for preview: {source.position!r}")
    direction = parse_direction(source.direction)
    if direction is None:
        warnings.append(f"Source direction is invalid or zero for preview: {source.direction!r}")
    normal = parse_direction(source.normal)
    if normal is None and source.position_mode == "plane":
        warnings.append(f"Source plane normal is invalid or zero for preview: {source.normal!r}")

    mode = source.angular_mode.strip().lower() or "fixed"
    if mode == "beam":
        mode = "fixed"
    shape = source.source_shape.strip().lower() or ("point" if source.position_mode == "point" else "circle")
    radius = parse_length_to_mm(source.radius) if source.radius.strip() else None
    inner_radius = parse_length_to_mm(source.inner_radius) if source.inner_radius.strip() else None
    halfx = parse_length_to_mm(source.halfx) if source.halfx.strip() else None
    halfy = parse_length_to_mm(source.halfy) if source.halfy.strip() else None
    cone_half_angle = parse_angle_deg(source.cone_half_angle) if source.cone_half_angle.strip() else None

    preview = PreviewSource(
        particle=source.particle,
        energy=source.energy,
        position_mm=position,
        direction=direction,
        mode=mode,
        position_mode=source.position_mode.strip().lower() or source.position_type.strip().lower() or "point",
        source_shape=shape,
        radius_mm=radius,
        inner_radius_mm=inner_radius,
        halfx_mm=halfx,
        halfy_mm=halfy,
        normal=normal,
        cone_half_angle_deg=cone_half_angle,
    )
    if position and direction:
        preview.preview_rays = _build_rays(preview, source.preview_ray_count, source.random_seed_preview)
    return preview


def _build_rays(source: PreviewSource, count: int, seed: int) -> list[tuple[Vec3, Vec3]]:
    count = max(1, min(512, int(count)))
    length = 25.0
    starts = _sample_starts(source, count, seed)
    if source.mode == "fixed":
        direction = source.direction or (0.0, 0.0, 1.0)
        return [(start, add_vec3(start, scale_vec3(direction, length))) for start in starts]
    if source.mode == "isotropic":
        rng = random.Random(seed)
        return [(start, add_vec3(start, scale_vec3(_random_isotropic(rng), length))) for start in starts]
    if source.mode == "cone":
        rng = random.Random(seed)
        axis = source.direction or (0.0, 0.0, 1.0)
        max_angle = math.radians(source.cone_half_angle_deg if source.cone_half_angle_deg is not None else 5.0)
        rays = []
        for start in starts:
            angle = max_angle * math.sqrt(rng.random())
            azimuth = 2.0 * math.pi * rng.random()
            direction = rotate_from_axis(axis, angle, azimuth)
            rays.append((start, add_vec3(start, scale_vec3(direction, length))))
        return rays
    return []


def _sample_starts(source: PreviewSource, count: int, seed: int) -> list[Vec3]:
    center = source.position_mm or (0.0, 0.0, 0.0)
    if source.position_mode != "plane":
        if source.mode in {"cone", "isotropic"}:
            return [center] * max(1, min(count, 64))
        return [center]
    rng = random.Random(seed + 17)
    normal = source.normal or source.direction or (0.0, 0.0, 1.0)
    from g4usim_gui.preview3d.units import perpendicular_basis

    u, v = perpendicular_basis(normal)
    shape = source.source_shape
    starts = []
    sample_count = max(1, min(count, 64))
    if shape in {"circle", "annulus"} and source.radius_mm:
        inner = source.inner_radius_mm if shape == "annulus" and source.inner_radius_mm else 0.0
        for _ in range(sample_count):
            r = math.sqrt(rng.uniform(inner * inner, source.radius_mm * source.radius_mm))
            a = rng.uniform(0.0, 2.0 * math.pi)
            starts.append(add_vec3(center, add_vec3(scale_vec3(u, r * math.cos(a)), scale_vec3(v, r * math.sin(a)))))
        return starts
    if shape in {"rectangle", "square"} and source.halfx_mm:
        hx = source.halfx_mm
        hy = source.halfy_mm if source.source_shape == "rectangle" and source.halfy_mm else hx
        for _ in range(sample_count):
            starts.append(add_vec3(center, add_vec3(scale_vec3(u, rng.uniform(-hx, hx)), scale_vec3(v, rng.uniform(-hy, hy)))))
        return starts
    return [center]


def _random_isotropic(rng: random.Random) -> Vec3:
    z = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    r = math.sqrt(max(0.0, 1.0 - z * z))
    return (r * math.cos(phi), r * math.sin(phi), z)
