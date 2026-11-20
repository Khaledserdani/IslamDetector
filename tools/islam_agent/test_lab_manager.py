import unittest
from lab_manager import LabInputError, simulate_dc_resistive_network


class CircuitLabTests(unittest.TestCase):
    def test_divider_matches_hand_calculation_and_kcl(self):
        result = simulate_dc_resistive_network({
            "ground": "0",
            "resistors": [
                {"a": "supply", "b": "mid", "ohms": 1000},
                {"a": "mid", "b": "0", "ohms": 1000},
            ],
            "voltage_sources": [{"positive": "supply", "negative": "0", "volts": 10}],
        })
        self.assertAlmostEqual(result["node_voltages_v"]["mid"], 5.0, places=8)
        self.assertTrue(result["verified_numerically"])
        self.assertLess(result["max_kcl_residual_a"], 1e-8)

    def test_refuses_singular_floating_network(self):
        with self.assertRaises(LabInputError):
            simulate_dc_resistive_network({
                "ground": "0", "resistors": [{"a": "x", "b": "y", "ohms": 1000}],
                "voltage_sources": [],
            })

    def test_rejects_unbounded_or_invalid_component_values(self):
        with self.assertRaises(LabInputError):
            simulate_dc_resistive_network({
                "ground": "0", "resistors": [{"a": "x", "b": "0", "ohms": 0}],
                "voltage_sources": [{"positive": "x", "negative": "0", "volts": 5}],
            })


if __name__ == "__main__":
    unittest.main()
