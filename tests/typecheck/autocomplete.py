"""Compile-time contract for the types ordinary scripts rely on most."""
from __future__ import annotations

from typing import Optional

import pysa
from pysa import (AREA, AreaId, Ped, Placement, ScriptSession, VEHICLE, WEAPON, Vehicle,
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
current_area: AREA = pysa.player.location.area
custom_area: AreaId = 42
outside: bool = pysa.player.location.outside
entrance = pysa.player.location.last_entry_exit
if entrance is not None:
    exterior: Placement = entrance.exterior
    pysa.player.location.teleport(exterior)
pysa.player.location.teleport((0, 0, 5), area=AREA.OUTSIDE,
                              heading=90, include_vehicle=True)
world_area: AREA = world.current_area()
world.set_area(AREA.OUTSIDE)


@pysa.dev_test
def typed_smoke_test() -> None:
    assert pysa.player.ped.exists


console: pysa.DeveloperConsole = pysa.DeveloperConsole()
test_run: pysa.TestRun = pysa.run_tests("typed")

waypoint = pysa.blips.waypoint()
if waypoint is not None:
    waypoint.x
marker = pysa.blips.add_short_range((0, 0, 0), pysa.BLIP_SPRITE.NONE)
marker.set_friendly()
marker.exists
pysa.camera.move((0, 0, 10), (20, 20, 10), 1000)
pysa.camera.interpolate_fov(70.0, 40.0, 500)
pysa.game.show_hud(True)
pysa.game.language()
scene = pysa.Cutscene("intro").load((0, 0, 0))
scene.loaded
mission_train = pysa.trains.spawn(0, (0, 0, 0))
mission_train.derailed
pysa.world.closest_straight_road((0, 0, 0)).start
