from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from g4usim_gui.core.diagnostics import (
    EditorLocation, collect_diagnostics, emit_diagnostic, extend_diagnostics, reset_diagnostics, source_location,
)

from g4usim_gui.editors.editable_models import EditableDocument
from g4usim_gui.parsers.materials_parser import NIST_QUICK_LIST, MaterialsSummary, material_reference_status


MATERIAL_MODES = {"nist", "mass_fraction", "volume_fraction", "atom_count"}
FRACTION_TOLERANCE = 1.0e-6


@dataclass
class MaterialComponent:
    name: str = ""
    value: str = ""
    kind: str = "unknown"


@dataclass
class MaterialRow:
    enabled: bool = True
    name: str = ""
    mode: str = "mass_fraction"
    density: str = ""
    nist_name: str = ""
    components_text: str = ""
    components: list[MaterialComponent] = field(default_factory=list)
    notes: str = ""
    source_section: str = ""
    is_dirty: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.errors:
            return "ERROR"
        if self.warnings:
            return "WARN"
        return "OK"


@dataclass
class MaterialDocument(EditableDocument):
    rows: list[MaterialRow] = field(default_factory=list)
    raw_source_text: str = ""
    source_errors: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    preserved_sections: list[str] = field(default_factory=list)   # [NIST]/[element.*]/[isotope.*], verbatim


def material_document_from_summary(summary: MaterialsSummary | None) -> MaterialDocument:
    document = MaterialDocument()
    if summary is None:
        return document
    document.source_path = summary.path
    document.raw_source_text = summary.raw_text
    document._f4_source_diagnostics = collect_diagnostics(summary)
    document.source_errors = _deduplicate(summary.errors)
    document.warnings = list(summary.warnings)
    document.preserved_sections = list(summary.preserved_sections)
    for entry in summary.materials:
        mode = _mode_from_kind(entry.kind)
        density = entry.density
        if entry.kind == "nist" and entry.components:
            name = entry.name
            nist_name = entry.components[0]
            components_text = ""
            notes = f"NIST alias: {nist_name}"
        else:
            name = entry.name
            nist_name = ""
            components_text = "\n".join(entry.components)
            notes = ""
        row = MaterialRow(
            enabled=True,
            name=name,
            mode=mode,
            density=density,
            nist_name=nist_name,
            components_text=components_text,
            source_section=entry.section,
            notes=notes,
        )
        row.components = parse_components_text(row.components_text, row.mode)
        document.rows.append(row)
    validate_material_document(document)
    document.is_dirty = False
    for row in document.rows:
        row.is_dirty = False
    return document


def _mode_from_kind(kind: str) -> str:
    if kind == "nist":
        return "nist"
    if kind in {"mass_fraction", "volume_fraction", "atom_count"}:
        return kind
    return "mass_fraction"


def parse_components_text(text: str, mode: str) -> list[MaterialComponent]:
    kind = "count" if mode == "atom_count" else "fraction" if mode in {"mass_fraction", "volume_fraction"} else "unknown"
    components: list[MaterialComponent] = []
    normalized = text.replace(",", "\n")
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            components.append(MaterialComponent(name=line, value="", kind=kind))
            continue
        name, value = line.split(":", 1)
        components.append(MaterialComponent(name=name.strip(), value=value.strip(), kind=kind))
    return components


def components_to_ini_text(text: str, mode: str) -> str:
    return ", ".join(f"{component.name}:{component.value}" for component in parse_components_text(text, mode))


def add_default_row(document: MaterialDocument, mode: str) -> MaterialRow:
    if mode == "nist":
        row = MaterialRow(name=_unique_name(document, "G4_Si"), mode="nist", density="", nist_name="G4_Si", components_text="")
    elif mode == "volume_fraction":
        row = MaterialRow(
            name=_unique_name(document, "NewComposite"),
            mode="volume_fraction",
            density="auto",
            components_text="G4_SILICON_DIOXIDE:0.5\nG4_POLYETHYLENE:0.5",
        )
    elif mode == "atom_count":
        row = MaterialRow(
            name=_unique_name(document, "NewCompound"),
            mode="atom_count",
            density="1.0 g/cm3",
            components_text="G4_H:2\nG4_O:1",
        )
    else:
        row = MaterialRow(
            name=_unique_name(document, "NewMaterial"),
            mode="mass_fraction",
            density="1.0 g/cm3",
            components_text="G4_Si:1.0",
        )
    row.components = parse_components_text(row.components_text, row.mode)
    row.is_dirty = True
    document.rows.append(row)
    mark_dirty(document)
    validate_material_document(document)
    return row


