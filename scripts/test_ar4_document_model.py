"""Finite document/session contracts; no QApplication, IO validation or backend."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui'))
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_to_json
from g4usim_gui.core.edit_transactions import EditSession, TransactionConflict, TransactionApplyError
from g4usim_gui.core.document_edit_model import reduce_documents, row_ref, RowRef


def main():
    session = EditSession(WorkspaceSnapshot(G4USimProject()))
    def edit(action):
        session.replace('document', reduce_documents(session.current(), action, revision=session.revision))
    edit({'kind': 'material_add', 'mode': 'mass_fraction'})
    old = session.current()
    ref = row_ref(old, 'material', 0, session.revision)
    edit({'kind': 'material_detail', 'ref': ref, 'values': {
        'name': '  edited  ', 'mode': 'mass_fraction', 'density': '-',
        'components_text': '  G4_Si:1 ', 'enabled': True}})
    assert session.current().project.materialEditor.rows[0].density == '-'
    assert session.current().state['drafts']['detail.material.0.name'] == '  edited  '
    try:
        edit({'kind': 'material_delete', 'ref': ref})
        raise AssertionError('stale reference accepted')
    except TransactionConflict:
        pass
    session.undo()
    assert snapshot_to_json(session.current()) == snapshot_to_json(old)
    session.redo()
    before = session.current()
    history = (session.revision, session.history_count, session.history_bytes, session.can_redo,
               session.saved_fingerprint, session._merge_generation)
    selection = dict(before.state['selections'], materials_table=-1)
    session.update_interaction(selection, expected_revision=session.revision,
                               expected_selections=before.state['selections'])
    assert history == (session.revision, session.history_count, session.history_bytes, session.can_redo,
                       session.saved_fingerprint, session._merge_generation)
    try:
        session.update_interaction({}, expected_revision=session.revision,
                                   expected_selections=before.state['selections'])
        raise AssertionError('stale selection accepted')
    except TransactionConflict:
        pass
    stable = snapshot_to_json(session.current())
    calls = []
    def failing(state):
        calls.append(state)
        if len(calls) == 1:
            raise RuntimeError('projection failure')
    try:
        session.update_interaction({}, expected_revision=session.revision,
                                   expected_selections=selection, apply=failing)
        raise AssertionError('projection error lost')
    except TransactionApplyError as error:
        assert error.rollback is None
    assert len(calls) == 2 and snapshot_to_json(session.current()) == stable
    print('AR4 document material/session milestone passed')


def interaction_revision_contract():
    session = EditSession(WorkspaceSnapshot(G4USimProject()))
    before = snapshot_to_json(session.current())
    calls = []
    for revision in (None, True, False, '0', 0.0, [], {}):
        try:
            session.update_interaction({}, expected_revision=revision, expected_selections={},
                                       apply=calls.append)
            raise AssertionError(f'invalid revision accepted: {revision!r}')
        except TransactionConflict:
            pass
        assert snapshot_to_json(session.current()) == before
        assert session.revision == 0 and session.history_count == 0 and calls == []
    # The existing optional revision API intentionally remains compatible.
    session.replace('unchanged', session.current(), expected_revision=None)
    candidate = reduce_documents(session.current(), {'kind': 'material_add', 'mode': 'nist'}, revision=0)
    ref = row_ref(candidate, 'material', 0, 0)
    before = snapshot_to_json(candidate)
    for invalid in (None, RowRef('material', 0, False, ref.row), RowRef('material', True, 0, ref.row),
                    RowRef('unknown', 0, 0, ref.row), RowRef('material', 0, 0, [])):
        try:
            reduce_documents(candidate, {'kind': 'material_delete', 'ref': invalid}, revision=0)
            raise AssertionError('invalid direct RowRef accepted')
        except (TransactionConflict, ValueError):
            pass
        assert snapshot_to_json(candidate) == before
    print('C01 required revision: seven invalid types rejected; legacy replace unchanged')
    print('Direct RowRef: five invalid payload/type cases rejected without mutation')


def geometry_contract():
    session=EditSession(WorkspaceSnapshot(G4USimProject()))
    def edit(action):
        candidate=reduce_documents(session.current(),action,revision=session.revision)
        session.replace('geometry',candidate)
    edit({'kind':'geometry_scalar','binding':'config.geometry_template','value':'hierarchical'})
    edit({'kind':'geometry_structure','collection':'volume','operation':'add'})
    before=session.current()
    ref=row_ref(before,'volume',1,session.revision)
    edit({'kind':'geometry_buffer','ref':ref,'column':1,'raw':'uncommitted'})
    assert session.current().project.geometryEditor.volumes[1].name==before.project.geometryEditor.volumes[1].name
    ref=row_ref(session.current(),'volume',1,session.revision)
    edit({'kind':'geometry_structure','collection':'volume','operation':'move','ref':ref,'direction':-1})
    moved=session.current()
    assert moved.state['tables']['geometry_table'][0][1]=='uncommitted'
    assert moved.state['selections']['pending_geometry_table_row']==0
    session.undo()
    assert session.current().state['selections']['pending_geometry_table_row']==1
    ref=row_ref(session.current(),'volume',0,session.revision)
    try:
        edit({'kind':'geometry_structure','collection':'volume','operation':'delete','ref':ref})
        raise AssertionError('world deleted')
    except ValueError:
        pass
    edit({'kind':'geometry_structure','collection':'boolean','operation':'add'})
    ref=row_ref(session.current(),'boolean',0,session.revision)
    edit({'kind':'geometry_cell','ref':ref,'column':2,'raw':'not-int'})
    assert session.current().state['tables']['boolean_table'][0][2]=='not-int'
    assert session.current().project.geometryEditor.boolean_ops[0].index==0
    print('Geometry buffer/permutation/world refusal/boolean fallback passed')


def interaction_atomic_contract():
    import copy
    from g4usim_gui.core.edit_transactions import TransactionCapacityError, TransactionError
    from g4usim_gui.core.edit_snapshot import snapshot_size
    session = EditSession(WorkspaceSnapshot(G4USimProject()))
    candidate = reduce_documents(session.current(), {'kind':'material_add','mode':'nist'}, revision=0)
    session.replace('add', candidate)
    session.undo()
    before = session.current()
    commands = copy.deepcopy(session._commands)
    facts = (session.revision, session.history_bytes, session._cursor, session._merge_generation,
             session.saved_fingerprint, session.can_redo, session.is_modified)
    calls = []
    session.update_interaction({'materials_table':-1}, expected_revision=session.revision,
        expected_selections=before.state['selections'], apply=calls.append)
    assert len(calls)==1
    assert session._commands == commands
    assert facts == (session.revision,session.history_bytes,session._cursor,session._merge_generation,
                     session.saved_fingerprint,session.can_redo,session.is_modified)
    current = session.current()
    current.state['selections'] = before.state['selections']
    current.project.editingState = copy.deepcopy(current.state)
    assert snapshot_to_json(current) == snapshot_to_json(before)
    stable = snapshot_to_json(session.current())
    session.update_interaction({'materials_table':-1}, expected_revision=session.revision,
        expected_selections={'materials_table':-1}, apply=lambda _: (_ for _ in ()).throw(AssertionError('no-op applied')))
    limit = session.max_bytes
    session.max_bytes = snapshot_size(session.current())
    try:
        session.update_interaction({'materials_table':-1,'geometry_table':1}, expected_revision=session.revision,
            expected_selections={'materials_table':-1}, apply=calls.append)
        raise AssertionError('capacity accepted')
    except TransactionCapacityError: pass
    finally: session.max_bytes = limit
    assert snapshot_to_json(session.current())==stable and len(calls)==1
    attempts=[]
    def apply_with_reentry(_):
        for operation in (lambda: session.replace('nested',session.current()), session.undo, session.redo,
                          session.mark_saved, session.break_merge, lambda:session.reset(session.current())):
            try: operation()
            except TransactionError: attempts.append('rejected')
            else: raise AssertionError('nested write accepted')
    session.update_interaction({},expected_revision=session.revision,
        expected_selections={'materials_table':-1},apply=apply_with_reentry)
    assert len(attempts)==6
    stable=snapshot_to_json(session.current())
    count=[]
    def fail(_):
        count.append(1)
        raise RuntimeError('first' if len(count)==1 else 'rollback')
    try:
        session.update_interaction({'materials_table':-1},expected_revision=session.revision,
            expected_selections={},apply=fail)
        raise AssertionError('double error lost')
    except TransactionApplyError as error:
        assert str(error.original)=='first' and str(error.rollback)=='rollback'
    assert len(count)==2 and snapshot_to_json(session.current())==stable
    session.redo()
    assert len(session.current().project.materialEditor.rows)==1
    print('C01 codec/history/redo/no-op/capacity/reentry/double failure passed')


def preservation_contract():
    import copy
    from dataclasses import asdict
    from g4usim_gui.core.edit_snapshot import snapshot_from_json
    from g4usim_gui.editors.material_editor_model import MaterialDocument
    p=G4USimProject()
    p.materialEditor=None
    original=WorkspaceSnapshot(p)
    assert snapshot_from_json(snapshot_to_json(original)).project.materialEditor is None
    p.materialEditor=MaterialDocument()
    assert snapshot_from_json(snapshot_to_json(WorkspaceSnapshot(p))).project.materialEditor is not None
    snapshot=reduce_documents(WorkspaceSnapshot(p),{'kind':'geometry_scalar','binding':'config.geometry_template','value':'hierarchical'},revision=0)
    snapshot=reduce_documents(snapshot,{'kind':'geometry_structure','collection':'volume','operation':'add'},revision=0)
    row=snapshot.project.geometryEditor.volumes[1]
    row.shape_properties['unknown-preserved']='raw'
    row.preview_properties['future-property']='value'
    row.visual['vis.future']='kept'
    row.production_cuts['cut.future']='kept'
    snapshot.project.geometryEditor.layered_device.gap='9 mm'
    before=copy.deepcopy(snapshot.project.geometryEditor)
    snapshot=reduce_documents(snapshot,{'kind':'geometry_detail','ref':row_ref(snapshot,'volume',1,0),
        'values':{'copy_no':'17','metadata':'tag','prop.dx1':'4 mm','vis.alpha':'0.5','cut.gamma':'1 mm'}},revision=0)
    actual=snapshot.project.geometryEditor.volumes[1]
    assert actual.shape_properties['unknown-preserved']=='raw' and actual.preview_properties['future-property']=='value'
    assert actual.visual['vis.future']=='kept' and actual.production_cuts['cut.future']=='kept'
    assert snapshot.project.geometryEditor.layered_device==before.layered_device
    original=copy.deepcopy(actual)
    snapshot=reduce_documents(snapshot,{'kind':'geometry_structure','collection':'volume','operation':'duplicate',
        'ref':row_ref(snapshot,'volume',1,0)},revision=0)
    clone=copy.deepcopy(snapshot.project.geometryEditor.volumes[2]);clone.name=original.name
    assert asdict(clone)==asdict(original)
    assert snapshot_from_json(snapshot_to_json(snapshot)).project.geometryEditor==snapshot.project.geometryEditor
    print('Full geometry payload/inactive data/duplicate and None versus empty codec passed')


if __name__ == '__main__':
    if '--interaction-revision-only' in sys.argv:
        interaction_revision_contract()
    else:
        main()
        interaction_revision_contract()
        geometry_contract()
        interaction_atomic_contract()
        preservation_contract()

