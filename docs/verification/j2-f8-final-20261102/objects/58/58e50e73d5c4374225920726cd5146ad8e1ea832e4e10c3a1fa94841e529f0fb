import os,sys,runpy
from pathlib import Path
root=Path.cwd();out=root/'out/collab/f8-history-label/v2';scale=os.environ['F8_PROBE_SCALE'];os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']=scale
sys.path[:0]=[str(root/'gui'),str(root/'gui/smoke_tests'),str(out)]
from candidate import install
install()
artifacts=out/('scale'+scale);artifacts.mkdir(parents=True,exist_ok=True)
sys.argv=[str(root/'tools/test_assert_probe.py'),str(out/'smoke_f8_accessibility.proposed.py'),'--output',str(artifacts)]
runpy.run_path(str(root/'tools/test_assert_probe.py'),run_name='__main__')
