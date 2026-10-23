"""3D view of the geometry (roadmap A5, G1-G3): the Geant4 world or the editor sketch.

Both are drawn through one path: a list of view_model.ViewItems with their meshes,
styled by a ViewState (material colours and legend, world/hidden/isolated volumes,
selection, section plane). Interaction: hover shows a volume's name, material, solid
and volume; a click (without dragging) selects it and emits volumeSelected so the
geometry table can follow; Isolate/Hide/Show all, the legend's check boxes, camera
presets, an orthographic toggle and a section plane change only what is drawn.
"""

from __future__ import annotations

import math
import os

import numpy as np

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.theme import current_colors
from g4usim_gui.preview3d.backend_mesh import BackendMesh
from g4usim_gui.preview3d.geometry_primitives import add_vec3, scale_vec3, scene_extent
from g4usim_gui.preview3d.scene_model import PreviewScene, PreviewVolume
from g4usim_gui.preview3d.units import perpendicular_basis
from g4usim_gui.preview3d.trajectories import TrackFilter, TrajectorySet
from g4usim_gui.preview3d.view_model import CAMERA_PRESETS, ViewItem, ViewState, backend_items, mark_containers

CLICK_TOLERANCE_PX = 4
SECTION_LABELS = (("No section", ""), ("Section x", "x"), ("Section y", "y"), ("Section z", "z"))


