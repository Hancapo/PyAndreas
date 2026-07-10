import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pysa import _mock, _runtime, game_events, hooks
from pysa.entities import GameObject, Ped, Vehicle
from pysa.models import VEHICLE
from pysa.ped_models import PED


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        printer = mock.patch("builtins.print")
        printer.start()
        self.addCleanup(printer.stop)
        _runtime._clear_registries()
        _runtime._unload_script_modules()
        for name, _ in _runtime._scripts:
            sys.modules.pop(name, None)
        _runtime._scripts.clear()
        _runtime._scripts_dir = ""
        _runtime._reload_was_down = False
        _mock._reset()

    def tearDown(self):
        _runtime._clear_registries()
        _runtime._unload_script_modules()
        _runtime._scripts.clear()
        _runtime._scripts_dir = ""

    def test_handler_is_disabled_after_first_error(self):
        calls = []

        def broken():
            calls.append("called")
            raise RuntimeError("boom")
        _runtime.register("tick", broken)

        _runtime.dispatch("tick")
        _runtime.dispatch("tick")

        self.assertEqual(calls, ["called"])
        self.assertTrue(_runtime._handlers["tick"][0].disabled)
        self.assertTrue(any("disabled after error" in line
                            for line in _mock._log_lines))

    def test_interval_handlers_and_tasks_use_game_clock(self):
        clock = [100]
        events = []

        _runtime.register("tick", lambda: events.append("interval"), ms=50)

        def sequence():
            events.append("task-1")
            yield 25
            events.append("task-2")

        _runtime.start(sequence())
        with mock.patch.object(_mock, "game_time", side_effect=lambda: clock[0]):
            _runtime.dispatch("tick")
            clock[0] = 130
            _runtime.dispatch("tick")
            clock[0] = 150
            _runtime.dispatch("tick")

        self.assertEqual(events,
                         ["interval", "task-1", "task-2", "interval"])

    def test_failed_import_rolls_back_every_registration_type(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, "broken.py")
            path.write_text(
                "import pysa\n"
                "@pysa.on_tick\n"
                "def leaked_tick(): pass\n"
                "@pysa.on_key(65)\n"
                "def leaked_key(): pass\n"
                "@pysa.on_call(0x123456)\n"
                "def leaked_hook(call): pass\n"
                "@pysa.on_vehicle_damage\n"
                "def leaked_event(event): pass\n"
                "raise RuntimeError('import failed')\n",
                encoding="utf-8",
            )

            self.assertEqual(_runtime.bootstrap(folder), 0)

        self.assertFalse(_runtime._handlers)
        self.assertFalse(_runtime._key_watchers)
        self.assertFalse(hooks._HOOKS)
        self.assertFalse(game_events._handlers)
        self.assertFalse(game_events._hook_ids)
        self.assertFalse(_mock._hooks)

    def test_failed_import_discards_new_local_helper_module(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "_local_helper.py").write_text("VALUE = 1\n",
                                                         encoding="utf-8")
            Path(folder, "broken.py").write_text(
                "import _local_helper\nraise RuntimeError('nope')\n",
                encoding="utf-8",
            )
            sys.path.insert(0, folder)
            try:
                self.assertEqual(_runtime.bootstrap(folder), 0)
                self.assertNotIn("_local_helper", sys.modules)
            finally:
                sys.path.remove(folder)

    def test_reload_reimports_local_helper_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            helper = Path(folder, "_reload_helper.py")
            helper.write_text("VALUE = 1\n", encoding="utf-8")
            Path(folder, "main.py").write_text(
                "import pysa\n"
                "from _reload_helper import VALUE\n"
                "@pysa.on_tick\n"
                "def report(): pysa.log(f'value={VALUE}')\n",
                encoding="utf-8",
            )
            sys.path.insert(0, folder)
            try:
                self.assertEqual(_runtime.bootstrap(folder), 1)
                _runtime.dispatch("tick")
                self.assertIn("value=1", _mock._log_lines)

                helper.write_text("VALUE = 22\n", encoding="utf-8")
                # Make cache invalidation deterministic on timestamp-based pyc.
                stamp = helper.stat().st_mtime + 2
                os.utime(helper, (stamp, stamp))
                _runtime.reload_scripts()
                _runtime.dispatch("tick")

                self.assertEqual(_mock._log_lines.count("value=1"), 1)
                self.assertEqual(_mock._log_lines.count("value=22"), 1)
            finally:
                sys.path.remove(folder)

    def test_task_cleanup_error_does_not_abort_registry_clear(self):
        def bad_cleanup():
            try:
                yield
            finally:
                raise RuntimeError("cleanup failed")

        task = _runtime.start(bad_cleanup())
        next(task.gen)
        _runtime.register("tick", lambda: None)

        _runtime._clear_registries()

        self.assertTrue(task.done)
        self.assertFalse(_runtime._tasks)
        self.assertFalse(_runtime._handlers)
        self.assertTrue(any("error while cancelling task" in line
                            for line in _mock._log_lines))

    def test_plugin_lifecycle_event_dispatch(self):
        received = []
        _runtime.register("device_reset", lambda: received.append("reset"))
        _runtime.register("game_restart", lambda: received.append("restart"))

        _runtime.dispatch("device_reset")
        _runtime.dispatch("game_restart")

        self.assertEqual(received, ["reset", "restart"])

    def test_high_frequency_native_events_are_subscription_gated(self):
        received = []
        self.assertNotIn("vehicle_render", _mock._enabled_events)

        _runtime.register("vehicle_render", lambda vehicle: received.append(vehicle))
        self.assertIn("vehicle_render", _mock._enabled_events)
        _runtime.dispatch("vehicle_render", 0x123400)

        self.assertIsInstance(received[0], Vehicle)
        self.assertEqual(received[0].address, 0x123400)
        _runtime._clear_registries()
        self.assertNotIn("vehicle_render", _mock._enabled_events)

    def test_crashed_render_handler_turns_its_native_gate_off(self):
        def broken(_vehicle):
            raise RuntimeError("render failed")

        _runtime.register("vehicle_render", broken)
        _runtime.dispatch("vehicle_render", 0x123400)

        self.assertTrue(_runtime._handlers["vehicle_render"][0].disabled)
        self.assertNotIn("vehicle_render", _mock._enabled_events)

    def test_model_change_events_wrap_entities_and_include_model(self):
        received = []
        _runtime.register("vehicle_model_changed",
                          lambda entity, model: received.append((entity, model)))
        _runtime.register("ped_model_changed",
                          lambda entity, model: received.append((entity, model)))

        _runtime.dispatch("vehicle_model_changed", (0x123400, 411))
        _runtime.dispatch("ped_model_changed", (0x567800, 7))

        self.assertIsInstance(received[0][0], Vehicle)
        self.assertEqual(received[0][0].address, 0x123400)
        self.assertIs(received[0][1], VEHICLE.INFERNUS)
        self.assertEqual(received[0][1], 411)
        self.assertIsInstance(received[1][0], Ped)
        self.assertEqual(received[1][0].address, 0x567800)
        self.assertIs(received[1][1], PED.MALE01)
        self.assertEqual(received[1][1], 7)

    def test_created_events_wait_until_every_entity_type_is_ready(self):
        cases = (
            ("vehicle_created", 0x123400, Vehicle, VEHICLE.INFERNUS),
            ("ped_created", 0x223400, Ped, PED.MALE01),
            ("object_created", 0x323400, GameObject, 1337),
        )
        received = {event: [] for event, *_ in cases}
        for event, ptr, _wrapper, _model in cases:
            _runtime.register(event, received[event].append)
            # plugin-sdk's constructor event arrives with m_nModelIndex -1.
            _mock.write_u16(ptr + 0x22, 0xFFFF)
            _runtime.dispatch(event, ptr)

        _runtime.dispatch("tick")
        self.assertTrue(all(not items for items in received.values()))

        for event, ptr, _wrapper, model in cases:
            _mock.write_u16(ptr + 0x22, model)
        _runtime.dispatch("tick")

        for event, ptr, wrapper, model in cases:
            self.assertEqual(len(received[event]), 1)
            entity = received[event][0]
            self.assertIsInstance(entity, wrapper)
            self.assertEqual(entity.address, ptr)
            self.assertEqual(_mock.read_u16(entity.address + 0x22), model)

    def test_lifecycle_events_never_publish_invalid_wrappers(self):
        received = []
        _runtime.register("vehicle_render", received.append)
        for invalid_ref in (-1, 0xC81):
            with mock.patch.object(
                    Vehicle, "_handle_of",
                    staticmethod(lambda _ptr, ref=invalid_ref: ref)):
                _runtime.dispatch("vehicle_render", 0x123400)
        self.assertFalse(received)


if __name__ == "__main__":
    unittest.main()
