import unittest

from ac_network import ACNetworkError, simulate_ac_network
from agent_policy import PolicyViolation, validate_proposal
from tool_runner import SafeToolRunner


class ACNetworkTests(unittest.TestCase):
    def test_multinode_resistive_divider_matches_analytic_phasor(self):
        result = simulate_ac_network({
            "ground": "0", "frequency_hz": 1000.0,
            "resistors": [
                {"a": "in", "b": "mid", "value": 1000.0},
                {"a": "mid", "b": "0", "value": 1000.0},
            ],
            "capacitors": [], "inductors": [],
            "voltage_sources": [{"positive": "in", "negative": "0", "voltage_rms_v": 10.0}],
        })
        self.assertAlmostEqual(result["node_voltages_rms"]["mid"]["magnitude_v"], 5.0, places=9)
        self.assertLess(result["max_kcl_residual_a"], 1e-10)
        self.assertTrue(result["verified_numerically"])

    def test_rc_series_network_has_expected_midpoint_magnitude(self):
        result = simulate_ac_network({
            "ground": "0", "frequency_hz": 1000.0,
            "resistors": [{"a": "in", "b": "out", "value": 1000.0}],
            "capacitors": [{"a": "out", "b": "0", "value": 1e-6}],
            "inductors": [],
            "voltage_sources": [{"positive": "in", "negative": "0", "voltage_rms_v": 10.0}],
        })
        expected = 10.0 / ((1.0 + (2.0 * 3.141592653589793 * 1000.0 * 1000.0e-6) ** 2) ** 0.5)
        self.assertAlmostEqual(result["node_voltages_rms"]["out"]["magnitude_v"], expected, places=7)

    def test_agent_can_execute_only_the_validated_ac_network_lab(self):
        circuit = {
            "ground": "0", "frequency_hz": 1000.0,
            "resistors": [{"a": "in", "b": "0", "value": 1000.0}],
            "capacitors": [], "inductors": [],
            "voltage_sources": [{"positive": "in", "negative": "0", "voltage_rms_v": 2.0}],
        }
        proposal = {
            "task_id": "ac-network-1", "summary_ar": "تحليل شبكة AC",
            "steps": [{"kind": "simulate_ac_network", "target": "linear_ac_network", "circuit": circuit}],
            "needs_human_approval": True, "claims_to_verify": [],
        }
        validate_proposal(proposal, "ac-network-1")
        result = SafeToolRunner().execute_plan(proposal, "ac-network-1", human_approved=True)
        self.assertEqual(result[0]["result"]["laboratory"], "linear_ac_network_mna")
        self.assertTrue(result[0]["result"]["verified_numerically"])

    def test_rejects_unapproved_ac_network_target(self):
        proposal = {
            "task_id": "ac-network-2", "summary_ar": "رفض محرك غير معروف",
            "steps": [{"kind": "simulate_ac_network", "target": "arbitrary", "circuit": {}}],
            "needs_human_approval": True, "claims_to_verify": [],
        }
        with self.assertRaises(PolicyViolation):
            validate_proposal(proposal, "ac-network-2")

    def test_rejects_singular_and_out_of_bounds_networks(self):
        with self.assertRaises(ACNetworkError):
            simulate_ac_network({
                "ground": "0", "frequency_hz": 100.0,
                "resistors": [], "capacitors": [], "inductors": [],
                "voltage_sources": [{"positive": "x", "negative": "0", "voltage_rms_v": 5.0}],
            })
        with self.assertRaises(ACNetworkError):
            simulate_ac_network({
                "ground": "0", "frequency_hz": 0.0,
                "resistors": [{"a": "x", "b": "0", "value": 100.0}],
                "capacitors": [], "inductors": [], "voltage_sources": [],
            })


if __name__ == "__main__":
    unittest.main()