class PyVistaPreviewWidget(QWidget):
    volumeSelected = Signal(str)     # editor volume name, "" when the selection is cleared

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import pyvista as pv  # noqa: PLC0415
        import vtk  # noqa: PLC0415
        from pyvistaqt import QtInteractor  # noqa: PLC0415

        self._pv = pv
        self._vtk = vtk
        self._plotter = QtInteractor(self)
        self._show_source = True
        self._show_labels = False
        self.state = ViewState()
        self._meshes: dict[str, object] = {}
        self._actors: dict[str, object] = {}
        self._items: dict[str, ViewItem] = {}
        self._actor_keys: dict[int, str] = {}
        self._plane = vtk.vtkPlane()
        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.0005)
        self._press_position: tuple[int, int] | None = None
        self._hovered = ""
        self._source_label = ""

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setProperty("uiRole", "hint")
        self.empty = QLabel(ui_text("Press Refresh Preview to draw the editor geometry, or Show Backend "
                                    "Geometry for the geometry Geant4 builds."))
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setProperty("uiRole", "emptyState")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self._plotter)

        # view controls: cameras, projection, world, section, visibility
        self.camera_buttons: dict[str, QToolButton] = {}
        controls = QHBoxLayout()
        controls.setSpacing(4)
        controls.addWidget(QLabel("View"))
        for name, label in (("front", "Front"), ("side", "Side"), ("top", "Top"), ("iso", "Iso")):
            button = QToolButton()
            button.setText(label)
            button.setProperty("toolbarButton", True)
            button.setToolTip(ui_format("Look at the geometry from the {view}", view=label.lower()))
            button.clicked.connect(lambda _checked=False, preset=name: self.set_camera(preset))
            controls.addWidget(button)
            self.camera_buttons[name] = button
        self.ortho = QCheckBox("Orthographic")
        self.show_world = QCheckBox("World")
        self.show_world.setToolTip("Draw the world volume as a faint outline")
        self.section_axis = QComboBox()
        for label, axis in SECTION_LABELS:
            self.section_axis.addItem(ui_text(label), axis)
        self.section_slider = QSlider(Qt.Horizontal)
        self.section_slider.setRange(0, 1000)
        self.section_slider.setValue(500)
        self.section_slider.setEnabled(False)
        self.section_slider.setMinimumWidth(110)
        self.isolate_button = QToolButton()
        self.isolate_button.setText("Isolate")
        self.hide_button = QToolButton()
        self.hide_button.setText("Hide")
        self.show_all_button = QToolButton()
        self.show_all_button.setText("Show all")
        for button in (self.isolate_button, self.hide_button, self.show_all_button):
            button.setProperty("toolbarButton", True)
        controls.addSpacing(6)
        controls.addWidget(self.ortho)
        controls.addWidget(self.show_world)
        controls.addStretch(1)
        tools = QHBoxLayout()     # second row: cut and visibility
        tools.setSpacing(4)
        tools.addWidget(self.section_axis)
        tools.addWidget(self.section_slider, 1)
        tools.addSpacing(10)
        tools.addWidget(self.isolate_button)
        tools.addWidget(self.hide_button)
        tools.addWidget(self.show_all_button)

        self.legend = QListWidget()
        self.legend.setFixedWidth(190)
        self.legend.setIconSize(QSize(14, 14))
        self.legend.setToolTip("Materials in the view; untick one to hide its volumes")
        legend_box = QVBoxLayout()
        legend_title = QLabel("Materials")
        legend_title.setProperty("uiRole", "sectionTitle")
        legend_box.addWidget(legend_title)
        legend_box.addWidget(self.legend, 1)

        # particle tracks (roadmap G6): hidden until a trajectory file is loaded
        self.trajectories: TrajectorySet | None = None
        self.track_filter = TrackFilter()
        self._track_actors: list = []
        self.particle_legend = QListWidget()
        self.particle_legend.setFixedWidth(190)
        self.particle_legend.setIconSize(QSize(14, 14))
        self.particle_legend.setToolTip("Particles of the loaded tracks; untick one to hide its tracks")
        self.particle_title = QLabel("Particles")
        self.particle_title.setProperty("uiRole", "sectionTitle")
        legend_box.addWidget(self.particle_title)
        legend_box.addWidget(self.particle_legend, 1)
        self.track_previous = QToolButton()
        self.track_previous.setText("<")
        self.track_previous.setToolTip("Previous event")
        self.track_event = QComboBox()
        self.track_next = QToolButton()
        self.track_next.setText(">")
        self.track_next.setToolTip("Next event")
        for button in (self.track_previous, self.track_next):
            button.setProperty("toolbarButton", True)
        self.track_primaries = QCheckBox("Primaries only")
        self.track_min_energy = QDoubleSpinBox()
        self.track_min_energy.setRange(0.0, 1.0e7)
        self.track_min_energy.setDecimals(3)
        self.track_min_energy.setSuffix(" MeV")
        self.track_min_energy.setToolTip("Hide secondary tracks that start below this kinetic energy")
        self.track_clear = QToolButton()
        self.track_clear.setText("Clear tracks")
        self.track_clear.setProperty("toolbarButton", True)
        self.track_info = QLabel()
        self.track_info.setProperty("uiRole", "hint")
        self.track_row = QWidget()
        track_box = QVBoxLayout(self.track_row)
        track_box.setContentsMargins(0, 0, 0, 0)
        track_box.setSpacing(2)
        track_layout = QHBoxLayout()
        track_layout.setSpacing(4)
        track_box.addLayout(track_layout)
        track_layout.addWidget(QLabel("Tracks"))
        for widget in (self.track_previous, self.track_event, self.track_next):
            track_layout.addWidget(widget)
        track_layout.addSpacing(6)
        track_layout.addWidget(self.track_primaries)
        track_layout.addWidget(QLabel("min"))
        track_layout.addWidget(self.track_min_energy)
        track_layout.addWidget(self.track_clear)
        track_layout.addStretch(1)
        track_box.addWidget(self.track_info)
        self._show_track_controls(False)
        view_row = QHBoxLayout()
        view_row.addWidget(self.stack, 1)
        view_row.addLayout(legend_box)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addLayout(tools)
        layout.addWidget(self.track_row)
        layout.addLayout(view_row, 1)
        layout.addWidget(self.status)

        self.ortho.toggled.connect(self._on_ortho)
        self.show_world.toggled.connect(self._on_show_world)
        self.section_axis.currentIndexChanged.connect(self._on_section_axis)
        self.section_slider.valueChanged.connect(self._on_section_slider)
        self.isolate_button.clicked.connect(self.isolate_selected)
        self.hide_button.clicked.connect(self.hide_selected)
        self.show_all_button.clicked.connect(self.show_all)
        self.legend.itemChanged.connect(self._on_legend_item)
        self.particle_legend.itemChanged.connect(self._on_particle_item)
        self.track_event.currentIndexChanged.connect(self._on_track_event)
        self.track_previous.clicked.connect(lambda: self.step_event(-1))
        self.track_next.clicked.connect(lambda: self.step_event(1))
        self.track_primaries.toggled.connect(self._on_track_options)
        self.track_min_energy.valueChanged.connect(self._on_track_options)
        self.track_clear.clicked.connect(self.clear_trajectories)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(40)
        self._hover_timer.timeout.connect(self._update_hover)
        iren = self._plotter.iren
        iren.add_observer("MouseMoveEvent", lambda *_: self._hover_timer.start())
        iren.add_observer("LeftButtonPressEvent", self._on_press)
        iren.add_observer("LeftButtonReleaseEvent", self._on_release)
        self._update_controls()
        self.set_theme()

    # --- public API used by the Configuration page -----------------------------------
    def set_theme(self) -> None:
        colors = current_colors()
        self._plotter.set_background(colors.surface_alt)
        self._apply_styles()
        self._fill_legend()

    def refresh_language(self) -> None:
        for index, (label, _axis) in enumerate(SECTION_LABELS):
            self.section_axis.setItemText(index, ui_text(label))
        self._show_info()

    def clear(self) -> None:
        self._plotter.clear()
        self._meshes, self._actors, self._items, self._actor_keys = {}, {}, {}, {}
        self._track_actors = []
        self.status.clear()

    # --- particle tracks (roadmap G6) ---------------------------------------------------
    def show_trajectories(self, trajectories: TrajectorySet) -> None:
        """Overlay the tracks of a run's trajectory files; the first event is shown."""
        self.trajectories = trajectories
        self.track_filter = TrackFilter(event_index=0, min_energy=self.track_min_energy.value(),
                                        primaries_only=self.track_primaries.isChecked())
        self.track_event.blockSignals(True)
        self.track_event.clear()
        for event in trajectories.events:
            self.track_event.addItem(ui_format("Event {event}", event=event.event), event.event)
        self.track_event.addItem(ui_text("All events"), -1)
        self.track_event.setCurrentIndex(0)
        self.track_event.blockSignals(False)
        self._fill_particle_legend()
        self._show_track_controls(True)
        if self.stack.currentWidget() is not self._plotter:
            self.stack.setCurrentWidget(self._plotter)
        self._draw_tracks()

    def clear_trajectories(self) -> None:
        self.trajectories = None
        self._remove_track_actors()
        self._show_track_controls(False)
        self._plotter.render()

    def step_event(self, delta: int) -> None:
        if self.trajectories and self.trajectories.events:
            count = len(self.trajectories.events)
            current = self.track_event.currentIndex()
            self.track_event.setCurrentIndex(0 if current >= count else (current + delta) % count)

    def shown_tracks(self) -> list:
        return self.track_filter.tracks(self.trajectories) if self.trajectories else []

    def _show_track_controls(self, shown: bool) -> None:
        if self.state.tracks_shown != shown:
            self.state.tracks_shown = shown
            self._apply_styles(render=False)
        self.track_row.setVisible(shown)
        self.particle_title.setVisible(shown)
        self.particle_legend.setVisible(shown)

    def _fill_particle_legend(self) -> None:
        self.particle_legend.blockSignals(True)
        self.particle_legend.clear()
        if self.trajectories:
            colours = self.trajectories.colours()
            for particle, count in self.trajectories.particles().items():
                swatch = QPixmap(14, 14)
                swatch.fill(QColor(colours[particle]))
                item = QListWidgetItem(QIcon(swatch), f"{particle}  ({count})")
                item.setData(Qt.UserRole, particle)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked if particle in self.track_filter.hidden_particles else Qt.Checked)
                self.particle_legend.addItem(item)
        self.particle_legend.blockSignals(False)

    def _remove_track_actors(self) -> None:
        for actor in self._track_actors:
            self._plotter.remove_actor(actor, render=False)
        self._track_actors = []

    def _draw_tracks(self, render: bool = True) -> None:
        self._remove_track_actors()
        tracks = self.shown_tracks()
        if self.trajectories:
            colours = self.trajectories.colours()
            by_particle: dict[str, list] = {}
            for track in tracks:
                if len(track.points) >= 2:
                    by_particle.setdefault(track.particle, []).append(track)
            for particle, group in sorted(by_particle.items()):
                points, lines = [], []
                for track in group:
                    start = len(points)
                    points.extend(track.points)
                    lines.extend([len(track.points), *range(start, start + len(track.points))])
                poly = self._pv.PolyData(np.asarray(points, dtype=float), lines=np.asarray(lines))
                actor = self._plotter.add_mesh(poly, color=colours[particle], line_width=2.0, pickable=False,
                                               reset_camera=False, render_lines_as_tubes=False)
                self._track_actors.append(actor)
            events = self.trajectories.events
            index = self.track_filter.event_index
            where = (ui_text("all events") if index is None
                     else ui_format("event {event} ({position} of {count})", event=events[index].event,
                                    position=index + 1, count=len(events)) if events else "")
            note = ui_text(" (file truncated)") if self.trajectories.truncated else ""
            self.track_info.setText(ui_format("{count} tracks, {where}{note}", count=len(tracks), where=where,
                                              note=note))
        if render:
            self._plotter.render()

    def _on_track_event(self, index: int) -> None:
        if self.trajectories is None:
            return
        self.track_filter.event_index = None if self.track_event.itemData(index) == -1 else index
        self._draw_tracks()

    def _on_track_options(self) -> None:
        self.track_filter.primaries_only = self.track_primaries.isChecked()
        self.track_filter.min_energy = self.track_min_energy.value()
        self._draw_tracks()

    def _on_particle_item(self, item: QListWidgetItem) -> None:
        particle = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            self.track_filter.hidden_particles.discard(particle)
        else:
            self.track_filter.hidden_particles.add(particle)
        self._draw_tracks()

    def reset_camera(self) -> None:
        self.set_camera("iso")

    def set_show_source(self, show: bool) -> None:
        self._show_source = show

    def set_show_labels(self, show: bool) -> None:
        self._show_labels = show

    def set_camera(self, preset: str) -> None:
        direction, up = CAMERA_PRESETS[preset]
        self._plotter.view_vector(direction, viewup=up)
        self._plotter.reset_camera(bounds=self.state.visible_bounds())
        self._plotter.render()

    def select_volume(self, name: str) -> None:
        """Select a volume by its editor name (from the geometry table); "" clears."""
        if (name or None) == self.state.selected:
            return
        self.state.select(name or None)
        self._apply_styles()
        self._show_info()
        self._update_controls()

    def isolate_selected(self) -> None:
        self.state.isolate_selected()
        self._apply_visibility()

    def hide_selected(self) -> None:
        self.state.hide_selected()
        self._apply_visibility()
        self.volumeSelected.emit("")

    def show_all(self) -> None:
        self.state.show_all()
        self._apply_visibility()

    def render_scene(self, scene: PreviewScene) -> None:
        """The editor sketch: approximate shapes from the editor's geometry."""
        self.stack.setCurrentWidget(self._plotter)
        try:
            items, meshes = [], {}
            for volume in scene.volumes:
                if volume.role == "boolean_tool" or not volume.size_mm or not volume.position_mm:
                    continue
                mesh = self._make_volume_mesh(volume)
                if mesh is None:
                    continue
                key = volume.name or f"volume{len(items)}"
                items.append(ViewItem(key=key, name=volume.name, material=volume.material, solid=volume.shape,
                                      sensitive=volume.sensitive, world=volume.role == "world",
                                      bounds=tuple(mesh.bounds)))
                meshes[key] = mesh
            mark_containers(items)
            self._render(items, meshes, scene)
            if scene.errors:
                summary = ui_format("Rendered with {errors} error(s) and {warnings} warning(s).",
                                    errors=len(scene.errors), warnings=len(scene.warnings))
            elif scene.warnings:
                summary = ui_format("Rendered with {warnings} warning(s).", warnings=len(scene.warnings))
            else:
                summary = ui_text("3D Preview: OK")
            self._source_label = summary
            self._show_info()
            self.status.setToolTip("\n".join([*scene.errors, *scene.warnings][:12]))
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"3D render failed: {exc}")

    def render_backend_mesh(self, mesh: BackendMesh) -> None:
        """Show the geometry Geant4 built (exportMesh), not the editor approximation."""
        self.stack.setCurrentWidget(self._plotter)
        try:
            items = backend_items(mesh)
            meshes = {}
            by_path = {volume.path: volume for volume in mesh.volumes}
            for item in items:
                volume = by_path[item.key]
                faces: list[int] = []
                for face in volume.faces:
                    faces.extend((len(face), *face))
                meshes[item.key] = self._pv.PolyData(np.asarray(volume.vertices, dtype=float), faces)
            self._render(items, meshes, None)
            self._source_label = ui_format("Backend geometry: {count} volume copies from Geant4.",
                                           count=len(mesh.volumes))
            self._show_info()
            self.status.setToolTip(mesh.source_file)
        except Exception as exc:  # noqa: BLE001
            self.status.setText(ui_format("Backend geometry render failed: {reason}", reason=exc))

    # --- drawing -------------------------------------------------------------------------
    def _render(self, items: list[ViewItem], meshes: dict, scene: PreviewScene | None) -> None:
        first = not self._items
        self._plotter.clear()
        self.state.set_items(items)
        self._meshes = meshes
        self._items = {item.key: item for item in items}
        self._actors, self._actor_keys = {}, {}
        for item in items:
            actor = self._plotter.add_mesh(meshes[item.key], show_edges=not item.world, smooth_shading=False,
                                           pickable=not item.world, reset_camera=False)
            self._actors[item.key] = actor
            self._actor_keys[id(actor)] = item.key
        if scene is not None and self._show_source and scene.source.position_mm and scene.source.direction:
            styled = {id(a) for a in self._actors.values()}
            self._add_source(scene)
            for actor in self._plotter.renderer.actors.values():
                if id(actor) not in styled and hasattr(actor, "SetPickable"):
                    actor.SetPickable(False)
        if self._show_labels:
            seen = set()
            for item in items:
                if item.world or item.name in seen or not item.bounds:
                    continue
                seen.add(item.name)
                b = item.bounds
                self._plotter.add_point_labels([((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2)],
                                               [item.name], point_size=0, font_size=11, pickable=False)
        self._plotter.add_axes()
        self._track_actors = []          # cleared with the scene: draw the loaded tracks again
        if self.trajectories is not None:
            self._draw_tracks(render=False)
        self._apply_visibility(render=False)
        self._apply_styles(render=False)
        self._fill_legend()
        if first:
            self.set_camera("iso")
        else:
            self._plotter.render()

    def _apply_styles(self, render: bool = True) -> None:
        colors = current_colors()
        edge = colors.border_strong
        for key, actor in self._actors.items():
            style = self.state.style(self._items[key])
            prop = actor.GetProperty()
            if style["wireframe"]:
                prop.SetRepresentationToWireframe()
                prop.SetColor(QColor(colors.text_muted).getRgbF()[:3])
                prop.SetOpacity(0.25)
                continue
            prop.SetRepresentationToSurface()
            prop.SetColor(QColor(style["colour"]).getRgbF()[:3])
            prop.SetOpacity(style["opacity"])
            prop.SetEdgeVisibility(True)
            if style["selected"]:
                prop.SetEdgeColor(QColor(colors.accent).getRgbF()[:3])
                prop.SetLineWidth(2.5)
            else:
                prop.SetEdgeColor(QColor(edge).getRgbF()[:3])
                prop.SetLineWidth(0.6)
        if render:
            self._plotter.render()

    def _apply_visibility(self, render: bool = True) -> None:
        for key, actor in self._actors.items():
            actor.SetVisibility(self.state.visible(self._items[key]))
        self._apply_section(render=False)
        self._apply_styles(render=False)
        self._update_controls()
        self._fill_legend()
        if render:
            self._plotter.render()

    def _apply_section(self, render: bool = True) -> None:
        plane = self.state.section_plane()
        for key, actor in self._actors.items():
            mapper = actor.GetMapper()
            mapper.RemoveAllClippingPlanes()
            if plane is not None and not self._items[key].world:
                mapper.AddClippingPlane(self._plane)
        if plane is not None:
            self._plane.SetOrigin(*plane[0])
            self._plane.SetNormal(*plane[1])
        if render:
            self._plotter.render()

    def _fill_legend(self) -> None:
        self.legend.blockSignals(True)
        self.legend.clear()
        for material, colour, count, shown in self.state.legend():
            swatch = QPixmap(14, 14)
            swatch.fill(QColor(colour))
            item = QListWidgetItem(QIcon(swatch), f"{material}  ({count})")
            item.setData(Qt.UserRole, material)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if shown else Qt.Unchecked)
            self.legend.addItem(item)
        self.legend.blockSignals(False)

    def _update_controls(self) -> None:
        has_selection = self.state.selected is not None
        self.isolate_button.setEnabled(has_selection)
        self.hide_button.setEnabled(has_selection)
        self.show_all_button.setEnabled(bool(self.state.hidden or self.state.hidden_materials or self.state.isolated))

    def _show_info(self) -> None:
        item = next((i for i in self._items.values() if i.name == (self._hovered or self.state.selected)), None)
        if self._hovered:
            hovered = self._items.get(self._hovered)
            text = hovered.describe() if hovered else ""
        elif item is not None:
            text = ui_format("Selected: {volume}", volume=item.describe())
        else:
            text = self._source_label + "  " + ui_text("Hover a volume to name it; click to select it.")
        self.status.setText(text)

    # --- interaction ------------------------------------------------------------------------
    def _pick(self) -> str:
        x, y = self._plotter.iren.interactor.GetEventPosition()
        if not self._picker.Pick(x, y, 0, self._plotter.renderer):
            return ""
        return self._actor_keys.get(id(self._picker.GetActor()), "")

    def _update_hover(self) -> None:
        key = self._pick() if self._actors else ""
        if key != self._hovered:
            self._hovered = key
            self._show_info()

    def _on_press(self, *_args) -> None:
        self._press_position = tuple(self._plotter.iren.interactor.GetEventPosition())

    def _on_release(self, *_args) -> None:
        start, self._press_position = self._press_position, None
        position = tuple(self._plotter.iren.interactor.GetEventPosition())
        if start is None or max(abs(position[0] - start[0]), abs(position[1] - start[1])) > CLICK_TOLERANCE_PX:
            return    # a drag rotates the camera; only a click selects
        key = self._pick()
        name = self._items[key].name if key else ""
        self.select_volume(name)
        self.volumeSelected.emit(name)

    def _on_ortho(self, on: bool) -> None:
        if on:
            self._plotter.enable_parallel_projection()
        else:
            self._plotter.disable_parallel_projection()
        self._plotter.render()

    def _on_show_world(self, on: bool) -> None:
        self.state.show_world = on
        self._apply_visibility()

    def _on_section_axis(self) -> None:
        self.state.section_axis = self.section_axis.currentData() or ""
        self.section_slider.setEnabled(bool(self.state.section_axis))
        self._apply_section()

    def _on_section_slider(self, value: int) -> None:
        self.state.section_fraction = value / 1000.0
        self._apply_section()

    def _on_legend_item(self, item: QListWidgetItem) -> None:
        self.state.toggle_material(item.data(Qt.UserRole), item.checkState() == Qt.Checked)
        self._apply_visibility()

    def _make_volume_mesh(self, volume: PreviewVolume):
        sx, sy, sz = volume.size_mm
        px, py, pz = volume.position_mm
        shape = volume.shape.lower()
        if shape == "box":
            mesh = self._pv.Box(bounds=(px - sx / 2, px + sx / 2, py - sy / 2, py + sy / 2, pz - sz / 2, pz + sz / 2))
        elif shape in {"tubs", "cylinder"}:
            inner_radius = volume.parameters_mm[0] if len(volume.parameters_mm) >= 3 else 0.0
            outer_radius = volume.parameters_mm[1] if len(volume.parameters_mm) >= 3 else max(sx, sy) / 2
            half_z = volume.parameters_mm[2] if len(volume.parameters_mm) >= 3 else sz / 2
            mesh = make_tubs_mesh(
                self._pv,
                center=volume.position_mm,
                inner_radius=inner_radius,
                outer_radius=outer_radius,
                half_z=half_z,
            )
        elif shape in {"sphere", "orb"}:
            radius = max(sx, sy, sz) / 2
            mesh = self._pv.Sphere(radius=radius, center=volume.position_mm, theta_resolution=48, phi_resolution=24)
        elif shape == "cone":
            radius = max(sx, sy) / 2
            height = sz
            mesh = self._pv.Cone(center=volume.position_mm, direction=(0.0, 0.0, 1.0), height=height, radius=radius, resolution=64)
        elif shape == "trd" and len(volume.parameters_mm) >= 5:
            mesh = make_trd_mesh(
                self._pv,
                center=volume.position_mm,
                dx1=volume.parameters_mm[0],
                dx2=volume.parameters_mm[1],
                dy1=volume.parameters_mm[2],
                dy2=volume.parameters_mm[3],
                half_z=volume.parameters_mm[4],
            )
        else:
            return None
        self._apply_rotation(mesh, volume)
        return mesh

    def _apply_rotation(self, mesh, volume: PreviewVolume) -> None:
        if not volume.rotation_deg or not volume.position_mm:
            return
        rx, ry, rz = volume.rotation_deg
        if abs(rx) > 1.0e-9:
            mesh.rotate_x(rx, point=volume.position_mm, inplace=True)
        if abs(ry) > 1.0e-9:
            mesh.rotate_y(ry, point=volume.position_mm, inplace=True)
        if abs(rz) > 1.0e-9:
            mesh.rotate_z(rz, point=volume.position_mm, inplace=True)

    def _add_source(self, scene: PreviewScene) -> None:
        start = scene.source.position_mm
        direction = scene.source.direction
        if not start or not direction:
            return
        self._add_source_surface(scene)
        length = scene_extent(scene.bounds_mm) * 0.28
        rays = scene.source.preview_rays or [(start, add_vec3(start, scale_vec3(direction, length)))]
        label_point = rays[0][1]
        for ray_start, ray_end in rays[:256]:
            self._add_source_ray(ray_start, ray_end)
        end = label_point
        if self._show_labels:
            self._plotter.add_point_labels([end], [f"Source: {scene.source.particle} {scene.source.energy}"], point_size=0, font_size=12)

    def _add_source_ray(self, start, end) -> None:
        direction = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
        length = max((direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2) ** 0.5, 1.0e-9)
        arrow = self._pv.Arrow(
            start=start,
            direction=direction,
            tip_length=0.18,
            tip_radius=0.035,
            shaft_radius=0.006,
            scale=length,
        )
        self._plotter.add_mesh(arrow, color="red", opacity=0.35)

    def _add_source_surface(self, scene: PreviewScene) -> None:
        source = scene.source
        center = source.position_mm
        if not center or source.position_mode != "plane":
            return
        normal = source.normal or source.direction or (0.0, 0.0, 1.0)
        if source.source_shape in {"circle", "annulus"} and source.radius_mm:
            disk = self._pv.Disc(center=center, inner=source.inner_radius_mm or 0.0, outer=source.radius_mm, normal=normal, r_res=1, c_res=64)
            self._plotter.add_mesh(disk, color="red", opacity=0.12, show_edges=True)
        elif source.source_shape in {"rectangle", "square"} and source.halfx_mm:
            hx = source.halfx_mm
            hy = source.halfy_mm if source.source_shape == "rectangle" and source.halfy_mm else hx
            u, v = perpendicular_basis(normal)
            points = [
                add_vec3(center, add_vec3(scale_vec3(u, -hx), scale_vec3(v, -hy))),
                add_vec3(center, add_vec3(scale_vec3(u, hx), scale_vec3(v, -hy))),
                add_vec3(center, add_vec3(scale_vec3(u, hx), scale_vec3(v, hy))),
                add_vec3(center, add_vec3(scale_vec3(u, -hx), scale_vec3(v, hy))),
            ]
            mesh = self._pv.PolyData(points, faces=[4, 0, 1, 2, 3])
            self._plotter.add_mesh(mesh, color="red", opacity=0.12, show_edges=True)


