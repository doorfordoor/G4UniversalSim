"""J2 independent in-memory inputs, project isolation, and portable export."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings
from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.core import wizard
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_fingerprint
from g4usim_gui.core.experiment_bundle import export_bundle, load_bundle
from g4usim_gui.core.project import G4USimProject, save_project, load_project
from g4usim_gui.editors.geometry_editor_model import HierarchicalVolumeRow
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.writers.package_writer import create_run_package, PackageValidationError


def package(project):
    return create_run_package(project=project, paths=project.pathSettings, run=project.runSettings,
        geometry=project.geometrySettings, source=project.sourceSettings, physics=project.physicsSettings,
        scoring=project.scoringSettings, material_document=project.materialEditor,
        geometry_document=project.geometryEditor, source_model=project.sourceEditor,
        physics_model=project.physicsEditor, scoring_model=project.scoringEditor)[0]


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName('G4UniversalSimSmoke')
    app.setApplicationName('J2Blank')
    QSettings().clear()
    with tempfile.TemporaryDirectory(prefix='j2-blank-') as directory:
        root = Path(directory).resolve()
        project = G4USimProject(executable=sys.executable, workspaceRoot=str(root), runsRoot=str(root / 'runs'))
        project.pathSettings = PathSettings(executable=sys.executable, workspace_root=str(root), runs_root=project.runsRoot)
        wizard.apply_to_project(project, wizard.blank_result())
        assert len(project.geometryEditor.volumes) == 1
        assert project.materialEditor.rows == [] and project.materialEditor.is_dirty
        assert not project.geometrySettings.config_path and not project.pathSettings.materials_config
        result = package(project)
        assert Path(result.materials_ini_path).is_file() and Path(result.geometry_ini_path).is_file()
        assert '[world]' in Path(result.geometry_ini_path).read_text(encoding='utf-8')
        project.geometryEditor.volumes.append(HierarchicalVolumeRow(name='Detector', parent='world',
            shape='box', size='10 mm, 10 mm, 10 mm', material='G4_Si', sensitive=True))
        project.scoringEditor.hits = True
        for scenario in wizard.SCENARIOS:
            template = copy.deepcopy(project)
            wizard.apply_to_project(template, wizard.build(wizard.default_spec(scenario)))
            assert Path(package(template).geometry_ini_path).is_file(), scenario
        saved = root / 'project.json'
        save_project(project, saved)
        loaded = load_project(saved)
        assert [v.name for v in loaded.geometryEditor.volumes] == ['world', 'Detector']
        assert loaded.materialEditor.rows == []
        assert Path(package(loaded).geometry_ini_path).is_file()
        # A captured external source does not become an independent document by
        # merely clearing its path control; lost files must continue to block.
        bad = copy.deepcopy(loaded)
        bad.geometryEditor.source_path = str(root / 'deleted.ini')
        try:
            package(bad)
        except PackageValidationError as exc:
            assert any(d.code == 'config.path.geometry.required' for d in exc.report.diagnostics)
        else:
            assert False, 'clearing an external input bypassed source checks'
        bundle = root / 'bundle'
        export_bundle(WorkspaceSnapshot(project), bundle)
        assert (bundle / 'manifest.json').is_file() and (bundle / 'replay.py').is_file()
        restored = load_bundle(bundle, executable=sys.executable)
        assert [v.name for v in restored.project.geometryEditor.volumes] == ['world', 'Detector']
        # Ordinary project save and export have never overwritten any inputs.
        assert saved.read_bytes() and not (root / 'deleted.ini').exists()
        window = MainWindow()
        try:
            window._set_project(project)
            window.project_file = saved
            old = saved.read_bytes()
            window.project_page.project_name.setText('unsaved old document')
            window._finish_history_merge()
            before = snapshot_fingerprint(window.capture_workspace())
            window._choose_unsaved_action = lambda: QMessageBox.Cancel
            assert not window.new_blank_project()
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert window.project_file == saved
            window._choose_unsaved_action = lambda: QMessageBox.Discard
            assert window.new_blank_project()
            assert window.project_file is None and saved.read_bytes() == old
            page = window.config_builder_page
            assert len(page.geometry_document.volumes) == 1 and page.material_document.rows == []
            assert page.materials_summary is None and page.geometry_summary is None
            assert page.validate_current(window.project).can_run
            window.project_page.project_name.setText('my blank simulation')
            window._finish_history_merge()
            assert window._edit_session.can_undo
            window.undo_edit()
            assert window.project.projectName == 'new_simulation'
            window.redo_edit()
            assert window.project.projectName == 'my blank simulation'
            assert window.project_file is None and saved.read_bytes() == old
        finally:
            close_window(app, window)
    print('J2 blank/template/package/save/undo/export checks passed')


if __name__ == '__main__':
    main()
