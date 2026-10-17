"""End-to-end hierarchical GUI geometry round-trip against the real backend."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary  # noqa: E402
from g4usim_gui.parsers.geometry_parser import parse_geometry  # noqa: E402
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text  # noqa: E402


def summary_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            result[key] = value
    return result


def volume_semantics(summary) -> list[tuple]:
    return [
        (row.name, row.parent, row.shape, row.size, row.parameters, row.material,
         row.position, row.rotation, row.sensitive, row.bias, row.region, row.copy_no,
         row.metadata, row.shape_properties, row.visual, row.production_cuts)
        for row in summary.volumes
    ]


def run_backend(executable: Path, temp: Path, label: str, macro_text: str, events: int) -> None:
    macro = temp / f"{label}.mac"
    macro.write_text(macro_text, encoding="utf-8")
    output = temp / label
    run = subprocess.run(
        [str(executable), "--macro", str(macro), "--output", str(output),
         "--threads", "1"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
    )
    log = run.stdout + run.stderr
    assert run.returncode == 0, f"{label} failed:\n{log[-6000:]}"
    values = summary_values(output / "run_summary.txt")
    assert (values["status"], values["macro_execution_status"], values["run_count"],
            values["planned_event_count"], values["actual_completed_event_count"]) == (
                "completed", "completed", "1", str(events), str(events)
            ), values
    assert values.get("geometry_config_warning_count") == "0", values
    assert "Overlap is detected" not in log, log[-6000:]


def main() -> int:
    executable = Path(os.environ.get(
        "G4USIM_EXE", str(ROOT / "build_vs2026" / "Release" / "G4UniversalSim.exe")
    ))
    if not executable.is_file():
        raise SystemExit(f"Executable not found: {executable}")
    source = ROOT / "scripts" / "fixtures" / "hierarchical_gui_roundtrip.ini"
    parsed = parse_geometry(source, "hierarchical")
    assert not parsed.errors and not parsed.round_trip_blockers, parsed.errors + parsed.round_trip_blockers
    document = geometry_document_from_summary(parsed, "hierarchical")

    with tempfile.TemporaryDirectory(prefix="g4usim-b3-geometry-") as directory:
        temp = Path(directory)
        generated = temp / "generated.ini"
        generated.write_text(generate_geometry_ini_text(document), encoding="utf-8")
        reparsed = parse_geometry(generated, "hierarchical")
        assert not reparsed.errors and not reparsed.round_trip_blockers
        assert volume_semantics(parsed) == volume_semantics(reparsed)

        for label, geometry in (("source", source), ("generated", generated)):
            run_backend(
                executable, temp, label,
                "/AIHL/geometry/setTemplate hierarchical\n"
                f"/AIHL/geometry/loadConfig {geometry.as_posix()}\n"
                "/AIHL/geometry/checkOverlaps true\n"
                "/AIHL/source/particle e-\n"
                "/AIHL/source/energy 1 MeV\n"
                "/AIHL/source/point 0 0 -2 cm\n"
                "/AIHL/source/direction 0 0 1\n"
                "/run/initialize\n"
                "/run/beamOn 2\n",
                2,
            )

        strict_source = temp / "strict_source.ini"
        strict_source.write_text("[global]\nversion = 2\n\n" + source.read_text(encoding="utf-8"), encoding="utf-8")
        strict_parsed = parse_geometry(strict_source, "hierarchical")
        assert strict_parsed.schema_version == 2 and not strict_parsed.round_trip_blockers
        strict_document = geometry_document_from_summary(strict_parsed, "hierarchical")
        strict_generated = temp / "strict_generated.ini"
        strict_generated.write_text(generate_geometry_ini_text(strict_document), encoding="utf-8")
        strict_reparsed = parse_geometry(strict_generated, "hierarchical")
        assert strict_reparsed.schema_version == 2 and not strict_reparsed.round_trip_blockers
        assert volume_semantics(strict_parsed) == volume_semantics(strict_reparsed)
        for label, geometry in (("strict_source", strict_source), ("strict_generated", strict_generated)):
            run_backend(
                executable, temp, label,
                "/AIHL/geometry/setTemplate hierarchical\n"
                f"/AIHL/geometry/loadConfig {geometry.as_posix()}\n"
                "/AIHL/source/particle e-\n"
                "/AIHL/source/energy 1 MeV\n"
                "/AIHL/source/point 0 0 -2 cm\n"
                "/AIHL/source/direction 0 0 1\n"
                "/run/initialize\n/run/beamOn 2\n",
                2,
            )

        complex_source = ROOT / "test" / "geometry" / "hierarchical_test.ini"
        complex_parsed = parse_geometry(complex_source, "hierarchical")
        assert not complex_parsed.errors and not complex_parsed.round_trip_blockers
        complex_document = geometry_document_from_summary(complex_parsed, "hierarchical")
        complex_generated = temp / "complex_generated.ini"
        complex_generated.write_text(generate_geometry_ini_text(complex_document), encoding="utf-8")
        complex_reparsed = parse_geometry(complex_generated, "hierarchical")
        assert not complex_reparsed.errors and not complex_reparsed.round_trip_blockers
        assert volume_semantics(complex_parsed) == volume_semantics(complex_reparsed)
        batch_macro = (ROOT / "test" / "macros" / "run_hierarchical_batch.mac").read_text(encoding="utf-8")
        for label, geometry in (("complex_source", complex_source), ("complex_generated", complex_generated)):
            macro_text = batch_macro.replace(
                "test/geometry/hierarchical_test.ini", geometry.as_posix()
            )
            run_backend(executable, temp, label, macro_text, 3)

        layered_source = ROOT / "scripts" / "fixtures" / "layered_gui_roundtrip.ini"
        layered_parsed = parse_geometry(layered_source, "layered_device")
        assert not layered_parsed.errors and not layered_parsed.round_trip_blockers
        layered_document = geometry_document_from_summary(layered_parsed, "layered_device")
        assert layered_document.layered_device.auto_stack is False
        layered_generated = temp / "layered_generated.ini"
        layered_generated.write_text(generate_geometry_ini_text(layered_document), encoding="utf-8")
        layered_reparsed = parse_geometry(layered_generated, "layered_device")
        assert not layered_reparsed.errors and not layered_reparsed.round_trip_blockers
        assert geometry_document_from_summary(layered_reparsed, "layered_device").layered_device == layered_document.layered_device
        for label, geometry in (("layered_source", layered_source), ("layered_generated", layered_generated)):
            run_backend(
                executable, temp, label,
                "/AIHL/geometry/setTemplate layered_device\n"
                f"/AIHL/geometry/loadConfig {geometry.as_posix()}\n"
                "/AIHL/geometry/checkOverlaps true\n"
                "/AIHL/source/particle e-\n"
                "/AIHL/source/energy 1 MeV\n"
                "/AIHL/source/point 0 0 -2 cm\n"
                "/AIHL/source/direction 0 0 1\n"
                "/run/initialize\n/run/beamOn 2\n",
                2,
            )

    print("M0-3B3 hierarchical and layered GUI-to-backend round-trip passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
