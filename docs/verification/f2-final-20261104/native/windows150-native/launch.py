from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from g4usim_gui.main_window import MainWindow
from g4usim_gui.core import i18n,theme
base=Path(__file__).resolve().parent
from g4usim_gui.history import run_history_store
run_history_store.STATE_PATH=base/'history.json'
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(base/'settings'))
app=QApplication([]);app.setStyle('Fusion');i18n.apply_language(app,'zh_CN');theme.apply_theme(app,'light')
w=MainWindow(recovery_root=base/'recovery',offer_recovery=False)
w.project_page.executable.setText(str(ROOT/'out/collab/f2-independent-build/Release/G4UniversalSim.exe'))
w.project_page.runs_root.setText(str(base/'runs'));w.flush_pending_edit()
w.resize(1440,900);w.setWindowTitle('G4UniversalSim F2 independent native review');w.show()
print(json.dumps({'candidate':'864bc036d6d7752475e52db4efd2b950cabfcc3d','backend_build':'864bc036d6d7752475e52db4efd2b950cabfcc3d','qt_platform':app.platformName(),'device_pixel_ratio':w.devicePixelRatioF(),'executable':w.project.executable}),flush=True)
rc=app.exec();print('GUI_EXIT',rc,flush=True);sys.exit(rc)
