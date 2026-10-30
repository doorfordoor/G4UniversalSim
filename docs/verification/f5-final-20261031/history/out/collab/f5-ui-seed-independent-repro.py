"""Exercise the actual Generate signal with an invalid seed; no backend run."""
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

app = QApplication([])
app.setOrganizationName('G4UniversalSimAudit')
app.setApplicationName('F5SeedIndependent')
with tempfile.TemporaryDirectory(prefix='f5-ui-seed-review-') as temporary:
    folder = Path(temporary)
    w = MainWindow(recovery_root=folder / 'recovery', offer_recovery=False)
    w._choose_unsaved_action = lambda: QMessageBox.Discard
    messages = []
    def capture_message(*args):
        messages.append(str(args[-1]))
        return QMessageBox.Ok
    try:
        page = w.config_builder_page
        with (patch.object(QMessageBox, 'warning', capture_message),
              patch.object(QMessageBox, 'information', capture_message)):
            assert w.apply_simulation_wizard(default_spec('single_target'), run_after=False)
            executable = folder / 'G4UniversalSim-validation-only'
            executable.write_bytes(b'not executed')
            w.project_page.executable.setText(str(executable))
            w.project_page.runs_root.setText(str(folder / 'runs'))
            page.seed.setText('not-an-integer')
            w.flush_pending_edit()
            before = {'visible_seed': page.seed.text(), 'project_seed': w.project_page.seed.text(),
                      'validation_can_run': page.validate_current(w.project).can_run}
            page.generatePackageRequested.emit(False)
            generated = Path(w._generated_package_dir) if w._generated_package_dir else None
            evidence = {'before': before, 'after_visible_seed': page.seed.text(),
                        'package_generated': bool(generated and generated.is_dir()),
                        'messages': messages}
            if generated and generated.is_dir():
                evidence['generated_main'] = Path(w.project.configPath).read_text(encoding='utf-8')
            destination = ROOT / 'out/collab/f5-ui-seed-independent-repro.json'
            destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
    finally:
        w.close()
        app.processEvents()