def duplicate_row(document: MaterialDocument, index: int) -> MaterialRow | None:
    if index < 0 or index >= len(document.rows):
        return None
    source = document.rows[index]
    row = MaterialRow(
        enabled=source.enabled,
            name=_unique_name(document, f"{source.name}_copy"),
            mode=source.mode,
            density=source.density,
            nist_name=source.nist_name,
        components_text=source.components_text,
        notes=source.notes,
        is_dirty=True,
    )
    row.components = parse_components_text(row.components_text, row.mode)
    document.rows.insert(index + 1, row)
    mark_dirty(document)
    validate_material_document(document)
    return row


def delete_row(document: MaterialDocument, index: int) -> None:
    if 0 <= index < len(document.rows):
        del document.rows[index]
        mark_dirty(document)
        validate_material_document(document)


def mark_dirty(document: MaterialDocument) -> None:
    document.is_dirty = True


def validate_material_document(document: MaterialDocument, *, geometry_material_refs: set[str] | None = None) -> MaterialDocument:
    reset_diagnostics(document)
    extend_diagnostics(document, (item for item in getattr(document, "_f4_source_diagnostics", ())
                                  if item.severity == "error"), append=False)
    validation_errors: list[str] = []
    document.warnings = []
    names: dict[str, int] = {}
    enabled_names: set[str] = set()
    for index, row in enumerate(document.rows):
        reset_diagnostics(row)
        row._f4_row_index = index
        row.errors = []
        row.warnings = []
        row.name = row.name.strip()
        row.mode = row.mode.strip()
        row.density = row.density.strip()
        row.components = parse_components_text(row.components_text, row.mode)
        if not row.enabled:
            continue
        if not row.name:
            _issue(row, 'materials.name.required', 'error', "name is required", 'name')
        else:
            key = row.name.lower()
            names[key] = names.get(key, 0) + 1
            enabled_names.add(row.name)
        if row.mode not in MATERIAL_MODES:
            _issue(row, 'materials.mode.unsupported', 'error', f"unsupported mode '{row.mode}'", 'mode')
        _validate_density(row)
        _validate_components(row, document)
    for row in document.rows:
        if row.enabled and row.name and names.get(row.name.lower(), 0) > 1:
            _issue(row, 'materials.name.duplicate', 'error', "duplicate material name", 'name')
    validation_errors.extend(_dependency_cycles(document))
    if geometry_material_refs:
        for ref in sorted(geometry_material_refs):
            if not ref:
                continue
            status = material_reference_status(ref, enabled_names)
            if status in {"custom", "nist"}:
                continue
            if status == "g4":
                _issue(document, 'materials.geometry_reference.unlisted', 'warning', f"Geometry references possible NIST material '{ref}', not in quick list.", 'rows', reason='cross_document_reference', facts={'material': ref})
            else:
                message = f"Geometry references custom material '{ref}' but it is not defined in edited materials."
                validation_errors.append(message)
                _issue(document, "materials.geometry_reference.undefined", "error", message, "rows",
                       reason="cross_document_reference", facts={"material": ref}, append=False)
    for row in document.rows:
        for error in row.errors:
            validation_errors.append(f"{row.name or '<unnamed>'}: {error}")
        for warning in row.warnings:
            document.warnings.append(f"{row.name or '<unnamed>'}: {warning}")
        extend_diagnostics(document, collect_diagnostics(row), prefix=f"{row.name or '<unnamed>'}: ", append=False)
    document.validation_errors = _deduplicate(validation_errors)
    document.errors = _deduplicate([*document.source_errors, *document.validation_errors])
    return document


