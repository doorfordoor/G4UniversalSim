"""E6 real-backend equivalence of source, migrated, and editable-writer inputs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core.config_migration import digest, publish_migration
from g4usim_gui.core.geometry_migration import plan_geometry_migration
from g4usim_gui.core.project import G4USimProject, load_project, save_project
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary, validate_geometry_document
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from test_geometry_config_diagnostics import SIMPLE, LAYERED, ARRAY, SHIELDING, HIERARCHICAL
from test_geometry_a5 import GDML_SENSDET, octahedron, write_binary_stl


def summary_values(path):
    return dict(line.split(" = ", 1) for line in path.read_text(encoding="utf-8").splitlines() if " = " in line)


def backend(executable, root, label, template, geometry, *, expected=True):
    output = root / label
    config = root / f"{label}.main.ini"
    mesh = root / f"{label}.mesh.json"
    macro = root / f"{label}.mac"
    config.write_text(f"""[run]
threads = 1
seed = 4242
verbose = 0
[output]
dir = {output.as_posix()}
format = csv
[materials]
file = {(ROOT / 'config/materials/material.ini').as_posix()}
[geometry]
template = {template}
config = {geometry.as_posix()}
[physics]
reference = FTFP_BERT
default_cut = 1 mm
[source]
particle = geantino
energy = 1 MeV
position_type = point
position = 0 mm, 0 mm, 0 mm
direction = 0,0,1
[scoring]
enabled = false
""", encoding="utf-8")
    macro.write_text(f"/run/initialize\n/AIHL/geometry/exportMesh {mesh.as_posix()}\n/run/beamOn 2\n", encoding="utf-8")
    result = subprocess.run([str(executable), "--config", str(config), "--macro", str(macro)],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    log = result.stdout + result.stderr
    if not expected:
        assert result.returncode != 0 and "created_geometry_object_count=0" in log, log[-5000:]
        return None
    assert result.returncode == 0, (label, log[-6000:])
    values = summary_values(output / "run_summary.txt")
    assert values["status"] == "completed", values
    assert values["planned_event_count"] == values["actual_completed_event_count"] == "2", values
    assert values["run_count"] == "1" and values["macro_execution_status"] == "completed", values
    data = json.loads(mesh.read_text(encoding="utf-8"))
    assert data["schema"] == "g4usim_geometry_mesh_v1" and data["volume_count"] > 0
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", default=os.environ.get("G4USIM_EXE"))
    parser.add_argument("--baseline", default=os.environ.get("G4USIM_BASELINE_EXE"))
    args = parser.parse_args()
    if not args.executable:
        raise ValueError("G4USIM_EXE or --executable is required")
    executable = Path(args.executable).resolve(strict=True)
    baseline = Path(args.baseline).resolve(strict=True) if args.baseline else executable
    with tempfile.TemporaryDirectory(prefix="g4usim-e6-backend-") as directory:
        work = Path(directory)
        sources = work / "sources"
        migrated = work / "relocated"
        sources.mkdir(); migrated.mkdir()
        fixtures = [
            ("simple", "simple", SIMPLE, True),
            ("layered", "layered", LAYERED, True),
            ("array", "array", ARRAY, False),
            ("shielding", "shielding", SHIELDING, False),
            ("hierarchical", "hierarchical", (ROOT / "scripts/fixtures/hierarchical_gui_roundtrip.ini").read_text(encoding="utf-8"), True),
            ("layered_fields", "layered_device", (ROOT / "scripts/fixtures/layered_gui_roundtrip.ini").read_text(encoding="utf-8"), True),
            ("legacy_metadata", "hierarchical", HIERARCHICAL + "LegacyTag = retained # kept\n", False),
        ]
        write_binary_stl(sources / "mesh.stl", octahedron(10))
        fixtures.append(("stl", "hierarchical", HIERARCHICAL.replace("shape = box\nsize = 1 cm, 1 cm, 1 cm", "shape = tessellated\nfile = mesh.stl"), False))
        (sources / "copies.csv").write_text("x_mm,y_mm,z_mm,rot_x_deg,rot_y_deg,rot_z_deg,material\n-20,0,0,0,0,0,G4_Si\n20,0,0,0,0,0,G4_WATER\n", encoding="utf-8")
        fixtures.append(("copies", "hierarchical", HIERARCHICAL + "placement = parameterised\ncopies_file = copies.csv\n", False))
        capabilities = subprocess.run([str(executable), "--capabilities"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert capabilities.returncode == 0
        has_gdml = next(item["runtime"] for item in json.loads(capabilities.stdout)["templates"] if item["id"] == "gdml")
        assert isinstance(has_gdml, bool)
        (sources / "source.gdml").write_text(GDML_SENSDET, encoding="utf-8")
        gdml_text = "[gdml]\nfile = source.gdml\nvalidate = false\n"
        if has_gdml:
            fixtures.append(("gdml", "gdml", gdml_text, False))
        else:
            (sources / "gdml-format.ini").write_text(gdml_text, encoding="utf-8")
            plan = plan_geometry_migration(sources / "gdml-format.ini", "gdml")
            assert b"version = 2" in plan.payload
        for label, template, text, editable in fixtures:
            source = sources / f"{label}.ini"
            source.write_text(text, encoding="utf-8")
            before = digest(source.read_bytes())
            mapping = {"[volume.Target]/LegacyTag": "metadata.LegacyTag"} if label == "legacy_metadata" else None
            plan = plan_geometry_migration(source, template, metadata_mapping=mapping)
            target = migrated / source.name
            publish_migration(plan, target)
            original_mesh = backend(baseline, work, label + "-source", template, source)
            migrated_mesh = backend(executable, work, label + "-migrated", template, target)
            assert original_mesh == migrated_mesh, label
            assert digest(source.read_bytes()) == before
            if editable:
                mode = {"simple": "simple_box", "layered": "layered_device"}.get(template, template)
                document = geometry_document_from_summary(parse_geometry(target, mode), mode)
                validate_geometry_document(document)
                assert not document.errors and not document.round_trip_blockers, (label, document.errors, document.round_trip_blockers)
                project_path = work / f"{label}.project.json"
                save_project(G4USimProject(geometryEditor=document), project_path)
                loaded = load_project(project_path)
                writer_target = migrated / f"{label}.writer.ini"
                writer_target.write_text(generate_geometry_ini_text(loaded.geometryEditor), encoding="utf-8")
                writer_mesh = backend(executable, work, label + "-writer", template, writer_target)
                assert writer_mesh == migrated_mesh, label
            print(f"{label}: source/migrated geometry and real 2-event runs agree" + ("; project/writer agrees" if editable else ""))
        invalid = sources / "duplicate.ini"
        invalid.write_text("[global]\nversion=2\n" + HIERARCHICAL + "Material=G4_Si\n", encoding="utf-8")
        backend(executable, work, "strict-duplicate", "hierarchical", invalid, expected=False)
    print("E6 real-backend migration equivalence passed (engineering checks, not a physics benchmark)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
