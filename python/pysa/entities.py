"""Ped, Vehicle and GameObject wrappers.

Entities wrap SCM handles and expose game state as properties:

    veh = Vehicle.spawn('infernus')          # in front of the player
    veh.pos = (2488, -1666, 13.5)            # ints fine, coerced to floats
    veh.heading = 180
    print(veh.speed, veh.health, veh.driver)

    ped = Ped.spawn(167, player.pos + (3, 0, 0))
    ped.give_weapon(WEAPON.AK47)
    ped.tasks.attack(player.ped)

Any entity can be passed straight into cmd.*/call() wherever a script
command expects a car/char/object handle.
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .math3 import Vector3
from .models import PED_TYPE, vehicle_id
from .native import cmd


def load_model(model: int, timeout_frames: int = 200) -> bool:
    """Request a model and block until it is streamed in (or give up)."""
    cmd.REQUEST_MODEL(int(model))
    cmd.LOAD_ALL_MODELS_NOW()
    if cmd.HAS_MODEL_LOADED(int(model)):
        return True
    for _ in range(timeout_frames):
        if cmd.HAS_MODEL_LOADED(int(model)):
            return True
    return False


def release_model(model: int) -> None:
    cmd.MARK_MODEL_AS_NO_LONGER_NEEDED(int(model))


def _xy(value) -> tuple[float, float]:
    if isinstance(value, Vector3):
        return value.x, value.y
    x, y, *_ = value
    return float(x), float(y)


class Entity:
    """Base wrapper around an SCM handle."""

    __slots__ = ("_handle",)

    def __init__(self, handle):
        self._handle = int(getattr(handle, "_handle", handle))

    @property
    def handle(self) -> int:
        return self._handle

    def __eq__(self, other) -> bool:
        return isinstance(other, Entity) and other._handle == self._handle

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._handle))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(handle={self._handle}, addr=0x{self.address:08X})"

    # subclasses override
    _ptr_of = staticmethod(lambda h: 0)
    _handle_of = staticmethod(lambda p: -1)

    @classmethod
    def from_ptr(cls, ptr: int):
        """Wrap a raw game object pointer (e.g. from a created/destroyed event)."""
        return cls(cls._handle_of(ptr))

    @property
    def address(self) -> int:
        """Address of the underlying game object (0 if it no longer exists)."""
        return self._ptr_of(self._handle)

    @property
    def exists(self) -> bool:
        return self._handle != -1 and self.address != 0

    _struct_class = None  # subclasses set the C++ class name

    @property
    def struct(self):
        """Typed view over the raw game object (see pysa.gamestruct)."""
        from .gamestruct import Struct
        addr = self.address
        if not addr:
            raise ValueError(f"{type(self).__name__} {self._handle} has no live address")
        return Struct(addr, self._struct_class or "CEntity")

    def dont_remove(self) -> None:
        """Keep the entity out of mission cleanup where the game supports it."""
        if isinstance(self, Ped):
            cmd.DONT_REMOVE_CHAR(self)
        elif isinstance(self, GameObject):
            cmd.DONT_REMOVE_OBJECT(self)

    def no_longer_needed(self) -> None:
        """Release the entity back to game cleanup where the game supports it."""
        if isinstance(self, Ped):
            cmd.MARK_CHAR_AS_NO_LONGER_NEEDED(self)
        elif isinstance(self, Vehicle):
            cmd.MARK_CAR_AS_NO_LONGER_NEEDED(self)
        elif isinstance(self, GameObject):
            cmd.MARK_OBJECT_AS_NO_LONGER_NEEDED(self)

    # -- spatial helpers (work on any positioned entity) -------------------

    def distance_to(self, target) -> float:
        """Distance to a position, or to another entity."""
        other = target.pos if isinstance(target, Entity) else target
        return self.pos.distance_to(other)

    def is_near(self, target, radius: float) -> bool:
        """True if within `radius` game units of a position or entity."""
        return self.distance_to(target) <= radius

    def direction_to(self, target) -> Vector3:
        """Unit vector from this entity toward a position or entity."""
        other = target.pos if isinstance(target, Entity) else Vector3.of(target)
        return (other - self.pos).normalized()

    def heading_to(self, target) -> float:
        """Compass heading (degrees) that would face this entity at `target`."""
        import math
        other = target.pos if isinstance(target, Entity) else Vector3.of(target)
        d = other - self.pos
        return math.degrees(math.atan2(-d.x, d.y)) % 360.0

    def face(self, target) -> None:
        """Turn to face a position or entity (sets heading)."""
        self.heading = self.heading_to(target)

    # -- blips --------------------------------------------------------------

    def add_blip(self, color: int = None, scale: int = None):
        """Attach a radar blip that tracks this entity; returns a blips.Blip."""
        from . import blips
        if isinstance(self, Ped):
            blip = blips.add_for_char(self)
        elif isinstance(self, Vehicle):
            blip = blips.add_for_car(self)
        else:
            blip = blips.add_for_object(self)
        if color is not None:
            blip.color = color
        if scale is not None:
            blip.scale = scale
        return blip


class PedTasks:
    """AI task shortcuts for a ped: `ped.tasks.wander()`, `.attack(target)`..."""

    __slots__ = ("_ped",)

    def __init__(self, ped: "Ped"):
        self._ped = ped

    def clear(self, immediately: bool = False) -> None:
        if immediately:
            cmd.CLEAR_CHAR_TASKS_IMMEDIATELY(self._ped)
        else:
            cmd.CLEAR_CHAR_TASKS(self._ped)

    def wander(self) -> None:
        cmd.TASK_WANDER_STANDARD(self._ped)

    def go_to(self, pos, mode: int = 4) -> None:
        """Walk/run to a point. mode: 4=walk, 6=run, 7=sprint (MoveState)."""
        x, y, z = Vector3.of(pos)
        cmd.TASK_GO_STRAIGHT_TO_COORD(self._ped, x, y, z, mode, -1)

    def enter_vehicle(self, vehicle: "Vehicle", seat: int = None,
                      timeout_ms: int = 10000) -> None:
        """Enter as driver (seat None) or passenger seat 0..3."""
        if seat is None:
            cmd.TASK_ENTER_CAR_AS_DRIVER(self._ped, vehicle, timeout_ms)
        else:
            cmd.TASK_ENTER_CAR_AS_PASSENGER(self._ped, vehicle, timeout_ms, seat)

    def leave_vehicle(self, vehicle: "Vehicle" = None) -> None:
        veh = vehicle or self._ped.vehicle
        if veh is not None:
            cmd.TASK_LEAVE_CAR(self._ped, veh)

    def attack(self, target: "Ped") -> None:
        cmd.TASK_KILL_CHAR_ON_FOOT(self._ped, target)

    def flee_from(self, target: "Ped", distance: float = 100.0,
                  duration_ms: int = 10000) -> None:
        cmd.TASK_SMART_FLEE_CHAR(self._ped, target, distance, duration_ms)

    def drive_around(self, vehicle: "Vehicle", speed: float = 15.0,
                     driving_mode: int = 0) -> None:
        cmd.TASK_CAR_DRIVE_WANDER(self._ped, vehicle, speed, driving_mode)

    def look_at(self, target: "Ped", duration_ms: int = 4000) -> None:
        cmd.TASK_LOOK_AT_CHAR(self._ped, target, duration_ms)

    def hands_up(self, duration_ms: int = 4000) -> None:
        cmd.TASK_HANDS_UP(self._ped, duration_ms)

    def duck(self, duration_ms: int = 4000) -> None:
        cmd.TASK_DUCK(self._ped, duration_ms)

    def play_anim(self, anim: str, group: str, blend: float = 4.0,
                  loop: bool = False, duration_ms: int = -1) -> None:
        """Play an animation (loads the group if needed), e.g. ('idle_chat', 'ped')."""
        if not cmd.HAS_ANIMATION_LOADED(group):
            cmd.REQUEST_ANIMATION(group)
            cmd.LOAD_ALL_MODELS_NOW()
        cmd.TASK_PLAY_ANIM(self._ped, anim, group, blend, int(loop), 0, 0, 0,
                           duration_ms)

    def aim_at(self, target: "Ped", duration_ms: int = 4000) -> None:
        cmd.TASK_AIM_GUN_AT_CHAR(self._ped, target, duration_ms)

    def shoot_at(self, target: "Ped", duration_ms: int = 4000) -> None:
        cmd.TASK_SHOOT_AT_CHAR(self._ped, target, duration_ms)

    def turn_to(self, target: "Ped") -> None:
        cmd.TASK_TURN_CHAR_TO_FACE_CHAR(self._ped, target)

    def turn_to_coord(self, pos) -> None:
        x, y, z = Vector3.of(pos)
        cmd.TASK_TURN_CHAR_TO_FACE_COORD(self._ped, x, y, z)

    def swim_to(self, pos) -> None:
        x, y, z = Vector3.of(pos)
        cmd.TASK_SWIM_TO_COORD(self._ped, x, y, z)

    def leave_vehicle_immediately(self, vehicle: "Vehicle" = None) -> None:
        veh = vehicle or self._ped.vehicle
        if veh is not None:
            cmd.TASK_LEAVE_CAR_IMMEDIATELY(self._ped, veh)


class PedWeapons:
    """Weapon inventory facade: `ped.weapons.give(...)`, `.ammo(...)`, `.current`."""

    __slots__ = ("_ped",)

    def __init__(self, ped: "Ped"):
        self._ped = ped

    @property
    def current(self) -> int:
        return self._ped.current_weapon

    @current.setter
    def current(self, weapon: int) -> None:
        self._ped.current_weapon = weapon

    def give(self, weapon: int, ammo: int = 500, equip: bool = True) -> None:
        self._ped.give_weapon(weapon, ammo, equip)

    def remove(self, weapon: int) -> None:
        self._ped.remove_weapon(weapon)

    def clear(self) -> None:
        self._ped.remove_weapons()

    def has(self, weapon: int) -> bool:
        return self._ped.has_weapon(weapon)

    def ammo(self, weapon: int) -> int:
        return self._ped.ammo(weapon)

    def set_ammo(self, weapon: int, ammo: int) -> None:
        self._ped.set_ammo(weapon, ammo)

    def add_ammo(self, weapon: int, ammo: int) -> None:
        self._ped.add_ammo(weapon, ammo)

    def slot(self, slot: int) -> tuple[int, int, int]:
        return self._ped.weapon_in_slot(slot)


class Ped(Entity):
    """A character. The player's own ped is `pysa.player.ped`."""

    __slots__ = ()
    _struct_class = "CPed"
    _ptr_of = staticmethod(_pysa.ped_ptr)
    _handle_of = staticmethod(_pysa.ped_handle)

    @classmethod
    def spawn(cls, model: int, pos, ped_type: int = PED_TYPE.CIVMALE) -> "Ped":
        if not load_model(model):
            raise RuntimeError(f"ped model {model} failed to load")
        x, y, z = Vector3.of(pos)
        ped = cmd.CREATE_CHAR(ped_type, model, x, y, z)
        release_model(model)
        return ped

    @property
    def tasks(self) -> PedTasks:
        return PedTasks(self)

    @property
    def weapons(self) -> PedWeapons:
        return PedWeapons(self)

    @property
    def pos(self) -> Vector3:
        return Vector3(*cmd.GET_CHAR_COORDINATES(self))

    @pos.setter
    def pos(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CHAR_COORDINATES(self, x, y, z)

    @property
    def heading(self) -> float:
        return cmd.GET_CHAR_HEADING(self)

    @heading.setter
    def heading(self, degrees: float) -> None:
        cmd.SET_CHAR_HEADING(self, degrees)

    @property
    def health(self) -> int:
        return cmd.GET_CHAR_HEALTH(self)

    @health.setter
    def health(self, value: int) -> None:
        cmd.SET_CHAR_HEALTH(self, value)

    @property
    def armour(self) -> int:
        return cmd.GET_CHAR_ARMOUR(self)

    @armour.setter
    def armour(self, value: int) -> None:
        # No SET_CHAR_ARMOUR in vanilla SA; CPed::m_fArmour is at +0x548.
        addr = self.address
        if addr:
            _pysa.write_f32(addr + 0x548, float(value))

    @property
    def max_health(self) -> float:
        addr = self.address
        return _pysa.read_f32(addr + 0x544) if addr else 0.0

    @max_health.setter
    def max_health(self, value: int) -> None:
        cmd.SET_CHAR_MAX_HEALTH(self, value)

    @property
    def money(self) -> int:
        # No GET_CHAR_MONEY in vanilla SA; CPed::m_nMoneyCount is at +0x756.
        addr = self.address
        return _pysa.read_u16(addr + 0x756) if addr else 0

    @money.setter
    def money(self, value: int) -> None:
        cmd.SET_CHAR_MONEY(self, value)

    @property
    def is_dead(self) -> bool:
        return cmd.IS_CHAR_DEAD(self)

    @property
    def alive(self) -> bool:
        return not self.is_dead

    @property
    def stopped(self) -> bool:
        return cmd.IS_CHAR_STOPPED(self)

    @property
    def on_screen(self) -> bool:
        return cmd.IS_CHAR_ON_SCREEN(self)

    @property
    def in_water(self) -> bool:
        return cmd.IS_CHAR_IN_WATER(self)

    @property
    def swimming(self) -> bool:
        return cmd.IS_CHAR_SWIMMING(self)

    @property
    def swim_state(self) -> int:
        return cmd.GET_CHAR_SWIM_STATE(self)

    @property
    def area_visible(self) -> int:
        return cmd.GET_CHAR_AREA_VISIBLE(self)

    @area_visible.setter
    def area_visible(self, area_id: int) -> None:
        cmd.SET_CHAR_AREA_VISIBLE(self, area_id)

    @property
    def on_foot(self) -> bool:
        return cmd.IS_CHAR_ON_FOOT(self)

    @property
    def in_any_vehicle(self) -> bool:
        return cmd.IS_CHAR_IN_ANY_CAR(self)

    @property
    def sitting_in_vehicle(self) -> bool:
        return cmd.IS_CHAR_SITTING_IN_ANY_CAR(self)

    @property
    def getting_into_vehicle(self) -> bool:
        return cmd.IS_CHAR_GETTING_IN_TO_A_CAR(self)

    @property
    def attached_vehicle(self):
        if not cmd.IS_CHAR_ATTACHED_TO_ANY_CAR(self):
            return None
        return cmd.STORE_CAR_CHAR_IS_ATTACHED_TO_NO_SAVE(self)

    @property
    def vehicle(self):
        """The vehicle this ped is in, or None."""
        if not self.in_any_vehicle:
            return None
        return cmd.STORE_CAR_CHAR_IS_IN_NO_SAVE(self)

    @property
    def velocity(self) -> Vector3:
        return Vector3(*cmd.GET_CHAR_VELOCITY(self))

    @velocity.setter
    def velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CHAR_VELOCITY(self, x, y, z)

    @property
    def speed(self) -> float:
        return cmd.GET_CHAR_SPEED(self)

    @property
    def height_above_ground(self) -> float:
        return cmd.GET_CHAR_HEIGHT_ABOVE_GROUND(self)

    @property
    def model(self) -> int:
        return cmd.GET_CHAR_MODEL(self)

    @property
    def current_weapon(self) -> int:
        return cmd.GET_CURRENT_CHAR_WEAPON(self)

    @current_weapon.setter
    def current_weapon(self, weapon: int) -> None:
        cmd.SET_CURRENT_CHAR_WEAPON(self, weapon)

    def give_weapon(self, weapon: int, ammo: int = 500, equip: bool = True) -> None:
        model = cmd.GET_WEAPONTYPE_MODEL(weapon)
        if model > 0:
            load_model(model)
        cmd.GIVE_WEAPON_TO_CHAR(self, weapon, ammo)
        if equip:
            cmd.SET_CURRENT_CHAR_WEAPON(self, weapon)
        if model > 0:
            release_model(model)

    def remove_weapons(self) -> None:
        cmd.REMOVE_ALL_CHAR_WEAPONS(self)

    def remove_weapon(self, weapon: int) -> None:
        cmd.REMOVE_WEAPON_FROM_CHAR(self, weapon)

    def has_weapon(self, weapon: int) -> bool:
        return cmd.HAS_CHAR_GOT_WEAPON(self, weapon)

    def ammo(self, weapon: int) -> int:
        return cmd.GET_AMMO_IN_CHAR_WEAPON(self, weapon)

    def set_ammo(self, weapon: int, ammo: int) -> None:
        cmd.SET_CHAR_AMMO(self, weapon, ammo)

    def add_ammo(self, weapon: int, ammo: int) -> None:
        cmd.ADD_AMMO_TO_CHAR(self, weapon, ammo)

    def weapon_in_slot(self, slot: int) -> tuple[int, int, int]:
        """Return (weapon_type, ammo, model) for a weapon slot."""
        return cmd.GET_CHAR_WEAPON_IN_SLOT(self, slot)

    @property
    def last_weapon_damage(self) -> int:
        addr = self.address
        return _pysa.read_u32(addr + 0x760) if addr else 0

    def damaged_by_weapon(self, weapon: int) -> bool:
        return cmd.HAS_CHAR_BEEN_DAMAGED_BY_WEAPON(self, weapon)

    def damaged_by_char(self, other: "Ped") -> bool:
        return cmd.HAS_CHAR_BEEN_DAMAGED_BY_CHAR(self, other)

    def damaged_by_vehicle(self, vehicle: "Vehicle") -> bool:
        return cmd.HAS_CHAR_BEEN_DAMAGED_BY_CAR(self, vehicle)

    def clear_last_weapon_damage(self) -> None:
        cmd.CLEAR_CHAR_LAST_WEAPON_DAMAGE(self)

    def clear_last_damage_entity(self) -> None:
        cmd.CLEAR_CHAR_LAST_DAMAGE_ENTITY(self)

    def set_accuracy(self, percent: int) -> None:
        cmd.SET_CHAR_ACCURACY(self, percent)

    def set_shoot_rate(self, rate: int) -> None:
        cmd.SET_CHAR_SHOOT_RATE(self, rate)

    def set_weapon_skill(self, skill: int) -> None:
        cmd.SET_CHAR_WEAPON_SKILL(self, skill)

    def set_fighting_style(self, style: int, moves: int = 6) -> None:
        cmd.GIVE_MELEE_ATTACK_TO_CHAR(self, style, moves)

    def damage(self, amount: int, damage_armour: bool = True) -> None:
        cmd.DAMAGE_CHAR(self, amount, damage_armour)

    def freeze(self, frozen: bool = True) -> None:
        cmd.FREEZE_CHAR_POSITION(self, frozen)

    def collision(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_COLLISION(self, enabled)

    def visible(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_VISIBLE(self, enabled)

    def bleeding(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_BLEEDING(self, enabled)

    def stay_in_same_place(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_STAY_IN_SAME_PLACE(self, enabled)

    def can_duck(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_ALLOWED_TO_DUCK(self, enabled)

    def drowns_in_water(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_DROWNS_IN_WATER(self, enabled)

    def wanted_by_police(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_WANTED_BY_POLICE(self, enabled)

    def only_damaged_by_player(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_ONLY_DAMAGED_BY_PLAYER(self, enabled)

    def can_be_shot_in_vehicle(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_CAN_BE_SHOT_IN_VEHICLE(self, enabled)

    def stay_in_car_when_jacked(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_STAY_IN_CAR_WHEN_JACKED(self, enabled)

    def drops_weapons_when_dead(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_DROPS_WEAPONS_WHEN_DEAD(self, enabled)

    def never_leaves_group(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_NEVER_LEAVES_GROUP(self, enabled)

    def keep_task(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_KEEP_TASK(self, enabled)

    def drugged_up(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_DRUGGED_UP(self, enabled)

    def force_die_in_car(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_FORCE_DIE_IN_CAR(self, enabled)

    def get_out_upside_down_car(self, enabled: bool = True) -> None:
        cmd.SET_CHAR_GET_OUT_UPSIDE_DOWN_CAR(self, enabled)

    def talking(self) -> bool:
        return cmd.IS_CHAR_TALKING(self)

    def disable_speech(self, stop_now: bool = False) -> None:
        cmd.DISABLE_CHAR_SPEECH(self, stop_now)

    def enable_speech(self) -> None:
        cmd.ENABLE_CHAR_SPEECH(self)

    def start_facial_talk(self, duration_ms: int = 4000) -> None:
        cmd.START_CHAR_FACIAL_TALK(self, duration_ms)

    def stop_facial_talk(self) -> None:
        cmd.STOP_CHAR_FACIAL_TALK(self)

    def make_proof(self, bullet=True, fire=True, explosion=True,
                   collision=True, melee=True) -> None:
        cmd.SET_CHAR_PROOFS(self, bullet, fire, explosion, collision, melee)

    def warp_into(self, vehicle: "Vehicle") -> None:
        cmd.WARP_CHAR_INTO_CAR(self, vehicle)

    def warp_into_passenger(self, vehicle: "Vehicle", seat: int = 0) -> None:
        cmd.WARP_CHAR_INTO_CAR_AS_PASSENGER(self, vehicle, seat)

    def warp_out(self, pos=None) -> None:
        p = Vector3.of(pos) if pos is not None else self.pos
        cmd.WARP_CHAR_FROM_CAR_TO_COORD(self, p.x, p.y, p.z)

    def delete(self) -> None:
        cmd.DELETE_CHAR(self)


class VehicleDoor:
    """One vehicle door/panel index facade."""

    __slots__ = ("_vehicle", "_index")

    def __init__(self, vehicle: "Vehicle", index: int):
        self._vehicle = vehicle
        self._index = int(index)

    @property
    def index(self) -> int:
        return self._index

    @property
    def angle(self) -> float:
        return self._vehicle.door_angle_ratio(self._index)

    @angle.setter
    def angle(self, ratio: float) -> None:
        self._vehicle.open_door_ratio(self._index, ratio)

    @property
    def damaged(self) -> bool:
        return self._vehicle.door_damaged(self._index)

    @property
    def fully_open(self) -> bool:
        return self._vehicle.door_fully_open(self._index)

    def open(self) -> None:
        self._vehicle.open_door(self._index)

    def close_all(self) -> None:
        self._vehicle.close_doors()

    def damage(self) -> None:
        self._vehicle.damage_door(self._index)

    def fix(self) -> None:
        self._vehicle.fix_door(self._index)

    def pop(self, visible: bool = True) -> None:
        self._vehicle.pop_door(self._index, visible)


class VehicleDoors:
    """Door collection facade: `car.doors[0].open()`, `car.doors.close_all()`."""

    __slots__ = ("_vehicle",)

    def __init__(self, vehicle: "Vehicle"):
        self._vehicle = vehicle

    def __getitem__(self, index: int) -> VehicleDoor:
        return VehicleDoor(self._vehicle, index)

    def close_all(self) -> None:
        self._vehicle.close_doors()

    def lock(self, locked: bool = True) -> None:
        self._vehicle.lock(locked)

    @property
    def lock_status(self) -> int:
        return self._vehicle.door_lock_status

    @lock_status.setter
    def lock_status(self, status: int) -> None:
        self._vehicle.set_lock_status(status)


class VehicleTyre:
    """One vehicle tyre facade."""

    __slots__ = ("_vehicle", "_index")

    def __init__(self, vehicle: "Vehicle", index: int):
        self._vehicle = vehicle
        self._index = int(index)

    def burst(self) -> None:
        self._vehicle.burst_tyre(self._index)

    def fix(self) -> None:
        self._vehicle.fix_tyre(self._index)


class VehicleTyres:
    """Tyre collection facade: `car.tyres[2].burst()`."""

    __slots__ = ("_vehicle",)

    def __init__(self, vehicle: "Vehicle"):
        self._vehicle = vehicle

    def __getitem__(self, index: int) -> VehicleTyre:
        return VehicleTyre(self._vehicle, index)

    def can_burst(self, enabled: bool = True) -> None:
        self._vehicle.tyres_can_burst(enabled)


class VehicleDamage:
    """Damage/proofing facade for a vehicle."""

    __slots__ = ("_vehicle",)

    def __init__(self, vehicle: "Vehicle"):
        self._vehicle = vehicle

    @property
    def visible(self) -> bool:
        return self._vehicle.visibly_damaged

    def can_be_damaged(self, enabled: bool = True) -> None:
        self._vehicle.can_be_damaged(enabled)

    def can_be_visibly_damaged(self, enabled: bool = True) -> None:
        self._vehicle.can_be_visibly_damaged(enabled)

    def only_by_player(self, enabled: bool = True) -> None:
        self._vehicle.only_damaged_by_player(enabled)

    def proofs(self, bullet=True, fire=True, explosion=True,
               collision=True, melee=True) -> None:
        self._vehicle.make_proof(bullet, fire, explosion, collision, melee)

    def by_weapon(self, weapon: int) -> bool:
        return self._vehicle.damaged_by_weapon(weapon)

    def by_ped(self, ped: Ped) -> bool:
        return self._vehicle.damaged_by_ped(ped)

    def by_vehicle(self, other: "Vehicle") -> bool:
        return self._vehicle.damaged_by_vehicle(other)

    def clear_weapon(self) -> None:
        self._vehicle.clear_last_weapon_damage()

    def clear_entity(self) -> None:
        self._vehicle.clear_last_damage_entity()


class VehicleMods:
    """Vehicle upgrade facade."""

    __slots__ = ("_vehicle",)

    def __init__(self, vehicle: "Vehicle"):
        self._vehicle = vehicle

    def add(self, model_id: int) -> int:
        return self._vehicle.mod(model_id)

    def remove(self, model_id: int) -> None:
        self._vehicle.remove_mod(model_id)

    def current(self, slot: int) -> int:
        return self._vehicle.current_mod(slot)

    def available(self, slot: int) -> int:
        return self._vehicle.available_mod(slot)


class VehicleAI:
    """AI driving facade for script-controlled vehicles."""

    __slots__ = ("_vehicle",)

    def __init__(self, vehicle: "Vehicle"):
        self._vehicle = vehicle

    def goto(self, pos, accurate: bool = False, racing: bool = False) -> None:
        self._vehicle.goto(pos, accurate=accurate, racing=racing)

    def wander(self) -> None:
        self._vehicle.wander()

    def idle(self) -> None:
        self._vehicle.idle()

    def cruise_speed(self, speed: float) -> None:
        self._vehicle.cruise_speed(speed)

    def driving_style(self, style: int) -> None:
        self._vehicle.driving_style(style)

    def mission(self, mission_id: int) -> None:
        self._vehicle.mission(mission_id)

    def temp_action(self, action_id: int, duration_ms: int = 1000) -> None:
        self._vehicle.temp_action(action_id, duration_ms)


class Vehicle(Entity):
    """A car, bike, boat, plane or helicopter."""

    __slots__ = ()
    _struct_class = "CVehicle"
    _ptr_of = staticmethod(_pysa.vehicle_ptr)
    _handle_of = staticmethod(_pysa.vehicle_handle)

    @classmethod
    def spawn(cls, model, pos=None, heading: float = None) -> "Vehicle":
        """Create a vehicle by id or name ('infernus', 'rhino', ...).

        With no pos, it spawns a few meters ahead of the player.
        """
        mid = vehicle_id(model)
        if pos is None:
            from .player import player
            import math
            ped = player.ped
            at = ped.pos
            rad = math.radians(ped.heading)
            pos = Vector3(at.x - 5.0 * math.sin(rad), at.y + 5.0 * math.cos(rad), at.z)
            if heading is None:
                heading = ped.heading
        if not load_model(mid):
            raise RuntimeError(f"vehicle model {model!r} failed to load")
        x, y, z = Vector3.of(pos)
        veh = cmd.CREATE_CAR(mid, x, y, z)
        release_model(mid)
        if heading is not None:
            veh.heading = heading
        return veh

    @property
    def pos(self) -> Vector3:
        return Vector3(*cmd.GET_CAR_COORDINATES(self))

    @property
    def doors(self) -> VehicleDoors:
        return VehicleDoors(self)

    @property
    def tyres(self) -> VehicleTyres:
        return VehicleTyres(self)

    @property
    def damage(self) -> VehicleDamage:
        return VehicleDamage(self)

    @property
    def mods(self) -> VehicleMods:
        return VehicleMods(self)

    @property
    def ai(self) -> VehicleAI:
        return VehicleAI(self)

    @pos.setter
    def pos(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CAR_COORDINATES(self, x, y, z)

    @property
    def heading(self) -> float:
        return cmd.GET_CAR_HEADING(self)

    @heading.setter
    def heading(self, degrees: float) -> None:
        cmd.SET_CAR_HEADING(self, degrees)

    @property
    def health(self) -> int:
        """0-1000; below ~250 the engine catches fire."""
        return cmd.GET_CAR_HEALTH(self)

    @health.setter
    def health(self, value: int) -> None:
        cmd.SET_CAR_HEALTH(self, value)

    @property
    def speed(self) -> float:
        return cmd.GET_CAR_SPEED(self)

    @speed.setter
    def speed(self, value: float) -> None:
        cmd.SET_CAR_FORWARD_SPEED(self, value)

    @property
    def is_dead(self) -> bool:
        return cmd.IS_CAR_DEAD(self)

    @property
    def alive(self) -> bool:
        return not self.is_dead

    @property
    def exists_command(self) -> bool:
        return cmd.DOES_VEHICLE_EXIST(self)

    @property
    def stopped(self) -> bool:
        return cmd.IS_CAR_STOPPED(self)

    @property
    def on_screen(self) -> bool:
        return cmd.IS_CAR_ON_SCREEN(self)

    @property
    def in_water(self) -> bool:
        return cmd.IS_CAR_IN_WATER(self)

    @property
    def on_fire(self) -> bool:
        return cmd.IS_CAR_ON_FIRE(self)

    @property
    def in_air(self) -> bool:
        return cmd.IS_CAR_IN_AIR_PROPER(self)

    @property
    def upside_down(self) -> bool:
        return cmd.IS_CAR_UPSIDEDOWN(self)

    @property
    def stuck_on_roof(self) -> bool:
        return cmd.IS_CAR_STUCK_ON_ROOF(self)

    @property
    def visibly_damaged(self) -> bool:
        return cmd.IS_CAR_VISIBLY_DAMAGED(self)

    @property
    def big(self) -> bool:
        return cmd.IS_BIG_VEHICLE(self)

    @property
    def low_rider(self) -> bool:
        return cmd.IS_CAR_LOW_RIDER(self)

    @property
    def street_racer(self) -> bool:
        return cmd.IS_CAR_STREET_RACER(self)

    @property
    def driver(self):
        """The driving ped, or None if empty."""
        return cmd.GET_DRIVER_OF_CAR(self)

    def passenger(self, seat: int = 0):
        return cmd.GET_CHAR_IN_CAR_PASSENGER_SEAT(self, seat)

    def passenger_seat_free(self, seat: int = 0) -> bool:
        return cmd.IS_CAR_PASSENGER_SEAT_FREE(self, seat)

    @property
    def passenger_count(self) -> int:
        return cmd.GET_NUMBER_OF_PASSENGERS(self)

    @property
    def max_passengers(self) -> int:
        return cmd.GET_MAXIMUM_NUMBER_OF_PASSENGERS(self)

    @property
    def model(self) -> int:
        return cmd.GET_CAR_MODEL(self)

    @property
    def model_name(self) -> str:
        """The internal model name, e.g. 'infernus' (None if not a standard car)."""
        from .models import VEHICLE_NAMES
        return VEHICLE_NAMES.get(self.model)

    @property
    def vehicle_class(self) -> int:
        return cmd.GET_VEHICLE_CLASS(self)

    @property
    def passengers(self) -> list:
        """All passenger peds currently in this vehicle (excludes the driver)."""
        out = []
        for seat in range(max(0, self.max_passengers)):
            ped = self.passenger(seat)
            if ped is not None and ped.exists:
                out.append(ped)
        return out

    @property
    def occupants(self) -> list:
        """Everyone in the vehicle: driver first (if any), then passengers."""
        out = []
        driver = self.driver
        if driver is not None and driver.exists:
            out.append(driver)
        out.extend(self.passengers)
        return out

    @property
    def empty(self) -> bool:
        """True if nobody is inside."""
        return not self.occupants

    @property
    def mass(self) -> float:
        return cmd.GET_CAR_MASS(self)

    @property
    def pitch(self) -> float:
        return cmd.GET_CAR_PITCH(self)

    @property
    def roll(self) -> float:
        return cmd.GET_CAR_ROLL(self)

    @roll.setter
    def roll(self, degrees: float) -> None:
        cmd.SET_CAR_ROLL(self, degrees)

    @property
    def upright_value(self) -> float:
        return cmd.GET_CAR_UPRIGHT_VALUE(self)

    @property
    def forward(self) -> tuple[float, float]:
        return (cmd.GET_CAR_FORWARD_X(self), cmd.GET_CAR_FORWARD_Y(self))

    @property
    def velocity(self) -> Vector3:
        return Vector3(*cmd.GET_CAR_SPEED_VECTOR(self))

    @property
    def quaternion(self) -> tuple[float, float, float, float]:
        return cmd.GET_VEHICLE_QUATERNION(self)

    @quaternion.setter
    def quaternion(self, quat) -> None:
        x, y, z, w = quat
        cmd.SET_VEHICLE_QUATERNION(self, x, y, z, w)

    @property
    def colours(self) -> tuple:
        return cmd.GET_CAR_COLOURS(self)

    @colours.setter
    def colours(self, pair) -> None:
        c1, c2 = pair
        cmd.CHANGE_CAR_COLOUR(self, c1, c2)

    @property
    def extra_colours(self) -> tuple:
        return cmd.GET_EXTRA_CAR_COLOURS(self)

    @extra_colours.setter
    def extra_colours(self, pair) -> None:
        c3, c4 = pair
        cmd.SET_EXTRA_CAR_COLOURS(self, c3, c4)

    @property
    def paintjob(self) -> int:
        return cmd.GET_CURRENT_VEHICLE_PAINTJOB(self)

    @paintjob.setter
    def paintjob(self, paintjob_id: int) -> None:
        cmd.GIVE_VEHICLE_PAINTJOB(self, paintjob_id)

    @property
    def door_lock_status(self) -> int:
        return cmd.GET_CAR_DOOR_LOCK_STATUS(self)

    @property
    def dirt_level(self) -> float:
        addr = self.address
        return _pysa.read_f32(addr + 0x4B0) if addr else 0.0

    @dirt_level.setter
    def dirt_level(self, value: float) -> None:
        cmd.SET_VEHICLE_DIRT_LEVEL(self, value)

    def set_pos_no_offset(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CAR_COORDINATES_NO_OFFSET(self, x, y, z)

    def offset(self, local) -> Vector3:
        x, y, z = Vector3.of(local)
        return Vector3(*cmd.GET_OFFSET_FROM_CAR_IN_WORLD_COORDS(self, x, y, z))

    def engine_on(self, on: bool = True) -> None:
        cmd.SET_CAR_ENGINE_ON(self, on)

    def lights_on(self, on: bool = True) -> None:
        cmd.SET_CAR_LIGHTS_ON(self, on)

    def force_lights(self, mode: int) -> None:
        cmd.FORCE_CAR_LIGHTS(self, mode)

    def siren(self, enabled: bool = True) -> None:
        cmd.SWITCH_CAR_SIREN(self, enabled)

    def break_engine(self) -> None:
        cmd.SET_CAR_ENGINE_BROKEN(self, True)

    def give_nitro(self) -> None:
        cmd.GIVE_NON_PLAYER_CAR_NITRO(self)

    def hydraulics(self, enabled: bool = True) -> None:
        cmd.SET_CAR_HYDRAULICS(self, enabled)

    @property
    def has_hydraulics(self) -> bool:
        return cmd.DOES_CAR_HAVE_HYDRAULICS(self)

    def reset_hydraulics(self) -> None:
        cmd.RESET_VEHICLE_HYDRAULICS(self)

    def lock(self, locked: bool = True) -> None:
        cmd.LOCK_CAR_DOORS(self, 2 if locked else 1)

    def set_lock_status(self, status: int) -> None:
        cmd.LOCK_CAR_DOORS(self, status)

    def close_doors(self) -> None:
        cmd.CLOSE_ALL_CAR_DOORS(self)

    def open_door(self, door: int) -> None:
        cmd.OPEN_CAR_DOOR(self, door)

    def open_door_ratio(self, door: int, ratio: float) -> None:
        cmd.OPEN_CAR_DOOR_A_BIT(self, door, ratio)

    def door_angle_ratio(self, door: int) -> float:
        return cmd.GET_DOOR_ANGLE_RATIO(self, door)

    def door_damaged(self, door: int) -> bool:
        return cmd.IS_CAR_DOOR_DAMAGED(self, door)

    def door_fully_open(self, door: int) -> bool:
        return cmd.IS_CAR_DOOR_FULLY_OPEN(self, door)

    def damage_door(self, door: int) -> None:
        cmd.DAMAGE_CAR_DOOR(self, door)

    def fix_door(self, door: int) -> None:
        cmd.FIX_CAR_DOOR(self, door)

    def pop_door(self, door: int, visible: bool = True) -> None:
        cmd.POP_CAR_DOOR(self, door, visible)

    def pop_boot(self) -> None:
        cmd.POP_CAR_BOOT(self)

    def damage_panel(self, panel: int) -> None:
        cmd.DAMAGE_CAR_PANEL(self, panel)

    def fix_panel(self, panel: int) -> None:
        cmd.FIX_CAR_PANEL(self, panel)

    def pop_panel(self, panel: int, drop: bool = True) -> None:
        cmd.POP_CAR_PANEL(self, panel, drop)

    def burst_tyre(self, tyre: int) -> None:
        cmd.BURST_CAR_TYRE(self, tyre)

    def fix_tyre(self, tyre: int) -> None:
        cmd.FIX_CAR_TYRE(self, tyre)

    def tyres_can_burst(self, enabled: bool = True) -> None:
        cmd.SET_CAN_BURST_CAR_TYRES(self, enabled)

    def freeze(self, frozen: bool = True) -> None:
        cmd.FREEZE_CAR_POSITION(self, frozen)

    def freeze_without_collision_load(self, frozen: bool = True) -> None:
        cmd.FREEZE_CAR_POSITION_AND_DONT_LOAD_COLLISION(self, frozen)

    def collision(self, enabled: bool = True) -> None:
        cmd.SET_CAR_COLLISION(self, enabled)

    def visible(self, enabled: bool = True) -> None:
        cmd.SET_CAR_VISIBLE(self, enabled)

    def can_be_damaged(self, enabled: bool = True) -> None:
        cmd.SET_CAR_CAN_BE_DAMAGED(self, enabled)

    def can_be_visibly_damaged(self, enabled: bool = True) -> None:
        cmd.SET_CAR_CAN_BE_VISIBLY_DAMAGED(self, enabled)

    def only_damaged_by_player(self, enabled: bool = True) -> None:
        cmd.SET_CAR_ONLY_DAMAGED_BY_PLAYER(self, enabled)

    def heavy(self, enabled: bool = True) -> None:
        cmd.SET_CAR_HEAVY(self, enabled)

    def strong(self, enabled: bool = True) -> None:
        cmd.SET_CAR_STRONG(self, enabled)

    def watertight(self, enabled: bool = True) -> None:
        cmd.SET_CAR_WATERTIGHT(self, enabled)

    def targettable(self, enabled: bool = True) -> None:
        cmd.SET_VEHICLE_CAN_BE_TARGETTED(self, enabled)

    def heatseeker_targettable(self, enabled: bool = True) -> None:
        cmd.VEHICLE_CAN_BE_TARGETTED_BY_HS_MISSILE(self, enabled)

    def provides_cover(self, enabled: bool = True) -> None:
        cmd.VEHICLE_DOES_PROVIDE_COVER(self, enabled)

    def freebies(self, enabled: bool = True) -> None:
        cmd.SET_FREEBIES_IN_VEHICLE(self, enabled)

    def make_proof(self, bullet=True, fire=True, explosion=True,
                   collision=True, melee=True) -> None:
        cmd.SET_CAR_PROOFS(self, bullet, fire, explosion, collision, melee)

    def damaged_by_weapon(self, weapon: int) -> bool:
        return cmd.HAS_CAR_BEEN_DAMAGED_BY_WEAPON(self, weapon)

    def damaged_by_ped(self, ped: Ped) -> bool:
        return cmd.HAS_CAR_BEEN_DAMAGED_BY_CHAR(self, ped)

    def damaged_by_vehicle(self, other: "Vehicle") -> bool:
        return cmd.HAS_CAR_BEEN_DAMAGED_BY_CAR(self, other)

    def clear_last_weapon_damage(self) -> None:
        cmd.CLEAR_CAR_LAST_WEAPON_DAMAGE(self)

    def clear_last_damage_entity(self) -> None:
        cmd.CLEAR_CAR_LAST_DAMAGE_ENTITY(self)

    def start_fire(self) -> int:
        return cmd.START_CAR_FIRE(self)

    def explode(self) -> None:
        cmd.EXPLODE_CAR(self)

    def explode_cutscene(self) -> None:
        cmd.EXPLODE_CAR_IN_CUTSCENE(self)

    def explode_cutscene_bits(self, shake: bool = True, effect: bool = True,
                              sound: bool = True) -> None:
        cmd.EXPLODE_CAR_IN_CUTSCENE_SHAKE_AND_BITS(self, shake, effect, sound)

    def add_upside_down_check(self) -> None:
        cmd.ADD_UPSIDEDOWN_CAR_CHECK(self)

    def remove_upside_down_check(self) -> None:
        cmd.REMOVE_UPSIDEDOWN_CAR_CHECK(self)

    def upside_down_not_damaged(self, enabled: bool = True) -> None:
        cmd.SET_UPSIDEDOWN_CAR_NOT_DAMAGED(self, enabled)

    def add_stuck_check(self, distance: float = 2.0, time_ms: int = 5000) -> None:
        cmd.ADD_STUCK_CAR_CHECK(self, distance, time_ms)

    def add_stuck_check_with_warp(self, distance: float = 2.0, time_ms: int = 5000,
                                  stuck: bool = True, flipped: bool = True,
                                  in_water: bool = True, nodes: int = 3) -> None:
        cmd.ADD_STUCK_CAR_CHECK_WITH_WARP(self, distance, time_ms, stuck, flipped, in_water, nodes)

    def remove_stuck_check(self) -> None:
        cmd.REMOVE_STUCK_CAR_CHECK(self)

    @property
    def has_stuck_check(self) -> bool:
        return cmd.DOES_CAR_HAVE_STUCK_CAR_CHECK(self)

    @property
    def stuck(self) -> bool:
        return cmd.IS_CAR_STUCK(self)

    def cruise_speed(self, speed: float) -> None:
        cmd.SET_CAR_CRUISE_SPEED(self, speed)

    def driving_style(self, style: int) -> None:
        cmd.SET_CAR_DRIVING_STYLE(self, style)

    def mission(self, mission_id: int) -> None:
        cmd.SET_CAR_MISSION(self, mission_id)

    def status(self, status: int) -> None:
        cmd.SET_CAR_STATUS(self, status)

    def temp_action(self, action_id: int, duration_ms: int = 1000) -> None:
        cmd.SET_CAR_TEMP_ACTION(self, action_id, duration_ms)

    def traction(self, value: float) -> None:
        cmd.SET_CAR_TRACTION(self, value)

    def air_resistance(self, multiplier: float) -> None:
        cmd.SET_VEHICLE_AIR_RESISTANCE_MULTIPLIER(self, multiplier)

    def rotation_velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_CAR_ROTATION_VELOCITY(self, x, y, z)

    def add_rotation_velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.ADD_TO_CAR_ROTATION_VELOCITY(self, x, y, z)

    def turn_to_face(self, x: float, y: float) -> None:
        cmd.TURN_CAR_TO_FACE_COORD(self, x, y)

    def goto(self, pos, accurate: bool = False, racing: bool = False) -> None:
        x, y, z = Vector3.of(pos)
        if racing:
            cmd.CAR_GOTO_COORDINATES_RACING(self, x, y, z)
        elif accurate:
            cmd.CAR_GOTO_COORDINATES_ACCURATE(self, x, y, z)
        else:
            cmd.CAR_GOTO_COORDINATES(self, x, y, z)

    def wander(self) -> None:
        cmd.CAR_WANDER_RANDOMLY(self)

    def idle(self) -> None:
        cmd.CAR_SET_IDLE(self)

    def mod(self, model_id: int) -> int:
        return cmd.ADD_VEHICLE_MOD(self, model_id)

    def remove_mod(self, model_id: int) -> None:
        cmd.REMOVE_VEHICLE_MOD(self, model_id)

    def current_mod(self, slot: int) -> int:
        return cmd.GET_CURRENT_CAR_MOD(self, slot)

    def available_mod(self, slot: int) -> int:
        return cmd.GET_AVAILABLE_VEHICLE_MOD(self, slot)

    def moving_component_offset(self) -> float:
        return cmd.GET_CAR_MOVING_COMPONENT_OFFSET(self)

    def control_moving_part(self, value: float) -> None:
        cmd.CONTROL_MOVABLE_VEHICLE_PART(self, value)

    def train_speed(self, speed: float) -> None:
        cmd.SET_TRAIN_SPEED(self, speed)

    def train_cruise_speed(self, speed: float) -> None:
        cmd.SET_TRAIN_CRUISE_SPEED(self, speed)

    def train_forced_to_slow_down(self, enabled: bool = True) -> None:
        cmd.SET_TRAIN_FORCED_TO_SLOW_DOWN(self, enabled)

    @property
    def train_derailed(self) -> bool:
        return cmd.HAS_TRAIN_DERAILED(self)

    @property
    def train_direction(self) -> bool:
        return cmd.FIND_TRAIN_DIRECTION(self)

    def train_carriage(self, number: int):
        return cmd.GET_TRAIN_CARRIAGE(self, number)

    @property
    def train_caboose(self):
        return cmd.GET_TRAIN_CABOOSE(self)

    def boat_anchor(self, enabled: bool = True) -> None:
        cmd.ANCHOR_BOAT(self, enabled)

    def boat_stop(self) -> None:
        cmd.BOAT_STOP(self)

    def boat_cruise_speed(self, speed: float) -> None:
        cmd.SET_BOAT_CRUISE_SPEED(self, speed)

    def heli_goto(self, pos, min_altitude: float = 15.0,
                  max_altitude: float = 60.0) -> None:
        x, y, z = Vector3.of(pos)
        cmd.HELI_GOTO_COORDS(self, x, y, z, min_altitude, max_altitude)

    def heli_land_at(self, pos, min_altitude: float = 0.0,
                     max_altitude: float = 20.0) -> None:
        x, y, z = Vector3.of(pos)
        cmd.HELI_LAND_AT_COORDS(self, x, y, z, min_altitude, max_altitude)

    def heli_blades_full_speed(self) -> None:
        cmd.SET_HELI_BLADES_FULL_SPEED(self)

    def heli_stabiliser(self, enabled: bool = True) -> None:
        cmd.SET_HELI_STABILISER(self, enabled)

    def heli_crash(self) -> None:
        cmd.MAKE_HELI_COME_CRASHING_DOWN(self)

    def plane_goto(self, pos, min_altitude: float = 30.0,
                   max_altitude: float = 120.0) -> None:
        x, y, z = Vector3.of(pos)
        cmd.PLANE_GOTO_COORDS(self, x, y, z, min_altitude, max_altitude)

    def plane_throttle(self, value: float) -> None:
        cmd.SET_PLANE_THROTTLE(self, value)

    def plane_starts_in_air(self) -> None:
        cmd.PLANE_STARTS_IN_AIR(self)

    def plane_undercarriage_up(self, enabled: bool = True) -> None:
        cmd.SET_PLANE_UNDERCARRIAGE_UP(self, enabled)

    @property
    def plane_undercarriage_position(self) -> float:
        return cmd.GET_PLANE_UNDERCARRIAGE_POSITION(self)

    def delete(self) -> None:
        cmd.DELETE_CAR(self)


class ObjectAnimation:
    """Object animation facade: `obj.anim.play(...)`, `.time(...)`, `.speed(...)`."""

    __slots__ = ("_obj",)

    def __init__(self, obj: "GameObject"):
        self._obj = obj

    def play(self, anim: str, group: str, frame_delta: float = 4.0,
             lock_final: bool = False, loop: bool = False) -> None:
        self._obj.play_anim(anim, group, frame_delta, lock_final, loop)

    def playing(self, anim: str) -> bool:
        return self._obj.is_playing_anim(anim)

    def time(self, anim: str) -> float:
        return self._obj.anim_time(anim)

    def set_time(self, anim: str, time: float) -> None:
        self._obj.set_anim_time(anim, time)

    def speed(self, anim: str, speed: float) -> None:
        self._obj.set_anim_speed(anim, speed)


class GameObject(Entity):
    """A world object (crates, props, ...)."""

    __slots__ = ()
    _struct_class = "CObject"
    _ptr_of = staticmethod(_pysa.object_ptr)
    _handle_of = staticmethod(_pysa.object_handle)

    @classmethod
    def spawn(cls, model: int, pos) -> "GameObject":
        if not load_model(model):
            raise RuntimeError(f"object model {model} failed to load")
        x, y, z = Vector3.of(pos)
        obj = cmd.CREATE_OBJECT(model, x, y, z)
        release_model(model)
        return obj

    @property
    def pos(self) -> Vector3:
        return Vector3(*cmd.GET_OBJECT_COORDINATES(self))

    @property
    def anim(self) -> ObjectAnimation:
        return ObjectAnimation(self)

    @pos.setter
    def pos(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_OBJECT_COORDINATES(self, x, y, z)

    @property
    def heading(self) -> float:
        return cmd.GET_OBJECT_HEADING(self)

    @heading.setter
    def heading(self, degrees: float) -> None:
        cmd.SET_OBJECT_HEADING(self, degrees)

    @property
    def health(self) -> int:
        return cmd.GET_OBJECT_HEALTH(self)

    @health.setter
    def health(self, value: int) -> None:
        cmd.SET_OBJECT_HEALTH(self, value)

    @property
    def model(self) -> int:
        return cmd.GET_OBJECT_MODEL(self)

    @property
    def mass(self) -> float:
        return cmd.GET_OBJECT_MASS(self)

    @mass.setter
    def mass(self, value: float) -> None:
        cmd.SET_OBJECT_MASS(self, value)

    @property
    def turn_mass(self) -> float:
        return cmd.GET_OBJECT_TURN_MASS(self)

    @turn_mass.setter
    def turn_mass(self, value: float) -> None:
        cmd.SET_OBJECT_TURN_MASS(self, value)

    @property
    def velocity(self) -> Vector3:
        return Vector3(*cmd.GET_OBJECT_VELOCITY(self))

    @velocity.setter
    def velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_OBJECT_VELOCITY(self, x, y, z)

    def add_velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.ADD_TO_OBJECT_VELOCITY(self, x, y, z)

    @property
    def rotation_velocity(self) -> Vector3:
        return Vector3(*cmd.GET_OBJECT_ROTATION_VELOCITY(self))

    @rotation_velocity.setter
    def rotation_velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_OBJECT_ROTATION_VELOCITY(self, x, y, z)

    def add_rotation_velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.ADD_TO_OBJECT_ROTATION_VELOCITY(self, x, y, z)

    @property
    def speed(self) -> float:
        return cmd.GET_OBJECT_SPEED(self)

    @property
    def quaternion(self) -> tuple[float, float, float, float]:
        return cmd.GET_OBJECT_QUATERNION(self)

    @quaternion.setter
    def quaternion(self, quat) -> None:
        x, y, z, w = quat
        cmd.SET_OBJECT_QUATERNION(self, x, y, z, w)

    def set_rotation(self, x: float, y: float, z: float) -> None:
        cmd.SET_OBJECT_ROTATION(self, x, y, z)

    def offset(self, local) -> Vector3:
        x, y, z = Vector3.of(local)
        return Vector3(*cmd.GET_OFFSET_FROM_OBJECT_IN_WORLD_COORDS(self, x, y, z))

    def set_pos_and_velocity(self, value) -> None:
        x, y, z = Vector3.of(value)
        cmd.SET_OBJECT_COORDINATES_AND_VELOCITY(self, x, y, z)

    def freeze(self, frozen: bool = True) -> None:
        cmd.FREEZE_OBJECT_POSITION(self, frozen)

    def collision(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_COLLISION(self, enabled)

    def visible(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_VISIBLE(self, enabled)

    def dynamic(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_DYNAMIC(self, enabled)

    def draw_last(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_DRAW_LAST(self, enabled)

    def targettable(self, enabled: bool = True) -> None:
        cmd.MAKE_OBJECT_TARGETTABLE(self, enabled)

    def stealable(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_AS_STEALABLE(self, enabled)

    def collision_damage_effect(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_COLLISION_DAMAGE_EFFECT(self, enabled)

    def records_collisions(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_RECORDS_COLLISIONS(self, enabled)

    def render_scorched(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_RENDER_SCORCHED(self, enabled)

    def only_damaged_by_player(self, enabled: bool = True) -> None:
        cmd.SET_OBJECT_ONLY_DAMAGED_BY_PLAYER(self, enabled)

    def make_proof(self, bullet=True, fire=True, explosion=True,
                   collision=True, melee=True) -> None:
        cmd.SET_OBJECT_PROOFS(self, bullet, fire, explosion, collision, melee)

    def damaged(self) -> bool:
        return cmd.HAS_OBJECT_BEEN_DAMAGED(self)

    def damaged_by_weapon(self, weapon: int) -> bool:
        return cmd.HAS_OBJECT_BEEN_DAMAGED_BY_WEAPON(self, weapon)

    def clear_last_weapon_damage(self) -> None:
        cmd.CLEAR_OBJECT_LAST_WEAPON_DAMAGE(self)

    def collided_with_anything(self) -> bool:
        return cmd.HAS_OBJECT_COLLIDED_WITH_ANYTHING(self)

    def uprooted(self) -> bool:
        return cmd.HAS_OBJECT_BEEN_UPROOTED(self)

    def photographed(self) -> bool:
        return cmd.HAS_OBJECT_BEEN_PHOTOGRAPHED(self)

    def has_model(self, model: int) -> bool:
        return cmd.DOES_OBJECT_HAVE_THIS_MODEL(self, model)

    @property
    def on_screen(self) -> bool:
        return cmd.IS_OBJECT_ON_SCREEN(self)

    @property
    def in_water(self) -> bool:
        return cmd.IS_OBJECT_IN_WATER(self)

    @property
    def is_static(self) -> bool:
        return cmd.IS_OBJECT_STATIC(self)

    @property
    def attached(self) -> bool:
        return cmd.IS_OBJECT_ATTACHED(self)

    @property
    def intersecting_world(self) -> bool:
        return cmd.IS_OBJECT_INTERSECTING_WORLD(self)

    def in_area_2d(self, left_bottom, right_top, draw_sphere: bool = False) -> bool:
        x1, y1 = _xy(left_bottom)
        x2, y2 = _xy(right_top)
        return cmd.IS_OBJECT_IN_AREA_2D(self, x1, y1, x2, y2, draw_sphere)

    def in_area_3d(self, left_bottom, right_top, draw_sphere: bool = False) -> bool:
        x1, y1, z1 = Vector3.of(left_bottom)
        x2, y2, z2 = Vector3.of(right_top)
        return cmd.IS_OBJECT_IN_AREA_3D(self, x1, y1, z1, x2, y2, z2, draw_sphere)

    def locate_2d(self, pos, x_radius: float, y_radius: float,
                  draw_sphere: bool = False) -> bool:
        x, y, _ = Vector3.of(pos)
        return cmd.LOCATE_OBJECT_2D(self, x, y, x_radius, y_radius, draw_sphere)

    def locate_3d(self, pos, x_radius: float, y_radius: float, z_radius: float,
                  draw_sphere: bool = False) -> bool:
        x, y, z = Vector3.of(pos)
        return cmd.LOCATE_OBJECT_3D(self, x, y, z, x_radius, y_radius, z_radius, draw_sphere)

    def attach_to_vehicle(self, vehicle: Vehicle, offset=(0, 0, 0),
                          rotation=(0, 0, 0)) -> None:
        x, y, z = Vector3.of(offset)
        rx, ry, rz = Vector3.of(rotation)
        cmd.ATTACH_OBJECT_TO_CAR(self, vehicle, x, y, z, rx, ry, rz)

    def attach_to_ped(self, ped: Ped, offset=(0, 0, 0),
                      rotation=(0, 0, 0)) -> None:
        x, y, z = Vector3.of(offset)
        rx, ry, rz = Vector3.of(rotation)
        cmd.ATTACH_OBJECT_TO_CHAR(self, ped, x, y, z, rx, ry, rz)

    def attach_to_object(self, other: "GameObject", offset=(0, 0, 0),
                         rotation=(0, 0, 0)) -> None:
        x, y, z = Vector3.of(offset)
        rx, ry, rz = Vector3.of(rotation)
        cmd.ATTACH_OBJECT_TO_OBJECT(self, other, x, y, z, rx, ry, rz)

    def detach(self, pitch: float = 0.0, heading: float = 0.0,
               strength: float = 0.0, apply_turn_force: bool = False) -> None:
        cmd.DETACH_OBJECT(self, pitch, heading, strength, apply_turn_force)

    def place_relative_to_vehicle(self, vehicle: Vehicle, offset=(0, 0, 0)) -> None:
        x, y, z = Vector3.of(offset)
        cmd.PLACE_OBJECT_RELATIVE_TO_CAR(self, vehicle, x, y, z)

    def sort_collision_with_vehicle(self, vehicle: Vehicle) -> None:
        cmd.SORT_OUT_OBJECT_COLLISION_WITH_CAR(self, vehicle)

    def play_anim(self, anim: str, group: str, frame_delta: float = 4.0,
                  lock_final: bool = False, loop: bool = False) -> None:
        cmd.PLAY_OBJECT_ANIM(self, anim, group, frame_delta, lock_final, loop)

    def is_playing_anim(self, anim: str) -> bool:
        return cmd.IS_OBJECT_PLAYING_ANIM(self, anim)

    def anim_time(self, anim: str) -> float:
        return cmd.GET_OBJECT_ANIM_CURRENT_TIME(self, anim)

    def set_anim_time(self, anim: str, time: float) -> None:
        cmd.SET_OBJECT_ANIM_CURRENT_TIME(self, anim, time)

    def set_anim_speed(self, anim: str, speed: float) -> None:
        cmd.SET_OBJECT_ANIM_SPEED(self, anim, speed)

    def break_object(self, intensity: int = 100) -> None:
        cmd.BREAK_OBJECT(self, intensity)

    def remove_elegantly(self) -> None:
        cmd.REMOVE_OBJECT_ELEGANTLY(self)

    def scale(self, value: float) -> None:
        cmd.SET_OBJECT_SCALE(self, value)

    @property
    def rope_height(self) -> float:
        return cmd.GET_ROPE_HEIGHT_FOR_OBJECT(self)

    @rope_height.setter
    def rope_height(self, value: float) -> None:
        cmd.SET_ROPE_HEIGHT_FOR_OBJECT(self, value)

    def release_rope_entity(self) -> None:
        cmd.RELEASE_ENTITY_FROM_ROPE_FOR_OBJECT(self)

    def winch_can_pick_up(self, enabled: bool = True) -> None:
        cmd.WINCH_CAN_PICK_OBJECT_UP(self, enabled)

    def delete(self) -> None:
        cmd.DELETE_OBJECT(self)


def all_peds():
    """Every ped currently in the world (includes the player)."""
    return [Ped.from_ptr(p) for p in _pysa.peds()]


def all_vehicles():
    """Every vehicle currently in the world."""
    return [Vehicle.from_ptr(p) for p in _pysa.vehicles()]


def all_objects():
    """Every dynamic object currently in the world."""
    return [GameObject.from_ptr(p) for p in _pysa.objects()]
