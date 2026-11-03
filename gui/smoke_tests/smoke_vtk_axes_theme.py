"""The XYZ captions of the 3D preview stay readable on every skin (J3 N1).

The bug: PyVista creates the axes marker with black caption text.  ``style_vtk_axes``
only set the presentation font, so after switching from a light to a dark skin the
captions stayed black on a dark canvas (J3 N1 review, ``axis-probe`` recorded
``[0, 0, 0]`` for all three captions).

Two explicit modes; there is no silent skip that could pass for acceptance:

``--objects-only`` (default)
    No window, no rendered frame: the caption colour maths on every registered skin,
    a real ``pyvista.create_axes_marker()`` actor and a real renderer styled through
    the production ``fonts.style_vtk_axes`` (creation, theme switch, rebuild), and a
    real ``pyvista.Plotter`` clearing an existing orientation marker.  Creating these
    VTK objects needs no OpenGL context.  A missing VTK or broken object is a failure,
    not a skip.

``--native``
    Additionally drives the real ``PyVistaPreviewWidget``: render a scene, switch
    skins, ``clear()``, switch again, rebuild the scene and check the captions, the
    arrow colours and the camera each time.  Requires a real display: with Qt's
    offscreen platform VTK fails to get a pixel format on Windows and the process
    crashes, so this mode must run with ``QT_QPA_PLATFORM`` unset, and it fails
    instead of skipping when there is no display.

The ``getsource`` checks in ``check_wiring`` are supplementary: they document the
production call sites, while the real VTK objects and (in ``--native``) the real
widget provide the behaviour.
"""

from __future__ import annotations

import argparse
import os
import sys
from inspect import getsource
from pathlib import Path

GUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GUI))

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from g4usim_gui.core import fonts, theme  # noqa: E402
from g4usim_gui.preview3d import pyvista_preview_widget as preview_module  # noqa: E402

THEME_SEQUENCE = ("paper", "circuit", "contrast_light")
AXIS_CHANNELS = ("X", "Y", "Z")


def rgb(colour: str) -> tuple[float, float, float]:
    value = QColor(colour)
    return value.redF(), value.greenF(), value.blueF()


def assert_rgb(actual, expected, label: str) -> None:
    for got, want, channel in zip(actual, expected, "rgb"):
        assert abs(got - want) < 1e-6, f"{label} {channel}: {got!r} != {want!r}"


def caption_text_properties(axes) -> list:
    return [
        axes.GetXAxisCaptionActor2D().GetCaptionTextProperty(),
        axes.GetYAxisCaptionActor2D().GetCaptionTextProperty(),
        axes.GetZAxisCaptionActor2D().GetCaptionTextProperty(),
    ]


def arrow_colours(axes) -> dict[str, tuple[tuple[float, float, float], ...]]:
    """The three arrow colours; the theme must only touch the caption text."""
    return {
        channel: (tuple(getattr(axes, f"Get{channel}AxisShaftProperty")().GetColor()),
                  tuple(getattr(axes, f"Get{channel}AxisTipProperty")().GetColor()))
        for channel in AXIS_CHANNELS
    }


def assert_arrow_colours(axes, baseline, label: str) -> None:
    current = arrow_colours(axes)
    assert set(current) == set(baseline), label
    for channel in AXIS_CHANNELS:
        assert_rgb(current[channel][0], baseline[channel][0], f"{label} {channel} shaft")
        assert_rgb(current[channel][1], baseline[channel][1], f"{label} {channel} tip")


def apply_skin(app: QApplication, skin_id: str) -> str:
    """Apply one skin exactly as an appearance menu choice does; return its canvas."""
    skin = theme.SKINS[skin_id]
    light = skin_id if skin.mode == "light" else "paper"
    dark = skin_id if skin.mode == "dark" else "midnight"
    theme.apply_theme(app, skin.mode, light_skin=light, dark_skin=dark)
    assert theme.current_skin().id == skin_id, theme.current_skin().id
    return theme.current_colors(app)


# --------------------------------------------------------------------------- pure part


def check_caption_colour_maths() -> None:
    lowest = (999.0, "")
    for skin_id in theme.SKIN_IDS:
        skin = theme.SKINS[skin_id]
        colour = preview_module.axis_caption_colour(skin.colors)
        assert colour == theme.veil_text(
            skin.colors.text_muted, skin.colors.surface_alt,
            minimum=preview_module.AXIS_CAPTION_MINIMUM_CONTRAST), skin_id
        ratio = theme.contrast_ratio(colour, skin.colors.surface_alt)
        assert ratio >= 4.5, (skin_id, colour, round(ratio, 3))
        if ratio < lowest[0]:
            lowest = (ratio, skin_id)
    assert lowest[1], "no skins registered"
    print(f"caption colour: {len(theme.SKIN_IDS)} skins, lowest contrast {lowest[0]:.3f} ({lowest[1]})")


