import unittest
from unittest import mock
from types import SimpleNamespace

from pysa import (_mock, _runtime, console_command, console_commands,
                  dev_console, testing)
from pysa.dev_console import DeveloperConsole
from pysa.keys import KEY
from pysa.player import PlayerControls


class DeveloperToolsTests(unittest.TestCase):
    def setUp(self):
        _runtime._clear_registries()
        _runtime._reload_requested = False
        _mock._reset()

    def tearDown(self):
        _runtime._reload_requested = False
        _runtime._clear_registries()

    def test_console_evaluates_persistent_python_and_builtin_commands(self):
        console = DeveloperConsole()

        self.assertEqual(console.execute("1 + 2"), 3)
        console.execute("answer = 42")
        self.assertEqual(console.execute("answer"), 42)

        self.assertIsNone(console.execute('print("hola")'))
        self.assertIn("hola", console.output)

        console.execute("reload")
        self.assertTrue(_runtime._reload_requested)
        self.assertIn("Script reload queued...", console.output)
        self.assertIs(console.execute("blips"), console.namespace["pysa"].blips)
        self.assertIs(console.execute("camera"), console.namespace["pysa"].camera)

    def test_slash_commands_support_help_aliases_and_readable_errors(self):
        console = DeveloperConsole()

        console.execute("/help vehicle")
        self.assertTrue(any("/vehicle <model>" in line
                            for line in console.output))
        console.execute("/restart")
        self.assertTrue(_runtime._reload_requested)

        with self.assertRaisesRegex(
                console_commands.CommandError, "Did you mean /vehicle"):
            console.execute("/vehcle")
        with self.assertRaisesRegex(
                console_commands.CommandError, "Usage: /wanted <level>"):
            console.execute("/wanted")

    def test_custom_slash_commands_convert_typed_arguments(self):
        received = []

        @console_command("demo", aliases=("d",),
                         description="A custom command")
        def demo(count: int, enabled: bool = True):
            received.append((count, enabled))
            return "done"

        console = DeveloperConsole()
        self.assertEqual(console.execute("/demo 3 off"), "done")
        console.execute("/d 4 on")
        self.assertEqual(received, [(3, False), (4, True)])
        self.assertIn("demo", console_commands.command_names())

    def test_slash_completion_covers_commands_and_arguments(self):
        console = DeveloperConsole()
        console.input = "/ve"
        console.cursor = len(console.input)
        console._complete()
        self.assertIsNotNone(console._completion)
        self.assertIn("/vehicle", console._completion.labels)

        console.input = "/vehicle inf"
        console.cursor = len(console.input)
        console._complete()
        self.assertIsNotNone(console._completion)
        self.assertIn("infernus", console._completion.labels)

        console.input = "/weather sun"
        console.cursor = len(console.input)
        console._complete()
        self.assertIsNotNone(console._completion)
        self.assertIn("sunny_la", console._completion.labels)

        self.assertTrue(console_commands.can_execute_without_arguments(
            "/heal"))
        self.assertFalse(console_commands.can_execute_without_arguments(
            "/wanted"))

    def test_slash_command_cleanup_owns_spawned_resources(self):
        cleaned = []

        class Resource:
            def delete(self):
                cleaned.append("deleted")

        console = DeveloperConsole()
        console._command_context.track(Resource())
        console.execute("/cleanup")

        self.assertEqual(cleaned, ["deleted"])
        self.assertIn("Cleaned up 1 resource(s)", console.output)

    def test_gravity_command_accepts_metres_per_second_squared(self):
        console = DeveloperConsole()
        with mock.patch("pysa.world.set_gravity") as set_gravity:
            console.execute("/gravity 9.81")
            set_gravity.assert_called_once_with(0.008)

        with mock.patch("pysa.world.set_gravity") as set_gravity:
            console.execute("/gravity 1")
            self.assertAlmostEqual(
                set_gravity.call_args.args[0], 0.008 / 9.81)
        self.assertTrue(any("Gravity set to 1 m/s^2" in line
                            for line in console.output))

    def test_failed_script_import_rolls_back_console_commands(self):
        checkpoint = console_commands._checkpoint()

        @console_command("temporary")
        def temporary():
            return None

        self.assertIn("temporary", console_commands.command_names())
        console_commands._rollback(checkpoint)
        self.assertNotIn("temporary", console_commands.command_names())

    def test_console_warns_about_snapshot_and_read_only_assignments(self):
        from pysa.math3 import Vector3

        class Target:
            def __init__(self):
                self._pos = Vector3(1, 2, 3)

            @property
            def pos(self) -> Vector3:
                return Vector3.of(self._pos)

            @pos.setter
            def pos(self, value) -> None:
                self._pos = Vector3.of(value)

            @property
            def name(self) -> str:
                return "target"

        console = DeveloperConsole(namespace={
            "target": Target(), "__builtins__": __builtins__})

        snapshot = console._assignment_warnings("target.pos.x += 1")
        readonly = console._assignment_warnings("target.name = 'new'")
        self.assertIn("Vector3 snapshot", snapshot[0])
        self.assertIn("target.pos = value", snapshot[0])
        self.assertEqual(readonly, [
            "target.name is read-only; it has no setter."])

        console.execute("target.pos.x += 1")
        self.assertTrue(any(line.startswith("Warning:")
                            for line in console.output))

    def test_console_keyboard_input_is_edge_triggered(self):
        console = DeveloperConsole()
        console.visible = True

        with mock.patch("pysa.dev_console._pysa.key_down",
                        side_effect=lambda key: key == KEY.A), \
                mock.patch("pysa.dev_console._translate_key",
                           return_value="a"):
            console.update()
            console.update()
        self.assertEqual(console.input, "a")

        with mock.patch("pysa.dev_console._pysa.key_down", return_value=False):
            console.update()
        with mock.patch("pysa.dev_console._pysa.key_down",
                        side_effect=lambda key: key == KEY.BACKSPACE):
            console.update()
        self.assertEqual(console.input, "")

    def test_tab_completes_builtins_and_trailing_dot_attributes(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, alpine=2, beta=3),
            "__builtins__": __builtins__,
        })
        console.input = "pri"
        console.cursor = len(console.input)
        console._complete()
        self.assertEqual(console.input, "pri")
        self.assertIsNotNone(console._completion)
        console._accept_completion()
        self.assertEqual(console.input, "print(")

        console.input = "thing."
        console.cursor = len(console.input)
        console._completion = None
        console._complete()
        self.assertEqual(console.input, "thing.")
        self.assertIsNotNone(console._completion)
        self.assertEqual(console._completion.labels,
                         ["alpha", "alpine", "beta"])

    def test_completion_box_navigates_and_accepts_candidates(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, alpine=2),
            "__builtins__": __builtins__,
        })
        console.input = "thing.al"
        console.cursor = len(console.input)

        console._complete()
        self.assertIsNotNone(console._completion)
        console._move_completion(1)
        console._accept_completion()
        self.assertEqual(console.input, "thing.alpine")

    def test_completion_popup_updates_while_typing(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, beta=2),
            "__builtins__": __builtins__,
        })
        console.visible = True
        console.input = "thing."
        console.cursor = len(console.input)
        console._complete()

        with mock.patch.object(dev_console._pysa, "key_down",
                               return_value=False):
            console.update()
        self.assertIsNotNone(console._completion)

        console._insert("a")
        self.assertEqual(console.input, "thing.a")
        self.assertIsNotNone(console._completion)
        self.assertEqual(console._completion.labels, ["alpha"])

        console._insert("z")
        self.assertIsNone(console._completion)

    def test_completion_popup_updates_after_backspace(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, alpine=2, beta=3),
            "__builtins__": __builtins__,
        })
        console.visible = True
        console.input = "thing.alph"
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None
        self.assertEqual(console._completion.labels, ["alpha"])

        with mock.patch.object(dev_console._pysa, "key_down",
                               side_effect=lambda key: key == KEY.BACKSPACE):
            console.update()
        self.assertEqual(console.input, "thing.alp")
        self.assertIsNotNone(console._completion)
        self.assertEqual(console._completion.labels, ["alpha", "alpine"])

    def test_member_completion_recovers_after_temporary_no_match(self):
        console = DeveloperConsole()
        console.visible = True
        console.input = "player.pe"
        console.cursor = len(console.input)
        console._complete()
        self.assertIsNotNone(console._completion)

        console._insert("z")
        self.assertEqual(console.input, "player.pez")
        self.assertIsNone(console._completion)

        console._down.clear()
        with mock.patch.object(dev_console._pysa, "key_down",
                               side_effect=lambda key: key == KEY.BACKSPACE):
            console.update()
        self.assertEqual(console.input, "player.pe")
        self.assertIsNotNone(console._completion)
        self.assertIn("ped", console._completion.labels)
        self.assertIn("perks", console._completion.labels)

    def test_holding_down_repeats_completion_navigation(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, beta=2, gamma=3),
            "__builtins__": __builtins__,
        })
        console.visible = True
        console.input = "thing."
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None

        with mock.patch.object(dev_console._pysa, "key_down",
                               side_effect=lambda key: key == KEY.DOWN), \
                mock.patch("pysa.dev_console.time.monotonic") as clock:
            clock.return_value = 0.0
            console.update()
            self.assertEqual(console._completion.selected, 1)
            clock.return_value = 0.2
            console.update()
            self.assertEqual(console._completion.selected, 1)
            clock.return_value = 0.33
            console.update()
            self.assertEqual(console._completion.selected, 2)
            clock.return_value = 0.42
            console.update()
            self.assertEqual(console._completion.selected, 0)

    def test_completion_popup_reserves_output_space(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(**{f"item{i}": i for i in range(12)}),
            "__builtins__": __builtins__,
        })
        console.visible = True
        console.input = "thing."
        console.cursor = len(console.input)
        console.output = [f"output row {i}" for i in range(30)]
        console._complete()

        with mock.patch("pysa.dev_console.hud.screen_size",
                        return_value=(1920, 1080)), \
                mock.patch("pysa.dev_console.draw.rect"), \
                mock.patch("pysa.dev_console.hud.draw_mono") as draw_text, \
                mock.patch("pysa.dev_console.hud.mono_text_width",
                           side_effect=lambda text, height:
                           len(text) * height * 0.6), \
                mock.patch("pysa.dev_console.time.monotonic", return_value=0):
            console.draw()

        output_calls = [call for call in draw_text.call_args_list
                        if str(call.args[0]).startswith("output row")]
        popup_calls = [call for call in draw_text.call_args_list
                       if str(call.args[0]).startswith("item")]
        self.assertTrue(popup_calls)
        if output_calls:
            self.assertLess(max(call.args[2] for call in output_calls),
                            min(call.args[2] for call in popup_calls))

    def test_completion_understands_typed_function_results(self):
        console = DeveloperConsole()
        console.input = "blips.waypoint()."
        console.cursor = len(console.input)
        console._complete()

        self.assertIsNotNone(console._completion)
        labels = console._completion.labels
        self.assertIn("x", labels)
        self.assertIn("y", labels)
        self.assertIn("z", labels)
        self.assertEqual(len(labels), len(console._completion.details))

    def test_dot_opens_intellisense_automatically(self):
        console = DeveloperConsole()
        console.input = "player.ped"
        console.cursor = len(console.input)
        console._insert(".")

        self.assertIsNotNone(console._completion)
        self.assertIn("pos", console._completion.labels)
        pos_index = console._completion.labels.index("pos")
        self.assertEqual(console._completion.colors[pos_index],
                         dev_console._CODE_ATTRIBUTE)
        self.assertIn("property pos: Vector3",
                      console._completion.details[pos_index])

    def test_completion_colors_describe_semantic_kinds(self):
        console = DeveloperConsole()
        console.input = "player."
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None

        camera = console._completion.labels.index("camera")
        build = console._completion.labels.index("build_model(")
        self.assertEqual(console._completion.colors[camera],
                         dev_console._CODE_ATTRIBUTE)
        self.assertEqual(console._completion.colors[build],
                         dev_console._CODE_CALL)
        self.assertEqual(console._completion.details[camera],
                         "property camera: PlayerCamera")

    def test_editor_pairs_delimiters_and_skips_existing_closer(self):
        console = DeveloperConsole()
        console._insert("(")
        self.assertEqual(console.input, "()")
        self.assertEqual(console.cursor, 1)
        console._insert(")")
        self.assertEqual(console.input, "()")
        self.assertEqual(console.cursor, 2)

        console.input = "[]"
        console.cursor = 1
        console._down.clear()
        console.visible = True
        with mock.patch.object(dev_console._pysa, "key_down",
                               side_effect=lambda key: key == KEY.BACKSPACE):
            console.update()
        self.assertEqual(console.input, "")

    def test_editor_word_navigation_helpers(self):
        console = DeveloperConsole()
        console.input = "player.ped.health"
        console.cursor = len(console.input)
        self.assertEqual(console._word_left(), len("player.ped."))
        console.cursor = 0
        self.assertEqual(console._word_right(), len("player"))

    def test_signature_help_tracks_multiple_parameters_and_nested_commas(self):
        console = DeveloperConsole()
        console.input = "camera.move((0, 0, 0), "
        console.cursor = len(console.input)

        hint = console._call_hint()
        self.assertIsNotNone(hint)
        assert hint is not None
        self.assertEqual(hint.name, "camera.move")
        self.assertEqual(hint.active, 1)
        self.assertEqual(hint.parameters[hint.active].name, "end")
        self.assertEqual([parameter.name for parameter in hint.parameters],
                         ["start", "end", "ms", "ease"])

        console.input = "camera.move((0, 0, 0), (1, 2, 3), 1000, "
        console.cursor = len(console.input)
        hint = console._call_hint()
        assert hint is not None
        self.assertEqual(hint.parameters[hint.active].name, "ease")

    def test_ctrl_space_completion_offers_named_parameters(self):
        console = DeveloperConsole()
        console.input = "camera.move("
        console.cursor = len(console.input)
        console._complete()

        self.assertIsNotNone(console._completion)
        labels = console._completion.labels
        self.assertIn("start=", labels)
        self.assertIn("end=", labels)
        self.assertIn("ms=", labels)
        self.assertIn("ease=", labels)

        console.input = "camera.move(start=(0, 0, 0), e"
        console.cursor = len(console.input)
        console._completion = None
        console._complete()
        self.assertIsNotNone(console._completion)
        self.assertEqual(console._completion.labels, ["end=", "ease="])

    def test_partial_single_match_opens_box_and_tab_accepts(self):
        console = DeveloperConsole()
        console.visible = True
        console.input = "player.ped.po"
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None
        self.assertEqual(console._completion.labels, ["pos"])
        self.assertEqual(console.input, "player.ped.po")

        console._down[KEY.TAB] = False
        with mock.patch.object(dev_console._pysa, "key_down",
                               side_effect=lambda key: key == KEY.TAB):
            console.update()
        self.assertEqual(console.input, "player.ped.pos")
        self.assertIsNone(console._completion)

    def test_console_uses_active_layout_translation(self):
        console = DeveloperConsole()
        console.visible = True

        with mock.patch("pysa.dev_console._pysa.key_down",
                        side_effect=lambda key: key == KEY.N2), \
                mock.patch("pysa.dev_console._translate_key",
                           return_value="@") as translate:
            console.update()

        self.assertEqual(console.input, "@")
        translate.assert_called_once_with(KEY.N2)

    def test_console_closes_for_frontend_and_restores_without_reopening(self):
        console = DeveloperConsole()
        console.visible = True
        console._controls_were_enabled = True

        with mock.patch("pysa.dev_console._pysa.frontend_active",
                        return_value=True), \
                mock.patch.object(PlayerControls, "enabled",
                                  new_callable=mock.PropertyMock):
            console.update()
        self.assertFalse(console.visible)
        self.assertTrue(console._restore_after_frontend)

        with mock.patch("pysa.dev_console._pysa.frontend_active",
                        return_value=False), \
                mock.patch.object(PlayerControls, "enabled",
                                  new_callable=mock.PropertyMock) as enabled:
            console.update()
        self.assertFalse(console.visible)
        self.assertIsNone(console._restore_after_frontend)
        enabled.assert_called_with(True)

    def test_console_captures_all_game_input_while_open(self):
        console = DeveloperConsole()
        with mock.patch.object(dev_console._pysa, "capture_input") as capture, \
                mock.patch.object(PlayerControls, "enabled",
                                  new_callable=mock.PropertyMock,
                                  return_value=True):
            console.open()
            console.close()
        self.assertEqual(capture.call_args_list,
                         [mock.call(True), mock.call(False)])

    def test_console_wraps_output_and_scrolls_long_input(self):
        console = DeveloperConsole()
        console.output = ["short", "x" * 25, "two words fit naturally"]
        rows = console._wrapped_output(10)
        self.assertTrue(all(len(row) <= 10 for row in rows))
        self.assertEqual("".join(rows[1:4]), "x" * 25)

        console.input = "0123456789abcdefghij"
        console.cursor = len(console.input)
        start, visible = console._input_window(8)
        self.assertEqual(visible, "cdefghij")
        self.assertEqual(start, 12)

    def test_console_edits_at_visible_cursor(self):
        console = DeveloperConsole()
        console.input = "ac"
        console.cursor = 1
        console._insert("b")
        self.assertEqual(console.input, "abc")
        self.assertEqual(console.cursor, 2)

        console.visible = True
        with mock.patch("pysa.dev_console._pysa.key_down",
                        side_effect=lambda key: key == KEY.LEFT):
            console.update()
        self.assertEqual(console.cursor, 1)

    def test_holding_backspace_repeats_after_keyboard_delay(self):
        console = DeveloperConsole()
        console.visible = True
        console.input = "abcd"
        console.cursor = 4

        with mock.patch("pysa.dev_console._pysa.key_down",
                        side_effect=lambda key: key == KEY.BACKSPACE), \
                mock.patch("pysa.dev_console.time.monotonic") as clock:
            clock.return_value = 0.0
            console.update()
            self.assertEqual(console.input, "abc")
            clock.return_value = 0.2
            console.update()
            self.assertEqual(console.input, "abc")
            clock.return_value = 0.36
            console.update()
            self.assertEqual(console.input, "ab")
            clock.return_value = 0.41
            console.update()
            self.assertEqual(console.input, "a")

    def test_mock_monospace_measurement_counts_trailing_spaces(self):
        from pysa import hud

        self.assertGreater(hud.mono_text_width("a ", 16),
                           hud.mono_text_width("a", 16))

    def test_mouse_drag_selects_and_repositions_input_text(self):
        console = DeveloperConsole()
        console.visible = True
        console.input = "abcde"
        console.cursor = 5
        input_x, input_y, _, pixels, _ = console._input_geometry()
        cell = _mock.mono_text_width("M", pixels)
        console.mouse_x = input_x
        console.mouse_y = input_y

        with mock.patch("pysa.dev_console._pysa.mouse_state",
                        side_effect=[(0, 0, True),
                                     (cell * 3, 0, True),
                                     (0, 0, False)]):
            console._update_mouse()
            console._update_mouse()
            console._update_mouse()

        self.assertEqual(console._selection_bounds(), (0, 3))

        console.mouse_x = input_x + cell
        with mock.patch("pysa.dev_console._pysa.mouse_state",
                        side_effect=[(0, 0, True),
                                     (cell * 4, 0, True),
                                     (0, 0, False)]):
            console._update_mouse()
            console._update_mouse()
            console._update_mouse()

        self.assertEqual(console.input, "deabc")
        self.assertEqual(console._selection_bounds(), (2, 5))

    def test_mouse_hovers_and_clicks_completion_rows(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, beta=2, gamma=3),
            "__builtins__": __builtins__,
        })
        console.input = "thing."
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None
        console._completion_hitbox = (10.0, 20.0, 200.0, 15.0, 0, 3)
        console.mouse_x = 20.0
        console.mouse_y = 42.0  # second row

        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)), \
                mock.patch("pysa.dev_console.time.monotonic",
                           return_value=1.0):
            console._update_mouse()

        self.assertEqual(console.input, "thing.beta")
        self.assertIsNone(console._completion)

    def test_completion_hover_never_reclaims_keyboard_selection(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, beta=2, gamma=3),
            "__builtins__": __builtins__,
        })
        console.visible = True
        console.input = "thing."
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None
        console._completion_hitbox = (10.0, 20.0, 200.0, 15.0, 0, 3)
        console.mouse_x = 20.0
        console.mouse_y = 25.0  # first row remains hovered

        # Establish the row currently under the pointer, then navigate by
        # keyboard while the pointer stays there.
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, False, False, 0)):
            console._update_mouse()
        with mock.patch.object(dev_console._pysa, "key_down",
                               side_effect=lambda key: key == KEY.DOWN), \
             mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, False, False, 0)), \
             mock.patch("pysa.dev_console.time.monotonic", return_value=1.0):
            console.update()
        self.assertEqual(console._completion.selected, 1)

        # Moving inside the original row or across other rows changes only the
        # hover decoration. It must never move or scroll keyboard selection.
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(2, 0, False, False, 0)):
            console._update_mouse()
        self.assertEqual(console._completion.selected, 1)
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 31, False, False, 0)):
            console._update_mouse()
        self.assertEqual(console._completion.selected, 1)
        self.assertEqual(console._completion_hover_row, 2)

    def test_mouse_wheel_navigates_completions_and_scrollback(self):
        console = DeveloperConsole(namespace={
            "thing": SimpleNamespace(alpha=1, beta=2, gamma=3),
            "__builtins__": __builtins__,
        })
        console.input = "thing."
        console.cursor = len(console.input)
        console._complete()
        assert console._completion is not None
        console._completion_hitbox = (10.0, 20.0, 200.0, 15.0, 0, 3)

        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, False, False, -1)):
            console._update_mouse()
        self.assertEqual(console._completion.selected, 1)

        console._completion = None
        console.output = [str(i) for i in range(20)]
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, False, False, 1)):
            console._update_mouse()
        self.assertEqual(console._scroll_offset, 3)

    def test_scrollback_eases_toward_wheel_target(self):
        console = DeveloperConsole()
        console.visible = True
        console.output = [f"line {i}" for i in range(40)]
        console._scroll_offset = 6
        console._scroll_visual = 0.0
        console._scroll_time = 0.0

        with mock.patch("pysa.dev_console.hud.screen_size",
                        return_value=(1280, 720)), \
                mock.patch("pysa.dev_console.draw.rect"), \
                mock.patch("pysa.dev_console.hud.draw_mono"), \
                mock.patch("pysa.dev_console.hud.mono_text_width",
                           side_effect=lambda text, height:
                           len(text) * height * 0.6), \
                mock.patch("pysa.dev_console.time.monotonic",
                           return_value=0.016):
            console.draw()
        first = console._scroll_visual
        self.assertGreater(first, 0.0)
        self.assertLess(first, 6.0)

        with mock.patch("pysa.dev_console.hud.screen_size",
                        return_value=(1280, 720)), \
                mock.patch("pysa.dev_console.draw.rect"), \
                mock.patch("pysa.dev_console.hud.draw_mono"), \
                mock.patch("pysa.dev_console.hud.mono_text_width",
                           side_effect=lambda text, height:
                           len(text) * height * 0.6), \
                mock.patch("pysa.dev_console.time.monotonic",
                           return_value=0.032):
            console.draw()
        self.assertGreater(console._scroll_visual, first)
        self.assertLess(console._scroll_visual, 6.0)

    def test_clicking_command_output_recalls_full_history_entry(self):
        console = DeveloperConsole()
        command = "player.ped.pos = world.closest_straight_road((1, 2, 3)).start"
        console.history = [command]
        console._output_hitboxes = [(0, 100, 0, 20, ">>> player.ped.pos = world", 0)]
        console._wrapped_output_cache = [">>> player.ped.pos = world"]
        console.mouse_x = 10
        console.mouse_y = 10
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)), \
                mock.patch("pysa.dev_console.time.monotonic",
                           return_value=1.0):
            console._update_mouse()
        console._mouse_was_down = False
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)), \
                mock.patch("pysa.dev_console.time.monotonic",
                           return_value=1.1):
            console._update_mouse()
        self.assertEqual(console.input, command)
        self.assertEqual(console.cursor, len(command))

    def test_history_text_drag_selection_copies_across_rows(self):
        console = DeveloperConsole()
        console._wrapped_output_cache = ["abcdef", "ghijkl"]
        console._output_cell_width = 10.0
        console._output_hitboxes = [
            (0, 100, 0, 20, "abcdef", 0),
            (0, 100, 20, 40, "ghijkl", 1),
        ]
        console.mouse_x = 10
        console.mouse_y = 10

        with mock.patch.object(dev_console._pysa, "mouse_state",
                               side_effect=[(0, 0, True, False, 0),
                                            (40, 20, True, False, 0),
                                            (0, 0, False, False, 0)]):
            console._update_mouse()
            console._update_mouse()
            console._update_mouse()

        self.assertEqual(console._output_selection_bounds(),
                         ((0, 1), (1, 5)))
        self.assertTrue(console._copy_selection())
        self.assertEqual(_mock.clipboard_get(), "bcdef\nghijk")

    def test_scrollbar_thumb_can_be_dragged(self):
        console = DeveloperConsole()
        console._max_scroll = 10
        console._scrollbar_hitbox = (100, 0, 10, 100, 80, 20)
        console.mouse_x = 105
        console.mouse_y = 90

        with mock.patch.object(dev_console._pysa, "mouse_state",
                               side_effect=[(0, 0, True, False, 0),
                                            (0, -70, True, False, 0),
                                            (0, 0, False, False, 0)]):
            console._update_mouse()
            console._update_mouse()
            console._update_mouse()

        self.assertFalse(console._scrollbar_dragging)
        self.assertGreaterEqual(console._scroll_offset, 8)
        self.assertEqual(console._scroll_visual,
                         float(console._scroll_offset))

    def test_selection_aware_clipboard_and_deletion(self):
        console = DeveloperConsole()
        console.input = "hello world"
        console.selection_anchor = 6
        console.cursor = 11

        self.assertTrue(console._copy_selection())
        self.assertEqual(_mock.clipboard_get(), "world")
        self.assertTrue(console._delete_selection())
        self.assertEqual(console.input, "hello ")
        console._insert(_mock.clipboard_get())
        self.assertEqual(console.input, "hello world")

    def test_game_print_stream_mirrors_log_and_queues_subtitle(self):
        import io

        log = io.StringIO()
        stream = _runtime._GamePrintStream(log)
        stream.write("hello")
        stream.write(" world\n")

        self.assertEqual(log.getvalue(), "hello world\n")
        self.assertEqual(_runtime._print_messages.get_nowait(), "hello world")

    def test_builtin_console_accepts_bom_prefixed_ini(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "PyAndreas.ini").write_text(
                "[PyAndreas]\nDeveloperMode = 1\n"
                "ConsoleBackgroundOpacity = 0.42\n"
                "ConsoleScale = 1.20\n",
                encoding="utf-8-sig")
            with mock.patch.object(dev_console, "_current_console", None):
                console = dev_console._install_builtin(folder)

            self.assertTrue(console.enabled)
            self.assertEqual(console.background_opacity, 0.42)
            self.assertEqual(console.scale, 1.2)

    def test_console_text_scales_with_resolution(self):
        console = DeveloperConsole()
        console.visible = True
        console.input = "print('stable')"
        console.cursor = 5

        with mock.patch("pysa.dev_console.hud.screen_size",
                        return_value=(1920, 1080)), \
                mock.patch("pysa.dev_console.draw.rect"), \
                mock.patch("pysa.dev_console.hud.draw_mono") as draw_text, \
                mock.patch("pysa.dev_console.hud.mono_text_width",
                           side_effect=lambda text, height:
                           len(text) * height * 0.6), \
                mock.patch("pysa.dev_console.time.monotonic", return_value=0):
            console.draw()

        sizes = [call.args[3] for call in draw_text.call_args_list]
        rendered = [call.args[0] for call in draw_text.call_args_list]
        self.assertGreater(min(sizes), 1.0)
        self.assertIn("print('stable')", "".join(rendered))
        self.assertFalse(any("|" in text for text in rendered))

    def test_console_code_surface_uses_configurable_transparency(self):
        console = DeveloperConsole(background_opacity=120 / 255)
        console.visible = True
        with mock.patch("pysa.dev_console.hud.screen_size",
                        return_value=(1280, 720)), \
                mock.patch("pysa.dev_console.draw.rect") as rect, \
                mock.patch("pysa.dev_console.hud.draw_mono"), \
                mock.patch("pysa.dev_console.hud.mono_text_width",
                           side_effect=lambda text, height:
                           len(text) * height * 0.6):
            console.draw()

        colors = [call.args[4] for call in rect.call_args_list]
        self.assertIn((5, 7, 9, 120), colors)
        self.assertIn((10, 14, 17, 175), colors)

    def test_console_settings_use_normalized_opacity_and_persist(self):
        console = DeveloperConsole(background_opacity=0.5)
        with mock.patch.object(dev_console, "_save_console_settings") as save:
            console._apply_setting_action("opacity_down")
            self.assertEqual(console.background_opacity, 0.45)
            console._apply_setting_action("opacity_up")
            self.assertEqual(console.background_opacity, 0.5)
            console._apply_setting_action("scale_up")
            self.assertEqual(console.scale, 1.1)
            console._apply_setting_action("autocomplete")
            self.assertFalse(console.auto_complete)
        self.assertEqual(save.call_count, 4)

        console.background_opacity = 0.0
        console._apply_setting_action("opacity_down")
        self.assertEqual(console.background_opacity, 0.0)
        console.background_opacity = 1.0
        console._apply_setting_action("opacity_up")
        self.assertEqual(console.background_opacity, 1.0)

    def test_console_settings_use_compact_aligned_controls(self):
        console = DeveloperConsole()
        with mock.patch("pysa.dev_console.draw.rect"), \
                mock.patch("pysa.dev_console.draw.bar"), \
                mock.patch("pysa.dev_console.hud.draw_mono"), \
                mock.patch("pysa.dev_console.hud.mono_text_width",
                           side_effect=lambda text, pixels:
                           len(text) * pixels * 0.6):
            console._draw_settings_panel(0.0, 0.0, 1000.0, 600.0, 1.0)

        sliders = console._settings_slider_hitboxes
        self.assertEqual(set(sliders), {"scale", "opacity", "history"})
        self.assertEqual(len({bounds.x for bounds in sliders.values()}), 1)
        self.assertEqual(len({bounds.width for bounds in sliders.values()}), 1)
        self.assertGreater(sliders["scale"].x, 400.0)
        self.assertLess(sliders["scale"].width, 300.0)
        actions = {hitbox[-1] for hitbox in console._settings_hitboxes}
        self.assertEqual(actions, {"autocomplete", "reset"})

    def test_clickable_settings_and_close_header_buttons(self):
        console = DeveloperConsole()
        console.visible = True
        console._settings_hitbox = (10, 10, 100, 30)
        console._close_hitbox = (120, 10, 30, 30)
        console.mouse_x = 20
        console.mouse_y = 20
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)):
            console._update_mouse()
        self.assertTrue(console.settings_visible)

        console._mouse_was_down = False
        console.mouse_x = 130
        with mock.patch.object(dev_console._pysa, "mouse_state",
                               return_value=(0, 0, True, False, 0)), \
                mock.patch.object(PlayerControls, "enabled",
                                  new_callable=mock.PropertyMock):
            console._update_mouse()
        self.assertFalse(console.visible)
        self.assertFalse(console.settings_visible)

    def test_python_syntax_highlighting_classifies_common_tokens(self):
        console = DeveloperConsole()
        source = "if len(items) > 2: print('ready') # comment"
        spans = console._syntax_spans(source)
        colors = {source[start:end]: color for start, end, color in spans
                  if source[start:end].strip()}

        self.assertEqual(colors["if"], dev_console._CODE_KEYWORD)
        self.assertEqual(colors["len"], dev_console._CODE_BUILTIN)
        self.assertEqual(colors["2"], dev_console._CODE_NUMBER)
        self.assertEqual(colors["'ready'"], dev_console._CODE_STRING)
        self.assertEqual(colors["# comment"], dev_console._CODE_COMMENT)

        result = "Vector3(1.0, 2.0, 3.0)"
        result_spans = console._syntax_spans(result)
        result_colors = {result[start:end]: color
                         for start, end, color in result_spans
                         if result[start:end].strip()}
        self.assertEqual(result_colors["Vector3"], dev_console._CODE_CALL)
        self.assertEqual(result_colors["1.0"], dev_console._CODE_NUMBER)

    def test_test_runner_isolates_failures_and_supports_waits(self):
        output = []

        @testing.dev_test
        def ordinary_pass():
            return None

        @testing.dev_test("delayed pass")
        def delayed_pass():
            yield 25
            return True

        @testing.dev_test
        def expected_failure():
            raise AssertionError("intentional")

        with mock.patch.object(testing._runtime._pysa, "log"):
            run = testing.run_tests(output=output.append)
            now = 0
            while not run.task.done:
                run.task._step(now)
                now += 25

        self.assertTrue(run.finished)
        self.assertEqual(run.passed, 2)
        self.assertEqual(run.failed, 1)
        self.assertIn(("expected_failure", "AssertionError: intentional"),
                      run.failures)
        self.assertIn("[TEST] 2 passed, 1 failed", output)

    def test_failed_script_load_rolls_back_registered_tests(self):
        @testing.dev_test("existing")
        def existing():
            pass

        checkpoint = _runtime._registry_checkpoint()

        @testing.dev_test("temporary")
        def temporary():
            pass

        _runtime._rollback_registries(checkpoint)
        self.assertEqual(testing.test_names(), ["existing"])


if __name__ == "__main__":
    unittest.main()
