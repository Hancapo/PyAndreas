"""Controller support: buttons, combos, sticks, and rumble.

- D-pad UP spawns an NRG-500 and buzzes the controller.
- Hold L1 and press CROSS to heal.
- While using a controller, the left-stick vector is shown on screen.
"""
import pysa
from pysa import VEHICLE, Vehicle, hud, pad, player
from pysa.pad import BUTTON


@pysa.on_button(BUTTON.DPAD_UP)
def spawn_bike():
    Vehicle.spawn(VEHICLE.NRG500)
    pad.rumble(300, 220)
    hud.help_text("NRG-500")


@pysa.on_button(BUTTON.CROSS)
def maybe_heal():
    # A simple combo: only when L1 is held at the same time.
    if pad.pressed(BUTTON.L1):
        player.heal()
        hud.help_text("Healed")


@pysa.on_draw
def show_stick():
    if not pad.using_joypad() or not player.playing:
        return
    x, y = pad.left_stick()
    if x or y:
        hud.draw(f"stick ({x:+.2f}, {y:+.2f})", 20, 60, size=0.7,
                 color=(120, 200, 255))
