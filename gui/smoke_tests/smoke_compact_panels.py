"""The compact band must not take away a panel the user just opened."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from g4usim_gui.core.theme import apply_theme
from gui_test_window import MainWindow


def settle(app):
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def resize(window, app, width, height=800):
    window.resize(width, height)
    settle(app)
    assert window.width() == width, (window.width(), width)


def main():
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("G4UniversalSimSmoke")
    app.setApplicationName("CompactOptionalPanels")
    settings = QSettings()
    settings.clear()
    apply_theme(app, "light")

    # 1. A panel opened inside the compact band survives every width step
    #    inside that band (the independent retest found 1200 -> 1205 hiding it).
    window = MainWindow()
    try:
        window.resize(1200, 800)
        window.show()
        settle(app)
        layout = window.workspace_layout
        ai = layout.docks["ai"]
        preview = layout.docks["preview"]
        assert ai.isHidden() and preview.isHidden(), \
            "first entry into the compact band still auto-hides the optional docks"

        ai.toggleViewAction().trigger()
        settle(app)
        assert not ai.isHidden(), "the AI panel opens from its own toggle action"
        resize(window, app, 1205)
        assert not ai.isHidden(), \
            "a resize inside the compact band keeps the AI panel the user just opened"
        resize(window, app, 1190, 760)
        assert not ai.isHidden(), "further in-band resizes keep the AI panel"
        resize(window, app, 1399, 900)
        assert not ai.isHidden(), "the band edge itself does not hide the AI panel"

        preview.toggleViewAction().trigger()
        settle(app)
        assert not preview.isHidden(), "the 3D panel opens inside the compact band"
        resize(window, app, 1230, 820)
        assert not preview.isHidden() and not ai.isHidden(), \
            "both optional panels survive an in-band resize"
        resize(window, app, 1500, 900)
        assert not preview.isHidden() and not ai.isHidden(), \
            "leaving the band keeps the user's own panel choices"

        # A user close is not undone by entering or leaving the band.
        ai.toggleViewAction().trigger()
        settle(app)
        assert ai.isHidden(), "the user can still close the AI panel"
        resize(window, app, 1200, 800)
        assert ai.isHidden(), "a panel the user closed stays closed the next time the band starts"
        resize(window, app, 1500, 900)
        assert ai.isHidden(), "leaving the band does not override a user close"
    finally:
        window.close()
        window.deleteLater()
        settle(app)

    # 2. Auto-hidden docks come back when the wide layout returns.
    settings.clear()  # closing a window saves its layout; start from the default here
    window = MainWindow()
    try:
        window.resize(1500, 900)
        window.show()
        settle(app)
        layout = window.workspace_layout
        preview = layout.docks["preview"]
        window.page_stack.setCurrentIndex(2)
        settle(app)
        assert preview.isVisible(), "the configuration page shows the 3D dock at full width"
        assert layout._optional_overrides.get("preview") is None
        resize(window, app, 1200, 800)
        assert preview.isHidden(), "entering the compact band auto-hides the 3D dock"
        assert "preview" in layout._auto_hidden
        resize(window, app, 1500, 900)
        assert preview.isVisible(), "leaving the band restores the dock it auto-hid"
    finally:
        window.close()
        window.deleteLater()
        settle(app)

    # 3. The configuration page button is an explicit choice too: the
    #    independent retest clicked "Show 3D view" at 1200 wide and lost the
    #    dock on 1200 -> 1205.
    settings.clear()
    window = MainWindow()
    try:
        window.resize(1500, 900)
        window.show()
        settle(app)
        window.page_stack.setCurrentIndex(2)
        settle(app)
        layout = window.workspace_layout
        preview = layout.docks["preview"]
        config = window.config_builder_page
        resize(window, app, 1200, 800)
        assert preview.isHidden(), "the band start still closes the 3D dock"
        index = config.preview3d_tab_index()
        tabs = config.workspace_tabs
        tabs.setCurrentIndex(index)
        settle(app)
        anchor = tabs.widget(index)
        buttons = anchor.findChildren(QPushButton) if hasattr(anchor, "findChildren") else []
        show_buttons = [b for b in buttons if b.property("workspaceText") == "Show 3D view"]
        assert len(show_buttons) == 1, [b.text() for b in buttons]
        button = show_buttons[0]
        assert button.isVisibleTo(window) and button.isEnabled(), "Show 3D view is usable in the band"
        button.click()
        settle(app)
        assert not preview.isHidden(), "the button opens the 3D dock"
        resize(window, app, 1205, 800)
        assert not preview.isHidden(), "1200 -> 1205 keeps the dock opened by the button"
        resize(window, app, 1399, 900)
        assert not preview.isHidden(), "the band edge keeps the dock opened by the button"
        resize(window, app, 1500, 900)
        assert not preview.isHidden(), "leaving the band keeps the button choice"
    finally:
        window.close()
        window.deleteLater()
        settle(app)

    # 4. A saved layout that shows the AI panel restores the user's choice for
    #    the whole band; 1205 -> 1211 must not hide it again.
    settings.clear()
    window = MainWindow()
    try:
        window.resize(1500, 900)
        window.show()
        settle(app)
        layout = window.workspace_layout
        ai = layout.docks["ai"]
        resize(window, app, 1205, 800)
        ai.toggleViewAction().trigger()
        settle(app)
        assert not ai.isHidden(), "AI opens before the layout is saved"
        assert layout.save(), "the shown layout is saved"
        ai.toggleViewAction().trigger()
        settle(app)
        assert ai.isHidden(), "the user can close the AI panel after saving"
        assert layout.restore(), "the saved layout restores"
        settle(app)
        assert not ai.isHidden(), "the saved layout brings the AI panel back"
        resize(window, app, 1211, 800)
        assert not ai.isHidden(), "a resize after restore keeps the restored AI panel"
        resize(window, app, 1399, 900)
        assert not ai.isHidden(), "the band edge keeps the restored AI panel"
    finally:
        window.close()
        window.deleteLater()
        settle(app)

    # 5. The other direction: a layout that saves the AI panel hidden must not
    #    make it appear when the band is resized.
    settings.clear()
    window = MainWindow()
    try:
        window.resize(1500, 900)
        window.show()
        settle(app)
        layout = window.workspace_layout
        ai = layout.docks["ai"]
        if not ai.isHidden():
            ai.toggleViewAction().trigger()
            settle(app)
        assert ai.isHidden(), "AI is hidden before the hidden layout is saved"
        assert layout.save(), "the hidden layout is saved"
        resize(window, app, 1205, 800)
        ai.toggleViewAction().trigger()
        settle(app)
        assert not ai.isHidden(), "the user opens AI after saving the hidden layout"
        assert layout.restore(), "the hidden layout restores"
        settle(app)
        assert ai.isHidden(), "the saved hidden state wins over the transient open"
        resize(window, app, 1216, 800)
        assert ai.isHidden(), "a resize after restoring a hidden layout keeps it hidden"
    finally:
        window.close()
        window.deleteLater()
        settle(app)

    print("compact_panels: ok")


if __name__ == "__main__":
    main()
