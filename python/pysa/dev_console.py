"""Built-in in-game Python console for development and smoke testing."""
from __future__ import annotations

import ctypes
import configparser
import ast
import inspect
import io
import keyword
import math
import os
import re
import textwrap
import time
import token as token_types
import tokenize
import traceback
import types
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Union, get_args, get_origin, get_type_hints

try:
    import _pysa
except ImportError:
    from . import _mock as _pysa

from . import _runtime, console_commands, draw, hud, testing, ui
from .keys import KEY


_UNION_ORIGINS = ((Union, types.UnionType)
                  if hasattr(types, "UnionType") else (Union,))


_TEXT_KEYS = (
    KEY.SPACE,
    *range(KEY.N0, KEY.N9 + 1),
    *range(KEY.A, KEY.Z + 1),
    *range(KEY.NUMPAD0, KEY.DIVIDE + 1),
    KEY.SEMICOLON, KEY.EQUALS, KEY.COMMA, KEY.MINUS, KEY.PERIOD,
    KEY.SLASH, KEY.BACKTICK, KEY.LEFT_BRACKET, KEY.BACKSLASH,
    KEY.RIGHT_BRACKET, KEY.QUOTE, KEY.OEM_102,
)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_get_keyboard_state = _user32.GetKeyboardState
_get_keyboard_state.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
_get_keyboard_state.restype = ctypes.c_int
_get_keyboard_layout = _user32.GetKeyboardLayout
_get_keyboard_layout.argtypes = [ctypes.c_uint]
_get_keyboard_layout.restype = ctypes.c_void_p
_map_virtual_key = _user32.MapVirtualKeyExW
_map_virtual_key.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
_map_virtual_key.restype = ctypes.c_uint
_to_unicode = _user32.ToUnicodeEx
_to_unicode.argtypes = [
    ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p,
]
_to_unicode.restype = ctypes.c_int
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_write_ini = _kernel32.WritePrivateProfileStringW
_write_ini.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                       ctypes.c_wchar_p, ctypes.c_wchar_p]
_write_ini.restype = ctypes.c_int


def _translate_key(key: int) -> str:
    """Translate a virtual key using the active Windows keyboard layout."""
    state = (ctypes.c_ubyte * 256)()
    if not _get_keyboard_state(state):
        return ""
    layout = _get_keyboard_layout(0)
    scan_code = _map_virtual_key(int(key), 0, layout)
    buffer = ctypes.create_unicode_buffer(8)
    count = _to_unicode(int(key), scan_code, state, buffer, len(buffer),
                        0, layout)
    if count <= 0:
        # A negative result is a dead key. Windows retains it and composes it
        # when the next printable key is translated.
        return ""
    return buffer[:count]


@dataclass
class _CompletionMenu:
    start: int
    end: int
    candidates: list[str]
    labels: list[str]
    details: list[str]
    colors: list[tuple[int, int, int]]
    selected: int = 0


@dataclass
class _CallHint:
    key: tuple[str, int]
    function: Any
    name: str
    signature: inspect.Signature
    parameters: list[inspect.Parameter]
    active: int
    argument_start: int
    documentation: str


_CODE_DEFAULT = (226, 232, 236)
_CODE_KEYWORD = (198, 146, 255)
_CODE_STRING = (224, 170, 108)
_CODE_NUMBER = (116, 201, 190)
_CODE_COMMENT = (106, 153, 85)
_CODE_OPERATOR = (154, 166, 176)
_CODE_BUILTIN = (86, 190, 220)
_CODE_CALL = (220, 210, 125)
_CODE_ATTRIBUTE = (145, 205, 232)
_CODE_ENUM = (255, 156, 108)
_CODE_CLASS = (110, 200, 255)
_CODE_MODULE = (112, 190, 215)
_CLOSE_THEME = ui.Theme(
    control=(40, 47, 52, 230), hover=(150, 55, 58, 245),
    text=(255, 235, 235), muted=(190, 199, 205),
)


