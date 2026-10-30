from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
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
    canvas="#f3f5f7",
    surface="#ffffff",
    surface_alt="#f5f7f9",
    input="#ffffff",
    text="#18212a",
    text_muted="#5f6d76",
    border="#e1e6ea",
    border_strong="#c7d0d6",
    accent="#1d7a6c",
    accent_hover="#16645a",
    accent_soft="#e2f1ed",
    selection="#d5ebe5",
    success="#2b7b55",
    warning="#a5640f",
    danger="#b3363f",
    sidebar="#0f171c",
    sidebar_hover="#19242a",
    sidebar_selected="#1f3237",
    sidebar_text="#eef3f4",
    sidebar_muted="#90a1a8",
)


DARK = ThemeColors(
    canvas="#0e1316",
    surface="#151c20",
    surface_alt="#1a2328",
    input="#11181b",
    text="#e7edef",
    text_muted="#9caeb5",
    border="#243036",
    border_strong="#354349",
    accent="#4cb3a1",
    accent_hover="#66c6b5",
    accent_soft="#1e3a36",
    selection="#2a4a45",
    success="#62bb88",
    warning="#e0a04a",
    danger="#ee7178",
    sidebar="#090e10",
    sidebar_hover="#141c20",
    sidebar_selected="#1d3034",
    sidebar_text="#eef3f4",
    sidebar_muted="#8b9da4",
)


def current_colors(app: QApplication | None = None) -> ThemeColors:
    """Colours of the theme currently applied to the application."""
    app = app or QApplication.instance()
    return DARK if app is not None and app.property("resolvedTheme") == "dark" else LIGHT


def on_accent(c: ThemeColors) -> str:
    """Text colour on an accent-filled control: white on a dark accent, near-black on a light one."""
    red, green, blue = (int(c.accent[i:i + 2], 16) / 255 for i in (1, 3, 5))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#ffffff" if luminance < 0.45 else "#0b1214"


def resolve_theme(app: QApplication, mode: ThemeMode) -> Literal["light", "dark"]:
    if mode != "system":
        return mode
    scheme = app.styleHints().colorScheme()
    if scheme != Qt.ColorScheme.Unknown:
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    # the application palette is ours once a theme is applied: ask the style for the system one
    window_color = app.style().standardPalette().color(QPalette.Window)
    return "dark" if window_color.lightness() < 128 else "light"


def apply_theme(app: QApplication, mode: ThemeMode) -> Literal["light", "dark"]:
    resolved = resolve_theme(app, mode)
    colors = DARK if resolved == "dark" else LIGHT
    font = app.font()   # Latin text in Segoe UI, Chinese in Microsoft YaHei UI (other systems: their defaults)
    font.setFamilies(list(dict.fromkeys(["Segoe UI", "Microsoft YaHei UI", *font.families()])))
    app.setFont(font)
    app.setPalette(build_palette(colors))   # what the style draws itself: check boxes, arrows, popups
    app.setStyleSheet(build_stylesheet(colors))
    app.setProperty("themeMode", mode)
    app.setProperty("resolvedTheme", resolved)
    return resolved


def build_palette(c: ThemeColors) -> QPalette:
    palette = QPalette()
    for role, color in ((QPalette.Window, c.canvas), (QPalette.WindowText, c.text), (QPalette.Base, c.input),
                        (QPalette.AlternateBase, c.surface_alt), (QPalette.Text, c.text),
                        (QPalette.Button, c.surface), (QPalette.ButtonText, c.text),
                        (QPalette.Highlight, c.accent), (QPalette.HighlightedText, on_accent(c)),
                        (QPalette.ToolTipBase, c.sidebar), (QPalette.ToolTipText, c.sidebar_text),
                        (QPalette.PlaceholderText, c.text_muted), (QPalette.Link, c.accent),
                        (QPalette.Mid, c.border_strong), (QPalette.Dark, c.border_strong), (QPalette.Light, c.surface)):
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(c.text_muted))
    return palette


