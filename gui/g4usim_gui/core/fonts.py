"""Presentation fonts shared by Qt, Matplotlib and optional VTK text.

No font is bundled or installed. Missing proprietary fonts use installed CJK
alternatives and finally the renderer's ordinary sans-serif fallback.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

UI_FONT_FAMILIES = (
    "Microsoft YaHei", "Microsoft YaHei UI", "Noto Sans CJK SC",
    "Source Han Sans SC", "SimHei", "PingFang SC", "WenQuanYi Zen Hei",
)


def preferred_font_families(available, fallback=()):
    installed = set(available)
    return list(dict.fromkeys([
        *(name for name in UI_FONT_FAMILIES if name in installed), *fallback,
    ]))


@lru_cache(maxsize=1)
def vtk_font_file() -> str | None:
    """VTK only accepts built-in families or an explicit FreeType font file.

    Matplotlib's cross-platform font inventory resolves the actual installed
    file (including Windows TTC). This is lazy: Qt-only startup need not load it.
    """
    from matplotlib import font_manager

    installed = {entry.name for entry in font_manager.fontManager.ttflist}
    for family in (*UI_FONT_FAMILIES, "DejaVu Sans"):
        if family in installed:
            path = font_manager.findfont(
                font_manager.FontProperties(family=family), fallback_to_default=False)
            if Path(path).is_file():
                return str(path)

    return None


def style_vtk_axes(axes) -> None:
    """Apply the same file to the three VTK caption actors, not Qt widgets."""
    font_file = vtk_font_file()
    if font_file:
        from vtkmodules.vtkCommonCore import VTK_FONT_FILE

        for caption in (axes.GetXAxisCaptionActor2D(), axes.GetYAxisCaptionActor2D(),
                        axes.GetZAxisCaptionActor2D()):
            prop = caption.GetCaptionTextProperty()
            prop.SetFontFamily(VTK_FONT_FILE)
            prop.SetFontFile(font_file)


def configure_numeric_display(root) -> None:
    """Set ASCII numeric display on a UI root before constructing its children.

    This is a QWidget locale only: never change QLocale's process default, which
    remains responsible for interpreting pre-existing F5 localized raw drafts.
    Theme and language changes must not call this helper on existing editors.
    """
    from PySide6.QtCore import QLocale
    root.setLocale(QLocale.c())
