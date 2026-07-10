import unittest

from pysa import signature
from pysa.signatures import PARAM_TYPES


class SignatureTypeTests(unittest.TestCase):
    def test_common_scm_parameters_keep_their_domain_types(self):
        self.assertEqual(
            PARAM_TYPES["GIVE_WEAPON_TO_CHAR"],
            ("Char", "WeaponType", "int"),
        )
        self.assertEqual(
            PARAM_TYPES["CREATE_CAR"],
            ("model_vehicle", "float", "float", "float"),
        )

    def test_runtime_signature_shows_friendly_types(self):
        text = signature("GIVE_WEAPON_TO_CHAR")
        self.assertIn("self: Ped", text)
        self.assertIn("weaponType: WEAPON", text)


if __name__ == "__main__":
    unittest.main()
