"""Bound SPS editor authority and finite Qt actions; no backend."""
from __future__ import annotations
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import copy
from pathlib import Path
import sys
import tempfile
from contextlib import nullcontext
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QApplication, QLineEdit, QCheckBox, QSpinBox, QComboBox
from smoke_f5_editor_history import owned_window
from g4usim_gui.core.project import G4USimProject,save_project,load_project
from g4usim_gui.core.edit_snapshot import snapshot_to_json,project_for_snapshot
from g4usim_gui.core.edit_transactions import TransactionApplyError,TransactionCapacityError,TransactionConflict
from g4usim_gui.core import sps_edit_model as sps


def main():
    app=QApplication.instance() or QApplication([])
    evidence = os.environ.get('G4USIM_TEST_EVIDENCE_DIR')
    if evidence: Path(evidence).mkdir(parents=True,exist_ok=True)
    temp = tempfile.mkdtemp(prefix='ar4-sps-',dir=evidence)
    print('SPS component evidence:',temp,flush=True)
    # Preserve failed attempts; cleanup must not mask a projection/service failure.
    with nullcontext(temp), owned_window(app,Path(temp)/'recovery') as w:
        page=w.config_builder_page
        p=G4USimProject()
        p.sourceEditor.energy='11 MeV'; p.sourceSettings.energy='77 MeV'
        p.physicsEditor.default_cut='0.2 mm'; p.physicsSettings.default_cut='0.9 mm'
        p.scoringEditor.hist_bins=31; p.scoringSettings.hist_bins=83
        p.sourceEditor.position_mode=p.sourceEditor.position_type='plane'
        p.sourceEditor.source_shape='rectangle';p.sourceEditor.angular_mode='isotropic'
        w._set_project(p)
        assert w._edit_session.current().project.sourceSettings.energy=='77 MeV'
        assert w.capture_workspace().project.scoringSettings.hist_bins==83
        revision=w._edit_session.revision
        page.source_energy.setText(' 2 MeV ')
        snap=w._edit_session.current()
        assert w._edit_session.revision==revision+1
        assert snap.project.sourceEditor.energy=='2 MeV' and page.source_energy.text()==' 2 MeV '
        assert snap.project.sourceEditor.position_mode=='plane'
        assert snap.project.sourceEditor.angular_mode=='isotropic'
        assert snap.project.physicsSettings.default_cut=='0.2 mm'
        assert snap.project.scoringSettings.hist_bins==31
        w.undo_edit(); snap=w._edit_session.current()
        assert snap.project.sourceSettings.energy=='77 MeV' and snap.project.sourceEditor.energy=='11 MeV'
        assert snap.project.physicsSettings.default_cut=='0.9 mm'
        assert snap.project.scoringSettings.hist_bins==83
        w.redo_edit()
        # All seven raw slots; advanced preserves advanced raw but mirrors quick.
        for key in sps.RAW_BINDINGS: w.edit_sps(key,'-')
        page.source_editor_energy.setText('3 MeV')
        drafts=w._edit_session.current().state['drafts']
        assert 'config.hist_bins.raw' not in drafts
        for key in sps.RAW_BINDINGS-{'config.hist_bins.raw'}: assert drafts[key]=='-'
        page.source_energy.setText('4 MeV')
        assert not (sps.RAW_BINDINGS & w._edit_session.current().state['drafts'].keys())
        w.edit_sps('config.hist_bins',17,raw='-')
        assert page.hist_bins.lineEdit().text()=='-'
        page.source_editor_energy.setText('5 MeV')
        assert page.hist_bins.lineEdit().text()!='-'
        # Copy-returning properties isolate validator/consumer mutation.
        model=page.source_editor;model.energy='POISON'
        assert w._edit_session.current().project.sourceEditor.energy=='5 MeV'
        # Poison every migrated scalar getter and every old J2 collector.
        from contextlib import ExitStack
        before=snapshot_to_json(w.capture_workspace())
        with ExitStack() as stack:
            for widget in page.sps_controls().values():
                name='isChecked' if isinstance(widget,QCheckBox) else 'value' if isinstance(widget,QSpinBox) else 'currentText' if isinstance(widget,QComboBox) else 'text'
                stack.enter_context(patch.object(widget,name,side_effect=AssertionError('migrated getter read')))
            stack.enter_context(patch.object(page.j2_run_editors,'collect_into',side_effect=AssertionError('J2 capture read')))
            assert snapshot_to_json(w.capture_workspace())==before
            page._update_main_ini_preview()
            target=Path(temp)/'saved.json'
            save_project(project_for_snapshot(w.capture_workspace()),target)
            assert load_project(target).sourceEditor.energy=='5 MeV'
        # Real named row UI operations, including programmatic hidden-field edits.
        gps=page.j2_run_editors.row_editors['gps_sources']
        gps._structure('Add')
        assert len(w._edit_session.current().project.sourceEditor.gps_sources)==1
        first=w._edit_session.current().project.sourceEditor.gps_sources[0].editor_id
        oldref=copy.deepcopy(gps._row_reference)
        gps.controls['name'].setText('alpha')
        gps.controls['spectrum_file'].setText(' hidden spectrum.csv ')
        assert w._edit_session.current().project.sourceEditor.gps_sources[0].spectrum_file==' hidden spectrum.csv '
        assert w._edit_session.current().project.sourceEditor.gps_sources[0].editor_id==first
        with __import__('unittest').TestCase().assertRaises(TransactionConflict):
            w.edit_sps(action={'kind':'row','key':'gps_sources','op':'set','index':0,'reference':oldref,'revision':oldref['revision'],'field':'name','value':'stale'})
        # Actual Qt textChanged with an obsolete token must restore the visible row.
        stable = snapshot_to_json(w._edit_session.current())
        current_name = gps.controls['name'].text()
        gps._row_reference = oldref
        caught=[]
        with patch('sys.excepthook', side_effect=lambda kind,error,tb: caught.append(error)):
            gps.controls['name'].setText('rejected visible name')
        assert len(caught)==1 and isinstance(caught[0],TransactionConflict)
        assert gps.controls['name'].text()==current_name
        assert snapshot_to_json(w._edit_session.current())==stable
        # The outer boundary restores the whole view when the same rejection propagates.
        try:
            with w.workspace_transaction('obsolete row action'):
                gps._row_reference=oldref
                blocker=QSignalBlocker(gps.controls['name'])
                gps.controls['name'].setText('outer rejected visible name')
                del blocker
                gps._edit('name','outer rejected visible name')
        except TransactionConflict:
            pass
        else:
            raise AssertionError('obsolete outer row action accepted')
        assert gps.controls['name'].text()==current_name
        assert snapshot_to_json(w._edit_session.current())==stable
        gps._structure('Duplicate')
        rows=w._edit_session.current().project.sourceEditor.gps_sources
        assert len(rows)==2 and rows[0].editor_id!=rows[1].editor_id
        assert gps.list.currentRow()==1
        revision=w._edit_session.revision;gps.list.setCurrentRow(0)
        assert w._edit_session.revision==revision
        gps._structure('Move down')
        assert w._edit_session.current().project.sourceEditor.gps_sources[1].editor_id==first
        for key in ('regions','fields','bias_rules'):
            editor=page.j2_run_editors.row_editors[key]
            editor._structure('Add'); reference=copy.deepcopy(editor._row_reference)
            field='particle' if key=='bias_rules' else 'name'
            editor.controls[field].setText('draft-row')
            assert getattr(getattr(w._edit_session.current().project.physicsEditor,key)[0],field)=='draft-row'
            with __import__('unittest').TestCase().assertRaises(TransactionConflict):
                w.edit_sps(action={'kind':'row','key':key,'op':'remove','index':0,'reference':reference,'revision':reference['revision']})
        modules=page.j2_run_editors.modules['extra_modules']
        modules._change('Add'); modules._change('Add')
        assert len(w._edit_session.current().project.physicsEditor.extra_modules)==2
        page.j2_run_editors.cuts['e-'].setText(' ')
        assert w._edit_session.current().project.physicsEditor.particle_cuts['e-']==' '
        page.j2_run_editors.cuts['e-'].setText('')
        assert 'e-' not in w._edit_session.current().project.physicsEditor.particle_cuts
        page.j2_run_editors.phase_space_file.setText('relative.csv')
        assert w._edit_session.current().project.sourceEditor.phase_space_file=='relative.csv'
        # Existing validator conflict remains; projection validation is private.
        from g4usim_gui.editors.source_physics_scoring_model import validate_source_model
        snapshot=w._edit_session.current(); raw=snapshot_to_json(snapshot)
        assert validate_source_model(page.source_editor).errors
        assert snapshot_to_json(w._edit_session.current())==raw
        # Real fields service (only file identity/validation, never transport).
        from g4usim_gui.core.wizard import build, default_spec, apply_to_project
        from smoke_k1_workflow import wait_workflow
        qualified=G4USimProject()
        apply_to_project(qualified,build(default_spec('single_target')))
        qualified.executable=qualified.pathSettings.executable=sys.executable
        qualified.workspaceRoot=qualified.pathSettings.workspace_root=temp
        qualified.runsRoot=qualified.pathSettings.runs_root=str(Path(temp)/'runs')
        w._set_project(qualified)
        assert not w._edit_session.current().project.sourceEditor.gps_sources
        assert page.j2_run_editors.row_editors['gps_sources'].list.count()==0
        assert all(editor.list.currentRow()==-1 for editor in page.j2_run_editors.row_editors.values())
        page.source_editor_energy.setText('2 MeV')
        w.flush_pending_edit()
        with patch.object(w.runner,'start',side_effect=AssertionError('no backend allowed')):
            w.experiment.validate('fields')
            wait_workflow(app,w)
            record=w.experiment.records()[-1]
            assert record['status']=='passed', record
            identity=record['record_id']
            epoch=w.experiment._epoch
            page.source_energy.setText('3 MeV')
            w.flush_pending_edit();w.undo_edit()
            old=next(r for r in w.experiment.records() if r['record_id']==identity)
            assert old['stale'] and w.experiment._epoch>=epoch
            # Rejection does not restore this old qualification either.
            ref_epoch=w.experiment._epoch
            try:w.edit_sps('config.scoring_enabled','not a boolean')
            except TypeError:pass
            else:raise AssertionError('invalid action accepted')
            assert next(r for r in w.experiment.records() if r['record_id']==identity)['stale']
            assert w.experiment._epoch>=ref_epoch
        # Reject/correct single projection, and freeze failed rollback.
        w._finish_history_merge(); before=snapshot_to_json(w._edit_session.current())
        capacity=w._edit_session.max_bytes;w._edit_session.max_bytes=1
        try:
            try:w.edit_sps('config.source_energy','capacity')
            except TransactionCapacityError:pass
            else:raise AssertionError('capacity accepted')
        finally:w._edit_session.max_bytes=capacity
        assert snapshot_to_json(w._edit_session.current())==before
        original=w._project_sps; calls=[]
        def fail_once(state):
            calls.append(1);original(state)
            if len(calls)==1:raise RuntimeError('SPS first projection')
        with patch.object(w,'_project_sps',fail_once):
            try:w.edit_sps('config.source_energy','projection')
            except TransactionApplyError as error:assert error.rollback is None
            else:raise AssertionError('projection accepted')
        assert snapshot_to_json(w._edit_session.current())==before
        def fail_twice(state):original(state);raise RuntimeError('SPS rollback failed')
        with patch.object(w,'_project_sps',fail_twice):
            try:w.edit_sps('config.source_energy','both')
            except TransactionApplyError as error:assert error.rollback is not None
            else:raise AssertionError('double failure accepted')
        assert w._workspace_fault and not w.can_mutate_workspace('run')
        assert w.restore_last_verified_workspace() and w._generated_package_stale
    print('AR4 SPS Qt authority/actions/raw/rollback checks passed; no backend')
    return 0

if __name__=='__main__':raise SystemExit(main())
