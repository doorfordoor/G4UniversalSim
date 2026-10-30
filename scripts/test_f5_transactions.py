"""F5 pure editor history: atomic publication, raw drafts and writer semantics."""
from __future__ import annotations

import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from g4usim_gui.core.edit_snapshot import (
    WorkspaceSnapshot, clone_snapshot, project_for_snapshot, snapshot_fingerprint,
    snapshot_from_dict, snapshot_from_json, snapshot_size, snapshot_to_dict, snapshot_to_json,
)
from g4usim_gui.core.edit_state import empty_editing_state
from g4usim_gui.core.diagnostics import collect_diagnostics
from g4usim_gui.core.edit_transactions import (
    EditSession, TransactionApplyError, TransactionCapacityError, TransactionConflict,
)
from g4usim_gui.core.project import G4USimProject, SCHEMA_VERSION, load_project, project_from_dict, project_to_dict, save_project
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary, generate_materials_ini_text
from g4usim_gui.parsers.geometry_parser import parse_geometry_text
from g4usim_gui.parsers.materials_parser import parse_materials_text
from g4usim_gui.writers.geometry_ini_writer import generate_geometry_ini_text
from g4usim_gui.writers.package_writer import create_run_package
from g4usim_gui.validators.config_validator import validate_config_builder
from g4usim_gui.models.package_model import GeometrySettings, PathSettings

MATERIALS = """# material source retained, including ordered definitions
[element.MySi]
symbol = Si
z = 14
a = 28.0855 g/mole
[material.Mixed]
density = 2.33 g/cm3
components = MySi:1
"""
GEOMETRY = """[global]
version = 2
[world]
shape = box
size = 10 cm,10 cm,10 cm
material = G4_AIR
[volume.target]
parent = world
shape = box
size = 1 cm,1 cm,1 cm
material = Mixed
position = 0,0,0 mm
sensitive = true
"""


def rejected(action, fragment=""):
    try:
        action()
    except (ValueError, OSError) as error:
        assert fragment in str(error), str(error)
        return error
    assert False, "Invalid edit or payload unexpectedly accepted"


def fixture() -> WorkspaceSnapshot:
    project = G4USimProject(projectName="事务中文", seed="1e", threads=3)
    project.runSettings.seed = None
    project.runSettings.run_name = ""
    project.pathSettings.executable = ""
    project.executable = "backend"
    material_summary = parse_materials_text(MATERIALS, source_path="/missing/materials.ini")
    geometry_summary = parse_geometry_text(GEOMETRY, source_path="/missing/geometry.ini", template_name="hierarchical")
    project.materialEditor = material_document_from_summary(material_summary)
    project.materialEditor.is_dirty = True
    project.geometryEditor = geometry_document_from_summary(geometry_summary, "hierarchical")
    project.geometryEditor.is_dirty = True
    state = empty_editing_state()
    state["drafts"] = {"project.seed": "1e", "config.source_energy": " 1 GeV ", "config.seed": "--"}
    state["tables"] = {"geometry_table": [["target", "incomplete, size"]]}
    state["selections"] = {"geometry_table": 1}
    state["sources"] = {
        "materials": {"path": material_summary.path, "text": MATERIALS, "read_success": True, "template": ""},
        "geometry": {"path": geometry_summary.path, "text": GEOMETRY, "read_success": True, "template": "hierarchical"},
    }
    return WorkspaceSnapshot(project, state, {"materials": material_summary, "geometry": geometry_summary})


def changed(snapshot, name):
    result = clone_snapshot(snapshot)
    result.project.projectName = name
    return result


