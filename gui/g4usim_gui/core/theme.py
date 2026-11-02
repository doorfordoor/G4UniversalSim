"""Appearance tokens, palettes and the application style sheet.

The module owns three things:

* ``ThemeColors`` — the colour roles every widget reads (``current_colors()``);
* ``SKINS`` — the named appearances the user can pick (light and dark groups);
* ``apply_theme`` — validates a request, resolves follow-the-system mode, keeps the
  remembered appearance and installs QPalette + QSS in one synchronous step.

Compatibility: ``B``/``K`` are the historical light palettes and ``C`` the historical
dark palette; they remain valid skin ids, ``apply_theme(app, mode, "K")`` keeps the old
meaning, and ``lightThemePalette`` stays the remembered light id for older tests.
"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from g4usim_gui.core.fonts import preferred_font_families


ThemeMode = Literal["light", "dark", "system"]
# Kept as an alias: B/K/C are still accepted wherever a palette id was accepted.
ThemePalette = str
SkinMode = Literal["light", "dark"]


#: Spacing scale used by hand-built layouts (4/8/12/16/24/32 px).
SPACE = {"xs": 4, "s": 8, "m": 12, "l": 16, "xl": 24, "xxl": 32}
#: Corner radii used by the style sheet and custom widgets.
RADIUS = {"s": 6, "m": 9, "l": 14, "xl": 18}
#: Height of the standard one-line control.
CONTROL_HEIGHT = 32
#: Default icon edge in the navigation and toolbars.
ICON_SIZE = 18
#: Duration of non-blocking UI motion (ms); Qt properties may use it later.
MOTION_MS = 160


@dataclass(frozen=True)
class ThemeColors:
    """Colour roles. The first twenty fields are the historical contract."""

    canvas: str
    surface: str
    surface_alt: str
    input: str
    text: str
    text_muted: str
    border: str
    border_strong: str
    accent: str
    accent_hover: str
    accent_soft: str
    selection: str
    success: str
    warning: str
    danger: str
    sidebar: str
    sidebar_hover: str
    sidebar_selected: str
    sidebar_text: str
    sidebar_muted: str
    # Appearance v2 roles (defaults describe a light work surface).
    canvas_alt: str = "#e9edf0"
    surface_hover: str = "#f3f6f8"
    border_subtle: str = "#edf1f3"
    focus_ring: str = "#1d7a6c"
    info: str = "#2a6f97"
    grid: str = "#e3e8ec"
    shadow: str = "rgba(15, 23, 28, 0.10)"
    sidebar_accent: str = "#2e9e8b"


LIGHT = ThemeColors(
    canvas="#f3f5f7",
    surface="#ffffff",
    surface_alt="#f5f7f9",
    input="#ffffff",
    text="#18212a",
    text_muted="#5f6d76",
    border="#e1e6ea",
    border_strong="#c7d0d6",
    accent="#1d7a6c",
    accent_hover="#16645a",
    accent_soft="#e2f1ed",
    selection="#d5ebe5",
    success="#2b7b55",
    warning="#a5640f",
    danger="#b3363f",
    sidebar="#0f171c",
    sidebar_hover="#19242a",
    sidebar_selected="#1f3237",
    sidebar_text="#eef3f4",
    sidebar_muted="#90a1a8",
    canvas_alt="#e9edf0",
    surface_hover="#f3f6f8",
    border_subtle="#edf1f3",
    focus_ring="#1d7a6c",
    info="#2a6f97",
    grid="#e3e8ec",
    shadow="rgba(15, 23, 28, 0.10)",
    sidebar_accent="#2e9e8b",
)


DARK = ThemeColors(
    canvas="#0e1316",
    surface="#151c20",
    surface_alt="#1a2328",
    input="#11181b",
    text="#e7edef",
    text_muted="#9caeb5",
    border="#243036",
    border_strong="#354349",
    accent="#4cb3a1",
    accent_hover="#66c6b5",
    accent_soft="#1e3a36",
    selection="#2a4a45",
    success="#62bb88",
    warning="#e0a04a",
    danger="#ee7178",
    sidebar="#090e10",
    sidebar_hover="#141c20",
    sidebar_selected="#1d3034",
    sidebar_text="#eef3f4",
    sidebar_muted="#8b9da4",
    canvas_alt="#0a0f12",
    surface_hover="#1e282d",
    border_subtle="#1b2429",
    focus_ring="#66c6b5",
    info="#7cc4f0",
    grid="#1f2a30",
    shadow="rgba(0, 0, 0, 0.45)",
    sidebar_accent="#4cb3a1",
)


# The historical palettes remain skins with legacy ids; their declared colours are
# normalised by _accessible() below like every other skin, and B/K/C are rebound to
# the normalised objects after the registry is built.
_RAW_B = replace(LIGHT, canvas="#ffffff", surface_alt="#f5f9fa", text="#1f2933",
                 text_muted="#5b6975", border="#e1e7eb", accent="#0e7c86",
                 accent_hover="#0a5a62", accent_soft="#dff6f2", selection="#bfefe9")
_RAW_K = replace(LIGHT, canvas="#f8f9fa", surface_alt="#edf1f5", text="#212529",
                 text_muted="#5c6670", border="#e1e5ea", accent="#1971c2",
                 accent_hover="#12508f", accent_soft="#e7f5ff", selection="#d0ebff")
_RAW_C = replace(DARK, canvas="#111820", surface="#172029", surface_alt="#1c2833",
                 input="#111820", text="#d5dce4", text_muted="#8d9baa", border="#26313d",
                 accent="#8cc8f0", accent_hover="#addbfa", accent_soft="#243d50", selection="#304b60")


def _light(**overrides: str) -> ThemeColors:
    return replace(LIGHT, **overrides)


def _dark(**overrides: str) -> ThemeColors:
    return replace(DARK, **overrides)


PAPER = _light(
    canvas="#f5efe3", surface="#fffdf7", surface_alt="#efe7d7", input="#fffdf7",
    text="#2a251e", text_muted="#6a6151", border="#e0d6c3", border_strong="#c4b8a1",
    accent="#9c3b2e", accent_hover="#7d2d23", accent_soft="#f6e4dc", selection="#efd8cd",
    success="#3f6b47", warning="#94610f", danger="#a5343c",
    sidebar="#241f19", sidebar_hover="#302a22", sidebar_selected="#3a3127",
    sidebar_text="#f6efe2", sidebar_muted="#b1a591",
    canvas_alt="#e9dfcc", surface_hover="#fbf5ea", border_subtle="#ece2d0",
    focus_ring="#9c3b2e", info="#2f5f7f", grid="#e6dcc8",
    shadow="rgba(60, 45, 22, 0.12)", sidebar_accent="#c56a4a")

SANDSTONE = _light(
    canvas="#f4efe7", surface="#fcfaf5", surface_alt="#ece5d8", input="#fcfaf5",
    text="#2b2822", text_muted="#6b6459", border="#ddd3c2", border_strong="#c0b49f",
    accent="#0f766e", accent_hover="#0b5c56", accent_soft="#dcf1ee", selection="#c9e9e4",
    success="#2f6f4a", warning="#8a5a12", danger="#a63a3a",
    sidebar="#20201c", sidebar_hover="#2b2b26", sidebar_selected="#353429",
    sidebar_text="#f2ede1", sidebar_muted="#aca493",
    canvas_alt="#e5ddcc", surface_hover="#faf6ee", border_subtle="#e8e0d1",
    focus_ring="#0f766e", info="#2b5f86", grid="#e2d9c8",
    shadow="rgba(52, 42, 26, 0.12)", sidebar_accent="#3fa596")

BOTANICAL = _light(
    canvas="#f1f4ee", surface="#fbfdf8", surface_alt="#e7ede1", input="#fbfdf8",
    text="#1e2a20", text_muted="#5d6b5f", border="#d8e1d0", border_strong="#b8c7ae",
    accent="#2f6b3f", accent_hover="#24552f", accent_soft="#e0eedf", selection="#cfe4ca",
    success="#2f7a4b", warning="#86610f", danger="#a53636",
    sidebar="#16221a", sidebar_hover="#1f2d23", sidebar_selected="#283a2c",
    sidebar_text="#eef5ee", sidebar_muted="#9db3a2",
    canvas_alt="#dfe7d7", surface_hover="#f5f9f1", border_subtle="#e3ebdc",
    focus_ring="#2f6b3f", info="#2f6478", grid="#dce5d6",
    shadow="rgba(30, 48, 32, 0.12)", sidebar_accent="#59a06b")

GRAPHITE = _light(
    canvas="#f2f3f4", surface="#ffffff", surface_alt="#eaecee", input="#ffffff",
    text="#171b1e", text_muted="#5b6368", border="#d6dade", border_strong="#b3bcc2",
    accent="#3c5560", accent_hover="#2c4049", accent_soft="#e3e9ec", selection="#d3dfe4",
    success="#2f6b4f", warning="#8a5c12", danger="#a83a40",
    sidebar="#14181b", sidebar_hover="#1e2428", sidebar_selected="#293136",
    sidebar_text="#eef1f3", sidebar_muted="#9aa4aa",
    canvas_alt="#e1e4e6", surface_hover="#f6f7f8", border_subtle="#e9ecee",
    focus_ring="#3c5560", info="#2f6274", grid="#dfe3e6",
    shadow="rgba(20, 26, 30, 0.12)", sidebar_accent="#8fa4ad")

FROST = _light(
    canvas="#edf3f7", surface="#fbfdff", surface_alt="#e3edf4", input="#fbfdff",
    text="#16232c", text_muted="#54646e", border="#d5e2eb", border_strong="#b2c3cf",
    accent="#0b6ea8", accent_hover="#085a8b", accent_soft="#dcecf7", selection="#cfe6f4",
    success="#2f6b55", warning="#8a5f12", danger="#a8393f",
    sidebar="#10202c", sidebar_hover="#182b39", sidebar_selected="#21394a",
    sidebar_text="#eaf3fa", sidebar_muted="#93aab8",
    canvas_alt="#dbe7ef", surface_hover="#f4f9fd", border_subtle="#e2ecf3",
    focus_ring="#0b6ea8", info="#0b6ea8", grid="#d9e5ee",
    shadow="rgba(16, 32, 44, 0.12)", sidebar_accent="#5aa7d2")

CONTRAST_LIGHT = _light(
    canvas="#ffffff", surface="#ffffff", surface_alt="#f0f1f2", input="#ffffff",
    text="#0a0c0d", text_muted="#3c4245", border="#9aa1a6", border_strong="#5f676b",
    accent="#0b57d0", accent_hover="#0842a0", accent_soft="#e0e8fb", selection="#c9daf8",
    success="#11692f", warning="#7a4a00", danger="#b3261e",
    sidebar="#000000", sidebar_hover="#1b1c1d", sidebar_selected="#2b2c2d",
    sidebar_text="#ffffff", sidebar_muted="#c8ced2",
    canvas_alt="#e4e6e8", surface_hover="#f5f6f7", border_subtle="#d6d9db",
    focus_ring="#0b57d0", info="#0b57d0", grid="#c5c9cc",
    shadow="rgba(0, 0, 0, 0.16)", sidebar_accent="#6aa2ff")

MIDNIGHT = _dark(
    canvas="#0b1220", surface="#121b2b", surface_alt="#172235", input="#0e1726",
    text="#e6eefb", text_muted="#93a4bf", border="#223147", border_strong="#33465f",
    accent="#5b9dff", accent_hover="#7fb4ff", accent_soft="#1b2f4d", selection="#23405f",
    success="#56c08b", warning="#e0a94a", danger="#f0717a",
    sidebar="#070d18", sidebar_hover="#101a2a", sidebar_selected="#16253c",
    sidebar_text="#e8f0fb", sidebar_muted="#8aa0bd",
    canvas_alt="#0a1019", surface_hover="#182338", border_subtle="#1c2840",
    focus_ring="#7fb4ff", info="#7fb4ff", grid="#1b2740",
    shadow="rgba(0, 0, 0, 0.50)", sidebar_accent="#5b9dff")

CIRCUIT = _dark(
    canvas="#08110e", surface="#0f1b17", surface_alt="#142520", input="#0b1512",
    text="#e2f0e9", text_muted="#93b1a4", border="#1e332b", border_strong="#2e4a3e",
    accent="#34d399", accent_hover="#6ee7b7", accent_soft="#123328", selection="#17493a",
    success="#34d399", warning="#d9a441", danger="#f0717a",
    sidebar="#050c0a", sidebar_hover="#0c1814", sidebar_selected="#11261f",
    sidebar_text="#dff3ea", sidebar_muted="#8aa79b",
    canvas_alt="#070f0c", surface_hover="#16261f", border_subtle="#182b23",
    focus_ring="#6ee7b7", info="#5cc8d8", grid="#152a22",
    shadow="rgba(0, 0, 0, 0.50)", sidebar_accent="#34d399")

SLATE = _dark(
    canvas="#14171a", surface="#1b1f23", surface_alt="#22272c", input="#171b1f",
    text="#e7eaec", text_muted="#9aa3aa", border="#2b3137", border_strong="#3c454d",
    accent="#7fb3d5", accent_hover="#a3c9e2", accent_soft="#22323d", selection="#2b404f",
    success="#7cc79b", warning="#d6a85b", danger="#e2858c",
    sidebar="#0e1113", sidebar_hover="#171b1e", sidebar_selected="#20262a",
    sidebar_text="#eef1f3", sidebar_muted="#8d979e",
    canvas_alt="#121518", surface_hover="#252b30", border_subtle="#24292e",
    focus_ring="#a3c9e2", info="#7fb3d5", grid="#262c31",
    shadow="rgba(0, 0, 0, 0.45)", sidebar_accent="#7fb3d5")

EMBER = _dark(
    canvas="#17120e", surface="#1f1813", surface_alt="#271f18", input="#1a140f",
    text="#f2e9df", text_muted="#b5a595", border="#332820", border_strong="#4a3a2d",
    accent="#e0a458", accent_hover="#f0bd7a", accent_soft="#3a2a1b", selection="#4a3523",
    success="#9dc78f", warning="#e0a458", danger="#e57373",
    sidebar="#100c09", sidebar_hover="#19130e", sidebar_selected="#241a12",
    sidebar_text="#f5ecdf", sidebar_muted="#bda990",
    canvas_alt="#141009", surface_hover="#2b2118", border_subtle="#2a2119",
    focus_ring="#f0bd7a", info="#c8a06a", grid="#2b2218",
    shadow="rgba(0, 0, 0, 0.50)", sidebar_accent="#e0a458")

AURORA = _dark(
    canvas="#0d1017", surface="#141826", surface_alt="#1a2030", input="#101320",
    text="#e9ecf5", text_muted="#9ba6c0", border="#242c42", border_strong="#36405c",
    accent="#9d8cff", accent_hover="#bfb3ff", accent_soft="#241f45", selection="#2f2a55",
    success="#5ad1a8", warning="#e6b45c", danger="#f07a8a",
    sidebar="#080a10", sidebar_hover="#10131c", sidebar_selected="#171c2a",
    sidebar_text="#eaeef8", sidebar_muted="#939ec0",
    canvas_alt="#0b0e14", surface_hover="#1c2233", border_subtle="#1d2537",
    focus_ring="#bfb3ff", info="#8ec5ff", grid="#1c2438",
    shadow="rgba(0, 0, 0, 0.50)", sidebar_accent="#9d8cff")

CONTRAST_DARK = _dark(
    canvas="#000000", surface="#0a0a0a", surface_alt="#141414", input="#060606",
    text="#ffffff", text_muted="#d0d4d6", border="#6b7175", border_strong="#9aa1a6",
    accent="#7cb7ff", accent_hover="#a6ceff", accent_soft="#10233d", selection="#1d3a5c",
    success="#6ee7a8", warning="#ffd166", danger="#ff8a8a",
    sidebar="#000000", sidebar_hover="#1a1a1a", sidebar_selected="#262626",
    sidebar_text="#ffffff", sidebar_muted="#c8ced2",
    canvas_alt="#050505", surface_hover="#1f1f1f", border_subtle="#2a2a2a",
    focus_ring="#a6ceff", info="#7cb7ff", grid="#262626",
    shadow="rgba(0, 0, 0, 0.70)", sidebar_accent="#7cb7ff")


# --------------------------------------------------------------------------- colour maths


def _channels(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"not a #rrggbb colour: {value!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def mix(first: str, second: str, weight: float = 0.5) -> str:
    """Blend two #rrggbb colours; ``weight`` is the share of ``first`` (0..1)."""
    a, b = _channels(first), _channels(second)
    share = min(1.0, max(0.0, float(weight)))
    return "#" + "".join(f"{round(x * share + y * (1 - share)):02x}" for x, y in zip(a, b))


