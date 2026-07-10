"""Automatic ownership for temporary scripted effects and mission scenes.

Use ``with ScriptSession()`` inside a ``@pysa.script`` coroutine. Anything
spawned or tracked by the session is cleaned up on normal exit, exceptions,
script cancellation, and F11 hot reload.
"""
from __future__ import annotations

import traceback

from . import camera


_active_sessions = set()


class SessionCamera:
    """Camera proxy that automatically restores gameplay camera on cleanup."""

    __slots__ = ("_session",)

    def __init__(self, session: "ScriptSession"):
        self._session = session

    def _claim(self) -> None:
        self._session._camera_used = True

    def fix_at(self, pos, look_at=None) -> None:
        self._claim()
        camera.fix_at(pos, look_at)

    def point_at(self, entity, mode=None) -> None:
        self._claim()
        if mode is None:
            camera.point_at(entity)
        else:
            camera.point_at(entity, mode)

    def behind_player(self) -> None:
        self._claim()
        camera.behind_player()

    def shake(self, intensity: int = 100) -> None:
        self._claim()
        camera.shake(intensity)

    def widescreen(self, enabled: bool = True) -> None:
        self._claim()
        camera.widescreen(enabled)
        if enabled:
            self._session.defer(camera.widescreen, False)

    def restore(self, instantly: bool = True) -> None:
        camera.restore(instantly)
        self._session._camera_used = False


class ScriptSession:
    """Own temporary resources and undo state overrides as one unit."""

    __slots__ = ("_cleanups", "_closed", "_entered", "_camera_used",
                 "camera")

    def __init__(self):
        self._cleanups = []
        self._closed = False
        self._entered = False
        self._camera_used = False
        self.camera = SessionCamera(self)

    def __enter__(self) -> "ScriptSession":
        if self._entered:
            raise RuntimeError("ScriptSession cannot be entered twice")
        self._entered = True
        _active_sessions.add(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.close()
        return False

    def defer(self, callback, *args, **kwargs):
        """Run ``callback`` during cleanup; callbacks run last-added first."""
        if self._closed:
            raise RuntimeError("cannot add cleanup to a closed ScriptSession")
        self._cleanups.append((callback, args, kwargs))
        return callback

    def track(self, resource, cleanup=None):
        """Adopt a resource and infer its normal cleanup method."""
        if cleanup is None:
            from .entities import Entity
            if isinstance(resource, Entity):
                cleanup = resource.delete
            else:
                for name in ("remove", "clear", "close", "delete", "stop"):
                    candidate = getattr(resource, name, None)
                    if callable(candidate):
                        cleanup = candidate
                        break
        if not callable(cleanup):
            raise TypeError("resource needs remove(), clear(), close(), delete(), "
                            "stop(), or an explicit cleanup callback")
        self.defer(cleanup)
        return resource

    def spawn_ped(self, model, pos, ped_type=None):
        from .entities import Ped
        if ped_type is None:
            return self.track(Ped.spawn(model, pos))
        return self.track(Ped.spawn(model, pos, ped_type))

    def spawn_vehicle(self, model, pos=None, heading=None):
        from .entities import Vehicle
        return self.track(Vehicle.spawn(model, pos, heading))

    def spawn_object(self, model: int, pos):
        from .entities import GameObject
        return self.track(GameObject.spawn(model, pos))

    def checkpoint(self, pos, **kwargs):
        from .markers import Checkpoint
        return self.track(Checkpoint(pos, **kwargs))

    def marker(self, pos, **kwargs):
        from .markers import Marker3D
        return self.track(Marker3D(pos, **kwargs))

    def sphere(self, center, radius: float = 10.0):
        from .markers import Sphere
        return self.track(Sphere(center, radius))

    def mission_audio(self, slot=None):
        from .audio import MissionAudio
        audio = MissionAudio() if slot is None else MissionAudio(slot)
        return self.track(audio)

    def disable_player_controls(self) -> None:
        """Disable all player input until this session closes."""
        from .player import player
        player.controls.enabled = False
        self.defer(setattr, player.controls, "enabled", True)

    def disable_vital_stats_button(self) -> None:
        from .player import player
        player.controls.vital_stats = False
        self.defer(setattr, player.controls, "vital_stats", True)

    def close(self) -> None:
        """Idempotently restore camera/state and release owned resources."""
        if self._closed:
            return
        self._closed = True
        _active_sessions.discard(self)

        if self._camera_used:
            try:
                camera.restore(instantly=False)
                camera.behind_player()
            except Exception:
                _log_cleanup_error("camera")
            self._camera_used = False

        while self._cleanups:
            callback, args, kwargs = self._cleanups.pop()
            try:
                callback(*args, **kwargs)
            except Exception:
                _log_cleanup_error(getattr(callback, "__name__", "resource"))


def _log_cleanup_error(name: str) -> None:
    try:
        from . import _runtime
        _runtime._pysa.log(
            f"[pysa] ScriptSession cleanup failed for {name}:\n"
            f"{traceback.format_exc()}")
    except Exception:
        pass


def _close_all() -> None:
    for session in tuple(_active_sessions):
        session.close()
