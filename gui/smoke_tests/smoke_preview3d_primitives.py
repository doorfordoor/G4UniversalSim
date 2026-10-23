from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow,
    GeometryDocument,
    HierarchicalVolumeRow,
    geometry_document_from_summary,
)
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.preview3d.scene_builder import build_preview_scene


def _scene_for(shape: str, parameters: str = "", size: str = ""):
    geometry = GeometryDocument(mode="hierarchical", is_dirty=True)
    geometry.volumes = [
        HierarchicalVolumeRow(name="world", parent="", shape="box", size="10 cm,10 cm,10 cm", material="G4_AIR"),
        HierarchicalVolumeRow(
            name="Primitive",
            parent="world",
            shape=shape,
            size=size,
            parameters=parameters,
            position="0 mm,0 mm,0 mm",
            rotation="0 deg,0 deg,0 deg",
            material="G4_Si",
        ),
    ]
    return build_preview_scene(geometry, SourceEditableModel())


def test_primitives_keep_shape() -> None:
    assert _scene_for("box", size="1 mm,2 mm,3 mm").volumes[1].shape == "box"
    tubs = _scene_for("tubs", parameters="0 mm, 2 mm, 5 mm, 0 deg, 360 deg")
    assert tubs.volumes[1].shape == "tubs"
    assert tubs.volumes[1].size_mm == (4.0, 4.0, 10.0)
    assert tubs.volumes[1].parameters_mm == (0.0, 2.0, 5.0)
    hollow_tubs = _scene_for("tubs", parameters="1 mm, 2 mm, 5 mm, 0 deg, 360 deg")
    assert hollow_tubs.volumes[1].parameters_mm == (1.0, 2.0, 5.0)
    sphere = _scene_for("sphere", parameters="0 mm, 3 mm, 0 deg, 360 deg, 0 deg, 180 deg")
    assert sphere.volumes[1].shape == "sphere"
    assert sphere.volumes[1].size_mm == (6.0, 6.0, 6.0)
    orb = _scene_for("orb", parameters="4 mm")
    assert orb.volumes[1].shape == "orb"
    assert orb.volumes[1].size_mm == (8.0, 8.0, 8.0)
    cone = _scene_for("cone", parameters="0 mm, 1 mm, 0 mm, 3 mm, 5 mm, 0 deg, 360 deg")
    assert cone.volumes[1].shape == "cone"
    assert cone.volumes[1].size_mm == (6.0, 6.0, 10.0)


def test_unsupported_fallback_warning() -> None:
    # a polycone without its planes cannot be drawn: listed with the reason, not silently missing
    scene = _scene_for("polycone", size="1 mm,1 mm,1 mm")
    assert scene.volumes[1].shape == "polycone"
    assert scene.volumes[1].vertices is None and "z_planes" in scene.volumes[1].not_drawn
    assert any("not drawn" in item for item in scene.warnings)
    # with its planes it is drawn (roadmap G4)
    geometry = GeometryDocument(mode="hierarchical", is_dirty=True)
    geometry.volumes = [
        HierarchicalVolumeRow(name="world", parent="", shape="box", size="10 cm,10 cm,10 cm", material="G4_AIR"),
        HierarchicalVolumeRow(name="Bottle", parent="world", shape="polycone", parameters="0 deg, 360 deg",
                              material="G4_Si", preview_properties={"z_planes": "-1 cm, 1 cm",
                                                                    "r_inner": "0 cm, 0 cm",
                                                                    "r_outer": "1 cm, 2 cm"}),
    ]
    bottle = build_preview_scene(geometry, SourceEditableModel()).volumes[1]
    assert bottle.vertices is not None and not bottle.not_drawn
    assert abs(bottle.vertices[:, 0].max() - 20.0) < 1e-9 and abs(bottle.vertices[:, 2].min() + 10.0) < 1e-9


def test_boolean_tool_tubs_not_box() -> None:
    geometry = GeometryDocument(mode="hierarchical_boolean", is_dirty=True)
    geometry.volumes = [
        HierarchicalVolumeRow(name="world", parent="", shape="box", size="10 cm,10 cm,10 cm", material="G4_AIR"),
        HierarchicalVolumeRow(name="Target", parent="world", shape="box", size="1 cm,1 cm,1 cm", material="G4_Si"),
    ]
    geometry.boolean_ops = [
        BooleanOperationRow(
            target_volume="Target",
            index=0,
            operation="subtraction",
            tool_shape="tubs",
            tool_parameters="0 mm, 1 mm, 5 mm, 0 deg, 360 deg",
            position="0 mm,0 mm,0 mm",
            rotation="0 deg,0 deg,0 deg",
        )
    ]
    scene = build_preview_scene(geometry, SourceEditableModel())
    tool = next(volume for volume in scene.volumes if volume.role == "boolean_tool")
    assert tool.shape == "tubs"
    assert tool.size_mm == (2.0, 2.0, 10.0)


