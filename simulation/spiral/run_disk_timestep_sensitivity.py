"""Measure time-step sensitivity of the reduced disk target model.

All target and coil values are synthetic fixtures. This is a numerical
sensitivity check, not a physical detection-performance prediction.
"""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_disk import Coil, ConductiveDisk, Pulse, receive_peak, simulate


def main() -> None:
    rows = []
    for ring_count in (4, 6, 8):
        disk = ConductiveDisk(
            radius_m=0.012,
            thickness_m=0.001,
            conductivity_s_m=35e6,
            depth_m=0.04,
            rings=ring_count,
        )
        for dt_us in (2.0, 1.0, 0.5, 0.25, 0.125):
            pulse = Pulse(time_step_s=dt_us * 1e-6)
            peak = receive_peak(simulate(Coil(), disk, pulse, ring_segments=96))
            rows.append({
                "rings": ring_count,
                "time_step_us": dt_us,
                "receive_peak_v": f"{peak:.12e}",
                "fixture_only": "true",
            })
            print(rows[-1])

    output = Path("disk_surrogate_timestep_sensitivity.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
