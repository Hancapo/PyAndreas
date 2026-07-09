"""Game-time timers. They use the game clock, so they pause when the game is
paused and scale with slow-motion - unlike time.time().

    from pysa import timers

    watch = timers.Stopwatch()
    ...
    print(watch.seconds)               # elapsed game seconds

    bomb = timers.Countdown(5000)      # 5 seconds
    @pysa.on_tick
    def tick():
        if bomb.finished:
            boom()
        hud.draw(f"{bomb.remaining/1000:.1f}s", 20, 20)
"""
from __future__ import annotations

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa


def now() -> int:
    """Current game time in milliseconds (pauses with the game)."""
    return _pysa.game_time()


class Stopwatch:
    """Measures elapsed game time. Starts running immediately."""

    __slots__ = ("_start", "_stopped_at")

    def __init__(self, running: bool = True):
        self._start = now()
        self._stopped_at = None if running else self._start

    def reset(self) -> None:
        self._start = now()
        if self._stopped_at is not None:
            self._stopped_at = self._start

    def stop(self) -> None:
        if self._stopped_at is None:
            self._stopped_at = now()

    def resume(self) -> None:
        if self._stopped_at is not None:
            self._start += now() - self._stopped_at
            self._stopped_at = None

    @property
    def running(self) -> bool:
        return self._stopped_at is None

    @property
    def elapsed(self) -> int:
        """Elapsed milliseconds."""
        end = now() if self._stopped_at is None else self._stopped_at
        return max(0, end - self._start)

    @property
    def seconds(self) -> float:
        return self.elapsed / 1000.0

    def __repr__(self) -> str:
        return f"Stopwatch({self.elapsed} ms{'' if self.running else ', stopped'})"


class Countdown:
    """Counts down from a duration in milliseconds."""

    __slots__ = ("_duration", "_end")

    def __init__(self, duration_ms: int):
        self._duration = int(duration_ms)
        self._end = now() + self._duration

    def reset(self, duration_ms: int = None) -> None:
        if duration_ms is not None:
            self._duration = int(duration_ms)
        self._end = now() + self._duration

    @property
    def remaining(self) -> int:
        """Milliseconds left (0 once finished)."""
        return max(0, self._end - now())

    @property
    def seconds(self) -> float:
        return self.remaining / 1000.0

    @property
    def finished(self) -> bool:
        return now() >= self._end

    @property
    def fraction(self) -> float:
        """Progress 0.0 (just started) .. 1.0 (finished) - good for bars."""
        if self._duration <= 0:
            return 1.0
        return 1.0 - self.remaining / self._duration

    def __repr__(self) -> str:
        return f"Countdown({self.remaining}/{self._duration} ms)"
