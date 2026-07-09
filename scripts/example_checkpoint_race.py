"""Checkpoint mini-game: reach the marker before the timer runs out.

Press F8 to start. Shows off the new OOP pieces working together: Checkpoint
and Marker3D, a Countdown timer, entity.distance_to(), and a @pysa.script
coroutine driving it all.
"""
import pysa
from pysa import KEY, Checkpoint, Countdown, Marker3D, Vector3, hud, player


@pysa.on_key(KEY.F8)
def start_race():
    pysa.start(race)


def race():
    # Drop a checkpoint 40m north of the player.
    target = player.pos + Vector3(0, 40, 0)
    checkpoint = Checkpoint(target, radius=4.0)
    marker = Marker3D(target)
    clock = Countdown(15000)                 # 15 seconds
    hud.help_text("Reach the checkpoint!")

    try:
        while not clock.finished:
            if player.ped.distance_to(target) < 5.0:
                hud.big_text("CHECKPOINT!", 3000, 0)
                return
            # live countdown in the corner
            hud.draw(f"{clock.seconds:4.1f}s", *(20, 140),
                     size=1.2, color=(255, 220, 80))
            yield                             # wait one frame
        hud.big_text("TOO SLOW", 3000, 1)
    finally:
        checkpoint.remove()
        marker.remove()
