"""Independent repair check of exact capacity injection and publication edges."""
import hashlib,json,os
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'gui/smoke_tests'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QMessageBox,QWidget
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.project import save_project,load_project
from g4usim_gui.core.edit_snapshot import project_for_snapshot,snapshot_fingerprint,snapshot_size
from g4usim_gui.core.edit_transactions import TransactionCapacityError
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
from smoke_project_import_projection import snapshot
app=QApplication([]);app.setQuitOnLastWindowClosed(False);set_application_language(app,'en')
facts=[]
with tempfile.TemporaryDirectory(prefix='f5-open-capacity-recheck-') as tmp:
    work=Path(tmp);run_history_store.STATE_PATH=work/'state.json'
    w=MainWindow(recovery_root=work/'recovery',offer_recovery=False)
    w._choose_unsaved_action=lambda:QMessageBox.Discard
    page=w.config_builder_page
    try:
        old_path=work/'original.json';assert w._save_project_to(old_path)
        assert w._load_project_path(str(old_path))
        page.beam_on.setValue(201);w._finish_history_merge();w.undo_edit()
        assert w._edit_session.can_redo
        before=w._edit_session.current();before_hash=snapshot_fingerprint(before)
        session=w._edit_session
        history=(session.revision,session.saved_fingerprint,session.history_bytes,session.can_redo)
        origin=(w._recovery_origin_path,w._recovery_origin_sha256)
        candidate=project_for_snapshot(before);candidate.projectName='replacement-'+('X'*500)
        candidate.editingState['drafts']['project.project_name']=candidate.projectName
        path=work/'candidate.json';save_project(candidate,path);raw=path.read_bytes();old_raw=old_path.read_bytes()
        assert load_project(path).projectName==candidate.projectName
        for timer in w.findChildren(QTimer):timer.stop()
        widgets=w.findChildren(QWidget);old_view=snapshot(w,widgets)
        limit=session.max_bytes;session.max_bytes=snapshot_size(before)+1
        for entry in ('direct_set','actual_load'):
            errors=[]
            with patch.object(QMessageBox,'critical',side_effect=lambda *args:errors.append(str(args[-1]))),patch.object(w,'_confirm_unsaved_edits',side_effect=AssertionError('capacity preflight must run before an unsaved prompt')),patch.object(w,'apply_workspace',side_effect=AssertionError('capacity rejection must precede projection')):
                if entry=='direct_set':
                    try:w._set_project(candidate)
                    except TransactionCapacityError as exc:errors.append(str(exc))
                    else:assert False
                else:assert w._load_project_path(str(path)) is False
            assert errors and 'capacity' in errors[0].lower()
            assert snapshot(w,widgets)==old_view
            assert history==(session.revision,session.saved_fingerprint,session.history_bytes,session.can_redo)
            assert origin==(w._recovery_origin_path,w._recovery_origin_sha256)
            assert w.project_file==old_path and not w._workspace_fault
            facts.append({'case':entry,'rejected_before_projection_and_prompt':True,'all_widget_model_ids_and_file_history_receipt_preserved':True})
        session.max_bytes=limit
        legacy=work/'legacy.json';legacy.write_text(json.dumps({'projectName':'legacy replacement'}),encoding='utf-8')
        errors=[]
        with patch.object(session,'reset',side_effect=TransactionCapacityError('independent late reset rejection')),patch.object(QMessageBox,'critical',side_effect=lambda *args:errors.append(str(args[-1]))):
            assert w._load_project_path(str(legacy)) is False
        assert errors and 'late reset' in errors[-1]
        assert snapshot_fingerprint(w.capture_workspace())==before_hash
        assert snapshot_fingerprint(session.current())==before_hash
        assert history==(session.revision,session.saved_fingerprint,session.history_bytes,session.can_redo)
        assert w.project_file==old_path and origin==(w._recovery_origin_path,w._recovery_origin_sha256)
        assert not w._workspace_fault
        facts.append({'case':'actual_load_late_session_reset_rejection','view_history_path_origin_rolled_back':True})
        real_reset=w._reset_edit_history
        def failing_notice(*args,**kwargs):
            with patch.object(w,'history_changed',side_effect=RuntimeError('independent afterpublish notification failure')):
                return real_reset(*args,**kwargs)
        with patch.object(w,'_reset_edit_history',failing_notice):
            assert w._load_project_path(str(path)) is True
        assert w.project_file==path and w.project.projectName==candidate.projectName
        assert session.current().project.projectName==candidate.projectName
        assert snapshot_fingerprint(w.capture_workspace())==snapshot_fingerprint(session.current())
        assert session.revision>history[0] and not session.is_modified and not session.can_redo
        assert w._recovery_origin_path==str(path.absolute()) and w._recovery_origin_sha256==hashlib.sha256(raw).hexdigest()
        assert 'status update failed' in w.statusBar().currentMessage().lower()
        assert old_path.read_bytes()==old_raw and path.read_bytes()==raw
        facts.append({'case':'afterpublish_notification_exception','open_succeeded_new_view_history_path_and_actual_byte_receipt_aligned':True,'original_and_candidate_files_unchanged':True})
    finally:
        w._edit_session.max_bytes=32*1024*1024
        if w._workspace_fault:w.restore_last_verified_workspace()
        w.close();app.processEvents()
print(json.dumps(facts,ensure_ascii=False,indent=2))
