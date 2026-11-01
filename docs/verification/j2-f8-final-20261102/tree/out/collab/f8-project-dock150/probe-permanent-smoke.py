import os,sys,runpy
from pathlib import Path
ROOT=Path.cwd()
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_SCALE_FACTOR']=os.environ['F8_PROBE_SCALE']
sys.path[:0]=[str(ROOT/'gui'),str(ROOT/'gui/smoke_tests'),str(ROOT/'out/collab/f8-project-dock150')]
from candidate import install
install()
out=ROOT/'out/collab/f8-project-dock150'/('permanent-v2-smoke-'+os.environ['F8_PROBE_SCALE']);out.mkdir(parents=True,exist_ok=True)
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),str(ROOT/'out/collab/f8-project-dock150/smoke_f8_accessibility.proposed.py'),'--output',str(out)]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
