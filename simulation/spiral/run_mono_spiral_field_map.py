"""Generate a magnetostatic B-field map for the continuous Mono Spiral path.

Run from this directory:
    python run_mono_spiral_field_map.py

The CSV is a numerical field reference only; it is not a PI transient,
eddy-current, soil, receiver, or detection-depth simulation.
"""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_geometry import MonoSpiral


def main() -> None:
    coil = MonoSpiral()
    output = Path("mono_spiral_magnetostatic_field_map.csv")
    heights_m = (0.04, 0.08, 0.12)
    coordinates_m = tuple(index * 0.02 for index in range(-10, 11))
    rows = []

    for z_m in heights_m:
        for y_m in coordinates_m:
            for x_m in coordinates_m:
                bx, by, bz = coil.magnetic_field_tesla(
                    (x_m, y_m, z_m), current_a=1.0, segments_per_side=80
                )
                magnitude = (bx * bx + by * by + bz * bz) ** 0.5
                rows.append({
                    "x_m": f"{x_m:.4f}",
                    "y_m": f"{y_m:.4f}",
                    "z_m": f"{z_m:.4f}",
                    "current_a": "1.0",
                    "bx_t_per_a": f"{bx:.12e}",
                    "by_t_per_a": f"{by:.12e}",
                    "bz_t_per_a": f"{bz:.12e}",
                    "b_magnitude_t_per_a": f"{magnitude:.12e}",
                    "model": "continuous_filament_magnetostatic",
                })

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} field samples to {output}")
    for z_m in heights_m:
        center = next(row for row in rows
                      if float(row["x_m"]) == 0.0
                      and float(row["y_m"]) == 0.0
                      and float(row["z_m"]) == z_m)
        print(f"z={z_m:.2f} m: Bz={float(center['bz_t_per_a'])*1e6:.6f} uT/A")


if __name__ == "__main__":
    main()
