"""Iterate the vehicle pool and blow things up.

Type BOOM to explode every nearby car, or KABOOM for every car in the world.
Shows the live entity collections: iterate `pysa.vehicles` (or
`world.vehicles`) directly - no parentheses - and filter with .near()/.where().
"""
import pysa
from pysa import hud, player, vehicles


@pysa.on_cheat("BOOM")
def nearby():
    count = 0
    for car in vehicles.near(player.pos, 60, exclude=player.vehicle):
        car.explode()
        count += 1
    hud.help_text(f"Exploded {count} nearby cars")


@pysa.on_cheat("KABOOM")
def everything():
    count = 0
    for car in vehicles:                 # iterate the whole pool directly
        if car != player.vehicle:
            car.explode()
            count += 1
    hud.help_text(f"Exploded {count} cars")


@pysa.on_cheat("CARS")
def report_models():
    # Getting each car's model while iterating the list.
    from collections import Counter
    tally = Counter(car.model_name or f"model {car.model}" for car in vehicles)
    for name, n in tally.most_common(10):
        pysa.log(f"[cars] {n:3d} x {name}")
    hud.help_text(f"{len(vehicles)} cars, {len(tally)} models - see log")

