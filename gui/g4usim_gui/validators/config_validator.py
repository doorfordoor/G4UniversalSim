from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.core.config_schema import check_value
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.capability_messages import capability_message
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.models.physics_model import PhysicsSettings
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.models.scoring_model import ScoringSettings
from g4usim_gui.models.source_model import SourceSettings
from g4usim_gui.editors.geometry_editor_model import (
    GeometryDocument,
    geometry_bias_count,
    geometry_material_refs,
    geometry_sensitive_count,
    validate_geometry_document,
)
from g4usim_gui.editors.material_editor_model import MaterialDocument, validate_material_document
from g4usim_gui.editors.source_physics_scoring_model import (
    PhysicsEditableModel,
    ScoringEditableModel,
    SourceEditableModel,
    validate_physics_model,
    validate_scoring_model,
    validate_source_model,
)
from g4usim_gui.parsers.geometry_parser import GeometrySummary, parse_geometry
from g4usim_gui.parsers.materials_parser import MaterialsSummary, material_reference_status, parse_materials


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def can_run(self) -> bool:
        return not self.errors

    def to_text(self) -> str:
        lines = [f"can_run = {str(self.can_run).lower()}", "", "[errors]"]
        lines.extend(self.errors or ["<none>"])
        lines.extend(["", "[warnings]"])
        lines.extend(self.warnings or ["<none>"])
        lines.extend(["", "[info]"])
        lines.extend(self.info or ["<none>"])
        return "\n".join(lines)


def _has_three_components(value: str) -> bool:
    tokens = [token for token in re.split(r"[,\s]+", value.strip()) if token]
    return len(tokens) >= 3


def _direction_is_nonzero(value: str) -> bool:
    tokens = [token for token in re.split(r"[,\s]+", value.strip()) if token]
    try:
        numeric = [float(token) for token in tokens[:3]]
    except ValueError:
        return True
    return any(abs(item) > 0 for item in numeric)


def _looks_like_value_with_unit(value: str) -> bool:
    return bool(re.search(r"\d", value)) and bool(re.search(r"[A-Za-z]", value))


