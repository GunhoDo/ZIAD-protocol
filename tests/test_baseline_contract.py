import unittest

from experiments.baselines.base import validate_execution_contract


class BaselineExecutionContractTest(unittest.TestCase):
    def test_defaults_are_supported(self):
        memory_policy, calibration = validate_execution_contract(
            {}, baseline_name="PatchCore"
        )

        self.assertEqual("default/SCS", memory_policy)
        self.assertEqual("none", calibration)

    def test_rejects_unsupported_memory_policy(self):
        with self.assertRaisesRegex(RuntimeError, "memory_policy='FIFO'"):
            validate_execution_contract(
                {"memory_policy": "FIFO"}, baseline_name="PatchCore"
            )

    def test_can_allow_baseline_specific_memory_policy(self):
        memory_policy, calibration = validate_execution_contract(
            {"memory_policy": "FIFO"},
            baseline_name="RareCLIP",
            supported_memory_policies={"default/SCS", "FIFO"},
        )

        self.assertEqual("FIFO", memory_policy)
        self.assertEqual("none", calibration)

    def test_rejects_unsupported_calibration(self):
        with self.assertRaisesRegex(RuntimeError, "calibration='temperature_scaling'"):
            validate_execution_contract(
                {"calibration": "temperature_scaling"}, baseline_name="RareCLIP"
            )


if __name__ == "__main__":
    unittest.main()
