"""Layered-device layer table and the selected layer's fields."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidgetItem

from g4usim_gui.editors.geometry_editor_model import LayerRow


class LayersMixin:
    """Layered-device layer table and the selected layer's fields. Mixed into ConfigBuilderPage."""

    def _populate_layers_table(self) -> None:
        self._building = True
        self.layer_table.setRowCount(0)
        for layer in self.geometry_document.layered_device.layers:
            row = self.layer_table.rowCount()
            self.layer_table.insertRow(row)
            values = [
                "yes" if layer.enabled else "no",
                layer.name,
                layer.material,
                layer.thickness,
                layer.xy,
                "yes" if layer.sensitive else "no",
                "yes" if layer.bias else "no",
                layer.region,
            ]
            for col, value in enumerate(values):
                self.layer_table.setItem(row, col, QTableWidgetItem(value))
        self.layer_table.resizeColumnsToContents()
        self._building = False
        if self.geometry_document.layered_device.layers:
            row = min(max(self._selected_layer_row, 0), len(self.geometry_document.layered_device.layers) - 1)
            self.layer_table.selectRow(row)
            self._select_layer_row(row)
        else:
            self._select_layer_row(-1)

    def _on_layer_selection_changed(self) -> None:
        if self._building:
            return
        self._select_layer_row(self.layer_table.currentRow())

    def _select_layer_row(self, row: int) -> None:
        self._building = True
        self._selected_layer_row = row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            self.layer_enabled.setChecked(False)
            self.layer_name.clear()
            self.layer_thickness.clear()
            self.layer_xy.clear()
            self.layer_region.clear()
            self.layer_copy_no.clear()
            self.layer_position.clear()
            self.layer_rotation.clear()
            self.layer_status.setPlainText("Select a layer to edit.")
            self._building = False
            return
        layer = layers[row]
        self.layer_enabled.setChecked(layer.enabled)
        self.layer_name.setText(layer.name)
        self._set_combo_text(self.layer_material, layer.material)
        self.layer_thickness.setText(layer.thickness)
        self.layer_xy.setText(layer.xy)
        self.layer_sensitive.setChecked(layer.sensitive)
        self.layer_bias.setChecked(layer.bias)
        self.layer_region.setText(layer.region)
        self.layer_copy_no.setText(layer.copy_no)
        self.layer_position.setText(layer.position)
        self.layer_rotation.setText(layer.rotation)
        self._building = False

    def _update_selected_layer_from_detail(self) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            return
        layer = layers[row]
        layer.enabled = self.layer_enabled.isChecked()
        layer.name = self.layer_name.text().strip()
        layer.material = self.layer_material.currentText().strip()
        layer.thickness = self.layer_thickness.text().strip()
        layer.xy = self.layer_xy.text().strip()
        layer.sensitive = self.layer_sensitive.isChecked()
        layer.bias = self.layer_bias.isChecked()
        layer.region = self.layer_region.text().strip()
        layer.copy_no = self.layer_copy_no.text().strip()
        layer.position = self.layer_position.text().strip()
        layer.rotation = self.layer_rotation.text().strip()
        self._populate_layers_table()
        if 0 <= row < self.layer_table.rowCount():
            self.layer_table.selectRow(row)

    def _add_layer(self) -> None:
        layer = LayerRow(name=f"Layer{len(self.geometry_document.layered_device.layers) + 1}", material="G4_Si", thickness="1 um", xy="10 mm, 10 mm")
        self.geometry_document.layered_device.layers.append(layer)
        self.geometry_document.is_dirty = True
        self._selected_layer_row = len(self.geometry_document.layered_device.layers) - 1
        self._populate_layers_table()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._emit_changed()

    def _duplicate_layer(self) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            return
        source = layers[row]
        duplicate = LayerRow(**source.__dict__.copy())
        duplicate.name = f"{source.name}_copy"
        layers.insert(row + 1, duplicate)
        self.geometry_document.is_dirty = True
        self._selected_layer_row = row + 1
        self._populate_layers_table()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._emit_changed()

    def _delete_layer(self) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        if row < 0 or row >= len(layers):
            return
        del layers[row]
        self.geometry_document.is_dirty = True
        self._selected_layer_row = min(row, len(layers) - 1)
        self._populate_layers_table()
        self._validate_geometry_editor()
        self._update_generated_geometry_preview()
        self._emit_changed()

    def _move_layer(self, direction: int) -> None:
        row = self._selected_layer_row
        layers = self.geometry_document.layered_device.layers
        target = row + direction
        if row < 0 or row >= len(layers) or target < 0 or target >= len(layers):
            return
        layers[row], layers[target] = layers[target], layers[row]
        self.geometry_document.is_dirty = True
        self._selected_layer_row = target
        self._populate_layers_table()
        self._update_generated_geometry_preview()
        self._emit_changed()
