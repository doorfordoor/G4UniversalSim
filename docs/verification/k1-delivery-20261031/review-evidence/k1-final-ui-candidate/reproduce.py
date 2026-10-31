"""Retained negative control with real completed record and actual state producer."""
from pathlib import Path
from types import MethodType, SimpleNamespace
import argparse
import copy
import json

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import load_project
from g4usim_gui.core.experiment_workflow import ExperimentWorkflow
from g4usim_gui.window.experiment import ExperimentMixin
from g4usim_gui.window.run import RunMixin
from g4usim_gui.widgets.run_page import RunPage
from g4usim_gui.widgets.experiment_panel import ExperimentPanel

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--case', choices=('cwd', 'pending'))
parser.add_argument('--label')
args = parser.parse_args()
app = QApplication.instance() or QApplication([])
set_application_language(app, 'en')
view = None
try:
    if args.case == 'cwd':
        visible = ROOT / 'out/verification/k1-8213ced/visible'
        state = json.loads((visible / 'current-state.json').read_text(encoding='utf-8'))
        record = [r for r in state['workflow']['history'] if r.get('action') == 'run' and r.get('status') == 'passed'][-1]
        project = load_project(state['project_path'])
        editor_cwd = project.workspaceRoot
        logical = record['launch']['working_directory']
        assert Path(editor_cwd).resolve() != Path(logical).resolve()
        view = RunPage()
        idle = lambda *_args: None
        host = SimpleNamespace(project=project, _history_restoring=False, run_page=view,
            _edit_session=SimpleNamespace(current=lambda: SimpleNamespace(project=copy.deepcopy(project))),
            project_page=SimpleNamespace(set_project=idle),
            config_builder_page=SimpleNamespace(set_package_path=idle),
            output_page=SimpleNamespace(set_package_dir=idle),
            run_history_page=SimpleNamespace(set_runs_root=idle, refresh=idle))
        host._format_command_preview = MethodType(RunMixin._format_command_preview, host)
        ExperimentMixin._bind_experiment_package(host, record)
        text = view.command_preview.toPlainText()
        result = {'record_id': record['record_id'], 'saved_project': state['project_path'],
                  'editor_cwd': editor_cwd, 'actual_record_cwd': logical, 'displayed_preview': text,
                  'editor_cwd_after': project.workspaceRoot}
        (OUT / (args.label + '-cwd-observation.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result), flush=True)
        assert '\n  ' + logical + '\n' in text, 'actual completed record cwd absent from preview'
        assert project.workspaceRoot == editor_cwd
    else:
        source = SimpleNamespace(session=SimpleNamespace(revision=7), busy=False, _freshness='checking',
            records=lambda: [dict(record_id='recorded-check', run_id='r', revision=7,
                                  level='fields', status='passed', stale=False)])
        payload = ExperimentWorkflow._state(source)
        view = ExperimentPanel()
        view.set_state(payload)
        shown = view._level_labels['fields'].text()
        result = {'producer_payload': payload, 'rendered_fields': shown,
                  'rendered_summary': view._summary_label.text()}
        (OUT / (args.label + '-pending-observation.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result), flush=True)
        assert payload['levels'][0]['status'] == 'pending'
        assert shown == 'In progress', 'real producer pending incorrectly falls back to Unobserved'
finally:
    if view is not None:
        view.close()
        view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
