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


if __name__ == '__main__':
    # Explicit suite also works under the formal assertion probe's runpy path;
    # unittest.main() would discover the probe's __main__, not this module.
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(RunPathContract))
    raise SystemExit(0 if result.wasSuccessful() else 1)
