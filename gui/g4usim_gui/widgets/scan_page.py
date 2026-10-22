"""Parameter scans and batch runs page (roadmap C3).

Creates a scan from the current Configuration page (one setting over a list of
values, one ordinary run package per point), runs the points one after another with
the normal runner, and shows a results table and a plot of a chosen scorer quantity
(with its statistical error) against the scanned value. Scans are reopened from
their scan.json manifest.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core import scan
from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.scan_runner import ScanRunner
from g4usim_gui.core.theme import current_colors
from g4usim_gui.widgets.plot_panel import draw_empty, style_axes

# (base, runs root, executable, workspace root) for the current configuration; raises ValueError
BaseProvider = Callable[[], tuple[scan.ScanBase, str, str, str]]


class ScanPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._provider: BaseProvider | None = None
        self._base: scan.ScanBase | None = None
        self._parameters: list[scan.ScanParameter] = []
        self._manifest: scan.ScanManifest | None = None
        self._results: list[scan.PointResult] = []
        self._executable = ""
        self._workspace = ""
        self._runs_root = ""
        self.runner = ScanRunner(self)

        self.parameter = QComboBox()
        self.refresh_button = QPushButton("Use current configuration")
        self.values = QLineEdit()
        self.values.setPlaceholderText(ui_text("e.g. 50, 100, 150 MeV   or   lin(10, 200, 5) MeV   or   log(1, 1000, 4) MeV"))
        self.name = QLineEdit("scan")
        self.create_button = QPushButton("Create scan")
        self.open_button = QPushButton("Open scan...")
        self.run_button = QPushButton("Run pending points")
        self.rerun_button = QPushButton("Run all points")
        self.stop_button = QPushButton("Stop scan")
        self.status = QLabel("Create a scan from the Configuration page or open a saved scan.")
        self.status.setWordWrap(True)
        # not "metric": that name would shadow QPaintDevice.metric() and crash painting
        self.quantity = QComboBox()
        self.per_primary = QCheckBox("Per primary")
        self.export_button = QPushButton("Export results...")
        self.table = QTableWidget(0, 6)
        self.table.verticalHeader().setVisible(False)   # the Point column numbers the rows
        self._set_headers()
        self.figure = Figure(figsize=(6, 3.6), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        setup = QGroupBox("Scan setup")
        form = QFormLayout(setup)
        row = QHBoxLayout()
        row.addWidget(self.parameter, 1)
        row.addWidget(self.refresh_button)
        form.addRow(QLabel("Parameter"), row)
        form.addRow(QLabel("Values"), self.values)
        form.addRow(QLabel("Scan name"), self.name)
        buttons = QHBoxLayout()
        for button in (self.create_button, self.open_button, self.run_button, self.rerun_button, self.stop_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        form.addRow(buttons)
        results_row = QHBoxLayout()
        results_row.addWidget(QLabel("Quantity"))
        results_row.addWidget(self.quantity, 1)
        results_row.addWidget(self.per_primary)
        results_row.addWidget(self.export_button)
        lower = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.table, 2)
        left_layout.addWidget(self.log, 1)
        lower.addWidget(left)
        lower.addWidget(self.canvas)
        lower.setSizes([520, 620])
        layout = QVBoxLayout(self)
        layout.addWidget(setup)
        layout.addWidget(self.status)
        layout.addLayout(results_row)
        layout.addWidget(lower, 1)

        self.refresh_button.clicked.connect(self.refresh_base)
        self.create_button.clicked.connect(lambda: self.create_scan())
        self.open_button.clicked.connect(self._choose_scan)
        self.run_button.clicked.connect(lambda: self.run_scan(all_points=False))
        self.rerun_button.clicked.connect(lambda: self.run_scan(all_points=True))
        self.stop_button.clicked.connect(self.runner.stop)
        self.quantity.currentIndexChanged.connect(self._show_results)
        self.per_primary.toggled.connect(self._show_results)
        self.export_button.clicked.connect(self._choose_export)
        self.runner.pointStarted.connect(self._on_point_started)
        self.runner.pointFinished.connect(self._on_point_finished)
        self.runner.allFinished.connect(self._on_all_finished)
        self.runner.logLine.connect(self.log.appendPlainText)
        self._update_buttons()

    # --- API used by the main window and the smoke tests ------------------------------

    def _set_headers(self) -> None:
        self.table.setHorizontalHeaderLabels([ui_text(text) for text in
                                              ("Point", "Value", "State", "Events", "Quantity", "Rel. error")])

    def refresh_theme(self) -> None:
        self._draw()

    def refresh_language(self) -> None:
        self._set_headers()
        self._show_results()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt override
        # load the scannable settings the first time the page is shown
        if self._base is None and self._provider is not None:
            self.refresh_base()
        super().showEvent(event)

    def set_base_provider(self, provider: BaseProvider) -> None:
        self._provider = provider

    def refresh_base(self) -> bool:
        if self._provider is None:
            return False
        try:
            self._base, self._runs_root, self._executable, self._workspace = self._provider()
        except ValueError as error:
            self._base = None
            self.status.setText(ui_format("Cannot use the current configuration: {error}", error=error))
            self._update_buttons()
            return False
        current = self.parameter.currentData()
        self._parameters = scan.parameters(self._base)
        self.parameter.clear()
        for parameter in self._parameters:
            self.parameter.addItem(f"{parameter.label}  ({parameter.key})", parameter.key)
        index = self.parameter.findData(current)
        self.parameter.setCurrentIndex(max(index, 0))
        self.status.setText(ui_format("Base: run {name}, {events} events per point, {threads} threads.",
                                      name=self._base.run.run_name, events=self._base.run.beam_on,
                                      threads=self._base.run.threads))
        self._update_buttons()
        return True

    def select_parameter(self, key: str) -> bool:
        index = self.parameter.findData(key)
        if index >= 0:
            self.parameter.setCurrentIndex(index)
        return index >= 0

    def create_scan(self) -> bool:
        if self._base is None and not self.refresh_base():
            return False
        parameter = next((p for p in self._parameters if p.key == self.parameter.currentData()), None)
        if parameter is None:
            self.status.setText(ui_text("Choose a parameter to scan."))
            return False
        try:
            values = scan.expand_values(self.values.text())
            manifest = scan.create_scan(self._base, parameter, values, self.name.text().strip() or "scan",
                                        self._runs_root)
        except (ValueError, OSError) as error:
            self.status.setText(ui_format("Scan not created: {error}", error=error))
            return False
        self.load_scan(manifest)
        self.status.setText(ui_format("Created {count} run packages in {path}.", count=len(manifest.points),
                                      path=manifest.scan_dir))
        return True

    def load_scan(self, manifest: scan.ScanManifest | str | Path) -> None:
        if not isinstance(manifest, scan.ScanManifest):
            manifest = scan.load_manifest(manifest)
        self._manifest = manifest
        self.refresh_results()
        if self.is_read_only():
            self.status.setText(ui_format("Showing the results of {path}; its run packages are not there, so "
                                          "create a new scan to run it again.", path=manifest.scan_dir))

    def manifest(self) -> scan.ScanManifest | None:
        return self._manifest

    def results(self) -> list[scan.PointResult]:
        return list(self._results)

    def run_scan(self, *, all_points: bool) -> bool:
        if self._manifest is None or self.runner.is_running():
            return False
        if not self._executable and self._provider is not None:
            self.refresh_base()
        points = [r.index for r in self._results if all_points or r.state != "success"]
        if not points:
            self.status.setText(ui_text("Every point already completed successfully."))
            return False
        started = self.runner.start(self._manifest, self._executable, self._workspace, points)
        self._update_buttons()
        return started

    def refresh_results(self) -> None:
        self._results = scan.collect(self._manifest) if self._manifest else []
        current = self.quantity.currentData()
        self.quantity.blockSignals(True)
        self.quantity.clear()
        for key in scan.metric_keys(self._results):
            self.quantity.addItem(f"{key[0]} / {key[1]}  {key[2]}", "|".join(key))
        index = self.quantity.findData(current)
        self.quantity.setCurrentIndex(index if index >= 0 else 0)
        self.quantity.blockSignals(False)
        self._show_results()

    def select_quantity(self, scorer: str, quantity: str) -> bool:
        """Plot the first metric of that scorer and quantity (e.g. edep / raw_edep)."""
        for index in range(self.quantity.count()):
            key = str(self.quantity.itemData(index)).split("|")
            if key[:2] == [scorer, quantity]:
                self.quantity.setCurrentIndex(index)
                return True
        return False

    def is_read_only(self) -> bool:
        """A scan whose run packages are not there (bundled example results) can be viewed, not run."""
        return self._manifest is not None and any(not point.main_ini or not Path(point.main_ini).is_file()
                                                  for point in self._manifest.points)

    def current_metric(self) -> tuple[str, str, str] | None:
        data = self.quantity.currentData()
        return tuple(data.split("|")) if data else None

    def plotted(self) -> tuple[list[float], list[float], list[float]]:
        """x, y, y error of the current plot (points with the quantity only)."""
        metric = self.current_metric()
        xs, ys, es = [], [], []
        numeric = all(scan.numeric_value(r.value) is not None for r in self._results)
        for position, result in enumerate(self._results):
            value = result.metrics.get(metric) if metric else None
            if value is None:
                continue
            scale = 1.0
            if self.per_primary.isChecked():
                if not result.completed_events:
                    continue
                scale = 1.0 / result.completed_events
            xs.append(scan.numeric_value(result.value) if numeric else float(position))
            ys.append(value[0] * scale)
            es.append(abs(value[0]) * value[1] * scale)
        return xs, ys, es

    def export_results(self, path: str) -> None:
        if self._manifest is not None:
            scan.write_results_csv(self._manifest, self._results, path, self.current_metric())

    # --- view ----------------------------------------------------------------------------

    def _show_results(self) -> None:
        metric = self.current_metric()
        self.table.setRowCount(len(self._results))
        for row, result in enumerate(self._results):
            value = result.metrics.get(metric) if metric else None
            cells = [str(result.index), result.value, ui_text(result.state),
                     "" if result.completed_events is None else str(result.completed_events),
                     "" if value is None else f"{value[0]:.6g} {value[2]}",
                     "" if value is None else f"{value[1]:.3g}"]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column == 2 and result.reason:
                    item.setToolTip(result.reason)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self._draw()
        self._update_buttons()

    def _draw(self) -> None:
        colors = current_colors()
        metric = self.current_metric()
        xs, ys, es = self.plotted()
        if not (metric and xs):
            draw_empty(self.figure, colors, ui_text("No scan results yet: create or open a scan and run its points.")
                       if self._manifest is None or not self._results else
                       ui_text("No point has this quantity yet."))
            self.canvas.draw_idle()
            return
        self.figure.clear()
        axes = self.figure.add_subplot(1, 1, 1)
        style_axes(self.figure, axes, colors)
        if metric and xs:
            axes.errorbar(xs, ys, yerr=es, fmt="o-", capsize=3, color=colors.accent)
            numeric = all(scan.numeric_value(r.value) is not None for r in self._results)
            if not numeric:
                axes.set_xticks(xs)
                axes.set_xticklabels([self._results[int(x)].value for x in xs], rotation=30, ha="right")
            unit = next((r.metrics[metric][2] for r in self._results if metric in r.metrics), "")
            label = f"{metric[0]} / {metric[1]} [{unit}{' / primary' if self.per_primary.isChecked() else ''}]"
            axes.set_ylabel(label, color=colors.text)
            axes.set_xlabel(self._manifest.parameter if self._manifest else "", color=colors.text)
            axes.set_title(metric[2], color=colors.text, fontsize=9, loc="left")
        self.canvas.draw_idle()

    def _update_buttons(self) -> None:
        running = self.runner.is_running()
        self.create_button.setEnabled(not running)
        self.open_button.setEnabled(not running)
        runnable = self._manifest is not None and not running and not self.is_read_only()
        self.run_button.setEnabled(runnable)
        self.rerun_button.setEnabled(runnable)
        self.stop_button.setEnabled(running)
        self.export_button.setEnabled(self._manifest is not None)

    def _on_point_started(self, index: int) -> None:
        self.status.setText(ui_format("Running point {index} of {count} ({value})...", index=index + 1,
                                      count=len(self._manifest.points), value=self._manifest.points[index].value))
        self._update_buttons()

    def _on_point_finished(self, index: int, state: str) -> None:
        self.log.appendPlainText(ui_format("Point {index} ({value}): {state}", index=index,
                                           value=self._manifest.points[index].value, state=ui_text(state)))
        self.refresh_results()

    def _on_all_finished(self) -> None:
        done = sum(1 for r in self._results if r.state == "success")
        self.status.setText(ui_format("Scan finished: {done} of {count} points completed successfully.",
                                      done=done, count=len(self._results)))
        self._update_buttons()

    def _choose_scan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, ui_text("Open scan"), "", "scan.json (scan.json)")
        if path:
            try:
                self.load_scan(path)
            except (ValueError, OSError) as error:
                self.status.setText(ui_format("Cannot open scan: {error}", error=error))

    def _choose_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, ui_text("Export results"), "scan_results.csv", "CSV (*.csv)")
        if path:
            self.export_results(path)
