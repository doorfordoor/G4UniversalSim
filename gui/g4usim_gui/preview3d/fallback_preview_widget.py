from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from g4usim_gui.core.i18n import ui_format
from g4usim_gui.preview3d.backend_mesh import BackendMesh
from g4usim_gui.preview3d.scene_model import PreviewScene


class FallbackPreviewWidget(QWidget):
    volumeSelected = Signal(str)   # same interface as the 3D widget; text has nothing to click
    def __init__(self, parent: QWidget | None = None, reason: str = "") -> None:
        super().__init__(parent)
        self.reason = reason
        layout = QVBoxLayout(self)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.banner)
        layout.addWidget(self.text, 1)
        self._set_banner()

    def _set_banner(self) -> None:
        reason = f"\nReason: {self.reason}" if self.reason else ""
        self.banner.setText(
            "3D preview dependencies are optional and are not currently available."
            f"{reason}\nInstall with: pip install -r requirements-3d.txt"
        )

    def render_scene(self, scene: PreviewScene) -> None:
        self.text.setPlainText("\n".join(scene.summary_lines()))

    def render_backend_mesh(self, mesh: BackendMesh) -> None:
        lines = [ui_format("Backend geometry: {count} volume copies from Geant4.", count=len(mesh.volumes))]
        for volume in mesh.volumes:
            lines.append(f"{'  ' * volume.depth}{volume.path}  {volume.solid}  {volume.material}  "
                         f"{volume.cubic_volume_mm3:.6g} mm3{'  sensitive' if volume.sensitive else ''}")
        self.text.setPlainText("\n".join(lines))

    def clear(self) -> None:
        self.text.clear()

    def reset_camera(self) -> None:
        # Text fallback has no camera; keep this method so toolbar actions are safe.
        return

    def set_show_source(self, show: bool) -> None:
        return

    def set_show_labels(self, show: bool) -> None:
        return

    def select_volume(self, name: str) -> None:
        return

    def show_trajectories(self, trajectories) -> None:
        """Without 3D: a text summary of the loaded tracks."""
        lines = [f"Tracks of run {trajectories.run}: {len(trajectories.events)} events"]
        lines += [f"  {particle}: {count} tracks" for particle, count in trajectories.particles().items()]
        self.text.appendPlainText("\n".join(lines))

    def clear_trajectories(self) -> None:
        return
