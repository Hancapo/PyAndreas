"""Teleport hotkeys.

F3 = Grove Street, F4 = Mount Chiliad summit, F5 = LV strip.
Also: NUM8 nudges you 10m forward (works in vehicles too).
"""
import math

import pysa
from pysa import KEY, Vector3, hud, player, world

PLACES = {
    KEY.F3: ("Grove Street", Vector3(2495.0, -1668.0, 13.4)),
    KEY.F4: ("Mount Chiliad", Vector3(-2318.0, -1637.0, 483.7)),
    KEY.F5: ("Las Venturas strip", Vector3(2027.0, 1008.0, 10.8)),
}


def _teleport(where, pos):
    target = player.vehicle or player.ped
    # Snap to the ground so we don't fall through the world.
    z = world.ground_z(pos.x, pos.y)
    target.pos = Vector3(pos.x, pos.y, (z or pos.z) + 1.0)
    hud.help_text(f"Teleported to {where}")


for _key, (_name, _pos) in PLACES.items():
    pysa.on_key(_key)(lambda n=_name, p=_pos: _teleport(n, p))


@pysa.on_key(KEY.NUMPAD8)
def nudge_forward():
    ped = player.ped
    rad = math.radians(ped.heading)
    step = Vector3(-10.0 * math.sin(rad), 10.0 * math.cos(rad), 0.0)
    target = player.vehicle or ped
    target.pos = target.pos + step
