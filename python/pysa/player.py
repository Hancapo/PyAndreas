"""The player: CJ himself.

    from pysa import player

    player.money += 5000
    player.wanted_level = 0
    player.armour = 100
    player.pos = (2488, -1666, 14)
    car = player.vehicle           # None when on foot
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .entities import Ped, Vehicle
from .math3 import Vector3
from .native import call, cmd


# plugin-sdk: CWorld::Players = (CPlayerInfo*)0xB7CD98, sizeof(CPlayerInfo)=0x190
_PLAYER_INFO_BASE = 0xB7CD98
_PLAYER_INFO_SIZE = 0x190


class PLAYER_STATE:
    """CPlayerInfo::m_nPlayerState values."""

    PLAYING = 0
    HAS_DIED = 1
    HAS_BEEN_ARRESTED = 2
    FAILED_MISSION = 3
    LEFT_GAME = 4


_PLAYER_STATE_NAMES = {
    PLAYER_STATE.PLAYING: "playing",
    PLAYER_STATE.HAS_DIED: "has_died",
    PLAYER_STATE.HAS_BEEN_ARRESTED: "has_been_arrested",
    PLAYER_STATE.FAILED_MISSION: "failed_mission",
    PLAYER_STATE.LEFT_GAME: "left_game",
}


def _player_info_addr(index: int) -> int:
    return _PLAYER_INFO_BASE + int(index) * _PLAYER_INFO_SIZE


def _read_bool(addr: int) -> bool:
    return bool(_pysa.read_u8(addr))


def _write_bool(addr: int, value: bool) -> None:
    _pysa.write_u8(addr, 1 if value else 0)


def _write_u8(addr: int, value: int) -> None:
    _pysa.write_u8(addr, max(0, min(255, int(value))))


def _write_u16(addr: int, value: int) -> None:
    _pysa.write_u16(addr, max(0, min(0xFFFF, int(value))))


def _write_u32(addr: int, value: int) -> None:
    _pysa.write_u32(addr, int(value) & 0xFFFFFFFF)


def _vehicle_from_ptr(ptr: int):
    return Vehicle.from_ptr(ptr) if ptr else None


class PlayerStats:
    """Convenience access to CStats through script commands."""

    def int(self, stat_id: int) -> int:
        return cmd.GET_INT_STAT(stat_id)

    def get_int(self, stat_id: int) -> int:
        return self.int(stat_id)

    def set_int(self, stat_id: int, value: int) -> None:
        cmd.SET_INT_STAT(stat_id, value)

    def inc_int(self, stat_id: int, value: int = 1, message: bool = True) -> None:
        if message:
            cmd.INCREMENT_INT_STAT(stat_id, value)
        else:
            cmd.INCREMENT_INT_STAT_NO_MESSAGE(stat_id, value)

    def dec_int(self, stat_id: int, value: int = 1) -> None:
        cmd.DECREMENT_INT_STAT(stat_id, value)

    def register_int(self, stat_id: int, value: int) -> None:
        cmd.REGISTER_INT_STAT(stat_id, value)

    def float(self, stat_id: int) -> float:
        return cmd.GET_FLOAT_STAT(stat_id)

    def get_float(self, stat_id: int) -> float:
        return self.float(stat_id)

    def set_float(self, stat_id: int, value: float) -> None:
        cmd.SET_FLOAT_STAT(stat_id, value)

    def inc_float(self, stat_id: int, value: float, message: bool = True) -> None:
        if message:
            cmd.INCREMENT_FLOAT_STAT(stat_id, value)
        else:
            cmd.INCREMENT_FLOAT_STAT_NO_MESSAGE(stat_id, value)

    def dec_float(self, stat_id: int, value: float) -> None:
        cmd.DECREMENT_FLOAT_STAT(stat_id, value)

    def register_float(self, stat_id: int, value: float) -> None:
        cmd.REGISTER_FLOAT_STAT(stat_id, value)

    def award_respect(self, value: int) -> None:
        cmd.AWARD_PLAYER_MISSION_RESPECT(value)

    def show_updates(self, enabled: bool = True) -> None:
        cmd.SHOW_UPDATE_STATS(enabled)

    @property
    def max_group_members(self) -> int:
        return cmd.FIND_MAX_NUMBER_OF_GROUP_MEMBERS()

    @property
    def territory_under_control(self) -> int:
        return cmd.GET_TERRITORY_UNDER_CONTROL_PERCENTAGE()


class PlayerGroup:
    """The player's recruitable gang group."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def handle(self) -> int:
        return cmd.GET_PLAYER_GROUP(self._player.index)

    @property
    def exists(self) -> bool:
        return cmd.DOES_GROUP_EXIST(self.handle)

    @property
    def size(self) -> tuple[int, int]:
        """(leaders, members) currently in the group."""
        return cmd.GET_GROUP_SIZE(self.handle)

    @property
    def leaders(self) -> int:
        return self.size[0]

    @property
    def member_count(self) -> int:
        return self.size[1]

    @property
    def members(self) -> list[Ped]:
        return [
            ped for i in range(self.member_count)
            if (ped := cmd.GET_GROUP_MEMBER(self.handle, i)) is not None
        ]

    def is_leader(self, ped: Ped) -> bool:
        return cmd.IS_GROUP_LEADER(self.handle, ped)

    def is_member(self, ped: Ped) -> bool:
        return cmd.IS_GROUP_MEMBER(self.handle, ped)

    def set_leader(self, ped: Ped) -> None:
        cmd.SET_GROUP_LEADER(self.handle, ped)

    def add_member(self, ped: Ped) -> None:
        cmd.SET_GROUP_MEMBER(self.handle, ped)

    def remove_member(self, ped: Ped) -> None:
        cmd.REMOVE_CHAR_FROM_GROUP(ped)

    def remove(self) -> None:
        cmd.REMOVE_GROUP(self.handle)

    def set_separation_range(self, distance: float) -> None:
        cmd.SET_GROUP_SEPARATION_RANGE(self.handle, distance)

    def set_follow_status(self, enabled: bool = True) -> None:
        cmd.SET_GROUP_FOLLOW_STATUS(self.handle, enabled)

    def set_recruitment(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_GROUP_RECRUITMENT(self._player.index, enabled)

    def listen_to_commands(self, ped: Ped, enabled: bool = True) -> None:
        cmd.LISTEN_TO_PLAYER_GROUP_COMMANDS(ped, enabled)

    def disappear(self) -> None:
        cmd.MAKE_PLAYER_GANG_DISAPPEAR()

    def reappear(self) -> None:
        cmd.MAKE_PLAYER_GANG_REAPPEAR()

    def follow_always(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_GROUP_TO_FOLLOW_ALWAYS(self._player.index, enabled)

    def follow_never(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_GROUP_TO_FOLLOW_NEVER(self._player.index, enabled)

    def make_room_for_mission_peds(self, count: int) -> None:
        cmd.MAKE_ROOM_IN_PLAYER_GANG_FOR_MISSION_PEDS(count)


class PlayerWeapons:
    """Player weapon facade: `player.weapons.give(...)`, `.current`, `.ammo(...)`."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def current(self) -> int:
        return self._player.current_weapon

    @current.setter
    def current(self, weapon: int) -> None:
        self._player.current_weapon = weapon

    def give(self, weapon: int, ammo: int = 500, equip: bool = True) -> None:
        self._player.give_weapon(weapon, ammo, equip)

    def remove(self, weapon: int) -> None:
        self._player.remove_weapon(weapon)

    def clear(self) -> None:
        self._player.remove_weapons()

    def has(self, weapon: int) -> bool:
        return self._player.has_weapon(weapon)

    def ammo(self, weapon: int) -> int:
        return self._player.ammo(weapon)

    def set_ammo(self, weapon: int, ammo: int) -> None:
        self._player.set_ammo(weapon, ammo)

    def add_ammo(self, weapon: int, ammo: int) -> None:
        self._player.add_ammo(weapon, ammo)

    def ensure_drive_by(self, ammo: int = 9999) -> None:
        self._player.ensure_drive_by_weapon(ammo)


class PlayerWanted:
    """Wanted/chase facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def level(self) -> int:
        return self._player.wanted_level

    @level.setter
    def level(self, value: int) -> None:
        self._player.wanted_level = value

    @property
    def max_level(self) -> int:
        return self._player.max_wanted_level

    @max_level.setter
    def max_level(self, value: int) -> None:
        self._player.max_wanted_level = value

    @property
    def chase_value(self) -> float:
        return self._player.current_chase_value

    @chase_value.setter
    def chase_value(self, value: float) -> None:
        self._player.current_chase_value = value

    def clear(self) -> None:
        self._player.wanted_level = 0

    def set_no_drop(self, level: int) -> None:
        self._player.set_wanted_level_no_drop(level)

    def greater_than(self, level: int) -> bool:
        return self._player.is_wanted_level_greater(level)

    def multiplier(self, value: float) -> None:
        self._player.set_wanted_multiplier(value)

    def ignore_by_police(self, enabled: bool = True) -> None:
        self._player.ignore_by_police(enabled)

    def clear_in_garage(self) -> None:
        self._player.clear_wanted_level_in_garage()


class PlayerControls:
    """Input/control facade for toggling player actions."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def enabled(self) -> bool:
        return self._player.control_on

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._player.control_on = value

    @property
    def fire(self) -> bool:
        return True

    @fire.setter
    def fire(self, enabled: bool) -> None:
        self._player.set_fire_button(enabled)

    @property
    def jump(self) -> bool:
        return True

    @jump.setter
    def jump(self, enabled: bool) -> None:
        self._player.set_jump_button(enabled)

    @property
    def duck(self) -> bool:
        return True

    @duck.setter
    def duck(self, enabled: bool) -> None:
        self._player.set_duck_button(enabled)

    @property
    def enter_car(self) -> bool:
        return True

    @enter_car.setter
    def enter_car(self, enabled: bool) -> None:
        self._player.set_enter_car_button(enabled)

    @property
    def cycle_weapon(self) -> bool:
        return True

    @cycle_weapon.setter
    def cycle_weapon(self, enabled: bool) -> None:
        self._player.set_cycle_weapon_button(enabled)

    @property
    def vital_stats(self) -> bool:
        return True

    @vital_stats.setter
    def vital_stats(self, enabled: bool) -> None:
        self._player.set_vital_stats_button(enabled)

    def all(self, enabled: bool = True) -> None:
        self._player.set_control(enabled)


class PlayerPerks:
    """Perks and immunity/restriction facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def never_tired(self) -> bool:
        return self._player.never_tired_enabled

    @never_tired.setter
    def never_tired(self, enabled: bool) -> None:
        self._player.never_tired(enabled)

    @property
    def fast_reload(self) -> bool:
        return self._player.fast_reload_enabled

    @fast_reload.setter
    def fast_reload(self, enabled: bool) -> None:
        self._player.fast_reload(enabled)

    @property
    def fire_proof(self) -> bool:
        return self._player.fire_proof_enabled

    @fire_proof.setter
    def fire_proof(self, enabled: bool) -> None:
        self._player.fire_proof(enabled)

    @property
    def drive_by(self) -> bool:
        return self._player.can_do_drive_by

    @drive_by.setter
    def drive_by(self, enabled: bool) -> None:
        self._player.can_do_drive_by = enabled

    @property
    def jail_free(self) -> bool:
        return self._player.get_out_of_jail_free

    @jail_free.setter
    def jail_free(self, enabled: bool) -> None:
        self._player.get_out_of_jail_free = enabled

    @property
    def hospital_free(self) -> bool:
        return self._player.get_out_of_hospital_free

    @hospital_free.setter
    def hospital_free(self, enabled: bool) -> None:
        self._player.get_out_of_hospital_free = enabled

    def ignore_by_everyone(self, enabled: bool = True) -> None:
        self._player.ignore_by_everyone(enabled)

    def disable_sprint(self, disabled: bool = True) -> None:
        self._player.disable_sprint(disabled)

    def death_penalties(self, enabled: bool = True) -> None:
        self._player.switch_death_penalties(enabled)

    def arrest_penalties(self, enabled: bool = True) -> None:
        self._player.switch_arrest_penalties(enabled)


class PlayerClothes:
    """Clothes/model facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def skin_name(self) -> str:
        return self._player.skin_name

    @property
    def skin_texture_address(self) -> int:
        return self._player.skin_texture_address

    def set_model(self, model: int) -> None:
        self._player.set_model(model)

    def rebuild(self) -> None:
        self._player.build_model()

    def hashes(self, texture_hash: int, model_hash: int, body_part: int) -> None:
        self._player.give_clothes(texture_hash, model_hash, body_part)

    def named(self, texture: str, model: str, body_part: int) -> None:
        self._player.give_clothes_named(texture, model, body_part)

    def item(self, body_part: int) -> tuple[int, int]:
        return self._player.clothes_item(body_part)

    def wearing(self, body_part: int, model_name: str) -> bool:
        return self._player.is_wearing(body_part, model_name)

    def store(self) -> None:
        self._player.store_clothes()

    def restore(self) -> None:
        self._player.restore_clothes()


class PlayerVitals:
    """Health, armour, and recovery facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def health(self) -> int:
        return self._player.health

    @health.setter
    def health(self, value: int) -> None:
        self._player.health = value

    @property
    def max_health(self) -> int:
        return self._player.max_health

    @max_health.setter
    def max_health(self, value: int) -> None:
        self._player.max_health = value

    @property
    def armour(self) -> int:
        return self._player.armour

    @armour.setter
    def armour(self, value: int) -> None:
        self._player.armour = value

    @property
    def max_armour(self) -> int:
        return self._player.max_armour

    @max_armour.setter
    def max_armour(self, value: int) -> None:
        self._player.max_armour = value

    def heal(self, armour: bool = True) -> None:
        self._player.heal(armour)

    def increase_max_health(self, amount: int) -> None:
        self._player.increase_max_health(amount)

    def increase_max_armour(self, amount: int) -> None:
        self._player.increase_max_armour(amount)


class PlayerVehicles:
    """Player vehicle relationship facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def current(self):
        return self._player.vehicle

    @property
    def remote(self):
        return self._player.remote_vehicle

    @property
    def special_collision(self):
        return self._player.special_collision_vehicle

    @property
    def last_target(self):
        return self._player.last_target_vehicle

    @property
    def time_counter(self) -> int:
        return self._player.vehicle_time_counter

    @property
    def trying_to_exit(self) -> bool:
        return self._player.trying_to_exit_car

    def apply_brakes(self, enabled: bool = True) -> None:
        self._player.apply_brakes_to_car(enabled)

    def consider(self, vehicle: Vehicle, enabled: bool = True) -> None:
        self._player.set_vehicle_considered(vehicle, enabled)

    def use_favourite_radio(self) -> None:
        self._player.use_favourite_radio_station()


class PlayerTargeting:
    """Targeting/crosshair facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def anything(self) -> bool:
        return self._player.targetting_anything

    @property
    def crosshair_active(self) -> bool:
        return self._player.crosshair_active

    @property
    def crosshair_target(self) -> tuple[float, float]:
        return self._player.crosshair_target

    def entity(self, entity) -> bool:
        return self._player.is_targetting(entity)


class PlayerRecords:
    """Player stats/counters that are stored on CPlayerInfo or SCM stats."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def wheelie_stats(self) -> tuple[int, float, int, float, int, float]:
        return self._player.wheelie_stats

    @property
    def total_peds_killed(self) -> int:
        return self._player.total_peds_killed

    def models_killed(self, model_id: int) -> int:
        return self._player.num_models_killed(model_id)

    def reset_models_killed(self) -> None:
        self._player.reset_num_models_killed()

    @property
    def kill_frenzy_status(self) -> int:
        return self._player.kill_frenzy_status

    @property
    def havoc_caused(self) -> int:
        return self._player.havoc_caused

    @havoc_caused.setter
    def havoc_caused(self, value: int) -> None:
        self._player.havoc_caused = value

    @property
    def best_car_two_wheels_time_ms(self) -> int:
        return self._player.best_car_two_wheels_time_ms

    @best_car_two_wheels_time_ms.setter
    def best_car_two_wheels_time_ms(self, value: int) -> None:
        self._player.best_car_two_wheels_time_ms = value

    @property
    def best_car_two_wheels_distance_m(self) -> float:
        return self._player.best_car_two_wheels_distance_m

    @best_car_two_wheels_distance_m.setter
    def best_car_two_wheels_distance_m(self, value: float) -> None:
        self._player.best_car_two_wheels_distance_m = value

    @property
    def best_bike_wheelie_time_ms(self) -> int:
        return self._player.best_bike_wheelie_time_ms

    @best_bike_wheelie_time_ms.setter
    def best_bike_wheelie_time_ms(self, value: int) -> None:
        self._player.best_bike_wheelie_time_ms = value

    @property
    def best_bike_wheelie_distance_m(self) -> float:
        return self._player.best_bike_wheelie_distance_m

    @best_bike_wheelie_distance_m.setter
    def best_bike_wheelie_distance_m(self, value: float) -> None:
        self._player.best_bike_wheelie_distance_m = value

    @property
    def best_bike_stoppie_time_ms(self) -> int:
        return self._player.best_bike_stoppie_time_ms

    @best_bike_stoppie_time_ms.setter
    def best_bike_stoppie_time_ms(self, value: int) -> None:
        self._player.best_bike_stoppie_time_ms = value

    @property
    def best_bike_stoppie_distance_m(self) -> float:
        return self._player.best_bike_stoppie_distance_m

    @best_bike_stoppie_distance_m.setter
    def best_bike_stoppie_distance_m(self, value: float) -> None:
        self._player.best_bike_stoppie_distance_m = value

    @property
    def collectables_picked_up(self) -> int:
        return self._player.collectables_picked_up

    @property
    def total_collectables(self) -> int:
        return self._player.total_collectables


class PlayerCamera:
    """Player camera facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def car_mode(self) -> int:
        return self._player.car_camera_mode

    @car_mode.setter
    def car_mode(self, mode: int) -> None:
        self._player.car_camera_mode = mode

    def behind(self) -> None:
        self._player.camera_behind()

    def front(self) -> None:
        self._player.camera_in_front()


class PlayerCoop:
    """Two-player/co-op related facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def active(self) -> bool:
        return self._player.two_player_game

    def limit_distance(self, distance: float) -> None:
        self._player.limit_two_player_distance(distance)

    def release_distance(self) -> None:
        self._player.release_two_player_distance()

    def camera_mode(self, mode: int) -> None:
        self._player.set_two_player_camera_mode(mode)

    def separate_cars(self, enabled: bool = True) -> None:
        self._player.set_players_can_be_in_separate_cars(enabled)

    def targetting(self, enabled: bool = True) -> None:
        self._player.set_player_targetting(enabled)


class PlayerMissions:
    """Mission/minigame helper facade."""

    __slots__ = ("_player",)

    def __init__(self, player: "_Player"):
        self._player = player

    @property
    def can_start(self) -> bool:
        return self._player.can_start_mission

    @property
    def deatharrest_executed(self) -> bool:
        return self._player.deatharrest_executed

    def deatharrest_state(self, enabled: bool = True) -> None:
        self._player.set_deatharrest_state(enabled)

    def safe_for_cutscene(self) -> None:
        self._player.safe_for_cutscene()

    def progress(self, value: int) -> None:
        self._player.made_progress(value)

    def bought_item(self, item_id: int) -> bool:
        return self._player.has_bought_item(item_id)

    def dock_crane(self) -> None:
        self._player.entered_dock_crane()

    def buildingsite_crane(self) -> None:
        self._player.entered_buildingsite_crane()

    def quarry_crane(self) -> None:
        self._player.entered_quarry_crane()

    def las_vegas_crane(self) -> None:
        self._player.entered_las_vegas_crane()

    def left_crane(self) -> None:
        self._player.left_crane()


class _Player:
    """Player 0 (single player). Use the module-level `player` instance."""

    index = 0
    _handle = 0  # lets you pass `player` where a command expects playerIndex

    @property
    def playing(self) -> bool:
        """True while a game session is running and the player is alive."""
        return cmd.IS_PLAYER_PLAYING(self.index)

    @property
    def ped(self) -> Ped:
        """The player's character (a Ped with all its properties/tasks)."""
        return cmd.GET_PLAYER_CHAR(self.index)

    @property
    def address(self) -> int:
        """Address of the player's CPed (0 outside a session)."""
        return _pysa.player_ped()

    @property
    def info_address(self) -> int:
        """Address of this player's CPlayerInfo."""
        return _player_info_addr(self.index)

    @property
    def stats(self) -> PlayerStats:
        return PlayerStats()

    @property
    def group(self) -> PlayerGroup:
        return PlayerGroup(self)

    @property
    def weapons(self) -> PlayerWeapons:
        return PlayerWeapons(self)

    @property
    def wanted(self) -> PlayerWanted:
        return PlayerWanted(self)

    @property
    def controls(self) -> PlayerControls:
        return PlayerControls(self)

    @property
    def perks(self) -> PlayerPerks:
        return PlayerPerks(self)

    @property
    def clothes(self) -> PlayerClothes:
        return PlayerClothes(self)

    @property
    def vitals(self) -> PlayerVitals:
        return PlayerVitals(self)

    @property
    def vehicles(self) -> PlayerVehicles:
        return PlayerVehicles(self)

    @property
    def targeting(self) -> PlayerTargeting:
        return PlayerTargeting(self)

    @property
    def records(self) -> PlayerRecords:
        return PlayerRecords(self)

    @property
    def camera(self) -> PlayerCamera:
        return PlayerCamera(self)

    @property
    def coop(self) -> PlayerCoop:
        return PlayerCoop(self)

    @property
    def missions(self) -> PlayerMissions:
        return PlayerMissions(self)

    # -- convenience proxies to the ped ---------------------------------------

    @property
    def pos(self) -> Vector3:
        return self.ped.pos

    @pos.setter
    def pos(self, value) -> None:
        self.ped.pos = value

    @property
    def heading(self) -> float:
        return self.ped.heading

    @heading.setter
    def heading(self, degrees: float) -> None:
        self.ped.heading = degrees

    @property
    def health(self) -> int:
        return self.ped.health

    @health.setter
    def health(self, value: int) -> None:
        self.ped.health = value

    @property
    def max_health(self) -> int:
        return int(self.ped.max_health)

    @max_health.setter
    def max_health(self, value: int) -> None:
        self.ped.max_health = value
        _write_u8(self.info_address + 0x14F, value)

    def increase_max_health(self, amount: int) -> None:
        cmd.INCREASE_PLAYER_MAX_HEALTH(self.index, amount)

    @property
    def armour(self) -> int:
        return self.ped.armour

    @armour.setter
    def armour(self, value: int) -> None:
        self.ped.armour = value

    @property
    def max_armour(self) -> int:
        return cmd.GET_PLAYER_MAX_ARMOUR(self.index)

    @max_armour.setter
    def max_armour(self, value: int) -> None:
        _write_u8(self.info_address + 0x150, value)

    def increase_max_armour(self, amount: int) -> None:
        cmd.INCREASE_PLAYER_MAX_ARMOUR(self.index, amount)

    @property
    def vehicle(self):
        """Vehicle the player is driving/riding, or None."""
        return self.ped.vehicle

    @property
    def remote_vehicle(self):
        """RC vehicle controlled by the player, or None."""
        return _vehicle_from_ptr(_pysa.read_u32(self.info_address + 0xB0))

    @property
    def special_collision_vehicle(self):
        return _vehicle_from_ptr(_pysa.read_u32(self.info_address + 0xB4))

    @property
    def last_target_vehicle(self):
        """Last vehicle the player tried to enter, or None."""
        return _vehicle_from_ptr(_pysa.read_u32(self.info_address + 0xD8))

    @property
    def speed(self) -> float:
        return self.ped.speed

    @property
    def current_weapon(self) -> int:
        return self.ped.current_weapon

    @current_weapon.setter
    def current_weapon(self, weapon: int) -> None:
        self.ped.current_weapon = weapon

    def give_weapon(self, weapon: int, ammo: int = 500, equip: bool = True) -> None:
        self.ped.give_weapon(weapon, ammo, equip)

    def add_ammo(self, weapon: int, ammo: int) -> None:
        cmd.ADD_AMMO_TO_CHAR(self.ped, weapon, ammo)

    def set_ammo(self, weapon: int, ammo: int) -> None:
        cmd.SET_CHAR_AMMO(self.ped, weapon, ammo)

    def ammo(self, weapon: int) -> int:
        return cmd.GET_AMMO_IN_CHAR_WEAPON(self.ped, weapon)

    def has_weapon(self, weapon: int) -> bool:
        return cmd.HAS_CHAR_GOT_WEAPON(self.ped, weapon)

    def remove_weapon(self, weapon: int) -> None:
        self.ped.remove_weapon(weapon)

    def remove_weapons(self) -> None:
        self.ped.remove_weapons()

    # -- money / wanted --------------------------------------------------------

    @property
    def money(self) -> int:
        return cmd.STORE_SCORE(self.index)

    @money.setter
    def money(self, value: int) -> None:
        cmd.ADD_SCORE(self.index, int(value) - self.money)

    @property
    def display_money(self) -> int:
        """Money value currently being animated/displayed by the HUD."""
        return _pysa.read_i32(self.info_address + 0xBC)

    @property
    def wanted_level(self) -> int:
        return cmd.STORE_WANTED_LEVEL(self.index)

    @wanted_level.setter
    def wanted_level(self, level: int) -> None:
        if level <= 0:
            cmd.CLEAR_WANTED_LEVEL(self.index)
        else:
            cmd.ALTER_WANTED_LEVEL(self.index, level)

    def set_wanted_level_no_drop(self, level: int) -> None:
        cmd.ALTER_WANTED_LEVEL_NO_DROP(self.index, level)

    def is_wanted_level_greater(self, level: int) -> bool:
        return cmd.IS_WANTED_LEVEL_GREATER(self.index, level)

    @property
    def max_wanted_level(self) -> int:
        return cmd.GET_MAX_WANTED_LEVEL()

    @max_wanted_level.setter
    def max_wanted_level(self, level: int) -> None:
        cmd.SET_MAX_WANTED_LEVEL(level)

    def set_max_wanted_level(self, level: int) -> None:
        self.max_wanted_level = level

    def clear_wanted_level_in_garage(self) -> None:
        cmd.CLEAR_WANTED_LEVEL_IN_GARAGE()

    def set_wanted_multiplier(self, multiplier: float) -> None:
        cmd.SET_WANTED_MULTIPLIER(multiplier)

    @property
    def current_chase_value(self) -> float:
        return _pysa.read_f32(self.info_address + 0x148)

    @current_chase_value.setter
    def current_chase_value(self, value: float) -> None:
        _pysa.write_f32(self.info_address + 0x148, value)

    # -- state / control -------------------------------------------------------

    @property
    def state(self) -> int:
        """Raw CPlayerInfo::m_nPlayerState."""
        return _pysa.read_u8(self.info_address + 0xDC)

    @property
    def state_name(self) -> str:
        return _PLAYER_STATE_NAMES.get(self.state, f"unknown_{self.state}")

    @property
    def is_dead(self) -> bool:
        return cmd.IS_PLAYER_DEAD(self.index)

    @property
    def is_busted(self) -> bool:
        return self.state == PLAYER_STATE.HAS_BEEN_ARRESTED

    @property
    def control_on(self) -> bool:
        return cmd.IS_PLAYER_CONTROL_ON(self.index)

    @control_on.setter
    def control_on(self, enabled: bool) -> None:
        cmd.SET_PLAYER_CONTROL(self.index, enabled)

    def set_control(self, enabled: bool = True) -> None:
        self.control_on = enabled

    def safe_for_cutscene(self) -> None:
        cmd.MAKE_PLAYER_SAFE_FOR_CUTSCENE(self.index)

    def set_deatharrest_state(self, enabled: bool = True) -> None:
        cmd.SET_DEATHARREST_STATE(enabled)

    @property
    def deatharrest_executed(self) -> bool:
        return cmd.HAS_DEATHARREST_BEEN_EXECUTED()

    @property
    def can_start_mission(self) -> bool:
        return cmd.CAN_PLAYER_START_MISSION(self.index)

    @property
    def trying_to_exit_car(self) -> bool:
        return _read_bool(self.info_address + 0xD5)

    @property
    def vehicle_time_counter(self) -> int:
        return _pysa.read_u32(self.info_address + 0xD0)

    @property
    def last_bump_player_car_timer(self) -> int:
        return _pysa.read_u32(self.info_address + 0xC8)

    @property
    def after_remote_vehicle_explosion(self) -> bool:
        return _read_bool(self.info_address + 0xDD)

    @after_remote_vehicle_explosion.setter
    def after_remote_vehicle_explosion(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0xDD, enabled)

    @property
    def create_remote_vehicle_explosion(self) -> bool:
        return _read_bool(self.info_address + 0xDE)

    @create_remote_vehicle_explosion.setter
    def create_remote_vehicle_explosion(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0xDE, enabled)

    @property
    def fade_after_remote_vehicle_explosion(self) -> bool:
        return _read_bool(self.info_address + 0xDF)

    @fade_after_remote_vehicle_explosion.setter
    def fade_after_remote_vehicle_explosion(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0xDF, enabled)

    @property
    def time_of_remote_vehicle_explosion(self) -> int:
        return _pysa.read_u32(self.info_address + 0xE0)

    @time_of_remote_vehicle_explosion.setter
    def time_of_remote_vehicle_explosion(self, value: int) -> None:
        _write_u32(self.info_address + 0xE0, value)

    @property
    def last_time_energy_lost(self) -> int:
        return _pysa.read_u32(self.info_address + 0xE4)

    @last_time_energy_lost.setter
    def last_time_energy_lost(self, value: int) -> None:
        _write_u32(self.info_address + 0xE4, value)

    @property
    def last_time_armour_lost(self) -> int:
        return _pysa.read_u32(self.info_address + 0xE8)

    @last_time_armour_lost.setter
    def last_time_armour_lost(self, value: int) -> None:
        _write_u32(self.info_address + 0xE8, value)

    @property
    def last_time_big_gun_fired(self) -> int:
        return _pysa.read_u32(self.info_address + 0xEC)

    @last_time_big_gun_fired.setter
    def last_time_big_gun_fired(self, value: int) -> None:
        _write_u32(self.info_address + 0xEC, value)

    @property
    def times_upside_down_in_row(self) -> int:
        return _pysa.read_u32(self.info_address + 0xF0)

    @times_upside_down_in_row.setter
    def times_upside_down_in_row(self, value: int) -> None:
        _write_u32(self.info_address + 0xF0, value)

    @property
    def times_stuck_in_row(self) -> int:
        return _pysa.read_u32(self.info_address + 0xF4)

    @times_stuck_in_row.setter
    def times_stuck_in_row(self, value: int) -> None:
        _write_u32(self.info_address + 0xF4, value)

    @property
    def car_two_wheel_counter(self) -> int:
        return _pysa.read_u32(self.info_address + 0xF8)

    @property
    def car_two_wheel_distance(self) -> float:
        return _pysa.read_f32(self.info_address + 0xFC)

    @property
    def car_less_three_wheel_counter(self) -> int:
        return _pysa.read_u32(self.info_address + 0x100)

    @property
    def bike_rear_wheel_counter(self) -> int:
        return _pysa.read_u32(self.info_address + 0x104)

    @property
    def bike_rear_wheel_distance(self) -> float:
        return _pysa.read_f32(self.info_address + 0x108)

    @property
    def bike_front_wheel_counter(self) -> int:
        return _pysa.read_u32(self.info_address + 0x10C)

    @property
    def bike_front_wheel_distance(self) -> float:
        return _pysa.read_f32(self.info_address + 0x110)

    @property
    def temp_buffer_counter(self) -> int:
        return _pysa.read_u32(self.info_address + 0x114)

    @property
    def best_car_two_wheels_time_ms(self) -> int:
        return _pysa.read_u32(self.info_address + 0x118)

    @best_car_two_wheels_time_ms.setter
    def best_car_two_wheels_time_ms(self, value: int) -> None:
        _write_u32(self.info_address + 0x118, value)

    @property
    def best_car_two_wheels_distance_m(self) -> float:
        return _pysa.read_f32(self.info_address + 0x11C)

    @best_car_two_wheels_distance_m.setter
    def best_car_two_wheels_distance_m(self, value: float) -> None:
        _pysa.write_f32(self.info_address + 0x11C, value)

    @property
    def best_bike_wheelie_time_ms(self) -> int:
        return _pysa.read_u32(self.info_address + 0x120)

    @best_bike_wheelie_time_ms.setter
    def best_bike_wheelie_time_ms(self, value: int) -> None:
        _write_u32(self.info_address + 0x120, value)

    @property
    def best_bike_wheelie_distance_m(self) -> float:
        return _pysa.read_f32(self.info_address + 0x124)

    @best_bike_wheelie_distance_m.setter
    def best_bike_wheelie_distance_m(self, value: float) -> None:
        _pysa.write_f32(self.info_address + 0x124, value)

    @property
    def best_bike_stoppie_time_ms(self) -> int:
        return _pysa.read_u32(self.info_address + 0x128)

    @best_bike_stoppie_time_ms.setter
    def best_bike_stoppie_time_ms(self, value: int) -> None:
        _write_u32(self.info_address + 0x128, value)

    @property
    def best_bike_stoppie_distance_m(self) -> float:
        return _pysa.read_f32(self.info_address + 0x12C)

    @best_bike_stoppie_distance_m.setter
    def best_bike_stoppie_distance_m(self, value: float) -> None:
        _pysa.write_f32(self.info_address + 0x12C, value)

    @property
    def car_density_for_current_zone(self) -> int:
        return _pysa.read_u16(self.info_address + 0x130)

    @car_density_for_current_zone.setter
    def car_density_for_current_zone(self, value: int) -> None:
        _write_u16(self.info_address + 0x130, value)

    @property
    def road_density_around_player(self) -> float:
        return _pysa.read_f32(self.info_address + 0x134)

    @road_density_around_player.setter
    def road_density_around_player(self, value: float) -> None:
        _pysa.write_f32(self.info_address + 0x134, value)

    @property
    def time_of_last_car_explosion_caused(self) -> int:
        return _pysa.read_u32(self.info_address + 0x138)

    @time_of_last_car_explosion_caused.setter
    def time_of_last_car_explosion_caused(self, value: int) -> None:
        _write_u32(self.info_address + 0x138, value)

    @property
    def explosion_multiplier(self) -> int:
        return _pysa.read_u32(self.info_address + 0x13C)

    @explosion_multiplier.setter
    def explosion_multiplier(self, value: int) -> None:
        _write_u32(self.info_address + 0x13C, value)

    @property
    def havoc_caused(self) -> int:
        return _pysa.read_u32(self.info_address + 0x140)

    @havoc_caused.setter
    def havoc_caused(self, value: int) -> None:
        _write_u32(self.info_address + 0x140, value)

    @property
    def hours_without_eating(self) -> int:
        return _pysa.read_u16(self.info_address + 0x144)

    @hours_without_eating.setter
    def hours_without_eating(self, value: int) -> None:
        _write_u16(self.info_address + 0x144, value)

    @property
    def busted_audio_status(self) -> int:
        return _pysa.read_u8(self.info_address + 0x154)

    @busted_audio_status.setter
    def busted_audio_status(self, value: int) -> None:
        _write_u8(self.info_address + 0x154, value)

    @property
    def last_bust_message_number(self) -> int:
        return _pysa.read_u16(self.info_address + 0x156)

    @last_bust_message_number.setter
    def last_bust_message_number(self, value: int) -> None:
        _write_u16(self.info_address + 0x156, value)

    @property
    def parachute_referenced(self) -> bool:
        return _read_bool(self.info_address + 0x188)

    @parachute_referenced.setter
    def parachute_referenced(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0x188, enabled)

    @property
    def require_parachute_timer(self) -> int:
        return _pysa.read_u32(self.info_address + 0x18C)

    @require_parachute_timer.setter
    def require_parachute_timer(self, value: int) -> None:
        _write_u32(self.info_address + 0x18C, value)

    # -- targeting / movement checks -----------------------------------------

    @property
    def targetting_anything(self) -> bool:
        return cmd.IS_PLAYER_TARGETTING_ANYTHING(self.index)

    def is_targetting(self, entity) -> bool:
        if isinstance(entity, Ped):
            return cmd.IS_PLAYER_TARGETTING_CHAR(self.index, entity)
        return cmd.IS_PLAYER_TARGETTING_OBJECT(self.index, entity)

    @property
    def crosshair_active(self) -> bool:
        return bool(_pysa.read_u32(self.info_address + 0x158))

    @property
    def crosshair_target(self) -> tuple[float, float]:
        return (
            _pysa.read_f32(self.info_address + 0x15C),
            _pysa.read_f32(self.info_address + 0x160),
        )

    @property
    def pressing_horn(self) -> bool:
        return cmd.IS_PLAYER_PRESSING_HORN(self.index)

    @property
    def climbing(self) -> bool:
        return cmd.IS_PLAYER_CLIMBING(self.index)

    @property
    def using_jetpack(self) -> bool:
        return cmd.IS_PLAYER_USING_JETPACK(self.index)

    @property
    def in_remote_mode(self) -> bool:
        return cmd.IS_PLAYER_IN_REMOTE_MODE(self.index)

    @property
    def performing_wheelie(self) -> bool:
        return cmd.IS_PLAYER_PERFORMING_WHEELIE(self.index)

    @property
    def performing_stoppie(self) -> bool:
        return cmd.IS_PLAYER_PERFORMING_STOPPIE(self.index)

    @property
    def wheelie_stats(self) -> tuple[int, float, int, float, int, float]:
        """Latest (two_wheels_time, distance, wheelie_time, distance, stoppie_time, distance)."""
        return cmd.GET_WHEELIE_STATS(self.index)

    def camera_behind(self) -> None:
        cmd.SET_CAMERA_BEHIND_PLAYER()

    def camera_in_front(self) -> None:
        cmd.SET_CAMERA_IN_FRONT_OF_PLAYER()

    def apply_brakes_to_car(self, enabled: bool = True) -> None:
        cmd.APPLY_BRAKES_TO_PLAYERS_CAR(self.index, enabled)

    # -- perks / restrictions --------------------------------------------------

    @property
    def never_tired_enabled(self) -> bool:
        return _read_bool(self.info_address + 0x14C)

    def never_tired(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_NEVER_GETS_TIRED(self.index, enabled)

    def disable_sprint(self, disabled: bool = True) -> None:
        cmd.DISABLE_PLAYER_SPRINT(self.index, disabled)

    @property
    def fast_reload_enabled(self) -> bool:
        return _read_bool(self.info_address + 0x14D)

    def fast_reload(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_FAST_RELOAD(self.index, enabled)

    @property
    def fire_proof_enabled(self) -> bool:
        return _read_bool(self.info_address + 0x14E)

    def fire_proof(self, enabled: bool = True) -> None:
        cmd.MAKE_PLAYER_FIRE_PROOF(self.index, enabled)

    def ignore_by_everyone(self, enabled: bool = True) -> None:
        cmd.SET_EVERYONE_IGNORE_PLAYER(self.index, enabled)

    def ignore_by_police(self, enabled: bool = True) -> None:
        cmd.SET_POLICE_IGNORE_PLAYER(self.index, enabled)

    @property
    def can_do_drive_by(self) -> bool:
        return _read_bool(self.info_address + 0x153)

    @can_do_drive_by.setter
    def can_do_drive_by(self, enabled: bool) -> None:
        cmd.SET_PLAYER_CAN_DO_DRIVE_BY(self.index, enabled)

    def ensure_drive_by_weapon(self, ammo: int = 9999) -> None:
        cmd.ENSURE_PLAYER_HAS_DRIVE_BY_WEAPON(self.index, ammo)

    def set_mood(self, mood: int, duration_ms: int = 4000) -> None:
        cmd.SET_PLAYER_MOOD(self.index, mood, duration_ms)

    def set_drunkenness(self, intensity: int) -> None:
        cmd.SET_PLAYER_DRUNKENNESS(self.index, intensity)

    def set_swim_speed(self, speed: float) -> None:
        cmd.SET_SWIM_SPEED(self.ped, speed)

    def set_fire_button(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_FIRE_BUTTON(self.index, enabled)

    def set_jump_button(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_JUMP_BUTTON(self.index, enabled)

    def set_duck_button(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_DUCK_BUTTON(self.index, enabled)

    def set_enter_car_button(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_ENTER_CAR_BUTTON(self.index, enabled)

    def set_cycle_weapon_button(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_CYCLE_WEAPON_BUTTON(self.index, enabled)

    def set_vital_stats_button(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_DISPLAY_VITAL_STATS_BUTTON(self.index, enabled)

    def put_on_goggles(self, animate: bool = True) -> None:
        call(0x09EA, self.index, animate)

    def take_off_goggles(self, animate: bool = True) -> None:
        cmd.PLAYER_TAKE_OFF_GOGGLES(self.index, animate)

    @property
    def get_out_of_jail_free(self) -> bool:
        return _read_bool(self.info_address + 0x151)

    @get_out_of_jail_free.setter
    def get_out_of_jail_free(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0x151, enabled)

    @property
    def get_out_of_hospital_free(self) -> bool:
        return _read_bool(self.info_address + 0x152)

    @get_out_of_hospital_free.setter
    def get_out_of_hospital_free(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0x152, enabled)

    def switch_death_penalties(self, enabled: bool = True) -> None:
        cmd.SWITCH_DEATH_PENALTIES(enabled)

    def switch_arrest_penalties(self, enabled: bool = True) -> None:
        cmd.SWITCH_ARREST_PENALTIES(enabled)

    def heal(self, armour: bool = True) -> None:
        ped = self.ped
        ped.health = int(ped.max_health) or 100
        if armour:
            ped.armour = self.max_armour or 100

    # -- clothes / model -------------------------------------------------------

    def set_model(self, model: int) -> None:
        cmd.SET_PLAYER_MODEL(self.index, model)

    def build_model(self) -> None:
        cmd.BUILD_PLAYER_MODEL(self.index)

    def give_clothes(self, texture_hash: int, model_hash: int, body_part: int) -> None:
        cmd.GIVE_PLAYER_CLOTHES(self.index, texture_hash, model_hash, body_part)

    def give_clothes_named(self, texture: str, model: str, body_part: int) -> None:
        cmd.GIVE_PLAYER_CLOTHES_OUTSIDE_SHOP(self.index, texture, model, body_part)

    def clothes_item(self, body_part: int) -> tuple[int, int]:
        return cmd.GET_CLOTHES_ITEM(self.index, body_part)

    def is_wearing(self, body_part: int, model_name: str) -> bool:
        return cmd.IS_PLAYER_WEARING(self.index, body_part, model_name)

    def store_clothes(self) -> None:
        cmd.STORE_CLOTHES_STATE()

    def restore_clothes(self) -> None:
        cmd.RESTORE_CLOTHES_STATE()

    @property
    def skin_name(self) -> str:
        data = _pysa.mem_read(self.info_address + 0x164, 32)
        return data.split(b"\0", 1)[0].decode("ascii", "ignore")

    @property
    def skin_texture_address(self) -> int:
        return _pysa.read_u32(self.info_address + 0x184)

    # -- misc player progress -------------------------------------------------

    @property
    def city(self) -> int:
        return cmd.GET_CITY_PLAYER_IS_IN(self.index)

    def in_info_zone(self, name: str) -> bool:
        return cmd.IS_PLAYER_IN_INFO_ZONE(self.index, name)

    def set_stadium_radar(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_IS_IN_STADIUM(enabled)

    @property
    def collectables_picked_up(self) -> int:
        return _pysa.read_u32(self.info_address + 0xC0)

    @property
    def total_collectables(self) -> int:
        return _pysa.read_u32(self.info_address + 0xC4)

    @property
    def taxi_timer(self) -> int:
        return _pysa.read_u32(self.info_address + 0xCC)

    @property
    def taxi_timer_score_enabled(self) -> bool:
        return _read_bool(self.info_address + 0xD4)

    @taxi_timer_score_enabled.setter
    def taxi_timer_score_enabled(self, enabled: bool) -> None:
        _write_bool(self.info_address + 0xD4, enabled)

    def made_progress(self, progress: int) -> None:
        cmd.PLAYER_MADE_PROGRESS(progress)

    @property
    def kill_frenzy_status(self) -> int:
        return cmd.READ_KILL_FRENZY_STATUS()

    @property
    def total_peds_killed(self) -> int:
        return cmd.GET_TOTAL_NUMBER_OF_PEDS_KILLED_BY_PLAYER(self.index)

    def num_models_killed(self, model_id: int) -> int:
        return cmd.GET_NUM_OF_MODELS_KILLED_BY_PLAYER(self.index, model_id)

    def reset_num_models_killed(self) -> None:
        cmd.RESET_NUM_OF_MODELS_KILLED_BY_PLAYER(self.index)

    def is_last_building_model_shot(self, model_id: int) -> bool:
        return cmd.IS_LAST_BUILDING_MODEL_SHOT_BY_PLAYER(self.index, model_id)

    def clear_last_building_model_shot(self) -> None:
        cmd.CLEAR_LAST_BUILDING_MODEL_SHOT_BY_PLAYER(self.index)

    def has_bought_item(self, item_id: int) -> bool:
        return cmd.HAS_PLAYER_BOUGHT_ITEM(item_id)

    @property
    def conversation_ready(self) -> bool:
        return cmd.IS_PLAYER_IN_POSITION_FOR_CONVERSATION(self.ped)

    def get_rid_of_prostitute(self) -> None:
        cmd.GET_RID_OF_PLAYER_PROSTITUTE()

    def force_interior_lighting(self, enabled: bool = True) -> None:
        cmd.FORCE_INTERIOR_LIGHTING_FOR_PLAYER(self.index, enabled)

    @property
    def car_camera_mode(self) -> int:
        return cmd.GET_PLAYER_IN_CAR_CAMERA_MODE()

    @car_camera_mode.setter
    def car_camera_mode(self, mode: int) -> None:
        cmd.SET_PLAYER_IN_CAR_CAMERA_MODE(mode)

    def use_favourite_radio_station(self) -> None:
        cmd.SET_RADIO_TO_PLAYERS_FAVOURITE_STATION()

    # -- mission / minigame command helpers -----------------------------------

    def entered_dock_crane(self) -> None:
        cmd.PLAYER_ENTERED_DOCK_CRANE()

    def entered_buildingsite_crane(self) -> None:
        cmd.PLAYER_ENTERED_BUILDINGSITE_CRANE()

    def entered_quarry_crane(self) -> None:
        cmd.PLAYER_ENTERED_QUARRY_CRANE()

    def entered_las_vegas_crane(self) -> None:
        cmd.PLAYER_ENTERED_LAS_VEGAS_CRANE()

    def left_crane(self) -> None:
        cmd.PLAYER_LEFT_CRANE()

    def is_next_station_allowed(self, station: int) -> bool:
        return cmd.IS_NEXT_STATION_ALLOWED(station)

    def skip_to_next_allowed_station(self, train) -> None:
        cmd.SKIP_TO_NEXT_ALLOWED_STATION(train)

    # -- two-player / co-op ----------------------------------------------------

    @property
    def two_player_game(self) -> bool:
        return cmd.IS_2PLAYER_GAME_GOING_ON()

    def limit_two_player_distance(self, distance: float) -> None:
        cmd.LIMIT_TWO_PLAYER_DISTANCE(distance)

    def release_two_player_distance(self) -> None:
        cmd.RELEASE_TWO_PLAYER_DISTANCE()

    def set_two_player_camera_mode(self, mode: int) -> None:
        cmd.SET_TWO_PLAYER_CAMERA_MODE(mode)

    def set_players_can_be_in_separate_cars(self, enabled: bool = True) -> None:
        cmd.SET_PLAYERS_CAN_BE_IN_SEPARATE_CARS(enabled)

    def set_player_targetting(self, enabled: bool = True) -> None:
        cmd.SET_PLAYER_PLAYER_TARGETTING(enabled)

    def set_heading_for_attached(self, heading: float, heading_range: float) -> None:
        cmd.SET_HEADING_FOR_ATTACHED_PLAYER(self.index, heading, heading_range)

    @property
    def attached_heading_achieved(self) -> bool:
        return cmd.IS_ATTACHED_PLAYER_HEADING_ACHIEVED(self.index)

    def set_vehicle_considered(self, vehicle: Vehicle, enabled: bool = True) -> None:
        cmd.SET_VEHICLE_IS_CONSIDERED_BY_PLAYER(vehicle, enabled)


player = _Player()
