from __future__ import annotations

from PySide6.QtWidgets import QApplication

from g4usim_gui.main_window import MainWindow


def run_app(argv: list[str]) -> int:
    """Create and run the Qt application."""
    app = QApplication(argv)
    app.setApplicationName("G4UniversalSim Runner")
    app.setOrganizationName("G4UniversalSim")

    window = MainWindow()
    window.resize(1180, 760)
    window.show()
    return app.exec()
