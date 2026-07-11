"""Inactive example: waypoint travel and a smooth camera shot.

Copy this file to ``scripts/`` when you want to try it.
"""
import pysa
from pysa import KEY, blips, camera, hud, player


@pysa.on_key(KEY.F6)
def travel_to_waypoint():
    destination = blips.waypoint()
    if destination is None:
        hud.help_text("Place a waypoint on the map first")
        return
    destination.z = pysa.world.ground_z(destination.x, destination.y) + 1.0
    player.ped.pos = destination
    hud.help_text("Teleported to waypoint")


@pysa.script
def camera_demo():
    yield 2000
    ped = player.ped
    focus = ped.pos
    camera.move(focus + (-8, -8, 5), focus + (8, -8, 3), 3000)
    camera.track(focus, focus + (0, 0, 0), 3000)
    camera.interpolate_fov(70.0, 45.0, 3000)
    yield 3200
    camera.restore()
