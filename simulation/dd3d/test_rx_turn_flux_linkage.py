#!/usr/bin/env python3
"""Tests for per-turn signed RX flux using supplied 3D wire paths."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from filament_model import circular_loop
from rx_turn_flux_linkage import compute_turn_flux


class RxTurnFluxTests(unittest.TestCase):
    def _run(self, reverse_second=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tx = circular_loop(0.12, 128, z_m=0.0).tolist()
            rx1 = circular_loop(0.10, 96, z_m=0.02).tolist()
            rx2 = circular_loop(0.10, 96, z_m=0.025).tolist()
            if reverse_second:
                rx2 = rx2[::-1]
            geometry = {
                "tx_path_m": tx,
                "tx_turns": 20,
                "rx_turns": [
                    {"turn_id": "RX-01", "path_m": rx1},
                    {"turn_id": "RX-02", "path_m": rx2},
                ],
            }
            geometry_path = root / "geometry.json"
            geometry_path.write_text(json.dumps(geometry), encoding="utf-8")
            current_path = root / "current.csv"
            current_path.write_text(
                "time_s,current_a\n0,0\n0.000001,2\n0.000002,-1\n",
                encoding="utf-8")
            output_path = root / "turn_flux.csv"
            compute_turn_flux(geometry_path, current_path, output_path, subdivisions=8)
            with output_path.open(newline="", encoding="utf-8") as stream:
                return list(csv.DictReader(stream))

    def test_outputs_each_turn_at_each_time_sample(self):
        rows = self._run()
        self.assertEqual(len(rows), 6)
        self.assertEqual([(r["turn_id"], float(r["time_s"])) for r in rows],
                         [("RX-01", 0.0), ("RX-02", 0.0),
                          ("RX-01", 1e-6), ("RX-02", 1e-6),
                          ("RX-01", 2e-6), ("RX-02", 2e-6)])
        self.assertAlmostEqual(float(rows[0]["flux_per_turn_Wb"]), 0.0, delta=1e-18)

    def test_reversing_one_turn_reverses_its_signed_flux_only(self):
        forward = self._run(False)
        reversed_rows = self._run(True)
        for i in (0, 2, 4):
            self.assertAlmostEqual(float(forward[i]["flux_per_turn_Wb"]),
                                   float(reversed_rows[i]["flux_per_turn_Wb"]),
                                   delta=abs(float(forward[i]["flux_per_turn_Wb"])) * 1e-12 + 1e-18)
            self.assertAlmostEqual(float(forward[i + 1]["flux_per_turn_Wb"]),
                                   -float(reversed_rows[i + 1]["flux_per_turn_Wb"]),
                                   delta=abs(float(forward[i + 1]["flux_per_turn_Wb"])) * 1e-12 + 1e-18)

    def test_rejects_non_monotonic_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            geometry_path = root / "geometry.json"
            geometry_path.write_text(json.dumps({
                "tx_path_m": circular_loop(0.12, 64).tolist(),
                "tx_turns": 1,
                "rx_turns": [{"turn_id": "1", "path_m": circular_loop(0.1, 64, 0.02).tolist()}],
            }), encoding="utf-8")
            current_path = root / "current.csv"
            current_path.write_text("time_s,current_a\n1,1\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                compute_turn_flux(geometry_path, current_path, root / "out.csv", subdivisions=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
