"""High-level game events - the friendly face of function hooks.

These read like the lifecycle events you already use (`on_vehicle_created`
etc.), but they fire on things the game *does*, with domain-named fields:

    @pysa.on_vehicle_damage
    def tougher_cars(e):
        if e.vehicle == pysa.player.vehicle:
            e.amount *= 0.5        # take half damage
            # e.cancel()          # or ignore the hit entirely

    @pysa.on_explosion
    def no_booms(e):
        if e.position.distance_to(pysa.player.pos) < 30:
            e.cancel()

Each event handler receives an event object `e` with:
    e.<subject>       the thing it happened to (a Ped/Vehicle), when there is one
    e.<field>         named, typed values (entities wrapped, floats as floats,
                      positions as Vector3); assign to rewrite before it happens
    e.cancel()        stop the original from happening
    e.raw             the low-level hooks.Call, if you need registers/raw args

Under the hood each event is a hook on a specific game function (see
`_EVENTS`); this module just gives them human names and fields. For anything
not covered here, drop to `pysa.on_call(...)`.
"""
from __future__ import annotations

import traceback

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import hooks
from .functions import FUNCTIONS
from .math3 import Vector3

_OWNER_WRAP = {"CPed": "ped", "CPlayerPed": "ped", "CVehicle": "vehicle",
               "CAutomobile": "vehicle", "CObject": "object"}


def entity_from_ptr(ptr: int):
    """Wrap a raw CEntity* into a Ped/Vehicle/GameObject by its type byte."""
    if not ptr:
        return None
    from .entities import GameObject, Ped, Vehicle
    kind = _pysa.read_u8(ptr + 0x36) & 0x7   # CEntity::m_nType (bits 0-2)
    if kind == 2:
        return Vehicle.from_ptr(ptr)
    if kind == 3:
        return Ped.from_ptr(ptr)
    if kind == 4:
        return GameObject.from_ptr(ptr)
    return ptr   # building / dummy / nothing - no wrapper


# event name -> (function, subject_or_None, {domain_field: (arg_name, kind)})
# kind: "entity" | "ped" | "vehicle" | "object" | "int" | "float" | "bool" | "vec"
_EVENTS = {
    "vehicle_damage": ("CVehicle::InflictDamage", "vehicle", {
        "attacker": ("damager", "entity"),
        "weapon": ("weapon", "int"),
        "amount": ("intensity", "float"),
    }),
    "vehicle_explode": ("CVehicle::BlowUpCar", "vehicle", {
        "attacker": ("damager", "entity"),
    }),
    "tyre_burst": ("CVehicle::BurstTyre", "vehicle", {
        "tyre": ("tyreComponentId", "int"),
    }),
    "weapon_fire": ("CWeapon::Fire", None, {
        "shooter": ("firingEntity", "entity"),
        "target": ("targetEntity", "entity"),
    }),
    "explosion": ("CExplosion::AddExplosion", None, {
        "victim": ("victim", "entity"),
        "creator": ("creator", "entity"),
        "kind": ("explosionType", "int"),
        "position": ("posn", "vec"),
    }),
    "wanted_level_change": ("CPlayerPed::SetWantedLevel", "player", {
        "level": ("level", "int"),
    }),
    "weapon_given": ("CPed::GiveWeapon", "ped", {
        "weapon": ("weaponType", "int"),
        "ammo": ("ammo", "int"),
    }),
    "projectile_fired": ("CProjectileInfo::AddProjectile", None, {
        "shooter": ("creator", "entity"),
        "weapon": ("weaponType", "int"),
        "position": ("posn", "vec"),
        "target": ("victim", "entity"),
    }),
}


