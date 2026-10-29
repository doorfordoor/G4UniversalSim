"""Read-only independent GUI projection audit; no production/test edits."""
from pathlib import Path
import hashlib
import json
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/verification/e6-gui-projection-review"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox
from g4usim_gui.core.project import project_from_dict, project_to_dict
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow

app = QApplication([])
app.setOrganizationName("E6ReadOnlyProjectionAudit")
app.setApplicationName("ProjectionReview")
app.setQuitOnLastWindowClosed(False)
run_history_store.STATE_PATH = OUT / "history.json"
tracked = ("gui/g4usim_gui/core/project.py", "gui/g4usim_gui/core/project_migration.py",
           "gui/g4usim_gui/widgets/config_builder_page.py", "gui/g4usim_gui/widgets/config/run_config.py",
           "gui/g4usim_gui/window/project.py")
before = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in tracked}
cases = {
    "negative-run-thread": {"runSettings": {"threads": -1}},
    "zero-run-thread": {"runSettings": {"threads": 0}},
    "negative-events": {"runSettings": {"beam_on": -1}},
    "negative-settings-bins": {"scoringSettings": {"hist_bins": -1}},
    "zero-editor-bins-fallback": {"scoringEditor": {"hist_bins": 0, "dose": True, "trajectory_events": 7}},
    "negative-rays": {"sourceEditor": {"preview_ray_count": -1}},
    "negative-preview-seed": {"sourceEditor": {"random_seed_preview": -1}},
    "negative-trajectories": {"scoringEditor": {"trajectory_events": -1}},
    "over-rays": {"sourceEditor": {"preview_ray_count": 513}},
    "over-preview-seed": {"sourceEditor": {"random_seed_preview": 2147483648}},
    "over-trajectories": {"scoringEditor": {"trajectory_events": 1001}},
    "empty-physics-reference-list-rejected": {"physicsEditor": {"mode": "manual", "reference_list": "", "manual_modules": ["G4EmStandardPhysics"]}},
    "empty-physics-reference-fallback": {"physicsEditor": {"mode": "manual", "reference_list": "", "enable_biasing_physics": True}},
    "empty-source-particle-fallback": {"sourceEditor": {"particle": "", "position_mode": "plane", "source_shape": "rectangle", "preview_ray_count": 88}},
    "unknown-enums": {"geometrySettings": {"template": "FutureTemplate"}, "sourceEditor": {"position_mode": "FuturePosition", "angular_mode": "FutureAngular"}, "physicsEditor": {"mode": "FuturePhysics", "reference_list": "FutureReference"}},
    "empty-enums": {"sourceEditor": {"preset": "", "angular_mode": ""}},
    "large-text-values": {"sourceEditor": {"energy": "1e309 MeV", "direction": "1e309,0,1", "cone_half_angle": "1e309 rad"}},
    "source-mode-conflict": {"sourceEditor": {"position_mode": "plane", "position_type": "point", "source_shape": "rectangle", "halfx": "1 mm", "halfy": "1 mm"}},
}
results = []
for name, incoming in cases.items():
    data = dict(projectName="incoming-" + name, **incoming)
    try:
        candidate = project_from_dict(data)
    except Exception as error:
        results.append({"name": name, "incoming": incoming, "error": "Before UI: " + type(error).__name__ + ": " + str(error)})
        continue
    model_before = project_to_dict(candidate)
    window = MainWindow()
    for timer in window.findChildren(QTimer): timer.stop()
    page = window.config_builder_page
    row = {"name": name, "incoming": incoming, "loaded_projection": {key: model_before[key] for key in incoming},
           "spinner_limits": {}, "error": None}
    for key in ("threads", "beam_on", "hist_bins", "source_editor_preview_rays", "source_editor_preview_seed", "scoring_editor_trajectories", "scoring_editor_bins"):
        spinner = getattr(page, key)
        row["spinner_limits"][key] = [spinner.minimum(), spinner.maximum()]
    row["project_import_double_spinboxes"] = len(window.project_page.findChildren(QDoubleSpinBox)) + len(page.findChildren(QDoubleSpinBox))
    try:
        window._set_project(candidate)
        row["control_values"] = {key: getattr(page, key).value() for key in row["spinner_limits"]}
        row["enum_controls"] = {key: getattr(page, key).currentText() for key in ("source_editor_preset", "source_editor_position_type", "source_editor_shape", "source_editor_angular_mode", "physics_editor_mode", "physics_editor_reference")}
        row["geometry_template_control"] = page.geometry_template.currentData()
        after = project_to_dict(candidate)
        row["after_projection"] = {key: after[key] for key in incoming}
    except Exception as error:
        row["error"] = type(error).__name__ + ": " + str(error)
    row["builder_building"] = page._building
    results.append(row)
    for timer in window.findChildren(QTimer): timer.stop()
    window.close()
    window.deleteLater()
    app.processEvents()
assert before == {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in tracked}
(OUT / "cases.json").write_text(json.dumps(dict(product_hashes=before, results=results), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for r in results:
    print(r["name"], "error=", r["error"], "controls=", r.get("control_values"), "enums=", r.get("enum_controls"))
print("project/control double-spinbox count", results[0]["project_import_double_spinboxes"])
print("Production hashes unchanged; cases", len(results))
