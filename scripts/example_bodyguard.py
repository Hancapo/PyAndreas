"""Coroutine + AI showcase: press F6 to spawn an armed bodyguard.

He walks up to you, gives a little nod (hands-up wave), then follows you
around and attacks whoever hurts you. Shows off: @pysa.script coroutines,
Ped.spawn, ped.tasks.*, blips, and markerless cmd calls.
"""
import pysa
from pysa import KEY, MOVE_STATE, PED, WEAPON, Ped, blips, hud, player

BODYGUARD_MODEL = PED.BMYBOUN  # suited man


@pysa.on_key(KEY.F6)
def hire():
    pysa.start(bodyguard_routine)


def bodyguard_routine():
    me = player.ped
    guard = Ped.spawn(BODYGUARD_MODEL, player.pos + (3, 0, 0))
    guard.give_weapon(WEAPON.DESERT_EAGLE, 999)
    guard.set_accuracy(90)
    guard.health = 200
    blip = blips.add_for_char(guard)
    blip.color = blips.COLOR.GREEN
    hud.help_text("Bodyguard hired")

    guard.tasks.go_to(player.pos, mode=MOVE_STATE.RUN)
    yield 1500
    guard.tasks.hands_up(800)
    yield 1000

    my_last_health = player.health
    while guard.exists and not guard.is_dead:
        # someone hurt us -> guard retaliates against the nearest hostile ped
        if player.health < my_last_health:
            for ped in pysa.all_peds():
                if ped == me or ped == guard or ped.is_dead:
                    continue
                if ped.pos.distance_to(player.pos) < 15:
                    guard.tasks.attack(ped)
                    break
        my_last_health = player.health

        # stay close when idling
        if guard.pos.distance_to(player.pos) > 12:
            guard.tasks.go_to(player.pos, mode=MOVE_STATE.RUN)
        yield 500

    blip.remove()
    hud.help_text("Bodyguard down")
