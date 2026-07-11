import threading
import unittest
from unittest import mock

import pysa
from pysa import (_mock, _runtime, camera, cmd, events, pad, state_events,
                  ui, world)
from pysa.entities import Ped
from pysa.enums import SURFACE
from pysa.keys import KEY
from pysa.pad import BUTTON
from pysa.session import ScriptSession


class FakePed:
    def __init__(self, handle=1):
        self.handle = handle
        self.health = 100
        self.dead = False
        self.vehicle = None
        self.current_weapon = 0


class FakeVehicle:
    def __init__(self):
        self.driver = None
        self.passengers = []


class ScriptingErgonomicsTests(unittest.TestCase):
    def setUp(self):
        _runtime._clear_registries()
        _mock._reset()

    def tearDown(self):
        _runtime._clear_registries()

    def test_ped_animation_facade_controls_named_clip(self):
        ped = Ped(7)
        with mock.patch.object(cmd, "HAS_ANIMATION_LOADED", return_value=False), \
                mock.patch.object(cmd, "REQUEST_ANIMATION") as request, \
                mock.patch.object(cmd, "LOAD_ALL_MODELS_NOW"), \
                mock.patch.object(cmd, "TASK_PLAY_ANIM_NON_INTERRUPTABLE") as play, \
                mock.patch.object(cmd, "SET_CHAR_ANIM_CURRENT_TIME") as set_time, \
                mock.patch.object(cmd, "SET_CHAR_ANIM_PLAYING_FLAG") as playing:
            clip = ped.anim.play("GunMove_BWD", "PED", interruptible=False)
            clip.time = 0.27
            clip.playing = False

        request.assert_called_once_with("PED")
        play.assert_called_once_with(
            ped, "GunMove_BWD", "PED", 4.0, False, False, False, False, -1)
        set_time.assert_called_once_with(ped, "GunMove_BWD", 0.27)
        playing.assert_called_once_with(ped, "GunMove_BWD", False)

    def test_vehicle_engine_and_camera_helpers_are_friendly(self):
        car = pysa.Vehicle(3)
        with mock.patch.object(_mock, "vehicle_engine_broken", return_value=True), \
                mock.patch.object(cmd, "SET_CAR_ENGINE_BROKEN") as broken, \
                mock.patch.object(cmd, "SET_CAMERA_BEHIND_PLAYER") as behind:
            self.assertTrue(car.engine_broken)
            car.engine_broken = False
            camera.behind_player()
        broken.assert_called_once_with(car, False)
        behind.assert_called_once_with()

    def test_script_session_cleans_up_in_reverse_and_on_registry_clear(self):
        cleaned = []

        class Resource:
            def remove(self):
                cleaned.append("resource")

        session = ScriptSession()
        session.__enter__()
        session.track(Resource())
        session.defer(cleaned.append, "last-added")

        _runtime._clear_registries()
        self.assertEqual(cleaned, ["last-added", "resource"])
        session.close()
        self.assertEqual(cleaned, ["last-added", "resource"])

    def test_raycast_returns_typed_collision_information(self):
        _mock._raycast_result = (
            1.0, 2.0, 3.0, 0.0, 0.0, 1.0, 0,
            int(SURFACE.TARMAC), 4, 12, 6, 0.25,
        )
        hit = world.raycast((0, 0, 0), (10, 10, 10), peds=False)

        self.assertEqual(hit.position, (1, 2, 3))
        self.assertEqual(hit.normal, (0, 0, 1))
        self.assertIs(hit.surface, SURFACE.TARMAC)
        self.assertEqual(hit.piece, 4)
        self.assertFalse(world.line_of_sight((0, 0, 0), (1, 1, 1)))

    def test_controller_direction_and_combo_edges_are_intuitive(self):
        with mock.patch.object(pad, "left_stick", return_value=(0.25, -0.75)):
            stick = pad.left_stick_direction()
        self.assertEqual(tuple(stick), (0.25, 0.75))

        held = {BUTTON.L1: False, BUTTON.DPAD_DOWN: False}
        clock = [1]
        action = pad.combo(BUTTON.L1, BUTTON.DPAD_DOWN)
        with mock.patch.object(pad, "pressed",
                               side_effect=lambda button, _pad=0: held[button]), \
                mock.patch.object(_mock, "game_time",
                                  side_effect=lambda: clock[0]):
            self.assertFalse(action.down)
            held.update({BUTTON.L1: True, BUTTON.DPAD_DOWN: True})
            clock[0] = 2
            self.assertTrue(action.pressed)
            self.assertTrue(action.down)

    def test_background_work_is_marshalled_to_game_thread(self):
        result = []
        futures = []

        def worker():
            futures.append(pysa.run_on_game_thread(result.append, "game"))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertFalse(futures[0].done())
        _runtime._drain_main_thread_queue()
        self.assertEqual(result, ["game"])
        self.assertTrue(futures[0].done())

    def test_menu_actions_toggles_and_choices(self):
        values = {"enabled": False, "weather": "sunny"}
        menu = ui.Menu("Test", toggle_key=KEY.F5, auto=False)
        menu.toggle_item("Enabled", lambda: values["enabled"],
                         lambda value: values.__setitem__("enabled", value))
        menu.choice("Weather", ("sunny", "rain"),
                    lambda: values["weather"],
                    lambda value: values.__setitem__("weather", value))

        menu.activate()
        menu.move(1)
        menu.activate()
        self.assertTrue(values["enabled"])
        self.assertEqual(values["weather"], "rain")

    def test_shared_slider_clamps_steps_and_tracks_the_pointer(self):
        value = {"current": 0.5}
        slider = ui.Slider(
            0.0, 1.0, 0.05, lambda: value["current"],
            lambda new_value: value.__setitem__("current", new_value))
        track = ui.Rect(100, 20, 200, 24)

        slider.set_from_pointer(250, track)
        self.assertEqual(value["current"], 0.75)
        slider.change(1)
        self.assertEqual(value["current"], 0.8)
        slider.set_from_pointer(500, track)
        self.assertEqual(value["current"], 1.0)
        slider.set_from_pointer(0, track)
        self.assertEqual(value["current"], 0.0)

    def test_polled_gameplay_events_are_dormant_until_subscribed(self):
        ped = FakePed()
        received = []
        with mock.patch("pysa.entities.all_peds", return_value=[ped]):
            state_events._poll()
            self.assertFalse(state_events._ped_state)

            events.on_ped_damage(received.append)
            state_events._poll()
            ped.health = 65
            state_events._poll()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].amount, 35)
        self.assertIs(received[0].ped, ped)

    def test_vehicle_and_weapon_transition_payloads(self):
        ped = FakePed()
        vehicle = FakeVehicle()
        vehicle.driver = ped
        enters, exits, weapons = [], [], []
        events.on_vehicle_enter(enters.append)
        events.on_vehicle_exit(exits.append)
        events.on_weapon_changed(weapons.append)

        with mock.patch("pysa.entities.all_peds", return_value=[ped]):
            state_events._poll()
            ped.vehicle = vehicle
            ped.current_weapon = int(pysa.WEAPON.M4)
            state_events._poll()
            ped.vehicle = None
            state_events._poll()

        self.assertEqual(len(enters), 1)
        self.assertTrue(enters[0].driver)
        self.assertEqual(len(exits), 1)
        self.assertTrue(exits[0].driver)
        self.assertIs(weapons[0].weapon, pysa.WEAPON.M4)


if __name__ == "__main__":
    unittest.main()