def persistence_contract():
    original = fixture()
    decoded = snapshot_from_json(snapshot_to_json(original))
    assert snapshot_fingerprint(decoded) == snapshot_fingerprint(original)
    assert decoded.project.seed == "1e" and decoded.project.runSettings.seed is None
    assert decoded.project.runSettings.run_name == ""
    assert decoded.project.pathSettings.executable == "" and decoded.project.executable == "backend"
    assert decoded.project.runSettings.threads == 1 and decoded.project.threads == 3
    assert decoded.project.geometryEditor.raw_source_text == GEOMETRY
    assert decoded.project.materialEditor.raw_source_text == MATERIALS
    assert decoded.project.materialEditor.rows[0].components_text == original.project.materialEditor.rows[0].components_text
    assert decoded.project.materialEditor.preserved_sections == original.project.materialEditor.preserved_sections
    assert decoded.project.materialEditor.is_dirty and decoded.project.geometryEditor.is_dirty
    assert decoded.state == original.state and decoded.transient == {}
    assert original.transient["materials"].raw_text == MATERIALS
    invalid_material = clone_snapshot(original)
    invalid_material.project.materialEditor.rows[0].density = float("inf")
    rejected(lambda: project_to_dict(invalid_material.project), "density")
    encoded = snapshot_to_dict(original)
    for mutate in (
        lambda data: data.update(unknown=1),
        lambda data: data.update(version=True),
        lambda data: data.update(version=2),
        lambda data: data["project"].pop("sourceEditor"),
        lambda data: data["project"]["materialEditor"].pop("raw_source_text"),
        lambda data: data["project"]["geometryEditor"]["simple_box"].pop("world_size"),
        lambda data: data["project"].update(editingState=empty_editing_state()),
        lambda data: data["state"].update(unknown=[]),
        lambda data: data["state"]["drafts"].update(unexpected_value=float("nan")),
        lambda data: data["state"]["drafts"].update(unexpected_value={"code": "arbitrary"}),
        lambda data: data["state"]["selections"].update(geometry_table=True),
        lambda data: data["state"]["tables"].update(geometry_table=[[False]]),
        lambda data: data["state"]["sources"]["materials"].update(read_success=1),
        lambda data: data["state"]["sources"].update(unknown={}),
        lambda data: data["project"]["materialEditor"]["rows"][0].update(unknown=1),
    ):
        invalid = copy.deepcopy(encoded)
        mutate(invalid)
        rejected(lambda invalid=invalid: snapshot_from_dict(invalid))
    raw = snapshot_to_json(original)
    duplicate = raw.replace(b'"schema":', b'"schema":"duplicate","schema":', 1)
    rejected(lambda: snapshot_from_json(duplicate), "Duplicate")
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "project.json"
        save_project(project_for_snapshot(original), path)
        loaded = load_project(path)
        assert loaded.version == SCHEMA_VERSION == 7
        assert asdict(loaded.materialEditor) == asdict(original.project.materialEditor)
        assert asdict(loaded.geometryEditor) == asdict(original.project.geometryEditor)
        assert loaded.editingState == original.state
        before = path.read_bytes()
        with patch("g4usim_gui.core.project.os.replace", side_effect=OSError("injected replace")):
            rejected(lambda: save_project(changed(original, "changed").project, path), "injected replace")
        assert path.read_bytes() == before
        assert not list(path.parent.glob(".project.json.*.tmp"))
    for version in range(1, SCHEMA_VERSION):
        legacy = project_from_dict({"version": version, "seed": "42", "runSettings": {"seed": None}})
        assert legacy.runSettings.seed == 42 and legacy.materialEditor is None and legacy.editingState is None
    empty = G4USimProject()
    empty.materialEditor = type(original.project.materialEditor)()
    assert project_from_dict(project_to_dict(empty)).materialEditor is not None
    assert project_from_dict(project_to_dict(empty)).materialEditor.rows == []


