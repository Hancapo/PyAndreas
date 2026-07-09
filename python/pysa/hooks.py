"""Function hooking - run your code whenever the game calls one of its own
functions. This is how you change behaviour the script commands can't reach.

The friendly way is to name the function. Arguments arrive as named,
typed attributes, and `this` is the object the method belongs to:

    import pysa

    @pysa.on_call("CVehicle::InflictDamage")
    def softer_crashes(call):
        car = call.this                 # a Vehicle
        print(car.handle, "hit for", call.intensity)
        call.intensity = call.intensity * 0.5   # halve the damage
        # call.skip()                   # or cancel the damage entirely

Discover functions like commands:

    pysa.find_functions("damage")       # names + signatures
    help(pysa.on_call)                  # this text
    print(pysa.function_doc("CVehicle::InflictDamage"))

Inside the callback, `call` gives you:
    call.this                  the object the method is on (Ped/Vehicle/...)
    call.<argname>             read a named argument (floats/ints, entities
                               auto-wrapped); assign to rewrite it
    call.skip(value=0)         don't run the original; return `value` instead
    call.raw                   low-level access (registers, raw stack args)

Power users can still hook a raw address:

    @pysa.on_call(0x6D7C90, args=6, convention="thiscall")
    def raw(h):
        h.arg(0); h.set_argf(2, 0.0); h.reg("eax")

WARNINGS
- A hook runs on the game thread, inside that function. Keep it quick; a hook
  on a per-frame function with heavy Python will cost FPS.
- A hook that raises is removed automatically and logged, so it can't spam.
- Addresses target the 1.0 US exe. `skip()` cancels the original entirely -
  handy, but don't cancel a function the game depends on.
"""
from __future__ import annotations

import traceback

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from .functions import FUNCTIONS

_CONV = {"cdecl": 0, "stdcall": 1, "thiscall": 2}
_WRAP = {}  # filled lazily to avoid a circular import

# hook id -> (callback, argc, conv, spec_or_None)
_HOOKS: dict[int, tuple] = {}


def _wrapper(kind: str):
    if not _WRAP:
        from .entities import GameObject, Ped, Vehicle
        _WRAP.update(ped=Ped, vehicle=Vehicle, object=GameObject)
    return _WRAP.get(kind)


# ---------------------------------------------------------------------------
# Low-level hook context (raw addresses / escape hatch)
# ---------------------------------------------------------------------------

class Hook:
    """Raw access to a hooked call: stack arguments and CPU registers."""

    __slots__ = ("_ctx", "_argc", "_conv")

    def __init__(self, ctx: int, argc: int, conv: int):
        self._ctx = ctx
        self._argc = argc
        self._conv = conv

    def arg(self, i: int) -> int:
        return _pysa.hook_arg(self._ctx, i)

    def set_arg(self, i: int, value: int) -> None:
        _pysa.hook_set_arg(self._ctx, i, int(value) & 0xFFFFFFFF)

    def argf(self, i: int) -> float:
        return _pysa.hook_argf(self._ctx, i)

    def set_argf(self, i: int, value: float) -> None:
        _pysa.hook_set_argf(self._ctx, i, float(value))

    @property
    def this(self) -> int:
        return _pysa.hook_reg(self._ctx, "ecx")

    def reg(self, name: str) -> int:
        return _pysa.hook_reg(self._ctx, name)

    def set_reg(self, name: str, value: int) -> None:
        _pysa.hook_set_reg(self._ctx, name, int(value) & 0xFFFFFFFF)

    def skip(self, value: int = 0) -> None:
        """Skip the original function and return `value`."""
        _pysa.hook_block(self._ctx, int(value) & 0xFFFFFFFF, self._argc, self._conv)

    block = skip  # backwards-compatible alias


# ---------------------------------------------------------------------------
# Friendly call event (named functions)
# ---------------------------------------------------------------------------

class Call:
    """A named function call: `call.<argname>`, `call.this`, `call.skip()`."""

    __slots__ = ("_raw", "_fields", "_owner")

    def __init__(self, raw: Hook, fields: dict, owner_class: str, thiscall: bool):
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_fields", fields)      # name -> (slot, is_float, wrap)
        object.__setattr__(self, "_owner", owner_class if thiscall else None)

    @property
    def raw(self) -> Hook:
        """The low-level Hook (registers, raw stack, etc.)."""
        return self._raw

    @property
    def this(self):
        """The object this method belongs to (Ped/Vehicle/GameObject/pointer)."""
        if self._owner is None:
            raise AttributeError("this: not a method call (no 'this' pointer)")
        ptr = self._raw.this
        cls = {"CPed": "ped", "CPlayerPed": "ped", "CVehicle": "vehicle",
               "CAutomobile": "vehicle", "CObject": "object"}.get(self._owner)
        wrapper = _wrapper(cls) if cls else None
        return wrapper.from_ptr(ptr) if wrapper else ptr

    def skip(self, value: int = 0) -> None:
        """Don't run the original function; return `value` instead."""
        self._raw.skip(value)

    def __getattr__(self, name: str):
        field = self._fields.get(name)
        if field is None:
            raise AttributeError(
                f"no argument {name!r} here; this call has: "
                f"{', '.join(self._fields) or '(none)'}")
        slot, is_float, wrap = field
        if is_float:
            return self._raw.argf(slot)
        value = self._raw.arg(slot)
        wrapper = _wrapper(wrap) if wrap else None
        return wrapper.from_ptr(value) if wrapper else value

    def __setattr__(self, name: str, value) -> None:
        field = self._fields.get(name)
        if field is None:
            raise AttributeError(f"cannot set {name!r} - not an argument of this call")
        slot, is_float, _ = field
        if is_float:
            self._raw.set_argf(slot, float(value))
        else:
            self._raw.set_arg(slot, int(getattr(value, "address", value)) & 0xFFFFFFFF)

    def __repr__(self) -> str:
        return f"Call({', '.join(self._fields)})"


