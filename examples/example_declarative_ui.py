"""Declarative PyAndreas UI example.

Copy this file and ``vehicle_tools.pui`` into ``PyAndreas/scripts``, then
press F6 in game. The XML file contains presentation; Python owns behavior.
"""
from dataclasses import dataclass
from pathlib import Path

import pysa
from pysa import cmd, hud, player, ui


@dataclass
class Settings:
    invincible: bool = False

    @property
    def vehicle_name(self) -> str:
        vehicle = player.vehicle
        return vehicle.model_name if vehicle is not None else "On foot"


settings = Settings()


def repair_vehicle() -> None:
    vehicle = player.vehicle
    if vehicle is None:
        hud.help_text("Enter a vehicle first")
        return
    vehicle.health = 1000
    cmd.FIX_CAR(vehicle)
    hud.help_text("Vehicle repaired")


@pysa.on_tick
def apply_invincibility() -> None:
    if player.playing:
        enabled = settings.invincible
        player.ped.make_proof(enabled, enabled, enabled, enabled, enabled)


@pysa.on_shutdown
def restore_damage() -> None:
    if player.playing:
        player.ped.make_proof(False, False, False, False, False)


menu = ui.load(
    Path(__file__).with_name("vehicle_tools.pui"),
    actions={"repair_vehicle": repair_vehicle},
    state={
        "settings": settings,
        "wanted": player.wanted,
    },
    styles={
        "heading": ui.ElementStyle(pixels=18),
        "primary": ui.ElementStyle(background=(28, 96, 70, 245)),
    },
)
