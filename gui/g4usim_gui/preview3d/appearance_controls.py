"""Transient display overrides. This widget has no project or backend references."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QComboBox, QPushButton, QDoubleSpinBox,
                              QLabel, QColorDialog)

from g4usim_gui.core.i18n import ui_text
from g4usim_gui.widgets.qt_data import combo_data
from g4usim_gui.preview3d.view_model import ViewState


class AppearanceControls(QWidget):
    changed = Signal()

    def __init__(self, state: ViewState, parent=None):
        super().__init__(parent)
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.scope = QComboBox()
        self.scope.addItem("", "volume")
        self.scope.addItem("", "material")
        self.target = QComboBox()
        self.target.setMinimumContentsLength(12)
        self.colour = QPushButton()
        self.opacity_label = QLabel()
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setDecimals(1)
        self.opacity.setSuffix(" %")
        self.opacity.setStyleSheet("QDoubleSpinBox { min-height: 30px; padding: 0 4px; } "
                                  "QDoubleSpinBox QLineEdit { padding: 0; border: 0; min-height: 0; }")
        self.reset = QPushButton()
        self.reset_all = QPushButton()
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setProperty("uiRole", "hint")
        for control in (self.title, self.scope, self.target, self.colour, self.opacity_label,
                        self.opacity, self.reset, self.reset_all, self.hint):
            layout.addWidget(control)
        self.scope.currentIndexChanged.connect(self.refresh_targets)
        self.target.currentIndexChanged.connect(self.refresh_value)
        self.colour.clicked.connect(self.choose_colour)
        self.opacity.valueChanged.connect(self.set_opacity)
        self.reset.clicked.connect(self.reset_target)
        self.reset_all.clicked.connect(self.reset_everything)
        self.refresh_language()
        self.refresh_targets()

    def refresh_language(self):
        self.title.setText(ui_text("3D appearance"))
        self.scope.setItemText(0, ui_text("Volume copy"))
        self.scope.setItemText(1, ui_text("Material"))
        self.opacity_label.setText(ui_text("Opacity"))
        self.reset.setText(ui_text("Reset target appearance"))
        self.reset_all.setText(ui_text("Reset all appearance"))
        self.hint.setText(ui_text("View only; not saved to the project. Explicit opacity overrides selection and track fading."))
        self.refresh_value()

    def refresh_targets(self):
        old = combo_data(self.target)
        self.target.blockSignals(True)
        self.target.clear()
        if combo_data(self.scope) == "volume":
            for item in self.state.items:
                self.target.addItem(item.key, item.key)
        else:
            for material in sorted({item.material for item in self.state.items}):
                self.target.addItem(material or "?", material)
        index = self.target.findData(old)
        if index >= 0:
            self.target.setCurrentIndex(index)
        self.target.blockSignals(False)
        self.refresh_value()

    def refresh_value(self):
        target = combo_data(self.target)
        scope = combo_data(self.scope)
        item = next((i for i in self.state.items if (i.key if scope == "volume" else i.material) == target), None)
        enabled = item is not None
        for control in (self.colour, self.opacity, self.reset):
            control.setEnabled(enabled)
        self.reset_all.setEnabled(bool(self.state.volume_appearance or self.state.material_appearance))
        if item and scope == "material":
            # A single copy override must not masquerade as a material preference.
            material_view = ViewState(items=self.state.items, material_appearance=self.state.material_appearance)
            display_style = material_view.style(item)
        else:
            display_style = self.state.style(item) if item else {"colour": None, "opacity": 0.6}
        colour = display_style["colour"]
        self.colour.setText(ui_text("Choose colour") + (f"  {colour}" if colour else ""))
        self.opacity.blockSignals(True)
        # Material editing reads its own preference, independent of a particular copy override.
        explicit = self.state.material_appearance.get(target, {}) if scope == "material" else {}
        opacity = explicit.get("opacity", display_style["opacity"])
        self.opacity.setValue(opacity * 100)
        self.opacity.blockSignals(False)

    def choose_colour(self):
        colour = QColorDialog.getColor(parent=self, title=ui_text("Choose colour"))
        if colour.isValid():
            self.state.set_appearance(combo_data(self.scope), combo_data(self.target), colour=colour.name())
            self._updated()

    def set_opacity(self, percent):
        if self.target.currentIndex() >= 0:
            self.state.set_appearance(combo_data(self.scope), combo_data(self.target), opacity=percent / 100)
            self._updated()

    def reset_target(self):
        self.state.reset_appearance(combo_data(self.scope), combo_data(self.target))
        self._updated()

    def reset_everything(self):
        self.state.reset_appearance()
        self._updated()

    def _updated(self):
        self.refresh_value()
        self.changed.emit()
