"""God mode + never-wanted, toggled by typing GODPY in-game."""
import pysa
from pysa import hud, player

god = False


@pysa.on_cheat("GODPY")
def toggle():
    global god
    god = not god
    # proof against bullets, fire, explosions, collisions and melee
    player.ped.make_proof(god, god, god, god, god)
    player.set_max_wanted_level(0 if god else 6)
    if god:
        player.heal()
        player.wanted_level = 0
    hud.big_text("GOD MODE " + ("ON" if god else "OFF"), 2000, 4)


@pysa.on_tick(ms=2000)
def upkeep():
    if god and player.playing:
        player.heal()
