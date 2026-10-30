from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from g4usim_gui.core.config_schema import check_value
from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.capability_messages import capability_message
from g4usim_gui.core.diagnostics import (
    Diagnostic, EditorLocation, collect_diagnostics, complete_diagnostics,
    diagnostics_to_dict, emit_diagnostic, extend_diagnostics, reset_diagnostics, source_location,
)
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

    def __post_init__(self) -> None:
        reset_diagnostics(self)
        self.snapshot_id = ''

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return complete_diagnostics(self, origin='config.validation')

    def add(self, code: str, severity: str, message: str, **kwargs) -> Diagnostic:
        kwargs.setdefault('origin', 'config.validation')
        return emit_diagnostic(self, code, severity, message, **kwargs)

    def to_dict(self, *, snapshot_id: str | None = None) -> dict:
        return diagnostics_to_dict(self.diagnostics,
            snapshot_id=self.snapshot_id if snapshot_id is None else snapshot_id,
            channels={'errors':self.errors,'warnings':self.warnings,'info':self.info})

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


def _include_messages(report: ValidationReport, owner, source_channel: str,
                      target_channel: str, prefix: str, *, origin: str) -> None:
    # Match only already-structured records to their unchanged legacy projection;
    # no location is derived from the message text.
    severity = {"errors": "error", "warnings": "warning", "info": "info"}[target_channel]
    candidates = list(collect_diagnostics(owner))
    # Documents retain parser records independently of editable-model validation.
    # In particular, round-trip blocker strings may have a display prefix only
    # in the model's errors channel, or not have been validated yet.
    known = {item.identity for item in candidates}
    candidates.extend(item for item in getattr(owner, '_f4_source_diagnostics', ())
                      if item.identity not in known)
    accepted = {severity, "blocker"} if severity == "error" else {severity}
    for slot, message in enumerate(getattr(owner, source_channel)):
        matched = [item for item in candidates
                   if item.severity in accepted and item.message == message]
        if not matched:
            matched = [item for item in candidates
                       if item.severity in accepted and item.raw_message == message]
        if matched:
            # One legacy text can describe multiple rows. Retain every producer
            # identity without repeating the already-deduplicated text channel.
            for item in matched:
                item = replace(item, message=prefix + message)
                existing = next((record for record in collect_diagnostics(report)
                                 if record.identity == item.identity), None)
                if existing is not None and existing.message != item.message:
                    # A parser fact may also be shown in a second report context.
                    # Its machine context, never its translated prefix, separates
                    # those projections while retaining original source facts.
                    item = replace(item, identity_parameters={
                        'producer_identity': item.identity,
                        'aggregation_origin': origin, 'aggregation_channel': source_channel})
                extend_diagnostics(report, (item,), append=False)
        else:
            report.add("legacy.unstructured", severity, prefix + message, origin=origin,
                       raw_message=message, unavailable_reason="legacy_unstructured",
                       identity_parameters={"channel": source_channel, "producer_slot": slot}, append=False)
        getattr(report, target_channel).append(prefix + message)


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
        report.add('config.path.executable.required', 'error', "Executable path is required.", editor='setup', field='executable')
    elif not Path(paths.executable).expanduser().is_file():
        report.add('config.path.executable.missing', 'error', f"Executable does not exist: {paths.executable}", editor='setup', field='executable')
    elif "G4UniversalSim" not in Path(paths.executable).name:
        report.add('config.path.executable.name', 'warning', "Executable file name does not contain G4UniversalSim.", editor='setup', field='executable')

    if paths.workspace_root and not Path(paths.workspace_root).expanduser().is_dir():
        report.add('config.path.workspace.missing', 'error', f"Workspace root does not exist: {paths.workspace_root}", editor='setup', field='workspace_root')

    if not paths.runs_root:
        report.add('config.path.runs.required', 'error', "Runs root is required.", editor='setup', field='runs_root')
    else:
        runs_root = Path(paths.runs_root).expanduser()
        parent = runs_root if runs_root.exists() else runs_root.parent
        if not parent.exists():
            report.add('config.path.runs.parent_missing', 'error', f"Runs root parent does not exist: {paths.runs_root}", editor='setup', field='runs_root')

    if not paths.materials_config:
        report.add('config.path.materials.required', 'error', "Materials config is required.", editor='setup', field='materials_config')
    elif not Path(paths.materials_config).expanduser().is_file():
        report.add('config.path.materials.missing', 'error', f"Materials config does not exist: {paths.materials_config}", editor='setup', field='materials_config')
    else:
        materials_summary = parse_materials(paths.materials_config)
        material_editor_covers_source = bool(
            material_document and _editor_source_matches(material_document, materials_summary)
        )
        if material_document and material_document.source_path and not material_editor_covers_source:
            report.add('config.source.materials.changed', 'error', ui_text("Materials source changed since the editor was loaded; reload materials before generating a package."), editor='setup', field='materials_config')
        # MaterialDocument retains source errors, but its semantic validator
        # rebuilds warnings; keep parser warnings from the current source.
        _include_messages(report, materials_summary, 'warnings', 'warnings', 'Materials: ', origin='materials_summary')
        if not material_editor_covers_source:
            _include_messages(report, materials_summary, 'errors', 'errors', 'Materials: ', origin='materials_summary')
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
        _include_messages(report, geometry_document, 'round_trip_blockers', 'errors', 'Geometry round-trip blocker: ', origin='geometry_document')

    if not geometry.template:
        report.add('config.geometry.template.required', 'error', "Geometry template is required.", editor='setup', field='geometry_template')

    if not geometry.config_path:
        report.add('config.path.geometry.required', 'error', "Geometry config is required.", editor='setup', field='geometry_config')
    elif not Path(geometry.config_path).expanduser().is_file():
        report.add('config.path.geometry.missing', 'error', f"Geometry config does not exist: {geometry.config_path}", editor='setup', field='geometry_config')
    else:
        geometry_summary = parse_geometry(geometry.config_path, geometry.template)
        geometry_editor_covers_source = bool(
            use_edited_geometry and geometry_document
            and _editor_source_matches(geometry_document, geometry_summary)
        )
        if use_edited_geometry and geometry_document and geometry_document.source_path and not geometry_editor_covers_source:
            report.add('config.source.geometry.changed', 'error', ui_text("Geometry source changed since the editor was loaded; reload geometry before generating a package."), editor='setup', field='geometry_config')
        if not geometry_editor_covers_source:
            _include_messages(report, geometry_summary, 'warnings', 'warnings', 'Geometry: ', origin='geometry_summary')
            _include_messages(report, geometry_summary, 'errors', 'errors', 'Geometry: ', origin='geometry_summary')
        _validate_geometry_text(Path(geometry.config_path).expanduser(), report)
        _validate_template_consistency(geometry.template, geometry_summary, report)

    # [run] fields the package writes, checked as the backend reads them (configuration schema, E2)
    if run.threads <= 0:
        report.add('config.run.threads.positive', 'error', "Threads must be a positive integer.", editor='run', field='threads')
    for key, value in (("threads", run.threads), ("seed", run.seed), ("name", run.run_name)):
        problem = check_value("run", key, str(value)) if value is not None else None
        if problem and not (key == "threads" and run.threads <= 0):
            report.add('config.run.field.invalid', 'error', problem, editor='run', field='run_name' if key == 'name' else key)
    if run.beam_on < 0:
        report.add('config.run.beam_on.nonnegative', 'error', "BeamOn must be >= 0.", editor='run', field='beam_on')
    if not run.run_name.strip():
        report.add('config.run.name.default', 'info', "Run name is empty; package writer will use gui_run.", editor='run', field='run_name')

    source_model = source_model or SourceEditableModel.from_settings(source)
    physics_model = physics_model or PhysicsEditableModel.from_settings(physics)
    scoring_model = scoring_model or ScoringEditableModel.from_settings(scoring)
    validate_source_model(source_model)
    validate_physics_model(physics_model)
    validate_scoring_model(scoring_model)
    _include_messages(report, source_model, 'errors', 'errors', 'Source: ', origin='source_model')
    _include_messages(report, source_model, 'warnings', 'warnings', 'Source: ', origin='source_model')
    _include_messages(report, physics_model, 'errors', 'errors', 'Physics: ', origin='physics_model')
    _include_messages(report, physics_model, 'warnings', 'warnings', 'Physics: ', origin='physics_model')

    if use_edited_geometry and geometry_document:
        material_names = _material_name_set(material_document, materials_summary)
        validate_geometry_document(
            geometry_document,
            material_names=material_names,
            scoring_hits_enabled=scoring_model.hits,
            physics_biasing_enabled=physics_model.enable_biasing_physics,
        )
        _include_messages(report, geometry_document, 'errors', 'errors', 'Geometry Editor: ', origin='geometry_document')
        _include_messages(report, geometry_document, 'warnings', 'warnings', 'Geometry Editor: ', origin='geometry_document')
        if material_document:
            validate_material_document(material_document, geometry_material_refs=geometry_material_refs(geometry_document))
            _include_messages(report, material_document, 'errors', 'errors', 'Materials Editor: ', origin='material_document')
            _include_messages(report, material_document, 'warnings', 'warnings', 'Materials Editor: ', origin='material_document')
        _add_edited_geometry_summary_info(geometry_document, report)
    elif geometry_document and geometry_document.source_copy_mode:
        report.add('config.geometry.source_copy.active', 'warning', "Geometry Editor: original source copy mode is active; blocked fields are preserved but not certified by editor validation.", editor='geometry', field='source_copy_mode')
    elif geometry_summary and material_document:
        validate_material_document(material_document, geometry_material_refs=geometry_summary.material_refs)
        _include_messages(report, material_document, 'errors', 'errors', 'Materials Editor: ', origin='material_document')
        _include_messages(report, material_document, 'warnings', 'warnings', 'Materials Editor: ', origin='material_document')
        _add_edited_material_summary_info(material_document, geometry_summary, report)
    elif materials_summary and geometry_summary:
        _validate_material_refs(materials_summary, geometry_summary, report)
        _add_summary_info(materials_summary, geometry_summary, report)

    _include_messages(report, scoring_model, 'errors', 'errors', 'Scoring: ', origin='scoring_model')
    _include_messages(report, scoring_model, 'warnings', 'warnings', 'Scoring: ', origin='scoring_model')
    _add_editor_summary_info(source_model, physics_model, scoring_model, report)

    if not report.errors:
        report.add('config.information.validate_config_builder.1', 'info', "Validation passed.", unavailable_reason='informational')
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
        report.add('geometry.shape.not_editable', 'warning', "Geometry uses shape = tessellated (STL, backend-supported); the GUI geometry "
                               "editors cannot edit it.", origin='config.source', source=_source_field_location(path, text, key='shape', allowed_values=('tessellated', 'stl')), unavailable_reason='source_only')
    if re.search(r"(?im)^\s*\[gdml\]\s*(?:#.*)?$", text):
        message = capability_message("geometry.gdml.external")
        if message not in report.warnings:
            report.add('geometry.gdml.external', 'warning', message, origin='config.source', source=_source_field_location(path, text, section='gdml'), unavailable_reason='source_only')
    unsupported_placements = sorted(set(re.findall(
        r"(?im)^\s*placement\s*=\s*(assembly)\s*(?:#.*)?$",
        text,
    )))
    for placement in unsupported_placements:
        report.add('geometry.placement.unsupported', 'error', capability_message("geometry.placement.unsupported", placement=placement), origin='config.source', source=_source_field_location(path, text, key='placement', value=placement), unavailable_reason='source_only')
    # Roadmap A5: the backend builds replica/parameterised placement from a
    # hand-written geometry INI; the GUI editors cannot edit them.
    if re.search(r"(?im)^\s*placement\s*=\s*(replica|parameteri[sz]ed)\s*(?:#.*)?$", text):
        report.add('geometry.placement.not_editable', 'warning', "Geometry uses placement=replica/parameterised (backend-supported); "
                               "the GUI geometry editors cannot edit these volumes.", origin='config.source', source=_source_field_location(path, text, key='placement', allowed_values=('replica', 'parameterised', 'parameterized')), unavailable_reason='source_only')
    if "let" in lower or "dose" in lower or "fluence" in lower:
        report.add('geometry.scoring.not_edited', 'warning', "Geometry config mentions LET/Dose/Fluence; those are not edited by this GUI MVP.", origin='config.source', source=source_location(str(path), text, key='', section='', value=''), unavailable_reason='source_only')
    if "[volume." in lower and ".boolean." in lower:
        report.add('config.information.validate_geometry_text.1', 'info', "Boolean geometry sections detected and allowed.", unavailable_reason='informational')
        for section_match in re.finditer(r"(?ims)^\s*\[([^\]]*boolean[^\]]*)\]\s*(.*?)(?=^\s*\[|\Z)", text):
            section_name = section_match.group(1)
            body = section_match.group(2).lower()
            for key in ["material", "sensitive", "bias", "region", "cuts", "production"]:
                if re.search(rf"^\s*{re.escape(key)}\s*=", body, re.MULTILINE):
                    report.add('geometry.boolean.ignored_field', 'warning', f"Boolean section [{section_name}] contains '{key}', which may be ignored by the boolean tool.", origin='config.source', source=_source_field_location(path, text, key=key, section=section_name), unavailable_reason='source_only')


