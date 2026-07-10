import unittest
from unittest import mock

from enum import IntEnum

from pysa import (CAMERA_MODE, CAR_MISSION, DOOR_LOCK, DRIVING_STYLE,
                  ENTITY_STATUS, MOVE_STATE, VEHICLE, VEHICLE_DOOR,
                  VEHICLE_WHEEL, WEAPON, PED, PICKUP_TYPE, Building, Dummy,
                  Ped, Pickup, Vehicle)
from pysa import _mock, camera, entities, pickups, world
from pysa.enums import VEHICLE_CLASS, VEHICLE_TYPE
from pysa.model_info import PedModelInfo, VehicleModelInfo, model_info


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

    def test_pickup_types_match_plugin_sdk_and_live_pool_is_inspectable(self):
        _mock._reset()
        handle = 77
        _mock._pool["pickup"].append(handle)
        _mock._pickup_info[handle] = (
            355, int(PICKUP_TYPE.ON_STREET), 120, 0, 0.0,
            10.0, 20.0, 30.0, 0x08,
        )

        item = world.pickups[0]

        self.assertIsInstance(item, Pickup)
        self.assertEqual(PICKUP_TYPE.RESPAWNS, 2)
        self.assertEqual(PICKUP_TYPE.ONCE, 3)
        self.assertEqual(PICKUP_TYPE.ONCE_TIMEOUT, 4)
        self.assertIs(item.type, PICKUP_TYPE.ON_STREET)
        self.assertEqual(item.ammo, 120)
        self.assertEqual(tuple(item.pos), (10.0, 20.0, 30.0))
        self.assertTrue(item.visible)
        self.assertTrue(item.exists)

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

    def test_vehicle_model_information_is_typed(self):
        _mock._reset()
        address = 0x30000
        collision = 0x40000
        _mock._model_info[int(VEHICLE.INFERNUS)] = address
        _mock.write_u32(address + 0x14, collision)
        _mock.write_f32(address + 0x18, 300.0)
        _mock.mem_write(address + 0x32, b"INFERNS\0")
        _mock.write_u32(address + 0x3C, VEHICLE_TYPE.AUTOMOBILE)
        _mock.write_f32(address + 0x40, 1.0)
        _mock.write_f32(address + 0x44, 1.1)
        _mock.write_u16(address + 0x4A, 11)
        _mock.write_u8(address + 0x4C, 2)
        _mock.write_u8(address + 0x4D, VEHICLE_CLASS.RICH_FAMILY)
        for offset, value in enumerate((-1.0, -2.0, -0.5, 1.0, 2.0, 1.5)):
            _mock.write_f32(collision + offset * 4, value)

        info = model_info(VEHICLE.INFERNUS)

        self.assertIsInstance(info, VehicleModelInfo)
        self.assertEqual(info.game_name, "INFERNS")
        self.assertIs(info.vehicle_type, VEHICLE_TYPE.AUTOMOBILE)
        self.assertIs(info.vehicle_class, VEHICLE_CLASS.RICH_FAMILY)
        self.assertEqual(info.door_count, 2)
        self.assertEqual(tuple(info.dimensions), (2.0, 4.0, 2.0))

    def test_static_world_entities_are_friendly_read_only_wrappers(self):
        _mock._reset()
        building_addr = 0x50000
        dummy_addr = 0x60000
        matrix_addr = 0x70000
        _mock._pool["building"].append(building_addr)
        _mock._pool["dummy"].append(dummy_addr)
        _mock.write_u16(building_addr + 0x22, 1234)
        _mock.write_u8(building_addr + 0x2F, 2)
        _mock.write_f32(building_addr + 0x4, 10.0)
        _mock.write_f32(building_addr + 0x8, 20.0)
        _mock.write_f32(building_addr + 0xC, 30.0)
        _mock.write_u16(dummy_addr + 0x22, 567)
        _mock.write_u32(dummy_addr + 0x14, matrix_addr)
        _mock.write_f32(matrix_addr + 0x30, 1.0)
        _mock.write_f32(matrix_addr + 0x34, 2.0)
        _mock.write_f32(matrix_addr + 0x38, 3.0)

        buildings = entities.all_buildings()
        dummies = entities.all_dummies()

        self.assertIsInstance(buildings[0], Building)
        self.assertIsInstance(dummies[0], Dummy)
        self.assertEqual(buildings[0].model, 1234)
        self.assertEqual(buildings[0].area, 2)
        self.assertEqual(tuple(buildings[0].pos), (10.0, 20.0, 30.0))
        self.assertEqual(tuple(dummies[0].pos), (1.0, 2.0, 3.0))

    def test_integer_ped_model_gets_specialized_information(self):
        _mock._reset()
        _mock._model_info[int(PED.MALE01)] = 0x80000
        self.assertIsInstance(model_info(int(PED.MALE01)), PedModelInfo)


if __name__ == "__main__":
    unittest.main()