# ----------------------------------------------------------- real VTK object part


def check_real_axes_actor(app: QApplication) -> None:
    import pyvista  # noqa: PLC0415

    from vtkmodules.vtkRenderingCore import vtkRenderer  # noqa: PLC0415

    renderer = vtkRenderer()
    axes = pyvista.create_axes_marker()
    assert axes is not None
    # The bug: PyVista creates black captions; the styling must replace them.
    for prop in caption_text_properties(axes):
        assert tuple(prop.GetColor()) == (0.0, 0.0, 0.0), tuple(prop.GetColor())
    baseline = arrow_colours(axes)
    assert baseline["X"][0] != baseline["Y"][0] and baseline["Y"][0] != baseline["Z"][0], baseline
    assert_arrow_colours(axes, baseline, "created")

    expected_font = fonts.vtk_font_file()
    for skin_id in THEME_SEQUENCE:
        colors = apply_skin(app, skin_id)
        renderer.SetBackground(*rgb(colors.surface_alt))
        expected = preview_module.axis_caption_colour(colors)
        fonts.style_vtk_axes(axes, caption_colour=expected)      # theme switch on the same actor
        for prop in caption_text_properties(axes):
            assert_rgb(tuple(prop.GetColor()), rgb(expected), f"{skin_id} caption")
            if expected_font:
                from vtkmodules.vtkCommonCore import VTK_FONT_FILE  # noqa: PLC0415

                assert prop.GetFontFamily() == VTK_FONT_FILE, skin_id
                assert prop.GetFontFile() == expected_font, skin_id
        assert theme.contrast_ratio(expected, colors.surface_alt) >= 4.5, skin_id
        assert_arrow_colours(axes, baseline, skin_id)

    # ``caption_colour=None`` keeps the historical font-only behaviour.
    colours_before = [tuple(prop.GetColor()) for prop in caption_text_properties(axes)]
    fonts.style_vtk_axes(axes)
    assert [tuple(prop.GetColor()) for prop in caption_text_properties(axes)] == colours_before

    # A rebuilt scene gets a fresh actor, which the creation path must style too.
    rebuilt = pyvista.create_axes_marker()
    rebuilt_arrows = arrow_colours(rebuilt)
    expected = preview_module.axis_caption_colour()
    fonts.style_vtk_axes(rebuilt, caption_colour=expected)
    for prop in caption_text_properties(rebuilt):
        assert_rgb(tuple(prop.GetColor()), rgb(expected), "rebuilt caption")
    assert_arrow_colours(rebuilt, rebuilt_arrows, "rebuilt")
    print("real VTK axis actors: creation, theme switch and rebuild recolor captions; arrows keep their colors")


def check_real_plotter_clear() -> None:
    """``Plotter.clear()`` keeps the orientation marker; the widget relies on that."""
    import pyvista  # noqa: PLC0415

    plotter = pyvista.Plotter(off_screen=True)
    try:
        renderer = plotter.renderer
        actor = plotter.add_axes()
        widget = renderer.axes_widget
        assert widget is not None and widget.GetEnabled(), "add_axes must enable the marker"
        assert renderer.axes_actor is actor
        plotter.clear()
        assert renderer.axes_widget is widget, "Plotter.clear() must keep the axes widget"
        assert widget.GetEnabled(), "the orientation marker stays enabled after clear()"
        assert renderer.axes_actor is actor, "Plotter.clear() keeps the axis actor alive"
        recoloured = preview_module.axis_caption_colour(theme.SKINS[theme.DEFAULT_DARK_SKIN].colors)
        fonts.style_vtk_axes(actor, caption_colour=recoloured)      # what set_theme() does after clear
        assert_rgb(tuple(actor.GetXAxisCaptionActor2D().GetCaptionTextProperty().GetColor()),
                   rgb(recoloured), "post-clear caption")
        replacement = plotter.add_axes()
        assert replacement is not actor, "a new scene must get a new axes marker"
        assert renderer.axes_widget is not widget and renderer.axes_widget.GetEnabled()
    finally:
        plotter.close()
    print("real PyVista plotter: clear keeps the marker enabled, a new add_axes replaces it")


# --------------------------------------------------------------------------- wiring


def check_wiring() -> None:
    """Supplementary: the production call sites these behaviours rely on."""
    widget = preview_module.PyVistaPreviewWidget
    clear_source = getsource(widget.clear)
    assert "_axes_actor = None" not in clear_source, "clear() must keep the marker reference"
    assert "self._apply_axes_style()" in clear_source, "clear() must restyle the remaining marker"
    render_source = getsource(widget._render)
    assert "_axes_actor = None" not in render_source, "_render() must not drop the marker reference"
    assert "self._add_axes()" in render_source, "_render() must create the axes marker"
    add_source = getsource(widget._add_axes)
    assert "self._plotter.add_axes()" in add_source, "the marker comes from pyvista add_axes()"
    assert "self._apply_axes_style()" in add_source, "a new marker must be styled on creation"
    style_source = getsource(widget._apply_axes_style)
    assert "caption_colour=axis_caption_colour()" in style_source, "the style must carry the readable colour"
    theme_source = getsource(widget.set_theme)
    assert "_apply_axes_style()" in theme_source, "set_theme() must restyle the captions"
    print("wiring: marker reference survives clear(), new markers are styled, set_theme restyles")


