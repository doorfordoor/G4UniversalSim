import os,sys,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests'),str(OUT)]
import PySide6
if sys.platform!='win32':os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
if '--candidate' in sys.argv:
 from candidate import install
 install()
namespace=runpy.run_path(str(OUT/'smoke_f8_accessibility.proposed.py'),run_name='layout_item_probe')
from PySide6.QtWidgets import QApplication
from g4usim_gui.core.theme import apply_theme
app=QApplication([]);app.setStyle('Fusion');apply_theme(app,'light')
print('runtime',sys.version,PySide6.__version__,sys.executable,flush=True)
namespace['test_layout_item_compatibility'](app)
print('real Qt stock layout + CI type replay + responsive language cases passed')
