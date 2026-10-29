"""Independent offscreen checks of the frontend guard; writes a new evidence root."""
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/verification/e6-frontend-guard-independent"
OUT.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT / "gui"))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QAbstractButton, QComboBox, QLineEdit, QSpinBox, QWidget
from g4usim_gui.core.project import project_from_dict, project_to_dict
from g4usim_gui.core.wizard import WizardSpec
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.window import project as project_window

FILES = ("gui/g4usim_gui/window/project.py", "gui/g4usim_gui/window/content.py",
         "gui/g4usim_gui/widgets/project_page.py", "gui/g4usim_gui/widgets/config_builder_page.py",
         "gui/g4usim_gui/widgets/config/run_config.py", "gui/g4usim_gui/widgets/migration_dialog.py")
def identities():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
before_hashes = identities()
app = QApplication.instance() or QApplication([])
app.setOrganizationName("E6IndependentFrontendGuard")
app.setApplicationName("ReadOnlyReview")
app.setQuitOnLastWindowClosed(False)
run_history_store.STATE_PATH = OUT / "history.json"
window = MainWindow()
for timer in window.findChildren(QTimer): timer.stop()
window.project_file = OUT / "original-project.json"
window._generated_package_stale = False
window._generated_package_dir = "independent-original-package"
widgets = window.findChildren(QWidget)
page = window.config_builder_page
facts = []


def capture():
    controls = []
    for item in widgets:
        if isinstance(item, QSpinBox): controls.append((id(item), "int", item.value()))
        elif isinstance(item, QLineEdit): controls.append((id(item), "text", item.text()))
        elif isinstance(item, QComboBox): controls.append((id(item), "combo", item.currentIndex(), item.currentText(), item.currentData()))
        elif isinstance(item, QAbstractButton): controls.append((id(item), "button", item.isChecked()))
    return copy.deepcopy((id(window.project), asdict(window.project), window.project_file,
                          window._generated_package_stale, window._generated_package_dir,
                          window.project_page._building, page._building, controls,
                          id(page.source_editor), id(page.physics_editor), id(page.scoring_editor), id(page.geometry_document)))


def set_field(data, name, value):
    parts = name.split(".")
    for part in parts[:-1]: data = data.setdefault(part, {})
    data[parts[-1]] = value


bindings = (
    ("threads", 1, 1024), ("runSettings.threads", 1, 1024),
    ("runSettings.beam_on", 0, 2_000_000_000), ("scoringSettings.hist_bins", 1, 10_000_000),
    ("scoringEditor.hist_bins", 1, 10_000_000), ("scoringEditor.trajectory_events", 0, 1000),
    ("sourceEditor.preview_ray_count", 1, 512), ("sourceEditor.random_seed_preview", 0, 2_147_483_647),
)
boxes = []
def dialog(kind):
    return lambda _parent, title, message, *_args, **_kwargs: boxes.append((kind, title, str(message)))


with patch.object(project_window.QMessageBox, "critical", side_effect=dialog("critical")), \
     patch.object(project_window.QMessageBox, "warning", side_effect=dialog("warning")):
    for mode in ("generated", "external"):
        for field, low, high in bindings:
            for value in (low - 1, high + 1, 10**100, -(10**100)):
                payload = {"projectName": "rejected independent review", "runInputMode": mode,
                           "scoringSettings": {"enabled": False}}
                set_field(payload, field, value)
                path = OUT / "rejected.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                raw = path.read_bytes()
                state = capture()
                boxes.clear()
                assert window._load_project_path(str(path)) is False
                assert capture() == state and path.read_bytes() == raw
                assert len(boxes) == 1 and boxes[0][0] == "critical" and field in boxes[0][2], (field, value, boxes)
                facts.append({"case": "reject-before-publish", "mode": mode, "field": field, "value": str(value)})
    # Direct callers cannot bypass the guard at _set_project.
    candidate = copy.deepcopy(window.project)
    candidate.runSettings.beam_on = -1
    state = capture()
    try: window._set_project(candidate)
    except ValueError: pass
    else: raise AssertionError("direct _set_project bypass")
    assert capture() == state
    facts.append({"case": "direct-set-project-guard", "unchanged": True})
    missing = OUT / "absent.json"
    for name, invoke, severity, title in (
        ("recent", lambda: window._open_recent_project(str(missing)), "warning", "Open recent project failed"),
        ("snapshot", lambda: window.load_snapshot_into_project(str(missing)), "warning", "Load snapshot failed"),
        ("normal", lambda: window._load_project_path(str(missing)), "critical", "Open project failed"),
    ):
        state = capture(); boxes.clear(); invoke()
        assert capture() == state and len(boxes) == 1 and boxes[0][:2] == (severity, title), boxes
        facts.append({"case": "original-error-severity", "entry": name, "severity": severity})
    for spec in (WizardSpec(threads=1025), WizardSpec(events=2_000_000_001)):
        state = capture(); boxes.clear()
        assert window.apply_simulation_wizard(spec, run_after=False) is False
        assert capture() == state and boxes[-1][0] == "warning"
        facts.append({"case": "wizard-refusal-before-in-place-apply", "unchanged": True})

# The guard accepts exact actual-range endpoints, independently of publication.
for field, low, high in bindings:
    for value in (low, high):
        payload = {}
        set_field(payload, field, value)
        candidate = project_from_dict(payload)
        window._check_project_projection(candidate)
        facts.append({"case": "inclusive-boundary-accepted", "field": field, "value": value})
unprojected = project_from_dict({"runSettings": {"seed": 10**100},
                               "scoringSettings": {"trajectory_events": 10**100},
                               "scoringEditor": {"trajectory_events": 0, "verbose": 10**100},
                               "geometryEditor": {"boolean_ops": [{"enabled": False, "index": 10**100}]}})
window._check_project_projection(unprojected)
facts.append({"case": "lineedit-and-unused-fields-have-no-spinbox-limit", "accepted": True})

# Compare exactly the guarded values before and after the real wizard's
# in-place application, without demanding unrelated path mirrors be equal.
checks = []
original_guard = window._check_project_projection
def observed_guard(candidate):
    original_guard(candidate)
    values = []
    for field, _low, _high in bindings:
        value = candidate
        for part in field.split("."): value = getattr(value, part)
        values.append(value)
    checks.append(values)
window._check_project_projection = observed_guard
object_identity = id(window.project)
assert window.apply_simulation_wizard(WizardSpec(project_name="independent wizard", threads=3, events=17), run_after=False)
assert len(checks) == 2 and checks[0] == checks[1] and id(window.project) == object_identity
facts.append({"case": "wizard-candidate-matches-in-place-guarded-values", "same_values": True, "same_project_identity": True})
window._check_project_projection = original_guard
window.close(); window.deleteLater()
after_hashes = identities()
assert after_hashes == before_hashes, "product files changed while independent review ran"
(OUT / "review.json").write_text(json.dumps({"scope": "offscreen independent frontend guard/state review; not visible UI or physical validation",
                                             "product_hashes": before_hashes, "product_unchanged": True,
                                             "facts": facts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Independent frontend guard review passed:", len(facts), "checks")
