#!/usr/bin/env python3
"""Convert a GetDP TimeTable A_phi point probe into per-turn magnetic flux."""
from __future__ import annotations
import argparse
import csv
import math
import re
from pathlib import Path

NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][-+]?\d+)?")

def convert(input_path: Path, output_path: Path, radius_m: float,
            expected_z_m: float, min_samples: int = 390) -> None:
    if not math.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("radius_m must be finite and positive")
    rows = []
    for line_no, line in enumerate(input_path.read_text(errors="replace").splitlines(), 1):
        values = []
        for token in NUMBER.findall(line):
            try:
                values.append(float(token.replace("D", "E").replace("d", "e")))
            except ValueError:
                pass
        # GetDP TimeTable: step, time, x, y, z, value for an OnPoint probe.
        if len(values) < 6:
            continue
        step, time_s, x, y, z, a_phi = values[0], values[1], values[2], values[3], values[4], values[-1]
        if not all(math.isfinite(v) for v in (time_s, x, y, z, a_phi)):
            raise ValueError(f"Non-finite numeric value on line {line_no}")
        if abs(x - radius_m) > 1e-6 or abs(y - expected_z_m) > 1e-6 or abs(z) > 1e-6:
            raise ValueError(
                f"Probe coordinates on line {line_no} do not match requested "
                f"(r,z,0)=({radius_m},{expected_z_m},0): got ({x},{y},{z})")
        rows.append((time_s, a_phi))
    if len(rows) < min_samples:
        raise ValueError(f"Expected at least {min_samples} probe rows; found {len(rows)}")
    rows.sort(key=lambda item: item[0])
    if any(rows[i][0] >= rows[i+1][0] for i in range(len(rows)-1)):
        raise ValueError("Probe time values must be unique and strictly increasing")
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "flux_per_turn_Wb"])
        for time_s, a_phi in rows:
            # Stokes/circulation relation for a circular axisymmetric turn:
            # Phi = integral A.dl = 2*pi*r*A_phi.
            writer.writerow([f"{time_s:.12g}", f"{2*math.pi*radius_m*a_phi:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--radius-m", required=True, type=float)
    parser.add_argument("--z-m", required=True, type=float)
    parser.add_argument("--min-samples", type=int, default=390)
    args = parser.parse_args()
    convert(args.input, args.output, args.radius_m, args.z_m, args.min_samples)
    print(f"WROTE {args.output}")


if __name__ == "__main__":
    main()