def relative_luminance(value: str) -> float:
    """WCAG relative luminance of a #rrggbb colour."""
    def linear(channel: int) -> float:
        srgb = channel / 255
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in _channels(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio between two #rrggbb colours (1..21)."""
    light, dark = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def on_color(value: str) -> str:
    """Readable text on a solid fill of ``value``.

    The crossover where near-black and white swap places is luminance 0.179; using the
    historical 0.45 threshold put white text on mid-light accents (2.2:1 instead of 7:1).
    """
    return "#ffffff" if relative_luminance(value) < 0.179 else "#0b1214"


def on_accent(c: ThemeColors) -> str:
    """Text colour on an accent-filled control: white on a dark accent, near-black on a light one."""
    return on_color(c.accent)


def _until_all(fg: str, toward: str, backgrounds: tuple[str, ...], target: float) -> str:
    """Move a foreground toward ``toward`` until it clears ``target`` on every background.

    ``mix`` takes the share of its first argument, so the share shrinks as the step
    grows; this walks the colour from its declared value toward ``toward`` in 2.5% steps
    and stops at the first one that clears the floor, keeping the smallest adjustment.
    """
    if all(contrast_ratio(fg, background) >= target for background in backgrounds):
        return fg
    for step in range(1, 41):
        candidate = mix(fg, toward, 1.0 - step / 40)
        if all(contrast_ratio(candidate, background) >= target for background in backgrounds):
            return candidate
    return toward


def _bg_until(start: str, fixed: str, toward: str, target: float) -> str:
    """Move a background toward ``toward`` until it contrasts ``fixed`` by ``target``."""
    if contrast_ratio(fixed, start) >= target:
        return start
    for step in range(1, 41):
        candidate = mix(start, toward, 1.0 - step / 40)
        if contrast_ratio(fixed, candidate) >= target:
            return candidate
    return toward


def _accessible(colors: ThemeColors) -> ThemeColors:
    """Raise declared colours to the J3 contrast floor while keeping their hue.

    Body text and hints keep 4.5:1 on every work surface, control boundaries and the
    focus ring keep 3:1 against what they sit on, accent chips keep 4.5:1 for accent
    text, and selected navigation rows stay distinguishable from the sidebar. Values
    only move when the declared colour misses the floor, so skins that already pass
    keep the colours their designers chose.
    """
    muted = _until_all(colors.text_muted, colors.text,
                       (colors.canvas, colors.surface, colors.canvas_alt, colors.surface_alt), 4.5)
    sidebar_muted = _until_all(colors.sidebar_muted, colors.sidebar_text, (colors.sidebar,), 4.5)
    border_strong = _until_all(colors.border_strong, colors.text,
                               (colors.surface, colors.input), 3.0)
    focus_ring = _until_all(colors.focus_ring, colors.text,
                            (colors.surface, colors.canvas), 3.0)
    accent = _until_all(colors.accent, colors.text, (colors.canvas, colors.surface), 3.0)
    accent_hover = colors.accent_hover if accent == colors.accent else mix(accent, colors.text, 0.22)
    accent_soft = _bg_until(colors.accent_soft, accent, colors.surface, 4.5)
    selection = _bg_until(colors.selection, colors.text, colors.surface, 4.5)
    sidebar_selected = _bg_until(colors.sidebar_selected, colors.sidebar, colors.sidebar_text, 1.15)
    return replace(colors, text_muted=muted, sidebar_muted=sidebar_muted,
                   border_strong=border_strong, focus_ring=focus_ring, accent=accent,
                   accent_hover=accent_hover, accent_soft=accent_soft, selection=selection,
                   sidebar_selected=sidebar_selected)



@dataclass(frozen=True)
class Skin:
    """One selectable appearance: a name for the menu plus its colour roles."""

    id: str
    name: str
    mode: SkinMode
    colors: ThemeColors
    description: str = ""
    series: tuple[str, ...] = ()
    legacy_light_key: str = ""


_RAW_SKINS: dict[str, Skin] = {
    # Historical palettes first so menus and the default stay stable.
    "B": Skin("B", "B · Lattice", "light", _RAW_B, "Crisp white lattice with a teal accent.",
              ("#0e7c86", "#d97706", "#3b6f9c", "#7c3aed", "#b3363f", "#2b7b55"), "B"),
    "K": Skin("K", "K · Software", "light", _RAW_K, "Soft neutral software surface with a blue accent.",
              ("#1971c2", "#d97706", "#2f8f6b", "#7048e8", "#c92a2a", "#0b7285"), "K"),
    "paper": Skin("paper", "Paper & Ink", "light", PAPER,
                  "Warm paper with oxblood ink for long editing sessions.",
                  ("#9c3b2e", "#b06a1f", "#3f6b47", "#2f5f7f", "#7a3f7a", "#8a6a2f")),
    "sandstone": Skin("sandstone", "Sandstone", "light", SANDSTONE,
                      "Desert clay and a deep teal accent.",
                      ("#0f766e", "#b45309", "#2f6b3f", "#2b5f86", "#7c3a5a", "#6b5b2f")),
    "botanical": Skin("botanical", "Botanical", "light", BOTANICAL,
                      "Sage greens with a forest accent.",
                      ("#2f6b3f", "#8a5c12", "#2f6b7f", "#6b3f7a", "#a53636", "#4f7a2f")),
    "graphite": Skin("graphite", "Graphite", "light", GRAPHITE,
                     "Neutral studio grey with a slate accent.",
                     ("#3c5560", "#a5640f", "#2f6f8f", "#6b4f8f", "#a83a40", "#2f7a5b")),
    "frost": Skin("frost", "Frost", "light", FROST,
                  "Cool blue daylight for dense data screens.",
                  ("#0b6ea8", "#b06a1f", "#2f8f6b", "#7048e8", "#c23a4a", "#0b8f9e")),
    "contrast_light": Skin("contrast_light", "High Contrast", "light", CONTRAST_LIGHT,
                           "Strong black-on-white for projection and low-contrast displays.",
                           ("#0b57d0", "#9a5b00", "#0f7a2f", "#8a2be2", "#c62828", "#00796b")),
    "C": Skin("C", "C · Night Reading", "dark", _RAW_C, "Deep night reading with a pale blue accent.",
              ("#8cc8f0", "#e0a04a", "#6ee7b7", "#b197fc", "#ff8a8a", "#66d9e8")),
    "midnight": Skin("midnight", "Midnight Blue", "dark", MIDNIGHT,
                     "Deep navy with a clear blue accent.",
                     ("#5b9dff", "#e0a94a", "#56c08b", "#c9a0ff", "#f0717a", "#5fd0e0")),
    "circuit": Skin("circuit", "Circuit Night", "dark", CIRCUIT,
                    "Dark control-room green with a signal accent.",
                    ("#34d399", "#e0b34a", "#5cc8d8", "#a78bfa", "#f0717a", "#9ee36b")),
    "slate": Skin("slate", "Slate", "dark", SLATE,
                  "Quiet neutral dark for mixed day and night work.",
                  ("#7fb3d5", "#d6a85b", "#7cc79b", "#b9a0e8", "#e2858c", "#7fd0c6")),
    "ember": Skin("ember", "Ember", "dark", EMBER,
                  "Warm low-light palette with an amber accent.",
                  ("#e0a458", "#e07a5f", "#9dc78f", "#d9a1c9", "#e57373", "#c8b06a")),
    "aurora": Skin("aurora", "Aurora", "dark", AURORA,
                   "Violet night sky with teal highlights.",
                   ("#9d8cff", "#5ad1a8", "#e6b45c", "#6ec5ff", "#f07a8a", "#c9a0ff")),
    "contrast_dark": Skin("contrast_dark", "Night Contrast", "dark", CONTRAST_DARK,
                          "Pure black and white for maximum legibility.",
                          ("#7cb7ff", "#ffd166", "#6ee7a8", "#caa8ff", "#ff8a8a", "#8fe3ff")),
}


def _build_skins() -> dict[str, Skin]:
    return {key: replace(raw, colors=_accessible(raw.colors)) for key, raw in _RAW_SKINS.items()}


SKINS: dict[str, Skin] = _build_skins()

# The historical names must observe exactly the colours the application applies: tests
# and callers compare ``current_colors()`` against these objects directly.
B, K, C = (SKINS[key].colors for key in ("B", "K", "C"))
PALETTES = {"B": B, "K": K, "C": C}

SKIN_IDS = tuple(SKINS)
LIGHT_SKIN_IDS = tuple(skin.id for skin in SKINS.values() if skin.mode == "light")
DARK_SKIN_IDS = tuple(skin.id for skin in SKINS.values() if skin.mode == "dark")
DEFAULT_LIGHT_SKIN = "B"
DEFAULT_DARK_SKIN = "C"
LEGACY_LIGHT_KEYS = ("B", "K")


def skins_for_mode(mode: SkinMode) -> tuple[Skin, ...]:
    return tuple(skin for skin in SKINS.values() if skin.mode == mode)


def skin(name: object) -> Skin | None:
    """The skin registered under ``name`` (legacy palette ids included), else None."""
    return SKINS.get(str(name)) if name is not None else None


# --------------------------------------------------------------------------- resolution


def current_skin(app: QApplication | None = None) -> Skin:
    app = app or QApplication.instance()
    if app is None:
        return SKINS[DEFAULT_LIGHT_SKIN]
    for name in ("resolvedSkin", "resolvedPalette"):
        found = skin(app.property(name))
        if found is not None:
            return found
    if app.property("resolvedTheme") == "dark":
        return SKINS[DEFAULT_DARK_SKIN]
    return SKINS[DEFAULT_LIGHT_SKIN]


def current_colors(app: QApplication | None = None) -> ThemeColors:
    """Colours of the theme currently applied to the application."""
    return current_skin(app).colors


def resolve_theme(app: QApplication, mode: ThemeMode) -> Literal["light", "dark"]:
    if mode != "system":
        return mode
    scheme = app.styleHints().colorScheme()
    if scheme != Qt.ColorScheme.Unknown:
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    # the application palette is ours once a theme is applied: ask the style for the system one
    window_color = app.style().standardPalette().color(QPalette.Window)
    return "dark" if window_color.lightness() < 128 else "light"


# --------------------------------------------------------------------------- persistence


def stored_appearance(settings=None) -> tuple[ThemeMode, str, str]:
    """Remembered (mode, light skin, dark skin) with the historical keys migrated."""
    if settings is None:
        from PySide6.QtCore import QSettings  # noqa: PLC0415 - avoid importing QtCore twice

        settings = QSettings()
    mode = str(settings.value("appearance/theme", "light") or "light")
    if mode not in ("light", "dark", "system"):
        mode = "light"
    light = str(settings.value("appearance/light_skin", "") or "")
    dark = str(settings.value("appearance/dark_skin", "") or "")
    legacy = str(settings.value("appearance/light_palette", "") or "")
    if not light and legacy in LEGACY_LIGHT_KEYS:
        light = legacy
    if not light:
        light = DEFAULT_LIGHT_SKIN
    if not dark:
        dark = DEFAULT_DARK_SKIN
    light_skin = SKINS.get(light)
    dark_skin = SKINS.get(dark)
    return (mode,
            light_skin.id if light_skin is not None and light_skin.mode == "light" else DEFAULT_LIGHT_SKIN,
            dark_skin.id if dark_skin is not None and dark_skin.mode == "dark" else DEFAULT_DARK_SKIN)


def persist_appearance(settings, light_skin: str, dark_skin: str) -> None:
    """Write the remembered appearance; the legacy key mirrors B/K for older code."""
    settings.setValue("appearance/light_skin", light_skin)
    settings.setValue("appearance/dark_skin", dark_skin)
    if light_skin in LEGACY_LIGHT_KEYS:
        settings.setValue("appearance/light_palette", light_skin)


def _valid_skin_id(value: object, mode: SkinMode, default: str) -> str:
    found = skin(value)
    return found.id if found is not None and found.mode == mode else default


def apply_appearance(app: QApplication, mode: ThemeMode, light_skin: str, dark_skin: str) -> Literal["light", "dark"]:
    """Apply one explicit appearance request (normally read from QSettings)."""
    return apply_theme(app, mode, light_skin=light_skin, dark_skin=dark_skin)


# --------------------------------------------------------------------------- application


def apply_theme(app: QApplication, mode: ThemeMode, palette: ThemePalette | None = None,
                *, light_skin: str | None = None, dark_skin: str | None = None) -> Literal["light", "dark"]:
    """Apply appearance without changing any project state.

    ``palette`` keeps the historical contract: a skin id selects the remembered skin of
    that skin's own group (B/K are light, C is dark) without erasing the other group.
    Selecting a dark appearance never erases the remembered light appearance and the
    mode is the only thing follow-the-system changes.
    """
    if mode not in ("light", "dark", "system"):
        raise ValueError("Unknown theme mode")
    if palette is not None:
        selected = skin(palette)
        if selected is None:
            raise ValueError("Unknown theme palette")
        if selected.mode == "light":
            light_skin = selected.id
        else:
            dark_skin = selected.id
    remembered_light = _valid_skin_id(
        light_skin if light_skin is not None else app.property("lightSkinId"),
        "light", _valid_skin_id(app.property("lightThemePalette"), "light", DEFAULT_LIGHT_SKIN))
    remembered_dark = _valid_skin_id(
        dark_skin if dark_skin is not None else app.property("darkSkinId"),
        "dark", DEFAULT_DARK_SKIN)
    app.setProperty("lightSkinId", remembered_light)
    app.setProperty("darkSkinId", remembered_dark)
    app.setProperty("lightThemePalette", remembered_light)  # historical name, same value
    resolved = resolve_theme(app, mode)
    resolved_id = remembered_dark if resolved == "dark" else remembered_light
    colors = SKINS[resolved_id].colors
    font = app.font()
    font.setFamilies(preferred_font_families(QFontDatabase.families(), font.families()))
    if font != app.font():
        app.setFont(font)
    native_palette = build_palette(colors)
    if native_palette != app.palette():
        app.setPalette(native_palette)   # native check boxes, arrows and popups
    stylesheet = build_stylesheet(colors)
    previous = app.styleSheet()
    if stylesheet != previous:
        # Qt 6's replacement of a live application sheet repeatedly repolishes
        # the large nested editor tree. Removing the old sheet first avoids that
        # slow replacement path. Keep both calls synchronous: no event processing
        # or queued work may expose the unstyled intermediate state.
        if previous:
            app.setStyleSheet("")
        app.setStyleSheet(stylesheet)
    app.setProperty("themeMode", mode)
    app.setProperty("resolvedTheme", resolved)
    app.setProperty("resolvedPalette", resolved_id)
    app.setProperty("resolvedSkin", resolved_id)
    return resolved


def build_palette(c: ThemeColors) -> QPalette:
    palette = QPalette()
    for role, color in ((QPalette.Window, c.canvas), (QPalette.WindowText, c.text), (QPalette.Base, c.input),
                        (QPalette.AlternateBase, c.surface_alt), (QPalette.Text, c.text),
                        (QPalette.Button, c.surface), (QPalette.ButtonText, c.text),
                        (QPalette.Highlight, c.accent), (QPalette.HighlightedText, on_accent(c)),
                        (QPalette.ToolTipBase, c.sidebar), (QPalette.ToolTipText, c.sidebar_text),
                        (QPalette.PlaceholderText, c.text_muted), (QPalette.Link, c.accent),
                        (QPalette.Mid, c.border_strong), (QPalette.Dark, c.border_strong), (QPalette.Light, c.surface)):
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(c.text_muted))
    return palette