class DeveloperConsole:
    """A small F10-style console that executes Python on GTA's game thread.

    PyAndreas owns one built-in instance. The class remains public for custom
    consoles, but scripts normally use :func:`developer_console` instead.
    """

    __slots__ = (
        "toggle_key", "visible", "prompt", "input", "history", "history_limit",
        "output", "output_limit", "namespace", "scale", "background_opacity",
        "auto_complete", "settings_visible", "cursor", "enabled",
        "_history_index", "_down", "_repeat_at", "_controls_were_enabled",
        "last_test_run", "_restore_after_frontend", "mouse_x", "mouse_y",
        "selection_anchor", "_mouse_was_down", "_mouse_selecting",
        "_drag_source", "_drag_target", "_completion",
        "_completion_hitbox", "_completion_hover_row", "_output_hitboxes",
        "_scroll_offset",
        "_scroll_visual", "_scroll_time", "_max_scroll",
        "_scrollbar_hitbox", "_scrollbar_dragging", "_scrollbar_drag_offset",
        "_wrapped_output_cache", "_output_cell_width",
        "_output_selection_anchor", "_output_selection_cursor",
        "_output_selecting", "_last_output_click",
        "_call_hint_cache",
        "_close_hitbox", "_settings_hitbox", "_settings_hitboxes",
        "_settings_sliders", "_settings_slider_hitboxes",
        "_settings_dragging", "_command_context",
    )

    def __init__(self, toggle_key: int = KEY.F10, *, prompt: str = ">>> ",
                 history_limit: int = 50, output_limit: int = 100,
                 namespace: Optional[dict[str, Any]] = None,
                 scale: float = 1.0, background_opacity: float = 0.69,
                 auto_complete: bool = True,
                 _register_handlers: bool = False):
        self.toggle_key = int(toggle_key)
        self.visible = False
        self.prompt = str(prompt)
        self.input = ""
        self.history: list[str] = []
        self.history_limit = max(1, int(history_limit))
        self.output: list[str] = [
            "PyAndreas developer console",
            "Type /help for commands; Python expressions work directly.",
        ]
        self.output_limit = max(10, int(output_limit))
        self.namespace = namespace or self._default_namespace()
        self.scale = max(0.5, float(scale))
        self.background_opacity = max(0.0, min(1.0, float(background_opacity)))
        self.auto_complete = bool(auto_complete)
        self.settings_visible = False
        self.cursor = 0
        self.enabled = True
        self._history_index = 0
        self._down: dict[int, bool] = {}
        self._repeat_at: dict[int, float] = {}
        self._controls_were_enabled: Optional[bool] = None
        self.last_test_run: Optional[testing.TestRun] = None
        self._restore_after_frontend: Optional[bool] = None
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.selection_anchor: Optional[int] = None
        self._mouse_was_down = False
        self._mouse_selecting = False
        self._drag_source: Optional[tuple[int, int]] = None
        self._drag_target: Optional[int] = None
        self._completion: Optional[_CompletionMenu] = None
        self._completion_hitbox: Optional[
            tuple[float, float, float, float, int, int]
        ] = None
        self._completion_hover_row: Optional[int] = None
        self._output_hitboxes: list[
            tuple[float, float, float, float, str, int]
        ] = []
        self._scroll_offset = 0
        self._scroll_visual = 0.0
        self._scroll_time = time.monotonic()
        self._max_scroll = 0
        self._scrollbar_hitbox: Optional[
            tuple[float, float, float, float, float, float]
        ] = None
        self._scrollbar_dragging = False
        self._scrollbar_drag_offset = 0.0
        self._wrapped_output_cache: list[str] = []
        self._output_cell_width = 1.0
        self._output_selection_anchor: Optional[tuple[int, int]] = None
        self._output_selection_cursor: Optional[tuple[int, int]] = None
        self._output_selecting = False
        self._last_output_click: Optional[tuple[float, int]] = None
        self._call_hint_cache: Optional[_CallHint] = None
        self._close_hitbox: Optional[tuple[float, float, float, float]] = None
        self._settings_hitbox: Optional[tuple[float, float, float, float]] = None
        self._settings_hitboxes: list[
            tuple[float, float, float, float, str]
        ] = []
        self._settings_sliders = {
            "scale": ui.Slider(0.60, 1.80, 0.10,
                                lambda: self.scale,
                                lambda value: self._set_setting_value(
                                    "scale", value)),
            "opacity": ui.Slider(0.0, 1.0, 0.05,
                                  lambda: self.background_opacity,
                                  lambda value: self._set_setting_value(
                                      "opacity", value)),
            "history": ui.Slider(25, 500, 25,
                                  lambda: self.output_limit,
                                  lambda value: self._set_setting_value(
                                      "history", value)),
        }
        self._settings_slider_hitboxes: dict[str, ui.Rect] = {}
        self._settings_dragging: Optional[str] = None
        self._command_context = console_commands.CommandContext(self)

        if _register_handlers:
            _runtime.register("tick", self.update)
            _runtime.register("draw", self.draw)
            _runtime.register("shutdown", self.close)

    @staticmethod
    def _default_namespace() -> dict[str, Any]:
        import pysa
        return {
            "pysa": pysa,
            "player": pysa.player,
            "world": pysa.world,
            "cmd": pysa.cmd,
            "hud": pysa.hud,
            "blips": pysa.blips,
            "camera": pysa.camera,
            "game": pysa.game,
            "cutscenes": pysa.cutscenes,
            "trains": pysa.trains,
            "pickups": pysa.pickups,
            "draw": pysa.draw,
            "ui": pysa.ui,
            "storage": pysa.storage,
            "VEHICLE": pysa.VEHICLE,
            "PED": pysa.PED,
            "WEAPON": pysa.WEAPON,
            "Vehicle": pysa.Vehicle,
            "Ped": pysa.Ped,
            "GameObject": pysa.GameObject,
            "Vector3": pysa.Vector3,
            "__builtins__": __builtins__,
        }

    def open(self) -> None:
        if self.visible:
            return
        self.visible = True
        self._down.clear()
        self._repeat_at.clear()
        screen_w, screen_h = hud.screen_size()
        self.mouse_x = float(screen_w) * 0.5
        self.mouse_y = float(screen_h) * 0.5
        self._mouse_was_down = False
        self._mouse_selecting = False
        self._drag_source = None
        self._drag_target = None
        _pysa.capture_input(True)
        try:
            from .player import player
            self._controls_were_enabled = player.controls.enabled
            player.controls.enabled = False
        except Exception:
            self._controls_were_enabled = None

    def close(self) -> None:
        if not self.visible:
            return
        self.visible = False
        self.settings_visible = False
        try:
            if self._controls_were_enabled is not None:
                from .player import player
                player.controls.enabled = self._controls_were_enabled
        except Exception:
            pass
        self._controls_were_enabled = None
        self._mouse_selecting = False
        self._drag_source = None
        self._drag_target = None
        _pysa.capture_input(False)

    def toggle(self) -> None:
        self.close() if self.visible else self.open()

    def write(self, message: Any) -> None:
        lines = str(message).replace("\r", "").split("\n")
        self.output.extend(lines)
        del self.output[:-self.output_limit]
        self._scroll_offset = 0
        self._scroll_visual = 0.0
        self._clear_output_selection()

    def clear(self) -> None:
        self.output.clear()
        self._scroll_offset = 0
        self._scroll_visual = 0.0
        self._clear_output_selection()

    def update(self) -> None:
        if not self.enabled:
            if self.visible:
                self.close()
            self._restore_after_frontend = None
            return
        if _pysa.frontend_active():
            self.suspend_for_frontend()
            return
        if self._restore_after_frontend is not None:
            # SET_PLAYER_CONTROL can be swallowed during a frontend
            # transition. Repeat the exact pre-console state on the first
            # gameplay tick, then leave the console closed.
            try:
                from .player import player
                player.controls.enabled = self._restore_after_frontend
            except Exception:
                return
            self._restore_after_frontend = None
        if self._pressed(self.toggle_key):
            self.toggle()
            # open() clears edge state; retain this key until it is released.
            self._down[self.toggle_key] = True
            return
        if not self.visible:
            return

        if self.settings_visible:
            if self._pressed(KEY.ESCAPE):
                self.settings_visible = False
                return
            self._update_mouse()
            return

        ctrl = (_pysa.key_down(KEY.CTRL) or _pysa.key_down(KEY.LCTRL) or
                _pysa.key_down(KEY.RCTRL))

        if self._completion is not None:
            if self._pressed(KEY.ESCAPE):
                self._completion = None
                return
            if self._pressed(KEY.ENTER):
                if (console_commands.can_execute_without_arguments(self.input)
                        or self._exact_completion_can_submit()):
                    self._completion = None
                    self._submit()
                else:
                    self._accept_completion()
                return
            if self._repeat_pressed(KEY.UP, initial_delay=0.32,
                                    interval=0.08):
                self._move_completion(-1)
                return
            if self._repeat_pressed(KEY.DOWN, initial_delay=0.32,
                                    interval=0.08):
                self._move_completion(1)
                return
            if self._repeat_pressed(KEY.PAGEUP, initial_delay=0.32,
                                    interval=0.12):
                self._move_completion(-7)
                return
            if self._repeat_pressed(KEY.PAGEDOWN, initial_delay=0.32,
                                    interval=0.12):
                self._move_completion(7)
                return
            if self._pressed(KEY.TAB):
                self._accept_completion()
                return

        if self._pressed(KEY.ESCAPE):
            self.close()
            return
        if self._pressed(KEY.ENTER):
            self._submit()
            return
        if self._repeat_pressed(KEY.BACKSPACE):
            self._clear_output_selection()
            refresh_completion = self._completion is not None
            if not self._delete_selection() and self.cursor > 0:
                pairs = {"(": ")", "[": "]", "{": "}", "'": "'", '"': '"'}
                before = self.input[self.cursor - 1]
                paired = (self.cursor < len(self.input) and
                          pairs.get(before) == self.input[self.cursor])
                left = self.cursor - 1
                right = self.cursor + (1 if paired else 0)
                self.input = self.input[:left] + self.input[right:]
                self.cursor = left
            if refresh_completion or self._should_auto_complete():
                self._complete()
        if self._repeat_pressed(KEY.DELETE):
            self._clear_output_selection()
            refresh_completion = self._completion is not None
            if (not self._delete_selection() and
                    self.cursor < len(self.input)):
                self.input = (self.input[:self.cursor] +
                              self.input[self.cursor + 1:])
            if refresh_completion or self._should_auto_complete():
                self._complete()
        if self._repeat_pressed(KEY.LEFT):
            self._completion = None
            selection = self._selection_bounds()
            self.cursor = (selection[0] if selection
                           else (self._word_left() if ctrl
                                 else max(0, self.cursor - 1)))
            self.selection_anchor = None
        if self._repeat_pressed(KEY.RIGHT):
            self._completion = None
            selection = self._selection_bounds()
            self.cursor = (selection[1] if selection
                           else (self._word_right() if ctrl
                                 else min(len(self.input), self.cursor + 1)))
            self.selection_anchor = None
        if self._pressed(KEY.HOME):
            self._completion = None
            self.cursor = 0
            self.selection_anchor = None
        if self._pressed(KEY.END):
            self._completion = None
            self.cursor = len(self.input)
            self.selection_anchor = None
        if self._pressed(KEY.UP):
            self._history_move(-1)
        if self._pressed(KEY.DOWN):
            self._history_move(1)
        if self._pressed(KEY.TAB):
            self._complete()

        if ctrl:
            if self._pressed(KEY.A):
                self._clear_output_selection()
                self.selection_anchor = 0
                self.cursor = len(self.input)
            if self._pressed(KEY.C):
                self._copy_selection()
            if self._pressed(KEY.X):
                if self._copy_selection():
                    self._delete_selection()
            if self._pressed(KEY.V):
                pasted = str(_pysa.clipboard_get())
                self._insert(pasted.replace("\r", "").replace("\n", " "))
            if self._pressed(KEY.SPACE):
                self._complete()
            if self._pressed(KEY.L):
                self.clear()
        else:
            for key in _TEXT_KEYS:
                if self._pressed(key):
                    self._insert(_translate_key(key))

        self._update_mouse()

    def suspend_for_frontend(self) -> None:
        """Close for GTA's front end and guarantee controls are restored."""
        if self.visible:
            restore = self._controls_were_enabled
            self.close()
            self._restore_after_frontend = restore

    def draw(self) -> None:
        if not self.enabled or not self.visible:
            return
        screen_w, screen_h = hud.screen_size()
        ui_scale = max(1.0, min(float(screen_h) / 448.0, 4.0)) * self.scale
        width = float(screen_w) * 0.86
        height = float(screen_h) * 0.58
        x = (float(screen_w) - width) * 0.5
        y = float(screen_h) * 0.055
        border = max(1.0, 1.2 * ui_scale)
        padding = 9.0 * ui_scale
        header_height = 27.0 * ui_scale
        input_height = 34.0 * ui_scale

        # Terminal-like shell: restrained chrome, opaque working area and a
        # separate input strip. Rendering occurs after GTA's HUD.
        draw.rect(x - border, y - border, width + border * 2,
                  height + border * 2, (52, 62, 72, 245))
        background_alpha = int(round(self.background_opacity * 255.0))
        draw.rect(x, y, width, height,
                  (5, 7, 9, background_alpha))
        draw.rect(x, y, width, header_height, (17, 21, 25, 255))
        draw.rect(x, y + header_height - 1.5 * ui_scale, width,
                  1.5 * ui_scale, (64, 190, 126, 255))
        draw.rect(x, y + height - input_height, width, input_height,
                  (10, 14, 17, min(255, background_alpha + 55)))
        draw.rect(x, y + height - input_height, width, 1.0 * ui_scale,
                  (45, 55, 62, 255))
        draw.rect(x + padding, y + 9.0 * ui_scale, 6.0 * ui_scale,
                  6.0 * ui_scale, (64, 210, 132, 255))

        font_pixels = 13.0 * ui_scale
        header_pixels = 12.0 * ui_scale
        input_pixels = 15.0 * ui_scale
        hud.draw_mono("PYANDREAS DEV CONSOLE",
                      x + padding + 11.0 * ui_scale, y + 5.0 * ui_scale,
                      header_pixels, (195, 204, 210))
        close_size = 20.0 * ui_scale
        close_x = x + width - padding - close_size
        close_y = y + 3.0 * ui_scale
        self._close_hitbox = (close_x, close_y, close_size, close_size)
        close_bounds = ui.Rect(close_x, close_y, close_size, close_size)
        ui.draw_button(close_bounds, "X",
                       hovered=close_bounds.contains(self.mouse_x, self.mouse_y),
                       pixels=header_pixels, theme=_CLOSE_THEME)

        settings_label = "SETTINGS"
        settings_width = (hud.mono_text_width(settings_label, header_pixels) +
                          14.0 * ui_scale)
        settings_x = close_x - 8.0 * ui_scale - settings_width
        self._settings_hitbox = (
            settings_x, close_y, settings_width, close_size)
        settings_bounds = ui.Rect(
            settings_x, close_y, settings_width, close_size)
        ui.draw_button(
            settings_bounds, settings_label,
            hovered=settings_bounds.contains(self.mouse_x, self.mouse_y),
            active=self.settings_visible, pixels=header_pixels)

        shortcut_label = "F10 / ESC"
        shortcut_x = settings_x - 12.0 * ui_scale - hud.mono_text_width(
            shortcut_label, header_pixels)
        hud.draw_mono(shortcut_label, shortcut_x, y + 5.0 * ui_scale,
                      header_pixels, (112, 125, 134))

        if self.settings_visible:
            self._output_hitboxes = []
            self._completion_hitbox = None
            self._scrollbar_hitbox = None
            self._draw_settings_panel(
                x + padding, y + header_height + 9.0 * ui_scale,
                width - padding * 2.0,
                height - header_height - 18.0 * ui_scale, ui_scale)
            hud.draw_mono("↖", self.mouse_x - 3.0 * ui_scale,
                          self.mouse_y - 8.0 * ui_scale, 13.0 * ui_scale,
                          (92, 235, 158))
            return

        line_height = 19.0 * ui_scale
        output_y = y + header_height + 7.0 * ui_scale
        input_y = y + height - input_height + 6.0 * ui_scale
        output_bottom = y + height - input_height - 4.0 * ui_scale
        if self._completion is not None:
            popup_height = self._completion_popup_height(ui_scale)
            popup_top = input_y - popup_height - 6.0 * ui_scale
            output_bottom = min(output_bottom, popup_top - 4.0 * ui_scale)
        else:
            call_hint = self._call_hint()
            if call_hint is not None:
                hint_top = input_y - 62.0 * ui_scale
                output_bottom = min(output_bottom,
                                    hint_top - 4.0 * ui_scale)
        count = max(0, int((output_bottom - output_y) // line_height))
        output_cell = max(1.0, hud.mono_text_width("M", font_pixels))
        self._output_cell_width = output_cell
        output_columns = max(
            1, int((width - padding * 2.0) // output_cell) - 1)
        wrapped_output = self._wrapped_output(output_columns)
        self._wrapped_output_cache = wrapped_output
        self._max_scroll = max(0, len(wrapped_output) - count)
        self._scroll_offset = min(self._scroll_offset, self._max_scroll)
        now = time.monotonic()
        elapsed = max(0.0, min(0.1, now - self._scroll_time))
        self._scroll_time = now
        blend = 1.0 - math.exp(-15.0 * elapsed)
        self._scroll_visual += (
            float(self._scroll_offset) - self._scroll_visual) * blend
        if abs(self._scroll_visual - self._scroll_offset) < 0.002:
            self._scroll_visual = float(self._scroll_offset)
        scroll_base = int(math.floor(self._scroll_visual))
        scroll_fraction = self._scroll_visual - scroll_base
        end = max(0, len(wrapped_output) - scroll_base)
        start = max(0, end - count - 1)
        self._output_hitboxes = []
        for absolute in range(start, end):
            line = wrapped_output[absolute]
            row = absolute - (end - count)
            line_y = (output_y + row * line_height +
                      scroll_fraction * line_height)
            if (line_y + line_height <= output_y or
                    line_y >= output_bottom):
                continue
            color = self._line_color(line)
            selection = self._output_selection_for_row(absolute, len(line))
            if selection is not None:
                selected_start, selected_end = selection
                draw.rect(x + padding + selected_start * output_cell,
                          line_y + 1.0 * ui_scale,
                          max(1.5 * ui_scale,
                              (selected_end - selected_start) * output_cell),
                          line_height - 2.0 * ui_scale,
                          (48, 92, 118, 235))
            clip = (x + padding, output_y,
                    x + width - padding, output_bottom)
            if line.startswith(">>> "):
                prompt = ">>> "
                hud.draw_mono(prompt, x + padding, line_y,
                              font_pixels, (74, 220, 142), clip=clip)
                self._draw_syntax(
                    line[4:], x + padding + 4 * output_cell, line_y,
                    font_pixels, output_cell, clip=clip)
            elif (line.startswith("Error:") or line.startswith("Warning:") or
                  line.startswith("[PASS]") or line.startswith("[FAIL]") or
                  line.startswith("[RUN ") or line.startswith("[TEST]")):
                hud.draw_mono(line, x + padding, line_y,
                              font_pixels, color, clip=clip)
            else:
                self._draw_syntax(
                    line, x + padding, line_y, font_pixels, output_cell,
                    clip=clip, default_color=color)
            self._output_hitboxes.append((
                x + padding, x + width - padding, line_y,
                line_y + line_height, line, absolute))
        if self._max_scroll > 0:
            track_x = x + width - 4.0 * ui_scale
            track_height = max(1.0, output_bottom - output_y)
            thumb_height = max(16.0 * ui_scale,
                               track_height * min(1.0, count / max(
                                   1.0, float(len(wrapped_output)))))
            travel = max(0.0, track_height - thumb_height)
            ratio = min(1.0, self._scroll_visual / self._max_scroll)
            thumb_y = output_y + travel * (1.0 - ratio)
            draw.rect(track_x, output_y, 2.0 * ui_scale, track_height,
                      (30, 39, 44, 180))
            draw.rect(track_x, thumb_y, 2.0 * ui_scale, thumb_height,
                      (74, 170, 126, 235))
            self._scrollbar_hitbox = (
                track_x - 5.0 * ui_scale, output_y,
                12.0 * ui_scale, track_height, thumb_y, thumb_height)
        else:
            self._scrollbar_hitbox = None

        hud.draw_mono(self.prompt, x + padding, input_y, input_pixels,
                      (74, 220, 142))
        prompt_width = hud.mono_text_width(self.prompt, input_pixels)
        input_x = x + padding + prompt_width
        cell_width = max(1.0, hud.mono_text_width("M", input_pixels))
        input_right = x + width - padding
        input_columns = max(
            1, int((input_right - input_x) // cell_width) - 1)
        view_start, visible_input = self._input_window(input_columns)
        selection = self._selection_bounds()
        if selection is not None:
            start, end = selection
            visible_start = max(start, view_start)
            visible_end = min(end, view_start + input_columns)
            if visible_start < visible_end:
                draw.rect(input_x + (visible_start - view_start) * cell_width,
                          input_y + 1.0 * ui_scale,
                          (visible_end - visible_start) * cell_width,
                          16.0 * ui_scale, (45, 88, 112, 230))
        if self._drag_target is not None:
            drag_column = self._drag_target - view_start
            if 0 <= drag_column <= input_columns:
                draw.rect(input_x + drag_column * cell_width,
                          input_y, max(1.5, ui_scale), 17.0 * ui_scale,
                          (255, 190, 80, 255))
        self._draw_syntax(
            self.input, input_x, input_y, input_pixels, cell_width,
            start=view_start, end=view_start + len(visible_input))

        self._draw_completion_menu(
            x + padding, input_y, input_right, input_pixels, ui_scale)
        if self._completion is None:
            self._draw_call_hint(
                x + padding, input_y, input_right, input_pixels, ui_scale)

        # The caret is a separate primitive. Blinking it never mutates the
        # input text, so GTA cannot flash or drop the complete command line.
        if int(time.monotonic() * 2.0) % 2 == 0:
            cursor_x = input_x + (self.cursor - view_start) * cell_width
            draw.rect(cursor_x, input_y + 1.0 * ui_scale,
                      max(1.5, 1.2 * ui_scale), 13.0 * ui_scale,
                      (92, 235, 158, 255))

        # A software pointer works in both exclusive fullscreen and windowed
        # mode because it follows GTA's relative mouse input.
        hud.draw_mono("↖", self.mouse_x - 3.0 * ui_scale,
                      self.mouse_y - 8.0 * ui_scale, 13.0 * ui_scale,
                      (92, 235, 158))

    @staticmethod
    def _line_color(line: str):
        if line.startswith("[PASS]"):
            return (105, 235, 135)
        if line.startswith("[FAIL]") or line.startswith("Error:"):
            return (255, 105, 105)
        if line.startswith("[RUN ") or line.startswith("[TEST]"):
            return (110, 190, 255)
        if line.startswith("Warning:"):
            return (255, 196, 92)
        return (230, 235, 240)

    def execute(self, source: str) -> Any:
        """Execute one console command or Python statement."""
        source = source.strip()
        if not source:
            return None
        slash = source.startswith("/")
        command_result = console_commands.execute(
            self._command_context, source[1:] if slash else source,
            slash=slash)
        if command_result is not NotImplemented:
            return command_result

        for warning in self._assignment_warnings(source):
            self.write("Warning: " + warning)

        captured = io.StringIO()
        try:
            with redirect_stdout(captured), redirect_stderr(captured):
                try:
                    code = compile(source, "<pysa-console>", "eval")
                except SyntaxError:
                    code = compile(source, "<pysa-console>", "exec")
                    exec(code, self.namespace, self.namespace)
                    return None
                return eval(code, self.namespace, self.namespace)
        finally:
            printed = captured.getvalue().rstrip("\r\n")
            if printed:
                self.write(printed)

    def _assignment_warnings(self, source: str) -> list[str]:
        """Find Python assignments that cannot update their game object."""
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError:
            return []
        warnings: list[str] = []
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
            elif isinstance(node, ast.AugAssign):
                targets.append(node.target)
            for target in targets:
                warning = self._assignment_target_warning(target)
                if warning and warning not in warnings:
                    warnings.append(warning)
        return warnings

    def _assignment_target_warning(self, target: ast.expr) -> Optional[str]:
        parts: list[str] = []
        value: ast.expr = target
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if not isinstance(value, ast.Name) or not parts:
            return None
        parts.reverse()
        root_name = value.id
        roots = self._root_completion_values()
        if root_name not in roots:
            return None
        current: Any = roots[root_name]
        path = root_name
        from .math3 import Vector3

        for index, part in enumerate(parts):
            try:
                descriptor = inspect.getattr_static(current, part)
            except AttributeError:
                return None
            path = f"{path}.{part}"
            final = index == len(parts) - 1
            if isinstance(descriptor, property):
                if final and descriptor.fset is None:
                    return f"{path} is read-only; it has no setter."
                getter = descriptor.fget
                annotation: Any = inspect.Signature.empty
                if getter is not None:
                    try:
                        annotation = get_type_hints(getter).get(
                            "return", inspect.Signature.empty)
                    except Exception:
                        annotation = inspect.Signature.empty
                annotation = self._concrete_annotation(annotation)
                if not final and annotation is Vector3:
                    suffix = ".".join(parts[index + 1:])
                    return (f"{path} returns a Vector3 snapshot; changing "
                            f".{suffix} will not move the game entity. "
                            f"Use: value = {path}; value.{suffix} = ...; "
                            f"{path} = value")
                if annotation is not inspect.Signature.empty:
                    current = annotation
                    continue
            try:
                current = getattr(current, part)
            except Exception:
                return None
        return None

    @staticmethod
    def _concrete_annotation(annotation: Any) -> Any:
        origin = get_origin(annotation)
        if origin in _UNION_ORIGINS:
            choices = [item for item in get_args(annotation)
                       if item is not type(None)]
            if len(choices) == 1:
                annotation = choices[0]
                origin = get_origin(annotation)
        return origin or annotation

    def _submit(self) -> None:
        source = self.input.strip()
        self.input = ""
        self.cursor = 0
        self.selection_anchor = None
        self._completion = None
        if not source:
            return
        self.write(">>> " + source)
        if not self.history or self.history[-1] != source:
            self.history.append(source)
            del self.history[:-self.history_limit]
        self._history_index = len(self.history)
        try:
            result = self.execute(source)
            if result is not None:
                self.write(repr(result))
        except Exception as exc:
            self.write(f"Error: {type(exc).__name__}: {exc}")
            _pysa.log(f"[pysa:console] {source}\n{traceback.format_exc()}")

    def _pressed(self, key: int) -> bool:
        down = bool(_pysa.key_down(int(key)))
        previous = self._down.get(int(key), False)
        self._down[int(key)] = down
        return down and not previous

    def _repeat_pressed(self, key: int, initial_delay: float = 0.35,
                        interval: float = 0.045) -> bool:
        """Edge trigger followed by normal keyboard-style held repetition."""
        key = int(key)
        down = bool(_pysa.key_down(key))
        previous = self._down.get(key, False)
        self._down[key] = down
        if not down:
            self._repeat_at.pop(key, None)
            return False
        now = time.monotonic()
        if not previous:
            self._repeat_at[key] = now + initial_delay
            return True
        next_at = self._repeat_at.get(key, now + initial_delay)
        if now >= next_at:
            self._repeat_at[key] = now + interval
            return True
        return False

    def _history_move(self, amount: int) -> None:
        if not self.history:
            return
        self._history_index = max(
            0, min(len(self.history), self._history_index + amount))
        self.input = ("" if self._history_index == len(self.history)
                      else self.history[self._history_index])
        self.cursor = len(self.input)
        self.selection_anchor = None

    def _selection_bounds(self) -> Optional[tuple[int, int]]:
        anchor = self.selection_anchor
        if anchor is None or anchor == self.cursor:
            return None
        return (min(anchor, self.cursor), max(anchor, self.cursor))

    def _delete_selection(self) -> bool:
        selection = self._selection_bounds()
        if selection is None:
            return False
        start, end = selection
        self.input = self.input[:start] + self.input[end:]
        self.cursor = start
        self.selection_anchor = None
        return True

    def _copy_selection(self) -> bool:
        output_text = self._output_selection_text()
        if output_text is not None:
            return bool(_pysa.clipboard_set(output_text))
        selection = self._selection_bounds()
        if selection is None:
            return False
        start, end = selection
        return bool(_pysa.clipboard_set(self.input[start:end]))

    def _clear_output_selection(self) -> None:
        self._output_selection_anchor = None
        self._output_selection_cursor = None
        self._output_selecting = False

    def _output_selection_bounds(self) -> Optional[
            tuple[tuple[int, int], tuple[int, int]]]:
        anchor = self._output_selection_anchor
        cursor = self._output_selection_cursor
        if anchor is None or cursor is None or anchor == cursor:
            return None
        return (anchor, cursor) if anchor < cursor else (cursor, anchor)

    def _output_selection_for_row(self, row: int,
                                  length: int) -> Optional[tuple[int, int]]:
        bounds = self._output_selection_bounds()
        if bounds is None:
            return None
        (start_row, start_col), (end_row, end_col) = bounds
        if row < start_row or row > end_row:
            return None
        start = start_col if row == start_row else 0
        end = end_col if row == end_row else length
        start = max(0, min(length, start))
        end = max(0, min(length, end))
        return (start, end) if start < end else None

    def _output_selection_text(self) -> Optional[str]:
        bounds = self._output_selection_bounds()
        if bounds is None:
            return None
        (start_row, start_col), (end_row, end_col) = bounds
        rows = self._wrapped_output_cache
        if not rows or start_row >= len(rows):
            return None
        end_row = min(end_row, len(rows) - 1)
        selected = rows[start_row:end_row + 1]
        if not selected:
            return None
        selected[0] = selected[0][start_col:]
        selected[-1] = selected[-1][:end_col]
        return "\n".join(selected)

    def _insert(self, text: str) -> None:
        if not text:
            return
        self._clear_output_selection()
        refresh_completion = self._completion is not None
        self._delete_selection()
        pairs = {"(": ")", "[": "]", "{": "}", "'": "'", '"': '"'}
        closing = set(pairs.values())
        if (len(text) == 1 and text in closing and
                self.cursor < len(self.input) and
                self.input[self.cursor] == text):
            self.cursor += 1
        elif len(text) == 1 and text in pairs:
            self.input = (self.input[:self.cursor] + text + pairs[text] +
                          self.input[self.cursor:])
            self.cursor += 1
        else:
            self.input = self.input[:self.cursor] + text + self.input[self.cursor:]
            self.cursor += len(text)
        if refresh_completion or self._should_auto_complete():
            self._complete()

    def _should_auto_complete(self) -> bool:
        """Whether the caret is editing a completable Python name."""
        if not self.auto_complete:
            return False
        if self.input.startswith("/"):
            return True
        target = self._completion_target()
        if target is None:
            return False
        _, fragment = target
        if self._last_top_level_dot(fragment) >= 0:
            return True
        return re.fullmatch(r"[A-Za-z_]\w*", fragment) is not None

    def _word_left(self) -> int:
        before = self.input[:self.cursor]
        match = re.search(r"\w+\W*$", before)
        return match.start() if match else max(0, self.cursor - 1)

    def _word_right(self) -> int:
        after = self.input[self.cursor:]
        match = re.search(r"\W*\w+", after)
        return (self.cursor + match.end() if match
                else min(len(self.input), self.cursor + 1))

    def _input_geometry(self) -> tuple[float, float, float, float, float]:
        screen_w, screen_h = hud.screen_size()
        ui_scale = max(1.0, min(float(screen_h) / 448.0, 4.0)) * self.scale
        width = float(screen_w) * 0.86
        height = float(screen_h) * 0.58
        x = (float(screen_w) - width) * 0.5
        y = float(screen_h) * 0.055
        padding = 9.0 * ui_scale
        input_height = 34.0 * ui_scale
        input_pixels = 15.0 * ui_scale
        input_y = y + height - input_height + 6.0 * ui_scale
        input_x = (x + padding +
                   hud.mono_text_width(self.prompt, input_pixels))
        return input_x, input_y, input_height, input_pixels, x + width - padding

    def _draw_completion_menu(self, menu_x: float, input_y: float,
                              input_right: float, pixels: float,
                              ui_scale: float) -> None:
        menu = self._completion
        if menu is None:
            self._completion_hitbox = None
            return
        max_rows = 7
        row_count = min(max_rows, len(menu.labels))
        first = min(max(0, menu.selected - max_rows + 1),
                    max(0, len(menu.labels) - max_rows))
        labels = menu.labels[first:first + row_count]
        cell = max(1.0, hud.mono_text_width("M", pixels))
        longest = max((len(label) for label in labels), default=1)
        available_width = input_right - menu_x
        width = min(available_width,
                    max(available_width * 0.78,
                        260.0 * ui_scale, (longest + 4) * cell))
        row_height = 20.0 * ui_scale
        footer_height = 36.0 * ui_scale
        height = row_count * row_height + footer_height + 4.0 * ui_scale
        x = menu_x
        y = input_y - height - 6.0 * ui_scale
        self._completion_hitbox = (
            x, y + 2.0 * ui_scale, width, row_height, first, row_count)
        draw.rect(x - 1.0 * ui_scale, y - 1.0 * ui_scale,
                  width + 2.0 * ui_scale, height + 2.0 * ui_scale,
                  (55, 66, 75, 255))
        draw.rect(x, y, width, height, (12, 17, 20, 255))
        for row, label in enumerate(labels):
            absolute = first + row
            row_y = y + 2.0 * ui_scale + row * row_height
            if absolute == menu.selected:
                draw.rect(x + 2.0 * ui_scale, row_y,
                          width - 4.0 * ui_scale, row_height,
                          (35, 92, 68, 255))
            elif absolute == self._completion_hover_row:
                draw.rect(x + 2.0 * ui_scale, row_y,
                          width - 4.0 * ui_scale, row_height,
                          (27, 36, 41, 255))
            available = max(1, int((width - 12.0 * ui_scale) // cell))
            shown = label if len(label) <= available else label[:max(1, available - 1)] + "~"
            self._draw_syntax(
                shown, x + 7.0 * ui_scale, row_y + 2.0 * ui_scale,
                pixels, cell,
                default_color=menu.colors[absolute])
        footer_y = y + 3.0 * ui_scale + row_count * row_height
        detail = menu.details[menu.selected]
        detail_pixels = pixels * 0.76
        detail_cell = max(1.0, hud.mono_text_width("M", detail_pixels))
        detail_columns = max(1, int((width - 14.0 * ui_scale) // detail_cell))
        if len(detail) > detail_columns:
            detail = detail[:max(1, detail_columns - 1)] + "~"
        self._draw_syntax(
            detail, x + 7.0 * ui_scale, footer_y,
            detail_pixels, detail_cell, default_color=(154, 190, 218))
        controls = (f"{menu.selected + 1}/{len(menu.labels)}  "
                    "UP/DOWN/PG  ENTER/TAB  ESC")
        hud.draw_mono(controls, x + 7.0 * ui_scale,
                      footer_y + 17.0 * ui_scale,
                      pixels * 0.68, (103, 210, 154))

    def _completion_popup_height(self, ui_scale: float) -> float:
        menu = self._completion
        if menu is None:
            return 0.0
        rows = min(7, len(menu.labels))
        return (rows * 20.0 * ui_scale + 36.0 * ui_scale +
                4.0 * ui_scale)

    def _draw_call_hint(self, left: float, input_y: float, right: float,
                        pixels: float, ui_scale: float) -> None:
        hint = self._call_hint()
        if hint is None:
            return
        width = right - left
        height = 56.0 * ui_scale
        top = input_y - height - 6.0 * ui_scale
        draw.rect(left - ui_scale, top - ui_scale,
                  width + 2.0 * ui_scale, height + 2.0 * ui_scale,
                  (55, 66, 75, 255))
        draw.rect(left, top, width, height, (13, 18, 22, 255))
        cell = max(1.0, hud.mono_text_width("M", pixels * 0.78))
        columns = max(1, int((width - 14.0 * ui_scale) // cell))

        signature = f"{hint.name}{hint.signature}"
        if len(signature) > columns:
            signature = signature[:max(1, columns - 1)] + "~"
        self._draw_syntax(
            signature, left + 7.0 * ui_scale, top + 4.0 * ui_scale,
            pixels * 0.78, cell, default_color=(180, 211, 234))

        parameter = (hint.parameters[hint.active]
                     if hint.parameters else None)
        prefix = f"ARG {hint.active + 1}/{len(hint.parameters)}  "
        hud.draw_mono(prefix, left + 7.0 * ui_scale,
                      top + 22.0 * ui_scale, pixels * 0.78,
                      (255, 196, 92))
        parameter_text = (str(parameter) if parameter is not None
                          else "NO PARAMETERS")
        parameter_columns = max(1, columns - len(prefix))
        if len(parameter_text) > parameter_columns:
            parameter_text = parameter_text[:max(1, parameter_columns - 1)] + "~"
        self._draw_syntax(
            parameter_text,
            left + 7.0 * ui_scale + len(prefix) * cell,
            top + 22.0 * ui_scale, pixels * 0.78, cell,
            default_color=(230, 213, 164))
        documentation = hint.documentation
        if len(documentation) > columns:
            documentation = documentation[:max(1, columns - 1)] + "~"
        hud.draw_mono(documentation, left + 7.0 * ui_scale,
                      top + 40.0 * ui_scale, pixels * 0.68,
                      (151, 162, 170))

    def _draw_settings_panel(self, x: float, y: float, width: float,
                             height: float, ui_scale: float) -> None:
        self._settings_hitboxes = []
        self._settings_slider_hitboxes = {}
        # Settings are a compact dialog inside the console instead of a form
        # stretched across the complete code surface.
        ui_scale = min(ui_scale, max(0.78, height / 350.0))
        panel_width = min(width, 620.0 * ui_scale)
        panel_height = min(height, 344.0 * ui_scale)
        panel_x = x + (width - panel_width) * 0.5
        panel_y = y + max(0.0, min(24.0 * ui_scale,
                                  (height - panel_height) * 0.28))
        border = max(1.0, ui_scale)
        padding = 18.0 * ui_scale
        title_pixels = 16.0 * ui_scale
        text_pixels = 12.0 * ui_scale
        hint_pixels = 9.0 * ui_scale

        draw.rect(panel_x - border, panel_y - border,
                  panel_width + border * 2.0,
                  panel_height + border * 2.0, ui.DARK_THEME.border)
        draw.rect(panel_x, panel_y, panel_width, panel_height,
                  (10, 14, 17, 248))
        draw.rect(panel_x, panel_y, 3.0 * ui_scale, panel_height,
                  ui.DARK_THEME.accent)
        hud.draw_mono("CONSOLE PREFERENCES", panel_x + padding,
                      panel_y + 15.0 * ui_scale, title_pixels,
                      ui.DARK_THEME.text)
        hud.draw_mono("Appearance, editor behavior, and retained output",
                      panel_x + padding, panel_y + 38.0 * ui_scale,
                      hint_pixels, ui.DARK_THEME.muted)
        saved = "SAVED LIVE"
        saved_width = hud.mono_text_width(saved, hint_pixels)
        hud.draw_mono(saved, panel_x + panel_width - padding - saved_width,
                      panel_y + 18.0 * ui_scale, hint_pixels,
                      ui.DARK_THEME.accent[:3])

        content_x = panel_x + 12.0 * ui_scale
        content_width = panel_width - 24.0 * ui_scale
        row_height = 44.0 * ui_scale
        row_y = panel_y + 81.0 * ui_scale
        control_right = panel_x + panel_width - padding
        control_left = panel_x + panel_width * 0.50

        def button(bx: float, by: float, bw: float, label: str,
                   action: str, active: bool = False) -> None:
            bounds = ui.Rect(bx, by, bw, 26.0 * ui_scale)
            hover = bounds.contains(self.mouse_x, self.mouse_y)
            ui.draw_button(bounds, label, hovered=hover, active=active,
                           pixels=text_pixels)
            self._settings_hitboxes.append(
                (bx, by, bw, bounds.height, action))

        def section(label: str) -> None:
            hud.draw_mono(label, content_x + 6.0 * ui_scale,
                          row_y - 16.0 * ui_scale, hint_pixels,
                          ui.DARK_THEME.accent[:3])

        def row_surface() -> None:
            draw.rect(content_x, row_y, content_width, row_height,
                      ui.DARK_THEME.surface)
            draw.rect(content_x, row_y + row_height - border,
                      content_width, border, (31, 42, 48, 235))

        def slider_row(label: str, hint: str, key: str, value: str) -> None:
            nonlocal row_y
            row_surface()
            hud.draw_mono(label, content_x + 12.0 * ui_scale,
                          row_y + 7.0 * ui_scale,
                          text_pixels, ui.DARK_THEME.text)
            hud.draw_mono(hint, content_x + 12.0 * ui_scale,
                          row_y + 26.0 * ui_scale,
                          hint_pixels, ui.DARK_THEME.muted)
            value_width = 52.0 * ui_scale
            value_x = control_right - value_width
            slider_x = control_left
            slider_width = max(80.0 * ui_scale,
                               value_x - slider_x - 12.0 * ui_scale)
            bounds = ui.Rect(slider_x, row_y + 8.0 * ui_scale,
                             slider_width, 28.0 * ui_scale)
            slider = self._settings_sliders[key]
            hovered = (bounds.contains(self.mouse_x, self.mouse_y) or
                       self._settings_dragging == key)
            ui.draw_slider(bounds, slider.fraction, hovered=hovered)
            value_text_width = hud.mono_text_width(value, text_pixels)
            hud.draw_mono(value,
                          value_x + (value_width - value_text_width) * 0.5,
                          row_y + 13.0 * ui_scale, text_pixels,
                          ui.DARK_THEME.accent[:3])
            self._settings_slider_hitboxes[key] = bounds
            row_y += row_height + 3.0 * ui_scale

        section("APPEARANCE")
        slider_row("Interface scale", "Size of console text and controls",
                   "scale", f"{self.scale:.2f}")
        slider_row("Surface opacity", "Transparency of the code workspace",
                   "opacity", f"{self.background_opacity:.2f}")

        row_y += 18.0 * ui_scale
        section("EDITOR")
        slider_row("Retained output", "Console history capacity in lines",
                   "history", str(self.output_limit))

        row_surface()
        hud.draw_mono("Automatic IntelliSense", content_x + 12.0 * ui_scale,
                      row_y + 7.0 * ui_scale, text_pixels,
                      ui.DARK_THEME.text)
        hud.draw_mono("Show suggestions while typing",
                      content_x + 12.0 * ui_scale,
                      row_y + 26.0 * ui_scale, hint_pixels,
                      ui.DARK_THEME.muted)
        toggle_width = 74.0 * ui_scale
        toggle_bounds = ui.Rect(control_right - toggle_width,
                                row_y + 9.0 * ui_scale,
                                toggle_width, 26.0 * ui_scale)
        ui.draw_toggle(toggle_bounds, self.auto_complete,
                       hovered=toggle_bounds.contains(self.mouse_x,
                                                      self.mouse_y),
                       pixels=text_pixels)
        self._settings_hitboxes.append((
            toggle_bounds.x, toggle_bounds.y, toggle_bounds.width,
            toggle_bounds.height, "autocomplete"))

        footer_y = panel_y + panel_height - 39.0 * ui_scale
        reset_width = 132.0 * ui_scale
        button(panel_x + padding, footer_y, reset_width,
               "RESET DEFAULTS", "reset")
        return_text = "ESC TO RETURN"
        return_width = hud.mono_text_width(return_text, hint_pixels)
        hud.draw_mono(return_text,
                      panel_x + panel_width - padding - return_width,
                      footer_y + 8.0 * ui_scale, hint_pixels,
                      ui.DARK_THEME.muted)

    def _set_setting_value(self, key: str, value: float) -> None:
        if key == "scale":
            value = float(value)
            if self.scale == value:
                return
            self.scale = value
        elif key == "opacity":
            value = float(value)
            if self.background_opacity == value:
                return
            self.background_opacity = value
        elif key == "history":
            size = int(value)
            if self.output_limit == size and self.history_limit == size:
                return
            self.output_limit = size
            self.history_limit = size
        else:
            raise KeyError(key)
        del self.output[:-self.output_limit]
        del self.history[:-self.history_limit]
        _save_console_settings(self)

    def _apply_setting_action(self, action: str) -> None:
        if action == "scale_down":
            self._settings_sliders["scale"].change(-1)
            return
        elif action == "scale_up":
            self._settings_sliders["scale"].change(1)
            return
        elif action == "opacity_down":
            self._settings_sliders["opacity"].change(-1)
            return
        elif action == "opacity_up":
            self._settings_sliders["opacity"].change(1)
            return
        elif action == "history_down":
            self._settings_sliders["history"].change(-1)
            return
        elif action == "history_up":
            self._settings_sliders["history"].change(1)
            return
        elif action == "autocomplete":
            self.auto_complete = not self.auto_complete
        elif action == "reset":
            self.scale = 1.0
            self.background_opacity = 0.69
            self.output_limit = 100
            self.history_limit = 100
            self.auto_complete = True
        del self.output[:-self.output_limit]
        del self.history[:-self.history_limit]
        _save_console_settings(self)

    def _wrapped_output(self, columns: int) -> list[str]:
        """Visual console rows, hard-limited to the panel's cell width."""
        rows: list[str] = []
        columns = max(1, int(columns))
        for line in self.output:
            if not line:
                rows.append("")
                continue
            rows.extend(textwrap.wrap(
                line, width=columns, replace_whitespace=False,
                drop_whitespace=False, break_long_words=True,
                break_on_hyphens=False) or [""])
        return rows

    @staticmethod
    def _syntax_spans(source: str, default_color=_CODE_DEFAULT
                      ) -> list[tuple[int, int, tuple[int, int, int]]]:
        if not source:
            return []
        parsed: list[tokenize.TokenInfo] = []
        try:
            stream = tokenize.generate_tokens(io.StringIO(source).readline)
            while True:
                parsed.append(next(stream))
        except (StopIteration, tokenize.TokenError, IndentationError):
            pass
        meaningful = [item for item in parsed if item.type not in (
            token_types.ENCODING, token_types.ENDMARKER,
            token_types.NEWLINE, tokenize.NL, token_types.INDENT,
            token_types.DEDENT)]
        builtin_values = __builtins__
        builtin_names = set(builtin_values if isinstance(builtin_values, dict)
                            else dir(builtin_values))
        spans: list[tuple[int, int, tuple[int, int, int]]] = []
        cursor = 0
        for index, item in enumerate(meaningful):
            if item.start[0] != 1:
                continue
            start, end = item.start[1], item.end[1]
            if start > cursor:
                spans.append((cursor, start, default_color))
            color = default_color
            if item.type == token_types.NAME:
                if keyword.iskeyword(item.string):
                    color = _CODE_KEYWORD
                elif item.string in builtin_names:
                    color = _CODE_BUILTIN
                else:
                    previous = meaningful[index - 1] if index else None
                    following = (meaningful[index + 1]
                                 if index + 1 < len(meaningful) else None)
                    if previous is not None and previous.string == ".":
                        color = _CODE_ATTRIBUTE
                    elif following is not None and following.string == "(":
                        color = _CODE_CALL
            elif item.type == token_types.STRING:
                color = _CODE_STRING
            elif item.type == token_types.NUMBER:
                color = _CODE_NUMBER
            elif item.type == token_types.COMMENT:
                color = _CODE_COMMENT
            elif item.type == token_types.OP:
                color = _CODE_OPERATOR
            elif item.type == token_types.ERRORTOKEN and item.string in "'\"":
                color = _CODE_STRING
            spans.append((start, min(len(source), end), color))
            cursor = max(cursor, end)
        if cursor < len(source):
            spans.append((cursor, len(source), default_color))
        return spans

    def _draw_syntax(self, source: str, x: float, y: float,
                     pixels: float, cell_width: float, *,
                     start: int = 0, end: Optional[int] = None,
                     clip=None, default_color=_CODE_DEFAULT) -> None:
        end = len(source) if end is None else min(len(source), end)
        for span_start, span_end, color in self._syntax_spans(
                source, default_color):
            visible_start = max(start, span_start)
            visible_end = min(end, span_end)
            if visible_start >= visible_end:
                continue
            hud.draw_mono(
                source[visible_start:visible_end],
                x + (visible_start - start) * cell_width, y,
                pixels, color, clip=clip)

    def _input_window(self, columns: int) -> tuple[int, str]:
        """Horizontal input viewport kept around the editing caret."""
        columns = max(1, int(columns))
        start = max(0, self.cursor - columns + 1)
        start = min(start, max(0, len(self.input) - columns))
        return start, self.input[start:start + columns]

    def _mouse_index(self, mouse_x: float) -> int:
        input_x, _, _, input_pixels, input_right = self._input_geometry()
        cell = max(1.0, hud.mono_text_width("M", input_pixels))
        columns = max(1, int((input_right - input_x) // cell) - 1)
        view_start, _ = self._input_window(columns)
        index = view_start + int((mouse_x - input_x) / cell + 0.5)
        return max(0, min(len(self.input), index))

    def _output_point(self) -> Optional[tuple[int, int, str]]:
        for left, right, top, bottom, line, row in self._output_hitboxes:
            if top <= self.mouse_y < bottom:
                column = int((self.mouse_x - left) / self._output_cell_width + 0.5)
                return row, max(0, min(len(line), column)), line
        if self._output_selecting and self._output_hitboxes:
            item = (self._output_hitboxes[0] if
                    self.mouse_y < self._output_hitboxes[0][2]
                    else self._output_hitboxes[-1])
            left, _, _, _, line, row = item
            column = int((self.mouse_x - left) / self._output_cell_width + 0.5)
            return row, max(0, min(len(line), column)), line
        return None

    def _set_scroll_from_mouse(self, mouse_y: float) -> None:
        hitbox = self._scrollbar_hitbox
        if hitbox is None or self._max_scroll <= 0:
            return
        _, track_y, _, track_height, _, thumb_height = hitbox
        travel = max(1.0, track_height - thumb_height)
        thumb_top = max(track_y, min(
            track_y + travel, mouse_y - self._scrollbar_drag_offset))
        ratio = (thumb_top - track_y) / travel
        value = round((1.0 - ratio) * self._max_scroll)
        self._scroll_offset = max(0, min(self._max_scroll, value))
        self._scroll_visual = float(self._scroll_offset)

    def _update_mouse(self) -> None:
        state = tuple(_pysa.mouse_state())
        dx, dy, down = state[:3]
        right_down = bool(state[3]) if len(state) > 3 else False
        wheel = int(state[4]) if len(state) > 4 else 0
        screen_w, screen_h = hud.screen_size()
        self.mouse_x = max(0.0, min(float(screen_w), self.mouse_x + float(dx)))
        self.mouse_y = max(0.0, min(float(screen_h), self.mouse_y + float(dy)))
        down = bool(down)

        if down and not self._mouse_was_down:
            if self._point_in_hitbox(self._close_hitbox):
                self._mouse_was_down = True
                self.close()
                return
            if self._point_in_hitbox(self._settings_hitbox):
                self.settings_visible = not self.settings_visible
                self._completion = None
                self._clear_output_selection()
                self._mouse_was_down = True
                return
            if self.settings_visible:
                for key, bounds in self._settings_slider_hitboxes.items():
                    if bounds.contains(self.mouse_x, self.mouse_y):
                        self._settings_dragging = key
                        self._settings_sliders[key].set_from_pointer(
                            self.mouse_x, bounds)
                        self._mouse_was_down = True
                        return
                for left, top, width, height, action in self._settings_hitboxes:
                    if (left <= self.mouse_x <= left + width and
                            top <= self.mouse_y <= top + height):
                        self._apply_setting_action(action)
                        self._mouse_was_down = True
                        return
        if self.settings_visible:
            if self._settings_dragging is not None:
                if down:
                    bounds = self._settings_slider_hitboxes.get(
                        self._settings_dragging)
                    if bounds is not None:
                        self._settings_sliders[
                            self._settings_dragging].set_from_pointer(
                                self.mouse_x, bounds)
                else:
                    self._settings_dragging = None
            self._mouse_was_down = down
            return

        scrollbar = self._scrollbar_hitbox
        if scrollbar is not None:
            bar_x, bar_y, bar_w, bar_height, thumb_y, thumb_height = scrollbar
            over_bar = (bar_x <= self.mouse_x <= bar_x + bar_w and
                        bar_y <= self.mouse_y <= bar_y + bar_height)
            over_thumb = (over_bar and thumb_y <= self.mouse_y <=
                          thumb_y + thumb_height)
            if down and not self._mouse_was_down and over_bar:
                self._scrollbar_dragging = True
                self._scrollbar_drag_offset = (
                    self.mouse_y - thumb_y if over_thumb
                    else thumb_height * 0.5)
                self._set_scroll_from_mouse(self.mouse_y)
                self._mouse_was_down = True
                return
            if self._scrollbar_dragging:
                if down:
                    self._set_scroll_from_mouse(self.mouse_y)
                    self._mouse_was_down = True
                    return
                self._scrollbar_dragging = False

        hitbox = self._completion_hitbox
        if self._completion is not None and hitbox is not None:
            box_x, box_y, box_w, row_height, first, row_count = hitbox
            over_rows = (box_x <= self.mouse_x <= box_x + box_w and
                         box_y <= self.mouse_y < box_y + row_count * row_height)
            if over_rows:
                row = int((self.mouse_y - box_y) // row_height)
                absolute = min(
                    len(self._completion.labels) - 1, first + row)
                clicked = down and not self._mouse_was_down
                self._completion_hover_row = absolute
                # Hover is visual only. Keyboard navigation retains the active
                # selection until the user explicitly clicks a mouse row.
                if clicked:
                    self._completion.selected = absolute
                    self._accept_completion()
                    self._mouse_was_down = down
                    return
            else:
                self._completion_hover_row = None
            if wheel:
                self._move_completion(-wheel)
                self._mouse_was_down = down
                return
        else:
            self._completion_hover_row = None
        if (self._completion is None or hitbox is None) and wheel:
            self._scroll_offset = max(
                0, min(max(self._max_scroll, len(self.output) - 1),
                       self._scroll_offset + wheel * 3))

        output_point = self._output_point()
        if down and not self._mouse_was_down and output_point is not None:
            row, column, line = output_point
            now = time.monotonic()
            double_click = (self._last_output_click is not None and
                            self._last_output_click[1] == row and
                            now - self._last_output_click[0] <= 0.35)
            self._last_output_click = (now, row)
            if double_click and line.startswith(">>> "):
                    self.input = next(
                        (source for source in reversed(self.history)
                         if (">>> " + source).startswith(line)),
                        line[4:])
                    self.cursor = len(self.input)
                    self.selection_anchor = None
                    self._completion = None
                    self._scroll_offset = 0
                    self._mouse_was_down = down
                    return
            self._output_selection_anchor = (row, column)
            self._output_selection_cursor = (row, column)
            self._output_selecting = True
            self.selection_anchor = None
        elif down and self._mouse_was_down and self._output_selecting:
            point = self._output_point()
            if point is not None:
                self._output_selection_cursor = (point[0], point[1])
        elif not down and self._mouse_was_down and self._output_selecting:
            self._output_selecting = False

        input_x, input_y, input_height, _, input_right = self._input_geometry()
        over_input = (input_x <= self.mouse_x <= input_right and
                      input_y - 4.0 <= self.mouse_y <=
                      input_y + input_height)
        index = self._mouse_index(self.mouse_x)

        if down and not self._mouse_was_down and over_input:
            self._completion = None
            self._clear_output_selection()
            selection = self._selection_bounds()
            if selection and selection[0] <= index <= selection[1]:
                self._drag_source = selection
                self._drag_target = index
                self._mouse_selecting = False
            else:
                self.selection_anchor = index
                self.cursor = index
                self._mouse_selecting = True
                self._drag_source = None
                self._drag_target = None
        elif down and self._mouse_was_down:
            if self._drag_source is not None:
                self._drag_target = index
            elif self._mouse_selecting:
                self.cursor = index
        elif not down and self._mouse_was_down:
            if self._drag_source is not None and self._drag_target is not None:
                self._drop_selection(self._drag_source, self._drag_target)
            elif self._mouse_selecting and self.selection_anchor == self.cursor:
                self.selection_anchor = None
            self._mouse_selecting = False
            self._drag_source = None
            self._drag_target = None

        self._mouse_was_down = down

    def _point_in_hitbox(self, hitbox: Optional[
            tuple[float, float, float, float]]) -> bool:
        if hitbox is None:
            return False
        left, top, width, height = hitbox
        return (left <= self.mouse_x <= left + width and
                top <= self.mouse_y <= top + height)

    def _drop_selection(self, selection: tuple[int, int], target: int) -> None:
        start, end = selection
        if start <= target <= end:
            return
        text = self.input[start:end]
        remaining = self.input[:start] + self.input[end:]
        if target > end:
            target -= end - start
        target = max(0, min(len(remaining), target))
        self.input = remaining[:target] + text + remaining[target:]
        self.selection_anchor = target
        self.cursor = target + len(text)

    def _complete(self) -> None:
        if self.input.startswith("/"):
            completion = console_commands.complete(
                self._command_context, self.input, self.cursor)
            if completion is None:
                self._completion = None
                return
            self._completion = _CompletionMenu(
                completion.start, completion.end, completion.candidates,
                completion.labels, completion.details,
                [_CODE_CALL for _ in completion.candidates])
            return
        target = self._completion_target()
        if target is None:
            self._completion = None
            return
        start, fragment = target
        dot = self._last_top_level_dot(fragment)
        call_hint = self._call_hint()
        if (call_hint is not None and dot < 0 and
                start >= call_hint.argument_start):
            used = set(re.findall(
                r"\b([A-Za-z_]\w*)\s*=",
                self.input[call_hint.argument_start:self.cursor]))
            parameters = [
                parameter for parameter in call_hint.parameters
                if parameter.name not in used and
                parameter.kind not in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD) and
                parameter.name.startswith(fragment)
            ]
            if parameters:
                labels = [parameter.name + "=" for parameter in parameters]
                details = [f"parameter {parameter}" for parameter in parameters]
                colors = [_CODE_ATTRIBUTE for _ in parameters]
                self._completion = _CompletionMenu(
                    start, self.cursor, labels[:], labels, details, colors)
                return
        try:
            if dot < 0:
                prefix = fragment
                values = self._root_completion_values()
                leaves = self._candidate_labels(values, prefix)
                candidates = leaves[:]
                details = [self._completion_detail(
                    leaf.rstrip("("), values[leaf.rstrip("(")])
                    for leaf in leaves]
                colors = [self._completion_color(values[leaf.rstrip("(")])
                          for leaf in leaves]
            else:
                receiver_text = fragment[:dot]
                prefix = fragment[dot + 1:]
                receiver = self._resolve_completion_receiver(receiver_text)
                names = {name: inspect.getattr_static(receiver, name)
                         for name in dir(receiver)
                         if name.startswith(prefix) and
                         (not name.startswith("_") or prefix.startswith("_"))}
                leaves = self._candidate_labels(names, prefix)
                candidates = [f"{receiver_text}.{leaf}" for leaf in leaves]
                details = [self._completion_detail(
                    leaf.rstrip("("), names[leaf.rstrip("(")])
                    for leaf in leaves]
                colors = [self._completion_color(names[leaf.rstrip("(")])
                          for leaf in leaves]
        except Exception:
            self._completion = None
            return
        if not candidates:
            self._completion = None
            return
        self._completion = _CompletionMenu(
            start, self.cursor, candidates, leaves, details, colors)

    def _call_hint(self) -> Optional[_CallHint]:
        if self.input.startswith("/"):
            slash_hint = console_commands.call_hint(self.input, self.cursor)
            if slash_hint is None:
                self._call_hint_cache = None
                return None
            command, signature, active = slash_hint
            key = (self.input, self.cursor)
            if (self._call_hint_cache is not None and
                    self._call_hint_cache.key == key):
                return self._call_hint_cache
            parameters = list(signature.parameters.values())
            self._call_hint_cache = _CallHint(
                key, command.handler, f"/{command.name}", signature,
                parameters, active, 0, command.description)
            return self._call_hint_cache
        key = (self.input, self.cursor)
        if self._call_hint_cache is not None and self._call_hint_cache.key == key:
            return self._call_hint_cache
        before = self.input[:self.cursor]
        stack: list[tuple[str, int]] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        quote = ""
        escaped = False
        for index, char in enumerate(before):
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in "'\"":
                quote = char
            elif char in "([{":
                stack.append((char, index))
            elif char in ")]}":
                if stack and stack[-1][0] == pairs[char]:
                    stack.pop()
        opening = next((position for kind, position in reversed(stack)
                        if kind == "("), None)
        if opening is None:
            self._call_hint_cache = None
            return None
        name_match = re.search(
            r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*$",
            before[:opening])
        if name_match is None:
            self._call_hint_cache = None
            return None
        function_name = name_match.group(1)
        try:
            function = self._resolve_completion_receiver(function_name)
            try:
                signature = inspect.signature(function, eval_str=True)
            except TypeError:  # ``eval_str`` was added after Python 3.8.
                signature = inspect.signature(function)
        except Exception:
            self._call_hint_cache = None
            return None
        parameters = list(signature.parameters.values())
        if parameters and parameters[0].name in ("self", "cls"):
            parameters = parameters[1:]
        argument_start = opening + 1
        arguments = before[argument_start:]
        active = self._active_argument_index(arguments)
        current = arguments.rsplit(",", 1)[-1]
        keyword_match = re.match(r"\s*([A-Za-z_]\w*)\s*=", current)
        if keyword_match:
            keyword_name = keyword_match.group(1)
            for index, parameter in enumerate(parameters):
                if parameter.name == keyword_name:
                    active = index
                    break
        if parameters:
            active = max(0, min(len(parameters) - 1, active))
        else:
            active = 0
        documentation = (inspect.getdoc(function) or "").split("\n", 1)[0]
        self._call_hint_cache = _CallHint(
            key, function, function_name, signature, parameters, active,
            argument_start, documentation)
        return self._call_hint_cache

    @staticmethod
    def _active_argument_index(arguments: str) -> int:
        depth = 0
        commas = 0
        quote = ""
        escaped = False
        for char in arguments:
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in "'\"":
                quote = char
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                commas += 1
        return commas

    def _completion_target(self) -> Optional[tuple[int, str]]:
        before = self.input[:self.cursor]
        depth = 0
        start = 0
        delimiters = set("=;+*/%<>!&|^~,:\\")
        for index in range(len(before) - 1, -1, -1):
            char = before[index]
            if char in ")]}":
                depth += 1
            elif char in "([{":
                if depth:
                    depth -= 1
                else:
                    start = index + 1
                    break
            elif depth == 0 and (char.isspace() or char in delimiters):
                start = index + 1
                break
        fragment = before[start:]
        if not fragment:
            return start, fragment
        if not re.match(r"[A-Za-z_]", fragment):
            return None
        return start, fragment

    @staticmethod
    def _last_top_level_dot(fragment: str) -> int:
        depth = 0
        quote = ""
        escaped = False
        result = -1
        for index, char in enumerate(fragment):
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                continue
            if char in "'\"":
                quote = char
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            elif char == "." and depth == 0:
                result = index
        return result

    def _root_completion_values(self) -> dict[str, Any]:
        builtins = self.namespace.get("__builtins__", {})
        values = dict(builtins if isinstance(builtins, dict)
                      else vars(builtins))
        values.update(self.namespace)
        values.update({word: None for word in keyword.kwlist})
        for name in dir(self):
            if name.startswith("_command_"):
                values[name[len("_command_"):]] = getattr(self, name)
        return values

    @staticmethod
    def _candidate_labels(values: dict[str, Any], prefix: str) -> list[str]:
        labels: list[str] = []
        for name in sorted(values):
            if not name.startswith(prefix):
                continue
            if name.startswith("_") and not prefix.startswith("_"):
                continue
            labels.append(name + ("(" if callable(values[name]) else ""))
        return labels

    @staticmethod
    def _completion_detail(name: str, value: Any) -> str:
        if isinstance(value, property):
            getter = value.fget
            if getter is not None:
                try:
                    result = get_type_hints(getter).get("return")
                    if result is not None:
                        return (f"property {name}: "
                                f"{DeveloperConsole._type_display(result)}")
                except Exception:
                    pass
            return f"property {name}"
        if callable(value):
            kind = "class" if inspect.isclass(value) else "function"
            try:
                return f"{kind} {name}{inspect.signature(value)}"
            except (TypeError, ValueError):
                return f"{kind} {name}(...)"
        if isinstance(value, Enum):
            return f"enum {type(value).__name__}.{name} = {value.value}"
        if inspect.ismodule(value):
            return f"module {value.__name__}"
        return f"value {name}: {type(value).__name__}"

    @staticmethod
    def _completion_color(value: Any) -> tuple[int, int, int]:
        if isinstance(value, property):
            return _CODE_ATTRIBUTE
        if isinstance(value, Enum):
            return _CODE_ENUM
        if inspect.isclass(value):
            return _CODE_CLASS
        if inspect.ismodule(value):
            return _CODE_MODULE
        if callable(value):
            return _CODE_CALL
        if isinstance(value, (int, float, complex, bool)):
            return _CODE_NUMBER
        if isinstance(value, str):
            return _CODE_STRING
        return _CODE_DEFAULT

    @staticmethod
    def _type_display(annotation: Any) -> str:
        origin = get_origin(annotation)
        if origin in _UNION_ORIGINS:
            return " | ".join(DeveloperConsole._type_display(item)
                              for item in get_args(annotation))
        if origin is not None:
            arguments = get_args(annotation)
            base = getattr(origin, "__name__", str(origin).replace("typing.", ""))
            if arguments:
                return (f"{base}[" + ", ".join(
                    DeveloperConsole._type_display(item)
                    for item in arguments) + "]")
            return base
        if annotation is type(None):
            return "None"
        if isinstance(annotation, type):
            return annotation.__name__
        return str(annotation).replace("typing.", "")

    def _resolve_completion_receiver(self, source: str) -> Any:
        node = ast.parse(source, mode="eval").body

        def resolve(value: ast.AST) -> Any:
            if isinstance(value, ast.Name):
                roots = self._root_completion_values()
                return roots[value.id]
            if isinstance(value, ast.Attribute):
                return getattr(resolve(value.value), value.attr)
            if isinstance(value, ast.Call):
                function = resolve(value.func)
                if inspect.isclass(function):
                    return function
                hints = get_type_hints(function)
                annotation = hints.get("return", inspect.Signature.empty)
                if annotation is inspect.Signature.empty:
                    raise TypeError("call has no return annotation")
                origin = get_origin(annotation)
                if origin in _UNION_ORIGINS:
                    choices = [item for item in get_args(annotation)
                               if item is not type(None)]
                    if len(choices) == 1:
                        annotation = choices[0]
                        origin = get_origin(annotation)
                return origin or annotation
            if isinstance(value, ast.Subscript):
                # Indexing is evaluated only when the base is already a live
                # value; calls themselves are never executed by completion.
                base = resolve(value.value)
                index = ast.literal_eval(value.slice)
                return base[index]
            raise TypeError("unsupported completion expression")

        return resolve(node)

    def _move_completion(self, amount: int) -> None:
        if self._completion is not None:
            count = len(self._completion.candidates)
            self._completion.selected = (
                self._completion.selected + amount) % count

    def _exact_completion_can_submit(self) -> bool:
        """Whether Enter can execute without accepting an identical result."""
        menu = self._completion
        if menu is None:
            return False
        current = self.input[menu.start:menu.end]
        if current not in menu.candidates:
            return False
        if self.input.startswith("/"):
            return True
        try:
            compile(self.input, "<console>", "eval")
        except SyntaxError:
            try:
                compile(self.input, "<console>", "exec")
            except SyntaxError:
                return False
        return True

    def _accept_completion(self) -> None:
        menu = self._completion
        if menu is None:
            return
        self._replace_completion(
            menu.start, menu.end, menu.candidates[menu.selected])
        self._completion = None

    def _replace_completion(self, start: int, end: int, text: str) -> None:
        self.input = self.input[:start] + text + self.input[end:]
        self.cursor = start + len(text)
        self.selection_anchor = None


_current_console: Optional[DeveloperConsole] = None
_config_path: Optional[str] = None


def _save_console_settings(console: DeveloperConsole) -> None:
    if not _config_path:
        return
    values = {
        "ConsoleScale": f"{console.scale:.2f}",
        "ConsoleBackgroundOpacity": f"{console.background_opacity:.2f}",
        "ConsoleHistoryLimit": str(console.output_limit),
        "ConsoleAutoComplete": "1" if console.auto_complete else "0",
    }
    for key, value in values.items():
        _write_ini("PyAndreas", key, value, _config_path)


def _install_builtin(base_dir: str) -> DeveloperConsole:
    global _config_path, _current_console
    if _current_console is None:
        _current_console = DeveloperConsole(_register_handlers=False)
    _config_path = os.path.join(base_dir, "PyAndreas.ini")
    parser = configparser.ConfigParser()
    # utf-8-sig accepts both regular UTF-8 and files written with a BOM by
    # Windows tools such as PowerShell and Notepad.
    parser.read(_config_path, encoding="utf-8-sig")
    _current_console.enabled = parser.getboolean(
        "PyAndreas", "DeveloperMode", fallback=False)
    _current_console.scale = max(0.60, min(1.80, parser.getfloat(
        "PyAndreas", "ConsoleScale", fallback=1.0)))
    if parser.has_option("PyAndreas", "ConsoleBackgroundOpacity"):
        opacity = parser.getfloat(
            "PyAndreas", "ConsoleBackgroundOpacity", fallback=0.69)
    else:
        opacity = parser.getint(
            "PyAndreas", "ConsoleBackgroundAlpha", fallback=176) / 255.0
    _current_console.background_opacity = max(0.0, min(1.0, opacity))
    _current_console.output_limit = max(25, min(500, parser.getint(
        "PyAndreas", "ConsoleHistoryLimit", fallback=100)))
    _current_console.history_limit = _current_console.output_limit
    _current_console.auto_complete = parser.getboolean(
        "PyAndreas", "ConsoleAutoComplete", fallback=True)
    return _current_console


def _set_developer_mode(enabled: bool) -> None:
    console = _current_console
    if console is None:
        return
    console.enabled = bool(enabled)
    if not console.enabled:
        console.close()


def _update_builtin() -> None:
    if _current_console is not None:
        _current_console.update()


def _draw_builtin() -> None:
    if _current_console is not None:
        _current_console.draw()


def _suspend_builtin() -> None:
    if _current_console is not None:
        _current_console.suspend_for_frontend()


def _shutdown_builtin() -> None:
    if _current_console is not None:
        _current_console.close()


def developer_console() -> DeveloperConsole:
    """Return the console instance owned by the PyAndreas runtime."""
    if _current_console is None:
        raise RuntimeError("the PyAndreas developer console is not ready")
    return _current_console
