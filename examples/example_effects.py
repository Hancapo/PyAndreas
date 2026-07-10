"""Audio + particle FX demo: toggle a fiery aura with the cheat PYRO.

Attaches a flame particle system to the player, plays a whoosh, and draws a
glowing corona above them each frame. Type PYRO again to turn it off.
"""
import pysa
from pysa import audio, fx, player

aura = None


@pysa.on_cheat("PYRO")
def toggle():
    global aura
    if aura is None:
        aura = fx.FxSystem.on(player.ped, fx.FX.FIRE, offset=(0, 0, 0.4))
        aura.play()
        audio.play_sound(player.pos, 1058)   # a whoosh
    else:
        aura.remove()
        aura = None


@pysa.on_draw
def glow():
    if aura is not None and player.playing:
        fx.corona(player.pos + (0, 0, 2.5), size=2.0, color=(255, 120, 0),
                  corona_type=fx.CORONA.NORMAL)


@pysa.on_shutdown
def cleanup():
    global aura
    if aura is not None:
        aura.remove()
        aura = None
