"""Candidate-only semantic and reference-count checks; no frozen code edits."""
import gc
import json
import os
import sys
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtGui import QStandardItem,QStandardItemModel
from PySide6.QtWidgets import QApplication,QComboBox
import PySide6
from qt_data_candidate import combo_data

def main():
    app=QApplication([])
    combo=QComboBox()
    payloads=[0,False,'','名称\u00a0',[0,False,''],{'x':1},{'x':None}]
    for number,value in enumerate(payloads):combo.addItem(str(number),value)
    combo.addItem('missing-role')
    records=[]
    for row,expected in enumerate(payloads):
        combo.setCurrentIndex(row)
        actual=combo_data(combo)
        assert type(actual) is type(expected) and actual==expected,(row,actual,expected)
        assert combo_data(combo,row)==actual
        before=sys.getrefcount(None)
        for _ in range(500):combo_data(combo,row)
        after=sys.getrefcount(None)
        records.append({'row':row,'type':type(expected).__name__,'calls':500,'delta':after-before})
    missing=len(payloads)
    assert combo_data(combo,missing) is None
    combo.setCurrentIndex(-1)
    assert combo_data(combo) is None
    assert combo_data(combo,1000) is None
    before=sys.getrefcount(None)
    for _ in range(500):combo_data(combo,missing)
    records.append({'row':'missing','calls':500,'delta':sys.getrefcount(None)-before})
    tree=QComboBox()
    model=QStandardItemModel(tree)
    parent=QStandardItem('root')
    parent.setData('wrong-root',Qt.ItemDataRole.UserRole)
    model.appendRow(parent)
    first=QStandardItem('wrong-column')
    first.setData('wrong-column-data',Qt.ItemDataRole.UserRole)
    second=QStandardItem('visible-name')
    second.setData('right-child-column',Qt.ItemDataRole.UserRole)
    second.setData('secondary-role',int(Qt.ItemDataRole.UserRole)+1)
    parent.appendRow([first,second])
    root=model.index(0,0)
    tree.setModel(model)
    tree.setRootModelIndex(root)
    tree.setModelColumn(1)
    tree.setCurrentIndex(0)
    assert combo_data(tree)=='right-child-column'
    assert combo_data(tree,0,int(Qt.ItemDataRole.UserRole)+1)=='secondary-role'
    assert combo_data(tree,-1) is None
    assert combo_data(tree,1) is None
    assert tree.rootModelIndex()==root and tree.modelColumn()==1 and tree.currentIndex()==0
    print(json.dumps({'python':sys.version,'pyside':PySide6.__version__,'records':records,'custom_root_column':'pass'}),flush=True)
    combo.close();tree.close()
    combo.deleteLater();tree.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents()
    del combo,tree,model,parent,first,second
    gc.collect()
    print('candidate role reader semantic checks and natural teardown complete',flush=True)

main()
