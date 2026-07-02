from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    materials = parse_materials(root / "config" / "materials" / "material.ini")
    assert materials.materials, "materials parser found no materials"
    material_doc = material_document_from_summary(materials)
    assert material_doc.rows, "material editable model has no rows"

    simple = parse_geometry(root / "config" / "geometry" / "simple_box.ini")
    assert simple.volumes, "simple_box has no volumes"
    assert "G4_Si" in simple.material_refs
    simple_doc = geometry_document_from_summary(simple)
    assert simple_doc.volumes, "geometry editable model has no volumes"

    boolean = parse_geometry(root / "config" / "geometry" / "boolean_mixed_csg.ini")
    assert boolean.boolean_ops, "boolean_mixed_csg has no boolean ops"
    assert all(".boolean." not in volume.section for volume in boolean.volumes)
    boolean_doc = geometry_document_from_summary(boolean)
    assert boolean_doc.boolean_ops, "geometry editable model has no boolean ops"

    print("smoke_parsers: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
