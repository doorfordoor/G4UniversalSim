"""Keyboard-first launcher for pages, actions and appearances (Ctrl+K).

The window supplies the entries before every open; this module only renders,
filters and reports the chosen callback so keyboard behaviour is testable on
its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from g4usim_gui.core.i18n import ui_text
from g4usim_gui.core.theme import current_colors


@dataclass(frozen=True)
class PaletteEntry:
    """One palette row: what the user sees and what to run when it is chosen."""

    label: str
    category: str
    detail: str
    callback: Callable[[], None]


class CommandPalette(QDialog):
    """A small search dialog. ``exec()`` returns Accepted when an entry ran."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("commandPalette")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._entries: list[PaletteEntry] = []
        self.chosen: Callable[[], None] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 8)
        layout.setSpacing(8)

        self.category_label = QLabel()
        self.category_label.setObjectName("paletteCategory")
        layout.addWidget(self.category_label)

        self.search = QLineEdit()
        self.search.setObjectName("paletteSearch")
        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self.run_current)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setObjectName("paletteList")
        self.list.setUniformItemSizes(True)
        self.list.itemActivated.connect(lambda _item: self.run_current())
        layout.addWidget(self.list, 1)

        self.hint = QLabel()
        self.hint.setObjectName("paletteHint")
        layout.addWidget(self.hint)

        self.refresh_language()

    # -- public API -------------------------------------------------------
    @property
    def entries(self) -> list[PaletteEntry]:
        return list(self._entries)

    def set_entries(self, entries) -> None:
        self._entries = list(entries)
        self.chosen = None
        self.search.clear()
        self._refresh("")
        self.search.setFocus()

    def current_entry(self) -> PaletteEntry | None:
        item = self.list.currentItem()
        if item is None:
            return None
        index = item.data(Qt.UserRole)
        if index is None or not 0 <= int(index) < len(self._entries):
            return None
        return self._entries[int(index)]

    def run_current(self) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        self.chosen = entry.callback
        self.accept()

    def refresh_language(self) -> None:
        self.setWindowTitle(ui_text("Command palette"))
        self.search.setPlaceholderText(ui_text("Search pages, actions and appearances\u2026"))
        self.hint.setText(ui_text("Enter to run \u00b7 Esc to close"))
        self._refresh(self.search.text())

    # -- filtering --------------------------------------------------------
    def _matches(self, text: str) -> list[tuple[int, PaletteEntry]]:
        """Label matches win; actions/pages only fall back to category or detail."""
        tokens = [token for token in text.strip().lower().split() if token]

        def label_hit(entry: PaletteEntry) -> bool:
            label = entry.label.lower()
            return all(token in label for token in tokens)

        def full_hit(entry: PaletteEntry) -> bool:
            haystack = f"{entry.label} {entry.category} {entry.detail}".lower()
            return all(token in haystack for token in tokens)

        direct = [(index, entry) for index, entry in enumerate(self._entries) if label_hit(entry)]
        if direct:
            return direct
        return [(index, entry) for index, entry in enumerate(self._entries) if full_hit(entry)]

    def _refresh(self, text: str = "") -> None:
        self.list.clear()
        matches = self._matches(text)
        colours = current_colors(QApplication.instance())
        header_font = QFont(self.list.font())
        header_font.setPointSizeF(max(7.0, header_font.pointSizeF() - 2.0))
        header_font.setBold(True)
        category = None
        for index, entry in matches:
            if entry.category != category:
                category = entry.category
                header = QListWidgetItem(ui_text(entry.category + "s"))
                header.setFlags(Qt.NoItemFlags)
                header.setFont(header_font)
                header.setForeground(QColor(colours.text_muted))
                header.setData(Qt.UserRole, None)
                self.list.addItem(header)
            item = QListWidgetItem("    " + entry.label)
            item.setToolTip(entry.detail or entry.category)
            item.setData(Qt.UserRole, index)
            self.list.addItem(item)
        if matches:
            self._select_first()
        self.category_label.setText(
            ui_text("Command palette") if matches else ui_text("No matching command")
        )

    def _selectable_rows(self) -> list[int]:
        return [
            row
            for row in range(self.list.count())
            if self.list.item(row).data(Qt.UserRole) is not None
        ]

    def _select_first(self) -> None:
        rows = self._selectable_rows()
        if rows:
            self.list.setCurrentRow(rows[0])

    def _move_selection(self, step: int) -> None:
        rows = self._selectable_rows()
        if not rows:
            return
        current = self.list.currentRow()
        if current in rows:
            position = rows.index(current)
        else:
            position = 0 if step < 0 else -1
        position = min(max(position + step, 0), len(rows) - 1)
        self.list.setCurrentRow(rows[position])

    # -- keyboard ---------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.run_current()
            return
        if event.key() == Qt.Key_Down:
            self._move_selection(1)
            return
        if event.key() == Qt.Key_Up:
            self._move_selection(-1)
            return
        super().keyPressEvent(event)
