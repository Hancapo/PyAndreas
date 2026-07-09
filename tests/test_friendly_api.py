import unittest
from unittest import mock

from enum import IntEnum

from pysa import (CAMERA_MODE, CAR_MISSION, DOOR_LOCK, DRIVING_STYLE,
                  ENTITY_STATUS, MOVE_STATE, VEHICLE, VEHICLE_DOOR,
                  VEHICLE_WHEEL, WEAPON, PED, Ped, Vehicle)
from pysa import _mock, camera, entities, pickups


class FriendlyApiTests(unittest.TestCase):
    def test_vehicle_and_weapon_constants_are_integer_enums(self):
        self.assertIsInstance(VEHICLE.INFERNUS, IntEnum)
        self.assertIsInstance(WEAPON.M4, IntEnum)
        self.assertIsInstance(PED.BMYBOUN, IntEnum)
        self.assertEqual(int(VEHICLE.INFERNUS), 411)
        self.assertEqual(int(WEAPON.M4), 31)
        self.assertEqual(int(PED.BMYBOUN), 163)
        self.assertEqual(len(PED), 265)

    def test_plugin_sdk_behavior_enums_have_exact_values(self):
        self.assertEqual(MOVE_STATE.RUN, 6)
        self.assertEqual(CAMERA_MODE.FIXED, 15)
        self.assertEqual(DRIVING_STYLE.PLOUGH_THROUGH, 3)
        self.assertEqual(CAR_MISSION.RACING, 33)
        self.assertEqual(DOOR_LOCK.COP_CAR, 5)
        self.assertEqual(ENTITY_STATUS.WRECKED, 5)
        self.assertEqual(VEHICLE_DOOR.REAR_RIGHT, 5)
        self.assertEqual(VEHICLE_WHEEL.FRONT_RIGHT, 2)

    def test_vehicle_resolver_prefers_enum_and_keeps_legacy_names(self):
        self.assertEqual(entities.vehicle_id(VEHICLE.INFERNUS), 411)
        self.assertEqual(entities.vehicle_id("infernus"), 411)

    def test_entity_model_properties_return_known_enums(self):
        ped = Ped(7)
        vehicle = Vehicle(8)
        with mock.patch.object(entities.cmd, "GET_CHAR_MODEL", return_value=163), \
                mock.patch.object(entities.cmd, "GET_CAR_MODEL", return_value=411):
            self.assertIs(ped.model, PED.BMYBOUN)
            self.assertIs(vehicle.model, VEHICLE.INFERNUS)

    def test_regular_ped_weapons_facade_accepts_enum(self):
        ped = Ped(7)
        with mock.patch.object(entities.cmd, "GET_WEAPONTYPE_MODEL",
                               return_value=0), \
                mock.patch.object(entities.cmd, "GIVE_WEAPON_TO_CHAR") as give, \
                mock.patch.object(entities.cmd, "SET_CURRENT_CHAR_WEAPON") as equip:
            ped.weapons.give(WEAPON.AK47, ammo=250)

        give.assert_called_once_with(ped, WEAPON.AK47, 250)
        equip.assert_called_once_with(ped, WEAPON.AK47)

    def test_regular_pickup_module_accepts_weapon_enum(self):
        with mock.patch.object(pickups.cmd, "GET_WEAPONTYPE_MODEL",
                               return_value=355) as get_model, \
                mock.patch.object(pickups, "load_model", return_value=True), \
                mock.patch.object(pickups, "release_model"), \
                mock.patch.object(pickups.cmd, "CREATE_PICKUP_WITH_AMMO",
                                  return_value=9):
            result = pickups.weapon((1, 2, 3), WEAPON.AK47, ammo=120)

        self.assertEqual(result.handle, 9)
        get_model.assert_called_once_with(WEAPON.AK47)

    def test_task_and_vehicle_facades_forward_enums(self):
        ped = Ped(7)
        vehicle = Vehicle(8)
        with mock.patch.object(entities.cmd, "TASK_GO_STRAIGHT_TO_COORD") as go, \
                mock.patch.object(entities.cmd, "SET_CAR_DRIVING_STYLE") as style, \
                mock.patch.object(entities.cmd, "LOCK_CAR_DOORS") as lock:
            ped.tasks.go_to((1, 2, 3), MOVE_STATE.SPRINT)
            vehicle.ai.driving_style(DRIVING_STYLE.AVOID_CARS)
            vehicle.doors.lock_status = DOOR_LOCK.LOCKOUT_PLAYER_ONLY

        go.assert_called_once_with(ped, 1.0, 2.0, 3.0, MOVE_STATE.SPRINT, -1)
        style.assert_called_once_with(vehicle, DRIVING_STYLE.AVOID_CARS)
        lock.assert_called_once_with(vehicle, DOOR_LOCK.LOCKOUT_PLAYER_ONLY)

    def test_camera_uses_camera_mode_enum(self):
        ped = Ped(7)
        with mock.patch.object(camera.cmd, "POINT_CAMERA_AT_CHAR") as point:
            camera.point_at(ped, CAMERA_MODE.FOLLOW_PED)
        point.assert_called_once_with(ped, CAMERA_MODE.FOLLOW_PED, 2)

    def test_vehicle_handling_is_typed_and_read_only(self):
        _mock._reset()
        vehicle_ptr = 0x10000
        handling_ptr = 0x20000
        vehicle = Vehicle(_mock.vehicle_handle(vehicle_ptr))
        _mock.write_u32(vehicle_ptr + 0x384, handling_ptr)
        _mock.write_f32(handling_ptr + 0x04, 1400.0)
        _mock.write_f32(handling_ptr + 0x28, 0.8)
        _mock.write_f32(handling_ptr + 0x14, 0.0)
        _mock.write_f32(handling_ptr + 0x18, 0.15)
        _mock.write_f32(handling_ptr + 0x1C, -0.1)

        self.assertAlmostEqual(vehicle.handling.mass, 1400.0)
        self.assertAlmostEqual(vehicle.handling.traction_multiplier, 0.8)
        center = vehicle.handling.center_of_mass
        self.assertAlmostEqual(center.x, 0.0)
        self.assertAlmostEqual(center.y, 0.15)
        self.assertAlmostEqual(center.z, -0.1)
        with self.assertRaises(AttributeError):
            vehicle.handling.mass = 900.0


if __name__ == "__main__":
    unittest.main()
