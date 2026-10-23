"""Backend geometry meshes (roadmap A5).

The backend command ``/AIHL/geometry/exportMesh <file.json>`` writes the world
that Geant4 actually built: every physical-volume copy (including replica and
parameterised copies) as a polyhedron in world coordinates, schema
``g4usim_geometry_mesh_v1``. Unlike the editor preview this is the real
geometry, so it also shows solids, placements and boolean results the GUI
editors cannot represent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "g4usim_geometry_mesh_v1"


@dataclass
class BackendVolume:
    path: str
    name: str
    copy: int
    depth: int
    solid: str
    material: str
    sensitive: bool
    cubic_volume_mm3: float
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, ...]]
    logical: str = ""


@dataclass
class BackendMesh:
    source_file: str
    volumes: list[BackendVolume] = field(default_factory=list)

    @property
    def leaf_volumes(self) -> list[BackendVolume]:
        """Volumes without daughters (the parts a user normally wants to see)."""
        parents = {volume.path.rsplit("/", 1)[0] for volume in self.volumes}
        return [volume for volume in self.volumes if volume.path not in parents]

    def bounds_mm(self, include_world: bool = False) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        points = [p for v in self.volumes if include_world or v.depth > 0 for p in v.vertices]
        if not points:
            return None
        return (tuple(min(p[k] for p in points) for k in range(3)),  # type: ignore[return-value]
                tuple(max(p[k] for p in points) for k in range(3)))


def load_backend_mesh(path: str | Path) -> BackendMesh:
    """Read and validate an exportMesh JSON file. Raises ValueError on a bad file."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read backend geometry '{path}': {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("length_unit") != "mm":
        raise ValueError(f"'{path}' is not a {SCHEMA} file")
    mesh = BackendMesh(source_file=str(path))
    for item in data.get("volumes", []):
        vertices = [tuple(float(c) for c in vertex) for vertex in item["vertices"]]
        faces = [tuple(int(i) for i in face) for face in item["faces"]]
        if any(len(v) != 3 for v in vertices):
            raise ValueError(f"'{path}': volume {item.get('path')} has a vertex without 3 coordinates")
        if any(len(f) not in (3, 4) or min(f) < 0 or max(f) >= len(vertices) for f in faces):
            raise ValueError(f"'{path}': volume {item.get('path')} has an invalid face")
        mesh.volumes.append(BackendVolume(
            path=str(item["path"]), name=str(item["name"]), copy=int(item["copy"]), depth=int(item["depth"]),
            solid=str(item["solid"]), material=str(item["material"]), sensitive=bool(item["sensitive"]),
            cubic_volume_mm3=float(item["cubic_volume_mm3"]), vertices=vertices, faces=faces,
            logical=str(item.get("logical", "")),
        ))
    if len(mesh.volumes) != int(data.get("volume_count", -1)):
        raise ValueError(f"'{path}': volume_count does not match the volumes list")
    return mesh


def write_export_macro(directory: str | Path, json_path: str | Path) -> Path:
    """Macro that only initializes Geant4 and exports the built geometry (no events)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    macro = directory / "export_geometry.mac"
    macro.write_text(f"/run/initialize\n/AIHL/geometry/exportMesh {Path(json_path).as_posix()}\n", encoding="utf-8")
    return macro


def export_arguments(config_path: str, macro_path: str | Path, output_dir: str | Path) -> list[str]:
    """Backend arguments for the export run (the project's main INI, our macro, a scratch output)."""
    return ["--config", str(config_path), "--macro", str(macro_path), "--output", str(output_dir)]
