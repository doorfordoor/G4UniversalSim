"""No QApplication/widgets/backend: real Windows alias and strict resource proof."""
from pathlib import Path
import copy
import ctypes
import hashlib
import json
import sys

ROOT = Path.cwd().resolve()
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "gui"), str(ROOT / "scripts")]
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.core.project_snapshot import _geometry_resources


def main():
    folder = (OUT / "long-resource-identity-fixture").resolve()
    folder.mkdir(exist_ok=True)
    buffer = ctypes.create_unicode_buffer(32768)
    assert ctypes.windll.kernel32.GetShortPathNameW(str(folder), buffer, len(buffer))
    alias = Path(buffer.value)
    assert alias != folder and alias.samefile(folder)
    mesh = folder / "mesh.stl"
    mesh.write_bytes(b"solid placeholder\nendsolid placeholder\n")
    content_sha = hashlib.sha256(mesh.read_bytes()).hexdigest()
    text = ("[world]\nshape=box\nsize=2 m,2 m,2 m\nmaterial=G4_AIR\n"
            "[volume.Mesh]\nparent=world\nshape=tessellated\nfile=mesh.stl\nfile_unit=mm\nmaterial=G4_AIR\n")
    results = []
    for spelling in (folder, alias):
        source = spelling / "geometry.ini"
        source.write_text(text, encoding="utf-8")
        summary = parse_geometry_text(text, source_path=source, template_name="hierarchical")
        doc = geometry_document_from_summary(summary, "hierarchical")
        generated = generate_geometry_ini_text(doc)
        old_assert = f'file = {spelling / "mesh.stl"}' in generated
        assert old_assert == (spelling == folder)
        # Proposed smoke correction: exact native writer spelling remains checked.
        assert f'file = {(spelling / "mesh.stl").resolve()}' in generated
        target = folder / "generated.ini"
        target.write_text(generated, encoding="utf-8")
        parsed = parse_geometry_text(generated, source_path=target, template_name="hierarchical")
        assert not parsed.round_trip_blockers
        restored = geometry_document_from_summary(parsed, "hierarchical")
        row = next(r for r in restored.volumes if r.shape == "tessellated")
        resource = Path(row.shape_properties["file"])
        assert resource.samefile(mesh)
        assert resource.resolve() == mesh.resolve()
        assert hashlib.sha256(resource.read_bytes()).hexdigest() == content_sha
        receipts = _geometry_resources(parsed, target, folder)
        assert len(receipts) == 1 and receipts[0].sha256 == content_sha
        assert Path(receipts[0].path).samefile(mesh)
        (OUT / ("generated-alias.ini" if spelling == alias else "generated-native.ini")).write_text(generated, encoding="utf-8")
        results.append({"folder_spelling": str(spelling), "old_text_assert": old_assert,
                        "generated_file": str(resource), "samefile": True,
                        "sha256": content_sha, "closure_receipt_sha256": receipts[0].sha256})
    # Original closure gates still reject a missing file or an existing outside file.
    hidden = folder / "mesh.stl.hidden"
    assert not hidden.exists()
    mesh.rename(hidden)
    try:
        try:
            _geometry_resources(parsed, target, folder)
        except ValueError as error:
            assert "resource is missing" in str(error)
        else:
            assert False, "Missing actual STL must be rejected"
    finally:
        hidden.rename(mesh)
    outside = OUT / "outside.stl"
    outside.write_bytes(mesh.read_bytes())
    escaped = copy.deepcopy(parsed)
    next(r for r in escaped.volumes if r.shape == "tessellated").shape_properties["file"] = str(outside)
    try:
        _geometry_resources(escaped, target, folder)
    except ValueError as error:
        assert "escapes through a symbolic link" in str(error)
    else:
        assert False, "Same bytes outside the accepted package must still be rejected"
    (OUT / "path-proof.json").write_text(json.dumps({"kind": "real Windows short-path reproduction; CI did not print actual path", "no_qapplication_or_backend": True, "results": results, "missing_resource_rejected": True, "outside_resource_rejected": True}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Windows native/short alias writer-parser-SHA identity and closure rejection: PASS")


if __name__ == "__main__":
    main()
