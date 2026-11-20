import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kicad_export import compile_kicad_schematic


def design():
    return {
        "schema_version": 2,
        "name": "KiCad CLI integration validation",
        "ground": "GND",
        "components": [
            {
                "ref": "R1", "type": "resistor",
                "pins": {"1": "VIN", "2": "VOUT"},
                "pin_numbers": {"1": "1", "2": "2"},
                "value": 10000, "unit": "ohm", "rating": {"power_w": 0.25},
                "package": "0603", "manufacturer_part": "GENERIC-10K",
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


class KiCadCliIntegrationTests(unittest.TestCase):
    def test_kicad_cli_parses_and_exports_generated_schematic(self):
        executable = shutil.which("kicad-cli")
        self.assertIsNotNone(executable, "kicad-cli must be installed in this validation job")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ISLAM.kicad_sch"
            netlist = root / "ISLAM.net"
            source.write_text(compile_kicad_schematic(design())["kicad_sch"], encoding="utf-8")
            result = subprocess.run(
                [executable, "sch", "export", "netlist", "--output", str(netlist), str(source)],
                cwd=root, shell=False, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(netlist.is_file(), result.stdout)
            netlist_text = netlist.read_text(encoding="utf-8")
            self.assertIn("R1", netlist_text)
            self.assertIn("U1", netlist_text)
            self.assertIn("VOUT", netlist_text)

    def test_kicad_cli_renders_generated_schematic_to_svg(self):
        executable = shutil.which("kicad-cli")
        self.assertIsNotNone(executable, "kicad-cli must be installed in this validation job")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ISLAM.kicad_sch"
            output = root / "svg"
            output.mkdir()
            source.write_text(compile_kicad_schematic(design())["kicad_sch"], encoding="utf-8")
            result = subprocess.run(
                [executable, "sch", "export", "svg", "--output", str(output), str(source)],
                cwd=root, shell=False, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(list(output.glob("*.svg")), result.stdout)

    def test_kicad_cli_generates_erc_report_without_claiming_zero_violations(self):
        executable = shutil.which("kicad-cli")
        self.assertIsNotNone(executable, "kicad-cli must be installed in this validation job")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ISLAM.kicad_sch"
            report = root / "ISLAM-erc.rpt"
            source.write_text(compile_kicad_schematic(design())["kicad_sch"], encoding="utf-8")
            result = subprocess.run(
                [executable, "sch", "erc", "--output", str(report), "--severity-all", str(source)],
                cwd=root, shell=False, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=120, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(report.is_file(), result.stdout)
            report_text = report.read_text(encoding="utf-8")
            self.assertTrue(report_text.strip(), "KiCad ERC report must not be empty")
            # Report generation is verified; this test does not interpret an
            # unreviewed prototype's violations as a clean ERC.


if __name__ == "__main__":
    unittest.main()
