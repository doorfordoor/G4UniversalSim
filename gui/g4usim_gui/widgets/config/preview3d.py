"""3D preview: its widget (the 3D Preview tab) and its logic on the Configuration page."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.preview3d.fallback_preview_widget import FallbackPreviewWidget
from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget, pyvista_available
from g4usim_gui.preview3d.scene_builder import build_preview_scene
from g4usim_gui.preview3d.source_builder import build_preview_source


class Preview3DPanel(QWidget):
    """3D Preview tab: buttons, options, status and the 3D view (PyVista, or text without it)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview3d_refresh_button = QPushButton("Refresh Preview")
        self.preview3d_reset_button = QPushButton("Reset Camera")
        self.preview3d_tracks_button = QPushButton("Load Tracks...")
        self.preview3d_tracks_button.setToolTip(
            "Overlay the particle tracks of a run (trajectories_tN.json; set 'Particle tracks of the first "
            "events' on the Run Config tab before running)")
        self.preview3d_backend_button = QPushButton("Show Backend Geometry")
        self.preview3d_backend_button.setToolTip(
            "Run the backend with /run/initialize only and show the geometry Geant4 actually built "
            "(every replica and parameterised copy, all solids)."
        )
        self.preview3d_show_source = QCheckBox("Show Source")
        self.preview3d_show_source.setChecked(True)
        self.preview3d_show_labels = QCheckBox("Show Labels")
        self.preview3d_show_labels.setChecked(False)   # hovering a volume names it (G3)
        self.preview3d_auto_backend = QCheckBox("Geant4 geometry automatically")
        self.preview3d_auto_backend.setChecked(True)
        self.preview3d_auto_backend.setToolTip(
            "While this tab is open, rebuild the Geant4 geometry a moment after each change "
            "(about 3 s; unchanged geometry is shown from the cache).")
        self.preview3d_status = QLabel("3D Preview: stale")
        self.preview3d_status.setWordWrap(True)
        self.preview3d_messages = QPlainTextEdit()
        self.preview3d_messages.setReadOnly(True)
        self.preview3d_messages.setMaximumHeight(150)
        self.preview3d_widget = self._create_preview3d_widget()
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.preview3d_refresh_button)
        toolbar.addWidget(self.preview3d_backend_button)
        toolbar.addWidget(self.preview3d_tracks_button)
        self.preview3d_reset_button.hide()   # the view's own Iso camera button does this now (G2)
        toolbar.addStretch(1)
        options = QHBoxLayout()
        options.addWidget(self.preview3d_auto_backend)
        options.addWidget(self.preview3d_show_source)
        options.addWidget(self.preview3d_show_labels)
        options.addStretch(1)
        layout.addLayout(toolbar)
        layout.addLayout(options)
        layout.addWidget(self.preview3d_status)
        layout.addWidget(self.preview3d_widget, 3)
        layout.addWidget(QLabel("3D preview messages"))
        layout.addWidget(self.preview3d_messages, 1)

    def _create_preview3d_widget(self) -> QWidget:
        available, reason = pyvista_available()
        if not available:
            return FallbackPreviewWidget(reason=reason)
        try:
            return PyVistaPreviewWidget()
        except Exception as exc:  # noqa: BLE001
            return FallbackPreviewWidget(reason=str(exc))


