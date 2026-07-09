"""World state: clock, weather, gravity, spawning, queries.

    from pysa import world

    world.set_time(0, 0)                          # midnight
    world.force_weather(world.WEATHER.SANDSTORM)
    world.set_gravity(0.002)                      # moon mode (default 0.008)
    z = world.ground_z(x, y)
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import memory
from .entities import (GameObject, Ped, Vehicle, all_objects, all_peds,
                       all_vehicles, load_model, release_model)
from .math3 import Vector3
from .native import cmd

GRAVITY_ADDR = 0x863984
DEFAULT_GRAVITY = 0.008


class WEATHER:
    SUNNY_LA = 0
    SUNNY_SF = 1
    SUNNY_VEGAS = 2
    SUNNY_COUNTRYSIDE = 3
    SUNNY_DESERT = 4
    OVERCAST_LA = 7
    RAINY_SF = 8
    FOGGY_SF = 9
    RAINY_COUNTRYSIDE = 16
    SANDSTORM = 19
    UNDERWATER = 20


def get_time() -> tuple:
    """Current in-game clock as (hours, minutes)."""
    return cmd.GET_TIME_OF_DAY()


def set_time(hours: int, minutes: int = 0) -> None:
    cmd.SET_TIME_OF_DAY(hours, minutes)


def force_weather(weather_id: int) -> None:
    cmd.FORCE_WEATHER_NOW(weather_id)


def force_weather_later(weather_id: int) -> None:
    cmd.FORCE_WEATHER(weather_id)


def release_weather() -> None:
    """Let the weather cycle naturally again."""
    cmd.RELEASE_WEATHER()


def set_appropriate_weather_now() -> None:
    cmd.SET_WEATHER_TO_APPROPRIATE_TYPE_NOW()


def get_gravity() -> float:
    return memory.read_float(GRAVITY_ADDR)


def set_gravity(value: float) -> None:
    memory.write_float(GRAVITY_ADDR, float(value), True)


def ground_z(x: float, y: float, probe_z: float = 1000.0) -> float:
    """Height of the ground at (x, y)."""
    return cmd.GET_GROUND_Z_FOR_3D_COORD(x, y, probe_z)


def water_height(x: float, y: float, waves: bool = True) -> float:
    return cmd.GET_WATER_HEIGHT_AT_COORDS(x, y, waves)


def sync_water() -> None:
    cmd.SYNC_WATER()


def game_timer() -> int:
    return cmd.GET_GAME_TIMER()


def minutes_to_time(hours: int, minutes: int = 0) -> int:
    return cmd.GET_MINUTES_TO_TIME_OF_DAY(hours, minutes)


def one_day_forward() -> None:
    cmd.SET_TIME_ONE_DAY_FORWARD()


def random_int() -> int:
    return cmd.GENERATE_RANDOM_INT()


def random_int_range(min_value: int, max_value: int) -> int:
    return cmd.GENERATE_RANDOM_INT_IN_RANGE(min_value, max_value)


def random_float() -> float:
    return cmd.GENERATE_RANDOM_FLOAT()


def random_float_range(min_value: float, max_value: float) -> float:
    return cmd.GENERATE_RANDOM_FLOAT_IN_RANGE(min_value, max_value)


def current_area() -> int:
    return cmd.GET_AREA_VISIBLE()


def set_area(area_id: int) -> None:
    cmd.SET_AREA_VISIBLE(area_id)


def current_population_zone_type() -> int:
    return cmd.GET_CURRENT_POPULATION_ZONE_TYPE()


def zone_name(pos) -> str:
    x, y, z = Vector3.of(pos)
    return cmd.GET_NAME_OF_ZONE(x, y, z)


def info_zone_name(pos) -> str:
    x, y, z = Vector3.of(pos)
    return cmd.GET_NAME_OF_INFO_ZONE(x, y, z)


class EXPLOSION:
    GRENADE = 0
    MOLOTOV = 1
    ROCKET = 2
    CAR = 4
    HELI = 5
    BOAT = 7
    TANK = 8
    SMALL = 9
    TINY = 10


def explosion(pos, explosion_type: int = EXPLOSION.GRENADE) -> None:
    """Boom at pos."""
    x, y, z = Vector3.of(pos)
    cmd.ADD_EXPLOSION(x, y, z, explosion_type)


def explosion_no_sound(pos, explosion_type: int = EXPLOSION.GRENADE) -> None:
    x, y, z = Vector3.of(pos)
    cmd.ADD_EXPLOSION_NO_SOUND(x, y, z, explosion_type)


def explosion_shake(pos, explosion_type: int = EXPLOSION.GRENADE,
                    shake: float = 1.0) -> None:
    x, y, z = Vector3.of(pos)
    cmd.ADD_EXPLOSION_VARIABLE_SHAKE(x, y, z, explosion_type, shake)


def explosion_in_area(explosion_type: int, left_bottom, right_top) -> bool:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    return cmd.IS_EXPLOSION_IN_AREA(explosion_type, x1, y1, z1, x2, y2, z2)


def fire_single_bullet(from_pos, to_pos, damage: int = 75) -> None:
    x1, y1, z1 = Vector3.of(from_pos)
    x2, y2, z2 = Vector3.of(to_pos)
    cmd.FIRE_SINGLE_BULLET(x1, y1, z1, x2, y2, z2, damage)


def start_fire(pos, propagation: bool = True, size: int = 1) -> int:
    x, y, z = Vector3.of(pos)
    return cmd.START_SCRIPT_FIRE(x, y, z, propagation, size)


def fire_exists(handle: int) -> bool:
    return cmd.DOES_SCRIPT_FIRE_EXIST(handle)


def fire_coords(handle: int) -> Vector3:
    return Vector3(*cmd.GET_SCRIPT_FIRE_COORDS(handle))


def fire_extinguished(handle: int) -> bool:
    return cmd.IS_SCRIPT_FIRE_EXTINGUISHED(handle)


def remove_fire(handle: int) -> None:
    cmd.REMOVE_SCRIPT_FIRE(handle)


def remove_all_fires() -> None:
    cmd.REMOVE_ALL_SCRIPT_FIRES()


def extinguish_fire_at(pos, radius: float = 6.0) -> None:
    x, y, z = Vector3.of(pos)
    cmd.EXTINGUISH_FIRE_AT_POINT(x, y, z, radius)


def fire_count_in_range(pos, radius: float) -> int:
    x, y, z = Vector3.of(pos)
    return cmd.GET_NUMBER_OF_FIRES_IN_RANGE(x, y, z, radius)


def set_time_scale(scale: float) -> None:
    """Slow motion / fast forward (1.0 = normal, 0.3 = bullet time)."""
    cmd.SET_TIME_SCALE(scale)


def clear_area(pos, radius: float, clear_particles: bool = True) -> None:
    x, y, z = Vector3.of(pos)
    cmd.CLEAR_AREA(x, y, z, radius, clear_particles)


def clear_area_of_cars(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.CLEAR_AREA_OF_CARS(x1, y1, z1, x2, y2, z2)


def clear_area_of_peds(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.CLEAR_AREA_OF_CHARS(x1, y1, z1, x2, y2, z2)


def area_occupied(left_bottom, right_top, solid=True, cars=True,
                  chars=True, objects=True, particles=True) -> bool:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    return cmd.IS_AREA_OCCUPIED(x1, y1, z1, x2, y2, z2, solid, cars, chars, objects, particles)


def set_car_density(multiplier: float) -> None:
    cmd.SET_CAR_DENSITY_MULTIPLIER(multiplier)


def set_ped_density(multiplier: float) -> None:
    cmd.SET_PED_DENSITY_MULTIPLIER(multiplier)


def set_random_cops(enabled: bool = True) -> None:
    cmd.SET_CREATE_RANDOM_COPS(enabled)


def set_random_gang_members(enabled: bool = True) -> None:
    cmd.SET_CREATE_RANDOM_GANG_MEMBERS(enabled)


def set_disable_military_zones(enabled: bool = True) -> None:
    cmd.SET_DISABLE_MILITARY_ZONES(enabled)


def switch_random_trains(enabled: bool = True) -> None:
    cmd.SWITCH_RANDOM_TRAINS(enabled)


def switch_ambient_planes(enabled: bool = True) -> None:
    cmd.SWITCH_AMBIENT_PLANES(enabled)


def switch_police_helis(enabled: bool = True) -> None:
    cmd.SWITCH_POLICE_HELIS(enabled)


def switch_cops_on_bikes(enabled: bool = True) -> None:
    cmd.SWITCH_COPS_ON_BIKES(enabled)


def roads_on(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.SWITCH_ROADS_ON(x1, y1, z1, x2, y2, z2)


def roads_off(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.SWITCH_ROADS_OFF(x1, y1, z1, x2, y2, z2)


def roads_reset(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.SWITCH_ROADS_BACK_TO_ORIGINAL(x1, y1, z1, x2, y2, z2)


def ped_roads_on(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.SWITCH_PED_ROADS_ON(x1, y1, z1, x2, y2, z2)


def ped_roads_off(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.SWITCH_PED_ROADS_OFF(x1, y1, z1, x2, y2, z2)


def ped_roads_reset(left_bottom, right_top) -> None:
    x1, y1, z1 = Vector3.of(left_bottom)
    x2, y2, z2 = Vector3.of(right_top)
    cmd.SWITCH_PED_ROADS_BACK_TO_ORIGINAL(x1, y1, z1, x2, y2, z2)


def activate_garage(name: str) -> None:
    cmd.ACTIVATE_GARAGE(name)


def deactivate_garage(name: str) -> None:
    cmd.DEACTIVATE_GARAGE(name)


def open_garage(name: str) -> None:
    cmd.OPEN_GARAGE(name)


def close_garage(name: str) -> None:
    cmd.CLOSE_GARAGE(name)


def garage_open(name: str) -> bool:
    return cmd.IS_GARAGE_OPEN(name)


def garage_closed(name: str) -> bool:
    return cmd.IS_GARAGE_CLOSED(name)


def set_garage_respray_free(name: str, enabled: bool = True) -> None:
    cmd.SET_GARAGE_RESPRAY_FREE(name, enabled)


def set_target_vehicle_for_garage(name: str, vehicle: Vehicle) -> None:
    cmd.SET_TARGET_CAR_FOR_MISSION_GARAGE(name, vehicle)


def tag_percentage(left_bottom, right_top) -> int:
    x1, y1, _ = Vector3.of(left_bottom)
    x2, y2, _ = Vector3.of(right_top)
    return cmd.GET_PERCENTAGE_TAGGED_IN_AREA(x1, y1, x2, y2)


def set_tag_status(left_bottom, right_top, percent: int) -> None:
    x1, y1, _ = Vector3.of(left_bottom)
    x2, y2, _ = Vector3.of(right_top)
    cmd.SET_TAG_STATUS_IN_AREA(x1, y1, x2, y2, percent)


# Spawning shortcuts (see entities.py for the full API)
spawn_vehicle = Vehicle.spawn
spawn_ped = Ped.spawn
spawn_object = GameObject.spawn

peds = all_peds
vehicles = all_vehicles
objects = all_objects
