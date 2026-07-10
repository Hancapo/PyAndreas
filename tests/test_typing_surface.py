import inspect
import unittest
from pathlib import Path

from pysa import Ped, Position, Vehicle, VehicleModel, WeaponId, world
from pysa.entities import Entity, PedWeapons
from pysa.player import PlayerVehicles
from pysa.session import ScriptSession


class TypingSurfaceTests(unittest.TestCase):
    def test_live_collections_preserve_their_member_type(self):
        self.assertEqual(
            world.__annotations__["vehicles"], "EntityCollection[Vehicle]")
        self.assertEqual(
            world.__annotations__["peds"], "EntityCollection[Ped]")
        self.assertEqual(
            inspect.signature(world.EntityCollection.nearest).return_annotation,
            "Optional[TEntity]",
        )

    def test_sessions_and_relationships_return_concrete_entities(self):
        self.assertEqual(
            ScriptSession.track.__annotations__["return"], "TResource")
        self.assertIn(
            "Vehicle", ScriptSession.spawn_vehicle.__annotations__["return"])
        self.assertEqual(
            PlayerVehicles.current.fget.__annotations__["return"],
            "Optional[Vehicle]",
        )

    def test_public_aliases_and_weapon_facade_are_typed(self):
        self.assertIsNotNone(Position)
        self.assertIsNotNone(VehicleModel)
        self.assertIsNotNone(WeaponId)
        self.assertEqual(
            PedWeapons.current.fget.__annotations__["return"], "WeaponId")
        self.assertEqual(Entity.from_ptr.__annotations__["return"], "TEntity")

    def test_generated_native_stub_keeps_domain_wrappers_and_enums(self):
        source = (Path(__file__).parents[1] / "python" / "pysa" /
                  "native.pyi").read_text(encoding="utf-8")
        self.assertIn("pickup: Pickup | int", source)
        self.assertIn("self_: Blip | int", source)
        self.assertIn("buttonId: BUTTON | int", source)
        self.assertIn("type: WEATHER | int", source)
        self.assertIn("drivingStyle: DRIVING_STYLE | int", source)


if __name__ == "__main__":
    unittest.main()
