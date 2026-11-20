import unittest

from circuit_design import CircuitDesignError, compile_circuit_design, validate_design


def divider():
    return {
        "name": "10V resistor divider",
        "ground": "GND",
        "components": [
            {"ref": "R1", "type": "resistor", "pins": {"1": "VIN", "2": "VOUT"},
             "value": 1000, "unit": "ohm", "rating_power_w": 0.25, "tolerance_pct": 5},
            {"ref": "R2", "type": "resistor", "pins": {"1": "VOUT", "2": "GND"},
             "value": 1000, "unit": "ohm", "rating_power_w": 0.25, "tolerance_pct": 5},
            {"ref": "V1", "type": "dc_voltage_source", "pins": {"1": "VIN", "2": "GND"},
             "value": 10, "unit": "V"},
        ],
    }


class CircuitDesignTests(unittest.TestCase):
    def test_compiles_bom_spice_and_schematic(self):
        result = compile_circuit_design(divider())
        self.assertEqual(result["component_count"], 3)
        self.assertEqual(len(result["bom"]), 2)
        self.assertIn("R1 VIN VOUT 1000", result["spice_netlist"])
        self.assertIn("V1 VIN GND 10", result["spice_netlist"])
        self.assertIn("<svg", result["schematic_svg"])
        self.assertIn("VIN", result["schematic_svg"])
        self.assertIn("pins 1", result["schematic_svg"])

    def test_node_labels_are_the_connectivity_contract(self):
        result = validate_design(divider())
        self.assertEqual(result["nodes"], ["GND", "VIN", "VOUT"])

    def test_rejects_duplicate_reference(self):
        spec = divider()
        spec["components"][1]["ref"] = "R1"
        with self.assertRaises(CircuitDesignError):
            validate_design(spec)

    def test_rejects_missing_component_rating(self):
        spec = divider()
        del spec["components"][0]["rating_power_w"]
        with self.assertRaises(CircuitDesignError):
            validate_design(spec)

    def test_rejects_wrong_pin_schema_and_invalid_unit(self):
        spec = divider()
        spec["components"][0]["pins"] = {"1": "VIN", "3": "VOUT"}
        with self.assertRaises(CircuitDesignError):
            validate_design(spec)
        spec = divider()
        spec["components"][0]["unit"] = "kohm"
        with self.assertRaises(CircuitDesignError):
            validate_design(spec)

    def test_rejects_nonfinite_and_out_of_range_values(self):
        spec = divider()
        spec["components"][0]["value"] = float("nan")
        with self.assertRaises(CircuitDesignError):
            validate_design(spec)
        spec = divider()
        spec["components"][0]["value"] = 0
        with self.assertRaises(CircuitDesignError):
            validate_design(spec)


if __name__ == "__main__":
    unittest.main()