def _validate_material_text(path: Path, report: ValidationReport) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    unsupported = sorted(set(re.findall(r"(?im)^\s*(temperature|pressure)\s*=", text)))
    for field in unsupported:
        report.add('materials.field.unsupported', 'error', capability_message("materials.field.unsupported", field=field), origin='config.source', source=_source_field_location(path, text, key=field), unavailable_reason='source_only')


def _source_field_location(filename: str | Path, text: str, *, key: str = '',
                           section: str = '', value: str = '', allowed_values=()):
    """Locate a raw producer fact in its already-read text, never display text.

    Aggregate rules retain one diagnostic per value, with the first actual
    matching source occurrence. If no exact occurrence exists, retain the
    file-level fact without inventing a line number.
    """
    current_section = ''
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('[') and ']' in line:
            current_section = line[1:line.index(']')].strip()
            if not key and section and current_section.lower() == section.lower():
                return source_location(filename, text, line=line_number, section=current_section)
            continue
        if not key or '=' not in line or (section and current_section.lower() != section.lower()):
            continue
        source_key, source_value = (part.strip() for part in line.split('=', 1))
        for marker in (' #', ' ;'):
            source_value = source_value.split(marker, 1)[0].rstrip()
        if source_key.lower() != key.lower() or (value and source_value != value):
            continue
        if allowed_values and source_value.lower() not in allowed_values:
            continue
        return source_location(filename, text, line=line_number, section=current_section,
                               key=source_key, value=source_value)
    return source_location(filename, text, section=section, key=key, value=value)

