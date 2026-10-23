"""The editor sketch's solids and placements, computed as the backend does (roadmap G4).

No Qt or VTK: every volume becomes a polygon mesh (vertices in mm, faces of 3 or 4
vertex indices) in world coordinates, so the sketch can be compared with the mesh
Geant4 builds (``/AIHL/geometry/exportMesh``).

The rules follow the backend source:

* values: ``UnitParser::ParseDoubleWithUnit`` (a unitless value is in Geant4's internal
  units, mm or rad), ``ParseLength`` and ``ParseAngle`` (rotations), and the list
  splitting of ``GeometryUtils::SplitVectorText``;
* placement: ``G4PVPlacement(R, t)`` with ``R = rotateX, rotateY, rotateZ`` applied in
  that order (``VolumeBuilder::CreateRotation``). Geant4 treats R as the rotation of the
  mother frame, so a daughter point p is at ``R^-1 p + t`` in the mother;
* solids: the parameters of ``VolumeBuilder::Create*Solid`` (G4Tubs, G4Sphere, G4Orb,
  G4Cons, G4Trd, G4Trap, G4Ellipsoid, G4EllipticalTube, G4Torus, G4Para, G4Hype,
  G4Polycone, G4Polyhedra, G4TessellatedSolid from STL), including phi/theta segments.

What cannot be drawn raises ``SketchError`` with the reason, which the scene lists
instead of silently leaving the volume out.
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

Mesh = tuple[np.ndarray, list[tuple[int, ...]]]

# G4UnitDefinition values (internal units: mm, rad) for the units a geometry file uses
LENGTH_UNITS = {"nm": 1e-6, "um": 1e-3, "mum": 1e-3, "mm": 1.0, "cm": 10.0, "m": 1000.0, "km": 1.0e6,
                "fermi": 1e-12, "fm": 1e-12, "angstrom": 1e-7, "pc": 3.0856775807e19,
                "nanometer": 1e-6, "micrometer": 1e-3, "millimeter": 1.0, "centimeter": 10.0, "meter": 1000.0,
                "kilometer": 1.0e6}
ANGLE_UNITS = {"rad": 1.0, "mrad": 1e-3, "deg": math.pi / 180.0, "radian": 1.0, "milliradian": 1e-3,
               "degree": math.pi / 180.0}
# ParseLength/ParseAngle accept only these
STRICT_LENGTH = {"nm", "um", "mm", "cm", "m"}
STRICT_ANGLE = {"deg", "rad"}
SEGMENTS = 64          # per full turn
QUANTITY = re.compile(r"\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(?:\*\s*)?(\S*)\s*")


class SketchError(ValueError):
    """A volume the sketch cannot draw; the message says why."""


# --- values, as the backend parses them -----------------------------------------------
def quantity(text: str, units: dict[str, float] | None = None) -> float:
    """``ParseDoubleWithUnit`` (units=None: lengths and angles) or a typed parse."""
    match = QUANTITY.fullmatch(text or "")
    if not match:
        raise SketchError(f"cannot read the value {text!r}")
    value, unit = float(match.group(1)), match.group(2)
    if not unit:
        return value
    table = units if units is not None else {**LENGTH_UNITS, **ANGLE_UNITS}
    if unit not in table:
        raise SketchError(f"unknown unit {unit!r} in {text!r}")
    return value * table[unit]


def split_vector(text: str) -> list[str]:
    """``GeometryUtils::SplitVectorText``."""
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    tokens = text.split()
    if len(tokens) in (3, 5):
        return tokens
    if len(tokens) in (6, 10):
        return [f"{tokens[i]} {tokens[i + 1]}" for i in range(0, len(tokens), 2)]
    return tokens


def length_vec3(text: str) -> tuple[float, float, float]:
    parts = split_vector(text)
    if len(parts) != 3:
        raise SketchError(f"expected 3 lengths: {text!r}")
    units = {key: LENGTH_UNITS[key] for key in STRICT_LENGTH}
    return tuple(quantity(part, units) for part in parts)  # type: ignore[return-value]


def angle_vec3(text: str) -> tuple[float, float, float]:
    """Radians; a unitless angle is in radians, as in the backend."""
    parts = split_vector(text)
    if len(parts) != 3:
        raise SketchError(f"expected 3 angles: {text!r}")
    units = {key: ANGLE_UNITS[key] for key in STRICT_ANGLE}
    return tuple(quantity(part, units) for part in parts)  # type: ignore[return-value]


def parameter_list(text: str) -> list[float]:
    """``GeometryUtils::ParseParameterList`` with units."""
    text = (text or "").strip()
    if not text:
        return []
    if "," not in text and len(text.split()) == 2:
        return [quantity(text)]
    return [quantity(part) for part in split_vector(text)]


def length(text: str) -> float:
    return quantity(text, {key: LENGTH_UNITS[key] for key in STRICT_LENGTH})


def angle(text: str) -> float:
    return quantity(text, {key: ANGLE_UNITS[key] for key in STRICT_ANGLE})


# --- placements ---------------------------------------------------------------------
def _axis_rotation(axis: int, a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)
    if axis == 1:
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


@dataclass
class Placement:
    """Daughter -> mother: p_mother = rotation @ p + translation."""
    rotation: np.ndarray
    translation: np.ndarray

    @staticmethod
    def identity() -> "Placement":
        return Placement(np.eye(3), np.zeros(3))

    @staticmethod
    def from_g4(position_mm: tuple[float, float, float], rotation_rad: tuple[float, float, float]) -> "Placement":
        """G4PVPlacement(R, t), R = rotateX(rx) then rotateY(ry) then rotateZ(rz) = Rz Ry Rx; the solid turns by R^-1."""
        rx, ry, rz = rotation_rad
        frame = _axis_rotation(2, rz) @ _axis_rotation(1, ry) @ _axis_rotation(0, rx)
        return Placement(frame.T, np.asarray(position_mm, dtype=float))

    def then(self, inner: "Placement") -> "Placement":
        """This placement applied after the daughter's own (world <- mother <- daughter)."""
        return Placement(self.rotation @ inner.rotation, self.rotation @ inner.translation + self.translation)

    def apply(self, points: np.ndarray) -> np.ndarray:
        return points @ self.rotation.T + self.translation