def _svg_url(name: str, color: str) -> str:
    """A line icon as an SVG file for style sheet image: urls (cached in the temp folder)."""
    from g4usim_gui.core import icons   # noqa: PLC0415 - keeps this module free of QtSvg at import
    path = Path(tempfile.gettempdir()) / "g4usim_gui_icons" / f"{name}_{color.lstrip('#')}.svg"
    try:
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(icons.svg(name, color), encoding="utf-8")
    except OSError:
        return ""
    return path.as_posix()


def build_stylesheet(c: ThemeColors) -> str:
    down, up = _svg_url("chevron_down", c.text_muted), _svg_url("chevron_up", c.text_muted)
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
QWidget#sidebar QLabel {{
    background: transparent;
}}
QLabel#brandMark {{
    color: {c.sidebar_text};
    font-size: 16px;
    font-weight: 600;
}}
QLabel#brandCaption, QLabel#sidebarSection, QLabel#sidebarFooter {{
    color: {c.sidebar_muted};
}}
QLabel#brandCaption {{
    font-size: 11px;
}}
QLabel#sidebarSection {{
    font-size: 10px;
    font-weight: 700;
}}
QLabel#sidebarFooter {{
    font-size: 11px;
}}
QToolButton[navButton="true"] {{
    background: transparent;
    color: {c.sidebar_muted};
    border: 0;
    border-radius: 8px;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}}
