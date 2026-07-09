import unittest
from unittest import mock

from pysa import Vehicle
from pysa import native


class NativeCommandTests(unittest.TestCase):
    def test_typed_command_packs_inputs_and_wraps_entity_output(self):
        with mock.patch.object(native._pysa, "call",
                               return_value=(True, (17,))) as bridge:
            result = native.cmd.CREATE_CAR(411, 1, 2.5, 3)

        self.assertIsInstance(result, Vehicle)
        self.assertEqual(result.handle, 17)
        bridge.assert_called_once_with(0x00A5, "ifffI", 411, 1.0, 2.5, 3.0)

    def test_condition_command_returns_boolean(self):
        with mock.patch.object(native._pysa, "call",
                               return_value=(False, ())):
            self.assertIs(native.cmd.IS_CHAR_IN_ANY_CAR(3), False)

    def test_conditional_outputs_return_none_when_condition_fails(self):
        sig = (0x1234, "i", "I", native.FLAG_COND, "value", "output", "")
        with mock.patch.object(native._pysa, "call",
                               return_value=(False, (99,))):
            self.assertIsNone(native._invoke("TEST", sig, (1,)))

    def test_manual_call_preserves_output_kinds(self):
        with mock.patch.object(native._pysa, "call",
                               return_value=(True, (3, 2.5, "ok"))) as bridge:
            result = native.call(0x1234, 7, native.Out.INT,
                                 native.Out.FLOAT, native.Out.STR)

        self.assertEqual(result, (3, 2.5, "ok"))
        bridge.assert_called_once_with(0x1234, "iIFS", 7)

    def test_bad_argument_count_has_readable_signature(self):
        with self.assertRaisesRegex(TypeError, "CREATE_CAR"):
            native.cmd.CREATE_CAR(411)

    def test_unknown_command_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown script command"):
            native.call("THIS_COMMAND_DOES_NOT_EXIST")


if __name__ == "__main__":
    unittest.main()
