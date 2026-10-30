"""Captured source text must retain parser semantics after source replacement."""
from dataclasses import asdict
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.diagnostics import collect_diagnostics
from g4usim_gui.parsers.ini_light_parser import parse_ini_light, parse_ini_light_text
from g4usim_gui.parsers.materials_parser import parse_materials, parse_materials_text
from g4usim_gui.parsers.geometry_parser import parse_geometry, parse_geometry_text


def same_capture(before, after):
    assert asdict(before) == asdict(after)
    assert [item.to_dict() for item in collect_diagnostics(before)] == [
        item.to_dict() for item in collect_diagnostics(after)]
    assert after._f4_read_success is True


def main():
    with tempfile.TemporaryDirectory(prefix="f5-source-snapshot-") as folder:
        source = Path(folder) / "captured.ini"
        cases = (
            ("", "simple_box"),
            ("outside=4\n[material.A]\n= bad\nbroken\n", "hierarchical"),
            ("[NIST]\nmaterials = G4_Si, G4_AIR\n"
             "[isotope.C12]\nZ=6\nN=12\nA=12 g/mole\n"
             "[material.M]\nmode=mass_fraction\ndensity=2 g/cm3\n"
             "components=G4_Si:1\nmisspelled=1\n", "simple_box"),
            ("[global]\nversion=2\n[world]\nsize=100 100 100 mm\nmaterial=G4_AIR\n"
             "[volume.det]\nshape=box\nsize=1 1 1 mm\nmaterial=G4_Si\n"
             "metadata.note=retain\nvis.unknown=blocked\n[volume.det]\nshape=tubs\n", "hierarchical"),
            ("[global]\nversion=2\n[world]\nsize=10 10 10 cm\nmaterial=G4_AIR\n"
             "[layers]\nnames=a\nauto_stack=true\n[layer.a]\nmaterial=G4_Si\n"
             "thickness=1 mm\nmetadata.note=一层\n", "layered_device"),
        )
        for text, template in cases:
            source.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
            ini = parse_ini_light(source)
            materials = parse_materials(source)
            geometry = parse_geometry(source, template)
            captured = ini.raw_text
            assert captured == text
            source.write_text("[unrelated]\nchanged=1\n", encoding="utf-8")
            with patch.object(Path, "read_text", side_effect=AssertionError("Captured parser read disk")):
                same_capture(ini, parse_ini_light_text(captured, source_path=source))
                same_capture(materials, parse_materials_text(captured, source_path=source))
                same_capture(geometry, parse_geometry_text(captured, source_path=source, template_name=template))
            source.unlink()
            same_capture(geometry, parse_geometry_text(captured, source_path=source, template_name=template))
            missing = parse_ini_light(source)
            assert missing._f4_read_success is False and missing.errors
            assert collect_diagnostics(missing)[0].source.text_snapshot is None
        for parse in (parse_ini_light_text, parse_materials_text, parse_geometry_text):
            for value in (None, {}, 3):
                try:
                    parse(value, source_path=source)
                except TypeError:
                    rejected = True
                else:
                    rejected = False
                assert rejected
    print("F5 captured source parsers retain semantics, provenance and missing-read distinction")


if __name__ == "__main__":
    main()
