"""Static contract for the appearance registry and its accessibility floor.

Run directly (``python -B scripts/test_theme_registry.py``) or through the unified
runner, which records the executed assertions. The test is deliberately independent of
the window: the registry, persistence and the applied theme must be correct before a
single page is built.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gui"))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core import theme  # noqa: E402


def _application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([sys.argv[0]])
        app.setStyle("Fusion")
    return app


def test_registry_shape() -> None:
    skins = theme.SKINS
    assert len(skins) == 15, sorted(skins)
    assert len(set(skins)) == 15
    names = [candidate.name for candidate in skins.values()]
    assert len(set(names)) == 15, names
    assert all(candidate.description.strip() for candidate in skins.values())
    assert all(len(candidate.series) == 6 for candidate in skins.values())
    for candidate in skins.values():
        assert candidate.mode in ("light", "dark"), candidate.id
        for color in candidate.series:
            assert theme.contrast_ratio(color, color) == 1.0
    assert all(skin.mode == "light" for skin in theme.skins_for_mode("light"))
    assert all(skin.mode == "dark" for skin in theme.skins_for_mode("dark"))
    assert len(theme.LIGHT_SKIN_IDS) == 8
    assert len(theme.DARK_SKIN_IDS) == 7
    assert theme.LIGHT_SKIN_IDS + theme.DARK_SKIN_IDS == theme.SKIN_IDS
    for legacy in ("B", "K", "C"):
        assert legacy in theme.SKINS, legacy
    assert theme.skin("B") is theme.SKINS["B"]
    assert theme.skin("B").colors is theme.B
    assert theme.skin("K").colors is theme.K
    assert theme.skin("C").colors is theme.C
    assert theme.PALETTES == {"B": theme.B, "K": theme.K, "C": theme.C}
    assert theme.DEFAULT_LIGHT_SKIN in theme.LIGHT_SKIN_IDS
    assert theme.DEFAULT_DARK_SKIN in theme.DARK_SKIN_IDS
    assert theme.skin("nope") is None
    assert theme.skin(None) is None


def test_contrast_floor() -> None:
    # WCAG 1.4.3 for text and 1.4.11 for component boundaries; see the J3 contract.
    checks = (
        ("text on canvas", lambda c: (c.text, c.canvas), 4.5),
        ("text on surface", lambda c: (c.text, c.surface), 4.5),
        ("text on canvas_alt", lambda c: (c.text, c.canvas_alt), 4.5),
        ("muted on canvas", lambda c: (c.text_muted, c.canvas), 4.5),
        ("muted on surface", lambda c: (c.text_muted, c.surface), 4.5),
        ("muted on canvas_alt", lambda c: (c.text_muted, c.canvas_alt), 4.5),
        ("muted on surface_alt", lambda c: (c.text_muted, c.surface_alt), 4.5),
        ("accent text", lambda c: (theme.on_accent(c), c.accent), 4.5),
        ("accent on canvas", lambda c: (c.accent, c.canvas), 3.0),
        ("accent on surface", lambda c: (c.accent, c.surface), 3.0),
        ("accent on soft chip", lambda c: (c.accent, c.accent_soft), 4.5),
        ("success", lambda c: (c.success, c.surface), 4.5),
        ("warning", lambda c: (c.warning, c.surface), 4.5),
        ("danger", lambda c: (c.danger, c.surface), 4.5),
        ("info", lambda c: (c.info, c.surface), 4.5),
        ("control boundary", lambda c: (c.border_strong, c.surface), 3.0),
        ("input boundary", lambda c: (c.border_strong, c.input), 3.0),
        ("focus ring", lambda c: (c.focus_ring, c.surface), 3.0),
        ("focus ring on canvas", lambda c: (c.focus_ring, c.canvas), 3.0),
        ("selection text", lambda c: (c.selection, c.text), 4.5),
        ("sidebar text", lambda c: (c.sidebar_text, c.sidebar), 4.5),
        ("sidebar hint", lambda c: (c.sidebar_muted, c.sidebar), 4.5),
        ("selected row", lambda c: (c.sidebar_selected, c.sidebar), 1.15),
    )
    for candidate in theme.SKINS.values():
        for label, getter, target in checks:
            first, second = getter(candidate.colors)
            ratio = theme.contrast_ratio(first, second)
            assert ratio >= target, f"{candidate.id}: {label} {ratio:.2f} < {target}"
        # The chips paint semantic text on a tinted veil, not on the bare surface.
        # B/K/botanical used to be 4.35/4.35/4.31 here while passing the surface checks.
        for role, (first, second) in theme.status_combinations(candidate.colors).items():
            ratio = theme.contrast_ratio(first, second)
            assert ratio >= 4.5, f"{candidate.id}: status {role} {ratio:.2f} < 4.5"


def test_colour_maths() -> None:
    assert theme.mix("#000000", "#ffffff", 1.0) == "#000000"
    assert theme.mix("#000000", "#ffffff", 0.0) == "#ffffff"
    assert theme.contrast_ratio("#000000", "#ffffff") == 21.0
    assert theme.contrast_ratio("#ffffff", "#ffffff") == 1.0
    assert theme.contrast_ratio("#777777", "#000000") == theme.contrast_ratio("#000000", "#777777")
    dark = theme.SKINS["C"].colors
    light = theme.SKINS["B"].colors
    assert theme.on_color("#102030") == "#ffffff"
    assert theme.on_color("#f0f0f0") == "#0b1214"
    # on_color must always pick the better of the two fixed text colours.
    for sample in ("#0e7c86", "#5b9dff", "#e0a458", "#f6e7c1", "#123456", "#abcdef"):
        chosen = theme.contrast_ratio(theme.on_color(sample), sample)
        white = theme.contrast_ratio("#ffffff", sample)
        black = theme.contrast_ratio("#0b1214", sample)
        assert chosen >= max(white, black) - 0.01, sample
    assert theme.on_accent(dark) == "#0b1214"
    assert theme.on_accent(light) == "#ffffff"
    # veil_text keeps an already readable colour and lightens/darkens only when needed.
    assert theme.veil_text("#000000", "#ffffff") == "#000000"
    fixed = theme.veil_text("#2b7b55", "#e3eee9")
    assert fixed != "#2b7b55"
    assert theme.contrast_ratio(fixed, "#e3eee9") >= 4.6


def test_persistence_migration() -> None:
    root = ROOT / "out" / "verification" / "theme-registry-test"
    root.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(root / "appearance.ini"), QSettings.IniFormat)
    settings.clear()
    mode, light, dark = theme.stored_appearance(settings)
    assert (mode, light, dark) == ("light", "B", "C")

    settings.setValue("appearance/light_palette", "K")
    assert theme.stored_appearance(settings)[:2] == ("light", "K")

    settings.setValue("appearance/light_skin", "paper")
    mode, light, dark = theme.stored_appearance(settings)
    assert (light, dark) == ("paper", "C")

    settings.setValue("appearance/dark_skin", "midnight")
    assert theme.stored_appearance(settings)[1:] == ("paper", "midnight")

    settings.setValue("appearance/light_skin", "C")  # dark skin in the light slot
    settings.setValue("appearance/dark_skin", "K")  # light skin in the dark slot
    settings.setValue("appearance/theme", "sepia")
    mode, light, dark = theme.stored_appearance(settings)
    assert (mode, light, dark) == ("light", "B", "C")

    settings.setValue("appearance/theme", "system")
    assert theme.stored_appearance(settings)[0] == "system"

    theme.persist_appearance(settings, "K", "slate")
    assert settings.value("appearance/light_skin") == "K"
    assert settings.value("appearance/dark_skin") == "slate"
    assert settings.value("appearance/light_palette") == "K"
    theme.persist_appearance(settings, "paper", "slate")
    assert settings.value("appearance/light_palette") == "K"  # not overwritten by new ids


def test_apply_contract() -> None:
    app = _application()
    settings = QSettings(str(ROOT / "out" / "verification" / "theme-registry-test" / "apply.ini"),
                         QSettings.IniFormat)
    settings.clear()
    try:
        theme.apply_theme(app, "sepia")  # type: ignore[arg-type]
    except ValueError:
        pass
    else:
        raise AssertionError("unknown theme mode must raise")

    try:
        theme.apply_theme(app, "light", "nope")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown palette must raise")

    theme.apply_theme(app, "light", "K")
    assert theme.current_colors() is theme.K
    assert app.property("lightThemePalette") == "K"
    theme.apply_theme(app, "dark", "C")
    assert theme.current_colors() is theme.C
    assert app.property("lightThemePalette") == "K"  # choosing dark keeps the light choice
    theme.apply_theme(app, "system")
    assert theme.current_colors() in (theme.K, theme.C)
    assert app.property("lightThemePalette") == "K"
    theme.apply_theme(app, "light")
    assert theme.current_colors() is theme.K
    theme.apply_theme(app, "light", "B")
    assert theme.current_colors() is theme.B

    theme.apply_theme(app, "light", light_skin="paper", dark_skin="midnight")
    assert theme.current_colors() is theme.SKINS["paper"].colors
    assert app.property("lightSkinId") == "paper"
    assert app.property("darkSkinId") == "midnight"
    assert app.property("resolvedSkin") == "paper"
    theme.apply_theme(app, "dark")
    assert theme.current_colors() is theme.SKINS["midnight"].colors
    assert app.property("resolvedSkin") == "midnight"
    theme.apply_theme(app, "light")  # back to the remembered light skin
    assert theme.current_colors() is theme.SKINS["paper"].colors
    theme.apply_theme(app, "light", "B")


def test_stylesheets() -> None:
    for candidate in theme.SKINS.values():
        sheet = theme.build_stylesheet(candidate.colors)
        assert "$" not in sheet, f"{candidate.id}: unsubstituted style token"
        assert "QWidget" in sheet
        assert candidate.colors.canvas in sheet
        assert candidate.colors.text in sheet
        assert "url(" in sheet  # combo/check icons are real files


if __name__ == "__main__":
    test_registry_shape()
    test_contrast_floor()
    test_colour_maths()
    test_persistence_migration()
    test_apply_contract()
    test_stylesheets()
    print("theme registry: OK")
