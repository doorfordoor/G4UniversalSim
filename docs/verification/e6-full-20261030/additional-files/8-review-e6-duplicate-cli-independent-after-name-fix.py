"""Different-writer observations of helper/current GUI CLI copy startup."""
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
OUT = ROOT / "out/verification/e6-duplicate-cli-independent-after-name-fix"
OUT.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT / "gui")); sys.path.insert(0, str(ROOT / "scripts"))
from test_project_snapshot_compat import build_package_fixture
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox, QComboBox, QWidget
from g4usim_gui.history.run_package_actions import read_generated_run_settings
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.window import project as project_window

PRODUCTS = ("gui/g4usim_gui/history/run_package_actions.py", "gui/g4usim_gui/window/project.py",
            "gui/g4usim_gui/widgets/project_page.py", "gui/g4usim_gui/core/runner.py")
def hashes(): return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in PRODUCTS}
before_hashes = hashes()
app = QApplication.instance() or QApplication([])
app.setOrganizationName("E6IndependentCopyCLI")
app.setApplicationName("ReadOnlyReview")
app.setQuitOnLastWindowClosed(False)
run_history_store.STATE_PATH = OUT / "history.json"
window = MainWindow()
for timer in window.findChildren(QTimer): timer.stop()
facts = []
issues = []


def current():
    candidate = copy.deepcopy(window._default_project())
    candidate.executable = sys.executable
    candidate.runsRoot = str(OUT / "copies")
    candidate.threads = candidate.runSettings.threads = 7
    candidate.seed = "999"; candidate.runSettings.seed = 999
    candidate.runName = candidate.runSettings.run_name = "unrelated current"
    window._set_project(candidate)
    for timer in window.findChildren(QTimer): timer.stop()


def state():
    controls = []
    for item in window.findChildren(QWidget):
        if isinstance(item, QLineEdit): controls.append((id(item), item.text()))
        elif isinstance(item, QSpinBox): controls.append((id(item), item.value()))
        elif isinstance(item, QComboBox): controls.append((id(item), item.currentIndex(), item.currentText()))
    return copy.deepcopy((id(window.project), asdict(window.project), window.project_file,
                          window._generated_package_dir, window._generated_package_stale, controls,
                          window.project_page._building, window.config_builder_page._building))


def arg(command, key): return command[command.index(key) + 1] if key in command else None


for index, (label, seed, thread, name, accepted) in enumerate((
    ("missing-seed", None, "2", "snapshot_fixture", True),
    ("zero-seed", "0", "2", "snapshot_fixture", True),
    ("negative-zero-seed", "-0", "2", "snapshot_fixture", True),
    ("invalid-seed", "invalid", "2", "snapshot_fixture", False),
    ("gui-thread-upper-plus-one", "43", "1025", "snapshot_fixture", False),
    ("backend-thread-zero", "43", "0", "snapshot_fixture", False),
    ("missing-name", "43", "2", None, True),
    ("unicode-name-tail", "43", "2", "精确名字\u00a0", True),
)):
    folder = OUT / f"fixture-{index}"
    folder.mkdir()
    package, _ = build_package_fixture(folder, Path(sys.executable))
    main = Path(package.main_ini_path)
    raw = main.read_text(encoding="utf-8")
    raw = raw.replace("threads = 1\n", f"threads = {thread}\n", 1)
    raw = raw.replace("seed = 12345\n", "" if seed is None else f"seed = {seed}\n", 1)
    raw = raw.replace("name = snapshot_fixture\n", "" if name is None else f"name = {name}\n", 1)
    main.write_text(raw, encoding="utf-8", newline="\n")
    source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in Path(package.package_dir).rglob("*") if path.is_file()}
    helper = None; helper_error = None
    try: helper = asdict(read_generated_run_settings(package.package_dir))
    except ValueError as error: helper_error = str(error)
    current(); old = state()
    boxes, inspections, starts = [], [], []
    with patch.object(project_window.QMessageBox, "warning", side_effect=lambda _p, title, text, *_a: boxes.append((title, str(text)))), \
         patch.object(window._macro_inspection, "start", side_effect=lambda: inspections.append(list(window._macro_inspection.arguments()))), \
         patch.object(window.runner, "start", side_effect=lambda project, command: starts.append(list(command))):
        window.duplicate_history_package(package.package_dir, run_after=True)
        if accepted:
            assert not boxes and len(inspections) == 1, (label, boxes, inspections)
            plan = {"schema": "G4UniversalSimRunPlan", "version": 1,
                    "macro_plan": {"commands": [{"file": window.project.macroPath, "line": 1, "category": "beam_on", "text": "/run/beamOn 2"}]},
                    "initial_configuration": [], "macro_execution_planned": True}
            with patch.object(window._macro_inspection, "readAllStandardOutput", return_value=json.dumps(plan).encode()), \
                 patch.object(window._macro_inspection, "readAllStandardError", return_value=b""):
                window._on_macro_inspection_finished(0, QProcess.NormalExit)
            assert len(starts) == 1
            expected_seed = None if seed is None else str(int(seed))
            assert arg(starts[0], "--threads") == thread and arg(starts[0], "--seed") == expected_seed
            expected_name = name or None
            actual_name = arg(starts[0], "--run-name")
            if actual_name != expected_name:
                issues.append({"case": label, "helper_name": helper["run_name"], "expected_command_name": expected_name, "actual_command_name": actual_name})
            fact = {"case": label, "helper": helper, "inspect_arguments": inspections[0], "run_command": starts[0], "expected_name_preserved": actual_name == expected_name}
        else:
            assert boxes and not inspections and not starts and state() == old, (label, boxes)
            fact = {"case": label, "helper": helper, "helper_error": helper_error, "rejected_before_current_publication": True, "warning": boxes[0]}
    assert all(Path(path).read_bytes() and hashlib.sha256(Path(path).read_bytes()).hexdigest() == value for path, value in source_hashes.items())
    facts.append(fact)
window.close(); window.deleteLater()
assert hashes() == before_hashes
(OUT / "review.json").write_text(json.dumps({"scope": "offscreen actual Run/inspection callback; process launches intercepted, no physical run",
                                             "product_hashes": before_hashes, "product_unchanged": True, "facts": facts, "issues": issues}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Independent duplicate CLI review:", len(facts), "cases; issues:", len(issues))
for issue in issues: print(json.dumps(issue, ensure_ascii=False))
