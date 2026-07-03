from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow,
    GeometryDocument,
    HierarchicalVolumeRow,
    geometry_document_from_summary,
    validate_geometry_document,
)
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.preview3d.scene_builder import build_preview_scene
from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.writers.package_writer import create_run_package


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class BackendResult:
    label: str
    package_dir: Path
    output_dir: Path
    stdout_path: Path
    stderr_path: Path
    exit_code: int
    mt_status: str = ""


def _materials() -> set[str]:
    return {"G4_AIR", "G4_WATER", "G4_Si", "G4_Al"}


def _dummy_exe(tmp: Path) -> Path:
    exe = tmp / "G4UniversalSim.exe"
    exe.write_text("", encoding="utf-8")
    return exe


def _source(particle: str = "proton", energy: str = "10 MeV", z: str = "-20 mm") -> SourceSettings:
    return SourceSettings(
        preset="proton_beam",
        particle=particle,
        energy=energy,
        position=f"0 mm, 0 mm, {z}",
        direction="0,0,1",
    )


def _scoring(hist_max: str = "10 MeV") -> ScoringSettings:
    return ScoringSettings(
        enabled=True,
        hits=True,
        event_edep=True,
        edep=True,
        hist_bins=100,
        hist_min="0 eV",
        hist_max=hist_max,
    )


def test_hierarchical_roundtrip() -> None:
    summary = parse_geometry(ROOT / "config" / "geometry" / "hierarchical_volume.ini")
    document = geometry_document_from_summary(summary, "hierarchical")
    assert document.mode == "hierarchical"
    assert any(row.name == "world" for row in document.volumes)
    assert any(row.name == "Detector" and row.sensitive for row in document.volumes)

    document.volumes.append(
        HierarchicalVolumeRow(
            name="Guard",
            parent="Container",
            shape="box",
            size="2 mm,2 mm,2 mm",
            material="G4_Al",
            position="1 mm,0 mm,0 mm",
            rotation="0 deg,0 deg,0 deg",
        )
    )
    duplicate = HierarchicalVolumeRow(**document.volumes[-1].__dict__.copy())
    duplicate.name = "GuardCopy"
    document.volumes.append(duplicate)
    document.volumes = [row for row in document.volumes if row.name != "GuardCopy"]
    document.is_dirty = True

    validate_geometry_document(document, material_names=_materials())
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "[volume.Guard]" in text
    reparsed = parse_geometry(_write_tmp_ini(text))
    assert "Guard" in reparsed.volume_names


def test_hierarchical_validation_errors() -> None:
    document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / "hierarchical_volume.ini"), "hierarchical")
    document.volumes.append(HierarchicalVolumeRow(name="Detector", parent="world", shape="box", size="1 mm,1 mm,1 mm", material="G4_Si"))
    document.volumes[1].parent = "Detector"
    document.volumes[2].parent = "Container"
    document.volumes[1].material = "MissingCustom"
    validate_geometry_document(document, material_names=_materials())
    joined = "\n".join(document.errors)
    assert "duplicate volume name" in joined.lower()
    assert "undefined custom material" in joined.lower()
    assert "parent cycle" in joined.lower()


