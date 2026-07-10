"""Small controller/keyboard menu widgets built on PyAndreas drawing.

    menu = ui.Menu("My Trainer", toggle_key=KEY.F5)
    menu.action("Heal", lambda: player.vitals.heal())
    menu.toggle_item("Never tired", lambda: player.perks.never_tired,
                     lambda value: setattr(player.perks, "never_tired", value))

Menus register their own lightweight tick/draw handlers by default. They are
removed automatically with the script that created them during hot reload.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, TypeVar, Union

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import _runtime, draw, hud, pad
from .keys import KEY
from .pad import BUTTON


TChoice = TypeVar("TChoice")
Enabled = Union[bool, Callable[[], bool]]


class MenuItem:
    """A selectable menu row."""

    __slots__ = ("label", "callback", "enabled", "value")

    def __init__(self, label: str, callback: Callable[[], Any],
                 enabled: Enabled = True, value: Any = None):
        self.label = str(label)
        self.callback = callback
        self.enabled = enabled
        self.value = value

    def is_enabled(self) -> bool:
        return bool(self.enabled() if callable(self.enabled) else self.enabled)

    def display_value(self) -> str:
        value = self.value() if callable(self.value) else self.value
        return "" if value is None else str(value)

    def activate(self) -> None:
        if self.is_enabled():
            self.callback()


class Menu:
    """A simple auto-updating action menu for ordinary mod settings."""

    __slots__ = ("title", "items", "selected", "visible", "toggle_key",
                 "toggle_button", "x", "y", "width", "row_height",
                 "_input_state")

    def __init__(self, title: str, *, toggle_key: Optional[int] = None,
                 toggle_button: Optional[BUTTON] = None,
                 x: float = 32.0, y: float = 72.0, width: float = 280.0,
                 row_height: float = 28.0, auto: bool = True):
        self.title = str(title)
        self.items = []
        self.selected = 0
        self.visible = False
        self.toggle_key = None if toggle_key is None else int(toggle_key)
        self.toggle_button = (None if toggle_button is None
                              else BUTTON(toggle_button))
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.row_height = float(row_height)
        self._input_state = {}
        if auto:
            _runtime.register("tick", self.update)
            _runtime.register("draw", self.draw)

    def action(self, label: str, callback: Callable[[], Any], *,
               enabled: Enabled = True) -> MenuItem:
        item = MenuItem(label, callback, enabled)
        self.items.append(item)
        return item

    def toggle_item(self, label: str, getter: Callable[[], bool],
                    setter: Callable[[bool], Any], *, enabled: Enabled = True,
                    on_text: str = "ON", off_text: str = "OFF") -> MenuItem:
        def activate():
            setter(not bool(getter()))

        def value():
            return on_text if getter() else off_text

        item = MenuItem(label, activate, enabled, value)
        self.items.append(item)
        return item

    def choice(self, label: str, values: Iterable[TChoice],
               getter: Callable[[], TChoice],
               setter: Callable[[TChoice], Any], *, enabled: Enabled = True,
               formatter: Callable[[TChoice], object] = str) -> MenuItem:
        choices = tuple(values)
        if not choices:
            raise ValueError("choice needs at least one value")

        def activate():
            current = getter()
            try:
                index = choices.index(current)
            except ValueError:
                index = -1
            setter(choices[(index + 1) % len(choices)])

        item = MenuItem(label, activate, enabled,
                        lambda: formatter(getter()))
        self.items.append(item)
        return item

    def open(self) -> None:
        self.visible = True
        self._ensure_selection()

    def close(self) -> None:
        self.visible = False

    def toggle(self) -> None:
        self.visible = not self.visible
        if self.visible:
            self._ensure_selection()

    def update(self) -> None:
        if self.toggle_key is not None and self._key_pressed(self.toggle_key):
            self.toggle()
        if (self.toggle_button is not None and
                self._button_pressed(self.toggle_button)):
            self.toggle()
        if not self.visible:
            return

        if (self._key_pressed(KEY.ESCAPE) or
                self._button_pressed(BUTTON.CIRCLE)):
            self.close()
            return
        if (self._key_pressed(KEY.UP) or
                self._button_pressed(BUTTON.DPAD_UP)):
            self.move(-1)
        if (self._key_pressed(KEY.DOWN) or
                self._button_pressed(BUTTON.DPAD_DOWN)):
            self.move(1)
        if (self._key_pressed(KEY.ENTER) or
                self._button_pressed(BUTTON.CROSS)):
            self.activate()

    def move(self, amount: int) -> None:
        if not self.items:
            return
        for _ in range(len(self.items)):
            self.selected = (self.selected + int(amount)) % len(self.items)
            if self.items[self.selected].is_enabled():
                break

    def activate(self) -> None:
        if self.items:
            self.items[self.selected].activate()

    def draw(self) -> None:
        if not self.visible:
            return
        height = self.row_height * (len(self.items) + 1) + 12.0
        draw.rect(self.x, self.y, self.width, height, (8, 12, 18, 220))
        draw.rect(self.x, self.y, self.width, self.row_height + 4.0,
                  (35, 105, 165, 240))
        hud.draw(self.title, self.x + 12.0, self.y + 6.0, size=0.75,
                 color=(255, 255, 255), align=hud.ALIGN.LEFT)

        for index, item in enumerate(self.items):
            top = self.y + self.row_height * (index + 1) + 6.0
            enabled = item.is_enabled()
            if index == self.selected:
                draw.rect(self.x + 4.0, top - 2.0, self.width - 8.0,
                          self.row_height, (70, 135, 190, 180))
            color = (245, 245, 245) if enabled else (125, 125, 125)
            hud.draw(item.label, self.x + 12.0, top + 3.0, size=0.62,
                     color=color, align=hud.ALIGN.LEFT)
            value = item.display_value()
            if value:
                hud.draw(value, self.x + self.width - 12.0, top + 3.0,
                         size=0.62, color=color, align=hud.ALIGN.RIGHT)

    def _ensure_selection(self) -> None:
        if self.items and not self.items[self.selected].is_enabled():
            self.move(1)

    def _edge(self, key: object, down: bool) -> bool:
        previous = self._input_state.get(key, False)
        self._input_state[key] = bool(down)
        return bool(down) and not previous

    def _key_pressed(self, key: int) -> bool:
        return self._edge(("key", int(key)), _pysa.key_down(int(key)))

    def _button_pressed(self, button: BUTTON) -> bool:
        return self._edge(("button", int(button)), pad.pressed(button))
