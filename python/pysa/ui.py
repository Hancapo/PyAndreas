"""Small controller/keyboard menu widgets built on PyAndreas drawing.

    menu = ui.Menu("My Trainer", toggle_key=KEY.F5)
    menu.action("Heal", lambda: player.vitals.heal())
    menu.toggle_item("Never tired", lambda: player.perks.never_tired,
                     lambda value: setattr(player.perks, "never_tired", value))

Menus register their own lightweight tick/draw handlers by default. They are
removed automatically with the script that created them during hot reload.
"""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class Theme:
    """Shared colors for PyAndreas' built-in UI controls."""

    surface: tuple[int, int, int, int] = (15, 18, 23, 244)
    control: tuple[int, int, int, int] = (24, 29, 35, 244)
    hover: tuple[int, int, int, int] = (29, 39, 40, 248)
    accent: tuple[int, int, int, int] = (52, 211, 153, 255)
    track: tuple[int, int, int, int] = (42, 49, 57, 245)
    text: tuple[int, int, int] = (235, 239, 243)
    muted: tuple[int, int, int] = (148, 163, 174)
    border: tuple[int, int, int, int] = (57, 66, 78, 255)


DARK_THEME = Theme()


@dataclass(frozen=True)
class Rect:
    """Rectangle shared by drawing and pointer hit-testing."""

    x: float
    y: float
    width: float
    height: float

    def contains(self, x: float, y: float) -> bool:
        return (self.x <= float(x) <= self.x + self.width and
                self.y <= float(y) <= self.y + self.height)


class Slider:
    """Value and interaction logic for a horizontal numeric slider.

    The widget is renderer-independent, so menus and developer tools can use
    the same clamping, stepping and mouse behavior.
    """

    __slots__ = ("minimum", "maximum", "step", "getter", "setter")

    def __init__(self, minimum: float, maximum: float, step: float,
                 getter: Callable[[], float],
                 setter: Callable[[float], Any]):
        if maximum <= minimum:
            raise ValueError("slider maximum must be greater than minimum")
        if step <= 0:
            raise ValueError("slider step must be positive")
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.step = float(step)
        self.getter = getter
        self.setter = setter

    @property
    def value(self) -> float:
        return max(self.minimum, min(self.maximum, float(self.getter())))

    @property
    def fraction(self) -> float:
        return (self.value - self.minimum) / (self.maximum - self.minimum)

    def set(self, value: float) -> float:
        value = max(self.minimum, min(self.maximum, float(value)))
        steps = round((value - self.minimum) / self.step)
        value = self.minimum + steps * self.step
        value = max(self.minimum, min(self.maximum, value))
        # Avoid exposing floating-point noise in settings and scripts.
        precision = max(0, len(f"{self.step:.10f}".rstrip("0").split(".")[-1]))
        value = round(value, precision)
        self.setter(value)
        return value

    def change(self, steps: int) -> float:
        return self.set(self.value + int(steps) * self.step)

    def set_from_pointer(self, x: float, track: Rect) -> float:
        fraction = ((float(x) - track.x) / max(1.0, track.width))
        return self.set(self.minimum + max(0.0, min(1.0, fraction)) *
                        (self.maximum - self.minimum))


def draw_button(bounds: Rect, label: str, *, hovered: bool = False,
                active: bool = False, pixels: float = 13.0,
                theme: Theme = DARK_THEME) -> None:
    """Draw a standard monospace PyAndreas button."""
    draw.rect(bounds.x, bounds.y, bounds.width, bounds.height,
              theme.hover if hovered or active else theme.control)
    text_width = hud.mono_text_width(str(label), pixels)
    hud.draw_mono(str(label), bounds.x + (bounds.width - text_width) * 0.5,
                  bounds.y + (bounds.height - pixels) * 0.42, pixels,
                  theme.text if hovered or active else theme.muted)


def draw_slider(bounds: Rect, fraction: float, *, hovered: bool = False,
                theme: Theme = DARK_THEME) -> None:
    """Draw the standard PyAndreas slider track, fill and thumb."""
    fraction = max(0.0, min(1.0, float(fraction)))
    track_height = max(4.0, bounds.height * 0.22)
    track_y = bounds.y + (bounds.height - track_height) * 0.5
    draw.bar(bounds.x, track_y, bounds.width, track_height, fraction,
             fg=theme.accent, bg=theme.track)
    thumb = max(10.0, bounds.height * 0.55)
    thumb_x = bounds.x + fraction * bounds.width
    draw.rect(thumb_x - thumb * 0.5, bounds.y + (bounds.height - thumb) * 0.5,
              thumb, thumb, theme.text if hovered else theme.accent)


def draw_toggle(bounds: Rect, enabled: bool, *, hovered: bool = False,
                pixels: float = 13.0, theme: Theme = DARK_THEME) -> None:
    """Draw a toggle using the same surface, accent and text rules."""
    draw_button(bounds, "ON" if enabled else "OFF", hovered=hovered,
                active=enabled, pixels=pixels, theme=theme)


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


# The retained document engine is kept separate so this compact legacy menu
# remains easy to maintain.  Re-export its public surface through ``pysa.ui``
# for a single, friendly scripting namespace.
from .ui_document import (Anchor, Binding, Button, Choice, Column, Element,
                          ElementStyle, Image, MarkupError, Page, Row, Scroll,
                          Separator, SliderItem, Spacer, Text, Toggle, UIError,
                          View, bind, load, read)


__all__ = [
    "Anchor", "Binding", "Button", "Choice", "Column", "DARK_THEME",
    "Element", "ElementStyle", "Image", "MarkupError", "Menu", "MenuItem",
    "Page", "Rect", "Row", "Scroll", "Separator", "Slider", "SliderItem",
    "Spacer", "Text", "Theme", "Toggle", "UIError", "View", "bind",
    "draw_button", "draw_slider", "draw_toggle", "load", "read",
]