def _validate_template_consistency(template: str, summary: GeometrySummary, report: ValidationReport) -> None:
    template = template.strip().lower()
    if template == "gdml":
        message = capability_message("geometry.gdml.unsupported")
        if message not in report.errors:
            report.add('config.geometry.template.gdml', 'error', message, editor='setup', field='geometry_template')
        return
    known = {"simple_box", "layered_device", "hierarchical", "array", "shielding", "boolean_hierarchical", "hierarchical_boolean"}
    if template and template not in known:
        report.add('config.geometry.template.unknown', 'warning', f"Geometry template '{template}' is not in the GUI quick list; verify C++ support.", editor='setup', field='geometry_template')
    if template == "hierarchical" and not any(volume.section.lower().startswith("volume.") for volume in summary.volumes):
        report.add('config.geometry.template.hierarchical_mismatch', 'warning', "Template is hierarchical but geometry config has no [volume.*] sections.", editor='setup', field='geometry_template')
    if template == "simple_box" and sum(1 for volume in summary.volumes if volume.section.lower().startswith("volume.")) > 1:
        report.add('config.geometry.template.simple_mismatch', 'warning', "Template is simple_box but geometry config looks like hierarchical multi-volume config.", editor='setup', field='geometry_template')
    if template == "layered_device" and "layer" not in summary.raw_text.lower():
        report.add('config.geometry.template.layered_mismatch', 'warning', "Template is layered_device but geometry config has no obvious layer keys/sections.", editor='setup', field='geometry_template')
    if summary.boolean_ops and template not in {"hierarchical", "boolean_hierarchical", "hierarchical_boolean"}:
        report.add('config.geometry.template.boolean_expected', 'warning', "Geometry config contains boolean sections; hierarchical template is usually expected.", editor='setup', field='geometry_template')
    if template in {"boolean_hierarchical", "hierarchical_boolean"} and not summary.boolean_ops:
        report.add('config.geometry.template.boolean_missing', 'warning', "Template is boolean_hierarchical but no boolean sections were found.", editor='setup', field='geometry_template')


