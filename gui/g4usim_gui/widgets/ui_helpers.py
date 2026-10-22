from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def create_section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("uiRole", "sectionTitle")
    return label


def create_hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("uiRole", "hint")
    return label


def create_empty_state_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setAlignment(Qt.AlignCenter)
    label.setProperty("uiRole", "emptyState")
    return label


class CollapsibleSection(QWidget):
    """A group box whose title is a toggle: the user can fold the section away.

    The group keeps its widgets and layout; only its title moves to the toggle button
    (so translation still finds it as button text).
    """

    def __init__(self, group: QGroupBox, expanded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.group = group
        self.toggle = QToolButton()
        self.toggle.setText(group.title())
        self.toggle.setProperty("sectionToggle", True)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setCursor(Qt.PointingHandCursor)
        group.setTitle("")
        group.setProperty("uiRole", "panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle)
        layout.addWidget(group)
        self.toggle.toggled.connect(self.set_expanded)
        self.toggle.setChecked(expanded)
        self.set_expanded(expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.group.setVisible(expanded)
        if self.toggle.isChecked() != expanded:
            self.toggle.setChecked(expanded)

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()


def set_table_compact_readonly(table: QTableWidget) -> None:
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    table.verticalHeader().setVisible(False)


def set_table_minimum_rows(table: QTableWidget, rows: int = 8, row_height: int = 28) -> None:
    table.setMinimumHeight(max(180, rows * row_height + 44))


def make_path_row(line_edit: QLineEdit, button_text: str, callback) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    line_edit.setMinimumWidth(180)
    button = QPushButton(button_text)
    button.clicked.connect(callback)
    layout.addWidget(line_edit, 1)
    layout.addWidget(button)
    return container


def show_error_message(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_info_message(parent: QWidget, title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)