def _dependency_cycles(document: MaterialDocument) -> list[str]:
    """Materials built from each other in a loop, which the backend refuses (MaterialManager::BuildMaterial)."""
    rows = {row.name.lower(): row for row in document.rows if row.enabled and row.name and row.mode != "nist"}
    uses = {key: [c.name.lower() for c in row.components if c.name.lower() in rows] for key, row in rows.items()}
    errors: list[str] = []
    state: dict[str, str] = {}

    def visit(key: str, path: list[str]) -> None:
        state[key] = "open"
        for used in uses[key]:
            if state.get(used) == "open":
                loop = path[path.index(used):] + [used]
                message = "Circular material dependency: " + " -> ".join(rows[k].name for k in loop)
                errors.append(message)
                _issue(document, "materials.components.cycle", "error", message, "components_text",
                       target=rows[key], facts={"cycle": loop}, append=False)
            elif used not in state:
                visit(used, path + [used])
        state[key] = "done"

    for key in rows:
        if key not in state:
            visit(key, [key])
    return errors


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _issue(owner, code: str, severity: str, message: str, field: str, *,
           target=None, reason: str = "", facts: dict | None = None, append: bool = True, source=None) -> None:
    """Emit at the rule site without changing the established text channel."""
    if append:
        getattr(owner, "errors" if severity == "error" else "warnings").append(message)
    target = owner if target is None else target
    row = getattr(target, "_f4_row_index", None)
    location = None if reason else EditorLocation("materials", field, "rows" if row is not None else "",
                                                   row, getattr(target, "name", ""))
    value = getattr(target, field, None)
    if not isinstance(value, (str, int, float, bool, type(None))):
        value = None
    identity = {"value": value, **(facts or {})}
    if location is None:
        identity.update(field=field, collection="rows" if row is not None else "", row=row,
                        entity=getattr(target, "name", ""))
    emit_diagnostic(owner, code, severity, message, origin="materials.editor", location=location, source=source,
                    identity_parameters=identity,
                    unavailable_reason=reason, append=False)


def _validate_density(row: MaterialRow) -> None:
    if row.mode == "nist":
        if row.density:
            _issue(row, 'materials.density.ignored', 'warning', "density is ignored for nist rows", 'density')
        return
    if row.mode == "volume_fraction" and row.density.lower() in {"", "auto"}:
        return   # the backend computes it from the components (no density means auto, as in MaterialIniReader)
    if not row.density:
        _issue(row, 'materials.density.required', 'error', "density is required", 'density')
        return
    first = row.density.split()[0]
    try:
        value = float(first)
    except ValueError:
        _issue(row, 'materials.density.numeric', 'error', "density should start with a positive number or be auto for volume_fraction", 'density')
        return
    if value <= 0.0:
        _issue(row, 'materials.density.positive', 'error', "density must be > 0", 'density')


def _validate_components(row: MaterialRow, document: MaterialDocument) -> None:
    if row.mode == "nist":
        if row.components:
            _issue(row, 'materials.components.ignored', 'warning', "components are ignored for nist rows", 'components_text')
        if not (row.name.startswith("G4_") or row.name in NIST_QUICK_LIST):
            target = row.nist_name.strip() or row.name
            if not target.startswith("G4_") and target not in NIST_QUICK_LIST:
                # The alias's retained NIST target has no dedicated editor control.
                source = (source_location(document.source_path, document.raw_source_text)
                          if row.nist_name.strip() and document.source_path else None)
                _issue(row, 'materials.nist.unlisted', 'warning', "nist target is not in the quick NIST list",
                       'nist_name' if row.nist_name.strip() else 'name',
                       reason='unsupported_editor' if row.nist_name.strip() else '', source=source)
        return
    if not row.components:
        _issue(row, 'materials.components.required', 'error', "at least one component is required", 'components_text')
        return
    values: list[float] = []
    for index, component in enumerate(row.components, start=1):
        if not component.name:
            _issue(row, 'materials.component.name_required', 'error', f"component line {index}: name is required", 'components_text', facts={'component': index})
        if not component.value:
            _issue(row, 'materials.component.value_required', 'error', f"component line {index}: value is required", 'components_text', facts={'component': index})
            continue
        try:
            value = float(component.value)
        except ValueError:
            _issue(row, 'materials.component.numeric', 'error', f"component line {index}: value must be numeric", 'components_text', facts={'component': index})
            continue
        if value <= 0.0:
            _issue(row, 'materials.component.positive', 'error', f"component line {index}: value must be > 0", 'components_text', facts={'component': index})
        values.append(value)
        if row.mode == "atom_count" and abs(value - round(value)) > 1.0e-9:
            _issue(row, 'materials.component.integer', 'error', f"component line {index}: atom_count value must be an integer", 'components_text', facts={'component': index})
        if row.mode == "volume_fraction":
            _validate_volume_component(row, component, document)
    if row.mode in {"mass_fraction", "volume_fraction"} and values:
        total = sum(values)
        if abs(total - 1.0) > FRACTION_TOLERANCE:
            _issue(row, 'materials.components.total', 'error', f"{row.mode} components must sum to 1.0; got {total:g}", 'components_text')


