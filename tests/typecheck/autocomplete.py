"""Compile-time contract for the types ordinary scripts rely on most."""
from __future__ import annotations

from typing import Optional

import pysa
from pysa import (Ped, ScriptSession, VEHICLE, WEAPON, Vehicle,
                  VehicleModelInfo, model_info, world)


@pysa.on_vehicle_render
def rendering_car(car: Vehicle) -> None:
    if car.health < 300:
        pysa.log(f"Damaged vehicle: {car.model}")


nearest_car: Optional[Vehicle] = world.vehicles.nearest((0, 0, 0))
nearby_peds: list[Ped] = world.peds.near((0, 0, 0), 30.0)
vehicle_info: VehicleModelInfo = model_info(VEHICLE.INFERNUS)

session = ScriptSession()
spawned_car: Vehicle = session.spawn_vehicle(VEHICLE.INFERNUS)
tracked_car: Vehicle = session.track(spawned_car)
spawned_car.model
spawned_car.driver

pysa.player.weapons.current = WEAPON.M4
