"""On-screen text: HUD messages and per-frame 2D text drawing.

    from pysa import hud

    hud.help_text("Press ~k~~VEHICLE_ENTER_EXIT~ to enter")   # black help box
    hud.text("Subtitle style message", ms=3000)               # subtitle queue
    hud.big_text("MISSION PASSED", style=1)                   # big title

    @pysa.on_draw
    def overlay():
        hud.draw("Speed: 42", 20, 300, size=1.0, color=(255, 220, 0))
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa


class FONT:
    GOTHIC = 0
    SUBTITLES = 1
    MENU = 2
    PRICEDOWN = 3


class ALIGN:
    CENTER = 0
    LEFT = 1
    RIGHT = 2


def help_text(text: str, quick: bool = True, permanent: bool = False) -> None:
    """Show a message in the black help box (top-left)."""
    _pysa.help_message(str(text), quick, permanent)


def text(message: str, ms: int = 2000) -> None:
    """Show a subtitle-style message at the bottom of the screen."""
    _pysa.message(str(message), ms, 0)


def big_text(message: str, ms: int = 4000, style: int = 0) -> None:
    """Show a big title message ('MISSION PASSED' style)."""
    _pysa.big_message(str(message), ms, style)


def _pack(color) -> int:
    if isinstance(color, int):
        return color
    r, g, b, *rest = color
    a = rest[0] if rest else 255
    return ((r & 0xFF) << 24) | ((g & 0xFF) << 16) | ((b & 0xFF) << 8) | (a & 0xFF)


def draw(message: str, x: float, y: float, size: float = 1.0,
         color=(255, 255, 255), font: int = FONT.SUBTITLES,
         align: int = ALIGN.LEFT, shadow: int = 1,
         shadow_color=(0, 0, 0), proportional: bool = True,
         scale=None, wrap: float = 0.0) -> None:
    """Draw text this frame. Call every frame (from an @on_draw handler).

    x/y are pixels; get the resolution from screen_size(). `size` scales a
    readable default; pass scale=(sx, sy) for exact font scale instead.
    color is (r, g, b) or (r, g, b, a) or packed 0xRRGGBBAA.
    """
    if scale is None:
        sx, sy = 0.5 * size, 1.1 * size
    else:
        sx, sy = scale
    _pysa.draw_text(str(message), float(x), float(y), float(sx), float(sy),
                    _pack(color), int(font), int(align), int(shadow),
                    _pack(shadow_color), 1 if proportional else 0, float(wrap))


def screen_size() -> tuple:
    """Current render resolution as (width, height)."""
    return _pysa.screen_size()
