"""PyAndreas runtime: event dispatch, script loading, hot reload.

The C++ plugin calls two entry points here:
    bootstrap(scripts_dir)  - once, after Python is initialized
    dispatch(event, arg)    - every frame / game event

User code never imports this module directly; it uses the decorators from
pysa.events.
"""
from __future__ import annotations

import importlib.util
import sys
import traceback

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

VERSION = "0.1.0"
RELOAD_KEY = 0x7A  # F11 - set to None (from a script) to disable hot reload


class Handler:
    """A registered callback with error containment.

    A handler that raises is disabled (not removed) and the traceback goes
    to PyAndreas.log - one bad script can't spam or kill the others.
    """

    __slots__ = ("fn", "name", "disabled", "extra")

    def __init__(self, fn, extra=None):
        self.fn = fn
        self.name = f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__name__', '?')}"
        self.disabled = False
        self.extra = extra or {}

    def run(self, *args) -> None:
        if self.disabled:
            return
        try:
            self.fn(*args)
        except Exception:
            self.disabled = True
            _pysa.log(f"[pysa] handler {self.name} disabled after error:\n"
                      f"{traceback.format_exc()}")
            try:
                _pysa.help_message(f"~r~Script error:~w~ {self.name} (see log)", True, False)
            except Exception:
                pass


# event name -> [Handler]; 'tick'/'draw'/'game_start'/'shutdown'/
# '{ped,vehicle,object}_{created,destroyed}'
_handlers: dict = {}
# tick handlers with an interval: [Handler(extra={'ms', 'next_at'})]
_interval_ticks: list = []
# key watchers: [Handler(extra={'vk', 'trigger', 'was_down'})]
_key_watchers: list = []
# cheat-word watchers: [Handler(extra={'word_reversed'})]
_cheat_watchers: list = []

_scripts: list = []       # [(module_name, file_path)]
_scripts_dir: str = ""
_reload_was_down = False

# coroutine tasks: generators resumed by the tick loop
_task_funcs: list = []    # @script-decorated generator functions (restarted on game_start)
_tasks: list = []         # live Task instances


class Task:
    """A running coroutine script. yield <ms> sleeps, bare yield waits a frame."""

    __slots__ = ("gen", "name", "resume_at", "done")

    def __init__(self, gen):
        self.gen = gen
        self.name = getattr(gen, "__name__", None) or getattr(
            getattr(gen, "gi_code", None), "co_name", "task")
        self.resume_at = 0
        self.done = False

    def cancel(self) -> None:
        self.done = True
        self.gen.close()

    def _step(self, now: int) -> None:
        if self.done or now < self.resume_at:
            return
        try:
            delay = next(self.gen)
        except StopIteration:
            self.done = True
        except Exception:
            self.done = True
            _pysa.log(f"[pysa] script task '{self.name}' crashed:\n"
                      f"{traceback.format_exc()}")
        else:
            if delay:
                self.resume_at = now + int(delay)


def start(gen_or_func) -> Task:
    """Start a coroutine now: pysa.start(my_generator_function)."""
    gen = gen_or_func() if callable(gen_or_func) else gen_or_func
    task = Task(gen)
    _tasks.append(task)
    return task


def script(fn):
    """Decorator: run `fn` as a coroutine on every game start / reload.

        @pysa.script
        def intro():
            yield 3000                 # wait 3s of game time
            hud.big_text("Welcome")
            while True:
                yield                  # wait one frame
    """
    _task_funcs.append(fn)
    return fn


def register(event: str, fn, **extra):
    """Used by the pysa.events decorators."""
    h = Handler(fn, extra)
    if event == "tick" and "ms" in extra:
        h.extra["next_at"] = 0
        _interval_ticks.append(h)
    elif event == "key":
        h.extra["was_down"] = False
        _key_watchers.append(h)
    elif event == "cheat":
        h.extra["word_reversed"] = extra["word"].upper()[::-1]
        _cheat_watchers.append(h)
    else:
        _handlers.setdefault(event, []).append(h)
    return fn


def _clear_registries() -> None:
    _handlers.clear()
    _interval_ticks.clear()
    _key_watchers.clear()
    _cheat_watchers.clear()
    for t in _tasks:
        t.cancel()
    _tasks.clear()
    _task_funcs.clear()
    try:
        from . import game_events
        game_events._clear()
    except Exception:
        pass
    try:
        from . import hooks
        hooks.remove_all()
    except Exception:
        pass


