from pathlib import Path
import sys,os,time,json,tempfile
root=Path.cwd();sys.path[:0]=[str(root/'gui'),str(root/'gui/smoke_tests')];os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from gui_test_window import MainWindow
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
w=MainWindow();w.show();app.processEvents();records=[]
for name in ('_confirm_unsaved_edits','_finish_history_merge','flush_pending_edit','capture_workspace','history_changed','_recovery_before_close'):
 original=getattr(w,name)
 def wrapped(*args,_name=name,_original=original,**kwargs):
  start=time.perf_counter()
  try:return _original(*args,**kwargs)
  finally:records.append({'method':_name,'seconds':time.perf_counter()-start})
 setattr(w,name,wrapped)
start=time.perf_counter();result=w.close();elapsed=time.perf_counter()-start;app.processEvents()
print(json.dumps({'close':result,'seconds':elapsed,'calls':records},indent=2))
