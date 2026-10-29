from __future__ import annotations
import gc, json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'gui'))
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QComboBox
from g4usim_gui.widgets.qt_data import combo_data

app = QApplication([])
class Payload:
    def __init__(self): self.value = 17
payload = Payload()
combo = QComboBox()
values = [0, False, '', 'name\u00a0', 1.25, [0, False, ''], {'key': 3}, ('scorer','value'), payload]
for row, value in enumerate(values):
    combo.addItem(str(row), value)
    combo.setCurrentIndex(row)
    expected = combo.currentData()
    actual = combo_data(combo)
    assert type(actual) is type(expected) and actual == expected, (row, type(actual), type(expected))
    assert combo_data(combo, row) == expected
assert combo_data(combo, len(values)-1) is payload
combo.addItem('missing')
missing = combo.count()-1
combo.addItem('explicit None', None)
assert combo_data(combo, missing) is None
assert combo_data(combo, missing+1) is None
combo.setCurrentIndex(-1)
assert combo_data(combo) is None
assert combo_data(combo,-1) is None and combo_data(combo,combo.count()) is None

tree = QComboBox()
model = QStandardItemModel(tree)
root = QStandardItem('root'); root.setData('wrong root', Qt.ItemDataRole.UserRole)
model.appendRow(root)
left, right = QStandardItem('left'), QStandardItem('right')
left.setData('wrong column', Qt.ItemDataRole.UserRole)
right.setData('right child', Qt.ItemDataRole.UserRole)
right.setData(False, int(Qt.ItemDataRole.UserRole)+1)
root.appendRow([left,right])
tree.setModel(model); tree.setRootModelIndex(model.index(0,0)); tree.setModelColumn(1); tree.setCurrentIndex(0)
assert combo_data(tree) == tree.currentData() == 'right child'
assert combo_data(tree,0,int(Qt.ItemDataRole.UserRole)+1) is False
assert combo_data(tree,0,Qt.ItemDataRole.DisplayRole) == tree.itemData(0,Qt.ItemDataRole.DisplayRole) == 'right'
assert combo_data(tree,1) is None
assert tree.modelColumn() == 1 and tree.rootModelIndex() == model.index(0,0) and tree.currentIndex() == 0

def measure(label, getter):
    for _ in range(50): assert getter() is None
    gc.collect()
    samples = [sys.getrefcount(None)]
    for _ in range(3):
        for _ in range(2000): assert getter() is None
        samples.append(sys.getrefcount(None))
    deltas = [b-a for a,b in zip(samples,samples[1:])]
    # Stable bounded interpreter noise is allowed. A per-call drain is not.
    assert min(deltas) >= -10, (label, samples, deltas)
    return {'case':label,'samples':samples,'deltas':deltas,'iterations_per_batch':2000}

results = [measure('helper_missing_role', lambda:combo_data(combo,missing)), measure('helper_invalid_selection',lambda:combo_data(combo))]
if '--product' in sys.argv:
    from g4usim_gui.widgets.plot_panel import PlotPanel
    from g4usim_gui.widgets.scan_page import ScanPage
    plot = PlotPanel(); scan = ScanPage()
    results.extend([measure('product_empty_current_dataset',plot.current_dataset), measure('product_empty_current_metric',scan.current_metric)])
    plot.close(); scan.close(); plot.deleteLater(); scan.deleteLater()
combo.close(); tree.close(); combo.deleteLater(); tree.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete); app.processEvents()
print(json.dumps({'python':sys.version,'pyside':pyside_version,'semantics':'all pass','refcount_batches':results}),flush=True)
