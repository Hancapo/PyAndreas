"""Localised GXT text with styling.

For arbitrary strings you normally want `pysa.hud.draw(...)` (it handles any
text via the font engine). This module is for the game's *GXT* text: keys
defined in the game's language files or a loaded mission-text table, drawn
each frame with full style control.

    from pysa import text

    @pysa.on_draw
    def hud():
        text.show("NUMBER", 0.1, 0.1, number=42,
                  size=(0.4, 1.0), color=(255, 220, 80),
                  align=text.ALIGN.LEFT, shadow=2)

Positions are 0..1 screen fractions (the GXT drawing convention), not pixels.
"""
from __future__ import annotations

from .native import cmd


class ALIGN:
    LEFT = 0
    CENTER = 1
    RIGHT = 2


class FONT:
    GOTHIC = 0
    SUBTITLES = 1
    MENU = 2
    PRICEDOWN = 3


def load_table(table_name: str) -> None:
    """Load an external mission-text (GXT) table so its keys resolve."""
    cmd.LOAD_MISSION_TEXT(str(table_name))


def string_width(gxt_key: str) -> float:
    """Width (screen fraction) a GXT entry would take at the current scale."""
    return cmd.GET_STRING_WIDTH(str(gxt_key))


def clear() -> None:
    """Clear queued big/styled prints."""
    cmd.CLEAR_PRINTS()


def _apply_style(size, color, font, align, shadow, wrap, background):
    sx, sy = size
    cmd.SET_TEXT_SCALE(float(sx), float(sy))
    r, g, b, *a = color
    cmd.SET_TEXT_COLOUR(int(r), int(g), int(b), int(a[0]) if a else 255)
    cmd.SET_TEXT_FONT(int(font))
    cmd.SET_TEXT_CENTRE(align == ALIGN.CENTER)
    cmd.SET_TEXT_RIGHT_JUSTIFY(align == ALIGN.RIGHT)
    cmd.SET_TEXT_PROPORTIONAL(True)
    if shadow:
        cmd.SET_TEXT_DROPSHADOW(int(shadow), 0, 0, 0, 255)
    if wrap:
        cmd.SET_TEXT_WRAPX(float(wrap))
    if background:
        cmd.SET_TEXT_BACKGROUND(True)


def show(gxt_key: str, x: float, y: float, number: int = None,
         size=(0.5, 1.0), color=(255, 255, 255), font: int = FONT.SUBTITLES,
         align: int = ALIGN.LEFT, shadow: int = 1, wrap: float = 0.0,
         background: bool = False) -> None:
    """Draw a GXT string this frame (call every frame from on_draw).

    If `number` is given, uses the ~1~ placeholder in the GXT entry.
    x/y are 0..1 screen fractions.
    """
    _apply_style(size, color, font, align, shadow, wrap, background)
    if number is None:
        cmd.DISPLAY_TEXT(float(x), float(y), str(gxt_key))
    else:
        cmd.DISPLAY_TEXT_WITH_NUMBER(float(x), float(y), str(gxt_key), int(number))
