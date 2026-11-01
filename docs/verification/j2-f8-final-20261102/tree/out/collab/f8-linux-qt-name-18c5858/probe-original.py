import os,sys,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
import PySide6
os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
print('runtime',sys.version,PySide6.__version__,sys.executable,flush=True)
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),str(ROOT/'gui/smoke_tests/smoke_f8_accessibility.py'),'--output',str(OUT/'linux-original-6113')]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