def validate_config_builder(
    *,
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
) -> ValidationReport:
    report = ValidationReport()
    materials_summary: MaterialsSummary | None = None
    geometry_summary: GeometrySummary | None = None

    if not paths.executable:
        report.errors.append("Executable path is required.")
    elif not Path(paths.executable).expanduser().is_file():
        report.errors.append(f"Executable does not exist: {paths.executable}")
    elif "G4UniversalSim" not in Path(paths.executable).name:
        report.warnings.append("Executable file name does not contain G4UniversalSim.")

    if paths.workspace_root and not Path(paths.workspace_root).expanduser().is_dir():
        report.errors.append(f"Workspace root does not exist: {paths.workspace_root}")

    if not paths.runs_root:
        report.errors.append("Runs root is required.")
    else:
        runs_root = Path(paths.runs_root).expanduser()
        parent = runs_root if runs_root.exists() else runs_root.parent
        if not parent.exists():
            report.errors.append(f"Runs root parent does not exist: {paths.runs_root}")

    if not paths.materials_config:
        report.errors.append("Materials config is required.")
    elif not Path(paths.materials_config).expanduser().is_file():
        report.errors.append(f"Materials config does not exist: {paths.materials_config}")
    else:
        materials_summary = parse_materials(paths.materials_config)
        material_editor_covers_source = bool(
            material_document and _editor_source_matches(material_document, materials_summary)
        )
        if material_document and material_document.source_path and not material_editor_covers_source:
            report.errors.append(ui_text("Materials source changed since the editor was loaded; reload materials before generating a package."))
        # MaterialDocument retains source errors, but its semantic validator
        # rebuilds warnings; keep parser warnings from the current source.
        report.warnings.extend(f"Materials: {item}" for item in materials_summary.warnings)
        if not material_editor_covers_source:
            report.errors.extend(f"Materials: {item}" for item in materials_summary.errors)
        _validate_material_text(Path(paths.materials_config).expanduser(), report)

    use_edited_geometry = bool(
        geometry_document
        and geometry_document.is_dirty
        and geometry_document.mode != "preview_only"
        and not geometry_document.source_copy_mode
    )
    if (
        geometry_document
        and not use_edited_geometry
        and geometry_document.round_trip_blockers
        and not geometry_document.source_copy_mode
    ):
        report.errors.extend(
            f"Geometry round-trip blocker: {item}" for item in geometry_document.round_trip_blockers
        )

    if not geometry.template:
        report.errors.append("Geometry template is required.")

    if not geometry.config_path:
        report.errors.append("Geometry config is required.")
    elif not Path(geometry.config_path).expanduser().is_file():
        report.errors.append(f"Geometry config does not exist: {geometry.config_path}")
    else:
        geometry_summary = parse_geometry(geometry.config_path, geometry.template)
        geometry_editor_covers_source = bool(
            use_edited_geometry and geometry_document
            and _editor_source_matches(geometry_document, geometry_summary)
        )
        if use_edited_geometry and geometry_document and geometry_document.source_path and not geometry_editor_covers_source:
            report.errors.append(ui_text("Geometry source changed since the editor was loaded; reload geometry before generating a package."))
        if not geometry_editor_covers_source:
            report.warnings.extend(f"Geometry: {item}" for item in geometry_summary.warnings)
            report.errors.extend(f"Geometry: {item}" for item in geometry_summary.errors)
        _validate_geometry_text(Path(geometry.config_path).expanduser(), report)
        _validate_template_consistency(geometry.template, geometry_summary, report)

    # [run] fields the package writes, checked as the backend reads them (configuration schema, E2)
    if run.threads <= 0:
        report.errors.append("Threads must be a positive integer.")
    for key, value in (("threads", run.threads), ("seed", run.seed), ("name", run.run_name)):
        problem = check_value("run", key, str(value)) if value is not None else None
        if problem and not (key == "threads" and run.threads <= 0):
            report.errors.append(problem)
    if run.beam_on < 0:
        report.errors.append("BeamOn must be >= 0.")
    if not run.run_name.strip():
        report.info.append("Run name is empty; package writer will use gui_run.")

    source_model = source_model or SourceEditableModel.from_settings(source)
    physics_model = physics_model or PhysicsEditableModel.from_settings(physics)
    scoring_model = scoring_model or ScoringEditableModel.from_settings(scoring)
    validate_source_model(source_model)
    validate_physics_model(physics_model)
    validate_scoring_model(scoring_model)
    report.errors.extend(f"Source: {item}" for item in source_model.errors)
    report.warnings.extend(f"Source: {item}" for item in source_model.warnings)
    report.errors.extend(f"Physics: {item}" for item in physics_model.errors)
    report.warnings.extend(f"Physics: {item}" for item in physics_model.warnings)

    if use_edited_geometry and geometry_document:
        material_names = _material_name_set(material_document, materials_summary)
        validate_geometry_document(
            geometry_document,
            material_names=material_names,
            scoring_hits_enabled=scoring_model.hits,
            physics_biasing_enabled=physics_model.enable_biasing_physics,
        )
        report.errors.extend(f"Geometry Editor: {item}" for item in geometry_document.errors)
        report.warnings.extend(f"Geometry Editor: {item}" for item in geometry_document.warnings)
        if material_document:
            validate_material_document(material_document, geometry_material_refs=geometry_material_refs(geometry_document))
            report.errors.extend(f"Materials Editor: {item}" for item in material_document.errors)
            report.warnings.extend(f"Materials Editor: {item}" for item in material_document.warnings)
        _add_edited_geometry_summary_info(geometry_document, report)
    elif geometry_document and geometry_document.source_copy_mode:
        report.warnings.append(
            "Geometry Editor: original source copy mode is active; blocked fields are preserved but not certified by editor validation."
        )
    elif geometry_summary and material_document:
        validate_material_document(material_document, geometry_material_refs=geometry_summary.material_refs)
        report.errors.extend(f"Materials Editor: {item}" for item in material_document.errors)
        report.warnings.extend(f"Materials Editor: {item}" for item in material_document.warnings)
        _add_edited_material_summary_info(material_document, geometry_summary, report)
    elif materials_summary and geometry_summary:
        _validate_material_refs(materials_summary, geometry_summary, report)
        _add_summary_info(materials_summary, geometry_summary, report)

    report.errors.extend(f"Scoring: {item}" for item in scoring_model.errors)
    report.warnings.extend(f"Scoring: {item}" for item in scoring_model.warnings)
    _add_editor_summary_info(source_model, physics_model, scoring_model, report)

    if not report.errors:
        report.info.append("Validation passed.")
    return report


