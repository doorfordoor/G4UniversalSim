"""Out-only history/settings isolation; target tests and assert probe unchanged."""
from pathlib import Path
import os,runpy,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'))
from PySide6.QtCore import QSettings
from g4usim_gui.history import run_history_store
state=Path(os.environ['G4_F4_QA_STATE_ROOT']);state.mkdir(parents=True,exist_ok=True)
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,str(state/'settings'))
run_history_store.STATE_PATH=state/'history.json'
sys.argv=[str(ROOT/'tools/test_assert_probe.py'),*sys.argv[1:]]
runpy.run_path(str(ROOT/'tools/test_assert_probe.py'),run_name='__main__')
