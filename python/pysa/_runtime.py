"""PyAndreas runtime: event dispatch, script loading, hot reload.

The C++ plugin calls two entry points here:
    bootstrap(scripts_dir)  - once, after Python is initialized
    dispatch(event, arg)    - every frame / game event

User code never imports this module directly; it uses the decorators from
pysa.events.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import traceback
import threading
from concurrent.futures import Future
from queue import Empty, Queue

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

VERSION = "0.2.1"
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
# button watchers: [Handler(extra={'button', 'pad', 'trigger', 'was_down'})]
_button_watchers: list = []
# cheat-word watchers: [Handler(extra={'word_reversed'})]
_cheat_watchers: list = []
# Constructor hooks run before GTA assigns the final model. Created callbacks
# are released on a later tick once both the pool handle and model are usable.
_pending_entity_creations: dict = {}  # {(event, pointer): retry_count}
_CREATION_RETRY_FRAMES = 5

_scripts: list = []       # [(module_name, file_path)]
_script_modules: set = set()  # every module loaded from the scripts folder
_scripts_dir: str = ""
_reload_was_down = False
_reload_requested = False
_game_stdout_installed = False

# coroutine tasks: generators resumed by the tick loop
_task_funcs: list = []    # @script-decorated generator functions (restarted on game_start)
_tasks: list = []         # live Task instances

# Work posted by background threads and executed at the start of the next
# game tick. Only this queue may cross from worker threads into game APIs.
_main_thread_id = threading.get_ident()
_main_thread_queue = Queue()

_NATIVE_GATED_EVENTS = frozenset({
    "hud_draw", "radar_draw", "after_fade_draw", "menu_draw",
    "vehicle_render", "ped_render", "object_render",
})


def _sync_native_event(event: str) -> None:
    if event in _NATIVE_GATED_EVENTS:
        enabled = any(not handler.disabled for handler in _handlers.get(event, ()))
        _pysa.set_event_enabled(event, enabled)


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


def run_on_game_thread(fn, *args, **kwargs) -> Future:
    """Safely schedule callable ``fn`` on GTA's game thread.

    The returned standard-library Future receives the return value or raised
    exception. Calls made from the game thread execute immediately.
    """
    future = Future()
    if threading.get_ident() == _main_thread_id:
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
    else:
        _main_thread_queue.put((future, fn, args, kwargs))
    return future


call_soon = run_on_game_thread


def request_reload() -> None:
    """Reload all user scripts safely at the start of the next game tick."""
    global _reload_requested
    _reload_requested = True


class _GamePrintStream:
    """Mirror stdout to the log and queue complete lines as subtitles."""

    def __init__(self, log_stream):
        self.log_stream = log_stream
        self.buffer = ""
        self.encoding = getattr(log_stream, "encoding", "utf-8")
        self.errors = getattr(log_stream, "errors", "replace")

    def write(self, value) -> int:
        text = str(value)
        self.log_stream.write(text)
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                _print_messages.put(line)
        return len(text)

    def flush(self) -> None:
        self.log_stream.flush()

    def isatty(self) -> bool:
        return False

    def __getattr__(self, name):
        return getattr(self.log_stream, name)


_print_messages = Queue()


def _install_game_stdout() -> None:
    global _game_stdout_installed
    if (_game_stdout_installed or
            getattr(_pysa, "__name__", "") != "_pysa"):
        return
    sys.stdout = _GamePrintStream(sys.stdout)
    _game_stdout_installed = True


def _drain_print_messages() -> None:
    while True:
        try:
            message = _print_messages.get_nowait()
        except Empty:
            return
        try:
            _pysa.message(message, 3000, 0)
        except Exception:
            _pysa.log(f"[pysa] could not display print subtitle:\n"
                      f"{traceback.format_exc()}")


def _drain_main_thread_queue() -> None:
    while True:
        try:
            future, fn, args, kwargs = _main_thread_queue.get_nowait()
        except Empty:
            return
        if future.set_running_or_notify_cancel():
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as exc:
                future.set_exception(exc)


def _cancel_main_thread_queue() -> None:
    while True:
        try:
            future, _, _, _ = _main_thread_queue.get_nowait()
        except Empty:
            return
        future.cancel()


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
    elif event == "button":
        h.extra["was_down"] = False
        _button_watchers.append(h)
    elif event == "cheat":
        h.extra["word_reversed"] = extra["word"].upper()[::-1]
        _cheat_watchers.append(h)
    else:
        _handlers.setdefault(event, []).append(h)
        _sync_native_event(event)
    return fn


def _clear_registries() -> None:
    try:
        from . import session
        session._close_all()
    except Exception:
        pass
    _cancel_main_thread_queue()
    for event in _NATIVE_GATED_EVENTS:
        if _handlers.get(event):
            _pysa.set_event_enabled(event, False)
    _handlers.clear()
    _interval_ticks.clear()
    _key_watchers.clear()
    _button_watchers.clear()
    _cheat_watchers.clear()
    _pending_entity_creations.clear()
    for t in _tasks:
        try:
            t.cancel()
        except Exception:
            _pysa.log(f"[pysa] error while cancelling task '{t.name}':\n"
                      f"{traceback.format_exc()}")
    _tasks.clear()
    _task_funcs.clear()
    try:
        from . import game_events
        game_events._clear()
    except Exception:
        pass
    try:
        from . import state_events
        state_events._reset()
    except Exception:
        pass
    try:
        from . import testing
        testing._clear()
    except Exception:
        pass
    try:
        from . import console_commands
        console_commands._clear_user_commands()
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

def _is_script_module(module) -> bool:
    """Return whether a module's source lives below the active scripts folder."""
    filename = getattr(module, "__file__", None)
    if not filename or not _scripts_dir:
        return False
    try:
        folder = os.path.normcase(os.path.realpath(_scripts_dir))
        source = os.path.normcase(os.path.realpath(filename))
        return os.path.commonpath((folder, source)) == folder
    except (OSError, ValueError):
        return False


