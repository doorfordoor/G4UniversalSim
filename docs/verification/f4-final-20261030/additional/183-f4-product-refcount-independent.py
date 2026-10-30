"""Read-only actual product path probes, no MainWindow or backend required."""
import sys,json,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gui'))
from PySide6 import __version__
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QWidget
from g4usim_gui.core.i18n import apply_language,set_application_language
from g4usim_gui.widgets.diagnostic_navigation import WidgetHighlighter
app=QApplication([])
set_application_language(app,'en')
widget=QWidget()
highlighter=WidgetHighlighter()
def language():apply_language(widget,'en')
def highlighting():
    highlighter.highlight(widget)
    highlighter.clear()
for name, action in [('apply_language_one_widget',language),('highlight_clear',highlighting)]:
    for _ in range(10):action()
    gc.collect()
    before=sys.getrefcount(None)
    for _ in range(100):action()
    after=sys.getrefcount(None)
    print(json.dumps({'path':name,'iterations':100,'none_before':before,'none_after':after,
                      'delta':after-before,'python':sys.version,'pyside':__version__}),flush=True)
highlighter.clear();highlighter.deleteLater();widget.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
