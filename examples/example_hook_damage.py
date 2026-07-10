"""Game-event showcase: make the player's car take half damage.

Reads like a normal event - "when a vehicle is damaged" - with named fields.
No addresses, no calling conventions, no C++ names.

Other events you can use the same way: on_vehicle_explode, on_tyre_burst,
on_weapon_fire, on_explosion, on_wanted_level_change, on_projectile_fired.
"""
import pysa
from pysa import hud, player

cushioned = 0


@pysa.on_vehicle_damage
def tougher_cars(e: pysa.VehicleDamageEvent) -> None:
    global cushioned
    if player.playing and e.vehicle == player.vehicle:
        cushioned += 1
        e.amount = e.amount * 0.5        # halve incoming damage
        # e.cancel()                     # would ignore the hit entirely


@pysa.on_explosion
def shield_nearby(e: pysa.ExplosionEvent) -> None:
    # Cancel explosions that go off right next to the player.
    if player.playing and e.position.distance_to(player.pos) < 4.0:
        e.cancel()


@pysa.on_tick(ms=1000)
def show():
    if cushioned:
        hud.help_text(f"cushioned hits: {cushioned}")
