"""F5 application QA fixtures; native actions/visual acceptance belong to reviewer."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--artifact-dir', type=Path, required=True)
parser.add_argument('--executable', type=Path, required=True)
parser.add_argument('--precheck', action='store_true')
parser.add_argument('--theme', choices=('light', 'dark'), default='light')
args = parser.parse_args()
if args.precheck:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
elif os.environ.get('QT_QPA_PLATFORM', '').lower() in {'offscreen', 'minimal'}:
    raise SystemExit('Native host refuses an inherited offscreen/minimal Qt platform.')
if os.environ.get('G4USIM_GEANT4_DATA'):
    os.environ['GEANT4_DATA_DIR'] = os.environ['G4USIM_GEANT4_DATA']
sys.path.insert(0, str(ROOT / 'gui'))

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QSettings, QTimer, Qt, qVersion
from PySide6.QtWidgets import QApplication, QLabel, QToolBar, QWidget
from shiboken6 import isValid
from g4usim_gui.core.edit_snapshot import clone_snapshot, project_for_snapshot, snapshot_fingerprint
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.project import G4USimProject, project_to_dict, save_project
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.core.workspace_recovery import RecoveryStore, origin_status
from g4usim_gui.editors.geometry_editor_model import geometry_document_from_summary
from g4usim_gui.editors.material_editor_model import material_document_from_summary
from g4usim_gui.history import run_history_store
from g4usim_gui.main_window import MainWindow
from g4usim_gui.models.package_model import GeometrySettings, PathSettings
from g4usim_gui.parsers.geometry_parser import parse_geometry
from g4usim_gui.parsers.materials_parser import parse_materials


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def git(*arguments):
    return subprocess.run(['git', *arguments], cwd=ROOT, text=True, encoding='utf-8',
                          capture_output=True, check=True).stdout.strip()


ARTIFACTS = args.artifact_dir.resolve()
if not ARTIFACTS.is_relative_to((ROOT / 'out').resolve()):
    raise SystemExit('QA artifact directory must be beneath this checkout/out.')
ARTIFACTS.mkdir(parents=True, exist_ok=True)
if (ARTIFACTS / 'identity.json').exists():
    raise SystemExit('Choose a fresh artifact directory; prior evidence is never overwritten.')
INPUTS = ARTIFACTS / 'fixture-inputs'
INPUTS.mkdir(exist_ok=False)
RECOVERY = INPUTS / 'recovery'
EXE = args.executable.resolve()
if not EXE.is_file():
    raise SystemExit(f'Backend does not exist: {EXE}')
SESSION = datetime.now().strftime('%Y%m%d-%H%M%S') + f'-{os.getpid()}'
gui_paths = git('ls-files', '--cached', '--others', '--exclude-standard', 'gui/g4usim_gui').splitlines()
gui_manifest = {path: {'sha256_raw': sha((ROOT / path).read_bytes()),
                       'sha256_lf': sha((ROOT / path).read_bytes().replace(b'\r\n', b'\n'))}
                for path in sorted(set(gui_paths)) if (ROOT / path).is_file()}
cap = subprocess.run([str(EXE), '--capabilities'], cwd=EXE.parent, capture_output=True, timeout=30)
(ARTIFACTS / 'backend-capabilities.stdout').write_bytes(cap.stdout)
(ARTIFACTS / 'backend-capabilities.stderr').write_bytes(cap.stderr)
try:
    capabilities = json.loads(cap.stdout)
except (ValueError, UnicodeError):
    capabilities = None
IDENTITY = {'session': SESSION, 'pid': os.getpid(), 'gui_head': git('rev-parse', 'HEAD'),
            'gui_status': git('status', '--porcelain'), 'gui_file_count': len(gui_manifest),
            'gui_files_sha256': sha(json.dumps(gui_manifest, sort_keys=True).encode('utf-8')),
            'host_sha256': sha(Path(__file__).read_bytes()), 'host_version': 1,
            'executable': str(EXE), 'executable_sha256': sha(EXE.read_bytes()),
            'capabilities_exit': cap.returncode, 'capabilities': capabilities,
            'qt_version': qVersion(), 'inputs': str(INPUTS),
            'mode': 'offscreen_precheck' if args.precheck else 'native_observation_pending',
            'visual_acceptance': 'not_claimed'}
write_json(ARTIFACTS / 'gui-file-hashes.json', gui_manifest)
write_json(ARTIFACTS / 'identity.json', IDENTITY)

app = QApplication([])
app.setStyle('Fusion')
BASE_STYLE_NAME = app.style().objectName()
assert BASE_STYLE_NAME.lower() == 'fusion'
app.setOrganizationName('G4UniversalSimQA')
app.setApplicationName('F5Visible-' + SESSION)
QSettings.setDefaultFormat(QSettings.IniFormat)
for scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, scope, str(INPUTS / 'settings' / str(scope.value)))
run_history_store.STATE_PATH = INPUTS / 'gui-history.json'
set_application_language(app, 'zh_CN')
apply_theme(app, args.theme)
IDENTITY.update(base_style=BASE_STYLE_NAME, theme=args.theme,
                theme_stylesheet_sha256=sha(app.styleSheet().encode('utf-8')),
                qt_platform=app.platformName())
write_json(ARTIFACTS / 'identity.json', IDENTITY)

MATERIAL = INPUTS / 'materials.ini'
GEOMETRY = INPUTS / 'geometry.ini'
MATERIAL.write_text('[NIST]\nmaterials = G4_AIR, G4_Si\n[material.QASilicon]\ndensity = 2.33 g/cm3\ncomponents = G4_Si:1\n', encoding='utf-8')
GEOMETRY.write_text('[global]\nversion = 2\n[world]\nshape = box\nsize = 100 mm,100 mm,100 mm\nmaterial = G4_AIR\n'
                    '[volume.target]\nparent = world\nshape = box\nsize = 10 mm,10 mm,10 mm\nmaterial = QASilicon\n'
                    'position = 0,0,0 mm\nsensitive = true\n', encoding='utf-8')


class QAWindow(MainWindow):
    def setWindowTitle(self, title):  # noqa: N802
        prefix = 'G4UniversalSim F5 实窗验收'
        super().setWindowTitle(title if title.startswith(prefix) else prefix + ' | ' + title)

    def closeEvent(self, event):  # noqa: N802
        host = getattr(self, '_qa_host', None)
        if host is not None:
            # Do not traverse the widget/model tree from Close, including before
            # product shutdown. Its last periodic state remains the prior view.
            host.timer.stop()
            host.emit('native_close_requested', spontaneous=event.spontaneous())
        super().closeEvent(event)
        if host is not None:
            if event.isAccepted():
                host.closed = True
                host.ready = False
                host.timer.stop()
                app.removeEventFilter(host)
                host.emit('product_close_accepted')
            else:
                host.emit('product_close_cancelled_or_deferred')
                host.timer.start()


class Host(QObject):
    def __init__(self):
        super().__init__()
        self.sequence = 0
        self.ready = False
        self.closed = False
        self.case = 'initial'
        self.recovery_fixture_id = None
        self.broken_fixture_id = None
        self.projection_original = None
        self.projection_remaining = 0
        self.window = QAWindow(recovery_root=RECOVERY, offer_recovery=False)
        self.window._qa_host = self
        self.window.resize(1400, 900)
        self.window.config_builder_page.preview3d_auto_backend.setChecked(False)
        self.note = QLabel('QA 夹具；实际编辑与验收由原生操作完成。')
        self.note.setWordWrap(True)
        self.window.statusBar().addPermanentWidget(self.note, 1)
        toolbar = QToolBar('QA 夹具（不计作产品操作）', self.window)
        toolbar.setObjectName('f5QAOnlyFixtures')
        toolbar.setMovable(False)
        toolbar.addWidget(QLabel('QA 夹具：'))
        for label, operation in (
                ('正常主配置（重置夹具）', self.prepare_normal),
                ('准备恢复副本 / 原件已变', self.prepare_recovery),
                ('准备损坏恢复条目', self.prepare_corrupt),
                ('布置双失败 → 请手动撤销', self.arm_projection_failure)):
            toolbar.addAction(label).triggered.connect(lambda _checked=False, operation=operation: self.dispatch(operation))
        self.window.addToolBarBreak(Qt.TopToolBarArea)
        self.window.addToolBar(Qt.TopToolBarArea, toolbar)
        self.timer = QTimer(self)
        self.timer.setInterval(600)
        self.timer.timeout.connect(self.save_state)
        self.prepare_normal()
        self.normal_snapshot = self.window.capture_workspace()
        self.ready = True
        app.installEventFilter(self)
        self.timer.start()

    def emit(self, kind, **values):
        self.sequence += 1
        record = {'sequence': self.sequence, 'time_utc': datetime.now(timezone.utc).isoformat(),
                  'kind': kind, 'case': self.case, 'visual_acceptance': 'not_claimed', **values}
        with (ARTIFACTS / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')

    def dispatch(self, operation):
        self.emit('qa_fixture_requested', fixture=operation.__name__, evidence_scope='synthetic preparation')
        try:
            operation()
        except Exception:
            self.note.setText('QA 夹具准备失败；检查宿主日志。')
            self.emit('qa_fixture_failure', traceback=traceback.format_exc())
            traceback.print_exc()
        self.save_state()

    def prepare_normal(self):
        if getattr(self.window, '_workspace_fault', ''):
            raise ValueError('Use the product repair action before resetting the QA fixture.')
        if not self.window.can_mutate_workspace('QA fixture reset'):
            raise ValueError('Current product state does not allow preparing a fixture.')
        self.disarm_projection()
        project = G4USimProject(projectName='F5 正常验收', executable=str(EXE), workspaceRoot=str(INPUTS),
                               runsRoot=str(INPUTS / 'runs'), runName='f5-native', seed='12345', threads=1)
        project.pathSettings = PathSettings(executable=str(EXE), workspace_root=str(INPUTS), runs_root=project.runsRoot,
                                           materials_config=str(MATERIAL), geometry_config=str(GEOMETRY))
        project.geometrySettings = GeometrySettings(template='hierarchical', config_path=str(GEOMETRY))
        project.materialEditor = material_document_from_summary(parse_materials(MATERIAL))
        project.geometryEditor = geometry_document_from_summary(parse_geometry(GEOMETRY, 'hierarchical'))
        project.materialEditor.is_dirty = project.geometryEditor.is_dirty = True
        project.runSettings.run_name, project.runSettings.seed = 'f5-native', 12345
        project.runSettings.threads, project.runSettings.beam_on = 1, 5
        self.window.project_file = None
        self.window._set_project(project)
        self.window._recovery_project_replaced(origin_path='', origin_sha256=None)
        self.window.page_stack.setCurrentWidget(self.window.config_builder_page)
        self.window.config_builder_page.workspace_tabs.setCurrentIndex(0)
        self.window.setWindowTitle('G4UniversalSim F5 撤销与恢复实窗验收')
        self.case = 'normal_configuration'
        self.note.setText('正常配置已准备。请原生输入、撤销/重做、保存/取消；恢复入口在“编辑”菜单。')
        self.emit('qa_fixture_prepared', fixture=self.case, evidence_scope='synthetic initial state')

    def prepare_recovery(self):
        store = RecoveryStore(RECOVERY)
        if self.recovery_fixture_id and any(c.session_id == self.recovery_fixture_id for c in store.discover()):
            self.note.setText('恢复副本仍在；请使用产品“编辑 → 恢复编辑副本”。')
            return
        snapshot = clone_snapshot(self.normal_snapshot)
        snapshot.project.projectName = 'QA 独立恢复草稿（原件已改）'
        snapshot.project.seed = 'unfinished-'
        snapshot.project.runSettings.seed = None
        snapshot.state['drafts']['project.project_name'] = snapshot.project.projectName
        snapshot.state['drafts']['project.seed'] = 'unfinished-'
        snapshot.state['drafts']['config.seed'] = 'unfinished-'
        snapshot.project.materialEditor.rows[-1].density = '2.70 g/cm3'
        snapshot.project.materialEditor.is_dirty = True
        original = INPUTS / 'recovery-origin.json'
        receipt = save_project(project_for_snapshot(self.normal_snapshot), original)
        session = store.open_session()
        try:
            publication = session.publish(project_to_dict(project_for_snapshot(snapshot)), 11,
                                          origin_path=receipt.path, origin_sha256=receipt.sha256)
            session.retain()
            self.recovery_fixture_id = session.session_id
        finally:
            session.close()
        changed = project_for_snapshot(self.normal_snapshot)
        changed.projectName = 'QA 原件已被外部修改（夹具）'
        save_project(changed, original)
        self.case = 'inactive_recovery_origin_changed'
        self.note.setText('独立恢复副本已写入并释放锁；原件随后改写。请手动打开恢复列表，观察原件状态并选择恢复/保留。')
        self.emit('qa_fixture_prepared', fixture=self.case, recovery_id=self.recovery_fixture_id,
                  recovery_path=str(publication.path), origin_path=str(original),
                  original_recorded_sha256=receipt.sha256, current_origin_sha256=sha(original.read_bytes()),
                  evidence_scope='synthetic inactive session; not an actual crash')

    def prepare_corrupt(self):
        if self.broken_fixture_id and (RECOVERY / f'{self.broken_fixture_id}.json').exists():
            return
        RECOVERY.mkdir(parents=True, exist_ok=True)
        self.broken_fixture_id = uuid.uuid4().hex
        path = RECOVERY / f'{self.broken_fixture_id}.json'
        path.write_bytes(b'{"schema": "F5-QA-broken-json",')
        self.case = 'corrupt_recovery'
        self.note.setText('损坏条目已准备；请手动打开恢复列表，确认不能恢复且原始文件保留。')
        self.emit('qa_fixture_prepared', fixture=self.case, path=str(path), sha256=sha(path.read_bytes()))

    def arm_projection_failure(self):
        w, page = self.window, self.window.config_builder_page
        if not w.can_mutate_workspace('QA projection fault'):
            raise ValueError('Repair or stop the current product activity first.')
        self.disarm_projection()
        w.apply_editor_operation('QA fixture: create one undo point',
                                 lambda config, _project: config.beam_on.setValue(config.beam_on.value() + 1))
        assert w._edit_session.can_undo
        self.projection_original = page.set_from_project
        self.projection_remaining = 2
        def injected(*values, **options):
            original = self.projection_original
            self.projection_remaining -= 1
            page.beam_on.setValue(2569)
            self.emit('qa_projection_failure_injected', remaining=self.projection_remaining,
                      evidence_scope='injected fault during reviewer-invoked product action')
            if self.projection_remaining == 0:
                page.set_from_project = original
                self.projection_original = None
            raise RuntimeError('QA injected projection failure after widget mutation')
        page.set_from_project = injected
        self.case = 'double_projection_failure_armed'
        self.note.setText('双失败已布置，尚未执行撤销。请手动撤销，观察冻结；再用产品“恢复最后可证实编辑状态”修复。')
        self.emit('qa_fixture_armed', fixture=self.case, verified_sha256=snapshot_fingerprint(w._edit_session.current()))

    def disarm_projection(self):
        if self.projection_original is not None:
            self.window.config_builder_page.set_from_project = self.projection_original
            self.projection_original = None
        self.projection_remaining = 0

    def save_state(self):
        if self.closed or not isValid(self.window):
            return
        w, page = self.window, self.window.config_builder_page
        session = w._edit_session
        verified = session.current()
        focus = app.focusWidget()
        state = {'identity': IDENTITY, 'case': self.case, 'ready': self.ready,
                 'visual_acceptance': 'not_claimed', 'window_title': w.windowTitle(),
                 'base_style': BASE_STYLE_NAME, 'current_style_class': app.style().metaObject().className(),
                 'theme': app.property('resolvedTheme'),
                 'main_page': w.page_stack.currentIndex(), 'config_tab': page.workspace_tabs.currentIndex(),
                 'focus': {'class': type(focus).__name__, 'name': focus.objectName()} if focus else None,
                 'revision': session.revision, 'dirty': session.is_modified,
                 'can_undo': session.can_undo, 'can_redo': session.can_redo,
                 'verified_snapshot_sha256': snapshot_fingerprint(verified),
                 'verified_raw_drafts': verified.state['drafts'],
                 'verified_selection_hints': verified.state['selections'],
                 'project_file': str(w.project_file) if w.project_file else None,
                 'visible': {'seed_config': page.seed.text(), 'seed_project': w.project_page.seed.text(),
                             'source_energy': page.source_energy.text(), 'beam_on': page.beam_on.value()},
                 'package_stale': w._generated_package_stale, 'run_result': w.run_page._result_state,
                 'workspace_fault': w._workspace_fault, 'repair_action_visible': w.repair_editor_action.isVisible(),
                 'recovery_status': w.recovery_status.text(), 'projection_failures_remaining': self.projection_remaining,
                 'recovery_root': str(RECOVERY), 'history_path': str(run_history_store.STATE_PATH),
                 'note': self.note.text(), 'event_sequence': self.sequence}
        write_json(ARTIFACTS / 'state.json', state)

    def eventFilter(self, watched, event):  # noqa: N802
        # Close events also occur while Qt dismantles child trees. Never inspect
        # objects or schedule state traversal from those notifications.
        if event.type() == QEvent.Close or self.closed or not self.ready:
            return False
        if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress) and isinstance(watched, QWidget):
            if watched.window() is self.window or self.window.isAncestorOf(watched):
                self.emit('qt_input_observed', event_type=int(event.type()), spontaneous=event.spontaneous(),
                          target_class=type(watched).__name__, target_name=watched.objectName(),
                          evidence_scope='Qt event observation; native screenshot/action receipt remains independent')
        return False

    def precheck(self):
        assert app.platformName() == 'offscreen'
        assert BASE_STYLE_NAME.lower() == 'fusion' and bool(app.styleSheet())
        assert app.property('resolvedTheme') == args.theme
        assert not self.window._edit_session.is_modified
        normal_report = self.window.config_builder_page.validate_current(self.window.project)
        assert normal_report.can_run, normal_report.errors
        self.prepare_recovery()
        self.prepare_corrupt()
        store = RecoveryStore(RECOVERY)
        candidates = store.discover()
        good = next(c for c in candidates if c.session_id == self.recovery_fixture_id)
        bad = next(c for c in candidates if c.session_id == self.broken_fixture_id)
        assert good.error == '' and bad.error
        with store.claim(good) as claim:
            assert origin_status(claim.read()) == 'changed'
        self.arm_projection_failure()
        assert self.projection_remaining == 2 and self.window._edit_session.can_undo
        assert not self.window._workspace_fault
        self.disarm_projection()
        self.prepare_normal()
        self.save_state()
        write_json(ARTIFACTS / 'precheck.json', {'passed': True, 'fixtures': 4,
                   'base_style': BASE_STYLE_NAME, 'actual_undo_restore_repair_invoked': False,
                   'visual_acceptance': 'not_claimed', 'recovery_candidate_count': len(candidates)})
        assert self.window.close()
        app.processEvents()


host = Host()
original_excepthook = sys.excepthook
def capture_exception(kind, value, tb):
    host.emit('python_exception', traceback=''.join(traceback.format_exception(kind, value, tb)))
    original_excepthook(kind, value, tb)
sys.excepthook = capture_exception
faulthandler.enable(all_threads=True)
requested_exit = 0
try:
    if args.precheck:
        host.precheck()
    else:
        host.window.show()
        host.save_state()
        print(json.dumps({'ready': True, 'pid': os.getpid(), 'state': str(ARTIFACTS / 'state.json'),
                          'visual_acceptance': 'not_claimed'}, ensure_ascii=False), flush=True)
        requested_exit = app.exec()
except Exception:
    requested_exit = 1
    traceback.print_exc()
    host.emit('host_exception', traceback=traceback.format_exc())
finally:
    host.timer.stop()
    app.removeEventFilter(host)
    host.ready = False
    host.disarm_projection()
    if not host.closed:
        if args.precheck and not host.window._workspace_fault:
            # Precheck creates only our synthetic fixture changes, so return to
            # its clean baseline before exercising normal product shutdown.
            host.prepare_normal()
        host.window.close()
        if not host.closed and not args.precheck:
            # Do not override a product Cancel/repair requirement on shutdown.
            app.exec()
        if not host.closed:
            requested_exit = 1
    host.emit('host_finished', requested_exit=requested_exit, product_close_accepted=host.closed)
    write_json(ARTIFACTS / 'exit.json', {'requested_exit': requested_exit, 'product_close_accepted': host.closed,
               'exit_scope': 'Python-requested return; launcher receipt must verify actual process exit',
               'visual_acceptance': 'not_claimed'})
    if not host.closed:
        # No prompt bypass on exceptional shutdown; preserve recovery before
        # QObject teardown. Parent must treat a nonzero launcher result as failure.
        host.window._recovery.close(keep=True)
        requested_exit = 1
    host.window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
print('F5 QA host requested exit', requested_exit, 'artifacts', ARTIFACTS, flush=True)
raise SystemExit(requested_exit)