def _local_module_names() -> set:
    return {name for name, module in tuple(sys.modules.items())
            if module is not None and _is_script_module(module)}


def _registry_checkpoint():
    """Capture append-only registration state before importing one script."""
    from . import console_commands, game_events, hooks, testing

    return {
        "handlers": {name: len(items) for name, items in _handlers.items()},
        "interval_ticks": len(_interval_ticks),
        "key_watchers": len(_key_watchers),
        "button_watchers": len(_button_watchers),
        "cheat_watchers": len(_cheat_watchers),
        "task_funcs": len(_task_funcs),
        "tasks": len(_tasks),
        "hooks": hooks._checkpoint(),
        "game_events": game_events._checkpoint(),
        "testing": testing._checkpoint(),
        "console_commands": console_commands._checkpoint(),
    }


def _rollback_registries(checkpoint) -> None:
    """Remove decorators/hooks/tasks created by a failed script import."""
    from . import console_commands, game_events, hooks, testing

    for name in list(_handlers):
        keep = checkpoint["handlers"].get(name, 0)
        del _handlers[name][keep:]
        if not _handlers[name]:
            _handlers.pop(name, None)

    del _interval_ticks[checkpoint["interval_ticks"]:]
    del _key_watchers[checkpoint["key_watchers"]:]
    del _button_watchers[checkpoint["button_watchers"]:]
    del _cheat_watchers[checkpoint["cheat_watchers"]:]
    del _task_funcs[checkpoint["task_funcs"]:]

    for task in _tasks[checkpoint["tasks"]:]:
        try:
            task.cancel()
        except Exception:
            _pysa.log(f"[pysa] error while rolling back task '{task.name}':\n"
                      f"{traceback.format_exc()}")
    del _tasks[checkpoint["tasks"]:]

    # Game events own hooks, so let them release theirs before removing any
    # remaining low-level hooks installed directly by the script.
    game_events._rollback(checkpoint["game_events"])
    hooks._rollback(checkpoint["hooks"])
    testing._rollback(checkpoint["testing"])
    console_commands._rollback(checkpoint["console_commands"])
    for event in _NATIVE_GATED_EVENTS:
        _sync_native_event(event)


def _unload_script_modules() -> None:
    """Forget scripts and their local helper modules so F11 reimports both."""
    importlib.invalidate_caches()
    # A shutdown handler may import a local helper for the first time.
    _script_modules.update(_local_module_names())
    for name in sorted(_script_modules, key=lambda value: value.count("."),
                       reverse=True):
        sys.modules.pop(name, None)
    _script_modules.clear()