# --- solids (local coordinates) -----------------------------------------------------
def box_mesh(hx: float, hy: float, hz: float) -> Mesh:
    return _hexahedron([(-hx, -hy, -hz), (hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz),
                        (-hx, -hy, hz), (hx, -hy, hz), (-hx, hy, hz), (hx, hy, hz)])


def _hexahedron(corners) -> Mesh:
    """Corners in G4Trap order: z-, then y-, x- first; faces as the backend's G4Trap."""
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return np.asarray(corners, dtype=float), faces


def revolve(profile: list[tuple[float, float]], loops: list[list[int]], caps: list[tuple[int, ...]],
            start_phi: float, delta_phi: float, segments: int | None = None, corner_scale: float = 1.0) -> Mesh:
    """Turn (r, z) profile loops about z from start_phi by delta_phi; caps close a partial turn."""
    full = delta_phi >= 2.0 * math.pi - 1e-9
    steps = segments or max(4, math.ceil(SEGMENTS * min(delta_phi, 2.0 * math.pi) / (2.0 * math.pi)))
    angles = [start_phi + delta_phi * j / steps for j in range(steps if full else steps + 1)]
    count = len(profile)
    vertices = np.array([(r * corner_scale * math.cos(a), r * corner_scale * math.sin(a), z)
                         for a in angles for r, z in profile], dtype=float)
    faces: list[tuple[int, ...]] = []
    for j in range(steps):
        a, b = j * count, ((j + 1) % len(angles)) * count
        for loop in loops:
            for k in range(len(loop)):
                p, q = loop[k], loop[(k + 1) % len(loop)]
                faces.append((a + p, a + q, b + q, b + p))
    if not full:
        last = (len(angles) - 1) * count
        for cap in caps:
            faces.append(tuple(reversed(cap)))
            faces.append(tuple(last + i for i in cap))
    return vertices, faces


def tubs_mesh(r_min: float, r_max: float, half_z: float, start_phi: float, delta_phi: float) -> Mesh:
    return cons_mesh(r_min, r_max, r_min, r_max, half_z, start_phi, delta_phi)


