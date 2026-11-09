"""Bound document editor component checks, without starting a backend."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from smoke_f5_editor_history import owned_window
from g4usim_gui.core.edit_snapshot import snapshot_to_json, snapshot_from_json
from unittest.mock import patch


def main():
    app = QApplication.instance() or QApplication([])
    evidence_parent = os.environ.get('G4USIM_TEST_EVIDENCE_DIR')
    if evidence_parent:
        Path(evidence_parent).mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='document-', dir=evidence_parent))
    print('Document component evidence:', root, flush=True)
    with owned_window(app, root / 'recovery') as window:
        page = window.config_builder_page
        window.show()
        window.page_stack.setCurrentWidget(page)
        page.workspace_tabs.setCurrentIndex(0)
        app.processEvents()
        before = window._edit_session.current()
        count = len(before.project.materialEditor.rows)
        page._add_material('mass_fraction')
        assert len(window._edit_session.current().project.materialEditor.rows) == count + 1
        page.materials_table.selectRow(count)
        page.material_name.setText('  Sample  ')
        page.material_density.setText('-')
        page._update_selected_material_from_detail()
        current = window._edit_session.current()
        assert current.project.materialEditor.rows[count].name == 'Sample'
        assert current.project.materialEditor.rows[count].density == '-'
        assert current.state['drafts'][f'detail.material.{count}.name'] == '  Sample  '
        page.material_document.rows[count].name = 'POISON'
        assert window.capture_workspace().project.materialEditor.rows[count].name == 'Sample'
        window.undo_edit()
        assert window._edit_session.current().project.materialEditor.rows[count].name != 'Sample'
        window.redo_edit()
        assert window._edit_session.current().project.materialEditor.rows[count].name == 'Sample'
        page.materials_table.selectRow(count)
        page.material_name.setFocus()
        page.material_name.selectAll()
        QTest.keyClicks(page.material_name, 'TypedSample')
        assert window._edit_session.current().project.materialEditor.rows[count].name == 'TypedSample'
        assert page.material_name.text() == 'TypedSample' and page.material_name.cursorPosition() == len('TypedSample')
        # Interior insertion detects cursor resets hidden by append-only typing.
        page.material_name.setCursorPosition(5)
        for offset, char in enumerate('XYZ', 1):
            QTest.keyClicks(page.material_name, char)
            app.processEvents()
            expected = 'Typed' + 'XYZ'[:offset] + 'Sample'
            assert page.material_name.hasFocus()
            assert page.material_name.cursorPosition() == 5 + offset
            assert page.material_name.text() == expected
            assert window._edit_session.current().project.materialEditor.rows[count].name == expected
        page.workspace_tabs.setCurrentIndex(1)
        app.processEvents()
        page._document_action({'kind':'geometry_scalar','binding':'config.geometry_template','value':'hierarchical'})
        page._add_hierarchical_volume()
        row = len(window._edit_session.current().project.geometryEditor.volumes)-1
        page.geometry_table.setCurrentCell(row,1)
        page.geometry_table.editItem(page.geometry_table.item(row,1))
        editor=next(e for e in page.geometry_table.findChildren(QLineEdit) if hasattr(e,'_document_ref'))
        old_name=window._edit_session.current().project.geometryEditor.volumes[row].name
        editor.selectAll()
        editor.setFocus()
        for offset, char in enumerate('PendingName', 1):
            QTest.keyClicks(editor, char)
            app.processEvents()
            assert editor.hasFocus()
            assert editor.cursorPosition() == offset
            assert editor._document_ref.revision == window._edit_session.revision
            assert window._edit_session.current().state['tables']['geometry_table'][row][1] == 'PendingName'[:offset]
        current=window._edit_session.current()
        assert current.state['tables']['geometry_table'][row][1]=='PendingName'
        assert current.project.geometryEditor.volumes[row].name==old_name
        assert editor.text()=='PendingName' and editor.cursorPosition()==len('PendingName')
        # Structural permutation and undo retain the unfinished editor on its entity.
        ref=editor._document_ref
        window.edit_document({'kind':'geometry_structure','collection':'volume','operation':'move','ref':ref,'direction':-1})
        assert window._edit_session.current().state['selections']['pending_geometry_table_row']==row-1
        window.undo_edit()
        assert window._edit_session.current().state['selections']['pending_geometry_table_row']==row
        editor=next(e for e in page.geometry_table.findChildren(QLineEdit)
                    if hasattr(e,'_document_ref') and not e.isHidden() and not getattr(e,'_document_retired',False))
        assert editor._document_ref.revision==window._edit_session.revision
        assert editor.text()=='PendingName'
        from g4usim_gui.core.project import load_project
        saved=root/'pending-project.json'
        assert window._save_project_to(saved)
        window._set_project(load_project(saved))
        assert window._edit_session.current().state['tables']['geometry_table'][row][1]=='PendingName'
        assert window._edit_session.current().project.geometryEditor.volumes[row].name==old_name
        editor=next(e for e in page.geometry_table.findChildren(QLineEdit)
                    if hasattr(e,'_document_ref') and not e.isHidden() and not getattr(e,'_document_retired',False))
        assert editor._document_ref.revision==window._edit_session.revision
        QTest.keyClick(editor,Qt.Key_Escape)
        app.processEvents()
        current=window._edit_session.current()
        assert current.project.geometryEditor.volumes[row].name==old_name
        assert current.state['tables']['geometry_table'][row][1]=='PendingName'
        assert 'pending_geometry_table_row' not in current.state['selections']
        page.geometry_table.editItem(page.geometry_table.item(row,1))
        app.processEvents()
        editor=next(e for e in page.geometry_table.findChildren(QLineEdit)
                    if hasattr(e,'_document_ref') and not e.isHidden())
        editor.selectAll()
        QTest.keyClicks(editor,'CommittedName')
        QTest.keyClick(editor,Qt.Key_Return)
        app.processEvents()
        assert window._edit_session.current().project.geometryEditor.volumes[row].name=='CommittedName'
        window.undo_edit()
        assert window._edit_session.current().project.geometryEditor.volumes[row].name==old_name
        # Close the earlier intentional raw mismatch before isolating source admission.
        from g4usim_gui.core.document_edit_model import row_ref
        window.edit_document({'kind':'geometry_cell','ref':row_ref(window._edit_session.current(),'volume',row,window._edit_session.revision),'column':1,'raw':old_name})
        # Failure is an operation result, not a new snapshot or failed source receipt.
        source=root/'materials.ini'
        source.write_text('[material.Sample]\nmaterial = G4_Si\n',encoding='utf-8')
        window.edit_run_path('config.materials_config',str(source))
        result=page.reload_materials()
        assert result['status']=='read_success', result
        captured=window._edit_session.current()
        assert captured.state['sources']['materials']['read_success'] is True
        source.unlink()
        before=snapshot_to_json(window._edit_session.current())
        revision=window._edit_session.revision
        result=page.reload_materials()
        assert result['status']=='read_failed' and window._edit_session.revision==revision
        assert snapshot_to_json(window._edit_session.current())==before
        source.write_text('',encoding='utf-8')
        result=page.reload_materials()
        assert result['status']=='read_success'
        assert window._edit_session.current().state['sources']['materials']['text']==''
        # No-source is non-destructive, and A/B mismatch never rewrites A's receipt.
        window.edit_run_path('config.materials_config','')
        before=snapshot_to_json(window._edit_session.current())
        revision=window._edit_session.revision
        assert page.reload_materials()['status']=='no_source'
        assert before==snapshot_to_json(window._edit_session.current()) and revision==window._edit_session.revision
        source.write_text('[material.Sample]\nmaterial = G4_Si\n',encoding='utf-8')
        window.edit_run_path('config.materials_config',str(source))
        assert page.reload_materials()['status']=='read_success'
        window.edit_run_path('config.materials_config',str(root/'absent-B.ini'))
        before=snapshot_to_json(window._edit_session.current())
        assert page.reload_materials()['status']=='read_failed'
        assert snapshot_to_json(window._edit_session.current())==before
        try: window._require_document_input()
        except ValueError: pass
        else: raise AssertionError('A receipt admitted for B')
        window.edit_run_path('config.materials_config',str(source))
        window._require_document_input()
        source.write_text('# changed externally\n',encoding='utf-8')
        try: window._require_document_input()
        except ValueError: pass
        else: raise AssertionError('changed source admitted')
        source.write_text('[material.Sample]\nmaterial = G4_Si\n',encoding='utf-8')
        window._require_document_input()  # current same A requires no synthetic failed-read latch
        # Persistence includes raw/pending and sources; the view cannot backwrite it.
        snapshot=window._edit_session.current()
        assert snapshot_to_json(snapshot_from_json(snapshot_to_json(snapshot)))==snapshot_to_json(snapshot)
        window.apply_workspace(snapshot_from_json(snapshot_to_json(snapshot)))
        assert snapshot_to_json(window.capture_workspace())==snapshot_to_json(snapshot)
        # Raw is checked at actual finite input boundaries before allocating/requesting.
        from g4usim_gui.core.document_edit_model import row_ref
        ref=row_ref(window._edit_session.current(),'volume',row,window._edit_session.revision)
        window.edit_document({'kind':'geometry_buffer','ref':ref,'column':1,'raw':'unaccepted raw'})
        with patch('g4usim_gui.window.content.generated_inputs',side_effect=AssertionError('allocated')) as factory, \
             patch.object(window.geometry_controller,'request',side_effect=AssertionError('backend requested')) as request:
            page.validate_current(window.project)
            window.export_backend_geometry(auto=True)
            assert factory.call_count==request.call_count==0
            try: window.scan_base()
            except ValueError: pass
            else: raise AssertionError('scan admitted raw')
        from g4usim_gui.core.experiment_workflow import document_raw_diagnostics, document_source_diagnostics
        from g4usim_gui.validators.config_validator import ValidationReport
        candidate=window._edit_session.current()
        report=ValidationReport();document_raw_diagnostics(candidate,report)
        assert report.errors
        candidate.project.runInputMode='external'
        report=ValidationReport();document_raw_diagnostics(candidate,report);document_source_diagnostics(candidate,report)
        assert not report.errors
        candidate.project.runInputMode='generated'
        report=ValidationReport();document_raw_diagnostics(candidate,report)
        assert report.errors
        # Preparation rejection preserves generated display; double projection failure freezes.
        from g4usim_gui.core.edit_transactions import TransactionApplyError
        before=snapshot_to_json(window._edit_session.current())
        window._generated_package_dir='existing-display'
        window._generated_package_stale=False
        page.set_package_path('existing-display')
        display=page.package_label.text()
        try: window.edit_document({'kind':'geometry_scalar','binding':'invalid','value':'x'})
        except ValueError: pass
        else: raise AssertionError('invalid action accepted')
        assert before==snapshot_to_json(window._edit_session.current()), 'preparation changed snapshot'
        assert page.package_label.text()==display, (display,page.package_label.text())
        original=window._project_materials
        def fail_both(state):
            original(state)
            raise RuntimeError('document projection failure')
        with patch.object(window,'_project_materials',fail_both):
            try: window.edit_document({'kind':'material_add','mode':'nist'})
            except TransactionApplyError as error: assert error.rollback is not None
            else: raise AssertionError('double failure accepted')
        assert window._workspace_fault and not window.can_mutate_workspace('run')
        assert before==snapshot_to_json(window._edit_session.current())
        assert window.restore_last_verified_workspace()
        print('C02-C04 source/raw/admission/persistence/rejection/double-failure checks passed')
    print('AR4 material Qt component milestone passed')


def standalone_contract():
    from g4usim_gui.widgets.config_builder_page import ConfigBuilderPage
    from g4usim_gui.core.project import G4USimProject
    from g4usim_gui.editors.material_editor_model import MaterialDocument
    app=QApplication.instance() or QApplication([])
    page=ConfigBuilderPage()
    project=G4USimProject();project.materialEditor=MaterialDocument()
    with patch.object(page,'reload_materials',side_effect=AssertionError('empty document reloaded')):
        page.set_from_project(project)
    assert page.material_document.rows==[]
    page._document_action({'kind':'geometry_scalar','binding':'config.geometry_template','value':'hierarchical'})
    page._add_hierarchical_volume()
    page.show();page.workspace_tabs.setCurrentIndex(1);app.processEvents()
    row=len(page.geometry_document.volumes)-1
    typed=page.geometry_document.volumes[row].name
    page.geometry_table.setCurrentCell(row,1)
    page.geometry_table.editItem(page.geometry_table.item(row,1))
    editor=next(e for e in page.geometry_table.findChildren(QLineEdit) if hasattr(e,'_document_ref') and not e.isHidden())
    editor.selectAll();QTest.keyClicks(editor,'standalone pending')
    assert page._document_snapshot().state['tables']['geometry_table'][row][1]=='standalone pending'
    assert page.geometry_document.volumes[row].name==typed
    QTest.keyClick(editor,Qt.Key_Escape);app.processEvents()
    assert page._document_snapshot().state['tables']['geometry_table'][row][1]=='standalone pending'
    assert 'pending_geometry_table_row' not in page._document_snapshot().state['selections']
    page.close();page.deleteLater();app.processEvents()
    print('Standalone explicit empty document and pending raw adapter passed')


def programmatic_contract():
    from g4usim_gui.core.project import load_project
    app=QApplication.instance() or QApplication([])
    parent=os.environ.get('G4USIM_TEST_EVIDENCE_DIR')
    if parent: Path(parent).mkdir(parents=True,exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='programmatic-',dir=parent))
    with owned_window(app,root/'recovery') as window:
        page=window.config_builder_page
        page._add_hierarchical_volume()
        row=len(window._edit_session.current().project.geometryEditor.volumes)-1
        page.geometry_table.selectRow(row)
        count=window._edit_session.history_count
        page.volume_details.fields['size'].setText('2 mm,3 mm,4 mm')
        assert window.capture_workspace().project.geometryEditor.volumes[row].size=='2 mm,3 mm,4 mm'
        assert window._edit_session.history_count==count+1
        count=window._edit_session.history_count
        page.volume_details.fields['copy_no'].setText('23')
        assert window.capture_workspace().project.geometryEditor.volumes[row].copy_no=='23'
        assert window._edit_session.history_count==count+1
        target=root/'direct-save.json'
        assert window._save_project_to(target)
        saved=load_project(target)
        assert saved.geometryEditor.volumes[row].size=='2 mm,3 mm,4 mm'
        assert saved.geometryEditor.volumes[row].copy_no=='23'
        # Programmatic scalar/detail setters share the same immediate action path.
        page.simple_target_size.setText('7 mm,8 mm,9 mm')
        assert window.capture_workspace().project.geometryEditor.simple_box.target_size=='7 mm,8 mm,9 mm'
        page._add_layer()
        layer=page._selected_layer_row
        page.layer_thickness.setText(' 3 mm ')
        capture=window.capture_workspace()
        assert capture.project.geometryEditor.layered_device.layers[layer].thickness=='3 mm'
        assert capture.state['drafts'][f'detail.layer.{layer}.thickness']==' 3 mm '
        page._add_material('mass_fraction')
        material=page._selected_material_row
        page.material_density.setText(' 4 g/cm3 ')
        capture=window.capture_workspace()
        assert capture.project.materialEditor.rows[material].density=='4 g/cm3'
        assert capture.state['drafts'][f'detail.material.{material}.density']==' 4 g/cm3 '
        window.flush_pending_edit()
        before=snapshot_to_json(window._edit_session.current())
        facts=(window._edit_session.revision,window._edit_session.history_count,window._edit_session.history_bytes)
        window._project_documents(window._edit_session.current())
        app.processEvents();window.flush_pending_edit()
        assert before==snapshot_to_json(window._edit_session.current())
        assert facts==(window._edit_session.revision,window._edit_session.history_count,window._edit_session.history_bytes)
        # Identical setter values and duplicate old callbacks do not create history.
        page.material_density.setText(page.material_density.text())
        page._update_selected_material_from_detail()
        assert facts==(window._edit_session.revision,window._edit_session.history_count,window._edit_session.history_bytes)
    print('Programmatic details/scalars/material/layer direct capture/save and projection/no-duplicate-history passed')


def load_overview_contract():
    import copy
    from g4usim_gui.core.project import G4USimProject
    from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot
    from g4usim_gui.core.edit_transactions import TransactionApplyError, TransactionCapacityError
    from g4usim_gui.editors.material_editor_model import MaterialDocument
    app=QApplication.instance() or QApplication([])
    parent=os.environ.get('G4USIM_TEST_EVIDENCE_DIR')
    if parent: Path(parent).mkdir(parents=True,exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='overview-',dir=parent))
    with owned_window(app,root/'recovery') as window:
        project=G4USimProject();project.materialEditor=MaterialDocument()
        project.pathSettings.materials_config='';project.pathSettings.geometry_config=''
        project.geometrySettings.config_path='';project.geometrySettings.template='hierarchical';project.workspaceRoot=str(root)
        window._edit_session.reset(WorkspaceSnapshot(project),apply=window.apply_workspace)
        window.history_changed()
        page=window.config_builder_page
        def assert_counts(materials,volumes):
            assert page.materials_table.rowCount()==materials
            assert page.geometry_table.rowCount()==volumes
            text=page.workspace_summary.text()
            assert f'Materials: {materials} entries' in text,text
            assert f'Geometry: {volumes} volumes' in text,text
            assert page.materials_table.rowCount()==materials
            assert page.geometry_table.rowCount()==volumes
        assert_counts(0,0)
        materials=root/'materials.ini';materials.write_text('[world]\nmaterial = G4_AIR\n[element.LocalCarbon]\nsymbol = C\nz = 6\na = 12.011 g/mole\n[material.Mix]\ndensity = 1.05 g/cm3\nmode = atom_count\ncomponents = LocalCarbon:2\nstate = solid\n',encoding='utf-8')
        geometry=root/'geometry.ini'
        world='[world]\nshape=box\nsize=1 m,1 m,1 m\nmaterial=G4_AIR\n'
        volume=lambda name: f'\n[volume.{name}]\nparent=world\nshape=box\nsize=1 mm,1 mm,1 mm\nmaterial=G4_Si\n'
        geometry.write_text(world+volume('A')+volume('B'),encoding='utf-8')
        observed=[]
        page.settingsChanged.connect(lambda: observed.append((
            len(window._edit_session.current().project.geometryEditor.volumes),page.workspace_summary.text())))
        read=Path.read_text
        for domain,path,m,v in [('materials',materials,2,0),('geometry',geometry,2,3)]:
            window.edit_run_path(f'config.{domain}_config',str(path))
            calls=[]
            def once(target,*args,**kwargs):
                if target.resolve()==path.resolve(): calls.append(str(target))
                return read(target,*args,**kwargs)
            with patch.object(Path,'read_text',once):
                result=getattr(page,'reload_'+domain)()
            assert result['status']=='read_success'
            assert len(calls)==1,calls
            assert_counts(m,v)  # synchronous: no processEvents/timer/edit to repair display
        assert observed and all(f'Geometry: {n} volumes' in text for n,text in observed),observed
        for domain in ('materials','geometry'):
            window.edit_run_path(f'config.{domain}_config',str(root/(domain+'-missing.ini')))
            before=(snapshot_to_json(window._edit_session.current()),page.workspace_summary.text(),
                    copy.deepcopy(getattr(page,domain+'_summary')))
            assert getattr(page,'reload_'+domain)()['status']=='read_failed'
            assert before==(snapshot_to_json(window._edit_session.current()),page.workspace_summary.text(),
                            getattr(page,domain+'_summary'))
            assert_counts(2,3)
        # A real replacement with a different count must not survive rejection/rollback.
        geometry.write_text(world+volume('A')+volume('B')+volume('C'),encoding='utf-8')
        window.edit_run_path('config.geometry_config',str(geometry))
        before=(snapshot_to_json(window._edit_session.current()),page.workspace_summary.text(),copy.deepcopy(page.geometry_summary))
        original=page._project_document_candidate;calls=[]
        def fail_once(candidate,**kwargs):
            original(candidate,**kwargs);calls.append(1)
            if len(calls)==1: raise RuntimeError('overview projection rejection')
        with patch.object(page,'_project_document_candidate',fail_once):
            try: page.reload_geometry()
            except TransactionApplyError as error: assert error.rollback is None
            else: raise AssertionError('failed projection accepted')
        assert len(calls)==2
        assert before==(snapshot_to_json(window._edit_session.current()),page.workspace_summary.text(),page.geometry_summary)
        assert_counts(2,3)
        limit=window._edit_session.max_bytes;window._edit_session.max_bytes=1
        try:
            try: page.reload_geometry()
            except TransactionCapacityError: pass
            else: raise AssertionError('over-capacity reload accepted')
        finally: window._edit_session.max_bytes=limit
        assert before==(snapshot_to_json(window._edit_session.current()),page.workspace_summary.text(),page.geometry_summary)
        assert_counts(2,3)
    print('Synchronous material/geometry load overview, one-read source, notification and failed reload/rollback counts passed')


if __name__ == '__main__':
    callback_errors=[]
    original_hook=sys.excepthook
    def record_callback_error(kind,value,tb):
        callback_errors.append(str(value))
        original_hook(kind,value,tb)
    sys.excepthook=record_callback_error
    try:
        if '--overview-only' in sys.argv:
            load_overview_contract()
        elif '--programmatic-only' not in sys.argv:
            main()
            standalone_contract()
        if '--overview-only' not in sys.argv:
            programmatic_contract()
            load_overview_contract()
        assert not callback_errors, callback_errors
    finally:
        sys.excepthook=original_hook
