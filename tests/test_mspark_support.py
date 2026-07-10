import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

from pysa import (CAMERA_MODE, EXPLOSION_KIND, MISSION_AUDIO_SLOT, GameObject,
                  Ped, Vehicle)
from pysa import _mock, _runtime, audio, entities, fx, markers
from pysa.math3 import Vector3


class MSparkSupportTests(unittest.TestCase):
    def setUp(self):
        _mock._reset()

    def tearDown(self):
        _runtime._clear_registries()

    def test_checkpoint_visual_update_uses_safe_native_bridge(self):
        with mock.patch.object(markers.cmd, "CREATE_CHECKPOINT", return_value=44):
            checkpoint = markers.Checkpoint((1, 2, 3), points_to=(1, 10, 3))

        updated = checkpoint.update_visual(
            (4, 5, 6), (0, 0.5, 0), (255, 128, 64, 32))

        self.assertTrue(updated)
        self.assertEqual(
            _mock._checkpoint_updates[44],
            ((4.0, 5.0, 6.0), (0.0, 0.5, 0.0), (255, 128, 64, 32)),
        )

    def test_reusable_entity_and_audio_helpers_forward_cleanly(self):
        ped = Ped(1)
        vehicle = Vehicle(2)
        obj = GameObject(3)
        with mock.patch.object(entities.cmd, "GET_OFFSET_FROM_CHAR_IN_WORLD_COORDS",
                               return_value=(10.0, 20.0, 30.0)) as offset, \
                mock.patch.object(entities.cmd, "ATTACH_CAR_TO_OBJECT") as attach, \
                mock.patch.object(audio.cmd, "CLEAR_MISSION_AUDIO") as clear:
            self.assertEqual(ped.offset((1, 2, 3)), Vector3(10, 20, 30))
            vehicle.attach_to_object(obj, (0, 7, 0), (1, 2, 3))
            audio.MissionAudio(MISSION_AUDIO_SLOT.SLOT3).clear()

        offset.assert_called_once_with(ped, 1.0, 2.0, 3.0)
        attach.assert_called_once_with(vehicle, obj, 0.0, 7.0, 0.0,
                                       1.0, 2.0, 3.0)
        clear.assert_called_once_with(3)

    def test_effect_helpers_and_explosion_values_are_typed(self):
        self.assertIs(EXPLOSION_KIND.MINE, EXPLOSION_KIND(8))
        with mock.patch.object(fx.cmd, "DRAW_WEAPONSHOP_CORONA") as corona, \
                mock.patch.object(fx.cmd, "DRAW_LIGHT_WITH_RANGE") as light, \
                mock.patch.object(fx.cmd, "ADD_SMOKE_PARTICLE") as smoke:
            fx.weaponshop_corona((1, 2, 3), 4.0, (5, 6, 7), fx.CORONA.STAR)
            fx.light((1, 2, 3), 25.0, (8, 9, 10))
            fx.smoke_particle((1, 2, 3), (4, 5, 6), alpha=0.75)

        corona.assert_called_once_with(1.0, 2.0, 3.0, 4.0, 1, 0, 5, 6, 7)
        light.assert_called_once_with(1.0, 2.0, 3.0, 8, 9, 10, 25.0)
        smoke.assert_called_once()

    def test_mspark_script_imports_and_registers_as_coroutine(self):
        path = Path(__file__).parents[1] / "examples" / "mspark.py"
        spec = importlib.util.spec_from_file_location("test_mspark_script", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)

        self.assertIn(module.mspark, _runtime._task_funcs)
        self.assertIsInstance(module.effect, module.MasterSpark)
        self.assertIsInstance(module.effect.config, module.SparkConfig)
        self.assertIs(CAMERA_MODE.CAM_ON_A_STRING,
                      CAMERA_MODE(module.CAMERA_MODE.CAM_ON_A_STRING))

    def test_mspark_stick_up_raises_the_beam(self):
        path = Path(__file__).parents[1] / "examples" / "mspark.py"
        spec = importlib.util.spec_from_file_location("test_mspark_aim", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)

        effect = module.MasterSpark()
        with mock.patch.object(module.pad, "left_stick_direction",
                               return_value=module.pad.Stick(0.0, 1.0)):
            effect._update_aim(20)
        self.assertEqual(effect.pitch, 1.0)

        with mock.patch.object(module.pad, "left_stick_direction",
                               return_value=module.pad.Stick(0.0, -1.0)):
            effect._update_aim(20)
        self.assertEqual(effect.pitch, 0.0)


if __name__ == "__main__":
    unittest.main()