def _svg_url(name: str, color: str) -> str:
    """A line icon as an SVG file for style sheet image: urls (cached in the temp folder)."""
    from g4usim_gui.core import icons   # noqa: PLC0415 - keeps this module free of QtSvg at import
    path = Path(tempfile.gettempdir()) / "g4usim_gui_icons" / f"{name}_{color.lstrip('#')}.svg"
    try:
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(icons.svg(name, color), encoding="utf-8")
    except OSError:
        return ""
    return path.as_posix()


_TOKEN = re.compile(r"\$([a-z_]+)")


def _styled(template: str, c: ThemeColors, **values: str) -> str:
    """Substitute ``$role`` tokens; missing tokens raise instead of leaking into QSS."""
    table: dict[str, str] = {name: value for name, value in vars(c).items()}
    table.update({
        "on_accent": on_accent(c),
        "on_color": on_color(c.accent),
        "on_danger": on_color(c.danger),
        "on_success": on_color(c.success),
        "accent_veil": mix(c.accent, c.canvas, 0.10),
        "danger_veil": mix(c.danger, c.surface, 0.12),
        "success_veil": mix(c.success, c.surface, 0.13),
        "warning_veil": mix(c.warning, c.surface, 0.14),
        "input_hover": mix(c.border_strong, c.accent, 0.55),
        "down": _svg_url("chevron_down", c.text_muted),
        "up": _svg_url("chevron_up", c.text_muted),
        "check": _svg_url("check", on_accent(c)),
        "check_menu": _svg_url("check", c.accent),
        "check_muted": _svg_url("check", c.text_muted),
    })
    table.update(values)

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in table:
            raise KeyError(f"unknown style token ${key}")
        return table[key]

    return _TOKEN.sub(substitute, template)


