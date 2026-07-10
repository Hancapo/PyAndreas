"""A minimal speedometer drawn while driving."""
import pysa
from pysa import hud, player


@pysa.on_draw
def speedo():
    if not player.playing:
        return
    veh = player.vehicle
    if veh is None:
        return
    kmh = veh.speed * 3.6  # game units are roughly m/s
    w, h = hud.screen_size()
    color = (255, 60, 60) if kmh > 120 else (255, 255, 255)
    hud.draw(f"{kmh:6.0f} km/h", w - 30, h - 90, size=1.4,
             color=color, align=hud.ALIGN.RIGHT, font=hud.FONT.PRICEDOWN)
    hud.draw(f"HP {veh.health}", w - 30, h - 50, size=0.8,
             color=(180, 180, 180), align=hud.ALIGN.RIGHT)
