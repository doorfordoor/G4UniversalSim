"""Proposed shared Qt role reader. Not applied to frozen product files."""
from PySide6.QtCore import Qt


def combo_data(combo, row=None, role=Qt.ItemDataRole.UserRole):
    if row is None:
        row = combo.currentIndex()
    model = combo.model()
    index = model.index(row, combo.modelColumn(), combo.rootModelIndex())
    if not index.isValid():
        return None
    return model.itemData(index).get(int(role))
