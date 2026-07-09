"""2D rendering: filled rectangles and textured sprites.

Call these from an @pysa.on_draw handler (they draw for one frame):

    from pysa import draw, hud

    @pysa.on_draw
    def hud_overlay():
        w, h = hud.screen_size()
        draw.rect(20, 20, 200, 60, (0, 0, 0, 150))          # translucent panel
        draw.bar(24, 24, 192, 8, 0.7, fg=(80, 220, 80))     # progress bar
        hud.draw("Shields", 28, 34)

Textures are PNGs loaded once (after the game is up):

    @pysa.on_game_start
    def load_art():
        draw.load_textures(pysa.base_dir() + r"\\textures")

    @pysa.on_draw
    def logo():
        draw.sprite("mylogo", 10, 10, 128, 128)

Colors are (r,g,b), (r,g,b,a) or packed 0xRRGGBBAA. Coordinates are pixels;
get the resolution from pysa.hud.screen_size().
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .hud import _pack


def rect(x: float, y: float, w: float, h: float, color=(0, 0, 0, 128)) -> None:
    """Filled rectangle at (x, y) with size (w, h)."""
    _pysa.draw_rect(float(x), float(y), float(x + w), float(y + h), _pack(color))


def rect_xyxy(x1: float, y1: float, x2: float, y2: float,
              color=(0, 0, 0, 128)) -> None:
    """Filled rectangle between two corners."""
    _pysa.draw_rect(float(x1), float(y1), float(x2), float(y2), _pack(color))


def sprite(name: str, x: float, y: float, w: float, h: float,
           color=(255, 255, 255)) -> None:
    """Draw a loaded texture (see load_texture/load_textures) as a rectangle.

    `color` tints the texture; white = untinted, alpha controls transparency.
    """
    _pysa.draw_sprite(str(name), float(x), float(y), float(x + w), float(y + h),
                      _pack(color))


def bar(x: float, y: float, w: float, h: float, progress: float,
        fg=(80, 220, 80), bg=(0, 0, 0, 160), border=None) -> None:
    """A horizontal progress bar; progress is 0.0..1.0."""
    progress = max(0.0, min(1.0, progress))
    if border is not None:
        rect(x - 1, y - 1, w + 2, h + 2, border)
    rect(x, y, w, h, bg)
    if progress > 0:
        rect(x, y, w * progress, h, fg)


def load_texture(png_path: str) -> bool:
    """Load one PNG. Keyed by its file's base name for use with sprite()."""
    return bool(_pysa.load_texture(str(png_path)))


def load_textures(folder: str) -> bool:
    """Load every PNG in a folder. Call from on_game_start (needs RW up)."""
    return bool(_pysa.load_textures(str(folder)))
