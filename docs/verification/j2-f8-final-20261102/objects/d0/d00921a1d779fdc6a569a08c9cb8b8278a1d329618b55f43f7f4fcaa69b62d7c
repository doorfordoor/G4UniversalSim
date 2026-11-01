import os,sys,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']='1.5'
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
namespace=runpy.run_path(str(OUT/'smoke_f8_accessibility.proposed.py'),run_name='qt_provider_component')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase
app=QApplication([]);app.setStyle('Fusion');app.setApplicationName('QtProviderNameComponent');app.setOrganizationName('G4UniversalSimSmoke')
QSettings.setDefaultFormat(QSettings.IniFormat)
for name in ('segoeui.ttf','msyh.ttc'):QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
namespace['test_history_directory_accessibility'](app,OUT/'windows-targeted')
print('Windows exact candidate History function + genuine missing-buddy negative passed')
