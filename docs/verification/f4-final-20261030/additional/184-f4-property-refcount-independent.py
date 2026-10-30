"""Small independent binding probe; does not import any product code."""
import argparse, sys, json, gc
from PySide6 import __version__
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget
parser=argparse.ArgumentParser()
parser.add_argument('mode', choices=('missing','guarded','present'))
args=parser.parse_args()
app=QApplication([])
w=QWidget()
if args.mode=='present':w.setProperty('diagnosticFocus', True)
def getter():
    if args.mode=='guarded' and b'diagnosticFocus' not in w.dynamicPropertyNames():return None
    return w.property('diagnosticFocus')
for _ in range(10):getter()
gc.collect()
before=sys.getrefcount(None)
for _ in range(500):getter()
after=sys.getrefcount(None)
print(json.dumps({'mode':args.mode,'python':sys.version,'pyside':__version__,
                  'iterations':500,'none_before':before,'none_after':after,'delta':after-before}),flush=True)
w.close();w.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
