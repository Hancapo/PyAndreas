import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

from pysa import ui
from pysa import ui_document


class DeclarativeUiTests(unittest.TestCase):
    def test_rounded_fill_uses_curved_scanline_bands(self):
        calls = []

        with mock.patch.object(ui_document.draw, "rect",
                               side_effect=lambda x, y, w, h, color:
                               calls.append((x, y, w, h))):
            ui_document._rounded_fill(
                ui.Rect(0, 0, 24, 16), (20, 30, 40, 255),
                ui.Rect(0, 0, 24, 16), 6)

        top_bands = sorted((call for call in calls if call[1] < 6),
                           key=lambda call: call[1])
        self.assertGreaterEqual(len(top_bands), 3)
        self.assertLess(top_bands[0][2], top_bands[-1][2])
        self.assertTrue(any(x == 0 and width == 24
                            for x, _, width, _ in calls))

    def test_binding_reads_and_writes_nested_objects_and_mappings(self):
        state = SimpleNamespace(options={"volume": 0.5})
        value = ui.bind(state, "options.volume")

        self.assertEqual(value.get(), 0.5)
        value.set(0.75)

        self.assertEqual(state.options["volume"], 0.75)
        self.assertTrue(value.writable)

    def test_read_only_binding_reports_assignment_clearly(self):
        value = ui.read(lambda: 42, name="answer")

        self.assertEqual(value.get(), 42)
        self.assertFalse(value.writable)
        with self.assertRaisesRegex(AttributeError, "read-only"):
            value.set(7)

    def test_python_view_supports_controls_pages_and_dynamic_state(self):
        state = SimpleNamespace(enabled=False, power=1.0, weather="sunny")
        actions = []
        page = ui.Page("Advanced", ui.Button("Reset", lambda: actions.append("reset")))
        view = ui.View(
            "Tools",
            ui.Button("Repair", lambda: actions.append("repair")),
            ui.Toggle("Enabled", ui.bind(state, "enabled")),
            ui.SliderItem("Power", 0.5, 2.0, 0.1,
                          ui.bind(state, "power")),
            ui.Choice("Weather", ("sunny", "rain"),
                      ui.bind(state, "weather")),
            page,
            capture_input=False,
            auto=False,
        )

        view.open()
        view.draw()
        self.assertEqual(len(view._hits), 5)

        view.activate()
        view.move(1)
        view.activate()
        view.move(1)
        view.adjust(2)
        view.move(1)
        view.adjust(1)
        view.move(1)
        view.activate()
        view.draw()

        self.assertEqual(actions, ["repair"])
        self.assertTrue(state.enabled)
        self.assertAlmostEqual(state.power, 1.2)
        self.assertEqual(state.weather, "rain")
        self.assertEqual(view.current_title, "Advanced")
        self.assertEqual(len(view._hits), 1)

        view.activate()
        view.back()
        self.assertEqual(actions, ["repair", "reset"])
        self.assertEqual(view.current_title, "Tools")

    def test_pui_loader_resolves_only_explicit_actions_and_state(self):
        settings = SimpleNamespace(enabled=False, power=1.0,
                                   weather="SUNNY", title="Live settings")
        calls = []
        markup = """\
<Menu title="Vehicle Tools" toggle-key="F6" anchor="top-right"
      width="400" capture-input="false">
    <Text value="{settings.title}" style="heading" />
    <Button text="Repair" on-click="repair" style="primary" />
    <Toggle text="Invincible" value="{settings.enabled}" />
    <Slider text="Engine power" value="{settings.power}"
            min="0.5" max="3.0" step="0.1" format=".1f" />
    <Choice text="Weather" value="{settings.weather}"
            options="{weather_options}" />
    <Page text="Advanced">
        <Button text="Reset" on-click="reset" />
    </Page>
</Menu>
"""
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "vehicle_tools.pui"
            source.write_text(markup, encoding="utf-8")
            view = ui.load(
                source,
                actions={"repair": lambda: calls.append("repair"),
                         "reset": lambda: calls.append("reset")},
                state={"settings": settings,
                       "weather_options": ("SUNNY", "RAINY")},
                styles={
                    "heading": ui.ElementStyle(pixels=18),
                    "primary": ui.ElementStyle(background=(20, 80, 60, 255)),
                },
                auto=False,
            )

        self.assertEqual(view.title, "Vehicle Tools")
        self.assertEqual(view.toggle_key, 0x75)
        self.assertIs(view.anchor, ui.Anchor.TOP_RIGHT)
        self.assertFalse(view.capture_input)
        self.assertEqual(len(view.children), 6)

        view.open()
        view.draw()
        view.activate()
        view.move(1)
        view.activate()
        self.assertEqual(calls, ["repair"])
        self.assertTrue(settings.enabled)

    def test_pui_rejects_expressions_unknown_actions_and_misspelled_attributes(self):
        cases = (
            ('<Menu><Toggle text="X" value="{settings.value + 1}" /></Menu>',
             "must be a {state.path} binding"),
            ('<Menu><Button text="X" on-click="missing" /></Menu>',
             "unknown action"),
            ('<Menu><Button text="X" on-click="ok" enabeld="true" /></Menu>',
             "unknown attribute"),
        )
        for markup, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / "invalid.pui"
                source.write_text(markup, encoding="utf-8")
                with self.assertRaisesRegex(ui.MarkupError, message):
                    ui.load(source, actions={"ok": lambda: None},
                            state={"settings": SimpleNamespace(value=1)},
                            auto=False)

    def test_mouse_hover_is_visual_until_click(self):
        calls = []
        view = ui.View(
            "Mouse",
            ui.Button("First", lambda: calls.append("first")),
            ui.Button("Second", lambda: calls.append("second")),
            capture_input=False, auto=False,
        )
        view.open()
        view.draw()
        self.assertIsNone(view._focus_source)
        second = view._hits[1].bounds
        view._mouse_x = second.x + second.width * 0.5
        view._mouse_y = second.y + second.height * 0.5

        with mock.patch.object(ui_document._pysa, "mouse_state",
                               return_value=(0, 0, False, False, 0)):
            view._update_mouse()

        self.assertEqual(view._hovered, 1)
        self.assertEqual(view.selected, 0)

        with mock.patch.object(ui_document._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)):
            view._update_mouse()

        self.assertEqual(view.selected, 1)
        self.assertEqual(calls, ["second"])

    def test_captured_view_consumes_pointer_only_over_its_panel(self):
        view = ui.View("Pointer", ui.Button("Action", lambda: None),
                       capture_input=True, auto=False)

        with mock.patch.object(ui_document, "_capture_menu_input") as capture, \
                mock.patch.object(ui_document,
                                  "_set_menu_pointer_consumed") as consumed:
            view.open()
            view.draw()
            capture.assert_called_once_with(True)
            self.assertIsNotNone(view._panel_bounds)

            panel = view._panel_bounds
            assert panel is not None
            view._mouse_x = panel.x + panel.width * 0.5
            view._mouse_y = panel.y + panel.height * 0.5
            view._update_pointer_capture()
            consumed.assert_called_with(True)

            view._mouse_x = 0.0
            view._mouse_y = 0.0
            view._update_pointer_capture()
            consumed.assert_called_with(False)

            view.close()
            capture.assert_called_with(False)
            consumed.assert_called_with(False)

    def test_mouse_page_click_is_not_replayed_as_controller_back(self):
        page = ui.Page("Advanced", ui.Button("Done", lambda: None))
        view = ui.View("Root", page, capture_input=True, auto=False)
        view.open()
        view.draw()
        bounds = view._hits[0].bounds
        view._mouse_x = bounds.x + bounds.width * 0.5
        view._mouse_y = bounds.y + bounds.height * 0.5

        def controller_state(button):
            return int(button) == int(ui_document.BUTTON.CIRCLE)

        with mock.patch.object(ui_document._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)), \
                mock.patch.object(ui_document._pysa, "key_down",
                                  return_value=False), \
                mock.patch.object(ui_document._pysa,
                                  "captured_button_down",
                                  side_effect=controller_state):
            view.update()

        self.assertTrue(view.visible)
        self.assertEqual(view.current_title, "Advanced")

    def test_right_click_navigates_back_one_page_per_press(self):
        page = ui.Page("Advanced", ui.Button("Done", lambda: None))
        view = ui.View("Root", page, capture_input=True, auto=False)
        view.open()
        view.draw()
        view.activate()
        self.assertEqual(view.current_title, "Advanced")

        with mock.patch.object(ui_document._pysa, "mouse_state",
                               return_value=(0, 0, False, True, 0)), \
                mock.patch.object(ui_document._pysa, "key_down",
                                  return_value=False), \
                mock.patch.object(ui_document._pysa,
                                  "captured_button_down",
                                  return_value=False):
            view.update()
            self.assertEqual(view.current_title, "Root")
            self.assertTrue(view.visible)
            # Holding right click must not immediately close the root view.
            view.update()

        self.assertTrue(view.visible)

    def test_keyboard_focus_moves_visual_selection_off_first_control(self):
        view = ui.View(
            "Focus",
            ui.Button("First", lambda: None),
            ui.Button("Second", lambda: None),
            capture_input=False,
            auto=False,
        )
        view.open()
        view.draw()
        view._focus_source = "keyboard"
        view.move(1)

        states = []
        with mock.patch.object(view, "draw_control_surface",
                               wraps=view.draw_control_surface) as surface:
            view.draw()
            states = [(call.args[1], call.args[2])
                      for call in surface.call_args_list]

        self.assertEqual(states, [(False, False), (True, False)])

    def test_hover_capture_restores_the_previous_player_control_state(self):
        controls = SimpleNamespace(enabled=True)
        fake_player = SimpleNamespace(controls=controls)
        view = ui.View("Controls", capture_input=True, auto=False)

        with mock.patch("pysa.player.player", fake_player):
            view._set_gameplay_controls_blocked(True)
            self.assertFalse(controls.enabled)

            view._set_gameplay_controls_blocked(False)
            self.assertTrue(controls.enabled)

            controls.enabled = False
            view._set_gameplay_controls_blocked(True)
            view._set_gameplay_controls_blocked(False)
            self.assertFalse(controls.enabled)

    def test_large_view_scrolls_to_keep_keyboard_selection_visible(self):
        view = ui.View(
            "Long",
            *(ui.Button(f"Item {index}", lambda: None)
              for index in range(12)),
            max_height=180, capture_input=False, auto=False,
        )
        view.open()
        view.draw()

        self.assertGreater(view._max_scroll, 0)
        for _ in range(9):
            view.move(1)
            view.draw()

        self.assertEqual(view.selected, 9)
        self.assertGreater(view.scroll, 0)

    def test_held_toggle_key_opens_view_only_once(self):
        view = ui.View("Toggle", toggle_key=ui_document.KEY.F6,
                       capture_input=False, auto=False)

        with mock.patch.object(ui_document._pysa, "key_down",
                               side_effect=lambda key: key == ui_document.KEY.F6), \
                mock.patch.object(ui_document.pad, "pressed", return_value=False):
            view.update()
            self.assertTrue(view.visible)
            view.update()
            self.assertTrue(view.visible)

        with mock.patch.object(ui_document._pysa, "key_down", return_value=False), \
                mock.patch.object(ui_document.pad, "pressed", return_value=False):
            view.update()
        with mock.patch.object(ui_document._pysa, "key_down",
                               side_effect=lambda key: key == ui_document.KEY.F6), \
                mock.patch.object(ui_document.pad, "pressed", return_value=False):
            view.update()

        self.assertFalse(view.visible)


if __name__ == "__main__":
    unittest.main()
