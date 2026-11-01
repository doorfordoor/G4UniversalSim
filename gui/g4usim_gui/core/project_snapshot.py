"""Explicit adapter for the known generated run-package snapshot envelope.

Restore current package materials/geometry and CURRENT main.ini run editors.
Macro execution and historical/new runtime success are never inferred.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import os
from pathlib import Path

from g4usim_gui.core.config_migration import digest, load_json_strict
from g4usim_gui.core.project_migration import normalize_project_data, validate_dataclass_fields
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.models.package_model import RunPackage
from g4usim_gui.models.run_model import RunSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.ini_light_parser import parse_ini_light
from g4usim_gui.parsers.materials_parser import parse_materials
from g4usim_gui.core.run_editor_import import parse_run_editor_ini, RunEditorImportError, ImportIssue


@dataclass(frozen=True)
class SnapshotInput:
    role: str
    path: str
    sha256: str


@dataclass(frozen=True)
class ProjectSnapshotLoad:
    project: object
    package_root: str
    notes: tuple[str, ...]
    inputs: tuple[SnapshotInput, ...]
    snapshot_sha256: str


@dataclass
class _MaterialBrief:
    name: str = ""
    kind: str = ""
    density: str = ""
    components: int = 0


@dataclass
class _MaterialsSummary:
    path: str = ""
    count: int = 0
    materials: list[_MaterialBrief] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class _VolumeBrief:
    name: str = ""
    parent: str = ""
    shape: str = ""
    material: str = ""
    sensitive: bool = False
    bias: bool = False
    booleanOps: int = 0


@dataclass
class _BooleanBrief:
    target: str = ""
    index: int = 0
    operation: str = ""
    toolShape: str = ""
    forbiddenKeys: list[str] = field(default_factory=list)


@dataclass
class _GeometrySummary:
    path: str = ""
    templateHint: str = ""
    volumes: list[_VolumeBrief] = field(default_factory=list)
    materialRefs: list[str] = field(default_factory=list)
    sensitiveVolumes: list[str] = field(default_factory=list)
    biasVolumes: list[str] = field(default_factory=list)
    booleanOps: list[_BooleanBrief] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class _MaterialRowBrief:
    enabled: bool = True
    name: str = ""
    mode: str = ""
    density: str = ""
    nistName: str = ""
    components: int = 0
    dirty: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _MaterialDocumentBrief:
    sourcePath: str = ""
    generatedPath: str = ""
    isDirty: bool = False
    rowCount: int = 0
    enabledCount: int = 0
    errors: list[str] = field(default_factory=list)
    sourceErrors: list[str] = field(default_factory=list)
    validationErrors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows: list[_MaterialRowBrief] = field(default_factory=list)


ENVELOPE = {"runPackage", "materialsSourceMode", "geometrySourceMode", "materialDocument",
            "geometryDocument", "materialsSummary", "geometrySummary"}
REQUIRED = {"schema", "version", "runPackage", "materialsSourceMode", "geometrySourceMode",
            "materialsSummary", "geometrySummary", "runSettings", "pathSettings", "geometrySettings",
            "sourceSettings", "physicsSettings", "scoringSettings"}
LAYOUT = {
    "package_dir": ".", "config_dir": "config", "macro_dir": "macros", "logs_dir": "logs",
    "output_dir": "output", "main_ini_path": "config/main.ini", "run_macro_path": "macros/run.mac",
    "validation_report_path": "validation_report.txt", "project_snapshot_path": "project_snapshot.json",
    "materials_ini_path": "config/materials/material.ini", "geometry_ini_path": "config/geometry/geometry.ini",
}


def _closed_object(value, model, location, *, require_all=True):
    validate_dataclass_fields(value, model, location)
    if require_all:
        missing = set(model.__dataclass_fields__) - set(value)
        if missing:
            raise ValueError(f"Incomplete snapshot object {location}: missing {', '.join(sorted(missing))}")


def _lexical_path(value: str, location: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Snapshot path must be absolute and contain no parent traversal: {location}")
    # Do not resolve stored paths: legacy duplicate values may point to a
    # deleted old package and must never be read or followed.
    return Path(os.path.normpath(str(path)))


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _package_paths(record, root: Path, notes: list[str]):
    _closed_object(record, RunPackage, "snapshot.runPackage")
    stored = {key: _lexical_path(record[key], f"snapshot.runPackage.{key}") for key in LAYOUT}
    actual = {key: root / relative for key, relative in LAYOUT.items()}
    legacy = {"materials_ini_path", "geometry_ini_path"}
    for key in set(LAYOUT) - legacy:
        if not _same_path(stored[key], actual[key]):
            raise ValueError(f"Snapshot runPackage path contradicts the current standard package layout: {key}")
    mismatched = {key for key in legacy if not _same_path(stored[key], actual[key])}
    if mismatched:
        if mismatched != legacy:
            raise ValueError("Snapshot has a single contradictory material/geometry package path")
        roots = []
        for key in sorted(legacy):
            relative = Path(LAYOUT[key])
            candidate = stored[key]
            if tuple(candidate.parts[-len(relative.parts):]) != tuple(relative.parts):
                raise ValueError("Unrecognized legacy duplicate material/geometry path suffix")
            roots.append(candidate.parents[len(relative.parts) - 1])
        if not _same_path(roots[0], roots[1]) or _same_path(roots[0], root):
            raise ValueError("Legacy duplicate resource paths must form a pair from one old standard package")
        notes.append("Legacy duplicate material/geometry path pair was ignored; only the current package's standard files were read.")
    for key, path in actual.items():
        if path.exists() and not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Snapshot package path escapes through a symbolic link: {key}")
    return actual


def _validate_envelope(data):
    _closed_object(data["materialsSummary"], _MaterialsSummary, "snapshot.materialsSummary")
    materials = data["materialsSummary"]
    if materials["count"] != len(materials["materials"]) or materials["count"] < 0:
        raise ValueError("Snapshot materialsSummary count is inconsistent")
    for index, item in enumerate(materials["materials"]):
        _closed_object(item, _MaterialBrief, f"snapshot.materialsSummary.materials[{index}]")
        if item["components"] < 0:
            raise ValueError("Snapshot material component count must be nonnegative")
    _closed_object(data["geometrySummary"], _GeometrySummary, "snapshot.geometrySummary")
    for index, item in enumerate(data["geometrySummary"]["volumes"]):
        _closed_object(item, _VolumeBrief, f"snapshot.geometrySummary.volumes[{index}]")
        if item["booleanOps"] < 0:
            raise ValueError("Snapshot geometry boolean count must be nonnegative")
    for index, item in enumerate(data["geometrySummary"]["booleanOps"]):
        _closed_object(item, _BooleanBrief, f"snapshot.geometrySummary.booleanOps[{index}]")
        if item["index"] < 0:
            raise ValueError("Snapshot boolean index must be nonnegative")
    if "materialDocument" in data:
        document = data["materialDocument"]
        _closed_object(document, _MaterialDocumentBrief, "snapshot.materialDocument")
        if (document["rowCount"] != len(document["rows"]) or document["rowCount"] < 0
                or document["enabledCount"] != sum(row["enabled"] for row in document["rows"])):
            raise ValueError("Snapshot materialDocument row/enabled counts are inconsistent")
        for index, row in enumerate(document["rows"]):
            _closed_object(row, _MaterialRowBrief, f"snapshot.materialDocument.rows[{index}]")
            if row["components"] < 0:
                raise ValueError("Snapshot materialDocument component count must be nonnegative")
    for key, choices in (("materialsSourceMode", {"generated by Materials Editor", "copied from source"}),
                         ("geometrySourceMode", {"generated by Geometry Editor", "copied from source",
                                                  "copied from source (Geometry Editor validation bypassed)"})):
        if type(data[key]) is not str or data[key] not in choices:
            raise ValueError(f"Unsupported snapshot source mode: {key}")


def _read_inside(path: Path, root: Path, role: str, *, text=True) -> SnapshotInput:
    if not path.is_file():
        raise ValueError(f"Snapshot package resource is missing: {role}: {path}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Snapshot package resource escapes through a symbolic link: {role}")
    raw = path.read_bytes()
    if text:
        raw.decode("utf-8")
        if b"\x00" in raw:
            raise ValueError(f"Snapshot package text resource contains NUL: {role}")
    return SnapshotInput(role, str(path), digest(raw))


def _geometry_resources(summary, path: Path, root: Path):
    references = []
    for volume in summary.volumes:
        def property_value(key):
            current = getattr(volume, "shape_properties", {})
            legacy = getattr(volume, "preview_properties", {})
            if key in current and key in legacy and current[key] != legacy[key]:
                raise ValueError(f"Conflicting geometry resource properties: geometry.{volume.name}.{key} (shape_properties / preview_properties)")
            return current[key] if key in current else legacy.get(key)
        if volume.shape.strip().lower() in {"tessellated", "stl"}:
            value = property_value("file")
            if value is None:
                raise ValueError(f"Missing geometry resource declaration: geometry.{volume.name}.file")
            references.append((f"geometry.{volume.name}.file", value))
        if (property_value("placement") or "").strip().lower() in {"parameterised", "parameterized"}:
            value = property_value("copies_file")
            # The backend also supports inline copies + copy_step, which has
            # no external table. Only an explicit file creates a read receipt.
            if value is not None:
                references.append((f"geometry.{volume.name}.copies_file", value))
    if summary.template_hint.strip().lower() == "gdml":
        for section in parse_ini_light(path).sections:
            if section.name.lower() == "gdml":
                for key, value in section.values.items():
                    if key.lower() == "file": references.append(("geometry.gdml.file", value))
    result = []
    for role, value in references:
        resource = Path(value)
        if not resource.is_absolute(): resource = path.parent / resource
        result.append(_read_inside(resource, root, role, text=False))
    return result


def load_snapshot(path: str | Path) -> ProjectSnapshotLoad:
    from g4usim_gui.core.project import G4USimProject, project_from_dict
    source = Path(path).absolute()
    raw = source.read_bytes()
    data = load_json_strict(raw)
    if type(data) is not dict:
        raise ValueError("Snapshot JSON root must be an object")
    if not set(data).intersection(ENVELOPE):
        project = project_from_dict(data)
        return ProjectSnapshotLoad(project, "", (
            "Legacy plain-project snapshot: only recorded editor parameters were loaded; original resources and historical runtime results were not verified.",
        ), (), digest(raw))
    unknown = set(data) - set(G4USimProject.__dataclass_fields__) - ENVELOPE
    if unknown:
        raise ValueError("Unsupported snapshot field: snapshot." + sorted(unknown)[0])
    missing = REQUIRED - set(data)
    if missing:
        raise ValueError("Incomplete generated-package snapshot: " + ", ".join(sorted(missing)))
    if source.is_symlink() or source.name != "project_snapshot.json":
        raise ValueError("Package snapshot must be the standard non-symlink project_snapshot.json at its package root")
    # Ordinary project validation remains the single version/type/compatibility
    # policy. Only this adapter consumes the enumerated envelope fields.
    payload = {key: copy.deepcopy(value) for key, value in data.items() if key not in ENVELOPE}
    validate_dataclass_fields(normalize_project_data(payload), G4USimProject, "snapshot.project")
    _closed_object(data["runSettings"], RunSettings, "snapshot.runSettings")
    recorded_run = data["runSettings"]
    payload["threads"] = recorded_run["threads"]
    payload["seed"] = "" if recorded_run["seed"] is None else str(recorded_run["seed"])
    payload["runName"] = recorded_run["run_name"]
    project = project_from_dict(payload)
    _validate_envelope(data)
    geometry_record = None
    if "geometryDocument" in data:
        geometry_record = project_from_dict({"geometryEditor": data["geometryDocument"]}).geometryEditor
    bypass = data["geometrySourceMode"] == "copied from source (Geometry Editor validation bypassed)"
    if bypass and (geometry_record is None or not geometry_record.source_copy_mode):
        raise ValueError("Snapshot bypass source mode lacks its explicit GeometryDocument source_copy_mode choice")
    if geometry_record is not None and geometry_record.source_copy_mode != bypass:
        raise ValueError("Snapshot geometryDocument source_copy_mode contradicts its source mode")
    root = source.parent
    notes = []
    actual = _package_paths(data["runPackage"], root, notes)
    inputs = [_read_inside(actual[key], root, key) for key in
              ("materials_ini_path", "geometry_ini_path", "main_ini_path", "run_macro_path")]
    main_text=actual["main_ini_path"].read_bytes().decode("utf-8")
    imported=parse_run_editor_ini(main_text,source_path=actual["main_ini_path"],previous_source=project.sourceEditor)
    current_main=parse_ini_light(actual["main_ini_path"])
    # The fixed package paths above are the accepted material/geometry owners.
    # Refuse a CURRENT main that points somewhere else rather than importing
    # unrelated standard files while silently ignoring its declared targets.
    current_sections={}
    current_lines={}
    for section in current_main.sections:
        name=section.name.lower()
        values=current_sections.setdefault(name,{})
        for key,value in sorted(section.values.items(),key=lambda item:section.key_lines[item[0]]):
            values[key.lower()]=value
            current_lines[(name,key.lower())]=(section.name,section.key_lines[key])
    for name in ("materials","geometry"):
        if name in current_sections:
            key="file" if name=="materials" else "config"
            values=current_sections[name]
            if key in values:
                declared=Path(values[key])
                if not declared.is_absolute(): declared=actual["main_ini_path"].parent/declared
                expected=actual["materials_ini_path" if name=="materials" else "geometry_ini_path"]
                if not _same_path(declared.resolve(),expected.resolve()):
                    section_name,line=current_lines[(name,key)]
                    raise RunEditorImportError(actual["main_ini_path"],main_text,[ImportIssue(section_name,key,values[key],line,"CURRENT package resource path contradicts its standard layout")])
            if name=="geometry" and "template" in values: project.geometrySettings.template=values["template"]
    project.sourceEditor,project.physicsEditor=imported.source,imported.physics
    project.sourceSettings,project.physicsSettings=imported.source.to_settings(),imported.physics.to_settings()
    notes.extend(imported.notes)
    resources=[]
    if project.sourceEditor.phase_space_file:
        resources.append((project.sourceEditor,"phase_space_file","phase_space",True))
    for row in project.sourceEditor.gps_sources:
        if row.energy_type in {"histogram","points"}: resources.append((row,"spectrum_file","spectrum",False))
    for row in project.physicsEditor.fields:
        for key in ("magnetic_map","electric_map"):
            if getattr(row,key): resources.append((row,key,"field_map",False))
    for owner,key,role,multiple in resources:
        targets=[]
        for item in getattr(owner,key).split(",") if multiple else [getattr(owner,key)]:
            target=Path(item.strip())
            if not target.is_absolute(): target=actual["main_ini_path"].parent/target
            inputs.append(_read_inside(target,root,role,text=False))
            targets.append(str(target.resolve()))
        setattr(owner,key,",".join(targets))
    material_summary = parse_materials(actual["materials_ini_path"])
    if material_summary.errors:
        raise ValueError("Current package materials cannot be restored: " + "; ".join(material_summary.errors))
    geometry_summary = parse_geometry(actual["geometry_ini_path"], project.geometrySettings.template)
    if geometry_summary.errors:
        raise ValueError("Current package geometry cannot be restored: " + "; ".join(geometry_summary.errors))
    inputs.extend(_geometry_resources(geometry_summary, actual["geometry_ini_path"], root))
    project.pathSettings.materials_config = str(actual["materials_ini_path"])
    project.pathSettings.geometry_config = str(actual["geometry_ini_path"])
    project.geometrySettings.config_path = str(actual["geometry_ini_path"])
    project.geometryEditor = geometry_document_from_summary(geometry_summary, project.geometrySettings.template)
    project.geometryEditor.source_copy_mode = bypass
    project.geometryEditor.is_dirty = False
    # A run-package restore uses current package inputs, not the v7 project's
    # historical materials or unsaved UI drafts captured before generation.
    project.materialEditor = material_document_from_summary(material_summary)
    project.editingState = None
    # Flat mirrors must reflect the recorded run, not stale project-page values
    # that happened to exist before package generation.
    project.runName = project.runSettings.run_name
    project.threads = project.runSettings.threads
    project.seed = "" if project.runSettings.seed is None else str(project.runSettings.seed)
    project.runInputMode = "generated"
    project.runsRoot = str(root.parent)
    project.pathSettings.runs_root = str(root.parent)
    project.configPath = ""
    project.macroPath = ""
    project.outputDir = ""
    notes.extend((
        "Restored CURRENT package materials, geometry and main.ini source/physics/field/bias editors; run/scoring parameters remain snapshot-recorded. Validate and generate a new package before running.",
        "Unwritten disabled rows/editor drafts are not restored; materialDocument contains component counts, not a full recipe.",
        "Macro edits, final runtime EffectiveConfig and historical success are not restored or verified. CURRENT main.ini import is configuration evidence only.",
        "This snapshot format has no original resource hashes; current input hashes do not prove equality with historical run bytes.",
    ))
    for item in inputs:
        if digest(Path(item.path).read_bytes()) != item.sha256:
            raise ValueError("Snapshot package resource changed during loading: " + item.role)
    if source.read_bytes() != raw:
        raise ValueError("Snapshot JSON changed during loading")
    return ProjectSnapshotLoad(project, str(root), tuple(notes), tuple(inputs), digest(raw))
