"""Friendly state-transition events that are polled only when subscribed.

These complement hook-backed events in :mod:`pysa.game_events`. They trade
same-instruction cancellation for safer, ordinary Python payloads and cover
state transitions that the Plugin SDK does not publish directly.
"""
from __future__ import annotations

from .models import WEAPON


class PedDamageEvent:
    __slots__ = ("ped", "amount", "previous_health", "health")

    def __init__(self, ped, amount: int, previous_health: int, health: int):
        self.ped = ped
        self.amount = int(amount)
        self.previous_health = int(previous_health)
        self.health = int(health)


class PedDeathEvent:
    __slots__ = ("ped",)

    def __init__(self, ped):
        self.ped = ped


class VehicleEnterEvent:
    __slots__ = ("ped", "vehicle", "seat")

    def __init__(self, ped, vehicle, seat: int):
        self.ped = ped
        self.vehicle = vehicle
        self.seat = int(seat)

    @property
    def driver(self) -> bool:
        return self.seat == -1


class VehicleExitEvent(VehicleEnterEvent):
    pass


class WeaponChangedEvent:
    __slots__ = ("ped", "previous", "weapon")

    def __init__(self, ped, previous, weapon):
        self.ped = ped
        self.previous = _weapon(previous)
        self.weapon = _weapon(weapon)


class ZoneEvent:
    __slots__ = ("name", "position")

    def __init__(self, name: str, position):
        from .math3 import Vector3
        self.name = str(name)
        self.position = Vector3.of(position)


_ped_state = {}
_vehicle_state = {}
_weapon_state = {}
_zone = None
_zone_initialized = False

_EVENT_NAMES = frozenset({
    "ped_damage", "ped_death", "vehicle_enter", "vehicle_exit",
    "weapon_changed", "zone_enter", "zone_exit",
})


def _weapon(value):
    try:
        return WEAPON(value)
    except ValueError:
        return int(value)


def _emit(name: str, payload) -> None:
    from . import _runtime
    for handler in _runtime._handlers.get(name, ()):
        handler.run(payload)


def _seat_of(ped, vehicle) -> int:
    try:
        if vehicle.driver == ped:
            return -1
        for seat, passenger in enumerate(vehicle.passengers):
            if passenger == ped:
                return seat
    except Exception:
        pass
    return -2  # in a vehicle, but the game has not assigned a stable seat yet


def _poll() -> None:
    from . import _runtime
    wanted = _EVENT_NAMES.intersection(
        name for name, handlers in _runtime._handlers.items()
        if any(not handler.disabled for handler in handlers))
    if not wanted:
        return

    from .entities import all_peds
    peds = all_peds()
    live_handles = {ped.handle for ped in peds}

    if "ped_damage" in wanted or "ped_death" in wanted:
        for ped in peds:
            try:
                health = int(ped.health)
                dead = bool(ped.dead)
            except Exception:
                continue
            previous = _ped_state.get(ped.handle)
            if previous is not None:
                old_health, old_dead = previous
                if health < old_health and "ped_damage" in wanted:
                    _emit("ped_damage", PedDamageEvent(
                        ped, old_health - health, old_health, health))
                if dead and not old_dead and "ped_death" in wanted:
                    _emit("ped_death", PedDeathEvent(ped))
            _ped_state[ped.handle] = (health, dead)
        for handle in set(_ped_state) - live_handles:
            _ped_state.pop(handle, None)

    if "vehicle_enter" in wanted or "vehicle_exit" in wanted:
        for ped in peds:
            try:
                current = ped.vehicle
            except Exception:
                continue
            initialized, previous, previous_seat = _vehicle_state.get(
                ped.handle, (False, None, -2))
            current_seat = -2 if current is None else _seat_of(ped, current)
            if initialized and previous != current:
                if previous is not None and "vehicle_exit" in wanted:
                    _emit("vehicle_exit", VehicleExitEvent(
                        ped, previous, previous_seat))
                if current is not None and "vehicle_enter" in wanted:
                    _emit("vehicle_enter", VehicleEnterEvent(
                        ped, current, current_seat))
            _vehicle_state[ped.handle] = (True, current, current_seat)
        for handle in set(_vehicle_state) - live_handles:
            _vehicle_state.pop(handle, None)

    if "weapon_changed" in wanted:
        for ped in peds:
            try:
                current = int(ped.current_weapon)
            except Exception:
                continue
            previous = _weapon_state.get(ped.handle)
            if previous is not None and previous != current:
                _emit("weapon_changed", WeaponChangedEvent(ped, previous, current))
            _weapon_state[ped.handle] = current
        for handle in set(_weapon_state) - live_handles:
            _weapon_state.pop(handle, None)

    if "zone_enter" in wanted or "zone_exit" in wanted:
        _poll_zone(wanted)


def _poll_zone(wanted) -> None:
    global _zone, _zone_initialized
    from .player import player
    from . import world
    if not player.playing:
        _zone_initialized = False
        _zone = None
        return
    position = player.pos
    current = world.zone_name(position)
    if _zone_initialized and current != _zone:
        if _zone and "zone_exit" in wanted:
            _emit("zone_exit", ZoneEvent(_zone, position))
        if current and "zone_enter" in wanted:
            _emit("zone_enter", ZoneEvent(current, position))
    _zone = current
    _zone_initialized = True


def _reset() -> None:
    global _zone, _zone_initialized
    _ped_state.clear()
    _vehicle_state.clear()
    _weapon_state.clear()
    _zone = None
    _zone_initialized = False