# --------------------------------------------------------------------------- widget part


def check_widget_lifecycle(app: QApplication) -> None:
    """Rendered lifecycle; ``--native`` only, always cleaned up in ``finally``."""
    from g4usim_gui.editors.geometry_editor_model import GeometryDocument  # noqa: PLC0415
    from g4usim_gui.editors.source_physics_scoring_model import SourceEditableModel  # noqa: PLC0415
    from g4usim_gui.preview3d.pyvista_preview_widget import PyVistaPreviewWidget  # noqa: PLC0415
    from g4usim_gui.preview3d.scene_builder import build_preview_scene  # noqa: PLC0415

    document = GeometryDocument(mode="simple_box", is_dirty=True)
    document.simple_box.target_size = "10 cm, 10 cm, 2 cm"
    source = SourceEditableModel(position="0,0,-5 cm", direction="0,0,1")
    scene = build_preview_scene(document, source)

    widget = PyVistaPreviewWidget()
    try:
        widget.resize(900, 650)
        widget.show()
        app.processEvents()
        widget.render_scene(scene)
        app.processEvents()
        assert widget._axes_actor is not None
        assert widget.stack.currentWidget() is widget._plotter
        camera = widget._plotter.camera_position
        baseline = arrow_colours(widget._axes_actor)

        for skin_id in THEME_SEQUENCE:
            colors = apply_skin(app, skin_id)
            expected = preview_module.axis_caption_colour(colors)
            widget.set_theme()
            app.processEvents()
            for prop in caption_text_properties(widget._axes_actor):
                assert_rgb(tuple(prop.GetColor()), rgb(expected), f"widget {skin_id} caption")
            assert widget._plotter.camera_position == camera, "a skin must not move the camera"
            assert_arrow_colours(widget._axes_actor, baseline, f"widget {skin_id}")

        # clear() -> theme switch -> rebuild: the marker survives the clear and follows the skin.
        marker = widget._axes_actor
        widget.clear()
        app.processEvents()
        assert widget._axes_actor is marker, "clear() must keep the still-enabled marker reference"
        assert widget._plotter.renderer.axes_widget is not None
        assert widget._plotter.renderer.axes_widget.GetEnabled(), "pyvista clear keeps the marker"
        colors = apply_skin(app, "contrast_dark")
        expected = preview_module.axis_caption_colour(colors)
        widget.set_theme()
        app.processEvents()
        for prop in caption_text_properties(widget._axes_actor):
            assert_rgb(tuple(prop.GetColor()), rgb(expected), "post-clear caption")
        widget.render_scene(scene)
        app.processEvents()
        assert widget._axes_actor is not marker, "a rebuilt scene gets a new marker"
        colors = theme.current_colors()
        expected = preview_module.axis_caption_colour(colors)
        for prop in caption_text_properties(widget._axes_actor):
            assert_rgb(tuple(prop.GetColor()), rgb(expected), "rebuilt widget caption")
        assert widget._plotter.renderer.axes_widget.GetEnabled()
    finally:
        widget._plotter.close()     # release the OpenGL context before the widget goes
        widget.close()
        widget.deleteLater()
        app.processEvents()
    print("widget: theme switch, clear+switch+rebuild recolor captions without touching the camera")


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="XYZ caption readability on the 3D preview canvas.")
    parser.add_argument("--objects-only", action="store_true",
                        help="real VTK objects without a window (default; works offscreen)")
    parser.add_argument("--native", action="store_true",
                        help="also drive the real PyVistaPreviewWidget; needs a real display")
    args = parser.parse_args(argv)
    if args.objects_only and args.native:
        parser.error("choose exactly one of --objects-only and --native")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    mode = "native" if args.native else "objects-only"
    if mode == "objects-only":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([sys.argv[0]])
    print(f"smoke_vtk_axes_theme: mode={mode}, platform={app.platformName()}")
    if mode == "native" and app.platformName() == "offscreen":
        raise SystemExit("smoke_vtk_axes_theme: --native needs a real display; unset QT_QPA_PLATFORM=offscreen")
    theme.apply_theme(app, "light", light_skin="paper", dark_skin="midnight")
    check_caption_colour_maths()
    check_real_axes_actor(app)
    check_real_plotter_clear()
    check_wiring()
    if mode == "native":
        check_widget_lifecycle(app)
    print(f"smoke_vtk_axes_theme: OK (mode={mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
