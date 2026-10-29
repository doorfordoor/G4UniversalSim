from __future__ import annotations
import gc,json,sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem,QStandardItemModel
from PySide6.QtWidgets import QApplication,QComboBox

def item_data(combo,index,role=Qt.ItemDataRole.UserRole):
    model=combo.model()
    cell=model.index(index,combo.modelColumn(),combo.rootModelIndex())
    return model.itemData(cell).get(int(role))

def current_data(combo,role=Qt.ItemDataRole.UserRole):
    return item_data(combo,combo.currentIndex(),role)

app=QApplication([])
rows=[]
def check(combo,label):
    # Only a bounded set of original getter calls establishes semantic equality;
    # stress checks use the proposed role-map exclusively.
    for index in range(-1,combo.count()+1):
        expected=combo.itemData(index)
        actual=item_data(combo,index)
        assert actual==expected,(label,index,expected,actual)
        rows.append({"case":label,"index":index,"value":actual})
    for index in (-1,*range(combo.count())):
        combo.setCurrentIndex(index)
        assert current_data(combo)==combo.currentData(),(label,index)
    return combo

combo=QComboBox()
for text,value in (("missing",None),("text","token"),("zero",0),("false",False),("integer",17),("floating",1.25),("list",[1,"x"]),("dict",{"key":"value"})):
    if text=="missing":combo.addItem(text)
    else:combo.addItem(text,value)
combo.addItem("explicit None",None)
check(combo,"default model including missing and explicit None")
assert int(Qt.ItemDataRole.UserRole) not in combo.model().itemData(combo.model().index(0,0))
assert int(Qt.ItemDataRole.UserRole) not in combo.model().itemData(combo.model().index(8,0))
# modelColumn/rootModelIndex are part of QComboBox itemData semantics.
model=QStandardItemModel();parent=QStandardItem("parent");model.appendRow(parent)
parent.appendRow([QStandardItem("wrong column"),QStandardItem("correct column")])
parent.child(0,0).setData("wrong data",Qt.ItemDataRole.UserRole)
parent.child(0,1).setData("right data",Qt.ItemDataRole.UserRole)
custom=QComboBox();custom.setModel(model);custom.setRootModelIndex(parent.index());custom.setModelColumn(1)
check(custom,"custom model column and root")
assert current_data(custom)=="right data"
# DisplayRole is also preserved, although existing state probes only need UserRole.
assert item_data(custom,0,Qt.ItemDataRole.DisplayRole)==custom.itemData(0,Qt.ItemDataRole.DisplayRole)
combo.setCurrentIndex(-1)
gc.collect();before=sys.getrefcount(None)
for _ in range(10000):
    value=current_data(combo)
    value=item_data(combo,0)
    assert value is None
    assert item_data(combo,1)=="token"
after=sys.getrefcount(None)
# Python locals can add a bounded reference, but no per-call drain is acceptable.
assert after>=before-3,(before,after)
print(json.dumps({"semantic_rows":rows,"role_map_refcounts":{"before":before,"after":after,"delta":after-before},"stress_iterations":10000,"business_assertions_retained":True}),flush=True)
combo.close();custom.close();combo.deleteLater();custom.deleteLater();app.processEvents()
