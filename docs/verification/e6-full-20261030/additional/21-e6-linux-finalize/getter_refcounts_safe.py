"""Read the exact UserRole through a role map, not a missing QVariant getter."""
import gc
import json
import os
import sys
os.environ['QT_QPA_PLATFORM']='offscreen'
import PySide6,shiboken6
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication,QComboBox

def role_data(combo,row):
    model=combo.model()
    index=model.index(row,combo.modelColumn(),combo.rootModelIndex())
    return model.itemData(index).get(int(Qt.ItemDataRole.UserRole))

def main():
    app=QApplication([])
    combo=QComboBox()
    combo.addItem('empty-data')
    combo.addItem('string-data','token')
    records=[]
    for name,row in [('empty',0),('token',1),('no_selection',-1)]:
        for _ in range(10):role_data(combo,row)
        before=sys.getrefcount(None)
        for _ in range(500):role_data(combo,row)
        after=sys.getrefcount(None)
        records.append({'getter':'model_role_map_'+name,'calls':500,'before':before,'after':after,'delta':after-before})
    print(json.dumps({'python':sys.version,'pyside':PySide6.__version__,'shiboken':shiboken6.__version__,'records':records}),flush=True)
    # These are equality assertions after measurement, not retained references.
    assert role_data(combo,0) is None
    assert role_data(combo,1)=='token'
    assert role_data(combo,-1) is None
    combo.close();combo.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents()
    del combo
    gc.collect()
    print('normal widget teardown complete; None refs',sys.getrefcount(None),flush=True)

main()