QToolButton[navButton="true"]:hover {{
    background: {c.sidebar_hover};
    color: {c.sidebar_text};
}}
QToolButton[navButton="true"]:checked {{
    background: {c.sidebar_selected};
    color: {c.sidebar_text};
    font-weight: 600;
}}
QFrame#pageHeader {{
    background: {c.surface};
    border-bottom: 1px solid {c.border};
}}
QLabel#pageTitle {{
    font-size: 18px;
    font-weight: 600;
    color: {c.text};
}}
QLabel#pageSubtitle, QLabel[uiRole="hint"] {{
    color: {c.text_muted};
}}
QLabel[uiRole="sectionTitle"] {{
    color: {c.text};
    font-size: 14px;
    font-weight: 600;
}}
QLabel[uiRole="emptyState"] {{
    color: {c.text_muted};
    padding: 12px;
}}
QLabel[uiRole="contextChip"] {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 1px solid {c.border};
    border-radius: 12px;
    padding: 3px 11px;
}}
QLabel[uiRole="statusChip"] {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 1px solid {c.border};
    border-radius: 12px;
    padding: 3px 11px;
    font-weight: 600;
}}
QLabel[uiRole="statusChip"][statusRole="running"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border-color: {c.accent};
}}
QLabel[uiRole="statusChip"][statusRole="success"] {{
    color: {c.success};
    border-color: {c.success};
}}
QLabel[uiRole="statusChip"][statusRole="failed"] {{
    color: {c.danger};
    border-color: {c.danger};
}}
QLabel[uiRole="contextChip"][statusRole="running"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border-color: {c.accent};
    font-weight: 600;
}}
QToolButton[iconButton="true"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px;
}}
QToolButton[iconButton="true"]:hover {{
    background: {c.surface_alt};
    border-color: {c.border};
}}
QToolButton[iconButton="true"]:checked {{
    background: {c.accent_soft};
    border-color: {c.accent};
}}
QToolButton[iconButton="true"]::menu-indicator {{
    image: none;
    width: 0;
}}
QFrame[uiRole="card"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 10px;
}}
QFrame[uiRole="card"]:hover {{
    border-color: {c.accent};
}}
QFrame[uiRole="card"] QLabel {{
    background: transparent;
    border: 0;
}}
QFrame[uiRole="hero"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 12px;
}}
QFrame[uiRole="hero"] QLabel {{
    background: transparent;
}}
QLabel[uiRole="heroTitle"] {{
    font-size: 22px;
    font-weight: 600;
}}
QLabel[uiRole="cardTitle"] {{
    font-size: 14px;
    font-weight: 600;
}}
QFrame[uiRole="card"] QLabel[uiRole="tag"], QLabel[uiRole="tag"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QFrame[uiRole="card"] QLabel[uiRole="thumbnail"], QLabel[uiRole="thumbnail"] {{
    background: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 8px;
}}
QGroupBox {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 10px;
    margin-top: 18px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox[uiRole="panel"] {{
    margin-top: 0;
    padding: 10px 12px;
}}
QToolButton[sectionToggle="true"] {{
    background: transparent;
    border: 0;
    color: {c.text};
    font-size: 13px;
    font-weight: 600;
    padding: 6px 2px 2px 0;
}}
QToolButton[sectionToggle="true"]:hover {{
    color: {c.accent};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: {c.text};
}}
QScrollArea#editorScroll, QScrollArea#editorScroll > QWidget#qt_scrollarea_viewport,
QScrollArea#sourceEditorScroll,
QScrollArea#sourceEditorScroll > QWidget > QWidget#sourceEditorContent {{
    background: {c.surface};
    border: 0;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QTableWidget, QTreeWidget, QListWidget {{
    background: {c.input};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 6px;
    selection-background-color: {c.selection};
    selection-color: {c.text};
}}
QTableWidget, QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit {{
    border-color: {c.border};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    min-height: 30px;
    padding: 0 8px;
}}
QComboBox::drop-down {{
    border: 0;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: url("{down}");
    width: 14px;
    height: 14px;
}}
QAbstractSpinBox::up-arrow {{
    image: url("{up}");
    width: 12px;
    height: 12px;
}}
QAbstractSpinBox::down-arrow {{
    image: url("{down}");
    width: 12px;
    height: 12px;
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    border: 0;
    background: transparent;
    width: 18px;
}}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: {c.surface_alt};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus, QTreeWidget:focus {{
    border: 1px solid {c.accent};
}}
QWidget[diagnosticFocus="true"] {{
    border: 2px solid {c.accent};
}}
QComboBox QAbstractItemView {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 6px;
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
    font-family: "Cascadia Mono", "Consolas";
    font-size: 12px;
}}
QPushButton, QToolButton[toolbarButton="true"] {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 6px;
    min-height: 30px;
    padding: 0 14px;
    font-weight: 500;
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
    color: {on_accent(c)};
    border-color: {c.accent};
    font-weight: 600;
}}
QPushButton[buttonRole="primary"]:hover {{
    background: {c.accent_hover};
    border-color: {c.accent_hover};
}}
QPushButton[buttonRole="primary"]:disabled {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border-color: {c.border};
}}
QPushButton[buttonRole="danger"] {{
    color: {c.danger};
    border-color: {c.danger};
}}
QPushButton[buttonRole="link"] {{
    background: transparent;
    border: 0;
    color: {c.accent};
    padding: 0 4px;
    text-align: left;
}}
QPushButton[buttonRole="link"]:hover {{
    color: {c.accent_hover};
    text-decoration: underline;
}}
QTabWidget::pane {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {c.text_muted};
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 8px 12px;
}}
QTabBar::tab:hover {{
    color: {c.text};
}}
QTabBar::tab:selected {{
    color: {c.accent};
    border-bottom-color: {c.accent};
    font-weight: 600;
}}
QTabBar QToolButton {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 4px;
}}
QHeaderView, QTableCornerButton::section {{
    background: {c.surface_alt};
    border: 0;
}}
QHeaderView::section {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 0;
    border-right: 1px solid {c.border};
    border-bottom: 1px solid {c.border};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableWidget, QTreeWidget {{
    gridline-color: {c.border};
    alternate-background-color: {c.surface_alt};
}}
QTableWidget::item, QTreeWidget::item {{
    padding: 4px;
}}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {c.selection};
    color: {c.text};
}}
QListWidget::item {{
    padding: 4px;
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
    border-radius: 6px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 24px 6px 10px;
    border-radius: 4px;
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
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c.border_strong};
    min-height: 28px;
    border-radius: 3px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c.border_strong};
    min-width: 28px;
    border-radius: 3px;
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
