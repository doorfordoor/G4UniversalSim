"""E6 migration preview, separate copies and window failure-state regression."""
from pathlib import Path
import ast
import json
import os
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import load_project
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.widgets.migration_dialog import MigrationDialog
from g4usim_gui.window import project as project_window


def main() -> None:
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4USimSmoke")
    app.setApplicationName("ConfigMigrationUI")
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="e6-ui-") as temporary:
        work = Path(temporary)
        run_history_store.STATE_PATH = work / "state.json"
        original = work / "旧项目.json"
        original.write_text(json.dumps({"schema": "G4UniversalSimProject", "version": 5,
                                        "projectName": "旧项目", "macroPath": "old.mac"}), encoding="utf-8")
        original_bytes = original.read_bytes()
        set_application_language(app, "zh_CN")
        dialog = MigrationDialog(open_project=lambda _: True)
        dialog.source_path.setText(str(original))
        assert dialog.preview(), dialog.status.text()
        assert "输入版本 5" in dialog.version_label.text()
        assert "输出版本 6" in dialog.version_label.text()
        assert dialog.changes.rowCount() > 0
        assert "未执行模拟" in dialog.boundary_label.text()
        assert dialog.write_button.isEnabled()
        assert not dialog.open_button.isEnabled()
        result = work / "迁移副本.json"
        assert dialog.write_copy(result)
        assert original.read_bytes() == original_bytes
        assert load_project(result).runInputMode == "external"
        assert dialog.open_button.isEnabled()
        cleanup_copy = work / "cleanup-warning.json"
        with patch("g4usim_gui.core.config_migration.Path.unlink", side_effect=OSError("injected cleanup failure")):
            assert dialog.write_copy(cleanup_copy)
        assert cleanup_copy.exists()
        assert "副本已发布" in dialog.status.text()
        assert "injected cleanup failure" in dialog.status.text()
        assert dialog.open_button.isEnabled()
        assert original.read_bytes() == original_bytes
        for temporary_file in work.glob(".cleanup-warning.json.*.tmp"):
            temporary_file.unlink()
        before_result = result.read_bytes()
        assert not dialog.write_copy(result)
        assert result.read_bytes() == before_result
        assert not dialog.write_copy(original)
        assert original.read_bytes() == original_bytes
        alias = work / "hardlink.json"
        os.link(original, alias)
        assert not dialog.write_copy(alias)
        assert alias.read_bytes() == original_bytes
        missing_target = work / "missing" / "copy.json"
        assert not dialog.write_copy(missing_target)
        assert not missing_target.exists()
        original.write_bytes(original_bytes + b" ")
        assert not dialog.write_copy(work / "changed-source.json")
        assert not (work / "changed-source.json").exists()
        original.write_bytes(original_bytes)
        future = work / "future.json"
        future.write_text('{"version":999}', encoding="utf-8")
        dialog.source_path.setText(str(future))
        assert not dialog.write_button.isEnabled()
        assert dialog.output_preview.toPlainText() == ""
        assert not dialog.preview()
        assert "999" in dialog.diagnostics.toPlainText()
        assert not dialog.write_copy(work / "bad.json")
        geometry = work / "geometry.ini"
        geometry.write_text("[world]\nshape = box\nsize = 10 cm, 10 cm, 10 cm\nmaterial = G4_AIR\nlabel = keep\n", encoding="utf-8")
        dialog.kind.setCurrentIndex(dialog.kind.findData("geometry"))
        dialog.source_path.setText(str(geometry))
        assert not dialog.preview()
        assert "mapping" in dialog.diagnostics.toPlainText()
        dialog.mapping.setPlainText('{"[world]/label":"metadata.label"}')
        assert dialog.preview()
        assert "metadata.label = keep" in dialog.output_preview.toPlainText()
        assert "version = 2" in dialog.output_preview.toPlainText()
        geometry_copy = work / "geometry-v2.ini"
        assert dialog.write_copy(geometry_copy)
        assert not dialog.open_button.isEnabled()  # no implicit project/input switch.
        assert "label = keep" in geometry.read_text(encoding="utf-8")
        main_ini = work / "main.ini"
        main_ini.write_text("[run]\nthreads = 1\n", encoding="utf-8")
        dialog.kind.setCurrentIndex(dialog.kind.findData("main"))
        dialog.source_path.setText(str(main_ini))
        assert dialog.preview(), dialog.status.text()
        assert "缺省" in dialog.version_label.text()
        assert "同目录" in dialog.diagnostics.toPlainText()
        other = work / "other"
        other.mkdir()
        assert not dialog.write_copy(other / "main-copy.ini")
        assert not (other / "main-copy.ini").exists()
        assert dialog.write_copy(work / "main-copy.ini")
        assert "schema_version = 1" in (work / "main-copy.ini").read_text(encoding="utf-8")
        assert main_ini.read_text(encoding="utf-8") == "[run]\nthreads = 1\n"
        dialog.reject()
        assert geometry_copy.exists()
        dialog.deleteLater()

        set_application_language(app, "en")
        english = MigrationDialog()
        assert english.windowTitle() == "Configuration migration copy..."
        assert english.write_button.text() == "Write new copy..."
        english.deleteLater()
        window = MainWindow()
        for timer in window.findChildren(QTimer):
            timer.stop()
        assert any(action.text() == "Configuration migration copy..." for action in window.menuBar().actions()[0].menu().actions())
        window.project_file = work / "current.json"
        current_project = window.project
        current_path = window.project_file
        view_path = window.project_page.workspace_root.text()
        stale = window._generated_package_stale
        with patch.object(project_window.QMessageBox, "critical"):
            assert not window._load_project_path(str(future))
            assert window.project is current_project
            assert window.project_file == current_path
            assert window.project_page.workspace_root.text() == view_path
            assert window._generated_package_stale == stale
            with patch.object(project_window.QFileDialog, "getSaveFileName", return_value=(str(work / "save-failed.json"), "")), \
                 patch.object(project_window, "save_project", side_effect=OSError("injected save failure")):
                window.save_project_as()
            assert window.project_file == current_path
            with patch.object(project_window.QFileDialog, "getSaveFileName", return_value=("", "")):
                window.save_project_as()
            assert window.project_file == current_path
        assert window._load_project_path(str(original))
        assert window.project.projectName == "旧项目"
        assert window.project.runInputMode == "external"
        assert window.project_file == original
        review = MigrationDialog(window, open_project=window._load_project_path)
        review.source_path.setText(str(original))
        assert review.preview()
        explicit_copy = work / "explicit-open.json"
        previous_project = window.project
        assert review.write_copy(explicit_copy)
        assert window.project is previous_project
        assert window.project_file == original
        review._open_copy()
        assert window.project_file == explicit_copy
        assert window.project.projectName == "旧项目"
        review.deleteLater()
        window.close()
        window.deleteLater()
        app.processEvents()

    # New migration translations must not silently replace an earlier entry.
    tree = ast.parse((ROOT / "gui/g4usim_gui/core/i18n.py").read_text(encoding="utf-8"))
    dictionary = next(item.value for item in tree.body if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "ZH_CN")
    keys = [item.value for item in dictionary.keys]
    for key in ("Configuration migration copy...", "Preview migration", "Write new copy...",
                "Open new project copy", "Migration copy failed: {error}"):
        assert keys.count(key) == 1
    print("smoke_config_migration_ui: ok")


if __name__ == "__main__":
    main()
