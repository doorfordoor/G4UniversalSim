from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
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
