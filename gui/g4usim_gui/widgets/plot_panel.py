"""Results / Plots tab (roadmap C1): built-in plots of an output directory.

Data come from output/plot_data.py; this widget only chooses the data set and the
view, draws it with matplotlib (Qt canvas, theme colours) and exports the figure or
the plotted numbers. Comparison overlays the same data set (same key) from other
output directories or from the other runs of this directory.
"""

from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.theme import DARK, LIGHT
from g4usim_gui.output import plot_data

AXES = ("0", "1", "2")


class PlotPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._output_dir = ""
        self._datasets: list[plot_data.DataSet] = []
        self._comparisons: list[str] = []
        self._plot: plot_data.Plot | None = None

        self.dataset_combo = QComboBox()
        self.dataset_combo.setMinimumWidth(320)
        self.view_combo = QComboBox()
        self.log_x = QCheckBox("Log X")
        self.log_y = QCheckBox("Log Y")
        self.all_runs = QCheckBox("Overlay all runs")
        self.per_primary = QCheckBox("Per primary")
        self.compare_button = QPushButton("Compare with output...")
        self.clear_compare_button = QPushButton("Clear comparison")
        self.export_png_button = QPushButton("Export image...")
        self.export_csv_button = QPushButton("Export plotted data...")
        self.comparison_label = QLabel("")
        self.comparison_label.setWordWrap(True)
        self.message = QLabel("Select an output directory to plot results.")
        self.message.setWordWrap(True)
        self.figure = Figure(figsize=(7, 4.5), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Data set"))
        row.addWidget(self.dataset_combo, 2)
        row.addWidget(QLabel("View"))
        row.addWidget(self.view_combo, 1)
        row.addWidget(self.log_x)
        row.addWidget(self.log_y)
        row.addWidget(self.per_primary)
        row.addWidget(self.all_runs)
        buttons = QHBoxLayout()
        buttons.addWidget(self.compare_button)
        buttons.addWidget(self.clear_compare_button)
        buttons.addStretch(1)
        buttons.addWidget(self.export_png_button)
        buttons.addWidget(self.export_csv_button)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addLayout(buttons)
        layout.addWidget(self.comparison_label)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.message)

        self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        self.view_combo.currentIndexChanged.connect(self.redraw)
        self.log_x.toggled.connect(self.redraw)
        self.log_y.toggled.connect(self.redraw)
        self.all_runs.toggled.connect(self.redraw)
        self.per_primary.toggled.connect(self.redraw)
        self.compare_button.clicked.connect(self._choose_comparison)
        self.clear_compare_button.clicked.connect(self.clear_comparisons)
        self.export_png_button.clicked.connect(self._choose_png)
        self.export_csv_button.clicked.connect(self._choose_csv)
        self._update_buttons()

    # --- public API (also used by the smoke test) ---------------------------------

    def set_output_dir(self, output_dir: str) -> None:
        self._output_dir = output_dir or ""
        current = self.current_dataset()
        self._datasets = plot_data.discover(self._output_dir) if self._output_dir else []
        self.dataset_combo.blockSignals(True)
        self.dataset_combo.clear()
        for dataset in self._datasets:
            self.dataset_combo.addItem(dataset.label, dataset.key)
        if current is not None:
            index = self.dataset_combo.findData(current.key)
            if index >= 0:
                self.dataset_combo.setCurrentIndex(index)
        self.dataset_combo.blockSignals(False)
        if not self._datasets:
            self._plot = None
            self.figure.clear()
            self.canvas.draw_idle()
            self.message.setText(ui_text("No plottable data in this output directory.") if self._output_dir
                                 else ui_text("Select an output directory to plot results."))
            self._update_buttons()
            return
        self._on_dataset_changed()

    def datasets(self) -> list[plot_data.DataSet]:
        return list(self._datasets)

    def current_dataset(self) -> plot_data.DataSet | None:
        key = self.dataset_combo.currentData()
        return next((d for d in self._datasets if d.key == key), None)

    def select(self, key: str) -> bool:
        index = self.dataset_combo.findData(key)
        if index < 0:
            return False
        self.dataset_combo.setCurrentIndex(index)
        return True

    def select_view(self, data: str) -> bool:
        index = self.view_combo.findData(data)
        if index < 0:
            return False
        self.view_combo.setCurrentIndex(index)
        return True

    def add_comparison(self, output_dir: str) -> None:
        if output_dir and output_dir != self._output_dir and output_dir not in self._comparisons:
            self._comparisons.append(output_dir)
        self._show_comparisons()
        self.redraw()

    def clear_comparisons(self) -> None:
        self._comparisons.clear()
        self._show_comparisons()
        self.redraw()

    def current_plot(self) -> plot_data.Plot | None:
        return self._plot

    def export_png(self, path: str) -> None:
        self.figure.savefig(path, dpi=150)

    def export_csv(self, path: str) -> None:
        if self._plot is not None:
            plot_data.write_plot_csv(self._plot, path)

    # --- building and drawing ------------------------------------------------------

    def _on_dataset_changed(self) -> None:
        dataset = self.current_dataset()
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        if dataset is not None and dataset.kind == "mesh":
            try:
                data = plot_data.load_mesh(self._output_dir, dataset)
                names = data.axes
            except Exception:
                names = ("i0", "i1", "i2")
            for axis in range(3):
                self.view_combo.addItem(ui_format("Profile along {axis}", axis=names[axis]), f"profile:{axis}")
            for ax, ay in ((2, 0), (2, 1), (0, 1)):
                self.view_combo.addItem(ui_format("Map {x} vs {y}", x=names[ax], y=names[ay]), f"map:{ax}:{ay}")
            if dataset is not None:
                try:
                    self.view_combo.setCurrentIndex(max(range(3), key=lambda a: data.bins[a]))
                except Exception:
                    pass
        else:
            self.view_combo.addItem(ui_text("Default"), "default")
        self.view_combo.blockSignals(False)
        self.log_x.setChecked(dataset is not None and dataset.kind == "phase")
        self.redraw()

    def _options(self) -> dict:
        # view keys: "default", "profile:<axis>", "map:<x axis>:<y axis>"
        view = str(self.view_combo.currentData() or "default").split(":")
        if view[0] == "profile":
            return {"axis": int(view[1])}
        if view[0] == "map":
            return {"map": (int(view[1]), int(view[2]))}
        return {}

    def _sources(self, dataset: plot_data.DataSet) -> list[tuple[str, plot_data.DataSet, str]]:
        """(directory, data set, legend prefix) for the main data set and its comparisons."""
        sources = []
        if self.all_runs.isChecked():
            base = dataset.key.rsplit("/r", 1)[0]
            for other in self._datasets:
                if other.key.rsplit("/r", 1)[0] == base:
                    sources.append((self._output_dir, other, ui_format("run {run}", run=other.run_id)))
        else:
            sources.append((self._output_dir, dataset, Path(self._output_dir).name))
        for directory in self._comparisons:
            match = plot_data.matching(plot_data.discover(directory), dataset.key)
            if match is not None:
                sources.append((directory, match, Path(directory).name))
        return sources

    def redraw(self) -> None:
        self.figure.clear()
        self._plot = None
        dataset = self.current_dataset()
        if dataset is None:
            self.canvas.draw_idle()
            self._update_buttons()
            return
        colors = DARK if QApplication.instance() and QApplication.instance().property("resolvedTheme") == "dark" \
            else LIGHT
        self.figure.set_facecolor(colors.surface)
        axes = self.figure.add_subplot(1, 1, 1)
        axes.set_facecolor(colors.surface)
        for spine in axes.spines.values():
            spine.set_color(colors.border_strong)
        axes.tick_params(colors=colors.text, which="both")
        options = self._options()
        notes: list[str] = []
        try:
            plots = []
            sources = self._sources(dataset)
            for directory, source, prefix in sources:
                plot = plot_data.build_plot(directory, source, per_primary=self.per_primary.isChecked(), **options)
                for series in plot.series:
                    series.label = prefix if len(plot.series) == 1 else f"{prefix}: {series.label}"
                plots.append(plot)
            main = plots[0]
            if main.kind == "image":
                if len(plots) > 1:
                    notes.append(ui_text("Maps show the main data set only; comparisons apply to profiles, "
                                         "spectra and totals."))
                image = axes.imshow(main.image, origin="lower", aspect="auto", extent=main.extent,
                                    cmap="viridis")
                bar = self.figure.colorbar(image, ax=axes)
                bar.ax.tick_params(colors=colors.text)
            elif main.kind == "bar":
                categories = []
                for plot in plots:
                    for name in plot.categories:
                        if name not in categories:
                            categories.append(name)
                width = 0.8 / len(plots)
                for n, plot in enumerate(plots):
                    series = plot.series[0]
                    lookup = dict(zip(plot.categories, zip(series.y, series.yerr)))
                    xs = [i + (n - (len(plots) - 1) / 2) * width for i, c in enumerate(categories) if c in lookup]
                    ys = [lookup[c][0] for c in categories if c in lookup]
                    es = [lookup[c][1] for c in categories if c in lookup]
                    axes.bar(xs, ys, width, yerr=es, capsize=3, label=series.label)
                axes.set_xticks(range(len(categories)))
                axes.set_xticklabels([c.rsplit("/", 1)[-1] for c in categories], rotation=30, ha="right",
                                     fontsize=8)
                main = plot_data.Plot(main.title, main.xlabel, main.ylabel, "bar", categories=categories,
                                      series=[s for p in plots for s in p.series], notes=main.notes)
            else:
                for plot in plots:
                    for series in plot.series:
                        if series.edges:
                            line, = axes.step(series.x[:-1], series.y, where="post", label=series.label)
                            if series.yerr is not None:
                                centres = 0.5 * (series.x[:-1] + series.x[1:])
                                axes.errorbar(centres, series.y, yerr=series.yerr, fmt="none",
                                              ecolor=line.get_color(), alpha=0.5, linewidth=0.8)
                        else:
                            axes.errorbar(series.x, series.y, yerr=series.yerr, fmt="-", capsize=0,
                                          linewidth=1.2, elinewidth=0.8, label=series.label)
                main = plot_data.Plot(main.title, main.xlabel, main.ylabel, main.kind,
                                      series=[s for p in plots for s in p.series], log_x=main.log_x,
                                      notes=main.notes)
            if main.kind != "image":
                if self.log_x.isChecked():
                    axes.set_xscale("log")
                if self.log_y.isChecked():
                    axes.set_yscale("log")
                if len(main.series) > 1 or self._comparisons:
                    legend = axes.legend(fontsize=8)
                    legend.get_frame().set_facecolor(colors.surface_alt)
                    for text in legend.get_texts():
                        text.set_color(colors.text)
            axes.set_title(main.title, color=colors.text)
            axes.set_xlabel(main.xlabel, color=colors.text)
            axes.set_ylabel(main.ylabel, color=colors.text)
            missing = len(self._comparisons) - sum(1 for directory, _, _ in sources if directory != self._output_dir)
            if missing > 0:
                notes.append(ui_format("{count} comparison directories have no data set {key}.",
                                       count=missing, key=dataset.key))
            self._plot = main
            notes = [ui_format(template, **values) for template, values in main.notes] + notes
            self.message.setText("\n".join(notes))
        except Exception as error:   # show the reason; the data set stays selectable
            self.message.setText(ui_format("Cannot plot {key}: {error}", key=dataset.key, error=error))
        self.canvas.draw_idle()
        self._update_buttons()

    # --- dialogs ---------------------------------------------------------------------

    def _choose_comparison(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, ui_text("Choose an output directory to compare"))
        if directory:
            self.add_comparison(directory)

    def _choose_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, ui_text("Export image"), "plot.png", "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)")
        if path:
            self.export_png(path)

    def _choose_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, ui_text("Export plotted data"), "plot.csv", "CSV (*.csv)")
        if path:
            self.export_csv(path)

    def _show_comparisons(self) -> None:
        self.comparison_label.setText(
            ui_format("Comparing with: {dirs}", dirs=", ".join(self._comparisons)) if self._comparisons else "")
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_plot = self._plot is not None
        self.export_png_button.setEnabled(has_plot)
        self.export_csv_button.setEnabled(has_plot)
        self.compare_button.setEnabled(bool(self._datasets))
        self.clear_compare_button.setEnabled(bool(self._comparisons))
        self.all_runs.setEnabled(bool(self._datasets))
