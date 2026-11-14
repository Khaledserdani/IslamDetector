#!/usr/bin/env python3
import csv
import tempfile
import unittest
from pathlib import Path

from derive_rx_linkage_voltage import derive_linkage


class RxLinkageVoltageTests(unittest.TestCase):
    def test_faraday_voltage_uses_total_linkage_without_second_turn_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "linkage.csv", Path(tmp) / "voltage.csv"
            source.write_text(
                "time_s,turn_count,flux_linkage_Wb_turn\n"
                "0,30,0\n1,30,2e-6\n2,30,4e-6\n",
                encoding="utf-8")
            derive_linkage(source, target)
            with target.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertAlmostEqual(float(row["rx_open_circuit_V"]), -2e-6)

    def test_rejects_non_increasing_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "linkage.csv", Path(tmp) / "voltage.csv"
            source.write_text(
                "time_s,flux_linkage_Wb_turn\n0,0\n0,1e-6\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                derive_linkage(source, target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
