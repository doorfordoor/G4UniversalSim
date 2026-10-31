"""F4 real backend Inspect refusal -> raw GUI diagnostic; no simulation runs."""
from __future__ import annotations

from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gui'))

from PySide6.QtCore import QCoreApplication, QEvent, QProcess, QSettings
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import G4USimProject
from gui_test_window import MainWindow
from g4usim_gui.widgets.diagnostic_navigation import configuration_snapshot
from smoke_k1_workflow import wait_workflow, close_window


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wait_for_inspection(app, process, completions, expected: int) -> None:
    deadline = time.monotonic() + 45
    while (len(completions) < expected or process.state() != QProcess.NotRunning) and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    assert process.state() == QProcess.NotRunning, 'Inspect process did not stop before the deadline'
    assert len(completions) == expected, completions


def check_backend(app, temp: Path, executable: Path) -> None:
    nested = temp / '子文件.mac'
    nested.write_text('# genuine backend preflight refusal\n/AIHL/output/setDir old-output\n', encoding='utf-8')
    top = temp / 'top.mac'
    top.write_text('/control/execute "子文件.mac"\n', encoding='utf-8')
    main = temp / 'main.ini'
    main.write_text('[run]\nseed = 17\n', encoding='utf-8')
    output = temp / 'not-created-output'
    original_hashes = {path: digest(path) for path in (top, nested, main)}
    window = MainWindow()
    process = window._macro_inspection
    completions = []
    process.finished.connect(lambda code, status: completions.append((code, status)))
    stderr_reads = []
    stdout_reads = []
    read_stderr = process.readAllStandardError
    read_stdout = process.readAllStandardOutput

    def capture_stderr():
        result = read_stderr()
        stderr_reads.append(bytes(result))
        return result

    def capture_stdout():
        result = read_stdout()
        stdout_reads.append(bytes(result))
        return result

    try:
        project = G4USimProject(projectName='F4 backend Inspect', runInputMode='external',
            executable=str(executable), workspaceRoot=str(ROOT), configPath=str(main),
            macroPath=str(top), outputDir=str(output), runsRoot=str(temp / 'runs'),
            threads=1, runName='f4-inspect-only')
        window._set_project(project)
        window.show()
        window.page_stack.setCurrentWidget(window.run_page)
        app.processEvents()
        window._update_project_from_page_without_preview()
        before_inspect = asdict(window.project)
        with patch.object(process, 'readAllStandardError', side_effect=capture_stderr), \
                patch.object(process, 'readAllStandardOutput', side_effect=capture_stdout), \
                patch.object(QMessageBox, 'warning', return_value=QMessageBox.Ok), \
                patch.object(window.runner, 'start') as start_run:
            # Read-only Inspect retains original file/line evidence. A separate
            # requested-run guard below checks that refusal never starts runner.
            window.inspect_external_macro()
            wait_workflow(app, window)
            assert Path(process.program()) == executable, window.experiment.records()[-1].get('reason')
            assert '--inspect-run' in process.arguments()
            wait_for_inspection(app, process, completions, 1)
            assert completions[0][0] != 0 and completions[0][1] == QProcess.NormalExit
            assert stderr_reads and b'conflicts with an explicit CLI lock' in b''.join(stderr_reads)
            raw = b''.join(stderr_reads).decode('utf-8', errors='replace')
            records = window.run_page.diagnostics_panel.records
            assert len(records) == 1, records
            diagnostic = records[0]
            assert diagnostic.code == 'backend.inspect_failed'
            assert diagnostic.raw_message == raw
            assert nested.name in raw and ':2' in raw
            assert '/aihl/output/setdir' in raw.lower(), raw
            assert diagnostic.location is None and diagnostic.source is None
            assert diagnostic.unavailable_reason and 'structured' in diagnostic.unavailable_reason
            assert not window.run_page.diagnostics_panel.locate_button.isEnabled()
            assert not window.run_page.diagnostics_panel.source_button.isEnabled()
            assert asdict(window.project) == before_inspect
            assert not start_run.called and not window.runner.is_running()
            assert not output.exists() and not list(temp.rglob('run_summary.txt'))

            before_navigation = (asdict(window.project), window.project_page.diagnostic_values(),
                                 configuration_snapshot(window.config_builder_page, 0))
            before_page = window.page_stack.currentWidget()
            assert not window._run_diagnostics.navigate(diagnostic)
            assert window.page_stack.currentWidget() is before_page
            assert before_navigation == (asdict(window.project), window.project_page.diagnostic_values(),
                                         configuration_snapshot(window.config_builder_page, 0))
            assert not any(widget.property('diagnosticFocus') for widget in window.findChildren(QWidget))
            assert {path: digest(path) for path in original_hashes} == original_hashes
            identity = diagnostic.identity
            for language, theme in (('zh_CN', 'dark'), ('en', 'light')):
                window._set_language(language, persist=False)
                window._set_theme(theme)
                app.processEvents()
                current = window.run_page.diagnostics_panel.records
                assert len(current) == 1 and current[0].identity == identity
                assert current[0].raw_message == raw and current[0].location is None
                assert asdict(window.project) == before_inspect

            guard = MainWindow()
            try:
                guard._set_project(copy.deepcopy(project))
                with patch.object(guard.runner, 'start') as guarded_start:
                    guard.inspect_external_macro(run_after=True)
                    wait_workflow(app, guard)
                    assert not guarded_start.called and not guard.runner.is_running()
                    assert guard.experiment.records()[-1]['status'] == 'failed'
                    assert not output.exists() and not list(temp.rglob('run_summary.txt'))
                    assert {path: digest(path) for path in original_hashes} == original_hashes
            finally:
                close_window(app, guard)
                guard.deleteLater()

            # A changed input invalidates the old report; a new real Inspect
            # result must replace it. This is still preflight, never beamOn.
            safe = temp / 'safe.mac'
            safe.write_text('/control/echo F4_INSPECT_MUST_NOT_EXECUTE\n', encoding='utf-8')
            window.project_page.macro_path.setText(str(safe))
            app.processEvents()
            assert not window._run_diagnostics.navigate(diagnostic)
            assert all(item.identity != identity for item in window.run_page.diagnostics_panel.records)
            before_success = asdict(window.project)
            stderr_reads.clear()
            stdout_reads.clear()
            window.inspect_external_macro()
            wait_workflow(app, window)
            wait_for_inspection(app, process, completions, 2)
            assert completions[1] == (0, QProcess.NormalExit)
            plan = json.loads(b''.join(stdout_reads).decode('utf-8'))
            assert plan['schema'] == 'G4UniversalSimRunPlan' and plan['execution_performed'] is False
            command = plan['macro_plan']['commands'][0]
            assert Path(command['file']) == safe and command['line'] == 1
            assert command['text'] == '/control/echo F4_INSPECT_MUST_NOT_EXECUTE'
            assert safe.name + ':1' in window.run_page.macro_plan_view.toPlainText()
            assert all(item.code != 'backend.inspect_failed' for item in window.run_page.diagnostics_panel.records)
            assert not start_run.called and not window.runner.is_running()
            assert asdict(window.project) == before_success
            assert not output.exists() and not list(temp.rglob('run_summary.txt'))
            assert {path: digest(path) for path in original_hashes} == original_hashes
    finally:
        if process.state() != QProcess.NotRunning:
            process.kill()
            process.waitForFinished(5000)
        close_window(app, window)
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def main() -> None:
    configured = os.environ.get('G4USIM_EXE', '').strip()
    assert configured, 'G4USIM_EXE is required: this test must run the real backend'
    executable = Path(configured).resolve()
    assert executable.is_file(), executable
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName('G4UniversalSimSmoke')
    app.setApplicationName('F4InspectBackend')
    set_application_language(app, 'en')
    environment = {}
    data = os.environ.get('G4USIM_GEANT4_DATA', '').strip()
    if data:
        environment['GEANT4_DATA_DIR'] = data
    with tempfile.TemporaryDirectory(prefix='g4usim-f4-inspect-') as raw, patch.dict(os.environ, environment):
        temp = Path(raw)
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(temp / 'settings'))
        check_backend(app, temp, executable)
    print('smoke_f4_inspect_backend: OK (real Inspect; no simulation execution)')


if __name__ == '__main__':
    main()
