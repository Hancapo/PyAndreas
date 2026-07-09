"""Rendering showcase: a live health/armour status panel.

Draws a translucent panel with health and armour bars plus a speed readout,
toggled with F7. Demonstrates pysa.draw (rectangles and bars).
"""
import pysa
from pysa import KEY, draw, hud, player

visible = True


@pysa.on_key(KEY.F7)
def toggle():
    global visible
    visible = not visible


@pysa.on_draw
def panel():
    if not visible or not player.playing:
        return

    ped = player.ped
    if not ped.exists:
        return
    health = max(0.0, ped.health)
    max_health = ped.max_health or 100.0
    armour = max(0.0, ped.armour)

    x, y = 24, 150
    draw.rect(x, y, 210, 78, (0, 0, 0, 150))
    hud.draw("CJ", x + 10, y + 6, size=0.9, color=(255, 220, 80))

    draw.bar(x + 10, y + 34, 190, 9, health / max_health,
             fg=(210, 60, 60), border=(0, 0, 0, 220))
    draw.bar(x + 10, y + 50, 190, 9, min(1.0, armour / 100.0),
             fg=(90, 150, 220), border=(0, 0, 0, 220))

    veh = player.vehicle
    if veh is not None:
        kmh = veh.speed * 3.6
        hud.draw(f"{kmh:.0f} km/h", x + 120, y + 6, size=0.8,
                 color=(255, 255, 255))
