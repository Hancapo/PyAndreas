"""A first PyAndreas script using the regular object-oriented API."""
import pysa
from pysa import KEY, VEHICLE, WEAPON, Vehicle, hud, player, world


@pysa.on_game_start
def welcome():
    hud.help_text("PyAndreas is ready - press F2 for a car")


@pysa.on_key(KEY.F2)
def get_a_car():
    car = Vehicle.spawn(VEHICLE.INFERNUS)
    player.ped.warp_into(car)
    hud.help_text("Your Infernus is ready")


@pysa.on_key(KEY.F3)
def get_a_loadout():
    player.weapons.give(WEAPON.M4, ammo=500)
    player.weapons.give(WEAPON.DESERT_EAGLE, ammo=100)
    player.vitals.heal()
    hud.help_text("Weapons and health restored")


@pysa.on_key(KEY.F4)
def visit_grove_street():
    player.pos = (2495, -1687, world.ground_z(2495, -1687))
    hud.help_text("Welcome to Grove Street")
