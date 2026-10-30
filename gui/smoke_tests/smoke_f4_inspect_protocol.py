"""F4 Inspect handler negative contracts; synthetic protocol, no backend execution."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QProcess
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.window.run import RunMixin


class HandlerHost(RunMixin):
    """Exercise the real callbacks with explicit, labelled component inputs."""

    def __init__(self, stdout: bytes = b'', stderr: bytes = b''):
        self.project = G4USimProject(runInputMode='external', executable='original-backend')
        self.form_changes = {}
        self.project_page = SimpleNamespace(apply_to_project=self._apply_form)
        self.plans = []
        self.run_page = SimpleNamespace(set_macro_plan=self.plans.append)
        self._macro_inspection = SimpleNamespace(
            readAllStandardOutput=lambda: stdout,
            readAllStandardError=lambda: stderr,
            errorString=lambda: 'original backend failed to start',
        )
        self._pending_inspection_run = True
        self._macro_inspection_snapshot = self._macro_inspection_inputs()
        self.records = []
        self.started = []

    def _apply_form(self, project):
        for field, value in self.form_changes.items():
            setattr(project, field, value)

    def _present_raw_run_diagnostic(self, code, message, **kwargs):
        self.records.append((code, message, kwargs))

    def _start_current_project(self):
        self.started.append(True)


def main() -> None:
    for stdout in (b'[]', b'null', b'"text"', b'42', b'true', b'{', b'{}'):
        host = HandlerHost(stdout, b'backend protocol context\n')
        before = asdict(host.project)
        host._on_macro_inspection_finished(0, QProcess.NormalExit)
        assert len(host.records) == 1, (stdout, host.records)
        code, _message, parameters = host.records[0]
        assert code == 'backend.inspect_protocol', (stdout, host.records)
        assert parameters['raw_message'] == stdout.decode() + '\nbackend protocol context\n'
        assert not host.started and not host._pending_inspection_run
        assert asdict(host.project) == before

    current = HandlerHost()
    before = asdict(current.project)
    current._on_macro_inspection_error(QProcess.FailedToStart)
    assert len(current.records) == 1 and current.records[0][0] == 'backend.inspect_start'
    assert current.records[0][1] == 'original backend failed to start'
    assert not current._pending_inspection_run and not current.started
    assert asdict(current.project) == before

    stale_start = HandlerHost()
    # The form can change before a queued process callback updates the model.
    stale_start.form_changes['executable'] = 'new-backend'
    stale_start._on_macro_inspection_error(QProcess.FailedToStart)
    assert not stale_start.records, stale_start.records
    assert not stale_start.started and not stale_start._pending_inspection_run
    assert stale_start.project.executable == 'new-backend'
    assert stale_start.plans and 'stale' in stale_start.plans[-1].lower()

    stale_finish = HandlerHost(b'[]', b'old error\n')
    stale_finish.form_changes['macroPath'] = 'new-input.mac'
    stale_finish._on_macro_inspection_finished(1, QProcess.NormalExit)
    assert not stale_finish.records and not stale_finish.started
    assert not stale_finish._pending_inspection_run
    assert stale_finish.project.macroPath == 'new-input.mac'
    print('smoke_f4_inspect_protocol: OK (synthetic handler contracts)')


if __name__ == '__main__':
    main()
