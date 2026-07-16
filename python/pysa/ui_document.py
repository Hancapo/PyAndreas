"""Declarative retained UI documents for ordinary PyAndreas scripts.

This module deliberately implements a small menu document format, not HTML or
XAML.  Presentation lives in a Python element tree or a ``.pui`` XML file;
behavior stays in named Python callbacks and explicit state bindings.
"""
from __future__ import annotations

import inspect
import math
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (Any, Callable, Generic, Iterable, Mapping, Optional,
                    Sequence, TypeVar, Union)

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import _runtime, draw, hud, pad
from .keys import KEY
from .pad import BUTTON
from .ui import DARK_THEME, Rect, Slider, Theme


T = TypeVar("T")
Dynamic = Union[T, Callable[[], T], "Binding[T]"]
_BINDING = re.compile(r"^\{([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\}$")
_ACTION = re.compile(r"^[A-Za-z_]\w*$")
_COMMON_ATTRIBUTES = {"visible", "enabled", "height", "style"}
_ELEMENT_ATTRIBUTES = {
    "text": {"text", "value"},
    "button": {"text", "value", "on-click"},
    "toggle": {"text", "value", "on-text", "off-text"},
    "slider": {"text", "value", "min", "max", "step", "format"},
    "choice": {"text", "value", "options"},
    "page": {"text", "value"},
    "column": {"gap", "padding"},
    "row": {"gap", "padding"},
    "scroll": {"gap", "padding"},
    "separator": set(),
    "spacer": set(),
    "image": {"sprite"},
}
_ROOT_ATTRIBUTES = {
    "title", "toggle-key", "toggle-button", "x", "y", "width",
    "max-height", "anchor", "scale", "theme", "padding", "gap",
    "text-size", "capture-input",
}


class UIError(RuntimeError):
    """Base error raised by the declarative UI layer."""


class MarkupError(UIError):
    """A malformed or unresolved ``.pui`` document."""


class Binding(Generic[T]):
    """A readable, optionally writable value used by UI controls."""

    __slots__ = ("_getter", "_setter", "path")

    def __init__(self, getter: Callable[[], T],
                 setter: Optional[Callable[[T], Any]] = None,
                 *, path: str = ""):
        if not callable(getter):
            raise TypeError("binding getter must be callable")
        if setter is not None and not callable(setter):
            raise TypeError("binding setter must be callable")
        self._getter = getter
        self._setter = setter
        self.path = str(path)

    @property
    def writable(self) -> bool:
        return self._setter is not None

    @property
    def value(self) -> T:
        return self._getter()

    @value.setter
    def value(self, value: T) -> None:
        if self._setter is None:
            suffix = f" {self.path!r}" if self.path else ""
            raise AttributeError(f"binding{suffix} is read-only")
        self._setter(value)

    def get(self) -> T:
        return self.value

    def set(self, value: T) -> T:
        self.value = value
        return value


