import csv
import math
import tempfile
import unittest
from pathlib import Path

from derive_rx_voltage import derive, derivative


class RxVoltageTests(unittest.TestCase):
    def test_linear_flux_has_constant_voltage(self):
        times = [0.0, 0.3, 0.9, 1.4]
        flux = [2.0 + 0.25*t for t in times]
        result = derivative(times, flux)
        for value in result:
            self.assertAlmostEqual(value, 0.25, places=12)

    def test_quadratic_flux_exact_on_nonuniform_grid(self):
        times = [0.0, 0.2, 0.75, 1.6]
        flux = [3.0*t*t - 2.0*t + 1.0 for t in times]
        result = derivative(times, flux)
        for t, value in zip(times, result):
            self.assertAlmostEqual(value, 6.0*t - 2.0, places=11)

    def test_turn_count_and_faraday_sign(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "flux.csv"
            target = Path(tmp) / "voltage.csv"
            source.write_text(
                "time_s,flux_per_turn_Wb\n0,0\n1,0.5\n2,1.0\n",
                encoding="utf-8")
            derive(source, target, turns=20)
            with target.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertAlmostEqual(float(row["rx_open_circuit_V"]), -10.0)

    def test_reversing_flux_reverses_voltage_polarity(self):
        times = [0.0, 0.5, 1.0]
        positive = derivative(times, [0.0, 1.0, 2.0])
        negative = derivative(times, [0.0, -1.0, -2.0])
        for a, b in zip(positive, negative):
            self.assertAlmostEqual(a, -b)

    def test_rejects_non_monotonic_time(self):
        with self.assertRaises(ValueError):
            derivative([0.0, 1.0, 0.5], [0.0, 1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
