import os,sys,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
os.environ['QT_QPA_PLATFORM']='offscreen';sys.path[:0]=[str(OUT),str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
import PySide6
if sys.platform!='win32':os.environ['QT_PLUGIN_PATH']=str(Path(PySide6.__file__).parent/'Qt/plugins')
print('runtime',sys.version,PySide6.__version__,sys.executable,flush=True)
output=OUT/sys.argv[1];output.mkdir(parents=True,exist_ok=True)
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),str(OUT/'smoke_f8_accessibility.proposed.py'),'--output',str(output)]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
