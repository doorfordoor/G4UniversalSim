"""Export Geant4 project: the Project menu action writes a standalone tree (GUI only)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
sys.path.insert(0, str(ROOT / "gui" / "smoke_tests"))

from PySide6.QtCore import QSettings  # noqa: E402

_settings_dir = tempfile.mkdtemp(prefix="g4usim-export-project-")
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _settings_dir)
QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, _settings_dir)

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([sys.argv[0]])
app.setStyle("Fusion")

from g4usim_gui.core import theme  # noqa: E402
from g4usim_gui.core import wizard  # noqa: E402
from g4usim_gui.core.export_project import verify_export  # noqa: E402
from g4usim_gui.core.project import G4USimProject  # noqa: E402
from gui_test_window import MainWindow  # noqa: E402

theme.apply_theme(app, "light")

EXAMPLES = ROOT / "examples" / "07_parallel_world_box"
window = MainWindow(recovery_root=Path(_settings_dir) / "recovery", offer_recovery=False)
window.show()
app.processEvents()

# --- The Project menu and its action exist ---------------------------------
menu = window.project_menu
assert menu is not None
assert window.export_project_action is not None
assert window.export_project_action.text() == "Export Geant4 project...", \
    window.export_project_action.text()
assert any(action is menu.menuAction() for action in window.menuBar().actions())

# --- A blank project cannot export, and says why ---------------------------
window.project = G4USimProject()
window.refresh_export_project_action()
assert not window.export_project_action.isEnabled()
reason = window.export_project_action.toolTip()
assert "geometry" in reason, reason

# --- A generated single-target project enables and exports -----------------
window.apply_simulation_wizard(wizard.default_spec("single_target"), run_after=False)
window.refresh_export_project_action()
assert window.export_project_action.isEnabled(), \
    window.export_project_action.toolTip()
work = Path(tempfile.mkdtemp(prefix="g4usim-export-project-out-"))
generated_dest = work / "generated"
result = window._export_project_to(generated_dest, interactive=False)
assert result is not None
manifest = json.loads((generated_dest / "export-manifest.json").read_text(encoding="utf-8"))
digest = manifest["identity"]["digest"]
assert result["payload_identity"]["digest"] == digest
assert result["destination"] == str(generated_dest)
assert len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)
for relative in ("project/main.ini", "project/config/materials.ini",
                 "project/config/geometry.ini", "project/macros/run.mac",
                 "README-EXPORT.md", "CMakeLists.txt", "export-template-manifest.json"):
    assert (generated_dest / relative).is_file(), relative
verified = verify_export(generated_dest)
assert verified["identity"]["digest"] == digest
assert digest in window.run_page.merged_view.toPlainText()
run_flags = ("--config project/main.ini --macro project/macros/run.mac "
             "--output runs/default/output")
assert run_flags in (generated_dest / "README-EXPORT.md").read_text(encoding="utf-8")
assert run_flags in manifest["build"]["commands"]["linux"][-1]
assert all(run_flags in run["command"] for run in manifest["tests"]["smoke_runs"])

# --- An opened external project exports as well ----------------------------
external_project = G4USimProject()
external_project.runInputMode = "external"
external_project.configPath = str(EXAMPLES / "main.ini")
external_project.macroPath = str(EXAMPLES / "run.mac")
window.project = external_project
window.refresh_export_project_action()
assert window.export_project_action.isEnabled(), \
    window.export_project_action.toolTip()
external_dest = work / "external"
external_result = window._export_project_to(external_dest, interactive=False)
assert external_result is not None
external_manifest = json.loads(
    (external_dest / "export-manifest.json").read_text(encoding="utf-8"))
assert external_manifest["project"]["selection"] == "opened_project"
assert external_manifest["project"]["original_project_root_audit"] == str(EXAMPLES)
assert verify_export(external_dest)["identity"]["digest"] == \
    external_manifest["identity"]["digest"]
assert (external_dest / "project" / "README.md").read_bytes() == \
    (EXAMPLES / "README.md").read_bytes()

# --- Existing destinations fail closed with an R code ----------------------
existing = window._export_project_to(external_dest, interactive=False)
assert existing is None
assert "R1" in window.run_page.merged_view.toPlainText(), \
    window.run_page.merged_view.toPlainText()[-600:]

# --- The action is translated with the rest of the window ------------------
window._set_language("zh_CN")
app.processEvents()
assert window.export_project_action.text() == "导出 Geant4 工程…", \
    window.export_project_action.text()
window._set_language("en")
app.processEvents()
assert window.export_project_action.text() == "Export Geant4 project...", \
    window.export_project_action.text()

window.close()
app.processEvents()
print("smoke_export_project: OK")
