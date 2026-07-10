"""World state: clock, weather, gravity, spawning, queries.

    from pysa import world

    world.set_time(0, 0)                          # midnight
    world.force_weather(world.WEATHER.SANDSTORM)
    world.set_gravity(0.002)                      # moon mode (default 0.008)
    z = world.ground_z(x, y)
"""
from __future__ import annotations

from enum import IntEnum
from typing import (Callable, Generic, Iterator, Optional, Protocol, TypeVar,
                    Union, overload)

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import memory
from .entities import (Building, Dummy, GameObject, Ped, Vehicle,
                       all_buildings, all_dummies,
                       all_objects, all_peds, all_vehicles, entity_from_ptr,
                       load_model, release_model)
from .enums import EXPLOSION_KIND, SURFACE
from .math3 import Vector3
from .native import cmd
from .pickups import Pickup, all_pickups
from .type_aliases import Position


TEntity = TypeVar("TEntity")


class _Positioned(Protocol):
    @property
    def pos(self) -> Vector3: ...


SpatialTarget = Union[Position, _Positioned]

GRAVITY_ADDR = 0x863984
DEFAULT_GRAVITY = 0.008


class WEATHER(IntEnum):
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


class RaycastHit:
    """One collision returned by :func:`raycast`."""

    __slots__ = ("position", "normal", "entity", "surface", "piece",
                 "daylight", "nightlight", "depth")

    def __init__(self, position, normal, entity, surface, piece: int,
                 daylight: int, nightlight: int, depth: float):
        self.position = Vector3.of(position)
        self.normal = Vector3.of(normal)
        self.entity = entity
        try:
            self.surface = SURFACE(surface)
        except ValueError:
            self.surface = int(surface)
        self.piece = int(piece)
        self.daylight = int(daylight)
        self.nightlight = int(nightlight)
        self.depth = float(depth)

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return (f"RaycastHit(position={self.position!r}, "
                f"surface={self.surface!r}, entity={self.entity!r})")


def raycast(start: Position, end: Position, *, ignore=None,
            buildings: bool = True,
            vehicles: bool = True, peds: bool = True,
            objects: bool = True, dummies: bool = True,
            see_through: bool = False, camera_ignore: bool = False,
            shoot_through: bool = False) -> Optional[RaycastHit]:
    """Cast a line through the world and return a :class:`RaycastHit`.

    ``ignore`` may be an entity that should not block the ray, commonly the
    player or the object firing it. Returns ``None`` when nothing was hit.
    """
    sx, sy, sz = Vector3.of(start)
    ex, ey, ez = Vector3.of(end)
    ignore_ptr = int(getattr(ignore, "address", ignore or 0))
    result = _pysa.world_raycast(
        sx, sy, sz, ex, ey, ez, ignore_ptr, bool(buildings), bool(vehicles),
        bool(peds), bool(objects), bool(dummies), bool(see_through),
        bool(camera_ignore), bool(shoot_through))
    if result is None:
        return None
    px, py, pz, nx, ny, nz, entity_ptr, surface, piece, day, night, depth = result
    return RaycastHit((px, py, pz), (nx, ny, nz),
                      entity_from_ptr(entity_ptr), surface, piece, day, night,
                      depth)


def line_of_sight(start, end, **filters) -> bool:
    """True when no enabled world category blocks the line between two points."""
    return raycast(start, end, **filters) is None


def get_time() -> tuple[int, int]:
    """Current in-game clock as (hours, minutes)."""
    return cmd.GET_TIME_OF_DAY()


def set_time(hours: int, minutes: int = 0) -> None:
    cmd.SET_TIME_OF_DAY(hours, minutes)


def force_weather(weather_id: WEATHER) -> None:
    cmd.FORCE_WEATHER_NOW(weather_id)


def force_weather_later(weather_id: WEATHER) -> None:
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


# Script-created explosions use the same eExplosionType values as the game.
EXPLOSION = EXPLOSION_KIND


