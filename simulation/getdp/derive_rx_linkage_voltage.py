#!/usr/bin/env python3
"""Derive RX open-circuit voltage from total signed flux-linkage history."""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path

from derive_rx_voltage import derivative


def derive_linkage(input_path: Path, output_path: Path) -> None:
    with input_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"time_s", "flux_linkage_Wb_turn"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must contain time_s,flux_linkage_Wb_turn")
        times, linkage = [], []
        for line_no, row in enumerate(reader, start=2):
            try:
                t = float(row["time_s"])
                value = float(row["flux_linkage_Wb_turn"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid linkage sample on line {line_no}") from exc
            if not math.isfinite(t) or not math.isfinite(value):
                raise ValueError(f"non-finite linkage sample on line {line_no}")
            times.append(t)
            linkage.append(value)
    if len(times) < 2:
        raise ValueError("at least two linkage samples are required")
    voltage = [-slope for slope in derivative(times, linkage)]
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "flux_linkage_Wb_turn", "rx_open_circuit_V"])
        for t, value, volts in zip(times, linkage, voltage):
            writer.writerow([f"{t:.12g}", f"{value:.12g}", f"{volts:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    derive_linkage(args.input, args.output)
    print(f"WROTE {args.output}")


if __name__ == "__main__":
    main()
