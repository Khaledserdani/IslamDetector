"""Run a reproducible mesh/ring-count sensitivity sweep for the disk surrogate."""
from __future__ import annotations

import csv
from pathlib import Path

from mono_spiral_disk import Coil, ConductiveDisk, Pulse, receive_peak, simulate


def main() -> None:
    coil = Coil()
    pulse = Pulse(time_step_s=1.0e-6)
    # Synthetic software fixture only; not a user-selected or measured target.
    cases = [(3, 32), (4, 48), (6, 64), (8, 96)]
    output = Path("disk_surrogate_convergence.csv")
    previous = None
    rows = []
    for ring_count, segment_count in cases:
        disk = ConductiveDisk(
            radius_m=0.012,
            thickness_m=0.001,
            conductivity_s_m=35e6,
            depth_m=0.04,
            rings=ring_count,
        )
        peak = receive_peak(simulate(coil, disk, pulse, ring_segments=segment_count))
        relative_change = None if previous is None else abs(peak-previous)/max(abs(peak),1e-30)
        rows.append({
            "rings": ring_count,
            "segments_per_ring": segment_count,
            "receive_peak_v": f"{peak:.12e}",
            "relative_change_from_previous": "" if relative_change is None else f"{relative_change:.8g}",
            "fixture_only": "true",
        })
        previous = peak

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
