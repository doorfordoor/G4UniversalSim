"""Wait for actual queued verification results; never bypass content checks."""
import time
from PySide6.QtWidgets import QApplication, QWidget

def wait_for_idle(widget,timeout=15):
    app=QApplication.instance();deadline=time.monotonic()+timeout;quiet=0
    while time.monotonic()<deadline:
        app.processEvents()
        widgets=[widget,*widget.findChildren(QWidget)]
        pending=any(getattr(getattr(item,name,None),'pending',False) for item in widgets for name in ('_identity_job','_scan_job','_selection_job'))
        quiet=0 if pending else quiet+1
        if quiet>=3:return
        time.sleep(.005)
    assert False,'queued output verification did not finish within bound'