def cons_mesh(r_min1, r_max1, r_min2, r_max2, half_z, start_phi, delta_phi) -> Mesh:
    profile = [(r_min1, -half_z), (r_max1, -half_z), (r_max2, half_z), (r_min2, half_z)]
    return revolve(profile, [[0, 1, 2, 3]], [(0, 1, 2, 3)], start_phi, delta_phi)


def sphere_mesh(r_min, r_max, start_phi, delta_phi, start_theta, delta_theta) -> Mesh:
    end_theta = min(math.pi, start_theta + delta_theta)
    steps = max(2, math.ceil(SEGMENTS / 2 * (end_theta - start_theta) / math.pi))
    thetas = [start_theta + (end_theta - start_theta) * i / steps for i in range(steps + 1)]
    outer = [(r_max * math.sin(t), r_max * math.cos(t)) for t in thetas]
    inner = [(r_min * math.sin(t), r_min * math.cos(t)) for t in reversed(thetas)]
    profile = outer + inner
    n = len(thetas)
    caps = [(i, i + 1, 2 * n - 2 - i, 2 * n - 1 - i) for i in range(n - 1)]
    return revolve(profile, [list(range(2 * n))], caps, start_phi, delta_phi)


def polycone_mesh(start_phi, delta_phi, z: list[float], r_inner: list[float], r_outer: list[float],
                  sides: int = 0) -> Mesh:
    """G4Polycone, or with sides > 0 G4Polyhedra (its radii are to the side faces, not the corners)."""
    n = len(z)
    profile = [(r_outer[i], z[i]) for i in range(n)] + [(r_inner[i], z[i]) for i in reversed(range(n))]
    caps = [(i, i + 1, 2 * n - 2 - i, 2 * n - 1 - i) for i in range(n - 1)]
    scale = 1.0 / math.cos(min(delta_phi, 2.0 * math.pi) / sides / 2.0) if sides else 1.0
    return revolve(profile, [list(range(2 * n))], caps, start_phi, delta_phi, segments=sides or None,
                   corner_scale=scale)


def torus_mesh(r_min, r_max, r_tor, start_phi, delta_phi) -> Mesh:
    steps = SEGMENTS // 2
    circle = [2.0 * math.pi * i / steps for i in range(steps)]
    profile = [(r_tor + r_max * math.cos(a), r_max * math.sin(a)) for a in circle]
    loops = [list(range(steps))]
    caps: list[tuple[int, ...]] = []
    if r_min > 0.0:
        profile += [(r_tor + r_min * math.cos(a), r_min * math.sin(a)) for a in circle]
        loops.append(list(range(2 * steps - 1, steps - 1, -1)))
        caps = [(i, (i + 1) % steps, steps + (i + 1) % steps, steps + i) for i in range(steps)]
    else:
        profile.append((r_tor, 0.0))
        caps = [(i, (i + 1) % steps, steps, steps) for i in range(steps)]
    return revolve(profile, loops, caps, start_phi, delta_phi)


def hype_mesh(r_in, r_out, stereo_in, stereo_out, half_z) -> Mesh:
    steps = 16
    zs = [-half_z + 2.0 * half_z * i / steps for i in range(steps + 1)]
    outer = [(math.hypot(r_out, z * math.tan(stereo_out)), z) for z in zs]
    inner = [(math.hypot(r_in, z * math.tan(stereo_in)), z) for z in reversed(zs)]
    return revolve(outer + inner, [list(range(2 * len(zs)))], [], 0.0, 2.0 * math.pi)


def ellipsoid_mesh(ax, by, cz, z_bottom, z_top) -> Mesh:
    # G4Ellipsoid: both cuts 0 means no cut; cuts outside the solid are clamped to it
    if z_bottom == 0.0 and z_top == 0.0:
        z_bottom, z_top = -cz, cz
    z_bottom, z_top = max(z_bottom, -cz), min(z_top, cz)
    t_top, t_bottom = math.acos(z_top / cz), math.acos(z_bottom / cz)
    steps = max(2, math.ceil(SEGMENTS / 2 * (t_bottom - t_top) / math.pi))
    thetas = [t_top + (t_bottom - t_top) * i / steps for i in range(steps + 1)]
    profile = [(0.0, z_top)] + [(math.sin(t), cz * math.cos(t)) for t in thetas] + [(0.0, z_bottom)]
    vertices, faces = revolve(profile, [list(range(len(profile)))], [], 0.0, 2.0 * math.pi)
    vertices[:, 0] *= ax
    vertices[:, 1] *= by
    return vertices, faces


