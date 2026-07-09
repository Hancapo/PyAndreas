"""Background threads: PyAndreas releases the GIL between frames, so ordinary
Python threads keep running while you play.

This starts a worker that ticks on its own timer (imagine polling a file, a
socket, or doing slow computation) and the game just reads the latest result.

RULE: a background thread must NOT touch game state (commands, memory,
entities, drawing) - those are only safe on the game thread. Do your work in
the thread, stash the result, and read it from a handler like on_draw below.
"""
import threading

import pysa
from pysa import hud

_stop = threading.Event()
_state = {"beat": 0, "note": "starting..."}


def _worker():
    while not _stop.wait(1.0):        # wake every second, exit when stopped
        _state["beat"] += 1
        _state["note"] = f"worker alive for {_state['beat']}s"


_thread = threading.Thread(target=_worker, name="pysa-example-worker", daemon=True)
_thread.start()


@pysa.on_shutdown
def _stop_worker():
    # Fires on game exit and on F11 reload, so the thread doesn't pile up.
    _stop.set()


@pysa.on_draw
def show():
    w, h = hud.screen_size()
    hud.draw(_state["note"], 20, h - 40, size=0.7, color=(160, 200, 255))