def _editor_source_matches(document: MaterialDocument | GeometryDocument,
                           summary: MaterialsSummary | GeometrySummary) -> bool:
    return bool(
        document.source_path
        and Path(document.source_path).expanduser().resolve() == Path(summary.path).expanduser().resolve()
        and document.raw_source_text == summary.raw_text
    )


def build_config_summary_text(
    *,
    materials_summary: MaterialsSummary | None,
    geometry_summary: GeometrySummary | None,
) -> str:
    lines: list[str] = []
    if materials_summary:
        lines.extend(["", "[materials summary]", f"path = {materials_summary.path}", f"count = {len(materials_summary.materials)}"])
        for entry in materials_summary.materials:
            lines.append(
                f"- {entry.name} kind={entry.kind} density={entry.density or '<none>'} components={len(entry.components)} section=[{entry.section}]"
            )
    if geometry_summary:
        lines.extend(["", "[geometry summary]", f"path = {geometry_summary.path}", f"template_hint = {geometry_summary.template_hint or '<unknown>'}", f"volumes = {len(geometry_summary.volumes)}"])
        for volume in geometry_summary.volumes:
            flags = []
            if volume.sensitive:
                flags.append("sensitive")
            if volume.bias:
                flags.append("bias")
            lines.append(
                f"- {volume.name} parent={volume.parent or '<none>'} shape={volume.shape or '<none>'} material={volume.material or '<none>'} boolean_ops={len(volume.boolean_ops)} {' '.join(flags)}"
            )
        lines.extend(["", "Sensitive volumes:"])
        if geometry_summary.sensitive_volumes:
            lines.extend(f"- {name}" for name in sorted(geometry_summary.sensitive_volumes))
        else:
            lines.append("- <none>")
        lines.extend(["", "Bias volumes:"])
        if geometry_summary.bias_volumes:
            lines.extend(f"- {name}" for name in sorted(geometry_summary.bias_volumes))
        else:
            lines.append("- <none>")
        lines.extend(["", "Boolean operations:"])
        if geometry_summary.boolean_ops:
            for op in geometry_summary.boolean_ops:
                lines.append(f"- {op.target_volume}[{op.index}] {op.operation or '<none>'} {op.tool_shape or '<none>'}")
        else:
            lines.append("- <none>")
    return "\n".join(lines)


