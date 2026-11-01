import os,sys,runpy
from pathlib import Path
root=Path.cwd();os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']='1.5'
sys.path[:0]=[str(root/'gui'),str(root/'gui/smoke_tests')]
namespace=runpy.run_path(str(root/'out/collab/f8-project-dock150/v3/smoke_f8_accessibility.proposed.py'),run_name='permanent_baseline_control')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
app=QApplication([]);app.setApplicationName('F8-Retained-Baseline');app.setOrganizationName('G4UniversalSimSmoke');app.setStyle('Fusion')
for font in ('segoeui.ttf','msyh.ttc'):QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/font))
QSettings.setDefaultFormat(QSettings.IniFormat)
namespace['test_retained_dock_focus'](app,root/'out/collab/f8-project-dock150/v3/permanent-baseline150')
