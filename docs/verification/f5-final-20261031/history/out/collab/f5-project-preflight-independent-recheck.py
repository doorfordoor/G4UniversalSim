"""Reject invalid project publications without touching any existing state."""
import copy,json,os
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'));sys.path.insert(0,str(ROOT/'gui/smoke_tests'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QMessageBox,QWidget
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.project import project_from_dict
from g4usim_gui.core.edit_snapshot import project_for_snapshot,snapshot_fingerprint
from g4usim_gui.history import run_history_store
from smoke_project_import_projection import snapshot
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
facts=[]
with tempfile.TemporaryDirectory(prefix='f5-preflight-independent-') as tmp:
    work=Path(tmp);run_history_store.STATE_PATH=work/'state.json'
    w=MainWindow(recovery_root=work/'recovery',offer_recovery=False)
    w._choose_unsaved_action=lambda:QMessageBox.Discard
    page=w.config_builder_page
    try:
        # Create a real dirty saved state plus a redo branch before rejecting.
        page.beam_on.setValue(201);w._finish_history_merge()
        assert w._save_project_to(work/'saved.json')
        page.beam_on.setValue(202);w._finish_history_merge();w.undo_edit()
        assert w._edit_session.can_redo and not w._edit_session.is_modified
        for timer in w.findChildren(QTimer):timer.stop()
        w._generated_package_stale=False;w._generated_package_dir='retained previous package'
        page.set_package_path('retained previous package')
        w.run_page.set_macro_plan('retained inspection text')
        widgets=w.findChildren(QWidget);before=snapshot(w,widgets)
        session=w._edit_session
        history=(session.revision,session.saved_fingerprint,session.history_bytes,session.can_undo,session.can_redo,snapshot_fingerprint(session.current()))
        candidates=[]
        candidates.append(('legacy_huge_run',project_from_dict({'runSettings':{'beam_on':10**100}})))
        candidate=project_for_snapshot(session.current());candidate.runSettings.beam_on=10**100
        candidates.append(('v7_huge_run',candidate))
        candidate=project_for_snapshot(session.current());candidate.editingState['drafts']['config.unknown_bound_widget']='x'
        candidates.append(('v7_unknown_widget_binding',candidate))
        candidate=project_for_snapshot(session.current());candidate.editingState['drafts']['config.beam_on']=10**100
        candidates.append(('v7_raw_widget_range',candidate))
        for name,candidate in candidates:
            error=''
            with patch.object(w,'apply_workspace',side_effect=AssertionError('Rejected preflight must never begin projection or rollback')):
                try:w._set_project(candidate)
                except ValueError as exc:error=str(exc)
                else:assert False,name
            assert error
            assert snapshot(w,widgets)==before,name
            assert history==(session.revision,session.saved_fingerprint,session.history_bytes,session.can_undo,session.can_redo,snapshot_fingerprint(session.current())),name
            assert not w._workspace_fault and not w._history_restoring
            facts.append({'case':name,'error':error,'widgets_objects_evidence_unchanged':True,'history_savepoint_redo_unchanged':True,'no_projection_called':True})
    finally:
        if w._workspace_fault:w.restore_last_verified_workspace()
        w.close();app.processEvents()
print(json.dumps(facts,ensure_ascii=False,indent=2))
