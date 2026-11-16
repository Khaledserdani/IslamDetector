"""Run independent angular and refined radial sensitivity sweeps."""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_disk import Coil, ConductiveDisk, Pulse, receive_peak, simulate


def evaluate(rings: int, segments: int) -> float:
    # Synthetic software fixture only; not a user-selected or measured target.
    disk = ConductiveDisk(
        radius_m=0.012,
        thickness_m=0.001,
        conductivity_s_m=35e6,
        depth_m=0.04,
        rings=rings,
    )
    return receive_peak(simulate(Coil(), disk, Pulse(time_step_s=1.0e-6),
                                 ring_segments=segments))


def main() -> None:
    rows = []
    sweeps = [
        ("angular", [(6, 48), (6, 64), (6, 96), (6, 128)]),
        ("radial", [(4, 96), (5, 96), (6, 96), (7, 96),
                    (8, 96), (9, 96), (10, 96), (12, 96)]),
    ]
    for sweep_name, cases in sweeps:
        previous = None
        for rings, segments in cases:
            peak = evaluate(rings, segments)
            relative_change = None if previous is None else abs(peak-previous)/max(abs(peak),1e-30)
            row = {
                "sweep": sweep_name,
                "rings": rings,
                "segments_per_ring": segments,
                "receive_peak_v": f"{peak:.12e}",
                "relative_change_from_previous": "" if relative_change is None else f"{relative_change:.8g}",
                "fixture_only": "true",
            }
            rows.append(row)
            print(row)
            previous = peak

    output = Path("disk_surrogate_convergence.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