def _validate_geometry_text(path: Path, report: ValidationReport) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    if re.search(r"(?im)^\s*shape\s*=\s*(tessellated|stl)\s*(?:#.*)?$", text):
        report.warnings.append("Geometry uses shape = tessellated (STL, backend-supported); the GUI geometry "
                               "editors cannot edit it.")
    if re.search(r"(?im)^\s*\[gdml\]\s*(?:#.*)?$", text):
        message = capability_message("geometry.gdml.external")
        if message not in report.warnings:
            report.warnings.append(message)
    unsupported_placements = sorted(set(re.findall(
        r"(?im)^\s*placement\s*=\s*(assembly)\s*(?:#.*)?$",
        text,
    )))
    for placement in unsupported_placements:
        report.errors.append(capability_message("geometry.placement.unsupported", placement=placement))
    # Roadmap A5: the backend builds replica/parameterised placement from a
    # hand-written geometry INI; the GUI editors cannot edit them.
    if re.search(r"(?im)^\s*placement\s*=\s*(replica|parameteri[sz]ed)\s*(?:#.*)?$", text):
        report.warnings.append("Geometry uses placement=replica/parameterised (backend-supported); "
                               "the GUI geometry editors cannot edit these volumes.")
    if "let" in lower or "dose" in lower or "fluence" in lower:
        report.warnings.append("Geometry config mentions LET/Dose/Fluence; those are not edited by this GUI MVP.")
    if "[volume." in lower and ".boolean." in lower:
        report.info.append("Boolean geometry sections detected and allowed.")
        for section_match in re.finditer(r"(?ims)^\s*\[([^\]]*boolean[^\]]*)\]\s*(.*?)(?=^\s*\[|\Z)", text):
            section_name = section_match.group(1)
            body = section_match.group(2).lower()
            for key in ["material", "sensitive", "bias", "region", "cuts", "production"]:
                if re.search(rf"^\s*{re.escape(key)}\s*=", body, re.MULTILINE):
                    report.warnings.append(
                        f"Boolean section [{section_name}] contains '{key}', which may be ignored by the boolean tool."
                    )


def _validate_material_text(path: Path, report: ValidationReport) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    unsupported = sorted(set(re.findall(r"(?im)^\s*(temperature|pressure)\s*=", text)))
    for field in unsupported:
        report.errors.append(capability_message("materials.field.unsupported", field=field))

def _validate_template_consistency(template: str, summary: GeometrySummary, report: ValidationReport) -> None:
    template = template.strip().lower()
    if template == "gdml":
        message = capability_message("geometry.gdml.unsupported")
        if message not in report.errors:
            report.errors.append(message)
        return
    known = {"simple_box", "layered_device", "hierarchical", "array", "shielding", "boolean_hierarchical", "hierarchical_boolean"}
    if template and template not in known:
        report.warnings.append(f"Geometry template '{template}' is not in the GUI quick list; verify C++ support.")
    if template == "hierarchical" and not any(volume.section.lower().startswith("volume.") for volume in summary.volumes):
        report.warnings.append("Template is hierarchical but geometry config has no [volume.*] sections.")
    if template == "simple_box" and sum(1 for volume in summary.volumes if volume.section.lower().startswith("volume.")) > 1:
        report.warnings.append("Template is simple_box but geometry config looks like hierarchical multi-volume config.")
    if template == "layered_device" and "layer" not in summary.raw_text.lower():
        report.warnings.append("Template is layered_device but geometry config has no obvious layer keys/sections.")
    if summary.boolean_ops and template not in {"hierarchical", "boolean_hierarchical", "hierarchical_boolean"}:
        report.warnings.append("Geometry config contains boolean sections; hierarchical template is usually expected.")
    if template in {"boolean_hierarchical", "hierarchical_boolean"} and not summary.boolean_ops:
        report.warnings.append("Template is boolean_hierarchical but no boolean sections were found.")


def _validate_material_refs(materials: MaterialsSummary, geometry: GeometrySummary, report: ValidationReport) -> None:
    for material in sorted(ref for ref in geometry.material_refs if ref):
        status = material_reference_status(material, materials.names)
        if status in {"custom", "nist"}:
            continue
        if status == "g4":
            report.warnings.append(f"Geometry references possible NIST material '{material}', not in GUI quick list. Verify Geant4 support.")
        else:
            report.errors.append(f"Geometry references custom material '{material}' but it is not defined in selected materials config.")


def _material_name_set(material_document: MaterialDocument | None, materials_summary: MaterialsSummary | None) -> set[str]:
    if material_document:
        return {row.name for row in material_document.rows if row.enabled and row.name}
    if materials_summary:
        return set(materials_summary.names)
    return set()