def _validate_material_refs(materials: MaterialsSummary, geometry: GeometrySummary, report: ValidationReport) -> None:
    for material in sorted(ref for ref in geometry.material_refs if ref):
        status = material_reference_status(material, materials.names)
        if status in {"custom", "nist"}:
            continue
        if status == "g4":
            report.add('geometry.material.unknown_nist', 'warning', f"Geometry references possible NIST material '{material}', not in GUI quick list. Verify Geant4 support.", origin='config.source', source=_source_field_location(geometry.path, geometry.raw_text, key='material', value=material), unavailable_reason='source_only')
        else:
            report.add('geometry.material.missing', 'error', f"Geometry references custom material '{material}' but it is not defined in selected materials config.", origin='config.source', source=_source_field_location(geometry.path, geometry.raw_text, key='material', value=material), unavailable_reason='source_only')


def _material_name_set(material_document: MaterialDocument | None, materials_summary: MaterialsSummary | None) -> set[str]:
    if material_document:
        return {row.name for row in material_document.rows if row.enabled and row.name}
    if materials_summary:
        return set(materials_summary.names)
    return set()


def _add_summary_info(materials: MaterialsSummary, geometry: GeometrySummary, report: ValidationReport) -> None:
    report.add('config.information.add_summary_info.1', 'info', f"Materials summary: {len(materials.materials)} material entries parsed.", unavailable_reason='informational')
    report.add('config.information.add_summary_info.2', 'info', f"Geometry summary: {len(geometry.volumes)} ordinary volumes parsed.", unavailable_reason='informational')
    if geometry.sensitive_volumes:
        report.add('config.information.add_summary_info.3', 'info', "Sensitive volumes: " + ", ".join(sorted(geometry.sensitive_volumes)), unavailable_reason='informational')
    else:
        report.add('config.information.add_summary_info.4', 'info', "Sensitive volumes: <none>", unavailable_reason='informational')
    if geometry.bias_volumes:
        report.add('config.information.add_summary_info.5', 'info', "Bias volumes: " + ", ".join(sorted(geometry.bias_volumes)), unavailable_reason='informational')
    else:
        report.add('config.information.add_summary_info.6', 'info', "Bias volumes: <none>", unavailable_reason='informational')
    if geometry.boolean_ops:
        report.add('config.information.add_summary_info.7', 'info', "Boolean operations: "
            + "; ".join(f"{op.target_volume}[{op.index}] {op.operation} {op.tool_shape}" for op in geometry.boolean_ops), unavailable_reason='informational')
    else:
        report.add('config.information.add_summary_info.8', 'info', "Boolean operations: <none>", unavailable_reason='informational')