class GameEvent:
    """The friendly event object passed to a game-event handler."""

    __slots__ = ("_h", "_fields", "_subject", "_owner")

    def __init__(self, raw: hooks.Hook, fields: dict, subject, owner_class):
        object.__setattr__(self, "_h", raw)
        object.__setattr__(self, "_fields", fields)   # domain -> (slot, kind)
        object.__setattr__(self, "_subject", subject)  # domain name of `this`, or None
        object.__setattr__(self, "_owner", owner_class)

    @property
    def raw(self) -> hooks.Hook:
        return self._h

    def cancel(self, value: int = 0) -> None:
        """Stop the original from happening (returns `value` to the game)."""
        self._h.skip(value)

    def _read(self, slot, kind):
        if kind == "float":
            return self._h.argf(slot)
        if kind == "vec":
            return Vector3(self._h.argf(slot), self._h.argf(slot + 1),
                           self._h.argf(slot + 2))
        raw = self._h.arg(slot)
        if kind == "entity":
            return entity_from_ptr(raw)
        if kind in ("ped", "vehicle", "object"):
            from .entities import GameObject, Ped, Vehicle
            return {"ped": Ped, "vehicle": Vehicle, "object": GameObject}[kind].from_ptr(raw)
        if kind == "bool":
            return bool(raw)
        return raw

    def __getattr__(self, name: str):
        if name == self._subject:
            ptr = self._h.this
            wrap = _OWNER_WRAP.get(self._owner)
            if wrap:
                from .entities import GameObject, Ped, Vehicle
                return {"ped": Ped, "vehicle": Vehicle, "object": GameObject}[wrap].from_ptr(ptr)
            return ptr
        field = self._fields.get(name)
        if field is None:
            raise AttributeError(f"event has no field {name!r}; available: "
                                 f"{', '.join(self._field_names())}")
        return self._read(*field)

    def __setattr__(self, name: str, value) -> None:
        field = self._fields.get(name)
        if field is None:
            raise AttributeError(f"cannot set {name!r} on this event")
        slot, kind = field
        if kind == "float":
            self._h.set_argf(slot, float(value))
        elif kind == "vec":
            raise AttributeError(f"{name!r} (a position) is read-only")
        else:
            self._h.set_arg(slot, int(getattr(value, "address", value)) & 0xFFFFFFFF)

    def _field_names(self):
        names = list(self._fields)
        if self._subject:
            names.insert(0, self._subject)
        return names

    def __repr__(self) -> str:
        return f"GameEvent({', '.join(self._field_names())})"


# Registry: one hook per event, fanning out to many handlers.
_handlers: dict[str, list] = {}
_hook_ids: dict[str, int] = {}


def _make_dispatch(event_name: str, subject, resolved: dict, owner_class: str):
    def dispatch(raw: hooks.Hook):
        ev = GameEvent(raw, resolved, subject, owner_class)
        for fn in list(_handlers.get(event_name, ())):
            try:
                fn(ev)
            except Exception:
                _handlers[event_name].remove(fn)
                _pysa.log(f"[pysa] {event_name} handler {getattr(fn, '__name__', fn)!r} "
                          f"removed after error:\n{traceback.format_exc()}")
    return dispatch


def _register(event_name: str, fn):
    if event_name not in _EVENTS:
        raise ValueError(f"unknown game event {event_name!r}")
    _handlers.setdefault(event_name, []).append(fn)

    # Install the underlying hook once, on first handler.
    if event_name not in _hook_ids:
        func, subject, fields = _EVENTS[event_name]
        addr, conv, ret, cls, slots, catalog_fields = FUNCTIONS[func]
        by_name = {f[0]: (f[1], f[2]) for f in catalog_fields}  # arg -> (slot, is_float)
        resolved = {}
        for domain, (arg_name, kind) in fields.items():
            slot, _is_float = by_name[arg_name]
            resolved[domain] = (slot, kind)
        dispatch = _make_dispatch(event_name, subject, resolved, cls)
        _hook_ids[event_name] = hooks._install_raw(addr, dispatch, slots, conv)
    return fn


def _clear() -> None:
    for hid in _hook_ids.values():
        hooks.remove(hid)
    _hook_ids.clear()
    _handlers.clear()


def _checkpoint():
    """Internal import transaction marker used by the script loader."""
    return ({name: len(items) for name, items in _handlers.items()},
            set(_hook_ids))


def _rollback(checkpoint) -> None:
    """Remove handlers and owned hooks added during a failed import."""
    handler_lengths, hook_names = checkpoint
    for name in list(_handlers):
        keep = handler_lengths.get(name, 0)
        del _handlers[name][keep:]
        if not _handlers[name]:
            _handlers.pop(name, None)
    for name in set(_hook_ids) - hook_names:
        hooks.remove(_hook_ids.pop(name))


def _make_decorator(event_name: str):
    def decorator(fn):
        return _register(event_name, fn)
    decorator.__name__ = f"on_{event_name}"
    decorator.__doc__ = f"Run when: {event_name.replace('_', ' ')} " \
                        f"(hooks {_EVENTS[event_name][0]}). Handler gets an event " \
                        f"with fields: {', '.join(_EVENTS[event_name][2])}."
    return decorator


# Public decorators: on_vehicle_damage, on_explosion, ...
on_vehicle_damage = _make_decorator("vehicle_damage")
on_vehicle_explode = _make_decorator("vehicle_explode")
on_tyre_burst = _make_decorator("tyre_burst")
on_weapon_fire = _make_decorator("weapon_fire")
on_explosion = _make_decorator("explosion")
on_wanted_level_change = _make_decorator("wanted_level_change")
on_projectile_fired = _make_decorator("projectile_fired")
on_weapon_given = _make_decorator("weapon_given")


def events() -> list:
    """List the available game-event names."""
    return list(_EVENTS)
