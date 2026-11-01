"""Isolated real Windows host; setup and passive observation only, no UI input."""
from __future__ import annotations
import argparse, dataclasses, hashlib, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'gui'))
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--language', default='zh_CN')
parser.add_argument('--width', type=int, default=1200)
parser.add_argument('--height', type=int, default=800)
parser.add_argument('--x', type=int, default=20)
parser.add_argument('--y', type=int, default=20)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
from PySide6.QtCore import QSettings, QTimer, QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QDialog
from g4usim_gui.history import run_history_store
run_history_store.STATE_PATH = output / 'history.json'
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(output / 'settings'))
os.environ['G4USIM_RECOVERY_DIR'] = str(output / 'recovery')
from g4usim_gui.core.i18n import set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.main_window import MainWindow
app = QApplication([])
app.setApplicationName('J2 F8 Native Acceptance')
app.setOrganizationName('G4UniversalSimAcceptance')
app.setStyle('Fusion')
apply_theme(app, 'light')
set_application_language(app, args.language)
window = MainWindow(recovery_root=output / 'recovery', offer_recovery=False)
p = window.project
p.executable = os.environ['G4USIM_EXE']
p.pathSettings.executable = p.executable
p.runsRoot = str(output / 'runs')
p.pathSettings.runs_root = p.runsRoot
p.outputDir = str(output / 'runs' / 'demo' / 'output')
window._set_project(p)
window._reset_edit_history()
window.resize(args.width, args.height)
window.move(args.x, args.y)
window.setWindowTitle('J2 F8 Native Acceptance')
files = {str(f.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(f.read_bytes()).hexdigest()
         for f in (ROOT / 'gui' / 'g4usim_gui').rglob('*.py')}
(output / 'identity.json').write_text(json.dumps({'gui_files': files, 'exe': p.executable,
    'exe_sha256': hashlib.sha256(Path(p.executable).read_bytes()).hexdigest(), 'pid': os.getpid(),
    'scale_factor': os.environ.get('QT_SCALE_FACTOR', ''), 'language': args.language,
    'screen_geometry': list(window.screen().geometry().getRect()),
    'available_geometry': list(window.screen().availableGeometry().getRect()),
    'logical_dpi': window.screen().logicalDotsPerInch(),
    'physical_dpi': window.screen().physicalDotsPerInch(),
    'fixture': 'Production MainWindow, isolated settings/history/recovery/runs; no input automation in host'}, indent=2), encoding='utf-8')
last = None
def observe():
    global last
    focus = app.focusWidget()
    modal = app.activeModalWidget()
    state = {'page': window.page_stack.currentIndex(), 'title': window.windowTitle(),
        'focus': {'class': type(focus).__name__, 'object_name': focus.objectName(), 'name': focus.accessibleName()} if focus else None,
        'modal': modal.windowTitle() if modal else None,
        'dialogs': [w.windowTitle() for w in app.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()],
        'size': [window.width(), window.height()], 'dpr': window.devicePixelRatioF(),
        'project_file': str(window.project_file) if window.project_file else None,
        'project_sha': hashlib.sha256(json.dumps(dataclasses.asdict(window.project), sort_keys=True, default=str).encode()).hexdigest(),
        'runner_state': str(window.runner._process.state())}
    if state != last:
        with (output / 'observations.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'time': time.time(), **state}, ensure_ascii=False) + '\n')
        last = state
timer = QTimer()
timer.setInterval(300)
timer.timeout.connect(observe)
timer.start()
window.show()
code = app.exec()
timer.stop()
(output / 'exit.json').write_text(json.dumps({'exit_code': code, 'time': time.time(), 'visible': window.isVisible()}), encoding='utf-8')
window.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
app.processEvents()
sys.exit(code)
