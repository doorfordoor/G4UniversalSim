"""Required backend + real HTTP/Qt/K1 agent chain; model reply is a fixed fixture.

This tests orchestration and actual transport, not a model's NL understanding or
independent physics accuracy. Live model task-set evidence is recorded separately.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'gui'), str(ROOT / 'scripts')]

from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch

from gui_test_window import MainWindow
from smoke_k1_workflow import close_window
from g4usim_gui.agent.actions import SCHEMA
from g4usim_gui.core.edit_snapshot import snapshot_fingerprint, snapshot_to_dict
from g4usim_gui.core.wizard import default_spec
from run_m0_tests import workspace_source_fingerprint


def wait(app, window, predicate, timeout=120):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(.01)
    assert False, window.agent_controller.state()


class ModelFixture(BaseHTTPRequestHandler):
    requests = []
    def log_message(self, *args):
        pass

    def do_POST(self):
        assert self.path == '/v1/chat/completions'
        assert self.headers.get('Authorization') is None
        raw = self.rfile.read(int(self.headers['Content-Length']))
        data = json.loads(raw)
        self.requests.append(data)
        context = json.loads(data['messages'][1]['content'])['context']
        changes = [dict(domain='volume', target='Target', field='material', value='G4_Si'),
                   dict(domain='source', target='source', field='particle', value='e-'),
                   dict(domain='source', target='source', field='energy', value='1 GeV'),
                   dict(domain='run', target='', field='beam_on', value=4)]
        plan = dict(schema=SCHEMA, base_fingerprint=context['base_fingerprint'], summary='Fixed protocol fixture',
                    clarifications=[], changes=changes)
        payload = json.dumps(dict(model='fixture-local', choices=[dict(index=0, finish_reason='stop',
                             message=dict(role='assistant', content=json.dumps(plan)))]),
                             ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args = parser.parse_args()
    executable = os.environ.get('G4USIM_EXE', '')
    assert executable and Path(executable).is_file(), 'G4USIM_EXE required; no fallback'
    capabilities = json.loads(subprocess.check_output([executable, '--capabilities'], cwd=ROOT))
    assert capabilities['source_fingerprint'] == workspace_source_fingerprint()
    output = Path(args.output or os.environ.get('G4USIM_TEST_EVIDENCE_DIR') or
                  tempfile.mkdtemp(prefix='l1-backend-')).resolve()
    output.mkdir(parents=True, exist_ok=True)
    receipt = output / 'receipt.json'
    assert not receipt.exists(), 'Refuse evidence overwrite'
    app = QApplication.instance() or QApplication([])
    QCoreApplication.setOrganizationName('G4USim-Agent-Smoke')
    QCoreApplication.setApplicationName('Backend')
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(output / 'settings'))
    ModelFixture.requests = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), ModelFixture)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    window = None
    started = time.monotonic()
    with patch.object(QMessageBox, 'warning', return_value=QMessageBox.Ok):
        try:
            window = MainWindow(recovery_root=output / 'recovery')
            window.config_builder_page.preview3d_auto_backend.setChecked(False)
            spec = replace(default_spec('single_target'), events=4, threads=1, hits=True)
            assert window.apply_simulation_wizard(spec, run_after=False)
            window.project_page.executable.setText(executable)
            window.project_page.workspace_root.setText(str(output))
            window.project_page.runs_root.setText(str(output / 'runs'))
            window.flush_pending_edit()
            before = snapshot_fingerprint(window.capture_workspace())
            window._set_agent_provider(dict(provider='local', url=f'http://127.0.0.1:{server.server_port}/v1',
                                           model='fixture-local', auth_mode='none', credential_id=''))
            controller = window.agent_controller
            assert controller.provider is not None
            auth = dict(allowed_actions=['plan', 'apply', 'validate', 'initialize', 'generate', 'run', 'evaluate', 'export'],
                        max_calls=16, max_events=4, timeout_seconds=300)
            window._start_agent_task(dict(prompt='把Target改为G4_Si，source改为1 GeV电子束e-，保留位置方向，跑4事件。只检查事件完成性。',
                                          authorization=auth, auto_apply=True, auto_run=True,
                                          evaluation_scope='input_run_completion'))
            wait(app, window, lambda: controller.journal is not None and
                 controller.journal.state in {'awaiting_confirmation', 'failed'} and not controller.busy)
            assert controller.journal.state == 'awaiting_confirmation', controller.state()
            journal = controller.journal.to_dict()
            assert [o['action'] for o in journal['operations']] == ['plan', 'apply', 'validate', 'initialize', 'generate', 'run', 'evaluate']
            assert all(o['result']['status'] == 'passed' for o in journal['operations'])
            run_op = next(o for o in journal['operations'] if o['action'] == 'run')
            assert run_op['binding']['events'] == run_op['result']['events'] == 4
            run = next(r for r in window.experiment.records() if r['record_id'] == run_op['binding']['record_id'])
            assert run['status'] == 'passed' and not run.get('stale')
            assert run['result']['planned_events'] == run['result']['completed_events'] == 4
            assert Path(run['output_dir'], 'run_summary.txt').is_file()
            assert window._edit_session.current().project.sourceEditor.energy == '1 GeV'
            assert window._edit_session.current().project.sourceEditor.particle == 'e-'
            assert next(r for r in window._edit_session.current().project.geometryEditor.volumes if r.name == 'Target').material == 'G4_Si'
            assert len(ModelFixture.requests) == 1
            collected, accepted = window.capture_workspace(), window._edit_session.current()
            for name, snapshot in [('collected', collected), ('accepted', accepted)]:
                (output / (name + '-snapshot.json')).write_bytes(
                    (json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
            assert snapshot_fingerprint(collected) == snapshot_fingerprint(accepted)
            destination = output / 'exported-bundle'
            controller.confirm(destination)
            wait(app, window, lambda: controller.journal.state in {'completed', 'failed'} and not controller.busy)
            assert controller.journal.state == 'completed', controller.state()
            assert destination.is_dir() and any(destination.iterdir())
            window.undo_edit()
            assert snapshot_fingerprint(window.capture_workspace()) == before
            result = dict(status='passed', model_response_kind='deterministic_loopback_protocol_fixture',
                          executable=str(Path(executable).resolve()),
                          executable_sha256=hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
                          capabilities=capabilities, workspace_source_fingerprint=workspace_source_fingerprint(),
                          task=controller.journal.to_dict(), run_record=run,
                          elapsed_seconds=time.monotonic() - started,
                          evaluation_scope='execution_completion_only_not_physics_validation',
                          live_model_NL_understanding_tested=False, export_path=str(destination))
            # Record is already K1's explicit public projection; remove the live ValidationReport object.
            result['run_record'] = {k: v for k, v in run.items() if k != 'report' and not k.startswith('_')}
            receipt.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())
            print('L1 real HTTP/Qt/K1/backend/export/Undo passed; fixed model fixture')
        finally:
            if window is not None:
                close_window(app, window)
                assert not window.agent_controller.busy
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)
            assert not worker.is_alive()


if __name__ == '__main__':
    main()