def explosion(pos, explosion_type: EXPLOSION = EXPLOSION.GRENADE) -> None:
    """Boom at pos."""
    x, y, z = Vector3.of(pos)
    cmd.ADD_EXPLOSION(x, y, z, explosion_type)


def explosion_no_sound(pos, explosion_type: EXPLOSION = EXPLOSION.GRENADE) -> None:
    x, y, z = Vector3.of(pos)
    cmd.ADD_EXPLOSION_NO_SOUND(x, y, z, explosion_type)


def explosion_shake(pos, explosion_type: EXPLOSION = EXPLOSION.GRENADE,
                    shake: float = 1.0) -> None:
    x, y, z = Vector3.of(pos)
    cmd.ADD_EXPLOSION_VARIABLE_SHAKE(x, y, z, explosion_type, shake)


def explosion_in_area(explosion_type: EXPLOSION, left_bottom, right_top) -> bool:
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


class Fire:
    """A script-started fire you can hold onto and query."""

    __slots__ = ("_handle",)

    def __init__(self, pos=None, propagation: bool = True, size: int = 1,
                 handle: int = None):
        if handle is not None:
            self._handle = handle
        else:
            x, y, z = Vector3.of(pos)
            self._handle = cmd.START_SCRIPT_FIRE(x, y, z, propagation, size)

    @property
    def handle(self) -> int:
        return self._handle

    @property
    def exists(self) -> bool:
        return cmd.DOES_SCRIPT_FIRE_EXIST(self._handle)

    @property
    def extinguished(self) -> bool:
        return cmd.IS_SCRIPT_FIRE_EXTINGUISHED(self._handle)

    @property
    def pos(self) -> Vector3:
        return Vector3(*cmd.GET_SCRIPT_FIRE_COORDS(self._handle))

    def remove(self) -> None:
        cmd.REMOVE_SCRIPT_FIRE(self._handle)

    def __repr__(self) -> str:
        return f"Fire(handle={self._handle})"


def light_fire(pos, propagation: bool = True, size: int = 1) -> Fire:
    """Start a fire and get a Fire object back (OOP form of start_fire)."""
    return Fire(pos, propagation, size)


# ---------------------------------------------------------------------------
# Spatial queries over the live entity pools
# ---------------------------------------------------------------------------

def _as_pos(target: SpatialTarget) -> Vector3:
    return target.pos if hasattr(target, "pos") else Vector3.of(target)


def _near(items: list[TEntity], origin: SpatialTarget, radius: float,
          exclude: Optional[TEntity]) -> list[TEntity]:
    o = _as_pos(origin)
    out = [(e.pos.distance_to(o), e) for e in items if e != exclude]
    return [e for d, e in sorted(out, key=lambda t: t[0]) if d <= radius]


def _nearest(items: list[TEntity], origin: SpatialTarget,
             max_dist: Optional[float],
             exclude: Optional[TEntity]) -> Optional[TEntity]:
    o = _as_pos(origin)
    best, best_d = None, None
    for e in items:
        if e == exclude:
            continue
        d = e.pos.distance_to(o)
        if best_d is None or d < best_d:
            best, best_d = e, d
    if best is None or (max_dist is not None and best_d > max_dist):
        return None
    return best


def peds_near(origin: SpatialTarget, radius: float,
              exclude: Optional[Ped] = None) -> list[Ped]:
    """Peds within `radius` of a position/entity, nearest first."""
    return _near(all_peds(), origin, radius, exclude)


def vehicles_near(origin: SpatialTarget, radius: float,
                  exclude: Optional[Vehicle] = None) -> list[Vehicle]:
    return _near(all_vehicles(), origin, radius, exclude)


def objects_near(origin: SpatialTarget, radius: float,
                 exclude: Optional[GameObject] = None) -> list[GameObject]:
    return _near(all_objects(), origin, radius, exclude)


