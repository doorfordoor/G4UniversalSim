from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


ThemeMode = Literal["light", "dark", "system"]


@dataclass(frozen=True)
class ThemeColors:
    canvas: str
    surface: str
    surface_alt: str
    input: str
    text: str
    text_muted: str
    border: str
    border_strong: str
    accent: str
    accent_hover: str
    accent_soft: str
    selection: str
    success: str
    warning: str
    danger: str
    sidebar: str
    sidebar_hover: str
    sidebar_selected: str
    sidebar_text: str
    sidebar_muted: str


LIGHT = ThemeColors(
    canvas="#eef2f3",
    surface="#ffffff",
    surface_alt="#f6f8f8",
    input="#fbfcfc",
    text="#172126",
    text_muted="#607078",
    border="#d5dddf",
    border_strong="#b8c5c8",
    accent="#267a6d",
    accent_hover="#1f665c",
    accent_soft="#dceeea",
    selection="#cfe5e1",
    success="#2d7d57",
    warning="#a76618",
    danger="#b33b43",
    sidebar="#172126",
    sidebar_hover="#253238",
    sidebar_selected="#2d4548",
    sidebar_text="#f2f7f7",
    sidebar_muted="#9fb0b4",
)


DARK = ThemeColors(
    canvas="#111719",
    surface="#1a2326",
    surface_alt="#202a2e",
    input="#151d20",
    text="#eef4f4",
    text_muted="#a7b6ba",
    border="#334146",
    border_strong="#4b5b60",
    accent="#58b6a5",
    accent_hover="#70c9b8",
    accent_soft="#24413e",
    selection="#31534f",
    success="#68bd8d",
    warning="#e1a14d",
    danger="#ef747b",
    sidebar="#0b1012",
    sidebar_hover="#182125",
    sidebar_selected="#263b3e",
    sidebar_text="#f2f7f7",
    sidebar_muted="#91a3a8",
)


def resolve_theme(app: QApplication, mode: ThemeMode) -> Literal["light", "dark"]:
    if mode != "system":
        return mode
    window_color = app.palette().color(QPalette.Window)
    return "dark" if window_color.lightness() < 128 else "light"


def apply_theme(app: QApplication, mode: ThemeMode) -> Literal["light", "dark"]:
    resolved = resolve_theme(app, mode)
    colors = DARK if resolved == "dark" else LIGHT
    app.setStyleSheet(build_stylesheet(colors))
    app.setProperty("themeMode", mode)
    app.setProperty("resolvedTheme", resolved)
    return resolved


