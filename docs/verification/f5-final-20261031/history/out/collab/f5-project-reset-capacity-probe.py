"""Small capacity fault injection; does not alter production defaults or sources."""
import json,os
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'gui'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core.project import save_project,load_project
from g4usim_gui.core.edit_snapshot import project_for_snapshot,snapshot_fingerprint,snapshot_size
from g4usim_gui.history import run_history_store
app=QApplication([]);app.setQuitOnLastWindowClosed(False);facts=[]
with tempfile.TemporaryDirectory(prefix='f5-reset-capacity-probe-') as tmp:
    work=Path(tmp);run_history_store.STATE_PATH=work/'state.json'
    for entry in ('direct_set','public_load'):
        w=MainWindow(recovery_root=work/entry,offer_recovery=False)
        w._choose_unsaved_action=lambda:QMessageBox.Discard
        try:
            assert w._save_project_to(work/(entry+'-original.json'))
            before=w._edit_session.current();before_hash=snapshot_fingerprint(before)
            before_file=str(w.project_file);before_revision=w._edit_session.revision
            old_limit=w._edit_session.max_bytes
            current_size=snapshot_size(before)
            candidate=project_for_snapshot(before);candidate.projectName='replacement-'+('X'*500)
            candidate.editingState['drafts']['project.project_name']=candidate.projectName
            path=work/(entry+'-candidate.json');save_project(candidate,path)
            assert load_project(path).projectName==candidate.projectName
            w._edit_session.max_bytes=current_size+1
            errors=[]
            with patch.object(QMessageBox,'critical',side_effect=lambda *args:errors.append(str(args[-1]))):
                try:
                    if entry=='public_load':returned=w._load_project_path(str(path))
                    else:w._set_project(candidate);returned=True
                except Exception as exc:errors.append(type(exc).__name__+': '+str(exc));returned=False
            observed={'entry':entry,'normal_default_bytes':old_limit,'injected_limit_bytes':current_size+1,
              'original_snapshot_bytes':current_size,'candidate_file_bytes':path.stat().st_size,
              'return_success':returned,'errors':errors,
              'view_project_name_is_new':w.project.projectName==candidate.projectName,
              'history_is_original':snapshot_fingerprint(w._edit_session.current())==before_hash,
              'view_is_original':snapshot_fingerprint(w.capture_workspace())==before_hash,
              'path_is_original':str(w.project_file)==before_file,
              'revision_is_original':w._edit_session.revision==before_revision,
              'workspace_fault':w._workspace_fault,'can_mutate':w.can_mutate_workspace()}
            facts.append(observed)
            print(json.dumps(observed,ensure_ascii=False),flush=True)
            assert not returned and errors
            assert observed['history_is_original'] and observed['revision_is_original']
            assert observed['view_project_name_is_new'] and not observed['view_is_original']
            assert observed['can_mutate'] and not observed['workspace_fault']
        finally:
            w._edit_session.max_bytes=32*1024*1024
            w.apply_workspace(before,reason='audit-cleanup')
            w.close();app.processEvents()
print(json.dumps(facts,ensure_ascii=False,indent=2))
