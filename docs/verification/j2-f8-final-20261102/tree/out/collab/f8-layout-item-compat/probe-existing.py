import os,sys,runpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
import PySide6
os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
if '--candidate' in sys.argv:
 sys.path.insert(0,str(OUT))
 from candidate import install
 install()
from g4usim_gui.main_window import MainWindow
original=MainWindow.__init__
def init(self,*args,**kwargs):
 original(self,*args,**kwargs)
 self.config_builder_page._backend_timer.stop()
 self.config_builder_page.schedule_backend_geometry=lambda *a,**k:None
MainWindow.__init__=init
name=sys.argv[1]
print('runtime',sys.version,PySide6.__version__,sys.executable,flush=True)
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),str(ROOT/'gui/smoke_tests'/name)]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