def make_tubs_mesh(pv, *, center, inner_radius: float, outer_radius: float, half_z: float, resolution: int = 64):
    """Build a closed full-phi G4Tubs approximation, preserving a non-zero inner radius."""
    if inner_radius <= 1.0e-9:
        return pv.Cylinder(
            center=center,
            direction=(0.0, 0.0, 1.0),
            radius=outer_radius,
            height=2.0 * half_z,
            resolution=resolution,
        )

    cx, cy, cz = center
    points: list[tuple[float, float, float]] = []
    for radius, z_offset in [
        (outer_radius, -half_z),
        (outer_radius, half_z),
        (inner_radius, -half_z),
        (inner_radius, half_z),
    ]:
        for index in range(resolution):
            angle = math.tau * index / resolution
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle), cz + z_offset))

    outer_bottom = 0
    outer_top = resolution
    inner_bottom = 2 * resolution
    inner_top = 3 * resolution
    faces: list[int] = []
    for index in range(resolution):
        next_index = (index + 1) % resolution
        faces.extend([4, outer_bottom + index, outer_bottom + next_index, outer_top + next_index, outer_top + index])
        faces.extend([4, inner_bottom + next_index, inner_bottom + index, inner_top + index, inner_top + next_index])
        faces.extend([4, outer_top + index, outer_top + next_index, inner_top + next_index, inner_top + index])
        faces.extend([4, outer_bottom + next_index, outer_bottom + index, inner_bottom + index, inner_bottom + next_index])
    return pv.PolyData(points, faces)


