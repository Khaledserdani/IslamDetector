import csv
import math
import tempfile
import unittest
from pathlib import Path

from convert_rx_probe_to_flux import convert


class RxProbeFluxTests(unittest.TestCase):
    def test_a_phi_to_flux_uses_circular_line_integral(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "probe.txt"
            target = Path(tmp) / "flux.csv"
            source.write_text(
                "0 0.0 0.145 0.045 0.0 0.002\n"
                "1 1e-6 0.145 0.045 0.0 0.003\n",
                encoding="utf-8")
            convert(source, target, 0.145, 0.045, min_samples=2)
            with target.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertAlmostEqual(
                float(rows[0]["flux_per_turn_Wb"]),
                2 * math.pi * 0.145 * 0.002, places=14)

    def test_rejects_wrong_probe_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "probe.txt"
            target = Path(tmp) / "flux.csv"
            source.write_text(
                "0 0.0 0.2 0.045 0.0 0.002\n"
                "1 1e-6 0.2 0.045 0.0 0.003\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                convert(source, target, 0.145, 0.045, min_samples=2)

    def test_rejects_insufficient_probe_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "probe.txt"
            target = Path(tmp) / "flux.csv"
            source.write_text(
                "0 0.0 0.145 0.045 0.0 0.002\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                convert(source, target, 0.145, 0.045, min_samples=2)


if __name__ == "__main__":
    unittest.main()