def eltube_mesh(dx, dy, dz) -> Mesh:
    vertices, faces = revolve([(0.0, -dz), (1.0, -dz), (1.0, dz), (0.0, dz)], [[0, 1, 2, 3]], [], 0.0, 2.0 * math.pi)
    vertices[:, 0] *= dx
    vertices[:, 1] *= dy
    return vertices, faces


def para_mesh(dx, dy, dz, alpha, theta, phi) -> Mesh:
    ta, tt = math.tan(alpha), math.tan(theta)
    corners = []
    for z in (-dz, dz):
        for y in (-dy, dy):
            for x in (-dx, dx):
                corners.append((x + y * ta + z * tt * math.cos(phi), y + z * tt * math.sin(phi), z))
    return _hexahedron(corners)


def trap_mesh(dz, theta, phi, dy1, dx1, dx2, alpha1, dy2, dx3, dx4, alpha2) -> Mesh:
    tc, ts = math.tan(theta) * math.cos(phi), math.tan(theta) * math.sin(phi)
    t1, t2 = math.tan(alpha1), math.tan(alpha2)
    corners = [
        (-dz * tc - dy1 * t1 - dx1, -dz * ts - dy1, -dz), (-dz * tc - dy1 * t1 + dx1, -dz * ts - dy1, -dz),
        (-dz * tc + dy1 * t1 - dx2, -dz * ts + dy1, -dz), (-dz * tc + dy1 * t1 + dx2, -dz * ts + dy1, -dz),
        (dz * tc - dy2 * t2 - dx3, dz * ts - dy2, dz), (dz * tc - dy2 * t2 + dx3, dz * ts - dy2, dz),
        (dz * tc + dy2 * t2 - dx4, dz * ts + dy2, dz), (dz * tc + dy2 * t2 + dx4, dz * ts + dy2, dz),
    ]
    return _hexahedron(corners)


def trd_mesh(dx1, dx2, dy1, dy2, dz) -> Mesh:
    return trap_mesh(dz, 0.0, 0.0, dy1, dx1, dx1, 0.0, dy2, dx2, dx2, 0.0)