def build_stylesheet(c: ThemeColors) -> str:
    return f"""
QWidget {{
    color: {c.text};
    font-size: 13px;
}}
QMainWindow, QWidget#appShell, QWidget#contentHost, QWidget#pageViewport {{
    background: {c.canvas};
}}
QWidget#setupPanel {{
    background: {c.canvas};
}}
QWidget#sidebar {{
    background: {c.sidebar};
    color: {c.sidebar_text};
}}
QLabel#brandMark {{
    color: {c.sidebar_text};
    font-size: 19px;
    font-weight: 700;
}}
QLabel#brandCaption, QLabel#sidebarSection, QLabel#sidebarFooter {{
    color: {c.sidebar_muted};
}}
QLabel#sidebarSection {{
    font-size: 10px;
    font-weight: 700;
}}
QToolButton[navButton="true"] {{
    background: transparent;
    color: {c.sidebar_muted};
    border: 0;
    border-radius: 6px;
    padding: 10px 12px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
}}
QToolButton[navButton="true"]:hover {{
    background: {c.sidebar_hover};
    color: {c.sidebar_text};
}}
QToolButton[navButton="true"]:checked {{
    background: {c.sidebar_selected};
    color: {c.sidebar_text};
    border-left: 3px solid {c.accent};
    padding-left: 9px;
}}
QFrame#pageHeader {{
    background: {c.surface};
    border-bottom: 1px solid {c.border};
}}
QLabel#pageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {c.text};
}}
QLabel#pageSubtitle, QLabel[uiRole="hint"] {{
    color: {c.text_muted};
}}
QLabel[uiRole="sectionTitle"] {{
    color: {c.text};
    font-size: 14px;
    font-weight: 700;
}}
QLabel[uiRole="emptyState"] {{
    color: {c.text_muted};
    padding: 12px;
}}
QLabel[uiRole="contextChip"] {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 1px solid {c.border};
    border-radius: 6px;
    padding: 5px 9px;
}}
QLabel[statusRole="running"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border: 1px solid {c.accent};
    border-radius: 6px;
    padding: 5px 9px;
    font-weight: 600;
}}
QGroupBox {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 7px;
    margin-top: 16px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: {c.text};
}}
QScrollArea#sourceEditorScroll,
QScrollArea#sourceEditorScroll > QWidget > QWidget#sourceEditorContent {{
    background: {c.surface};
    border: 0;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QTableWidget, QTreeWidget, QListWidget {{
    background: {c.input};
    color: {c.text};
    border: 1px solid {c.border};
    border-radius: 5px;
    selection-background-color: {c.selection};
    selection-color: {c.text};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    min-height: 30px;
    padding: 0 8px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus, QTreeWidget:focus {{
    border: 1px solid {c.accent};
}}
QComboBox QAbstractItemView {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 4px;
    outline: 0;
    selection-background-color: {c.selection};
    selection-color: {c.text};
    padding: 3px;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 3px 8px;
}}
QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{
    background: {c.selection};
    color: {c.text};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    background: {c.surface_alt};
    color: {c.text_muted};
}}
QPlainTextEdit, QTextEdit {{
    padding: 8px;
    font-family: "Consolas";
    font-size: 12px;
}}
QPushButton, QToolButton[toolbarButton="true"] {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 5px;
    min-height: 30px;
    padding: 0 12px;
    font-weight: 600;
}}
QPushButton:hover, QToolButton[toolbarButton="true"]:hover {{
    background: {c.surface_alt};
    border-color: {c.accent};
}}
QPushButton:pressed, QToolButton[toolbarButton="true"]:pressed {{
    background: {c.selection};
}}
QPushButton:disabled, QToolButton[toolbarButton="true"]:disabled {{
    color: {c.text_muted};
    background: {c.surface_alt};
    border-color: {c.border};
}}
QPushButton[buttonRole="primary"] {{
    background: {c.accent};
    color: #ffffff;
    border-color: {c.accent};
}}
QPushButton[buttonRole="primary"]:hover {{
    background: {c.accent_hover};
    border-color: {c.accent_hover};
}}
QPushButton[buttonRole="danger"] {{
    color: {c.danger};
    border-color: {c.danger};
}}
QTabWidget::pane {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {c.text_muted};
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 9px 13px;
    min-width: 72px;
}}
QTabBar::tab:hover {{
    color: {c.text};
    background: {c.surface_alt};
}}
QTabBar::tab:selected {{
    color: {c.accent};
    border-bottom-color: {c.accent};
    font-weight: 700;
}}
QHeaderView::section {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 0;
    border-right: 1px solid {c.border};
    border-bottom: 1px solid {c.border};
    padding: 7px 8px;
    font-weight: 600;
}}
QTableWidget, QTreeWidget {{
    gridline-color: {c.border};
    alternate-background-color: {c.surface_alt};
}}
QTableWidget::item, QTreeWidget::item {{
    padding: 5px;
}}
QTableWidget::item:selected, QTreeWidget::item:selected {{
    background: {c.selection};
}}
QMenuBar {{
    background: {c.surface};
    color: {c.text};
    border-bottom: 1px solid {c.border};
}}
QMenuBar::item {{
    padding: 6px 10px;
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background: {c.selection};
}}
QMenu {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 24px 6px 10px;
}}
QStatusBar {{
    background: {c.surface};
    color: {c.text_muted};
    border-top: 1px solid {c.border};
}}
QSplitter::handle {{
    background: {c.border};
    width: 1px;
    height: 1px;
}}
QScrollArea {{
    background: {c.canvas};
    border: 0;
}}
QScrollArea QWidget#qt_scrollarea_viewport {{
    background: {c.canvas};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 11px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c.border_strong};
    min-height: 28px;
    border-radius: 4px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 11px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c.border_strong};
    min-width: 28px;
    border-radius: 4px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QCheckBox {{
    spacing: 7px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}
QToolTip {{
    background: {c.sidebar};
    color: {c.sidebar_text};
    border: 1px solid {c.border_strong};
    padding: 5px;
}}
"""