def _add_edited_material_summary_info(materials: MaterialDocument, geometry: GeometrySummary, report: ValidationReport) -> None:
    enabled_count = sum(1 for row in materials.rows if row.enabled)
    report.add('config.information.add_edited_material_summary_info.1', 'info', f"Materials Editor summary: {enabled_count} enabled material entries, {len(materials.rows) - enabled_count} disabled.", unavailable_reason='informational')
    report.add('config.information.add_edited_material_summary_info.2', 'info', f"Geometry summary: {len(geometry.volumes)} ordinary volumes parsed.", unavailable_reason='informational')
    if geometry.sensitive_volumes:
        report.add('config.information.add_edited_material_summary_info.3', 'info', "Sensitive volumes: " + ", ".join(sorted(geometry.sensitive_volumes)), unavailable_reason='informational')
    else:
        report.add('config.information.add_edited_material_summary_info.4', 'info', "Sensitive volumes: <none>", unavailable_reason='informational')
    if geometry.bias_volumes:
        report.add('config.information.add_edited_material_summary_info.5', 'info', "Bias volumes: " + ", ".join(sorted(geometry.bias_volumes)), unavailable_reason='informational')
    else:
        report.add('config.information.add_edited_material_summary_info.6', 'info', "Bias volumes: <none>", unavailable_reason='informational')
    if geometry.boolean_ops:
        report.add('config.information.add_edited_material_summary_info.7', 'info', "Boolean operations: "
            + "; ".join(f"{op.target_volume}[{op.index}] {op.operation} {op.tool_shape}" for op in geometry.boolean_ops), unavailable_reason='informational')
    else:
        report.add('config.information.add_edited_material_summary_info.8', 'info', "Boolean operations: <none>", unavailable_reason='informational')


