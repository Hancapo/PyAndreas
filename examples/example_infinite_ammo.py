"""Give every weapon full ammo, using the on_weapon_given event.

Whenever any ped is handed a weapon, top the ammo up. Reads as an event with
named fields - no addresses, no C++ names.
"""
import pysa
from pysa import hud, player


@pysa.on_weapon_given
def full_ammo(e):
    if e.ammo < 9999:
        e.ammo = 9999               # rewrite the ammo before it's applied
    if e.ped == player.ped:
        hud.help_text("Ammo topped up")