def history_contract():
    initial = fixture()
    history = EditSession(initial)
    initial.project.materialEditor.rows[0].components[0].name = "changed outside"
    assert history.current().project.materialEditor.rows[0].components[0].name != "changed outside"
    exposed = history.current()
    exposed.project.sourceEditor.energy = "outside"
    assert history.current().project.sourceEditor.energy != "outside"
    original = history.current()
    history.replace("name", changed(original, "first"))
    assert history.can_undo and not history.can_redo and history.is_modified
    assert history.undo_label == "name" and history.revision == 1
    history.undo()
    assert not history.is_modified and history.can_redo and history.revision == 2
    history.redo()
    history.mark_saved()
    assert not history.is_modified
    saved = history.current()
    history.replace("second", changed(saved, "second"))
    history.undo()
    assert not history.is_modified and history.can_redo
    history.replace("branch", changed(saved, "branch"))
    assert not history.can_redo and history.is_modified
    history.mark_saved(saved)
    assert history.is_modified
    history.undo()
    assert not history.is_modified
    revision = history.revision
    count = history.history_count
    selected = history.current()
    selected.state["selections"]["geometry_table"] = 0
    selected.project.geometryEditor.errors.append("derived warning")
    history.replace("derived", selected)
    assert history.revision == revision and history.history_count == count and history.can_redo
    rejected(lambda: history.replace("stale", changed(saved, "stale"), expected_revision=revision - 1), "changed")
    assert history.revision == revision and history.can_redo

    def broken(candidate):
        candidate.project.materialEditor.rows.clear()
        raise ValueError("group failed")
    rejected(lambda: history.transact("group", broken), "group failed")
    assert snapshot_fingerprint(history.current()) == snapshot_fingerprint(saved)
    assert history.revision == revision and history.can_redo
    rejected(lambda: history.transact("nested", lambda candidate: history.undo()), "Nested")
    assert history.revision == revision
    history.transact("automation", lambda candidate: setattr(candidate.project.sourceEditor, "energy", "1 GeV"), expected_revision=revision)
    assert history.current().project.sourceEditor.energy == "1 GeV" and not history.can_redo
    history.undo()
    assert history.current().project.sourceEditor.energy == saved.project.sourceEditor.energy


def grouping_and_capacity():
    initial = fixture()
    history = EditSession(initial, max_commands=2)
    for name in ("a", "ab", "abc"):
        history.replace("type", changed(initial, name), merge_key="project.name")
    assert history.history_count == 1
    history.mark_saved()
    saved = history.current()
    history.replace("type", changed(initial, "abcd"), merge_key="project.name")
    assert history.history_count == 2
    history.undo()
    assert not history.is_modified
    history.break_merge()
    for name in ("x", "y", "z"):
        history.replace("new name", changed(initial, name))
    assert history.history_count == 2
    history.undo()
    history.undo()
    assert not history.can_undo and history.is_modified
    history.mark_saved(saved)
    assert history.is_modified
    history.reset(saved, saved=True)
    assert not history.can_undo and not history.can_redo and not history.is_modified
    small = EditSession(initial, max_bytes=snapshot_size(initial) + 1)
    before = small.current()
    rejected(lambda: small.replace("too large", changed(initial, "large")), "capacity")
    assert small.revision == 0 and not small.can_undo
    assert snapshot_fingerprint(small.current()) == snapshot_fingerprint(before)
    history = EditSession(initial)
    history.replace("type", changed(initial, "x"), merge_key="name")
    history.replace("type", initial, merge_key="name")
    assert not history.can_undo and not history.is_modified and history.revision == 2


def projection_failure():
    initial = fixture()
    history = EditSession(initial)
    seen = []

    def fails_once(candidate):
        seen.append(candidate.project.projectName)
        if len(seen) == 1:
            raise ValueError("projection failure")
    error = rejected(lambda: history.replace("publish", changed(initial, "new"), apply=fails_once), "projection failure")
    assert isinstance(error, TransactionApplyError) and error.rollback is None
    assert seen == ["new", initial.project.projectName]
    assert history.revision == 0 and not history.can_undo and not history.is_modified
    def always_fails(candidate):
        raise ValueError("view unavailable")
    error = rejected(lambda: history.replace("publish", changed(initial, "new"), apply=always_fails), "restoring")
    assert error.rollback is not None and history.revision == 0
    history.replace("publish", changed(initial, "new"))
    seen.clear()
    rejected(lambda: history.undo(apply=fails_once), "projection failure")
    assert history.current().project.projectName == "new" and history.revision == 1 and not history.can_redo
    history.undo()
    seen.clear()
    rejected(lambda: history.redo(apply=fails_once), "projection failure")
    assert history.current().project.projectName == initial.project.projectName and history.revision == 2 and history.can_redo


def fingerprint_checkpoint(history):
    current = history.current()
    actual = snapshot_fingerprint(current)
    assert history._current_fingerprint == actual
    assert history.is_modified == (actual != history.saved_fingerprint)
    return (snapshot_to_json(current), actual, history.saved_fingerprint,
            history.revision, history.history_count, history.history_bytes,
            history.can_undo, history.can_redo, history.undo_label, history.redo_label)


