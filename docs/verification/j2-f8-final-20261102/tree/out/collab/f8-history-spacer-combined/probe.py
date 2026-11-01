import os,sys,runpy,json,hashlib
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'out/collab/f8-history-spacer-combined';scale=os.environ['F8_PROBE_SCALE'];os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_SCALE_FACTOR']=scale
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests')]
# Load the two unchanged product proposals in dependency order, only in memory.
paths=[ROOT/'out/collab/f8-layout-item-compat/candidate.py',ROOT/'out/collab/f8-history-label/v2/candidate.py']
for path in paths:runpy.run_path(str(path))['install']()
artifacts=OUT/('scale'+scale);artifacts.mkdir(parents=True,exist_ok=True)
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),str(OUT/'smoke_f8_accessibility.proposed.py'),'--output',str(artifacts)]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
