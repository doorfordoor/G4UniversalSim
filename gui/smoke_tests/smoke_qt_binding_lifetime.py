"""GUI regression: binding None returns must preserve Python ownership."""
from __future__ import annotations
import gc
import json
import os
import platform
import sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6 import __version__ as pyside_version
import shiboken6
from PySide6.QtCore import QCoreApplication,QEvent,qVersion
from PySide6.QtWidgets import QApplication,QWidget

def main():
    print(json.dumps({'python':sys.version,'implementation':platform.python_implementation(),
         'PySide6':pyside_version,'shiboken6':shiboken6.__version__,'Qt':qVersion()}),flush=True)
    assert pyside_version == shiboken6.__version__, 'Unmatched PySide6/shiboken6 pair'
    app=QApplication.instance() or QApplication([])
    widget=QWidget()
    def check(name,action):
        for _ in range(10):action()
        gc.collect()
        before=sys.getrefcount(None)
        for _ in range(100):action()
        after=sys.getrefcount(None)
        print(json.dumps({'operation':name,'iterations':100,'none_ref_delta':after-before}),flush=True)
        assert after == before, f'{name}: binding changed None refs by {after-before}'
    try:
        # Real app setters return None; the empty dynamic-property path is a
        # separate return conversion. Count alone never replaces process exit.
        check('QWidget.update',widget.update)
        check('QObject.setObjectName',lambda:widget.setObjectName('probe'))
        check('QObject.missing_property',lambda:widget.property('notDeclared'))
        widget.setProperty('probeBool',False)
        check('QObject.existing_false_property',lambda:widget.property('probeBool'))
        assert widget.property('probeBool') is False
        assert widget.objectName() == 'probe'
        assert b'notDeclared' not in widget.dynamicPropertyNames()
    finally:
        widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        app.processEvents()
    print('smoke_qt_binding_lifetime: OK (natural process exit still required)',flush=True)

if __name__=='__main__':main()
