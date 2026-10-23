"""Boolean operations table (hierarchical geometry)."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidgetItem

from g4usim_gui.editors.geometry_editor_model import BooleanOperationRow


class BooleansMixin:
    """Boolean operations table (hierarchical geometry). Mixed into ConfigBuilderPage."""

    def _on_boolean_table_changed(self, item: QTableWidgetItem) -> None:
        if self._building:
            return
        row = item.row()
        if row < 0 or row >= len(self.geometry_document.boolean_ops):
            return
        op = self.geometry_document.boolean_ops[row]
        values = [self._table_text(self.boolean_table, row, col) for col in range(self.boolean_table.columnCount())]
        op.enabled = self._as_bool(values[0])
        op.target_volume = values[1]
        try:
            op.index = int(values[2])
        except ValueError:
            op.index = row
        op.operation = values[3] or "subtraction"
        op.tool_shape = values[4] or "box"
        op.tool_size = values[5]
        op.tool_parameters = values[6]
        op.position = values[7]
        op.rotation = values[8]
        self._mark_geometry_dirty()

    def _add_boolean_op(self) -> None:
        target = self._first_non_world_volume_name()
        index = sum(1 for op in self.geometry_document.boolean_ops if op.target_volume == target)
        self.geometry_document.boolean_ops.append(
            BooleanOperationRow(
                target_volume=target,
                index=index,
                operation="subtraction",
                tool_shape="box",
                tool_size="1 mm,1 mm,1 mm",
                position="0 mm,0 mm,0 mm",
                rotation="0 deg,0 deg,0 deg",
                name=f"{target}_cut_{index}" if target else "",
            )
        )
        if self.geometry_document.mode == "hierarchical":
            self.geometry_document.mode = "hierarchical_boolean"
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    def _duplicate_boolean_op(self) -> None:
        row = self.boolean_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.boolean_ops):
            return
        source = self.geometry_document.boolean_ops[row]
        duplicate = BooleanOperationRow(**{k: v for k, v in source.__dict__.items() if k in BooleanOperationRow.__dataclass_fields__})
        duplicate.index = source.index + 1
        duplicate.name = f"{source.name}_copy" if source.name else ""
        duplicate.errors = []
        duplicate.warnings = []
        self.geometry_document.boolean_ops.insert(row + 1, duplicate)
        self._renumber_boolean_ops()
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.boolean_table.selectRow(row + 1)

    def _delete_boolean_op(self) -> None:
        row = self.boolean_table.currentRow()
        if row < 0 or row >= len(self.geometry_document.boolean_ops):
            return
        del self.geometry_document.boolean_ops[row]
        self._renumber_boolean_ops()
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()

    def _move_boolean_op(self, direction: int) -> None:
        row = self.boolean_table.currentRow()
        target = row + direction
        rows = self.geometry_document.boolean_ops
        if row < 0 or target < 0 or row >= len(rows) or target >= len(rows):
            return
        rows[row], rows[target] = rows[target], rows[row]
        self._renumber_boolean_ops()
        self._mark_geometry_dirty()
        self._populate_hierarchical_tables()
        self.boolean_table.selectRow(target)

    def _renumber_boolean_ops(self) -> None:
        counts: dict[str, int] = {}
        for op in self.geometry_document.boolean_ops:
            target = op.target_volume.strip()
            op.index = counts.get(target, 0)
            counts[target] = op.index + 1
