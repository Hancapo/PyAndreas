"""Friendly toolkit: menu, raycast, state events and automatic cleanup.

Press F6 for the menu. Press F7 to identify what the camera is looking at.
"""
import pysa
from pysa import KEY, PED, ScriptSession, hud, player, ui, world


menu = ui.Menu("PyAndreas Toolkit", toggle_key=KEY.F6)
menu.action("Heal player", lambda: player.vitals.heal())
menu.toggle_item(
    "Never tired",
    lambda: player.perks.never_tired,
    lambda enabled: setattr(player.perks, "never_tired", enabled),
)


@pysa.on_key(KEY.F7)
def inspect_camera_target():
    start = pysa.camera.position()
    target = pysa.camera.target()
    direction = (target - start).normalized()
    hit = world.raycast(start, start + direction * 200.0, ignore=player.ped)
    if hit:
        hud.help_text(f"Hit {hit.surface.name}: {hit.entity}")
    else:
        hud.help_text("Nothing in sight")


@pysa.on_vehicle_enter
def entered_vehicle(event: pysa.VehicleEnterEvent) -> None:
    if event.ped == player.ped:
        pysa.log(f"Entered {event.vehicle.model_name}")


@pysa.script
def temporary_bodyguard():
    """The ped is deleted automatically if this script errors or reloads."""
    with ScriptSession() as session:
        guard = session.spawn_ped(PED.BMYBOUN, player.pos + (3, 0, 0))
        guard.tasks.follow(player.ped)
        yield 10000
