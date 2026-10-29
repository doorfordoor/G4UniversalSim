"""Qt combo role semantics and missing-data reference ownership regression."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QComboBox
from g4usim_gui.widgets.qt_data import combo_data


def main():
    app = QApplication.instance() or QApplication([])
    combo = QComboBox()
    for number, payload in enumerate((0, False, "", "名称\u00a0", [0, False, ""], {"key": 3}, ("scorer", "value"))):
        combo.addItem(str(number), payload)
        combo.setCurrentIndex(number)
        # Only non-missing roles use the original getter as an independent reference.
        expected = combo.currentData()
        actual = combo_data(combo)
        assert type(actual) is type(expected) and actual == expected
        assert combo_data(combo, number) == expected
    combo.addItem("no user role")
    missing = combo.count() - 1
    assert combo_data(combo, missing) is None
    combo.setCurrentIndex(-1)
    assert combo_data(combo) is None
    assert combo_data(combo, -1) is None
    assert combo_data(combo, combo.count()) is None
    # Measure a steady loop, retaining no extra None references as a workaround.
    for _ in range(20):
        combo_data(combo, missing)
        combo_data(combo)
    before = sys.getrefcount(None)
    for _ in range(1000):
        combo_data(combo, missing)
        combo_data(combo)
    after = sys.getrefcount(None)
    print(f"missing-role None references: before={before} after={after} delta={after-before}")
    assert before - after < 10, (before, after)

    tree = QComboBox()
    model = QStandardItemModel(tree)
    root = QStandardItem("root")
    root.setData("wrong root", Qt.ItemDataRole.UserRole)
    model.appendRow(root)
    left, right = QStandardItem("left"), QStandardItem("right")
    left.setData("wrong column", Qt.ItemDataRole.UserRole)
    right.setData("selected child", Qt.ItemDataRole.UserRole)
    right.setData(False, int(Qt.ItemDataRole.UserRole) + 1)
    root.appendRow([left, right])
    root_index = model.index(0, 0)
    tree.setModel(model)
    tree.setRootModelIndex(root_index)
    tree.setModelColumn(1)
    tree.setCurrentIndex(0)
    assert combo_data(tree) == "selected child"
    assert combo_data(tree, 0, int(Qt.ItemDataRole.UserRole) + 1) is False
    assert combo_data(tree, -1) is None
    assert combo_data(tree, 1) is None
    assert tree.rootModelIndex() == root_index
    assert tree.modelColumn() == 1 and tree.currentIndex() == 0
    assert combo_data(tree, 0, Qt.ItemDataRole.DisplayRole) == "right"
    combo.close()
    tree.close()
    combo.deleteLater()
    tree.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    del combo, tree, model, root, left, right
    # Exercise the product entry points too, so a future missed import/use is caught.
    from g4usim_gui.widgets.plot_panel import PlotPanel
    from g4usim_gui.widgets.scan_page import ScanPage
    plot = PlotPanel()
    scan = ScanPage()
    scan.refresh_results()
    assert plot.current_dataset() is None and scan.current_metric() is None
    for name, getter in (("plot.current_dataset", plot.current_dataset), ("scan.current_metric", scan.current_metric)):
        for _ in range(20):
            getter()
        before = sys.getrefcount(None)
        for _ in range(1000):
            getter()
        after = sys.getrefcount(None)
        print(f"{name} None references: before={before} after={after} delta={after-before}")
        assert before - after < 10, (name, before, after)
    del getter
    plot.close()
    scan.close()
    plot.deleteLater()
    scan.deleteLater()
    app.processEvents()
    del plot, scan
    print("smoke_qt_combo_data: ok")


if __name__ == "__main__":
    main()
