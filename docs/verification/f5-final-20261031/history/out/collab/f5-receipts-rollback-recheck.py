"""Independent post-fix verification using the original failure semantics."""
import hashlib,json,os
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from g4usim_gui.core import project as model
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.edit_transactions import TransactionApplyError
facts=[]
with tempfile.TemporaryDirectory(prefix='f5-receipt-recheck-') as tmp:
    work=Path(tmp);source=work/'legacy.json'
    raw=b'\xef\xbb\xbf'+b'{\r\n "version": 6, "projectName": "legacy"\r\n}\r\n'
    source.write_bytes(raw)
    parsed,receipt=model.load_project_with_receipt(source)
    assert parsed.version==7 and receipt.sha256==hashlib.sha256(raw).hexdigest()
    target=work/'target.json';target.write_bytes(b'original')
    read_bytes=Path.read_bytes
    def fail_temp_read(path):
        if path.suffix=='.tmp':raise OSError('receipt read fails before publication')
        return read_bytes(path)
    with patch.object(Path,'read_bytes',fail_temp_read):
        try:model.save_project(model.G4USimProject(),target)
        except OSError:rejected=True
        else:rejected=False
    assert rejected and target.read_bytes()==b'original' and not list(work.glob('.*.tmp'))
    unlink=Path.unlink;cleanup_calls=[]
    def fail_cleanup(path,*args,**kwargs):
        if path.suffix=='.tmp' and not path.exists():
            cleanup_calls.append(str(path));raise OSError('postpublication cleanup failure')
        return unlink(path,*args,**kwargs)
    with patch.object(Path,'unlink',fail_cleanup):
        receipt=model.save_project(model.G4USimProject(projectName='already published'),target)
    assert json.loads(target.read_bytes())['projectName']=='already published'
    assert receipt.sha256==hashlib.sha256(target.read_bytes()).hexdigest()
    assert not cleanup_calls
    facts.append({'case':'P2_save_publication_commit_point','status':'pass',
                  'postpublication_cleanup_calls':cleanup_calls,'actual_written_sha':receipt.sha256,
                  'legacy_BOM_CRLF_receipt_and_prepublication_failure_preserved':True})

from PySide6.QtWidgets import QApplication,QMessageBox
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
app=QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False);set_application_language(app,'en')
with tempfile.TemporaryDirectory(prefix='f5-rollback-recheck-') as tmp:
    work=Path(tmp);run_history_store.STATE_PATH=work/'gui-state.json'
    window=MainWindow(recovery_root=work/'recovery',offer_recovery=False)
    page=window.config_builder_page;page.preview3d_auto_backend.setChecked(False)
    window._choose_unsaved_action=lambda:QMessageBox.Discard
    try:
        page.beam_on.setValue(page.beam_on.value()+1);window.flush_pending_edit()
        before=window._edit_session.current();before_hash=snapshot_fingerprint(before)
        before_revision=window._edit_session.revision;before_beam=page.beam_on.value()
        before_dirty=window._edit_session.is_modified
        assert window._edit_session.can_undo
        def break_projection(*args,**kwargs):
            page.beam_on.setValue(before_beam+2468)
            raise RuntimeError('injected Qt projection failure after changing beam widget')
        with patch.object(page,'set_from_project',break_projection):
            try:window.undo_edit()
            except TransactionApplyError as exc:double_failure=exc.rollback is not None
            else:double_failure=False
            assert double_failure
            assert not window.restore_last_verified_workspace()
        assert snapshot_fingerprint(window._edit_session.current())==before_hash
        assert window._edit_session.revision==before_revision
        assert snapshot_fingerprint(window.capture_workspace())!=before_hash
        assert page.beam_on.value()==before_beam+2468
        assert window._workspace_fault
        assert not window.can_mutate_workspace('save after failed rollback')
        target=work/'must-not-save.json'
        assert not window._save_project_to(target) and not target.exists()
        with patch('g4usim_gui.window.run.create_run_package',side_effect=AssertionError('faulty projection reached generation')):
            assert not window._generate_current_package()
            window.generate_package(False)
        assert not page.isEnabled() and not window.undo_action.isEnabled()
        assert window.restore_last_verified_workspace()
        assert not window._workspace_fault and window._workspace_fault_snapshot is None
        assert page.beam_on.value()==before_beam
        assert snapshot_fingerprint(window.capture_workspace())==before_hash
        assert snapshot_fingerprint(window._edit_session.current())==before_hash
        assert window._edit_session.revision==before_revision
        assert window._edit_session.is_modified==before_dirty
        assert window._edit_session.can_undo and page.isEnabled()
        assert window.can_mutate_workspace('save after explicit repair')
        assert window._save_project_to(work/'repaired.json')
        assert model.load_project(work/'repaired.json').runSettings.beam_on==before_beam
        assert not window._edit_session.is_modified
        facts.append({'case':'P1_actual_MainWindow_double_projection_failure','status':'pass',
          'actual_bad_widget_value':before_beam+2468,'save_generation_and_editor_blocked':True,
          'repair_failure_remained_frozen':True,'explicit_successful_repair_preserved_history_and_savepoint':True,
          'repaired_saved_beam_on':before_beam,'native_visible_test':False})
    finally:
        if window._workspace_fault:window.restore_last_verified_workspace()
        window.close();app.processEvents()
print(json.dumps(facts,ensure_ascii=False,indent=2))
