"""Measure getter reference deltas, retaining no extra None references."""
import gc
import json
import os
import sys
os.environ['QT_QPA_PLATFORM']='offscreen'
import PySide6, shiboken6
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QComboBox,QLineEdit

def main():
    app=QApplication([])
    combo=QComboBox()
    combo.addItem('empty-data')
    combo.addItem('string-data','token')
    line=QLineEdit('text')
    records=[]
    getters=[('combo_currentData_empty',lambda:combo.currentData()),
             ('combo_itemData_empty',lambda:combo.itemData(0)),
             ('combo_itemData_string',lambda:combo.itemData(1)),
             ('combo_currentText',lambda:combo.currentText()),
             ('widget_isEnabled',lambda:combo.isEnabled()),
             ('line_text',lambda:line.text())]
    for name,getter in getters:
        for _ in range(10):getter()
        before=sys.getrefcount(None)
        for _ in range(500):getter()
        after=sys.getrefcount(None)
        records.append({'getter':name,'calls':500,'before':before,'after':after,'delta':after-before})
    print(json.dumps({'python':sys.version,'pyside':PySide6.__version__,'shiboken':shiboken6.__version__,'records':records}),flush=True)
    getters.clear()
    del getter
    combo.close();line.close()
    combo.deleteLater();line.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents()
    del combo,line
    gc.collect()
    print('normal widget teardown complete; None refs',sys.getrefcount(None),flush=True)

main()
