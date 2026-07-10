import unittest
from pathlib import Path


class EventTypeTests(unittest.TestCase):
    def test_entity_event_stubs_publish_exact_callback_types(self):
        source = (Path(__file__).parents[1] / "python" / "pysa" /
                  "events.pyi").read_text(encoding="utf-8")

        self.assertIn("Callable[[Vehicle], Any]", source)
        self.assertIn("Callable[[Ped], Any]", source)
        self.assertIn("Callable[[GameObject], Any]", source)
        self.assertIn("Callable[[Vehicle, VEHICLE | int], Any]", source)
        self.assertIn("def on_vehicle_render(fn: _VehicleEvent", source)


if __name__ == "__main__":
    unittest.main()
