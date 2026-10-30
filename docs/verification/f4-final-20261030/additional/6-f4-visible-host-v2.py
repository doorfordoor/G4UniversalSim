"""F4 QA only: real product controls, synthetic inputs, no visual self-acceptance."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import faulthandler

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--executable', type=Path, required=True)
parser.add_argument('--artifact-dir', type=Path)
parser.add_argument('--state-file', type=Path)
parser.add_argument('--precheck', action='store_true')
args = parser.parse_args()
if args.precheck:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
if os.environ.get('G4USIM_GEANT4_DATA'):
    os.environ['GEANT4_DATA_DIR'] = os.environ['G4USIM_GEANT4_DATA']
sys.path.insert(0, str(ROOT / 'gui'))

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QProcess, QSettings, QTimer, Qt
from PySide6.QtWidgets import QApplication, QLabel, QToolBar, QWidget
from shiboken6 import isValid
from g4usim_gui.core import wizard as wz
from g4usim_gui.core.diagnostics import collect_diagnostics, extend_diagnostics
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core.project import G4USimProject
from g4usim_gui.editors.geometry_editor_model import (
    BooleanOperationRow, GeometryDocument, HierarchicalVolumeRow, LayerRow,
    validate_geometry_document,
)
from g4usim_gui.editors.material_editor_model import MaterialDocument, MaterialRow, validate_material_document
from g4usim_gui.editors.source_physics_scoring_model import validate_source_model
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.models.package_model import PathSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.validators.config_validator import ValidationReport
from g4usim_gui.widgets.diagnostic_navigation import configuration_snapshot
from g4usim_gui.widgets.diagnostic_panel import DiagnosticPanel
from g4usim_gui.widgets.new_simulation_wizard import NewSimulationWizard


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_hash(value) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8'))


SESSION = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid())
INPUTS = ROOT / 'out/collab/f4-visible-inputs' / SESSION
ARTIFACTS = (args.artifact_dir or ROOT / 'out/collab' / ('f4-visible-' + SESSION)).resolve()
for directory in (INPUTS, ARTIFACTS):
    directory.mkdir(parents=True, exist_ok=True)
STATE = args.state_file or ARTIFACTS / 'state.json'
STATE.parent.mkdir(parents=True, exist_ok=True)
EVENTS = ARTIFACTS / 'events.jsonl'
EXE = args.executable.resolve()
if not EXE.is_file():
    raise SystemExit('Backend executable does not exist: ' + str(EXE))


def git(*argv) -> str:
    return subprocess.run(['git', *argv], cwd=ROOT, text=True, encoding='utf-8',
                          capture_output=True, check=True).stdout.strip()


gui_files = git('ls-files', 'gui/g4usim_gui').splitlines()
gui_manifest = {path: sha((ROOT / path).read_bytes().replace(b'\r\n', b'\n')) for path in gui_files}
cap = subprocess.run([str(EXE), '--capabilities'], cwd=EXE.parent, capture_output=True, timeout=30)
(ARTIFACTS / 'backend-capabilities.stdout').write_bytes(cap.stdout)
(ARTIFACTS / 'backend-capabilities.stderr').write_bytes(cap.stderr)
try:
    capabilities = json.loads(cap.stdout)
except (ValueError, UnicodeError):
    capabilities = None
IDENTITY = {'gui_head': git('rev-parse', 'HEAD'), 'gui_status': git('status', '--porcelain'),
            'gui_files_sha256': normalized_hash(gui_manifest), 'executable': str(EXE),
            'executable_sha256': sha(EXE.read_bytes()), 'capabilities_exit': cap.returncode,
            'capabilities': capabilities, 'inputs': str(INPUTS), 'pid': os.getpid(),
            'mode': 'offscreen_precheck' if args.precheck else 'native_observation_pending',
            'visual_acceptance': 'not_claimed'}
IDENTITY.update(host_version=2, host_sha256=sha(Path(__file__).read_bytes()))
(ARTIFACTS / 'identity.json').write_text(json.dumps(IDENTITY, indent=2, ensure_ascii=False), encoding='utf-8')
(ARTIFACTS / 'gui-file-hashes.json').write_text(json.dumps(gui_manifest, indent=2), encoding='utf-8')

app = QApplication([])
app.setStyle('Fusion')
app.setOrganizationName('G4UniversalSimQA')
app.setApplicationName('F4Visible-' + SESSION)
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(INPUTS / 'settings'))
run_history_store.STATE_PATH = INPUTS / 'gui-history.json'
set_application_language(app, 'zh_CN')
apply_theme(app, 'light')

MATERIAL = INPUTS / 'materials.ini'
GEOMETRY = INPUTS / 'geometry.ini'
MATERIAL.write_text('[NIST]\nmaterials=G4_AIR, G4_Si, G4_Al\n', encoding='utf-8')
GEOMETRY.write_text('[world]\nshape=box\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\n', encoding='utf-8')

CASES = (
    ('energy', '源能量'), ('geometry', '几何重名'), ('material', '材料重名'),
    ('layer', '层厚度'), ('boolean', '布尔'), ('stale', '旧报告'),
    ('source', '源文件'), ('history', '历史源'), ('project', '跨页'),
    ('scenario', '场景'), ('wizard', '向导'), ('scan', '扫描'), ('backend', '后端原文'),
)


class Host(QObject):
    def __init__(self):
        super().__init__()
        self.window = MainWindow()
        self.window.setWindowTitle('G4UniversalSim F4 诊断定位实窗验收')
        self.window.resize(1366, 768)
        self.window.config_builder_page.preview3d_auto_backend.setChecked(False)
        self.case = ''
        self.panel = None
        self.wizard = None
        self.ready = False
        self.closed = False
        self._sequence = 0
        self._in_dispatch = False
        self._generation = 0
        self._inspect_receipts = []
        self._raw_stderr = []
        original_stderr = self.window._macro_inspection.readAllStandardError
        def capture_stderr():
            data = original_stderr()
            self._raw_stderr.append(bytes(data))
            return data
        self.window._macro_inspection.readAllStandardError = capture_stderr
        self.window._macro_inspection.finished.connect(self.inspection_finished)
        toolbar = QToolBar('QA 合成状态', self.window)
        toolbar.setMovable(False)
        self.window.addToolBar(Qt.TopToolBarArea, toolbar)
        toolbar.addWidget(QLabel('QA 合成：'))
        for key, label in CASES:
            action = toolbar.addAction(label)
            action.triggered.connect(lambda _checked=False, key=key: self.prepare(key))
        self.note = QLabel('准备中；视觉验收待原生观察')
        self.note.setWordWrap(True)
        self.window.statusBar().addPermanentWidget(self.note, 1)
        app.installEventFilter(self)
        self.window.show()

    def emit(self, kind, **values):
        self._sequence += 1
        event = {'sequence': self._sequence, 'time_utc': datetime.now(timezone.utc).isoformat(),
                 'case': self.case, 'kind': kind, 'visual_acceptance': 'not_claimed', **values}
        with EVENTS.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(event, ensure_ascii=False, default=str) + '\n')

    def business(self):
        p = self.window.config_builder_page
        scan = self.window.scan_page
        return {'project': asdict(self.window.project),
                'project_drafts': self.window.project_page.diagnostic_values(),
                'config': configuration_snapshot(p, 0),
                'models': {name: asdict(getattr(p, name)) for name in
                    ('material_document', 'geometry_document', 'source_editor', 'physics_editor', 'scoring_editor')},
                'scenario': self.window.scenario_page.values(),
                'scan': {'base': asdict(scan._base) if scan._base else None,
                         'values': scan.values.text(), 'parameter': scan.parameter.currentData(), 'name': scan.name.text()},
                'wizard': (asdict(self.wizard.spec), self.wizard._diagnostic_values()) if self.wizard else None,
                'fixture_files': {str(path.relative_to(INPUTS)): sha(path.read_bytes())
                                  for path in INPUTS.rglob('*') if path.is_file() and path.suffix in ('.ini', '.mac')
                                  and 'settings' not in path.parts}}

    def view(self):
        p = self.window.config_builder_page
        focus = app.focusWidget()
        return {'main_page': self.window.page_stack.currentIndex(), 'config_tab': p.workspace_tabs.currentIndex(),
                'geometry_tab': p.geometry_editor_tabs.currentIndex(),
                'geometry_cell': [p.geometry_table.currentRow(), p.geometry_table.currentColumn()],
                'material_row': p._selected_material_row, 'layer_row': p._selected_layer_row,
                'boolean_cell': [p.boolean_table.currentRow(), p.boolean_table.currentColumn()],
                'wizard_page': self.wizard.currentId() if self.wizard else None,
                'scenario_advanced': self.window.scenario_page.advanced_check.isChecked(),
                'focus': focus.objectName() if focus else None,
                'highlighted': [w.objectName() or type(w).__name__ for w in self.window.findChildren(QWidget)
                                if w.property('diagnosticFocus')],
                'status': self.panel.status.text() if self.panel else None,
                'source_visible': self.panel.source_view.isVisible() if self.panel else False,
                'source_text': self.panel.source_view.toPlainText() if self.panel else None}

    def save_state(self):
        records = []
        if self.panel:
            for d in self.panel.records:
                records.append({'code': d.code, 'identity': d.identity, 'location': asdict(d.location) if d.location else None,
                                'source': asdict(d.source) if d.source else None, 'raw_message': d.raw_message})
        state = {'identity': IDENTITY, 'case': self.case, 'ready': self.ready, 'closed': self.closed,
                 'business_sha256': normalized_hash(self.business()), 'presentation': self.view(),
                 'records': records, 'stale': self.panel.stale if self.panel else None,
                 'window_size': [self.window.width(), self.window.height()], 'events': str(EVENTS),
                 'inspect_receipts': self._inspect_receipts, 'visual_acceptance': 'not_claimed'}
        STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

    def eventFilter(self, watched, event):
        kind = event.type()
        # Qt sends Close while tearing down child QFrames. Never traverse a
        # partially destroyed QObject tree from this application-wide observer.
        if kind == QEvent.Close:
            if watched is self.window:
                self.ready = False
                self._generation += 1
                self._in_dispatch = False
                self.closed = True
                self.emit('main_window_close_requested')
                wizard, self.wizard = self.wizard, None
                self.panel = None
                if wizard is not None and isValid(wizard):
                    wizard.close()
                    wizard.deleteLater()
            return False
        if kind not in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.KeyPress):
            return False
        if self.ready and not self._in_dispatch and not self.closed:
            # The prepared fixture owns one active panel. Do not scan unrelated
            # pages/wizards; their wrappers may be in a destruction transition.
            current = self.panel
            panel = None
            if current is not None and isValid(current) and isValid(current.table):
                controls = (current.locate_button, current.source_button, current.table, current.table.viewport())
                panel = current if any(watched is control for control in controls if isValid(control)) else None
            mouse = kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick)
            key = kind == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape)
            escape = kind == QEvent.KeyPress and event.key() == Qt.Key_Escape
            if panel and (mouse or key) or escape:
                before = normalized_hash(self.business())
                self.panel = panel or self.panel
                self.emit('product_input_before', event_type=int(event.type()),
                          control=watched.objectName() or type(watched).__name__, before=before, presentation=self.view())
                self._in_dispatch = True
                generation, case = self._generation, self.case
                QTimer.singleShot(80, lambda before=before, generation=generation, case=case:
                                  self.after_input(before, generation, case))
        return False

    def after_input(self, before, generation, case):
        if self.closed or not self.ready or generation != self._generation or case != self.case:
            self.emit('product_input_discarded', originating_case=case, originating_generation=generation,
                      current_generation=self._generation, reason='fixture_replaced_or_closed')
            return
        after = normalized_hash(self.business())
        self._in_dispatch = False
        self.emit('product_input_after', before=before, after=after, model_unchanged=before == after,
                  presentation=self.view())
        self.save_state()

    def baseline(self):
        self.ready = False
        self.panel = None
        wizard, self.wizard = self.wizard, None
        if wizard is not None and isValid(wizard):
            wizard.close()
            wizard.deleteLater()
        w = self.window
        project = G4USimProject(projectName='F4 QA synthetic inputs', runInputMode='generated',
                    executable=str(EXE), workspaceRoot=str(INPUTS), runsRoot=str(INPUTS / 'packages'),
                    outputDir=str(INPUTS / 'not-run'), threads=1)
        project.pathSettings = PathSettings(executable=str(EXE), workspace_root=str(INPUTS),
                    runs_root=str(INPUTS / 'packages'), materials_config=str(MATERIAL), geometry_config=str(GEOMETRY))
        project.geometrySettings.template = 'hierarchical'
        project.geometrySettings.config_path = str(GEOMETRY)
        w._set_project(project)
        assert w.apply_simulation_wizard(wz.default_spec('single_target'), run_after=False)
        w.config_builder_page.preview3d_auto_backend.setChecked(False)
        w._clear_project_diagnostics()
        w.config_builder_page.set_validation_text('QA synthetic fixture; visual observation pending.')
        w._clear_diagnostic_highlights()
        self.panel = w.config_builder_page.diagnostic_panel

    def present(self, owner, predicate):
        records = collect_diagnostics(owner)
        report = ValidationReport()
        extend_diagnostics(report, records)
        p = self.window.config_builder_page
        p.set_validation_report(report)
        self.panel = p.diagnostic_panel
        p.workspace_tabs.setCurrentIndex(5)
        self.select(predicate)

    def select(self, predicate):
        index = next(i for i, d in enumerate(self.panel.records) if predicate(d))
        self.panel.table.setCurrentCell(index, 0)
        self.panel.show()

    def prepare(self, key):
        if self.window._macro_inspection.state() != QProcess.NotRunning:
            return
        self.ready = False
        self._generation += 1
        self._in_dispatch = False
        self.case = key
        try:
            self.baseline()
            w = self.window
            p = w.config_builder_page
            note = '使用产品定位按钮 / Enter / 双击；Esc 清高亮；业务值应保持。'
            if key in ('energy', 'stale'):
                p.source_editor.energy = 'invalid-energy'
                p._populate_sps_editors()
                validate_source_model(p.source_editor)
                self.present(p.source_editor, lambda d: d.location and d.location.field == 'energy')
                if key == 'stale':
                    p.source_editor_energy.setText('changed-after-report')
                    note = '旧报告已过期：定位应禁用；不要重新验证后再观察旧报告。'
            elif key in ('geometry', 'boolean'):
                p.geometry_document = GeometryDocument(mode='hierarchical', is_dirty=True, volumes=[
                    HierarchicalVolumeRow(name='world', shape='box', size='10 cm,10 cm,10 cm', material='G4_AIR'),
                    HierarchicalVolumeRow(name='Sensor', parent='world', shape='box', size='1 mm,1 mm,1 mm', material='G4_Si'),
                    HierarchicalVolumeRow(name='Sensor', parent='world', shape='box', size='bad', material='G4_Si')])
                if key == 'boolean':
                    p.geometry_document.volumes.pop()
                    p.geometry_document.boolean_ops = [BooleanOperationRow(target_volume='Sensor', index=2,
                            operation='invalid-operation', tool_shape='box', tool_size='0.1 mm,0.1 mm,0.1 mm')]
                p._populate_geometry_editor()
                validate_geometry_document(p.geometry_document)
                self.present(p.geometry_document, lambda d: d.location and (
                    d.location.collection == 'volumes' and d.location.row == 2 and d.location.field == 'size'
                    if key == 'geometry' else d.location.editor == 'booleans' and d.location.field == 'operation'))
                note = '真实模型第 3 行与第 2 行重名；定位到第 3 行 size。' if key == 'geometry' else '真实布尔行 index=2；定位 operation 单元格。'
            elif key == 'material':
                p.material_document = MaterialDocument(is_dirty=True, rows=[
                    MaterialRow(name='SameMaterial', density='1 g/cm3', components_text='Si:1'),
                    MaterialRow(name='SameMaterial', density='bad', components_text='Si:1')])
                p._populate_material_editor()
                validate_material_document(p.material_document)
                self.present(p.material_document, lambda d: d.location and d.location.row == 1 and d.location.field == 'density')
                note = '两个材料同名；定位第二行 density，保留 bad 值与 dirty 状态。'
            elif key == 'layer':
                p.geometry_document = GeometryDocument(mode='layered_device', is_dirty=True)
                p.geometry_document.layered_device.layers = [LayerRow(name='First'), LayerRow(name='Second', thickness='bad')]
                p._populate_geometry_editor()
                validate_geometry_document(p.geometry_document)
                self.present(p.geometry_document, lambda d: d.location and d.location.editor == 'layers' and d.location.row == 1 and d.location.field == 'thickness')
            elif key in ('source', 'history'):
                source = INPUTS / 'standalone-source-audit.ini'
                source.write_text('[world]\nshape=box\nsize=10 cm,10 cm,10 cm\nmaterial=G4_AIR\nmystery=bad\n', encoding='utf-8')
                parsed = parse_geometry(source, 'hierarchical')
                report = ValidationReport()
                extend_diagnostics(report, collect_diagnostics(parsed))
                w._run_diagnostics.set_report(report)
                self.panel = w.run_page.diagnostics_panel
                self.select(lambda d: d.source and d.source.key.lower() == 'mystery')
                if key == 'history':
                    source.write_text('# changed after the actual parser read\n[world]\nshape=box\n', encoding='utf-8')
                w.page_stack.setCurrentWidget(w.run_page)
                note = '独立源文件审计夹具（不是当前配置）；点查看源文件。' + ('应标记历史快照，不能套用旧行号到新文件。' if key == 'history' else '应显示真实第 5 行 mystery。')
            elif key == 'project':
                w.project_page.executable.setText('')
                w._validate_project_diagnostics()
                self.panel = w.run_page.diagnostics_panel
                self.select(lambda d: d.location and d.location.field == 'executable')
                w.page_stack.setCurrentWidget(w.run_page)
                note = '运行页诊断定位到 Project 可执行文件；不要填值，检查跨页与空值保持。'
            elif key == 'scenario':
                s = w.scenario_page
                s.set_values({'pore_fraction': '2', 'threads': '1'})
                s.validate_form()
                s.advanced_check.setChecked(False)
                self.panel = s.diagnostics_panel
                self.select(lambda d: d.location and d.location.field == 'pore_fraction')
                w.page_stack.setCurrentWidget(s)
                note = '高级区域已隐藏；定位应展开并滚到 pore_fraction，数值仍为 2。'
            elif key == 'wizard':
                self.wizard = NewSimulationWizard(w)
                self.wizard.setWindowTitle('F4 QA 合成向导 — 使用产品定位按钮')
                self.wizard.resize(900, 680)
                self.wizard.show()
                for _ in range(3):
                    self.wizard.next()
                    app.processEvents()
                assert self.wizard.currentId() == 3
                self.wizard.spec.target_material = 'unavailable-material'
                self.wizard.geometry_page.target_material.setCurrentIndex(-1)
                self.wizard.run_page._update()
                self.panel = self.wizard.run_page.diagnostics_panel
                self.select(lambda d: d.location and d.location.field == 'target_material')
                note = '向导最后页定位到已访问的几何页；空材料选择与未提交值应保持。'
            elif key == 'scan':
                s = w.scan_page
                assert s.refresh_base()
                s.values.setText('')
                assert not s.validate_inputs()
                self.panel = s.diagnostics_panel
                self.select(lambda d: d.location and d.location.field == 'values')
                w.page_stack.setCurrentWidget(s)
            elif key == 'backend':
                self.prepare_backend()
                note = '真实后端 Inspect 进行中；仅预检，不执行仿真。'
            else:
                raise ValueError(key)
            self.note.setText('QA：' + note)
            app.processEvents()
            self.ready = key != 'backend'
            self.emit('state_prepared', producer='real_product_on_synthetic_fixture', business_sha256=normalized_hash(self.business()))
            self.save_state()
        except Exception:
            self.emit('preparation_failed', traceback=traceback.format_exc())
            self.note.setText('QA 准备失败，见 events.jsonl')
            self.save_state()
            if args.precheck:
                raise

    def prepare_backend(self):
        nested = INPUTS / '子文件.mac'
        nested.write_text('# actual backend preflight refusal\n/AIHL/output/setDir old-output\n', encoding='utf-8')
        top = INPUTS / 'top.mac'
        top.write_text('/control/execute "子文件.mac"\n', encoding='utf-8')
        main = INPUTS / 'main.ini'
        main.write_text('[run]\nseed=17\n', encoding='utf-8')
        project = G4USimProject(projectName='F4 QA actual Inspect', runInputMode='external',
                executable=str(EXE), workspaceRoot=str(INPUTS), configPath=str(main), macroPath=str(top),
                outputDir=str(INPUTS / 'inspect-no-output'), runsRoot=str(INPUTS / 'packages'), threads=1)
        self.window._set_project(project)
        self.window.config_builder_page.preview3d_auto_backend.setChecked(False)
        self.window.page_stack.setCurrentWidget(self.window.run_page)
        self.panel = self.window.run_page.diagnostics_panel
        self._raw_stderr.clear()
        self.window.inspect_external_macro(run_after=False)
        process = self.window._macro_inspection
        self.emit('actual_backend_started', program=process.program(), arguments=process.arguments(),
                  executable_sha256=IDENTITY['executable_sha256'], simulation_requested=False)

    def inspection_finished(self, code, status):
        if self.case != 'backend':
            return
        process = self.window._macro_inspection
        raw = b''.join(self._raw_stderr)
        receipt = {'program': process.program(), 'arguments': process.arguments(), 'exit_code': code,
                   'exit_status': int(status.value), 'stderr_sha256': sha(raw), 'stderr': raw.decode('utf-8', errors='replace'),
                   'executable_sha256': IDENTITY['executable_sha256'], 'simulation_requested': False,
                   'runner_running': self.window.runner.is_running(),
                   'run_summary_files': [str(p) for p in INPUTS.rglob('run_summary.txt')]}
        self._inspect_receipts.append(receipt)
        (ARTIFACTS / 'inspect.stderr').write_bytes(raw)
        self.panel = self.window.run_page.diagnostics_panel
        self.ready = True
        self.note.setText('QA 真实 Inspect 已拒绝：原文无 GUI 位置；两定位按钮应禁用；未执行仿真。')
        self.emit('actual_backend_finished', **receipt)
        self.save_state()

    def precheck(self):
        results = []
        for key, _ in CASES:
            self.prepare(key)
            if key == 'backend':
                deadline = time.monotonic() + 45
                while not self.ready and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.005)
                assert self.ready, 'backend Inspect timed out'
                receipt = self._inspect_receipts[-1]
                assert receipt['exit_code'] != 0 and receipt['exit_status'] == 0
                assert 'conflicts with an explicit CLI lock' in receipt['stderr']
                assert not receipt['runner_running'] and not receipt['run_summary_files']
                d = self.panel.records[0]
                assert d.raw_message == receipt['stderr'] and d.location is None and d.source is None
                assert not self.panel.locate_button.isEnabled() and not self.panel.source_button.isEnabled()
            assert self.ready and self.panel.records
            d = self.panel.selected_diagnostic()
            assert d is not None
            if key == 'stale':
                assert self.panel.stale and not self.panel.locate_button.isEnabled()
            elif key in ('source', 'history'):
                assert d.source.line == 5 and d.source.text_sha256 and d.source.text_snapshot
                assert self.panel.source_button.isEnabled()
                assert ('mystery' in Path(d.source.filename).read_text(encoding='utf-8')) == (key == 'source')
            elif key != 'backend':
                assert d.location is not None and self.panel.locate_button.isEnabled()
            results.append({'case': key, 'prepared': True, 'code': d.code, 'navigation_executed': False,
                            'visual_observation': False, 'business_sha256': normalized_hash(self.business())})
        (ARTIFACTS / 'precheck.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        self.emit('offscreen_precheck_finished', states=len(results), visual_acceptance='not_claimed')
        self.window.close()


host = Host()
exit_code = 0
faulthandler.enable(all_threads=True)
try:
    if args.precheck:
        host.precheck()
        app.processEvents()
    else:
        host.prepare('energy')
        print(json.dumps({'ready': True, 'pid': os.getpid(), 'state': str(STATE), 'artifacts': str(ARTIFACTS)}, ensure_ascii=False), flush=True)
        exit_code = app.exec()
except Exception:
    exit_code = 1
    host.emit('host_exception', traceback=traceback.format_exc())
    traceback.print_exc()
    host.window.close()
finally:
    host.emit('host_finished', exit_code=exit_code, close_requested=host.closed)
    host.save_state()
    (ARTIFACTS / 'exit.json').write_text(json.dumps({'exit_code': exit_code, 'close_requested': host.closed,
           'event_loop_used': not args.precheck, 'visual_acceptance': 'not_claimed',
           'exit_code_scope': 'python_requested_return; launcher_must_verify_actual_process_exit'}), encoding='utf-8')
    app.removeEventFilter(host)
    host.ready = False
    host._generation += 1
    host._in_dispatch = False
    wizard, host.wizard = host.wizard, None
    host.panel = None
    if wizard is not None and isValid(wizard):
        wizard.close()
        wizard.deleteLater()
    host.window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
print('F4 QA host exit', exit_code, 'artifacts:', ARTIFACTS, flush=True)
raise SystemExit(exit_code)
