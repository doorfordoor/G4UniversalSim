"""AR4 bounded run/path data contract. Does not import or construct Qt."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui'))
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, snapshot_to_json, snapshot_from_json
from g4usim_gui.core.edit_transactions import EditSession, TransactionConflict, TransactionApplyError
from g4usim_gui.core.run_path_model import (
    BINDINGS, RAW_BINDINGS, reduce_run_path, run_path_projection, path_settings,
)


class RunPathContract(unittest.TestCase):
    def initial(self):
        p = G4USimProject()
        p.threads, p.runSettings.threads = 2, 7
        p.seed, p.runSettings.seed = ' 0042 ', 83
        p.runName, p.runSettings.run_name = 'flat', 'typed'
        p.executable, p.pathSettings.executable = 'flat-exe', 'typed-exe'
        p.geometrySettings.config_path = 'geometry-priority'
        p.pathSettings.geometry_config = 'paths-fallback'
        return WorkspaceSnapshot(p)

    def test_loaded_difference_and_read_only_projection(self):
        s = self.initial()
        encoded = snapshot_to_json(s)
        v = run_path_projection(s)
        assert (v['project.threads'], v['config.threads']) == (2, 7)
        assert v['config.seed'] == '83'
        assert v['config.geometry_config'] == 'geometry-priority'
        assert snapshot_to_json(s) == encoded
        assert snapshot_to_json(snapshot_from_json(encoded)) == encoded
        assert s.state['drafts'] == {}

    def test_every_binding_edit_codec_undo_redo(self):
        actions = {
            'project.project_name': '  renamed  ', 'project.run_input_mode': 'external',
            'project.executable': ' missing exe ', 'project.workspace_root': ' ../relative ',
            'project.config_path': ' missing/main.ini ', 'project.macro_path': '',
            'project.output_dir': ' output ', 'project.runs_root': '',
            'project.threads': 11, 'project.seed': '1e', 'project.run_name': '  name  ',
            'config.run_name': '  run  ', 'config.threads': 13, 'config.seed': ' 0042 ',
            'config.beam_on': 0, 'config.check_overlaps': True, 'config.dry_run': True,
            'config.materials_config': ' invalid/materials ', 'config.geometry_config': ' ./shape ',
        }
        assert set(actions) == BINDINGS
        for key, value in actions.items():
            with self.subTest(binding=key):
                session = EditSession(self.initial())
                before = snapshot_to_json(session.current())
                session.transact(key, lambda s: reduce_run_path(s, key, value))
                after = snapshot_to_json(session.current())
                assert before != after
                assert snapshot_to_json(snapshot_from_json(after)) == after
                assert snapshot_to_json(session.undo()) == before
                assert snapshot_to_json(session.redo()) == after
                assert session.history_count == 1
        # Existing project/editor imports reach i18n (and Qt types); no app or widget is created.
        from PySide6.QtWidgets import QApplication
        assert QApplication.instance() is None

    def test_seed_names_and_group_mirrors(self):
        for prefix in ('project', 'config'):
            for raw, typed in [('1e', None), ('', None), (' \t ', None), (' 0042 ', 42)]:
                s = reduce_run_path(self.initial(), prefix + '.seed', raw)
                assert s.project.runSettings.seed == typed
                assert s.project.seed == raw.strip()
                assert run_path_projection(s)['project.seed'] == raw
                assert run_path_projection(s)['config.seed'] == raw
        s = reduce_run_path(self.initial(), 'project.run_name', ' \t ')
        assert s.project.runName == ''
        assert s.project.runSettings.run_name == 'demo'
        s = reduce_run_path(self.initial(), 'config.run_name', '\u3000')
        assert s.project.runName == '\u3000'
        s = reduce_run_path(self.initial(), 'config.run_name', ' \t ')
        assert s.project.runName == 'gui_run'
        s = reduce_run_path(self.initial(), 'project.project_name', '')
        assert (s.project.threads, s.project.runSettings.threads) == (2, 2)
        s = reduce_run_path(self.initial(), 'config.dry_run', True)
        assert (s.project.threads, s.project.runSettings.threads) == (7, 7)

    def test_raw_spelling_never_parsed_and_paths_no_io(self):
        for key in RAW_BINDINGS:
            for raw in ('', '-', '1.234', '1\u202f234'):
                before = self.initial()
                s = reduce_run_path(before, key, raw)
                assert s.state['drafts'][key] == raw
                assert s.project.runSettings == before.project.runSettings
                assert s.project.threads == before.project.threads
        s = reduce_run_path(self.initial(), 'project.output_dir', ' some/missing ')
        assert s.project.runsRoot == ''
        assert s.project.pathSettings.runs_root == ''
        assert path_settings(s.project).runs_root == 'some/missing'
        s = reduce_run_path(s, 'config.geometry_config', ' bad path ')
        assert s.project.pathSettings.geometry_config == 'bad path'
        assert s.project.geometrySettings.config_path == 'bad path'

    def test_reject_atomically_and_existing_transaction_guards(self):
        s = self.initial()
        before = snapshot_to_json(s)
        for key, value in [('config.beam_on', -1), ('config.beam_on', 2000000001),
                           ('project.threads', 0), ('config.threads', 1025),
                           ('project.threads', True), ('config.dry_run', 1),
                           ('config.seed', 42), ('project.run_input_mode', 'invalid'),
                           ('not.registered', 'x'), ('config.threads.raw', 1)]:
            with self.assertRaises(ValueError):
                reduce_run_path(s, key, value)
            assert snapshot_to_json(s) == before
        session = EditSession(s)
        with self.assertRaises(TransactionConflict):
            session.transact('stale', lambda x: reduce_run_path(x, 'config.seed', '1'), expected_revision=99)
        seen = []
        def fail_once(candidate):
            seen.append(candidate)
            if len(seen) == 1:
                raise RuntimeError('projection rejected')
        with self.assertRaises(TransactionApplyError):
            session.transact('failed', lambda x: reduce_run_path(x, 'config.seed', '1'), apply=fail_once)
        assert len(seen) == 2
        assert snapshot_to_json(session.current()) == before
        assert session.revision == 0


    def test_sps_scalar_and_raw_actions(self):
        from g4usim_gui.core import sps_edit_model as sps
        from g4usim_gui.core.edit_snapshot import snapshot_from_json
        from PySide6.QtWidgets import QApplication
        assert QApplication.instance() is None
        initial = WorkspaceSnapshot(G4USimProject())
        initial.project.sourceSettings.energy = '77 MeV'
        initial.project.sourceEditor.energy = '11 MeV'
        initial.project.sourceEditor.position_mode = 'plane'
        initial.project.sourceEditor.position_type = 'plane'
        initial.project.sourceEditor.source_shape = 'rectangle'
        initial.project.sourceEditor.angular_mode = 'isotropic'
        unchanged = snapshot_to_json(initial)
        assert len(sps.BINDINGS) == 76 and len(sps.RAW_BINDINGS) == 7
        for key, (_, _, kind, _) in sps.SCALARS.items():
            value = True if kind == 'bool' else sps.RANGES[key][0] if kind == 'int' else '  new raw  '
            changed = sps.reduce_sps(initial, key, value)
            assert changed.state['drafts'][key] == value
            assert snapshot_to_json(initial) == unchanged
            restored = snapshot_from_json(snapshot_to_json(changed))
            assert snapshot_to_json(restored) == snapshot_to_json(changed)
            session = EditSession(initial)
            session.replace('SPS field', changed)
            session.undo()
            assert snapshot_to_json(session.current()) == unchanged
            session.redo()
            assert snapshot_to_json(session.current()) == snapshot_to_json(changed)
        for key in sps.RAW_BINDINGS:
            changed = sps.reduce_sps(initial, key, '-')
            assert changed.state['drafts'][key] == '-'
            assert changed.project.sourceSettings.energy == '77 MeV'
        quick = sps.reduce_sps(initial, 'config.source_energy', ' 2 MeV ')
        assert quick.project.sourceEditor.energy == '2 MeV'
        assert quick.project.sourceSettings.energy == '2 MeV'
        assert quick.project.sourceEditor.position_mode == 'plane'
        assert quick.project.sourceEditor.source_shape == 'rectangle'
        assert quick.project.sourceEditor.angular_mode == 'isotropic'
        assert quick.state['drafts']['config.source_energy'] == ' 2 MeV '
        advanced = sps.reduce_sps(initial, 'config.scoring_editor_bins', 0)
        assert advanced.project.scoringEditor.hist_bins == 0
        assert sps.sps_projection(advanced)['config.hist_bins'] == 1
        with self.assertRaises(ValueError): sps.reduce_sps(initial, 'config.hist_bins', 0)
        with self.assertRaises(TypeError): sps.reduce_sps(initial, 'config.source_energy', None)
        assert snapshot_to_json(initial) == unchanged

    def test_sps_rows_modules_and_stale_actions(self):
        from dataclasses import fields
        from g4usim_gui.core import sps_edit_model as sps
        from g4usim_gui.core.edit_snapshot import snapshot_from_json
        initial = WorkspaceSnapshot(G4USimProject())
        for collection, (owner, cls) in sps.COLLECTIONS.items():
            first = sps.reduce_sps_structure(initial, {'kind':'row','key':collection,'op':'add',
                'new_id':'caller-supplied-1','revision':0}, revision=0)
            ref = sps.row_reference(first, collection, 0, 1)
            row = getattr(getattr(first.project, owner), collection)[0]
            for field in fields(cls):
                if field.name == 'editor_id': continue
                value = not getattr(row,field.name) if type(getattr(row,field.name)) is bool else ' invalid hidden draft '
                action = {'kind':'row','key':collection,'op':'set','index':0,'reference':ref,
                          'field':field.name,'value':value,'revision':1}
                edited = sps.reduce_sps_structure(first,action,revision=1)
                assert getattr(getattr(getattr(edited.project,owner),collection)[0],field.name) == value
                assert snapshot_to_json(snapshot_from_json(snapshot_to_json(edited))) == snapshot_to_json(edited)
                with self.assertRaises(TransactionConflict): sps.reduce_sps_structure(first,action,revision=2)
                bad = dict(action, reference=dict(ref,digest='wrong'))
                with self.assertRaises(TransactionConflict): sps.reduce_sps_structure(first,bad,revision=1)
            duplicate = sps.reduce_sps_structure(first, {'kind':'row','key':collection,'op':'duplicate',
                'index':0,'reference':ref,'new_id':'caller-supplied-2','revision':1},revision=1)
            rows = getattr(getattr(duplicate.project,owner),collection)
            assert len(rows)==2
            if collection == 'gps_sources': assert rows[0].editor_id != rows[1].editor_id
            moved = sps.reduce_sps_structure(duplicate, {'kind':'row','key':collection,'op':'move','index':1,
                'target':0,'reference':sps.row_reference(duplicate,collection,1,2),'revision':2},revision=2)
            assert sps.row_digest(getattr(getattr(moved.project,owner),collection)[0]) == sps.row_digest(rows[1])
            removed = sps.reduce_sps_structure(moved, {'kind':'row','key':collection,'op':'remove','index':0,
                'reference':sps.row_reference(moved,collection,0,3),'revision':3},revision=3)
            assert len(getattr(getattr(removed.project,owner),collection))==1
        for key in sps.MODULES:
            value = initial
            for revision in (0,1):
                value=sps.reduce_sps_structure(value,{'kind':'module','key':key,'op':'add','value':'UnknownConstructor','revision':revision},revision=revision)
            assert getattr(value.project.physicsEditor,key)==['UnknownConstructor','UnknownConstructor']
            value=sps.reduce_sps_structure(value,{'kind':'module','key':key,'op':'remove','index':0,'revision':2},revision=2)
            assert getattr(value.project.physicsEditor,key)==['UnknownConstructor']
        for key in ('gamma','e-','e+','proton'):
            a=sps.reduce_sps_structure(initial,{'kind':'cut','key':key,'value':' ','revision':0},revision=0)
            assert a.project.physicsEditor.particle_cuts[key]==' '
            b=sps.reduce_sps_structure(a,{'kind':'cut','key':key,'value':'','revision':1},revision=1)
            assert key not in b.project.physicsEditor.particle_cuts
        for key,value in [('source.multiple_vertex',True),('source.phase_space_file',' relative, path.csv '),('source.phase_space_recycle',True)]:
            a=sps.reduce_sps_structure(initial,{'kind':'top','key':key,'value':value,'revision':0},revision=0)
            assert getattr(a.project.sourceEditor,key.split('.')[1])==value


    def test_sps_dynamic_accepted_raw_gate(self):
        from g4usim_gui.core import sps_edit_model as sps
        from g4usim_gui.core.experiment_workflow import _draft_value, _raw_diagnostics, _field_report
        from g4usim_gui.validators.config_validator import ValidationReport
        initial=WorkspaceSnapshot(G4USimProject())
        dynamic=[key for key in sps.BINDINGS if key.count('.')>1]
        assert len(dynamic)==20
        for key in dynamic:
            accepted=_draft_value(initial.project,key)
            snapshot=WorkspaceSnapshot(initial.project)
            snapshot.state['drafts'][key]=accepted
            report=ValidationReport();_raw_diagnostics(snapshot,report)
            assert report.can_run, (key,report.errors)
            snapshot.state['drafts'][key] = not accepted if type(accepted) is bool else accepted+1 if type(accepted) is int else 'definitely invalid raw'
            report=ValidationReport();_raw_diagnostics(snapshot,report)
            assert not report.can_run, key
        for key in ('config.scoring_filter.dose.unknown','config.scoring_spectrum.unknown.bins','config.scoring_filter.dose.enabled.extra'):
            with self.assertRaises(KeyError):_draft_value(initial.project,key)
            initial.state['drafts'][key]='bad'
        report=ValidationReport();_raw_diagnostics(initial,report)
        assert not report.can_run
        for key in sps.RAW_BINDINGS:
            snapshot=sps.reduce_sps(WorkspaceSnapshot(G4USimProject()),key,'-')
            assert snapshot.state['drafts'][key[:-4]] is not None
            report=_field_report(snapshot)
            assert any(d.code=='experiment.raw_spin.unaccepted' for d in report.diagnostics), key


if __name__ == '__main__':
    # Explicit suite also works under the formal assertion probe's runpy path;
    # unittest.main() would discover the probe's __main__, not this module.
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(RunPathContract))
    raise SystemExit(0 if result.wasSuccessful() else 1)
