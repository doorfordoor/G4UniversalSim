from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from g4usim_gui.core.project import G4USimProject, project_to_dict
from g4usim_gui.editors.geometry_editor_model import EDITABLE_GEOMETRY_MODES, GeometryDocument, geometry_document_to_snapshot
from g4usim_gui.editors.material_editor_model import MaterialDocument, material_document_to_snapshot, validate_material_document
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
    physics_model_to_snapshot,
    scoring_model_to_snapshot,
    source_model_to_snapshot,
)
from g4usim_gui.models.package_model import GeometrySettings, PathSettings, RunPackage
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.parsers.geometry_parser import GeometrySummary, parse_geometry
from g4usim_gui.parsers.materials_parser import MaterialsSummary, parse_materials
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.validators.config_validator import build_config_summary_text
from g4usim_gui.writers.macro_writer import write_run_macro
from g4usim_gui.writers.main_ini_writer import write_main_ini
from g4usim_gui.writers.geometry_ini_writer import write_geometry_ini
from g4usim_gui.writers.materials_ini_writer import write_materials_ini
from g4usim_gui.writers.validation_report_writer import write_validation_report


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "gui_run"


def create_run_package(
    *,
    project: G4USimProject,
    paths: PathSettings,
    run: RunSettings,
    geometry: GeometrySettings,
    source: SourceSettings,
    physics: PhysicsSettings,
    scoring: ScoringSettings,
    material_document: MaterialDocument | None = None,
    geometry_document: GeometryDocument | None = None,
    source_model: SourceEditableModel | None = None,
    physics_model: PhysicsEditableModel | None = None,
    scoring_model: ScoringEditableModel | None = None,
) -> tuple[RunPackage, str]:
    report = validate_config_builder(
        paths=paths,
        run=run,
        geometry=geometry,
        source=source,
        physics=physics,
        scoring=scoring,
        material_document=material_document if material_document and material_document.is_dirty else None,
        geometry_document=geometry_document if geometry_document and geometry_document.is_dirty else None,
        source_model=source_model,
        physics_model=physics_model,
        scoring_model=scoring_model,
    )
    if not report.can_run:
        raise ValueError(report.to_text())

    package = _allocate_package(paths.runs_root, run.run_name or project.projectName)
    materials_source_mode, geometry_source_mode = _copy_or_generate_inputs(package, paths, geometry, material_document, geometry_document)
    materials_summary = parse_materials(package.materials_ini_path)
    geometry_summary = parse_geometry(package.geometry_ini_path)
    summary_text = (
        _package_paths_text(paths, package, materials_source_mode, geometry_source_mode)
        + "\n"
        + build_config_summary_text(materials_summary=materials_summary, geometry_summary=geometry_summary)
    )
    write_main_ini(
        package.main_ini_path,
        package=package,
        run=run,
        geometry=geometry,
        source=source,
        physics=physics,
        scoring=scoring,
        source_model=source_model,
        physics_model=physics_model,
        scoring_model=scoring_model,
    )
    write_run_macro(package.run_macro_path, run)
    write_validation_report(package.validation_report_path, report, summary_text)
    _write_snapshot(
        package.project_snapshot_path,
        project,
        paths,
        run,
        geometry,
        source,
        physics,
        scoring,
        package,
        materials_summary,
        geometry_summary,
        material_document,
        materials_source_mode,
        geometry_document,
        geometry_source_mode,
        source_model,
        physics_model,
        scoring_model,
    )
    return package, report.to_text() + ("\n" + summary_text if summary_text else "")


