#!/usr/bin/env python3
"""Derive open-circuit RX voltage from a validated per-turn flux history.

Input CSV contract:
  time_s,flux_per_turn_Wb
The flux column must be the signed flux through one receiver turn (webers),
not B-field, not J2, and not an already turn-multiplied flux linkage.
"""
from __future__ import annotations
import argparse
import csv
import math
from pathlib import Path


def derivative(times: list[float], values: list[float]) -> list[float]:
    """Differentiate on a strictly increasing, possibly nonuniform time grid."""
    n = len(times)
    if n != len(values) or n < 2:
        raise ValueError("At least two paired time/flux samples are required")
    if any(not math.isfinite(x) for x in times + values):
        raise ValueError("Time and flux samples must all be finite")
    h = [times[i + 1] - times[i] for i in range(n - 1)]
    if any(step <= 0 for step in h):
        raise ValueError("time_s must be strictly increasing")

    if n == 2:
        slope = (values[1] - values[0]) / h[0]
        return [slope, slope]

    out = [0.0] * n
    h0, h1 = h[0], h[1]
    out[0] = (-(2*h0 + h1)/(h0*(h0+h1))*values[0]
              + (h0+h1)/(h0*h1)*values[1]
              - h0/(h1*(h0+h1))*values[2])
    for i in range(1, n - 1):
        left, right = h[i - 1], h[i]
        out[i] = (-right/(left*(left+right))*values[i - 1]
                  + (right-left)/(left*right)*values[i]
                  + left/(right*(left+right))*values[i + 1])
    h0, h1 = h[-1], h[-2]
    out[-1] = ((2*h0 + h1)/(h0*(h0+h1))*values[-1]
               - (h0+h1)/(h0*h1)*values[-2]
               + h0/(h1*(h0+h1))*values[-3])
    return out


def load_flux_csv(path: Path) -> tuple[list[float], list[float]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"time_s", "flux_per_turn_Wb"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must contain time_s,flux_per_turn_Wb columns")
        times, flux = [], []
        for line_number, row in enumerate(reader, start=2):
            try:
                times.append(float(row["time_s"]))
                flux.append(float(row["flux_per_turn_Wb"]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value on CSV line {line_number}") from exc
    if len(times) < 2:
        raise ValueError("CSV must contain at least two data rows")
    return times, flux


def derive(input_path: Path, output_path: Path, turns: int) -> None:
    if turns <= 0:
        raise ValueError("turns must be a positive integer")
    times, flux = load_flux_csv(input_path)
    dphi_dt = derivative(times, flux)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "flux_per_turn_Wb", "turns", "rx_open_circuit_V"])
        for t, phi, slope in zip(times, flux, dphi_dt):
            writer.writerow([f"{t:.12g}", f"{phi:.12g}", turns, f"{-turns*slope:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="CSV with time_s,flux_per_turn_Wb")
    parser.add_argument("--output", required=True, type=Path, help="Output voltage CSV")
    parser.add_argument("--turns", required=True, type=int, help="Physical RX turn count")
    args = parser.parse_args()
    derive(args.input, args.output, args.turns)
    print(f"WROTE {args.output}")


if __name__ == "__main__":
    main()