def _add_edited_geometry_summary_info(geometry: GeometryDocument, report: ValidationReport) -> None:
    report.add('config.information.add_edited_geometry_summary_info.1', 'info', f"Geometry Editor summary: mode={geometry.mode}, dirty={geometry.is_dirty}", unavailable_reason='informational')
    report.add('config.information.add_edited_geometry_summary_info.2', 'info', "Geometry Editor material refs: " + (", ".join(sorted(geometry_material_refs(geometry))) or "<none>"), unavailable_reason='informational')
    report.add('config.information.add_edited_geometry_summary_info.3', 'info', f"Geometry Editor sensitive volumes/layers: {geometry_sensitive_count(geometry)}", unavailable_reason='informational')
    report.add('config.information.add_edited_geometry_summary_info.4', 'info', f"Geometry Editor bias volumes/layers: {geometry_bias_count(geometry)}", unavailable_reason='informational')
    if geometry.volumes:
        report.add('config.information.add_edited_geometry_summary_info.5', 'info', f"Geometry Editor hierarchical volumes: {sum(1 for row in geometry.volumes if row.enabled)} enabled / {len(geometry.volumes)} rows", unavailable_reason='informational')
    if geometry.boolean_ops:
        report.add('config.information.add_edited_geometry_summary_info.6', 'info', f"Geometry Editor boolean ops: {sum(1 for row in geometry.boolean_ops if row.enabled)} enabled / {len(geometry.boolean_ops)} rows", unavailable_reason='informational')


def _add_editor_summary_info(
    source: SourceEditableModel,
    physics: PhysicsEditableModel,
    scoring: ScoringEditableModel,
    report: ValidationReport,
) -> None:
    report.add('config.information.add_editor_summary_info.1', 'info', f"Source summary: preset={source.preset}, particle={source.particle}, energy={source.energy}", unavailable_reason='informational')
    report.add('config.information.add_editor_summary_info.2', 'info', f"Physics summary: mode={physics.mode}, reference={physics.reference_list}, default_cut={physics.default_cut}, biasing={physics.enable_biasing_physics}", unavailable_reason='informational')
    report.add('config.information.add_editor_summary_info.3', 'info', "Scoring summary: "
        f"enabled={scoring.enabled}, hits={scoring.hits}, event_edep={scoring.event_edep}, edep={scoring.edep}, "
        f"hist_bins={scoring.hist_bins}", unavailable_reason='informational')