def _get_member(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _set_member(value: Any, name: str, new_value: Any) -> None:
    if isinstance(value, dict):
        value[name] = new_value
    else:
        setattr(value, name, new_value)


def bind(target: Any, attribute: str) -> Binding[Any]:
    """Bind a control to an object attribute or mapping path.

    ``target`` may be a callable returning the current object, which is useful
    for state such as ``lambda: player.vehicle`` that can change over time.
    """
    parts = tuple(part for part in str(attribute).split(".") if part)
    if not parts:
        raise ValueError("binding attribute cannot be empty")

    def root() -> Any:
        return target() if callable(target) else target

    def parent_and_name() -> tuple[Any, str]:
        current = root()
        for part in parts[:-1]:
            current = _get_member(current, part)
        return current, parts[-1]

    def getter() -> Any:
        parent, name = parent_and_name()
        return _get_member(parent, name)

    def setter(value: Any) -> None:
        parent, name = parent_and_name()
        _set_member(parent, name, value)

    writable_setter: Optional[Callable[[Any], None]] = setter
    if not callable(target):
        try:
            parent, name = parent_and_name()
            descriptor = inspect.getattr_static(parent, name)
            if isinstance(descriptor, property) and descriptor.fset is None:
                writable_setter = None
        except (AttributeError, KeyError, TypeError):
            pass
    return Binding(getter, writable_setter, path=".".join(parts))


def read(getter: Callable[[], T], *, name: str = "") -> Binding[T]:
    """Create an explicitly read-only binding."""
    return Binding(getter, path=name)


def _value(value: Dynamic[T]) -> T:
    if isinstance(value, Binding):
        return value.get()
    return value() if callable(value) else value


def _capture_menu_input(enabled: bool) -> None:
    capture = getattr(_pysa, "capture_menu_input", _pysa.capture_input)
    capture(bool(enabled))


def _set_menu_pointer_consumed(consumed: bool) -> None:
    setter = getattr(_pysa, "set_menu_pointer_consumed", None)
    if setter is not None:
        setter(bool(consumed))


@dataclass(frozen=True)
class ElementStyle:
    """Optional local overrides selected by an element's ``style`` name."""

    background: Optional[tuple[int, int, int, int]] = None
    text: Optional[tuple[int, int, int]] = None
    muted: Optional[tuple[int, int, int]] = None
    height: Optional[float] = None
    pixels: Optional[float] = None
    padding: Optional[float] = None


class Anchor(str, Enum):
    TOP_LEFT = "top-left"
    TOP_CENTER = "top-center"
    TOP_RIGHT = "top-right"
    CENTER = "center"
    BOTTOM_LEFT = "bottom-left"
    BOTTOM_CENTER = "bottom-center"
    BOTTOM_RIGHT = "bottom-right"


class Element:
    """Base class for controls and layout containers."""

    focusable = False
    default_height = 30.0

    def __init__(self, *, visible: Dynamic[bool] = True,
                 enabled: Dynamic[bool] = True,
                 height: Optional[float] = None, style: str = ""):
        self.visible = visible
        self.enabled = enabled
        self.height = None if height is None else float(height)
        self.style = str(style)
        self.bounds: Optional[Rect] = None

    def is_visible(self) -> bool:
        return bool(_value(self.visible))

    def is_enabled(self) -> bool:
        return bool(_value(self.enabled))

    def preferred_height(self, view: "View") -> float:
        style = view.style_for(self)
        if self.height is not None:
            return self.height * view.scale
        if style.height is not None:
            return style.height * view.scale
        return self.default_height * view.scale

    def activate(self, view: "View") -> None:
        pass

    def adjust(self, view: "View", amount: int) -> None:
        if amount:
            self.activate(view)

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        pass


class Container(Element):
    def __init__(self, *children: Element, gap: float = 6.0,
                 padding: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.children = list(children)
        self.gap = float(gap)
        self.padding = float(padding)

    def add(self, *children: Element) -> "Container":
        self.children.extend(children)
        return self


class Column(Container):
    """Lay out child elements vertically."""


class Row(Container):
    """Lay out child elements horizontally with equal-width cells."""


class Scroll(Column):
    """A vertical group; scrolling is owned by the containing :class:`View`."""


class Text(Element):
    default_height = 28.0

    def __init__(self, value: Dynamic[Any], **kwargs):
        super().__init__(**kwargs)
        self.value = value

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        style = view.style_for(self)
        pixels = (style.pixels or view.text_pixels) * view.scale
        color = style.text or view.theme.text
        hud.draw_mono(str(_value(self.value)), bounds.x, bounds.y + 3 * view.scale,
                      pixels, color, clip=_clip_tuple(clip))


class Button(Element):
    focusable = True
    default_height = 40.0

    def __init__(self, text: Dynamic[Any], on_click: Callable[[], Any],
                 **kwargs):
        if not callable(on_click):
            raise TypeError("button on_click must be callable")
        super().__init__(**kwargs)
        self.text = text
        self.on_click = on_click

    def activate(self, view: "View") -> None:
        if self.is_enabled():
            self.on_click()

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        view.draw_control(bounds, str(_value(self.text)), "",
                          self.is_enabled(), selected, hovered, clip, self)


class Toggle(Element):
    focusable = True
    default_height = 40.0

    def __init__(self, text: Dynamic[Any], value: Binding[Any], *,
                 on_text: str = "ON", off_text: str = "OFF", **kwargs):
        if not isinstance(value, Binding):
            raise TypeError("toggle value must be a ui.Binding")
        if not value.writable:
            raise TypeError("toggle value binding must be writable")
        super().__init__(**kwargs)
        self.text = text
        self.value = value
        self.on_text = str(on_text)
        self.off_text = str(off_text)

    def activate(self, view: "View") -> None:
        if self.is_enabled():
            self.value.set(not bool(self.value.get()))

    def adjust(self, view: "View", amount: int) -> None:
        if self.is_enabled() and amount:
            self.value.set(amount > 0)

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        enabled = self.is_enabled()
        active = bool(self.value.get())
        label = str(_value(self.text))
        view.draw_control(bounds, label, "", enabled,
                          selected, hovered, clip, self)
        style = view.style_for(self)
        pixels = (style.pixels or view.text_pixels) * view.scale
        padding = (style.padding or 12.0) * view.scale
        switch_width = 38.0 * view.scale
        switch_height = 20.0 * view.scale
        switch = Rect(bounds.x + bounds.width - padding - switch_width,
                      bounds.y + (bounds.height - switch_height) * 0.5,
                      switch_width, switch_height)
        switch_color = view.theme.accent if active else view.theme.track
        _surface(switch, switch_color, view.theme.border, clip,
                 7.0 * view.scale)
        thumb = 14.0 * view.scale
        thumb_x = (switch.x + switch.width - thumb - 3.0 * view.scale
                   if active else switch.x + 3.0 * view.scale)
        thumb_bounds = Rect(thumb_x, switch.y + (switch.height - thumb) * 0.5,
                            thumb, thumb)
        _rounded_fill(thumb_bounds,
                      view.theme.text if enabled else view.theme.muted,
                      clip, 5.0 * view.scale)
        state_text = self.on_text if active else self.off_text
        state_width = hud.mono_text_width(state_text, pixels * 0.82)
        state_x = switch.x - 8.0 * view.scale - state_width
        label_width = hud.mono_text_width(label, pixels)
        if state_x > bounds.x + padding + label_width + 10.0 * view.scale:
            hud.draw_mono(state_text, state_x,
                          bounds.y + (bounds.height - pixels * 0.82) * 0.42,
                          pixels * 0.82,
                          view.theme.accent if active else view.theme.muted,
                          clip=_clip_tuple(clip))


class Choice(Element):
    focusable = True
    default_height = 40.0

    def __init__(self, text: Dynamic[Any], values: Dynamic[Iterable[Any]],
                 value: Binding[Any], *,
                 formatter: Callable[[Any], object] = str, **kwargs):
        if not isinstance(value, Binding):
            raise TypeError("choice value must be a ui.Binding")
        if not value.writable:
            raise TypeError("choice value binding must be writable")
        if not callable(formatter):
            raise TypeError("choice formatter must be callable")
        super().__init__(**kwargs)
        self.text = text
        self.values = values
        self.value = value
        self.formatter = formatter

    def _choices(self) -> tuple[Any, ...]:
        choices = tuple(_value(self.values))
        if not choices:
            raise ValueError("choice needs at least one value")
        return choices

    def adjust(self, view: "View", amount: int) -> None:
        if not self.is_enabled() or not amount:
            return
        choices = self._choices()
        current = self.value.get()
        try:
            index = choices.index(current)
        except ValueError:
            index = -1 if amount > 0 else 0
        self.value.set(choices[(index + amount) % len(choices)])

    def activate(self, view: "View") -> None:
        self.adjust(view, 1)

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        current = self.value.get()
        view.draw_control(bounds, str(_value(self.text)),
                          str(self.formatter(current)), self.is_enabled(),
                          selected, hovered, clip, self)


class SliderItem(Element):
    """A labelled slider control for Python views and ``<Slider>`` markup."""

    focusable = True
    default_height = 54.0

    def __init__(self, text: Dynamic[Any], minimum: float, maximum: float,
                 step: float, value: Binding[Any], *, value_format: str = "g",
                 **kwargs):
        if not isinstance(value, Binding):
            raise TypeError("slider value must be a ui.Binding")
        if not value.writable:
            raise TypeError("slider value binding must be writable")
        super().__init__(**kwargs)
        self.text = text
        self.value = value
        self.value_format = str(value_format)
        self.slider = Slider(minimum, maximum, step, value.get, value.set)
        self.track_bounds: Optional[Rect] = None

    def adjust(self, view: "View", amount: int) -> None:
        if self.is_enabled() and amount:
            self.slider.change(amount)

    def activate(self, view: "View") -> None:
        pass

    def set_from_pointer(self, x: float) -> None:
        if self.track_bounds is not None and self.is_enabled():
            self.slider.set_from_pointer(x, self.track_bounds)

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        style = view.style_for(self)
        view.draw_control_surface(bounds, selected, hovered, clip, self)
        pixels = (style.pixels or view.text_pixels) * view.scale
        color = ((style.text or view.theme.text) if self.is_enabled()
                 else (style.muted or view.theme.muted))
        padding = (style.padding or 12.0) * view.scale
        label_y = bounds.y + 6.0 * view.scale
        hud.draw_mono(str(_value(self.text)), bounds.x + padding, label_y,
                      pixels, color, clip=_clip_tuple(clip))
        value_text = format(self.slider.value, self.value_format)
        value_width = hud.mono_text_width(value_text, pixels)
        hud.draw_mono(value_text, bounds.x + bounds.width - padding - value_width,
                      label_y, pixels, color, clip=_clip_tuple(clip))
        self.track_bounds = Rect(bounds.x + padding,
                                 bounds.y + bounds.height - 17.0 * view.scale,
                                 max(1.0, bounds.width - padding * 2),
                                 12.0 * view.scale)
        _draw_slider_clipped(self.track_bounds, self.slider.fraction,
                             selected or hovered, view.theme, clip)


class Page(Element):
    focusable = True
    default_height = 40.0

    def __init__(self, text: Dynamic[Any], *children: Element, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.children = list(children)

    def add(self, *children: Element) -> "Page":
        self.children.extend(children)
        return self

    def activate(self, view: "View") -> None:
        if self.is_enabled():
            view.open_page(self)

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        view.draw_control(bounds, str(_value(self.text)), ">",
                          self.is_enabled(), selected, hovered, clip, self)


class Separator(Element):
    default_height = 12.0

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        line = Rect(bounds.x, bounds.y + bounds.height * 0.5,
                    bounds.width, max(1.0, view.scale))
        _fill(line, view.theme.border, clip)


class Spacer(Element):
    default_height = 12.0


class Image(Element):
    default_height = 96.0

    def __init__(self, sprite: Dynamic[str], *, tint=(255, 255, 255, 255),
                 **kwargs):
        super().__init__(**kwargs)
        self.sprite = sprite
        self.tint = tint

    def draw(self, view: "View", bounds: Rect, selected: bool,
             hovered: bool, clip: Rect) -> None:
        clipped = _intersection(bounds, clip)
        if clipped is not None:
            draw.sprite(str(_value(self.sprite)), clipped.x, clipped.y,
                        clipped.width, clipped.height, self.tint)


def _intersection(a: Rect, b: Rect) -> Optional[Rect]:
    left, top = max(a.x, b.x), max(a.y, b.y)
    right = min(a.x + a.width, b.x + b.width)
    bottom = min(a.y + a.height, b.y + b.height)
    if right <= left or bottom <= top:
        return None
    return Rect(left, top, right - left, bottom - top)


def _fill(bounds: Rect, color, clip: Rect) -> None:
    clipped = _intersection(bounds, clip)
    if clipped is not None:
        draw.rect(clipped.x, clipped.y, clipped.width, clipped.height, color)


def _rounded_fill(bounds: Rect, color, clip: Rect, radius: float = 4.0) -> None:
    """Draw rounded corners as grouped horizontal scanline bands."""
    radius = max(0.0, min(float(radius), bounds.width * 0.25,
                          bounds.height * 0.25))
    if radius < 1.0:
        _fill(bounds, color, clip)
        return
    rows = max(1, int(math.ceil(radius)))
    offsets = []
    for row in range(rows):
        distance = radius - min(radius, row + 0.5)
        inset = radius - math.sqrt(max(0.0, radius * radius -
                                       distance * distance))
        offsets.append(max(0, int(round(inset))))

    band_start = 0
    while band_start < rows:
        inset = offsets[band_start]
        band_end = band_start + 1
        while band_end < rows and offsets[band_end] == inset:
            band_end += 1
        band_height = float(band_end - band_start)
        width = max(0.0, bounds.width - inset * 2.0)
        _fill(Rect(bounds.x + inset, bounds.y + band_start,
                   width, band_height), color, clip)
        _fill(Rect(bounds.x + inset,
                   bounds.y + bounds.height - band_end,
                   width, band_height), color, clip)
        band_start = band_end

    middle_height = max(0.0, bounds.height - rows * 2.0)
    if middle_height > 0.0:
        _fill(Rect(bounds.x, bounds.y + rows,
                   bounds.width, middle_height), color, clip)


def _surface(bounds: Rect, background, border, clip: Rect,
             radius: float = 4.0, border_width: float = 1.0) -> None:
    """Draw a bordered surface with one consistent corner treatment."""
    _rounded_fill(bounds, border, clip, radius)
    inset = max(1.0, float(border_width))
    inner = Rect(bounds.x + inset, bounds.y + inset,
                 max(0.0, bounds.width - inset * 2),
                 max(0.0, bounds.height - inset * 2))
    _rounded_fill(inner, background, clip, max(0.0, radius - inset))


def _clip_tuple(bounds: Rect) -> tuple[float, float, float, float]:
    return (bounds.x, bounds.y, bounds.x + bounds.width,
            bounds.y + bounds.height)


def _draw_slider_clipped(bounds: Rect, fraction: float, hovered: bool,
                         theme: Theme, clip: Rect) -> None:
    fraction = max(0.0, min(1.0, float(fraction)))
    track_height = max(3.0, bounds.height * 0.28)
    track = Rect(bounds.x, bounds.y + (bounds.height - track_height) * 0.5,
                 bounds.width, track_height)
    _rounded_fill(track, theme.track, clip, track.height * 0.5)
    if fraction > 0.0:
        _rounded_fill(Rect(track.x, track.y,
                           max(track.height, track.width * fraction),
                           track.height), theme.accent, clip,
                      track.height * 0.5)
    thumb = max(10.0, bounds.height)
    thumb_x = bounds.x + bounds.width * fraction
    thumb_bounds = Rect(thumb_x - thumb * 0.5,
                        bounds.y + (bounds.height - thumb) * 0.5,
                        thumb, thumb)
    _surface(thumb_bounds, theme.text if hovered else theme.accent,
             theme.surface, clip, thumb * 0.35)


@dataclass
class _Hit:
    element: Element
    bounds: Rect


class View:
    """A retained, themed menu view created from Python or a ``.pui`` file."""

    def __init__(self, title: str, *children: Element,
                 toggle_key: Optional[int] = None,
                 toggle_button: Optional[BUTTON] = None,
                 x: float = 32.0, y: float = 48.0, width: float = 380.0,
                 max_height: float = 520.0, anchor: Anchor = Anchor.TOP_LEFT,
                 scale: float = 1.0, theme: Theme = DARK_THEME,
                 styles: Optional[Mapping[str, ElementStyle]] = None,
                 padding: float = 14.0, gap: float = 8.0,
                 text_pixels: float = 15.0, capture_input: bool = True,
                 auto: bool = True):
        self.title = str(title)
        self.children = list(children)
        self.toggle_key = None if toggle_key is None else int(toggle_key)
        self.toggle_button = (None if toggle_button is None
                              else BUTTON(toggle_button))
        self.x, self.y = float(x), float(y)
        self.width, self.max_height = float(width), float(max_height)
        self.anchor = Anchor(anchor)
        self.scale = max(0.5, float(scale))
        self.theme = theme
        self.styles = dict(styles or {})
        self.padding, self.gap = float(padding), float(gap)
        self.text_pixels = float(text_pixels)
        self.capture_input = bool(capture_input)
        self.visible = False
        self.selected = 0
        self.scroll = 0.0
        self._max_scroll = 0.0
        self._hits: list[_Hit] = []
        self._page_stack: list[tuple[Page, int, float]] = []
        self._input_state: dict[object, bool] = {}
        self._repeat_at: dict[object, float] = {}
        self._mouse_x = 0.0
        self._mouse_y = 0.0
        self._mouse_was_down = False
        self._mouse_right_was_down = False
        self._mouse_right_pressed = False
        self._mouse_click_consumed = False
        self._controls_were_enabled: Optional[bool] = None
        self._hovered: Optional[int] = None
        self._focus_source: Optional[str] = None
        self._dragging: Optional[SliderItem] = None
        self._close_bounds: Optional[Rect] = None
        self._panel_bounds: Optional[Rect] = None
        self._viewport: Optional[Rect] = None
        self._scrollbar_bounds: Optional[Rect] = None
        self._scrollbar_thumb: Optional[Rect] = None
        self._scrollbar_dragging = False
        self._scrollbar_drag_offset = 0.0
        if auto:
            _runtime.register("tick", self.update)
            _runtime.register("draw", self.draw)
            _runtime.register("shutdown", self.close)

    @property
    def current_children(self) -> list[Element]:
        return (self._page_stack[-1][0].children
                if self._page_stack else self.children)

    @property
    def current_title(self) -> str:
        return (str(_value(self._page_stack[-1][0].text))
                if self._page_stack else self.title)

    def add(self, *children: Element) -> "View":
        self.children.extend(children)
        return self

    def style_for(self, element: Element) -> ElementStyle:
        return self.styles.get(element.style, ElementStyle())

    def open(self) -> None:
        if self.visible:
            return
        self.visible = True
        self._repeat_at.clear()
        screen_w, screen_h = hud.screen_size()
        self._mouse_x, self._mouse_y = screen_w * 0.5, screen_h * 0.5
        self._mouse_was_down = False
        self._mouse_right_was_down = False
        self._mouse_right_pressed = False
        self._focus_source = None
        if self.capture_input:
            _set_menu_pointer_consumed(False)
            _capture_menu_input(True)
        self._ensure_selection()

    def close(self) -> None:
        if not self.visible:
            return
        self.visible = False
        self._dragging = None
        self._scrollbar_dragging = False
        self._mouse_right_was_down = False
        self._mouse_right_pressed = False
        self._restore_gameplay_controls()
        if self.capture_input:
            _set_menu_pointer_consumed(False)
            _capture_menu_input(False)

    def toggle(self) -> None:
        self.close() if self.visible else self.open()

    def open_page(self, page: Page) -> None:
        self._page_stack.append((page, self.selected, self.scroll))
        self.selected = 0
        self.scroll = 0.0
        self._focus_source = None
        self._ensure_selection()

    def back(self) -> None:
        if self._page_stack:
            _, self.selected, self.scroll = self._page_stack.pop()
            self._ensure_selection()
        else:
            self.close()

    def update(self) -> None:
        if self.toggle_key is not None and self._edge(
                ("key", self.toggle_key), _pysa.key_down(self.toggle_key)):
            self.toggle()
        if (self.toggle_button is not None and self._edge(
                ("button", int(self.toggle_button)),
                self._button_down(self.toggle_button))):
            self.toggle()
        if not self.visible:
            return

        self._update_mouse()
        if not self.visible:
            return
        escape_pressed = self._edge(
            ("key", KEY.ESCAPE), _pysa.key_down(KEY.ESCAPE))
        back_pressed = self._edge(
            ("button", int(BUTTON.CIRCLE)),
            self._button_down(BUTTON.CIRCLE))
        if (escape_pressed or self._mouse_right_pressed or
                (back_pressed and not self._mouse_click_consumed)):
            self.back()
            return
        if self._repeat(("key", KEY.UP), _pysa.key_down(KEY.UP)) or \
                self._repeat(("button", int(BUTTON.DPAD_UP)),
                             self._button_down(BUTTON.DPAD_UP)):
            self._focus_source = "keyboard"
            self.move(-1)
        if self._repeat(("key", KEY.DOWN), _pysa.key_down(KEY.DOWN)) or \
                self._repeat(("button", int(BUTTON.DPAD_DOWN)),
                             self._button_down(BUTTON.DPAD_DOWN)):
            self._focus_source = "keyboard"
            self.move(1)
        if self._repeat(("key", KEY.LEFT), _pysa.key_down(KEY.LEFT)) or \
                self._repeat(("button", int(BUTTON.DPAD_LEFT)),
                             self._button_down(BUTTON.DPAD_LEFT)):
            self._focus_source = "keyboard"
            self.adjust(-1)
        if self._repeat(("key", KEY.RIGHT), _pysa.key_down(KEY.RIGHT)) or \
                self._repeat(("button", int(BUTTON.DPAD_RIGHT)),
                             self._button_down(BUTTON.DPAD_RIGHT)):
            self._focus_source = "keyboard"
            self.adjust(1)
        enter_pressed = self._edge(
            ("key", KEY.ENTER), _pysa.key_down(KEY.ENTER))
        confirm_pressed = self._edge(
            ("button", int(BUTTON.CROSS)),
            self._button_down(BUTTON.CROSS))
        if enter_pressed or (confirm_pressed and
                             not self._mouse_click_consumed):
            self._focus_source = "keyboard"
            self.activate()

    def move(self, amount: int) -> None:
        if not self._hits:
            return
        for _ in range(len(self._hits)):
            self.selected = (self.selected + int(amount)) % len(self._hits)
            if self._hits[self.selected].element.is_enabled():
                break
        self._keep_selected_visible()

    def activate(self) -> None:
        if self._hits:
            self._hits[self.selected].element.activate(self)

    def adjust(self, amount: int) -> None:
        if self._hits:
            self._hits[self.selected].element.adjust(self, int(amount))

    def draw(self) -> None:
        if not self.visible:
            return
        screen_w, screen_h = hud.screen_size()
        panel_width = min(self.width * self.scale, float(screen_w) - 16.0)
        header_height = 46.0 * self.scale
        padding = self.padding * self.scale
        content_width = panel_width - padding * 2
        total = self._measure_vertical(self.current_children, content_width)
        desired_height = header_height + padding * 2 + total
        panel_height = min(self.max_height * self.scale,
                           float(screen_h) - 16.0, desired_height)
        panel = self._anchored_rect(panel_width, panel_height,
                                    float(screen_w), float(screen_h))
        self._panel_bounds = panel
        self._update_pointer_capture()
        screen = Rect(0.0, 0.0, float(screen_w), float(screen_h))
        shadow = Rect(panel.x + 5.0 * self.scale,
                      panel.y + 7.0 * self.scale,
                      panel.width, panel.height)
        _rounded_fill(shadow, (0, 0, 0, 105), screen, 8.0 * self.scale)
        _surface(panel, self.theme.surface, self.theme.border, screen,
                 8.0 * self.scale)
        header = Rect(panel.x, panel.y, panel.width, header_height)
        _fill(Rect(panel.x + self.scale,
                   panel.y + header.height - self.scale,
                   panel.width - self.scale * 2, self.scale),
              self.theme.border, panel)
        title_pixels = 16.0 * self.scale
        hud.draw_mono(self.current_title, panel.x + padding,
                      panel.y + 12.0 * self.scale, title_pixels,
                      self.theme.text, clip=_clip_tuple(header))
        close_size = 28.0 * self.scale
        self._close_bounds = Rect(panel.x + panel.width - padding - close_size,
                                  panel.y + 9.0 * self.scale,
                                  close_size, close_size)
        close_hovered = self._close_bounds.contains(
            self._mouse_x, self._mouse_y)
        _surface(self._close_bounds,
                 self.theme.hover if close_hovered else self.theme.control,
                 self.theme.accent if close_hovered else self.theme.border,
                 header, 6.0 * self.scale)
        close_color = self.theme.text if close_hovered else self.theme.muted
        close_width = hud.mono_text_width("X", 14.0 * self.scale)
        hud.draw_mono("X", self._close_bounds.x +
                      (close_size - close_width) * 0.5,
                      self._close_bounds.y + 5.0 * self.scale,
                      14.0 * self.scale, close_color,
                      clip=_clip_tuple(header))

        viewport = Rect(panel.x + padding, panel.y + header_height + padding,
                        content_width,
                        max(0.0, panel.height - header_height - padding * 2))
        self._viewport = viewport
        self._max_scroll = max(0.0, total - viewport.height)
        self.scroll = max(0.0, min(self._max_scroll, self.scroll))
        self._hits = []
        self._layout_vertical(self.current_children, viewport.x,
                              viewport.y - self.scroll, viewport.width,
                              viewport, self.gap * self.scale)
        self._ensure_selection()
        if self._max_scroll > 0:
            track = Rect(panel.x + panel.width - 5.0 * self.scale,
                         viewport.y, 2.0 * self.scale, viewport.height)
            self._scrollbar_bounds = track
            _rounded_fill(track, self.theme.track, panel,
                          track.width * 0.5)
            thumb_height = max(18.0 * self.scale,
                               track.height * viewport.height / total)
            travel = max(0.0, track.height - thumb_height)
            thumb_y = track.y + travel * (self.scroll / self._max_scroll)
            self._scrollbar_thumb = Rect(track.x - 3.0 * self.scale, thumb_y,
                                         track.width + 6.0 * self.scale,
                                         thumb_height)
            _rounded_fill(Rect(track.x, thumb_y, track.width, thumb_height),
                          self.theme.accent, panel, track.width * 0.5)
        else:
            self._scrollbar_bounds = None
            self._scrollbar_thumb = None

        hud.draw_mono("↖", self._mouse_x - 3.0 * self.scale,
                      self._mouse_y - 2.0 * self.scale, 15.0 * self.scale,
                      self.theme.accent)

    def draw_control(self, bounds: Rect, label: str, value: str,
                     enabled: bool, selected: bool, hovered: bool, clip: Rect,
                     element: Element) -> None:
        style = self.draw_control_surface(bounds, selected, hovered, clip,
                                          element)
        pixels = (style.pixels or self.text_pixels) * self.scale
        color = ((style.text or self.theme.text) if enabled
                 else (style.muted or self.theme.muted))
        padding = (style.padding or 12.0) * self.scale
        y = bounds.y + (bounds.height - pixels) * 0.42
        hud.draw_mono(label, bounds.x + padding, y, pixels, color,
                      clip=_clip_tuple(clip))
        if value:
            value_width = hud.mono_text_width(value, pixels)
            hud.draw_mono(value, bounds.x + bounds.width - padding - value_width,
                          y, pixels, color, clip=_clip_tuple(clip))

    def draw_control_surface(self, bounds: Rect, selected: bool,
                             hovered: bool, clip: Rect,
                             element: Element) -> ElementStyle:
        style = self.style_for(element)
        active = selected or hovered
        background = style.background or (
            self.theme.hover if active else self.theme.control)
        border = self.theme.accent if active else self.theme.border
        _surface(bounds, background, border, clip, 6.0 * self.scale)
        return style

    def _measure_vertical(self, elements: Sequence[Element], width: float,
                          gap: Optional[float] = None) -> float:
        visible = [element for element in elements if element.is_visible()]
        actual_gap = self.gap * self.scale if gap is None else gap
        total = 0.0
        for index, element in enumerate(visible):
            if index:
                total += actual_gap
            total += self._measure_element(element, width)
        return total

    def _measure_element(self, element: Element, width: float) -> float:
        if isinstance(element, Row):
            return self._measure_row(element, width)
        if isinstance(element, (Column, Scroll)):
            padding = element.padding * self.scale
            inner = max(0.0, width - padding * 2)
            return (self._measure_vertical(
                element.children, inner, element.gap * self.scale) +
                    padding * 2)
        return element.preferred_height(self)

    def _measure_row(self, row: Row, width: float) -> float:
        visible = [child for child in row.children if child.is_visible()]
        if not visible:
            return 0.0
        padding = row.padding * self.scale
        gap = row.gap * self.scale
        inner_width = max(0.0, width - padding * 2 - gap * (len(visible) - 1))
        cell_width = inner_width / len(visible)
        return max(self._measure_element(child, cell_width)
                   for child in visible) + padding * 2

    def _layout_vertical(self, elements: Sequence[Element], x: float, y: float,
                         width: float, clip: Rect,
                         gap: Optional[float] = None) -> float:
        visible = [element for element in elements if element.is_visible()]
        actual_gap = self.gap * self.scale if gap is None else gap
        cursor = y
        for index, element in enumerate(visible):
            if index:
                cursor += actual_gap
            if isinstance(element, Row):
                height = self._layout_row(element, x, cursor, width, clip)
            elif isinstance(element, (Column, Scroll)):
                padding = element.padding * self.scale
                height = (self._layout_vertical(
                    element.children, x + padding, cursor + padding,
                    max(0.0, width - padding * 2), clip,
                    element.gap * self.scale) - cursor + padding)
            else:
                height = element.preferred_height(self)
                bounds = Rect(x, cursor, width, height)
                element.bounds = bounds
                if element.focusable:
                    hit_index = len(self._hits)
                    self._hits.append(_Hit(element, bounds))
                    hovered = (self._focus_source == "mouse" and
                               hit_index == self._hovered)
                    selected = (self._focus_source == "keyboard" and
                                hit_index == self.selected)
                else:
                    hovered = selected = False
                if _intersection(bounds, clip) is not None:
                    element.draw(self, bounds, selected, hovered, clip)
            cursor += height
        return cursor

    def _layout_row(self, row: Row, x: float, y: float, width: float,
                    clip: Rect) -> float:
        children = [child for child in row.children if child.is_visible()]
        if not children:
            return 0.0
        padding = row.padding * self.scale
        gap = row.gap * self.scale
        inner_width = max(0.0, width - padding * 2 - gap * (len(children) - 1))
        cell_width = inner_width / len(children)
        height = self._measure_row(row, width)
        cell_height = height - padding * 2
        cursor = x + padding
        for child in children:
            bounds = Rect(cursor, y + padding, cell_width, cell_height)
            child.bounds = bounds
            if isinstance(child, Row):
                self._layout_row(child, bounds.x, bounds.y,
                                 bounds.width, clip)
            elif isinstance(child, (Column, Scroll)):
                child_padding = child.padding * self.scale
                self._layout_vertical(
                    child.children, bounds.x + child_padding,
                    bounds.y + child_padding,
                    max(0.0, bounds.width - child_padding * 2), clip,
                    child.gap * self.scale)
            elif child.focusable:
                hit_index = len(self._hits)
                self._hits.append(_Hit(child, bounds))
                hovered = (self._focus_source == "mouse" and
                           hit_index == self._hovered)
                selected = (self._focus_source == "keyboard" and
                            hit_index == self.selected)
            else:
                hovered = selected = False
            if (not isinstance(child, Container) and
                    _intersection(bounds, clip) is not None):
                child.draw(self, bounds, selected, hovered, clip)
            cursor += cell_width + gap
        return height

    def _anchored_rect(self, width: float, height: float,
                       screen_w: float, screen_h: float) -> Rect:
        margin_x, margin_y = self.x * self.scale, self.y * self.scale
        if self.anchor in (Anchor.TOP_CENTER, Anchor.CENTER,
                           Anchor.BOTTOM_CENTER):
            x = (screen_w - width) * 0.5 + margin_x
        elif self.anchor in (Anchor.TOP_RIGHT, Anchor.BOTTOM_RIGHT):
            x = screen_w - width - margin_x
        else:
            x = margin_x
        if self.anchor in (Anchor.CENTER,):
            y = (screen_h - height) * 0.5 + margin_y
        elif self.anchor in (Anchor.BOTTOM_LEFT, Anchor.BOTTOM_CENTER,
                             Anchor.BOTTOM_RIGHT):
            y = screen_h - height - margin_y
        else:
            y = margin_y
        return Rect(max(8.0, min(screen_w - width - 8.0, x)),
                    max(8.0, min(screen_h - height - 8.0, y)), width, height)

    def _update_mouse(self) -> None:
        self._mouse_click_consumed = False
        state = tuple(_pysa.mouse_state())
        dx, dy, down = state[:3]
        right_down = bool(state[3]) if len(state) > 3 else False
        wheel = int(state[4]) if len(state) > 4 else 0
        screen_w, screen_h = hud.screen_size()
        self._mouse_x = max(0.0, min(float(screen_w),
                                     self._mouse_x + float(dx)))
        self._mouse_y = max(0.0, min(float(screen_h),
                                     self._mouse_y + float(dy)))
        down = bool(down)
        self._mouse_right_pressed = (right_down and
                                     not self._mouse_right_was_down)
        self._mouse_right_was_down = right_down
        if dx or dy:
            self._focus_source = "mouse"
        self._hovered = next((index for index, hit in enumerate(self._hits)
                              if (self._viewport is not None and
                                  self._viewport.contains(self._mouse_x,
                                                          self._mouse_y) and
                                  hit.bounds.contains(self._mouse_x,
                                                      self._mouse_y))), None)
        if wheel:
            self.scroll = max(0.0, min(self._max_scroll,
                                       self.scroll - wheel * 72.0 * self.scale))
        if down and not self._mouse_was_down:
            self._focus_source = "mouse"
            if self._close_bounds is not None and self._close_bounds.contains(
                    self._mouse_x, self._mouse_y):
                self._mouse_click_consumed = True
                self.close()
                self._mouse_was_down = True
                return
            if (self._scrollbar_bounds is not None and
                    Rect(self._scrollbar_bounds.x - 6.0 * self.scale,
                         self._scrollbar_bounds.y,
                         self._scrollbar_bounds.width + 12.0 * self.scale,
                         self._scrollbar_bounds.height).contains(
                             self._mouse_x, self._mouse_y)):
                self._mouse_click_consumed = True
                self._scrollbar_dragging = True
                if (self._scrollbar_thumb is not None and
                        self._scrollbar_thumb.contains(self._mouse_x,
                                                       self._mouse_y)):
                    self._scrollbar_drag_offset = (
                        self._mouse_y - self._scrollbar_thumb.y)
                elif self._scrollbar_thumb is not None:
                    self._scrollbar_drag_offset = self._scrollbar_thumb.height * 0.5
                self._set_scroll_from_pointer(self._mouse_y)
                self._mouse_was_down = True
                return
            if self._hovered is not None and self._hovered < len(self._hits):
                self._mouse_click_consumed = True
                self.selected = self._hovered
                element = self._hits[self.selected].element
                if (isinstance(element, SliderItem) and
                        element.track_bounds is not None and
                        element.track_bounds.contains(self._mouse_x,
                                                      self._mouse_y)):
                    self._dragging = element
                    element.set_from_pointer(self._mouse_x)
                elif not isinstance(element, SliderItem):
                    element.activate(self)
        elif down:
            if self._scrollbar_dragging:
                self._set_scroll_from_pointer(self._mouse_y)
            elif self._dragging is not None:
                self._dragging.set_from_pointer(self._mouse_x)
        elif not down:
            self._dragging = None
            self._scrollbar_dragging = False
        self._mouse_was_down = down
        self._update_pointer_capture()

    def _update_pointer_capture(self) -> None:
        if not self.capture_input:
            return
        over_panel = (self._panel_bounds is not None and
                      self._panel_bounds.contains(self._mouse_x, self._mouse_y))
        consumed = (self.visible and
                    (over_panel or self._dragging is not None or
                     self._scrollbar_dragging))
        _set_menu_pointer_consumed(consumed)
        self._set_gameplay_controls_blocked(consumed)

    def _set_gameplay_controls_blocked(self, blocked: bool) -> None:
        if blocked:
            if self._controls_were_enabled is not None:
                return
            try:
                from .player import player
                previous = player.controls.enabled
                player.controls.enabled = False
            except Exception:
                return
            self._controls_were_enabled = previous
            return
        self._restore_gameplay_controls()

    def _restore_gameplay_controls(self) -> None:
        previous = self._controls_were_enabled
        if previous is None:
            return
        self._controls_were_enabled = None
        try:
            from .player import player
            player.controls.enabled = previous
        except Exception:
            pass

    def _button_down(self, button: BUTTON) -> bool:
        captured = getattr(_pysa, "captured_button_down", None)
        if self.visible and self.capture_input and captured is not None:
            return bool(captured(int(button)))
        return bool(pad.pressed(button))

    def _set_scroll_from_pointer(self, mouse_y: float) -> None:
        track = self._scrollbar_bounds
        thumb = self._scrollbar_thumb
        if track is None or thumb is None or self._max_scroll <= 0:
            return
        travel = max(1.0, track.height - thumb.height)
        thumb_y = max(track.y, min(track.y + travel,
                                  float(mouse_y) - self._scrollbar_drag_offset))
        self.scroll = self._max_scroll * ((thumb_y - track.y) / travel)

    def _ensure_selection(self) -> None:
        if not self._hits:
            self.selected = 0
            return
        self.selected = max(0, min(self.selected, len(self._hits) - 1))
        if not self._hits[self.selected].element.is_enabled():
            self.move(1)

    def _keep_selected_visible(self) -> None:
        if not self._hits or self._viewport is None:
            return
        bounds = self._hits[self.selected].bounds
        panel_top = self._viewport.y
        panel_bottom = self._viewport.y + self._viewport.height
        if bounds.y < panel_top:
            self.scroll -= panel_top - bounds.y
        elif bounds.y + bounds.height > panel_bottom:
            self.scroll += bounds.y + bounds.height - panel_bottom
        self.scroll = max(0.0, min(self._max_scroll, self.scroll))

    def _edge(self, key: object, down: bool) -> bool:
        previous = self._input_state.get(key, False)
        self._input_state[key] = bool(down)
        return bool(down) and not previous

    def _repeat(self, key: object, down: bool) -> bool:
        now = time.monotonic()
        previous = self._input_state.get(key, False)
        self._input_state[key] = bool(down)
        if not down:
            self._repeat_at.pop(key, None)
            return False
        if not previous:
            self._repeat_at[key] = now + 0.35
            return True
        if now >= self._repeat_at.get(key, now + 1.0):
            self._repeat_at[key] = now + 0.075
            return True
        return False


def _state_binding(state: Mapping[str, Any], path: str) -> Binding[Any]:
    parts = path.split(".")
    if parts[0] not in state:
        raise MarkupError(f"unknown state root {parts[0]!r} in binding {{{path}}}")

    if len(parts) > 1:
        nested = bind(state[parts[0]], ".".join(parts[1:]))
        return Binding(nested.get, nested.set if nested.writable else None,
                       path=path)

    def parent_and_name() -> tuple[Any, str]:
        current: Any = state
        for part in parts[:-1]:
            current = _get_member(current, part)
        return current, parts[-1]

    def getter() -> Any:
        parent, name = parent_and_name()
        return _get_member(parent, name)

    def setter(value: Any) -> None:
        parent, name = parent_and_name()
        _set_member(parent, name, value)

    return Binding(getter, setter, path=path)


def _dynamic(text: Optional[str], state: Mapping[str, Any],
             default: Any = None) -> Any:
    if text is None:
        return default
    match = _BINDING.fullmatch(text.strip())
    return _state_binding(state, match.group(1)) if match else text


def _bool_dynamic(text: Optional[str], state: Mapping[str, Any],
                  default: bool = True) -> Dynamic[bool]:
    value = _dynamic(text, state, default)
    if isinstance(value, Binding):
        return value
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().lower()
    if lowered in ("true", "yes", "on", "1"):
        return True
    if lowered in ("false", "no", "off", "0"):
        return False
    raise MarkupError(f"expected a boolean or binding, got {value!r}")


def _number(text: Optional[str], name: str, default: Optional[float] = None) -> float:
    if text is None:
        if default is None:
            raise MarkupError(f"missing required {name!r} attribute")
        return float(default)
    try:
        return float(text)
    except ValueError as exc:
        raise MarkupError(f"{name!r} must be a number, got {text!r}") from exc


def _common(node: ET.Element, state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "visible": _bool_dynamic(node.get("visible"), state, True),
        "enabled": _bool_dynamic(node.get("enabled"), state, True),
        "height": (_number(node.get("height"), "height")
                   if node.get("height") is not None else None),
        "style": node.get("style", ""),
    }


def _action(actions: Mapping[str, Callable[[], Any]], name: Optional[str]) -> Callable[[], Any]:
    if not name or not _ACTION.fullmatch(name):
        raise MarkupError("on-click must name a Python action")
    try:
        callback = actions[name]
    except KeyError as exc:
        raise MarkupError(f"unknown action {name!r}") from exc
    if not callable(callback):
        raise MarkupError(f"action {name!r} is not callable")
    return callback


def _children(node: ET.Element, actions: Mapping[str, Callable[[], Any]],
              state: Mapping[str, Any]) -> list[Element]:
    return [_parse_element(child, actions, state) for child in node]


def _check_attributes(node: ET.Element, allowed: set[str]) -> None:
    unknown = set(node.attrib) - allowed
    if unknown:
        names = ", ".join(sorted(repr(name) for name in unknown))
        raise MarkupError(f"<{node.tag}> has unknown attribute(s): {names}")


def _parse_element(node: ET.Element,
                   actions: Mapping[str, Callable[[], Any]],
                   state: Mapping[str, Any]) -> Element:
    tag = node.tag.lower()
    if tag not in _ELEMENT_ATTRIBUTES:
        raise MarkupError(f"unknown UI element <{node.tag}>")
    _check_attributes(node, _COMMON_ATTRIBUTES | _ELEMENT_ATTRIBUTES[tag])
    common = _common(node, state)
    text = _dynamic(node.get("text", node.get("value")), state, "")
    if tag == "text":
        return Text(text, **common)
    if tag == "button":
        return Button(text, _action(actions, node.get("on-click")), **common)
    if tag == "toggle":
        value = _dynamic(node.get("value"), state)
        if not isinstance(value, Binding):
            raise MarkupError("Toggle value must be a {state.path} binding")
        if not value.writable:
            raise MarkupError(f"Toggle binding {value.path!r} is read-only")
        return Toggle(text, value, on_text=node.get("on-text", "ON"),
                      off_text=node.get("off-text", "OFF"), **common)
    if tag == "slider":
        value = _dynamic(node.get("value"), state)
        if not isinstance(value, Binding):
            raise MarkupError("Slider value must be a {state.path} binding")
        if not value.writable:
            raise MarkupError(f"Slider binding {value.path!r} is read-only")
        return SliderItem(text, _number(node.get("min"), "min"),
                          _number(node.get("max"), "max"),
                          _number(node.get("step"), "step", 1.0), value,
                          value_format=node.get("format", "g"), **common)
    if tag == "choice":
        value = _dynamic(node.get("value"), state)
        if not isinstance(value, Binding):
            raise MarkupError("Choice value must be a {state.path} binding")
        if not value.writable:
            raise MarkupError(f"Choice binding {value.path!r} is read-only")
        options = _dynamic(node.get("options"), state)
        if isinstance(options, Binding):
            values: Dynamic[Iterable[Any]] = options
        elif options is None:
            raise MarkupError("Choice requires an options attribute")
        else:
            values = tuple(part.strip() for part in str(options).split(",")
                           if part.strip())
        return Choice(text, values, value, formatter=_friendly_value, **common)
    if tag == "page":
        return Page(text, *_children(node, actions, state), **common)
    if tag in ("column", "scroll"):
        cls = Scroll if tag == "scroll" else Column
        return cls(*_children(node, actions, state),
                   gap=_number(node.get("gap"), "gap", 6.0),
                   padding=_number(node.get("padding"), "padding", 0.0),
                   **common)
    if tag == "row":
        return Row(*_children(node, actions, state),
                   gap=_number(node.get("gap"), "gap", 6.0),
                   padding=_number(node.get("padding"), "padding", 0.0),
                   **common)
    if tag == "separator":
        return Separator(**common)
    if tag == "spacer":
        return Spacer(**common)
    if tag == "image":
        sprite = _dynamic(node.get("sprite"), state)
        if not sprite:
            raise MarkupError("Image requires a sprite attribute")
        return Image(sprite, **common)
    raise AssertionError(f"unhandled UI element <{node.tag}>")


def _friendly_value(value: Any) -> object:
    return getattr(value, "name", value)


def _key(value: Optional[str]) -> Optional[int]:
    if value is None or not value.strip():
        return None
    name = value.strip().upper()
    if hasattr(KEY, name):
        return int(getattr(KEY, name))
    try:
        return int(name, 0)
    except ValueError as exc:
        raise MarkupError(f"unknown key {value!r}") from exc


def _button(value: Optional[str]) -> Optional[BUTTON]:
    if value is None or not value.strip():
        return None
    name = value.strip().upper()
    try:
        return BUTTON[name]
    except KeyError as exc:
        raise MarkupError(f"unknown controller button {value!r}") from exc


def _resolve_path(path: Union[str, Path]) -> Path:
    requested = Path(path)
    if requested.is_absolute() and requested.is_file():
        return requested
    candidates = [requested, Path(str(_pysa.base_dir())) / requested,
                  Path(str(_pysa.base_dir())) / "scripts" / requested]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"UI document not found: {path}")


def load(path: Union[str, Path], *,
         actions: Optional[Mapping[str, Callable[[], Any]]] = None,
         state: Optional[Mapping[str, Any]] = None,
         themes: Optional[Mapping[str, Theme]] = None,
         styles: Optional[Mapping[str, ElementStyle]] = None,
         auto: bool = True) -> View:
    """Load a safe XML-like ``.pui`` menu document.

    Markup can access only the names explicitly supplied through ``actions``
    and ``state``.  It never evaluates Python expressions.
    """
    source = _resolve_path(path)
    try:
        root = ET.parse(str(source)).getroot()
    except ET.ParseError as exc:
        raise MarkupError(f"{source.name}:{exc}") from exc
    if root.tag.lower() != "menu":
        raise MarkupError(f"{source.name}: root element must be <Menu>")
    _check_attributes(root, _ROOT_ATTRIBUTES)
    action_map = dict(actions or {})
    state_map = dict(state or {})
    theme_map = {"dark": DARK_THEME}
    theme_map.update(themes or {})
    theme_name = root.get("theme", "dark")
    try:
        theme = theme_map[theme_name]
    except KeyError as exc:
        raise MarkupError(f"unknown theme {theme_name!r}") from exc
    title = root.get("title", source.stem)
    try:
        anchor = Anchor(root.get("anchor", Anchor.TOP_LEFT.value))
    except ValueError as exc:
        choices = ", ".join(item.value for item in Anchor)
        raise MarkupError(f"anchor must be one of: {choices}") from exc
    return View(
        title, *_children(root, action_map, state_map),
        toggle_key=_key(root.get("toggle-key")),
        toggle_button=_button(root.get("toggle-button")),
        x=_number(root.get("x"), "x", 32.0),
        y=_number(root.get("y"), "y", 48.0),
        width=_number(root.get("width"), "width", 360.0),
        max_height=_number(root.get("max-height"), "max-height", 520.0),
        anchor=anchor,
        scale=_number(root.get("scale"), "scale", 1.0),
        theme=theme, styles=styles,
        padding=_number(root.get("padding"), "padding", 12.0),
        gap=_number(root.get("gap"), "gap", 6.0),
        text_pixels=_number(root.get("text-size"), "text-size", 15.0),
        capture_input=bool(_bool_dynamic(root.get("capture-input"), {}, True)),
        auto=auto,
    )


__all__ = [
    "Anchor", "Binding", "Button", "Choice", "Column", "Element",
    "ElementStyle", "Image", "MarkupError", "Page", "Row", "Scroll",
    "Separator", "SliderItem", "Spacer", "Text", "Toggle", "UIError",
    "View", "bind", "load", "read",
]