class Preview3DMixin:
    """3D preview logic; mixed into ConfigBuilderPage."""

    def _connect_preview_signals(self) -> None:
        """3D tab buttons, options and the selection link."""
        self.preview3d_refresh_button.clicked.connect(self.refresh_3d_preview)
        self.preview3d_reset_button.clicked.connect(lambda: self.preview3d_widget.reset_camera())
        self.preview3d_backend_button.clicked.connect(self.backendGeometryRequested.emit)
        self.preview3d_tracks_button.clicked.connect(self.tracksRequested.emit)
        self.preview3d_auto_backend.toggled.connect(lambda on: on and self.schedule_backend_geometry(100))
        # selection follows between the 3D view and the volume table (G3)
        self.preview3d_widget.volumeSelected.connect(self.select_geometry_row)
        self.geometry_table.itemSelectionChanged.connect(self._on_geometry_row_selected)
        self.preview3d_show_source.stateChanged.connect(self._update_preview_display_options)
        self.preview3d_show_labels.stateChanged.connect(self._update_preview_display_options)

    def preview3d_tab_visible(self) -> bool:
        current = self.workspace_tabs.currentWidget()   # the 3D tab's scroll area
        return bool(self.isVisible() and current is not None and current.isAncestorOf(self.preview3d_widget))

    def preview3d_tab_index(self) -> int:
        return next(i for i in range(self.workspace_tabs.count())
                    if self.workspace_tabs.widget(i).isAncestorOf(self.preview3d_widget))

    def schedule_backend_geometry(self, delay_ms: int | None = None) -> None:
        """Ask for the Geant4 world a moment after the last change, while the 3D tab is shown."""
        if not self.preview3d_auto_backend.isChecked() or not self.preview3d_tab_visible():
            return
        if delay_ms is not None:
            self._backend_timer.setInterval(delay_ms)
        self._backend_timer.start()
        self._backend_timer.setInterval(1200)

    def _request_auto_backend_geometry(self) -> None:
        if self.preview3d_auto_backend.isChecked() and self.preview3d_tab_visible():
            self.autoBackendGeometryRequested.emit()

    def _mark_preview_stale(self) -> None:
        if hasattr(self, "preview3d_status"):
            self.preview3d_status.setText("3D Preview: stale. Click Refresh Preview to rebuild the scene.")

    def _update_preview_display_options(self) -> None:
        if hasattr(self.preview3d_widget, "set_show_source"):
            self.preview3d_widget.set_show_source(self.preview3d_show_source.isChecked())
        if hasattr(self.preview3d_widget, "set_show_labels"):
            self.preview3d_widget.set_show_labels(self.preview3d_show_labels.isChecked())   # redraws at once

    def refresh_3d_preview(self) -> None:
        try:
            self.preview_scene = build_preview_scene(self.geometry_document, self.source_editor)
            if hasattr(self.preview3d_widget, "set_show_source"):
                self.preview3d_widget.set_show_source(self.preview3d_show_source.isChecked())
            if hasattr(self.preview3d_widget, "set_show_labels"):
                self.preview3d_widget.set_show_labels(self.preview3d_show_labels.isChecked())
            self.preview3d_widget.render_scene(self.preview_scene)
            message_lines = self.preview_scene.summary_lines()
            self.preview3d_messages.setPlainText("\n".join(message_lines))
            status = "ERROR" if self.preview_scene.errors else "WARN" if self.preview_scene.warnings else "OK"
            self.preview3d_status.setText(
                ui_format(
                    "3D Preview: {status} | volumes={volumes}",
                    status=ui_text(status),
                    volumes=len(self.preview_scene.volumes),
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.preview3d_status.setText(f"3D Preview: ERROR")
            self.preview3d_messages.setPlainText(f"Preview refresh failed:\n{exc}")

    def set_backend_geometry_busy(self, busy: bool) -> None:
        self.preview3d_backend_button.setEnabled(not busy)
        if busy:
            # the editor sketch while Geant4 builds; it is labelled as an approximation
            self.refresh_3d_preview()
            self.preview3d_status.setText(ui_text(
                "Building the Geant4 geometry... Showing the editor sketch meanwhile (approximate)."))

    def show_backend_geometry_message(self, message: str) -> None:
        self.preview3d_status.setText(ui_text(
            "Geant4 geometry not available; the editor sketch (approximate) is shown. Reason below."))
        self.preview3d_messages.setPlainText(message)

    def show_backend_geometry(self, mesh, cached: bool = False, *, with_source: bool = True) -> None:
        """Display the exportMesh result; the editor preview is replaced until the next Refresh.

        with_source: draw the Source editor's source over it (the run's source in generated mode)."""
        source = None
        if with_source:
            source = build_preview_source(self.source_editor, [], [])
        if hasattr(self.preview3d_widget, "set_show_source"):
            self.preview3d_widget.set_show_source(self.preview3d_show_source.isChecked())
        self.preview3d_widget.render_backend_mesh(mesh, source)
        solids = sorted({volume.solid for volume in mesh.volumes})
        self.preview3d_status.setText(ui_format(
            "Backend geometry: {count} volume copies from Geant4.", count=len(mesh.volumes))
            + ("  " + ui_text("(unchanged, from the cache)") if cached else ""))
        self.preview3d_messages.setPlainText("\n".join([
            ui_text("This is the geometry built by the Geant4 backend, not the editor approximation."),
            ui_format("Source: {path}", path=mesh.source_file),
            ui_format("Solids: {solids}", solids=", ".join(solids)),
            *(f"{volume.path}  {volume.solid}  {volume.material}  {volume.cubic_volume_mm3:.6g} mm3"
              for volume in mesh.volumes[:200]),
        ]))