def build_stylesheet(c: ThemeColors) -> str:
    return _base_stylesheet(c) + _design_stylesheet(c) + _shell_stylesheet(c)


def _base_stylesheet(c: ThemeColors) -> str:
    down, up = _svg_url("chevron_down", c.text_muted), _svg_url("chevron_up", c.text_muted)
    return f"""
QWidget {{
    color: {c.text};
    font-size: 13px;
}}
QMainWindow, QWidget#appShell, QWidget#contentHost, QWidget#pageViewport {{
    background: {c.canvas};
}}
QWidget#setupPanel {{
    background: {c.canvas};
}}
QWidget#sidebar {{
    background: {c.sidebar};
    color: {c.sidebar_text};
}}
QWidget#sidebar QLabel {{
    background: transparent;
}}
QLabel#brandMark {{
    color: {c.sidebar_text};
    font-size: 16px;
    font-weight: 600;
}}
QLabel#brandCaption, QLabel#sidebarSection, QLabel#sidebarFooter {{
    color: {c.sidebar_muted};
}}
QLabel#brandCaption {{
    font-size: 11px;
}}
QLabel#sidebarSection {{
    font-size: 10px;
    font-weight: 700;
}}
QLabel#sidebarFooter {{
    font-size: 11px;
}}
QToolButton[navButton="true"] {{
    background: transparent;
    color: {c.sidebar_muted};
    border: 0;
    border-radius: 8px;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}}
QToolButton[navButton="true"]:hover {{
    background: {c.sidebar_hover};
    color: {c.sidebar_text};
}}
QToolButton[navButton="true"]:checked {{
    background: {c.sidebar_selected};
    color: {c.sidebar_text};
    font-weight: 600;
}}
QFrame#pageHeader {{
    background: {c.surface};
    border-bottom: 1px solid {c.border};
}}
QLabel#pageTitle {{
    font-size: 18px;
    font-weight: 600;
    color: {c.text};
}}
QLabel#pageSubtitle, QLabel[uiRole="hint"] {{
    color: {c.text_muted};
}}
QLabel[uiRole="sectionTitle"] {{
    color: {c.text};
    font-size: 14px;
    font-weight: 600;
}}
QLabel[uiRole="emptyState"] {{
    color: {c.text_muted};
    padding: 12px;
}}
QLabel[uiRole="contextChip"] {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 1px solid {c.border};
    border-radius: 12px;
    padding: 3px 11px;
}}
QLabel[uiRole="statusChip"] {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 1px solid {c.border};
    border-radius: 12px;
    padding: 3px 11px;
    font-weight: 600;
}}
QLabel[uiRole="statusChip"][statusRole="running"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border-color: {c.accent};
}}
QLabel[uiRole="statusChip"][statusRole="success"] {{
    color: {c.success};
    border-color: {c.success};
}}
QLabel[uiRole="statusChip"][statusRole="failed"] {{
    color: {c.danger};
    border-color: {c.danger};
}}
QLabel[uiRole="contextChip"][statusRole="running"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border-color: {c.accent};
    font-weight: 600;
}}
QToolButton[iconButton="true"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px;
}}
QToolButton[iconButton="true"]:hover {{
    background: {c.surface_alt};
    border-color: {c.border};
}}
QToolButton[iconButton="true"]:checked {{
    background: {c.accent_soft};
    border-color: {c.accent};
}}
QToolButton[iconButton="true"]::menu-indicator {{
    image: none;
    width: 0;
}}
QFrame[uiRole="card"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 10px;
}}
QFrame[uiRole="card"]:hover {{
    border-color: {c.accent};
}}
QFrame[uiRole="card"] QLabel {{
    background: transparent;
    border: 0;
}}
QFrame[uiRole="hero"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 12px;
}}
QFrame[uiRole="hero"] QLabel {{
    background: transparent;
}}
QLabel[uiRole="heroTitle"] {{
    font-size: 22px;
    font-weight: 600;
}}
QLabel[uiRole="cardTitle"] {{
    font-size: 14px;
    font-weight: 600;
}}
QFrame[uiRole="card"] QLabel[uiRole="tag"], QLabel[uiRole="tag"] {{
    background: {c.accent_soft};
    color: {c.accent};
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QFrame[uiRole="card"] QLabel[uiRole="thumbnail"], QLabel[uiRole="thumbnail"] {{
    background: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 8px;
}}
QGroupBox {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 10px;
    margin-top: 18px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox[uiRole="panel"] {{
    margin-top: 0;
    padding: 10px 12px;
}}
QToolButton[sectionToggle="true"] {{
    background: transparent;
    border: 0;
    color: {c.text};
    font-size: 13px;
    font-weight: 600;
    padding: 6px 2px 2px 0;
}}
QToolButton[sectionToggle="true"]:hover {{
    color: {c.accent};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: {c.text};
}}
QScrollArea#editorScroll, QScrollArea#editorScroll > QWidget#qt_scrollarea_viewport,
QScrollArea#sourceEditorScroll,
QScrollArea#sourceEditorScroll > QWidget > QWidget#sourceEditorContent {{
    background: {c.surface};
    border: 0;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QTableWidget, QTreeWidget, QListWidget {{
    background: {c.input};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 6px;
    selection-background-color: {c.selection};
    selection-color: {c.text};
}}
QTableWidget, QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit {{
    border-color: {c.border};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    min-height: 30px;
    padding: 0 8px;
}}
QComboBox::drop-down {{
    border: 0;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: url("{down}");
    width: 14px;
    height: 14px;
}}
QAbstractSpinBox::up-arrow {{
    image: url("{up}");
    width: 12px;
    height: 12px;
}}
QAbstractSpinBox::down-arrow {{
    image: url("{down}");
    width: 12px;
    height: 12px;
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    border: 0;
    background: transparent;
    width: 18px;
}}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: {c.surface_alt};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus, QTreeWidget:focus {{
    border: 1px solid {c.accent};
}}
QWidget[diagnosticFocus="true"] {{
    border: 2px solid {c.accent};
}}
QComboBox QAbstractItemView {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 6px;
    outline: 0;
    selection-background-color: {c.selection};
    selection-color: {c.text};
    padding: 3px;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 3px 8px;
}}
QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{
    background: {c.selection};
    color: {c.text};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {{
    background: {c.surface_alt};
    color: {c.text_muted};
}}
QPlainTextEdit, QTextEdit {{
    padding: 8px;
    font-size: 12px;
}}
QPushButton, QToolButton[toolbarButton="true"] {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border_strong};
    border-radius: 6px;
    min-height: 30px;
    padding: 0 14px;
    font-weight: 500;
}}
QPushButton:hover, QToolButton[toolbarButton="true"]:hover {{
    background: {c.surface_alt};
    border-color: {c.accent};
}}
QPushButton:pressed, QToolButton[toolbarButton="true"]:pressed {{
    background: {c.selection};
}}
QPushButton:disabled, QToolButton[toolbarButton="true"]:disabled {{
    color: {c.text_muted};
    background: {c.surface_alt};
    border-color: {c.border};
}}
QPushButton[buttonRole="primary"] {{
    background: {c.accent};
    color: {on_accent(c)};
    border-color: {c.accent};
    font-weight: 600;
}}
QPushButton[buttonRole="primary"]:hover {{
    background: {c.accent_hover};
    border-color: {c.accent_hover};
}}
QPushButton[buttonRole="primary"]:disabled {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border-color: {c.border};
}}
QPushButton[buttonRole="danger"] {{
    color: {c.danger};
    border-color: {c.danger};
}}
QPushButton[buttonRole="link"] {{
    background: transparent;
    border: 0;
    color: {c.accent};
    padding: 0 4px;
    text-align: left;
}}
QPushButton[buttonRole="link"]:hover {{
    color: {c.accent_hover};
    text-decoration: underline;
}}
QTabWidget::pane {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 8px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {c.text_muted};
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 8px 12px;
}}
QTabBar::tab:hover {{
    color: {c.text};
}}
QTabBar::tab:selected {{
    color: {c.accent};
    border-bottom-color: {c.accent};
    font-weight: 600;
}}
QTabBar QToolButton {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 4px;
}}
QHeaderView, QTableCornerButton::section {{
    background: {c.surface_alt};
    border: 0;
}}
QHeaderView::section {{
    background: {c.surface_alt};
    color: {c.text_muted};
    border: 0;
    border-right: 1px solid {c.border};
    border-bottom: 1px solid {c.border};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableWidget, QTreeWidget {{
    gridline-color: {c.border};
    alternate-background-color: {c.surface_alt};
}}
QTableWidget::item, QTreeWidget::item {{
    padding: 4px;
}}
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {c.selection};
    color: {c.text};
}}
QListWidget::item {{
    padding: 4px;
}}
QMenuBar {{
    background: {c.surface};
    color: {c.text};
    border-bottom: 1px solid {c.border};
}}
QMenuBar::item {{
    padding: 6px 10px;
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background: {c.selection};
}}
QMenu {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
    border-radius: 6px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 24px 6px 10px;
    border-radius: 4px;
}}
QStatusBar {{
    background: {c.surface};
    color: {c.text_muted};
    border-top: 1px solid {c.border};
}}
QSplitter::handle {{
    background: {c.border};
    width: 1px;
    height: 1px;
}}
QScrollArea {{
    background: {c.canvas};
    border: 0;
}}
QScrollArea QWidget#qt_scrollarea_viewport {{
    background: {c.canvas};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c.border_strong};
    min-height: 28px;
    border-radius: 3px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c.border_strong};
    min-width: 28px;
    border-radius: 3px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QCheckBox {{
    spacing: 7px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}
QToolTip {{
    background: {c.sidebar};
    color: {c.sidebar_text};
    border: 1px solid {c.border_strong};
    padding: 5px;
}}
"""