def _load_script(path) -> bool:
    name = "pysa_script_" + path.stem
    modules_before = set(sys.modules)
    checkpoint = _registry_checkpoint()
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _scripts.append((name, str(path)))
        _script_modules.update(_local_module_names())
        _pysa.log(f"[pysa] loaded {path.name}")
        return True
    except Exception:
        _rollback_registries(checkpoint)
        # Also discard helper modules first imported by the failed script.
        for module_name in set(sys.modules) - modules_before:
            module = sys.modules.get(module_name)
            if module_name == name or (module is not None and _is_script_module(module)):
                sys.modules.pop(module_name, None)
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
    _install_game_stdout()
    from . import dev_console
    dev_console._install_builtin(os.path.dirname(scripts_dir))
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
    _unload_script_modules()
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
    _sync_native_event(event)
    if event == "shutdown":
        try:
            from . import storage
            storage.flush_all()
        except Exception:
            _pysa.log(f"[pysa] storage flush failed:\n{traceback.format_exc()}")


def _tick() -> None:
    global _reload_requested, _reload_was_down

    _drain_main_thread_queue()
    _drain_print_messages()

    from . import dev_console
    dev_console._update_builtin()

    if _reload_requested:
        _reload_requested = False
        reload_scripts()
        return

    # hot reload key (edge-triggered)
    if RELOAD_KEY:
        down = _pysa.key_down(RELOAD_KEY)
        if down and not _reload_was_down:
            _reload_was_down = True
            reload_scripts()
            return
        _reload_was_down = down

    _flush_entity_creations()

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

    # controller button watchers (same edge logic, via the pad module)
    if _button_watchers:
        from . import pad as _pad
        for h in _button_watchers:
            down = _pad.pressed(h.extra["button"], h.extra["pad"])
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

    # Friendly state transitions are entirely dormant without subscribers.
    try:
        from . import state_events
        state_events._poll()
    except Exception:
        _pysa.log(f"[pysa] state event polling failed:\n{traceback.format_exc()}")

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


def _ready_entity(event: str, ptr: int):
    """Return a pool-backed entity with an initialized model, or ``None``."""
    try:
        entity = _wrap_entity(event, ptr)
        if entity.handle == -1 or entity.address != ptr:
            return None
        if _pysa.read_u16(ptr + 0x22) == 0xFFFF:
            return None
        return entity
    except (TypeError, ValueError):
        return None


def _queue_entity_creation(event: str, ptr: int) -> None:
    _pending_entity_creations.setdefault((event, int(ptr)), 0)


def _flush_entity_creations() -> None:
    """Deliver constructor events only after the entity is script-ready."""
    pending = tuple(_pending_entity_creations.items())
    _pending_entity_creations.clear()
    for (event, ptr), retries in pending:
        if not _handlers.get(event):
            continue
        entity = _ready_entity(event, ptr)
        if entity is None:
            if retries + 1 < _CREATION_RETRY_FRAMES:
                _pending_entity_creations[(event, ptr)] = retries + 1
            continue
        for handler in tuple(_handlers[event]):
            handler.run(entity)


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
        elif event == "developer_console_draw":
            from . import dev_console
            dev_console._draw_builtin()
        elif event == "frontend_open":
            from . import dev_console
            dev_console._suspend_builtin()
        elif event == "game_start":
            _restart_script_tasks()
            dispatch_simple("game_start")
        elif event == "developer_mode_changed":
            from . import dev_console
            dev_console._set_developer_mode(bool(arg))
        elif event in ("vehicle_model_changed", "ped_model_changed"):
            ptr, model = arg
            if _handlers.get(event):
                entity = _ready_entity(event, ptr)
                if entity is None:
                    return
                if event.startswith("vehicle"):
                    from .models import VEHICLE
                    enum_type = VEHICLE
                else:
                    from .ped_models import PED
                    enum_type = PED
                try:
                    model = enum_type(model)
                except ValueError:
                    model = int(model)  # custom model outside the stock enum
                for h in _handlers[event]:
                    h.run(entity, model)
        elif arg is not None and event in ("vehicle_created", "ped_created",
                                           "object_created"):
            if _handlers.get(event):
                _queue_entity_creation(event, arg)
        elif arg is not None and event in ("vehicle_destroyed", "ped_destroyed",
                                           "object_destroyed", "vehicle_render",
                                           "ped_render", "object_render"):
            if _handlers.get(event):
                entity = _ready_entity(event, arg)
                if entity is None:
                    return
                for h in _handlers[event]:
                    h.run(entity)
                _sync_native_event(event)
        else:
            dispatch_simple(event)
            if event == "shutdown":
                from . import dev_console
                dev_console._shutdown_builtin()
    except Exception:
        # Last-ditch guard: never let an exception cross into C++.
        try:
            _pysa.log(f"[pysa] dispatch({event}) error:\n{traceback.format_exc()}")
        except Exception:
            pass
