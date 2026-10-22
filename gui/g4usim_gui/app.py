from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from g4usim_gui.core.i18n import default_language, normalize_language, set_application_language
from g4usim_gui.core.theme import apply_theme
from g4usim_gui.main_window import MainWindow


def run_app(argv: list[str]) -> int:
    """Create and run the Qt application."""
    if "--self-test" in argv:
        return self_test(argv)
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


def self_test(argv: list[str]) -> int:
    """--self-test <report.json>: build the main window off screen and report the install layout.

    A packaged (frozen, windowed) GUI has no console, so the report goes to a file; the
    package build uses it to check that the frozen GUI starts and finds its backend.
    """
    import json
    import os
    from pathlib import Path

    from g4usim_gui.core import install_layout

    index = argv.index("--self-test")
    report_path = Path(argv[index + 1]) if index + 1 < len(argv) else Path("gui_self_test.json")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([argv[0]])
    app.setApplicationName("G4UniversalSim Runner SelfTest")
    app.setOrganizationName("G4UniversalSim")
    report = {"schema": "g4usim_gui_self_test_v1", "frozen": install_layout.is_frozen(),
              "application_root": str(install_layout.application_root()),
              "default_backend": install_layout.default_backend_executable(),
              "runs_root": str(install_layout.default_runs_root()),
              "script_python": install_layout.script_python()}
    try:
        window = MainWindow()
        report["pages"] = window.page_stack.count()
        report["plots"] = window.output_page.plot_panel is not None
        try:
            import pyvista  # noqa: F401
            report["preview3d"] = True
        except ImportError:
            report["preview3d"] = False
        from g4usim_gui.core.i18n import ui_text
        set_application_language(app, "zh_CN")
        report["zh_CN"] = ui_text("Parameter Scans")
        window.close()
        report["ok"] = True
    except Exception as error:   # the report must say why the GUI cannot start
        report["ok"] = False
        report["error"] = f"{type(error).__name__}: {error}"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if report["ok"] else 1