def test_source_plane_and_cone_preview() -> None:
    circle = SourceEditableModel(
        position_mode="plane",
        source_shape="circle",
        radius="2 mm",
        angular_mode="fixed",
        position="0,0,-5 mm",
        direction="0,0,1",
        preview_ray_count=8,
    )
    scene = build_preview_scene(GeometryDocument(mode="simple_box"), circle)
    assert scene.source.position_mode == "plane"
    assert scene.source.source_shape == "circle"
    assert scene.source.radius_mm == 2.0
    assert scene.source.preview_rays

    rectangle = SourceEditableModel(
        position_mode="plane",
        source_shape="rectangle",
        halfx="1 mm",
        halfy="2 mm",
        angular_mode="fixed",
        preview_ray_count=6,
    )
    scene = build_preview_scene(GeometryDocument(mode="simple_box"), rectangle)
    assert scene.source.source_shape == "rectangle"
    assert len(scene.source.preview_rays) == 6

    cone = SourceEditableModel(
        position_mode="point",
        source_shape="point",
        angular_mode="cone",
        cone_half_angle="10 deg",
        preview_ray_count=9,
    )
    scene = build_preview_scene(GeometryDocument(mode="simple_box"), cone)
    assert scene.source.mode == "cone"
    assert len(scene.source.preview_rays) == 9


def test_bad_direction_warning() -> None:
    scene = build_preview_scene(GeometryDocument(mode="simple_box"), SourceEditableModel(direction="0,0,0"))
    assert scene.source.direction is None
    assert any("direction" in item.lower() for item in scene.warnings)


def _closed(faces) -> bool:
    """Every edge is shared by exactly two faces."""
    edges: dict[tuple[int, int], int] = {}
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            if a != b:
                key = (min(a, b), max(a, b))
                edges[key] = edges.get(key, 0) + 1
    return all(count == 2 for count in edges.values())


def test_hollow_tubs_mesh_is_closed() -> None:
    import math

    from g4usim_gui.preview3d.sketch_geometry import sphere_mesh, trd_mesh, tubs_mesh

    vertices, faces = tubs_mesh(2.0, 4.0, 5.0, 0.0, 2.0 * math.pi)
    assert {round(float(math.hypot(x, y)), 6) for x, y, _z in vertices} == {2.0, 4.0}
    assert _closed(faces)
    vertices, faces = tubs_mesh(2.0, 4.0, 5.0, math.radians(30), math.radians(90))   # a segment, with end caps
    assert _closed(faces)
    angles = {round(math.degrees(math.atan2(y, x)), 6) for x, y, _z in vertices}
    assert min(angles) == 30.0 and max(angles) == 120.0
    _vertices, faces = sphere_mesh(1.0, 3.0, 0.0, math.radians(120), math.radians(30), math.radians(60))
    assert _closed(faces)
    vertices, faces = trd_mesh(8.0, 10.0, 8.0, 10.0, 2.0)
    assert len(vertices) == 8 and len(faces) == 6 and _closed(faces)


def test_hierarchical_fixture_keeps_hollow_tubs_and_trd() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = parse_geometry(root / "test" / "geometry" / "hierarchical_test.ini", "hierarchical")
    document = geometry_document_from_summary(summary, "hierarchical")
    scene = build_preview_scene(document, SourceEditableModel())

    water = next(volume for volume in scene.volumes if volume.name == "water_moderator")
    assert water.parameters_mm == (21.0, 35.0, 50.0)
    stand = next(volume for volume in scene.volumes if volume.name == "iron_stand")
    assert stand.shape == "trd"
    assert stand.parameters_mm == (80.0, 100.0, 80.0, 100.0, 20.0)


if __name__ == "__main__":
    test_primitives_keep_shape()
    test_unsupported_fallback_warning()
    test_boolean_tool_tubs_not_box()
    test_source_plane_and_cone_preview()
    test_bad_direction_warning()
    test_hollow_tubs_mesh_is_closed()
    test_hierarchical_fixture_keeps_hollow_tubs_and_trd()
    print("smoke_preview3d_primitives: OK")
