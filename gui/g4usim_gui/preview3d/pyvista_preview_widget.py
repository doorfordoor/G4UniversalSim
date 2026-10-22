from __future__ import annotations

import math
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from g4usim_gui.core.i18n import ui_format, ui_text
from g4usim_gui.core.theme import current_colors
from g4usim_gui.preview3d.backend_mesh import BackendMesh
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
        self.status.setMaximumHeight(34)
        self.status.setProperty("uiRole", "hint")
        # until the first render the (black) render window is replaced by a hint
        self.empty = QLabel(ui_text("Press Refresh Preview to draw the editor geometry, or Show Backend "
                                    "Geometry for the geometry Geant4 builds."))
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setProperty("uiRole", "emptyState")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self._plotter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack, 1)
        layout.addWidget(self.status)
        self.set_theme()

    def set_theme(self) -> None:
        colors = current_colors()
        self._plotter.set_background(colors.surface_alt)
        self._plotter.render()

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
        self.stack.setCurrentWidget(self._plotter)
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
            if scene.errors:
                summary = ui_format(
                    "Rendered with {errors} error(s) and {warnings} warning(s).",
                    errors=len(scene.errors),
                    warnings=len(scene.warnings),
                )
            elif scene.warnings:
                summary = ui_format("Rendered with {warnings} warning(s).", warnings=len(scene.warnings))
            else:
                summary = ui_text("3D Preview: OK")
            self.status.setText(summary)
            self.status.setToolTip("\n".join([*scene.errors, *scene.warnings][:12]))
        except Exception as exc:  # noqa: BLE001
            self.status.setText(f"3D render failed: {exc}")

    def render_backend_mesh(self, mesh: BackendMesh) -> None:
        """Show the geometry Geant4 built (exportMesh), not the editor approximation."""
        self.stack.setCurrentWidget(self._plotter)
        try:
            self.clear()
            for volume in mesh.volumes:
                if not volume.vertices or not volume.faces:
                    continue
                faces: list[int] = []
                for face in volume.faces:
                    faces.extend((len(face), *face))
                poly = self._pv.PolyData(volume.vertices, faces)
                if volume.depth == 0:
                    color, opacity, style = ("white", 0.08, "wireframe")
                elif volume.sensitive:
                    color, opacity, style = ("dodgerblue", 0.55, "surface")
                else:
                    color, opacity, style = ("lightblue", 0.4, "surface")
                self._plotter.add_mesh(poly, color=color, opacity=opacity, style=style, show_edges=True)
            self._plotter.add_axes()
            self._plotter.reset_camera()
            self._plotter.render()
            self.status.setText(ui_format("Backend geometry: {count} volume copies from Geant4.", count=len(mesh.volumes)))
            self.status.setToolTip(mesh.source_file)
        except Exception as exc:  # noqa: BLE001
            self.status.setText(ui_format("Backend geometry render failed: {reason}", reason=exc))

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
