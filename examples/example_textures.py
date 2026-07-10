"""Textured sprites: load PNGs and draw them.

Put .png files in  <game>\\PyAndreas\\textures\\  and they load by file name.
This example is defensive: if the folder/texture is missing it draws a plain
rectangle instead, so it never errors out.

    draw.load_textures(folder)      # once, after the game is up
    draw.sprite("name", x, y, w, h) # each frame (name = png file without .png)
"""
import pysa
from pysa import draw, hud

_loaded = False


@pysa.on_game_start
def load_art():
    global _loaded
    folder = pysa.base_dir() + r"\textures"
    _loaded = draw.load_textures(folder)
    pysa.log(f"[textures] loaded from {folder}: {_loaded}")


@pysa.on_draw
def logo():
    x, y, size = 30, 30, 128
    if _loaded:
        # 'logo' = logo.png in the textures folder; tint white = untinted.
        draw.sprite("logo", x, y, size, size)
    else:
        # Fallback so the example still shows something without art files.
        draw.rect(x, y, size, size, (40, 40, 60, 180))
        hud.draw("add textures/logo.png", x + 8, y + size / 2, size=0.6)