def make_trd_mesh(pv, *, center, dx1: float, dx2: float, dy1: float, dy2: float, half_z: float):
    """Build the eight-corner G4Trd surface used by read-only geometry preview."""
    cx, cy, cz = center
    points = [
        (cx - dx1, cy - dy1, cz - half_z),
        (cx + dx1, cy - dy1, cz - half_z),
        (cx + dx1, cy + dy1, cz - half_z),
        (cx - dx1, cy + dy1, cz - half_z),
        (cx - dx2, cy - dy2, cz + half_z),
        (cx + dx2, cy - dy2, cz + half_z),
        (cx + dx2, cy + dy2, cz + half_z),
        (cx - dx2, cy + dy2, cz + half_z),
    ]
    faces = [
        4, 0, 3, 2, 1,
        4, 4, 5, 6, 7,
        4, 0, 1, 5, 4,
        4, 1, 2, 6, 5,
        4, 2, 3, 7, 6,
        4, 3, 0, 4, 7,
    ]
    return pv.PolyData(points, faces)


def pyvista_available() -> tuple[bool, str]:
    if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen" and os.environ.get("G4USIM_ENABLE_OFFSCREEN_PYVISTA") != "1":
        return False, "PyVistaQt preview is disabled for QT_QPA_PLATFORM=offscreen; using text fallback."
    try:
        import pyvista  # noqa: F401, PLC0415
        import pyvistaqt  # noqa: F401, PLC0415
        import vtk  # noqa: F401, PLC0415
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
