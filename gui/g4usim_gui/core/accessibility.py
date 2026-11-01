"""Presentation-only accessibility helpers; never collect or mutate business models."""
from __future__ import annotations

import re
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtWidgets import (
    QApplication, QAbstractButton, QAbstractItemView, QAbstractSpinBox, QComboBox,
    QDialog, QFormLayout, QGridLayout, QLabel, QLineEdit, QPlainTextEdit,
    QScrollArea, QTabBar, QTextEdit, QWidget, QWizard, QVBoxLayout, QFrame,
)
from g4usim_gui.core.i18n import ui_text

FIELDS = (QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit, QAbstractItemView)


def readable_label(text: str) -> str:
    return re.sub(r'<[^>]*>', '', text).replace('&&', '\0').replace('&', '').replace('\0', '&').strip().rstrip(':：')


def name_control(widget: QWidget, source: str) -> None:
    widget.setProperty('f8AccessibleSource', source)
    widget.setAccessibleName(ui_text(source))


def _item_field(item):
    if item is None:
        return None
    widget = item.widget()
    if isinstance(widget, FIELDS):
        return widget
    if widget is not None:
        candidates = widget.findChildren(QWidget)
        return next((child for child in candidates if isinstance(child, FIELDS)
                     and not isinstance(child.parentWidget(), (QComboBox, QAbstractSpinBox))), None)
    layout = item.layout()
    if layout is not None:
        return next((found for i in range(layout.count()) if (found := _item_field(layout.itemAt(i))) is not None), None)
    return None


def _buddy(label, field):
    if not isinstance(label, QLabel) or field is None or not readable_label(label.text()):
        return
    if label.buddy() is None:
        label.setBuddy(field)
    if not field.accessibleName() or getattr(field, '_f8_accessible_label', None) is label:
        field._f8_accessible_label = label
        field.setAccessibleName(readable_label(label.text()))


def decorate_accessibility(root: QWidget) -> None:
    """Bind actual form/grid labels, retaining existing explicit accessible names.

    Only same-row labels are used. No placeholder, current value, objectName or
    translated error text is guessed to be a field's identity.
    """
    widgets = [root, *root.findChildren(QWidget)]
    for parent in widgets:
        layout = parent.layout()
        layouts = [] if layout is None else [layout]
        while layouts:
            current = layouts.pop()
            if isinstance(current, QFormLayout):
                current.setRowWrapPolicy(QFormLayout.WrapLongRows)
                for row in range(current.rowCount()):
                    label_item = current.itemAt(row, QFormLayout.LabelRole)
                    label = label_item.widget() if label_item is not None else None
                    _buddy(label, _item_field(current.itemAt(row, QFormLayout.FieldRole)))
            elif isinstance(current, QGridLayout):
                for i in range(current.count()):
                    item = current.itemAt(i)
                    label = item.widget()
                    if not isinstance(label, QLabel):
                        continue
                    row, column, row_span, column_span = current.getItemPosition(i)
                    if row_span == 1:
                        _buddy(label, _item_field(current.itemAtPosition(row, column + column_span)))
            for i in range(current.count()):
                child = current.itemAt(i).layout()
                if child is not None:
                    layouts.append(child)
        source = parent.property('f8AccessibleSource')
        if source:
            parent.setAccessibleName(ui_text(str(source)))
        label = getattr(parent, '_f8_accessible_label', None)
        if label is not None:
            parent.setAccessibleName(readable_label(label.text()))
        if not source and isinstance(parent, QAbstractButton) and (not parent.accessibleName() or parent.property('f8ButtonName')):
            parent.setProperty('f8ButtonName', True)
            parent.setAccessibleName(readable_label(parent.text()) or readable_label(parent.toolTip()))
        # Let Tab leave multiline text; an actual tab can still be pasted.
        if isinstance(parent, (QPlainTextEdit, QTextEdit)):
            parent.setTabChangesFocus(True)


def _focus_control(widget: QWidget | None) -> QWidget | None:
    """Resolve actual editor controls, never a scroll area/viewport/container."""
    if widget is None:
        return None
    parent = widget.parentWidget()
    if isinstance(parent, (QComboBox, QAbstractSpinBox)):
        widget = parent
    if isinstance(widget, (*FIELDS, QAbstractButton, QTabBar)):
        return widget
    return None


def focus_first(root: QWidget) -> QWidget | None:
    current = _focus_control(root.focusWidget())
    if (current is not None and (current is root or root.isAncestorOf(current))
            and current.isVisible() and current.isEnabled() and current.focusPolicy() & Qt.TabFocus):
        current.setFocus(Qt.ShortcutFocusReason)
        ensure_focus_visible(current)
        return current
    candidate = root
    seen = set()
    while candidate not in seen:
        seen.add(candidate)
        control = _focus_control(candidate)
        if (control is not None and (control is root or root.isAncestorOf(control))
                and control.isVisible() and control.isEnabled() and control.focusPolicy() & Qt.TabFocus):
            control.setFocus(Qt.ShortcutFocusReason)
            ensure_focus_visible(control)
            return control
        candidate = candidate.nextInFocusChain()
    return None


