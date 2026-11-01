"""Pure synthetic validation self-checks. No Git calls, actual candidate mapping or runtime imports."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('mapping_checker', Path(__file__).with_name('check_mapping.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Validation(unittest.TestCase):
    def setUp(self):
        self.future = 'a' * 40  # Synthetic value; never looked up or mapped.
        self.anchor = {'scope_sha256': 'b' * 64}
        self.original = {p: b'old\n' for p in sorted(m.SMOKES)}
        self.changed = {p: b'new\n' for p in self.original}
        self.plan = {'schema': 'g4usim_native_mapping_allowlist_v1', 'status': 'frozen', 'frozen_by': 'main',
                     'base_head': m.BASE, 'candidate_head': self.future, 'scope_sha256': 'b' * 64,
                     'allowed_changes': [{'path': p, 'kind': 'smoke', 'before_sha256': m.digest(self.original[p]),
                                          'after_sha256': m.digest(self.changed[p])} for p in self.original]}
        self.before = {p: {'mode': '100644', 'kind': 'blob', 'oid': '1' * 40} for p in self.original}
        self.after = {p: {'mode': '100644', 'kind': 'blob', 'oid': '2' * 40} for p in self.original}

    def plan_valid(self):
        return m.allowlist(self.plan, self.future, self.anchor)

    def test_exact_two_smoke_diff_validation_only(self):
        m.check_diff(self.before, self.after, self.plan_valid(), self.original, self.changed)

    def test_runtime_change_refused(self):
        self.after['gui/g4usim_gui/core/run_editor_model.py'] = {'mode': '100644', 'kind': 'blob', 'oid': '3' * 40}
        with self.assertRaises(m.Rejected):
            m.check_diff(self.before, self.after, self.plan_valid(), self.original, self.changed)

    def test_unapproved_resource_added_refused(self):
        self.after['gui/g4usim_gui/core/extra-resource.json'] = {'mode': '100644', 'kind': 'blob', 'oid': '3' * 40}
        with self.assertRaises(m.Rejected):
            m.check_diff(self.before, self.after, self.plan_valid(), self.original, self.changed)

    def test_runtime_disguised_as_docs_refused(self):
        for path in ('gui/g4usim_gui/core/i18n.py', 'schema/config_schema.json', 'CMakeLists.txt',
                     'packaging/build_package.py', '.github/workflows/linux-geant4.yml'):
            plan = copy.deepcopy(self.plan)
            plan['allowed_changes'].append({'path': path, 'kind': 'docs', 'before_sha256': None, 'after_sha256': 'c' * 64})
            with self.assertRaises(m.Rejected):
                m.allowlist(plan, self.future, self.anchor)

    def test_extra_smoke_refused(self):
        self.plan['allowed_changes'].append({'path': 'gui/smoke_tests/smoke_main_window_ui.py', 'kind': 'smoke',
                                              'before_sha256': 'c' * 64, 'after_sha256': 'd' * 64})
        with self.assertRaises(m.Rejected): self.plan_valid()

    def test_main_freeze_head_scope_mismatch_refused(self):
        for key, value in (('status', 'template_not_frozen'), ('frozen_by', 'author'),
                           ('candidate_head', m.BASE), ('scope_sha256', 'e' * 64)):
            plan = copy.deepcopy(self.plan); plan[key] = value
            with self.assertRaises(m.Rejected): m.allowlist(plan, self.future, self.anchor)

    def test_explicit_document_blob_change(self):
        path = 'docs/J2-editing.md'
        self.plan['allowed_changes'].append({'path': path, 'kind': 'docs', 'before_sha256': None, 'after_sha256': m.digest(b'doc\n')})
        self.after[path] = {'mode': '100644', 'kind': 'blob', 'oid': '4' * 40}
        self.changed[path] = b'doc\n'
        m.check_diff(self.before, self.after, self.plan_valid(), self.original, self.changed)

    def test_unlisted_document_refused(self):
        self.after['docs/unapproved.md'] = {'mode': '100644', 'kind': 'blob', 'oid': '4' * 40}
        with self.assertRaises(m.Rejected):
            m.check_diff(self.before, self.after, self.plan_valid(), self.original, self.changed)

    def test_duplicate_path_refused(self):
        self.plan['allowed_changes'].append(copy.deepcopy(self.plan['allowed_changes'][0]))
        with self.assertRaises(m.Rejected): self.plan_valid()

    def test_symlink_executable_and_submodule_modes_refused(self):
        for mode in ('120000', '100755', '160000'):
            after = copy.deepcopy(self.after); after[next(iter(after))]['mode'] = mode
            with self.assertRaises(m.Rejected):
                m.check_diff(self.before, after, self.plan_valid(), self.original, self.changed)

    def test_frozen_blob_tamper_refused(self):
        changed = dict(self.changed); changed[next(iter(changed))] = b'not frozen\n'
        with self.assertRaises(m.Rejected):
            m.check_diff(self.before, self.after, self.plan_valid(), self.original, changed)

    def test_unused_allowlist_entry_refused(self):
        self.after[next(iter(self.after))] = copy.deepcopy(self.before[next(iter(self.before))])
        with self.assertRaises(m.Rejected):
            m.check_diff(self.before, self.after, self.plan_valid(), self.original, self.changed)

    def test_ambiguous_path_and_duplicate_json_refused(self):
        for path in ('../x', 'docs/../gui/a.py', 'docs\\x', '/tmp/x', 'docs/x\ny', 'docs//x'):
            with self.assertRaises(m.Rejected): m.relative(path)
        with self.assertRaises(m.Rejected): json.loads('{"k":1,"k":2}', object_pairs_hook=m.unique_object)


if __name__ == '__main__':
    unittest.main(verbosity=2)