def _dispatch_hook(hid: int, ctxaddr: int) -> None:
    """Entry point the C++ hook trampoline calls (must never raise into C++)."""
    try:
        from . import hooks
        hooks._dispatch(hid, ctxaddr)
    except Exception:
        try:
            _pysa.log(f"[pysa] _dispatch_hook error:\n{traceback.format_exc()}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Script loading / hot reload
# ---------------------------------------------------------------------------

def _load_script(path) -> bool:
    name = "pysa_script_" + path.stem
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _scripts.append((name, str(path)))
        _pysa.log(f"[pysa] loaded {path.name}")
        return True
    except Exception:
        sys.modules.pop(name, None)
        _pysa.log(f"[pysa] FAILED to load {path.name}:\n{traceback.format_exc()}")
        try:
            _pysa.help_message(f"~r~{path.name} failed to load~w~ (see log)", True, False)
        except Exception:
            pass
        return False


def bootstrap(scripts_dir: str) -> int:
    """Called by the plugin once Python is up. Loads every script."""
    global _scripts_dir
    from pathlib import Path

    _scripts_dir = scripts_dir
    _pysa.log(f"[pysa] runtime {VERSION}, python {sys.version.split()[0]}, "
              f"scripts: {scripts_dir}")

    loaded = 0
    folder = Path(scripts_dir)
    if folder.is_dir():
        for path in sorted(folder.glob("*.py")):
            if not path.name.startswith("_"):
                loaded += _load_script(path)
    else:
        _pysa.log(f"[pysa] scripts folder missing: {scripts_dir}")
    _pysa.log(f"[pysa] {loaded} script(s) active")
    return loaded


def reload_scripts() -> None:
    """Drop every handler and re-import all scripts (F11 in-game)."""
    _pysa.log("[pysa] reloading scripts...")
    dispatch_simple("shutdown")
    _clear_registries()
    for name, _ in _scripts:
        sys.modules.pop(name, None)
    _scripts.clear()
    count = bootstrap(_scripts_dir)
    dispatch("game_start")
    try:
        _pysa.help_message(f"PyAndreas: reloaded {count} script(s)", True, False)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dispatch (called from C++)
# ---------------------------------------------------------------------------

def dispatch_simple(event: str) -> None:
    for h in _handlers.get(event, ()):  # copy not needed: handlers disable, not remove
        h.run()


def _tick() -> None:
    global _reload_was_down

    # hot reload key (edge-triggered)
    if RELOAD_KEY:
        down = _pysa.key_down(RELOAD_KEY)
        if down and not _reload_was_down:
            _reload_was_down = True
            reload_scripts()
            return
        _reload_was_down = down

    # key watchers
    for h in _key_watchers:
        down = _pysa.key_down(h.extra["vk"])
        trigger = h.extra["trigger"]
        was = h.extra["was_down"]
        h.extra["was_down"] = down
        if trigger == "pressed" and down and not was:
            h.run()
        elif trigger == "released" and was and not down:
            h.run()
        elif trigger == "down" and down:
            h.run()

    # cheat words (the game stores recently typed chars most-recent-first)
    if _cheat_watchers:
        buf = _pysa.cheat_buffer().upper()
        for h in _cheat_watchers:
            if buf.startswith(h.extra["word_reversed"]):
                _pysa.clear_cheat_buffer()
                h.run()

    now = _pysa.game_time()

    # interval ticks (game time: pauses when the game is paused)
    for h in _interval_ticks:
        if now >= h.extra["next_at"]:
            h.extra["next_at"] = now + h.extra["ms"]
            h.run()

    # coroutine tasks
    if _tasks:
        for t in _tasks:
            t._step(now)
        _tasks[:] = [t for t in _tasks if not t.done]

    dispatch_simple("tick")


def _wrap_entity(event: str, ptr: int):
    from .entities import GameObject, Ped, Vehicle

    if event.startswith("vehicle"):
        return Vehicle.from_ptr(ptr)
    if event.startswith("ped"):
        return Ped.from_ptr(ptr)
    return GameObject.from_ptr(ptr)


def _restart_script_tasks() -> None:
    for t in _tasks:
        t.cancel()
    _tasks.clear()
    for fn in _task_funcs:
        try:
            _tasks.append(Task(fn()))
        except Exception:
            _pysa.log(f"[pysa] could not start script task '{fn.__name__}':\n"
                      f"{traceback.format_exc()}")


def dispatch(event: str, arg=None) -> None:
    """Single entry point called by the C++ plugin."""
    try:
        if event == "tick":
            _tick()
        elif event == "draw":
            dispatch_simple("draw")
        elif event == "game_start":
            _restart_script_tasks()
            dispatch_simple("game_start")
        elif arg is not None and event in ("vehicle_created", "vehicle_destroyed",
                                           "ped_created", "ped_destroyed",
                                           "object_created", "object_destroyed"):
            if _handlers.get(event):
                entity = _wrap_entity(event, arg)
                for h in _handlers[event]:
                    h.run(entity)
        else:
            dispatch_simple(event)
    except Exception:
        # Last-ditch guard: never let an exception cross into C++.
        try:
            _pysa.log(f"[pysa] dispatch({event}) error:\n{traceback.format_exc()}")
        except Exception:
            pass
