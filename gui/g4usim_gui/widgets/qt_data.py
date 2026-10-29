"""Read combo roles without the missing-QVariant None return binding path."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox


def combo_data(combo: QComboBox, row: int | None = None,
               role: Qt.ItemDataRole | int = Qt.ItemDataRole.UserRole) -> Any:
    """Read roles exposed by the project's standard Qt combo models.

    PySide6 6.12 on Python 3.11 loses a None reference for missing combo data.
    Query the role map instead: an absent role is handled by Python's dict.get.
    Root/column and falsy values are preserved. Custom models that compute roles
    outside itemData(), and arbitrary nested QVariant binding bugs, are outside
    this helper's contract.
    """
    if row is None:
        row = combo.currentIndex()
    model = combo.model()
    index = model.index(row, combo.modelColumn(), combo.rootModelIndex())
    if not index.isValid():
        return None
    return model.itemData(index).get(int(role))
