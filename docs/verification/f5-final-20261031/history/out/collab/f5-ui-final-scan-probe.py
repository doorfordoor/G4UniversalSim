"""Read-only product audit: public Scan controls import invalid/faulted config."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))
from PySide6.QtWidgets import QApplication, QMessageBox
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.wizard import default_spec
from g4usim_gui.core.edit_transactions import TransactionApplyError
from g4usim_gui.history import run_history_store

app = QApplication([])
facts = {}
with tempfile.TemporaryDirectory(prefix='f5-final-scan-probe-') as directory:
    work = Path(directory)
    with patch.object(run_history_store, 'STATE_PATH', work / 'state.json'):
        window = MainWindow(recovery_root=work / 'recovery', offer_recovery=False)
        window._choose_unsaved_action = lambda: QMessageBox.Discard
        page = window.config_builder_page
        scan = window.scan_page
        try:
            with (patch.object(QMessageBox, 'warning', return_value=QMessageBox.Ok),
                  patch.object(QMessageBox, 'information', return_value=QMessageBox.Ok)):
                assert window.apply_simulation_wizard(default_spec('single_target'), run_after=False)
                fake = work / 'validation-only-executable'
                fake.write_bytes(b'never executed')
                window.project_page.executable.setText(str(fake))
                window.project_page.runs_root.setText(str(work / 'packages'))
                page.seed.setText('not-an-integer')
                window._finish_history_merge()
                assert not page.validate_current(window.project).can_run
                scan.refresh_button.click()
                assert scan.select_parameter('source.energy')
                scan.values.setText('2 MeV')
                scan.create_button.click()
                manifest = scan._manifest
                ini = Path(manifest.points[0].main_ini).read_text(encoding='utf-8')
                facts['invalid_seed'] = {'raw': page.seed.text(), 'base_seed': scan._base.run.seed,
                    'package_created': Path(manifest.points[0].main_ini).is_file(),
                    'package_has_seed': 'seed =' in ini, 'main_ini': ini}
                assert facts['invalid_seed']['package_created'] and not facts['invalid_seed']['package_has_seed']
                page.seed.setText('42')
                page.beam_on.setValue(101)
                window._finish_history_merge()
                def broken(*args, **kwargs):
                    page.beam_on.setValue(2569)
                    raise RuntimeError('audit injected projection failure')
                with patch.object(page, 'set_from_project', broken):
                    try:
                        window.undo_edit()
                    except TransactionApplyError as exc:
                        assert exc.rollback is not None
                assert window._workspace_fault and not window.can_mutate_workspace()
                scan.refresh_button.click()
                scan.name.setText('after-fault')
                scan.values.setText('3 MeV')
                scan.create_button.click()
                manifest = scan._manifest
                macro = Path(manifest.points[0].macro).read_text(encoding='utf-8')
                facts['faulted_editor'] = {'fault': window._workspace_fault, 'main_editor_can_mutate': window.can_mutate_workspace(),
                    'history_beam_on': window._edit_session.current().project.runSettings.beam_on,
                    'scan_base_beam_on': scan._base.run.beam_on,
                    'package_created': Path(manifest.points[0].main_ini).is_file(), 'macro': macro}
                assert '/run/beamOn 2569' in macro and facts['faulted_editor']['history_beam_on'] == 101
                assert window.restore_last_verified_workspace()
        finally:
            if window._workspace_fault:
                window.restore_last_verified_workspace()
            window.close()
            app.processEvents()
destination = ROOT / 'out/collab/f5-ui-final-scan-probe.json'
destination.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(facts, ensure_ascii=False, indent=2))
