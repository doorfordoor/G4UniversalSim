"""J2 structured editors share F4 navigation, F5 history and strict recovery."""
from __future__ import annotations
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core import wizard
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.edit_snapshot import snapshot_to_json, snapshot_from_json, snapshot_fingerprint
from g4usim_gui.core.run_editor_model import GPSDefinition, FieldDefinition
from g4usim_gui.core.diagnostics import collect_diagnostics
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.editors.source_physics_scoring_model import validate_source_model
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.validators.config_validator import ValidationReport


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName('G4UniversalSimSmoke')
    app.setApplicationName('J2Workspace')
    QSettings().clear()
    with tempfile.TemporaryDirectory(prefix='j2-workspace-') as tmp:
        root = Path(tmp).resolve()
        project = G4USimProject(executable=sys.executable, workspaceRoot=str(root), runsRoot=str(root/'runs'))
        project.pathSettings = PathSettings(executable=sys.executable, workspace_root=str(root), runs_root=project.runsRoot)
        wizard.apply_to_project(project, wizard.blank_result())
        project.sourceEditor.gps_sources = [GPSDefinition(name='first', energy='1 MeV'), GPSDefinition(name='second', energy='1 MeV')]
        project.physicsEditor.fields = [FieldDefinition()]
        window = MainWindow()
        try:
            assert window._set_project(project) is not False
            page = window.config_builder_page
            window.page_stack.setCurrentWidget(page)
            window.show()
            app.processEvents()
            source_rows = page.j2_run_editors.row_editors['gps_sources']
            source_rows.list.setCurrentRow(1)
            original_id = source_rows.rows[1].editor_id
            control = source_rows.controls['energy']
            control.setText('  invalid-energy  ')
            window._finish_history_merge()
            captured = window.capture_workspace()
            assert captured.project.sourceEditor.gps_sources[1].energy == '  invalid-energy  '
            assert not any(key.startswith('j2.') for key in captured.state['drafts'])
            assert captured.state['selections']['j2.gps_sources.selection'] == 1
            restored = snapshot_from_json(snapshot_to_json(captured))
            assert restored.project.sourceEditor.gps_sources[1].editor_id == original_id
            assert restored.project.sourceEditor.gps_sources[1].energy == '  invalid-energy  '
            window.undo_edit()
            assert page.source_editor.gps_sources[1].energy == '1 MeV'
            window.redo_edit()
            assert page.source_editor.gps_sources[1].energy == '  invalid-energy  '
            assert source_rows.list.currentRow() == 1
            report = page.validate_current(window.project)
            page.set_validation_report(report)
            issue = next(d for d in report.diagnostics if d.location and d.location.collection == 'gps_sources' and d.location.field == 'energy')
            assert issue.location.row == 1 and issue.location.entity == original_id
            generation = page._diagnostic_generation
            source_rows.list.setCurrentRow(0)
            assert page._diagnostic_generation == generation
            result = page.navigate_diagnostic(issue)
            assert result.ok and source_rows.list.currentRow() == 1, result
            assert control.text() == '  invalid-energy  '
            ids = []
            for language in ('en', 'zh_CN'):
                set_application_language(app, language)
                validate_source_model(page.source_editor)
                ids.append([d.identity for d in collect_diagnostics(page.source_editor)])
            assert ids[0] == ids[1]
            # Actual Qt undo routing owns advanced editors, not QLineEdit history.
            control.setFocus()
            QTest.keyClick(control, Qt.Key_Z, Qt.ControlModifier)
            app.processEvents()
            assert page.source_editor.gps_sources[1].energy == '1 MeV'
            page.geometry_table.selectRow(0)
            detail = page.volume_details.fields['vis.alpha']
            detail.setText('  bad-alpha  ')
            window._finish_history_merge()
            assert page.geometry_document.volumes[0].visual['vis.alpha'] == '  bad-alpha  '
            geometric = window.capture_workspace()
            assert snapshot_from_json(snapshot_to_json(geometric)).project.geometryEditor.volumes[0].visual['vis.alpha'] == '  bad-alpha  '
            report = page.validate_current(window.project)
            page.set_validation_report(report)
            issue = next(d for d in report.diagnostics if d.location and d.location.field == 'vis.alpha')
            result = page.navigate_diagnostic(issue)
            assert result.ok and result.widget is detail, result
            window.undo_edit()
            assert 'vis.alpha' not in page.geometry_document.volumes[0].visual
            window.redo_edit()
            assert page.geometry_document.volumes[0].visual['vis.alpha'] == '  bad-alpha  '
            window.apply_workspace(snapshot_from_json(snapshot_to_json(geometric)))
            assert snapshot_fingerprint(window.capture_workspace()) == snapshot_fingerprint(geometric)
        finally:
            close_window(app, window)
    print('J2 full-window raw drafts, keyboard undo, stable diagnostics and recovery replay passed')


if __name__ == '__main__':
    main()
