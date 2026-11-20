import csv
import tempfile
import unittest
from pathlib import Path

from sum_rx_turn_flux_linkage import sum_linkage


class RxFluxLinkageTests(unittest.TestCase):
    def test_sums_signed_flux_of_each_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "turns.csv"
            target = Path(tmp) / "linkage.csv"
            source.write_text(
                "turn_id,time_s,flux_per_turn_Wb\n"
                "1,0,1e-6\n2,0,2e-6\n"
                "1,1e-6,3e-6\n2,1e-6,-1e-6\n",
                encoding="utf-8")
            sum_linkage(source, target, expected_turns=2)
            with target.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertAlmostEqual(float(rows[0]["flux_linkage_Wb_turn"]), 3e-6)
            self.assertAlmostEqual(float(rows[1]["flux_linkage_Wb_turn"]), 2e-6)

    def test_rejects_missing_turn_at_a_time_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "turns.csv"
            target = Path(tmp) / "linkage.csv"
            source.write_text(
                "turn_id,time_s,flux_per_turn_Wb\n"
                "1,0,1e-6\n2,0,2e-6\n1,1e-6,3e-6\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                sum_linkage(source, target, expected_turns=2)

    def test_rejects_duplicate_turn_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "turns.csv"
            target = Path(tmp) / "linkage.csv"
            source.write_text(
                "turn_id,time_s,flux_per_turn_Wb\n"
                "1,0,1e-6\n1,0,2e-6\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                sum_linkage(source, target, expected_turns=1)


if __name__ == "__main__":
    unittest.main()
