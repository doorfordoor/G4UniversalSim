"""Line icons drawn for this GUI (24 px grid, 1.8 px strokes), coloured at runtime.

Every icon is a small SVG body whose strokes/fills use "{c}"; icon(name, color) renders
it with QSvgRenderer at 2x for high-DPI screens and caches the result. Colours come from
the theme (core/theme.py), so callers re-request icons after a theme change.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_STROKE = 'fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'

BODIES = {
    "logo": ('<ellipse cx="12" cy="12" rx="9.5" ry="3.8" {s}/>'
             '<ellipse cx="12" cy="12" rx="9.5" ry="3.8" transform="rotate(60 12 12)" {s}/>'
             '<ellipse cx="12" cy="12" rx="9.5" ry="3.8" transform="rotate(120 12 12)" {s}/>'
             '<circle cx="12" cy="12" r="1.9" fill="{c}"/>'),
    "start": '<path d="M3.5 11 L12 4 L20.5 11 M5.5 9.5 V20 H18.5 V9.5 M10 20 V14.5 H14 V20" {s}/>',
    "project": '<path d="M3 7 V18.5 H21 V9 H11.5 L9.5 6.5 H3.8 Z" {s}/>',
    "configuration": ('<path d="M4 6.5 H20 M4 12 H20 M4 17.5 H20" {s}/>'
                      '<circle cx="9" cy="6.5" r="2.2" fill="{bg}" stroke="{c}" stroke-width="1.8"/>'
                      '<circle cx="15.5" cy="12" r="2.2" fill="{bg}" stroke="{c}" stroke-width="1.8"/>'
                      '<circle cx="7.5" cy="17.5" r="2.2" fill="{bg}" stroke="{c}" stroke-width="1.8"/>'),
    "run": '<circle cx="12" cy="12" r="8.5" {s}/><path d="M10.2 8.6 L15.6 12 L10.2 15.4 Z" fill="{c}" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>',
    "results": '<path d="M4 20 H20" {s}/><rect x="5.5" y="12" width="3" height="8" rx="0.6" {s}/>'
               '<rect x="10.5" y="6" width="3" height="14" rx="0.6" {s}/><rect x="15.5" y="9.5" width="3" height="10.5" rx="0.6" {s}/>',
    "history": '<circle cx="12" cy="12.5" r="8" {s}/><path d="M12 8.5 V12.5 L14.8 14.3" {s}/>',
    "scans": '<path d="M4 18 L9 12.5 L13 14.5 L20 6.5" {s}/><circle cx="4" cy="18" r="1.7" fill="{c}"/>'
             '<circle cx="9" cy="12.5" r="1.7" fill="{c}"/><circle cx="13" cy="14.5" r="1.7" fill="{c}"/>'
             '<circle cx="20" cy="6.5" r="1.7" fill="{c}"/>',
    "theme": '<circle cx="12" cy="12" r="8" {s}/><path d="M12 4 A8 8 0 0 1 12 20 Z" fill="{c}"/>',
    "language": '<circle cx="12" cy="12" r="8.5" {s}/><ellipse cx="12" cy="12" rx="3.8" ry="8.5" {s}/><path d="M3.5 12 H20.5" {s}/>',
    "plus": '<path d="M12 5 V19 M5 12 H19" {s}/>',
    "open": '<path d="M3 7 V18.5 H18 L21 11 H7 L4.5 18" {s}/><path d="M3 7 H9 L11 9 H17 V11" {s}/>',
    "refresh": '<path d="M19.5 12 A7.5 7.5 0 1 1 17 6.4" {s}/><path d="M19.5 4.5 V9 H15" {s}/>',
    "export": '<path d="M12 4 V14.5 M7.5 10 L12 14.5 L16.5 10 M5 19.5 H19" {s}/>',
    "play": '<path d="M8 5.5 L18.5 12 L8 18.5 Z" fill="{c}" stroke="{c}" stroke-width="1.4" stroke-linejoin="round"/>',
    "flask": '<path d="M9.5 3.5 H14.5 M10.5 3.5 V9.5 L5 18.5 C4.4 19.6 5.1 20.5 6.3 20.5 H17.7 C18.9 20.5 19.6 19.6 19 18.5 L13.5 9.5 V3.5" {s}/>'
             '<path d="M7.4 15 H16.6" {s}/>',
    "book": '<path d="M4 5.5 C6.5 4.5 9.5 4.5 12 6 C14.5 4.5 17.5 4.5 20 5.5 V19 C17.5 18 14.5 18 12 19.5 C9.5 18 6.5 18 4 19 Z M12 6 V19.5" {s}/>',
    "home": '<path d="M4 11 L12 4.5 L20 11 M6 9.5 V19.5 H18 V9.5" {s}/>',
    "zoom": '<circle cx="10.5" cy="10.5" r="6" {s}/><path d="M15 15 L20 20 M8 10.5 H13 M10.5 8 V13" {s}/>',
    "pan": '<path d="M12 3.5 V20.5 M3.5 12 H20.5 M9.5 6 L12 3.5 L14.5 6 M9.5 18 L12 20.5 L14.5 18 M6 9.5 L3.5 12 L6 14.5 M18 9.5 L20.5 12 L18 14.5" {s}/>',
    "back": '<path d="M15 5.5 L8.5 12 L15 18.5" {s}/>',
    "forward": '<path d="M9 5.5 L15.5 12 L9 18.5" {s}/>',
    "chevron_down": '<path d="M6.5 9.5 L12 15 L17.5 9.5" {s}/>',
    "chevron_up": '<path d="M6.5 14.5 L12 9 L17.5 14.5" {s}/>',
    "target": '<circle cx="12" cy="12" r="8.5" {s}/><circle cx="12" cy="12" r="4.8" {s}/>'
              '<circle cx="12" cy="12" r="1.6" fill="{c}"/>',
    "layers": '<rect x="4" y="4" width="16" height="3.6" rx="0.8" {s}/><rect x="4" y="10.2" width="16" height="3.6" rx="0.8" {s}/>'
              '<rect x="4" y="16.4" width="16" height="3.6" rx="0.8" {s}/>',
    "shield": '<path d="M12 3.5 L19 6.2 V11.5 C19 15.8 16 18.9 12 20.5 C8 18.9 5 15.8 5 11.5 V6.2 Z" {s}/>',
    "chip": '<rect x="7" y="7" width="10" height="10" rx="1.2" {s}/>'
            '<path d="M10 4 V7 M14 4 V7 M10 17 V20 M14 17 V20 M4 10 H7 M4 14 H7 M17 10 H20 M17 14 H20" {s}/>',
    "spectrum": '<path d="M3.5 19.5 H20.5" {s}/><path d="M4.5 19 C6 17.5 7 12 8.5 12 C10 12 10.5 16 12 16 C13 16 13.5 15 14 13 '
                'L15.5 5 L17 13 C17.5 15 18.5 17.5 20 18.5" {s}/>',
    "save": '<path d="M5 4.5 H16 L19.5 8 V19.5 H5 Z M8 4.5 V9 H15 V4.5 M8 19.5 V14 H16 V19.5" {s}/>',
}


def svg(name: str, color: str, background: str = "none") -> str:
    body = BODIES[name].replace("{s}", _STROKE).replace("{c}", color).replace("{bg}", background)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">{body}</svg>'


@lru_cache(maxsize=512)
def pixmap(name: str, color: str, size: int = 20, background: str = "none") -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg(name, color, background).encode("utf-8")))
    image = QPixmap(size * 2, size * 2)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
    painter.end()
    image.setDevicePixelRatio(2.0)
    return image


def icon(name: str, color: str, size: int = 20, *, active: str = "", background: str = "none") -> QIcon:
    """An icon in one colour; with active, the checked/selected state uses that colour."""
    result = QIcon(pixmap(name, color, size, background))
    if active:
        result.addPixmap(pixmap(name, active, size, background), QIcon.Normal, QIcon.On)
        result.addPixmap(pixmap(name, active, size, background), QIcon.Active, QIcon.Off)
    return result
