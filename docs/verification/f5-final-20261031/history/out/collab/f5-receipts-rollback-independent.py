"""Independent receipt IO + real MainWindow double-rollback fault injection."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from g4usim_gui.core import project as model
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.edit_transactions import TransactionApplyError
facts=[]

with tempfile.TemporaryDirectory(prefix='f5-receipt-independent-') as tmp:
    work=Path(tmp); source=work/'legacy-中文.json'
    # Encoding/layout changes and migration must not canonicalize observed SHA.
    raw=b'\xef\xbb\xbf'+b'{\r\n  "version": 6,\r\n  "projectName": "legacy"\r\n}\r\n'
    source.write_bytes(raw)
    parsed,receipt=model.load_project_with_receipt(source)
    assert parsed.version==7 and receipt.sha256==hashlib.sha256(raw).hexdigest()
    assert receipt.sha256!=hashlib.sha256(json.dumps(model.project_to_dict(parsed)).encode()).hexdigest()
    target=work/'target.json'; target.write_bytes(b'original bytes')
    original=target.read_bytes()
    read_bytes=Path.read_bytes
    def fail_temp_read(path):
        if path.suffix=='.tmp': raise OSError('receipt-read failure before publication')
        return read_bytes(path)
    with patch.object(Path,'read_bytes',fail_temp_read):
        try:model.save_project(model.G4USimProject(projectName='new'),target)
        except OSError: rejected=True
        else:rejected=False
    assert rejected and target.read_bytes()==original
    assert not list(work.glob('.*.tmp'))
    facts.append({'category':'no_issue','case':'receipt_raw_bytes_and_prepublication_hash_failure',
                  'legacy_bom_crlf_sha_retained':True,'hash_failure_kept_original':True})
    # An inherited save finally can throw after successful publication.
    unlink=Path.unlink
    def fail_cleanup(path,*args,**kwargs):
        if path.suffix=='.tmp' and not path.exists():
            raise OSError('postpublication cleanup failure')
        return unlink(path,*args,**kwargs)
    save_error=None
    with patch.object(Path,'unlink',fail_cleanup):
        try: saved_receipt=model.save_project(model.G4USimProject(projectName='already published'),target)
        except OSError as exc:save_error=str(exc)
    committed=json.loads(target.read_bytes())['projectName']=='already published'
    assert save_error and committed
    facts.append({'category':'confirmed','case':'postpublication_cleanup_reported_save_failure',
                  'error':save_error,'new_target_already_published':committed,
                  'scope':'inherited finally behavior; exact normal cleanup OS frequency not claimed'})

from PySide6.QtWidgets import QApplication,QMessageBox
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
app=QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False);set_application_language(app,'en')
with tempfile.TemporaryDirectory(prefix='f5-rollback-independent-') as tmp:
    work=Path(tmp);run_history_store.STATE_PATH=work/'gui-state.json'
    window=MainWindow(recovery_root=work/'recovery',offer_recovery=False)
    page=window.config_builder_page;page.preview3d_auto_backend.setChecked(False)
    window._choose_unsaved_action=lambda:QMessageBox.Discard
    try:
        page.beam_on.setValue(page.beam_on.value()+1)
        window.flush_pending_edit()
        assert window._edit_session.can_undo
        before=window._edit_session.current();before_hash=snapshot_fingerprint(before)
        before_revision=window._edit_session.revision;before_beam=page.beam_on.value()
        def break_projection(*args,**kwargs):
            # A real widget is partially updated, then the projection fails on
            # both initial apply and rollback, as a Qt binding/widget fault may.
            page.beam_on.setValue(before_beam+2468)
            raise RuntimeError('injected Qt projection failure after changing beam widget')
        with patch.object(page,'set_from_project',break_projection):
            try:window.undo_edit()
            except TransactionApplyError as exc:
                double_failure=exc.rollback is not None;error=str(exc)
            else:double_failure=False;error=''
        assert double_failure
        assert snapshot_fingerprint(window._edit_session.current())==before_hash
        assert window._edit_session.revision==before_revision
        view_hash=snapshot_fingerprint(window.capture_workspace())
        assert view_hash!=before_hash and page.beam_on.value()==before_beam+2468
        allowed=window.can_mutate_workspace('save after failed rollback')
        target=work/'saved-after-rollback-failure.json'
        if allowed:
            saved=window._save_project_to(target)
            recorded=model.load_project(target)
            actual=recorded.runSettings.beam_on
        else:
            saved=False;actual=None
        facts.append({'category':'confirmed' if allowed and saved else 'no_issue',
                      'case':'double_projection_failure_ui_not_frozen',
                      'double_failure_error':error,'view_differs_from_authoritative_history':view_hash!=before_hash,
                      'can_mutate_workspace':allowed,'save_succeeded':saved,
                      'beam_before_failure':before_beam,'beam_written_after_failure':actual,
                      'history_now_clean':not window._edit_session.is_modified})
        assert allowed and saved and actual==before_beam+2468
    finally:
        window._choose_unsaved_action=lambda:QMessageBox.Discard
        window.close();app.processEvents()
print(json.dumps(facts,ensure_ascii=False,indent=2))
