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
    exit_code = app.exec()
    # Destroy the window tree while the QApplication is still alive. PySide runs
    # destroyQCoreApplication() during interpreter finalisation and walks every
    # object it still owns; a widget tree that contains a matplotlib canvas can be
    # double-deleted there (observed as SIGSEGV in QObject::~QObject on Linux).
    window.close()
    window.deleteLater()
    app.processEvents()
    return exit_code


def _close_self_test_window(window, app, *, timeout: float = 10.0) -> bool:
    """Let the normal asynchronous close finish before deleting native widgets."""
    import time
    from PySide6.QtCore import QCoreApplication, QEvent
    accepted = window.close()
    deadline = time.monotonic() + timeout
    while not accepted and time.monotonic() < deadline:
        app.processEvents()
        # The product schedules its own close when evidence jobs finish. The
        # self-test starts with a shown window, so hiding marks that accepted close.
        accepted = not window.isVisible()
        if not accepted:
            time.sleep(0.01)
    if accepted:
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    return accepted


def self_test(argv: list[str]) -> int:
    """--self-test <report.json>: build the main window off screen and report the install layout.

    A packaged (frozen, windowed) GUI has no console, so the report goes to a file; the
    package build uses it to check that the frozen GUI starts and finds its backend.
    """
    import json
    import os
    import tempfile
    import shutil
    from pathlib import Path

    from g4usim_gui.core import install_layout

    index = argv.index("--self-test")
    report_path = Path(argv[index + 1]) if index + 1 < len(argv) else Path("gui_self_test.json")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([argv[0]])
    app.setApplicationName("G4UniversalSim Runner SelfTest")
    app.setOrganizationName("G4UniversalSimSelfTest")
    # Package checks must not restore or rewrite the user's projects, recovery
    # copies, history or desktop preferences.
    state_root = Path(tempfile.mkdtemp(prefix="g4usim-gui-selftest-state-"))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(state_root / "settings"))
    from g4usim_gui.history import run_history_store
    run_history_store.STATE_PATH = state_root / "history.json"
    os.environ["G4USIM_RECOVERY_DIR"] = str(state_root / "recovery")
    app.setStyle("Fusion")
    apply_theme(app, "light")
    report = {"schema": "g4usim_gui_self_test_v1", "frozen": install_layout.is_frozen(),
              "application_root": str(install_layout.application_root()),
              "default_backend": install_layout.default_backend_executable(),
              "runs_root": str(install_layout.default_runs_root()),
              "script_python": install_layout.script_python()}
    window = None
    try:
        window = MainWindow(offer_recovery=False)
        # Exercise the real shown-window lifecycle, also on the offscreen Qt
        # platform. A never-shown restored dock tree has a different teardown.
        window.show()
        app.processEvents()
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
        report["ok"] = True
    except Exception as error:   # the report must say why the GUI cannot start
        report["ok"] = False
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        closed = True
        if window is not None:
            closed = _close_self_test_window(window, app)
            if not closed:
                report["ok"] = False
                report["error"] = "Main window did not finish self-test shutdown before the deadline"
                report["retained_state_directory"] = str(state_root)
        if closed:
            shutil.rmtree(state_root)
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return 0 if report["ok"] else 1
