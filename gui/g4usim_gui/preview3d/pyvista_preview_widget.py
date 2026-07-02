from __future__ import annotations

import os

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from g4usim_gui.preview3d.geometry_primitives import add_vec3, scale_vec3, scene_extent
from g4usim_gui.preview3d.scene_model import PreviewScene, PreviewVolume


class PyVistaPreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import pyvista as pv  # noqa: PLC0415
        from pyvistaqt import QtInteractor  # noqa: PLC0415

        self._pv = pv
        self._plotter = QtInteractor(self)
        self._show_source = True
        self._show_labels = True
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._plotter, 1)
        layout.addWidget(self.status)

    def clear(self) -> None:
        self._plotter.clear()
        self.status.clear()

    def reset_camera(self) -> None:
        self._plotter.reset_camera()
        self._plotter.render()

    def set_show_source(self, show: bool) -> None:
        self._show_source = show

    def set_show_labels(self, show: bool) -> None:
        self._show_labels = show

    def render_scene(self, scene: PreviewScene) -> None:
        try:
            self.clear()
            for volume in scene.volumes:
                self._add_volume(volume)
            if self._show_source and scene.source.position_mm and scene.source.direction:
                self._add_source(scene)
            if scene.bounds_mm:
                self._plotter.show_bounds(grid="front", location="outer")
            self._plotter.add_axes()
            self._plotter.reset_camera()
            self._plotter.render()
            messages = scene.errors or scene.warnings
            self.status.setText("\n".join(messages[:8]) if messages else "3D Preview: OK")
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"3D render failed: {exc}")

    def _add_volume(self, volume: PreviewVolume) -> None:
        if volume.shape.lower() != "box" or not volume.size_mm or not volume.position_mm:
            return
        sx, sy, sz = volume.size_mm
        px, py, pz = volume.position_mm
        mesh = self._pv.Box(bounds=(px - sx / 2, px + sx / 2, py - sy / 2, py + sy / 2, pz - sz / 2, pz + sz / 2))
        color, opacity, style = _style(volume)
        self._plotter.add_mesh(mesh, color=color, opacity=opacity, style=style, show_edges=True)
        if self._show_labels and volume.role != "world":
            label = volume.name
            if volume.sensitive:
                label += " [S]"
            if volume.bias:
                label += " [B]"
            self._plotter.add_point_labels([volume.position_mm], [label], point_size=0, font_size=12)

    def _add_source(self, scene: PreviewScene) -> None:
        start = scene.source.position_mm
        direction = scene.source.direction
        if not start or not direction:
            return
        length = scene_extent(scene.bounds_mm) * 0.35
        end = add_vec3(start, scale_vec3(direction, length))
        arrow = self._pv.Arrow(start=start, direction=direction, tip_length=0.25, tip_radius=0.06 * length, shaft_radius=0.015 * length, scale=length)
        self._plotter.add_mesh(arrow, color="red")
        if self._show_labels:
            self._plotter.add_point_labels([end], [f"{scene.source.particle} {scene.source.energy}"], point_size=0, font_size=12)


def _style(volume: PreviewVolume) -> tuple[str, float, str]:
    if volume.role == "world":
        return ("white", 0.08, "wireframe")
    if volume.sensitive and volume.bias:
        return ("magenta", 0.45, "surface")
    if volume.sensitive:
        return ("dodgerblue", 0.55, "surface")
    if volume.bias:
        return ("orange", 0.45, "surface")
    if volume.role == "layer":
        return ("lightgray", 0.65, "surface")
    if volume.role == "boolean_tool":
        return ("crimson", 0.25, "wireframe")
    return ("lightblue", 0.55, "surface")


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