def fingerprint_cache_isolation():
    """Dirty queries reuse only private state; mutable public copies cannot alter it."""
    initial = fixture()
    saved = clone_snapshot(initial)
    history = EditSession(initial)
    baseline = fingerprint_checkpoint(history)
    initial.project.materialEditor.rows[0].components.clear()
    initial.state['drafts']['config.seed'] = 'external input change'
    exposed = history.current()
    exposed.project.sourceEditor.energy = 'external output change'
    exposed.state['tables']['geometry_table'][0][1] = 'external table change'
    assert fingerprint_checkpoint(history) == baseline

    with patch('g4usim_gui.core.edit_transactions.snapshot_fingerprint', wraps=snapshot_fingerprint) as digest:
        assert not history.is_modified
        assert not history.is_modified
        history.mark_saved()
        assert not history.is_modified
        assert digest.call_count == 0
        history.mark_saved(saved)
        assert digest.call_count == 1
        # Even a no-op external candidate must still be cloned and validated.
        history.replace('no-op', history.current())
        assert digest.call_count == 2
    assert fingerprint_checkpoint(history) == baseline

    candidate = changed(saved, 'published')
    callback_copies = []
    def projection(view):
        callback_copies.append(view)
        view.project.projectName = 'projection only'
        view.state['drafts']['config.seed'] = 'projection only'
    returned = history.replace('publish', candidate, apply=projection)
    published = fingerprint_checkpoint(history)
    assert history.current().project.projectName == 'published' and history.is_modified
    candidate.project.projectName = 'caller retained input'
    returned.project.projectName = 'caller retained return'
    callback_copies[0].project.materialEditor.rows.clear()
    assert fingerprint_checkpoint(history) == published

    escaped = []
    def transform(draft):
        escaped.append(draft)
        draft.state['drafts']['config.seed'] = 'unfinished-'
    returned = history.transact('raw draft', transform)
    transformed = fingerprint_checkpoint(history)
    escaped[0].state['drafts']['config.seed'] = 'escaped transform'
    returned.state['drafts']['config.seed'] = 'escaped return'
    assert fingerprint_checkpoint(history) == transformed
    assert history.current().state['drafts']['config.seed'] == 'unfinished-'


def fingerprint_saved_cursor():
    initial = fixture()
    history = EditSession(initial, saved=False)
    assert history.is_modified and history.saved_fingerprint is None
    fingerprint_checkpoint(history)
    history.mark_saved()
    assert not history.is_modified
    history.replace('first', changed(initial, 'first'))
    fingerprint_checkpoint(history)
    first = history.current()
    history.mark_saved(first)
    assert not history.is_modified
    history.replace('second', changed(initial, 'second'))
    second = fingerprint_checkpoint(history)
    assert history.is_modified
    history.undo()
    fingerprint_checkpoint(history)
    assert not history.is_modified
    history.redo()
    assert fingerprint_checkpoint(history)[:3] == second[:3]
    assert history.is_modified
    history.mark_saved(initial)
    assert history.saved_fingerprint == snapshot_fingerprint(initial) and history.is_modified
    history.undo()
    fingerprint_checkpoint(history)
    assert history.is_modified
    history.undo()
    fingerprint_checkpoint(history)
    assert not history.is_modified
    returned = history.reset(first, saved=False)
    reset = fingerprint_checkpoint(history)
    returned.project.projectName = 'reset return changed'
    assert fingerprint_checkpoint(history) == reset
    assert history.is_modified and history.saved_fingerprint is None
    history.reset(initial, saved=True)
    fingerprint_checkpoint(history)
    assert not history.is_modified and not history.can_undo and not history.can_redo
    history.replace('merge', changed(initial, 'merge away'), merge_key='name')
    history.replace('merge', initial, merge_key='name')
    fingerprint_checkpoint(history)
    assert not history.is_modified and not history.can_undo