def _reading_anchor(control: QWidget, viewport: QWidget) -> QRect:
    """Prefer the full label/control union; use a reading anchor only if it cannot fit."""
    full = QRect(control.mapTo(viewport, QPoint(0, 0)), control.size())
    label = getattr(control, '_f8_accessible_label', None)
    label_rect = None
    if label is not None and label.isVisible() and label.window() is control.window():
        label_rect = QRect(label.mapTo(viewport, QPoint(0, 0)), label.size())
    union = full.united(label_rect) if label_rect is not None else full
    if union.width() <= viewport.width() and union.height() <= viewport.height():
        return union

    # An oversized table/text area has a meaningful cell/cursor, not its huge frame.
    reading = QRect(full)
    if isinstance(control, QAbstractItemView):
        cell = control.visualRect(control.currentIndex())
        local = cell if cell.isValid() else QRect(0, 0, 96, 32)
        reading = QRect(control.viewport().mapTo(viewport, local.topLeft()), local.size())
    elif isinstance(control, (QPlainTextEdit, QTextEdit)):
        local = control.cursorRect().adjusted(0, 0, 80, 0)
        reading = QRect(control.viewport().mapTo(viewport, local.topLeft()), local.size())
    elif isinstance(control, QTabBar) and control.currentIndex() >= 0:
        local = control.tabRect(control.currentIndex())
        reading = QRect(control.mapTo(viewport, local.topLeft()), local.size())
    elif union.width() > viewport.width():
        reading.setWidth(min(reading.width(), 128))

    contextual = reading.united(label_rect) if label_rect is not None else reading
    # Keep full dimensions on each axis that can fit, independently. A tall text
    # area must not force a horizontally fitting field/label to become clipped.
    if union.width() <= viewport.width():
        left, width = union.left(), union.width()
    else:
        left, width = contextual.left(), min(contextual.width(), max(1, viewport.width() - 24))
    if union.height() <= viewport.height():
        top, height = union.top(), union.height()
    elif contextual.height() <= viewport.height():
        top, height = contextual.top(), contextual.height()
    else:
        top, height = reading.top(), min(reading.height(), max(1, viewport.height() - 24))
    return QRect(left, top, width, height)


def _reveal_axis(bar, low: int, high: int, extent: int) -> None:
    # Exact smallest delta: a 5px overflow moves 5px, never an extra margin.
    if low < 0:
        bar.setValue(bar.value() + low)
    elif high >= extent:
        bar.setValue(bar.value() + high - extent + 1)


def ensure_focus_visible(widget: QWidget) -> None:
    """Reveal only meaningful control/label anchors with minimal scrolling."""
    control = _focus_control(widget)
    if control is None:
        return
    parent = control.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea) and parent.widget() is not None and parent.widget().isAncestorOf(control):
            viewport = parent.viewport()
            anchor = _reading_anchor(control, viewport)
            _reveal_axis(parent.horizontalScrollBar(), anchor.left(), anchor.right(), viewport.width())
            _reveal_axis(parent.verticalScrollBar(), anchor.top(), anchor.bottom(), viewport.height())
        parent = parent.parentWidget()


def translate_wizard_buttons(wizard: QWizard) -> None:
    roles = ((QWizard.NextButton, 'Next'), (QWizard.BackButton, 'Back'),
             (QWizard.FinishButton, 'Finish'), (QWizard.CancelButton, 'Cancel'))
    # Setting a role's text can rebuild Qt's button layout. Name the final set
    # only after all roles have their translated labels.
    for role, source in roles:
        wizard.setButtonText(role, ui_text(source))
    for role, source in roles:
        button = wizard.button(role)
        if button is not None:
            name_control(button, source)
    if not wizard.property('f8WizardButtonsConnected'):
        wizard.setProperty('f8WizardButtonsConnected', True)
        wizard.currentIdChanged.connect(lambda _page: translate_wizard_buttons(wizard))


def scroll_wizard_pages(wizard: QWizard) -> None:
    """Keep wizard buttons outside scrollable page bodies; keep original fields/layouts."""
    for page_id in wizard.pageIds():
        page = wizard.page(page_id)
        layout = page.layout()
        if layout is None or page.property('f8PageScroll'):
            continue
        # RunPage already owns a scroll viewport. Never wrap it a second time.
        if layout.count() == 1 and isinstance(layout.itemAt(0).widget(), QScrollArea):
            continue
        content = QWidget()
        content.setLayout(layout)
        scroll = QScrollArea(page)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setObjectName('f8WizardPageScroll')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        page.setProperty('f8PageScroll', True)


def owned_widget(owner: QWidget, widget: QWidget) -> bool:
    # QWidget.isAncestorOf stops at dialog/window boundaries; QObject ownership
    # still links I2 -> I1 -> MainWindow, including floating docks.
    current = widget.parentWidget()
    while current is not None:
        if current is owner:
            return True
        current = current.parentWidget()
    return False


class AccessibilityController(QObject):
    """One per main window: decorate owned dialogs and reveal keyboard focus."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        QApplication.instance().installEventFilter(self)
        self.refresh()

    def refresh(self):
        for wizard in self.owner.findChildren(QWizard):
            translate_wizard_buttons(wizard)
        decorate_accessibility(self.owner)

    def close(self):
        QApplication.instance().removeEventFilter(self)

    def eventFilter(self, watched, event):  # noqa: N802
        if not isinstance(watched, QWidget) or not owned_widget(self.owner, watched):
            return False
        content_scroll = getattr(self.owner, 'content_scroll', None)
        if event.type() == QEvent.Resize and content_scroll is not None and watched is content_scroll.viewport():
            self.owner.start_page.adapt_to_width(watched.width())
        if event.type() == QEvent.FocusIn:
            ensure_focus_visible(watched)
        elif event.type() == QEvent.Show and isinstance(watched, QDialog):
            if isinstance(watched, QWizard):
                scroll_wizard_pages(watched)
                translate_wizard_buttons(watched)
            decorate_accessibility(watched)
            screen = watched.screen()
            if screen is not None:
                available = screen.availableGeometry()
                watched.resize(min(watched.width(), max(480, available.width() - 48)),
                               min(watched.height(), max(360, available.height() - 64)))
        return False