def _add_summary_info(materials: MaterialsSummary, geometry: GeometrySummary, report: ValidationReport) -> None:
    report.info.append(f"Materials summary: {len(materials.materials)} material entries parsed.")
    report.info.append(f"Geometry summary: {len(geometry.volumes)} ordinary volumes parsed.")
    if geometry.sensitive_volumes:
        report.info.append("Sensitive volumes: " + ", ".join(sorted(geometry.sensitive_volumes)))
    else:
        report.info.append("Sensitive volumes: <none>")
    if geometry.bias_volumes:
        report.info.append("Bias volumes: " + ", ".join(sorted(geometry.bias_volumes)))
    else:
        report.info.append("Bias volumes: <none>")
    if geometry.boolean_ops:
        report.info.append(
            "Boolean operations: "
            + "; ".join(f"{op.target_volume}[{op.index}] {op.operation} {op.tool_shape}" for op in geometry.boolean_ops)
        )
    else:
        report.info.append("Boolean operations: <none>")


def _add_edited_material_summary_info(materials: MaterialDocument, geometry: GeometrySummary, report: ValidationReport) -> None:
    enabled_count = sum(1 for row in materials.rows if row.enabled)
    report.info.append(f"Materials Editor summary: {enabled_count} enabled material entries, {len(materials.rows) - enabled_count} disabled.")
    report.info.append(f"Geometry summary: {len(geometry.volumes)} ordinary volumes parsed.")
    if geometry.sensitive_volumes:
        report.info.append("Sensitive volumes: " + ", ".join(sorted(geometry.sensitive_volumes)))
    else:
        report.info.append("Sensitive volumes: <none>")
    if geometry.bias_volumes:
        report.info.append("Bias volumes: " + ", ".join(sorted(geometry.bias_volumes)))
    else:
        report.info.append("Bias volumes: <none>")
    if geometry.boolean_ops:
        report.info.append(
            "Boolean operations: "
            + "; ".join(f"{op.target_volume}[{op.index}] {op.operation} {op.tool_shape}" for op in geometry.boolean_ops)
        )
    else:
        report.info.append("Boolean operations: <none>")


def _add_edited_geometry_summary_info(geometry: GeometryDocument, report: ValidationReport) -> None:
    report.info.append(f"Geometry Editor summary: mode={geometry.mode}, dirty={geometry.is_dirty}")
    report.info.append("Geometry Editor material refs: " + (", ".join(sorted(geometry_material_refs(geometry))) or "<none>"))
    report.info.append(f"Geometry Editor sensitive volumes/layers: {geometry_sensitive_count(geometry)}")
    report.info.append(f"Geometry Editor bias volumes/layers: {geometry_bias_count(geometry)}")
    if geometry.volumes:
        report.info.append(
            f"Geometry Editor hierarchical volumes: {sum(1 for row in geometry.volumes if row.enabled)} enabled / {len(geometry.volumes)} rows"
        )
    if geometry.boolean_ops:
        report.info.append(
            f"Geometry Editor boolean ops: {sum(1 for row in geometry.boolean_ops if row.enabled)} enabled / {len(geometry.boolean_ops)} rows"
        )


def _add_editor_summary_info(
    source: SourceEditableModel,
    physics: PhysicsEditableModel,
    scoring: ScoringEditableModel,
    report: ValidationReport,
) -> None:
    report.info.append(f"Source summary: preset={source.preset}, particle={source.particle}, energy={source.energy}")
    report.info.append(
        f"Physics summary: mode={physics.mode}, reference={physics.reference_list}, default_cut={physics.default_cut}, biasing={physics.enable_biasing_physics}"
    )
    report.info.append(
        "Scoring summary: "
        f"enabled={scoring.enabled}, hits={scoring.hits}, event_edep={scoring.event_edep}, edep={scoring.edep}, "
        f"hist_bins={scoring.hist_bins}"
    )
