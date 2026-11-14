#!/usr/bin/env python3
"""Compute signed flux through each explicitly supplied 3D RX turn path."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from filament_model import flux_through_loop


def compute_turn_flux(geometry_path: Path, current_path: Path, output_path: Path,
                      subdivisions: int = 16) -> None:
    if subdivisions < 1:
        raise ValueError("subdivisions must be positive")
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    source = geometry.get("tx_path_m")
    source_turns = geometry.get("tx_turns")
    receivers = geometry.get("rx_turns")
    if not isinstance(source, list) or not isinstance(receivers, list) or not receivers:
        raise ValueError("geometry requires tx_path_m and a non-empty rx_turns list")
    if not isinstance(source_turns, int) or source_turns < 1:
        raise ValueError("tx_turns must be a positive integer")
    turn_ids = []
    for item in receivers:
        if not isinstance(item, dict) or not isinstance(item.get("turn_id"), str):
            raise ValueError("each RX turn requires a string turn_id")
        turn_id = item["turn_id"].strip()
        if not turn_id or turn_id in turn_ids or not isinstance(item.get("path_m"), list):
            raise ValueError("RX turn IDs must be unique and each turn needs path_m")
        turn_ids.append(turn_id)

    samples = []
    with current_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"time_s", "current_a"}.issubset(reader.fieldnames):
            raise ValueError("current CSV must contain time_s,current_a")
        for line_no, row in enumerate(reader, start=2):
            try:
                time_s, current_a = float(row["time_s"]), float(row["current_a"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid current sample on line {line_no}") from exc
            if not math.isfinite(time_s) or not math.isfinite(current_a):
                raise ValueError(f"non-finite current sample on line {line_no}")
            if samples and time_s <= samples[-1][0]:
                raise ValueError("time_s must be strictly increasing")
            samples.append((time_s, current_a))
    if len(samples) < 2:
        raise ValueError("at least two current samples are required")

    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["turn_id", "time_s", "flux_per_turn_Wb"])
        for time_s, current_a in samples:
            for item in receivers:
                flux = flux_through_loop(
                    source, item["path_m"], current_a=current_a,
                    source_turns=source_turns, subdivisions=subdivisions
                )
                writer.writerow([item["turn_id"], f"{time_s:.12g}", f"{flux:.12g}"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--current", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--subdivisions", type=int, default=16)
    args = parser.parse_args()
    compute_turn_flux(args.geometry, args.current, args.output, args.subdivisions)
    print(f"WROTE {args.output}")


if __name__ == "__main__":
    main()