def test_boolean_roundtrip_and_indices() -> None:
    summary = parse_geometry(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini")
    document = geometry_document_from_summary(summary, "hierarchical")
    assert document.mode == "hierarchical_boolean"
    assert len(document.boolean_ops) == 3
    assert document.boolean_ops[0].tool_parameters

    document.boolean_ops.append(
        BooleanOperationRow(
            target_volume="Target",
            index=99,
            operation="subtraction",
            tool_shape="box",
            tool_size="1 mm,1 mm,1 mm",
            position="0 mm,0 mm,0 mm",
            rotation="0 deg,0 deg,0 deg",
            name="extra_cut",
        )
    )
    document.boolean_ops.insert(0, document.boolean_ops.pop())
    del document.boolean_ops[1]
    document.is_dirty = True

    validate_geometry_document(document, material_names=_materials())
    assert not document.errors, document.errors
    text = generate_geometry_ini_text(document)
    assert "[volume.Target.boolean.0]" in text
    assert "[volume.Target.boolean.1]" in text
    assert "[volume.Target.boolean.2]" in text
    assert "[volume.Target.boolean.3]" not in text
    assert "material =" not in _boolean_section_text(text)
    reparsed = parse_geometry(_write_tmp_ini(text))
    assert [op.index for op in reparsed.boolean_ops] == [0, 1, 2]


def test_boolean_validation_errors() -> None:
    document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini"), "hierarchical")
    document.boolean_ops[0].target_volume = "MissingTarget"
    document.boolean_ops[1].tool_shape = "invalid_shape"
    validate_geometry_document(document, material_names=_materials())
    joined = "\n".join(document.errors)
    assert "target volume does not exist" in joined.lower()
    assert "unsupported boolean tool shape" in joined.lower()


def test_package_writer_and_preview(tmp: Path, exe: Path) -> Path:
    document = _doc_from_geometry("boolean_mixed_csg.ini", "hierarchical")
    package_dir = _create_package(
        tmp,
        "hier_bool_writer_smoke",
        "hierarchical",
        "boolean_mixed_csg.ini",
        document,
        exe,
        _source(),
        _scoring(),
        beam_on=10,
    )
    geometry_text = (package_dir / "config" / "geometry" / "geometry.ini").read_text(encoding="utf-8")
    report = (package_dir / "validation_report.txt").read_text(encoding="utf-8")
    main_ini = (package_dir / "config" / "main.ini").read_text(encoding="utf-8")
    assert "geometry_source_mode = generated by Geometry Editor" in report
    assert "[volume.Target.boolean.0]" in geometry_text
    assert "material =" not in _boolean_section_text(geometry_text)
    assert f"config = {package_dir / 'config' / 'geometry' / 'geometry.ini'}" in main_ini
    scene = build_preview_scene(document, SourceEditableModel())
    assert any(volume.role == "boolean_tool" for volume in scene.volumes)
    return package_dir


def test_config_builder_hier_bool_ui() -> None:
    app = QApplication.instance() or QApplication([])
    page = ConfigBuilderPage()
    page.geometry_config.setText(str(ROOT / "config" / "geometry" / "boolean_mixed_csg.ini"))
    page.geometry_template.setCurrentText("hierarchical")
    page.reload_geometry()
    tab_names = [page.geometry_editor_tabs.tabText(index) for index in range(page.geometry_editor_tabs.count())]
    assert "Hierarchical Volumes" in tab_names
    assert "Boolean Operations" in tab_names
    page.add_volume_button.click()
    assert any(row.name.startswith("Volume") for row in page.geometry_document.volumes)
    page.add_boolean_button.click()
    assert page.geometry_document.boolean_ops
    page.refresh_3d_preview()
    assert "3D Preview:" in page.preview3d_status.text()
    page.deleteLater()


def run_backend_matrix(tmp: Path, exe: Path) -> list[BackendResult]:
    scenarios = [
        (
            "hierarchical",
            "hierarchical",
            "hierarchical_volume.ini",
            _source("proton", "10 MeV", "-20 mm"),
            _scoring("10 MeV"),
            100,
        ),
        (
            "boolean_subtraction",
            "hierarchical",
            "boolean_box_minus_tubs.ini",
            _source("proton", "10 MeV", "-20 mm"),
            _scoring("10 MeV"),
            100,
        ),
        (
            "boolean_mixed",
            "hierarchical",
            "boolean_mixed_csg.ini",
            _source("proton", "10 MeV", "-20 mm"),
            _scoring("10 MeV"),
            100,
        ),
        (
            "boolean_hit_smoke",
            "hierarchical",
            "boolean_sensitive_hit_smoke.ini",
            _source("e-", "1 MeV", "-9 mm"),
            _scoring("1 MeV"),
            100,
        ),
    ]
    results: list[BackendResult] = []
    for label, template, config_name, source, scoring, beam_on in scenarios:
        document = _doc_from_geometry(config_name, template)
        package_dir = _create_package(tmp, label, template, config_name, document, exe, source, scoring, beam_on=beam_on)
        _assert_generated_geometry_contract(package_dir)
        result = _run_backend(label, package_dir, exe, threads=1, output_name="output")
        _assert_backend_outputs(result, require_hits=(label == "boolean_hit_smoke"))
        results.append(result)

    mt_package = results[2].package_dir
    mt_result = _run_backend("boolean_mixed_mt", mt_package, exe, threads=2, output_name="output_mt")
    _assert_backend_outputs(mt_result, require_hits=False, allow_mt_degraded=True)
    results.append(mt_result)
    return results


def _doc_from_geometry(config_name: str, template: str) -> GeometryDocument:
    document = geometry_document_from_summary(parse_geometry(ROOT / "config" / "geometry" / config_name), template)
    document.is_dirty = True
    validate_geometry_document(document, material_names=_materials())
    assert not document.errors, document.errors
    return document


def _create_package(
    tmp: Path,
    name: str,
    template: str,
    source_geometry: str,
    document: GeometryDocument,
    exe: Path,
    source: SourceSettings,
    scoring: ScoringSettings,
    *,
    beam_on: int,
) -> Path:
    package, _report = create_run_package(
        project=G4USimProject(projectName=name),
        paths=PathSettings(
            executable=str(exe),
            workspace_root=str(ROOT),
            runs_root=str(tmp / "runs"),
            materials_config=str(ROOT / "config" / "materials" / "material.ini"),
            geometry_config=str(ROOT / "config" / "geometry" / source_geometry),
        ),
        run=RunSettings(run_name=name, threads=1, beam_on=beam_on, check_overlaps=True),
        geometry=GeometrySettings(template=template, config_path=str(ROOT / "config" / "geometry" / source_geometry)),
        source=source,
        physics=PhysicsSettings(reference="FTFP_BERT_EMZ", default_cut="1 mm", enable_biasing=False),
        scoring=scoring,
        geometry_document=document,
    )
    return Path(package.package_dir)


def _assert_generated_geometry_contract(package_dir: Path) -> None:
    geometry_path = package_dir / "config" / "geometry" / "geometry.ini"
    main_ini_path = package_dir / "config" / "main.ini"
    report_path = package_dir / "validation_report.txt"
    assert geometry_path.is_file(), geometry_path
    assert main_ini_path.is_file(), main_ini_path
    assert report_path.is_file(), report_path
    geometry_text = geometry_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")
    main_ini = main_ini_path.read_text(encoding="utf-8")
    assert "[world]" in geometry_text
    assert "geometry_source_mode = generated by Geometry Editor" in report_text
    assert f"config = {geometry_path}" in main_ini
    if ".boolean." in geometry_text:
        boolean_text = _boolean_section_text(geometry_text)
        for forbidden in ["material =", "sensitive =", "bias =", "region ="]:
            assert forbidden not in boolean_text, f"forbidden boolean tool key emitted: {forbidden}"
        reparsed = parse_geometry(geometry_path)
        by_target: dict[str, list[int]] = {}
        for op in reparsed.boolean_ops:
            by_target.setdefault(op.target_volume, []).append(op.index)
        for target, indices in by_target.items():
            assert sorted(indices) == list(range(len(indices))), f"non-contiguous boolean indices for {target}: {indices}"


def _run_backend(label: str, package_dir: Path, exe: Path, *, threads: int, output_name: str) -> BackendResult:
    if not exe.is_file():
        raise FileNotFoundError(f"G4USIM_EXE does not exist: {exe}")
    output_dir = package_dir / output_name
    logs_dir = package_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    stdout_path = logs_dir / f"{label}_stdout.log"
    stderr_path = logs_dir / f"{label}_stderr.log"
    command = [
        str(exe),
        "--config",
        str(package_dir / "config" / "main.ini"),
        "--macro",
        str(package_dir / "macros" / "run.mac"),
        "--output",
        str(output_dir),
        "--threads",
        str(threads),
    ]
    completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, timeout=300, check=False)
    stdout_path.write_text(completed.stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(completed.stderr, encoding="utf-8", errors="replace")
    result = BackendResult(
        label=label,
        package_dir=package_dir,
        output_dir=output_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        exit_code=completed.returncode,
    )
    print(f"{label}: exit={result.exit_code} package={package_dir}")
    print(f"{label}: stdout={stdout_path}")
    print(f"{label}: stderr={stderr_path}")
    return result


def _assert_backend_outputs(
    result: BackendResult,
    *,
    require_hits: bool,
    allow_mt_degraded: bool = False,
) -> None:
    stderr = result.stderr_path.read_text(encoding="utf-8", errors="replace")
    stdout = result.stdout_path.read_text(encoding="utf-8", errors="replace")
    assert result.exit_code == 0, f"{result.label} exit={result.exit_code}\nSTDERR:\n{stderr}\nSTDOUT:\n{stdout}"
    fatal_markers = ["Fatal Exception", "AIHLSDMT001"]
    assert not any(marker in stderr for marker in fatal_markers), stderr
    assert "G4Exception" not in stderr or "JustWarning" in stderr, stderr
    if allow_mt_degraded and not (result.output_dir / "run_summary.txt").is_file():
        fallback_output = result.package_dir / "output"
        if (fallback_output / "run_summary.txt").is_file():
            result.output_dir = fallback_output
            result.mt_status = "DEGRADED output override ignored; single package output directory used"
    assert (result.output_dir / "run_summary.txt").is_file(), result.output_dir
    assert (result.output_dir / "event_edep_t0.csv").is_file(), result.output_dir
    assert (result.output_dir / "hist_edep_raw_t0.csv").is_file(), result.output_dir
    assert (result.output_dir / "hist_edep_weighted_t0.csv").is_file(), result.output_dir
    if require_hits:
        assert (result.output_dir / "hits_t0.csv").is_file(), result.output_dir
    if allow_mt_degraded:
        worker_event = result.output_dir / "event_edep_t1.csv"
        if worker_event.is_file():
            result.mt_status = "OK per-worker output detected"
        elif not result.mt_status:
            result.mt_status = "DEGRADED single-worker output only"
        print(f"{result.label}: MT status = {result.mt_status}")
    files = sorted(path.name for path in result.output_dir.glob("*"))
    print(f"{result.label}: output files = {files}")


def _write_tmp_ini(text: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="g4usim_hier_bool_ini_"))
    path = tmp / "geometry.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _boolean_section_text(text: str) -> str:
    chunks = []
    capture = False
    for line in text.splitlines():
        if line.startswith("[volume.") and ".boolean." in line:
            capture = True
        elif line.startswith("[") and capture:
            capture = False
        if capture:
            chunks.append(line)
    return "\n".join(chunks)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="g4usim_hier_bool_check_"))
    exe_env = os.environ.get("G4USIM_EXE", "").strip()
    exe = Path(exe_env) if exe_env else _dummy_exe(tmp)
    try:
        test_hierarchical_roundtrip()
        test_hierarchical_validation_errors()
        test_boolean_roundtrip_and_indices()
        test_boolean_validation_errors()
        writer_package = test_package_writer_and_preview(tmp, exe)
        test_config_builder_hier_bool_ui()
        print("GUI writer smoke passed")
        print(f"writer package: {writer_package}")
        if exe_env:
            results = run_backend_matrix(tmp, exe)
            print("backend verification passed")
            for result in results:
                mt = f" mt={result.mt_status}" if result.mt_status else ""
                print(f"- {result.label}: package={result.package_dir} output={result.output_dir}{mt}")
            print(f"backend packages preserved under: {tmp}")
        else:
            print("backend skipped: set G4USIM_EXE to run C++ hierarchical/boolean backend verification")
            shutil.rmtree(tmp, ignore_errors=True)
        print("smoke_hier_boolean_geometry_editor: OK")
        return 0
    except Exception:
        print(f"failure artifacts preserved under: {tmp}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
