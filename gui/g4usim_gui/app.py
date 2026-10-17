from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from g4usim_gui.core.i18n import default_language, normalize_language, set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.main_window import MainWindow


def run_app(argv: list[str]) -> int:
    """Create and run the Qt application."""
    app = QApplication(argv)
    app.setApplicationName("G4UniversalSim Runner")
    app.setOrganizationName("G4UniversalSim")
    app.setStyle("Fusion")

    settings = QSettings()
    theme_mode = str(settings.value("appearance/theme", "light"))
    if theme_mode not in {"light", "dark", "system"}:
        theme_mode = "light"
    apply_theme(app, theme_mode)
    language = normalize_language(settings.value("appearance/language", default_language()))
    set_application_language(app, language)

    window = MainWindow()
    window.show()
    return app.exec()