def read_stl(path: Path, scale: float) -> Mesh:
    """ASCII or binary STL, scaled to mm (as ``StlReader``)."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SketchError(f"cannot read the STL file {path}: {error.strerror or error}") from error
    triangles: list[tuple[float, ...]] = []
    if len(data) >= 84 and 84 + 50 * struct.unpack_from("<I", data, 80)[0] == len(data):
        for i in range(struct.unpack_from("<I", data, 80)[0]):
            triangles.append(struct.unpack_from("<9f", data, 84 + 50 * i + 12))
    else:
        text = data.decode("utf-8", "replace")
        numbers = [float(c) for triple in re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text) for c in triple]
        if not numbers or len(numbers) % 9:
            raise SketchError(f"{path.name} is not an STL file the sketch can read")
        triangles = [tuple(numbers[i:i + 9]) for i in range(0, len(numbers), 9)]
    if not triangles:
        raise SketchError(f"{path.name} has no triangles")
    vertices = np.asarray(triangles, dtype=float).reshape(-1, 3) * scale
    return vertices, [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(triangles))]


def solid_mesh(shape: str, *, size: str = "", parameters: str = "", properties: dict[str, str] | None = None,
               base_dir: Path | None = None) -> Mesh:
    """Local mesh of one backend solid from its INI fields (raises SketchError with the reason)."""
    shape = shape.strip().lower() or "box"
    props = {key.lower(): value for key, value in (properties or {}).items()}
    p = parameter_list(parameters)

    def need(count: int, names: str) -> list[float]:
        if len(p) < count:
            raise SketchError(f"{shape} needs {count} parameters ({names}), got {len(p)}")
        return p

    def prop_length(key: str) -> float:
        if not props.get(key, "").strip():
            raise SketchError(f"{shape} needs {key}")
        return length(props[key])

    def prop_angle(key: str) -> float:
        if not props.get(key, "").strip():
            raise SketchError(f"{shape} needs {key}")
        return angle(props[key])

    if shape in {"box", "cube"}:
        sx, sy, sz = length_vec3(size)
        return box_mesh(sx / 2, sy / 2, sz / 2)
    if shape in {"tubs", "tube", "cylinder"}:
        if len(p) >= 5:
            return tubs_mesh(*p[:5])
        if size.strip():
            sx, _sy, sz = length_vec3(size)
            return tubs_mesh(0.0, sx / 2, sz / 2, 0.0, 2.0 * math.pi)
        need(5, "rMin, rMax, halfZ, startPhi, deltaPhi")
    if shape == "sphere":
        return sphere_mesh(*need(6, "rMin, rMax, startPhi, deltaPhi, startTheta, deltaTheta")[:6])
    if shape == "orb":
        radius = p[0] if p else length_vec3(size)[0] / 2
        return sphere_mesh(0.0, radius, 0.0, 2.0 * math.pi, 0.0, math.pi)
    if shape in {"cone", "cons"}:
        return cons_mesh(*need(7, "rMin1, rMax1, rMin2, rMax2, halfZ, startPhi, deltaPhi")[:7])
    if shape in {"trd", "trapezoid"}:
        return trd_mesh(*(prop_length(k) for k in ("dx1", "dx2", "dy1", "dy2", "dz")))
    if shape == "trap":
        return trap_mesh(prop_length("dz"), prop_angle("theta"), prop_angle("phi"), prop_length("dy1"),
                         prop_length("dx1"), prop_length("dx2"), prop_angle("alpha1"), prop_length("dy2"),
                         prop_length("dx3"), prop_length("dx4"), prop_angle("alpha2"))
    if shape == "ellipsoid":
        if len(p) not in (3, 5):
            raise SketchError(f"ellipsoid needs 3 or 5 parameters, got {len(p)}")
        return ellipsoid_mesh(p[0], p[1], p[2], p[3] if len(p) == 5 else 0.0, p[4] if len(p) == 5 else 0.0)
    if shape in {"eltube", "elliptical_tube"}:
        return eltube_mesh(*need(3, "dx, dy, dz")[:3])
    if shape == "torus":
        return torus_mesh(*need(5, "rMin, rMax, rTor, startPhi, deltaPhi")[:5])
    if shape in {"para", "parallelepiped"}:
        return para_mesh(*need(6, "dx, dy, dz, alpha, theta, phi")[:6])
    if shape == "hype":
        return hype_mesh(*need(5, "innerRadius, outerRadius, innerStereo, outerStereo, halfZ")[:5])
    if shape in {"polycone", "polyhedra"}:
        z = parameter_list(props.get("z_planes", ""))
        r_in, r_out = parameter_list(props.get("r_inner", "")), parameter_list(props.get("r_outer", ""))
        if len(z) < 2 or len(r_in) != len(z) or len(r_out) != len(z):
            raise SketchError(f"{shape} needs matching z_planes, r_inner and r_outer lists")
        if shape == "polyhedra":
            need(3, "startPhi, deltaPhi, numSide")
            return polycone_mesh(p[0], p[1], z, r_in, r_out, sides=int(p[2]))
        need(2, "startPhi, deltaPhi")
        return polycone_mesh(p[0], p[1], z, r_in, r_out)
    if shape in {"tessellated", "stl"}:
        file = props.get("file", "").strip()
        if not file:
            raise SketchError("tessellated needs file")
        path = Path(file)
        if not path.is_absolute():
            if base_dir is None:
                raise SketchError(f"the STL path {file} is relative to a geometry file the sketch does not know")
            path = base_dir / path
        return read_stl(path, length(f"1 {props.get('file_unit', 'mm').strip() or 'mm'}"))
    raise SketchError(f"shape {shape!r} is not a backend solid")


def mesh_bounds(vertices: np.ndarray) -> tuple[float, float, float, float, float, float]:
    low, high = vertices.min(axis=0), vertices.max(axis=0)
    return (float(low[0]), float(high[0]), float(low[1]), float(high[1]), float(low[2]), float(high[2]))
