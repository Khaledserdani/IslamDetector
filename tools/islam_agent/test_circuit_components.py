import unittest

from tool_runner import SafeToolRunner
from circuit_components import (
    COMPONENT_LIBRARY, CircuitSchemaError, component_catalog, validate_circuit_v2,
)


def base_spec(parts):
    return {"schema_version": 2, "name": "Mixed signal board", "ground": "GND", "components": parts}


def resistor():
    return {
        "ref": "R1", "type": "resistor",
        "pins": {"1": "VIN", "2": "VOUT"},
        "pin_numbers": {"1": "1", "2": "2"},
        "value": 1000, "unit": "ohm", "rating": {"power_w": 0.25},
    }


def opamp():
    return {
        "ref": "U1", "type": "opamp",
        "pins": {"1": "OUT", "2": "INM", "3": "INP", "4": "VEE", "5": "VCC"},
        # Deliberately explicit: these are package pin numbers, not assumed
        # from a generic op-amp symbol. A real part must use its datasheet map.
        "pin_numbers": {"1": "6", "2": "2", "3": "3", "4": "4", "5": "7"},
        "model_id": "vendor.example:OPAMP_MODEL",
        "package": "SOIC-8",
        "manufacturer_part": "EXAMPLE-OPAMP",
        "pinout_source": "manufacturer datasheet, SOIC-8 pinout table",
    }


class CircuitComponentsTests(unittest.TestCase):
    def test_catalog_contains_multi_pin_semiconductor_and_ic_families(self):
        catalog = component_catalog()
        for kind in ("diode", "bjt_npn", "mosfet_n", "opamp", "timer_555",
                     "logic_gate_2input", "transformer_1p1s", "connector_4"):
            self.assertIn(kind, catalog)
        self.assertEqual(catalog["opamp"]["simulation_model_required"], True)
        self.assertEqual(catalog["mosfet_n"]["pin_number_policy"],
                         "must be supplied from the selected package datasheet")

    def test_accepts_mixed_passive_and_datasheet_mapped_ic(self):
        result = validate_circuit_v2(base_spec([resistor(), opamp()]))
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["component_count"], 2)
        self.assertIn("VCC", result["nodes"])
        self.assertFalse(result["simulation_ready"])
        self.assertEqual(result["models_requiring_independent_verification"], ["U1"])
        self.assertFalse(result["build_ready"])

    def test_rejects_assumed_or_missing_physical_pinout(self):
        part = opamp()
        del part["pin_numbers"]
        with self.assertRaisesRegex(CircuitSchemaError, "physical pin-number map"):
            validate_circuit_v2(base_spec([part]))

    def test_rejects_duplicate_physical_pin_mapping(self):
        part = opamp()
        part["pin_numbers"]["2"] = "6"
        with self.assertRaisesRegex(CircuitSchemaError, "one physical package pin"):
            validate_circuit_v2(base_spec([part]))

    def test_rejects_semiconductor_without_model(self):
        part = {
            "ref": "D1", "type": "diode",
            "pins": {"1": "ANODE", "2": "CATHODE"},
            "pin_numbers": {"1": "1", "2": "2"},
        }
        with self.assertRaisesRegex(CircuitSchemaError, "verified model_id"):
            validate_circuit_v2(base_spec([part]))

    def test_rejects_pin_count_or_number_mismatch(self):
        part = resistor()
        part["pins"] = {"1": "VIN", "3": "VOUT"}
        with self.assertRaisesRegex(CircuitSchemaError, "logical pin keys"):
            validate_circuit_v2(base_spec([part]))

    def test_rejects_wrong_reference_prefix_and_unknown_type(self):
        part = resistor()
        part["ref"] = "C1"
        with self.assertRaisesRegex(CircuitSchemaError, "reference designator"):
            validate_circuit_v2(base_spec([part]))
        part = resistor()
        part["type"] = "invented_device"
        with self.assertRaisesRegex(CircuitSchemaError, "unsupported component"):
            validate_circuit_v2(base_spec([part]))

    def test_rejects_nonfinite_ratings_and_values(self):
        part = resistor()
        part["rating"]["power_w"] = float("inf")
        with self.assertRaisesRegex(CircuitSchemaError, "rating.power_w"):
            validate_circuit_v2(base_spec([part]))
        part = resistor()
        part["value"] = float("nan")
        with self.assertRaisesRegex(CircuitSchemaError, "finite positive"):
            validate_circuit_v2(base_spec([part]))

    def test_agent_runner_validates_multi_pin_design_with_approval(self):
        design = base_spec([resistor(), opamp()])
        proposal = {
            "task_id": "circuit-v2-1",
            "summary_ar": "التحقق من مخطط متعدد الأرجل",
            "steps": [{"kind": "validate_circuit_v2", "target": "circuit_schema_v2", "design": design}],
            "needs_human_approval": True,
            "claims_to_verify": [],
        }
        result = SafeToolRunner().execute_plan(proposal, "circuit-v2-1", human_approved=True)
        self.assertEqual(result[0]["kind"], "validate_circuit_v2")
        self.assertEqual(result[0]["result"]["component_count"], 2)
        self.assertIn("opamp", result[0]["component_catalog"])

    def test_rejects_multiple_push_pull_outputs_on_same_net(self):
        spec = base_spec([
            {"ref":"U1","type":"opamp","pins":{"1":"SHARED","2":"A","3":"B","4":"VEE","5":"VCC"},
             "pin_numbers":{"1":"6","2":"2","3":"3","4":"4","5":"7"},
             "model_id":"M1","pinout_source":"datasheet rev A"},
            {"ref":"U2","type":"opamp","pins":{"1":"SHARED","2":"C","3":"D","4":"VEE2","5":"VCC2"},
             "pin_numbers":{"1":"6","2":"2","3":"3","4":"4","5":"7"},
             "model_id":"M2","pinout_source":"datasheet rev A"},
        ])
        with self.assertRaisesRegex(CircuitSchemaError, "multiple push-pull output"):
            validate_circuit_v2(spec)

    def test_rejects_duplicate_reference_and_unknown_schema_version(self):
        first, second = resistor(), resistor()
        second["pins"] = {"1": "VOUT", "2": "GND"}
        with self.assertRaisesRegex(CircuitSchemaError, "duplicated"):
            validate_circuit_v2(base_spec([first, second]))
        spec = base_spec([resistor()])
        spec["schema_version"] = 1
        with self.assertRaisesRegex(CircuitSchemaError, "version 2"):
            validate_circuit_v2(spec)


if __name__ == "__main__":
    unittest.main()
