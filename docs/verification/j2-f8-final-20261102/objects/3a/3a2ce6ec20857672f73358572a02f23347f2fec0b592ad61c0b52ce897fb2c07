import os,sys,runpy
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'out/collab/f8-layout-item-compat';scale=os.environ['F8_PROBE_SCALE'];os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']=scale
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests'),str(OUT)]
from candidate import install
install()
artifacts=OUT/('full-'+scale);artifacts.mkdir(parents=True,exist_ok=True)
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),str(OUT/'smoke_f8_accessibility.proposed.py'),'--output',str(artifacts)]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
