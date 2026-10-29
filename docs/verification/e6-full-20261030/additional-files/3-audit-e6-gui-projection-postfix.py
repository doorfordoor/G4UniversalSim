"""Independent post-fix replay of immutable pre-fix inputs, plus legacy probes."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
from unittest.mock import patch
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/verification/e6-gui-projection-postfix"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget, QSpinBox, QComboBox, QLineEdit, QCheckBox, QPlainTextEdit
from g4usim_gui.core.project import G4USimProject, project_from_dict, project_to_dict, load_project
from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.window import project as project_window

original = ROOT / "out/verification/e6-gui-projection-review/cases.json"
original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
old = json.loads(original.read_text(encoding="utf-8"))
app = QApplication([])
app.setOrganizationName("E6IndependentPostfixReview")
app.setApplicationName("ProjectionPostfix")
app.setQuitOnLastWindowClosed(False)
run_history_store.STATE_PATH = OUT / "history.json"
rejects = {"negative-run-thread", "zero-run-thread", "negative-events", "negative-settings-bins", "zero-editor-bins-fallback",
           "negative-rays", "negative-preview-seed", "negative-trajectories", "over-rays", "over-preview-seed", "over-trajectories", "source-mode-conflict"}
payloads = [(row["name"], dict(projectName="incoming-" + row["name"], **row["incoming"]), row["name"] not in rejects)
            for row in old["results"]]
for name in ("flat_threads_huge", "run_threads_huge", "events_huge", "settings_hist_bins_huge", "editor_hist_bins_huge",
             "preview_rays_huge", "preview_seed_huge", "trajectories_huge", "flat_threads_clamped", "events_clamped", "hist_bins_clamped"):
    path = ROOT / "out/verification/e6-startpage-modal" / (name + ".json")
    payloads.append((name, json.loads(path.read_text(encoding="utf-8")), False))


def widget_digest(window):
    values = []
    for widget in window.findChildren(QWidget):
        if not isinstance(widget, (QSpinBox, QComboBox, QLineEdit, QCheckBox, QPlainTextEdit)): continue
        if isinstance(widget, QSpinBox): value = widget.value()
        elif isinstance(widget, QComboBox): value = [widget.currentIndex(), widget.currentText(), widget.currentData()]
        elif isinstance(widget, QCheckBox): value = widget.isChecked()
        elif isinstance(widget, QPlainTextEdit): value = widget.toPlainText()
        else: value = widget.text()
        values.append([type(widget).__name__, widget.objectName(), value])
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, default=str).encode()).hexdigest()


records = []
for index, (name, data, expected) in enumerate(payloads):
    source = OUT / f"input-{index}-{name}.json"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    raw_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    window = MainWindow()
    for timer in window.findChildren(QTimer): timer.stop()
    previous = window.project
    window.project_file = OUT / "old-current.json"
    window._generated_package_stale = False
    window._generated_package_dir = "keep-existing-package"
    before = widget_digest(window)
    errors = []
    with patch.object(project_window.QMessageBox, "critical", side_effect=lambda *_args: errors.append(_args[-1])), \
         patch.object(project_window.QMessageBox, "warning", side_effect=lambda *_args: errors.append(_args[-1])):
        accepted = window._load_project_path(str(source))
    assert accepted == expected, (name, accepted, errors)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == raw_hash
    row = dict(name=name, expected_accept=expected, accepted=accepted, errors=errors, source_unchanged=True)
    if not accepted:
        assert window.project is previous and window.project_file == OUT / "old-current.json", name
        assert window._generated_package_stale is False and window._generated_package_dir == "keep-existing-package", name
        assert before == widget_digest(window), name
        assert not window.project_page._building and not window.config_builder_page._building, name
        row["old_object_path_controls_building_package_unchanged"] = True
    else:
        page = window.config_builder_page
        if name == "empty-enums":
            assert page.source_editor_preset.currentIndex() == page.source_editor_angular_mode.currentIndex() == -1
            assert window.project.sourceEditor.preset == window.project.sourceEditor.angular_mode == ""
        if name == "empty-source-particle-fallback":
            assert window.project.sourceEditor.particle == ""
            assert window.project.sourceEditor.position_mode == "plane" and window.project.sourceEditor.source_shape == "rectangle"
            assert window.project.sourceEditor.preview_ray_count == 88
        if name in ("empty-physics-reference-fallback", "empty-physics-reference-list-rejected"):
            assert window.project.physicsEditor.mode == "manual" and window.project.physicsEditor.reference_list == ""
            assert page.physics_editor_reference.currentIndex() == -1
        if name == "empty-physics-reference-fallback": assert window.project.physicsEditor.enable_biasing_physics is True
        if name == "empty-physics-reference-list-rejected": assert window.project.physicsEditor.manual_modules == ["G4EmStandardPhysics"]
        if name == "unknown-enums":
            assert page.geometry_template.currentData() == "FutureTemplate"
            assert page.source_editor_position_type.currentText() == "FuturePosition"
            assert page.source_editor_angular_mode.currentText() == "FutureAngular"
            assert page.physics_editor_mode.currentText() == "FuturePhysics"
            assert page.physics_editor_reference.currentText() == "FutureReference"
        if name == "large-text-values": assert window.project.sourceEditor.energy == "1e309 MeV"
    records.append(row)
    for timer in window.findChildren(QTimer): timer.stop()
    window.close(); window.deleteLater(); app.processEvents()

legacy = []
for version in (None, 1, 2, 3, 4, 5, 6):
    base = {} if version is None else {"version": version}
    for alias in ("position_mode", "position_type"):
        for value in ("plane", "FuturePosition", ""):
            data = dict(base, sourceEditor={alias: value})
            frozen = copy.deepcopy(data)
            project = project_from_dict(data)
            assert data == frozen
            assert project.sourceEditor.position_mode == project.sourceEditor.position_type == value
            snapshot = project_to_dict(project)
            assert snapshot["sourceEditor"]["position_mode"] == snapshot["sourceEditor"]["position_type"] == value
            legacy.append(dict(version=version, alias=alias, value=value, accepted=True))
    default = project_from_dict(base)
    assert default.version == 6 and default.sourceEditor.particle == "proton"
    for pair in (("plane", "point"), ("", "point"), ("FuturePosition", "point")):
        try: project_from_dict(dict(base, sourceEditor=dict(position_mode=pair[0], position_type=pair[1])))
        except ValueError as error: assert "position_mode" in str(error) and "position_type" in str(error)
        else: assert False, (version, pair)

for supplied in ({"sourceEditor": {"particle": "", "preview_ray_count": 88}},
                 {"physicsEditor": {"reference_list": "", "enable_biasing_physics": True}},
                 {"scoringEditor": {"hist_bins": 0, "dose": True, "trajectory_events": 7}}):
    project = project_from_dict(supplied)
    for section, fields in supplied.items():
        for key, value in fields.items(): assert getattr(getattr(project, section), key) == value

caller = G4USimProject(sourceEditor=SourceEditableModel(position_mode="plane"))
assert caller.sourceEditor.position_type == "point"
exported = project_to_dict(caller)
assert exported["sourceEditor"]["position_mode"] == exported["sourceEditor"]["position_type"] == "plane"
assert caller.sourceEditor.position_type == "point" and caller.sourceEditor.position_mode == "plane"
assert project_from_dict(exported).sourceEditor.position_type == "plane"
assert hashlib.sha256(original.read_bytes()).hexdigest() == original_hash
(OUT / "result.json").write_text(json.dumps(dict(pre_fix_evidence=str(original), pre_fix_sha256=original_hash,
    gui_replays=records, legacy_alias_cases=legacy, export_copy_does_not_mutate_caller=True), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Independent GUI replays", len(records), "passed; version/alias cases", len(legacy), "passed; original evidence unchanged")
