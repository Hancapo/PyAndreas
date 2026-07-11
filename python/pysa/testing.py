"""Small in-game test registry for smoke-testing scripts and API behavior.

Tests are opt-in and run on GTA's game thread. A test may be an ordinary
function or a generator that yields game milliseconds, just like
``@pysa.script`` coroutines.
"""
from __future__ import annotations

import inspect
import traceback
from typing import Any, Callable, Generator, Iterable, Optional, Union, overload

from . import _runtime


TestFunction = Callable[[], Any]
OutputFunction = Callable[[str], Any]
_tests: dict[str, TestFunction] = {}


class TestRun:
    """Live status for a group of in-game tests."""

    __slots__ = ("names", "passed", "failed", "failures", "running", "task",
                 "_output")

    def __init__(self, names: Iterable[str], output: OutputFunction):
        self.names = tuple(names)
        self.passed = 0
        self.failed = 0
        self.failures: list[tuple[str, str]] = []
        self.running = True
        self.task: Optional[_runtime.Task] = None
        self._output = output

    @property
    def total(self) -> int:
        return len(self.names)

    @property
    def finished(self) -> bool:
        return not self.running

    @property
    def successful(self) -> bool:
        return self.finished and self.failed == 0

    def _execute(self) -> Generator[Optional[int], None, None]:
        if not self.names:
            self._output("[TEST] No matching tests")
            self.running = False
            return

        self._output(f"[TEST] Running {self.total} test(s)")
        for name in self.names:
            self._output(f"[RUN ] {name}")
            try:
                result = _tests[name]()
                if inspect.isgenerator(result):
                    yield from result
                elif result is False:
                    raise AssertionError("test returned False")
            except Exception as exc:
                self.failed += 1
                detail = "".join(traceback.format_exception_only(
                    type(exc), exc)).strip()
                self.failures.append((name, detail))
                self._output(f"[FAIL] {name}: {detail}")
                _runtime._pysa.log(
                    f"[pysa:test] {name} failed:\n{traceback.format_exc()}")
            else:
                self.passed += 1
                self._output(f"[PASS] {name}")
            yield

        self.running = False
        self._output(
            f"[TEST] {self.passed} passed, {self.failed} failed")


@overload
def dev_test(fn: TestFunction, /) -> TestFunction: ...


@overload
def dev_test(name: str) -> Callable[[TestFunction], TestFunction]: ...


def dev_test(arg: Union[TestFunction, str]) -> Union[
        TestFunction, Callable[[TestFunction], TestFunction]]:
    """Register an in-game smoke test.

    Use ``@pysa.dev_test`` or ``@pysa.dev_test("readable name")``.
    """
    if callable(arg):
        _register(arg.__name__, arg)
        return arg

    name = str(arg)

    def decorator(fn: TestFunction) -> TestFunction:
        _register(name, fn)
        return fn

    return decorator


def _register(name: str, fn: TestFunction) -> None:
    if not name.strip():
        raise ValueError("test name cannot be empty")
    if name in _tests and _tests[name] is not fn:
        raise ValueError(f"a test named {name!r} is already registered")
    _tests[name] = fn


def test_names(pattern: Optional[str] = None) -> list[str]:
    """Registered test names, optionally filtered by a substring."""
    names = sorted(_tests)
    if pattern:
        needle = pattern.casefold()
        names = [name for name in names if needle in name.casefold()]
    return names


def run_tests(pattern: Optional[str] = None,
              output: Optional[OutputFunction] = None) -> TestRun:
    """Start matching tests and return their live :class:`TestRun`."""
    sink = output or _runtime._pysa.log
    run = TestRun(test_names(pattern), sink)
    run.task = _runtime.start(run._execute())
    return run


def _clear() -> None:
    _tests.clear()


def _checkpoint() -> dict[str, TestFunction]:
    return dict(_tests)


def _rollback(checkpoint: dict[str, TestFunction]) -> None:
    _tests.clear()
    _tests.update(checkpoint)