def nearest_ped(origin: SpatialTarget, max_dist: Optional[float] = None,
                exclude: Optional[Ped] = None) -> Optional[Ped]:
    """The closest ped to a position/entity, or None."""
    return _nearest(all_peds(), origin, max_dist, exclude)


def nearest_vehicle(origin: SpatialTarget, max_dist: Optional[float] = None,
                    exclude: Optional[Vehicle] = None) -> Optional[Vehicle]:
    return _nearest(all_vehicles(), origin, max_dist, exclude)


def nearest_object(origin: SpatialTarget, max_dist: Optional[float] = None,
                   exclude: Optional[GameObject] = None) -> Optional[GameObject]:
    return _nearest(all_objects(), origin, max_dist, exclude)


class EntityCollection(Generic[TEntity]):
    """A live, iterable view over a game entity pool.

    Iterate it directly (it re-reads the pool each time):

        for car in world.vehicles:          # no parentheses needed
            car.explode()

        len(world.peds)                      # how many peds exist
        world.vehicles[0]                    # first vehicle
        world.vehicles(...)                  # still callable -> a plain list
        world.vehicles.near(player.pos, 30)  # nearest-first within radius
        world.peds.nearest(player.pos, exclude=player.ped)
        world.vehicles.where(lambda v: v.health < 300)
    """

    __slots__ = ("_fetch", "_name")

    def __init__(self, fetch: Callable[[], list[TEntity]], name: str):
        self._fetch = fetch
        self._name = name

    def __iter__(self) -> Iterator[TEntity]:
        return iter(self._fetch())

    def __len__(self) -> int:
        return len(self._fetch())

    @overload
    def __getitem__(self, index: int) -> TEntity: ...

    @overload
    def __getitem__(self, index: slice) -> list[TEntity]: ...

    def __getitem__(self, index):
        return self._fetch()[index]

    def __call__(self) -> list[TEntity]:
        """Back-compat: world.vehicles() returns a plain list snapshot."""
        return self._fetch()

    def __repr__(self) -> str:
        return f"<{self._name}: {len(self)} live>"

    def near(self, origin: SpatialTarget, radius: float,
             exclude: Optional[TEntity] = None) -> list[TEntity]:
        """Members within `radius` of a position/entity, nearest first."""
        return _near(self._fetch(), origin, radius, exclude)

    def nearest(self, origin: SpatialTarget, max_dist: Optional[float] = None,
                exclude: Optional[TEntity] = None) -> Optional[TEntity]:
        """The closest member to a position/entity, or None."""
        return _nearest(self._fetch(), origin, max_dist, exclude)

    def where(self, predicate: Callable[[TEntity], bool]) -> list[TEntity]:
        """Members matching a predicate: world.vehicles.where(lambda v: ...)."""
        return [e for e in self._fetch() if predicate(e)]

    def of_model(self, model) -> list[TEntity]:
        """Members of a given model id (vehicles also accept a name, e.g. 'rhino')."""
        if isinstance(model, str):
            from .models import vehicle_id
            model = vehicle_id(model)
        model = int(model)
        return [e for e in self._fetch() if getattr(e, "model", None) == model]

    def count(self) -> int:
        return len(self._fetch())


# Spawning shortcuts (see entities.py for the full API)
spawn_vehicle = Vehicle.spawn
spawn_ped = Ped.spawn
spawn_object = GameObject.spawn

#: Live, iterable views over the entity pools (iterate without parentheses).
peds: EntityCollection[Ped] = EntityCollection(all_peds, "peds")
vehicles: EntityCollection[Vehicle] = EntityCollection(all_vehicles, "vehicles")
objects: EntityCollection[GameObject] = EntityCollection(all_objects, "objects")
buildings: EntityCollection[Building] = EntityCollection(all_buildings, "buildings")
dummies: EntityCollection[Dummy] = EntityCollection(all_dummies, "dummies")
pickups: EntityCollection[Pickup] = EntityCollection(all_pickups, "pickups")