def _design_stylesheet(c: ThemeColors) -> str:
    """Appearance v2: a calmer surface hierarchy, crisper controls and clearer states.

    It is appended after the historical sheet, so equal-specificity rules here win; the
    historical object names and roles stay untouched (tests read them).
    """
    return _styled("""
/* ---------------------------------------------------------------- surfaces */
QMainWindow { background: $canvas_alt; }
QWidget#appShell { background: $canvas_alt; }
QWidget#contentHost, QWidget#pageViewport { background: $canvas; }
QWidget#setupPanel { background: $canvas; }
QWidget#sidebar {
    background: $sidebar;
    border-right: 1px solid $sidebar_hover;
}
QLabel#brandMark { color: $sidebar_text; font-size: 16px; font-weight: 700; }
QLabel#brandCaption { color: $sidebar_muted; font-size: 10px; }
QLabel#sidebarSection { color: $sidebar_muted; font-size: 10px; font-weight: 700; padding-left: 6px; }
QLabel#sidebarFooter { color: $sidebar_muted; font-size: 10px; }

QToolButton[navButton="true"] {
    background: transparent;
    color: $sidebar_muted;
    border: 0;
    border-left: 3px solid transparent;
    border-radius: 9px;
    padding: 9px 12px;
    margin: 1px 6px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
QToolButton[navButton="true"]:hover { background: $sidebar_hover; color: $sidebar_text; }
QToolButton[navButton="true"]:checked {
    background: $sidebar_selected;
    color: $sidebar_text;
    font-weight: 600;
    border-left: 3px solid $sidebar_accent;
}
QToolButton[navButton="true"]:focus { border-left: 3px solid $sidebar_accent; }

QFrame#pageHeader { background: $surface; border: 0; border-bottom: 1px solid $border_subtle; }
QLabel#pageTitle { color: $text; font-size: 19px; font-weight: 700; }
QLabel#pageSubtitle { color: $text_muted; font-size: 12px; }
QLabel[uiRole="hint"] { color: $text_muted; }
QLabel[uiRole="sectionTitle"] { color: $text; font-size: 13px; font-weight: 700; }
QLabel[uiRole="emptyState"] { color: $text_muted; padding: 14px; }
QLabel[uiRole="contextChip"], QLabel[uiRole="statusChip"] {
    background: $canvas_alt;
    color: $text_muted;
    border: 1px solid $border_subtle;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel[uiRole="statusChip"][statusRole="running"],
QLabel[uiRole="contextChip"][statusRole="running"] {
    background: $accent_soft;
    color: $accent;
    border-color: $accent;
}
QLabel[uiRole="statusChip"][statusRole="success"] {
    background: $success_veil;
    color: $success;
    border-color: $success;
}
QLabel[uiRole="statusChip"][statusRole="failed"] {
    background: $danger_veil;
    color: $danger;
    border-color: $danger;
}

QToolButton[iconButton="true"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 6px;
}
QToolButton[iconButton="true"]:hover { background: $canvas_alt; border-color: $border; }
QToolButton[iconButton="true"]:checked { background: $accent_soft; border-color: $accent; }
QToolButton[iconButton="true"]::menu-indicator { image: none; width: 0; }

QFrame[uiRole="card"] {
    background: $surface;
    border: 1px solid $border_subtle;
    border-radius: 14px;
}
QFrame[uiRole="card"]:hover { border-color: $accent; }
QFrame[uiRole="card"] QLabel { background: transparent; border: 0; }
QFrame[uiRole="hero"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 $surface, stop:1 $surface_alt);
    border: 1px solid $border_subtle;
    border-radius: 18px;
}
QFrame[uiRole="hero"] QLabel { background: transparent; }
QLabel[uiRole="heroTitle"] { font-size: 26px; font-weight: 700; }
QLabel[uiRole="cardTitle"] { font-size: 14px; font-weight: 700; }
QFrame[uiRole="card"] QLabel[uiRole="tag"], QLabel[uiRole="tag"] {
    background: $accent_soft;
    color: $accent;
    border-radius: 8px;
    padding: 2px 9px;
    font-size: 11px;
    font-weight: 700;
}
QFrame[uiRole="card"] QLabel[uiRole="thumbnail"], QLabel[uiRole="thumbnail"] {
    background: $surface_alt;
    border: 1px solid $border_subtle;
    border-radius: 10px;
}

/* ---------------------------------------------------------------- containers */
QGroupBox {
    background: $surface;
    border: 1px solid $border_subtle;
    border-radius: 14px;
    margin-top: 20px;
    padding: 20px 14px 14px 14px;
    font-weight: 600;
}
QGroupBox[uiRole="panel"] { margin-top: 0; padding: 12px 14px; }
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: $text_muted;
    font-size: 11px;
    font-weight: 700;
}
QToolButton[sectionToggle="true"] {
    background: transparent;
    border: 0;
    color: $text;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 2px 4px 0;
}
QToolButton[sectionToggle="true"]:hover { color: $accent; }

QScrollArea { background: $canvas; border: 0; }
QScrollArea > QWidget#qt_scrollarea_viewport { background: $canvas; }
QScrollArea#editorScroll, QScrollArea#editorScroll > QWidget#qt_scrollarea_viewport,
QScrollArea#sourceEditorScroll,
QScrollArea#sourceEditorScroll > QWidget > QWidget#sourceEditorContent {
    background: $surface;
    border: 0;
}

/* ---------------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit,
QTableWidget, QTreeWidget, QListWidget {
    background: $input;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    selection-background-color: $selection;
    selection-color: $text;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { min-height: 32px; padding: 0 10px; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border-color: $input_hover;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus, QTreeWidget:focus {
    border: 1px solid $accent;
    background: $surface;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled,
QPlainTextEdit:disabled, QTextEdit:disabled {
    background: $surface_alt;
    color: $text_muted;
    border-color: $border;
}
QPlainTextEdit, QTextEdit { padding: 10px; font-size: 12px; }
QComboBox::drop-down { border: 0; width: 26px; }
QComboBox::down-arrow { image: url("$down"); width: 14px; height: 14px; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: $selection;
    selection-color: $text;
}
QComboBox QAbstractItemView::item { min-height: 28px; padding: 3px 10px; border-radius: 6px; }

/* ---------------------------------------------------------------- buttons */
QPushButton, QToolButton[toolbarButton="true"] {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    min-height: 32px;
    padding: 0 16px;
    font-weight: 500;
}
QPushButton:hover, QToolButton[toolbarButton="true"]:hover {
    background: $surface_hover;
    border-color: $accent;
}
QPushButton:pressed, QToolButton[toolbarButton="true"]:pressed { background: $accent_soft; }
QPushButton:disabled, QToolButton[toolbarButton="true"]:disabled {
    color: $text_muted;
    background: $surface_alt;
    border-color: $border;
}
QPushButton[buttonRole="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent, stop:1 $accent_hover);
    color: $on_accent;
    border: 1px solid $accent_hover;
    font-weight: 700;
}
QPushButton[buttonRole="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_hover, stop:1 $accent);
    border-color: $accent_hover;
}
QPushButton[buttonRole="primary"]:pressed { background: $accent_hover; }
QPushButton[buttonRole="primary"]:disabled {
    background: $surface_alt;
    color: $text_muted;
    border-color: $border;
}
QPushButton[buttonRole="danger"] {
    background: $danger_veil;
    color: $danger;
    border: 1px solid $danger;
    font-weight: 700;
}
QPushButton[buttonRole="danger"]:hover { background: $danger; color: $on_danger; }
QPushButton[buttonRole="danger"]:disabled {
    background: $surface_alt;
    color: $text_muted;
    border-color: $border;
}
QPushButton[buttonRole="link"] {
    background: transparent;
    border: 0;
    color: $accent;
    padding: 0 4px;
    text-align: left;
    font-weight: 600;
}
QPushButton[buttonRole="link"]:hover { color: $accent_hover; }

/* ---------------------------------------------------------------- tabs and tables */
QTabWidget::pane {
    background: $surface;
    border: 1px solid $border_subtle;
    border-radius: 12px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: $text_muted;
    border: 0;
    border-radius: 8px;
    /* Six configuration tabs must fit a docked editor; the old 14px padding
       pushed the scroll buttons over the last tab label. */
    padding: 7px 11px;
    margin-right: 3px;
}
QToolButton:focus {
    border: 1px solid $focus_ring;
}
QToolButton[navButton="true"]:focus {
    background: $sidebar_hover;
    color: $sidebar_text;
}
QTabBar::tab:hover { background: $canvas_alt; color: $text; }
QTabBar::tab:selected { background: $accent_soft; color: $accent; font-weight: 700; }
QTabBar QToolButton { background: $surface; border: 1px solid $border; border-radius: 6px; }

QHeaderView, QTableCornerButton::section { background: $surface_alt; border: 0; }
QHeaderView::section {
    background: $surface_alt;
    color: $text_muted;
    border: 0;
    border-right: 1px solid $border_subtle;
    border-bottom: 1px solid $border_subtle;
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
}
QTableWidget, QTreeWidget { gridline-color: $border_subtle; alternate-background-color: $surface_alt; }
QTableWidget::item, QTreeWidget::item, QListWidget::item { padding: 6px 8px; }
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background: $selection;
    color: $text;
}

/* ---------------------------------------------------------------- menus and status */
QMenuBar { background: $canvas_alt; border-bottom: 1px solid $border_subtle; }
QMenuBar::item { padding: 6px 12px; border-radius: 6px; }
QMenuBar::item:selected { background: $surface_hover; color: $text; }
QMenu {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item { padding: 7px 28px 7px 12px; border-radius: 7px; }
QMenu::item:selected { background: $selection; color: $text; }
QMenu::separator { height: 1px; background: $border_subtle; margin: 6px 8px; }
QMenu::indicator { width: 15px; height: 15px; }
QMenu::indicator:checked { image: url("$check_menu"); }
QStatusBar { background: $canvas_alt; color: $text_muted; border-top: 1px solid $border_subtle; }
QStatusBar::item { border: 0; }

/* ---------------------------------------------------------------- docks and chrome */
QDockWidget {
    color: $text_muted;
    font-size: 11px;
    font-weight: 600;
}
QDockWidget::title {
    background: $surface_alt;
    color: $text_muted;
    border: 0;
    border-bottom: 1px solid $border_subtle;
    padding: 7px 10px;
    text-align: left;
}
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent;
    border: 0;
    border-radius: 4px;
    padding: 2px;
}
QDockWidget::close-button:hover, QDockWidget::float-button:hover { background: $surface_hover; }
QMainWindow::separator { background: $border_subtle; }
QMainWindow::separator:hover { background: $accent; }
QToolBar { background: $canvas_alt; border: 0; border-bottom: 1px solid $border_subtle; spacing: 4px; padding: 3px 8px; }
QToolBar QToolButton { padding: 4px 9px; border-radius: 6px; color: $text; }
QToolBar QToolButton:hover { background: $surface_hover; }
QToolBar QToolButton:checked { background: $selection; color: $on_accent; }
QToolBar::separator { background: $border_subtle; width: 1px; margin: 4px 6px; }
QToolBar::separator { background: $border_subtle; width: 1px; margin: 6px 4px; }
QTabBar::scroller { width: 30px; }
QTabBar QToolButton { background: transparent; border: 0; border-radius: 6px; padding: 2px 3px; }
QTabBar QToolButton:hover { background: $surface_hover; }
QLabel[uiRole="contextChip"], QLabel[uiRole="statusChip"] { font-size: 11px; font-weight: 600; }

/* ---------------------------------------------------------------- splitters and scrollbars */
QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 8px; }
QSplitter::handle:vertical { height: 8px; }
QSplitter::handle:hover { background: $accent_soft; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px 3px; }
QScrollBar::handle:vertical { background: $border_strong; min-height: 32px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 3px 2px; }
QScrollBar::handle:horizontal { background: $border_strong; min-width: 32px; border-radius: 4px; }
QScrollBar::handle:horizontal:hover { background: $accent; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* ---------------------------------------------------------------- checks, progress, tooltips */
QCheckBox { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 17px;
    height: 17px;
    border: 2px solid $border_strong;
    border-radius: 5px;
    background: $input;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$check"); }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    border-color: $border;
    background: $surface_alt;
}
QRadioButton::indicator { border-radius: 9px; }
QRadioButton::indicator:checked { background: $input; border: 5px solid $accent; }
QProgressBar {
    background: $canvas_alt;
    border: 0;
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
    text-align: center;
    color: $text;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent_hover);
    border-radius: 5px;
}
QWidget[diagnosticFocus="true"] { border: 2px solid $accent; border-radius: 9px; }
QToolTip {
    background: $sidebar;
    color: $sidebar_text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 7px 9px;
}
""", c)