def _validate_volume_component(row: MaterialRow, component: MaterialComponent, document: MaterialDocument) -> None:
    defined = {item.name for item in document.rows if item.enabled and item.name and item.name != row.name}
    if component.name in defined:
        return
    if component.name in NIST_QUICK_LIST:
        return
    if component.name.startswith("G4_"):
        _issue(row, 'materials.component.unlisted', 'warning', f"component '{component.name}' is a G4_ name outside the quick list; verify it is a material", 'components_text', facts={'component_name': component.name})
        return
    _issue(row, 'materials.component.undefined', 'error', f"volume_fraction component '{component.name}' is not defined as a material", 'components_text', facts={'component_name': component.name})


def generate_materials_ini_text(document: MaterialDocument) -> str:
    validate_material_document(document)
    if document.errors:
        raise ValueError("Cannot generate materials.ini with validation errors:\n" + "\n".join(document.errors))
    lines = [
        "# Generated by G4UniversalSim GUI",
        "# Source materials.ini is not overwritten.",
        "",
    ]
    for text in document.preserved_sections:   # elements and isotopes first: materials may use them
        lines.extend([text, ""])
    for row in document.rows:
        if not row.enabled:
            continue
        if row.mode == "nist":
            lines.extend([f"[{row.name}]", f"material = {row.nist_name.strip() or row.name}", ""])
            continue
        lines.extend([
            f"[material.{row.name}]",
            f"mode = {row.mode}",
            f"density = {row.density or 'auto'}",
            f"components = {components_to_ini_text(row.components_text, row.mode)}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def material_document_to_snapshot(document: MaterialDocument) -> dict:
    return {
        "sourcePath": document.source_path,
        "generatedPath": document.generated_path,
        "isDirty": document.is_dirty,
        "rowCount": len(document.rows),
        "enabledCount": sum(1 for row in document.rows if row.enabled),
        "errors": list(document.errors),
        "sourceErrors": list(document.source_errors),
        "validationErrors": list(document.validation_errors),
        "warnings": list(document.warnings),
        "rows": [
            {
                "enabled": row.enabled,
                "name": row.name,
                "mode": row.mode,
                "density": row.density,
                "nistName": row.nist_name,
                "components": len(parse_components_text(row.components_text, row.mode)),
                "dirty": row.is_dirty,
                "errors": row.errors,
                "warnings": row.warnings,
            }
            for row in document.rows
        ],
    }


def _unique_name(document: MaterialDocument, base: str) -> str:
    names = {row.name.lower() for row in document.rows}
    candidate = base
    suffix = 1
    while candidate.lower() in names:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def clone_document(document: MaterialDocument) -> MaterialDocument:
    clone = MaterialDocument(
        source_path=document.source_path,
        generated_path=document.generated_path,
        is_dirty=document.is_dirty,
        errors=list(document.errors),
        warnings=list(document.warnings),
        raw_source_text=document.raw_source_text,
        source_errors=list(document.source_errors),
        validation_errors=list(document.validation_errors),
        preserved_sections=list(document.preserved_sections),
    )
    for row in document.rows:
        clone.rows.append(
            MaterialRow(
                enabled=row.enabled,
                name=row.name,
                mode=row.mode,
                density=row.density,
                nist_name=row.nist_name,
                components_text=row.components_text,
                components=list(row.components),
                notes=row.notes,
                source_section=row.source_section,
                is_dirty=row.is_dirty,
                errors=list(row.errors),
                warnings=list(row.warnings),
            )
        )
    clone._f4_source_diagnostics = tuple(getattr(document, "_f4_source_diagnostics", ()))
    extend_diagnostics(clone, collect_diagnostics(document), append=False)
    return clone


def source_file_unchanged(path: str, original_text: str) -> bool:
    if not path:
        return True
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace") == original_text
    except OSError:
        return False