def fingerprint_failed_publication():
    initial = fixture()
    for operation in ('replace', 'undo', 'redo', 'reset'):
        history = EditSession(initial)
        history.replace('first', changed(initial, 'first'))
        history.mark_saved()
        history.replace('second', changed(initial, 'second'))
        if operation == 'redo':
            history.undo()
        baseline = fingerprint_checkpoint(history)
        def publish(apply):
            if operation == 'replace':
                return history.replace('third', changed(initial, 'third'), apply=apply)
            if operation == 'reset':
                return history.reset(initial, apply=apply)
            return getattr(history, operation)(apply=apply)
        for double_failure in (False, True):
            calls = []
            def projection(view):
                calls.append(view.project.projectName)
                view.project.projectName = 'mutated failed projection'
                if len(calls) == 1 or double_failure:
                    raise ValueError('projection/cache fault')
            error = rejected(lambda: publish(projection), 'projection/cache fault')
            assert isinstance(error, TransactionApplyError)
            assert (error.rollback is not None) == double_failure and len(calls) == 2
            assert fingerprint_checkpoint(history) == baseline
        # New-state hash failure is detected before a projection can alter UI.
        calls = []
        with patch('g4usim_gui.core.edit_transactions.snapshot_fingerprint', side_effect=ValueError('digest fault')):
            rejected(lambda: publish(lambda view: calls.append(view)), 'digest fault')
        assert not calls
        assert fingerprint_checkpoint(history) == baseline

    history = EditSession(initial, max_bytes=snapshot_size(initial) + 1)
    baseline = fingerprint_checkpoint(history)
    rejected(lambda: history.replace('too large', changed(initial, 'large')), 'capacity')
    rejected(lambda: history.reset(changed(initial, 'x' * 4096)), 'capacity')
    rejected(lambda: history.replace('stale', initial, expected_revision=-1), 'changed')
    invalid = history.current()
    invalid.project.threads = True
    rejected(lambda: history.replace('invalid type', invalid), 'threads')
    rejected(lambda: history.mark_saved(invalid), 'threads')
    assert fingerprint_checkpoint(history) == baseline


def writer_semantics():
    original = fixture()
    history = EditSession(original)
    materials_before = generate_materials_ini_text(history.current().project.materialEditor)
    geometry_before = generate_geometry_ini_text(history.current().project.geometryEditor)
    candidate = history.current()
    candidate.project.materialEditor.rows[0].density = "4 g/cm3"
    candidate.project.geometryEditor.volumes[-1].size = "2 cm,2 cm,2 cm"
    candidate.state["drafts"]["config.seed"] = "unfinished-"
    history.replace("compound geometry/material edit", candidate)
    assert generate_materials_ini_text(history.current().project.materialEditor) != materials_before
    assert generate_geometry_ini_text(history.current().project.geometryEditor) != geometry_before
    history.undo()
    assert generate_materials_ini_text(history.current().project.materialEditor) == materials_before
    assert generate_geometry_ini_text(history.current().project.geometryEditor) == geometry_before
    assert history.current().state["drafts"]["config.seed"] == "--"
    history.mark_saved()
    assert history.current().project.materialEditor.is_dirty and history.current().project.geometryEditor.is_dirty
    candidate = history.current()
    candidate.project.geometryEditor.source_errors = ["source schema error"]
    candidate.project.geometryEditor.round_trip_blockers = ["unknown source property"]
    history.replace("source rejected", candidate)
    rejected(lambda: generate_geometry_ini_text(history.current().project.geometryEditor))
    history.undo()
    history.redo()
    assert history.current().project.geometryEditor.source_errors == ["source schema error"]
    assert history.current().project.geometryEditor.round_trip_blockers == ["unknown source property"]
    candidate = history.current()
    candidate.project.geometryEditor.source_copy_mode = True
    history.replace("explicit source copy", candidate)
    history.undo()
    assert not history.current().project.geometryEditor.source_copy_mode


