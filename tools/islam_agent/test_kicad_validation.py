import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from kicad_validation import (
    KiCadCliUnavailable, KiCadValidationError, validate_kicad_design,
)


def design():
    return {
        "schema_version": 2, "name": "CLI test", "ground": "GND",
        "components": [{
            "ref": "R1", "type": "resistor",
            "pins": {"1": "VIN", "2": "GND"},
            "pin_numbers": {"1": "1", "2": "2"},
            "value": 1000, "unit": "ohm", "rating": {"power_w": 0.25},
            "package": "0603", "footprint": "Resistor_SMD:R_0603_1608Metric",
            "manufacturer_part": "GENERIC-1K",
        }],
    }


class KiCadValidationTests(unittest.TestCase):
    @patch("kicad_validation.shutil.which", return_value="/usr/bin/kicad-cli")
    @patch("kicad_validation.subprocess.run")
    def test_runs_only_fixed_netlist_svg_and_erc_commands(self, run, which):
        def fake_run(command, **kwargs):
            self.assertIs(kwargs["shell"], False)
            if command[1] == "version":
                return CompletedProcess(command, 0, stdout="9.0.8")
            output = Path(command[command.index("--output") + 1])
            if command[3] == "netlist":
                output.write_text("(export (components (comp (ref R1))))", encoding="utf-8")
            elif command[3] == "svg":
                output.mkdir(exist_ok=True)
                (output / "page.svg").write_text("<svg/>", encoding="utf-8")
            elif command[2] == "erc":
                output.write_text("ERC report: 0 errors, 1 warning", encoding="utf-8")
            return CompletedProcess(command, 0, stdout="completed")
        run.side_effect = fake_run
        result = validate_kicad_design(design())
        self.assertEqual(result["kicad_cli_version"], "9.0.8")
        self.assertTrue(result["schematic_parsed"])
        self.assertTrue(result["netlist_exported"])
        self.assertTrue(result["svg_rendered"])
        self.assertTrue(result["erc_report_generated"])
        self.assertEqual(result["erc_status"], "review_required")
        self.assertIn("1 warning", result["erc_report"])
        self.assertFalse(result["build_ready"])
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][1:], ["version"])
        self.assertEqual(commands[1][1:4], ["sch", "export", "netlist"])
        self.assertEqual(commands[2][1:4], ["sch", "export", "svg"])
        self.assertEqual(commands[3][1:3], ["sch", "erc"])

    @patch("kicad_validation.shutil.which", return_value=None)
    def test_reports_cli_unavailable_without_claiming_validation(self, which):
        with self.assertRaises(KiCadCliUnavailable):
            validate_kicad_design(design())

    @patch("kicad_validation.subprocess.run")
    @patch("kicad_validation.shutil.which", return_value="/usr/bin/kicad-cli")
    def test_rejects_invalid_design_before_running_cli(self, which, run):
        spec = design()
        spec["components"][0]["pin_numbers"]["2"] = "1"
        with self.assertRaisesRegex(ValueError, "one physical package pin"):
            validate_kicad_design(spec)
        run.assert_not_called()

    @patch("kicad_validation.shutil.which", return_value="/usr/bin/kicad-cli")
    @patch("kicad_validation.subprocess.run")
    def test_timeout_is_reported_as_validation_failure(self, run, which):
        from subprocess import TimeoutExpired
        run.side_effect = TimeoutExpired("kicad-cli", 120)
        with self.assertRaisesRegex(KiCadValidationError, "timed out"):
            validate_kicad_design(design())


if __name__ == "__main__":
    unittest.main()
