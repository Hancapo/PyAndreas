import unittest

from pysa import EXPLOSION_KIND, WEAPON, VehicleDamageEvent
from pysa import _mock, game_events
from pysa.entities import Ped, Vehicle


class FakeHook:
    def __init__(self, this=0, ints=None, floats=None):
        self.this = this
        self.ints = dict(ints or {})
        self.floats = dict(floats or {})
        self.skipped = None

    def arg(self, slot):
        return self.ints.get(slot, 0)

    def argf(self, slot):
        return self.floats.get(slot, 0.0)

    def set_arg(self, slot, value):
        self.ints[slot] = value

    def set_argf(self, slot, value):
        self.floats[slot] = value

    def skip(self, value=0):
        self.skipped = value


class GameEventPayloadTests(unittest.TestCase):
    def setUp(self):
        _mock._reset()
        game_events._handlers.clear()

    def tearDown(self):
        game_events._handlers.clear()

    def test_vehicle_damage_dispatches_specific_typed_payload(self):
        vehicle_ptr = 0x10000
        attacker_ptr = 0x20000
        _mock.write_u8(attacker_ptr + 0x36, 3)  # ENTITY_TYPE_PED
        received = []
        game_events._handlers["vehicle_damage"] = [received.append]
        raw = FakeHook(vehicle_ptr, {0: attacker_ptr, 1: int(WEAPON.M4)},
                       {2: 75.0})
        dispatch = game_events._make_dispatch(
            "vehicle_damage", "vehicle",
            {"attacker": (0, "entity"), "weapon": (1, "weapon"),
             "amount": (2, "float")},
            "CVehicle",
        )

        dispatch(raw)
        event = received[0]

        self.assertIsInstance(event, VehicleDamageEvent)
        self.assertIsInstance(event.vehicle, Vehicle)
        self.assertIsInstance(event.attacker, Ped)
        self.assertIs(event.weapon, WEAPON.M4)
        self.assertEqual(event.amount, 75.0)
        event.amount = 25.0
        self.assertEqual(raw.floats[2], 25.0)

    def test_explosion_kind_is_an_enum_and_unknown_values_survive(self):
        known = game_events.ExplosionEvent(
            FakeHook(ints={0: 4}), {"kind": (0, "explosion")}, None,
            "CExplosion",
        )
        custom = game_events.ExplosionEvent(
            FakeHook(ints={0: 99}), {"kind": (0, "explosion")}, None,
            "CExplosion",
        )

        self.assertIs(known.kind, EXPLOSION_KIND.CAR)
        self.assertEqual(custom.kind, 99)


if __name__ == "__main__":
    unittest.main()
