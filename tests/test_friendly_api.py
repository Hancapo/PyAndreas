import unittest
from unittest import mock
import importlib
import math

from enum import IntEnum

from pysa import (AREA, CAMERA_MODE, CAR_MISSION, DOOR_LOCK, DRIVING_STYLE,
                  ENTITY_STATUS, MOVE_STATE, VEHICLE, VEHICLE_DOOR,
                  VEHICLE_WHEEL, WEAPON, PED, PICKUP_TYPE, Building, Dummy,
                  EntryExit, Ped, Pickup, Placement, Vehicle, Cutscene, Train)
from pysa import _mock, blips, camera, entities, game, pickups, trains, world
from pysa.enums import VEHICLE_CLASS, VEHICLE_TYPE
from pysa.model_info import PedModelInfo, VehicleModelInfo, model_info
player_module = importlib.import_module("pysa.player")


class FriendlyApiTests(unittest.TestCase):
    def test_map_waypoint_is_a_vector_or_none(self):
        with mock.patch.object(blips._pysa, "waypoint",
                               return_value=(123.0, -456.0, 0.0)):
            point = blips.waypoint()
        assert point is not None
        self.assertEqual(tuple(point), (123.0, -456.0, 0.0))

        with mock.patch.object(blips._pysa, "waypoint", return_value=None):
            self.assertIsNone(blips.waypoint())

    def test_blip_facade_exposes_lifecycle_and_options(self):
        marker = blips.Blip(12)
        with mock.patch.object(blips.cmd, "DOES_BLIP_EXIST", return_value=True), \
                mock.patch.object(blips.cmd, "SET_BLIP_AS_FRIENDLY") as friendly, \
                mock.patch.object(blips.cmd, "SET_BLIP_ALWAYS_DISPLAY_ON_ZOOMED_RADAR") as zoom:
            self.assertTrue(marker.exists)
            marker.set_friendly()
            marker.keep_on_zoomed_radar()
        friendly.assert_called_once_with(marker, True)
        zoom.assert_called_once_with(marker, True)

    def test_short_range_and_contact_blips_are_wrapped(self):
        sprite = next(iter(blips.BLIP_SPRITE))
        with mock.patch.object(blips.cmd, "ADD_SHORT_RANGE_SPRITE_BLIP_FOR_COORD",
                               return_value=21), \
                mock.patch.object(blips.cmd, "ADD_SPRITE_BLIP_FOR_CONTACT_POINT",
                                  return_value=22):
            nearby = blips.add_short_range((1, 2, 3), sprite)
            mission = blips.add_contact_point((4, 5, 6), sprite)
        self.assertEqual(nearby.handle, 21)
        self.assertEqual(mission.handle, 22)

    def test_camera_move_track_and_attachment_are_friendly(self):
        ped, vehicle = Ped(7), Vehicle(8)
        with mock.patch.object(camera.cmd, "ATTACH_CAMERA_TO_CHAR_LOOK_AT_VEHICLE") as attach, \
                mock.patch.object(camera.cmd, "CAMERA_SET_VECTOR_MOVE") as move, \
                mock.patch.object(camera.cmd, "CAMERA_SET_VECTOR_TRACK") as track:
            camera.attach_to(ped, (1, 2, 3), look_at=vehicle,
                             switch=camera.SWITCH.SMOOTH)
            camera.move((0, 0, 0), (10, 20, 30), 1500)
            camera.track((1, 1, 1), (2, 2, 2), 500, ease=False)
        attach.assert_called_once_with(
            ped, 1.0, 2.0, 3.0, vehicle, 0.0, camera.SWITCH.SMOOTH)
        move.assert_called_once_with(0.0, 0.0, 0.0, 10.0, 20.0, 30.0, 1500, True)
        track.assert_called_once_with(1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 500, False)

    def test_game_facade_types_language_and_clamps_radar_zoom(self):
        with mock.patch.object(game.cmd, "GET_CURRENT_LANGUAGE", return_value=4), \
                mock.patch.object(game.cmd, "SET_RADAR_ZOOM") as zoom:
            self.assertIs(game.language(), game.LANGUAGE.SPANISH)
            game.set_radar_zoom(999)
        zoom.assert_called_once_with(170)

    def test_cutscene_object_owns_named_workflow(self):
        scene = Cutscene("intro")
        with mock.patch("pysa.cutscenes.cmd.LOAD_CUTSCENE") as load, \
                mock.patch("pysa.cutscenes.cmd.SET_CUTSCENE_OFFSET") as offset, \
                mock.patch("pysa.cutscenes.cmd.START_CUTSCENE") as start:
            self.assertIs(scene.load((10, 20, 30)), scene)
            scene.start()
        load.assert_called_once_with("intro")
        offset.assert_called_once_with(10.0, 20.0, 30.0)
        start.assert_called_once_with()

    def test_world_date_roads_and_roadblocks(self):
        with mock.patch.object(world.cmd, "GET_CURRENT_DATE", return_value=(11, 7)), \
                mock.patch.object(world.cmd, "GET_CLOSEST_STRAIGHT_ROAD",
                                  return_value=(1, 2, 3, 4, 5, 6, 90.0)), \
                mock.patch.object(world.cmd, "CREATE_SCRIPT_ROADBLOCK") as roadblock:
            self.assertEqual(world.get_date(), (11, 7))
            road = world.closest_straight_road((0, 0, 0))
            world.add_roadblock((1, 2, 3), (4, 5, 6), kind=2)
        self.assertEqual(tuple(road.start), (1, 2, 3))
        self.assertEqual(tuple(road.end), (4, 5, 6))
        self.assertEqual(road.angle, 90.0)
        roadblock.assert_called_once_with(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 2)

    def test_train_spawn_returns_specialized_vehicle(self):
        with mock.patch.object(trains.cmd, "CREATE_MISSION_TRAIN", return_value=44), \
                mock.patch.object(trains.cmd, "SET_TRAIN_CRUISE_SPEED") as cruise, \
                mock.patch.object(trains.cmd, "SET_TRAIN_SPEED") as speed:
            train = trains.spawn(0, (10, 20, 30))
            train.set_speed(12.5)
        self.assertIsInstance(train, Train)
        self.assertEqual(train.handle, 44)
        cruise.assert_called_once_with(train, 12.5)
        speed.assert_called_once_with(train, 12.5)

    def test_vehicle_and_weapon_constants_are_integer_enums(self):
        self.assertIsInstance(VEHICLE.INFERNUS, IntEnum)
        self.assertIsInstance(WEAPON.M4, IntEnum)
        self.assertIsInstance(PED.BMYBOUN, IntEnum)
        self.assertEqual(int(VEHICLE.INFERNUS), 411)
        self.assertEqual(int(WEAPON.M4), 31)
        self.assertEqual(int(PED.BMYBOUN), 163)
        self.assertEqual(len(PED), 265)

    def test_plugin_sdk_behavior_enums_have_exact_values(self):
        self.assertEqual(AREA.OUTSIDE, 0)
        self.assertEqual(AREA.INTERIOR_18, 18)
        self.assertEqual(int(AREA(42)), 42)
        self.assertEqual(AREA(42).name, "CUSTOM_42")
        self.assertEqual(MOVE_STATE.RUN, 6)
        self.assertEqual(CAMERA_MODE.FIXED, 15)
        self.assertEqual(DRIVING_STYLE.PLOUGH_THROUGH, 3)
        self.assertEqual(CAR_MISSION.RACING, 33)
        self.assertEqual(DOOR_LOCK.COP_CAR, 5)
        self.assertEqual(ENTITY_STATUS.WRECKED, 5)
        self.assertEqual(VEHICLE_DOOR.REAR_RIGHT, 5)
        self.assertEqual(VEHICLE_WHEEL.FRONT_RIGHT, 2)

    def test_player_location_exposes_enex_as_structured_data(self):
        player = player_module.player
        ped = Ped(7)
        with mock.patch.object(type(player), "ped",
                               new_callable=mock.PropertyMock,
                               return_value=ped), \
                mock.patch.object(entities.cmd, "GET_CHAR_AREA_VISIBLE",
                                  return_value=3), \
                mock.patch.object(player_module.cmd,
                                  "GET_NAME_OF_ENTRY_EXIT_CHAR_USED",
                                  return_value="AMMUN1"), \
                mock.patch.object(player_module.cmd,
                                  "GET_POSITION_OF_ENTRY_EXIT_CHAR_USED",
                                  return_value=(10.0, 20.0, 30.0, math.pi / 2)):
            enex = player.location.last_entry_exit

        self.assertIsInstance(enex, EntryExit)
        assert enex is not None
        self.assertEqual(enex.name, "AMMUN1")
        self.assertEqual(enex.exterior,
                         Placement((10, 20, 30), 90, AREA.OUTSIDE))

    def test_player_location_teleport_synchronizes_outside_state(self):
        player = player_module.player
        ped = Ped(7)
        destination = Placement((100, 200, 12), 45, AREA.OUTSIDE)
        with mock.patch.object(type(player), "ped",
                               new_callable=mock.PropertyMock,
                               return_value=ped), \
                mock.patch.object(type(player), "vehicle",
                                  new_callable=mock.PropertyMock,
                                  return_value=None), \
                mock.patch.object(player_module.cmd, "SET_AREA_VISIBLE") as world_area, \
                mock.patch.object(entities.cmd, "SET_CHAR_AREA_VISIBLE") as char_area, \
                mock.patch.object(player_module.cmd, "REQUEST_COLLISION") as collision, \
                mock.patch.object(player_module.cmd, "LOAD_SCENE_IN_DIRECTION") as scene, \
                mock.patch.object(entities.cmd, "SET_CHAR_COORDINATES") as coords, \
                mock.patch.object(entities.cmd, "SET_CHAR_HEADING") as set_heading, \
                mock.patch.object(player_module.cmd,
                                  "FORCE_INTERIOR_LIGHTING_FOR_PLAYER") as lighting:
            result = player.location.teleport(destination)

        self.assertEqual(result, destination)
        world_area.assert_called_once_with(AREA.OUTSIDE)
        char_area.assert_called_once_with(ped, AREA.OUTSIDE)
        collision.assert_called_once_with(100.0, 200.0)
        scene.assert_called_once_with(100.0, 200.0, 12.0, 45.0)
        coords.assert_called_once_with(ped, 100.0, 200.0, 12.0)
        set_heading.assert_called_once_with(ped, 45.0)
        lighting.assert_called_once_with(player.index, False)

    def test_player_location_teleport_carries_current_vehicle(self):
        player = player_module.player
        ped, vehicle = Ped(7), Vehicle(8)
        destination = Placement((50, 60, 7), 180, AREA.INTERIOR_2)
        with mock.patch.object(type(player), "ped",
                               new_callable=mock.PropertyMock,
                               return_value=ped), \
                mock.patch.object(type(player), "vehicle",
                                  new_callable=mock.PropertyMock,
                                  return_value=vehicle), \
                mock.patch.object(player_module.cmd, "SET_AREA_VISIBLE"), \
                mock.patch.object(entities.cmd, "SET_CHAR_AREA_VISIBLE"), \
                mock.patch.object(player_module.cmd,
                                  "SET_VEHICLE_AREA_VISIBLE") as vehicle_area, \
                mock.patch.object(entities.cmd, "SET_CAR_COORDINATES") as coords, \
                mock.patch.object(entities.cmd, "SET_CAR_HEADING") as heading, \
                mock.patch.object(entities.cmd, "SET_CHAR_COORDINATES") as ped_coords:
            player.location.teleport(destination, load_scene=False)

        vehicle_area.assert_called_once_with(vehicle, AREA.INTERIOR_2)
        coords.assert_called_once_with(vehicle, 50.0, 60.0, 7.0)
        heading.assert_called_once_with(vehicle, 180.0)
        ped_coords.assert_not_called()

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

    def test_player_skin_change_streams_model_before_using_it(self):
        player = player_module.player

        with mock.patch.object(type(player), "playing",
                               new_callable=mock.PropertyMock,
                               return_value=True), \
                mock.patch.object(type(player), "ped",
                                  new_callable=mock.PropertyMock,
                                  return_value=Ped(7)), \
                mock.patch.object(Ped, "_ptr_of",
                                  new=staticmethod(lambda _handle: 0x1000)), \
                mock.patch.object(player_module, "load_model",
                                  return_value=True) as load, \
                mock.patch.object(player_module, "release_model") as release, \
                mock.patch.object(player_module.cmd, "SET_PLAYER_MODEL") as set_model:
            player.clothes.set_model(PED.WMYMECH)

        load.assert_called_once_with(int(PED.WMYMECH))
        set_model.assert_called_once_with(player.index, int(PED.WMYMECH))
        release.assert_called_once_with(int(PED.WMYMECH))

    def test_player_skin_change_stops_when_streaming_fails(self):
        player = player_module.player

        with mock.patch.object(type(player), "playing",
                               new_callable=mock.PropertyMock,
                               return_value=True), \
                mock.patch.object(type(player), "ped",
                                  new_callable=mock.PropertyMock,
                                  return_value=Ped(7)), \
                mock.patch.object(Ped, "_ptr_of",
                                  new=staticmethod(lambda _handle: 0x1000)), \
                mock.patch.object(player_module, "load_model",
                                  return_value=False), \
                mock.patch.object(player_module.cmd, "SET_PLAYER_MODEL") as set_model:
            with self.assertRaisesRegex(RuntimeError, "failed to load"):
                player.clothes.set_model(PED.WMYMECH)
        set_model.assert_not_called()

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
