"""Messages and files tab of the Configuration page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.widgets.ui_helpers import set_table_compact_readonly, set_table_minimum_rows


class DetailsPanel(QTabWidget):
    """Messages and files tab: messages, raw and generated files, the NIST quick list.

    The 3D tab's message box is shown here (it was always reparented to this tab).
    """

    def __init__(self, preview3d_messages: QPlainTextEdit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview3d_messages = preview3d_messages
        self.materials_messages = QPlainTextEdit()
        self.materials_messages.setReadOnly(True)
        self.materials_raw = QPlainTextEdit()
        self.materials_raw.setReadOnly(True)
        self.generated_materials_raw = QPlainTextEdit()
        self.generated_materials_raw.setReadOnly(True)
        self.nist_table = QTableWidget(0, 1)
        self.nist_table.setHorizontalHeaderLabels(["common NIST names"])
        set_table_compact_readonly(self.nist_table)
        set_table_minimum_rows(self.nist_table, 8)
        self.nist_table.itemClicked.connect(lambda item: QApplication.clipboard().setText(item.text()))
        self.geometry_messages = QPlainTextEdit()
        self.geometry_messages.setReadOnly(True)
        self.geometry_raw = QPlainTextEdit()
        self.geometry_raw.setReadOnly(True)
        self.generated_geometry_raw = QPlainTextEdit()
        self.generated_geometry_raw.setReadOnly(True)
        self.generated_main_ini_raw = QPlainTextEdit()
        self.generated_main_ini_raw.setReadOnly(True)
        self.validation_text = QPlainTextEdit()
        self.validation_text.setReadOnly(True)
        self.setDocumentMode(True)
        self.addTab(self._messages_tab(), "Messages")
        self.addTab(self._raw_files_tab(), "Raw Files")
        self.addTab(self._table_tab(QLabel("Click a material name to copy it to the clipboard."), self.nist_table), "NIST Quick List")

    def _messages_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("Validation result"))
        layout.addWidget(self.validation_text, 1)
        layout.addWidget(QLabel("Materials messages"))
        layout.addWidget(self.materials_messages, 1)
        layout.addWidget(QLabel("Geometry messages"))
        layout.addWidget(self.geometry_messages, 1)
        layout.addWidget(QLabel("3D Preview messages"))
        layout.addWidget(self.preview3d_messages, 1)
        return tab

    def _raw_files_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        raw_tabs = QTabWidget()
        raw_tabs.addTab(self.materials_raw, "Source materials raw")
        raw_tabs.addTab(self.generated_materials_raw, "Generated materials preview")
        raw_tabs.addTab(self.generated_geometry_raw, "Generated geometry preview")
        raw_tabs.addTab(self.generated_main_ini_raw, "Generated main.ini preview")
        raw_tabs.addTab(self.geometry_raw, "Geometry raw")
        layout.addWidget(raw_tabs, 1)
        return tab

    def _table_tab(self, label: QLabel, table: QTableWidget) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(label)
        layout.addWidget(table, 1)
        return tab
