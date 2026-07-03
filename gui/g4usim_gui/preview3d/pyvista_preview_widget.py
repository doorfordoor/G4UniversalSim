from __future__ import annotations

import os

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from g4usim_gui.preview3d.geometry_primitives import add_vec3, scale_vec3, scene_extent
from g4usim_gui.preview3d.scene_model import PreviewScene, PreviewVolume
from g4usim_gui.preview3d.units import perpendicular_basis


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
        if not volume.size_mm or not volume.position_mm:
            return
        mesh = self._make_volume_mesh(volume)
        if mesh is None:
            return
        color, opacity, style = _style(volume)
        self._plotter.add_mesh(mesh, color=color, opacity=opacity, style=style, show_edges=True)
        if self._show_labels and volume.role != "world":
            label = volume.name
            if volume.sensitive:
                label += " [S]"
            if volume.bias:
                label += " [B]"
            self._plotter.add_point_labels([volume.position_mm], [label], point_size=0, font_size=12)

    def _make_volume_mesh(self, volume: PreviewVolume):
        sx, sy, sz = volume.size_mm
        px, py, pz = volume.position_mm
        shape = volume.shape.lower()
        if shape == "box":
            mesh = self._pv.Box(bounds=(px - sx / 2, px + sx / 2, py - sy / 2, py + sy / 2, pz - sz / 2, pz + sz / 2))
        elif shape in {"tubs", "cylinder"}:
            radius = volume.parameters_mm[1] if len(volume.parameters_mm) >= 2 else max(sx, sy) / 2
            height = 2.0 * volume.parameters_mm[2] if len(volume.parameters_mm) >= 3 else sz
            mesh = self._pv.Cylinder(center=volume.position_mm, direction=(0.0, 0.0, 1.0), radius=radius, height=height, resolution=64)
        elif shape in {"sphere", "orb"}:
            radius = max(sx, sy, sz) / 2
            mesh = self._pv.Sphere(radius=radius, center=volume.position_mm, theta_resolution=48, phi_resolution=24)
        elif shape == "cone":
            radius = max(sx, sy) / 2
            height = sz
            mesh = self._pv.Cone(center=volume.position_mm, direction=(0.0, 0.0, 1.0), height=height, radius=radius, resolution=64)
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