def _allocate_package(runs_root: str, run_name: str) -> RunPackage:
    root = Path(runs_root).expanduser()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{timestamp}_{safe_name(run_name)}"
    package_dir = root / base
    suffix = 1
    while package_dir.exists():
        package_dir = root / f"{base}_{suffix}"
        suffix += 1

    config_dir = package_dir / "config"
    macro_dir = package_dir / "macros"
    logs_dir = package_dir / "logs"
    output_dir = package_dir / "output"
    materials_dir = config_dir / "materials"
    geometry_dir = config_dir / "geometry"
    for directory in [materials_dir, geometry_dir, macro_dir, logs_dir, output_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return RunPackage(
        package_dir=str(package_dir.resolve()),
        config_dir=str(config_dir.resolve()),
        macro_dir=str(macro_dir.resolve()),
        logs_dir=str(logs_dir.resolve()),
        output_dir=str(output_dir.resolve()),
        main_ini_path=str((config_dir / "main.ini").resolve()),
        run_macro_path=str((macro_dir / "run.mac").resolve()),
        validation_report_path=str((package_dir / "validation_report.txt").resolve()),
        project_snapshot_path=str((package_dir / "project_snapshot.json").resolve()),
        materials_ini_path=str((materials_dir / "material.ini").resolve()),
        geometry_ini_path=str((geometry_dir / "geometry.ini").resolve()),
    )


def _copy_or_generate_inputs(
    package: RunPackage,
    paths: PathSettings,
    geometry: GeometrySettings,
    material_document: MaterialDocument | None,
    geometry_document: GeometryDocument | None,
) -> tuple[str, str]:
    if material_document and material_document.is_dirty:
        validate_material_document(material_document)
        if material_document.errors:
            raise ValueError("Materials Editor validation failed:\n" + "\n".join(material_document.errors))
        write_materials_ini(package.materials_ini_path, material_document)
        materials_source_mode = "generated by Materials Editor"
    else:
        shutil.copyfile(Path(paths.materials_config).expanduser(), package.materials_ini_path)
        materials_source_mode = "copied from source"
    if geometry.config_path:
        source_geometry = Path(geometry.config_path).expanduser()
    else:
        source_geometry = Path(paths.geometry_config).expanduser()
    if geometry_document and geometry_document.source_copy_mode:
        shutil.copyfile(source_geometry, package.geometry_ini_path)
        geometry_source_mode = "copied from source (Geometry Editor validation bypassed)"
    elif geometry_document and geometry_document.is_dirty and geometry_document.mode in EDITABLE_GEOMETRY_MODES:
        if geometry_document.source_errors:
            raise ValueError("Geometry source errors block editable package generation:\n" + "\n".join(geometry_document.source_errors))
        if geometry_document.round_trip_blockers:
            raise ValueError("Geometry round-trip blockers prevent editable package generation:\n" + "\n".join(geometry_document.round_trip_blockers))
        write_geometry_ini(package.geometry_ini_path, geometry_document)
        geometry_source_mode = "generated by Geometry Editor"
    else:
        shutil.copyfile(source_geometry, package.geometry_ini_path)
        geometry_source_mode = "copied from source"
    return materials_source_mode, geometry_source_mode


def _package_paths_text(paths: PathSettings, package: RunPackage, materials_source_mode: str, geometry_source_mode: str) -> str:
    return "\n".join(
        [
            "[selected input files]",
            f"materials = {paths.materials_config}",
            f"geometry = {paths.geometry_config}",
            "",
            "[copied files]",
            f"materials_source_mode = {materials_source_mode}",
            f"geometry_source_mode = {geometry_source_mode}",
            f"materials = {package.materials_ini_path}",
            f"geometry = {package.geometry_ini_path}",
            f"main_ini = {package.main_ini_path}",
            f"run_macro = {package.run_macro_path}",
            f"output = {package.output_dir}",
        ]
    )


def _write_snapshot(
    path: str,
    project: G4USimProject,
    paths: PathSettings,
    run: RunSettings,
    geometry: GeometrySettings,
    source: SourceSettings,
    physics: PhysicsSettings,
    scoring: ScoringSettings,
    package: RunPackage,
    materials_summary: MaterialsSummary,
    geometry_summary: GeometrySummary,
    material_document: MaterialDocument | None,
    materials_source_mode: str,
    geometry_document: GeometryDocument | None,
    geometry_source_mode: str,
    source_model: SourceEditableModel | None,
    physics_model: PhysicsEditableModel | None,
    scoring_model: ScoringEditableModel | None,
) -> None:
    data = project_to_dict(project)
    data["pathSettings"] = asdict(paths)
    data["runSettings"] = asdict(run)
    data["geometrySettings"] = asdict(geometry)
    data["sourceSettings"] = asdict(source)
    data["physicsSettings"] = asdict(physics)
    data["scoringSettings"] = asdict(scoring)
    data["runPackage"] = asdict(package)
    data["materialsSourceMode"] = materials_source_mode
    data["geometrySourceMode"] = geometry_source_mode
    if material_document:
        data["materialDocument"] = material_document_to_snapshot(material_document)
    if geometry_document:
        data["geometryDocument"] = geometry_document_to_snapshot(geometry_document)
    if source_model:
        data["sourceEditor"] = source_model_to_snapshot(source_model)
    if physics_model:
        data["physicsEditor"] = physics_model_to_snapshot(physics_model)
    if scoring_model:
        data["scoringEditor"] = scoring_model_to_snapshot(scoring_model)
    data["materialsSummary"] = {
        "path": materials_summary.path,
        "count": len(materials_summary.materials),
        "materials": [
            {"name": entry.name, "kind": entry.kind, "density": entry.density, "components": len(entry.components)}
            for entry in materials_summary.materials
        ],
        "warnings": materials_summary.warnings,
        "errors": materials_summary.errors,
    }
    data["geometrySummary"] = {
        "path": geometry_summary.path,
        "templateHint": geometry_summary.template_hint,
        "volumes": [
            {
                "name": volume.name,
                "parent": volume.parent,
                "shape": volume.shape,
                "material": volume.material,
                "sensitive": volume.sensitive,
                "bias": volume.bias,
                "booleanOps": len(volume.boolean_ops),
            }
            for volume in geometry_summary.volumes
        ],
        "materialRefs": sorted(geometry_summary.material_refs),
        "sensitiveVolumes": sorted(geometry_summary.sensitive_volumes),
        "biasVolumes": sorted(geometry_summary.bias_volumes),
        "booleanOps": [
            {
                "target": op.target_volume,
                "index": op.index,
                "operation": op.operation,
                "toolShape": op.tool_shape,
                "forbiddenKeys": op.forbidden_keys,
            }
            for op in geometry_summary.boolean_ops
        ],
        "warnings": geometry_summary.warnings,
        "errors": geometry_summary.errors,
    }
    target = Path(path)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