def source_constraint_contract():
    """Persisted diagnostic caches cannot waive captured source constraints."""
    with tempfile.TemporaryDirectory(prefix='f5-source-constraints-') as temp:
        folder = Path(temp)
        material_path, geometry_path = folder / 'materials.ini', folder / 'geometry.ini'
        material_text, geometry_text = MATERIALS + 'unknown_parameter = 7\n', GEOMETRY + 'placement = replica\n'
        material_path.write_text(material_text, encoding='utf-8')
        geometry_path.write_text(geometry_text, encoding='utf-8')
        executable = folder / 'validation-only-backend'
        executable.write_bytes(b'not executed')
        project = G4USimProject()
        project.materialEditor = material_document_from_summary(parse_materials_text(material_text, source_path=material_path))
        project.geometryEditor = geometry_document_from_summary(parse_geometry_text(geometry_text, source_path=geometry_path, template_name='hierarchical'))
        project.materialEditor.is_dirty = project.geometryEditor.is_dirty = True
        project.geometrySettings = GeometrySettings(template='hierarchical', config_path=str(geometry_path))
        project.pathSettings = PathSettings(executable=str(executable), workspace_root=str(folder), runs_root=str(folder / 'runs'),
                                           materials_config=str(material_path), geometry_config=str(geometry_path))
        state = empty_editing_state()
        state['drafts']['config.seed'] = 'unfinished-'
        state['sources'] = {
            'materials': {'path': str(material_path), 'text': material_text, 'read_success': True, 'template': ''},
            'geometry': {'path': str(geometry_path), 'text': geometry_text, 'read_success': True, 'template': 'hierarchical'},
        }
        original = WorkspaceSnapshot(project, state)
        wire = snapshot_to_dict(original)
        for kind in ('materialEditor', 'geometryEditor'):
            wire['project'][kind]['source_errors'] = []
            wire['project'][kind]['errors'] = []
        wire['project']['geometryEditor']['round_trip_blockers'] = []
        restored = snapshot_from_dict(wire)
        assert restored.project.materialEditor.source_errors == original.project.materialEditor.source_errors
        assert restored.project.geometryEditor.round_trip_blockers == original.project.geometryEditor.round_trip_blockers
        assert restored.state['drafts']['config.seed'] == 'unfinished-'
        rejected(lambda: generate_materials_ini_text(restored.project.materialEditor), 'unknown_parameter')
        rejected(lambda: generate_geometry_ini_text(restored.project.geometryEditor), 'placement')
        assert any(d.code == 'materials.source.unknown_key' and d.source.line == 9
                   for d in getattr(restored.project.materialEditor, '_f4_source_diagnostics', ()))
        kwargs = dict(paths=project.pathSettings, run=project.runSettings, geometry=project.geometrySettings,
                      source=project.sourceSettings, physics=project.physicsSettings, scoring=project.scoringSettings,
                      source_model=project.sourceEditor, physics_model=project.physicsEditor, scoring_model=project.scoringEditor)
        report = validate_config_builder(**kwargs, material_document=restored.project.materialEditor,
                                        geometry_document=restored.project.geometryEditor)
        assert not report.can_run
        assert any(d.code == 'materials.source.unknown_key' for d in collect_diagnostics(report))
        assert any('placement' in error for error in report.errors)

        # Ordinary v7 load, an omitted redundant source map, and transaction
        # callers all enforce the same parser facts without losing user drafts.
        ordinary = copy.deepcopy(wire['project'])
        ordinary['editingState'] = copy.deepcopy(state)
        loaded = project_from_dict(ordinary)
        assert loaded.materialEditor.source_errors and loaded.geometryEditor.round_trip_blockers
        ordinary['editingState'] = None
        loaded = project_from_dict(ordinary)
        assert loaded.materialEditor.source_errors and loaded.geometryEditor.round_trip_blockers
        for old_version in range(1, 7):
            downgraded = copy.deepcopy(ordinary)
            downgraded['version'] = old_version
            loaded = project_from_dict(downgraded)
            assert loaded.materialEditor.source_errors == original.project.materialEditor.source_errors
            assert loaded.geometryEditor.round_trip_blockers == original.project.geometryEditor.round_trip_blockers
            rejected(lambda: generate_materials_ini_text(loaded.materialEditor), 'unknown_parameter')
            rejected(lambda: generate_geometry_ini_text(loaded.geometryEditor), 'placement')
            downgraded['geometryEditor']['source_copy_mode'] = True
            copied = project_from_dict(downgraded)
            assert copied.geometryEditor.source_copy_mode and copied.geometryEditor.round_trip_blockers
            downgraded['materialEditor']['unknown_future_field'] = 'still rejected'
            rejected(lambda: project_from_dict(downgraded), 'unknown_future_field')
            # Actual old projects omit source text and full editor snapshots;
            # absence still means legacy reload, never an invented empty editor.
            legacy = project_from_dict({'schema': 'G4UniversalSimProject', 'version': old_version,
                                        'seed': '21', 'runSettings': {'seed': None}})
            assert legacy.materialEditor is None and legacy.editingState is None
            assert legacy.runSettings.seed == 21
            assert legacy.geometryEditor.raw_source_text == '' and not legacy.geometryEditor.round_trip_blockers
        history = EditSession(restored)
        def clear_cache(candidate):
            candidate.project.materialEditor.source_errors = []
            candidate.project.materialEditor.errors = []
            candidate.project.geometryEditor.round_trip_blockers = []
            candidate.project.materialEditor.rows[0].density = 'raw-invalid-density'
        history.transact('edit with cleared caches', clear_cache)
        assert history.current().project.materialEditor.rows[0].density == 'raw-invalid-density'
        assert history.current().project.materialEditor.source_errors
        assert history.current().project.geometryEditor.round_trip_blockers
        history.undo()
        history.redo()
        assert history.current().project.materialEditor.rows[0].density == 'raw-invalid-density'

        conflict = copy.deepcopy(wire)
        conflict['state']['sources']['materials']['text'] = MATERIALS
        rejected(lambda: snapshot_from_dict(conflict), 'disagrees')
        material_path.write_text(MATERIALS, encoding='utf-8')
        geometry_path.unlink()
        with patch.object(Path, 'read_text', side_effect=AssertionError('unexpected source reread')):
            restored = snapshot_from_dict(wire)
        assert restored.project.materialEditor.source_errors and restored.project.geometryEditor.round_trip_blockers

        # Explicit original-source copy remains available and copies the exact
        # unsupported geometry; it never routes through the lossy editor writer.
        geometry_path.write_text(geometry_text, encoding='utf-8')
        copy_project = copy.deepcopy(project)
        copy_project.materialEditor = material_document_from_summary(parse_materials_text(MATERIALS, source_path=material_path))
        copy_project.materialEditor.is_dirty = True
        copy_project.geometryEditor.source_copy_mode = True
        copy_state = copy.deepcopy(state)
        copy_state['sources']['materials']['text'] = MATERIALS
        copy_snapshot = snapshot_from_json(snapshot_to_json(WorkspaceSnapshot(copy_project, copy_state)))
        assert copy_snapshot.project.geometryEditor.source_copy_mode
        assert copy_snapshot.project.geometryEditor.round_trip_blockers
        package, _ = create_run_package(project=copy_snapshot.project, **kwargs,
                                        material_document=copy_snapshot.project.materialEditor,
                                        geometry_document=copy_snapshot.project.geometryEditor)
        assert Path(package.geometry_ini_path).read_bytes() == geometry_path.read_bytes()
        assert b'placement = replica' in Path(package.geometry_ini_path).read_bytes()
        assert material_path.read_text(encoding='utf-8') == MATERIALS

        # Failed capture does not become a successful empty parse, even if its
        # serialized error cache is cleared. Source-only diagnostics stay typed.
        failed = copy.deepcopy(wire)
        failed['project']['materialEditor']['raw_source_text'] = ''
        failed['state']['sources']['materials'].update(text='', read_success=False)
        restored = snapshot_from_dict(failed)
        assert restored.project.materialEditor.source_errors
        records = restored.project.materialEditor._f4_source_diagnostics
        assert records and all(d.code == 'ini.read_failed' and d.source.text_snapshot is None for d in records)


def main():
    persistence_contract()
    history_contract()
    grouping_and_capacity()
    projection_failure()
    fingerprint_cache_isolation()
    fingerprint_saved_cursor()
    fingerprint_failed_publication()
    writer_semantics()
    source_constraint_contract()
    print("F5 transactions: persistence, failure atomicity, branching, capacity and writer semantics passed")


if __name__ == "__main__":
    main()
