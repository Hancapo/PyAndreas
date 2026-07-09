"""God mode + never-wanted, toggled by typing GODPY in-game."""
import pysa
from pysa import cmd, hud, player

god = False


@pysa.on_cheat("GODPY")
def toggle():
    global god
    god = not god
    ped = player.ped
    # bullet, fire, explosion, collision, melee proofs
    cmd.SET_CHAR_PROOFS(ped, *([1] * 5 if god else [0] * 5))
    player.set_max_wanted_level(0 if god else 6)
    if god:
        player.heal()
        player.wanted_level = 0
    hud.big_text("GOD MODE " + ("ON" if god else "OFF"), 2000, 4)


@pysa.on_tick(ms=2000)
def upkeep():
    if god and player.playing:
        player.heal()
