"""Real Qt/K1/F5 agent integration; controlled model text, no backend execution."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))

from PySide6.QtCore import QCoreApplication, QLocale, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch

from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.agent.actions import SCHEMA
from g4usim_gui.agent.session import TaskJournal
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint
from g4usim_gui.core.wizard import default_spec
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.widgets.project_page import ProjectPage


def wait(app, predicate, window, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(.005)
    assert False, window.agent_controller.state()


def response(messages, changes=None, questions=None):
    context = json.loads(messages[1]['content'])['context']
    return json.dumps({'schema': SCHEMA, 'base_fingerprint': context['base_fingerprint'],
                       'summary': 'Controlled response, no model/physics claim',
                       'clarifications': questions or [], 'changes': changes or []})


def test_generated_paths_preserve_other_controls(app):
    page = ProjectPage()
    try:
        page.threads.setLocale(QLocale('zh_HK'))
        project = G4USimProject(threads=2)
        page.set_project(project)
        page.project_name.setText('  retained name  ')
        page.executable.setText('  retained executable  ')
        page.workspace_root.setText('  retained workspace  ')
        page.runs_root.setText('  retained runs  ')
        page.seed.setText('  0042  ')
        page.run_name.setText('  retained run  ')
        page.threads.lineEdit().setText('02')
        controls = ('project_name', 'executable', 'workspace_root', 'runs_root', 'seed', 'run_name')
        original = {name: getattr(page, name).text() for name in controls}
        changed = []
        page.projectChanged.connect(lambda: changed.append(True))
        project.configPath, project.macroPath, project.outputDir = 'new/main.ini', 'new/run.mac', 'new/output'
        page.show_generated_paths(project)
        assert {name: getattr(page, name).text() for name in controls} == original
        assert page.threads.value() == 2 and page.threads.lineEdit().text() == '02'
        assert [page.config_path.text(), page.macro_path.text(), page.output_dir.text()] == [
            project.configPath, project.macroPath, project.outputDir]
        assert changed == []
        page.threads.lineEdit().setText('INVALID')
        page.show_generated_paths(project)
        assert page.threads.lineEdit().text() == 'INVALID'
        # Loading a business project is a different operation and still resets
        # an old raw draft, even when its typed thread value is the same.
        page.set_project(G4USimProject(projectName='new project', threads=2))
        assert page.threads.lineEdit().text() != 'INVALID' and page.threads.value() == 2
        assert page.project_name.text() == 'new project'
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def main():
    app = QApplication.instance() or QApplication([])
    test_generated_paths_preserve_other_controls(app)
    QCoreApplication.setOrganizationName('G4USim-Agent-Smoke')
    QCoreApplication.setApplicationName('Components')
    with tempfile.TemporaryDirectory(prefix='agent-qt-') as directory, \
            patch.object(QMessageBox, 'warning', return_value=QMessageBox.Ok):
        root = Path(directory)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(root / 'settings'))
        window = MainWindow(recovery_root=root / 'recovery')
        window.show()
        try:
            window.config_builder_page.preview3d_auto_backend.setChecked(False)
            assert window.apply_simulation_wizard(default_spec('single_target'), run_after=False)
            window.project_page.threads.setLocale(QLocale('zh_HK'))
            window.project_page.threads.setValue(1)
            window.config_builder_page.threads.setValue(1)
            window.project_page.executable.setText(sys.executable)
            window.project_page.workspace_root.setText(str(root))
            window.project_page.runs_root.setText(str(root / 'runs'))
            window.config_builder_page.beam_on.setValue(4)
            # Dormant inputs are owned test files, outside private source paths.
            parked_config, parked_macro = root / 'parked.ini', root / 'parked.mac'
            parked_config.write_text('[simulation]\nthreads = 1\nseed = 42\n', encoding='utf-8')
            parked_macro.write_text('/run/initialize\n', encoding='utf-8')
            # Absolute unclassified dormant paths are correctly privacy-rejected;
            # these relative drafts exercise preservation without relaxing that guard.
            window.project_page.config_path.setText('  parked.ini  ')
            window.project_page.macro_path.setText('  parked.mac  ')
            window.flush_pending_edit()
            controller = window.agent_controller
            before = snapshot_fingerprint(window.capture_workspace())
            sentinel = 'L1_SECRET_SENTINEL_7F3A'
            window._set_agent_provider(dict(provider='local', url='http://127.0.0.1:1/v1', model=sentinel,
                                           credential=sentinel, auth_mode='session', credential_id='test-reference'))
            assert not window._agent_connection
            assert window._agent_credentials.get('test-reference', storage='session') is None
            assert all(sentinel not in str(QSettings().value(key)) for key in QSettings().allKeys())
            target = next(r.name for r in window.project.geometryEditor.volumes if r.sensitive)
            changes = [dict(domain='volume', target=target, field='material', value='G4_Al'),
                       dict(domain='source', target='source', field='energy', value='1 GeV')]
            controller.set_provider(lambda messages, cancel_event=None: response(messages, changes))
            auth = dict(allowed_actions=['plan', 'apply'], max_calls=8, max_events=4, timeout_seconds=60)
            scope = [dict(domain='volume', target=target, fields=['material']),
                     dict(domain='source', target='source', fields=['energy'])]
            controller.start('Set the named target to aluminum and source to 1 GeV', auth,
                             auto_apply=True, write_scope=scope)
            wait(app, lambda: controller.journal.state in {'awaiting_approval', 'failed'} and
                 any(o['action'] == 'apply' and o['result'] for o in controller.journal.to_dict()['operations']), window)
            assert controller.journal.state == 'awaiting_approval', controller.state()
            assert window.config_builder_page.source_editor_energy.text() == '1 GeV'
            assert next(r for r in window.config_builder_page.geometry_document.volumes if r.name == target).material == 'G4_Al'
            assert snapshot_fingerprint(window.capture_workspace()) == snapshot_fingerprint(window._edit_session.current())
            operations = controller.journal.to_dict()['operations']
            assert [o['action'] for o in operations] == ['plan', 'apply']
            assert operations[-1]['result']['status'] == 'passed'
            assert operations[-1]['binding']['record_id'] == operations[-1]['result']['record_id']
            controller.cancel()
            window.undo_edit()
            assert snapshot_fingerprint(window.capture_workspace()) == before

            run_changes = [dict(domain='run', target='', field=key, value=value)
                           for key, value in [('beam_on', 3), ('threads', 2), ('seed', 42)]]
            controller.set_provider(lambda messages, cancel_event=None: response(messages, run_changes))
            controller.start('Change run settings', auth, auto_apply=True,
                             write_scope=[dict(domain='run', target='', fields=['beam_on', 'threads', 'seed'])])
            wait(app, lambda: controller.journal.state in {'awaiting_approval', 'failed'} and
                 any(o['action'] == 'apply' and o['result'] for o in controller.journal.to_dict()['operations']), window)
            assert controller.journal.state == 'awaiting_approval', controller.state()
            assert window.config_builder_page.beam_on.value() == 3
            assert window.config_builder_page.threads.value() == 2
            assert window.config_builder_page.seed.text() == '42'
            assert snapshot_fingerprint(window.capture_workspace()) == snapshot_fingerprint(window._edit_session.current())
            revision = window._edit_session.revision
            assert window._edit_session.current().state['drafts']['project.config_path'].startswith('  ')
            assert window._edit_session.current().state['drafts']['project.macro_path'].endswith('  ')
            assert window.project_page.threads.lineEdit().text() == '2'
            window._bind_experiment_package(dict(action='generate', status='passed', stale=False, package={
                'main_ini_path': str(root / 'display-only/main.ini'),
                'run_macro_path': str(root / 'display-only/run.mac'),
                'output_dir': str(root / 'display-only/output'),
                'package_dir': str(root / 'display-only')}))
            for _ in range(3):
                app.processEvents()
            assert window.project_page.threads.lineEdit().text() == '2'
            assert snapshot_fingerprint(window.capture_workspace()) == snapshot_fingerprint(window._edit_session.current())
            window.flush_pending_edit()
            assert window._edit_session.revision == revision
            apply_id = next(o['binding']['record_id'] for o in controller.journal.to_dict()['operations'] if o['action'] == 'apply')
            assert not next(r for r in window.experiment.records() if r['record_id'] == apply_id)['stale']
            controller.cancel()
            window.undo_edit()
            assert snapshot_fingerprint(window.capture_workspace()) == before

            calls = []
            def plan_only(messages, cancel_event=None):
                calls.append(1)
                return response(messages, [dict(domain='source', target='source', field='energy', value='2 GeV')])
            controller.set_provider(plan_only)
            planning_auth = dict(auth, allowed_actions=['plan'])
            controller.start('Review before granting edits', planning_auth)
            wait(app, lambda: controller.journal.state == 'awaiting_approval', window)
            previous = controller.journal
            window.config_agent_panel.allow_apply.setChecked(True)
            assert window.config_agent_panel.action_buttons['apply'].isEnabled()
            window._agent_action('apply')
            wait(app, lambda: controller.journal.state in {'awaiting_approval', 'failed'} and
                 any(o['action'] == 'apply' and o['result'] for o in controller.journal.to_dict()['operations']), window)
            assert controller.journal.state == 'awaiting_approval', controller.state()
            assert controller.journal.task_id != previous.task_id
            assert previous.to_dict()['authorization'] == planning_auth
            assert len(calls) == 1
            assert window.config_builder_page.source_editor_energy.text() == '2 GeV'
            controller.cancel()
            window.undo_edit()
            window.config_agent_panel.allow_apply.setChecked(False)
            assert snapshot_fingerprint(window.capture_workspace()) == before

            controller.set_provider(lambda messages, cancel_event=None: response(messages, questions=['Which volume?']))
            controller.start('An ambiguous request', auth)
            wait(app, lambda: controller.journal.state == 'needs_clarification', window)
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert len(controller.journal.to_dict()['operations']) == 1
            controller.cancel()

            entered, release = threading.Event(), threading.Event()
            def delayed(messages, cancel_event=None):
                entered.set()
                release.wait(5)
                return response(messages, changes)
            controller.set_provider(delayed)
            controller.start('Will be cancelled', auth, auto_apply=True, write_scope=scope)
            wait(app, entered.is_set, window)
            controller.cancel()
            release.set()
            wait(app, lambda: not controller.busy, window)
            assert controller.journal.state == 'cancelled'
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert len(controller.journal.to_dict()['operations']) == 1

            controller.set_provider(lambda messages, cancel_event=None: response(messages, changes))
            narrow = [dict(domain='source', target='source', fields=['energy'])]
            controller.start('Only source energy is authorized', auth, auto_apply=True, write_scope=narrow)
            wait(app, lambda: controller.journal.state == 'failed' and not controller.busy, window)
            assert snapshot_fingerprint(window.capture_workspace()) == before
            assert len(controller.journal.to_dict()['operations']) == 1
            assert controller.state()['reason'] == 'agent.change_outside_authorization'
            assert not window.runner.is_running()
            previous = controller.journal
            try:
                controller.start('No plan authorization', dict(auth, allowed_actions=['apply']))
            except ValueError as error:
                assert str(error) == 'agent.action_not_authorized'
            else:
                assert False, 'Planning without authorization was accepted'
            assert controller.journal is previous

            controller.set_provider(lambda messages, cancel_event=None: response(messages))
            controller.start('Explicit plan review before recovery', auth)
            wait(app, lambda: controller.journal.state == 'awaiting_approval', window)
            controller.approve_plan()  # Queue a real owner callback without pumping it.
            controller.cancel()
            pending = TaskJournal.create(root / 'pending-recovery', 'Interrupted planning', auth, controller._identity())
            pending.record_intent('plan', {})
            pending_path = pending.path
            pending.close()
            raw = pending_path.read_bytes()
            count = len(window.experiment.records())
            policy = controller.recover(pending_path)
            for _ in range(5):
                app.processEvents()
            assert controller.state()['state'] == 'interrupted'
            assert controller.state()['reason'] != 'agent.journal_write_failed'
            assert policy['can_replay'] is False
            assert len(window.experiment.records()) == count
            assert pending_path.read_bytes() == raw
            print('L1 Qt/K1/F5 components passed; provider text controlled, no backend run')
        finally:
            close_window(app, window)
            assert not window.agent_controller.busy


if __name__ == '__main__':
    main()