def _shell_stylesheet(c: ThemeColors) -> str:
    """Shell chrome added by J3 stage 2: grouped navigation, breadcrumb, palette, status bar."""
    return _styled("""
/* ------------------------------------------------------- shell chrome (J3) */
#sidebar QLabel#sidebarSection {
    color: $sidebar_muted;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.9px;
    padding: 6px 8px 2px 8px;
}
#sidebar QToolButton[navButton="true"] {
    padding: 0 10px;
    border: 1px solid transparent;
}
#sidebar QToolButton[navButton="true"]:checked {
    background: $sidebar_selected;
    border-color: $sidebar_hover;
    border-left: 3px solid $sidebar_accent;
    padding-left: 7px;
    color: $sidebar_text;
}
QLabel[uiRole="crumb"] {
    color: $text_muted;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QLabel#statusMeta {
    color: $text_muted;
    font-size: 11px;
    padding: 0 8px;
}
QStatusBar {
    background: $surface;
    border-top: 1px solid $border_subtle;
}
QStatusBar::item { border: none; }
/* ------------------------------------------------------ command palette (J3) */
QDialog#commandPalette {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: $radius_l;
}
QLabel#paletteCategory {
    color: $text_muted;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.4px;
    padding: 0 2px;
}
QLineEdit#paletteSearch {
    background: $input;
    border: 1px solid $border;
    border-radius: $radius_m;
    min-height: 36px;
    padding: 0 12px;
    font-size: 14px;
    selection-background-color: $selection;
}
QLineEdit#paletteSearch:hover { border-color: $input_hover; }
QLineEdit#paletteSearch:focus { border: 1px solid $accent; }
QListWidget#paletteList {
    background: transparent;
    border: none;
    outline: 0;
}
QListWidget#paletteList::item {
    border-radius: $radius_s;
    padding: 7px 10px;
    margin: 1px 3px;
    color: $text;
}
QListWidget#paletteList::item:disabled {
    background: transparent;
    padding: 8px 4px 2px 4px;
    margin: 0;
}
QListWidget#paletteList::item:selected {
    background: $accent_soft;
    color: $text;
}
QLabel#paletteHint {
    color: $text_muted;
    font-size: 11px;
    padding: 2px 4px;
}
""", c,
        radius_s=f"{RADIUS['s']}px",
        radius_m=f"{RADIUS['m']}px",
        radius_l=f"{RADIUS['l']}px",
    )