# ---------------------------------------------------------------------------
# Catalog lookup / discovery
# ---------------------------------------------------------------------------

def _resolve(name: str):
    entry = FUNCTIONS.get(name)
    if entry is not None:
        return name, entry
    low = name.lower()
    for key, entry in FUNCTIONS.items():
        if key.lower() == low:
            return key, entry
    raise ValueError(f"unknown function {name!r} "
                     f"(try pysa.find_functions({name.split('::')[-1].lower()!r}))")


def signature(name: str) -> str:
    """Readable signature: 'CVehicle::InflictDamage(damager, weapon, intensity, coords)'."""
    key, (_, conv, ret, cls, _, fields) = _resolve(name)
    args = ", ".join(f for f, *_ in fields)
    return f"{key}({args}) -> {ret}  [{conv}]"


def function_doc(name: str) -> str:
    key, (addr, conv, ret, cls, slots, fields) = _resolve(name)
    lines = [signature(name), f"address 0x{addr:06X}"]
    if fields:
        detail = ", ".join(f"{f}{'(float)' if fl else ''}{'->'+w if w else ''}"
                           for f, _, fl, w in fields)
        lines.append("args: " + detail)
    return "\n".join(lines)


def find_functions(pattern: str, limit: int = 40) -> list:
    """Search the function catalog by name; returns signature strings."""
    p = pattern.lower()
    hits = [k for k in FUNCTIONS if p in k.lower()]
    return [signature(k) for k in sorted(hits)[:limit]]


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

def _install_named(name: str, callback):
    key, (addr, conv, ret, cls, slots, fields) = _resolve(name)
    field_map = {f: (slot, is_float, wrap) for f, slot, is_float, wrap in fields}
    thiscall = (conv == "thiscall")

    def wrapped(h: Hook, _fm=field_map, _cls=cls, _tc=thiscall):
        return callback(Call(h, _fm, _cls, _tc))

    return _install_raw(addr, wrapped, slots, conv), key


def _install_raw(addr: int, callback, args: int, convention) -> int:
    conv = convention if isinstance(convention, int) else _CONV.get(convention)
    if conv is None:
        raise ValueError(f"convention must be one of {list(_CONV)}")
    hid = _pysa.hook_install(int(addr), int(args), conv)
    _HOOKS[hid] = (callback, int(args), conv)
    return hid


def install(target, callback, args: int = 0, convention: str = "cdecl") -> int:
    """Install a hook. `target` is a catalog name or a raw address."""
    if isinstance(target, str):
        hid, _ = _install_named(target, callback)
        return hid
    return _install_raw(target, callback, args, convention)


def remove(hid: int) -> None:
    _pysa.hook_remove(hid)
    _HOOKS.pop(hid, None)


def remove_all() -> None:
    for hid in list(_HOOKS):
        _pysa.hook_remove(hid)
    _HOOKS.clear()


def on_call(target, args: int = 0, convention: str = "cdecl"):
    """Decorator: run the function whenever the game calls `target`.

    `target` is a catalog name like "CVehicle::InflictDamage" (recommended:
    the callback gets a friendly `Call` with named arguments) or a raw code
    address (the callback gets a low-level `Hook`; pass args= and convention=).
    """
    def decorator(fn):
        if isinstance(target, str):
            _install_named(target, fn)
        else:
            _install_raw(target, fn, args, convention)
        return fn
    return decorator


#: Alias that reads nicely as a decorator: @pysa.hook("CPed::ClearWeapons")
hook = on_call


def _dispatch(hid: int, ctxaddr: int) -> None:
    """Called by the C++ hook trampoline (via _runtime._dispatch_hook)."""
    entry = _HOOKS.get(hid)
    if entry is None:
        return
    callback, argc, conv = entry
    try:
        callback(Hook(ctxaddr, argc, conv))
    except Exception:
        remove(hid)
        _pysa.log(f"[pysa] hook {hid} removed after error:\n{traceback.format_exc()}")
