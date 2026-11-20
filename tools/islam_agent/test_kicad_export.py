import re
import unittest

from circuit_components import CircuitSchemaError
from kicad_export import _balanced_sexpr, compile_kicad_schematic
from tool_runner import SafeToolRunner


def sample_design():
    return {
        "schema_version": 2,
        "name": "Opamp signal conditioner",
        "ground": "GND",
        "components": [
            {
                "ref": "R1", "type": "resistor",
                "pins": {"1": "VIN", "2": "VPLUS"},
                "pin_numbers": {"1": "1", "2": "2"},
                "value": 10000, "unit": "ohm", "rating": {"power_w": 0.25},
                "package": "0603", "footprint": "Resistor_SMD:R_0603_1608Metric", "manufacturer_part": "GENERIC-10K",
            },
            {
                "ref": "U1", "type": "opamp",
                "pins": {"1": "VOUT", "2": "VMINUS", "3": "VPLUS", "4": "GND", "5": "VCC"},
                "pin_numbers": {"1": "6", "2": "2", "3": "3", "4": "4", "5": "7"},
                "model_id": "vendor.example:OPAMP_MODEL",
                "pinout_source": "manufacturer datasheet, SOIC-8 pinout table",
                "package": "SOIC-8", "manufacturer_part": "EXAMPLE-OPAMP",
            },
        ],
    }


class KiCadExportTests(unittest.TestCase):
    def test_emits_editable_kicad_schematic_and_pin_labels(self):
        result = compile_kicad_schematic(sample_design())
        source = result["kicad_sch"]
        self.assertTrue(source.startswith("(kicad_sch"))
        self.assertIn('(generator "islam-free-agent")', source)
        self.assertIn('(lib_id "ISLAM:ISLAM_R1")', source)
        self.assertIn('(lib_id "ISLAM:ISLAM_U1")', source)
        self.assertIn('(number "6"', source)
        self.assertIn('(label "VOUT"', source)
        self.assertIn('(label "GND"', source)
        self.assertIn('(property "Footprint" "Resistor_SMD:R_0603_1608Metric"', source)
        self.assertIn('(property "ISLAM_Package" "SOIC-8"', source)
        self.assertIn('(property "Simulation_Model_ID" "vendor.example:OPAMP_MODEL"', source)
        self.assertIn('(instances (project "ISLAM"', source)
        self.assertEqual(result["component_count"], 2)
        self.assertEqual(result["pin_count"], 7)
        self.assertEqual(result["net_label_count"], 7)
        self.assertEqual(len(result["bom"]), 2)
        self.assertEqual(result["bom"][0]["quantity"], 1)
        self.assertIn("U1", result["missing_bom_identity"])
        self.assertFalse(result["build_ready"])

    def test_each_pin_gets_one_exact_net_label(self):
        result = compile_kicad_schematic(sample_design())
        labels = re.findall(r'\(label "([^"]+)"', result["kicad_sch"])
        self.assertEqual(len(labels), result["pin_count"])
        self.assertCountEqual(labels, ["VIN", "VPLUS", "VOUT", "VMINUS", "VPLUS", "GND", "VCC"])

    def test_s_expression_balancer_handles_quoted_parentheses_and_escapes(self):
        self.assertTrue(_balanced_sexpr('(root (text "a (b) \\"quoted\\""))'))
        self.assertFalse(_balanced_sexpr('(root (child)'))
        self.assertFalse(_balanced_sexpr('(root))'))

    def test_refuses_invalid_design_before_export(self):
        design = sample_design()
        design["components"][1]["pin_numbers"]["2"] = "6"
        with self.assertRaises(CircuitSchemaError):
            compile_kicad_schematic(design)

    def test_safe_runner_exports_only_after_explicit_approval(self):
        proposal = {
            "task_id": "kicad-export-1",
            "summary_ar": "تصدير مخطط KiCad",
            "steps": [{"kind": "export_kicad_schematic", "target": "kicad_schematic", "design": sample_design()}],
            "needs_human_approval": True,
            "claims_to_verify": [],
        }
        result = SafeToolRunner().execute_plan(proposal, "kicad-export-1", human_approved=True)
        self.assertEqual(result[0]["kind"], "export_kicad_schematic")
        self.assertEqual(result[0]["result"]["filename"], "ISLAM.kicad_sch")
        self.assertIn("(kicad_sch", result[0]["result"]["kicad_sch"])

    def test_project_name_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "project_name"):
            compile_kicad_schematic(sample_design(), "../unsafe")


if __name__ == "__main__":
    unittest.main()
